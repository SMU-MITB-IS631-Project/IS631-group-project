#routes user_profile.py
from fastapi import APIRouter, HTTPException, status, Response
from typing import Dict, Any
from app.services.user_profile import verify_password
from app.db.db import SessionLocal

from app.models.user_profile import (
    UserProfile,
    BenefitsPreference,
    UserProfileResponse,
    UserProfileCreate,
    UserProfileBase,
    UserProfileUpdate,
    LoginPayload,
    LoginResponse
)
from app.services.user_profile import (
    get_users,
    get_next_available_user_id,
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

    user_id = get_next_available_user_id(users)

    new_user = create_user(
        user_id=user_id,
        username=payload.username,
        password=payload.password,
        name=payload.name,
        email=payload.email,
        benefits_preference=payload.benefits_preference
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

    session = SessionLocal()
    try:
        user = session.query(UserProfile).filter(UserProfile.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
        return {"message": "Login successful", "user_id": user.id}
    finally:
        session.close()