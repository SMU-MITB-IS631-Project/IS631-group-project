import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, cast

from sqlalchemy.orm import Session

from app.models.card_catalogue import CardCatalogue
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus
from app.models.user_profile import BenefitsPreference, UserProfile


@dataclass
class ServiceError(Exception):
    status_code: int
    code: str
    message: str
    details: Dict[str, Any]


class UserCardManagementService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _require_user_context(self, user_id: Optional[str]) -> str:
        if not user_id:
            raise ServiceError(401, "UNAUTHORIZED", "Missing or invalid user context.", {"required_header": "x-user-id"})
        return user_id

    def _resolve_user_id(self, user_id: Optional[str]) -> int:
        raw_user_id = self._require_user_context(user_id).strip()
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
            if today.month == 12:
                year, month = today.year + 1, 1
            else:
                year, month = today.year, today.month + 1
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
            "card_id": str(card.card_id),
            "refresh_day_of_month": card.billing_cycle_refresh_date.day,
            "annual_fee_billing_date": card.card_expiry_date.date().isoformat(),
        }

    def _story_user_card(self, card: UserOwnedCard, catalog: Optional[CardCatalogue]) -> Dict[str, Any]:
        data = self._public_wallet_card(card)
        data["id"] = str(card.id)
        data["reward_rules"] = {
            "reward_type": self._benefit_to_reward_type(catalog),
            "rule_summary": "See issuer terms for reward computation.",
        }
        return data

    def list_user_cards(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        resolved_user_id = self._resolve_user_id(user_id)
        user = self.db.query(UserProfile).filter(UserProfile.id == resolved_user_id).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        rows = (
            self.db.query(UserOwnedCard, CardCatalogue)
            .outerjoin(CardCatalogue, UserOwnedCard.card_id == CardCatalogue.card_id)
            .filter(
                UserOwnedCard.user_id == resolved_user_id,
                UserOwnedCard.status == UserOwnedCardStatus.Active,
            )
            .all()
        )
        return [self._story_user_card(card, catalog) for card, catalog in rows]

    def get_profile(self, user_id: Optional[str]) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        user = self.db.query(UserProfile).filter(UserProfile.id == resolved_user_id).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        cards = (
            self.db.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == resolved_user_id,
                UserOwnedCard.status == UserOwnedCardStatus.Active,
            )
            .all()
        )
        benefits_preference = cast(Optional[BenefitsPreference], user.benefits_preference)
        return {
            "user_id": self._format_user_id(cast(int, user.id)),
            "username": cast(str, user.username),
            "preference": benefits_preference.value if benefits_preference is not None else None,
            "wallet": [self._public_wallet_card(card) for card in cards],
        }

    def save_profile(self, user_id: Optional[str], profile: Dict[str, Any]) -> Dict[str, Any]:
        username = (profile.get("username") or "").strip()
        preference = profile.get("preference")
        wallet = profile.get("wallet")

        if not username:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "username", "reason": "Required."})
        if preference not in {"miles", "cashback"}:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "preference", "reason": "Must be miles or cashback."})
        if not isinstance(wallet, list) or len(wallet) < 1:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "wallet", "reason": "Must have at least one card."})

        resolved_user_id = self._resolve_user_id(profile.get("user_id") or user_id)
        user = self.db.query(UserProfile).filter(UserProfile.id == resolved_user_id).first()
        if not user:
            user = UserProfile(
                id=resolved_user_id,
                username=username,
                password_hash="not_set",
                benefits_preference=BenefitsPreference(preference),
            )
            self.db.add(user)
        else:
            user.username = username  # type: ignore[assignment]
            user.benefits_preference = BenefitsPreference(preference)  # type: ignore[assignment]

        for idx, card in enumerate(wallet):
            card_id = card.get("card_id")
            if not card_id:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Required."})

            refresh_day = card.get("refresh_day_of_month")
            if not isinstance(refresh_day, int) or refresh_day < 1 or refresh_day > 31:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].refresh_day_of_month", "reason": "Must be 1..31."})

            annual_date = card.get("annual_fee_billing_date")
            if not annual_date:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].annual_fee_billing_date", "reason": "Required when card_id is set."})

            cycle_spend = card.get("cycle_spend_sgd", 0)
            if not isinstance(cycle_spend, (int, float)) or cycle_spend < 0:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].cycle_spend_sgd", "reason": "Must be >= 0."})

            parsed_card_id = self._parse_card_id(card_id, field=f"wallet[{idx}].card_id")
            if not self._get_card_catalogue(parsed_card_id):
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Not in cards master."})

            existing = (
                self.db.query(UserOwnedCard)
                .filter(
                    UserOwnedCard.user_id == resolved_user_id,
                    UserOwnedCard.card_id == parsed_card_id,
                )
                .first()
            )
            if existing:
                existing.billing_cycle_refresh_date = self._next_billing_cycle_date(refresh_day)  # type: ignore[assignment]
                existing.card_expiry_date = self._parse_annual_fee_date(annual_date)  # type: ignore[assignment]
                existing.status = UserOwnedCardStatus.Active  # type: ignore[assignment]
            else:
                self.db.add(
                    UserOwnedCard(
                        user_id=resolved_user_id,
                        card_id=parsed_card_id,
                        billing_cycle_refresh_date=self._next_billing_cycle_date(refresh_day),
                        card_expiry_date=self._parse_annual_fee_date(annual_date),
                        status=UserOwnedCardStatus.Active,
                    )
                )

        self.db.commit()
        return self.get_profile(self._format_user_id(resolved_user_id))

    def add_user_card(self, user_id: Optional[str], card_data: Dict[str, Any]) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        user = self.db.query(UserProfile).filter(UserProfile.id == resolved_user_id).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        card_id = card_data.get("card_id")
        if not card_id:
            raise ServiceError(400, "VALIDATION_ERROR", "card_id is required.", {"field": "user_card.card_id"})
        parsed_card_id = self._parse_card_id(card_id)
        if not self._get_card_catalogue(parsed_card_id):
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"card_id '{card_id}' does not exist in cards master.",
                {"field": "user_card.card_id"},
            )

        existing = (
            self.db.query(UserOwnedCard)
            .filter(
                UserOwnedCard.user_id == resolved_user_id,
                UserOwnedCard.card_id == parsed_card_id,
                UserOwnedCard.status == UserOwnedCardStatus.Active,
            )
            .first()
        )
        if existing:
            raise ServiceError(409, "CONFLICT", f"card_id '{card_id}' already exists.", {"field": "user_card.card_id"})

        refresh_day = card_data["refresh_day_of_month"]
        annual_date = card_data["annual_fee_billing_date"]
        new_card = UserOwnedCard(
            user_id=resolved_user_id,
            card_id=parsed_card_id,
            billing_cycle_refresh_date=self._next_billing_cycle_date(refresh_day),
            card_expiry_date=self._parse_annual_fee_date(annual_date),
            status=UserOwnedCardStatus.Active,
        )
        self.db.add(new_card)
        self.db.commit()
        self.db.refresh(new_card)
        catalog = self._get_card_catalogue(parsed_card_id)
        return self._story_user_card(new_card, catalog)

    def replace_user_card(self, user_id: Optional[str], user_card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
        resolved_user_id = self._resolve_user_id(user_id)
        if not user_card_id.isdigit():
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})

        card = self.db.query(UserOwnedCard).filter(UserOwnedCard.id == int(user_card_id)).first()
        if not card:
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})
        if cast(int, card.user_id) != resolved_user_id:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})

        refresh_day = card_data["refresh_day_of_month"]
        annual_date = card_data["annual_fee_billing_date"]
        card.billing_cycle_refresh_date = self._next_billing_cycle_date(refresh_day)  # type: ignore[assignment]
        card.card_expiry_date = self._parse_annual_fee_date(annual_date)  # type: ignore[assignment]
        card.status = UserOwnedCardStatus.Active  # type: ignore[assignment]
        self.db.commit()
        catalog = self._get_card_catalogue(cast(int, card.card_id))
        return self._story_user_card(card, catalog)

    def delete_user_card(self, user_id: Optional[str], user_card_id: str) -> None:
        resolved_user_id = self._resolve_user_id(user_id)
        if not user_card_id.isdigit():
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})

        card = self.db.query(UserOwnedCard).filter(UserOwnedCard.id == int(user_card_id)).first()
        if not card:
            raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})
        if cast(int, card.user_id) != resolved_user_id:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})

        card.status = UserOwnedCardStatus.Inactive  # type: ignore[assignment]
        self.db.commit()
        logging.info(
            "Soft-deleted user card id=%s for user_id=%s",
            card.id,
            resolved_user_id,
        )
