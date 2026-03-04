import pytest
import sys, os
# ensure backend directory is on path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock
from fastapi import HTTPException

# ServiceException is not part of installed modules; define placeholder for tests
class ServiceException(Exception):
    pass
from app.services.rewards_earned_service import RewardsEarnedService
from app.models.transaction import UserTransaction
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import BonusCategory, CardBonusCategory

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def rewards_earned_service(mock_db):
    return RewardsEarnedService(db_session=mock_db)

def test_calculate_rewards_earned_no_active_cards(rewards_earned_service, mock_db):
    # Mock the database query to return no active cards
    mock_db.query().filter().all.return_value = []
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    assert result == {}  # Expecting an empty dictionary when there are no active cards

def test_calculate_rewards_earned_with_active_cards(rewards_earned_service, mock_db):
    # Mock the database query to return one active card
    mock_db.query().filter().all.side_effect = [
        [UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1)],  # Active cards
        [CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")],  # Card details
        [CardBonusCategory(card_id=1, bonus_category="food", bonus_benefit_rate=0.02, bonus_cap_in_dollar=100)],  # Bonus categories
        [UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=100, item="test", channel="online", is_overseas=False, category="food", transaction_date="2024-06-01")]  # Transactions
    ]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    expected_rewards = {
        1: 3.0  # Base rewards (100 * 0.01) + Bonus rewards (100 * 0.02) = 3.0
    }
    
    assert result == expected_rewards