"""
Card reward evaluation functions.
Each evaluator takes an upcoming transaction and monthly state,
returns a dict with reward value and explanations.
"""

from engine.models import UpcomingTransaction


# Default configuration values
DEFAULT_CONFIG = {
    # Woman's World Card
    "ww_mpd_online": 4.0,
    "ww_mpd_local_base": 0.4,
    "ww_online_cap_sgd": 1000.0,

    # PRVI Miles Card
    "prvi_mpd_local": 1.4,

    # UOB One Card
    "uobone_min_txn_count": 10,
    "uobone_tier_thresholds": [600, 1000, 2000],
    "uobone_quarterly_payout": {600: 60, 1000: 100, 2000: 200},
}


def evaluate_ww(txn: UpcomingTransaction, state: dict, config: dict = None) -> dict:
    """
    Evaluate DBS Woman's World card for the upcoming transaction.

    Rules:
    - Online transactions earn 4.0 mpd up to monthly cap of S$1000
    - Spillover above cap earns 0.4 mpd (base rate)
    - Offline transactions earn 0.4 mpd (base rate)

    Args:
        txn: UpcomingTransaction to evaluate
        state: Monthly state dict from build_month_state
        config: Optional config dict (uses defaults if not provided)

    Returns:
        Dict with keys:
            - card_id: "ww"
            - unit: "miles"
            - value: rounded miles (int)
            - raw_value: unrounded miles (float)
            - effective_rate_str: human-readable rate
            - explanations: list of explanation strings
    """
    if config is None:
        config = DEFAULT_CONFIG

    mpd_online = config.get("ww_mpd_online", 4.0)
    mpd_base = config.get("ww_mpd_local_base", 0.4)
    online_cap = config.get("ww_online_cap_sgd", 1000.0)

    ww_online_used = state.get("ww_online_spend_used", 0.0)

    explanations = []

    # Check if transaction is online
    if txn.channel == "online":
        remaining_cap = max(0, online_cap - ww_online_used)
        eligible_amount = min(txn.amount_sgd, remaining_cap)
        spillover_amount = txn.amount_sgd - eligible_amount

        # Calculate miles
        miles_from_eligible = eligible_amount * mpd_online
        miles_from_spillover = spillover_amount * mpd_base
        total_miles = miles_from_eligible + miles_from_spillover

        # Build explanations
        if spillover_amount > 0:
            # Spillover case
            effective_rate_str = f"split: {mpd_online:.1f}/{mpd_base:.1f} mpd"
            explanations.append(
                f"Online cap: S${eligible_amount:.2f} @ {mpd_online:.1f} mpd, "
                f"S${spillover_amount:.2f} @ {mpd_base:.1f} mpd"
            )
            explanations.append(f"Cap remaining before: S${remaining_cap:.2f}")
        else:
            # Fully eligible for online rate
            effective_rate_str = f"{mpd_online:.1f} mpd"
            explanations.append(f"Online transaction @ {mpd_online:.1f} mpd")
            explanations.append(f"Cap remaining before: S${remaining_cap:.2f}")
            explanations.append(f"Cap remaining after: S${remaining_cap - eligible_amount:.2f}")
    else:
        # Offline transaction - base rate
        total_miles = txn.amount_sgd * mpd_base
        effective_rate_str = f"{mpd_base:.1f} mpd"
        explanations.append(f"Offline transaction @ {mpd_base:.1f} mpd")

    return {
        "card_id": "ww",
        "unit": "miles",
        "value": round(total_miles),
        "raw_value": total_miles,
        "effective_rate_str": effective_rate_str,
        "explanations": explanations,
    }


def evaluate_prvi(txn: UpcomingTransaction, state: dict, config: dict = None) -> dict:
    """
    Evaluate UOB PRVI Miles card for the upcoming transaction.

    Rules:
    - All local transactions earn 1.4 mpd
    - No caps or restrictions
    - (Overseas handling omitted for MVP)

    Args:
        txn: UpcomingTransaction to evaluate
        state: Monthly state dict (unused for PRVI)
        config: Optional config dict (uses defaults if not provided)

    Returns:
        Dict with keys:
            - card_id: "prvi"
            - unit: "miles"
            - value: rounded miles (int)
            - raw_value: unrounded miles (float)
            - effective_rate_str: human-readable rate
            - explanations: list of explanation strings
    """
    if config is None:
        config = DEFAULT_CONFIG

    mpd_local = config.get("prvi_mpd_local", 1.4)

    # Simple calculation - no caps
    total_miles = txn.amount_sgd * mpd_local

    explanations = [
        f"Standard earn rate @ {mpd_local:.1f} mpd",
        "No monthly caps or restrictions"
    ]

    return {
        "card_id": "prvi",
        "unit": "miles",
        "value": round(total_miles),
        "raw_value": total_miles,
        "effective_rate_str": f"{mpd_local:.1f} mpd",
        "explanations": explanations,
    }


