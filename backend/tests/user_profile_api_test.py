import pytest
from fastapi.testclient import TestClient
from app.routes.user_profile import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_get_user_profile_not_found():
    response = client.get("/api/v1/user_profile")
    assert response.status_code == 404
    assert "error" in response.json()["detail"]

def test_create_user_profile_conflict():
    payload = {
        "username": "existinguser",
        "password": "password",
        "name": "Test User",
        "email": "existing@example.com",
        "benefits_preference": None
    }
    # First creation should succeed (if not present)
    client.post("/api/v1/user_profile", json=payload)
    # Second creation should fail due to conflict
    response = client.post("/api/v1/user_profile", json=payload)
    assert response.status_code == 409
    assert "error" in response.json()["detail"]

def test_login_missing_fields():
    response = client.post("/api/v1/user_profile/login", json={})
    assert response.status_code == 400
    assert "error" in response.json()["detail"]

def test_login_rate_limit():
    payload = {"username": "testuser", "password": "testpass"}
    for _ in range(5):
        client.post("/api/v1/user_profile/login", json=payload)
    response = client.post("/api/v1/user_profile/login", json=payload)
    assert response.status_code == 429

def test_update_user_profile():
    # Create a user first
    payload = {
        "username": "updateuser",
        "password": "password",
        "name": "Original Name",
        "email": "update@example.com",
        "benefits_preference": None
    }
    create_resp = client.post("/api/v1/user_profile", json=payload)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Update the user's name
    update_payload = {
        "name": "Updated Name"
    }
    update_resp = client.patch(f"/api/v1/user_profile/{user_id}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Name"