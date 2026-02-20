from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.card_catalogue import CardCatalogue, CardCatalogueResponse
from app.models.user_owned_cards import UserOwnedCardResponse
from app.services.catalog_service import CatalogService
from app.dependencies.services import get_catalog_service

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"]
)

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

@router.get("/", response_model=list[CardCatalogueResponse])
def get_catalog(service: CatalogService = Depends(get_catalog_service)):
    return service.get_catalog()

@router.post("/{card_id}/add", response_model=UserOwnedCardResponse, status_code=status.HTTP_201_CREATED)
def add_user_owned_card(
    card_id: int,
    user_id: int,
    card_expiry_date: datetime | None = None,
    billing_cycle_refresh_date: datetime | None = None,
    service: CatalogService = Depends(get_catalog_service),
):
    if not user_id:
        return _unauthorized_response()
    
    try:
        return service.add_user_owned_card(
            user_id=user_id,
            card_id=card_id,
            card_expiry_date=card_expiry_date,
            billing_cycle_refresh_date=billing_cycle_refresh_date
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc),
                    "details": {"user_id": user_id, "card_id": card_id},
                }
            },
        )