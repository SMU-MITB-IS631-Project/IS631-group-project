from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

class TransactionCreate(BaseModel):
    """Transaction creation request (from API contract)"""
    item: str
    amount_sgd: float
    card_id: str
    channel: str  # "online" or "offline"
    is_overseas: bool = False
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today if omitted

    @validator('item')
    def item_required(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('item is required')
        return v

    @validator('amount_sgd')
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError('amount_sgd must be greater than 0')
        return v

    @validator('channel')
    def channel_valid(cls, v):
        if v not in ['online', 'offline']:
            raise ValueError('channel must be "online" or "offline"')
        return v


class Transaction(TransactionCreate):
    """Transaction response model"""
    id: str

    class Config:
        from_attributes = True


class TransactionRequest(BaseModel):
    """Wrapper for API contract - POST body"""
    transaction: TransactionCreate
