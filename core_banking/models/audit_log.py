"""
Audit log model.

Records significant system events for compliance and debugging.
In banking, auditability is not optional — every important action
must be traceable.
"""

from datetime import datetime

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from core_banking.models.base import Base


class AuditLog(Base):
    """
    Immutable record of a system event.

    Like ledger entries, audit logs are append-only.
    You never update or delete an audit record.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
