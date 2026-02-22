import requests
import json

url = "http://localhost:8000/api/v1/user_cards"
headers = {"x-user-id": "qa_user_story_check"}

# Test 1: With existing card (should get a conflict)
print("Test 1: POST with existing card ID 'ww'")
payload = {
    "wallet_card": {
        "card_id": "ww",
        "refresh_day_of_month": 10,
        "annual_fee_billing_date": "2024-03-15",
        "cycle_spend_sgd": 100
    }
}

resp = requests.post(url, json=payload, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:200]}\n")

# Test 2: With a different card ID
print("Test 2: POST with card ID 'prvi'")
payload = {
    "wallet_card": {
        "card_id": "prvi",
        "refresh_day_of_month": 10,
        "annual_fee_billing_date": "2024-03-15",
        "cycle_spend_sgd": 100
    }
}

resp = requests.post(url, json=payload, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:500]}")
