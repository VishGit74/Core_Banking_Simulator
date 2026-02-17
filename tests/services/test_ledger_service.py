"""
Comprehensive tests for the LedgerService.

Tests cover:
- Account creation and uniqueness
- Balanced entry posting
- Unbalanced entry rejection
- Balance calculation for all account types
- Idempotency (duplicate transaction_id)
- Currency mismatch detection
- Inactive account rejection
"""

import uuid
from decimal import Decimal

import pytest

from core_banking.models.enums import AccountType, EntryType
from core_banking.services.ledger_service import LedgerService
from core_banking.schemas.ledger import (
    LedgerAccountCreate,
    PostEntriesRequest,
    LedgerEntryCreate,
)


# --- Helper to reduce repetition ---

def make_account(service, code, name, account_type, currency="USD"):
    """Create a ledger account and return it."""
    return service.create_account(LedgerAccountCreate(
        code=code,
        name=name,
        account_type=account_type,
        currency=currency,
    ))


# --- Account Creation Tests ---

class TestCreateAccount:

    def test_create_account_succeeds(self, db_session):
        service = LedgerService(db_session)
        account = make_account(
            service, "CASH-001", "Cash", AccountType.ASSET
        )
        db_session.commit()

        assert account.id is not None
        assert account.code == "CASH-001"
        assert account.account_type == AccountType.ASSET
        assert account.is_active is True

    def test_duplicate_code_rejected(self, db_session):
        service = LedgerService(db_session)
        make_account(service, "CASH-001", "Cash", AccountType.ASSET)
        db_session.commit()

        with pytest.raises(ValueError, match="already exists"):
            make_account(service, "CASH-001", "Cash Again", AccountType.ASSET)


# --- Post Entries Tests ---

