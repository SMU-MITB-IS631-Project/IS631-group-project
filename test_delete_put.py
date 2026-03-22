import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
headers = {"x-user-id": "qa_user_story_check"}

print("=" * 60)
print("Testing DELETE and PUT endpoints")
print("=" * 60)

# First, get current cards to find an ID to test with
print("\n1. GET current user cards...")
response = requests.get(f"{BASE_URL}/user_cards", headers=headers)
cards = response.json()["user_cards"]
print(f"   Total cards: {len(cards)}")
if cards:
    test_card = cards[-1]  # Get last card
    card_id = test_card["id"]
    print(f"   Using card ID for testing: {card_id}")
    print(f"   Card details: card_id={test_card['card_id']}, refresh_day={test_card['refresh_day_of_month']}")
else:
    print("   No cards found!")
    exit(1)

# Test PUT (update)
print(f"\n2. Testing PUT /api/v1/user_cards/{card_id}")
print("-" * 60)
put_payload = {
    "user_card": {
        "card_id": test_card["card_id"],
        "refresh_day_of_month": 20,  # Change this
        "annual_fee_billing_date": "2026-01-01",  # Change this
        "cycle_spend_sgd": 9999
    }
}

try:
    response = requests.put(f"{BASE_URL}/user_cards/{card_id}", json=put_payload, headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ PUT SUCCESS!")
        print(f"   Updated card: refresh_day={data['wallet_card']['refresh_day_of_month']}, cycle_spend={data['wallet_card']['cycle_spend_sgd']}")
    else:
        print(f"   ❌ PUT Failed: {response.text}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Verify the update
print(f"\n3. Verify update - GET card again...")
response = requests.get(f"{BASE_URL}/user_cards", headers=headers)
cards = response.json()["user_cards"]
updated_card = next((c for c in cards if c["id"] == card_id), None)
if updated_card:
    print(f"   Card after PUT: refresh_day={updated_card['refresh_day_of_month']}, cycle_spend={updated_card['cycle_spend_sgd']}")

# Test DELETE
print(f"\n4. Testing DELETE /api/v1/user_cards/{card_id}")
print("-" * 60)
try:
    response = requests.delete(f"{BASE_URL}/user_cards/{card_id}", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 204:
        print(f"   ✅ DELETE SUCCESS!")
    else:
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Verify deletion
print(f"\n5. Verify deletion - GET all cards...")
response = requests.get(f"{BASE_URL}/user_cards", headers=headers)
cards = response.json()["user_cards"]
deleted_card = next((c for c in cards if c["id"] == card_id), None)
if deleted_card is None:
    print(f"   ✅ Card successfully deleted (not in list)")
else:
    print(f"   ❌ Card still exists: {deleted_card}")

print(f"\n   Final card count: {len(cards)}")
print("\n" + "=" * 60)
