"""
Core Banking Simulator — FastAPI Application.
"""

from fastapi import FastAPI

from core_banking.config import get_settings
from core_banking.api.health import router as health_router
from core_banking.api.ledger import router as ledger_router
from core_banking.api.accounts import router as accounts_router
from core_banking.api.transactions import router as transactions_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A learning project implementing core banking concepts",
)

app.include_router(health_router)
app.include_router(ledger_router)
app.include_router(accounts_router)
app.include_router(transactions_router)
