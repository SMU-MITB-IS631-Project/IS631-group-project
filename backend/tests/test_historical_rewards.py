"""
Test-Driven Development (TDD) for Historical Reward Log Feature

This test file follows TDD principles:
1. Red: Write tests that fail (this file)
2. Green: Implement minimal code to make tests pass
3. Refactor: Clean up while keeping tests green

Test Coverage:
- Reward persistence in transactions table (total_reward column)
- Historical reward aggregation by month/card
- End-to-end reward calculation workflow
"""

import pytest
import sys
import os
from datetime import date, timedelta
from decimal import Decimal

# Ensure backend directory is on path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.db import Base
from app.models.transaction import UserTransaction, TransactionCategory, TransactionChannel, TransactionStatus
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import BonusCategory, CardBonusCategory
from app.models.user_profile import UserProfile
from app.services.transaction_service import TransactionService
from app.services.rewards_earned_service import RewardsEarnedService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def seed_test_data(test_db_session: Session):
    """Seed the database with test users, cards, and bonus categories"""
    # Create test user
    user = UserProfile(
        id=1,
        username="test_user",
        password_hash="hashed_password_123",  # Required field
        email="test@example.com"
    )
    test_db_session.add(user)
    
    # Create test cards in catalogue
    card1 = CardCatalogue(
        card_id=101,
        bank="DBS",
        card_name="DBS Black",
        benefit_type="cashback",
        base_benefit_rate=0.01,  # 1% base rate
        status="active"
    )
    card2 = CardCatalogue(
        card_id=102,
        bank="CITI",
        card_name="CITI Premier Miles",
        benefit_type="cashback",
        base_benefit_rate=0.015,  # 1.5% base rate
        status="active"
    )
    test_db_session.add_all([card1, card2])
    
    # Create bonus categories for cards
    bonus1 = CardBonusCategory(
        card_id=101,
        bonus_category=BonusCategory.Food,
        bonus_benefit_rate=0.02,  # 2% bonus rate for Food
        bonus_cap_in_dollar=200.00,
        bonus_minimum_spend_in_dollar=0.00
    )
    bonus2 = CardBonusCategory(
        card_id=102,
        bonus_category=BonusCategory.Transport,
        bonus_benefit_rate=0.03,  # 3% bonus rate for Transport
        bonus_cap_in_dollar=150.00,
        bonus_minimum_spend_in_dollar=0.00
    )
    test_db_session.add_all([bonus1, bonus2])
    
    # Add cards to user's wallet
    user_card1 = UserOwnedCard(
        user_id=1,
        card_id=101,
        status=UserOwnedCardStatus.Active,
        cycle_spend_sgd=0.00
    )
    user_card2 = UserOwnedCard(
        user_id=1,
        card_id=102,
        status=UserOwnedCardStatus.Active,
        cycle_spend_sgd=0.00
    )
    test_db_session.add_all([user_card1, user_card2])
    
    test_db_session.commit()
    
    return {
        "user_id": 1,
        "card_ids": [101, 102],
        "session": test_db_session
    }


# ============================================================================
# Phase 1: RED TESTS - These should FAIL initially
# ============================================================================

