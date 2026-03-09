from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.security_log import SecurityLog

MASK = "***"


class SecurityEventType:
    """Event type naming conventions for security logs."""

    AUTH_LOGIN = "auth.login"
    OTP_REQUEST = "otp.request"
    OTP_VERIFY = "otp.verify"
    GENAI_ACCESS = "genai.access"


SENSITIVE_KEYS = {
    "password",
    "passcode",
    "otp",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "secret",
}


def mask_sensitive_fields(value: Any, parent_key: Optional[str] = None) -> Any:
    """Recursively mask sensitive values in dictionaries/lists before persistence."""
    if parent_key and parent_key.lower() in SENSITIVE_KEYS:
        return MASK

    if isinstance(value, dict):
        return {k: mask_sensitive_fields(v, k) for k, v in value.items()}

    if isinstance(value, list):
        return [mask_sensitive_fields(item, parent_key) for item in value]

    return value


def log_security_event(
    db: Session,
    *,
    event_type: str,
    source: str,
    event_status: str = "success",
    user_id: Optional[int] = None,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> SecurityLog:
    """Persist one security/audit event with masked details."""
    masked_details = mask_sensitive_fields(details or {})

    ip_address = None
    user_agent = None
    request_id = None

    if request is not None:
        if request.client is not None:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")
        request_id = request.headers.get("x-request-id")

    record = SecurityLog(
        event_type=event_type,
        event_status=event_status,
        source=source,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        details=masked_details,
        error_message=error_message,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def log_auth_event(
    db: Session,
    *,
    status: str,
    request: Optional[Request],
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    reason: Optional[str] = None,
    error_message: Optional[str] = None,
) -> SecurityLog:
    """Convenience logger for authentication events."""
    details: Dict[str, Any] = {
        "username": username,
        "reason": reason,
        "outcome": status,
    }
    return log_security_event(
        db,
        event_type=SecurityEventType.AUTH_LOGIN,
        source="user_profile.login",
        event_status=status,
        user_id=user_id,
        request=request,
        details=details,
        error_message=error_message,
    )


def log_otp_event(
    db: Session,
    *,
    event_type: str,
    status: str,
    request: Optional[Request],
    user_id: Optional[int] = None,
    channel: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> SecurityLog:
    """Convenience logger for OTP request/verify events."""
    merged_details = {
        "channel": channel,
        "reason": reason,
        "outcome": status,
    }
    if details:
        merged_details.update(details)

    return log_security_event(
        db,
        event_type=event_type,
        source="otp",
        event_status=status,
        user_id=user_id,
        request=request,
        details=merged_details,
    )


def log_genai_access_event(
    db: Session,
    *,
    status: str,
    source: str,
    request: Optional[Request],
    user_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> SecurityLog:
    """Convenience logger for GenAI explanation endpoint access events."""
    merged_details: Dict[str, Any] = {
        "endpoint": endpoint,
        "outcome": status,
    }
    if details:
        merged_details.update(details)

    return log_security_event(
        db,
        event_type=SecurityEventType.GENAI_ACCESS,
        source=source,
        event_status=status,
        user_id=user_id,
        request=request,
        details=merged_details,
        error_message=error_message,
    )
