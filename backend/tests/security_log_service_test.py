from unittest.mock import MagicMock, patch

from starlette.requests import Request

from app.services.security_log_service import (
    SecurityEventType,
    log_auth_event,
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


def test_log_security_event_masks_details_and_request_context() -> None:
    db = MagicMock()
    request = _make_request()

    record = log_security_event(
        db,
        event_type=SecurityEventType.AUTH_LOGIN,
        source="user_profile.login",
        event_status="failed",
        user_id=2,
        request=request,
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

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(record)


def test_log_auth_event_uses_event_type_and_source_convention() -> None:
    db = MagicMock()
    request = _make_request()

    with patch("app.services.security_log_service.log_security_event") as mock_log:
        log_auth_event(
            db,
            status="success",
            request=request,
            user_id=7,
            username="alice",
            reason="authenticated",
        )

    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == SecurityEventType.AUTH_LOGIN
    assert kwargs["source"] == "user_profile.login"
    assert kwargs["event_status"] == "success"
    assert kwargs["user_id"] == 7
    assert kwargs["details"]["username"] == "alice"
    assert kwargs["details"]["outcome"] == "success"


def test_log_otp_event_uses_convention_and_masks_details() -> None:
    db = MagicMock()
    request = _make_request()

    record = log_otp_event(
        db,
        event_type=SecurityEventType.OTP_VERIFY,
        status="failed",
        request=request,
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
