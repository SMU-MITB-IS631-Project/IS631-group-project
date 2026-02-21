from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, field_validator, Field
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta, UTC
from enum import Enum as PyEnum

class UserOwnedCardStatus(PyEnum):
    Active = "Active"
    Inactive = "Suspended"
    Closed = "Expired"

def get_billing_cycle_date():
    # return last day of current month
    today = datetime.now(UTC).replace(tzinfo=None)
    # last day of the month
    if today.month == 12:
        return datetime(today.year, 12, 31)
    else:
        next_month = datetime(today.year, today.month + 1, 1)
        return next_month - timedelta(days=1)

class UserOwnedCard(Base):
    __tablename__ = "user_owned_cards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("card_catalogue.card_id", ondelete="CASCADE"), nullable=False)
    card_expiry_date = Column(DateTime, default=lambda: datetime(9999,1,1), nullable=False)
    billing_cycle_refresh_date = Column(DateTime, default=get_billing_cycle_date, nullable=False)
    status = Column(SAEnum(UserOwnedCardStatus), nullable=False, default=UserOwnedCardStatus.Active)

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_owned_cards")
    card_catalogue = relationship("CardCatalogue", back_populates="user_owned_cards")

# Pydantic Models for Request/Response Validation
class UserOwnedCardBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    card_id: int
    card_expiry_date: datetime = datetime(9999,1,1)
    billing_cycle_refresh_date: datetime = Field(default_factory=get_billing_cycle_date)
    status: UserOwnedCardStatus = UserOwnedCardStatus.Active

class UserOwnedCardCreate(UserOwnedCardBase):
    pass

class UserOwnedCardResponse(UserOwnedCardBase):
    id: int