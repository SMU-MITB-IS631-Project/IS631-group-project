from sqlalchemy import Column, Integer, Numeric, String, DateTime, Date, Boolean, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum as PyEnum
from decimal import Decimal
from typing import Optional

class TransactionCategory(PyEnum):
    food = "food"
    travel = "travel"
    shopping = "shopping"
    bills = "bills"
    entertainment = "entertainment"
    others = "others"

class TransactionChannel(PyEnum):
    online = "online"
    offline = "offline"

class UserTransaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("card_catalogue.card_id", ondelete="CASCADE"), nullable=False)
    amount_sgd = Column(Numeric(10,2), nullable=False)
    item = Column(String, nullable=False)
    channel = Column(SAEnum(TransactionChannel), nullable=False)
    category = Column(SAEnum(TransactionCategory), nullable=True)
    is_overseas = Column(Boolean, nullable=False)
    transaction_date = Column(Date, default=date.today, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_transactions")
    card_catalogue = relationship("CardCatalogue", back_populates="transactions")


# Create Pydantic models for Transaction
class TransactionCreate(BaseModel):
    """Transaction creation request (from API contract)"""
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    card_id: int
    amount_sgd: Decimal
    item: str
    channel: TransactionChannel  # "online" or "offline"
    is_overseas: bool = False
    transaction_date: date | None = None  # YYYY-MM-DD, defaults to today if omitted
    category: TransactionCategory | None = None

    @field_validator("item")
    @classmethod
    def item_required(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("item is required")
        return v

    @field_validator("amount_sgd")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount_sgd must be greater than 0")
        return v

    @field_validator("transaction_date", mode="before")
    @classmethod
    def set_transaction_date(cls, v):
        return date.today() if v is None else v

class TransactionResponse(TransactionCreate):
    """Transaction response model"""
    id: int
    created_date: datetime

class TransactionRequest(BaseModel):
    """Wrapper for API contract - POST body"""
    transaction: TransactionCreate
