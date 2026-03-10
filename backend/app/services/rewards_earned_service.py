from datetime import date, timedelta
from typing import Optional

from sqlalchemy import String, cast as sa_cast, func
from sqlalchemy.orm import Session

from app.models.card_bonus_category import CardBonusCategory
from app.models.card_catalogue import CardCatalogue
from app.models.transaction import UserTransaction
from app.models.user_owned_cards import UserOwnedCard

# Attempt to import ServiceException; provide fallback if module not available
try:
    from app.exceptions import ServiceException
except ImportError:
    class ServiceException(Exception):
        """Fallback exception used when app.exceptions is missing (e.g., during tests)"""


class RewardsEarnedService:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def calculate_rewards_earned(self, user_id: int) -> dict:
        """
        Calculate total rewards earned for a user for each active card in the latest billing cycle.
        """
        active_cards = (
            self.db_session.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == user_id,
                func.lower(sa_cast(UserOwnedCard.status, String)) == "active",
            )
                UserOwnedCard.status == UserOwnedCardStatus.Active
                )
            .all()
        )
        if not active_cards:
            return {}

        try:
            rewards_by_card = {}

            for user_card in active_cards:
                card = (
                    self.db_session.query(CardCatalogue)
                    .filter(CardCatalogue.card_id == user_card.card_id)
                    .first()
                )
                if not card:
                    continue

                day_of_month = getattr(user_card, "billing_cycle_refresh_day_of_mth", 1)
                today = date.today()
                if today.day >= day_of_month:
                    billing_cycle_start_date = today.replace(day=day_of_month)
                else:
                    first_of_month = today.replace(day=1)
                    prev_month_last = first_of_month - timedelta(days=1)
                    billing_cycle_start_date = prev_month_last.replace(day=day_of_month)

                bonus_categories_all = (
                    self.db_session.query(CardBonusCategory)
                    .filter(CardBonusCategory.card_id == card.card_id)
                    .all()
                )
                bonus_categories = [bonus.bonus_category.value for bonus in bonus_categories_all]

                transactions = (
                    self.db_session.query(UserTransaction)
                    .filter(
                        UserTransaction.user_id == user_id,
                        UserTransaction.card_id == card.card_id,
                        UserTransaction.transaction_date >= billing_cycle_start_date,
                    )
                    .all()
                )

                bonus_txn_amount = 0.0
                total_txn_amount = 0.0
                for txn in transactions:
                    txn_category = txn.category.value if txn.category else None
                    amount = float(txn.amount_sgd)
                    if txn_category in bonus_categories:
                        bonus_txn_amount += amount
                    total_txn_amount += amount

                if bonus_categories_all:
                    bonus = bonus_categories_all[0]
                    bonus_amt = min(bonus_txn_amount, float(bonus.bonus_cap_in_dollar))
                    base_amt = total_txn_amount - bonus_amt
                    rewards_amt_earned = (base_amt * float(card.base_benefit_rate)) + (
                        bonus_amt * float(bonus.bonus_benefit_rate)
                    )
                else:
                    rewards_amt_earned = total_txn_amount * float(card.base_benefit_rate)

                rewards_by_card[str(card.card_name)] = float(rewards_amt_earned)

            return rewards_by_card

        except Exception as e:
            raise ServiceException(f"Error calculating rewards earned: {str(e)}")

    def get_historical_rewards(
        self,
        user_id: int,
        card_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        group_by: str = "month",
    ) -> list:
        """
        Retrieve historical rewards from stored transaction.total_reward using SQL aggregation.

        Supported grouping:
        - month: sum per YYYY-MM
        - card: sum per card_id
        - month_card: sum per YYYY-MM and card_id
        """
        try:
            base_query = self.db_session.query(UserTransaction).filter(
                UserTransaction.user_id == user_id,
                UserTransaction.total_reward.isnot(None),
            )

            if card_id is not None:
                base_query = base_query.filter(UserTransaction.card_id == card_id)
            if start_date is not None:
                base_query = base_query.filter(UserTransaction.transaction_date >= start_date)
            if end_date is not None:
                base_query = base_query.filter(UserTransaction.transaction_date <= end_date)

            period_expr = func.strftime("%Y-%m", UserTransaction.transaction_date)

            if group_by == "month":
                rows = (
                    base_query.with_entities(
                        period_expr.label("period"),
                        func.sum(UserTransaction.total_reward).label("total_reward"),
                        func.count(UserTransaction.id).label("transaction_count"),
                    )
                    .group_by(period_expr)
                    .order_by(period_expr)
                    .all()
                )
                return [
                    {
                        "period": row.period,
                        "total_reward": round(float(row.total_reward), 2),
                        "transaction_count": int(row.transaction_count),
                    }
                    for row in rows
                ]

            if group_by == "card":
                rows = (
                    base_query.with_entities(
                        UserTransaction.card_id.label("card_id"),
                        func.sum(UserTransaction.total_reward).label("total_reward"),
                        func.count(UserTransaction.id).label("transaction_count"),
                    )
                    .group_by(UserTransaction.card_id)
                    .order_by(UserTransaction.card_id)
                    .all()
                )
                return [
                    {
                        "card_id": int(row.card_id),
                        "total_reward": round(float(row.total_reward), 2),
                        "transaction_count": int(row.transaction_count),
                    }
                    for row in rows
                ]

            if group_by in ("month_card", "card_month"):
                rows = (
                    base_query.with_entities(
                        period_expr.label("period"),
                        UserTransaction.card_id.label("card_id"),
                        func.sum(UserTransaction.total_reward).label("total_reward"),
                        func.count(UserTransaction.id).label("transaction_count"),
                    )
                    .group_by(period_expr, UserTransaction.card_id)
                    .order_by(period_expr, UserTransaction.card_id)
                    .all()
                )
                return [
                    {
                        "period": row.period,
                        "card_id": int(row.card_id),
                        "total_reward": round(float(row.total_reward), 2),
                        "transaction_count": int(row.transaction_count),
                    }
                    for row in rows
                ]

            raise ServiceException(f"Invalid group_by parameter: {group_by}")

        except ServiceException:
            raise
        except Exception as e:
            raise ServiceException(f"Error retrieving historical rewards: {str(e)}")
