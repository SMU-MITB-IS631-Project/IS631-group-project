"""
TDD Test Suite: AI Fallback for ExplanationService

This test suite verifies that the AI explanation system degrades gracefully when:
1. OpenAI API is unavailable
2. API call times out
3. API returns an error

Expected behavior:
- API returns 200 OK (not 500)
- Response includes is_fallback: True
- Explanation contains template-based text (not empty)
- System logs the fallback event
"""

import sys
import unittest
import logging
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from openai import APIError, APITimeoutError
import pytest


# Ensure backend/ is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base
from app.dependencies.auth import required_authenticated
from app.dependencies.db import get_db
from app.main import app
from app.models.user_profile import UserProfile, BenefitsPreference
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum
from app.models.card_bonus_category import CardBonusCategory, BonusCategory
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.transaction import UserTransaction  # noqa: F401


class TestExplanationFallback(unittest.TestCase):
    """Test suite for AI explanation fallback behavior"""

    def setUp(self):
        """Set up in-memory database with test fixtures"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        with self.Session() as db:
            # Create test user
            db.add(
                UserProfile(
                    id=1,
                    username="test_user",
                    cognito_sub="test-cognito-sub-explain-1",
                    benefits_preference=BenefitsPreference.cashback,
                )
            )

            # Create test card
            db.add(
                CardCatalogue(
                    card_id=1,
                    bank=BankEnum.DBS,
                    card_name="DBS Live Fresh",
                    benefit_type=BenefitTypeEnum.cashback,
                    base_benefit_rate=Decimal("0.01"),  # 1% cashback
                    status=StatusEnum.valid,
                )
            )

            # Add bonus category
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=1,
                    card_id=1,
                    bonus_category=BonusCategory.Fashion,
                    bonus_benefit_rate=Decimal("0.05"),  # 5% cashback
                    bonus_cap_in_dollar=100,
                    bonus_minimum_spend_in_dollar=50,
                )
            )

            # Add card to user's wallet
            db.add(
                UserOwnedCard(
                    user_id=1,
                    card_id=1,
                    status=UserOwnedCardStatus.active
                )
            )
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        # Override Cognito authentication (returns mocked claims)
        app.dependency_overrides[required_authenticated] = lambda: {"sub": "test-cognito-sub-explain-1"}
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up test fixtures"""
        app.dependency_overrides.clear()

    def test_api_returns_200_when_openai_timeout(self):
        """
        Test 1: Verify API returns 200 OK when OpenAI times out
        
        Expected:
        - HTTP 200 OK
        - is_fallback: true
        - explanation is not empty
        - model_used indicates timeout
        """
        with patch("app.services.explanation_service.openai_client") as mock_client:
            # Simulate OpenAI timeout
            mock_client.chat.completions.create.side_effect = APITimeoutError(
                request=MagicMock()
            )

            response = self.client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

            # Assertions
            self.assertEqual(
                response.status_code,
                200,
                f"Expected 200 OK, got {response.status_code}: {response.text}"
            )

            data = response.json()

            # Verify fallback metadata
            self.assertTrue(
                data.get("is_fallback"),
                "Expected is_fallback=true when OpenAI times out"
            )

            # Verify explanation is not empty
            explanation = data.get("explanation", "")
            self.assertGreater(
                len(explanation),
                0,
                "Expected non-empty explanation in fallback mode"
            )

            # Verify template-based explanation
            self.assertIn(
                "template",
                data.get("model_used", "").lower(),
                "Expected model_used to indicate template fallback"
            )

            # Verify explanation contains useful information
            self.assertTrue(
                any(word in explanation.lower() for word in ["card", "cashback", "reward", "fashion"]),
                f"Expected fallback explanation to contain card details, got: {explanation}"
            )

    def test_api_returns_200_when_openai_api_error(self):
        """
        Test 2: Verify API returns 200 OK when OpenAI returns an error
        
        Expected:
        - HTTP 200 OK
        - is_fallback: true
        - explanation contains template text
        """
        with patch("app.services.explanation_service.openai_client") as mock_client:
            # Simulate OpenAI API error
            mock_client.chat.completions.create.side_effect = APIError(
                message="Rate limit exceeded",
                request=MagicMock(),
                body=None
            )

            response = self.client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

            # Assertions
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertTrue(data.get("is_fallback"))
            self.assertGreater(len(data.get("explanation", "")), 0)
            self.assertIn("template", data.get("model_used", "").lower())

    def test_api_returns_200_when_openai_unavailable(self):
        """
        Test 3: Verify API returns 200 OK when OpenAI client is None
        
        Expected:
        - HTTP 200 OK
        - is_fallback: true
        - model_used: "template"
        """
        with patch("app.services.explanation_service.openai_client", None):
            response = self.client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

            # Assertions
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertTrue(
                data.get("is_fallback"),
                "Expected is_fallback=true when OpenAI client is unavailable"
            )
            self.assertEqual(
                data.get("model_used"),
                "template",
                "Expected model_used='template' when client is None"
            )

    def test_fallback_explanation_contains_card_details(self):
        """
        Test 4: Verify fallback explanation contains actual card information
        
        This ensures the template fallback is useful, not just a generic message
        """
        with patch("app.services.explanation_service.openai_client", None):
            response = self.client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

            data = response.json()
            explanation = data.get("explanation", "")

            # Verify explanation contains specific card details
            self.assertIn(
                "DBS Live Fresh",
                explanation,
                "Fallback explanation should include card name"
            )

            # Verify reward details are present
            self.assertTrue(
                "5" in explanation or "cashback" in explanation.lower(),
                "Fallback explanation should include reward rate or type"
            )

    def test_successful_ai_call_has_is_fallback_false(self):
        """
        Test 5: Verify is_fallback=false when AI call succeeds
        
        This is a sanity check to ensure the flag works correctly
        """
        with patch("app.services.explanation_service.openai_client") as mock_client:
            # Mock successful OpenAI response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = (
                "The DBS Live Fresh card offers 5% cashback on Fashion purchases."
            )
            mock_client.chat.completions.create.return_value = mock_response

            response = self.client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

            data = response.json()

            # When AI succeeds, is_fallback should be False
            self.assertFalse(
                data.get("is_fallback"),
                "Expected is_fallback=false when AI call succeeds"
            )

            # Model should not be "template"
            self.assertNotIn(
                "template",
                data.get("model_used", "").lower(),
                "Expected actual model name when AI succeeds"
            )


