"""
Command-line interface for the Credit Card Recommendation Engine.
Stage 1: CSV storage with add and show commands only.
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from engine.models import Transaction, UpcomingTransaction
from engine.state import build_month_state, month_key
from engine.recommender import recommend


# Default CSV file path
CSV_PATH = Path("data/transactions.csv")
CSV_HEADERS = ["id", "date", "amount_sgd", "card_id", "channel", "is_overseas"]


def ensure_csv_exists():
    """Create the CSV file with headers if it doesn't exist."""
    if not CSV_PATH.exists():
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def load_transactions() -> List[Transaction]:
    """
    Load all transactions from the CSV file.

    Returns:
        List of Transaction objects
    """
    transactions = []

    if not CSV_PATH.exists():
        return transactions

    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert is_overseas from string to bool/None
            is_overseas = None
            if row.get("is_overseas"):
                is_overseas = row["is_overseas"].lower() == "true"

            txn = Transaction(
                id=row["id"],
                date=row["date"],
                amount_sgd=float(row["amount_sgd"]),
                card_id=row["card_id"],
                channel=row["channel"],
                is_overseas=is_overseas
            )
            transactions.append(txn)

    return transactions


def generate_transaction_id() -> str:
    """
    Generate a unique transaction ID based on timestamp.

    Returns:
        Transaction ID string (e.g., "txn_20250115_123045_001")
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Check existing IDs to avoid collision
    transactions = load_transactions()
    existing_ids = {txn.id for txn in transactions}

    counter = 1
    while True:
        txn_id = f"txn_{timestamp}_{counter:03d}"
        if txn_id not in existing_ids:
            return txn_id
        counter += 1


def cmd_add(args):
    """
    Add a new transaction to the CSV file.

    Args:
        args: Parsed command-line arguments with fields:
            - date: YYYY-MM-DD
            - amount: float
            - card: card_id ('ww' | 'prvi' | 'uobone')
            - channel: 'online' | 'offline'
            - overseas: optional bool
    """
    ensure_csv_exists()

    # Validate card_id
    valid_cards = ["ww", "prvi", "uobone"]
    if args.card not in valid_cards:
        print(f"Error: Invalid card '{args.card}'. Must be one of: {', '.join(valid_cards)}")
        sys.exit(1)

    # Validate channel
    valid_channels = ["online", "offline"]
    if args.channel not in valid_channels:
        print(f"Error: Invalid channel '{args.channel}'. Must be one of: {', '.join(valid_channels)}")
        sys.exit(1)

    # Validate amount
    if args.amount <= 0:
        print(f"Error: Amount must be greater than 0. Got: {args.amount}")
        sys.exit(1)

    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
        sys.exit(1)

    # Generate transaction ID
    txn_id = generate_transaction_id()

    # Prepare row data
    is_overseas_str = ""
    if args.overseas is not None:
        is_overseas_str = "true" if args.overseas else "false"

    row = [txn_id, args.date, args.amount, args.card, args.channel, is_overseas_str]

    # Append to CSV
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    print(f"Transaction added: {txn_id}")
    print(f"  Date: {args.date}")
    print(f"  Amount: S${args.amount:.2f}")
    print(f"  Card: {args.card}")
    print(f"  Channel: {args.channel}")
    if args.overseas is not None:
        print(f"  Overseas: {args.overseas}")


def cmd_show(args):
    """
    Show monthly state for a given month.

    Args:
        args: Parsed command-line arguments with fields:
            - month: YYYY-MM
    """
    # Validate month format
    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        print(f"Error: Invalid month format '{args.month}'. Expected YYYY-MM.")
        sys.exit(1)

    # Load transactions
    transactions = load_transactions()

    if not transactions:
        print("No transactions found in the database.")
        return

    # Build state for the target month
    state = build_month_state(transactions, args.month)

    # Display results
    print(f"\n=== Monthly State for {args.month} ===\n")

    print("Spend by Card:")
    if state["month_spend_total"]:
        for card_id, spend in sorted(state["month_spend_total"].items()):
            print(f"  {card_id}: S${spend:.2f}")
    else:
        print("  (No spend recorded)")

    print("\nTransaction Count by Card:")
    if state["month_txn_count"]:
        for card_id, count in sorted(state["month_txn_count"].items()):
            print(f"  {card_id}: {count} transaction(s)")
    else:
        print("  (No transactions recorded)")

    print(f"\nWoman's World Online Spend Used: S${state['ww_online_spend_used']:.2f}")
    print()


def cmd_recommend(args):
    """
    Get a card recommendation for an upcoming transaction.

    Args:
        args: Parsed command-line arguments with fields:
            - date: YYYY-MM-DD
            - amount: float
            - channel: 'online' | 'offline'
            - pref: 'miles' | 'cashback'
    """
    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
        sys.exit(1)

    # Validate channel
    valid_channels = ["online", "offline"]
    if args.channel not in valid_channels:
        print(f"Error: Invalid channel '{args.channel}'. Must be one of: {', '.join(valid_channels)}")
        sys.exit(1)

    # Validate preference
    valid_prefs = ["miles", "cashback"]
    if args.pref not in valid_prefs:
        print(f"Error: Invalid preference '{args.pref}'. Must be one of: {', '.join(valid_prefs)}")
        sys.exit(1)

    # Validate amount
    if args.amount <= 0:
        print(f"Error: Amount must be greater than 0. Got: {args.amount}")
        sys.exit(1)

    # Load transactions
    transactions = load_transactions()

    # Create upcoming transaction
    upcoming_txn = UpcomingTransaction(
        date=args.date,
        amount_sgd=args.amount,
        channel=args.channel,
        is_overseas=None  # Not handling overseas in Stage 2 MVP
    )

    # Get recommendation
    result = recommend(transactions, upcoming_txn, args.pref)

    # Display results
    print(f"\n=== Card Recommendation ===\n")
    print(f"Transaction: S${upcoming_txn.amount_sgd:.2f} {upcoming_txn.channel} on {upcoming_txn.date}")
    print(f"Preference: {args.pref}")
    print(f"\nRecommended Card: {result.recommended_card_id.upper()}")
    print(f"\n--- Ranked Options ---\n")

    for i, card in enumerate(result.ranked_cards, 1):
        if card.reward_unit == "miles":
            reward_str = f"{card.estimated_reward_value} miles"
        else:
            reward_str = f"S${card.estimated_reward_value:.2f}"

        print(f"{i}. {card.card_id.upper()} - {reward_str} ({card.effective_rate_str})")
        for explanation in card.explanations:
            print(f"   • {explanation}")
        print()

    # Show state snapshot
    if result.state_snapshot:
        print("--- Current Month State ---")
        print(f"Month: {result.state_snapshot['target_month']}")
        print(f"WW Online Cap Remaining: S${result.state_snapshot['ww_online_cap_remaining']:.2f}")
        print(f"UOB One Progress: {result.state_snapshot['uobone_progress']['txn_count']} txns, "
              f"S${result.state_snapshot['uobone_progress']['spend']:.2f} spend")
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Credit Card Recommendation Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    parser_add = subparsers.add_parser("add", help="Add a new transaction")
    parser_add.add_argument("--date", required=True, help="Transaction date (YYYY-MM-DD)")
    parser_add.add_argument("--amount", type=float, required=True, help="Amount in SGD")
    parser_add.add_argument("--card", required=True, help="Card ID (ww | prvi | uobone)")
    parser_add.add_argument("--channel", required=True, help="Channel (online | offline)")
    parser_add.add_argument("--overseas", type=bool, default=None, help="Overseas transaction (optional)")

    # Show command
    parser_show = subparsers.add_parser("show", help="Show monthly state")
    parser_show.add_argument("--month", required=True, help="Target month (YYYY-MM)")

    # Recommend command
    parser_recommend = subparsers.add_parser("recommend", help="Get card recommendation")
    parser_recommend.add_argument("--date", required=True, help="Transaction date (YYYY-MM-DD)")
    parser_recommend.add_argument("--amount", type=float, required=True, help="Amount in SGD")
    parser_recommend.add_argument("--channel", required=True, help="Channel (online | offline)")
    parser_recommend.add_argument("--pref", required=True, help="Preference (miles | cashback)")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "add":
        cmd_add(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "recommend":
        cmd_recommend(args)


if __name__ == "__main__":
    main()
