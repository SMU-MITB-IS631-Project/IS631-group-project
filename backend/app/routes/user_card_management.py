"""User card management routes.

Implements Sprint 1 assigned user stories:
- View user-owned cards (GET /api/v1/user_cards)
- Edit user-owned cards (PUT /api/v1/user_cards/{id})
- Delete user-owned cards (DELETE /api/v1/user_cards/{id})

Route handlers keep local error response shaping and delegate business logic
to app.services.user_card_services.
Card catalog validation is resolved by the service against the
`card_catalogue` table/model in the application database.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.services.user_card_services import ServiceError, UserCardManagementService

logger = logging.getLogger(__name__)


class WalletCard(BaseModel):
    id: Optional[int] = None  # UserOwnedCard primary key, for deleting/updating
    card_id: str
    refresh_day_of_month: int = Field(..., ge=1, le=31)
    annual_fee_billing_date: str  # YYYY-MM-DD
    cycle_spend_sgd: float = Field(0, ge=0)

    @validator("annual_fee_billing_date")
    def validate_annual_fee_billing_date(cls, v: str) -> str:
        """Ensure date is in ISO YYYY-MM-DD format, per API contract."""
        try:
            # fromisoformat will raise ValueError if format is invalid
            datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("annual_fee_billing_date must be YYYY-MM-DD") from exc
        return v


class WalletCardCreate(BaseModel):
    wallet_card: WalletCard


class WalletCardUpdate(BaseModel):
    refresh_day_of_month: Optional[int] = Field(None, ge=1, le=31)
    annual_fee_billing_date: Optional[str] = None
    cycle_spend_sgd: Optional[float] = Field(None, ge=0)


class UserCardPut(BaseModel):
    user_card: WalletCard


class UserCardsResponse(BaseModel):
    user_cards: List[Dict[str, Any]]


class Profile(BaseModel):
    user_id: str
    username: str
    preference: str
    wallet: List[WalletCard]


class ProfileRequest(BaseModel):
    profile: Profile


class ProfileResponse(BaseModel):
    profile: Profile


class WalletResponse(BaseModel):
    wallet: List[WalletCard]


class WalletCardResponse(BaseModel):
    wallet_card: WalletCard


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=details or {}),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _get_user_id_from_request(request: Request) -> Optional[str]:
    user_id = request.headers.get("x-user-id")
    return user_id.strip() if user_id else None


def _service_from_request(db: Session) -> UserCardManagementService:
    return UserCardManagementService(db)


def _unauthorized_response() -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="UNAUTHORIZED",
        message="Missing or invalid user context.",
        details={"required_header": "x-user-id"},
    )


router = APIRouter(
    prefix="/api/v1"
)


@router.get("/user_cards", response_model=UserCardsResponse, tags=["user-cards"])
def get_user_cards(request: Request, db: Session = Depends(get_db)):
    """View user-owned active cards with reward-rules metadata."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        return _unauthorized_response()

    try:
        service = _service_from_request(db)
        return {"user_cards": service.list_user_cards(user_id)}
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.get("/wallet", response_model=WalletResponse, tags=["wallet"])
def get_wallet_alias(request: Request, db: Session = Depends(get_db)):
    """Backward-compatible alias to preserve existing wallet endpoint."""
    result = get_user_cards(request, db)
    if isinstance(result, JSONResponse):
        return result
    wallet_only = [
        {
            "card_id": card.get("card_id"),
            "refresh_day_of_month": card.get("refresh_day_of_month"),
            "annual_fee_billing_date": card.get("annual_fee_billing_date"),
            "cycle_spend_sgd": card.get("cycle_spend_sgd", 0),
        }
        for card in result["user_cards"]
    ]
    return {"wallet": wallet_only}


