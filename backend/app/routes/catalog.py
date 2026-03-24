from fastapi import APIRouter, Depends, HTTPException, status

from app.models.card_catalogue import CardCatalogueCreate, CardCatalogueResponse, CardRewardUpdateRequest
from app.services.catalog_service import CatalogService
from app.services.errors import ServiceError
from app.dependencies.services import get_catalog_service
from app.dependencies.auth import required_admin_role, required_authenticated

router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"]
)

@router.get("/", response_model=list[CardCatalogueResponse])
def get_catalog(service: CatalogService = Depends(get_catalog_service)):
    return service.get_catalog()

@router.post("/", response_model=CardCatalogueResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(required_admin_role)])
def create_card(card: CardCatalogueCreate, service: CatalogService = Depends(get_catalog_service)):
    return service.create_card(card)

@router.put("/{card_id}/rewards", dependencies=[Depends(required_admin_role)])
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

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(required_admin_role)])
def delete_card(card_id: int, service: CatalogService = Depends(get_catalog_service)):
    success = service.delete_card(card_id)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"message": "Card deleted successfully"}