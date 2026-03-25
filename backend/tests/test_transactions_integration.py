from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.auth import required_authenticated
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


# ============================================================================
# FIXTURES & SETUP
# ============================================================================


def override_get_db():
    # Provide an isolated DB session for each request handled by the TestClient.
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
    # Helper to keep tests focused on assertions instead of request boilerplate.
    response = client.post(
        "/api/v1/transactions",
        json=payload or _transaction_payload(),
        headers=USER_HEADERS,
    )
    assert response.status_code == 201
    return response.json()["transaction"]


@pytest.fixture()
def client():
    """Provide a TestClient for isolated request handling."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def dependency_overrides():
    """Inject test database into app dependency resolver for all tests."""
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "test-cognito-sub-1"}
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create fresh database schema per test with seeded user, card, and ownership records.
    
    Seeds:
      - UserProfile(id=1): Test user matching x-user-id header
      - CardCatalogue(card_id=101): Valid card for transaction references
      - UserOwnedCard: Authorization link between user 1 and card 101
    """
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


# ============================================================================
# CREATE TRANSACTION TESTS
# ============================================================================
# Verify POST /api/v1/transactions endpoint validates card ownership, required
# fields, and user authentication. Tests both happy path and error scenarios.


def test_create_transaction(client: TestClient):
    """Happy path: create transaction with valid card and all required fields."""
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


