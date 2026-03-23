import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.card_bonus_category import BonusCategory, CardBonusCategory  # noqa: E402
from app.models.card_catalogue import BenefitTypeEnum, CardCatalogue  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard  # noqa: E402
from app.models.user_profile import UserProfile  # noqa: E402
from app.services.recommendation_service import RecommendationService  # noqa: E402


class _FakeQuery:
    def __init__(self, *, first_result=None, all_result=None, scalar_result=None):
        self._first_result = first_result
        self._all_result = list(all_result or [])
        self._scalar_result = scalar_result

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result

    def first(self):
        return self._first_result

    def scalar(self):
        return self._scalar_result


class _MockSession:
    def __init__(self, *, user=None, owned_cards=None, catalog_cards=None, bonus_rules=None):
        self._queries = {
            UserProfile: _FakeQuery(first_result=user),
            UserOwnedCard: _FakeQuery(all_result=owned_cards or []),
            CardCatalogue: _FakeQuery(all_result=catalog_cards or []),
            CardBonusCategory: _FakeQuery(all_result=bonus_rules or []),
        }

    def query(self, model):
        return self._queries[model]


class RecommendationServiceTests(unittest.TestCase):
    _UNSET = object()

    def setUp(self):
        self.default_user = SimpleNamespace(id=1, benefits_preference=SimpleNamespace(value="no_preference"))
        self.default_owned_cards = [
            SimpleNamespace(card_id=10, billing_cycle_refresh_date=date(2026, 1, 1)),
            SimpleNamespace(card_id=20, billing_cycle_refresh_date=date(2026, 1, 1)),
        ]
        self.default_catalog_cards = [
            SimpleNamespace(
                card_id=10,
                card_name="Card A",
                benefit_type=BenefitTypeEnum.MILES,
                base_benefit_rate=Decimal("1.0"),
            ),
            SimpleNamespace(
                card_id=20,
                card_name="Card B",
                benefit_type=BenefitTypeEnum.MILES,
                base_benefit_rate=Decimal("1.5"),
            ),
        ]
        self.default_bonus_rules = [
            SimpleNamespace(
                card_id=10,
                bonus_category=BonusCategory.Food,
                bonus_benefit_rate=Decimal("5.0"),
                bonus_cap_in_dollar=99999999,
                bonus_minimum_spend_in_dollar=500,
            )
        ]

        self.spend_patcher = patch.object(
            RecommendationService,
            "_get_current_cycle_spend",
            return_value=Decimal("0"),
        )
        self.spend_patcher.start()
        self.addCleanup(self.spend_patcher.stop)

    def _make_service(self, *, user=_UNSET, owned_cards=_UNSET, catalog_cards=_UNSET, bonus_rules=_UNSET):
        session = _MockSession(
            user=(self.default_user if user is self._UNSET else user),
            owned_cards=(self.default_owned_cards if owned_cards is self._UNSET else owned_cards),
            catalog_cards=(self.default_catalog_cards if catalog_cards is self._UNSET else catalog_cards),
            bonus_rules=(self.default_bonus_rules if bonus_rules is self._UNSET else bonus_rules),
        )
        return RecommendationService(session)

    def test_food_bonus_applies_when_min_spend_met(self):
        best, ranked = self._make_service().recommend(
            user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("800")
        )

        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 10)
        self.assertEqual(best.effective_benefit_rate, Decimal("5.0"))
        self.assertEqual(best.reward_unit, "miles")
        # 800 * 5.0 mpd = 4000 miles
        self.assertEqual(best.estimated_reward_value, Decimal("4000"))
        self.assertGreaterEqual(len(ranked), 2)

    def test_bonus_ignored_when_min_spend_not_met(self):
        best, _ = self._make_service().recommend(
            user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("100")
        )

        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 20)
        self.assertEqual(best.effective_benefit_rate, Decimal("1.5"))
        # 100 * 1.5 mpd = 150 miles
        self.assertEqual(best.estimated_reward_value, Decimal("150"))

    def test_no_category_uses_base_rates(self):
        best, ranked = self._make_service().recommend(user_id=1)

        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 20)
        self.assertEqual(best.reward_unit, "miles")
        # No spend passed => legacy behavior: reward calculation is 0
        self.assertEqual(best.estimated_reward_value, Decimal("0"))
        # Food-specific bonus should not apply when no category is provided.
        food_card_entry = next((r for r in ranked if r.card_id == 10), None)
        self.assertIsNotNone(food_card_entry)
        self.assertNotEqual(food_card_entry.effective_benefit_rate, Decimal("5.0"))

    def test_cashback_cap_is_applied(self):
        cashback_user = SimpleNamespace(id=1, benefits_preference=SimpleNamespace(value="cashback"))
        catalog_cards = [
            SimpleNamespace(
                card_id=30,
                card_name="Cashback Card",
                benefit_type=BenefitTypeEnum.CASHBACK,
                base_benefit_rate=Decimal("0.01"),
            )
        ]
        owned_cards = [SimpleNamespace(card_id=30, billing_cycle_refresh_date=date(2026, 1, 1))]
        bonus_rules = [
            SimpleNamespace(
                card_id=30,
                bonus_category=BonusCategory.Food,
                bonus_benefit_rate=Decimal("0.10"),
                bonus_cap_in_dollar=20,
                bonus_minimum_spend_in_dollar=0,
            )
        ]

        best, _ = self._make_service(
            user=cashback_user,
            owned_cards=owned_cards,
            catalog_cards=catalog_cards,
            bonus_rules=bonus_rules,
        ).recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("1000"))

        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 30)
        self.assertEqual(best.reward_unit, "cashback")
        self.assertTrue(best.reward_breakdown.cap_applied)
        self.assertEqual(best.reward_breakdown.reward_before_cap, Decimal("100.0"))
        self.assertEqual(best.reward_breakdown.reward_after_cap, Decimal("20"))
        self.assertEqual(best.estimated_reward_value, Decimal("20"))

    def test_preference_override_changes_recommendation_unit(self):
        catalog_cards = [
            *self.default_catalog_cards,
            SimpleNamespace(
                card_id=30,
                card_name="Cashback Card",
                benefit_type=BenefitTypeEnum.CASHBACK,
                base_benefit_rate=Decimal("0.01"),
            ),
        ]
        owned_cards = [
            *self.default_owned_cards,
            SimpleNamespace(card_id=30, billing_cycle_refresh_date=date(2026, 1, 1)),
        ]

        service = self._make_service(catalog_cards=catalog_cards, owned_cards=owned_cards)

        best_miles, _ = service.recommend(
            user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("50"), preference="miles"
        )
        self.assertIsNotNone(best_miles)
        self.assertEqual(best_miles.reward_unit, "miles")

        best_cb, _ = service.recommend(
            user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("50"), preference="cashback"
        )
        self.assertIsNotNone(best_cb)
        self.assertEqual(best_cb.reward_unit, "cashback")

    def test_returns_none_when_user_not_found(self):
        best, ranked = self._make_service(user=None).recommend(user_id=999)
        self.assertIsNone(best)
        self.assertEqual(ranked, [])

    def test_returns_none_when_no_active_cards(self):
        best, ranked = self._make_service(owned_cards=[]).recommend(user_id=1)
        self.assertIsNone(best)
        self.assertEqual(ranked, [])

    def test_preference_filter_can_exclude_all_cards(self):
        best, ranked = self._make_service().recommend(
            user_id=1,
            category=BonusCategory.Food,
            amount_sgd=Decimal("50"),
            preference="cashback",
        )
        self.assertIsNone(best)
        self.assertEqual(ranked, [])

    def test_no_category_can_still_apply_all_bonus_rule(self):
        bonus_rules = [
            SimpleNamespace(
                card_id=10,
                bonus_category=BonusCategory.All,
                bonus_benefit_rate=Decimal("2.0"),
                bonus_cap_in_dollar=99999999,
                bonus_minimum_spend_in_dollar=0,
            )
        ]

        best, _ = self._make_service(bonus_rules=bonus_rules).recommend(
            user_id=1,
            amount_sgd=Decimal("50"),
        )
        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 10)
        self.assertEqual(best.effective_benefit_rate, Decimal("2.0"))

    def test_amount_zero_uses_rate_sorting_not_reward_sorting(self):
        # amount_sgd=0 should fall back to legacy rate-based ranking.
        best, _ = self._make_service().recommend(user_id=1, amount_sgd=Decimal("0"))
        self.assertIsNotNone(best)
        self.assertEqual(best.card_id, 20)

    def test_cashback_percent_style_rate_is_supported(self):
        cashback_user = SimpleNamespace(id=1, benefits_preference=SimpleNamespace(value="cashback"))
        catalog_cards = [
            SimpleNamespace(
                card_id=30,
                card_name="Cashback Card",
                benefit_type=BenefitTypeEnum.CASHBACK,
                base_benefit_rate=Decimal("0.01"),
            )
        ]
        owned_cards = [SimpleNamespace(card_id=30, billing_cycle_refresh_date=date(2026, 1, 1))]
        bonus_rules = [
            SimpleNamespace(
                card_id=30,
                bonus_category=BonusCategory.Food,
                bonus_benefit_rate=Decimal("3.0"),  # 3% represented as percent-style.
                bonus_cap_in_dollar=99999999,
                bonus_minimum_spend_in_dollar=0,
            )
        ]

        best, _ = self._make_service(
            user=cashback_user,
            owned_cards=owned_cards,
            catalog_cards=catalog_cards,
            bonus_rules=bonus_rules,
        ).recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("100"))

        self.assertIsNotNone(best)
        self.assertEqual(best.reward_unit, "cashback")
        # 3% of 100 => 3.00
        self.assertEqual(best.estimated_reward_value, Decimal("3.00"))

    def test_points_preference_is_treated_as_miles(self):
        best, _ = self._make_service().recommend(
            user_id=1,
            category=BonusCategory.Food,
            amount_sgd=Decimal("50"),
            preference="points",
        )
        self.assertIsNotNone(best)
        self.assertEqual(best.reward_unit, "miles")


if __name__ == "__main__":
    unittest.main()
