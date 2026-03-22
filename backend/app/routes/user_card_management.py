from typing import Any, Dict
import logging

from fastapi import APIRouter, HTTPException, status, Depends

from app.dependencies.services import get_user_card_management_service
from app.dependencies.auth import required_authenticated
from app.services.errors import ServiceError
from app.services.user_card_service import UserCardManagementService
from app.models.user_owned_cards import UserOwnedCardResponse, UserOwnedCardUpdate, UserOwnedCardCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user/cards", tags=["User Card Management"])


def _get_cognito_sub_from_claims(claims: Dict[str, Any]) -> str:
    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    return str(cognito_sub)

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
    except ServiceError as e:
        logger.error(f"Error fetching user cards: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    

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
    except ServiceError as e:
        logger.error(f"Error adding user card: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)    

    
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
    except ServiceError as e:
        logger.error(f"Error updating user card: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    

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
    except ServiceError as e:
        logger.error(f"Error removing user card: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)