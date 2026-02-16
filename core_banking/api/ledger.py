"""
Ledger API endpoints.

These endpoints expose the ledger operations to HTTP clients.
The API layer is thin — it handles HTTP concerns (status codes,
response formatting) and delegates all business logic to the
LedgerService.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core_banking.models.base import get_db
from core_banking.models.ledger_account import LedgerAccount
from core_banking.services.ledger_service import LedgerService
from core_banking.schemas.ledger import (
    PostEntriesRequest,
    PostEntriesResponse,
    LedgerEntryResponse,
    LedgerAccountCreate,
    LedgerAccountResponse,
    AccountBalanceResponse,
)

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.post("/accounts", response_model=LedgerAccountResponse, status_code=201)
def create_ledger_account(
    request: LedgerAccountCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new ledger account.

    Every account in the chart of accounts must be created
    before entries can be posted to it.
    """
    service = LedgerService(db)
    try:
        account = service.create_account(request)
        db.commit()
        return account
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/entries", response_model=PostEntriesResponse, status_code=201)
def post_entries(
    request: PostEntriesRequest,
    db: Session = Depends(get_db),
):
    """
    Post a balanced set of ledger entries.

    The entries must contain at least one debit and one credit,
    and total debits must equal total credits. If the
    transaction_id has been used before, the existing entries
    are returned (idempotency).
    """
    service = LedgerService(db)
    try:
        entries = service.post_entries(request)
        db.commit()

        total_amount = sum(
            e.amount for e in entries
            if e.entry_type.value == "DEBIT"
        )

        return PostEntriesResponse(
            transaction_id=request.transaction_id,
            entries=[LedgerEntryResponse.model_validate(e) for e in entries],
            total_amount=total_amount,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/accounts/{account_id}/balance",
    response_model=AccountBalanceResponse,
)
def get_account_balance(
    account_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the current balance for a ledger account.

    Balance is calculated from entries, not stored.
    This guarantees accuracy.
    """
    service = LedgerService(db)
    try:
        balance = service.get_account_balance(account_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    account = db.get(LedgerAccount, account_id)

    return AccountBalanceResponse(
        account_id=account.id,
        account_code=account.code,
        account_type=account.account_type,
        balance=balance,
        currency=account.currency,
    )


@router.get(
    "/accounts/{account_id}/entries",
    response_model=list[LedgerEntryResponse],
)
def get_account_entries(
    account_id: int,
    db: Session = Depends(get_db),
):
    """
    Get all ledger entries for an account, newest first.
    """
    service = LedgerService(db)
    entries = service.get_entries_by_account(account_id)
    if not entries:
        account = db.get(LedgerAccount, account_id)
        if not account:
            raise HTTPException(
                status_code=404, detail=f"Account {account_id} not found"
            )
    return entries
