#routes user_profile.py
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from app.services.user_profile import verify_password
from app.db.db import SessionLocal

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
    create_user
)

router = APIRouter(
    prefix="/api/v1/user_profile",
    tags=["user_profile"]
)


@router.get("", response_model=UserProfileResponse)
def get_user_profile() -> Dict[str, Any]:
    """
    Return the current user's profile.
    
    Returns:
    - user_profile: List of fields personal particulars in the user's profile

    """
    user_id = 1  # TODO: Get from auth token
    users = get_users()
    user = users.get(user_id)
    
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
def user_profile_login(payload: LoginPayload):
    """
    Input: username and password

    Logic: 
    If username does not exist, return error
    If username exists, check hashed password
    If password incorrect, return error
    If username and password correct, return authorised/success
    """
    username = payload.username
    password = payload.password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required."
        )

@router.post("/login", response_model=UserProfileResponse, tags=["user_profile"])
def login_user(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Login endpoint to check if user exists by username.
    
    Request body:
    - username: str
    - password: str
    
    Returns:
    - User profile if credentials are valid
    - 404 error if user doesn't exist
    - 401 error if password is invalid
    """
    username = payload.get("username", "").strip()
    password = payload.get("password", "")
    
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Username is required.",
                    "details": {}
                }
            }
        )
        
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Password is required.",
                    "details": {}
                }
            }
        )
    
    users = get_users()
    
    # Find user by username
    user = None
    for u in users.values():
        if u.get("username") == username:
            user = u
            break
    
    if not user:
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
        
    if not verify_password(password, user["password"]):
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
    
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user.get("name"),
        "email": user.get("email"),
        "benefits_preference": user.get("benefits_preference"),
        "created_date": user["created_date"],
    }
