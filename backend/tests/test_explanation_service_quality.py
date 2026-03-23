import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openai import OpenAI


# Ensure backend/ is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.card_catalogue import BenefitTypeEnum  # noqa: E402
from app.schemas.ai_schemas import ExplanationRequest, RecommendationContext  # noqa: E402
from app.services.explanation_service import ExplanationService  # noqa: E402


@pytest.mark.unit
@pytest.mark.llm
def test_template_explanation_is_rated_high_by_llm_judge():
    """Generate explanation via service and have an LLM judge rate its quality (1-5)."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not set; skipping LLM-judge quality test")

    request = ExplanationRequest(
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

    # Force deterministic template generation to keep this test stable.
    with patch("app.services.explanation_service.openai_client", None):
        service = ExplanationService(db=MagicMock())
        response = service.generate_explanation(request)

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
