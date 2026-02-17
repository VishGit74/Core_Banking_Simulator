"""
Customer account model.

This is the business-layer account that customers interact with.
Each account links to an underlying ledger account where the
actual balance is tracked through double-entry bookkeeping.

The account has a state machine governing its lifecycle.
Invalid state transitions are rejected.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, DateTime, ForeignKey,
    Enum as SAEnum, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_banking.models.base import Base
from core_banking.models.enums import CustomerAccountType, AccountStatus


# Valid state transitions — the source of truth for the state machine
VALID_TRANSITIONS: dict[AccountStatus, set[AccountStatus]] = {
    AccountStatus.PENDING: {AccountStatus.ACTIVE, AccountStatus.CLOSED},
    AccountStatus.ACTIVE: {
        AccountStatus.FROZEN,
        AccountStatus.BLOCKED,
        AccountStatus.CLOSED,
    },
    AccountStatus.FROZEN: {AccountStatus.ACTIVE, AccountStatus.BLOCKED},
    AccountStatus.BLOCKED: {AccountStatus.CLOSED},
    AccountStatus.CLOSED: set(),  # Terminal state — no transitions out
}


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, nullable=False, default=uuid.uuid4
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    ledger_account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id"), nullable=False, index=True
    )
    account_type: Mapped[CustomerAccountType] = mapped_column(
        SAEnum(
            CustomerAccountType,
            name="customer_account_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[AccountStatus] = mapped_column(
        SAEnum(
            AccountStatus,
            name="account_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=AccountStatus.PENDING,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="accounts")
    ledger_account: Mapped["LedgerAccount"] = relationship()

    def can_transition_to(self, new_status: AccountStatus) -> bool:
        """Check if a state transition is valid."""
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def __repr__(self) -> str:
        return (
            f"<Account {self.external_id} "
            f"{self.account_type.value} ({self.status.value})>"
        )
