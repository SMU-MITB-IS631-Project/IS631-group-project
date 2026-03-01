from fastapi import HTTPException, Request, status


def _error_payload(code: str, message: str, details: dict) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }


def require_user_id_header(request: Request) -> str:
    user_id = (request.headers.get("x-user-id") or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_payload(
                "UNAUTHORIZED",
                "Missing or invalid user context.",
                {"required_header": "x-user-id"},
            ),
        )
    return user_id


def parse_user_id_to_int(raw_user_id: str) -> int:
    value = (raw_user_id or "").strip()
    if value.isdigit():
        return int(value)
    if value.startswith("u_") and value[2:].isdigit():
        return int(value[2:])
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_error_payload(
            "VALIDATION_ERROR",
            "x-user-id header must be an integer or u_<integer> format.",
            {"header": "x-user-id", "value": raw_user_id},
        ),
    )


def require_user_id_int(request: Request) -> int:
    return parse_user_id_to_int(require_user_id_header(request))


def normalize_user_id(value: str) -> str:
    raw = (value or "").strip()
    if raw.isdigit():
        return str(int(raw))
    if raw.startswith("u_") and raw[2:].isdigit():
        return str(int(raw[2:]))
    return raw.lower()
