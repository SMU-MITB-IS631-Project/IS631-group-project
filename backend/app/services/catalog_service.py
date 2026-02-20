from sqlite3 import IntegrityError
from sqlalchemy.orm import Session
from app.models.card_catalogue import CardCatalogue
from app.models.user_profile import UserProfile
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus

class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def get_catalog(self):
        """Retrieve all cards from the database."""
        return self.db.query(CardCatalogue).all()
    
    def add_user_owned_card(self, user_id: int, card_id: int, card_expiry_date=None):
        """Add a card to a user's owned cards."""
        # Check if the user exists
        user = self.db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} does not exist.")
        # Check if the card exists in the catalog
        card = self.db.query(CardCatalogue).filter(CardCatalogue.card_id == card_id).first()
        if not card:
            raise ValueError(f"Card with id {card_id} does not exist in the catalog.")
        # Create a new UserOwnedCard entry
        user_owned_card = UserOwnedCard(
            user_id=user_id,
            card_id=card_id,
            status=UserOwnedCardStatus.Active,
            card_expiry_date=card_expiry_date if card_expiry_date else None
        )
        try:
            self.db.add(user_owned_card)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise

        self.db.refresh(user_owned_card)
        return user_owned_card