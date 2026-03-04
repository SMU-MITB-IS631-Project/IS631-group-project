"""Consolidated card management service with header-based authentication.

This service provides the primary interface for card and profile operations,
functioning as a unified wrapper around UserService and CardService.

Features:
- Header-based user identification via x-user-id extraction
- Service-level validation enforcing 401 errors for missing headers
- Single source of truth for card operations (database-backed)
- Unified profile and wallet management

Route handlers should:
1. Use get_required_user_id() as a FastAPI dependency to extract header
2. Pass the validated user_id to methods in this service
3. Handle ServiceError exceptions appropriately

Examples:
    from app.services.user_card_services import get_required_user_id
    
    @router.get("/cards")
    def get_cards(
        user_id: str = Depends(get_required_user_id),
        db: Session = Depends(get_db)
    ):
        service = UserCardManagementService(db)
        return service.list_user_cards(user_id)
"""

from typing import Any, Dict, List, Optional

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.services.card_service import CardService
from app.services.errors import ServiceError
from app.services.user_service import UserService


# ------------------------------------------------------------------
# Header-Based Authentication Dependency
# ------------------------------------------------------------------
async def get_required_user_id(
    x_user_id: Optional[str] = Header(None)
) -> str:
    """
    FastAPI dependency to extract and validate x-user-id header.
    
    Returns the stripped user ID if present, raises 401 Unauthorized if missing.
    Per team decision (March 4, 2026), user identification is handled
    via x-user-id header during session.
    
    Raises:
        HTTPException(401): If header is missing, empty, or invalid.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing or invalid user context.",
                    "details": {"required_header": "x-user-id"},
                }
            },
        )
    return x_user_id.strip()


class UserCardManagementService:
    """Consolidated interface for user card and profile operations.
    
    This service:
    - Acts as single source of truth for card operations (eliminating redundancy with wallet_service.py)
    - Delegates complex logic to specialized services (UserService, CardService)
    - Enforces header-based user identification validation
    - Points all operations to the database (not JSON files)
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_service = UserService(db)
        self.card_service = CardService(db, self.user_service)

    # Helpers -----------------------------------------------------------------
    def _validate_user_context(self, user_id: Optional[str]) -> str:
        """
        Validate that user_id is present (from x-user-id header).
        
        Raises:
            ServiceError(401): If user_id is None or empty.
        """
        if not user_id:
            raise ServiceError(
                401, 
                "UNAUTHORIZED", 
                "Missing or invalid user context.",
                {"required_header": "x-user-id"}
            )
        return user_id.strip()

    # Card operations ---------------------------------------------------------
    def list_user_cards(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        """
        List all active cards in user's wallet.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            
        Returns:
            List of card objects with reward metadata.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(404): If user profile not found.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.card_service.list_user_cards(validated_user_id)

    def add_user_card(self, user_id: Optional[str], card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new card to user's wallet.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            card_data: Card details including card_id, refresh_day_of_month, annual_fee_billing_date.
            
        Returns:
            Created card object with database ID and metadata.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(400): If card_data validation fails.
            ServiceError(409): If card already exists in wallet.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.card_service.add_user_card(validated_user_id, card_data)

    def replace_user_card(self, user_id: Optional[str], user_card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace (update) a user's card details.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            user_card_id: Database ID of the UserOwnedCard to update.
            card_data: Updated card details.
            
        Returns:
            Updated card object.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(403): If card doesn't belong to current user.
            ServiceError(404): If card/user not found.
            ServiceError(400): If card_data validation fails.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.card_service.replace_user_card(validated_user_id, user_card_id, card_data)

    def delete_user_card(self, user_id: Optional[str], user_card_id: str) -> None:
        """
        Delete a card from user's wallet.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            user_card_id: Database ID of the UserOwnedCard to delete.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(403): If card doesn't belong to current user.
            ServiceError(404): If card not found.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.card_service.delete_user_card(validated_user_id, user_card_id)

    # Profile operations ------------------------------------------------------
    def get_profile(self, user_id: Optional[str]) -> Dict[str, Any]:
        """
        Get user's complete profile including wallet.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            
        Returns:
            Profile object with user_id, username, preference, and wallet.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(404): If user profile not found.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.user_service.get_profile(validated_user_id, self.card_service)

    def save_profile(self, user_id: Optional[str], profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user's profile and/or wallet.
        
        Args:
            user_id: User identifier from x-user-id header (required).
            profile: Profile object with username, preference, and wallet.
            
        Returns:
            Updated profile object.
            
        Raises:
            ServiceError(401): If header is missing/invalid.
            ServiceError(400): If profile validation fails.
            ServiceError(404): If user not found.
        """
        validated_user_id = self._validate_user_context(user_id)
        return self.user_service.save_profile(validated_user_id, profile, self.card_service)
