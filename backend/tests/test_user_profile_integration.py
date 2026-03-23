from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies.auth import required_authenticated
from app.dependencies.services import get_user_profile_service
from app.exceptions import ServiceException
from app.models.user_profile import BenefitsPreference
from app.routes.user_profile import router


@pytest.fixture()
def app_and_service_mock():
    app = FastAPI()
    app.include_router(router)

    service_mock = Mock()
    app.dependency_overrides[get_user_profile_service] = lambda: service_mock
    try:
        yield app, service_mock
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client(app_and_service_mock):
    app, _ = app_and_service_mock
    with TestClient(app) as test_client:
        yield test_client


def _profile_payload(**overrides):
    payload = {
        "id": 1,
        "name": "Test User",
        "benefits_preference": "No preference",
        "created_date": datetime(2026, 3, 22, tzinfo=timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_get_my_profile_requires_authorization(client: TestClient):
    response = client.get("/user_profile/user")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_my_profile_not_found(client: TestClient, app_and_service_mock):
    app, service_mock = app_and_service_mock
    service_mock.get_user_profile.return_value = None
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "missing-user-sub"}

    response = client.get("/user_profile/user")

    assert response.status_code == 404
    assert response.json() == {"detail": "User profile not found."}
    service_mock.get_user_profile.assert_called_once_with("missing-user-sub")


def test_get_my_profile_success(client: TestClient, app_and_service_mock):
    app, service_mock = app_and_service_mock
    service_mock.get_user_profile.return_value = _profile_payload(id=10, name="Alice")
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "alice-sub"}

    response = client.get("/user_profile/user")

    assert response.status_code == 200
    assert response.json()["id"] == 10
    assert response.json()["name"] == "Alice"
    service_mock.get_user_profile.assert_called_once_with("alice-sub")


def test_update_my_profile_success(client: TestClient, app_and_service_mock):
    app, service_mock = app_and_service_mock
    service_mock.update_user_profile.return_value = _profile_payload(
        id=7,
        name="Updated User",
        benefits_preference="Cashback",
    )
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "update-sub"}

    response = client.put(
        "/user_profile/user",
        json={"name": "Updated User", "benefits_preference": "Cashback"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated User"
    assert response.json()["benefits_preference"] == "Cashback"
    service_mock.update_user_profile.assert_called_once_with(
        cognitosub="update-sub",
        name="Updated User",
        benefits_preference=BenefitsPreference.cashback,
    )


def test_update_my_profile_maps_service_exception(client: TestClient, app_and_service_mock):
    app, service_mock = app_and_service_mock
    service_mock.update_user_profile.side_effect = ServiceException(status_code=404, detail="User not found.")
    app.dependency_overrides[required_authenticated] = lambda: {"sub": "missing-sub"}

    response = client.put(
        "/user_profile/user",
        json={"name": "New Name", "benefits_preference": "No preference"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found."}


def test_get_my_profile_rejects_invalid_token_payload(client: TestClient, app_and_service_mock):
    app, _ = app_and_service_mock
    app.dependency_overrides[required_authenticated] = lambda: {}

    response = client.get("/user_profile/user")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token payload."}
