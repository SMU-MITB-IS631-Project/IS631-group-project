import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"x-user-id": "qa_user_story_check"}

# 1. GET current cards
print("1. Getting current cards...")
cards_response = requests.get(f"{BASE_URL}/user_cards", headers=HEADERS)
cards = cards_response.json().get("user_cards", [])
print(f"Total cards: {len(cards)}")

if not cards:
    print("No cards to delete")
    exit(0)

# Pick the last card
card_to_delete = cards[-1]
user_card_id = card_to_delete["id"]
card_id = card_to_delete["card_id"]

print(f"\n2. Deleting card {user_card_id} (card_id={card_id})...")
delete_response = requests.delete(f"{BASE_URL}/user_cards/{user_card_id}", headers=HEADERS)
print(f"DELETE Status: {delete_response.status_code}")
print(f"DELETE Headers: {dict(delete_response.headers)}")
print(f"DELETE Body: '{delete_response.text}'")
print(f"DELETE Body Length: {len(delete_response.text)}")

if delete_response.status_code == 204:
    print("✅ DELETE SUCCESS!")
else:
    print(f"❌ DELETE FAILED")
    try:
        error_data = delete_response.json()
        print(f"Error JSON: {json.dumps(error_data, indent=2)}")
    except Exception as e:
        print(f"Could not parse error as JSON: {e}")

# 3. Verify deletion
print(f"\n3. Verifying deletion...")
cards_response = requests.get(f"{BASE_URL}/user_cards", headers=HEADERS)
cards_after = cards_response.json().get("user_cards", [])
card_still_exists = any(c["id"] == user_card_id for c in cards_after)
print(f"Total cards after: {len(cards_after)}")
print(f"Card still in list: {card_still_exists}")

if not card_still_exists and len(cards_after) == len(cards) - 1:
    print("✅ Deletion verified - card removed from list")
else:
    print("❌ Deletion not verified properly")
