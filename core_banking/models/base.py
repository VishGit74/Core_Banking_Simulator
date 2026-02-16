"""
Database engine, session management, and base model.

This module is the foundation for all database operations.
Every model inherits from Base. Every request gets a session
from get_db().
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core_banking.config import get_settings

settings = get_settings()

# --- Engine ---
# The engine manages a pool of database connections.
# pool_pre_ping=True tests connections before using them,
# which handles cases where the database restarted or a
# connection went stale. In banking, a failed connection
# on a transaction is unacceptable.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# --- Session Factory ---
# Each call to SessionLocal() creates a new session.
# autocommit=False means we explicitly control when changes
# are saved — critical for financial transactions where you
# need all-or-nothing behavior.
# autoflush=False means SQLAlchemy won't send SQL to the
# database until we explicitly flush or commit — this gives
# us precise control over when queries execute.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# --- Base Model Class ---
# Every database model (Account, LedgerEntry, Transaction, etc.)
# will inherit from this class. SQLAlchemy uses it to track
# all models and generate the correct SQL for table creation.
class Base(DeclarativeBase):
    pass


# --- Dependency for FastAPI ---
def get_db():
    """
    Provide a database session for a single request.

    This is a generator that FastAPI uses as a dependency.
    It creates a session, gives it to the endpoint function,
    and guarantees cleanup when the request finishes —
    even if an error occurs.

    The try/finally pattern ensures the session is always
    closed, preventing connection leaks. A leaked connection
    stays occupied in the pool, and if enough leak, the
    application runs out of connections and stops working.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
