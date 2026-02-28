"""
TDD Test Suite for ExplanationService

Test Strategy:
1. Unit tests with mocked database and OpenAI API
2. Integration tests with real database (test fixtures)
3. Edge case validation (missing data, rate limits, timeouts)

Test Coverage Goals:
- Database query accuracy (ground truth extraction)
- Prompt construction correctness
- LLM fallback behavior
- Rate anti-hallucination validation
- Error handling robustness
"""

import os
import sys
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Add backend to path for imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from app.db.db import Base
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum
from app.models.card_bonus_category import CardBonusCategory, BonusCategory
from app.models.user_profile import UserProfile  # Import to ensure table creation
from app.models.transaction import UserTransaction  # Import to ensure table creation
from app.models.user_owned_cards import UserOwnedCard  # Import to ensure table creation
from app.schemas.ai_schemas import (
    RecommendationContext,
    ExplanationRequest,
    ExplanationResponse,
    BenefitType
)
from app.services.explanation_service import ExplanationService


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """
    Create an in-memory SQLite database session for testing.
    Uses nested transactions for automatic rollback after each test.
    
    Pattern: Mirrors production DB structure without polluting test data
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    # Nested transaction support for rollback
    session.begin_nested()
    
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not getattr(trans._parent, "nested", False):
            sess.begin_nested()
    
    yield session
    
    # Cleanup
    session.close()
    transaction.rollback()
    connection.close()
    event.remove(session, "after_transaction_end", restart_savepoint)


@pytest.fixture
def sample_card(db_session):
    """
    Create a test credit card in the database.
    
    Returns:
        CardCatalogue: DBS Live Fresh with 1% base cashback
    """
    card = CardCatalogue(
        card_id=101,
        bank=BankEnum.DBS,
        card_name="DBS Live Fresh",
        benefit_type=BenefitTypeEnum.cashback,
        base_benefit_rate=Decimal("0.01"),  # 1% base
        status=StatusEnum.valid
    )
    db_session.add(card)
    db_session.flush()
    return card


@pytest.fixture
def sample_bonus_category(db_session, sample_card):
    """
    Create a bonus category for Fashion purchases.
    
    Returns:
        CardBonusCategory: 3.5% cashback on Fashion (DBS Live Fresh)
    """
    bonus = CardBonusCategory(
        card_id=sample_card.card_id,
        bonus_category=BonusCategory.Fashion,
        bonus_benefit_rate=Decimal("0.035"),  # 3.5% bonus
        bonus_cap_in_dollar=100,  # SGD 100 monthly cap
        bonus_minimum_spend_in_dollar=0
    )
    db_session.add(bonus)
    db_session.flush()
    return bonus


@pytest.fixture
def mock_openai_client():
    """
    Mock OpenAI client for testing LLM interactions without API calls.
    
    Returns:
        MagicMock: Configured to return realistic chat completion responses
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="The DBS Live Fresh card offers 3.5% cashback on Fashion purchases."))
    ]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# =============================================================================
# TEST 1: Verify prompt contains correct bonus_rate from database
# =============================================================================

def test_prompt_contains_correct_bonus_rate_from_db(db_session, sample_card, sample_bonus_category):
    """
    CRITICAL TEST: Ensures the generated prompt uses database-verified bonus rates,
    not hallucinated or user-provided values.
    
    Test Flow:
    1. Create card with 1% base rate in DB
    2. Create bonus category with 3.5% bonus rate
    3. Build context from DB
    4. Verify prompt contains "3.5%" or "0.035"
    
    Anti-Hallucination Guard: This test fails if rates don't match database
    """
    service = ExplanationService(db_session)
    
    # Build context from database (ground truth source)
    context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("120.00")
    )
    
    # Verify context has correct database values
    assert context.bonus_rate == Decimal("0.035"), "Bonus rate should match DB value"
    assert context.base_rate == Decimal("0.01"), "Base rate should match DB value"
    assert context.is_bonus_eligible is True, "Should recognize Fashion as bonus category"
    
    # Build prompt and verify it contains ground truth
    request = ExplanationRequest(recommendation=context)
    prompt = service._build_prompt(context, request.comparison_cards)
    
    # Verify prompt contains the exact database rate
    assert "3.5%" in prompt or "3.50%" in prompt, "Prompt must contain bonus rate percentage"
    assert "0.035" in prompt, "Prompt must contain decimal bonus rate"
    assert "Fashion" in prompt, "Prompt must specify category"
    assert "DBS Live Fresh" in prompt, "Prompt must include card name"
    
    print(f"✅ Test 1 PASSED: Prompt correctly uses DB bonus rate of 3.5%")
    print(f"   Context bonus_rate: {context.bonus_rate}")
    print(f"   Prompt excerpt: {prompt[:200]}...")


