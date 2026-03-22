import sys
sys.path.insert(0, 'c:\\Users\\wenxu\\IS631-group-project\\backend')

from app.services.user_card_services import UserCardManagementService, ServiceError

print("=" * 60)
print("Testing UserCardManagementService.add_user_card()")
print("=" * 60)

try:
    # Create service with user context
    service = UserCardManagementService(user_id="qa_user_story_check")
    
    print("\n1. Service created successfully")
    print(f"   - User ID: qa_user_story_check")
    print(f"   - Cards master rows loaded: {len(service._cards_master_rows)}")
    print(f"   - Cards master IDs: {service._cards_master_ids}")
    
    # Try to add a card
    print("\n2. Attempting to add card 'uobone'...")
    card_data = {
        "card_id": "uobone",
        "refresh_day_of_month": 10,
        "annual_fee_billing_date": "2024-03-15",
        "cycle_spend_sgd": 250.50
    }
    
    result = service.add_user_card(card_data)
    print(f"✓ Card added successfully!")
    print(f"   Result: {result}")
    
except ServiceError as e:
    print(f"✗ ServiceError: {e.status_code} {e.code} - {e.message}")
    print(f"   Details: {e.details}")
except Exception as e:
    print(f"✗ Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
