"""
Monthly state computation from transaction logs.
Deterministic and unit-testable.
"""

from typing import List
from engine.models import Transaction


def month_key(date: str) -> str:
    """
    Extract the month key from a date string.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        Month key in YYYY-MM format

    Example:
        >>> month_key("2025-01-15")
        "2025-01"
    """
    return date[:7]  # Extract YYYY-MM from YYYY-MM-DD


def build_month_state(transactions: List[Transaction], target_yyyy_mm: str) -> dict:
    """
    Build the monthly state for a given month from transaction history.

    This function computes:
    - month_spend_total: total spend per card for the target month
    - month_txn_count: transaction count per card for the target month
    - ww_online_spend_used: total online spend for Woman's World card (for cap tracking)

    Args:
        transactions: List of Transaction objects
        target_yyyy_mm: Target month in YYYY-MM format (e.g., "2025-01")

    Returns:
        Dictionary with keys:
        - 'month_spend_total': dict[card_id -> float]
        - 'month_txn_count': dict[card_id -> int]
        - 'ww_online_spend_used': float

    Example:
        >>> txns = [
        ...     Transaction("1", "2025-01-05", 100.0, "ww", "online"),
        ...     Transaction("2", "2025-01-10", 50.0, "ww", "offline"),
        ...     Transaction("3", "2025-01-15", 200.0, "prvi", "online"),
        ... ]
        >>> state = build_month_state(txns, "2025-01")
        >>> state['month_spend_total']['ww']
        150.0
        >>> state['month_txn_count']['ww']
        2
        >>> state['ww_online_spend_used']
        100.0
    """
    # Initialize state containers
    month_spend_total = {}
    month_txn_count = {}
    ww_online_spend_used = 0.0

    # Filter transactions for the target month
    target_transactions = [
        txn for txn in transactions
        if month_key(txn.date) == target_yyyy_mm
    ]

    # Process each transaction
    for txn in target_transactions:
        card = txn.card_id

        # Update spend total
        month_spend_total[card] = month_spend_total.get(card, 0.0) + txn.amount_sgd

        # Update transaction count
        month_txn_count[card] = month_txn_count.get(card, 0) + 1

        # Track Woman's World online spend for cap calculation
        if card == "ww" and txn.channel == "online":
            ww_online_spend_used += txn.amount_sgd

    return {
        "month_spend_total": month_spend_total,
        "month_txn_count": month_txn_count,
        "ww_online_spend_used": ww_online_spend_used,
    }
