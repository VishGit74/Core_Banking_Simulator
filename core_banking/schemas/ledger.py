"""
Pydantic schemas for ledger operations.

These define the API contract — what data comes in,
what data goes out. They are separate from the database
models because the API shape and the storage shape
are often different.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from core_banking.models.enums import AccountType, EntryType


# --- Request Schemas ---

class LedgerEntryCreate(BaseModel):
    """A single debit or credit in a transaction."""
    account_id: int
    entry_type: EntryType
    amount: Decimal = Field(gt=0, decimal_places=4)
    description: str = Field(min_length=1, max_length=255)

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class PostEntriesRequest(BaseModel):
    """
    A complete transaction — a group of entries that must balance.

    The client provides a transaction_id (UUID) so that
    retries with the same ID are idempotent.
    """
    transaction_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    currency: str = Field(min_length=3, max_length=3)
    entries: list[LedgerEntryCreate] = Field(min_length=2)

    @field_validator("entries")
    @classmethod
    def must_have_debits_and_credits(cls, v: list) -> list:
        types = {e.entry_type for e in v}
        if EntryType.DEBIT not in types or EntryType.CREDIT not in types:
            raise ValueError(
                "transaction must contain at least one debit and one credit"
            )
        return v


# --- Response Schemas ---

class LedgerEntryResponse(BaseModel):
    """Single entry in API responses."""
    id: int
    transaction_id: uuid.UUID
    account_id: int
    entry_type: EntryType
    amount: Decimal
    currency: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PostEntriesResponse(BaseModel):
    """Response after posting a transaction."""
    transaction_id: uuid.UUID
    entries: list[LedgerEntryResponse]
    total_amount: Decimal

    model_config = {"from_attributes": True}


class AccountBalanceResponse(BaseModel):
    """Response for an account balance query."""
    account_id: int
    account_code: str
    account_type: AccountType
    balance: Decimal
    currency: str


class LedgerAccountCreate(BaseModel):
    """Request to create a new ledger account."""
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    account_type: AccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)


class LedgerAccountResponse(BaseModel):
    """Ledger account in API responses."""
    id: int
    code: str
    name: str
    account_type: AccountType
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
