from typing import Optional
from sqlalchemy import Column, Date, Integer, String, DateTime, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, field_validator, Field
from sqlalchemy.orm import relationship
from datetime import timedelta, date
from enum import Enum as PyEnum

class UserOwnedCardStatus(PyEnum):
    active = "Active"
    inactive = "Suspended"
    closed = "Expired"

def get_billing_cycle_date():
    # return last day of current month
    today = date.today()
    # last day of the month
    if today.month == 12:
        return date(today.year, 12, 31)
    else:
        next_month = date(today.year, today.month + 1, 1)
        return next_month - timedelta(days=1)

class UserOwnedCard(Base):
    __tablename__ = "user_owned_cards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("card_catalogue.card_id", ondelete="CASCADE"), nullable=False)
    card_expiry_date = Column(Date, default=lambda: date(9999,1,1), nullable=False)
    billing_cycle_refresh_date = Column(Date, default=get_billing_cycle_date, nullable=False)
    status = Column(SAEnum(UserOwnedCardStatus), nullable=False, default=UserOwnedCardStatus.active)
    cycle_spend_sgd: float = Field(0, ge=0)

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_owned_cards")
    card_catalogue = relationship("CardCatalogue", back_populates="user_owned_cards")

# Pydantic Models for Request/Response Validation
class UserOwnedCardBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    card_id: int
    card_expiry_date: date = date(9999,1,1)
    billing_cycle_refresh_date: date = Field(default_factory=get_billing_cycle_date)
    status: UserOwnedCardStatus = UserOwnedCardStatus.active
    cycle_spend_sgd: float = Field(0, ge=0)


class UserOwnedCardCreate(UserOwnedCardBase):
    pass

class UserOwnedCardUpdate(BaseModel):
    billing_cycle_refresh_date: Optional[date] = None
    card_expiry_date: Optional[date] = None
    cycle_spend_sgd: Optional[float] = Field(None, ge=0)
    status: Optional[UserOwnedCardStatus] = None

class UserOwnedCardResponse(UserOwnedCardBase):
    pass


class UserOwnedCarWrappedResponse(BaseModel):
    wallet: list[UserOwnedCardResponse]