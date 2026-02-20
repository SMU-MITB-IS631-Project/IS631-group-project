from fastapi import APIRouter, Depends, HTTPException, status

from app.models.card_catalogue import CardCatalogue, CardCatalogueResponse
from app.services.catalog_service import CatalogService
from app.dependencies.services import get_catalog_service

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"]
)

@router.get("/", response_model=list[CardCatalogueResponse])
def get_catalog(service: CatalogService = Depends(get_catalog_service)):
    return service.get_catalog()

@router.post("/{card_id}/add", response_model=CardCatalogueResponse, status_code=status.HTTP_201_CREATED)
def add_user_owned_card(card_id: int, user_id: int, card_expiry_date: str = None, service: CatalogService = Depends(get_catalog_service)):
    return service.add_user_owned_card(user_id=user_id, card_id=card_id, card_expiry_date=card_expiry_date)