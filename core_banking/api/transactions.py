"""
Transaction API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_banking.models.base import get_db
from core_banking.services.transaction_service import TransactionService
from core_banking.schemas.transaction import (
    DepositRequest,
    WithdrawalRequest,
    TransferRequest,
    TransactionResponse,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/deposit", response_model=TransactionResponse, status_code=201)
def deposit(
    request: DepositRequest,
    db: Session = Depends(get_db),
):
    """Deposit money into an account."""
    service = TransactionService(db)
    try:
        txn = service.deposit(request)
        db.commit()
        return txn
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw", response_model=TransactionResponse, status_code=201)
def withdraw(
    request: WithdrawalRequest,
    db: Session = Depends(get_db),
):
    """Withdraw money from an account."""
    service = TransactionService(db)
    try:
        txn = service.withdraw(request)
        db.commit()
        return txn
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfer", response_model=TransactionResponse, status_code=201)
def transfer(
    request: TransferRequest,
    db: Session = Depends(get_db),
):
    """Transfer money between two accounts."""
    service = TransactionService(db)
    try:
        txn = service.transfer(request)
        db.commit()
        return txn
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{transaction_id}/reverse",
    response_model=TransactionResponse,
    status_code=201,
)
def reverse_transaction(
    transaction_id: int,
    idempotency_key: str,
    db: Session = Depends(get_db),
):
    """Reverse a completed transaction."""
    service = TransactionService(db)
    try:
        txn = service.reverse(transaction_id, idempotency_key)
        db.commit()
        return txn
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    """Get transaction details."""
    service = TransactionService(db)
    try:
        return service.get_transaction(transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
