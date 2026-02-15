from sqlalchemy import Column, Integer, Numeric, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.db import Base
from pydantic import BaseModel, ConfigDict, field_validator
from enum import Enum as PyEnum
from decimal import Decimal


class BonusCategory(PyEnum):
    Food = "Food"
    Transport = "Transport"
    Entertainment = "Entertainment"
    Fashion = "Fashion"
    All = "All"


class CardBonusCategory(Base):
    __tablename__ = "card_bonus_category"

    card_bonuscat_id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    bonus_category = Column(SAEnum(BonusCategory), nullable=False)
    bonus_benefit_rate = Column(Numeric(10, 4), nullable=False)
    bonus_cap_in_dollar = Column(Integer, nullable=False, default=99999999)
    bonus_minimum_spend_in_dollar = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("card_id", "bonus_category", name="uq_card_bonus_category_per_card"),
    )

    card = relationship("Card", back_populates="bonus_categories")


class CardBonusCategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_id: int
    bonus_category: BonusCategory
    bonus_benefit_rate: Decimal
    bonus_cap_in_dollar: int = 99999999
    bonus_minimum_spend_in_dollar: int = 0

    @field_validator("bonus_benefit_rate")
    @classmethod
    def bonus_benefit_rate_non_negative(cls, v: Decimal):
        if v < 0:
            raise ValueError("bonus_benefit_rate must be non-negative")
        return v

    @field_validator("bonus_cap_in_dollar", "bonus_minimum_spend_in_dollar")
    @classmethod
    def non_negative_integers(cls, v: int):
        if v < 0:
            raise ValueError("Values must be non-negative")
        return v


class CardBonusCategoryCreate(CardBonusCategoryBase):
    pass


class CardBonusCategoryResponse(CardBonusCategoryBase):
    card_bonuscat_id: int
