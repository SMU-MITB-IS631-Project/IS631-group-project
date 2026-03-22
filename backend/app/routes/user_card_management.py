import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies.services import get_user_card_management_service
from app.models.user_owned_cards import (
    UserOwnedCardCreate,
    UserOwnedCardResponse,
    UserOwnedCardUpdate,
)
from app.exceptions import ServiceException
from app.services.cognito_service import CognitoService
from app.services.errors import ServiceError
from app.services.user_card_service import UserCardManagementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user/cards", tags=["User Card Management"])

_bearer_scheme = HTTPBearer(auto_error=False)

try:
    cognito_service = CognitoService()
except Exception:
    logger.exception("Failed to initialize CognitoService")
    class _CognitoServiceFallback:
        def validate_token(self, *_args, **_kwargs):
            raise RuntimeError("CognitoService unavailable")

    cognito_service = _CognitoServiceFallback()


def _raise_http_from_service_exception(exc: ServiceException | ServiceError) -> None:
    if isinstance(exc, ServiceException):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def get_cognito_sub_from_auth_header(
    auth: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated. Missing Authorization header.",
        )

    try:
        claims = cognito_service.validate_token(auth)
    except ServiceException as exc:
        # Translate Cognito validation errors into expected HTTP semantics.
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        )
    cognito_sub = claims.get("sub") if isinstance(claims, dict) else None
    if not cognito_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )
    return str(cognito_sub)

@router.get("/", response_model=list[UserOwnedCardResponse])
def get_user_cards(
    cognito_sub: str = Depends(get_cognito_sub_from_auth_header),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Get all cards owned by the authenticated user.
    """
    try:
        return service.get_user_cards(cognito_sub)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error fetching user cards: %s", exc)
        _raise_http_from_service_exception(exc)
    

@router.post("", response_model=UserOwnedCardResponse, status_code=status.HTTP_201_CREATED)
def add_user_card(
    card_data: UserOwnedCardCreate,
    cognito_sub: str = Depends(get_cognito_sub_from_auth_header),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Add a card to the authenticated user's collection.
    """
    try:
        return service.add_user_card(cognito_sub, card_data.card_id, card_data)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error adding user card: %s", exc)
        _raise_http_from_service_exception(exc)

    
@router.put("/{card_id}", response_model=UserOwnedCardResponse)
def update_user_card(
    card_id: int,
    card_data: UserOwnedCardUpdate,
    cognito_sub: str = Depends(get_cognito_sub_from_auth_header),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Update details of a card in the authenticated user's collection.
    """
    try:
        return service.update_user_card(cognito_sub, card_id, card_data)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error updating user card: %s", exc)
        _raise_http_from_service_exception(exc)
    

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_card(
    card_id: int,
    cognito_sub: str = Depends(get_cognito_sub_from_auth_header),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Remove a card from the authenticated user's collection.
    """
    try:
        service.remove_user_card(cognito_sub, card_id)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error removing user card: %s", exc)
        _raise_http_from_service_exception(exc)