import pytest
from unittest.mock import patch, MagicMock
import asyncio
from decimal import Decimal
from app.services.recommendation_service import RecommendationService, CardRecommendationDTO
from app.schemas.ai_schemas import RecommendationContext
from app.services.errors import ServiceError

@pytest.fixture
def service():
    db = MagicMock()
    return RecommendationService(db)

@pytest.fixture
def mock_card():
    return CardRecommendationDTO(
        card_id=99,
        card_name="AI Card",
        base_benefit_rate=Decimal("0.01"),
        effective_benefit_rate=Decimal("0.05"),
        applied_bonus_category="AI",
        bonus_rules=[],
        reward_unit="cashback",
        estimated_reward_value=Decimal("5.00"),
        effective_rate_str="5.0% cashback",
        explanations=["AI generated recommendation."],
        reward_breakdown=None,
    )

def test_recommend_returns_ai_on_success(service, mock_card):
    with patch.object(RecommendationService, "_get_ai_recommendation", return_value=mock_card):
        best, ranked = service.recommend(user_id=1, category=None, amount_sgd=Decimal("100.00"))
        assert best == mock_card

def test_recommend_falls_back_on_timeout(service, mock_card):
    async def slow_ai(*args, **kwargs):
        await asyncio.sleep(10)
        return mock_card
    with patch.object(RecommendationService, "_get_ai_recommendation", new=slow_ai):
        import time
        start = time.time()
        best, ranked = service.recommend(user_id=1, category=None, amount_sgd=Decimal("100.00"))
        elapsed = time.time() - start
        # Must return well before the 10s sleep — proves timeout kicked in and fell back
        assert elapsed < 5, "Fallback did not return within timeout"
        # Result is DB-driven (not the AI mock_card) — with a MagicMock db it returns None
        assert best != mock_card

def test_recommend_falls_back_on_api_error(service, mock_card):
    """Service must NOT raise when AI throws ServiceError; it must return a tuple."""
    with patch.object(RecommendationService, "_get_ai_recommendation", side_effect=ServiceError(
        status_code=500,
        code="AI_ERROR",
        message="AI API failed",
        details={},
    )):
        # With a MagicMock db the DB path returns (None, []) — the important thing is
        # that no exception is raised and a valid tuple is always returned.
        result = service.recommend(user_id=1, category=None, amount_sgd=Decimal("100.00"))
        assert isinstance(result, tuple), "recommend() must return a tuple on AI failure"
        assert len(result) == 2, "recommend() must return a 2-tuple on AI failure"
        best, ranked = result
        assert best != mock_card  # DB-driven result, not the AI mock
