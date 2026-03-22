import logging

from fastapi import APIRouter, HTTPException, status, Depends

from app.dependencies.user_context import get_cognito_sub
from app.dependencies.services import get_user_card_management_service
from app.services.errors import ServiceError
from app.services.user_card_service import UserCardManagementService
from app.models.user_owned_cards import UserOwnedCardResponse, UserOwnedCardUpdate, UserOwnedCardCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user/cards", tags=["User Card Management"])

@router.get("/", response_model=list[UserOwnedCardResponse])
def get_user_cards(
    cognito_sub: str = Depends(get_cognito_sub),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Get all cards owned by the authenticated user.
    """
    try:
        return service.get_user_cards(cognito_sub)
    except ServiceError as exc:
        logger.error("Error fetching user cards: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    

@router.post("", response_model=UserOwnedCardResponse, status_code=status.HTTP_201_CREATED)
def add_user_card(
    card_data: UserOwnedCardCreate,
    cognito_sub: str = Depends(get_cognito_sub),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Add a card to the authenticated user's collection.
    """
    try:
        return service.add_user_card(cognito_sub, card_data.card_id, card_data)
    except ServiceError as exc:
        logger.error("Error adding user card: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    
@router.put("/{card_id}", response_model=UserOwnedCardResponse)
def update_user_card(
    card_id: int,
    card_data: UserOwnedCardUpdate,
    cognito_sub: str = Depends(get_cognito_sub),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Update details of a card in the authenticated user's collection.
    """
    try:
        return service.update_user_card(cognito_sub, card_id, card_data)
    except ServiceError as exc:
        logger.error("Error updating user card: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_card(
    card_id: int,
    cognito_sub: str = Depends(get_cognito_sub),
    service: UserCardManagementService = Depends(get_user_card_management_service),
):
    """
    Remove a card from the authenticated user's collection.
    """
    try:
        service.remove_user_card(cognito_sub, card_id)
    except ServiceError as exc:
        logger.error("Error removing user card: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)