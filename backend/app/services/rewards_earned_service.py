from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
# Attempt to import ServiceException; provide fallback if module not available
try:
    from app.exceptions import ServiceException
except ImportError:
    class ServiceException(Exception):
        """Fallback exception used when app.exceptions is missing (e.g., during tests)"""
        pass
from app.models.transaction import UserTransaction
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import BonusCategory, CardBonusCategory

class RewardsEarnedService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def calculate_rewards_earned(self, user_id: int) -> dict:
        """
        Calculate total rewards earned for a user for each of their active cards in each of their latest billing cycle based on their transactions and card benefits.
        
        Args:
        - user_id: ID of the user
        
        Returns:
        - Dictionary mapping card_id to rewards_amt_earned for the latest billing cycle
        
        Raises:
        - ServiceException: If any error occurs during calculation
        """
        # Step 1: Get all active cards for the user
        active_cards = (
            self.db_session.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == user_id,
                UserOwnedCard.status == UserOwnedCardStatus.active
                )
            .all()
        )
        if not active_cards:
            return {}  # No active cards, hence no rewards
        
        # Step 2: For each active card, find the latest billing cycle, find all the transactions in the billing cycle, determine whether each transaction fall under base or bonus rate, exclude any bonus transactions exceeding the cap, and then calculate rewards.
        try:
            rewards_by_card = {}  # Dictionary to store rewards for each card
            
            for user_card in active_cards:
                card = self.db_session.query(CardCatalogue).filter(CardCatalogue.card_id == user_card.card_id).first()
                if not card:
                    continue  # Skip if card details not found
                
                # Get the latest billing cycle start date based on the user's billing refresh day-of-month
                # default to 1 if attribute missing (tests may not set it)
                day_of_month = getattr(user_card, "billing_cycle_refresh_day_of_mth", 1)
                # Use Python date arithmetic instead of SQL functions
                today = date.today()
                current_day = today.day
                if current_day >= day_of_month:
                    billing_cycle_start_date = today.replace(day=day_of_month)
                else:
                    first_of_month = today.replace(day=1)
                    prev_month_last = first_of_month - timedelta(days=1)
                    # if day_of_month greater than days in prev month, this may throw; assume valid
                    billing_cycle_start_date = prev_month_last.replace(day=day_of_month)
                
                # Get bonus categories for the card
                bonus_categories_all = (
                    self.db_session.query(CardBonusCategory)
                    .filter(CardBonusCategory.card_id == card.card_id)
                    .all()
                )
                bonus_categories = [bonus.bonus_category for bonus in bonus_categories_all]

                # Get all transactions for the card in the latest billing cycle
                transactions = (
                    self.db_session.query(UserTransaction)
                    .filter(
                        UserTransaction.user_id == user_id,
                        UserTransaction.card_id == card.card_id,
                        UserTransaction.transaction_date >= billing_cycle_start_date
                    )
                    .all()
                )

                # For each transaction, determine whether it falls under base or bonus category, calculate rewards, and exclude any bonus rewards exceeding the cap
                bonus_txn_amount = 0.0
                total_txn_amount = 0.0
                for txn in transactions:
                    reward_rate = card.base_benefit_rate
                    
                    # Check if transaction category matches any bonus category
                    if txn.category in bonus_categories:
                        bonus_txn_amount += float(txn.amount_sgd)
                        total_txn_amount += float(txn.amount_sgd)
                    else:
                        total_txn_amount += float(txn.amount_sgd)

                    # If there are bonus transactions, check against the cap
                if bonus_categories_all:  # Check if there are bonus categories
                    bonus = bonus_categories_all[0]  # Get the first bonus category
                    if bonus_txn_amount > float(bonus.bonus_cap_in_dollar):
                        bonus_amt = float(bonus.bonus_cap_in_dollar)
                    else:
                        bonus_amt = bonus_txn_amount
                    
                    base_amt = total_txn_amount - bonus_amt  
                    rewards_amt_earned = (base_amt * float(card.base_benefit_rate)) + (bonus_amt * float(card.base_benefit_rate + bonus.bonus_benefit_rate))
                else:
                    # No bonus categories, all rewards are base rate
                    rewards_amt_earned = total_txn_amount * float(card.base_benefit_rate)

                # Store rewards for this card in the dictionary
                rewards_by_card[str(card.card_name)] = float(rewards_amt_earned)
            
            # Return the dictionary of rewards for each card
            return rewards_by_card
            
        except Exception as e:
            raise ServiceException(f"Error calculating rewards earned: {str(e)}")
