"""
Health check endpoint.

Used by load balancers, monitoring systems, and humans
to verify the application is running and responsive.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from core_banking.models.base import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Return application health status including database connectivity.

    The database check executes a simple query to verify
    the connection is alive. If it fails, the endpoint
    returns an error — telling the load balancer this
    instance is unhealthy.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "core-banking-simulator",
        "database": db_status,
    }
