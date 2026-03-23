from unittest.mock import Mock, patch

import pytest

from starlette.requests import Request

from app.services.security_log_service import (
    SecurityEventType,
    log_auth_event,
    log_genai_access_event,
    log_otp_event,
    log_security_event,
    mask_sensitive_fields,
)


def _make_request() -> Request:
    scope = {
        "type": "http",
        "headers": [
            (b"user-agent", b"pytest-agent"),
            (b"x-request-id", b"req-123"),
        ],
        "client": ("127.0.0.1", 5151),
        "method": "POST",
        "path": "/api/v1/user_profile/login",
    }
    return Request(scope)


@pytest.fixture
def mock_db() -> Mock:
    return Mock()


@pytest.fixture
def mock_request() -> Request:
    return _make_request()


def test_mask_sensitive_fields_masks_nested_values() -> None:
    payload = {
        "username": "alice",
        "password": "plain",
        "nested": {
            "otp": "123456",
            "token": "abc",
            "non_sensitive": "ok",
        },
        "items": [
            {"authorization": "Bearer xyz"},
            {"note": "hello"},
        ],
    }

    masked = mask_sensitive_fields(payload)

    assert masked["username"] == "alice"
    assert masked["password"] == "***"
    assert masked["nested"]["otp"] == "***"
    assert masked["nested"]["token"] == "***"
    assert masked["nested"]["non_sensitive"] == "ok"
    assert masked["items"][0]["authorization"] == "***"
    assert masked["items"][1]["note"] == "hello"


def test_mask_sensitive_fields_masks_case_insensitive_keys() -> None:
    payload = {
        "Password": "plain",
        "nested": {
            "Authorization": "Bearer xyz",
            "safe": "ok",
        },
    }

    masked = mask_sensitive_fields(payload)

    assert masked["Password"] == "***"
    assert masked["nested"]["Authorization"] == "***"
    assert masked["nested"]["safe"] == "ok"


def test_log_security_event_masks_details_and_request_context(
    mock_db: Mock, mock_request: Request
) -> None:
    record = log_security_event(
        mock_db,
        event_type=SecurityEventType.AUTH_LOGIN,
        source="user_profile.login",
        event_status="failed",
        user_id=2,
        request=mock_request,
        details={"password": "secret", "username": "alice"},
        error_message="Invalid password",
    )

    assert record.event_type == SecurityEventType.AUTH_LOGIN
    assert record.event_status == "failed"
    assert record.user_id == 2
    assert record.ip_address == "127.0.0.1"
    assert record.user_agent == "pytest-agent"
    assert record.request_id == "req-123"
    assert record.details["password"] == "***"
    assert record.details["username"] == "alice"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(record)


def test_log_security_event_without_request_sets_request_fields_to_none(
    mock_db: Mock,
) -> None:
    record = log_security_event(
        mock_db,
        event_type=SecurityEventType.AUTH_LOGIN,
        source="user_profile.login",
        details={"token": "abc"},
    )

    assert record.ip_address is None
    assert record.user_agent is None
    assert record.request_id is None
    assert record.details["token"] == "***"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(record)


def test_log_security_event_with_request_without_client_sets_ip_none(
    mock_db: Mock,
) -> None:
    scope = {
        "type": "http",
        "headers": [(b"user-agent", b"pytest-agent")],
        "client": None,
        "method": "POST",
        "path": "/api/v1/user_profile/login",
    }
    request = Request(scope)

    record = log_security_event(
        mock_db,
        event_type=SecurityEventType.AUTH_LOGIN,
        source="user_profile.login",
        request=request,
        details={"password": "secret"},
    )

    assert record.ip_address is None
    assert record.user_agent == "pytest-agent"
    assert record.request_id is None
    assert record.details["password"] == "***"


def test_log_auth_event_uses_event_type_and_source_convention(
    mock_db: Mock, mock_request: Request
) -> None:
    with patch("app.services.security_log_service.log_security_event") as mock_log:
        log_auth_event(
            mock_db,
            status="success",
            request=mock_request,
            user_id=7,
            username="alice",
            reason="authenticated",
            error_message="bad credentials",
        )

    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == SecurityEventType.AUTH_LOGIN
    assert kwargs["source"] == "user_profile.login"
    assert kwargs["event_status"] == "success"
    assert kwargs["user_id"] == 7
    assert kwargs["details"]["username"] == "alice"
    assert kwargs["details"]["outcome"] == "success"
    assert kwargs["error_message"] == "bad credentials"


def test_log_otp_event_uses_convention_and_masks_details(
    mock_db: Mock, mock_request: Request
) -> None:
    record = log_otp_event(
        mock_db,
        event_type=SecurityEventType.OTP_VERIFY,
        status="failed",
        request=mock_request,
        user_id=8,
        channel="sms",
        reason="otp_mismatch",
        details={"otp": "654321", "attempt": 2},
    )

    assert record.event_type == SecurityEventType.OTP_VERIFY
    assert record.source == "otp"
    assert record.event_status == "failed"
    assert record.user_id == 8
    assert record.details["channel"] == "sms"
    assert record.details["reason"] == "otp_mismatch"
    assert record.details["otp"] == "***"
    assert record.details["attempt"] == 2
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(record)


def test_log_genai_access_event_uses_convention_and_masks_details(
    mock_db: Mock, mock_request: Request
) -> None:
    record = log_genai_access_event(
        mock_db,
        status="success",
        source="recommendation.explain",
        request=mock_request,
        user_id=9,
        endpoint="/api/v1/recommendation/explain",
        details={"category": "Food", "token": "abc123"},
    )

    assert record.event_type == SecurityEventType.GENAI_ACCESS
    assert record.source == "recommendation.explain"
    assert record.event_status == "success"
    assert record.user_id == 9
    assert record.details["endpoint"] == "/api/v1/recommendation/explain"
    assert record.details["category"] == "Food"
    assert record.details["token"] == "***"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(record)


def test_log_security_event_commit_error_is_raised(mock_db: Mock) -> None:
    mock_db.commit.side_effect = RuntimeError("db commit failed")

    with pytest.raises(RuntimeError, match="db commit failed"):
        log_security_event(
            mock_db,
            event_type=SecurityEventType.AUTH_LOGIN,
            source="user_profile.login",
            details={"password": "secret"},
        )
