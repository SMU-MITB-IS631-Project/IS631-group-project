from fastapi import APIRouter, Depends, HTTPException, status

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
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {},
                }
            },
        )
