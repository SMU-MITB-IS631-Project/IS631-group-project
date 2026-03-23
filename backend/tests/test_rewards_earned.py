import pytest
import sys, os
import builtins
import importlib.util
from pathlib import Path
# ensure backend directory is on path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock
from fastapi import HTTPException

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
def mockdb():
    return Mock()

@pytest.fixture
def rewards_earned_service(mockdb):
    return RewardsEarnedService(db_session=mockdb)

def test_calculate_rewards_earned_no_active_cards(rewards_earned_service, mockdb):
    # Mock the database query to return no active cards
    mockdb.query().filter().all.return_value = []
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    assert result == {}  # Expecting an empty dictionary when there are no active cards

def test_calculate_rewards_earned_with_active_cards(rewards_earned_service, mockdb):
    # Create proper mock query objects for each model type
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1)
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
    
    # Set up mockdb.query() to return appropriate MockQuery objects
    mockdb.query.side_effect = [MockQuery(result) for result in query_results]
    
    result = rewards_earned_service.calculate_rewards_earned(user_id=1)
    
    # Expected: base_amt=0 (all txn matched bonus) + bonus_amt=100 (0.20 rate) = 20.0
    expected_rewards = {
        "Test Card": 20.0
    }
    
    assert result == expected_rewards

def test_calculate_rewards_earned_with_no_transactions(rewards_earned_service, mockdb):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    
    mockdb.query.side_effect = [
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

def test_calculate_rewards_earned_with_bonus_cap_exceeded(rewards_earned_service, mockdb):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    bonus_category = CardBonusCategory(card_id=1, bonus_category=BonusCategory.Food, bonus_benefit_rate=0.2, bonus_cap_in_dollar=100)
    transaction = UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=600, item="test", channel=TransactionChannel.online, is_overseas=False, category=TransactionCategory.food, transaction_date="2024-06-01")
    
    mockdb.query.side_effect = [
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

def test_calculate_rewards_earned_with_no_bonus_categories(rewards_earned_service, mockdb):
    active_card = UserOwnedCard(id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1)
    card_catalogue = CardCatalogue(card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active")
    transaction = UserTransaction(id=1, user_id=1, card_id=1, amount_sgd=100, item="test", channel=TransactionChannel.online, is_overseas=False, category=TransactionCategory.food, transaction_date="2024-06-01")
    
    mockdb.query.side_effect = [
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


def test_module_import_uses_fallback_service_exception_when_app_exceptions_missing(monkeypatch):
    service_path = Path(__file__).resolve().parents[1] / "app/services/rewards_earned_service.py"
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app.exceptions":
            raise ImportError("forced import error for test")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    spec = importlib.util.spec_from_file_location("temp_rewards_service_importerror", str(service_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # If fallback path ran, ServiceException is defined inside the loaded module.
    assert module.ServiceException.__module__ == module.__name__


def test_calculate_rewards_earned_skips_when_card_not_found(rewards_earned_service, mockdb):
    missing_card_ref = UserOwnedCard(
        id=1, user_id=1, card_id=999, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1
    )
    valid_card_ref = UserOwnedCard(
        id=2, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1
    )
    valid_card = CardCatalogue(
        card_id=1, bank="Test Bank", card_name="Valid Card", benefit_type="cashback", base_benefit_rate=0.01, status="active"
    )
    txn = UserTransaction(
        id=1,
        user_id=1,
        card_id=1,
        amount_sgd=100,
        item="test",
        channel=TransactionChannel.online,
        is_overseas=False,
        category=TransactionCategory.food,
        transaction_date="2024-06-01",
    )

    mockdb.query.side_effect = [
        MockQuery([missing_card_ref, valid_card_ref]),  # active cards
        MockQuery([]),  # missing card lookup -> first() returns None
        MockQuery([valid_card]),  # valid card lookup
        MockQuery([]),  # no bonus categories
        MockQuery([txn]),  # valid card transactions
    ]

    result = rewards_earned_service.calculate_rewards_earned(user_id=1)

    assert result == {"Valid Card": 1.0}


def test_calculate_rewards_earned_uses_previous_month_when_refresh_day_not_reached(rewards_earned_service, mockdb, monkeypatch):
    import app.services.rewards_earned_service as rewards_module
    from datetime import date as real_date

    class FakeDate:
        @classmethod
        def today(cls):
            return real_date(2026, 3, 5)

    active_card = UserOwnedCard(
        id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=20
    )
    card_catalogue = CardCatalogue(
        card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active"
    )
    txn = UserTransaction(
        id=1,
        user_id=1,
        card_id=1,
        amount_sgd=100,
        item="test",
        channel=TransactionChannel.online,
        is_overseas=False,
        category=TransactionCategory.transport,
        transaction_date="2026-02-25",
    )

    monkeypatch.setattr(rewards_module, "date", FakeDate)

    mockdb.query.side_effect = [
        MockQuery([active_card]),
        MockQuery([card_catalogue]),
        MockQuery([]),
        MockQuery([txn]),
    ]

    result = rewards_earned_service.calculate_rewards_earned(user_id=1)

    assert result == {"Test Card": 1.0}


def test_calculate_rewards_earned_wraps_unexpected_errors(rewards_earned_service, mockdb):
    import app.services.rewards_earned_service as rewards_module

    class DummyServiceException(Exception):
        pass

    rewards_module.ServiceException = DummyServiceException

    active_card = UserOwnedCard(
        id=1, user_id=1, card_id=1, status=UserOwnedCardStatus.active, billing_cycle_refresh_day_of_mth=1
    )
    card_catalogue = CardCatalogue(
        card_id=1, bank="Test Bank", card_name="Test Card", benefit_type="cashback", base_benefit_rate=0.01, status="active"
    )
    bad_txn = UserTransaction(
        id=1,
        user_id=1,
        card_id=1,
        amount_sgd=100,
        item="test",
        channel=TransactionChannel.online,
        is_overseas=False,
        category=TransactionCategory.food,
        transaction_date="2024-06-01",
    )
    bad_txn.category = None  # Triggers AttributeError when service accesses txn.category.value

    mockdb.query.side_effect = [
        MockQuery([active_card]),
        MockQuery([card_catalogue]),
        MockQuery([]),
        MockQuery([bad_txn]),
    ]

    with pytest.raises(DummyServiceException, match="Error calculating rewards earned"):
        rewards_earned_service.calculate_rewards_earned(user_id=1)