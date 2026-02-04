"""
Unit tests for engine/state.py
Tests the monthly state computation logic.
"""

import pytest
from engine.models import Transaction
from engine.state import month_key, build_month_state


class TestMonthKey:
    """Tests for the month_key helper function."""

    def test_month_key_extracts_yyyy_mm(self):
        """Verify month_key correctly extracts YYYY-MM from a date string."""
        assert month_key("2025-01-15") == "2025-01"
        assert month_key("2024-12-31") == "2024-12"
        assert month_key("2025-02-01") == "2025-02"


class TestBuildMonthState:
    """Tests for the build_month_state function."""

    def test_spend_and_txn_counts_per_card(self):
        """
        Test that build_month_state correctly computes:
        - month_spend_total for each card
        - month_txn_count for each card
        """
        # Arrange: Create test transactions for January 2025
        transactions = [
            Transaction("1", "2025-01-05", 100.0, "ww", "online", None),
            Transaction("2", "2025-01-10", 50.0, "ww", "offline", None),
            Transaction("3", "2025-01-15", 200.0, "prvi", "online", None),
            Transaction("4", "2025-01-20", 75.0, "uobone", "offline", None),
            Transaction("5", "2025-01-25", 150.0, "ww", "online", None),
        ]

        # Act: Build state for January 2025
        state = build_month_state(transactions, "2025-01")

        # Assert: Verify spend totals
        assert state["month_spend_total"]["ww"] == 300.0  # 100 + 50 + 150
        assert state["month_spend_total"]["prvi"] == 200.0
        assert state["month_spend_total"]["uobone"] == 75.0

        # Assert: Verify transaction counts
        assert state["month_txn_count"]["ww"] == 3
        assert state["month_txn_count"]["prvi"] == 1
        assert state["month_txn_count"]["uobone"] == 1

    def test_ww_online_spend_used_calculation(self):
        """
        Test that build_month_state correctly computes ww_online_spend_used
        (sum of Woman's World card online transactions).
        """
        # Arrange: Create test transactions with mixed WW channels
        transactions = [
            Transaction("1", "2025-01-05", 100.0, "ww", "online", None),
            Transaction("2", "2025-01-10", 50.0, "ww", "offline", None),  # offline - not counted
            Transaction("3", "2025-01-15", 200.0, "ww", "online", None),
            Transaction("4", "2025-01-20", 75.0, "prvi", "online", None),  # different card - not counted
            Transaction("5", "2025-01-25", 150.0, "ww", "online", None),
        ]

        # Act: Build state for January 2025
        state = build_month_state(transactions, "2025-01")

        # Assert: Only WW online transactions should be counted
        assert state["ww_online_spend_used"] == 450.0  # 100 + 200 + 150

    def test_empty_transactions_list(self):
        """
        Test that build_month_state handles an empty transaction list correctly.
        """
        # Arrange: Empty transaction list
        transactions = []

        # Act: Build state for January 2025
        state = build_month_state(transactions, "2025-01")

        # Assert: All values should be empty/zero
        assert state["month_spend_total"] == {}
        assert state["month_txn_count"] == {}
        assert state["ww_online_spend_used"] == 0.0

    def test_filters_by_target_month(self):
        """
        Test that build_month_state only includes transactions from the target month.
        """
        # Arrange: Transactions across multiple months
        transactions = [
            Transaction("1", "2025-01-15", 100.0, "ww", "online", None),
            Transaction("2", "2025-02-10", 200.0, "ww", "online", None),  # Different month
            Transaction("3", "2024-12-25", 150.0, "ww", "online", None),  # Different month
            Transaction("4", "2025-01-20", 50.0, "prvi", "offline", None),
        ]

        # Act: Build state for January 2025
        state = build_month_state(transactions, "2025-01")

        # Assert: Only January transactions should be included
        assert state["month_spend_total"]["ww"] == 100.0
        assert state["month_txn_count"]["ww"] == 1
        assert state["month_spend_total"]["prvi"] == 50.0
        assert state["month_txn_count"]["prvi"] == 1
        assert state["ww_online_spend_used"] == 100.0

        # Verify February transactions are not included
        assert "2025-02-10" not in [t.date for t in transactions if month_key(t.date) == "2025-01"]

    def test_multiple_cards_with_mixed_channels(self):
        """
        Test a complex scenario with multiple cards and mixed channels.
        """
        # Arrange: Complex transaction mix
        transactions = [
            Transaction("1", "2025-01-01", 100.0, "ww", "online", None),
            Transaction("2", "2025-01-02", 50.0, "ww", "offline", None),
            Transaction("3", "2025-01-03", 200.0, "ww", "online", None),
            Transaction("4", "2025-01-04", 300.0, "prvi", "online", None),
            Transaction("5", "2025-01-05", 150.0, "prvi", "offline", None),
            Transaction("6", "2025-01-06", 75.0, "uobone", "online", None),
            Transaction("7", "2025-01-07", 80.0, "uobone", "offline", None),
            Transaction("8", "2025-01-08", 90.0, "uobone", "online", None),
        ]

        # Act: Build state for January 2025
        state = build_month_state(transactions, "2025-01")

        # Assert: Verify all computations
        assert state["month_spend_total"]["ww"] == 350.0  # 100 + 50 + 200
        assert state["month_spend_total"]["prvi"] == 450.0  # 300 + 150
        assert state["month_spend_total"]["uobone"] == 245.0  # 75 + 80 + 90

        assert state["month_txn_count"]["ww"] == 3
        assert state["month_txn_count"]["prvi"] == 2
        assert state["month_txn_count"]["uobone"] == 3

        assert state["ww_online_spend_used"] == 300.0  # Only WW online: 100 + 200
