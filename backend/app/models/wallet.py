from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class WalletCard(BaseModel):
    card_id: str
    refresh_day_of_month: int = Field(..., ge=1, le=31)
    annual_fee_billing_date: str  # YYYY-MM-DD
    cycle_spend_sgd: float = Field(0, ge=0)

    @field_validator("annual_fee_billing_date")
    @classmethod
    def validate_annual_fee_billing_date(cls, v: str) -> str:
        """Ensure date is in ISO YYYY-MM-DD format, per API contract."""
        try:
            # fromisoformat will raise ValueError if format is invalid
            datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("annual_fee_billing_date must be YYYY-MM-DD") from exc
        return v


class WalletCardCreate(BaseModel):
    wallet_card: WalletCard


class WalletCardUpdate(BaseModel):
    refresh_day_of_month: Optional[int] = Field(None, ge=1, le=31)
    annual_fee_billing_date: Optional[str] = None
    cycle_spend_sgd: Optional[float] = Field(None, ge=0)


class WalletResponse(BaseModel):
    wallet: List[WalletCard]


class WalletCardResponse(BaseModel):
    wallet_card: WalletCard
