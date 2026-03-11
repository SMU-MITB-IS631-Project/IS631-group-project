import sys
import os
from pathlib import Path
backend_dir = Path(__file__).resolve().parent
if backend_dir.name != "backend":
    backend_dir = backend_dir.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.user_card_services import UserCardManagementService

service = UserCardManagementService(user_id="qa_user_story_check")

# Check the path calculation
print(f"audit_log_file: {service._audit_log_file()}")
print(f"Exists: {os.path.exists(service._audit_log_file())}")

parent_dir = os.path.dirname(service._audit_log_file())
print(f"\nParent directory: {parent_dir}")
print(f"Parent exists: {os.path.exists(parent_dir)}")

if not os.path.exists(parent_dir):
    print("\nCreating parent directory...")
    os.makedirs(parent_dir, exist_ok=True)
    
print(f"\nAfter makedirs, parent exists: {os.path.exists(parent_dir)}")
