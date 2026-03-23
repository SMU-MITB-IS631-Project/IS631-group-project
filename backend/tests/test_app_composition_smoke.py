import pytest
from fastapi.testclient import TestClient

from app.main import app


# These are app-composition smoke tests, not business-logic tests.
# They guard against regressions where routers are not mounted correctly in app.main.

@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_transactions_routes_are_registered_in_openapi(client: TestClient):
    """Ensure transaction endpoints are exposed by the real application wiring."""
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json().get("paths", {})
    assert "/api/v1/transactions" in paths
    assert "/api/v1/transactions/{transaction_id}/status" in paths
    assert "/api/v1/transactions/bulk/status" in paths
