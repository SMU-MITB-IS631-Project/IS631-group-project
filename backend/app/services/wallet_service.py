import csv
import os
from typing import Dict, Any, List

from app.services.data_service import USERS_FILE, _load_json, _save_json


DEFAULT_USER_ID = 1


def _load_cards_master_ids() -> List[str]:
    """Load card_id values from frontend/public/data/cards_master.csv.

    Falls back to an empty list if the CSV is missing.
    """
    try:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # .../backend
        repo_root = os.path.dirname(backend_root)
        csv_path = os.path.join(
            repo_root,
            "frontend",
            "public",
            "data",
            "cards_master.csv",
        )
        if not os.path.exists(csv_path):
            return []

        ids: List[str] = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = (row.get("card_id") or "").strip()
                if cid:
                    ids.append(cid)
        return ids
    except Exception:
        # In a prototype setting, silently ignore and return empty list
        return []


CARDS_MASTER_IDS = set(_load_cards_master_ids())


def get_users() -> Dict[str, Any]:
    """Load users data from JSON file."""
    return _load_json(USERS_FILE)


def save_users(users: Dict[str, Any]) -> None:
    """Save users data to JSON file."""
    _save_json(USERS_FILE, users)


def get_or_create_user(user_id: str) -> Dict[str, Any]:
    """Get user data or create if doesn't exist."""
    users = get_users()
    user = users.get(user_id)
    if not user:
        user = {
            "user_id": user_id,
            "username": "demo",
            "preference": "miles",
            "wallet": [],
        }
        users[user_id] = user
        save_users(users)
    return user


def get_user_wallet(user_id: str = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
    """Get wallet for a specific user."""
    users = get_users()
    user = users.get(user_id)
    if not user:
        return []
    return user.get("wallet", [])


def add_card_to_wallet(card_data: Dict[str, Any], user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Add a card to user's wallet."""
    users = get_users()
    user = users.get(user_id) or get_or_create_user(user_id)
    wallet = user.get("wallet", [])
    wallet.append(card_data)
    user["wallet"] = wallet
    users[user_id] = user
    save_users(users)
    return card_data


def update_card_in_wallet(card_id: str, updates: Dict[str, Any], user_id: str = DEFAULT_USER_ID) -> Dict[str, Any] | None:
    """Update a card in user's wallet. Returns updated card or None if not found."""
    users = get_users()
    user = users.get(user_id)
    if not user:
        return None
    
    wallet = user.get("wallet", [])
    for wc in wallet:
        if wc.get("card_id") == card_id:
            for key, value in updates.items():
                if value is not None:
                    wc[key] = value
            user["wallet"] = wallet
            users[user_id] = user
            save_users(users)
            return wc
    
    return None


def delete_card_from_wallet(card_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Delete a card from user's wallet. Returns True if deleted, False if not found."""
    users = get_users()
    user = users.get(user_id)
    if not user:
        return False
    
    wallet = user.get("wallet", [])
    new_wallet = [wc for wc in wallet if wc.get("card_id") != card_id]
    
    if len(new_wallet) == len(wallet):
        return False
    
    user["wallet"] = new_wallet
    users[user_id] = user
    save_users(users)
    return True


def card_exists_in_master(card_id: str) -> bool:
    """Check if card_id exists in cards master CSV."""
    if not CARDS_MASTER_IDS:
        return True  # If master list not available, allow all
    return card_id in CARDS_MASTER_IDS


def card_exists_in_user_wallet(card_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Check if card already exists in user's wallet."""
    wallet = get_user_wallet(user_id)
    return any(wc.get("card_id") == card_id for wc in wallet)
