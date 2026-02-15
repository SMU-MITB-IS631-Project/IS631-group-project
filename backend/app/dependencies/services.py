from fastapi import Depends
from app.services.catalog_service import CatalogService
from app.services.user_card_services import UserCardManagementService
from app.dependencies.db import get_db
from sqlalchemy.orm import Session

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_user_card_management_service(db: Session = Depends(get_db)) -> UserCardManagementService:
    return UserCardManagementService(db)