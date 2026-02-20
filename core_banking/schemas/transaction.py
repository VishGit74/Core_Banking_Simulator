"""
Pydantic schemas for transaction operations.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from core_banking.models.enums import TransactionType, TransactionStatus


class DepositRequest(BaseModel):
    account_id: int
    amount: Decimal = Field(gt=0, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str = Field(default="Cash deposit", max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=100)


class WithdrawalRequest(BaseModel):
    account_id: int
    amount: Decimal = Field(gt=0, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str = Field(default="Cash withdrawal", max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=100)


class TransferRequest(BaseModel):
    source_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str = Field(default="Transfer", max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=100)


class TransactionResponse(BaseModel):
    id: int
    external_id: uuid.UUID
    idempotency_key: str
    transaction_type: TransactionType
    status: TransactionStatus
    source_account_id: int | None
    destination_account_id: int | None
    amount: Decimal
    currency: str
    description: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
