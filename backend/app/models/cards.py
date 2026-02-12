from sqlalchemy import Column, Integer, Numeric, String, DateTime, Date, Enum as SAEnum, ForeignKey
from app.db.db import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import relationship
from datetime import datetime, date
from enum import Enum as PyEnum
from decimal import Decimal

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)

    # Relationships with user_owned_cards and user_spending tables
    user_owned_cards = relationship("UserOwnedCard", back_populates="cards", cascade="all, delete-orphan")
    user_spending = relationship("UserSpending", back_populates="cards", cascade="all, delete-orphan")