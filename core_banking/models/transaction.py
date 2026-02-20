"""
Transaction model.

Represents a high-level business operation (deposit, withdrawal,
transfer) that generates ledger entries underneath. Transactions
add business context to the raw accounting entries.

Idempotency is enforced via the idempotency_key unique constraint.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, DateTime, Numeric, ForeignKey,
    Enum as SAEnum, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_banking.models.base import Base
from core_banking.models.enums import TransactionType, TransactionStatus


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, nullable=False, default=uuid.uuid4
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(
            TransactionType,
            name="transaction_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(
            TransactionStatus,
            name="transaction_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=TransactionStatus.PENDING,
    )
    source_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    destination_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    reference_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
    ledger_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    source_account: Mapped["Account | None"] = relationship(
        foreign_keys=[source_account_id]
    )
    destination_account: Mapped["Account | None"] = relationship(
        foreign_keys=[destination_account_id]
    )
    reference_transaction: Mapped["Transaction | None"] = relationship(
        remote_side=[id]
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction {self.transaction_type.value} "
            f"{self.amount} {self.currency} ({self.status.value})>"
        )
