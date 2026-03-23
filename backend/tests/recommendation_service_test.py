import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.card_bonus_category import BonusCategory, CardBonusCategory  # noqa: E402
from app.models.card_catalogue import BenefitTypeEnum, CardCatalogue  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard  # noqa: E402
from app.models.user_profile import UserProfile  # noqa: E402
from app.services.recommendation_service import RecommendationService  # noqa: E402


_UNSET = object()


@pytest.fixture(autouse=True)
def mock_cycle_spend():
    with patch.object(RecommendationService, "_get_current_cycle_spend", return_value=Decimal("0")):
        yield


@pytest.fixture
def default_user():
    return SimpleNamespace(id=1, benefits_preference=SimpleNamespace(value="no_preference"))


@pytest.fixture
def default_owned_cards():
    return [
        SimpleNamespace(card_id=10, billing_cycle_refresh_date=date(2026, 1, 1)),
        SimpleNamespace(card_id=20, billing_cycle_refresh_date=date(2026, 1, 1)),
    ]


@pytest.fixture
def default_catalog_cards():
    return [
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


@pytest.fixture
def default_bonus_rules():
    return [
        SimpleNamespace(
            card_id=10,
            bonus_category=BonusCategory.Food,
            bonus_benefit_rate=Decimal("5.0"),
            bonus_cap_in_dollar=99999999,
            bonus_minimum_spend_in_dollar=500,
        )
    ]



def _make_query(*, first_result=None, all_result=None, scalar_result=None) -> Mock:
    query = Mock()
    query.filter.return_value = query
    query.first.return_value = first_result
    query.all.return_value = list(all_result or [])
    query.scalar.return_value = scalar_result
    return query


@pytest.fixture
def make_service(default_user, default_owned_cards, default_catalog_cards, default_bonus_rules):
    def _factory(*, user=_UNSET, owned_cards=_UNSET, catalog_cards=_UNSET, bonus_rules=_UNSET):
        resolved_user = default_user if user is _UNSET else user
        resolved_owned_cards = default_owned_cards if owned_cards is _UNSET else owned_cards
        resolved_catalog_cards = default_catalog_cards if catalog_cards is _UNSET else catalog_cards
        resolved_bonus_rules = default_bonus_rules if bonus_rules is _UNSET else bonus_rules

        session = Mock()
        query_map = {
            UserProfile: _make_query(first_result=resolved_user),
            UserOwnedCard: _make_query(all_result=resolved_owned_cards),
            CardCatalogue: _make_query(all_result=resolved_catalog_cards),
            CardBonusCategory: _make_query(all_result=resolved_bonus_rules),
        }
        session.query.side_effect = lambda model: query_map[model]
        return RecommendationService(session)

    return _factory


def test_food_bonus_applies_when_min_spend_met(make_service):
    best, ranked = make_service().recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("800"))

    assert best is not None
    assert best.card_id == 10
    assert best.effective_benefit_rate == Decimal("5.0")
    assert best.reward_unit == "miles"
    # 800 * 5.0 mpd = 4000 miles
    assert best.estimated_reward_value == Decimal("4000")
    assert len(ranked) >= 2


def test_bonus_ignored_when_min_spend_not_met(make_service):
    best, _ = make_service().recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("100"))

    assert best is not None
    assert best.card_id == 20
    assert best.effective_benefit_rate == Decimal("1.5")
    # 100 * 1.5 mpd = 150 miles
    assert best.estimated_reward_value == Decimal("150")


def test_no_category_uses_base_rates(make_service):
    best, ranked = make_service().recommend(user_id=1)

    assert best is not None
    assert best.card_id == 20
    assert best.reward_unit == "miles"
    # No spend passed => legacy behavior: reward calculation is 0
    assert best.estimated_reward_value == Decimal("0")
    # Food-specific bonus should not apply when no category is provided.
    food_card_entry = next((r for r in ranked if r.card_id == 10), None)
    assert food_card_entry is not None
    assert food_card_entry.effective_benefit_rate != Decimal("5.0")


