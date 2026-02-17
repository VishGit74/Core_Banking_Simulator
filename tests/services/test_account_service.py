"""
Comprehensive tests for the AccountService.
"""

from decimal import Decimal

import pytest

from core_banking.models.enums import (
    AccountStatus,
    CustomerAccountType,
    EntryType,
)
from core_banking.services.account_service import AccountService
from core_banking.services.ledger_service import LedgerService
from core_banking.schemas.account import (
    CustomerCreate,
    AccountOpen,
    AccountStatusUpdate,
)
from core_banking.schemas.ledger import (
    PostEntriesRequest,
    LedgerEntryCreate,
    LedgerAccountCreate,
)
from core_banking.models.enums import AccountType


def make_customer(service, first="John", last="Doe", email="john@test.com"):
    return service.create_customer(CustomerCreate(
        first_name=first, last_name=last, email=email,
    ))


def open_checking(service, customer_id, currency="USD"):
    return service.open_account(AccountOpen(
        customer_id=customer_id,
        account_type=CustomerAccountType.CHECKING,
        currency=currency,
    ))


# --- Customer Tests ---

class TestCreateCustomer:

    def test_create_customer_succeeds(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()

        assert customer.id is not None
        assert customer.first_name == "John"
        assert customer.kyc_status.value == "PENDING"

    def test_duplicate_email_rejected(self, db_session):
        service = AccountService(db_session)
        make_customer(service)
        db_session.commit()

        with pytest.raises(ValueError, match="already exists"):
            make_customer(service)


# --- Account Opening Tests ---

class TestOpenAccount:

    def test_open_account_succeeds(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()

        account = open_checking(service, customer.id)
        db_session.commit()

        assert account.id is not None
        assert account.status == AccountStatus.PENDING
        assert account.ledger_account_id is not None
        assert account.opened_at is None  # Not yet active

    def test_creates_ledger_account(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()

        account = open_checking(service, customer.id)
        db_session.commit()

        # Verify the ledger account was created
        ledger_service = LedgerService(db_session)
        balance = ledger_service.get_account_balance(account.ledger_account_id)
        assert balance == Decimal("0")

    def test_nonexistent_customer_rejected(self, db_session):
        service = AccountService(db_session)

        with pytest.raises(ValueError, match="not found"):
            open_checking(service, customer_id=999)

    def test_multiple_accounts_per_customer(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()

        checking = open_checking(service, customer.id)
        savings = service.open_account(AccountOpen(
            customer_id=customer.id,
            account_type=CustomerAccountType.SAVINGS,
        ))
        db_session.commit()

        accounts = service.get_customer_accounts(customer.id)
        assert len(accounts) == 2


# --- State Machine Tests ---

class TestAccountStatusTransitions:

    def _make_active_account(self, db_session):
        """Helper: create a customer and activate an account."""
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()
        account = open_checking(service, customer.id)
        db_session.commit()

        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.ACTIVE, reason="KYC approved",
        ))
        db_session.commit()
        return service, account

    def test_pending_to_active(self, db_session):
        service, account = self._make_active_account(db_session)
        assert account.status == AccountStatus.ACTIVE
        assert account.opened_at is not None

    def test_active_to_frozen(self, db_session):
        service, account = self._make_active_account(db_session)

        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.FROZEN,
            reason="Suspicious activity detected",
        ))
        db_session.commit()
        assert account.status == AccountStatus.FROZEN

    def test_frozen_to_active(self, db_session):
        service, account = self._make_active_account(db_session)

        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.FROZEN, reason="Investigation",
        ))
        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.ACTIVE, reason="Cleared",
        ))
        db_session.commit()
        assert account.status == AccountStatus.ACTIVE

    def test_active_to_closed(self, db_session):
        service, account = self._make_active_account(db_session)

        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.CLOSED, reason="Customer request",
        ))
        db_session.commit()

        assert account.status == AccountStatus.CLOSED
        assert account.closed_at is not None
        # Ledger account should be deactivated
        assert account.ledger_account.is_active is False

    def test_closed_to_active_rejected(self, db_session):
        service, account = self._make_active_account(db_session)

        service.change_status(account.id, AccountStatusUpdate(
            new_status=AccountStatus.CLOSED, reason="Closing",
        ))
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot transition"):
            service.change_status(account.id, AccountStatusUpdate(
                new_status=AccountStatus.ACTIVE, reason="Reopen",
            ))

    def test_pending_to_frozen_rejected(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()
        account = open_checking(service, customer.id)
        db_session.commit()

        with pytest.raises(ValueError, match="Cannot transition"):
            service.change_status(account.id, AccountStatusUpdate(
                new_status=AccountStatus.FROZEN, reason="Not allowed",
            ))


# --- Balance Tests ---

class TestAccountBalance:

    def test_balance_from_ledger(self, db_session):
        """Account balance comes from ledger entries, not stored value."""
        acct_service = AccountService(db_session)
        ledger_service = LedgerService(db_session)

        customer = make_customer(acct_service)
        db_session.commit()
        account = open_checking(acct_service, customer.id)
        db_session.commit()

        # We need a cash account to post against
        cash = ledger_service.create_account(LedgerAccountCreate(
            code="CASH-MAIN",
            name="Main Cash",
            account_type=AccountType.ASSET,
        ))
        db_session.commit()

        # Post a deposit: debit cash, credit customer ledger account
        ledger_service.post_entries(PostEntriesRequest(
            currency="USD",
            entries=[
                LedgerEntryCreate(
                    account_id=cash.id,
                    entry_type=EntryType.DEBIT,
                    amount=Decimal("1000.00"),
                    description="Customer deposit",
                ),
                LedgerEntryCreate(
                    account_id=account.ledger_account_id,
                    entry_type=EntryType.CREDIT,
                    amount=Decimal("1000.00"),
                    description="Customer deposit",
                ),
            ],
        ))
        db_session.commit()

        balance = acct_service.get_balance(account.id)
        assert balance == Decimal("1000.00")

    def test_new_account_zero_balance(self, db_session):
        service = AccountService(db_session)
        customer = make_customer(service)
        db_session.commit()
        account = open_checking(service, customer.id)
        db_session.commit()

        balance = service.get_balance(account.id)
        assert balance == Decimal("0")
