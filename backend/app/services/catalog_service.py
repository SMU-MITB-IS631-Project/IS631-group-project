from sqlalchemy.exc import IntegrityError
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