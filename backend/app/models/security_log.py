from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.db.db import Base


class SecurityLog(Base):
    __tablename__ = "security_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_status = Column(String(50), nullable=False, default="success")
    source = Column(String(100), nullable=False)

    user_id = Column(Integer, ForeignKey("user_profile.id", ondelete="SET NULL"), nullable=True, index=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
