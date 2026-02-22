import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
USER_ID = "qa_user_story_check"

headers = {
    "x-user-id": USER_ID,
    "Content-Type": "application/json"
}

print("=" * 60)
print("Testing user_card_management API")
print("=" * 60)

# Test 1: GET user_cards
print("\n1. Testing GET /api/v1/user_cards")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/user_cards", headers=headers)
    print(f"✓ Status: {response.status_code}")
    data = response.json()
    print(f"✓ User Cards Count: {len(data['user_cards'])}")
    print(f"✓ Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: POST user_cards (Add a new card)
print("\n2. Testing POST /api/v1/user_cards")
print("-" * 60)
try:
    payload = {
        "wallet_card": {
            "card_id": "prvi",
            "refresh_day_of_month": 10,
            "annual_fee_billing_date": "2024-03-15",
            "cycle_spend_sgd": 250.50
        }
    }
    response = requests.post(f"{BASE_URL}/user_cards", json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Content (raw): {response.text[:500]}")
    if response.status_code == 201:
        data = response.json()
        print(f"✓ POST Success!")
        print(f"✓ Response: {json.dumps(data, indent=2)}")
    else:
        print(f"✗ POST Failed with status {response.status_code}")
        try:
            error_data = response.json()
            print(f"Error Response: {json.dumps(error_data, indent=2)}")
        except:
            print(f"Could not parse error response as JSON")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")

# Test 3: GET wallet endpoint
print("\n3. Testing GET /api/v1/wallet")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/wallet", headers=headers)
    print(f"✓ Status: {response.status_code}")
    data = response.json()
    print(f"✓ Wallet Cards Count: {len(data['wallet'])}")
    print(f"✓ Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
