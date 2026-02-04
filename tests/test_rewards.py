"""
Comprehensive tests for reward calculation and recommendation logic.
Tests all required scenarios from the PRD.
"""

import pytest
from engine.models import Transaction, UpcomingTransaction
from engine.cards import evaluate_ww, evaluate_prvi, evaluate_uobone_simple
from engine.recommender import recommend
from engine.state import build_month_state


class TestWomanWorldCard:
    """Tests for DBS Woman's World card evaluator."""

    def test_ww_online_early_month_full_cap_available(self):
        """
        Scenario 1: WW wins for online transaction early in month with cap remaining.

        Expected: Full 4.0 mpd rate applied, WW recommended in miles mode.
        """
        # Arrange: No prior WW online spend
        transactions = []
        state = build_month_state(transactions, "2025-02")

        upcoming_txn = UpcomingTransaction(
            date="2025-02-10",
            amount_sgd=250.0,
            channel="online",
            is_overseas=None
        )

        # Act: Evaluate WW
        ww_result = evaluate_ww(upcoming_txn, state)

        # Assert: Should get full 4.0 mpd
        expected_miles = 250.0 * 4.0  # 1000 miles
        assert ww_result["value"] == round(expected_miles)
        assert ww_result["effective_rate_str"] == "4.0 mpd"
        assert "Online transaction @ 4.0 mpd" in ww_result["explanations"][0]

        # Verify recommendation prefers WW in miles mode
        result = recommend(transactions, upcoming_txn, "miles")
        assert result.recommended_card_id == "ww"
        assert result.ranked_cards[0].card_id == "ww"
        assert result.ranked_cards[0].estimated_reward_value == round(expected_miles)

    def test_ww_spillover_crosses_cap(self):
        """
        Scenario 2: WW spillover when transaction crosses remaining cap.

        Expected: Partial amount at 4.0 mpd, remainder at 0.4 mpd (split rate).
        """
        # Arrange: S$900 already spent on WW online, S$100 cap remaining
        transactions = [
            Transaction("1", "2025-02-05", 300.0, "ww", "online", None),
            Transaction("2", "2025-02-10", 600.0, "ww", "online", None),
        ]
        state = build_month_state(transactions, "2025-02")

        # Verify state: 900 spent online
        assert state["ww_online_spend_used"] == 900.0

        # Upcoming transaction: S$250 (exceeds remaining S$100 cap)
        upcoming_txn = UpcomingTransaction(
            date="2025-02-15",
            amount_sgd=250.0,
            channel="online",
            is_overseas=None
        )

        # Act: Evaluate WW
        ww_result = evaluate_ww(upcoming_txn, state)

        # Assert: Spillover calculation
        # Eligible: S$100 @ 4.0 mpd = 400 miles
        # Spillover: S$150 @ 0.4 mpd = 60 miles
        # Total: 460 miles
        expected_miles = (100.0 * 4.0) + (150.0 * 0.4)
        assert ww_result["value"] == round(expected_miles)  # 460
        assert ww_result["effective_rate_str"] == "split: 4.0/0.4 mpd"
        assert "Online cap:" in ww_result["explanations"][0]
        assert "@ 4.0 mpd" in ww_result["explanations"][0]
        assert "@ 0.4 mpd" in ww_result["explanations"][0]

    def test_ww_cap_exhausted_prvi_wins(self):
        """
        Scenario 3: When WW cap is exhausted, PRVI wins in miles mode.

        Expected: PRVI gives 1.4 mpd > WW's 0.4 mpd, PRVI recommended.
        """
        # Arrange: S$1000+ already spent on WW online (cap exhausted)
        transactions = [
            Transaction("1", "2025-02-05", 600.0, "ww", "online", None),
            Transaction("2", "2025-02-10", 500.0, "ww", "online", None),
        ]
        state = build_month_state(transactions, "2025-02")

        # Verify cap exhausted
        assert state["ww_online_spend_used"] >= 1000.0

        # Upcoming online transaction
        upcoming_txn = UpcomingTransaction(
            date="2025-02-15",
            amount_sgd=200.0,
            channel="online",
            is_overseas=None
        )

        # Act: Evaluate both cards
        ww_result = evaluate_ww(upcoming_txn, state)
        prvi_result = evaluate_prvi(upcoming_txn, state)

        # Assert: WW only gets base rate (0.4 mpd), PRVI gets 1.4 mpd
        ww_miles = 200.0 * 0.4  # 80 miles
        prvi_miles = 200.0 * 1.4  # 280 miles

        assert ww_result["value"] == round(ww_miles)
        assert prvi_result["value"] == round(prvi_miles)

        # Verify PRVI is recommended
        result = recommend(transactions, upcoming_txn, "miles")
        assert result.recommended_card_id == "prvi"
        assert result.ranked_cards[0].card_id == "prvi"


