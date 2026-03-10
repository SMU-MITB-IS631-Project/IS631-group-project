from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

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
