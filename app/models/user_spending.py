from sqlalchemy import Column, Numeric, String, DateTime, Date, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum as PyEnum
from decimal import Decimal

class UserSpendingCategory(PyEnum):
    Food = "Food"
    Travel = "Travel"
    Shopping = "Shopping"
    Bills = "Bills"
    Entertainment = "Entertainment"
    Others = "Others"

class UserSpending(Base):
    __tablename__ = "user_spending"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(10,2), nullable=False)
    category = Column(SAEnum(UserSpendingCategory), nullable=True)
    spending_date = Column(Date, default=date.today, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_spending")
    cards = relationship("Card", back_populates="user_spending") 

# Pydantic Models for Request/Response Validation
class UserSpendingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    card_id: int
    amount: Decimal
    category: UserSpendingCategory | None = None
    spending_date: date | None = None

class UserSpendingCreate(UserSpendingBase):
    pass

class UserSpendingResponse(UserSpendingBase):
    id: int
    created_date: datetime