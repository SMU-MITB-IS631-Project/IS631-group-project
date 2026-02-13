from fastapi import Depends
from app.services.catalog_service import CatalogService
from app.services.data_service import DataService
from app.dependencies.db import get_db
from sqlalchemy.orm import Session

def get_catalog_service(db: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(db)

def get_data_service(db: Session = Depends(get_db)) -> DataService:
    return DataService(db)

