from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.db import Base
from app.dependencies.db import get_db
from app.models.user_profile import BenefitsPreference, UserProfile
import app.services.user_profile as user_profile_service


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ROUTER_MODULE_PATH = BACKEND_DIR / "app" / "routes" / "user_profile.py"
router_spec = spec_from_file_location("user_profile_route_for_tests", ROUTER_MODULE_PATH)
router_module = module_from_spec(router_spec)
assert router_spec and router_spec.loader
router_spec.loader.exec_module(router_module)
user_profile_router = router_module.router

app = FastAPI()
app.include_router(user_profile_router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    original_session_local = user_profile_service.SessionLocal
    user_profile_service.SessionLocal = TestingSessionLocal
    yield
    app.dependency_overrides = {}
    user_profile_service.SessionLocal = original_session_local


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(
            UserProfile(
                id=1,
                username="alice",
                password_hash=user_profile_service.hash_password("alice-pass"),
                name="Alice",
                email="alice@example.com",
                benefits_preference=BenefitsPreference.no_preference,
            )
        )
        db.commit()

        yield
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_user_profile(client: TestClient):
    response = client.post(
        "/api/v1/user_profile",
        json={
            "username": "new_user",
            "password": "my-password",
            "name": "New User",
            "email": "new_user@example.com",
            "benefits_preference": "No preference",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 2
    assert data["username"] == "new_user"
    assert data["name"] == "New User"
    assert data["email"] == "new_user@example.com"


def test_create_user_profile_conflict_username(client: TestClient):
    response = client.post(
        "/api/v1/user_profile",
        json={
            "username": "alice",
            "password": "another-pass",
            "name": "Alice 2",
            "email": "alice2@example.com",
            "benefits_preference": "No preference",
        },
    )

    assert response.status_code == 409
    body = response.json()
    error = body.get("error") or body.get("detail", {}).get("error", {})
    assert error["code"] == "CONFLICT"


def test_get_user_profile_by_header_id(client: TestClient):
    response = client.get("/api/v1/user_profile", headers={"x-user-id": "1"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["username"] == "alice"


def test_get_user_profile_requires_user_context(client: TestClient):
    response = client.get("/api/v1/user_profile")

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body.get("detail", {}).get("error", {})
    assert error["code"] == "UNAUTHORIZED"


def test_update_user_profile(client: TestClient):
    response = client.patch(
        "/api/v1/user_profile/1",
        json={
            "username": "alice",
            "password": "updated-pass",
            "name": "Alice Updated",
            "email": "alice.updated@example.com",
            "benefits_preference": "Cashback",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice Updated"
    assert data["email"] == "alice.updated@example.com"
    assert data["benefits_preference"] == "Cashback"


def test_login_success(client: TestClient):
    response = client.post(
        "/api/v1/user_profile/login",
        json={"username": "alice", "password": "alice-pass"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["username"] == "alice"


def test_login_invalid_password(client: TestClient):
    response = client.post(
        "/api/v1/user_profile/login",
        json={"username": "alice", "password": "wrong-pass"},
    )

    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body.get("detail", {}).get("error", {})
    assert error["code"] == "UNAUTHORIZED"