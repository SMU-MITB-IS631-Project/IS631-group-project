from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.services import get_user_profile_service
from app.models.user_profile import UserProfile, UserProfileResponse, UserProfileUpdate, UserProfileCreate
from app.services.cognito_service import CognitoService
from app.services.user_profile_service import UserProfileService

router = APIRouter(
    prefix="/user_profile",
    tags=["User Profile"]
)
cognito_service = CognitoService()
bearer_scheme = HTTPBearer(auto_error=False)


def _get_cognito_sub(auth: HTTPAuthorizationCredentials) -> str:
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")

    claims = cognito_service.validate_token(auth)
    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return cognito_sub

@router.get("/", response_model=list[UserProfileResponse])
def get_user_profiles(
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    service: UserProfileService = Depends(get_user_profile_service),
):
    _get_cognito_sub(auth)
    users_by_id = service.get_all_user_profiles()
    return list(users_by_id.values())

@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    service: UserProfileService = Depends(get_user_profile_service),
):
    cognito_sub = _get_cognito_sub(auth)

    profile = service.get_user_profile(cognito_sub)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found.")
    return profile

@router.put("/me", response_model=UserProfileResponse)
def update_my_profile(
    update: UserProfileUpdate,
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    service: UserProfileService = Depends(get_user_profile_service),
):
    cognito_sub = _get_cognito_sub(auth)

    try:
        updated_profile = service.update_user_profile(
            cognitosub=cognito_sub,
            name=update.name,
            benefits_preference=update.benefits_preference
        )
        return updated_profile
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/create", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_user_profile(
    profile: UserProfileCreate,
    auth: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    service: UserProfileService = Depends(get_user_profile_service),
):
    cognito_sub = _get_cognito_sub(auth)
    try:
        created_profile = service.create_user_profile(
            username=profile.username,
            email=profile.email,
            cognitosub=cognito_sub,
            name=profile.name,
            benefits_preference=profile.benefits_preference
        )
        return created_profile
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))