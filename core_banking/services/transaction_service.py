"""
Transaction service — deposits, withdrawals, and transfers.

Each operation:
1. Checks idempotency (has this key been used before?)
2. Validates the accounts (exist, active, correct currency)
3. Validates business rules (sufficient balance for withdrawals)
4. Creates the transaction record
5. Posts the ledger entries through LedgerService
6. Marks the transaction as completed

If anything fails, the transaction is marked FAILED with
an error message. The caller controls the commit.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_banking.models.account import Account
from core_banking.models.transaction import Transaction
from core_banking.models.enums import (
    AccountStatus,
    TransactionType,
    TransactionStatus,
    EntryType,
    AccountType,
)
from core_banking.schemas.transaction import (
    DepositRequest,
    WithdrawalRequest,
    TransferRequest,
)
from core_banking.schemas.ledger import (
    PostEntriesRequest,
    LedgerEntryCreate,
    LedgerAccountCreate,
)
from core_banking.services.ledger_service import LedgerService


# The bank needs a cash account to post deposits and withdrawals against.
# This is the code for that internal account.
CASH_ACCOUNT_CODE = "BANK-CASH-001"


class TransactionService:

    def __init__(self, db: Session):
        self.db = db
        self.ledger_service = LedgerService(db)

    def _check_idempotency(self, idempotency_key: str) -> Transaction | None:
        """Return existing transaction if key was used before."""
        return self.db.execute(
            select(Transaction).where(
                Transaction.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()

    def _validate_account(
        self, account_id: int, currency: str
    ) -> Account:
        """Validate that an account exists, is active, and matches currency."""
        account = self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if account.status != AccountStatus.ACTIVE:
            raise ValueError(
                f"Account {account_id} is not active "
                f"(status: {account.status.value})"
            )
        if account.currency != currency:
            raise ValueError(
                f"Account {account_id} currency is {account.currency}, "
                f"transaction currency is {currency}"
            )
        return account

    def _get_or_create_cash_account(self, currency: str):
        """
        Get the bank's internal cash account, creating it if needed.

        This is the counterparty for deposits and withdrawals.
        When a customer deposits cash, the bank's cash account
        is debited (asset increases) and the customer's account
        is credited (liability increases).
        """
        from core_banking.models.ledger_account import LedgerAccount
        cash = self.db.execute(
            select(LedgerAccount).where(
                LedgerAccount.code == CASH_ACCOUNT_CODE
            )
        ).scalar_one_or_none()

        if not cash:
            cash = self.ledger_service.create_account(LedgerAccountCreate(
                code=CASH_ACCOUNT_CODE,
                name="Bank Cash Account",
                account_type=AccountType.ASSET,
                currency=currency,
            ))
            self.db.flush()

        return cash

    def deposit(self, request: DepositRequest) -> Transaction:
        """
        Process a cash deposit into a customer account.

        Accounting:
            DEBIT  Bank Cash (asset increases — bank has more cash)
            CREDIT Customer Account (liability increases — bank owes more)
        """
        # Idempotency check
        existing = self._check_idempotency(request.idempotency_key)
        if existing:
            return existing

        # Validate
        account = self._validate_account(request.account_id, request.currency)
        cash = self._get_or_create_cash_account(request.currency)

        # Create transaction record
        ledger_txn_id = uuid.uuid4()
        txn = Transaction(
            idempotency_key=request.idempotency_key,
            transaction_type=TransactionType.DEPOSIT,
            status=TransactionStatus.PROCESSING,
            destination_account_id=account.id,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            ledger_transaction_id=ledger_txn_id,
        )
        self.db.add(txn)
        self.db.flush()

        # Post ledger entries
        try:
            self.ledger_service.post_entries(PostEntriesRequest(
                transaction_id=ledger_txn_id,
                currency=request.currency,
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                    LedgerEntryCreate(
                        account_id=account.ledger_account_id,
                        entry_type=EntryType.CREDIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                ],
            ))
            txn.status = TransactionStatus.COMPLETED
            txn.completed_at = datetime.utcnow()
        except Exception as e:
            txn.status = TransactionStatus.FAILED
            txn.error_message = str(e)
            raise

        self.db.flush()
        return txn

    def withdraw(self, request: WithdrawalRequest) -> Transaction:
        """
        Process a cash withdrawal from a customer account.

        Checks sufficient balance before proceeding.

        Accounting:
            DEBIT  Customer Account (liability decreases — bank owes less)
            CREDIT Bank Cash (asset decreases — bank has less cash)
        """
        existing = self._check_idempotency(request.idempotency_key)
        if existing:
            return existing

        account = self._validate_account(request.account_id, request.currency)
        cash = self._get_or_create_cash_account(request.currency)

        # Check sufficient balance
        balance = self.ledger_service.get_account_balance(
            account.ledger_account_id
        )
        if balance < request.amount:
            raise ValueError(
                f"Insufficient balance: available={balance}, "
                f"requested={request.amount}"
            )

        ledger_txn_id = uuid.uuid4()
        txn = Transaction(
            idempotency_key=request.idempotency_key,
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.PROCESSING,
            source_account_id=account.id,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            ledger_transaction_id=ledger_txn_id,
        )
        self.db.add(txn)
        self.db.flush()

        try:
            self.ledger_service.post_entries(PostEntriesRequest(
                transaction_id=ledger_txn_id,
                currency=request.currency,
                entries=[
                    LedgerEntryCreate(
                        account_id=account.ledger_account_id,
                        entry_type=EntryType.DEBIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.CREDIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                ],
            ))
            txn.status = TransactionStatus.COMPLETED
            txn.completed_at = datetime.utcnow()
        except Exception as e:
            txn.status = TransactionStatus.FAILED
            txn.error_message = str(e)
            raise

        self.db.flush()
        return txn

    def transfer(self, request: TransferRequest) -> Transaction:
        """
        Transfer money between two customer accounts.

        Checks sufficient balance on source account.

        Accounting:
            DEBIT  Source Customer Account (liability decreases)
            CREDIT Destination Customer Account (liability increases)
        """
        existing = self._check_idempotency(request.idempotency_key)
        if existing:
            return existing

        if request.source_account_id == request.destination_account_id:
            raise ValueError("Cannot transfer to the same account")

        source = self._validate_account(
            request.source_account_id, request.currency
        )
        destination = self._validate_account(
            request.destination_account_id, request.currency
        )

        # Check sufficient balance on source
        balance = self.ledger_service.get_account_balance(
            source.ledger_account_id
        )
        if balance < request.amount:
            raise ValueError(
                f"Insufficient balance: available={balance}, "
                f"requested={request.amount}"
            )

        ledger_txn_id = uuid.uuid4()
        txn = Transaction(
            idempotency_key=request.idempotency_key,
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.PROCESSING,
            source_account_id=source.id,
            destination_account_id=destination.id,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            ledger_transaction_id=ledger_txn_id,
        )
        self.db.add(txn)
        self.db.flush()

        try:
            self.ledger_service.post_entries(PostEntriesRequest(
                transaction_id=ledger_txn_id,
                currency=request.currency,
                entries=[
                    LedgerEntryCreate(
                        account_id=source.ledger_account_id,
                        entry_type=EntryType.DEBIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                    LedgerEntryCreate(
                        account_id=destination.ledger_account_id,
                        entry_type=EntryType.CREDIT,
                        amount=request.amount,
                        description=request.description,
                    ),
                ],
            ))
            txn.status = TransactionStatus.COMPLETED
            txn.completed_at = datetime.utcnow()
        except Exception as e:
            txn.status = TransactionStatus.FAILED
            txn.error_message = str(e)
            raise

        self.db.flush()
        return txn

    def reverse(self, transaction_id: int, idempotency_key: str) -> Transaction:
        """
        Reverse a completed transaction by posting offsetting entries.

        The original transaction is not modified — a new REVERSAL
        transaction is created that points to the original.
        This maintains the full audit trail.
        """
        existing = self._check_idempotency(idempotency_key)
        if existing:
            return existing

        original = self.db.get(Transaction, transaction_id)
        if not original:
            raise ValueError(f"Transaction {transaction_id} not found")
        if original.status != TransactionStatus.COMPLETED:
            raise ValueError(
                f"Can only reverse completed transactions "
                f"(status: {original.status.value})"
            )
        if original.status == TransactionStatus.REVERSED:
            raise ValueError("Transaction already reversed")

        # Build reversal ledger entries — mirror the original but swap debit/credit
        original_entries = self.ledger_service.get_entries_by_transaction(
            original.ledger_transaction_id
        )

        reversal_ledger_txn_id = uuid.uuid4()
        reversal_entries = []
        for entry in original_entries:
            reversed_type = (
                EntryType.CREDIT
                if entry.entry_type == EntryType.DEBIT
                else EntryType.DEBIT
            )
            reversal_entries.append(LedgerEntryCreate(
                account_id=entry.account_id,
                entry_type=reversed_type,
                amount=entry.amount,
                description=f"Reversal: {entry.description}",
            ))

        txn = Transaction(
            idempotency_key=idempotency_key,
            transaction_type=TransactionType.REVERSAL,
            status=TransactionStatus.PROCESSING,
            source_account_id=original.source_account_id,
            destination_account_id=original.destination_account_id,
            amount=original.amount,
            currency=original.currency,
            description=f"Reversal of transaction {original.id}",
            reference_transaction_id=original.id,
            ledger_transaction_id=reversal_ledger_txn_id,
        )
        self.db.add(txn)
        self.db.flush()

        try:
            self.ledger_service.post_entries(PostEntriesRequest(
                transaction_id=reversal_ledger_txn_id,
                currency=original.currency,
                entries=reversal_entries,
            ))
            txn.status = TransactionStatus.COMPLETED
            txn.completed_at = datetime.utcnow()
            original.status = TransactionStatus.REVERSED
        except Exception as e:
            txn.status = TransactionStatus.FAILED
            txn.error_message = str(e)
            raise

        self.db.flush()
        return txn

    def get_transaction(self, transaction_id: int) -> Transaction:
        """Get a transaction by ID."""
        txn = self.db.get(Transaction, transaction_id)
        if not txn:
            raise ValueError(f"Transaction {transaction_id} not found")
        return txn
