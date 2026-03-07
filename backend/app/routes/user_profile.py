#routes user_profile.py
import logging

from fastapi import APIRouter, HTTPException, status, Depends, Request
from passlib.exc import UnknownHashError
from typing import Dict, Any
from app.services.user_profile import verify_password
from app.db.db import SessionLocal
from app.dependencies.db import get_db
from app.services.user_card_services import get_required_user_id
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.services.security_log_service import log_auth_event

from app.models.user_profile import (
    UserProfileResponse,
    UserProfileCreate,
    UserProfileBase,
    UserProfileUpdate,
    LoginPayload,
    LoginResponse
)
from app.services.user_profile import (
    get_users,
    create_user,
    get_user_by_username
)

router = APIRouter(
    prefix="/api/v1/user_profile",
    tags=["user_profile"]
)

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


def _safe_log_auth_event(
    db: Session,
    *,
    status: str,
    request: Request,
    user_id: int | None = None,
    username: str | None = None,
    reason: str | None = None,
    error_message: str | None = None,
) -> None:
    # Security logging must never block auth flow.
    try:
        log_auth_event(
            db,
            status=status,
            request=request,
            user_id=user_id,
            username=username,
            reason=reason,
            error_message=error_message,
        )
    except Exception:
        logger.exception("Failed to write authentication security log")

@router.get("", response_model=UserProfileResponse)
def get_user_profile(user_id: str = Depends(get_required_user_id)) -> Dict[str, Any]:
    """
    Return the current user's profile.
    
    Returns:
    - user_profile: List of fields personal particulars in the user's profile
    
    Security:
    - Requires x-user-id header from authenticated session
    """
    users = get_users()

    # Normalize the incoming user identifier to match the int keys used by get_users().
    user = None
    try:
        int_user_id = int(user_id)
    except (TypeError, ValueError):
        int_user_id = None

    if int_user_id is not None:
        user = users.get(int_user_id)

    # If no user was found by integer ID, fall back to matching by username.
    if not user:
        # Handle "u_###" format (e.g. "u_001" -> 1)
        if user_id.startswith("u_") and user_id[2:].isdigit():
            user = users.get(int(user_id[2:]))
        else:
            for u in users.values():
                if u.get("username") == user_id:
                    user = u
                    break
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Profile not found.",
                    "details": {}
                }
            }
        )

    return {
        "id": user["id"],
        "username": user["username"],
        "name": user.get("name"),
        "email": user.get("email"),
        "benefits_preference": user.get("benefits_preference"),
        "created_date": user["created_date"],
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserProfileResponse)
def create_user_profile(payload: UserProfileCreate) -> Dict[str, Any]:
    """
    Add a new profile to app.db
    
    Request body:
    - profile details to add
    
    Validation:
    - id must not already exist in app.db
    - username must not already exist in app.db
    - email must not already exist in app.db
    
    Returns:
    - success status if created
    - failed status if not created
    """
    users = get_users()

    # Uniqueness checks
    if any(u["username"] == payload.username for u in users.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "Username already exists.",
                    "details": {"username": payload.username}
                }
            }
        )

    if payload.email and any(u.get("email") == payload.email for u in users.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "Email already exists.",
                    "details": {"email": payload.email}
                }
            }
        )
    
    try:
        new_user = create_user(
            username=payload.username,
            password=payload.password,
            name=payload.name,
            email=payload.email,
            benefits_preference=payload.benefits_preference.value if payload.benefits_preference else None
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": str(exc),
                    "details": {"username": payload.username}
                }
            }
        )

    return {
        "id": new_user["id"],
        "username": new_user["username"],
        "name": new_user.get("name"),
        "email": new_user.get("email"),
        "benefits_preference": new_user.get("benefits_preference"),
        "created_date": new_user["created_date"],
    }

@router.patch("/{user_id}", response_model=UserProfileResponse)
def update_user_profile(user_id: str, payload: UserProfileUpdate) -> Dict[str, Any]:
    """
    Update fields of an existing user profile
    
    Path Parameters:
    - user_id: The user ID to update
    
    Request body:
    - Only provided fields are updated
    
    Returns:
    - The updated full user profile
    """
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid user_id.",
                    "details": {"user_id": user_id}
                }
            }
        )

    users = get_users()
    user = users.get(user_id_int)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Profile not found.",
                    "details": {"user_id": user_id_int}
                }
            }
        )

    updates = payload.model_dump(exclude_unset=True)

    # Disallow created_date updates
    updates.pop("created_date", None)

    # Uniqueness checks if username/email provided
    if "username" in updates:
        if any(u["username"] == updates["username"] and u["id"] != user_id_int for u in users.values()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CONFLICT",
                        "message": "Username already exists.",
                        "details": {"username": updates["username"]}
                    }
                }
            )

    if "email" in updates and updates["email"] is not None:
        if any(u.get("email") == updates["email"] and u["id"] != user_id_int for u in users.values()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "CONFLICT",
                        "message": "Email already exists.",
                        "details": {"email": updates["email"]}
                    }
                }
            )

    # Handle password separately
    if "password" in updates:
        # TODO: hash password before storing
        user["password_hash"] = updates.pop("password")

    # Apply other updates
    for key, value in updates.items():
        user[key] = value

    return {
        "id": user["id"],
        "username": user["username"],
        "name": user.get("name"),
        "email": user.get("email"),
        "benefits_preference": user.get("benefits_preference"),
        "created_date": user["created_date"],
    }

@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Login endpoint to authenticate user credentials.
    
    Request body:
    - username: str
    - password: str
    
    Returns:
    - Login response with user profile if credentials are valid
    - 400 error if username or password is missing
    - 404 error if user doesn't exist
    - 401 error if password is invalid
    """
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        _safe_log_auth_event(
            db,
            status="failed",
            request=request,
            username=username or None,
            reason="missing_fields",
            error_message="Missing username or password",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Missing username or password",
                    "details": {}
                }
            }
        )
    
    user = get_user_by_username(username)
    
    if not user:
        _safe_log_auth_event(
            db,
            status="failed",
            request=request,
            username=username,
            reason="user_not_found",
            error_message="User not found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "User not found.",
                    "details": {"username": username}
                }
            }
        )
        
    try:
        is_valid_password = verify_password(password, user.password_hash)
    except (UnknownHashError, ValueError, TypeError):
        # Some legacy seeded users have non-passlib hashes; treat as invalid creds.
        is_valid_password = False

    if not is_valid_password:
        _safe_log_auth_event(
            db,
            status="failed",
            request=request,
            user_id=user.id,
            username=username,
            reason="invalid_password",
            error_message="Invalid username or password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid username or password.",
                    "details": {}
                }
            }
        )
    
    _safe_log_auth_event(
        db,
        status="success",
        request=request,
        user_id=user.id,
        username=username,
        reason="authenticated",
    )

    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "benefits_preference": user.benefits_preference,
        "created_date": user.created_date,
    }