# Pytest-based tests for logging verification (require caplog fixture)
@pytest.fixture
def test_client():
    """Create test client with in-memory database"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    # Override Cognito authentication (returns mocked claims)
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "test-cognito-sub-explain-2"}

    with TestSession() as db:
        # Create test user
        db.add(
            UserProfile(
                id=1,
                username="test_user",
                cognito_sub="test-cognito-sub-explain-2",
                benefits_preference=BenefitsPreference.cashback,
            )
        )

        # Create test card
        db.add(
            CardCatalogue(
                card_id=1,
                bank=BankEnum.DBS,
                card_name="DBS Live Fresh",
                benefit_type=BenefitTypeEnum.cashback,
                base_benefit_rate=Decimal("0.01"),
                status=StatusEnum.valid,
            )
        )

        # Add bonus category
        db.add(
            CardBonusCategory(
                card_bonuscat_id=1,
                card_id=1,
                bonus_category=BonusCategory.Fashion,
                bonus_benefit_rate=Decimal("0.05"),
                bonus_cap_in_dollar=100,
                bonus_minimum_spend_in_dollar=50,
            )
        )

        # Add card to user's wallet
        db.add(
            UserOwnedCard(
                user_id=1,
                card_id=1,
                status=UserOwnedCardStatus.active
            )
        )
        db.commit()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_logging_verification_on_timeout(test_client, caplog):
    """
    Test 6: Verify internal logging when OpenAI times out
    
    This satisfies the "Error is logged internally" criterion
    """
    with patch("app.services.explanation_service.openai_client") as mock_client:
        # Simulate OpenAI timeout
        mock_client.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock()
        )

        # Capture logs at WARNING level
        with caplog.at_level(logging.WARNING):
            response = test_client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

        # Verify response is still successful
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
        
        # Verify warning was logged
        warning_logs = [record for record in caplog.records if record.levelname == "WARNING"]
        assert len(warning_logs) > 0, "Expected at least one WARNING log when OpenAI times out"
        
        # Verify log message mentions timeout and fallback
        log_messages = [record.message for record in warning_logs]
        timeout_logged = any("timeout" in msg.lower() or "fallback" in msg.lower() for msg in log_messages)
        assert timeout_logged, f"Expected log to mention 'timeout' or 'fallback', got: {log_messages}"


def test_logging_verification_on_api_error(test_client, caplog):
    """
    Test 7: Verify internal logging when OpenAI returns API error
    """
    with patch("app.services.explanation_service.openai_client") as mock_client:
        # Simulate OpenAI API error
        mock_client.chat.completions.create.side_effect = APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None
        )

        # Capture logs at ERROR level
        with caplog.at_level(logging.ERROR):
            response = test_client.post(
                "/api/v1/recommendation/explain",
                json={
                    "user_id": 1,
                    "amount_sgd": 100.00,
                    "category": "Fashion"
                }
            )

        # Verify response is still successful
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
        
        # Verify error was logged
        error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_logs) > 0, "Expected at least one ERROR log when OpenAI API fails"
        
        # Verify log message mentions the error and fallback
        log_messages = [record.message for record in error_logs]
        error_logged = any("error" in msg.lower() and "fallback" in msg.lower() for msg in log_messages)
        assert error_logged, f"Expected log to mention 'error' and 'fallback', got: {log_messages}"


# ============================================================================
# RECOMMENDATION ENDPOINT TESTS (GET /api/v1/recommendation)
# ============================================================================
# Tests for the recommendation routing endpoint: bonus calculation, precedence,
# preference parameter routing, and validation.


class TestRecommendationEndpoint(unittest.TestCase):
    """Test suite for GET /api/v1/recommendation recommendation routing"""

    def setUp(self):
        """Set up in-memory database with miles-based reward fixtures"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        with self.Session() as db:
            # Create test user with no preference (will use best reward)
            db.add(
                UserProfile(
                    id=1,
                    username="u1",
                    cognito_sub="test-cognito-sub-reco-api-1",
                    benefits_preference=BenefitsPreference.no_preference,
                )
            )
            
            # Create miles card as primary option
            db.add(
                CardCatalogue(
                    card_id=10,
                    bank=BankEnum.DBS,
                    card_name="Card A",
                    benefit_type=BenefitTypeEnum.miles,
                    base_benefit_rate=Decimal("1.0"),
                    status=StatusEnum.valid,
                )
            )
            
            # Add All-category bonus (2.0x multiplier)
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=100,
                    card_id=10,
                    bonus_category=BonusCategory.All,
                    bonus_benefit_rate=Decimal("2.0"),
                    bonus_cap_in_dollar=99999999,
                    bonus_minimum_spend_in_dollar=0,
                )
            )
            
            # Grant user card ownership
            db.add(UserOwnedCard(user_id=1, card_id=10, status=UserOwnedCardStatus.active))
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        # Override Cognito authentication (returns mocked claims)
        app.dependency_overrides[required_authenticated] = lambda: {"sub": "test-cognito-sub-reco-api-1"}
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up all dependency overrides after each test"""
        app.dependency_overrides.clear()

    def test_full_flow_get_recommendation(self):
        """Happy path: GET recommendation calculates bonus correctly (All category 2x multiplier).
        
        Scenario: User requests recommendation for $50 Food purchase
        Expected: Bonus (All) 2.0x => 50 * 2.0 = 100 miles
        """
        response = self.client.get(
            "/api/v1/recommendation",
            params={"user_id": 1, "category": "Food", "amount_sgd": "50"},
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIsNotNone(data.get("recommended"))
        self.assertEqual(data["recommended"]["card_id"], 10)
        self.assertEqual(data["recommended"]["reward_unit"], "miles")
        
        # Verification: All-category bonus 2.0x => 50 * 2.0 = 100 miles
        self.assertEqual(data["recommended"]["estimated_reward_value"], 100)
        
        self.assertIn("reward_breakdown", data["recommended"])
        self.assertEqual(data["recommended"]["reward_breakdown"]["reward_after_cap"], 100)
        self.assertGreaterEqual(len(data.get("ranked_cards", [])), 1)

    def test_specific_category_bonus_takes_precedence_over_all(self):
        """Category-specific bonus overrides All-category bonus (higher rate wins).
        
        Scenario: Add Food category bonus (3.0x) to existing All bonus (2.0x)
        Expected: Food-specific bonus takes precedence => 50 * 3.0 = 150 miles
        """
        # Add a category-specific bonus for Food with higher rate
        with self.Session() as db:
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=101,
                    card_id=10,
                    bonus_category=BonusCategory.Food,
                    bonus_benefit_rate=Decimal("3.0"),
                    bonus_cap_in_dollar=99999999,
                    bonus_minimum_spend_in_dollar=0,
                )
            )
            db.commit()

        response = self.client.get(
            "/api/v1/recommendation",
            params={"user_id": 1, "category": "Food", "amount_sgd": "50"},
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIsNotNone(data.get("recommended"))
        self.assertEqual(data["recommended"]["card_id"], 10)
        self.assertEqual(data["recommended"]["reward_unit"], "miles")
        
        # Verification: Food-specific bonus 3.0x takes precedence => 50 * 3.0 = 150 miles
        self.assertEqual(data["recommended"]["estimated_reward_value"], 150)
        
        self.assertIn("reward_breakdown", data["recommended"])
        self.assertEqual(data["recommended"]["reward_breakdown"]["reward_after_cap"], 150)
        self.assertGreaterEqual(len(data.get("ranked_cards", [])), 1)

    def test_invalid_amount_returns_400(self):
        """Validation: reject negative amount_sgd values.
        
        Scenario: Request recommendation with amount_sgd=-1
        Expected: 400 VALIDATION_ERROR
        """
        response = self.client.get(
            "/api/v1/recommendation",
            params={"user_id": 1, "category": "Food", "amount_sgd": "-1"},
        )
        
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("detail", body)
        self.assertIn("error", body["detail"])
        self.assertEqual(body["detail"]["error"]["code"], "VALIDATION_ERROR")

    def test_invalid_preference_is_rejected(self):
        """Validation: reject invalid preference enum values.
        
        Scenario: Request recommendation with preference="invalid"
        Expected: 400 VALIDATION_ERROR (invalid enum)
        """
        response = self.client.get(
            "/api/v1/recommendation",
            params={
                "user_id": 1,
                "category": "Food",
                "amount_sgd": "50",
                "preference": "invalid"
            },
        )
        
        # App normalizes request validation errors to 400
        self.assertEqual(response.status_code, 400)

    def test_preference_parameter_changes_output(self):
        """Routing: preference parameter affects which card is recommended.
        
        Scenario: Add a cashback card alongside miles card; verify preference routing
        Expected: 
          - preference=miles → recommends miles card (10)
          - preference=cashback → recommends cashback card (30)
        """
        # Add a cashback card alternative
        with self.Session() as db:
            db.add(
                CardCatalogue(
                    card_id=30,
                    bank=BankEnum.DBS,
                    card_name="Cashback Card",
                    benefit_type=BenefitTypeEnum.CASHBACK,
                    base_benefit_rate=Decimal("0.01"),
                    status=StatusEnum.valid,
                )
            )
            db.add(UserOwnedCard(user_id=1, card_id=30, status=UserOwnedCardStatus.Active))
            db.commit()

        # Request with miles preference -> should recommend miles card
        response_miles = self.client.get(
            "/api/v1/recommendation",
            params={
                "user_id": 1,
                "category": "Food",
                "amount_sgd": "50",
                "preference": "miles"
            },
        )
        
        self.assertEqual(response_miles.status_code, 200)
        self.assertEqual(response_miles.json()["recommended"]["reward_unit"], "miles")

        # Request with cashback preference -> should recommend cashback card
        response_cb = self.client.get(
            "/api/v1/recommendation",
            params={
                "user_id": 1,
                "category": "Food",
                "amount_sgd": "50",
                "preference": "cashback"
            },
        )
        
        self.assertEqual(response_cb.status_code, 200)
        self.assertEqual(response_cb.json()["recommended"]["reward_unit"], "cashback")


if __name__ == "__main__":
    unittest.main()
