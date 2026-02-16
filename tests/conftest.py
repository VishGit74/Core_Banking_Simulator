"""
Shared test fixtures.

conftest.py is automatically loaded by pytest. Fixtures defined
here are available to all test files without explicit imports.
"""

import pytest
from fastapi.testclient import TestClient

from core_banking.main import app


@pytest.fixture
def client():
    """
    Provide a test client for the FastAPI application.

    TestClient wraps httpx to send requests directly to the app
    without starting a real server. No network involved — the
    request goes straight from the test to the endpoint function.
    This makes tests fast and reliable (no port conflicts,
    no network timeouts).
    """
    return TestClient(app)