def test_create_transaction_invalid_card(client: TestClient):
    """Error: reject transactions with card_id not owned by user."""
    response = client.post(
        "/api/v1/transactions",
        json=_transaction_payload(card_id=999),
        headers=USER_HEADERS,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "VALIDATION_ERROR"


def test_create_transaction_no_user_header(client: TestClient):
    """Error: reject requests when auth dependency returns empty claims."""
    app.dependency_overrides[required_authenticated] = lambda: {}
    response = client.post(
        "/api/v1/transactions",
        json=_transaction_payload(),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_transaction_null_required_field(client: TestClient):
    """Error: reject null values for required fields (e.g., item)."""
    response = client.post(
        "/api/v1/transactions",
        json={
            "transaction": {
                "card_id": 101,
                "amount_sgd": 50.0,
                "item": None,
                "channel": "online",
                "is_overseas": False,
                "date": "2026-02-18",
            }
        },
        headers=USER_HEADERS,
    )

    # Route-level harness returns FastAPI's default 422.
    # Full app harness may normalize this to 400 via global exception handler.
    assert response.status_code in (400, 422)


# ============================================================================
# READ/LIST TRANSACTION TESTS
# ============================================================================
# Verify GET endpoints return correct transaction lists, sorted correctly,
# and enforce user-scoped access controls.


def test_list_transactions(client: TestClient):
    """Happy path: list returns all transactions for user, newest first."""
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


# ============================================================================
# UPDATE TRANSACTION TESTS
# ============================================================================
# Verify PUT endpoints accept field updates, validate inputs, and enforce
# authorization. Tests status updates, field edits, nullable fields, and errors.


def test_update_transaction_success(client: TestClient):
    """Happy path: update item, amount, and category fields."""
    created = _create_transaction(client)

    response = client.put(
        f"/api/v1/transactions/{created['id']}",
        json={
            "transaction": {
                "item": "Updated Item",
                "amount_sgd": 75.00,
                "category": "fashion",
            }
        },
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    txn = response.json()["transaction"]
    assert txn["item"] == "Updated Item"
    assert txn["amount_sgd"] == 75.0
    assert txn["category"] == "fashion"


def test_update_transaction_accepts_lowercase_category(client: TestClient):
    """Category field accepts lowercase strings (case-normalization handled)."""
    created = _create_transaction(client)

    response = client.put(
        f"/api/v1/transactions/{created['id']}",
        json={
            "transaction": {
                "item": "Updated Item Lowercase Category",
                "category": "food",
            }
        },
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    txn = response.json()["transaction"]
    assert txn["item"] == "Updated Item Lowercase Category"
    assert txn["category"] == "food"


def test_update_transaction_not_found(client: TestClient):
    """Error: PUT non-existent transaction ID returns 404."""
    response = client.put(
        "/api/v1/transactions/999",
        json={"transaction": {"item": "Updated"}},
        headers=USER_HEADERS,
    )

    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"]["code"] == "NOT_FOUND"


def test_update_transaction_invalid_card(client: TestClient):
    """Error: reject card_id updates to cards not owned by user."""
    created = _create_transaction(client)

    response = client.put(
        f"/api/v1/transactions/{created['id']}",
        json={"transaction": {"card_id": 999}},
        headers=USER_HEADERS,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "VALIDATION_ERROR"


def test_update_transaction_clear_nullable_category(client: TestClient):
    """Nullable fields: set category to None to clear optional data."""
    created = _create_transaction(client, _transaction_payload(category="food"))

    response = client.put(
        f"/api/v1/transactions/{created['id']}",
        json={"transaction": {"category": None}},
        headers=USER_HEADERS,
    )

    assert response.status_code == 200
    txn = response.json()["transaction"]
    assert txn["category"] is None


# ============================================================================
# AUTHENTICATION & AUTHORIZATION TESTS
# ============================================================================
# Verify all endpoints require x-user-id header and enforce access controls.


def test_transactions_requires_user_context(client: TestClient):
    """Authorization: enforce auth claims on transaction endpoints."""
    app.dependency_overrides[required_authenticated] = lambda: {}
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# DELETE TRANSACTION TESTS
# ============================================================================
# Verify DELETE endpoint removes transactions and enforces authorization.


def test_delete_transaction_success(client: TestClient):
    """Happy path: delete transaction by ID and verify it no longer appears in list."""
    created = _create_transaction(client)

    response = client.delete(f"/api/v1/transactions/{created['id']}", headers=USER_HEADERS)

    assert response.status_code == 200
    deleted = response.json()["transaction"]
    assert deleted["id"] == created["id"]

    list_response = client.get("/api/v1/transactions", headers=USER_HEADERS)
    assert list_response.status_code == 200
    assert list_response.json()["transactions"] == []


def test_delete_transaction_not_found(client: TestClient):
    """Error: DELETE non-existent transaction ID returns 404."""
    response = client.delete("/api/v1/transactions/999", headers=USER_HEADERS)
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"]["code"] == "NOT_FOUND"


def test_delete_transaction_requires_user_context(client: TestClient):
    """Authorization: enforce auth claims on DELETE operations."""
    created = _create_transaction(client)
    app.dependency_overrides[required_authenticated] = lambda: {}

    response = client.delete(f"/api/v1/transactions/{created['id']}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# END-TO-END LIFECYCLE TEST
# ============================================================================
# Verify complete transaction lifecycle: create, read, update, and delete
# in a single test flow.


def test_full_crud_flow(client: TestClient):
    """Lifecycle test: POST → GET → PUT → DELETE transaction through all states."""
    create_response = client.post(
        "/api/v1/transactions",
        headers=USER_HEADERS,
        json={
            "transaction": {
                "card_id": 101,
                "amount_sgd": 200.00,
                "item": "CRUD Test",
                "channel": "offline",
                "category": "Entertainment",
                "is_overseas": False,
                "date": "2026-02-18",
            }
        },
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["transaction"]["id"]

    list_response = client.get("/api/v1/transactions", headers=USER_HEADERS)
    assert list_response.status_code == 200
    found = [t for t in list_response.json()["transactions"] if t["id"] == created_id]
    assert len(found) == 1
    assert found[0]["item"] == "CRUD Test"

    update_response = client.put(
        f"/api/v1/transactions/{created_id}",
        headers=USER_HEADERS,
        json={"transaction": {"item": "CRUD Test Updated", "amount_sgd": 250.00}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["transaction"]["item"] == "CRUD Test Updated"

    delete_response = client.delete(f"/api/v1/transactions/{created_id}", headers=USER_HEADERS)
    assert delete_response.status_code == 200

    verify_response = client.get("/api/v1/transactions", headers=USER_HEADERS)
    assert verify_response.status_code == 200
    still_exists = [t for t in verify_response.json()["transactions"] if t["id"] == created_id]
    assert len(still_exists) == 0