@router.get("/profile", response_model=ProfileResponse, tags=["profile"])
def get_profile(request: Request, db: Session = Depends(get_db)):
    """Contract endpoint: return current user profile with wallet cards."""
    try:
        user_id = _get_user_id_from_request(request) or "u_001"
        profile = _service_from_request(db).get_profile(user_id)
        return {"profile": profile}
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.post("/profile", response_model=ProfileResponse, tags=["profile"])
def save_profile(payload: ProfileRequest, request: Request, db: Session = Depends(get_db)):
    """Contract endpoint: create/update profile and wallet."""
    try:
        user_id = _get_user_id_from_request(request) or "u_001"
        profile = _service_from_request(db).save_profile(user_id, payload.profile.model_dump())
        return {"profile": profile}
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.post("/user_cards", status_code=status.HTTP_201_CREATED, response_model=WalletCardResponse, tags=["user-cards"])
def add_user_card(payload: WalletCardCreate, request: Request, db: Session = Depends(get_db)):
    """Add a user-owned card."""
    try:
        user_id = _get_user_id_from_request(request)
        if not user_id:
            return _unauthorized_response()

        service = _service_from_request(db)
        saved = service.add_user_card(user_id, payload.wallet_card.model_dump())
        
        return {"wallet_card": {
            "card_id": saved.get("card_id"),
            "refresh_day_of_month": saved.get("refresh_day_of_month"),
            "annual_fee_billing_date": saved.get("annual_fee_billing_date"),
            "cycle_spend_sgd": saved.get("cycle_spend_sgd", 0),
        }}
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        logger.exception("Unhandled exception in add_user_card")
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.post("/wallet", status_code=status.HTTP_201_CREATED, response_model=WalletCardResponse, tags=["wallet"])
def add_wallet_alias(payload: WalletCardCreate, request: Request, db: Session = Depends(get_db)):
    """Backward-compatible alias for add card endpoint."""
    return add_user_card(payload, request, db)


@router.put("/user_cards/{card_id}", response_model=WalletCardResponse, tags=["user-cards"])
def put_user_card(card_id: str, payload: UserCardPut, request: Request, db: Session = Depends(get_db)):
    """Edit user-owned card details (full replacement of editable fields)."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        return _unauthorized_response()

    try:
        service = _service_from_request(db)
        saved = service.replace_user_card(user_id, card_id, payload.user_card.model_dump())
        return {
            "wallet_card": {
                "card_id": saved.get("card_id"),
                "refresh_day_of_month": saved.get("refresh_day_of_month"),
                "annual_fee_billing_date": saved.get("annual_fee_billing_date"),
                "cycle_spend_sgd": saved.get("cycle_spend_sgd", 0),
            }
        }
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        logger.exception("Unhandled exception in put_user_card")
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.patch("/wallet/{card_id}", response_model=WalletCardResponse, tags=["wallet"])
def patch_wallet_alias(card_id: str, payload: WalletCardUpdate, request: Request, db: Session = Depends(get_db)):
    """Backward-compatible partial update endpoint."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        return _unauthorized_response()
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return _error_response(status_code=400, code="VALIDATION_ERROR", message="No fields to update.", details={})

    try:
        current_cards = _service_from_request(db).list_user_cards(user_id)
        current = next((c for c in current_cards if c.get("id") == card_id), None)
        if not current:
            return _error_response(status_code=404, code="NOT_FOUND", message=f"user_card_id '{card_id}' not found.", details={})
        merged = {
            "card_id": current.get("card_id"),
            "refresh_day_of_month": updates.get("refresh_day_of_month", current.get("refresh_day_of_month")),
            "annual_fee_billing_date": updates.get("annual_fee_billing_date", current.get("annual_fee_billing_date")),
            "cycle_spend_sgd": updates.get("cycle_spend_sgd", current.get("cycle_spend_sgd", 0)),
        }
        saved = _service_from_request(db).replace_user_card(user_id, card_id, merged)
        return {
            "wallet_card": {
                "card_id": saved.get("card_id"),
                "refresh_day_of_month": saved.get("refresh_day_of_month"),
                "annual_fee_billing_date": saved.get("annual_fee_billing_date"),
                "cycle_spend_sgd": saved.get("cycle_spend_sgd", 0),
            }
        }
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        logger.exception("Unhandled exception in patch_wallet_alias")
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.delete("/user_cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["user-cards"])
def delete_user_card(card_id: str, request: Request, db: Session = Depends(get_db)):
    """Delete (soft-delete) a user-owned card and write an audit event."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        return _unauthorized_response()

    try:
        _service_from_request(db).delete_user_card(user_id, card_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ServiceError as exc:
        return _error_response(status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details)
    except Exception:
        logger.exception("Unhandled exception in delete_user_card")
        return _error_response(status_code=500, code="INTERNAL_ERROR", message="Internal server error.", details={})


@router.delete("/wallet/{card_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["wallet"])
def delete_wallet_alias(card_id: str, request: Request, db: Session = Depends(get_db)):
    """Backward-compatible alias for delete endpoint."""
    return delete_user_card(card_id, request, db)
