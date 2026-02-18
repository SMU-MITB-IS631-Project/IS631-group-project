from typing import Dict, Any
from app.db.db import SessionLocal
from app.models.user_profile import UserProfile, BenefitsPreference

def get_users() -> Dict[str, Any]:
    """Load users data from the app.db database."""    
    session = SessionLocal()
    try:
        users = session.query(UserProfile).all()
        return {user.id: user.to_dict() for user in users}
    finally:
        session.close()

def get_next_available_user_id() -> int:
    """Get the next available user_id, which is +1 from the latest user_id in the user_profile tab in app.db"""    
    session = SessionLocal()
    try:
        max_user = session.query(UserProfile).order_by(UserProfile.id.desc()).first()
        next_id = (max_user.id + 1) if max_user else 1
        return next_id
    finally:
        session.close()

def create_user(username: str, password: str, name: str | None = None, email: str | None = None, benefits_preference: str | None = None) -> Dict[str, Any]:
    """Create a new user in the database. Returns user data as dictionary."""
    session = SessionLocal()
    try:
        # Check if username already exists
        existing_user = session.query(UserProfile).filter(UserProfile.username == username).first()
        if existing_user:
            raise ValueError("Username already exists")
        
        # Map benefits_preference string to enum
        pref_enum = BenefitsPreference.No_preference
        if benefits_preference:
            try:
                pref_enum = BenefitsPreference(benefits_preference)
            except ValueError:
                pref_enum = BenefitsPreference.No_preference
        
        # Create new user
        new_user = UserProfile(
            username=username,
            password_hash=password,
            name=name,
            email=email,
            benefits_preference=pref_enum
        )
        session.add(new_user)
        session.commit()
        return new_user.to_dict()
    finally:
        session.close()

