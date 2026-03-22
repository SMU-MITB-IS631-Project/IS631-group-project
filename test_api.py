"""Manual API smoke-test script (not a pytest test).

This file is named `test_api.py`, but it's intended to be run directly against
a locally running server. To avoid side effects during `pytest` collection,
all logic is behind a `__main__` guard and pytest collection is disabled via
`__test__ = False`.
"""

__test__ = False


def main() -> None:
    import json

    import requests

    base_url = "http://localhost:8000/api/v1"
    user_id = "qa_user_story_check"

    headers = {
        "x-user-id": user_id,
        "Content-Type": "application/json",
    }

    print("=" * 60)
    print("Testing user_card_management API")
    print("=" * 60)

    print("\n1. Testing GET /api/v1/user_cards")
    print("-" * 60)
    try:
        response = requests.get(f"{base_url}/user_cards", headers=headers, timeout=10)
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        print(f"✓ User Cards Count: {len(data.get('user_cards', []))}")
        print(f"✓ Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n2. Testing POST /api/v1/user_cards")
    print("-" * 60)
    try:
        payload = {
            "wallet_card": {
                "card_id": "prvi",
                "refresh_day_of_month": 10,
                "annual_fee_billing_date": "2024-03-15",
                "cycle_spend_sgd": 250.50,
            }
        }
        response = requests.post(
            f"{base_url}/user_cards",
            json=payload,
            headers=headers,
            timeout=10,
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content (raw): {response.text[:500]}")
        if response.status_code == 201:
            data = response.json()
            print("✓ POST Success!")
            print(f"✓ Response: {json.dumps(data, indent=2)}")
        else:
            print(f"✗ POST Failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error Response: {json.dumps(error_data, indent=2)}")
            except Exception:
                print("Could not parse error response as JSON")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    print("\n3. Testing GET /api/v1/wallet")
    print("-" * 60)
    try:
        response = requests.get(f"{base_url}/wallet", headers=headers, timeout=10)
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        print(f"✓ Wallet Cards Count: {len(data.get('wallet', []))}")
        print(f"✓ Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