def evaluate_uobone_simple(txn: UpcomingTransaction, state: dict, config: dict = None) -> dict:
    """
    Evaluate UOB One card for the upcoming transaction (simple MVP version).

    Rules:
    - Requires min 10 transactions per month to qualify
    - Spend tiers: S$600, S$1000, S$2000
    - Quarterly payouts: S$60, S$100, S$200 (modeled as monthly expected value / 3)
    - Returns incremental value (delta_value) from adding this transaction

    Args:
        txn: UpcomingTransaction to evaluate
        state: Monthly state dict from build_month_state
        config: Optional config dict (uses defaults if not provided)

    Returns:
        Dict with keys:
            - card_id: "uobone"
            - unit: "cashback"
            - value: incremental cashback value (float, rounded to 2 decimals)
            - raw_value: same as value
            - effective_rate_str: human-readable description
            - explanations: list of explanation strings
    """
    if config is None:
        config = DEFAULT_CONFIG

    min_txn_count = config.get("uobone_min_txn_count", 10)
    tier_thresholds = config.get("uobone_tier_thresholds", [600, 1000, 2000])
    quarterly_payout = config.get("uobone_quarterly_payout", {600: 60, 1000: 100, 2000: 200})

    # Get current state for UOB One
    spend_pre = state.get("month_spend_total", {}).get("uobone", 0.0)
    txns_pre = state.get("month_txn_count", {}).get("uobone", 0)

    # Calculate post-transaction state
    spend_post = spend_pre + txn.amount_sgd
    txns_post = txns_pre + 1

    # Helper function to determine tier
    def get_tier(spend):
        """Returns highest tier threshold met by spend, or None if no tier met."""
        for threshold in sorted(tier_thresholds, reverse=True):
            if spend >= threshold:
                return threshold
        return None

    tier_pre = get_tier(spend_pre)
    tier_post = get_tier(spend_post)

    # Check qualification
    qualified_pre = (txns_pre >= min_txn_count) and (tier_pre is not None)
    qualified_post = (txns_post >= min_txn_count) and (tier_post is not None)

    # Calculate expected monthly payouts
    payout_pre = (quarterly_payout[tier_pre] / 3.0) if qualified_pre else 0.0
    payout_post = (quarterly_payout[tier_post] / 3.0) if qualified_post else 0.0

    # Incremental value
    delta_value = payout_post - payout_pre

    # Build explanations
    explanations = []

    # Transaction count progress
    if txns_post < min_txn_count:
        remaining_txns = min_txn_count - txns_post
        explanations.append(f"Progress: {txns_post}/{min_txn_count} txns ({remaining_txns} more needed)")
    else:
        explanations.append(f"Transaction requirement met: {txns_post}/{min_txn_count} txns")

    # Spend tier progress
    if tier_post is None:
        # Not yet at any tier
        next_tier = tier_thresholds[0]
        remaining_spend = next_tier - spend_post
        explanations.append(f"Spend: S${spend_post:.2f} (S${remaining_spend:.2f} to S${next_tier} tier)")
    else:
        # At a tier - check if there's a higher tier
        higher_tiers = [t for t in tier_thresholds if t > tier_post]
        if higher_tiers:
            next_tier = min(higher_tiers)
            remaining_spend = next_tier - spend_post
            explanations.append(f"Current tier: S${tier_post} (S${remaining_spend:.2f} to S${next_tier} tier)")
        else:
            explanations.append(f"Highest tier achieved: S${tier_post}")

    # Qualification and value changes
    if not qualified_pre and qualified_post:
        explanations.append(f"This transaction qualifies you! Expected monthly payout: S${payout_post:.2f}")
    elif qualified_pre and tier_post > tier_pre:
        explanations.append(f"Tier upgrade: S${tier_pre} → S${tier_post} (+S${delta_value:.2f}/month)")
    elif qualified_post:
        explanations.append(f"Already qualified at S${tier_post} tier (S${payout_post:.2f}/month expected)")

    # Effective rate string
    if delta_value > 0:
        effective_rate_str = f"+S${delta_value:.2f}/month"
    else:
        effective_rate_str = "S$0.00/month"

    return {
        "card_id": "uobone",
        "unit": "cashback",
        "value": round(delta_value, 2),
        "raw_value": delta_value,
        "effective_rate_str": effective_rate_str,
        "explanations": explanations,
    }
