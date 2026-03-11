from fastapi import APIRouter, HTTPException, status
from app.services.cognito_service import CognitoService
from app.exceptions import ServiceException

router = APIRouter()
cognito_service = CognitoService()

@router.post("/login")
def login(username: str, password: str):
    """
    Login endpoint to authenticate users and return a JWT token.
    """
    try:
        tokens = cognito_service.authenticate_user(username, password)
        return {"message": "Login successful", "tokens": tokens}
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    
@router.post("/registration", status_code=status.HTTP_201_CREATED)
def register(username: str, email: str, password: str):
    """
    Register a new user with a distinct username, email, and password.
    """
    try:
        response = cognito_service.register_user(username, email, password)
        return {
            "message": "User registration successful.",
            "user_sub": response["UserSub"],
            "user_confirmed": response["UserConfirmed"]
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
        # Confirm sign-up
        cognito_service.client.confirm_sign_up(
            ClientId=cognito_service.client_id,
            Username=username,
            ConfirmationCode=confirmation_code,
            SecretHash=cognito_service.calculate_secret_hash(username)
        )

        return {"message": "User confirmed successfully."}

    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
