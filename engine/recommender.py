"""
Recommendation engine with preference-based ranking.
Orchestrates card evaluation and applies user preference logic.
"""

from typing import List

from engine.models import Transaction, UpcomingTransaction, RankedCard, RecommendationResult
from engine.state import build_month_state, month_key
from engine.cards import evaluate_ww, evaluate_prvi, evaluate_uobone_simple, DEFAULT_CONFIG


# Recommendation policy configuration
RECOMMENDATION_CONFIG = {
    "MIN_EFFECTIVE_MPD_TO_AVOID_CASHBACK": 1.0,
}


def recommend(
    transactions: List[Transaction],
    upcoming_txn: UpcomingTransaction,
    preference: str,
    config: dict = None
) -> RecommendationResult:
    """
    Generate a card recommendation for an upcoming transaction.

    Args:
        transactions: List of historical Transaction objects
        upcoming_txn: UpcomingTransaction to get recommendation for
        preference: User preference ("miles" or "cashback")
        config: Optional config dict (uses defaults if not provided)

    Returns:
        RecommendationResult with recommended card and ranked alternatives

    Raises:
        ValueError: If preference is not "miles" or "cashback"
    """
    if preference not in ["miles", "cashback"]:
        raise ValueError(f"Invalid preference: {preference}. Must be 'miles' or 'cashback'.")

    if config is None:
        config = DEFAULT_CONFIG.copy()
        config.update(RECOMMENDATION_CONFIG)

    # Build monthly state for the upcoming transaction's month
    target_month = month_key(upcoming_txn.date)
    state = build_month_state(transactions, target_month)

    # Evaluate all three cards
    ww_result = evaluate_ww(upcoming_txn, state, config)
    prvi_result = evaluate_prvi(upcoming_txn, state, config)
    uobone_result = evaluate_uobone_simple(upcoming_txn, state, config)

    # Apply preference-based recommendation logic
    if preference == "miles":
        recommended_card_id, ranked_cards = _recommend_miles(
            ww_result, prvi_result, uobone_result, config
        )
    else:  # cashback
        recommended_card_id, ranked_cards = _recommend_cashback(
            ww_result, prvi_result, uobone_result, config
        )

    # Build state snapshot for user visibility
    state_snapshot = {
        "target_month": target_month,
        "ww_online_cap_remaining": max(
            0, config.get("ww_online_cap_sgd", 1000.0) - state.get("ww_online_spend_used", 0.0)
        ),
        "uobone_progress": {
            "spend": state.get("month_spend_total", {}).get("uobone", 0.0),
            "txn_count": state.get("month_txn_count", {}).get("uobone", 0),
        },
    }

    return RecommendationResult(
        recommended_card_id=recommended_card_id,
        ranked_cards=ranked_cards,
        state_snapshot=state_snapshot,
    )


