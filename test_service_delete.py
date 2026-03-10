import sys
sys.path.insert(0, r"c:\Users\wenxu\IS631-group-project\backend")

from app.services.user_card_services import UserCardManagementService
import json

# Create service
service = UserCardManagementService(user_id="qa_user_story_check")

# Get cards
cards = service.list_user_cards()
print(f"Cards before delete: {len(cards)}")
for card in cards:
    print(f"  - {card['id']}: card_id={card['card_id']}")

if cards:
    card_to_delete = cards[0]["id"]
    print(f"\nAttempting to delete: {card_to_delete}")
    
    try:
        service.delete_user_card(card_to_delete)
        print("✅ DELETE completed without exception")
    except Exception as e:
        print(f"❌ DELETE raised exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Check cards after
    cards_after = service.list_user_cards()
    print(f"\nCards after delete: {len(cards_after)}")
    for card in cards_after:
        print(f"  - {card['id']}: card_id={card['card_id']} (is_active={card.get('is_active', True)})")
    
    # Check audit log
    with open(r"c:\Users\wenxu\IS631-group-project\backend\data\user_card_audit_log.json") as f:
        audit = json.load(f)
        print(f"\nAudit log entries: {len(audit['events'])}")
        if audit['events']:
            print(f"Latest entry: {audit['events'][-1]}")
else:
    print("No cards to delete")
