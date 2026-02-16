"""
Ledger entry model.

Each entry is one half of a double-entry transaction.
A debit in one account is always paired with a credit
in another. Entries are immutable — once posted, they
are never modified or deleted.
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
    """
    An immutable debit or credit entry in the ledger.

    Entries are grouped by transaction_id. Within a group,
    the sum of DEBIT amounts must equal the sum of CREDIT
    amounts. This invariant is enforced by the LedgerService,
    not by the model — the model is just the data structure.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, default=uuid.uuid4, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id"), nullable=False, index=True
    )
    entry_type: Mapped[EntryType] = mapped_column(
        SAEnum(EntryType, name="entry_type_enum"),
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

    # Relationship back to the account
    account: Mapped["LedgerAccount"] = relationship(
        back_populates="entries"
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerEntry {self.entry_type.value} "
            f"{self.amount} {self.currency}>"
        )
