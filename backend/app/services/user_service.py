from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING, cast

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user_profile import BenefitsPreference, UserProfile
from app.services.errors import ServiceError

if TYPE_CHECKING:
    from app.services.card_service import CardService


pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_user_context(self, user_identifier: Optional[str]) -> str:
        if not user_identifier:
            raise ServiceError(401, "UNAUTHORIZED", "Missing or invalid user context.", {"required_header": "x-user-id"})
        return user_identifier.strip()

    def resolve_user_identifier(self, user_identifier: Optional[str]) -> int:
        raw_user_id = self._require_user_context(user_identifier)
        if raw_user_id.isdigit():
            return int(raw_user_id)
        if raw_user_id.startswith("u_") and raw_user_id[2:].isdigit():
            return int(raw_user_id[2:])

        user = self.db.query(UserProfile).filter(UserProfile.username == raw_user_id).first()
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        return cast(int, user.id)

    def format_user_id(self, user_id: int) -> str:
        return f"u_{user_id:03d}"

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    # ------------------------------------------------------------------
    # User lookups
    # ------------------------------------------------------------------
    def list_users(self) -> Dict[int, Dict[str, Any]]:
        users = self.db.query(UserProfile).all()
        return {cast(int, user.id): user.to_dict() for user in users}

    def get_user_by_username(self, username: str) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter(UserProfile.username == username).first()

    def get_user_by_id(self, user_id: int) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter(UserProfile.id == user_id).first()

    def get_next_available_user_id(self) -> int:
        max_user = self.db.query(UserProfile).order_by(UserProfile.id.desc()).first()
        return (max_user.id + 1) if max_user else 1

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def create_user(
        self,
        username: str,
        password: str,
        name: str | None = None,
        email: str | None = None,
        benefits_preference: str | None = None,
    ) -> Dict[str, Any]:
        existing_user = self.get_user_by_username(username)
        if existing_user:
            raise ServiceError(409, "CONFLICT", "Username already exists", {})

        pref_enum = BenefitsPreference.No_preference
        if benefits_preference:
            try:
                pref_enum = BenefitsPreference(benefits_preference)
            except ValueError:
                pref_enum = BenefitsPreference.No_preference

        normalized_name = name.strip() if name and name.strip() else None
        normalized_email = email.strip() if email and email.strip() else None

        generated_id = self.get_next_available_user_id()
        hashed_password = self.hash_password(password)

        new_user = UserProfile(
            id=generated_id,
            username=username,
            password_hash=hashed_password,
            name=normalized_name,
            email=normalized_email,
            benefits_preference=pref_enum,
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user.to_dict()

    # ------------------------------------------------------------------
    # Profile aggregation
    # ------------------------------------------------------------------
    def get_profile(self, user_identifier: Optional[str], card_service: "CardService") -> Dict[str, Any]:
        resolved_user_id = self.resolve_user_identifier(user_identifier)
        user = self.get_user_by_id(resolved_user_id)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        benefits_preference = cast(Optional[BenefitsPreference], user.benefits_preference)
        wallet_cards = card_service.get_wallet_cards(resolved_user_id)
        return {
            "user_id": self.format_user_id(cast(int, user.id)),
            "username": cast(str, user.username),
            "preference": benefits_preference.value if benefits_preference is not None else None,
            "wallet": wallet_cards,
        }

    def save_profile(self, user_identifier: Optional[str], profile: Dict[str, Any], card_service: "CardService") -> Dict[str, Any]:
        username = (profile.get("username") or "").strip()
        preference = profile.get("preference")
        wallet = profile.get("wallet")

        if not username:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "username", "reason": "Required."})
        if preference not in {"miles", "cashback", "no preference"}:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "preference", "reason": "Must be miles, cashback, or no preference."})
        if not isinstance(wallet, list) or len(wallet) < 1:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "wallet", "reason": "Must have at least one card."})

        resolved_user_id = self.resolve_user_identifier(profile.get("user_id") or user_identifier)
        user = self.get_user_by_id(resolved_user_id)
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

        card_service.save_wallet(resolved_user_id, wallet)

        self.db.commit()
        return self.get_profile(self.format_user_id(resolved_user_id), card_service)
