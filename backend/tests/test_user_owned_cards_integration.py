from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.db import get_db
from app.dependencies.user_context import get_cognito_sub
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.models.user_profile import BenefitsPreference, UserProfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    card_id: int = 101,
    card_expiry_date: str = "2027-01-01",
    billing_cycle_refresh_day_of_month: int = 10,
) -> dict:
    return {
        "card_id": card_id,
        "card_expiry_date": card_expiry_date,
        "billing_cycle_refresh_day_of_month": billing_cycle_refresh_day_of_month,
    }


def _create_card_and_get_user_card_id(client: TestClient) -> str:
    create_response = client.post(
        "/user/cards",
        json=_wallet_card_payload(),
    )
    assert create_response.status_code == 201

    list_response = client.get("/user/cards/")
    assert list_response.status_code == 200

    user_cards = list_response.json()
    assert len(user_cards) == 1
    return str(user_cards[0]["id"])


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_sub] = lambda: "test-cognito-sub-1"
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
                cognito_sub="test-cognito-sub-1",
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
        "/user/cards",
        json=_wallet_card_payload(),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["card_id"] == 101
    assert data["billing_cycle_refresh_day_of_month"] == 10
    assert data["card_expiry_date"] == "2027-01-01"


def test_get_user_cards(client: TestClient):
    client.post(
        "/user/cards",
        json=_wallet_card_payload(),
    )

    response = client.get("/user/cards/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["card_id"] == 101


def test_update_user_card(client: TestClient):
    _create_card_and_get_user_card_id(client)

    response = client.put(
        "/user/cards/101",
        json={
            "billing_cycle_day_of_month": 20,
            "card_expiry_date": "2028-02-02",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["card_id"] == 101
    assert updated["billing_cycle_refresh_day_of_month"] == 20
    assert updated["card_expiry_date"] == "2028-02-02"


def test_delete_user_card(client: TestClient):
    _create_card_and_get_user_card_id(client)

    response = client.delete("/user/cards/101")
    assert response.status_code == 204

    after_delete = client.get("/user/cards/")
    assert after_delete.status_code == 200
    assert after_delete.json() == []


def test_get_user_cards_requires_user_context(client: TestClient):
    app.dependency_overrides.pop(get_cognito_sub, None)
    response = client.get("/user/cards/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthenticated. Missing Authorization header."