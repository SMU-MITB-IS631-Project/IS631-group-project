from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.user_context import get_x_user_id_int
from app.services.errors import ServiceError
from app.services.user_card_service import UserCardManagementService


router = APIRouter(prefix="/api/v1", tags=["User Card Management"])


class WalletCardBody(BaseModel):
    card_id: str
    refresh_day_of_month: int
    annual_fee_billing_date: str
    cycle_spend_sgd: float = 0.0


class WalletCardCreateRequest(BaseModel):
    wallet_card: WalletCardBody


class UserCardUpdateBody(BaseModel):
    card_id: str
    refresh_day_of_month: int
    annual_fee_billing_date: str
    cycle_spend_sgd: float = 0.0


class UserCardUpdateRequest(BaseModel):
    user_card: UserCardUpdateBody


def _unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid user context.",
                "details": {"required_header": "x-user-id"},
            }
        },
    )


def _service_error_response(exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            }
        },
    )


def _wallet_card_dict(card: Any) -> dict[str, Any]:
    expiry: Optional[date] = getattr(card, "card_expiry_date", None)
    cycle_spend = getattr(card, "cycle_spend_sgd", 0.0)
    return {
        "id": str(getattr(card, "id")),
        "card_id": str(getattr(card, "card_id")),
        "refresh_day_of_month": int(getattr(card, "billing_cycle_refresh_day_of_month")),
        "annual_fee_billing_date": expiry.isoformat() if expiry else None,
        "cycle_spend_sgd": float(cycle_spend or 0.0),
    }


def _build_create_payload(body: WalletCardBody) -> tuple[int, dict[str, Any]]:
    card_id_int = int(body.card_id)
    expiry_date = date.fromisoformat(body.annual_fee_billing_date)
    payload: dict[str, Any] = {
        "billing_cycle_refresh_day_of_month": int(body.refresh_day_of_month),
        "card_expiry_date": expiry_date,
        "cycle_spend_sgd": float(body.cycle_spend_sgd or 0.0),
    }
    return card_id_int, payload


@router.get("/user_cards")
def list_user_cards(
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    try:
        cards = service.get_user_cards_by_user_id(user_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return {"user_cards": [_wallet_card_dict(card) for card in cards]}


@router.post("/user_cards", status_code=status.HTTP_201_CREATED)
def create_user_card(
    request_body: WalletCardCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    card_id_int, payload = _build_create_payload(request_body.wallet_card)
    try:
        card = service.add_user_card_by_user_id(user_id, card_id_int, payload)
    except ServiceError as exc:
        return _service_error_response(exc)

    return {"wallet_card": _wallet_card_dict(card)}


@router.put("/user_cards/{owned_card_id}")
def update_user_card(
    owned_card_id: str,
    request_body: UserCardUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    card_id_int, payload = _build_create_payload(request_body.user_card)
    payload["card_id"] = card_id_int
    try:
        card = service.update_user_card_by_owned_id(user_id, int(owned_card_id), payload)
    except ServiceError as exc:
        return _service_error_response(exc)
    return {"wallet_card": _wallet_card_dict(card)}


@router.delete(
    "/user_cards/{owned_card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_user_card(
    owned_card_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> Response:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    try:
        service.remove_user_card_by_owned_id(user_id, int(owned_card_id))
    except ServiceError as exc:
        return _service_error_response(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/wallet")
def list_wallet_cards(
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    try:
        cards = service.get_user_cards_by_user_id(user_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return {"wallet": [_wallet_card_dict(card) for card in cards]}


@router.post("/wallet", status_code=status.HTTP_201_CREATED)
def create_wallet_card(
    request_body: WalletCardCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    card_id_int, payload = _build_create_payload(request_body.wallet_card)
    try:
        card = service.add_user_card_by_user_id(user_id, card_id_int, payload)
    except ServiceError as exc:
        return _service_error_response(exc)
    return {"wallet_card": _wallet_card_dict(card)}


@router.patch("/wallet/{owned_card_id}")
def update_wallet_card(
    owned_card_id: str,
    request_body: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> dict[str, Any]:
    if not user_id:
        return _unauthorized_response()

    updates: dict[str, Any] = {}
    if "refresh_day_of_month" in request_body:
        updates["billing_cycle_refresh_day_of_month"] = int(request_body["refresh_day_of_month"])
    if "annual_fee_billing_date" in request_body:
        updates["card_expiry_date"] = date.fromisoformat(str(request_body["annual_fee_billing_date"]))
    if "cycle_spend_sgd" in request_body:
        updates["cycle_spend_sgd"] = float(request_body["cycle_spend_sgd"])

    service = UserCardManagementService(db)
    try:
        card = service.update_user_card_by_owned_id(user_id, int(owned_card_id), updates)
    except ServiceError as exc:
        return _service_error_response(exc)
    return {"wallet_card": _wallet_card_dict(card)}


@router.delete(
    "/wallet/{owned_card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_wallet_card(
    owned_card_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_x_user_id_int),
) -> Response:
    if not user_id:
        return _unauthorized_response()

    service = UserCardManagementService(db)
    try:
        service.remove_user_card_by_owned_id(user_id, int(owned_card_id))
    except ServiceError as exc:
        return _service_error_response(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)