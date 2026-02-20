"""
Comprehensive tests for the TransactionService.
"""

from decimal import Decimal

import pytest

from core_banking.models.enums import (
    AccountStatus,
    CustomerAccountType,
    TransactionStatus,
    TransactionType,
)
from core_banking.services.account_service import AccountService
from core_banking.services.transaction_service import TransactionService
from core_banking.schemas.account import CustomerCreate, AccountOpen, AccountStatusUpdate
from core_banking.schemas.transaction import (
    DepositRequest,
    WithdrawalRequest,
    TransferRequest,
)


def setup_active_account(db_session, email="test@test.com"):
    """Helper: create customer + active checking account."""
    acct_service = AccountService(db_session)
    customer = acct_service.create_customer(CustomerCreate(
        first_name="Test", last_name="User", email=email,
    ))
    db_session.commit()

    account = acct_service.open_account(AccountOpen(
        customer_id=customer.id,
        account_type=CustomerAccountType.CHECKING,
    ))
    db_session.commit()

    acct_service.change_status(account.id, AccountStatusUpdate(
        new_status=AccountStatus.ACTIVE, reason="KYC approved",
    ))
    db_session.commit()

    return account


# --- Deposit Tests ---

class TestDeposit:

    def test_deposit_succeeds(self, db_session):
        account = setup_active_account(db_session)
        service = TransactionService(db_session)

        txn = service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("1000.00"),
            idempotency_key="dep-001",
        ))
        db_session.commit()

        assert txn.status == TransactionStatus.COMPLETED
        assert txn.transaction_type == TransactionType.DEPOSIT
        assert txn.amount == Decimal("1000.00")
        assert txn.completed_at is not None

    def test_deposit_updates_balance(self, db_session):
        account = setup_active_account(db_session)
        service = TransactionService(db_session)
        acct_service = AccountService(db_session)

        service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key="dep-002",
        ))
        db_session.commit()

        balance = acct_service.get_balance(account.id)
        assert balance == Decimal("500.00")

    def test_deposit_idempotency(self, db_session):
        account = setup_active_account(db_session)
        service = TransactionService(db_session)

        first = service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key="dep-same",
        ))
        db_session.commit()

        second = service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key="dep-same",
        ))

        assert first.id == second.id

        # Balance should be 500, not 1000
        acct_service = AccountService(db_session)
        assert acct_service.get_balance(account.id) == Decimal("500.00")

    def test_deposit_to_inactive_account_rejected(self, db_session):
        account = setup_active_account(db_session)
        acct_service = AccountService(db_session)
        acct_service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.FROZEN, reason="Test",
        ))
        db_session.commit()

        service = TransactionService(db_session)
        with pytest.raises(ValueError, match="not active"):
            service.deposit(DepositRequest(
                account_id=account.id,
                amount=Decimal("100.00"),
                idempotency_key="dep-frozen",
            ))


# --- Withdrawal Tests ---

class TestWithdrawal:

    def _fund_account(self, db_session, account, amount="1000.00"):
        service = TransactionService(db_session)
        service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal(amount),
            idempotency_key=f"fund-{account.id}-{amount}",
        ))
        db_session.commit()

    def test_withdrawal_succeeds(self, db_session):
        account = setup_active_account(db_session)
        self._fund_account(db_session, account, "1000.00")

        service = TransactionService(db_session)
        txn = service.withdraw(WithdrawalRequest(
            account_id=account.id,
            amount=Decimal("300.00"),
            idempotency_key="wd-001",
        ))
        db_session.commit()

        assert txn.status == TransactionStatus.COMPLETED
        assert txn.transaction_type == TransactionType.WITHDRAWAL

    def test_withdrawal_updates_balance(self, db_session):
        account = setup_active_account(db_session)
        self._fund_account(db_session, account, "1000.00")

        service = TransactionService(db_session)
        service.withdraw(WithdrawalRequest(
            account_id=account.id,
            amount=Decimal("300.00"),
            idempotency_key="wd-002",
        ))
        db_session.commit()

        acct_service = AccountService(db_session)
        assert acct_service.get_balance(account.id) == Decimal("700.00")

    def test_insufficient_balance_rejected(self, db_session):
        account = setup_active_account(db_session)
        self._fund_account(db_session, account, "100.00")

        service = TransactionService(db_session)
        with pytest.raises(ValueError, match="Insufficient balance"):
            service.withdraw(WithdrawalRequest(
                account_id=account.id,
                amount=Decimal("500.00"),
                idempotency_key="wd-nsf",
            ))

    def test_withdrawal_idempotency(self, db_session):
        account = setup_active_account(db_session)
        self._fund_account(db_session, account, "1000.00")

        service = TransactionService(db_session)
        first = service.withdraw(WithdrawalRequest(
            account_id=account.id,
            amount=Decimal("200.00"),
            idempotency_key="wd-same",
        ))
        db_session.commit()

        second = service.withdraw(WithdrawalRequest(
            account_id=account.id,
            amount=Decimal("200.00"),
            idempotency_key="wd-same",
        ))

        assert first.id == second.id

        acct_service = AccountService(db_session)
        assert acct_service.get_balance(account.id) == Decimal("800.00")


# --- Transfer Tests ---

