"""
Account service — manages customer accounts and their lifecycle.

This service coordinates between the account layer and the
ledger layer. Opening an account creates a corresponding
ledger account. Balance queries delegate to the ledger.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_banking.models.customer import Customer
from core_banking.models.account import Account, VALID_TRANSITIONS
from core_banking.models.enums import (
    AccountStatus,
    AccountType,
    KYCStatus,
    CustomerAccountType,
)
from core_banking.schemas.account import (
    CustomerCreate,
    AccountOpen,
    AccountStatusUpdate,
)
from core_banking.schemas.ledger import LedgerAccountCreate
from core_banking.services.ledger_service import LedgerService


# Maps customer account types to their ledger account type.
# Customer deposits are liabilities (bank owes the customer).
# Credit accounts are also liabilities (customer has a credit line).
ACCOUNT_TYPE_TO_LEDGER_TYPE = {
    CustomerAccountType.CHECKING: AccountType.LIABILITY,
    CustomerAccountType.SAVINGS: AccountType.LIABILITY,
    CustomerAccountType.CREDIT: AccountType.LIABILITY,
    CustomerAccountType.PREPAID: AccountType.LIABILITY,
}


class AccountService:

    def __init__(self, db: Session):
        self.db = db
        self.ledger_service = LedgerService(db)

    def create_customer(self, request: CustomerCreate) -> Customer:
        """Create a new customer."""
        existing = self.db.execute(
            select(Customer).where(Customer.email == request.email)
        ).scalar_one_or_none()

        if existing:
            raise ValueError(f"Customer with email '{request.email}' already exists")

        customer = Customer(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
        )
        self.db.add(customer)
        self.db.flush()
        return customer

    def open_account(self, request: AccountOpen) -> Account:
        """
        Open a new customer account.

        This creates the business-layer account AND the
        underlying ledger account in a single operation.
        The account starts in PENDING status.
        """
        # Validate customer exists
        customer = self.db.get(Customer, request.customer_id)
        if not customer:
            raise ValueError(f"Customer {request.customer_id} not found")

        if not customer.is_active:
            raise ValueError(f"Customer {request.customer_id} is not active")

        # Create the underlying ledger account
        ledger_code = f"CUST-{request.account_type.value}-{customer.id:05d}"
        ledger_type = ACCOUNT_TYPE_TO_LEDGER_TYPE[request.account_type]

        ledger_account = self.ledger_service.create_account(
            LedgerAccountCreate(
                code=ledger_code,
                name=f"{customer.first_name} {customer.last_name} {request.account_type.value}",
                account_type=ledger_type,
                currency=request.currency,
            )
        )

        # Create the customer-facing account
        account = Account(
            customer_id=customer.id,
            ledger_account_id=ledger_account.id,
            account_type=request.account_type,
            currency=request.currency,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def change_status(
        self, account_id: int, request: AccountStatusUpdate
    ) -> Account:
        """
        Transition an account to a new status.

        Enforces the state machine — only valid transitions
        are allowed. Records timestamps for significant
        transitions (activation, closure).
        """
        account = self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        if not account.can_transition_to(request.new_status):
            raise ValueError(
                f"Cannot transition from {account.status.value} "
                f"to {request.new_status.value}"
            )

        old_status = account.status
        account.status = request.new_status

        # Record significant timestamps
        if request.new_status == AccountStatus.ACTIVE:
            account.opened_at = datetime.utcnow()
        elif request.new_status == AccountStatus.CLOSED:
            account.closed_at = datetime.utcnow()
            # Deactivate the underlying ledger account
            account.ledger_account.is_active = False

        self.db.flush()
        return account

    def get_account(self, account_id: int) -> Account:
        """Get an account by ID."""
        account = self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        return account

    def get_balance(self, account_id: int) -> Decimal:
        """
        Get account balance by delegating to the ledger.

        The account doesn't store its balance — it asks
        the ledger to calculate it from entries.
        """
        account = self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        return self.ledger_service.get_account_balance(
            account.ledger_account_id
        )

    def get_customer_accounts(self, customer_id: int) -> list[Account]:
        """Get all accounts for a customer."""
        accounts = self.db.execute(
            select(Account).where(Account.customer_id == customer_id)
        ).scalars().all()
        return list(accounts)
