#routes user_profile.py
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List

from app.models.user_profile import (
    UserProfileResponse,
    UserProfileCreate,
    UserProfileUpdate
)
from app.services.user_profile import (
    get_users,
    create_user,
    get_next_available_user_id
)

router = APIRouter(
    prefix="/api/v1/user_profile",
    tags=["user_profile"]
)


@router.get("", response_model=List[UserProfileResponse])
def get_user_profiles() -> List[Dict[str, Any]]:
    """
    Returns a list of all the profiles in the database

    Returns:
    - user_profiles: Fields of all user profiles

    Raises:
    - 404: No profiles found
    """
    users = get_users()

    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "No profiles found.",
                    "details": {}
                }
            }
        )

    return [
        {
            "id": user["id"],
            "username": user["username"],
            "name": user.get("name"),
            "email": user.get("email"),
            "benefits_preference": user.get("benefits_preference"),
            "created_date": user["created_date"],
        }
        for user in users.values()
    ]


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user_profile_by_id(user_id: int) -> Dict[str, Any]:
    """
    Return the corresponding user profile that matches the id.

    Path Parameters:
    - user_id: The user ID to fetch

    Returns:
    - user_profile: Fields of the matching user profile

    Raises:
    - 404: Profile not found
    """
    users = get_users()
    user = users.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Profile not found.",
                    "details": {"user_id": user_id}
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
    
    next_user_id = get_next_available_user_id()

    new_user = create_user(
        username=next_user_id,
        password_hash=payload.password,
        name=payload.name,
        email=payload.email
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


