import pytest
import sys
import os
# ensure backend directory is on path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock

# ServiceException is not part of installed modules; define placeholder for tests
class ServiceException(Exception):
    pass
from app.services.rewards_earned_service import RewardsEarnedService
from app.models.transaction import UserTransaction, TransactionCategory, TransactionChannel
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import BonusCategory, CardBonusCategory

# Define MockQuery at module level so all tests can use it
class MockQuery:
    def __init__(self, result):
        self.result = result
    
    def filter(self, *args, **kwargs):
        return self
    
    def first(self):
        return self.result[0] if self.result else None
    
    def all(self):
        return self.result

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
    # Create proper mock query objects for each model type
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.Active, billing_cycle_refresh_day_of_month=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    bonus_category = CardBonusCategory(card_id=1, bonus_category=BonusCategory.Food, bonus_benefit_rate=0.2, bonus_cap_in_dollar=100)
    transaction = UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=100, item="test", channel=TransactionChannel.online, is_overseas=False, category=TransactionCategory.food, transaction_date="2024-06-01")
    
    # Build a side_effect list that returns appropriate objects based on query order
    query_results = [
        [active_card],        # 1st call: query(UserOwnedCard).filter().all()
        [card_catalogue],     # 2nd call: query(CardCatalogue).filter().first()
        [bonus_category],     # 3rd call: query(CardBonusCategory).filter().all()
        [transaction]         # 4th call: query(UserTransaction).filter().all()
    ]
    
    # Set up mock_db.query() to return appropriate MockQuery objects
    mock_db.query.side_effect = [MockQuery(result) for result in query_results]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    # Expected: base_amt=0 (all txn matched bonus) + bonus_amt=100 (0.20 rate) = 20.0
    expected_rewards = {
        "Test Card": 20.0
    }
    
    assert result == expected_rewards

def test_calculate_rewards_earned_with_no_transactions(rewards_earned_service, mock_db):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.Active, billing_cycle_refresh_day_of_month=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    
    mock_db.query.side_effect = [
        MockQuery([active_card]),  # Active cards query
        MockQuery([card_catalogue]),  # Card catalogue query
        MockQuery([]),  # Bonus categories query (no bonus categories)
        MockQuery([])   # Transactions query (no transactions)
    ]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    expected_rewards = {
        "Test Card": 0.0  # No transactions means no rewards
    }
    
    assert result == expected_rewards

def test_calculate_rewards_earned_with_bonus_cap_exceeded(rewards_earned_service, mock_db):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.Active, billing_cycle_refresh_day_of_month=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    bonus_category = CardBonusCategory(card_id=1, bonus_category=BonusCategory.Food, bonus_benefit_rate=0.2, bonus_cap_in_dollar=100)
    transaction = UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=600, item="test", channel=TransactionChannel.online, is_overseas=False, category=TransactionCategory.food, transaction_date="2024-06-01")
    
    mock_db.query.side_effect = [
        MockQuery([active_card]),  # Active cards query
        MockQuery([card_catalogue]),  # Card catalogue query
        MockQuery([bonus_category]),  # Bonus categories query
        MockQuery([transaction])   # Transactions query
    ]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    expected_rewards = {
        "Test Card": 25.0  # Bonus cap of $100 applies (0.20 rate on $600 would be $120 but capped at $100)
    }
    
    assert result == expected_rewards

def test_calculate_rewards_earned_with_no_bonus_categories(rewards_earned_service, mock_db):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.Active, billing_cycle_refresh_day_of_month=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    transaction = UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=100, item="test", channel=TransactionChannel.online, is_overseas=False, category=TransactionCategory.food, transaction_date="2024-06-01")
    
    mock_db.query.side_effect = [
        MockQuery([active_card]),  # Active cards query
        MockQuery([card_catalogue]),  # Card catalogue query
        MockQuery([]),  # Bonus categories query (no bonus categories)
        MockQuery([transaction])   # Transactions query
    ]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    expected_rewards = {
        "Test Card": 1.0  # All transactions earn base rate rewards (0.01 * $100)
    }
    
    assert result == expected_rewards