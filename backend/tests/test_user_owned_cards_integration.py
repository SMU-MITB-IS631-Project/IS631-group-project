from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.db import get_db
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.models.user_profile import BenefitsPreference, UserProfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

USER_HEADERS = {"x-user-id": "1"}

ROUTER_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "routes" / "user_card_management.py"
router_spec = spec_from_file_location("user_card_management_route_for_tests", ROUTER_MODULE_PATH)
router_module = module_from_spec(router_spec)
assert router_spec and router_spec.loader
router_spec.loader.exec_module(router_module)
user_cards_router = router_module.router

app = FastAPI()
app.include_router(user_cards_router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _wallet_card_payload(
    card_id: str = "101",
    refresh_day_of_month: int = 10,
    annual_fee_billing_date: str = "2027-01-01",
    cycle_spend_sgd: float = 150.0,
) -> dict:
    return {
        "wallet_card": {
            "card_id": card_id,
            "refresh_day_of_month": refresh_day_of_month,
            "annual_fee_billing_date": annual_fee_billing_date,
            "cycle_spend_sgd": cycle_spend_sgd,
        }
    }


def _create_card_and_get_user_card_id(client: TestClient) -> str:
    create_response = client.post(
        "/api/v1/user_cards",
        json=_wallet_card_payload(),
        headers=USER_HEADERS,
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/user_cards", headers=USER_HEADERS)
    assert list_response.status_code == 200

    user_cards = list_response.json()["user_cards"]
    assert len(user_cards) == 1
    return user_cards[0]["id"]


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


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
        db.add(
            UserProfile(
                id=1,
                username="alice",
                password_hash="test-hash",
                benefits_preference=BenefitsPreference.no_preference,
            )
        )
        db.add(
            CardCatalogue(
                card_id=101,
                bank=BankEnum.DBS,
                card_name="Integration Test Card",
                benefit_type=BenefitTypeEnum.cashback,
                base_benefit_rate=1.5,
                status=StatusEnum.valid,
            )
        )
        db.commit()

        yield
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_add_user_card(client: TestClient):
    response = client.post(
        "/api/v1/user_cards",
        json=_wallet_card_payload(),
        headers=USER_HEADERS,
    )

    assert response.status_code == 201
    data = response.json()["wallet_card"]
    assert data["card_id"] == "101"
    assert data["refresh_day_of_month"] == 10
    assert data["annual_fee_billing_date"] == "2027-01-01"


def test_get_user_cards(client: TestClient):
    client.post(
        "/api/v1/user_cards",
        json=_wallet_card_payload(),
        headers=USER_HEADERS,
    )

    response = client.get("/api/v1/user_cards", headers=USER_HEADERS)
    assert response.status_code == 200

    data = response.json()
    assert "user_cards" in data
    assert isinstance(data["user_cards"], list)
    assert len(data["user_cards"]) == 1
    assert data["user_cards"][0]["card_id"] == "101"


def test_update_user_card(client: TestClient):
    user_card_id = _create_card_and_get_user_card_id(client)

    response = client.put(
        f"/api/v1/user_cards/{user_card_id}",
        json={
            "user_card": {
                "card_id": "101",
                "refresh_day_of_month": 20,
                "annual_fee_billing_date": "2028-02-02",
                "cycle_spend_sgd": 300.0,
            }
        },
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    updated = response.json()["wallet_card"]
    assert updated["card_id"] == "101"
    assert updated["refresh_day_of_month"] == 20
    assert updated["annual_fee_billing_date"] == "2028-02-02"


def test_delete_user_card(client: TestClient):
    user_card_id = _create_card_and_get_user_card_id(client)

    response = client.delete(f"/api/v1/user_cards/{user_card_id}", headers=USER_HEADERS)
    assert response.status_code == 204

    after_delete = client.get("/api/v1/user_cards", headers=USER_HEADERS)
    assert after_delete.status_code == 200
    assert after_delete.json()["user_cards"] == []


def test_get_user_cards_requires_user_context(client: TestClient):
    response = client.get("/api/v1/user_cards")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"