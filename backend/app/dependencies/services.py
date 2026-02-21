from fastapi import Depends
from app.services.catalog_service import CatalogService
from app.models.user_profile import UserProfile
from app.services.user_card_services import UserCardManagementService
from app.services.transaction_service import TransactionService
from app.dependencies.db import get_db
from sqlalchemy.orm import Session

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_user_profile_service(db: Session = Depends(get_db)) -> UserProfile:
    # Creates and returns a UserProfile service instance using the injected database session.
    return UserProfile(db)

def get_user_card_management_service(db: Session = Depends(get_db)) -> UserCardManagementService:
    # Creates and returns a UserCardManagementService instance using the injected database session.
    return UserCardManagementService(db)

def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    # Creates and returns a TransactionService instance using the injected database session.
    return TransactionService(db)
