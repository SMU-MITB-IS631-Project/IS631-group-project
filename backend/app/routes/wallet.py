from fastapi import APIRouter, HTTPException, status, Response, Header
from typing import Dict, Any, Optional

from app.models.user_owned_cards import (
    UserOwnedCardCreate,
    UserOwnedCardUpdate,
    UserOwnedCardResponse,
    UserOwnedCarWrappedResponse,
)

from app.services.wallet_service import (
    DEFAULT_USER_ID,
    add_card_to_wallet,
    update_card_in_wallet,
    delete_card_from_wallet,
    card_exists_in_master,
    card_exists_in_user_wallet,
    get_users,
)


router = APIRouter(
    prefix="/api/v1/wallet",
    tags=["wallet"],
)


@router.get("", response_model=UserOwnedCarWrappedResponse)
def get_wallet(x_user_id: Optional[str] = Header(default=str(DEFAULT_USER_ID))):
    user_id = x_user_id or str(DEFAULT_USER_ID)
    users = get_users()
    user = users.get(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Profile not found.",
                    "details": {},
                }
            },
        )

    wallet_data = user.get("wallet", [])
    wallet_cards = [UserOwnedCardResponse(**c) for c in wallet_data]
    return {"wallet": wallet_cards}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Dict[str, UserOwnedCardResponse])
def add_wallet_card(payload: UserOwnedCardCreate) -> Dict[str, Any]:
    user_id = str(DEFAULT_USER_ID)  # TODO: Get from auth token
    card = payload

    if not card_exists_in_master(str(card.card_id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"card_id '{card.card_id}' does not exist in cards master.",
                    "details": {"field": "wallet_card.card_id"},
                }
            },
        )

    if card_exists_in_user_wallet(str(card.card_id), user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": f"card_id '{card.card_id}' already exists in wallet.",
                    "details": {"field": "wallet_card.card_id"},
                }
            },
        )

    card_data = add_card_to_wallet(card.model_dump(), user_id)
    return {"wallet_card": UserOwnedCardResponse(**card_data)}


@router.patch("/{card_id}", response_model=Dict[str, UserOwnedCardResponse])
def update_wallet_card(card_id: str, payload: UserOwnedCardUpdate) -> Dict[str, Any]:
    user_id = str(DEFAULT_USER_ID)  # TODO: Get from auth token

    updates: Dict[str, Any] = {}
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
                    "details": {},
                }
            },
        )

    return {"wallet_card": UserOwnedCardResponse(**updated_card)}


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet_card(card_id: str) -> Response:
    user_id = str(DEFAULT_USER_ID)  # TODO: Get from auth token

    deleted = delete_card_from_wallet(card_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"card_id '{card_id}' not found in wallet.",
                    "details": {},
                }
            },
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