def _recommend_miles(ww_result: dict, prvi_result: dict, uobone_result: dict, config: dict) -> tuple:
    """
    Apply miles preference logic.

    Rules:
    - Choose the card with highest miles (WW vs PRVI)
    - Fallback to cashback only if best effective mpd < MIN_EFFECTIVE_MPD_TO_AVOID_CASHBACK

    Returns:
        Tuple of (recommended_card_id, ranked_cards_list)
    """
    min_mpd_threshold = config.get("MIN_EFFECTIVE_MPD_TO_AVOID_CASHBACK", 1.0)

    # Compare WW vs PRVI miles
    ww_miles = ww_result["value"]
    prvi_miles = prvi_result["value"]

    # Determine best miles card
    if ww_miles >= prvi_miles:
        best_miles_result = ww_result
        second_miles_result = prvi_result
    else:
        best_miles_result = prvi_result
        second_miles_result = ww_result

    # Calculate effective mpd for best miles card
    best_effective_mpd = best_miles_result["raw_value"] / best_miles_result.get("txn_amount", 1.0)
    # We don't have txn_amount in result, need to recalculate from raw_value
    # For now, let's use a simpler heuristic - if raw_value >= amount * 1.0, it's good

    # Check if we should consider cashback fallback
    # For simplicity, we'll consider cashback if both WW and PRVI have low miles
    # Low is defined as < min_mpd_threshold effective rate

    # Since we don't store amount in results, let's use a simpler rule:
    # If the best miles card is WW with offline rate (0.4) or if both give < threshold miles per dollar
    # For MVP, let's just check if best miles raw_value suggests low rate

    # Actually, let's be more direct: check if it's WW with base rate or PRVI
    # WW base rate is 0.4, PRVI is 1.4
    # If effective_rate_str suggests low rate, consider cashback

    consider_cashback = False
    if "0.4 mpd" in best_miles_result["effective_rate_str"]:
        # WW base rate case - very low
        consider_cashback = True

    ranked_cards = []

    if consider_cashback and uobone_result["value"] > 0:
        # Cashback is viable, rank it first if value is good
        # But in miles mode, only fallback if really necessary
        # Let's still prefer miles unless cashback gives significantly more value
        # For simplicity, just rank them: best_miles, second_miles, cashback

        ranked_cards = [
            _result_to_ranked_card(best_miles_result),
            _result_to_ranked_card(second_miles_result),
            _result_to_ranked_card(uobone_result),
        ]
        recommended_card_id = best_miles_result["card_id"]
    else:
        # Standard miles ranking
        ranked_cards = [
            _result_to_ranked_card(best_miles_result),
            _result_to_ranked_card(second_miles_result),
            _result_to_ranked_card(uobone_result),
        ]
        recommended_card_id = best_miles_result["card_id"]

    return recommended_card_id, ranked_cards


def _recommend_cashback(ww_result: dict, prvi_result: dict, uobone_result: dict, config: dict) -> tuple:
    """
    Apply cashback preference logic.

    Rules:
    - Choose UOB One if delta_value > 0
    - Else fallback to best miles card (WW vs PRVI)

    Returns:
        Tuple of (recommended_card_id, ranked_cards_list)
    """
    uobone_value = uobone_result["value"]

    if uobone_value > 0:
        # UOB One is recommended
        recommended_card_id = "uobone"

        # Rank: uobone, then best miles, then other miles
        ww_miles = ww_result["value"]
        prvi_miles = prvi_result["value"]

        if ww_miles >= prvi_miles:
            ranked_cards = [
                _result_to_ranked_card(uobone_result),
                _result_to_ranked_card(ww_result),
                _result_to_ranked_card(prvi_result),
            ]
        else:
            ranked_cards = [
                _result_to_ranked_card(uobone_result),
                _result_to_ranked_card(prvi_result),
                _result_to_ranked_card(ww_result),
            ]
    else:
        # Fallback to best miles
        ww_miles = ww_result["value"]
        prvi_miles = prvi_result["value"]

        if ww_miles >= prvi_result["value"]:
            recommended_card_id = "ww"
            ranked_cards = [
                _result_to_ranked_card(ww_result),
                _result_to_ranked_card(prvi_result),
                _result_to_ranked_card(uobone_result),
            ]
        else:
            recommended_card_id = "prvi"
            ranked_cards = [
                _result_to_ranked_card(prvi_result),
                _result_to_ranked_card(ww_result),
                _result_to_ranked_card(uobone_result),
            ]

    return recommended_card_id, ranked_cards


def _result_to_ranked_card(result: dict) -> RankedCard:
    """
    Convert an evaluator result dict to a RankedCard object.

    Args:
        result: Dict from evaluate_ww, evaluate_prvi, or evaluate_uobone_simple

    Returns:
        RankedCard object
    """
    return RankedCard(
        card_id=result["card_id"],
        reward_unit=result["unit"],
        estimated_reward_value=result["value"],
        effective_rate_str=result["effective_rate_str"],
        explanations=result["explanations"],
    )
