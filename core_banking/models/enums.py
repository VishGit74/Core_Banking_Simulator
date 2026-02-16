"""
Shared enumerations for database models.

Using Python enums mapped to database enums ensures that
only valid values can be stored. An invalid account_type
or entry_type is caught at the database level, not just
in Python validation.
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
