"""
Ledger entry model.
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
from core_banking.models.enums import EntryType


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, default=uuid.uuid4, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id"), nullable=False, index=True
    )
    entry_type: Mapped[EntryType] = mapped_column(
        SAEnum(EntryType, name="entry_type_enum", create_constraint=True),
        nullable=False,
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    account: Mapped["LedgerAccount"] = relationship(
        back_populates="entries"
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerEntry {self.entry_type.value} "
            f"{self.amount} {self.currency}>"
        )
