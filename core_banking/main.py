"""
Core Banking Simulator — FastAPI Application.

This is the entry point for the application.
All routers are registered here.
"""

from fastapi import FastAPI

from core_banking.config import get_settings
from core_banking.api.health import router as health_router
from core_banking.api.ledger import router as ledger_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A learning project implementing core banking concepts",
)

# Register routers
app.include_router(health_router)
app.include_router(ledger_router)
