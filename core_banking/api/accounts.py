"""
Account and customer API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_banking.models.base import get_db
from core_banking.services.account_service import AccountService
from core_banking.schemas.account import (
    CustomerCreate,
    CustomerResponse,
    AccountOpen,
    AccountResponse,
    AccountStatusUpdate,
    AccountBalanceResponse,
)

router = APIRouter(tags=["Accounts"])


# --- Customer Endpoints ---

@router.post("/customers", response_model=CustomerResponse, status_code=201)
def create_customer(
    request: CustomerCreate,
    db: Session = Depends(get_db),
):
    """Create a new customer."""
    service = AccountService(db)
    try:
        customer = service.create_customer(request)
        db.commit()
        return customer
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Account Endpoints ---

@router.post("/accounts", response_model=AccountResponse, status_code=201)
def open_account(
    request: AccountOpen,
    db: Session = Depends(get_db),
):
    """
    Open a new customer account.

    Creates the account in PENDING status along with
    its underlying ledger account.
    """
    service = AccountService(db)
    try:
        account = service.open_account(request)
        db.commit()
        return account
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    """Get account details."""
    service = AccountService(db)
    try:
        return service.get_account(account_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/accounts/{account_id}/status",
    response_model=AccountResponse,
)
def change_account_status(
    account_id: int,
    request: AccountStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Change account status.

    Enforces the state machine — only valid transitions
    are allowed.
    """
    service = AccountService(db)
    try:
        account = service.change_status(account_id, request)
        db.commit()
        return account
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
def get_account_balance(
    account_id: int,
    db: Session = Depends(get_db),
):
    """Get account balance calculated from ledger entries."""
    service = AccountService(db)
    try:
        account = service.get_account(account_id)
        balance = service.get_balance(account_id)
        return AccountBalanceResponse(
            account_id=account.id,
            external_id=account.external_id,
            account_type=account.account_type,
            status=account.status,
            balance=float(balance),
            currency=account.currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
