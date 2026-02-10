import json
import os
from datetime import date
from typing import List, Dict, Any
import uuid

# Data directory is at backend/data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.json')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file, return empty dict if not exists"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}


def _save_json(file_path: str, data: Dict[str, Any]) -> None:
    """Save data to JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def get_user_wallet(user_id: str = "u_001") -> List[Dict[str, Any]]:
    """Get user's wallet (list of cards)"""
    users = _load_json(USERS_FILE)
    user = users.get(user_id, {})
    return user.get('wallet', [])


def card_exists_in_wallet(card_id: str, user_id: str = "u_001") -> bool:
    """Check if card_id exists in user's wallet"""
    wallet = get_user_wallet(user_id)
    return any(card['card_id'] == card_id for card in wallet)


def create_transaction(transaction_data: Dict[str, Any], user_id: str = "u_001") -> Dict[str, Any]:
    """Create and store a new transaction"""
    transactions = _load_json(TRANSACTIONS_FILE)
    
    # Generate ID and set date if not provided
    transaction_id = str(uuid.uuid4())[:8]  # Short ID like t_0001
    transaction_date = transaction_data.get('date') or str(date.today())
    
    # Build full transaction object
    transaction = {
        'id': transaction_id,
        'date': transaction_date,
        'item': transaction_data['item'],
        'amount_sgd': transaction_data['amount_sgd'],
        'card_id': transaction_data['card_id'],
        'channel': transaction_data['channel'],
        'is_overseas': transaction_data.get('is_overseas', False),
        'user_id': user_id
    }
    
    # Store in JSON
    if user_id not in transactions:
        transactions[user_id] = []
    transactions[user_id].append(transaction)
    _save_json(TRANSACTIONS_FILE, transactions)
    
    return transaction


def get_user_transactions(user_id: str = "u_001") -> List[Dict[str, Any]]:
    """Get all transactions for a user"""
    transactions = _load_json(TRANSACTIONS_FILE)
    return transactions.get(user_id, [])


def init_sample_data() -> None:
    """Initialize sample user data"""
    sample_user = {
        "user_id": "u_001",
        "username": "demo",
        "preference": "miles",
        "wallet": [
            {
                "card_id": "ww",
                "refresh_day_of_month": 15,
                "annual_fee_billing_date": "2026-06-28",
                "cycle_spend_sgd": 700
            },
            {
                "card_id": "tuvalu",
                "refresh_day_of_month": 20,
                "annual_fee_billing_date": "2026-07-15",
                "cycle_spend_sgd": 500
            }
        ]
    }
    
    users = _load_json(USERS_FILE)
    if 'u_001' not in users:
        users['u_001'] = sample_user
        _save_json(USERS_FILE, users)
