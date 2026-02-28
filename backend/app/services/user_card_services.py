"""Legacy wrapper preserved for backward compatibility.

This module now delegates to the centralized `UserService` and `CardService`
to avoid duplicating business logic. Prefer importing from
`app.services.user_service` and `app.services.card_service` directly.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.card_service import CardService
from app.services.errors import ServiceError
from app.services.user_service import UserService


class UserCardManagementService:
    """Thin compatibility layer around the new service modules."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_service = UserService(db)
        self.card_service = CardService(db, self.user_service)

    # Card operations -----------------------------------------------------
    def list_user_cards(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        return self.card_service.list_user_cards(user_id)

    def add_user_card(self, user_id: Optional[str], card_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.card_service.add_user_card(user_id, card_data)

    def replace_user_card(self, user_id: Optional[str], user_card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.card_service.replace_user_card(user_id, user_card_id, card_data)

    def delete_user_card(self, user_id: Optional[str], user_card_id: str) -> None:
        return self.card_service.delete_user_card(user_id, user_card_id)

    # Profile operations --------------------------------------------------
    def get_profile(self, user_id: Optional[str]) -> Dict[str, Any]:
        return self.user_service.get_profile(user_id, self.card_service)

    def save_profile(self, user_id: Optional[str], profile: Dict[str, Any]) -> Dict[str, Any]:
        return self.user_service.save_profile(user_id, profile, self.card_service)
