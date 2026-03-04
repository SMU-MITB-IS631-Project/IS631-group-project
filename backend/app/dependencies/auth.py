"""Authentication dependencies for FastAPI routes.

Provides user identification via x-user-id header following the team's
decision (March 4, 2026) to use header-based authentication during session.
"""

from typing import Optional
from fastapi import Header, HTTPException, status


async def get_current_user_id(
    x_user_id: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Extract x-user-id header from request.
    
    Returns the user ID if present, None otherwise.
    Use this for endpoints where authentication is optional.
    """
    return x_user_id.strip() if x_user_id else None


async def get_required_user_id(
    x_user_id: Optional[str] = Header(None)
) -> str:
    """
    Extract and require x-user-id header from request.
    
    Raises 401 Unauthorized if header is missing or empty.
    Use this for endpoints where authentication is required.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing or invalid user context.",
                    "details": {"required_header": "x-user-id"},
                }
            },
        )
    return x_user_id.strip()
