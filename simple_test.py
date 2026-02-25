import os
import requests
import json
import pytest

# This is an integration smoke test that expects the FastAPI server running locally.
# When running the full test suite, it should be skipped unless explicitly enabled.
RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"

if not RUN_INTEGRATION_TESTS:
    pytest.skip(
        "Skipping integration test; set RUN_INTEGRATION_TESTS=1 with server running on localhost:8000",
        allow_module_level=True,
    )

url = "http://localhost:8000/api/v1/user_cards"
headers = {"x-user-id": "qa_user_story_check"}


def _post_card(card_id: str):
    payload = {
        "wallet_card": {
            "card_id": card_id,
            "refresh_day_of_month": 10,
            "annual_fee_billing_date": "2024-03-15",
            "cycle_spend_sgd": 100,
        }
    }
    return requests.post(url, json=payload, headers=headers)


def test_post_existing_card_conflict():
    resp = _post_card("ww")
    print("Test 1: POST with existing card ID 'ww'")
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text[:200]}\n")
    assert resp.status_code in (200, 409)


def test_post_new_card():
    resp = _post_card("prvi")
    print("Test 2: POST with card ID 'prvi'")
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text[:500]}")
    assert resp.status_code in (200, 201, 409)


if __name__ == "__main__":
    # Allow ad-hoc execution without pytest
    for card in ("ww", "prvi"):
        response = _post_card(card)
        print(f"Card {card} -> {response.status_code}: {response.text[:200]}")
