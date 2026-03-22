from fastapi import APIRouter, Depends

from app.models.card_catalogue import CardCatalogueResponse, CardRewardUpdateRequest
from app.services.catalog_service import CatalogService
from app.services.errors import ServiceError
from app.dependencies.services import get_catalog_service

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"]
)

@router.get("/", response_model=list[CardCatalogueResponse])
def get_catalog(service: CatalogService = Depends(get_catalog_service)):
    return service.get_catalog()


@router.put("/{card_id}/rewards")
def update_card_rewards(
    card_id: int,
    request: CardRewardUpdateRequest,
    service: CatalogService = Depends(get_catalog_service),
):
    try:
        return {
            "update_result": service.update_card_rewards(card_id, request.reward_update)
        }
    except ServiceError as exc:
        raise exc
