from sqlalchemy.orm import Session
from app.models.cards import Card
from app.models.user_owned_cards import UserOwnedCard

class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def get_catalog(self):
        """Retrieve all cards from the database."""
        return self.db.query(Card).all()
    
    def add_card(self, card_id: int):
        """Add a new user owned card.

        To be refined again.
        """
        new_user_owned_card = UserOwnedCard(card_id=card_id)
        self.db.add(new_user_owned_card)
        self.db.commit()
        self.db.refresh(new_user_owned_card)
        return new_user_owned_card