def test_cashback_cap_is_applied(make_service):
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

    best, _ = make_service(
        user=cashback_user,
        owned_cards=owned_cards,
        catalog_cards=catalog_cards,
        bonus_rules=bonus_rules,
    ).recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("1000"))

    assert best is not None
    assert best.card_id == 30
    assert best.reward_unit == "cashback"
    assert best.reward_breakdown.cap_applied
    assert best.reward_breakdown.reward_before_cap == Decimal("100.0")
    assert best.reward_breakdown.reward_after_cap == Decimal("20")
    assert best.estimated_reward_value == Decimal("20")


def test_preference_override_changes_recommendation_unit(
    make_service,
    default_catalog_cards,
    default_owned_cards,
):
    catalog_cards = [
        *default_catalog_cards,
        SimpleNamespace(
            card_id=30,
            card_name="Cashback Card",
            benefit_type=BenefitTypeEnum.CASHBACK,
            base_benefit_rate=Decimal("0.01"),
        ),
    ]
    owned_cards = [
        *default_owned_cards,
        SimpleNamespace(card_id=30, billing_cycle_refresh_date=date(2026, 1, 1)),
    ]

    service = make_service(catalog_cards=catalog_cards, owned_cards=owned_cards)

    best_miles, _ = service.recommend(
        user_id=1,
        category=BonusCategory.Food,
        amount_sgd=Decimal("50"),
        preference="miles",
    )
    assert best_miles is not None
    assert best_miles.reward_unit == "miles"

    best_cb, _ = service.recommend(
        user_id=1,
        category=BonusCategory.Food,
        amount_sgd=Decimal("50"),
        preference="cashback",
    )
    assert best_cb is not None
    assert best_cb.reward_unit == "cashback"


def test_returns_none_when_user_not_found(make_service):
    best, ranked = make_service(user=None).recommend(user_id=999)
    assert best is None
    assert ranked == []


def test_returns_none_when_no_active_cards(make_service):
    best, ranked = make_service(owned_cards=[]).recommend(user_id=1)
    assert best is None
    assert ranked == []


def test_preference_filter_can_exclude_all_cards(make_service):
    best, ranked = make_service().recommend(
        user_id=1,
        category=BonusCategory.Food,
        amount_sgd=Decimal("50"),
        preference="cashback",
    )
    assert best is None
    assert ranked == []


def test_no_category_can_still_apply_all_bonus_rule(make_service):
    bonus_rules = [
        SimpleNamespace(
            card_id=10,
            bonus_category=BonusCategory.All,
            bonus_benefit_rate=Decimal("2.0"),
            bonus_cap_in_dollar=99999999,
            bonus_minimum_spend_in_dollar=0,
        )
    ]

    best, _ = make_service(bonus_rules=bonus_rules).recommend(user_id=1, amount_sgd=Decimal("50"))
    assert best is not None
    assert best.card_id == 10
    assert best.effective_benefit_rate == Decimal("2.0")


def test_amount_zero_uses_rate_sorting_not_reward_sorting(make_service):
    # amount_sgd=0 should fall back to legacy rate-based ranking.
    best, _ = make_service().recommend(user_id=1, amount_sgd=Decimal("0"))
    assert best is not None
    assert best.card_id == 20


def test_cashback_percent_style_rate_is_supported(make_service):
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

    best, _ = make_service(
        user=cashback_user,
        owned_cards=owned_cards,
        catalog_cards=catalog_cards,
        bonus_rules=bonus_rules,
    ).recommend(user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("100"))

    assert best is not None
    assert best.reward_unit == "cashback"
    # 3% of 100 => 3.00
    assert best.estimated_reward_value == Decimal("3.00")


def test_points_preference_is_treated_as_miles(make_service):
    best, _ = make_service().recommend(
        user_id=1,
        category=BonusCategory.Food,
        amount_sgd=Decimal("50"),
        preference="points",
    )
    assert best is not None
    assert best.reward_unit == "miles"