class TestPostEntries:

    def test_balanced_transaction_succeeds(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        entries = service.post_entries(PostEntriesRequest(
            currency="USD",
            entries=[
                LedgerEntryCreate(
                    account_id=cash.id,
                    entry_type=EntryType.DEBIT,
                    amount=Decimal("500.00"),
                    description="Cash deposit",
                ),
                LedgerEntryCreate(
                    account_id=deposit.id,
                    entry_type=EntryType.CREDIT,
                    amount=Decimal("500.00"),
                    description="Cash deposit",
                ),
            ],
        ))
        db_session.commit()

        assert len(entries) == 2
        assert entries[0].amount == Decimal("500.00")

    def test_unbalanced_transaction_rejected(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        with pytest.raises(ValueError, match="does not balance"):
            service.post_entries(PostEntriesRequest(
                currency="USD",
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal("500.00"),
                        description="Cash deposit",
                    ),
                    LedgerEntryCreate(
                        account_id=deposit.id,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal("300.00"),
                        description="Cash deposit",
                    ),
                ],
            ))

    def test_nonexistent_account_rejected(self, db_session):
        service = LedgerService(db_session)

        with pytest.raises(ValueError, match="not found"):
            service.post_entries(PostEntriesRequest(
                currency="USD",
                entries=[
                    LedgerEntryCreate(
                        account_id=999,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                    LedgerEntryCreate(
                        account_id=998,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                ],
            ))

    def test_inactive_account_rejected(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        cash.is_active = False
        db_session.commit()

        with pytest.raises(ValueError, match="not active"):
            service.post_entries(PostEntriesRequest(
                currency="USD",
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                    LedgerEntryCreate(
                        account_id=deposit.id,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                ],
            ))

    def test_currency_mismatch_rejected(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        with pytest.raises(ValueError, match="currency"):
            service.post_entries(PostEntriesRequest(
                currency="EUR",
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                    LedgerEntryCreate(
                        account_id=deposit.id,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal("100.00"),
                        description="Test",
                    ),
                ],
            ))

    def test_idempotency_returns_existing_entries(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        txn_id = uuid.uuid4()

        request = PostEntriesRequest(
            transaction_id=txn_id,
            currency="USD",
            entries=[
                LedgerEntryCreate(
                    account_id=cash.id,
                    entry_type=EntryType.DEBIT,
                    amount=Decimal("250.00"),
                    description="Deposit",
                ),
                LedgerEntryCreate(
                    account_id=deposit.id,
                    entry_type=EntryType.CREDIT,
                    amount=Decimal("250.00"),
                    description="Deposit",
                ),
            ],
        )

        first_result = service.post_entries(request)
        db_session.commit()

        second_result = service.post_entries(request)

        assert len(first_result) == len(second_result)
        assert first_result[0].id == second_result[0].id


# --- Balance Calculation Tests ---

class TestGetAccountBalance:

    def test_asset_account_balance(self, db_session):
        """Asset accounts: balance = debits - credits."""
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        # Deposit 1000
        service.post_entries(PostEntriesRequest(
            currency="USD",
            entries=[
                LedgerEntryCreate(
                    account_id=cash.id,
                    entry_type=EntryType.DEBIT,
                    amount=Decimal("1000.00"),
                    description="Deposit",
                ),
                LedgerEntryCreate(
                    account_id=deposit.id,
                    entry_type=EntryType.CREDIT,
                    amount=Decimal("1000.00"),
                    description="Deposit",
                ),
            ],
        ))
        db_session.commit()

        balance = service.get_account_balance(cash.id)
        assert balance == Decimal("1000.00")

    def test_liability_account_balance(self, db_session):
        """Liability accounts: balance = credits - debits."""
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        service.post_entries(PostEntriesRequest(
            currency="USD",
            entries=[
                LedgerEntryCreate(
                    account_id=cash.id,
                    entry_type=EntryType.DEBIT,
                    amount=Decimal("750.00"),
                    description="Deposit",
                ),
                LedgerEntryCreate(
                    account_id=deposit.id,
                    entry_type=EntryType.CREDIT,
                    amount=Decimal("750.00"),
                    description="Deposit",
                ),
            ],
        ))
        db_session.commit()

        balance = service.get_account_balance(deposit.id)
        assert balance == Decimal("750.00")

    def test_multiple_transactions_accumulate(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        # Two deposits: 500 + 300 = 800
        for amount in ["500.00", "300.00"]:
            service.post_entries(PostEntriesRequest(
                currency="USD",
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal(amount),
                        description="Deposit",
                    ),
                    LedgerEntryCreate(
                        account_id=deposit.id,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal(amount),
                        description="Deposit",
                    ),
                ],
            ))
        db_session.commit()

        assert service.get_account_balance(cash.id) == Decimal("800.00")
        assert service.get_account_balance(deposit.id) == Decimal("800.00")

    def test_new_account_has_zero_balance(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        db_session.commit()

        assert service.get_account_balance(cash.id) == Decimal("0")

    def test_nonexistent_account_raises_error(self, db_session):
        service = LedgerService(db_session)

        with pytest.raises(ValueError, match="not found"):
            service.get_account_balance(999)


class TestIntegrityCheck:

    def test_empty_ledger_is_balanced(self, db_session):
        service = LedgerService(db_session)
        result = service.check_integrity()
        assert result["is_balanced"] is True
        assert result["difference"] == Decimal("0")

    def test_ledger_with_entries_is_balanced(self, db_session):
        service = LedgerService(db_session)
        cash = make_account(service, "CASH", "Cash", AccountType.ASSET)
        deposit = make_account(
            service, "DEP", "Deposit", AccountType.LIABILITY
        )
        db_session.commit()

        for amount in ["1000.00", "500.00", "250.00"]:
            service.post_entries(PostEntriesRequest(
                currency="USD",
                entries=[
                    LedgerEntryCreate(
                        account_id=cash.id,
                        entry_type=EntryType.DEBIT,
                        amount=Decimal(amount),
                        description="Deposit",
                    ),
                    LedgerEntryCreate(
                        account_id=deposit.id,
                        entry_type=EntryType.CREDIT,
                        amount=Decimal(amount),
                        description="Deposit",
                    ),
                ],
            ))
        db_session.commit()

        result = service.check_integrity()
        assert result["is_balanced"] is True
        assert result["total_debits"] == Decimal("1750.00")
        assert result["total_credits"] == Decimal("1750.00")
