"""
Data models for the Credit Card Recommendation Engine.
All models are dataclasses for simplicity and type safety.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    """
    Represents a logged transaction (historical data).

    Fields:
    - id: unique identifier for the transaction
    - date: transaction date in YYYY-MM-DD format
    - amount_sgd: transaction amount in SGD (must be > 0)
    - card_id: which card was used ('ww' | 'prvi' | 'uobone')
    - channel: transaction channel ('online' | 'offline')
    - is_overseas: optional flag for overseas transactions
    """
    id: str
    date: str  # YYYY-MM-DD
    amount_sgd: float
    card_id: str  # 'ww' | 'prvi' | 'uobone'
    channel: str  # 'online' | 'offline'
    is_overseas: Optional[bool] = None


@dataclass
class UpcomingTransaction:
    """
    Represents an upcoming transaction for which we want a recommendation.
    Same fields as Transaction except no card_id (that's what we're deciding).

    Fields:
    - date: transaction date in YYYY-MM-DD format
    - amount_sgd: transaction amount in SGD (must be > 0)
    - channel: transaction channel ('online' | 'offline')
    - is_overseas: optional flag for overseas transactions
    """
    date: str  # YYYY-MM-DD
    amount_sgd: float
    channel: str  # 'online' | 'offline'
    is_overseas: Optional[bool] = None


@dataclass
class RankedCard:
    """
    Represents a card with its estimated reward for a specific transaction.

    Fields:
    - card_id: the card identifier ('ww' | 'prvi' | 'uobone')
    - reward_unit: type of reward ('miles' | 'cashback')
    - estimated_reward_value: calculated reward value (miles or SGD)
    - effective_rate_str: human-readable rate (e.g., "4.0 mpd", "S$20.00 cb")
    - explanations: list of explanation strings for the user
    """
    card_id: str
    reward_unit: str  # 'miles' | 'cashback'
    estimated_reward_value: float
    effective_rate_str: str
    explanations: list[str]


@dataclass
class RecommendationResult:
    """
    The complete recommendation output for an upcoming transaction.

    Fields:
    - recommended_card_id: the best card to use
    - ranked_cards: list of RankedCard objects sorted best to worst
    - state_snapshot: optional dict with current state info (caps, progress, etc.)
    """
    recommended_card_id: str
    ranked_cards: list[RankedCard]
    state_snapshot: Optional[dict] = None
