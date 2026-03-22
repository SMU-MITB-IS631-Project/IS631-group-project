import sys
import types
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


try:
    import jose  # noqa: F401
except ModuleNotFoundError:
    class _JWTError(Exception):
        pass

    class _ExpiredSignatureError(_JWTError):
        pass

    class _JWTNamespace:
        JWTError = _JWTError
        ExpiredSignatureError = _ExpiredSignatureError

        @staticmethod
        def get_unverified_header(token):
            return {}

        @staticmethod
        def decode(*args, **kwargs):
            return {}

    jose_stub = types.ModuleType("jose")
    jose_stub.jwt = _JWTNamespace
    sys.modules["jose"] = jose_stub


from app.db.db import Base
from app.dependencies.db import get_db
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.models.user_owned_cards import UserOwnedCardStatus
from app.models.user_profile import BenefitsPreference, UserProfile
from app.routes.user_card_management import router as wallet_router


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()
app.include_router(wallet_router)

AUTH_HEADERS = {"Authorization": "Bearer fake-token"}
COGNITO_SUB = "cognito-sub-1"


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
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(
            UserProfile(
                id=1,
                username="alice",
                email="alice@example.com",
                cognito_sub=COGNITO_SUB,
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


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def valid_token():
    with patch("app.dependencies.user_context.CognitoService.validate_token", return_value={"sub": COGNITO_SUB}):
        yield


def test_get_user_cards_requires_authorization(client: TestClient):
    response = client.get("/user/cards/")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthenticated. Missing Authorization header."}


def test_get_user_cards_returns_empty_list(client: TestClient, valid_token):
    response = client.get("/user/cards/", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json() == []


def test_add_user_card_success(client: TestClient, valid_token):
    response = client.post(
        "/user/cards",
        headers=AUTH_HEADERS,
        json={
            "card_id": 101,
            "billing_cycle_refresh_day_of_month": 15,
            "billing_cycle_refresh_date": "2026-04-30",
            "card_expiry_date": "2028-12-31",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["card_id"] == 101
    assert body["billing_cycle_refresh_day_of_month"] == 15
    assert body["billing_cycle_refresh_date"] == "2026-04-30"
    assert body["card_expiry_date"] == "2028-12-31"


def test_add_user_card_duplicate_returns_internal_server_error(client: TestClient, valid_token):
    payload = {
        "card_id": 101,
        "billing_cycle_refresh_day_of_month": 15,
        "billing_cycle_refresh_date": "2026-04-30",
        "card_expiry_date": "2028-12-31",
    }

    first = client.post("/user/cards", headers=AUTH_HEADERS, json=payload)
    second = client.post("/user/cards", headers=AUTH_HEADERS, json=payload)

    assert first.status_code == 201
    assert second.status_code == 400


def test_update_user_card_success(client: TestClient, valid_token):
    create = client.post(
        "/user/cards",
        headers=AUTH_HEADERS,
        json={
            "card_id": 101,
            "billing_cycle_refresh_day_of_month": 1,
            "billing_cycle_refresh_date": "2026-03-31",
            "card_expiry_date": "2027-03-31",
        },
    )
    assert create.status_code == 201

    update = client.put(
        "/user/cards/101",
        headers=AUTH_HEADERS,
        json={
            "billing_cycle_refresh_date": "2026-05-31",
            "card_expiry_date": "2029-01-31",
            "status": "Suspended",
        },
    )

    assert update.status_code == 200
    body = update.json()
    assert body["card_id"] == 101
    assert body["billing_cycle_refresh_date"] == "2026-05-31"
    assert body["card_expiry_date"] == "2029-01-31"
    assert body["status"] == UserOwnedCardStatus.Inactive.value


def test_remove_user_card_success(client: TestClient, valid_token):
    create = client.post(
        "/user/cards",
        headers=AUTH_HEADERS,
        json={
            "card_id": 101,
            "billing_cycle_refresh_day_of_month": 10,
            "billing_cycle_refresh_date": str(date(2026, 3, 31)),
            "card_expiry_date": str(date(2028, 3, 31)),
        },
    )
    assert create.status_code == 201

    delete_response = client.delete("/user/cards/101", headers=AUTH_HEADERS)
    assert delete_response.status_code == 204

    list_response = client.get("/user/cards/", headers=AUTH_HEADERS)
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_get_user_cards_invalid_token_payload(client: TestClient):
    with patch("app.dependencies.user_context.CognitoService.validate_token", return_value={}):
        response = client.get("/user/cards/", headers=AUTH_HEADERS)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token payload."}
