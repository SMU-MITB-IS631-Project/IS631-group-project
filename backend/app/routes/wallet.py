from fastapi import APIRouter, HTTPException, status, Response, Header
from typing import Dict, Any, List, Optional

from app.models.wallet import (
    UserOwnedCardBase,
    UserOwnedCardCreate,
    UserOwnedCardUpdate,
    UserOwnedCardResponse,
)
from app.services.wallet_service import (
    DEFAULT_USER_ID,
    get_user_wallet,
    add_card_to_wallet,
    update_card_in_wallet,
    delete_card_from_wallet,
    card_exists_in_master,
    card_exists_in_user_wallet,
    get_users
)

router = APIRouter(
    prefix="/api/v1/wallet",
    tags=["wallet"]
)


@router.get("", response_model=UserOwnedCardResponse)
def get_wallet(x_user_id: Optional[str] = Header(default=DEFAULT_USER_ID)) -> Dict[str, Any]:
    """
    Return the current user's wallet.
    
    Returns:
    - wallet: List of credit cards in user's wallet
    
    Security:
    - Returns wallet for authenticated user (user_id from x-user-id header)
    """
    user_id = x_user_id or DEFAULT_USER_ID
    users = get_users()
    user = users.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Profile not found.",
                    "details": {}
                }
            }
        )

    wallet_data = user.get("wallet", [])
    wallet_cards = [List(UserOwnedCardResponse)(**c) for c in wallet_data]
    return {"wallet": [c.model_dump() for c in wallet_cards]}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserOwnedCardResponse)
def add_wallet_card(payload: UserOwnedCardCreate) -> Dict[str, Any]:
    """
    Add a new card to the user's wallet.
    
    Request body:
    - wallet_card: Card details to add
    
    Validation:
    - card_id must exist in cards master
    - card_id must not already exist in wallet
    
    Returns:
    - wallet_card: The added card details
    """
    user_id = DEFAULT_USER_ID  # TODO: Get from auth token
    card = payload.UserOwnedCardCreate

    # Business validation: card_id must exist in cards master
    if not card_exists_in_master(card.card_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"card_id '{card.card_id}' does not exist in cards master.",
                    "details": {"field": "wallet_card.card_id"}
                }
            }
        )

    # Prevent duplicates
    if card_exists_in_user_wallet(card.card_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": f"card_id '{card.card_id}' already exists in wallet.",
                    "details": {"field": "wallet_card.card_id"}
                }
            }
        )

    # Add card to wallet
    card_data = add_card_to_wallet(card.model_dump(), user_id)
    return {"wallet_card": card_data}


@router.patch("/{card_id}", response_model=UserOwnedCardResponse)
def update_wallet_card(card_id: str, payload: UserOwnedCardUpdate) -> Dict[str, Any]:
    """
    Update fields of an existing wallet card.
    
    Path Parameters:
    - card_id: The card ID to update
    
    Request body:
    - Only provided fields are updated
    
    Returns:
    - wallet_card: The updated card details
    """
    user_id = DEFAULT_USER_ID  # TODO: Get from auth token
    
    # Prepare updates dict with only non-None values
    updates = {}
    if payload.billing_cycle_refresh_date is not None:
        updates["billing_cycle_refresh_date"] = payload.billing_cycle_refresh_date
    if payload.card_expiry_date is not None:
        updates["card_expiry_date"] = payload.card_expiry_date
    if payload.cycle_spend_sgd is not None:
        updates["cycle_spend_sgd"] = payload.cycle_spend_sgd
    if payload.status is not None:
        updates["status"] = payload.status
    
    updated_card = update_card_in_wallet(card_id, updates, user_id)
    
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"card_id '{card_id}' not found in wallet.",
                    "details": {}
                }
            }
        )
    
    return {"wallet_card": UserOwnedCardBase(**updated_card).model_dump()}


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet_card(card_id: str) -> Response:
    """
    Remove a card from the user's wallet.
    
    Path Parameters:
    - card_id: The card ID to remove
    
    Returns:
    - 204 No Content on success
    - 404 if card not found
    """
    user_id = DEFAULT_USER_ID  # TODO: Get from auth token
    
    deleted = delete_card_from_wallet(card_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"card_id '{card_id}' not found in wallet.",
                    "details": {}
                }
            }
        )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
