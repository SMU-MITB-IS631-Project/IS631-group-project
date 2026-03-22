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
TEST_DB_PATH = BACKEND_DIR / "test_user_profile_api.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ROUTER_MODULE_PATH = BACKEND_DIR / "app" / "routes" / "user_profile.py"
router_spec = spec_from_file_location("user_profile_route_for_api_tests", ROUTER_MODULE_PATH)
router_module = module_from_spec(router_spec)
assert router_spec and router_spec.loader
router_spec.loader.exec_module(router_module)
router = router_module.router

app = FastAPI()
app.include_router(router)

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
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def override_cognito_validate_token(monkeypatch: pytest.MonkeyPatch):
    def _fake_validate_token(_auth):
        return {"sub": "sub-alice"}

    monkeypatch.setattr(router_module.cognito_service, "validate_token", _fake_validate_token)
    yield


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
                benefits_preference=BenefitsPreference.no_preference,
                cognito_sub="sub-alice",
            )
        )
        db.commit()
        yield
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_my_profile_requires_auth(client: TestClient):
    response = client.get("/user_profile/me")
    assert response.status_code == 401


def test_get_my_profile_success(client: TestClient):
    response = client.get("/user_profile/me", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice"
    assert data["benefits_preference"] == "No preference"


def test_update_my_profile_success(client: TestClient):
    response = client.put(
        "/user_profile/me",
        json={"name": "Alice Updated", "benefits_preference": "Cashback"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice Updated"
    assert data["benefits_preference"] == "Cashback"


def test_get_user_profiles_success(client: TestClient):
    response = client.get("/user_profile/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 1
