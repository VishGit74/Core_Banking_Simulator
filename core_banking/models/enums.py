"""
Shared enumerations for database models.
"""

import enum


class AccountType(str, enum.Enum):
    """The five fundamental accounting categories."""
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class EntryType(str, enum.Enum):
    """Direction of a ledger entry."""
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class CustomerAccountType(str, enum.Enum):
    """Customer-facing account types."""
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CREDIT = "CREDIT"
    PREPAID = "PREPAID"


class AccountStatus(str, enum.Enum):
    """Account lifecycle states."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"


class KYCStatus(str, enum.Enum):
    """Know Your Customer verification status."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
