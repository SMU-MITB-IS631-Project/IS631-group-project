from typing import Dict, Any

from passlib.context import CryptContext

from app.db.db import SessionLocal
from app.models.user_profile import UserProfile
from app.services.errors import ServiceError
from app.services.user_service import UserService

pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_users() -> Dict[str, Any]:
    """Load users data from the app.db database."""
    session = SessionLocal()
    try:
        service = UserService(session)
        return service.list_users()
    finally:
        session.close()

def get_user_by_username(username: str) -> UserProfile | None:
    """Fetch a user by username from the database."""
    session = SessionLocal()
    try:
        return UserService(session).get_user_by_username(username)
    finally:
        session.close()

def get_next_available_user_id() -> int:
    """Get the next available user_id, which is +1 from the latest user_id in the user_profile tab in app.db"""
    session = SessionLocal()
    try:
        return UserService(session).get_next_available_user_id()
    finally:
        session.close()

def create_user(username: str, password: str, name: str | None = None, email: str | None = None, benefits_preference: str | None = None) -> Dict[str, Any]:
    """Create a new user in the database. Returns user data as dictionary."""
    session = SessionLocal()
    try:
        service = UserService(session)
        return service.create_user(username, password, name, email, benefits_preference)
    except ServiceError as exc:
        # Preserve previous ValueError contract for duplicate username
        if exc.code == "CONFLICT":
            raise ValueError(exc.message) from exc
        raise
    finally:
        session.close()

def login_user():
    """
    Check if the user keyed in the right credentials
    """
