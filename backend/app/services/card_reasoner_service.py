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
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from openai import AsyncOpenAI, OpenAI, APIError, APITimeoutError

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - Centralized settings
# ============================================================================

class LLMConfig:
    """LLM configuration with sensible defaults"""
    MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "150"))
    TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT", "5"))
    MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))

# Initialize clients
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning(
        "OPENAI_API_KEY environment variable not set. "
        "Card reasoner will use fallback template explanations. "
        "Set OPENAI_API_KEY to enable AI-powered explanations."
    )

client = OpenAI(api_key=OPENAI_API_KEY, timeout=float(LLMConfig.TIMEOUT_SECONDS)) if OPENAI_API_KEY else None
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=float(LLMConfig.TIMEOUT_SECONDS)) if OPENAI_API_KEY else None


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
    amount: float = Field(..., gt=0, le=1_000_000, example=120.00)
    category: str = Field(..., example="Fashion")
    
    @field_validator("merchant_name")
    @classmethod
    def validate_merchant_name(cls, v: str) -> str:
        """Merchant name must be non-empty after stripping"""
        if not v.strip():
            raise ValueError("Merchant name cannot be empty")
        return v.strip()


class CardDetail(BaseModel):
    """Credit card details with calculated values"""
    Card_ID: int = Field(..., alias="card_id", description="Unique card identifier")
    Bank: str = Field(..., description="Card issuing bank")
    Card_Name: str = Field(..., alias="card_name", description="Card product name")
    Benefit_type: BenefitTypeEnum = Field(..., alias="benefit_type")
    base_benefit_rate: float = Field(..., ge=0, description="Base reward rate")
    applied_bonus_rate: float = Field(..., ge=0, description="Category-specific bonus rate")
    total_calculated_value: float = Field(..., ge=0, description="Total calculated reward value")
    
    model_config = {"populate_by_name": True}  # Allow both PascalCase and snake_case


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

def _call_openai_sync(system_prompt: str, user_prompt: str) -> tuple[str, Optional[str]]:
    """
    Call OpenAI synchronously with retry logic.
    Returns: (explanation, error_message_or_none)
    """
    if not client:
        error_msg = "OpenAI API key not configured"
        logger.warning(error_msg)
        return _fallback_explanation(), error_msg
    
    for attempt in range(1, LLMConfig.MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLMConfig.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=LLMConfig.TEMPERATURE,
                max_tokens=LLMConfig.MAX_TOKENS
            )
            return response.choices[0].message.content.strip(), None
        except APITimeoutError as e:
            error_msg = f"LLM timeout (attempt {attempt}/{LLMConfig.MAX_RETRIES}): {str(e)}"
            logger.warning(error_msg)
            if attempt == LLMConfig.MAX_RETRIES:
                return _fallback_explanation(), error_msg
        except APIError as e:
            error_msg = f"LLM API error (attempt {attempt}/{LLMConfig.MAX_RETRIES}): {str(e)}"
            logger.warning(error_msg)
            return _fallback_explanation(), error_msg
        except (ConnectionError, IOError) as e:
            error_msg = f"Network error (attempt {attempt}/{LLMConfig.MAX_RETRIES}): {str(e)}"
            logger.warning(error_msg)
            if attempt == LLMConfig.MAX_RETRIES:
                return _fallback_explanation(), error_msg
        except Exception as e:
            error_msg = f"Unexpected error during LLM call: {type(e).__name__}: {str(e)}"
            logger.exception(error_msg)
            return _fallback_explanation(), error_msg
    
    return _fallback_explanation(), "Max retries exceeded"


