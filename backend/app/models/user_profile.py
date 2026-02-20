from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum
from app.db.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

class BenefitsPreference(PyEnum):
    Miles = "miles"
    Cashback = "cashback"
    No_preference = "no preference"

class UserProfile(Base):
    __tablename__ = "user_profile"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, unique=True)
    benefits_preference = Column(SAEnum(BenefitsPreference), nullable=False, default=BenefitsPreference.No_preference)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

# Relationships with user-owned cards and transactions
    user_owned_cards = relationship("UserOwnedCard", back_populates="user_profile", cascade="all, delete-orphan")
    user_transactions = relationship("UserTransaction", back_populates="user_profile", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "benefits_preference": self.benefits_preference.value if self.benefits_preference else None,
            "created_date": self.created_date,
        }

# Pydantic Models for Request/Response Validation
class UserProfileBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    name: str | None = None
    email: str | None = None
    benefits_preference: BenefitsPreference = BenefitsPreference.No_preference

# password in a separate model for creation because if it is in the base model, it will be exposed in responses
class UserProfileCreate(UserProfileBase):
    password: str

class UserProfileResponse(UserProfileBase):
    id: int
    created_date: datetime

class UserProfileUpdate(UserProfileBase):
    password: str

class LoginPayload(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    message: str
    user_id: int