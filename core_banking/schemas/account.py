"""
Pydantic schemas for customer and account operations.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr

from core_banking.models.enums import (
    CustomerAccountType,
    AccountStatus,
    KYCStatus,
)


# --- Customer Schemas ---

class CustomerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=255)


class CustomerResponse(BaseModel):
    id: int
    external_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    kyc_status: KYCStatus
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Account Schemas ---

class AccountOpen(BaseModel):
    """Request to open a new account."""
    customer_id: int
    account_type: CustomerAccountType
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountResponse(BaseModel):
    id: int
    external_id: uuid.UUID
    customer_id: int
    ledger_account_id: int
    account_type: CustomerAccountType
    status: AccountStatus
    currency: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountStatusUpdate(BaseModel):
    """Request to change account status."""
    new_status: AccountStatus
    reason: str = Field(min_length=1, max_length=255)


class AccountBalanceResponse(BaseModel):
    account_id: int
    external_id: uuid.UUID
    account_type: CustomerAccountType
    status: AccountStatus
    balance: float
    currency: str
