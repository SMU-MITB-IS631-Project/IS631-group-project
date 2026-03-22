
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.dependencies.services import get_user_profile_service
from app.models.user_profile import UserProfileResponse, UserProfileUpdate
from app.services.cognito_service import CognitoService
from app.services.errors import ServiceError
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
    return service.get_all_user_profiles()

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
            benefits_preference=update.benefits_preference,
        )
        return updated_profile
    except ServiceError as exc:
        detail = getattr(exc, "detail", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=detail)

