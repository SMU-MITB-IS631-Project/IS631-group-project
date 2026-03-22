from pathlib import Path
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.db import get_db
from app.models.card_bonus_category import BonusCategory, CardBonusCategory
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.models.card_change_notification import CardChangeNotification
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import BenefitsPreference, UserProfile
from app.routes.catalog import router as catalog_router
from app.routes.notifications import router as notifications_router


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test_notifications.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()
app.include_router(catalog_router)
app.include_router(notifications_router)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add_all(
            [
                UserProfile(
                    id=1,
                    username="owner_user",
                    cognito_sub="test-cognito-sub-owner-1",
                    benefits_preference=BenefitsPreference.no_preference,
                ),
                UserProfile(
                    id=2,
                    username="non_owner_user",
                    cognito_sub="test-cognito-sub-owner-2",
                    benefits_preference=BenefitsPreference.no_preference,
                ),
            ]
        )

        db.add_all(
            [
                CardCatalogue(
                    card_id=101,
                    bank=BankEnum.DBS,
                    card_name="DBS Test Rewards",
                    benefit_type=BenefitTypeEnum.cashback,
                    base_benefit_rate=Decimal("0.0100"),
                    status=StatusEnum.valid,
                ),
                CardCatalogue(
                    card_id=202,
                    bank=BankEnum.CITI,
                    card_name="CITI Other Card",
                    benefit_type=BenefitTypeEnum.cashback,
                    base_benefit_rate=Decimal("0.0150"),
                    status=StatusEnum.valid,
                ),
            ]
        )

        db.add(
            CardBonusCategory(
                card_id=101,
                bonus_category=BonusCategory.Food,
                bonus_benefit_rate=Decimal("0.0300"),
                bonus_cap_in_dollar=80,
                bonus_minimum_spend_in_dollar=500,
            )
        )

        db.add(
            UserOwnedCard(
                user_id=1,
                card_id=101,
                status=UserOwnedCardStatus.Active,
            )
        )

        db.commit()
        yield
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_owner_gets_notification_when_rewards_change(client: TestClient):
    response = client.put(
        "/api/v1/catalog/101/rewards",
        json={
            "reward_update": {
                "base_benefit_rate": 0.02,
                "effective_date": "2026-04-01",
                "bonus_rules": [
                    {
                        "bonus_category": "Food",
                        "bonus_benefit_rate": 0.05,
                        "bonus_cap_in_dollar": 120,
                        "bonus_minimum_spend_in_dollar": 600,
                    }
                ],
            }
        },
    )

    assert response.status_code == 200
    result = response.json()["update_result"]
    assert result["notifications_created"] == 1
    assert "base_benefit_rate" in result["changed_fields"]
    assert "bonus_rules" in result["changed_fields"]

    notifications_resp = client.get("/api/v1/notifications", headers={"x-user-id": "1"})
    assert notifications_resp.status_code == 200

    notifications = notifications_resp.json()["notifications"]
    assert len(notifications) == 1
    notif = notifications[0]
    assert notif["card_id"] == 101
    assert notif["card_name"] == "DBS Test Rewards"
    assert notif["effective_date"] == "2026-04-01"
    assert "base_benefit_rate" in notif["changed_fields"]


def test_non_owner_does_not_get_notification(client: TestClient):
    response = client.put(
        "/api/v1/catalog/101/rewards",
        json={
            "reward_update": {
                "base_benefit_rate": 0.02,
                "effective_date": "2026-04-01",
                "bonus_rules": [
                    {
                        "bonus_category": "Food",
                        "bonus_benefit_rate": 0.05,
                        "bonus_cap_in_dollar": 120,
                        "bonus_minimum_spend_in_dollar": 600,
                    }
                ],
            }
        },
    )

    assert response.status_code == 200

    notifications_resp = client.get("/api/v1/notifications", headers={"x-user-id": "2"})
    assert notifications_resp.status_code == 200
    assert notifications_resp.json()["notifications"] == []


def test_no_delta_creates_no_notification(client: TestClient):
    response = client.put(
        "/api/v1/catalog/101/rewards",
        json={
            "reward_update": {
                "base_benefit_rate": 0.01,
                "effective_date": "2026-04-01",
                "bonus_rules": [
                    {
                        "bonus_category": "Food",
                        "bonus_benefit_rate": 0.03,
                        "bonus_cap_in_dollar": 80,
                        "bonus_minimum_spend_in_dollar": 500,
                    }
                ],
            }
        },
    )

    assert response.status_code == 200
    result = response.json()["update_result"]
    assert result["changed_fields"] == {}
    assert result["notifications_created"] == 0

    owner_notifications_resp = client.get("/api/v1/notifications", headers={"x-user-id": "1"})
    assert owner_notifications_resp.status_code == 200
    assert owner_notifications_resp.json()["notifications"] == []

    db = TestingSessionLocal()
    try:
        assert db.query(CardChangeNotification).count() == 0
    finally:
        db.close()
