import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
headers = {"x-user-id": "qa_user_story_check"}

print("Testing POST endpoint with card_id='2'...")
payload = {
    "wallet_card": {
        "card_id": "2",
        "refresh_day_of_month": 25,
        "annual_fee_billing_date": "2025-01-01",
        "cycle_spend_sgd": 500
    }
}

try:
    response = requests.post(f"{BASE_URL}/user_cards", json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    if response.status_code == 201:
        data = response.json()
        print(f"✓ POST Success!")
        print(f"Response JSON: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
