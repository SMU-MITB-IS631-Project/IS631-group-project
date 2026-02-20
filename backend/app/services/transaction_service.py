from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, cast

from sqlalchemy.orm import Session

from app.models.transaction import TransactionCreate, UserTransaction, TransactionStatus
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import UserProfile


@dataclass
class ServiceError(Exception):
    status_code: int
    code: str
    message: str
    details: Dict[str, Any]


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
                UserOwnedCard.status == UserOwnedCardStatus.Active,
            )
            .first()
            is not None
        )

    def _transaction_to_dict(self, txn: UserTransaction) -> Dict[str, Any]:
        return {
            "id": str(txn.id),
            "date": txn.transaction_date.isoformat(),
            "item": txn.item,
            "amount_sgd": float(txn.amount_sgd),
            "card_id": str(txn.card_id),
            "channel": txn.channel.value,
            "category": txn.category.value if txn.category else None,
            "is_overseas": txn.is_overseas,
            "status": txn.status.value,
            "user_id": self._format_user_id(cast(int, txn.user_id)),
        }

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

