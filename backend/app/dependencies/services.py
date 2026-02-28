from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.models.user_profile import UserProfile
from app.services.card_service import CardService
from app.services.catalog_service import CatalogService
from app.services.transaction_service import TransactionService
from app.services.user_card_services import UserCardManagementService
from app.services.user_service import UserService

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_user_profile_service(db: Session = Depends(get_db)) -> UserProfile:
    # Creates and returns a UserProfile service instance using the injected database session.
    return UserProfile(db)

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)

def get_card_service(db: Session = Depends(get_db)) -> CardService:
    user_service = UserService(db)
    return CardService(db, user_service)

def get_user_card_management_service(db: Session = Depends(get_db)) -> UserCardManagementService:
    # Creates and returns a UserCardManagementService instance using the injected database session.
    return UserCardManagementService(db)

def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    # Creates and returns a TransactionService instance using the injected database session.
    return TransactionService(db)
