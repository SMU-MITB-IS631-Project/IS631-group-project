from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from openai import APIError, APITimeoutError

from app.models.card_bonus_category import BonusCategory, CardBonusCategory
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.schemas.ai_schemas import ExplanationResponse, RecommendationContext
from app.services.explanation_service import ExplanationService


@pytest.fixture
def mock_db() -> Mock:
    return Mock()


@pytest.fixture
def explanation_service(mock_db: Mock) -> ExplanationService:
    return ExplanationService(db=mock_db)


def _cashback_context() -> RecommendationContext:
    return RecommendationContext(
        card_id=1,
        card_name="DBS Live Fresh",
        bank="DBS",
        benefit_type=BenefitTypeEnum.cashback,
        category="Fashion",
        transaction_amount=Decimal("100.00"),
        base_rate=Decimal("0.01"),
        bonus_rate=Decimal("0.05"),
        is_bonus_eligible=True,
        bonus_cap_sgd=100,
        bonus_min_spend_sgd=50,
        total_reward_value=Decimal("5.00"),
    )


def _miles_context() -> RecommendationContext:
    return RecommendationContext(
        card_id=2,
        card_name="UOB PRVI Miles",
        bank="UOB",
        benefit_type=BenefitTypeEnum.miles,
        category="Travel",
        transaction_amount=Decimal("100.00"),
        base_rate=Decimal("1.20"),
        bonus_rate=Decimal("2.00"),
        is_bonus_eligible=True,
        bonus_cap_sgd=500,
        bonus_min_spend_sgd=0,
        total_reward_value=Decimal("200"),
    )


@pytest.mark.unit
def test_build_context_from_db_raises_when_card_not_found(explanation_service: ExplanationService, mock_db: Mock):
    card_query = Mock()
    card_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = card_query

    with pytest.raises(ValueError, match="Card ID 999 not found"):
        explanation_service.build_context_from_db(
            card_id=999,
            category="Fashion",
            transaction_amount=Decimal("10.00"),
        )


@pytest.mark.unit
def test_get_bonus_for_category_invalid_category_returns_non_eligible(explanation_service: ExplanationService):
    result = explanation_service._get_bonus_for_category(card_id=1, category="InvalidCategory")

    assert result == {
        "is_bonus_eligible": False,
        "bonus_rate": None,
        "bonus_cap_sgd": None,
        "bonus_min_spend_sgd": None,
    }


@pytest.mark.unit
def test_get_bonus_for_category_no_match_returns_non_eligible(explanation_service: ExplanationService, mock_db: Mock):
    bonus_query = Mock()
    bonus_query.filter.return_value.order_by.return_value.first.return_value = None
    mock_db.query.return_value = bonus_query

    result = explanation_service._get_bonus_for_category(card_id=1, category="Fashion")

    assert result["is_bonus_eligible"] is False
    assert result["bonus_rate"] is None


@pytest.mark.unit
def test_get_bonus_for_category_returns_bonus_data(explanation_service: ExplanationService, mock_db: Mock):
    bonus_row = CardBonusCategory(
        card_id=1,
        bonus_category=BonusCategory.Fashion,
        bonus_benefit_rate=Decimal("0.05"),
        bonus_cap_in_dollar=200,
        bonus_minimum_spend_in_dollar=100,
    )
    bonus_query = Mock()
    bonus_query.filter.return_value.order_by.return_value.first.return_value = bonus_row
    mock_db.query.return_value = bonus_query

    result = explanation_service._get_bonus_for_category(card_id=1, category="Fashion")

    assert result == {
        "is_bonus_eligible": True,
        "bonus_rate": Decimal("0.05"),
        "bonus_cap_sgd": 200,
        "bonus_min_spend_sgd": 100,
    }


@pytest.mark.unit
def test_build_context_from_db_applies_bonus_and_cap(explanation_service: ExplanationService, mock_db: Mock):
    card = CardCatalogue(
        card_id=1,
        bank=BankEnum.DBS,
        card_name="DBS Live Fresh",
        benefit_type=BenefitTypeEnum.cashback,
        base_benefit_rate=Decimal("0.01"),
        status=StatusEnum.valid,
    )
    card_query = Mock()
    card_query.filter.return_value.first.return_value = card

    def query_side_effect(model):
        if model is CardCatalogue:
            return card_query
        raise AssertionError(f"Unexpected model queried: {model}")

    mock_db.query.side_effect = query_side_effect

    with patch.object(
        explanation_service,
        "_get_bonus_for_category",
        return_value={
            "is_bonus_eligible": True,
            "bonus_rate": Decimal("0.10"),
            "bonus_cap_sgd": 5,
            "bonus_min_spend_sgd": 0,
        },
    ):
        context = explanation_service.build_context_from_db(
            card_id=1,
            category="Fashion",
            transaction_amount=Decimal("100.00"),
            merchant_name="Zalora",
        )

    assert context.is_bonus_eligible is True
    assert context.total_reward_value == Decimal("5")
    assert context.merchant_name == "Zalora"


