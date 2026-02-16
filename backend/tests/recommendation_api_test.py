import sys
import unittest
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.dependencies.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user_profile import UserProfile, BenefitsPreference  # noqa: E402
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum  # noqa: E402
from app.models.card_bonus_category import CardBonusCategory, BonusCategory  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus  # noqa: E402
from app.models.transaction import UserTransaction  # noqa: F401,E402


class RecommendationApiTests(unittest.TestCase):
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
            db.add(
                CardCatalogue(
                    card_id=10,
                    bank=BankEnum.DBS,
                    card_name="Card A",
                    benefit_type=BenefitTypeEnum.MILES,
                    base_benefit_rate=Decimal("1.0"),
                    status=StatusEnum.VALID,
                )
            )
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=100,
                    card_id=10,
                    bonus_category=BonusCategory.All,
                    bonus_benefit_rate=Decimal("2.0"),
                    bonus_cap_in_dollar=99999999,
                    bonus_minimum_spend_in_dollar=0,
                )
            )
            db.add(UserOwnedCard(user_id=1, card_id=10, status=UserOwnedCardStatus.Active))
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_full_flow_get_recommendation(self):
        resp = self.client.get(
            "/api/v1/recommendation",
            params={"user_id": 1, "category": "Food", "amount_sgd": "50"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNotNone(data.get("recommended"))
        self.assertEqual(data["recommended"]["card_id"], 10)
        self.assertEqual(data["recommended"]["reward_unit"], "miles")
        # Bonus (All) is 2.0 mpd => 50 * 2.0 = 100 miles
        self.assertEqual(data["recommended"]["estimated_reward_value"], 100)
        self.assertIn("reward_breakdown", data["recommended"])
        self.assertEqual(data["recommended"]["reward_breakdown"]["reward_after_cap"], 100)
        self.assertGreaterEqual(len(data.get("ranked_cards", [])), 1)

    def test_invalid_amount_returns_400(self):
        resp = self.client.get(
            "/api/v1/recommendation",
            params={"user_id": 1, "category": "Food", "amount_sgd": "0"},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("detail", body)
        self.assertIn("error", body["detail"])
        self.assertEqual(body["detail"]["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
