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

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


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

    original_validate_token = router_module.cognito_service.validate_token
    router_module.cognito_service.validate_token = lambda auth: {"sub": "test-cognito-sub-1"}

    yield

    app.dependency_overrides = {}
    router_module.cognito_service.validate_token = original_validate_token


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(
            UserProfile(
                id=1,
                username="alice",
                name="Alice",
                email="alice@example.com",
                cognito_sub="test-cognito-sub-1",
                benefits_preference=BenefitsPreference.no_preference,
            )
        )
        db.add(
            UserProfile(
                id=2,
                username="bob",
                name="Bob",
                email="bob@example.com",
                cognito_sub="test-cognito-sub-2",
                benefits_preference=BenefitsPreference.cashback,
            )
        )
        db.commit()

        yield
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_user_profiles(client: TestClient):
    response = client.get("/user_profile/", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {item["id"] for item in data} == {1, 2}


def test_get_my_profile(client: TestClient):
    response = client.get("/user_profile/me", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice"
    assert data["benefits_preference"] == "No preference"


def test_get_user_profile_requires_auth(client: TestClient):
    response = client.get("/user_profile/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization header."


def test_update_my_profile(client: TestClient):
    response = client.put(
        "/user_profile/me",
        json={
            "name": "Alice Updated",
            "benefits_preference": "Cashback",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice Updated"
    assert data["benefits_preference"] == "Cashback"


def test_get_my_profile_not_found_for_unknown_cognito_sub(client: TestClient):
    router_module.cognito_service.validate_token = lambda auth: {"sub": "unknown-sub"}

    response = client.get("/user_profile/me", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "User profile not found."
