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

"""
@router.post("/", response_model=UserOwnedCardResponse, status_code=status.HTTP_201_CREATED)
def add_user_owned_card(card: CardCatalogue, service: CatalogService = Depends(get_catalog_service)):
    return service.add_user_owned_card(card.id)
"""