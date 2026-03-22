from sqlalchemy import Column, Integer, String, Numeric, Enum as SAEnum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, field_validator
from enum import Enum as PyEnum
from decimal import Decimal
from datetime import date
from app.models.card_bonus_category import BonusCategory

# Python Enums for type safety
class BankEnum(str, PyEnum):
    # Canonical values
    DBS = "DBS"
    CITI = "CITI"
    Standard_Chartered = "Standard_Chartered"
    UOB = "UOB"

    # Legacy serialized names/values for backward compatibility
    Citi = "Citi"
    StandardChartered = "StandardChartered"
    dbs = "dbs"
    citi = "citi"
    standard_chartered = "standard_chartered"

class BenefitTypeEnum(str, PyEnum):
    miles = "miles"
    cashback = "cashback"
    both = "both"
    # Backward-compatible legacy names that may exist in older DB rows.
    Miles = "Miles"
    Cashback = "Cashback"
    MILES = "MILES"
    CASHBACK = "CASHBACK"
    BOTH = "BOTH"

class StatusEnum(str, PyEnum):
    valid = "valid"
    invalid = "invalid"
    # Backward-compatible legacy names that may exist in older DB rows.
    VALID = "VALID"
    INVALID = "INVALID"

# SQLAlchemy ORM Model
class CardCatalogue(Base):
    __tablename__ = "card_catalogue"
    
    card_id = Column(Integer, primary_key=True, index=True, unique=True)
    bank = Column(SAEnum(BankEnum), nullable=False)
    card_name = Column(String(255), nullable=False)
    benefit_type = Column(SAEnum(BenefitTypeEnum), nullable=False)
    base_benefit_rate = Column(Numeric(10, 4), nullable=False)
    status = Column(SAEnum(StatusEnum), nullable=False)
    
    # Table-level constraints
    __table_args__ = (
        UniqueConstraint('bank', 'card_name', name='uq_bank_card_name'),
        CheckConstraint('base_benefit_rate >= 0', name='ck_base_benefit_rate_non_negative'),
    )

    bonus_categories = relationship(
        "CardBonusCategory",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )
    user_owned_cards = relationship(
        "UserOwnedCard",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )
    transactions = relationship(
        "UserTransaction",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )

    bonus_categories = relationship(
        "CardBonusCategory",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )
    user_owned_cards = relationship(
        "UserOwnedCard",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )
    transactions = relationship(
        "UserTransaction",
        back_populates="card_catalogue",
        cascade="all, delete-orphan",
    )

# Pydantic Models for Request/Response
class CardCatalogueBase(BaseModel):
    bank: BankEnum
    card_name: str
    benefit_type: BenefitTypeEnum
    base_benefit_rate: Decimal
    status: StatusEnum
    
    @field_validator('card_name')
    @classmethod
    def card_name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Card name cannot be empty')
        return v.strip()
    
    @field_validator('base_benefit_rate')
    @classmethod
    def base_benefit_rate_non_negative(cls, v):
        if v < 0:
            raise ValueError('Base benefit rate must be non-negative')
        return v

class CardCatalogueCreate(CardCatalogueBase):
    """Schema for creating a new card catalogue entry"""
    pass

class CardCatalogueUpdate(BaseModel):
    """Schema for updating a card catalogue entry"""
    card_name: str | None = None
    benefit_type: BenefitTypeEnum | None = None
    base_benefit_rate: Decimal | None = None
    status: StatusEnum | None = None
    
    @field_validator('base_benefit_rate')
    @classmethod
    def base_benefit_rate_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError('Base benefit rate must be non-negative')
        return v

class CardCatalogueResponse(CardCatalogueBase):
    """Schema for API responses"""
    model_config = ConfigDict(from_attributes=True)
    card_id: int


class CardBonusRuleUpdate(BaseModel):
    bonus_category: BonusCategory
    bonus_benefit_rate: Decimal
    bonus_cap_in_dollar: int = 99999999
    bonus_minimum_spend_in_dollar: int = 0

    @field_validator('bonus_benefit_rate')
    @classmethod
    def bonus_benefit_rate_non_negative(cls, v):
        if v < 0:
            raise ValueError('bonus_benefit_rate must be non-negative')
        return v

    @field_validator('bonus_cap_in_dollar', 'bonus_minimum_spend_in_dollar')
    @classmethod
    def bonus_non_negative(cls, v):
        if v < 0:
            raise ValueError('Values must be non-negative')
        return v


class CardRewardUpdatePayload(BaseModel):
    base_benefit_rate: Decimal | None = None
    bonus_rules: list[CardBonusRuleUpdate] | None = None
    effective_date: date

    @field_validator('base_benefit_rate')
    @classmethod
    def base_rate_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError('base_benefit_rate must be non-negative')
        return v


class CardRewardUpdateRequest(BaseModel):
    reward_update: CardRewardUpdatePayload
