from typing import Any, Dict
import logging

from fastapi import APIRouter, HTTPException, status, Depends

from app.dependencies.services import get_user_card_management_service
from app.dependencies.auth import required_authenticated
from app.exceptions import ServiceException
from app.models.user_owned_cards import UserOwnedCardCreate, UserOwnedCardResponse, UserOwnedCardUpdate
from app.services.errors import ServiceError
from app.services.user_card_service import UserCardManagementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user/cards", tags=["User Card Management"])


def _raise_http_from_service_exception(exc: ServiceException | ServiceError) -> None:
    if isinstance(exc, ServiceError):
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_cognito_sub_from_claims(claims: Dict[str, Any]) -> str:
    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return str(cognito_sub)


def _raise_http_from_service_exception(exc: ServiceException | ServiceError) -> None:
    if isinstance(exc, ServiceException):
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )

@router.get("/", response_model=list[UserOwnedCardResponse])
def get_user_cards(
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Get all cards owned by the authenticated user.
    """
    try:
        cognito_sub = _get_cognito_sub_from_claims(claims)
        return service.get_user_cards(cognito_sub)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error fetching user cards: %s", exc)
        _raise_http_from_service_exception(exc)
    

@router.post("", response_model=UserOwnedCardResponse, status_code=status.HTTP_201_CREATED)
def add_user_card(
    card_data: UserOwnedCardCreate,
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Add a card to the authenticated user's collection.
    """
    try:
        cognito_sub = _get_cognito_sub_from_claims(claims)
        return service.add_user_card(cognito_sub, card_data.card_id, card_data)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error adding user card: %s", exc)
        _raise_http_from_service_exception(exc)

    
@router.put("/{card_id}", response_model=UserOwnedCardResponse)
def update_user_card(
    card_id: int,
    card_data: UserOwnedCardUpdate,
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Update details of a card in the authenticated user's collection.
    """
    try:
        cognito_sub = _get_cognito_sub_from_claims(claims)
        return service.update_user_card(cognito_sub, card_id, card_data)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error updating user card: %s", exc)
        _raise_http_from_service_exception(exc)
    

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_card(
    card_id: int,
    claims: Dict[str, Any] = Depends(required_authenticated),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Remove a card from the authenticated user's collection.
    """
    try:
        cognito_sub = _get_cognito_sub_from_claims(claims)
        service.remove_user_card(cognito_sub, card_id)
    except (ServiceException, ServiceError) as exc:
        logger.error("Error removing user card: %s", exc)
        _raise_http_from_service_exception(exc)