from typing import Dict, Any

from fastapi import APIRouter, HTTPException, logger, status, Depends

from app.exceptions import ServiceException
from app.dependencies.services import get_user_profile_service
from app.models.user_profile import UserProfileResponse, UserProfileUpdate
from app.services.user_profile_service import UserProfileService
from app.dependencies.auth import required_admin_role, required_authenticated

router = APIRouter(
    prefix="/user_profile",
    tags=["User Profile"]
)


def _get_cognito_sub_from_claims(claims: Dict[str, Any]) -> str:
    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return str(cognito_sub)

# @router.get("/", response_model=list[UserProfileResponse], dependencies=[Depends(required_admin_role)])
# def get_user_profiles(service: UserProfileService = Depends(get_user_profile_service)):
#     return service.get_all_user_profiles()

@router.get("/user", response_model=UserProfileResponse)
def get_my_profile(
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserProfileService = Depends(get_user_profile_service),
):
    cognito_sub = _get_cognito_sub_from_claims(claims)

    profile = service.get_user_profile(cognito_sub)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found.")
    return profile

@router.put("/user", response_model=UserProfileResponse)
def update_my_profile(
    update: UserProfileUpdate,
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserProfileService = Depends(get_user_profile_service),
):
    cognito_sub = _get_cognito_sub_from_claims(claims)

    try:
        updated_profile = service.update_user_profile(
            cognitosub=cognito_sub,
            name=update.name,
            benefits_preference=update.benefits_preference
        )
        return updated_profile
    
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception:
        logger.exception("Unexpected error updating profile")
        raise HTTPException(status_code=500, detail="Internal server error.")

