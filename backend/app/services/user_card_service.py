from typing import Optional
from sqlalchemy.orm import Session
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardCreate, UserOwnedCardUpdate
from app.models.user_profile import UserProfile
from app.services.errors import ServiceError

class UserCardManagementService:
    def __init__(self, db: Session):
        self.db = db

    _OWNED_CARD_UPDATABLE_FIELDS = {
        "billing_cycle_refresh_day_of_month",
        "card_expiry_date",
        "cycle_spend_sgd",
        "status",
        "card_id",
    }

    def _require_user_by_id(self, user_id: int) -> UserProfile:
        user = self.db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            raise ServiceError(status_code=404, code="NOT_FOUND", message="User not found.", details={})
        return user

    def get_user_cards_by_user_id(self, user_id: int) -> list[UserOwnedCard]:
        self._require_user_by_id(user_id)
        return self.db.query(UserOwnedCard).filter(UserOwnedCard.user_id == user_id).all()

    def add_user_card_by_user_id(self, user_id: int, card_id: int, create_payload: dict) -> UserOwnedCard:
        self._require_user_by_id(user_id)

        existing_card = (
            self.db.query(UserOwnedCard)
            .filter(UserOwnedCard.user_id == user_id, UserOwnedCard.card_id == card_id)
            .first()
        )
        if existing_card:
            raise ServiceError(
                status_code=409,
                code="CONFLICT",
                message="Wallet card already exists.",
                details={},
            )

        new_card = UserOwnedCard(user_id=user_id, card_id=card_id, **create_payload)
        self.db.add(new_card)
        self.db.commit()
        self.db.refresh(new_card)
        return new_card

    def update_user_card_by_owned_id(self, user_id: int, owned_card_id: int, updates: dict) -> UserOwnedCard:
        self._require_user_by_id(user_id)
        card = (
            self.db.query(UserOwnedCard)
            .filter(UserOwnedCard.user_id == user_id, UserOwnedCard.id == owned_card_id)
            .first()
        )
        if not card:
            raise ServiceError(
                status_code=404,
                code="NOT_FOUND",
                message="User card not found.",
                details={},
            )

        disallowed_fields = [key for key in updates.keys() if key not in self._OWNED_CARD_UPDATABLE_FIELDS]
        if disallowed_fields:
            raise ServiceError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="Invalid update fields for wallet card.",
                details={"fields": sorted(disallowed_fields)},
            )

        new_card_id = updates.get("card_id")
        if new_card_id is not None:
            try:
                new_card_id_int = int(new_card_id)
            except (TypeError, ValueError):
                raise ServiceError(
                    status_code=400,
                    code="VALIDATION_ERROR",
                    message="Invalid card_id.",
                    details={},
                )

            if int(getattr(card, "card_id")) != new_card_id_int:
                conflict = (
                    self.db.query(UserOwnedCard)
                    .filter(
                        UserOwnedCard.user_id == user_id,
                        UserOwnedCard.card_id == new_card_id_int,
                        UserOwnedCard.id != owned_card_id,
                    )
                    .first()
                )
                if conflict:
                    raise ServiceError(
                        status_code=409,
                        code="CONFLICT",
                        message="Wallet card already exists.",
                        details={},
                    )

                updates["card_id"] = new_card_id_int

        for key, value in updates.items():
            if hasattr(card, key):
                setattr(card, key, value)

        self.db.commit()
        self.db.refresh(card)
        return card

    def remove_user_card_by_owned_id(self, user_id: int, owned_card_id: int) -> None:
        self._require_user_by_id(user_id)
        card = (
            self.db.query(UserOwnedCard)
            .filter(UserOwnedCard.user_id == user_id, UserOwnedCard.id == owned_card_id)
            .first()
        )
        if not card:
            raise ServiceError(
                status_code=404,
                code="NOT_FOUND",
                message="User card not found.",
                details={},
            )
        self.db.delete(card)
        self.db.commit()

    def get_user_id_by_cognito_sub(self, cognitosub: str) -> Optional[int]:
        """Helper method to get user_id from Cognito sub."""
        result = self.db.query(UserProfile.id).filter(UserProfile.cognito_sub == cognitosub).first()
        return result[0] if result else None

    def _require_user_id(self, cognitosub: str) -> int:
        user_id = self.get_user_id_by_cognito_sub(cognitosub)
        if user_id is None:
            raise ServiceError(status_code=404, code="NOT_FOUND", message="User not found.", details={})
        return user_id

    def get_user_cards(self, cognitosub: str) -> list[UserOwnedCard]:
        """Return all cards owned by a user as a list of UserOwnedCard instances."""
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
            raise ServiceError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="User already owns this card.",
                details={},
            )

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
            raise ServiceError(
                status_code=404,
                code="NOT_FOUND",
                message="User does not own this card.",
                details={},
            )

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
            raise ServiceError(
                status_code=404,
                code="NOT_FOUND",
                message="User does not own this card.",
                details={},
            )

        for key, value in card_data.model_dump(exclude_unset=True, exclude_none=True).items():
            if hasattr(card, key):
                setattr(card, key, value)

        self.db.commit()
        self.db.refresh(card)
        return card