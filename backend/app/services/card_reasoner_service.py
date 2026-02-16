"""
Card Reasoner Service - Generates natural language explanations for credit card recommendations.
Optimized for Singapore users, focused on value maximization.

High-impact design decisions:
- Async-ready for LLM calls (non-blocking)
- Modular prompt engineering (easy to iterate)
- Graceful error handling with sensible fallback
- Audit logging for compliance & analytics
- Simple input validation
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, validator
from openai import AsyncOpenAI, OpenAI

# Initialize clients
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================================
# PYDANTIC MODELS - Type safety & validation
# ============================================================================

class BenefitTypeEnum(str, Enum):
    """Credit card benefit types"""
    MILES = "Miles"
    CASHBACK = "Cashback"
    BOTH = "Both"


class TransactionInput(BaseModel):
    """Validated transaction input"""
    merchant_name: str = Field(..., example="ZARA")
    amount: float = Field(..., gt=0, example=120.00)
    category: str = Field(..., example="Fashion")
    
    @validator("amount")
    def validate_amount(cls, v):
        if v < 0 or v > 1_000_000:
            raise ValueError("Amount must be between 0 and 1,000,000")
        return v


class CardDetail(BaseModel):
    """Credit card details with calculated values"""
    Card_ID: int
    Bank: str
    Card_Name: str
    Benefit_type: BenefitTypeEnum
    base_benefit_rate: float = Field(..., ge=0)
    applied_bonus_rate: float = Field(..., ge=0)
    total_calculated_value: float = Field(..., ge=0)


class ExplanationRequest(BaseModel):
    """API request for card explanation"""
    transaction: TransactionInput
    recommended_card: CardDetail
    comparison_cards: List[CardDetail] = Field(default_factory=list)


class AuditLogEntry(BaseModel):
    """Audit log entry"""
    event_type: str = "GENAI_TRIGGERED"
    timestamp: str
    model_used: str
    merchant_name: str
    category: str
    recommended_card_id: int
    recommended_card_name: str
    num_comparisons: int
    completion_tokens: Optional[int] = None
    error: Optional[str] = None


class ExplanationResponse(BaseModel):
    """API response with explanation"""
    explanation: str
    audit_log_entry: AuditLogEntry


# ============================================================================
# PROMPT ENGINEERING - Singapore context, value-focused
# ============================================================================

def build_system_prompt() -> str:
    """
    System prompt for card reasoning.
    Optimized for:
    - Singapore context
    - General users (non-finance experts)
    - Clear value explanation
    """
    return """You are a friendly financial advisor in Singapore who explains credit card recommendations in simple, jargon-free language.

Your goal: Help users understand WHY a specific card was chosen based on value maximization.

Key principles:
1. **Be specific** - Reference actual merchants, amounts, and rewards (e.g., "You'll earn 3.5% cashback = $4.20 on this $120 purchase")
2. **Simplify benefits** - Miles → "Free flights" or "Travel points", Cashback → "Money back"
3. **Singapore context** - Reference local spending patterns (hawker centers, malls, online shopping)
4. **Value-focused** - Emphasize money/miles earned, not card prestige
5. **Brief** - Keep explanations under 3 sentences
6. **No jargon** - Avoid "APR", "annual fee waiver", "rotating categories"

Generate an explanation that a 25-year-old Singaporean would understand without financial background."""


def build_user_prompt(
    transaction: TransactionInput,
    recommended_card: CardDetail,
    comparison_cards: List[CardDetail]
) -> str:
    """
    User prompt with transaction and card context.
    
    Structure:
    1. Transaction details
    2. Recommended card benefits
    3. Comparison with runner-ups (if any)
    """
    
    # Format transaction
    transaction_str = f"""Transaction:
- Merchant: {transaction.merchant_name}
- Category: {transaction.category}
- Amount: SGD {transaction.amount:.2f}"""

    # Format recommended card
    total_reward_value = transaction.amount * (
        recommended_card.base_benefit_rate + recommended_card.applied_bonus_rate
    )
    benefit_unit = "miles" if "Mile" in recommended_card.Benefit_type else "SGD"
    
    recommended_str = f"""Recommended Card:
