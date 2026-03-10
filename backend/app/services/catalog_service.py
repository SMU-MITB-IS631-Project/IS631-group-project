from sqlalchemy.orm import Session
from app.models.card_catalogue import CardCatalogue

class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def get_catalog(self):
        """Retrieve all cards from the database."""
        return self.db.query(CardCatalogue).all()