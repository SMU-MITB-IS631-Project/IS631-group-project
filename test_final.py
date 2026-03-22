import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
headers = {"x-user-id": "qa_user_story_check"}

print("=" * 60)
print("Final POST Test - Adding card_id='3'")
print("=" * 60)

payload = {
    "wallet_card": {
        "card_id": "3",
        "refresh_day_of_month": 5,
        "annual_fee_billing_date": "2025-12-31",
        "cycle_spend_sgd": 1000
    }
}

try:
    response = requests.post(f"{BASE_URL}/user_cards", json=payload, headers=headers)
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 201:
        data = response.json()
        print(f"✅ POST SUCCESS!")
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"❌ POST Failed")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Verification - GET all user cards")
print("=" * 60)

try:
    response = requests.get(f"{BASE_URL}/user_cards", headers=headers)
    data = response.json()
    print(f"\n✅ Total cards: {len(data['user_cards'])}")
    for card in data['user_cards']:
        print(f"  - {card['card_id']}: {card['id']}")
except Exception as e:
    print(f"✗ Error: {e}")
