"""
Customer model.

Represents an account holder. A customer can have
multiple accounts (checking, savings, credit, etc.).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core_banking.models.base import Base
from core_banking.models.enums import KYCStatus


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, nullable=False, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    kyc_status: Mapped[KYCStatus] = mapped_column(
        SAEnum(KYCStatus, name="kyc_status_enum", create_constraint=True),
        nullable=False,
        default=KYCStatus.PENDING,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # A customer can have many accounts
    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.first_name} {self.last_name}>"
