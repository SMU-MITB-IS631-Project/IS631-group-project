from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.security import require_user_id_int
from app.models.card_bonus_category import BonusCategory
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/v1", tags=["recommendation"])


class RecommendationCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_id: int
    card_name: str
    base_benefit_rate: float
    effective_benefit_rate: float
    applied_bonus_category: Optional[str] = None
    bonus_rules: list[dict[str, Any]]

    reward_unit: str
    estimated_reward_value: float
    effective_rate_str: str
    explanations: list[str]
    reward_breakdown: dict[str, Any]


class RecommendationResponse(BaseModel):
    recommended: Optional[RecommendationCard] = None
    ranked_cards: list[RecommendationCard]


@router.get("/recommendation", response_model=RecommendationResponse)
def get_recommendation(
    db: Session = Depends(get_db),
    authenticated_user_id: int = Depends(require_user_id_int),
    user_id: Optional[int] = Query(default=None),
    category: Optional[BonusCategory] = Query(default=None),
    amount_sgd: Optional[Decimal] = Query(default=None),
):
    """Recommend the best owned card for a given spend context.

    Must-have behavior:
    - Queries active user cards from DB.
    - Queries reward rules (bonus categories) from DB.
    """
    if user_id is not None and user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not allowed to access another user's recommendations.",
                    "details": {"authenticated_user_id": authenticated_user_id, "requested_user_id": user_id},
                }
            },
        )
    resolved_user_id = authenticated_user_id

    if amount_sgd is not None and amount_sgd <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "amount_sgd must be > 0 when provided.",
                    "details": {"amount_sgd": str(amount_sgd)},
                }
            },
        )

    service = RecommendationService(db)
    best, ranked = service.recommend(user_id=resolved_user_id, category=category, amount_sgd=amount_sgd)
    if not ranked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "User has no active cards (or none match the user preference).",
                    "details": {"user_id": resolved_user_id},
                }
            },
        )

    def as_json_number(value: Any, *, reward_unit: str) -> Any:
        if isinstance(value, Decimal):
            if reward_unit == "miles":
                return int(value)
            return float(value)
        return value

    def to_model(dto):
        unit = dto.reward_unit
        return RecommendationCard(
            card_id=dto.card_id,
            card_name=dto.card_name,
            base_benefit_rate=float(dto.base_benefit_rate),
            effective_benefit_rate=float(dto.effective_benefit_rate),
            applied_bonus_category=dto.applied_bonus_category,
            bonus_rules=[
                {
                    "bonus_category": r.bonus_category,
                    "bonus_benefit_rate": as_json_number(r.bonus_benefit_rate, reward_unit=unit),
                    "bonus_cap_in_dollar": r.bonus_cap_in_dollar,
                    "bonus_minimum_spend_in_dollar": r.bonus_minimum_spend_in_dollar,
                }
                for r in dto.bonus_rules
            ],

            reward_unit=dto.reward_unit,
            estimated_reward_value=as_json_number(dto.estimated_reward_value, reward_unit=unit),
            effective_rate_str=dto.effective_rate_str,
            explanations=dto.explanations,
            reward_breakdown={
                "amount_sgd": float(dto.reward_breakdown.amount_sgd),
                "reward_unit": dto.reward_breakdown.reward_unit,
                "base_rate": as_json_number(dto.reward_breakdown.base_rate, reward_unit=unit),
                "effective_rate": as_json_number(dto.reward_breakdown.effective_rate, reward_unit=unit),
                "rate_source": dto.reward_breakdown.rate_source,
                "applied_bonus_category": dto.reward_breakdown.applied_bonus_category,
                "min_spend_required_sgd": dto.reward_breakdown.min_spend_required_sgd,
                "min_spend_met": dto.reward_breakdown.min_spend_met,
                "cap_in_dollar": dto.reward_breakdown.cap_in_dollar,
                "reward_before_cap": as_json_number(dto.reward_breakdown.reward_before_cap, reward_unit=unit),
                "reward_after_cap": as_json_number(dto.reward_breakdown.reward_after_cap, reward_unit=unit),
                "cap_applied": dto.reward_breakdown.cap_applied,
            },
        )

    return RecommendationResponse(
        recommended=to_model(best) if best else None,
        ranked_cards=[to_model(c) for c in ranked],
    )