class TestUOBOneCard:
    """Tests for UOB One card evaluator and cashback mode."""

    def test_uobone_triggers_qualification(self):
        """
        Scenario 4: Cashback mode - UOB One recommended when transaction triggers qualification.

        Setup: 9 prior transactions, S$550 spend (below S$600 tier)
        Upcoming: 10th transaction for S$100 (crosses S$600 tier)
        Expected: Qualifies for S$60/quarter = S$20/month, delta = +S$20
        """
        # Arrange: 9 prior UOB One transactions totaling S$550
        transactions = []
        for i in range(9):
            transactions.append(
                Transaction(f"txn_{i}", "2025-02-05", 61.11, "uobone", "offline", None)
            )
        # Total: 9 * 61.11 = 549.99 ≈ 550

        state = build_month_state(transactions, "2025-02")

        # Verify pre-state: 9 txns, ~S$550 spend (not qualified yet)
        assert state["month_txn_count"]["uobone"] == 9
        assert state["month_spend_total"]["uobone"] < 600.0

        # Upcoming transaction: 10th txn, S$100 (total will be 650)
        upcoming_txn = UpcomingTransaction(
            date="2025-02-20",
            amount_sgd=100.0,
            channel="offline",
            is_overseas=None
        )

        # Act: Evaluate UOB One
        uobone_result = evaluate_uobone_simple(upcoming_txn, state)

        # Assert: Should qualify at S$600 tier
        # Payout: S$60 quarterly / 3 = S$20/month
        # Delta: S$20 - S$0 = S$20
        expected_delta = 20.0
        assert uobone_result["value"] == expected_delta
        assert uobone_result["unit"] == "cashback"
        assert "This transaction qualifies you!" in " ".join(uobone_result["explanations"])

        # Verify UOB One is recommended in cashback mode
        result = recommend(transactions, upcoming_txn, "cashback")
        assert result.recommended_card_id == "uobone"
        assert result.ranked_cards[0].card_id == "uobone"
        assert result.ranked_cards[0].estimated_reward_value == expected_delta

    def test_uobone_no_delta_fallback_to_miles(self):
        """
        Scenario 5: Cashback mode - UOB One NOT recommended when delta_value == 0.

        Setup: Already qualified at S$600 tier with 10+ txns
        Upcoming: Additional transaction doesn't change tier
        Expected: delta_value = 0, fallback to best miles card
        """
        # Arrange: Already qualified - 10 txns, S$650 spend (at S$600 tier)
        transactions = []
        for i in range(10):
            transactions.append(
                Transaction(f"txn_{i}", "2025-02-05", 65.0, "uobone", "offline", None)
            )
        # Total: 10 * 65 = 650

        state = build_month_state(transactions, "2025-02")

        # Verify pre-state: qualified at S$600 tier
        assert state["month_txn_count"]["uobone"] >= 10
        assert state["month_spend_total"]["uobone"] >= 600.0
        assert state["month_spend_total"]["uobone"] < 1000.0

        # Upcoming transaction: S$50 (total will be 700, still at S$600 tier)
        upcoming_txn = UpcomingTransaction(
            date="2025-02-20",
            amount_sgd=50.0,
            channel="online",
            is_overseas=None
        )

        # Act: Evaluate UOB One
        uobone_result = evaluate_uobone_simple(upcoming_txn, state)

        # Assert: delta_value should be 0 (already qualified, no tier change)
        assert uobone_result["value"] == 0.0

        # Verify fallback to best miles card (WW online = 4.0 mpd)
        result = recommend(transactions, upcoming_txn, "cashback")

        # Since it's online, WW should win with 4.0 mpd
        ww_miles = 50.0 * 4.0  # 200 miles
        assert result.recommended_card_id == "ww"
        assert result.ranked_cards[0].card_id == "ww"
        assert result.ranked_cards[0].estimated_reward_value == round(ww_miles)


