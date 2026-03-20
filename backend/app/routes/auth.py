from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.cognito_service import CognitoService
from app.exceptions import ServiceException
from app.models.user_profile import BenefitsPreference
from app.services.user_profile_service import UserProfileService
from app.dependencies.db import get_db
from jose import jwt

router = APIRouter()
cognito_service = CognitoService()


class RegistrationPayload(BaseModel):
    username: str
    email: str
    password: str
    name: str | None = None
    benefits_preference: BenefitsPreference = BenefitsPreference.no_preference

@router.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    """
    Login endpoint to authenticate users and return a JWT token.
    """
    try:
        tokens = cognito_service.authenticate_user(username, password)

        # Decode ID token to get cognito_sub
        id_token = tokens["id_token"]
        decoded = jwt.get_unverified_claims(id_token)
        cognito_sub = decoded.get("sub")
        cognito_username = decoded.get("cognito:username", username)
        
        if not cognito_sub:
            raise HTTPException(status_code=401, detail="Invalid token payload.")

        user_profile_service = UserProfileService(db)
        user = user_profile_service.get_user_profile(cognito_sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete registration first.",
            )
        
        return {"message": "Login successful", "user_id": user.id, "tokens": tokens}
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    
@router.post("/registration", status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationPayload, db: Session = Depends(get_db)):
    """
    Register a new user with a distinct username, email, and password.
    """
    try:
        response = cognito_service.register_user(payload.username, payload.email, payload.password)
        cognito_sub = response["UserSub"]

        user_profile_service = UserProfileService(db)
        try:
            user = user_profile_service.create_user_profile(
                username=payload.username,
                cognitosub=cognito_sub,
                email=payload.email,
                name=payload.name,
                benefits_preference=payload.benefits_preference,
            )
        except Exception:
            cognito_service.delete_user(payload.username)
            raise

        return {
            "message": "User registration successful.",
            "user_sub": response["UserSub"],
            "user_confirmed": response["UserConfirmed"],
            "user_id": user.id,
            "profile": {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "benefits_preference": user.benefits_preference.value if user.benefits_preference else None,
                "created_date": user.created_date,
            },
        }
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    
# Can we improve the code quality of the following endpoint implementation?
@router.post("/confirmation")
def confirm(username: str, confirmation_code: str):
    """
    Confirm the user's email address using the code sent by Cognito.
    """
    try:
        cognito_service.confirm_user(username=username, confirmation_code=confirmation_code)

        return {"message": "User confirmed successfully."}

    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
