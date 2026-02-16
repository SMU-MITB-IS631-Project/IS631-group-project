from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy.orm import Session

# Import models to ensure SQLAlchemy relationship targets are registered.
from app.models.transaction import UserTransaction  # noqa: F401
from app.models.user_profile import UserProfile  # noqa: F401
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import BonusCategory, CardBonusCategory


@dataclass(frozen=True)
class BonusRuleDTO:
    bonus_category: str
    bonus_benefit_rate: Decimal
    bonus_cap_in_dollar: int
    bonus_minimum_spend_in_dollar: int


@dataclass(frozen=True)
class RewardBreakdownDTO:
    amount_sgd: Decimal
    reward_unit: str  # "miles" | "cashback"
    base_rate: Decimal
    effective_rate: Decimal
    rate_source: str  # "base" | "bonus"
    applied_bonus_category: Optional[str]
    min_spend_required_sgd: int
    min_spend_met: bool
    cap_in_dollar: Optional[int]
    reward_before_cap: Decimal
    reward_after_cap: Decimal
    cap_applied: bool


@dataclass(frozen=True)
class CardRecommendationDTO:
    card_id: int
    card_name: str
    base_benefit_rate: Decimal
    effective_benefit_rate: Decimal
    applied_bonus_category: Optional[str]
    bonus_rules: list[BonusRuleDTO]

    reward_unit: str
    estimated_reward_value: Decimal
    effective_rate_str: str
    explanations: list[str]
    reward_breakdown: RewardBreakdownDTO


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def recommend(
        self,
        *,
        user_id: int,
        category: Optional[BonusCategory] = None,
        amount_sgd: Optional[Decimal] = None,
    ) -> tuple[Optional[CardRecommendationDTO], list[CardRecommendationDTO]]:
        """Return (best_card, ranked_cards) for a user.

        Rules (minimal + DB-driven):
        - Consider only active cards in `user_owned_cards`.
        - Base rate comes from `card_catalogue.base_benefit_rate`.
        - If `category` is provided, apply the highest matching bonus rule among:
          - exact category match, or
          - `All`
          and only if `amount_sgd` meets `bonus_minimum_spend_in_dollar`.
        """
        user = self.db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if user is None:
            return None, []

        preference_raw = getattr(user, "benefits_preference", None)
        preference_value = preference_raw.value if hasattr(preference_raw, "value") else str(preference_raw)
        preference_value = (preference_value or "").strip().lower()
        preferred_unit: Optional[str]
        if preference_value == "miles":
            preferred_unit = "miles"
        elif preference_value == "cashback":
            preferred_unit = "cashback"
        else:
            preferred_unit = None

        active_cards = (
            self.db.query(UserOwnedCard)
            .filter(UserOwnedCard.user_id == user_id)
            .filter(UserOwnedCard.status == UserOwnedCardStatus.Active)
            .all()
        )
        if not active_cards:
            return None, []

        card_ids = [uc.card_id for uc in active_cards]
        catalog_rows = (
            self.db.query(CardCatalogue)
            .filter(CardCatalogue.card_id.in_(card_ids))
            .all()
        )
        catalog_by_id = {c.card_id: c for c in catalog_rows}

        bonus_rows = (
            self.db.query(CardBonusCategory)
            .filter(CardBonusCategory.card_id.in_(card_ids))
            .all()
        )
        bonus_by_card: dict[int, list[CardBonusCategory]] = {}
        for row in bonus_rows:
            bonus_by_card.setdefault(row.card_id, []).append(row)

        ranked: list[CardRecommendationDTO] = []
        for card_id in card_ids:
            card = catalog_by_id.get(card_id)
            if not card:
                continue

            base_rate = Decimal(str(card.base_benefit_rate))
            effective_rate = base_rate
            applied_category: Optional[str] = None

            reward_unit = self._reward_unit(card, preferred_unit)
            if preferred_unit is not None and reward_unit != preferred_unit:
                # If the user has a preference, only compare cards that earn in that unit.
                continue
            selected_rule: Optional[CardBonusCategory] = None
            min_spend_required = 0
            min_spend_met = True
            cap_in_dollar: Optional[int] = None
            rate_source = "base"

            rules = bonus_by_card.get(card_id, [])
            matching_rules = self._matching_bonus_rules(
                rules=rules,
                category=category,
                amount_sgd=amount_sgd,
            )
            if matching_rules:
                selected_rule = max(matching_rules, key=lambda r: Decimal(str(r.bonus_benefit_rate)))
                effective_rate = Decimal(str(selected_rule.bonus_benefit_rate))
                applied_category = str(
                    selected_rule.bonus_category.value
                    if hasattr(selected_rule.bonus_category, "value")
                    else selected_rule.bonus_category
                )
                min_spend_required = int(selected_rule.bonus_minimum_spend_in_dollar)
                min_spend_met = amount_sgd is None or amount_sgd >= Decimal(min_spend_required)
                cap_in_dollar = int(selected_rule.bonus_cap_in_dollar)
                rate_source = "bonus"

            if amount_sgd is None:
                # Keep legacy behavior: rank by rate only when no spend provided.
                amount_for_calc = Decimal("0")
            else:
                amount_for_calc = Decimal(str(amount_sgd))

            reward_before_cap, reward_after_cap, cap_applied = self._estimate_reward(
                amount_sgd=amount_for_calc,
                reward_unit=reward_unit,
                effective_rate=effective_rate,
                cap_in_dollar=cap_in_dollar if selected_rule is not None else None,
                apply_cap=(selected_rule is not None),
            )

            effective_rate_str = self._format_effective_rate(reward_unit=reward_unit, effective_rate=effective_rate)
            estimated_reward_value = self._format_reward_value(reward_unit=reward_unit, reward=reward_after_cap)

            explanations = self._build_explanations(
                card_name=card.card_name,
                reward_unit=reward_unit,
                amount_sgd=amount_for_calc,
                effective_rate_str=effective_rate_str,
                applied_category=applied_category,
                min_spend_required=min_spend_required,
                min_spend_met=min_spend_met,
                cap_in_dollar=cap_in_dollar if selected_rule is not None else None,
                cap_applied=cap_applied,
            )

            ranked.append(
                CardRecommendationDTO(
                    card_id=card.card_id,
                    card_name=card.card_name,
                    base_benefit_rate=base_rate,
                    effective_benefit_rate=effective_rate,
                    applied_bonus_category=applied_category,
                    bonus_rules=[
                        BonusRuleDTO(
                            bonus_category=str(r.bonus_category.value if hasattr(r.bonus_category, "value") else r.bonus_category),
                            bonus_benefit_rate=Decimal(str(r.bonus_benefit_rate)),
                            bonus_cap_in_dollar=int(r.bonus_cap_in_dollar),
                            bonus_minimum_spend_in_dollar=int(r.bonus_minimum_spend_in_dollar),
                        )
                        for r in rules
                    ],

                    reward_unit=reward_unit,
                    estimated_reward_value=estimated_reward_value,
                    effective_rate_str=effective_rate_str,
                    explanations=explanations,
                    reward_breakdown=RewardBreakdownDTO(
                        amount_sgd=amount_for_calc,
                        reward_unit=reward_unit,
                        base_rate=base_rate,
                        effective_rate=effective_rate,
                        rate_source=rate_source,
                        applied_bonus_category=applied_category,
                        min_spend_required_sgd=min_spend_required,
                        min_spend_met=min_spend_met,
                        cap_in_dollar=(cap_in_dollar if selected_rule is not None else None),
                        reward_before_cap=reward_before_cap,
                        reward_after_cap=reward_after_cap,
                        cap_applied=cap_applied,
                    ),
                )
            )

        ranked.sort(key=lambda c: (c.effective_benefit_rate, c.base_benefit_rate), reverse=True)
        return (ranked[0] if ranked else None), ranked

    @staticmethod
    def _matching_bonus_rules(
        *,
        rules: Iterable[CardBonusCategory],
        category: Optional[BonusCategory],
        amount_sgd: Optional[Decimal],
    ) -> list[CardBonusCategory]:
        # If no category was provided, only consider "All" rules.
        # If a category is provided, consider (category OR All).
        allowed = (BonusCategory.All,) if category is None else (category, BonusCategory.All)

        matches: list[CardBonusCategory] = []
        for rule in rules:
            if rule.bonus_category not in allowed:
                continue
            if amount_sgd is not None:
                if amount_sgd < Decimal(int(rule.bonus_minimum_spend_in_dollar)):
                    continue
            matches.append(rule)
        return matches

    @staticmethod
    def _reward_unit(card: CardCatalogue, preferred_unit: Optional[str]) -> str:
        benefit_type = getattr(card, "benefit_type", None)
        raw = (benefit_type.value if hasattr(benefit_type, "value") else str(benefit_type)).upper()
        if "BOTH" in raw:
            return preferred_unit or "miles"
        if "CASH" in raw:
            return "cashback"
        if "MILE" in raw:
            return "miles"
        return preferred_unit or "miles"

    @staticmethod
    def _cashback_fraction(rate: Decimal) -> Decimal:
        # Supports both representations:
        # - fraction: 0.015 => 1.5%
        # - percent: 3.0 => 3%
        if rate > Decimal("1"):
            return rate / Decimal("100")
        return rate

    def _estimate_reward(
        self,
        *,
        amount_sgd: Decimal,
        reward_unit: str,
        effective_rate: Decimal,
        cap_in_dollar: Optional[int],
        apply_cap: bool,
    ) -> tuple[Decimal, Decimal, bool]:
        if amount_sgd <= 0:
            return Decimal("0"), Decimal("0"), False

        if reward_unit == "cashback":
            fraction = self._cashback_fraction(effective_rate)
            reward = (amount_sgd * fraction)
            if apply_cap and cap_in_dollar is not None:
                cap_value = Decimal(int(cap_in_dollar))
                capped = min(reward, cap_value)
                return reward, capped, capped != reward
            return reward, reward, False

        # miles (mpd)
        miles = amount_sgd * effective_rate
        return miles, miles, False

    @staticmethod
    def _format_effective_rate(*, reward_unit: str, effective_rate: Decimal) -> str:
        if reward_unit == "cashback":
            percent = effective_rate if effective_rate > Decimal("1") else (effective_rate * Decimal("100"))
            return f"{percent:.1f}% cashback"
        return f"{effective_rate:.1f} mpd"

    @staticmethod
    def _format_reward_value(*, reward_unit: str, reward: Decimal) -> Decimal:
        if reward_unit == "cashback":
            return reward.quantize(Decimal("0.01"))
        # miles
        return Decimal(int(reward.to_integral_value(rounding="ROUND_HALF_UP")))

    @staticmethod
    def _build_explanations(
        *,
        card_name: str,
        reward_unit: str,
        amount_sgd: Decimal,
        effective_rate_str: str,
        applied_category: Optional[str],
        min_spend_required: int,
        min_spend_met: bool,
        cap_in_dollar: Optional[int],
        cap_applied: bool,
    ) -> list[str]:
        lines: list[str] = []
        if applied_category:
            if min_spend_required > 0 and not min_spend_met:
                lines.append(
                    f"Bonus category '{applied_category}' exists but minimum spend ${min_spend_required} is not met."
                )
            else:
                lines.append(f"Applies bonus category '{applied_category}' for this spend.")
        else:
            lines.append("No matching bonus category rule applied; using base rate.")

        lines.append(f"Effective rate: {effective_rate_str} on ${amount_sgd}.")

        if reward_unit == "cashback" and cap_in_dollar is not None:
            if cap_applied:
                lines.append(f"Cashback capped at ${cap_in_dollar}.")
            else:
                lines.append(f"Cashback cap is ${cap_in_dollar} (not reached).")

        # Keep 2-5 bullets.
        return lines[:5]