class TestMilesMode:
    """Additional tests for miles preference mode."""

    def test_miles_mode_ww_vs_prvi_offline(self):
        """
        Test miles mode: offline transaction, PRVI wins (1.4 mpd > 0.4 mpd).
        """
        transactions = []
        state = build_month_state(transactions, "2025-02")

        upcoming_txn = UpcomingTransaction(
            date="2025-02-10",
            amount_sgd=100.0,
            channel="offline",
            is_overseas=None
        )

        # WW offline: 100 * 0.4 = 40 miles
        # PRVI: 100 * 1.4 = 140 miles

        result = recommend(transactions, upcoming_txn, "miles")
        assert result.recommended_card_id == "prvi"
        assert result.ranked_cards[0].estimated_reward_value == 140


class TestCashbackMode:
    """Additional tests for cashback preference mode."""

    def test_cashback_mode_tier_upgrade(self):
        """
        Test UOB One tier upgrade increases expected payout.

        Setup: 10 txns, S$650 spend (qualified at S$600 tier)
        Upcoming: S$400 (crosses to S$1000 tier)
        Expected: Delta from S$20/month to S$33.33/month = +S$13.33
        """
        # Arrange: Qualified at S$600 tier
        transactions = []
        for i in range(10):
            transactions.append(
                Transaction(f"txn_{i}", "2025-02-05", 65.0, "uobone", "offline", None)
            )

        state = build_month_state(transactions, "2025-02")

        # Upcoming: S$400 pushes to S$1050 total (crosses S$1000 tier)
        upcoming_txn = UpcomingTransaction(
            date="2025-02-20",
            amount_sgd=400.0,
            channel="offline",
            is_overseas=None
        )

        # Act
        uobone_result = evaluate_uobone_simple(upcoming_txn, state)

        # Assert: Tier upgrade
        # Pre: S$600 tier = S$60/quarter / 3 = S$20/month
        # Post: S$1000 tier = S$100/quarter / 3 = S$33.33/month
        # Delta: S$13.33
        expected_delta = (100.0 / 3.0) - (60.0 / 3.0)
        assert abs(uobone_result["value"] - expected_delta) < 0.01  # Allow floating point tolerance
        assert "Tier upgrade" in " ".join(uobone_result["explanations"])

        # Verify recommended in cashback mode
        result = recommend(transactions, upcoming_txn, "cashback")
        assert result.recommended_card_id == "uobone"


class TestEdgeCases:
    """Edge case tests."""

    def test_exact_cap_boundary(self):
        """Test transaction exactly at cap boundary."""
        # Arrange: Exactly S$1000 online spend used
        transactions = [
            Transaction("1", "2025-02-05", 1000.0, "ww", "online", None),
        ]
        state = build_month_state(transactions, "2025-02")

        upcoming_txn = UpcomingTransaction(
            date="2025-02-10",
            amount_sgd=100.0,
            channel="online",
            is_overseas=None
        )

        # Act
        ww_result = evaluate_ww(upcoming_txn, state)

        # Assert: All spillover (0 eligible, 100 spill)
        expected_miles = 100.0 * 0.4  # 40 miles
        assert ww_result["value"] == round(expected_miles)

    def test_uobone_not_qualified_insufficient_txns(self):
        """Test UOB One when spend is high but txn count is low."""
        # Arrange: 5 txns, S$700 spend (tier met, but < 10 txns)
        transactions = []
        for i in range(5):
            transactions.append(
                Transaction(f"txn_{i}", "2025-02-05", 140.0, "uobone", "offline", None)
            )

        state = build_month_state(transactions, "2025-02")

        upcoming_txn = UpcomingTransaction(
            date="2025-02-20",
            amount_sgd=100.0,
            channel="offline",
            is_overseas=None
        )

        # Act
        uobone_result = evaluate_uobone_simple(upcoming_txn, state)

        # Assert: Not qualified (txn count 6 < 10)
        # Pre: not qualified (5 txns) -> S$0
        # Post: not qualified (6 txns) -> S$0
        # Delta: S$0
        assert uobone_result["value"] == 0.0
        assert "more needed" in " ".join(uobone_result["explanations"])
