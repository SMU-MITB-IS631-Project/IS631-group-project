from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.cognito_service import CognitoService
from app.exceptions import ServiceException
from app.models.user_profile import BenefitsPreference
from app.services.user_profile_service import UserProfileService
from app.dependencies.db import get_db
from app.services.security_log_service import SecurityEventType, log_auth_event, log_otp_event
from jose import jwt

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
cognito_service = CognitoService()


class RegistrationPayload(BaseModel):
    username: str
    email: str
    password: str
    name: str | None = None
    benefits_preference: BenefitsPreference = BenefitsPreference.no_preference


class LoginPayload(BaseModel):
    username: str
    password: str


def _safe_log_auth(
    db: Session,
    *,
    status: str,
    request: Request,
    username: str,
    user_id: int | None = None,
    reason: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        log_auth_event(
            db,
            status=status,
            source="auth.login",
            request=request,
            user_id=user_id,
            username=username,
            reason=reason,
            error_message=error_message,
        )
    except Exception:
        # Never block auth flow because logging fails.
        pass


def _safe_log_otp(
    db: Session,
    *,
    event_type: str,
    status: str,
    request: Request,
    source: str,
    channel: str = "email",
    reason: str | None = None,
    details: dict | None = None,
) -> None:
    try:
        log_otp_event(
            db,
            event_type=event_type,
            status=status,
            request=request,
            source=source,
            channel=channel,
            reason=reason,
            details=details,
        )
    except Exception:
        # Never block auth flow because logging fails.
        pass

@router.post("/login")
def login(
    request: Request,
    payload: LoginPayload | None = None,
    username: str | None = None,
    password: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Login endpoint to authenticate users and return a JWT token.
    """
    resolved_username = (payload.username if payload else username) or ""
    resolved_username = resolved_username.strip()
    resolved_password = (payload.password if payload else password) or ""

    if not resolved_username or not resolved_password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    try:
        tokens = cognito_service.authenticate_user(resolved_username, resolved_password)

        # Decode ID token to get cognito_sub
        id_token = tokens["id_token"]
        decoded = jwt.get_unverified_claims(id_token)
        cognito_sub = decoded.get("sub")
        cognito_username = decoded.get("cognito:username", resolved_username)
        
        if not cognito_sub:
            raise ServiceException(status_code=401, detail="Invalid token payload.")

        user_profile_service = UserProfileService(db)
        user = user_profile_service.get_user_profile(cognito_sub)
        if not user:
            raise ServiceException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete registration first.",
            )

        _safe_log_auth(
            db,
            status="success",
            request=request,
            username=cognito_username,
            user_id=user.id,
            reason="authenticated",
        )
        
        return {"message": "Login successful", "user_id": user.id, "tokens": tokens}
    except ServiceException as e:
        _safe_log_auth(
            db,
            status="failed",
            request=request,
            username=resolved_username,
            reason="authentication_failed",
            error_message=e.detail,
        )
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        _safe_log_auth(
            db,
            status="failed",
            request=request,
            username=resolved_username,
            reason="unexpected_error",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="Internal server error.")
    
@router.post("/registration", status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationPayload, request: Request, db: Session = Depends(get_db)):
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
            # Best-effort cleanup: profile creation failure should not be hidden by
            # Cognito admin credential issues during rollback.
            try:
                cognito_service.delete_user(payload.username)
            except ServiceException:
                pass
            raise

        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_REQUEST,
            status="success",
            request=request,
            source="auth.registration",
            reason="signup_otp_sent",
            details={"username": payload.username, "email": payload.email, "user_id": user.id},
        )

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
        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_REQUEST,
            status="failed",
            request=request,
            source="auth.registration",
            reason="signup_failed",
            details={"username": payload.username, "email": payload.email, "error_message": e.detail},
        )
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_REQUEST,
            status="failed",
            request=request,
            source="auth.registration",
            reason="registration_profile_creation_failed",
            details={"username": payload.username, "email": payload.email, "error_message": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error.")
    
# Can we improve the code quality of the following endpoint implementation?
@router.post("/confirmation")
def confirm(
    username: str,
    confirmation_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Confirm the user's email address using the code sent by Cognito.
    """
    try:
        cognito_service.confirm_user(username=username, confirmation_code=confirmation_code)

        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_VERIFY,
            status="success",
            request=request,
            source="auth.confirmation",
            reason="otp_confirmed",
            details={"username": username},
        )

        return {"message": "User confirmed successfully."}

    except ServiceException as e:
        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_VERIFY,
            status="failed",
            request=request,
            source="auth.confirmation",
            reason="otp_confirmation_failed",
            details={"username": username, "error_message": e.detail},
        )
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        _safe_log_otp(
            db,
            event_type=SecurityEventType.OTP_VERIFY,
            status="failed",
            request=request,
            source="auth.confirmation",
            reason="unexpected_error",
            details={"username": username, "error_message": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error.")
