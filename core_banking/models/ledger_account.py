"""
Ledger account model (chart of accounts).
"""

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_banking.models.base import Base
from core_banking.models.enums import AccountType


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type_enum", create_constraint=True),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="account"
    )

    def __repr__(self) -> str:
        return f"<LedgerAccount {self.code} ({self.account_type.value})>"
