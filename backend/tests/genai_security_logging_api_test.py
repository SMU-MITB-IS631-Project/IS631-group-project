import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

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
from app.models.card_bonus_category import BonusCategory, CardBonusCategory  # noqa: E402
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum  # noqa: E402
from app.models.security_log import SecurityLog  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus  # noqa: E402
from app.models.user_profile import BenefitsPreference, UserProfile  # noqa: E402
from app.services.security_log_service import SecurityEventType  # noqa: E402


class GenAISecurityLoggingApiTests(unittest.TestCase):
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
                    benefits_preference=BenefitsPreference.no_preference,
                )
            )
            db.add(
                CardCatalogue(
                    card_id=10,
                    bank=BankEnum.DBS,
                    card_name="Card A",
                    benefit_type=BenefitTypeEnum.miles,
                    base_benefit_rate=Decimal("1.0"),
                    status=StatusEnum.valid,
                )
            )
            db.add(
                CardBonusCategory(
                    card_bonuscat_id=100,
                    card_id=10,
                    bonus_category=BonusCategory.Food,
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

    def test_recommendation_explain_writes_success_security_log(self):
        resp = self.client.post(
            "/api/v1/recommendation/explain",
            json={"user_id": 1, "category": "Food", "amount_sgd": 50.00},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.text)

        with self.Session() as db:
            log = (
                db.query(SecurityLog)
                .filter(SecurityLog.source == "recommendation.explain")
                .order_by(SecurityLog.id.desc())
                .first()
            )
            self.assertIsNotNone(log)
            self.assertEqual(log.event_type, SecurityEventType.GENAI_ACCESS)
            self.assertEqual(log.event_status, "success")
            self.assertEqual(log.user_id, 1)
            self.assertEqual((log.details or {}).get("endpoint"), "/api/v1/recommendation/explain")

    def test_card_reasoner_explain_db_writes_success_security_log(self):
        resp = self.client.post(
            "/api/v1/card-reasoner/explain-db",
            json={
                "card_id": 10,
                "category": "Food",
                "transaction_amount": 30.0,
                "merchant_name": "FairPrice",
                "user_id": 1,
            },
            headers={"x-user-id": "1"},
        )
        self.assertEqual(resp.status_code, 200, msg=resp.text)

        with self.Session() as db:
            log = (
                db.query(SecurityLog)
                .filter(SecurityLog.source == "card_reasoner.explain_db")
                .order_by(SecurityLog.id.desc())
                .first()
            )
            self.assertIsNotNone(log)
            self.assertEqual(log.event_type, SecurityEventType.GENAI_ACCESS)
            self.assertEqual(log.event_status, "success")
            self.assertEqual(log.user_id, 1)
            self.assertEqual((log.details or {}).get("endpoint"), "/api/v1/card-reasoner/explain-db")

    def test_card_reasoner_explain_writes_failed_security_log_on_error(self):
        payload = {
            "transaction": {
                "merchant_name": "ZARA",
                "amount": 120.0,
                "category": "Fashion",
            },
            "recommended_card": {
                "Card_ID": 10,
                "Bank": "DBS",
                "Card_Name": "Card A",
                "Benefit_type": "Miles",
                "base_benefit_rate": 1.0,
                "applied_bonus_rate": 1.0,
                "total_calculated_value": 120.0,
            },
            "comparison_cards": [],
        }

        with patch("app.routes.card_reasoner.generate_explanation", side_effect=Exception("boom")):
            resp = self.client.post(
                "/api/v1/card-reasoner/explain",
                json=payload,
                headers={"x-user-id": "1"},
            )

        self.assertEqual(resp.status_code, 500)

        with self.Session() as db:
            log = (
                db.query(SecurityLog)
                .filter(SecurityLog.source == "card_reasoner.explain")
                .order_by(SecurityLog.id.desc())
                .first()
            )
            self.assertIsNotNone(log)
            self.assertEqual(log.event_type, SecurityEventType.GENAI_ACCESS)
            self.assertEqual(log.event_status, "failed")
            self.assertEqual(log.user_id, 1)
            self.assertIn("boom", log.error_message or "")


if __name__ == "__main__":
    unittest.main()
