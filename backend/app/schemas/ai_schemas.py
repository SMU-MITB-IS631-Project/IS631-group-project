"""
AI Explanation Engine Schemas - DTOs for card recommendation explanations.

This module defines Pydantic models for structured data transfer between:
- Recommender Engine → Explanation Service
- Explanation Service → API Response Layer

Design Philosophy:
- Explicit field validation to prevent hallucinations
- Ground truth mapping to database entities
- Type safety for numerical calculations
"""

from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.card_catalogue import BenefitTypeEnum as BenefitType
class RecommendationContext(BaseModel):
    """
    Core DTO containing all ground truth data for explanation generation.
    
    This schema ensures the AI never hallucinates rates or caps by explicitly
    passing database-verified values.
    
    Usage:
        context = RecommendationContext(
            card_id=3,
            card_name="DBS Live Fresh",
            bank="DBS",
            benefit_type=BenefitType.CASHBACK,
            category="Fashion",
            base_rate=Decimal("0.01"),
            bonus_rate=Decimal("0.035"),
            is_bonus_eligible=True,
            transaction_amount=Decimal("120.00")
        )
    """
    model_config = ConfigDict(use_enum_values=True)
    
    # Card Identity (from CardCatalogue)
    card_id: int = Field(..., description="Primary key from card_catalogue")
    card_name: str = Field(..., description="Official card product name")
    bank: str = Field(..., description="Issuing bank")
    benefit_type: BenefitType = Field(..., description="Reward type: MILES/CASHBACK/BOTH")
    
    # Transaction Context
    category: str = Field(..., description="Spending category for this transaction")
    transaction_amount: Decimal = Field(..., gt=0, description="Transaction amount in SGD")
    merchant_name: Optional[str] = Field(None, description="Merchant name if available")
    
    # Reward Calculation Ground Truth (from CardBonusCategory + CardCatalogue)
    base_rate: Decimal = Field(..., ge=0, description="Base benefit rate (e.g., 0.01 = 1%)")
    bonus_rate: Optional[Decimal] = Field(None, ge=0, description="Applied bonus rate if eligible")
    is_bonus_eligible: bool = Field(default=False, description="Whether bonus rate applies")
    
    # Optional: Bonus constraints (from CardBonusCategory)
    bonus_cap_sgd: Optional[int] = Field(None, description="Monthly cap in SGD (if applicable)")
    bonus_min_spend_sgd: Optional[int] = Field(None, description="Minimum spend requirement")
    
    # Calculated Values
    total_reward_value: Optional[Decimal] = Field(None, description="Computed reward for this txn")
    
    @field_validator("base_rate", "bonus_rate")
    @classmethod
    def validate_rate_bounds(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure rates are non-negative. Miles-per-dollar rates legitimately exceed 1.0."""
        if v is not None and v < 0:
            raise ValueError("Rate must be non-negative.")
        return v
    
    @field_validator("card_name", "bank")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Prevent empty card names/banks"""
        if not v.strip():
            raise ValueError("Card name and bank must be non-empty")
        return v.strip()


class ExplanationRequest(BaseModel):
    """
    API request schema for explanation generation.
    
    Example:
        POST /api/v1/card-reasoner/explain
        {
            "recommendation": {
                "card_id": 3,
                "card_name": "DBS Live Fresh",
                "bank": "DBS",
                "benefit_type": "CASHBACK",
                "category": "Fashion",
                "transaction_amount": 120.00,
                "base_rate": 0.01,
                "bonus_rate": 0.035,
                "is_bonus_eligible": true
            },
            "comparison_cards": [...]
        }
    """
    recommendation: RecommendationContext = Field(..., description="The recommended card context")
    comparison_cards: List[RecommendationContext] = Field(
        default_factory=list,
        description="Alternative cards considered (for comparative explanations)"
    )
    user_id: Optional[int] = Field(None, description="User ID for personalization")


class ExplanationResponse(BaseModel):
    """
    API response containing the generated explanation and metadata.
    
    Example:
        {
            "explanation": "The DBS Live Fresh card gives you 3.5% cashback on Fashion...",
            "card_id": 3,
            "category": "Fashion",
            "total_reward": 4.20,
            "model_used": "gpt-4o-mini",
            "is_fallback": false
        }
    """
    explanation: str = Field(..., description="Natural language explanation for end users")
    card_id: int = Field(..., description="Recommended card ID")
    category: str = Field(..., description="Transaction category")
    total_reward: Optional[Decimal] = Field(None, description="Calculated reward value")
    
    # Metadata for debugging/analytics
    model_used: str = Field(default="template", description="LLM model or 'template' for fallback")
    is_fallback: bool = Field(default=False, description="Whether fallback logic was used")
    generation_time_ms: Optional[int] = Field(None, description="Time taken to generate")


class AuditLogEntry(BaseModel):
    """
    Structured audit log for compliance and analytics.
    
    Stored in: backend/data/user_card_audit_log.json (or future DB table)
    """
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    event_type: str = Field(default="explanation_generated", description="Event type")
    user_id: Optional[int] = Field(None, description="User ID if authenticated")
    card_id: int = Field(..., description="Recommended card ID")
    category: str = Field(..., description="Transaction category")
    model_used: str = Field(..., description="LLM model identifier")
    prompt_hash: Optional[str] = Field(None, description="Hash of prompt for deduplication")
    response_length: int = Field(..., description="Character count of explanation")
