from typing import Optional
from sqlalchemy import Column, Date, Integer, Enum as SAEnum, ForeignKey, Float
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import relationship
from datetime import timedelta, date
from enum import Enum as PyEnum

class UserOwnedCardStatus(PyEnum):
    # Backward-compatible aliases (older code/tests used title-case names)
    Active = "Active"
    Inactive = "Suspended"
    Closed = "Expired"

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
    billing_cycle_refresh_day_of_month = Column(Integer, nullable=False, default=1)
    status = Column(SAEnum(UserOwnedCardStatus), nullable=False, default=UserOwnedCardStatus.Active)
    cycle_spend_sgd = Column(Float, nullable=False, default=0.0)

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_owned_cards")
    card_catalogue = relationship("CardCatalogue", back_populates="user_owned_cards")

# Pydantic Models for Request/Response Validation
class UserOwnedCardBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    card_id: int

class UserOwnedCardCreate(UserOwnedCardBase):
    card_expiry_date: date = date(9999,1,1)
    billing_cycle_refresh_date: date = Field(default_factory=get_billing_cycle_date)
    billing_cycle_refresh_day_of_month: int = Field(1, ge=1, le=31) 

class UserOwnedCardUpdate(BaseModel):
    billing_cycle_refresh_date: Optional[date] = None
    billing_cycle_refresh_day_of_month: Optional[int] = Field(None, ge=1, le=31)
    card_expiry_date: Optional[date] = None
    status: Optional[UserOwnedCardStatus] = None

class UserOwnedCardResponse(UserOwnedCardBase):
    id: int | None = None  # Optional for JSON-backed wallet
    card_expiry_date: date
    billing_cycle_refresh_date: date
    billing_cycle_refresh_day_of_month: int
    status: UserOwnedCardStatus

class UserOwnedCardWrappedResponse(BaseModel):
    """Envelope response for wallet endpoints."""

    wallet: list[UserOwnedCardResponse]
