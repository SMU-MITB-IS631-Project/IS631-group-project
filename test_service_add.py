import sys
sys.path.insert(0, 'c:\\Users\\wenxu\\IS631-group-project\\backend')

from app.services.user_card_services import UserCardManagementService

print("Testing UserCardManagementService after __init__ fix...")
service = UserCardManagementService(user_id="qa_user_story_check")

print(f"\n✓ Service created successfully")
print(f"Cards loaded: {len(service._cards_master_rows)}")
print(f"Card IDs: {service._cards_master_ids}")
print(f"\nCards master rows:")
for row in service._cards_master_rows:
    print(f"  {row}")

# Test add_user_card
print("\n\nTesting add_user_card with card_id='1'...")
try:
    result = service.add_user_card({
        "card_id": "1",
        "refresh_day_of_month": 10,
        "annual_fee_billing_date": "2024-03-15",
        "cycle_spend_sgd": 250.50
    })
    print(f"✓ Card added successfully!")
    print(f"Result: {result}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
