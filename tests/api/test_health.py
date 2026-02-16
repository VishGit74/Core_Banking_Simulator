"""
Tests for the health check endpoint.
"""


def test_health_check_returns_200(client):
    """
    Verify the health endpoint responds with HTTP 200.

    This is the most basic test — can the application
    receive a request and respond? If this fails, nothing
    else will work.
    """
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_returns_service_name(client):
    """
    Verify the response includes the correct service name.

    This catches accidental changes to the response format
    that could break monitoring systems that parse this field.
    """
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "core-banking-simulator"


def test_health_check_reports_database_status(client):
    """
    Verify the response includes database connectivity status.

    The health endpoint should always report whether the
    database is reachable. Monitoring systems use this to
    detect database outages.
    """
    response = client.get("/health")
    data = response.json()
    assert "database" in data
    assert data["database"] in ("healthy", "unhealthy")