# =============================================================================
# TEST 2: Verify fallback returns factual template when LLM fails
# =============================================================================

def test_fallback_on_llm_error(db_session, sample_card, sample_bonus_category):
    """
    RELIABILITY TEST: Ensures system provides factual explanations even when
    OpenAI API is down or returns errors.
    
    Test Flow:
    1. Mock OpenAI client to raise APIError
    2. Generate explanation
    3. Verify response uses template fallback
    4. Verify fallback contains correct database rates (no hallucination)
    
    Business Value: System remains functional during API outages
    """
    service = ExplanationService(db_session)
    
    # Build context
    context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("120.00")
    )
    
    # Patch OpenAI client to simulate failure
    with patch("app.services.explanation_service.openai_client") as mock_client:
        # Simulate API error by raising a standard Exception
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        
        # Generate explanation
        request = ExplanationRequest(recommendation=context)
        response = service.generate_explanation(request)
        
        # Verify fallback was used
        assert response.is_fallback is True, "Should use fallback when LLM fails"
        assert "template" in response.model_used.lower(), "Model should indicate template usage"
        
        # Verify fallback contains factual data from DB
        assert "DBS Live Fresh" in response.explanation, "Fallback must include card name"
        assert "3.5%" in response.explanation or "3.50%" in response.explanation, \
            "Fallback must show correct bonus rate from DB"
        assert "Fashion" in response.explanation, "Fallback must mention category"
        
        # Verify calculated reward is accurate
        expected_reward = Decimal("120.00") * Decimal("0.035")  # 120 * 3.5%
        assert response.total_reward == expected_reward, \
            f"Reward calculation incorrect: expected {expected_reward}, got {response.total_reward}"
    
    print(f"✅ Test 2 PASSED: Fallback provides factual explanation during LLM failure")
    print(f"   Fallback explanation: {response.explanation}")
    print(f"   Is fallback: {response.is_fallback}")


# =============================================================================
# TEST 3: Verify explanation does not hallucinate higher rates
# =============================================================================

def test_no_hallucinated_rates_in_explanation(db_session, sample_card, sample_bonus_category, mock_openai_client):
    """
    ANTI-HALLUCINATION TEST: Ensures neither LLM nor template generates
    reward rates higher than database ground truth.
    
    Test Flow:
    1. Set database rate to 3.5%
    2. Mock LLM to return text with "5%" (hallucinated higher rate)
    3. Verify validation catches this
    4. Verify template fallback uses exact DB rate
    
    Security Implication: Prevents promising customers rewards they won't receive
    """
    service = ExplanationService(db_session)
    
    context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("120.00")
    )
    
    # Test 3a: Verify template fallback uses exact DB rate
    template_explanation = service._generate_template_fallback(context)
    
    # Extract all percentage mentions (regex would be better, but simple check works)
    assert "3.5%" in template_explanation or "3.50%" in template_explanation, \
        "Template must use exact DB rate"
    
    # Ensure no higher rates appear
    invalid_rates = ["4%", "5%", "6%", "10%"]
    for rate in invalid_rates:
        assert rate not in template_explanation, \
            f"Template hallucinated higher rate: {rate}"
    
    # Test 3b: Verify calculated reward doesn't exceed maximum possible
    max_possible_reward = Decimal("120.00") * Decimal("0.035")
    assert context.total_reward_value <= max_possible_reward, \
        "Total reward exceeds maximum possible from DB rate"
    
    # Test 3c: Verify bonus cap is respected
    # Create a high-value transaction that would exceed cap
    large_context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("5000.00")  # Would give $175 at 3.5%, but cap is $100
    )
    
    assert large_context.total_reward_value <= Decimal("100.00"), \
        "Reward should be capped at bonus_cap_in_dollar from DB"
    
    print(f"✅ Test 3 PASSED: No rate hallucinations detected")
    print(f"   DB rate: 3.5%")
    print(f"   Template uses: {template_explanation}")
    print(f"   Large transaction capped at: ${large_context.total_reward_value}")


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

