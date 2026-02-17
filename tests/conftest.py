"""
Shared test fixtures.

Sets up an isolated test database so tests never touch
the real database. Each test gets a fresh session that
rolls back after the test — no test data persists.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core_banking.main import app
from core_banking.models.base import Base, get_db


# Use SQLite for tests — no external database needed.
# This means tests run in CI (GitHub Actions) without
# any database infrastructure.
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
def setup_database():
    """
    Create all tables before each test, drop them after.

    autouse=True means every test gets this automatically.
    This ensures each test starts with a clean database.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a database session for direct service testing."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    """
    Provide a test client with the test database.

    We override the get_db dependency so the FastAPI app
    uses our test session instead of the real database.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
