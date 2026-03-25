from datetime import date
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import String, cast as sa_cast, func, or_
from sqlalchemy.orm import Session

from app.models.transaction import TransactionCreate, TransactionUpdate, UserTransaction, TransactionStatus
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import UserProfile
from app.services.errors import ServiceError


class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _resolve_user_sub(self, cognito_sub: Optional[str]) -> str:
        """
        Validate the Cognito sub (UUID) in the JWT and ensure user exists.
        """
        if not cognito_sub:
            raise ServiceError(401, "UNAUTHORIZED", "Missing Cognito sub in token.", {})
        user = self.db.query(UserProfile).filter(UserProfile.cognito_sub == cognito_sub).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        return user.id

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

    def _card_exists_in_wallet(self, user_sub: str, card_id: int) -> bool:
        return (
            self.db.query(UserOwnedCard.card_id)
            .filter(
                UserOwnedCard.user_id == user_sub,
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
            "user_id": txn.user_id,  # user_profile.id
        }

    def create_transaction(self, user_sub: Optional[str], payload: TransactionCreate) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_sub(user_sub)

        card_id = self._parse_card_id(payload.card_id)
        if not self._card_exists_in_wallet(resolved_user_id, card_id):
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"card_id '{card_id}' not found in user wallet",
                {},
            )

        transaction_date = payload.transaction_date or date.today()
        record = UserTransaction(
            user_id=resolved_user_id,
            card_id=card_id,
            amount_sgd=payload.amount_sgd,
            item=payload.item,
            channel=payload.channel,
            category=payload.category,
            is_overseas=payload.is_overseas,
            transaction_date=transaction_date,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._transaction_to_dict(record)

    def get_user_transactions(self, user_sub: str, sort_by_date_desc: Optional[bool] = True) -> List[Dict[str, Any]]:
        resolved_user_id = self._resolve_user_sub(user_sub)
        query = self.db.query(UserTransaction).filter(UserTransaction.user_id == resolved_user_id)
        if sort_by_date_desc is True:
            query = query.order_by(UserTransaction.transaction_date.desc())
        elif sort_by_date_desc is False:
            query = query.order_by(UserTransaction.transaction_date.asc())
        rows = query.all()
        return [self._transaction_to_dict(row) for row in rows]

    def get_transaction_by_id(self, transaction_id: int, user_sub: str) -> Dict[str, Any] | None:
        resolved_user_id = self._resolve_user_sub(user_sub)
        row = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )
        return self._transaction_to_dict(row) if row else None

    def update_transaction(self, user_sub: str, transaction_id: int, updates: TransactionUpdate) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_sub(user_sub)
        transaction = (
            self.db.query(UserTransaction)
            .filter(UserTransaction.user_id == resolved_user_id, UserTransaction.id == transaction_id)
            .first()
        )

        if not transaction:
            raise ServiceError(404, "NOT_FOUND", "Transaction not found.", {})

        updates_dict = updates.model_dump(exclude_unset=True, by_alias=False)

        if "card_id" in updates_dict:
            card_id = self._parse_card_id(updates_dict["card_id"])
            if not self._card_exists_in_wallet(resolved_user_id, card_id):
                raise ServiceError(
                    400,
                    "VALIDATION_ERROR",
                    f"card_id '{card_id}' not found in user wallet",
                    {},
                )
            transaction.card_id = card_id

        if "amount_sgd" in updates_dict:
            transaction.amount_sgd = updates_dict["amount_sgd"]

        if "item" in updates_dict:
            transaction.item = updates_dict["item"]

        if "channel" in updates_dict:
            transaction.channel = updates_dict["channel"]

        if "is_overseas" in updates_dict:
            transaction.is_overseas = updates_dict["is_overseas"]

        if "transaction_date" in updates_dict:
            transaction.transaction_date = updates_dict["transaction_date"]

        if "category" in updates_dict:
            transaction.category = updates_dict["category"]

        self.db.commit()
        self.db.refresh(transaction)
        return self._transaction_to_dict(transaction)


    def delete_transaction(self, user_id: str, transaction_id: int) -> Dict[str, Any]:
        """Delete a transaction. Returns deleted transaction."""
        resolved_user_id = self._resolve_user_sub(user_id)
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

