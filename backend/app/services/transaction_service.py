import calendar as _calendar
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import String, cast as sa_cast, func, or_
from sqlalchemy.orm import Session

from app.models.card_bonus_category import CardBonusCategory
from app.models.card_catalogue import CardCatalogue
from app.models.transaction import TransactionCreate, UserTransaction, TransactionStatus
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import UserProfile
from app.services.errors import ServiceError


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _resolve_user_id(self, user_id: Optional[str]) -> int:
        raw_user_id = (user_id or "").strip()
        if raw_user_id.isdigit():
            return int(raw_user_id)
        if raw_user_id.startswith("u_") and raw_user_id[2:].isdigit():
            return int(raw_user_id[2:])

        user = self.db.query(UserProfile).filter(UserProfile.username == raw_user_id).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        return cast(int, user.id)

    def _format_user_id(self, user_id: int) -> str:
        return f"u_{user_id:03d}"

    def _parse_card_id(self, card_id: Any) -> int:
        if isinstance(card_id, int):
            return card_id
        if isinstance(card_id, str) and card_id.isdigit():
            return int(card_id)
        raise ServiceError(
            400,
            "VALIDATION_ERROR",
            f"Invalid card_id '{card_id}'. Must be an integer.",
            {"field": "transaction.card_id", "reason": "Invalid format or type."},
        )

    def _card_exists_in_wallet(self, user_id: int, card_id: int) -> bool:
        return (
            self.db.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == user_id,
                UserOwnedCard.card_id == card_id,
                or_(
                    UserOwnedCard.status == UserOwnedCardStatus.Active,
                    func.lower(sa_cast(UserOwnedCard.status, String)) == "active",
                ),
            )
            .first()
            is not None
        )

    def _transaction_to_dict(self, txn: UserTransaction) -> Dict[str, Any]:
        channel_value = str(txn.channel.value if hasattr(txn.channel, "value") else txn.channel).lower()
        status_value = str(txn.status.value if hasattr(txn.status, "value") else txn.status).lower()
        category_raw = txn.category.value if txn.category else None
        category_value = str(category_raw).lower() if category_raw else None

        return {
            "id": str(txn.id),
            "date": txn.transaction_date.isoformat(),
            "item": txn.item,
            "amount_sgd": float(txn.amount_sgd),
            "card_id": str(txn.card_id),
            "channel": channel_value,
            "category": category_value,
            "is_overseas": txn.is_overseas,
            "status": status_value,
            "user_id": self._format_user_id(cast(int, txn.user_id)),
        }

    def _billing_cycle_start(self, refresh_day: int, transaction_date: date) -> date:
        """Return the start date of the billing cycle containing transaction_date."""
        max_day_this_month = _calendar.monthrange(transaction_date.year, transaction_date.month)[1]
        candidate = transaction_date.replace(day=min(refresh_day, max_day_this_month))
        if candidate <= transaction_date:
            return candidate
        # refresh day falls after transaction_date in this month: use previous month
        if transaction_date.month == 1:
            prev_year, prev_month = transaction_date.year - 1, 12
        else:
            prev_year, prev_month = transaction_date.year, transaction_date.month - 1
        max_day_prev = _calendar.monthrange(prev_year, prev_month)[1]
        return date(prev_year, prev_month, min(refresh_day, max_day_prev))

    def _calculate_transaction_reward(
        self,
        user_id: int,
        card_id: int,
        amount_sgd: Decimal,
        category: Any,
        transaction_date: date,
    ) -> Decimal:
        """Calculate and return the reward for a single transaction at write time."""
        card = self.db.query(CardCatalogue).filter(CardCatalogue.card_id == card_id).first()
        if not card:
            return Decimal("0")

        base_rate = float(card.base_benefit_rate)
        amount = float(amount_sgd)

        # Resolve the transaction category string
        if category is None:
            txn_category_value = None
        elif hasattr(category, "value"):
            txn_category_value = category.value
        else:
            txn_category_value = str(category)

        # Find a matching bonus category (exact category or catch-all "All")
        bonus_categories = (
            self.db.query(CardBonusCategory)
            .filter(CardBonusCategory.card_id == card_id)
            .all()
        )
        matching_bonus = next(
            (
                bc
                for bc in bonus_categories
                if bc.bonus_category.value in (txn_category_value, "All")
            ),
            None,
        )

        if not matching_bonus:
            return Decimal(str(round(amount * base_rate, 2)))

        bonus_rate = float(matching_bonus.bonus_benefit_rate)
        bonus_cap = float(matching_bonus.bonus_cap_in_dollar)

        # Determine the billing cycle start date from the user's card refresh day
        user_card = (
            self.db.query(UserOwnedCard)
            .filter(UserOwnedCard.user_id == user_id, UserOwnedCard.card_id == card_id)
            .first()
        )
        refresh_day = (
            user_card.billing_cycle_refresh_date.day
            if user_card and user_card.billing_cycle_refresh_date
            else 1
        )
        billing_start = self._billing_cycle_start(refresh_day, transaction_date)

        # Sum prior bonus-category spend already committed in this billing cycle
        prior_filter = [
            UserTransaction.user_id == user_id,
            UserTransaction.card_id == card_id,
            UserTransaction.transaction_date >= billing_start,
            UserTransaction.transaction_date <= transaction_date,
        ]
        if matching_bonus.bonus_category.value != "All":
            prior_filter.append(
                sa_cast(UserTransaction.category, String) == txn_category_value
            )

        prior_spend_raw = self.db.query(func.sum(UserTransaction.amount_sgd)).filter(
            *prior_filter
        ).scalar()
        prior_bonus_spend = float(prior_spend_raw) if prior_spend_raw is not None else 0.0

        remaining_cap = max(0.0, bonus_cap - prior_bonus_spend)
        bonus_amount = min(amount, remaining_cap)
        base_amount = amount - bonus_amount

        reward = bonus_amount * bonus_rate + base_amount * base_rate
        return Decimal(str(round(reward, 2)))

    def create_transaction(self, user_id: Optional[str], payload: TransactionCreate) -> Dict[str, Any]:
        raw_user_id = user_id
        if not raw_user_id and payload.user_id is not None:
            raw_user_id = str(payload.user_id)
        resolved_user_id = self._resolve_user_id(raw_user_id or "u_001")

        card_id = self._parse_card_id(payload.card_id)
        if not self._card_exists_in_wallet(resolved_user_id, card_id):
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"card_id '{card_id}' not found in user wallet",
                {},
            )

        transaction_date = payload.transaction_date or date.today()
        total_reward = self._calculate_transaction_reward(
            user_id=resolved_user_id,
            card_id=card_id,
            amount_sgd=payload.amount_sgd,
            category=payload.category,
            transaction_date=transaction_date,
        )
        record = UserTransaction(
            user_id=resolved_user_id,
            card_id=card_id,
            amount_sgd=payload.amount_sgd,
            item=payload.item,
            channel=payload.channel,
            category=payload.category,
            is_overseas=payload.is_overseas,
            transaction_date=transaction_date,
            total_reward=total_reward,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._transaction_to_dict(record)

    def get_user_transactions(self, user_id: str, sort_by_date_desc: Optional[bool] = True) -> List[Dict[str, Any]]:
        resolved_user_id = self._resolve_user_id(user_id)
        query = self.db.query(UserTransaction).filter(UserTransaction.user_id == resolved_user_id)
        if sort_by_date_desc is True:
            query = query.order_by(UserTransaction.transaction_date.desc())
        elif sort_by_date_desc is False:
            query = query.order_by(UserTransaction.transaction_date.asc())
        rows = query.all()
        return [self._transaction_to_dict(row) for row in rows]

    def get_transaction_by_id(self, transaction_id: int, user_id: str) -> Dict[str, Any] | None:
        resolved_user_id = self._resolve_user_id(user_id)
        row = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )
        return self._transaction_to_dict(row) if row else None

    def update_transaction_status(self, user_id: str, transaction_id: int, status: str) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        
        # Validate status
        valid_statuses = [s.value for s in TransactionStatus]
        if status not in valid_statuses:
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}",
                {"field": "status", "valid_values": valid_statuses},
            )
        
        transaction = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )
        
        if not transaction:
            raise ServiceError(404, "NOT_FOUND", "Transaction not found.", {})
        
        transaction.status = TransactionStatus[status.replace("deleted_with_card", "DeletedWithCard").replace("active", "Active")]
        self.db.commit()
        self.db.refresh(transaction)
        return self._transaction_to_dict(transaction)
    
    def update_transactions_by_card_id(self, user_id: str, card_id: int, status: str) -> int:
        """Update all transactions for a card to the given status. Returns count of updated transactions."""
        resolved_user_id = self._resolve_user_id(user_id)
        
        # Validate status
        valid_statuses = [s.value for s in TransactionStatus]
        if status not in valid_statuses:
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}",
                {"field": "status", "valid_values": valid_statuses},
            )
        
        status_enum = TransactionStatus[status.replace("deleted_with_card", "DeletedWithCard").replace("active", "Active")]
        
        count = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.card_id == card_id)
            .update({"status": status_enum})
        )
        
        self.db.commit()
        return count

    def bulk_update_transaction_status(self, user_id: str, transaction_ids: List[int], status: str) -> int:
        """Bulk update multiple transactions to the given status. Returns count of updated transactions."""
        resolved_user_id = self._resolve_user_id(user_id)
        
        # Validate status
        valid_statuses = [s.value for s in TransactionStatus]
        if status not in valid_statuses:
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}",
                {"field": "status", "valid_values": valid_statuses},
            )
        
        status_enum = TransactionStatus[status.replace("deleted_with_card", "DeletedWithCard").replace("active", "Active")]
        
        count = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id.in_(transaction_ids))
            .update({"status": status_enum})
        )
        
        self.db.commit()
        return count

    def update_transaction(self, user_id: str, transaction_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update transaction fields. Returns updated transaction."""
        resolved_user_id = self._resolve_user_id(user_id)
        
        transaction = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )
        
        if not transaction:
            raise ServiceError(404, "NOT_FOUND", "Transaction not found.", {})
        
        # Define which fields are nullable
        nullable_fields = {"category"}
        non_nullable_fields = {"card_id", "amount_sgd", "item", "channel", "is_overseas", "transaction_date"}
        
        # Validate non-nullable fields aren't explicitly set to None
        for field in non_nullable_fields:
            if field in updates and updates[field] is None:
                raise ServiceError(
                    400,
                    "VALIDATION_ERROR",
                    f"Field '{field}' cannot be null.",
                    {"field": field},
                )
        
        # Validate card_id if being updated
        if "card_id" in updates and updates["card_id"] is not None:
            card_id = self._parse_card_id(updates["card_id"])
            if not self._card_exists_in_wallet(resolved_user_id, card_id):
                raise ServiceError(
                    400,
                    "VALIDATION_ERROR",
                    f"card_id '{card_id}' not found in user wallet",
                    {},
                )
            updates["card_id"] = card_id
        
        # Apply updates (allow None for nullable fields, skip None for others)
        for key, value in updates.items():
            if key in nullable_fields or value is not None:
                setattr(transaction, key, value)
        
        self.db.commit()
        self.db.refresh(transaction)
        return self._transaction_to_dict(transaction)

    def delete_transaction(self, user_id: str, transaction_id: int) -> Dict[str, Any]:
        """Delete a transaction. Returns deleted transaction."""
        resolved_user_id = self._resolve_user_id(user_id)
        
        transaction = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )
        
        if not transaction:
            raise ServiceError(404, "NOT_FOUND", "Transaction not found.", {})
        
        transaction_dict = self._transaction_to_dict(transaction)
        self.db.delete(transaction)
        self.db.commit()
        return transaction_dict

