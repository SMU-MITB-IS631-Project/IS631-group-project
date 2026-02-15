from fastapi import APIRouter, HTTPException, Depends, status

from app.models.card_catalogue import CardCatalogue, CardCatalogueResponse
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardResponse
from app.services.catalog_service import CatalogService
from app.dependencies.services import get_catalog_service

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"]
)

@router.get("/catalog", response_model=list[CardCatalogueResponse])
def get_catalog(service: CatalogService = Depends(get_catalog_service)):
    return service.get_catalog()

# TODO: Implement endpoint for adding user-owned cards when requirements are defined.