- {recommended_card.Bank} {recommended_card.Card_Name}
- Benefit type: {recommended_card.Benefit_type}
- You'll earn: {total_reward_value:.2f} {benefit_unit} on this transaction
- Card's calculated value for this transaction: SGD {recommended_card.total_calculated_value:.2f}"""

    # Format comparisons if available
    comparison_str = ""
    if comparison_cards:
        comparison_str = "\nAlternatives considered:"
        for card in comparison_cards:
            comparison_str += f"\n- {card.Bank} {card.Card_Name} (would give SGD {card.total_calculated_value:.2f})"

    # Full prompt
    prompt = f"""{transaction_str}

{recommended_str}{comparison_str}

Explain in 2-3 sentences why this card was chosen. Be specific about the rewards earned on THIS transaction. Assume the user is a typical Singaporean (no finance background)."""
    
    return prompt


# ============================================================================
# LLM INTEGRATION - Sync & async ready
# ============================================================================

def _call_openai_sync(system_prompt: str, user_prompt: str) -> str:
    """
    Call OpenAI synchronously.
    Fallback to template if API fails.
    """
    if not client:
        return _fallback_explanation()
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-optimized, good quality
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=150,
            timeout=5.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] LLM call failed: {e}")
        return _fallback_explanation()


async def _call_openai_async(system_prompt: str, user_prompt: str) -> str:
    """
    Call OpenAI asynchronously.
    Non-blocking for high concurrency.
    """
    if not async_client:
        return _fallback_explanation()
    
    try:
        response = await asyncio.wait_for(
            async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            ),
            timeout=5.0
        )
        return response.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        print("[WARN] LLM call timed out")
        return _fallback_explanation()
    except Exception as e:
        print(f"[WARN] LLM call failed: {e}")
        return _fallback_explanation()


def _fallback_explanation() -> str:
    """
    Fallback explanation when LLM unavailable.
    Template-based, always works.
    """
    return "This card offers the best value for your purchase based on rewards rates and bonuses. You'll earn more points/cashback compared to other cards in your wallet."


# ============================================================================
# PUBLIC API - Sync (primary) & async variants
# ============================================================================

def generate_explanation(request: ExplanationRequest) -> ExplanationResponse:
    """
    Generate explanation for card recommendation (synchronous).
    
    Args:
        request: Validated explanation request with transaction, recommended card, comparisons
        
    Returns:
        ExplanationResponse with explanation text and audit log
        
    High-impact design:
    - Modular (easy to test, iterate)
    - Graceful error handling (LLM failure → fallback)
    - Audit logging (compliance, analytics)
    """
    
    # Validate inputs
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        request.transaction,
        request.recommended_card,
        request.comparison_cards
    )
    
    # Get explanation from LLM
    explanation = _call_openai_sync(system_prompt, user_prompt)
    
    # Create audit log
    audit_log = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        model_used="gpt-4o-mini",
        merchant_name=request.transaction.merchant_name,
        category=request.transaction.category,
        recommended_card_id=request.recommended_card.Card_ID,
        recommended_card_name=request.recommended_card.Card_Name,
        num_comparisons=len(request.comparison_cards)
    )
    
    return ExplanationResponse(
        explanation=explanation,
        audit_log_entry=audit_log
    )


async def generate_explanation_async(request: ExplanationRequest) -> ExplanationResponse:
    """
    Async variant for non-blocking execution in FastAPI routes.
    Same logic, non-blocking I/O.
    """
    
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        request.transaction,
        request.recommended_card,
        request.comparison_cards
    )
    
    explanation = await _call_openai_async(system_prompt, user_prompt)
    
    audit_log = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        model_used="gpt-4o-mini",
        merchant_name=request.transaction.merchant_name,
        category=request.transaction.category,
        recommended_card_id=request.recommended_card.Card_ID,
        recommended_card_name=request.recommended_card.Card_Name,
        num_comparisons=len(request.comparison_cards)
    )
    
    return ExplanationResponse(
        explanation=explanation,
        audit_log_entry=audit_log
    )


# ============================================================================
# LOGGING - Persist audit events (optional enhancement)
# ============================================================================

def save_audit_log(audit_entry: AuditLogEntry, custom_path: Optional[str] = None) -> None:
    """
    Save audit log entry to JSON file for compliance/analytics.
    
    Optional: Can be extended to write to database or event streaming.
    """
    try:
        log_file = custom_path or "data/card_explanation_audit.json"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logs = []
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                logs = json.load(f)
        
        logs.append(audit_entry.model_dump())
        
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save audit log: {e}")
