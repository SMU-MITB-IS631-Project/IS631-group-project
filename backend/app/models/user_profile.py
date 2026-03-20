from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum
from app.db.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

from app.services.datetime_utils import utc_now

class BenefitsPreference(PyEnum):
    miles = "Miles"
    cashback = "Cashback"
    no_preference = "No preference"
    # Backward-compatible aliases (older code/tests referenced this casing)
    Miles = "Miles"
    Cashback = "Cashback"
    # Backward-compatible alias (older code/tests referenced this casing)
    No_preference = "No preference"

class UserProfile(Base):
    __tablename__ = "user_profile"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, unique=True)
    cognito_sub = Column(String, nullable=True, unique=True)  # Store Cognito user ID
    benefits_preference = Column(SAEnum(BenefitsPreference), nullable=False, default=BenefitsPreference.no_preference)
    created_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)

# Relationships with user-owned cards and transactions
    user_owned_cards = relationship("UserOwnedCard", back_populates="user_profile", cascade="all, delete-orphan")
    user_transactions = relationship("UserTransaction", back_populates="user_profile", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "cognito_sub": self.cognito_sub,
            "benefits_preference": self.benefits_preference.value if self.benefits_preference else None,
            "created_date": self.created_date,
        }

# Pydantic Models for Request/Response Validation
class UserProfileBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str | None = None
    benefits_preference: BenefitsPreference = BenefitsPreference.no_preference

# password in a separate model for creation because if it is in the base model, it will be exposed in responses
class UserProfileCreate(UserProfileBase):
    username: str
    email: str | None = None

class UserProfileResponse(UserProfileBase):
    id: int
    created_date: datetime

class UserProfileUpdate(UserProfileBase):
    pass
