from __future__ import annotations

import calendar
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from sqlalchemy.orm import Session

from app.models.card_catalogue import CardCatalogue
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.services.errors import ServiceError
from app.services.user_service import UserService


class CardService:
    def __init__(self, db: Session, user_service: UserService) -> None:
        self.db = db
        self.user_service = user_service

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse_card_id(self, card_id: Any, field: str = "user_card.card_id") -> int:
        if isinstance(card_id, int):
            return card_id
        if isinstance(card_id, str) and card_id.isdigit():
            return int(card_id)
        raise ServiceError(
            400,
            "VALIDATION_ERROR",
            f"Invalid card_id '{card_id}'. Must be an integer.",
            {"field": field, "reason": "Invalid format or type."},
        )

    def _get_card_catalogue(self, card_id: int) -> Optional[CardCatalogue]:
        return self.db.query(CardCatalogue).filter(CardCatalogue.card_id == card_id).first()

    def _benefit_to_reward_type(self, card: Optional[CardCatalogue]) -> str:
        if not card or not getattr(card, "benefit_type", None):
            return "unknown"
        return str(card.benefit_type.value).lower()

    def _next_billing_cycle_date(self, refresh_day_of_month: int) -> datetime:
        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        day = min(refresh_day_of_month, last_day)
        candidate = date(today.year, today.month, day)
        if candidate < today:
            year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            last_day = calendar.monthrange(year, month)[1]
            day = min(refresh_day_of_month, last_day)
            candidate = date(year, month, day)
        return datetime.combine(candidate, datetime.min.time())

    def _parse_annual_fee_date(self, annual_fee_billing_date: str) -> datetime:
        try:
            return datetime.fromisoformat(annual_fee_billing_date)
        except ValueError as exc:
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                "Invalid profile payload.",
                {"field": "annual_fee_billing_date", "reason": "Must be YYYY-MM-DD."},
            ) from exc

    def _public_wallet_card(self, card: UserOwnedCard) -> Dict[str, Any]:
        return {
            "id": card.id,
            "card_id": str(card.card_id),
            "refresh_day_of_month": card.billing_cycle_refresh_date.day,
            "annual_fee_billing_date": card.card_expiry_date.isoformat() if card.card_expiry_date else None,
        }

    def _story_user_card(self, card: UserOwnedCard, catalog: Optional[CardCatalogue]) -> Dict[str, Any]:
        data = self._public_wallet_card(card)
        data["id"] = str(card.id)
        data["reward_rules"] = {
            "reward_type": self._benefit_to_reward_type(catalog),
            "rule_summary": "See issuer terms for reward computation.",
        }
        return data

    def _validate_wallet_entry(self, card: Dict[str, Any], idx: int = 0) -> Tuple[int, int, str]:
        card_id = card.get("card_id")
        if not card_id:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Required."})

        refresh_day = card.get("refresh_day_of_month")
        if not isinstance(refresh_day, int) or refresh_day < 1 or refresh_day > 31:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].refresh_day_of_month", "reason": "Must be 1..31."})

        annual_billing_date = card.get("annual_fee_billing_date")
        if not annual_billing_date:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].annual_fee_billing_date", "reason": "Required when card_id is set."})

        cycle_spend = card.get("cycle_spend_sgd", 0)
        if not isinstance(cycle_spend, (int, float)) or cycle_spend < 0:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].cycle_spend_sgd", "reason": "Must be >= 0."})

        parsed_card_id = self._parse_card_id(card_id, field=f"wallet[{idx}].card_id")
        if not self._get_card_catalogue(parsed_card_id):
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Not in cards master."})

        return parsed_card_id, refresh_day, annual_billing_date

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def list_user_cards(self, user_identifier: Optional[str]) -> List[Dict[str, Any]]:
        resolved_user_id = self.user_service.resolve_user_identifier(user_identifier)
        user = self.user_service.get_user_by_id(resolved_user_id)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        rows = (
            self.db.query(UserOwnedCard, CardCatalogue)
            .outerjoin(CardCatalogue, UserOwnedCard.card_id == CardCatalogue.card_id)
            .filter(
                UserOwnedCard.user_id == resolved_user_id,
                UserOwnedCard.status == UserOwnedCardStatus.active,
            )
            .all()
        )
        return [self._story_user_card(card, catalog) for card, catalog in rows]

    def get_wallet_cards(self, user_id: int) -> List[Dict[str, Any]]:
        cards = (
            self.db.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == user_id,
                UserOwnedCard.status == UserOwnedCardStatus.active,
            )
            .all()
        )
        return [self._public_wallet_card(card) for card in cards]

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    def add_user_card(self, user_identifier: Optional[str], card_data: Dict[str, Any]) -> Dict[str, Any]:
        resolved_user_id = self.user_service.resolve_user_identifier(user_identifier)
        user = self.user_service.get_user_by_id(resolved_user_id)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        parsed_card_id, refresh_day, annual_billing_date = self._validate_wallet_entry(card_data)

        existing = (
            self.db.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == resolved_user_id,
                UserOwnedCard.card_id == parsed_card_id,
                UserOwnedCard.status == UserOwnedCardStatus.active,
            )
            .first()
        )
        if existing:
            raise ServiceError(409, "CONFLICT", f"card_id '{card_data.get('card_id')}' already exists.", {"field": "user_card.card_id"})

        new_card = UserOwnedCard(
            user_id=resolved_user_id,
            card_id=parsed_card_id,
            billing_cycle_refresh_date=self._next_billing_cycle_date(refresh_day),
            card_expiry_date=self._parse_annual_fee_date(annual_billing_date),
            status=UserOwnedCardStatus.active,
        )
        self.db.add(new_card)
        self.db.commit()
        self.db.refresh(new_card)
        catalog = self._get_card_catalogue(parsed_card_id)
        return self._story_user_card(new_card, catalog)

    def replace_user_card(self, user_identifier: Optional[str], user_card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
        resolved_user_id = self.user_service.resolve_user_identifier(user_identifier)
        if not user_card_id.isdigit():
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})

        card = self.db.query(UserOwnedCard).filter(UserOwnedCard.id == int(user_card_id)).first()
        if not card:
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})
        if cast(int, card.user_id) != resolved_user_id:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})

        _, refresh_day, annual_billing_date = self._validate_wallet_entry(card_data)

        card.billing_cycle_refresh_date = self._next_billing_cycle_date(refresh_day)  # type: ignore[assignment]
        card.card_expiry_date = self._parse_annual_fee_date(annual_billing_date)  # type: ignore[assignment]
        card.status = UserOwnedCardStatus.active  # type: ignore[assignment]
        self.db.commit()
        catalog = self._get_card_catalogue(cast(int, card.card_id))
        return self._story_user_card(card, catalog)

    def delete_user_card(self, user_identifier: Optional[str], user_card_id: str) -> None:
        from app.models.transaction import UserTransaction, TransactionStatus

        resolved_user_id = self.user_service.resolve_user_identifier(user_identifier)
        if not user_card_id.isdigit():
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})

        card = self.db.query(UserOwnedCard).filter(UserOwnedCard.id == int(user_card_id)).first()
        if not card:
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})
        if cast(int, card.user_id) != resolved_user_id:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})

        card_id = cast(int, card.card_id)

        # Mark all transactions for this card as deleted_with_card (preserve transaction history)
        self.db.query(UserTransaction).filter(
            UserTransaction.user_id == resolved_user_id,
            UserTransaction.card_id == card_id,
        ).update({"status": TransactionStatus.DeletedWithCard})

        # Hard delete the card from user_owned_cards
        self.db.query(UserOwnedCard).filter(UserOwnedCard.id == int(user_card_id)).delete()

        self.db.commit()
        logging.info(
            "Hard-deleted user card id=%s for user_id=%s and marked associated transactions as deleted_with_card",
            card.id,
            resolved_user_id,
        )

    def save_wallet(self, user_id: int, wallet: List[Dict[str, Any]]) -> None:
        for idx, card in enumerate(wallet):
            parsed_card_id, refresh_day, annual_billing_date = self._validate_wallet_entry(card, idx)

            existing = (
                self.db.query(UserOwnedCard)
                .filter(
                    UserOwnedCard.user_id == user_id,
                    UserOwnedCard.card_id == parsed_card_id,
                )
                .first()
            )
            if existing:
                existing.billing_cycle_refresh_date = self._next_billing_cycle_date(refresh_day)  # type: ignore[assignment]
                existing.card_expiry_date = self._parse_annual_fee_date(annual_billing_date)  # type: ignore[assignment]
                existing.status = UserOwnedCardStatus.active  # type: ignore[assignment]
            else:
                self.db.add(
                    UserOwnedCard(
                        user_id=user_id,
                        card_id=parsed_card_id,
                        billing_cycle_refresh_date=self._next_billing_cycle_date(refresh_day),
                        card_expiry_date=self._parse_annual_fee_date(annual_billing_date),
                        status=UserOwnedCardStatus.active,
                    )
                )

        self.db.commit()
