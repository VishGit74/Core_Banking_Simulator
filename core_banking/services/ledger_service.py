"""
Ledger service — the core of the banking system.

This service enforces the fundamental rules:
1. Every transaction must balance (debits = credits)
2. Entries are immutable (append-only)
3. Accounts must exist and be active
4. Currency must match between entry and account

No other service writes to the ledger directly.
All financial operations go through this service.
"""

from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core_banking.models.ledger_account import LedgerAccount
from core_banking.models.ledger_entry import LedgerEntry
from core_banking.models.enums import AccountType, EntryType
from core_banking.schemas.ledger import (
    PostEntriesRequest,
    LedgerAccountCreate,
)


class LedgerService:
    """
    All ledger operations pass through this service.

    The service takes a database session as a constructor
    argument. This means the caller controls the transaction
    boundary — they decide when to commit or rollback.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_account(self, request: LedgerAccountCreate) -> LedgerAccount:
        """
        Create a new ledger account.

        Raises ValueError if the account code already exists.
        """
        existing = self.db.execute(
            select(LedgerAccount).where(LedgerAccount.code == request.code)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Account with code '{request.code}' already exists")

        account = LedgerAccount(
            code=request.code,
            name=request.name,
            account_type=request.account_type,
            currency=request.currency,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def post_entries(self, request: PostEntriesRequest) -> list[LedgerEntry]:
        """
        Post a balanced set of ledger entries as a single transaction.

        This is the most critical method in the entire system.
        It enforces:
        - All referenced accounts exist and are active
        - All accounts match the transaction currency
        - Total debits equal total credits
        - The transaction_id hasn't been used before

        If any check fails, nothing is written. The caller
        is responsible for calling db.commit() after this
        method returns successfully.
        """

        # --- Check for duplicate transaction_id ---
        existing = self.db.execute(
            select(LedgerEntry).where(
                LedgerEntry.transaction_id == request.transaction_id
            ).limit(1)
        ).scalar_one_or_none()

        if existing:
            # Idempotency: return the existing entries
            entries = self.db.execute(
                select(LedgerEntry).where(
                    LedgerEntry.transaction_id == request.transaction_id
                )
            ).scalars().all()
            return list(entries)

        # --- Validate all accounts ---
        account_ids = {entry.account_id for entry in request.entries}
        accounts = self.db.execute(
            select(LedgerAccount).where(LedgerAccount.id.in_(account_ids))
        ).scalars().all()

        accounts_by_id = {a.id: a for a in accounts}

        # Check all accounts exist
        missing = account_ids - set(accounts_by_id.keys())
        if missing:
            raise ValueError(f"Accounts not found: {missing}")

        # Check all accounts are active
        for account_id, account in accounts_by_id.items():
            if not account.is_active:
                raise ValueError(
                    f"Account {account.code} is not active"
                )

        # Check currency matches
        for account_id, account in accounts_by_id.items():
            if account.currency != request.currency:
                raise ValueError(
                    f"Account {account.code} currency is "
                    f"{account.currency}, transaction currency "
                    f"is {request.currency}"
                )

        # --- Enforce balance rule ---
        total_debits = sum(
            e.amount for e in request.entries
            if e.entry_type == EntryType.DEBIT
        )
        total_credits = sum(
            e.amount for e in request.entries
            if e.entry_type == EntryType.CREDIT
        )

        if total_debits != total_credits:
            raise ValueError(
                f"Transaction does not balance: "
                f"debits={total_debits}, credits={total_credits}"
            )

        # --- Create entries ---
        ledger_entries = []
        for entry_data in request.entries:
            entry = LedgerEntry(
                transaction_id=request.transaction_id,
                account_id=entry_data.account_id,
                entry_type=entry_data.entry_type,
                amount=entry_data.amount,
                currency=request.currency,
                description=entry_data.description,
            )
            self.db.add(entry)
            ledger_entries.append(entry)

        self.db.flush()
        return ledger_entries

    def get_account_balance(self, account_id: int) -> Decimal:
        """
        Calculate an account's balance from its entries.

        Balance is never stored — it's always derived from
        the entries. This guarantees the balance is correct
        as long as the entries are correct.

        For ASSET and EXPENSE accounts: balance = debits - credits
        For LIABILITY, EQUITY, and REVENUE: balance = credits - debits
        """
        account = self.db.execute(
            select(LedgerAccount).where(LedgerAccount.id == account_id)
        ).scalar_one_or_none()

        if not account:
            raise ValueError(f"Account {account_id} not found")

        # Sum debits
        total_debits = self.db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.entry_type == EntryType.DEBIT,
            )
        ).scalar()

        # Sum credits
        total_credits = self.db.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.entry_type == EntryType.CREDIT,
            )
        ).scalar()

        # Direction depends on account type
        if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            return Decimal(str(total_debits)) - Decimal(str(total_credits))
        else:
            return Decimal(str(total_credits)) - Decimal(str(total_debits))

    def get_entries_by_account(self, account_id: int) -> list[LedgerEntry]:
        """Return all entries for an account, newest first."""
        entries = self.db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
        ).scalars().all()
        return list(entries)

    def get_entries_by_transaction(
        self, transaction_id
    ) -> list[LedgerEntry]:
        """Return all entries for a transaction."""
        entries = self.db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.transaction_id == transaction_id)
        ).scalars().all()
        return list(entries)
