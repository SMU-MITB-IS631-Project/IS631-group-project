import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from openai import OpenAI
from dotenv import load_dotenv


# Ensure backend/ is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from app.models.card_catalogue import BenefitTypeEnum  # noqa: E402
from app.schemas.ai_schemas import ExplanationRequest, RecommendationContext  # noqa: E402
from app.services.explanation_service import ExplanationService  # noqa: E402


@pytest.fixture
def mock_db() -> Mock:
    return Mock()


@pytest.fixture
def explanation_service(mock_db: Mock) -> ExplanationService:
    return ExplanationService(db=mock_db)


def _build_request() -> ExplanationRequest:
    return ExplanationRequest(
        recommendation=RecommendationContext(
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
        ),
        comparison_cards=[],
    )


@pytest.mark.unit
def test_template_fallback_returns_expected_fields_and_content(
    explanation_service: ExplanationService,
):
    """Validate deterministic fallback behavior without external API calls."""
    request = _build_request()

    with patch("app.services.explanation_service.openai_client", None):
        response = explanation_service.generate_explanation(request)

    assert response.is_fallback is True
    assert response.model_used == "template"
    assert response.card_id == 1
    assert response.category == "Fashion"
    assert response.total_reward == Decimal("5.00")
    assert response.generation_time_ms is not None

    explanation = response.explanation
    assert "DBS Live Fresh" in explanation
    assert "Fashion" in explanation
    assert "5.00%" in explanation
    assert "SGD 5.00" in explanation


@pytest.mark.unit
@pytest.mark.llm
def test_template_explanation_is_rated_high_by_llm_judge(
    explanation_service: ExplanationService,
):
    """Generate explanation via service and have an LLM judge rate its quality (1-5)."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    run_llm_tests = os.getenv("RUN_LLM_TESTS")
    if not openai_api_key or run_llm_tests != "1":
        pytest.skip(
            "LLM tests are disabled. Set OPENAI_API_KEY and RUN_LLM_TESTS=1 to run this test."
        )

    request = _build_request()

    # Force deterministic template generation to keep this test stable.
    with patch("app.services.explanation_service.openai_client", None):
        response = explanation_service.generate_explanation(request)

    explanation = response.explanation
    assert explanation
    assert response.is_fallback is True
    assert "template" in response.model_used

    judge_prompt = (
        "Given this recommendation context: "
        "card='DBS Live Fresh', bank='DBS', category='Fashion', amount=100 SGD, "
        "base_rate=1%, bonus_rate=5%, total_reward=5 SGD. "
        f"Rate the following explanation from 1 (poor) to 5 (excellent): {explanation}. "
        "Return only one integer from 1 to 5."
    )

    judge_client = OpenAI(api_key=openai_api_key)
    completion = judge_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You evaluate recommendation explanations."},
            {"role": "user", "content": judge_prompt},
        ],
        temperature=0,
        max_tokens=5,
    )

    rating_text = (completion.choices[0].message.content or "").strip()
    rating_digits = "".join(ch for ch in rating_text if ch.isdigit())
    assert rating_digits, f"Expected numeric rating, got: {rating_text}"

    rating = int(rating_digits[0])
    assert rating >= 4, f"Expected rating >=4, got {rating} (raw: {rating_text})"
