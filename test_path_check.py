import sys
sys.path.insert(0, r"c:\Users\wenxu\IS631-group-project\backend")

from app.services.user_card_services import UserCardManagementService
import os

service = UserCardManagementService(user_id="qa_user_story_check")

# Check the path calculation
print(f"audit_log_file: {service._audit_log_file()}")
print(f"Exists: {os.path.exists(service._audit_log_file())}")
print(f"Expected path: c:\\Users\\wenxu\\IS631-group-project\\backend\\data\\user_card_audit_log.json")

parent_dir = os.path.dirname(service._audit_log_file())
print(f"\nParent directory: {parent_dir}")
print(f"Parent exists: {os.path.exists(parent_dir)}")

if not os.path.exists(parent_dir):
    print("\nCreating parent directory...")
    os.makedirs(parent_dir, exist_ok=True)
    
print(f"\nAfter makedirs, parent exists: {os.path.exists(parent_dir)}")
