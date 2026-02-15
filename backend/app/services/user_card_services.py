import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.db.db import SessionLocal
from app.models.card_catalogue import CardCatalogue
from app.services.data_service import USERS_FILE, _load_json, _save_json


@dataclass
class ServiceError(Exception):
    status_code: int
    code: str
    message: str
    details: Dict[str, Any]


class UserCardManagementService:
    _cards_master_cache: Optional[List[Dict[str, Any]]] = None
    _cards_master_cache_loaded_at: float = 0.0
    _cards_master_cache_ttl_seconds: int = 300
    _cards_master_cache_lock = threading.Lock()

    def __init__(self, user_id: Optional[str]) -> None:
        self.user_id = user_id
        self._cards_master_rows = self._get_cards_master_rows()
        self._cards_master_ids = {row["card_id"] for row in self._cards_master_rows}

    def _backend_root(self) -> str:
        return os.path.dirname(os.path.dirname(__file__))

    def _repo_root(self) -> str:
        return os.path.dirname(self._backend_root())

    def _audit_log_file(self) -> str:
        return os.path.join(self._backend_root(), "data", "user_card_audit_log.json")

    @classmethod
    def _get_cards_master_rows(cls) -> List[Dict[str, Any]]:
        now = time.monotonic()
        cache_is_fresh = (
            cls._cards_master_cache is not None
            and (now - cls._cards_master_cache_loaded_at) < cls._cards_master_cache_ttl_seconds
        )
        if cache_is_fresh:
            assert cls._cards_master_cache is not None
            return cls._cards_master_cache

        with cls._cards_master_cache_lock:
            now = time.monotonic()
            cache_is_fresh = (
                cls._cards_master_cache is not None
                and (now - cls._cards_master_cache_loaded_at) < cls._cards_master_cache_ttl_seconds
            )
            if cache_is_fresh:
                assert cls._cards_master_cache is not None
                return cls._cards_master_cache

            loaded_rows = cls._load_cards_master_rows()
            if loaded_rows:
                cls._cards_master_cache = loaded_rows
                cls._cards_master_cache_loaded_at = now
            else:
                logging.warning(
                    "Cards master cache not updated because loaded rows were empty; "
                    "will retry on next access."
                )
            return loaded_rows

    @classmethod
    def _invalidate_cards_master_cache(cls) -> None:
        with cls._cards_master_cache_lock:
            cls._cards_master_cache = None
            cls._cards_master_cache_loaded_at = 0.0

    @classmethod
    def _load_cards_master_rows(cls) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            with SessionLocal() as db:
                cards = db.query(CardCatalogue).all()

            for card in cards:
                # The current Card model only defines an `id` column; use it as the catalog identifier.
                catalog_card_id = getattr(card, "id", None)

                if catalog_card_id is None:
                    logging.warning("Encountered Card record without an 'id' value; skipping.")
                    continue

                row: Dict[str, Any] = {"card_id": str(catalog_card_id)}

                # If the Card model is later extended with a `reward_type` attribute,
                # include it here, but avoid assuming it exists today.
                if hasattr(card, "reward_type"):
                    reward_type = getattr(card, "reward_type")
                    if reward_type is not None:
                        row["reward_type"] = str(reward_type)
                rows.append(row)

            if not rows:
                logging.warning(
                    "Card catalog query returned no valid identifier values from CardCatalogue "
                    "(card_catalogue) table (no non-null id values found)."
                )
            return rows
        except Exception as e:
            logging.error(f"Failed to load card catalog from database: {e}")
            return []

    def _get_users(self) -> Dict[str, Any]:
        return _load_json(USERS_FILE)

    def _save_users(self, users: Dict[str, Any]) -> None:
        _save_json(USERS_FILE, users)

    def _load_audit_log(self) -> List[Dict[str, Any]]:
        raw = _load_json(self._audit_log_file())
        if isinstance(raw, list):
            return raw
        return raw.get("events", []) if isinstance(raw, dict) else []

    def _save_audit_log(self, events: List[Dict[str, Any]]) -> None:
        _save_json(self._audit_log_file(), {"events": events})

    def _require_user_context(self) -> str:
        if not self.user_id:
            raise ServiceError(401, "UNAUTHORIZED", "Missing or invalid user context.", {"required_header": "x-user-id"})
        return self.user_id

    def _ensure_wallet_card_ids(self, users: Dict[str, Any], user_key: str) -> bool:
        user = users.get(user_key, {})
        wallet = user.get("wallet", [])
        changed = False
        for card in wallet:
            if not card.get("id"):
                card["id"] = f"uc_{uuid.uuid4().hex}"
                changed = True
            if "is_active" not in card:
                card["is_active"] = True
                changed = True
        if changed:
            user["wallet"] = wallet
            users[user_key] = user
        return changed

    def _public_wallet_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "card_id": card.get("card_id"),
            "refresh_day_of_month": card.get("refresh_day_of_month"),
            "annual_fee_billing_date": card.get("annual_fee_billing_date"),
            "cycle_spend_sgd": card.get("cycle_spend_sgd", 0),
        }

    def _story_user_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        data = self._public_wallet_card(card)
        data["id"] = card.get("id")
        data["reward_rules"] = self._get_rewards_rule(card.get("card_id", ""))
        return data

    def _get_user_or_raise(self, require_auth: bool = False) -> tuple[Dict[str, Any], Dict[str, Any], str]:
        if require_auth:
            user_key = self._require_user_context()
        else:
            user_key = self.user_id or "u_001"
        users = self._get_users()
        user = users.get(user_key)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})
        if self._ensure_wallet_card_ids(users, user_key):
            self._save_users(users)
            user = users[user_key]
        return users, user, user_key

    def _find_user_card_owner(self, user_card_id: str) -> Optional[str]:
        users = self._get_users()
        for uid, user in users.items():
            for card in user.get("wallet", []):
                if card.get("id") == user_card_id and card.get("is_active", True):
                    return uid
        return None

    def _get_rewards_rule(self, card_id: str) -> Dict[str, Any]:
        row = next((r for r in self._cards_master_rows if r.get("card_id") == card_id), None)
        reward_type = (row or {}).get("reward_type", "unknown")
        
        # Validate that hardcoded defaults exist in master data
        defaults = {
            "ww": "4.0 mpd for eligible online spend, base rate otherwise.",
            "prvi": "Higher miles on eligible spend categories; base miles otherwise.",
            "uobone": "Tiered cashback with minimum monthly spend requirements.",
        }
        for default_id in defaults:
            if default_id not in self._cards_master_ids:
                logging.warning(f"Default reward rule for card_id '{default_id}' has no corresponding entry in card_catalogue table")
        
        return {
            "reward_type": reward_type,
            "rule_summary": defaults.get(card_id, "See issuer terms for reward computation."),
        }

    def list_user_cards(self) -> List[Dict[str, Any]]:
        _, user, _ = self._get_user_or_raise(require_auth=True)
        wallet = user.get("wallet", [])
        active_cards = [card for card in wallet if card.get("is_active", True)]
        return [self._story_user_card(card) for card in active_cards]

    def get_profile(self) -> Dict[str, Any]:
        _, user, _ = self._get_user_or_raise(require_auth=False)
        active_wallet = [self._public_wallet_card(card) for card in user.get("wallet", []) if card.get("is_active", True)]
        return {
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "preference": user.get("preference"),
            "wallet": active_wallet,
        }

    def save_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        username = (profile.get("username") or "").strip()
        preference = profile.get("preference")
        wallet = profile.get("wallet")

        if not username:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "username", "reason": "Required."})
        if preference not in {"miles", "cashback"}:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "preference", "reason": "Must be miles or cashback."})
        if not isinstance(wallet, list) or len(wallet) < 1:
            raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": "wallet", "reason": "Must have at least one card."})

        normalized_wallet: List[Dict[str, Any]] = []
        for idx, card in enumerate(wallet):
            card_id = card.get("card_id")
            if not card_id:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Required."})
            if not self._cards_master_rows:
                raise ServiceError(500, "SERVER_ERROR", "Master card data is not available. Cannot validate card.", {})
            if self._cards_master_ids and card_id not in self._cards_master_ids:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].card_id", "reason": "Not in cards master."})

            refresh_day = card.get("refresh_day_of_month")
            if not isinstance(refresh_day, int) or refresh_day < 1 or refresh_day > 31:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].refresh_day_of_month", "reason": "Must be 1..31."})

            annual_date = card.get("annual_fee_billing_date")
            if not annual_date:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].annual_fee_billing_date", "reason": "Required when card_id is set."})

            cycle_spend = card.get("cycle_spend_sgd", 0)
            if not isinstance(cycle_spend, (int, float)) or cycle_spend < 0:
                raise ServiceError(400, "VALIDATION_ERROR", "Invalid profile payload.", {"field": f"wallet[{idx}].cycle_spend_sgd", "reason": "Must be >= 0."})

            normalized_wallet.append(
                {
                    "id": card.get("id") or f"uc_{uuid.uuid4().hex}",
                    "card_id": card_id,
                    "refresh_day_of_month": refresh_day,
                    "annual_fee_billing_date": annual_date,
                    "cycle_spend_sgd": cycle_spend,
                    "is_active": True,
                }
            )

        users = self._get_users()
        user_key = profile.get("user_id") or self.user_id or "u_001"
        
        # Preserve inactive cards by merging wallets
        existing_user = users.get(user_key, {})
        existing_wallet = existing_user.get("wallet", [])
        active_new_card_ids = {c["card_id"] for c in normalized_wallet}
        
        merged_wallet = [c for c in existing_wallet if not c.get("is_active") or c.get("card_id") not in active_new_card_ids]
        merged_wallet.extend(normalized_wallet)
        
        users[user_key] = {
            "user_id": user_key,
            "username": username,
            "preference": preference,
            "wallet": merged_wallet,
        }
        self._save_users(users)
        return {
            "user_id": users[user_key]["user_id"],
            "username": users[user_key]["username"],
            "preference": users[user_key]["preference"],
            "wallet": [self._public_wallet_card(card) for card in merged_wallet if card.get("is_active")],
        }

    def add_user_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        user_key = self._require_user_context()
        card_id = card_data.get("card_id")
        if not card_id:
            raise ServiceError(400, "VALIDATION_ERROR", "card_id is required.", {"field": "user_card.card_id"})
        
        if not self._cards_master_rows:
            raise ServiceError(500, "SERVER_ERROR", "Master card data is not available. Cannot validate card.", {})
        
        if self._cards_master_ids and card_id not in self._cards_master_ids:
            raise ServiceError(
                400,
                "VALIDATION_ERROR",
                f"card_id '{card_id}' does not exist in cards master.",
                {"field": "user_card.card_id"},
            )

        users = self._get_users()
        user = users.get(user_key)
        if not user:
            user = {"user_id": user_key, "username": user_key, "preference": "miles", "wallet": []}
            users[user_key] = user

        wallet = user.get("wallet", [])
        if any(c.get("card_id") == card_id and c.get("is_active", True) for c in wallet):
            raise ServiceError(409, "CONFLICT", f"card_id '{card_id}' already exists.", {"field": "user_card.card_id"})

        new_card = {
            "id": f"uc_{uuid.uuid4().hex}",
            "card_id": card_id,
            "refresh_day_of_month": card_data["refresh_day_of_month"],
            "annual_fee_billing_date": card_data["annual_fee_billing_date"],
            "cycle_spend_sgd": card_data.get("cycle_spend_sgd", 0),
            "is_active": True,
        }
        wallet.append(new_card)
        user["wallet"] = wallet
        users[user_key] = user
        self._save_users(users)
        return self._story_user_card(new_card)

    def replace_user_card(self, user_card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
        user_key = self._require_user_context()
        users = self._get_users()
        user = users.get(user_key)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        wallet = user.get("wallet", [])
        for idx, card in enumerate(wallet):
            if card.get("id") == user_card_id and card.get("is_active", True):
                wallet[idx]["refresh_day_of_month"] = card_data["refresh_day_of_month"]
                wallet[idx]["annual_fee_billing_date"] = card_data["annual_fee_billing_date"]
                wallet[idx]["cycle_spend_sgd"] = card_data.get("cycle_spend_sgd", 0)
                users[user_key] = user
                self._save_users(users)
                return self._story_user_card(wallet[idx])

        owner = self._find_user_card_owner(user_card_id)
        if owner and owner != user_key:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})
        raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})

    def delete_user_card(self, user_card_id: str) -> None:
        user_key = self._require_user_context()
        users = self._get_users()
        user = users.get(user_key)
        if not user:
            raise ServiceError(404, "NOT_FOUND", "Profile not found.", {})

        wallet = user.get("wallet", [])
        for card in wallet:
            if card.get("id") == user_card_id and card.get("is_active", True):
                card["is_active"] = False
                users[user_key] = user
                self._save_users(users)
                events = self._load_audit_log()
                events.append(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "event": "DELETE_USER_CARD",
                        "user_id": user_key,
                        "user_card_id": user_card_id,
                        "card_id": card.get("card_id"),
                        "mode": "soft_delete",
                    }
                )
                self._save_audit_log(events)
                return

        owner = self._find_user_card_owner(user_card_id)
        if owner and owner != user_key:
            raise ServiceError(403, "FORBIDDEN", "Card does not belong to current user.", {})
        raise ServiceError(404, "NOT_FOUND", f"user_card_id '{user_card_id}' not found.", {})
