from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.services.user_profile_service import UserProfileService
from app.services.catalog_service import CatalogService
from app.services.transaction_service import TransactionService
from app.services.user_card_service import UserCardManagementService
from app.services.rewards_earned_service import RewardsEarnedService

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_rewards_earned_service(db: Session = Depends(get_db)) -> RewardsEarnedService:
    return RewardsEarnedService(db)

def get_user_profile_service(db: Session = Depends(get_db)) -> UserProfileService:
    # Creates and returns a UserProfile service instance using the injected database session.
    return UserProfileService(db)

def get_user_card_management_service(db: Session = Depends(get_db)) -> UserCardManagementService:
    # Creates and returns a UserCardManagementService instance using the injected database session.
    return UserCardManagementService(db)

def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    # Creates and returns a TransactionService instance using the injected database session.
    return TransactionService(db)
