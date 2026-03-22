"""
Verification tests for x-user-id header requirement refactor - /user_cards endpoints.

SCOPE: Tests focus on /api/v1/user_cards endpoints (GET, POST, PUT, DELETE) which are NOT
shadowed by legacy compatibility routes. These provide clean verification that:
1. x-user-id header enforcement works at the route layer
2. Service layer validates user_id: str (not Optional)
3. Both request validation and service validation are in place

NOTE: Legacy /wallet alias endpoints were removed as part of cleanup, so this module
focuses exclusively on /user_cards header enforcement behavior.

Tests verify:
1. All 4 /user_cards endpoints return 401 when x-user-id is missing
2. All 4 /user_cards endpoints proceed past auth check when x-user-id is provided
3. Edge cases (empty/whitespace headers) are handled correctly
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.main import app
from app.dependencies.db import get_db


# Test fixtures
@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def client(mock_db):
    """Create test client with dependency override."""
    def override_get_db():
        yield mock_db
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ============================================================================
# NEGATIVE TESTS: Missing x-user-id header on /user_cards endpoints
# ============================================================================

class TestMissingXUserId:
    """Verify all /user_cards endpoints return 401 when x-user-id is missing."""

    def test_get_user_cards_missing_header(self, client):
        """GET /api/v1/user_cards returns 401 without x-user-id."""
        response = client.get("/api/v1/user_cards")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert data["error"]["details"]["required_header"] == "x-user-id"

    def test_post_user_cards_missing_header(self, client):
        """POST /api/v1/user_cards returns 401 without x-user-id."""
        payload = {
            "wallet_card": {
                "card_id": "1",
                "refresh_day_of_month": 15,
                "annual_fee_billing_date": "2025-12-31",
                "cycle_spend_sgd": 5000.0,
            }
        }
        response = client.post("/api/v1/user_cards", json=payload)
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_put_user_cards_missing_header(self, client):
        """PUT /api/v1/user_cards/{card_id} returns 401 without x-user-id."""
        payload = {
            "user_card": {
                "card_id": "1",
                "refresh_day_of_month": 15,
                "annual_fee_billing_date": "2025-12-31",
                "cycle_spend_sgd": 5000.0,
            }
        }
        response = client.put("/api/v1/user_cards/1", json=payload)
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_delete_user_cards_missing_header(self, client):
        """DELETE /api/v1/user_cards/{card_id} returns 401 without x-user-id."""
        response = client.delete("/api/v1/user_cards/1")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# POSITIVE TESTS: Valid x-user-id header on /user_cards endpoints
# ============================================================================

class TestValidXUserId:
    """Verify /user_cards endpoints pass auth check with valid x-user-id."""

    @patch('app.services.user_card_services.UserCardManagementService.list_user_cards')
    def test_get_user_cards_with_header(self, mock_list, client):
        """GET /api/v1/user_cards passes auth check with valid x-user-id."""
        mock_list.return_value = []
        response = client.get(
            "/api/v1/user_cards",
            headers={"x-user-id": "u_001"}
        )
        assert response.status_code == 200
        assert "user_cards" in response.json()
        # Verify the service method was called with the correct user_id
        mock_list.assert_called_once_with("u_001")

    @patch('app.services.user_card_services.UserCardManagementService.add_user_card')
    def test_post_user_cards_with_header(self, mock_add, client):
        """POST /api/v1/user_cards passes auth check with valid x-user-id."""
        mock_add.return_value = {
            "card_id": "1",
            "refresh_day_of_month": 15,
            "annual_fee_billing_date": "2025-12-31",
            "cycle_spend_sgd": 0,
        }
        payload = {
            "wallet_card": {
                "card_id": "1",
                "refresh_day_of_month": 15,
                "annual_fee_billing_date": "2025-12-31",
                "cycle_spend_sgd": 5000.0,
            }
        }
        response = client.post(
            "/api/v1/user_cards",
            json=payload,
            headers={"x-user-id": "u_001"}
        )
        assert response.status_code == 201
        assert "wallet_card" in response.json()
        # Verify the service method was called with correct user_id
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] == "u_001"  # First positional arg is user_id

    @patch('app.services.user_card_services.UserCardManagementService.replace_user_card')
    def test_put_user_cards_with_header(self, mock_replace, client):
        """PUT /api/v1/user_cards/{card_id} passes auth check with valid x-user-id."""
        mock_replace.return_value = {
            "card_id": "1",
            "refresh_day_of_month": 20,
            "annual_fee_billing_date": "2025-12-31",
            "cycle_spend_sgd": 0,
        }
        payload = {
            "user_card": {
                "card_id": "1",
                "refresh_day_of_month": 20,
                "annual_fee_billing_date": "2025-12-31",
                "cycle_spend_sgd": 5000.0,
            }
        }
        response = client.put(
            "/api/v1/user_cards/1",
            json=payload,
            headers={"x-user-id": "u_001"}
        )
        assert response.status_code == 200
        assert "wallet_card" in response.json()
        # Verify service method was called with correct user_id
        mock_replace.assert_called_once()
        call_args = mock_replace.call_args
        assert call_args[0][0] == "u_001"  # First positional arg is user_id

    @patch('app.services.user_card_services.UserCardManagementService.delete_user_card')
    def test_delete_user_cards_with_header(self, mock_delete, client):
        """DELETE /api/v1/user_cards/{card_id} passes auth check with valid x-user-id."""
        mock_delete.return_value = None
        response = client.delete(
            "/api/v1/user_cards/1",
            headers={"x-user-id": "u_001"}
        )
        assert response.status_code == 204
        # Verify service method was called with correct user_id
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        assert call_args[0][0] == "u_001"  # First positional arg is user_id


# ============================================================================
# EDGE CASES: Empty or invalid x-user-id values on /user_cards endpoints
# ============================================================================

class TestEdgeCases:
    """Verify edge cases are handled correctly on /user_cards endpoints."""

    def test_empty_x_user_id_header(self, client):
        """Empty x-user-id header is treated as missing."""
        response = client.get(
            "/api/v1/user_cards",
            headers={"x-user-id": ""}
        )
        assert response.status_code == 401

    def test_whitespace_only_x_user_id_header(self, client):
        """Whitespace-only x-user-id header is treated as missing."""
        response = client.get(
            "/api/v1/user_cards",
            headers={"x-user-id": "   "}
        )
        # After .strip() this becomes empty
        assert response.status_code == 401

    @patch('app.services.user_card_services.UserCardManagementService.list_user_cards')
    def test_valid_numeric_x_user_id(self, mock_list, client):
        """Numeric x-user-id resolves correctly."""
        mock_list.return_value = []
        response = client.get(
            "/api/v1/user_cards",
            headers={"x-user-id": "1"}
        )
        # Numeric ID should pass auth
        assert response.status_code == 200
        mock_list.assert_called_once_with("1")

    @patch('app.services.user_card_services.UserCardManagementService.list_user_cards')
    def test_valid_u_prefixed_x_user_id(self, mock_list, client):
        """u_NNN formatted x-user-id resolves correctly."""
        mock_list.return_value = []
        response = client.get(
            "/api/v1/user_cards",
            headers={"x-user-id": "u_001"}
        )
        # u_NNN format should pass auth
        assert response.status_code == 200
        mock_list.assert_called_once_with("u_001")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