async def _call_openai_async(system_prompt: str, user_prompt: str) -> tuple[str, Optional[str]]:
    """
    Call OpenAI asynchronously with retry logic.
    Non-blocking for high concurrency.
    Returns: (explanation, error_message_or_none)
    """
    if not async_client:
        error_msg = "OpenAI API key not configured"
        logger.warning(error_msg)
        return _fallback_explanation(), error_msg
    
    for attempt in range(1, LLMConfig.MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                async_client.chat.completions.create(
                    model=LLMConfig.MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=LLMConfig.TEMPERATURE,
                    max_tokens=LLMConfig.MAX_TOKENS
                ),
                timeout=float(LLMConfig.TIMEOUT_SECONDS)
            )
            return response.choices[0].message.content.strip(), None
        except asyncio.TimeoutError as e:
            error_msg = f"LLM timeout (attempt {attempt}/{LLMConfig.MAX_RETRIES})"
            logger.warning(error_msg)
            if attempt == LLMConfig.MAX_RETRIES:
                return _fallback_explanation(), error_msg
        except APIError as e:
            error_msg = f"LLM API error (attempt {attempt}/{LLMConfig.MAX_RETRIES}): {str(e)}"
            logger.warning(error_msg)
            return _fallback_explanation(), error_msg
        except (ConnectionError, IOError) as e:
            error_msg = f"Network error (attempt {attempt}/{LLMConfig.MAX_RETRIES}): {str(e)}"
            logger.warning(error_msg)
            if attempt == LLMConfig.MAX_RETRIES:
                return _fallback_explanation(), error_msg
        except Exception as e:
            error_msg = f"Unexpected error during async LLM call: {type(e).__name__}: {str(e)}"
            logger.exception(error_msg)
            return _fallback_explanation(), error_msg
    
    return _fallback_explanation(), "Max retries exceeded"


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
    - Error tracking for debugging
    """
    
    # Validate inputs
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        request.transaction,
        request.recommended_card,
        request.comparison_cards
    )
    
    # Get explanation from LLM with error tracking
    explanation, error = _call_openai_sync(system_prompt, user_prompt)
    
    # Create audit log with error details if applicable
    audit_log = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        model_used=LLMConfig.MODEL,
        merchant_name=request.transaction.merchant_name,
        category=request.transaction.category,
        recommended_card_id=request.recommended_card.Card_ID,
        recommended_card_name=request.recommended_card.Card_Name,
        num_comparisons=len(request.comparison_cards),
        error=error
    )
    
    return ExplanationResponse(
        explanation=explanation,
        audit_log_entry=audit_log
    )


async def generate_explanation_async(request: ExplanationRequest) -> ExplanationResponse:
    """
    Async variant for non-blocking execution in FastAPI routes.
    Same logic, non-blocking I/O, error tracking.
    """
    
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        request.transaction,
        request.recommended_card,
        request.comparison_cards
    )
    
    # Get explanation with error tracking
    explanation, error = await _call_openai_async(system_prompt, user_prompt)
    
    audit_log = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        model_used=LLMConfig.MODEL,
        merchant_name=request.transaction.merchant_name,
        category=request.transaction.category,
        recommended_card_id=request.recommended_card.Card_ID,
        recommended_card_name=request.recommended_card.Card_Name,
        num_comparisons=len(request.comparison_cards),
        error=error
    )
    
    return ExplanationResponse(
        explanation=explanation,
        audit_log_entry=audit_log
    )


# ============================================================================
# LOGGING - Persist audit events (optional enhancement)
# ============================================================================

def save_audit_log(audit_entry: AuditLogEntry, custom_path: Optional[str] = None) -> bool:
    """
    Save audit log entry to JSON file for compliance/analytics.
    
    Optional: Can be extended to write to database or event streaming.
    
    Args:
        audit_entry: AuditLogEntry to save
        custom_path: Optional custom path for log file (should be absolute path)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use absolute path to prevent path traversal vulnerabilities
        if custom_path:
            # Ensure absolute path and normalize it
            log_file = os.path.abspath(custom_path)
        else:
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            log_file = os.path.join(base_dir, "data", "card_explanation_audit.json")
        
        # Create directory if needed
        log_dir = os.path.dirname(log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Use file locking approach to prevent race conditions
        # Note: For production, consider using database instead of JSON file
        lock_file = log_file + ".lock"
        max_lock_wait = 5  # seconds
        lock_start = datetime.now()
        
        # Wait for lock (simple retry mechanism)
        while os.path.exists(lock_file):
            if (datetime.now() - lock_start).total_seconds() > max_lock_wait:
                logger.warning(f"Could not acquire lock for {log_file}, skipping write")
                return False
            time.sleep(0.1)  # Brief sleep before retry
        
        # Create lock file
        try:
            with open(lock_file, "w") as f:
                f.write("locked")
            
            # Read existing logs
            logs = []
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    logs = json.load(f)
            
            # Append new entry
            logs.append(audit_entry.model_dump())
            
            # Write updated logs
            with open(log_file, "w") as f:
                json.dump(logs, f, indent=2, default=str)
            
            logger.debug(f"Audit log saved: {audit_entry.event_type} for {audit_entry.recommended_card_name}")
            return True
        finally:
            # Remove lock file
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except OSError:
                    pass  # Ignore if already removed
    except Exception as e:
        logger.exception(f"Failed to save audit log to {custom_path}: {e}")
        return False
