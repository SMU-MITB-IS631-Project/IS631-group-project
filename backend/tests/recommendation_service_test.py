import sys
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.models.user_profile import UserProfile, BenefitsPreference  # noqa: E402
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum  # noqa: E402
from app.models.card_bonus_category import CardBonusCategory, BonusCategory  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus  # noqa: E402
from app.models.transaction import UserTransaction  # noqa: F401,E402
from app.services.recommendation_service import RecommendationService  # noqa: E402


class RecommendationServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        with self.Session() as db:
            db.add(
                UserProfile(
                    id=1,
                    username="u1",
                    password_hash="x",
                    benefits_preference=BenefitsPreference.No_preference,
                )
            )

            db.add_all(
                [
                    CardCatalogue(
                        card_id=10,
                        bank=BankEnum.DBS,
                        card_name="Card A",
                        benefit_type=BenefitTypeEnum.MILES,
                        base_benefit_rate=Decimal("1.0"),
                        status=StatusEnum.VALID,
                    ),
                    CardCatalogue(
                        card_id=20,
                        bank=BankEnum.DBS,
                        card_name="Card B",
                        benefit_type=BenefitTypeEnum.MILES,
                        base_benefit_rate=Decimal("1.5"),
                        status=StatusEnum.VALID,
                    ),
                ]
            )

            db.add(
                CardBonusCategory(
                    card_bonuscat_id=100,
                    card_id=10,
                    bonus_category=BonusCategory.Food,
                    bonus_benefit_rate=Decimal("5.0"),
                    bonus_cap_in_dollar=99999999,
                    bonus_minimum_spend_in_dollar=500,
                )
            )

            db.add_all(
                [
                    UserOwnedCard(user_id=1, card_id=10, status=UserOwnedCardStatus.Active),
                    UserOwnedCard(user_id=1, card_id=20, status=UserOwnedCardStatus.Active),
                ]
            )
            db.commit()

    def test_food_bonus_applies_when_min_spend_met(self):
        with self.Session() as db:
            best, ranked = RecommendationService(db).recommend(
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
        with self.Session() as db:
            best, _ = RecommendationService(db).recommend(
                user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("100")
            )
            self.assertIsNotNone(best)
            self.assertEqual(best.card_id, 20)
            self.assertEqual(best.effective_benefit_rate, Decimal("1.5"))
            # 100 * 1.5 mpd = 150 miles
            self.assertEqual(best.estimated_reward_value, Decimal("150"))

    def test_no_category_uses_base_rates(self):
        with self.Session() as db:
            best, ranked = RecommendationService(db).recommend(user_id=1)
            self.assertIsNotNone(best)
            self.assertEqual(best.card_id, 20)
            self.assertEqual(best.reward_unit, "miles")
            # No spend passed => legacy behavior: reward calculation is 0
            self.assertEqual(best.estimated_reward_value, Decimal("0"))
            # Ensure that a Food-specific bonus (5.0 mpd on card 10) is not applied when no category is specified.
            food_card_entry = next((r for r in ranked if r.card_id == 10), None)
            self.assertIsNotNone(food_card_entry)
            self.assertNotEqual(food_card_entry.effective_benefit_rate, Decimal("5.0"))

    def test_cashback_cap_is_applied(self):
        with self.Session() as db:
            # Ensure we recommend within cashback cards (miles vs cashback is otherwise not comparable).
            profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
            self.assertIsNotNone(profile)
            profile.benefits_preference = BenefitsPreference.Cashback

            db.add(
                CardCatalogue(
                    card_id=30,
                    bank=BankEnum.DBS,
                    card_name="Cashback Card",
                    benefit_type=BenefitTypeEnum.CASHBACK,
                    base_benefit_rate=Decimal("0.01"),
                    status=StatusEnum.VALID,
                )
            )
            db.add(UserOwnedCard(user_id=1, card_id=30, status=UserOwnedCardStatus.Active))
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=200,
                    card_id=30,
                    bonus_category=BonusCategory.Food,
                    bonus_benefit_rate=Decimal("0.10"),  # 10% cashback
                    bonus_cap_in_dollar=20,
                    bonus_minimum_spend_in_dollar=0,
                )
            )
            db.commit()

            best, _ = RecommendationService(db).recommend(
                user_id=1, category=BonusCategory.Food, amount_sgd=Decimal("1000")
            )

            self.assertIsNotNone(best)
            self.assertEqual(best.card_id, 30)
            self.assertEqual(best.reward_unit, "cashback")
            self.assertTrue(best.reward_breakdown.cap_applied)
            self.assertEqual(best.reward_breakdown.reward_before_cap, Decimal("100.0"))
            self.assertEqual(best.reward_breakdown.reward_after_cap, Decimal("20"))
            self.assertEqual(best.estimated_reward_value, Decimal("20.00"))


if __name__ == "__main__":
    unittest.main()