class TestRewardPersistence:
    """Test that rewards are calculated and stored in the transactions table"""
    
    def test_transaction_has_total_reward_column(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that UserTransaction model has total_reward column
        
        Expected to FAIL because:
        - total_reward column doesn't exist in UserTransaction model yet
        """
        # Create a simple transaction
        transaction = UserTransaction(
            user_id=seed_test_data["user_id"],
            card_id=101,
            amount_sgd=Decimal("100.00"),
            item="Test purchase",
            channel=TransactionChannel.online,
            category=TransactionCategory.Food,
            is_overseas=False,
            transaction_date=date.today(),
            status=TransactionStatus.Active
        )
        
        # This should fail because total_reward attribute doesn't exist yet
        assert hasattr(transaction, 'total_reward'), \
            "UserTransaction model should have 'total_reward' attribute"
        
        # Try to set and verify the column exists
        transaction.total_reward = Decimal("2.00")
        test_db_session.add(transaction)
        test_db_session.commit()
        test_db_session.refresh(transaction)
        
        assert transaction.total_reward == Decimal("2.00"), \
            "total_reward should be persistable in database"
    
    
    def test_transaction_creation_calculates_and_stores_reward(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that creating a transaction automatically calculates and stores the reward
        
        Expected to FAIL because:
        - TransactionService.create_transaction() doesn't calculate rewards yet
        - total_reward column doesn't exist yet
        """
        transaction_service = TransactionService(test_db_session)
        
        # Create a Food transaction (bonus category for card 101)
        # Expected reward: $100 * 2% = $2.00 (within cap)
        transaction_data = {
            "card_id": 101,
            "amount_sgd": Decimal("100.00"),
            "item": "Restaurant meal",
            "channel": TransactionChannel.online,
            "category": TransactionCategory.Food,
            "is_overseas": False,
            "transaction_date": date.today()
        }
        
        # Create transaction (this should trigger reward calculation)
        from app.models.transaction import TransactionCreate
        payload = TransactionCreate(**transaction_data)
        result = transaction_service.create_transaction("u_001", payload)
        
        # Retrieve the transaction from DB
        txn_id = int(result["id"])
        saved_txn = test_db_session.query(UserTransaction).filter(
            UserTransaction.id == txn_id
        ).first()
        
        # Assert that total_reward was calculated and stored
        assert saved_txn is not None, "Transaction should be saved in database"
        assert hasattr(saved_txn, 'total_reward'), \
            "Transaction should have total_reward attribute"
        assert saved_txn.total_reward is not None, \
            "total_reward should not be null after transaction creation"
        assert float(saved_txn.total_reward) == 2.00, \
            f"Expected reward $2.00 for $100 Food purchase at 2% rate, got ${saved_txn.total_reward}"
    
    
    def test_reward_calculation_respects_bonus_cap(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that reward calculation respects bonus category spending cap
        
        Expected to FAIL because:
        - Reward calculation logic not integrated into transaction creation yet
        """
        transaction_service = TransactionService(test_db_session)
        
        # Create multiple Food transactions that exceed the $200 cap
        # Transaction 1: $150 Food (bonus)
        from app.models.transaction import TransactionCreate
        txn1 = TransactionCreate(
            card_id=101,
            amount_sgd=Decimal("150.00"),
            item="Grocery shopping",
            channel=TransactionChannel.online,
            category=TransactionCategory.Food,
            is_overseas=False
        )
        result1 = transaction_service.create_transaction("u_001", txn1)
        
        # Transaction 2: $100 Food (should be capped)
        txn2 = TransactionCreate(
            card_id=101,
            amount_sgd=Decimal("100.00"),
            item="Restaurant dinner",
            channel=TransactionChannel.online,
            category=TransactionCategory.Food,
            is_overseas=False
        )
        result2 = transaction_service.create_transaction("u_001", txn2)
        
        # Transaction 3: $50 Transport (base rate)
        txn3 = TransactionCreate(
            card_id=101,
            amount_sgd=Decimal("50.00"),
            item="Taxi ride",
            channel=TransactionChannel.online,
            category=TransactionCategory.Transport,
            is_overseas=False
        )
        result3 = transaction_service.create_transaction("u_001", txn3)
        
        # Calculate expected rewards:
        # Food total: $250, but capped at $200
        # - First $200 at 2% bonus = $4.00
        # - Remaining $50 at 1% base = $0.50
        # Transport: $50 at 1% base = $0.50
        # Total cycle reward: $5.00
        
        # Note: This test expects individual transaction rewards, not cycle-based
        # Each transaction should store its portion of the reward
        saved_txn1 = test_db_session.query(UserTransaction).filter(
            UserTransaction.id == int(result1["id"])
        ).first()
        saved_txn2 = test_db_session.query(UserTransaction).filter(
            UserTransaction.id == int(result2["id"])
        ).first()
        saved_txn3 = test_db_session.query(UserTransaction).filter(
            UserTransaction.id == int(result3["id"])
        ).first()
        
        # Verify individual rewards are calculated
        assert saved_txn1.total_reward is not None
        assert saved_txn2.total_reward is not None
        assert saved_txn3.total_reward is not None
        
        # Sum should respect the billing cycle cap logic
        total_rewards = float(saved_txn1.total_reward + saved_txn2.total_reward + saved_txn3.total_reward)
        assert abs(total_rewards - 5.00) < 0.01, \
            f"Expected total rewards ~$5.00 (respecting $200 cap), got ${total_rewards:.2f}"


class TestHistoricalAggregation:
    """Test that historical rewards can be queried and aggregated"""
    
    def test_get_historical_rewards_method_exists(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that RewardsEarnedService has get_historical_rewards method
        
        Expected to FAIL because:
        - get_historical_rewards method doesn't exist yet
        """
        rewards_service = RewardsEarnedService(test_db_session)
        
        assert hasattr(rewards_service, 'get_historical_rewards'), \
            "RewardsEarnedService should have get_historical_rewards method"
    
    
    def test_get_historical_rewards_by_month(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that historical rewards can be aggregated by month
        
        Expected to FAIL because:
        - get_historical_rewards method doesn't exist yet
        - total_reward column doesn't exist yet
        """
        # Manually create transactions with rewards across multiple months
        transactions = [
            # January 2026 - Card 101
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=100, item="Jan food",
                channel=TransactionChannel.online, category=TransactionCategory.Food,
                is_overseas=False, transaction_date=date(2026, 1, 15),
                status=TransactionStatus.Active, total_reward=Decimal("2.00")
            ),
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=50, item="Jan transport",
                channel=TransactionChannel.offline, category=TransactionCategory.Transport,
                is_overseas=False, transaction_date=date(2026, 1, 20),
                status=TransactionStatus.Active, total_reward=Decimal("0.50")
            ),
            # February 2026 - Card 101
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=200, item="Feb food",
                channel=TransactionChannel.online, category=TransactionCategory.Food,
                is_overseas=False, transaction_date=date(2026, 2, 10),
                status=TransactionStatus.Active, total_reward=Decimal("4.00")
            ),
            # February 2026 - Card 102
            UserTransaction(
                user_id=1, card_id=102, amount_sgd=100, item="Feb transport",
                channel=TransactionChannel.online, category=TransactionCategory.Transport,
                is_overseas=False, transaction_date=date(2026, 2, 25),
                status=TransactionStatus.Active, total_reward=Decimal("3.00")
            ),
        ]
        
        test_db_session.add_all(transactions)
        test_db_session.commit()
        
        # Query historical rewards
        rewards_service = RewardsEarnedService(test_db_session)
        result = rewards_service.get_historical_rewards(
            user_id=1,
            group_by="month"
        )
        
        # Expected aggregation:
        # 2026-01: $2.50 (card 101)
        # 2026-02: $7.00 ($4.00 from card 101 + $3.00 from card 102)
        
        assert isinstance(result, list), "Result should be a list of aggregated records"
        assert len(result) >= 2, "Should have at least 2 months of data"
        
        # Find January and February records
        jan_record = next((r for r in result if r["period"] == "2026-01"), None)
        feb_record = next((r for r in result if r["period"] == "2026-02"), None)
        
        assert jan_record is not None, "Should have January 2026 record"
        assert feb_record is not None, "Should have February 2026 record"
        
        assert float(jan_record["total_reward"]) == 2.50, \
            f"Expected $2.50 for Jan 2026, got ${jan_record['total_reward']}"
        assert float(feb_record["total_reward"]) == 7.00, \
            f"Expected $7.00 for Feb 2026, got ${feb_record['total_reward']}"
    
    
    def test_get_historical_rewards_by_card(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that historical rewards can be filtered and aggregated by card
        
        Expected to FAIL because:
        - get_historical_rewards method doesn't exist yet
        """
        # Create transactions for multiple cards
        transactions = [
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=100, item="Food",
                channel=TransactionChannel.online, category=TransactionCategory.Food,
                is_overseas=False, transaction_date=date(2026, 3, 1),
                status=TransactionStatus.Active, total_reward=Decimal("2.00")
            ),
            UserTransaction(
                user_id=1, card_id=102, amount_sgd=100, item="Transport",
                channel=TransactionChannel.online, category=TransactionCategory.Transport,
                is_overseas=False, transaction_date=date(2026, 3, 1),
                status=TransactionStatus.Active, total_reward=Decimal("3.00")
            ),
        ]
        test_db_session.add_all(transactions)
        test_db_session.commit()
        
        # Query rewards for specific card only
        rewards_service = RewardsEarnedService(test_db_session)
        result = rewards_service.get_historical_rewards(
            user_id=1,
            card_id=101,  # Filter by card
            group_by="card"
        )
        
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 1, "Should have exactly 1 card record"
        assert result[0]["card_id"] == 101, "Should be filtered to card 101"
        assert float(result[0]["total_reward"]) == 2.00, \
            f"Expected $2.00 for card 101, got ${result[0]['total_reward']}"
    
    
    def test_get_historical_rewards_date_range_filter(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Verify that historical rewards can be filtered by date range
        
        Expected to FAIL because:
        - get_historical_rewards method doesn't exist yet
        """
        # Create transactions across multiple months
        transactions = [
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=100, item="Old transaction",
                channel=TransactionChannel.online, category=TransactionCategory.Food,
                is_overseas=False, transaction_date=date(2025, 12, 1),
                status=TransactionStatus.Active, total_reward=Decimal("2.00")
            ),
            UserTransaction(
                user_id=1, card_id=101, amount_sgd=100, item="Recent transaction",
                channel=TransactionChannel.online, category=TransactionCategory.Food,
                is_overseas=False, transaction_date=date(2026, 3, 1),
                status=TransactionStatus.Active, total_reward=Decimal("2.00")
            ),
        ]
        test_db_session.add_all(transactions)
        test_db_session.commit()
        
        # Query only for March 2026
        rewards_service = RewardsEarnedService(test_db_session)
        result = rewards_service.get_historical_rewards(
            user_id=1,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            group_by="month"
        )
        
        assert isinstance(result, list), "Result should be a list"
        # Should only include March 2026, not December 2025
        for record in result:
            assert record["period"] >= "2026-03", \
                f"Should only include dates from March 2026 onwards, found {record['period']}"


# ============================================================================
# Phase 3: Integration Tests (End-to-End)
# ============================================================================

class TestEndToEndRewardTracking:
    """End-to-end tests for complete reward tracking workflow"""
    
    def test_complete_workflow_create_and_query_rewards(self, test_db_session: Session, seed_test_data):
        """
        RED TEST: Complete workflow from transaction creation to historical query
        
        Expected to FAIL because:
        - Multiple components not implemented yet
        """
        transaction_service = TransactionService(test_db_session)
        rewards_service = RewardsEarnedService(test_db_session)
        
        # Step 1: Create transactions
        from app.models.transaction import TransactionCreate
        
        txn1 = TransactionCreate(
            card_id=101,
            amount_sgd=Decimal("150.00"),
            item="Monthly groceries",
            channel=TransactionChannel.online,
            category=TransactionCategory.Food,
            is_overseas=False,
            transaction_date=date(2026, 3, 5)
        )
        transaction_service.create_transaction("u_001", txn1)
        
        txn2 = TransactionCreate(
            card_id=102,
            amount_sgd=Decimal("80.00"),
            item="Taxi rides",
            channel=TransactionChannel.online,
            category=TransactionCategory.Transport,
            is_overseas=False,
            transaction_date=date(2026, 3, 10)
        )
        transaction_service.create_transaction("u_001", txn2)
        
        # Step 2: Query historical rewards
        historical_rewards = rewards_service.get_historical_rewards(
            user_id=1,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            group_by="month"
        )
        
        # Step 3: Verify results
        assert len(historical_rewards) > 0, "Should have historical reward records"
        
        march_record = next((r for r in historical_rewards if r["period"] == "2026-03"), None)
        assert march_record is not None, "Should have March 2026 reward data"
        
        # Expected: 
        # Card 101: $150 * 2% = $3.00
        # Card 102: $80 * 3% = $2.40
        # Total: $5.40
        expected_total = 5.40
        assert abs(float(march_record["total_reward"]) - expected_total) < 0.01, \
            f"Expected ~${expected_total} for March 2026, got ${march_record['total_reward']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