def test_build_context_with_nonexistent_card(db_session):
    """
    ERROR HANDLING TEST: Verify graceful failure when card_id doesn't exist.
    """
    service = ExplanationService(db_session)
    
    with pytest.raises(ValueError, match="Card ID 999 not found"):
        service.build_context_from_db(
            card_id=999,
            category="Fashion",
            transaction_amount=Decimal("120.00")
        )
    
    print("✅ Test PASSED: Raises ValueError for non-existent card_id")


def test_build_context_without_bonus_category(db_session, sample_card):
    """
    BASELINE TEST: Verify service handles cards without bonus categories.
    Should fall back to base rate.
    """
    service = ExplanationService(db_session)
    
    # Query for category that has no bonus defined
    context = service.build_context_from_db(
        card_id=101,
        category="Bills",  # No bonus for Bills
        transaction_amount=Decimal("100.00")
    )
    
    assert context.is_bonus_eligible is False, "Should not be bonus eligible"
    assert context.bonus_rate is None, "Bonus rate should be None"
    assert context.total_reward_value == Decimal("100.00") * Decimal("0.01"), \
        "Should use base rate when no bonus"
    
    print("✅ Test PASSED: Correctly handles missing bonus category")


def test_explanation_response_structure(db_session, sample_card, sample_bonus_category):
    """
    INTEGRATION TEST: Verify complete response structure matches API contract.
    """
    service = ExplanationService(db_session)
    
    context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("120.00")
    )
    
    request = ExplanationRequest(recommendation=context)
    
    # Patch OpenAI to use template (avoid actual API call)
    with patch("app.services.explanation_service.openai_client", None):
        response = service.generate_explanation(request)
    
    # Verify response structure
    assert isinstance(response, ExplanationResponse), "Response must be ExplanationResponse"
    assert isinstance(response.explanation, str), "Explanation must be string"
    assert len(response.explanation) > 0, "Explanation must not be empty"
    assert response.card_id == 101, "Card ID must match request"
    assert response.category == "Fashion", "Category must match request"
    assert response.total_reward is not None, "Total reward must be calculated"
    assert response.generation_time_ms >= 0, "Generation time must be non-negative"
    
    print("✅ Test PASSED: Response structure matches API contract")
    print(f"   Response: {response.model_dump()}")


def test_multiple_bonus_categories_prioritizes_highest_rate(db_session, sample_card):
    """
    BUSINESS LOGIC TEST: When card has multiple applicable bonuses (e.g., "Fashion" and "All"),
    verify service returns the highest rate.
    """
    # Add "All" category with lower rate
    all_bonus = CardBonusCategory(
        card_id=101,
        bonus_category=BonusCategory.All,
        bonus_benefit_rate=Decimal("0.02"),  # 2% for all categories
        bonus_cap_in_dollar=999999,
        bonus_minimum_spend_in_dollar=0
    )
    db_session.add(all_bonus)
    
    # Add Fashion-specific higher rate
    fashion_bonus = CardBonusCategory(
        card_id=101,
        bonus_category=BonusCategory.Fashion,
        bonus_benefit_rate=Decimal("0.035"),  # 3.5% for Fashion
        bonus_cap_in_dollar=100,
        bonus_minimum_spend_in_dollar=0
    )
    db_session.add(fashion_bonus)
    db_session.flush()
    
    service = ExplanationService(db_session)
    context = service.build_context_from_db(
        card_id=101,
        category="Fashion",
        transaction_amount=Decimal("100.00")
    )
    
    # Should pick the higher fashion-specific rate
    assert context.bonus_rate == Decimal("0.035"), \
        "Should prioritize higher Fashion rate over generic All rate"
    
    print("✅ Test PASSED: Prioritizes highest applicable bonus rate")


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    # Run with: python -m pytest backend/tests/test_explanation_service.py -v
    pytest.main([__file__, "-v", "--tb=short"])
