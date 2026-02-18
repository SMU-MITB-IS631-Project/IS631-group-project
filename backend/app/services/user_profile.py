import csv
import os
from typing import Dict, Any, List
from app.db.db import SessionLocal
from app.models.user_profile import UserProfile, BenefitsPreference

from app.services.data_service import USERS_FILE, _load_json, _save_json

def get_users() -> Dict[str, Any]:
    """Load users data from the app.db database."""    
    session = SessionLocal()
    try:
        users = session.query(UserProfile).all()
        return {user.id: user.to_dict() for user in users}
    finally:
        session.close()

def get_user_profile_by_id(user_id: int) -> Dict[str, Any] | None:
    """Fetch a user profile by ID. Returns None if not found."""
    session = SessionLocal()
    try:
        user = session.query(UserProfile).filter(UserProfile.id == user_id).first()
        return user.to_dict() if user else None
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

def create_user(username: str, password_hash: str, name: str | None = None, email: str | None = None) -> Dict[str, Any]:
    """Create a new user in the database. Returns user data as dictionary."""
    session = SessionLocal()
    try:
        # Check if username already exists
        existing_user = session.query(UserProfile).filter(UserProfile.username == username).first()
        if existing_user:
            return existing_user.to_dict()
        
        # Create new user
        new_user = UserProfile(
            username=username,
            password_hash=password_hash,
            name=name,
            email=email,
            benefits_preference=BenefitsPreference.No_preference
        )
        session.add(new_user)
        session.commit()
        return new_user.to_dict()
    finally:
        session.close()

