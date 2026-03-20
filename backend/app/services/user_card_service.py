from typing import Optional, Dict, cast
from sqlalchemy.orm import Session
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardCreate, UserOwnedCardUpdate
from app.models.user_profile import UserProfile
from app.exceptions import ServiceException

class UserCardManagementService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_id_by_cognito_sub(self, cognitosub: str) -> Optional[int]:
        """Helper method to get user_id from Cognito sub."""
        result = self.db.query(UserProfile.id).filter(UserProfile.cognito_sub == cognitosub).first()
        return result[0] if result else None

    def _require_user_id(self, cognitosub: str) -> int:
        user_id = self.get_user_id_by_cognito_sub(cognitosub)
        if user_id is None:
            raise ServiceException(status_code=404, detail="User not found.")
        return user_id

    def get_user_cards(self, cognitosub: str):
        """Return all cards owned by a user as a dictionary keyed by card_id."""
        user_id = self._require_user_id(cognitosub)
        return self.db.query(UserOwnedCard).filter(UserOwnedCard.user_id == user_id).all()

    def add_user_card(self, cognitosub: str, card_id: int, card_data: UserOwnedCardCreate) -> UserOwnedCard:
        """Add a card to a user's collection."""
        user_id = self._require_user_id(cognitosub)
        existing_card = self.db.query(UserOwnedCard).filter(
            UserOwnedCard.user_id == user_id,
            UserOwnedCard.card_id == card_id
        ).first()
        if existing_card:
            raise ServiceException(status_code=400, detail="User already owns this card.")

        create_payload = card_data.model_dump(
            exclude_unset=True,
            exclude_none=True,
            exclude={"card_id"},
        )

        new_card = UserOwnedCard(
            **create_payload,
            user_id=user_id,
            card_id=card_id,
        )
        self.db.add(new_card)
        self.db.commit()
        self.db.refresh(new_card)
        return new_card

    def remove_user_card(self, cognitosub: str, card_id: int) -> None:
        """Remove a card from a user's collection."""
        user_id = self._require_user_id(cognitosub)
        card = self.db.query(UserOwnedCard).filter(
            UserOwnedCard.user_id == user_id,
            UserOwnedCard.card_id == card_id
        ).first()
        if not card:
            raise ServiceException(status_code=404, detail="User does not own this card.")

        self.db.delete(card)
        self.db.commit()

    def update_user_card(self, cognitosub: str, card_id: int, card_data: UserOwnedCardUpdate) -> UserOwnedCard:
        """Update details of a user's card."""
        user_id = self._require_user_id(cognitosub)
        card = self.db.query(UserOwnedCard).filter(
            UserOwnedCard.user_id == user_id,
            UserOwnedCard.card_id == card_id
        ).first()
        if not card:
            raise ServiceException(status_code=404, detail="User does not own this card.")

        for key, value in card_data.model_dump(exclude_unset=True, exclude_none=True).items():
            if hasattr(card, key):
                setattr(card, key, value)

        self.db.commit()
        self.db.refresh(card)
        return card