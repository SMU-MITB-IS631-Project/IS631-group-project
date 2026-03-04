from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.db import get_db
from app.models.card_catalogue import BankEnum, BenefitTypeEnum, CardCatalogue, StatusEnum
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import BenefitsPreference, UserProfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ROUTER_MODULE_PATH = BACKEND_DIR / "app" / "routes" / "transactions.py"
router_spec = spec_from_file_location("transactions_route_for_tests", ROUTER_MODULE_PATH)
router_module = module_from_spec(router_spec)
assert router_spec and router_spec.loader
router_spec.loader.exec_module(router_module)
transactions_router = router_module.router

app = FastAPI()
app.include_router(transactions_router)

USER_HEADERS = {"x-user-id": "1"}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _transaction_payload(
    *,
    card_id: int = 101,
    amount_sgd: float = 12.5,
    item: str = "GrabFood",
    channel: str = "online",
    category: str = "food",
    is_overseas: bool = False,
    date: str = "2026-02-18",
) -> dict:
    return {
        "transaction": {
            "card_id": card_id,
            "amount_sgd": amount_sgd,
            "item": item,
            "channel": channel,
            "category": category,
            "is_overseas": is_overseas,
            "date": date,
        }
    }


def _create_transaction(client: TestClient, payload: dict | None = None) -> dict:
    response = client.post(
        "/api/v1/transactions",
        json=payload or _transaction_payload(),
        headers=USER_HEADERS,
    )
    assert response.status_code == 201
    return response.json()["transaction"]


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


def test_create_transaction(client: TestClient):
    response = client.post(
        "/api/v1/transactions",
        json=_transaction_payload(),
        headers=USER_HEADERS,
    )

    assert response.status_code == 201
    data = response.json()["transaction"]
    assert data["item"] == "GrabFood"
    assert data["amount_sgd"] == 12.5
    assert data["card_id"] == "101"
    assert data["status"] == "active"


def test_list_transactions(client: TestClient):
    _create_transaction(
        client,
        _transaction_payload(item="Old txn", amount_sgd=10.0, date="2026-02-10"),
    )
    _create_transaction(
        client,
        _transaction_payload(item="New txn", amount_sgd=20.0, date="2026-02-20"),
    )

    response = client.get("/api/v1/transactions", headers=USER_HEADERS)

    assert response.status_code == 200
    transactions = response.json()["transactions"]
    assert len(transactions) == 2
    assert transactions[0]["item"] == "New txn"
    assert transactions[1]["item"] == "Old txn"


def test_get_transactions_for_specific_user(client: TestClient):
    created = _create_transaction(client)

    response = client.get("/api/v1/transactions/1", headers=USER_HEADERS)

    assert response.status_code == 200
    transactions = response.json()["transactions"]
    assert len(transactions) == 1
    assert transactions[0]["id"] == created["id"]


def test_update_transaction_status(client: TestClient):
    created = _create_transaction(client)

    response = client.put(
        f"/api/v1/transactions/{created['id']}",
        json={"status": "deleted_with_card"},
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    updated = response.json()["transaction"]
    assert updated["id"] == created["id"]
    assert updated["status"] == "deleted_with_card"


def test_bulk_update_transaction_status(client: TestClient):
    first = _create_transaction(client, _transaction_payload(item="First txn", date="2026-02-15"))
    second = _create_transaction(client, _transaction_payload(item="Second txn", date="2026-02-16"))

    response = client.put(
        "/api/v1/transactions/bulk/status",
        json={
            "transaction_ids": [int(first["id"]), int(second["id"])],
            "status": "deleted_with_card",
        },
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["status"] == "deleted_with_card"


def test_transactions_requires_user_context(client: TestClient):
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"