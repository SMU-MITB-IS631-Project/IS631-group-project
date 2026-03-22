from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user_profile import BenefitsPreference, UserProfile
from app.services.errors import ServiceError


class UserProfileService:
    def __init__(self, db: Session):
        self.db = db

    # Admin role
    def get_all_user_profiles(self):
        """Return all users as a dictionary keyed by user_id."""
        return self.db.query(UserProfile).all()

    # User role
    def get_user_profile(self, cognitosub: str) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter(UserProfile.cognito_sub == cognitosub).first()

    def update_user_profile(self, cognitosub: str, name: Optional[str] = None, benefits_preference: Optional[BenefitsPreference] = None) -> UserProfile:
        """Update a user's profile with the provided fields."""
        user = self.db.query(UserProfile).filter(UserProfile.cognito_sub == cognitosub).first()
        if not user:
            raise ServiceError(status_code=404, code="NOT_FOUND", message="User not found.", details={})

        if name is not None:
            user.name = name
        if benefits_preference is not None:
            user.benefits_preference = benefits_preference

        self.db.commit()
        self.db.refresh(user)
        return user

    # Creation of profile after Cognito registration
    def create_user_profile(self, username: str, email: str, cognitosub: str, name: Optional[str] = None, benefits_preference: BenefitsPreference = BenefitsPreference.no_preference) -> UserProfile:
        """Create a new user profile linked to a Cognito user."""
        existing_user = self.get_user_profile(cognitosub)
        if existing_user:
            raise ServiceError(
                status_code=409,
                code="CONFLICT",
                message="User profile already exists for this Cognito user.",
                details={},
            )

        username_conflict = self.db.query(UserProfile).filter(UserProfile.username == username).first()
        if username_conflict:
            raise ServiceError(status_code=409, code="CONFLICT", message="Username already exists.", details={})

        if email:
            email_conflict = self.db.query(UserProfile).filter(UserProfile.email == email).first()
            if email_conflict:
                raise ServiceError(status_code=409, code="CONFLICT", message="Email already exists.", details={})

        new_user = UserProfile(
            username=username,
            email=email,
            name=name,
            benefits_preference=benefits_preference,
            cognito_sub=cognitosub
        )
        self.db.add(new_user)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ServiceError(
                status_code=409,
                code="CONFLICT",
                message="Username or email already exists.",
                details={},
            )
        self.db.refresh(new_user)
        return new_user
    
    # Delete user profile (need to also delete Cognito user separately)
    def delete_user_profile(self, cognitosub: str) -> None:
        user = self.get_user_profile(cognitosub)
        if not user:
            raise ServiceError(status_code=404, code="NOT_FOUND", message="User not found.", details={})
        self.db.delete(user)
        self.db.commit()