@pytest.mark.unit
def test_build_context_from_db_falls_back_to_base_rate_when_min_spend_not_met(
    explanation_service: ExplanationService,
    mock_db: Mock,
):
    card = CardCatalogue(
        card_id=1,
        bank=BankEnum.DBS,
        card_name="DBS Live Fresh",
        benefit_type=BenefitTypeEnum.cashback,
        base_benefit_rate=Decimal("0.01"),
        status=StatusEnum.valid,
    )
    card_query = Mock()
    card_query.filter.return_value.first.return_value = card
    mock_db.query.return_value = card_query

    with patch.object(
        explanation_service,
        "_get_bonus_for_category",
        return_value={
            "is_bonus_eligible": True,
            "bonus_rate": Decimal("0.10"),
            "bonus_cap_sgd": 500,
            "bonus_min_spend_sgd": 200,
        },
    ):
        context = explanation_service.build_context_from_db(
            card_id=1,
            category="Fashion",
            transaction_amount=Decimal("100.00"),
        )

    assert context.is_bonus_eligible is False
    assert context.total_reward_value == Decimal("1.0000")


@pytest.mark.unit
def test_build_prompt_miles_includes_bonus_and_alternatives(explanation_service: ExplanationService):
    primary = _miles_context()
    alt_cashback = RecommendationContext(
        card_id=3,
        card_name="Citi Cash Back",
        bank="CITI",
        benefit_type=BenefitTypeEnum.cashback,
        category="Travel",
        transaction_amount=Decimal("100.00"),
        base_rate=Decimal("0.015"),
        bonus_rate=None,
        is_bonus_eligible=False,
        bonus_cap_sgd=None,
        bonus_min_spend_sgd=None,
        total_reward_value=Decimal("1.50"),
    )
    alt_miles = RecommendationContext(
        card_id=4,
        card_name="Citi PremierMiles",
        bank="CITI",
        benefit_type=BenefitTypeEnum.miles,
        category="Travel",
        transaction_amount=Decimal("100.00"),
        base_rate=Decimal("1.20"),
        bonus_rate=Decimal("1.40"),
        is_bonus_eligible=True,
        bonus_cap_sgd=None,
        bonus_min_spend_sgd=None,
        total_reward_value=Decimal("140"),
    )

    prompt = explanation_service._build_prompt(primary, [alt_cashback, alt_miles])

    assert "Effective Rate: 2.00 mpd" in prompt
    assert "Base Rate: 1.20 mpd" in prompt
    assert "Bonus Rate: 2.00 mpd" in prompt
    assert "Total Reward: 200 miles" in prompt
    assert "Alternative Considered:" in prompt
    assert "1.50% cashback = SGD 1.50" in prompt
    assert "1.40 mpd = 140 miles" in prompt


@pytest.mark.unit
def test_try_llm_generation_success_returns_model_output(explanation_service: ExplanationService):
    context = _cashback_context()
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Great choice"))]

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("app.services.explanation_service.openai_client", mock_client):
        explanation, model_used, is_fallback = explanation_service._try_llm_generation("prompt", context)

    assert explanation == "Great choice"
    assert model_used
    assert is_fallback is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "side_effect,expected_model",
    [
        (APITimeoutError(request=Mock()), "template_timeout"),
        (APIError(message="err", request=Mock(), body=None), "template_error"),
        (RuntimeError("boom"), "template_exception"),
    ],
)
def test_try_llm_generation_error_paths_fallback_to_template(
    explanation_service: ExplanationService,
    side_effect: Exception,
    expected_model: str,
):
    context = _cashback_context()
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.explanation_service.openai_client", mock_client):
        explanation, model_used, is_fallback = explanation_service._try_llm_generation("prompt", context)

    assert explanation
    assert model_used == expected_model
    assert is_fallback is True


@pytest.mark.unit
def test_generate_template_fallback_miles_non_bonus_path(explanation_service: ExplanationService):
    context = RecommendationContext(
        card_id=2,
        card_name="UOB PRVI Miles",
        bank="UOB",
        benefit_type=BenefitTypeEnum.miles,
        category="Travel",
        transaction_amount=Decimal("100.00"),
        base_rate=Decimal("1.20"),
        bonus_rate=None,
        is_bonus_eligible=False,
        bonus_cap_sgd=99999999,
        bonus_min_spend_sgd=None,
        total_reward_value=Decimal("120"),
    )

    explanation = explanation_service._generate_template_fallback(context)

    assert "1.20 mpd" in explanation
    assert "on all purchases" in explanation
    assert "120 miles" in explanation
    assert "monthly cap" not in explanation


@pytest.mark.unit
def test_create_audit_log_hashes_prompt_and_counts_response_length(explanation_service: ExplanationService):
    response = ExplanationResponse(
        explanation="Test explanation",
        card_id=1,
        category="Fashion",
        total_reward=Decimal("5.00"),
        model_used="template",
        is_fallback=True,
        generation_time_ms=10,
    )

    with patch(
        "app.services.explanation_service.utc_now",
        return_value=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    ):
        log_entry = explanation_service.create_audit_log(
            response=response,
            user_id=77,
            prompt="prompt-to-hash",
        )

    assert log_entry.timestamp == "2026-01-02T03:04:05+00:00"
    assert log_entry.user_id == 77
    assert log_entry.prompt_hash is not None
    assert len(log_entry.prompt_hash) == 16
    assert log_entry.response_length == len("Test explanation")
