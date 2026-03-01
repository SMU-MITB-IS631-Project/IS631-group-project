import pytest
from unittest.mock import Mock
from fastapi import HTTPException
#from app.exceptions import ServiceException
from app.services.catalog_service import CatalogService
from app.models.card_catalogue import CardCatalogue

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def catalog_service(mock_db):
    return CatalogService(db=mock_db)

def test_get_all_card_catalogue_success(catalog_service, mock_db):
    # Arrange
    mock_db.query.return_value.all.return_value = [
        CardCatalogue(card_id=1, bank="DBS", card_name="DBS Altitude",benefit_type="miles", base_benefit_rate="1.5", status="valid"),
        CardCatalogue(card_id=2, bank="CITI", card_name="CITI PremierMiles", benefit_type="miles", base_benefit_rate="1.2", status="valid"),
        CardCatalogue(card_id=3, bank="UOB", card_name="UOB ONE Miles", benefit_type="cashback", base_benefit_rate="0.005", status="valid")
    ]

    # Act
    result = catalog_service.get_catalog()

    # Assert
    assert len(result) == 3
    assert result[0].card_name == "DBS Altitude"
    assert result[1].bank == "CITI"
    assert result[2].benefit_type == "cashback"
    # Ensure the correct calls were made
    mock_db.query.assert_called_once_with(CardCatalogue)
    mock_db.query.return_value.all.assert_called_once()