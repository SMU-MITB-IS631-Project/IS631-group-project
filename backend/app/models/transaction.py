from sqlalchemy import Column, Integer, Numeric, String, DateTime, Date, Boolean, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum as PyEnum
from decimal import Decimal
from typing import Optional


def _enum_values(enum_cls):
    # Persist enum .value strings in DB instead of member names.
    return [member.value for member in enum_cls]


def _normalize_enum_input(value, enum_cls):
    """Normalize free-form enum strings from clients to enum members."""
    if value is None or isinstance(value, enum_cls):
        return value

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return value

        lowered = raw.lower()
        # Accept enum values case-insensitively.
        for member in enum_cls:
            if str(member.value).lower() == lowered:
                return member

        # Accept enum member names case-insensitively.
        for member in enum_cls:
            if member.name.lower() == lowered:
                return member

    return value

class TransactionCategory(PyEnum):
    food = "Food"
    transport = "Transport"
    fashion = "Fashion"
    entertainment = "Entertainment"
    others = "Others"
    # Backward-compatible legacy names in persisted enum strings.
    Food = "Food"
    Transport = "Transport"
    Fashion = "Fashion"
    Entertainment = "Entertainment"
    Others = "Others"

class TransactionChannel(PyEnum):
    online = "online"
    offline = "offline"
    # Backward-compatible legacy values found in older data.
    Online = "Online"
    Offline = "Offline"

class TransactionStatus(PyEnum):
    Active = "active"
    DeletedWithCard = "deleted_with_card"
    # Backward-compatible legacy values found in older data.
    ActiveLegacy = "Active"
    DeletedWithCardLegacy = "DeletedWithCard"

class UserTransaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(Integer, ForeignKey("card_catalogue.card_id", ondelete="CASCADE"), nullable=False)
    amount_sgd = Column(Numeric(10,2), nullable=False)
    item = Column(String, nullable=False)
    channel = Column(SAEnum(TransactionChannel, values_callable=_enum_values), nullable=False)
    category = Column(SAEnum(TransactionCategory, values_callable=_enum_values), nullable=True)
    is_overseas = Column(Boolean, nullable=False)
    transaction_date = Column(Date, default=date.today, nullable=False)
    status = Column(SAEnum(TransactionStatus, values_callable=_enum_values), default=TransactionStatus.Active, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Historical reward tracking
    total_reward = Column(Numeric(10,2), nullable=True)  # Calculated reward amount for this transaction

    # Relationship with UserProfile
    user_profile = relationship("UserProfile", back_populates="user_transactions")
    card_catalogue = relationship("CardCatalogue", back_populates="transactions")


# Create Pydantic models for Transaction
class TransactionCreate(BaseModel):
    """Transaction creation request (from API contract)"""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    user_id: int | None = None
    card_id: int
    amount_sgd: Decimal
    item: str
    channel: TransactionChannel  # "online" or "offline"
    is_overseas: bool = False
    transaction_date: date | None = Field(default=None, alias="date")  # YYYY-MM-DD, defaults to today if omitted
    category: TransactionCategory | None = None
    status: TransactionStatus = TransactionStatus.Active

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

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        return _normalize_enum_input(v, TransactionChannel)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        return _normalize_enum_input(v, TransactionCategory)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        return _normalize_enum_input(v, TransactionStatus)

    @field_validator("transaction_date", mode="before")
    @classmethod
    def set_transaction_date(cls, v):
        return date.today() if v is None else v

class TransactionResponse(TransactionCreate):
    """Transaction response model"""
    id: int
    created_date: datetime

class TransactionUpdate(BaseModel):
    """Transaction update request - all fields optional"""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    card_id: int | None = None
    amount_sgd: Decimal | None = None
    item: str | None = None
    channel: TransactionChannel | None = None
    is_overseas: bool | None = None
    transaction_date: date | None = Field(default=None, alias="date")
    category: TransactionCategory | None = None

    @field_validator("item")
    @classmethod
    def item_not_empty(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError("item cannot be empty")
        return v

    @field_validator("amount_sgd")
    @classmethod
    def amount_positive_if_provided(cls, v):
        if v is not None and v <= 0:
            raise ValueError("amount_sgd must be greater than 0")
        return v

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, v):
        return _normalize_enum_input(v, TransactionChannel)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v):
        return _normalize_enum_input(v, TransactionCategory)

class TransactionRequest(BaseModel):
    """Wrapper for API contract - POST body"""
    transaction: TransactionCreate
