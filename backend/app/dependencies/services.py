from fastapi import Depends
from app.services.catalog_service import CatalogService
from app.services.user_card_services import UserCardManagementService
from app.models.user_profile import UserProfile
from app.dependencies.db import get_db
from sqlalchemy.orm import Session

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_user_profile_service(db: Session = Depends(get_db)) -> UserProfile:
    # Creates and returns a UserProfile service instance using the injected database session.
    return UserProfile(db)