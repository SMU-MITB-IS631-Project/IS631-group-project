from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.cognito_service import CognitoService


_bearer_scheme = HTTPBearer(auto_error=False)


def get_x_user_id(request: Request) -> Optional[str]:
    """Return raw x-user-id header value (stripped) or None."""
    value = request.headers.get("x-user-id")
    if not value:
        return None
    value = value.strip()
    return value or None


def get_x_user_id_int(x_user_id: Optional[str] = Depends(get_x_user_id)) -> Optional[int]:
    """Return x-user-id as int if it's a plain integer string, else None."""
    if x_user_id and x_user_id.isdigit():
        return int(x_user_id)
    return None


def get_bearer_credentials(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> HTTPAuthorizationCredentials:
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated. Missing Authorization header.",
        )
    return auth


def get_cognito_claims(
    auth: HTTPAuthorizationCredentials = Depends(get_bearer_credentials),
    cognito_service: CognitoService = Depends(CognitoService),
) -> dict[str, Any]:
    return cognito_service.validate_token(auth)


def get_cognito_sub(claims: dict[str, Any] = Depends(get_cognito_claims)) -> str:
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )
    return str(sub)


__all__ = [
    "get_x_user_id",
    "get_x_user_id_int",
    "get_cognito_sub",
    "get_cognito_claims",
    "get_bearer_credentials",
]