class TestTransfer:

    def _fund_account(self, db_session, account, amount="1000.00"):
        service = TransactionService(db_session)
        service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal(amount),
            idempotency_key=f"fund-{account.id}-{amount}",
        ))
        db_session.commit()

    def test_transfer_succeeds(self, db_session):
        acct_a = setup_active_account(db_session, "a@test.com")
        acct_b = setup_active_account(db_session, "b@test.com")
        self._fund_account(db_session, acct_a, "1000.00")

        service = TransactionService(db_session)
        txn = service.transfer(TransferRequest(
            source_account_id=acct_a.id,
            destination_account_id=acct_b.id,
            amount=Decimal("400.00"),
            idempotency_key="xfr-001",
        ))
        db_session.commit()

        assert txn.status == TransactionStatus.COMPLETED
        assert txn.transaction_type == TransactionType.TRANSFER

    def test_transfer_updates_both_balances(self, db_session):
        acct_a = setup_active_account(db_session, "a@test.com")
        acct_b = setup_active_account(db_session, "b@test.com")
        self._fund_account(db_session, acct_a, "1000.00")

        service = TransactionService(db_session)
        service.transfer(TransferRequest(
            source_account_id=acct_a.id,
            destination_account_id=acct_b.id,
            amount=Decimal("400.00"),
            idempotency_key="xfr-002",
        ))
        db_session.commit()

        acct_service = AccountService(db_session)
        assert acct_service.get_balance(acct_a.id) == Decimal("600.00")
        assert acct_service.get_balance(acct_b.id) == Decimal("400.00")

    def test_transfer_insufficient_balance_rejected(self, db_session):
        acct_a = setup_active_account(db_session, "a@test.com")
        acct_b = setup_active_account(db_session, "b@test.com")
        self._fund_account(db_session, acct_a, "100.00")

        service = TransactionService(db_session)
        with pytest.raises(ValueError, match="Insufficient balance"):
            service.transfer(TransferRequest(
                source_account_id=acct_a.id,
                destination_account_id=acct_b.id,
                amount=Decimal("500.00"),
                idempotency_key="xfr-nsf",
            ))

    def test_transfer_to_same_account_rejected(self, db_session):
        acct = setup_active_account(db_session)
        self._fund_account(db_session, acct, "1000.00")

        service = TransactionService(db_session)
        with pytest.raises(ValueError, match="same account"):
            service.transfer(TransferRequest(
                source_account_id=acct.id,
                destination_account_id=acct.id,
                amount=Decimal("100.00"),
                idempotency_key="xfr-self",
            ))


# --- Reversal Tests ---

class TestReversal:

    def test_reverse_deposit(self, db_session):
        account = setup_active_account(db_session)
        service = TransactionService(db_session)

        txn = service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key="dep-rev",
        ))
        db_session.commit()

        reversal = service.reverse(txn.id, "rev-001")
        db_session.commit()

        assert reversal.status == TransactionStatus.COMPLETED
        assert reversal.transaction_type == TransactionType.REVERSAL
        assert reversal.reference_transaction_id == txn.id

        # Original marked as reversed
        assert txn.status == TransactionStatus.REVERSED

        # Balance back to zero
        acct_service = AccountService(db_session)
        assert acct_service.get_balance(account.id) == Decimal("0")

    def test_reverse_nonexistent_rejected(self, db_session):
        service = TransactionService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.reverse(999, "rev-bad")

    def test_reverse_already_reversed_rejected(self, db_session):
        account = setup_active_account(db_session)
        service = TransactionService(db_session)

        txn = service.deposit(DepositRequest(
            account_id=account.id,
            amount=Decimal("500.00"),
            idempotency_key="dep-rev2",
        ))
        db_session.commit()

        service.reverse(txn.id, "rev-002")
        db_session.commit()

        with pytest.raises(ValueError, match="only reverse completed"):
            service.reverse(txn.id, "rev-003")


# --- Ledger Integrity After Transactions ---

class TestLedgerIntegrity:

    def test_ledger_balanced_after_all_operations(self, db_session):
        """After deposits, withdrawals, transfers, and reversals
        the ledger must still balance."""
        from core_banking.services.ledger_service import LedgerService

        acct_a = setup_active_account(db_session, "a@test.com")
        acct_b = setup_active_account(db_session, "b@test.com")
        service = TransactionService(db_session)

        # Deposit into A
        service.deposit(DepositRequest(
            account_id=acct_a.id,
            amount=Decimal("5000.00"),
            idempotency_key="integrity-dep",
        ))
        db_session.commit()

        # Transfer A -> B
        service.transfer(TransferRequest(
            source_account_id=acct_a.id,
            destination_account_id=acct_b.id,
            amount=Decimal("2000.00"),
            idempotency_key="integrity-xfr",
        ))
        db_session.commit()

        # Withdraw from B
        service.withdraw(WithdrawalRequest(
            account_id=acct_b.id,
            amount=Decimal("500.00"),
            idempotency_key="integrity-wd",
        ))
        db_session.commit()

        # Reverse the withdrawal
        wd_txn = db_session.execute(
            __import__('sqlalchemy').select(
                __import__('core_banking.models.transaction', fromlist=['Transaction']).Transaction
            ).where(
                __import__('core_banking.models.transaction', fromlist=['Transaction']).Transaction.idempotency_key == "integrity-wd"
            )
        ).scalar_one()
        service.reverse(wd_txn.id, "integrity-rev")
        db_session.commit()

        # Ledger must balance
        ledger = LedgerService(db_session)
        result = ledger.check_integrity()
        assert result["is_balanced"] is True
