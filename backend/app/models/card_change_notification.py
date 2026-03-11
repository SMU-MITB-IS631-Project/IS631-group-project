from datetime import date, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String

from app.db.db import Base
from app.services.datetime_utils import utc_now


class CardChangeNotification(Base):
    __tablename__ = "card_change_notification"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("card_catalogue.card_id", ondelete="CASCADE"), nullable=False, index=True)
    card_name = Column(String(255), nullable=False)
    changed_fields = Column(JSON, nullable=False, default=dict)
    effective_date = Column(Date, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_date = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class CardChangeNotificationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    card_id: int
    card_name: str
    changed_fields: dict
    effective_date: date
    is_read: bool = False


class CardChangeNotificationResponse(CardChangeNotificationBase):
    id: int
    created_date: datetime
