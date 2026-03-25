import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.dependencies.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user_profile import BenefitsPreference, UserProfile  # noqa: E402


class AuthSecurityLoggingTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        with self.Session() as db:
            db.add(
                UserProfile(
                    id=1,
                    username="alice",
                    password_hash="x",
                    benefits_preference=BenefitsPreference.no_preference,
                    cognito_sub="sub-123",
                    email="alice@example.com",
                )
            )
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_login_success_logs_auth_login_success(self):
        with patch("app.routes.auth.cognito_service.authenticate_user", return_value={"id_token": "fake", "access_token": "a", "refresh_token": "r"}), patch(
            "app.routes.auth.jwt.get_unverified_claims",
            return_value={"sub": "sub-123", "cognito:username": "alice"},
        ), patch("app.routes.auth.log_auth_event") as mock_log_auth:
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "secret"}
            )

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(mock_log_auth.call_count, 1)
        kwargs = mock_log_auth.call_args.kwargs
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(kwargs["source"], "auth.login")

    def test_login_failure_logs_auth_login_failed(self):
        with patch(
            "app.routes.auth.cognito_service.authenticate_user",
            side_effect=Exception("boom"),
        ), patch("app.routes.auth.log_auth_event") as mock_log_auth:
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "wrong"}
            )

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(mock_log_auth.call_count, 1)
        kwargs = mock_log_auth.call_args.kwargs
        self.assertEqual(kwargs["status"], "failed")
        self.assertEqual(kwargs["source"], "auth.login")

    def test_login_service_exception_logs_auth_login_failed(self):
        from app.exceptions import ServiceException

        with patch(
            "app.routes.auth.cognito_service.authenticate_user",
            side_effect=ServiceException(status_code=401, detail="Invalid username or password."),
        ), patch("app.routes.auth.log_auth_event") as mock_log_auth:
            resp = self.client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "wrong"}
            )

        self.assertEqual(resp.status_code, 401, msg=resp.text)
        self.assertEqual(mock_log_auth.call_count, 1)
        kwargs = mock_log_auth.call_args.kwargs
        self.assertEqual(kwargs["status"], "failed")
        self.assertEqual(kwargs["source"], "auth.login")

    def test_registration_logs_otp_request_success(self):
        fake_cognito_resp = {"UserSub": "sub-new", "UserConfirmed": False}
        fake_user = SimpleNamespace(
            id=22,
            username="newuser",
            name="New User",
            email="newuser@example.com",
            benefits_preference=BenefitsPreference.no_preference,
            created_date="2026-03-23",
        )

        with patch("app.routes.auth.cognito_service.register_user", return_value=fake_cognito_resp), patch(
            "app.routes.auth.UserProfileService.create_user_profile",
            return_value=fake_user,
        ), patch("app.routes.auth.log_otp_event") as mock_log_otp:
            resp = self.client.post(
                "/api/v1/auth/registration",
                json={
                    "username": "newuser",
                    "email": "newuser@example.com",
                    "password": "Secret123!",
                    "name": "New User",
                    "benefits_preference": "No preference",
                },
            )

        self.assertEqual(resp.status_code, 201, msg=resp.text)
        self.assertEqual(mock_log_otp.call_count, 1)
        kwargs = mock_log_otp.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "otp.request")
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(kwargs["source"], "auth.registration")

    def test_confirmation_logs_otp_verify_success(self):
        with patch("app.routes.auth.cognito_service.confirm_user", return_value=None), patch(
            "app.routes.auth.log_otp_event"
        ) as mock_log_otp:
            resp = self.client.post(
                "/api/v1/auth/confirmation",
                json={"username": "alice", "confirmation_code": "123456"},
            )

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(mock_log_otp.call_count, 1)
        kwargs = mock_log_otp.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "otp.verify")
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(kwargs["source"], "auth.confirmation")


if __name__ == "__main__":
    unittest.main()
