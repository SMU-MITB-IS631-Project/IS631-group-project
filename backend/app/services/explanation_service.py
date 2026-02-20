"""
Explanation Service - Core business logic for AI-powered card recommendation explanations.

This service bridges the gap between:
1. Database ground truth (CardCatalogue + CardBonusCategory)
2. LLM prompt engineering
3. Fallback template generation (for offline/API-less scenarios)

Architectural Decisions:
- Database-first: All rates/caps pulled from DB to prevent hallucinations
- Graceful degradation: Falls back to template if LLM unavailable
- Dependency injection: Accepts SQLAlchemy session for testability
- Type-safe: Uses Pydantic schemas throughout
"""

import os
import time
import logging
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from openai import OpenAI, APIError, APITimeoutError

from app.models.card_catalogue import CardCatalogue
from app.models.card_bonus_category import CardBonusCategory, BonusCategory
from app.schemas.ai_schemas import (
    RecommendationContext,
    ExplanationRequest,
    ExplanationResponse,
    AuditLogEntry,
    BenefitType,
)

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# LLM Configuration
# =============================================================================

class LLMConfig:
    """Centralized LLM settings with environment variable overrides"""
    MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Parse temperature with validation and fallback
    _default_temperature = 0.7
    try:
        TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", str(_default_temperature)))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid LLM_TEMPERATURE value; falling back to default %s",
            _default_temperature,
        )
        TEMPERATURE = _default_temperature

    # Parse max tokens with validation and fallback
    _default_max_tokens = 150
    try:
        MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", str(_default_max_tokens)))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid LLM_MAX_TOKENS value; falling back to default %s",
            _default_max_tokens,
        )
        MAX_TOKENS = _default_max_tokens

    # Parse timeout with validation and fallback
    _default_timeout = 5
    try:
        TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT", str(_default_timeout)))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid LLM_TIMEOUT value; falling back to default %s seconds",
            _default_timeout,
        )
        TIMEOUT_SECONDS = _default_timeout

    # Parse max retries with validation and fallback
    _default_max_retries = 1
    try:
        MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", str(_default_max_retries)))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid LLM_MAX_RETRIES value; falling back to default %s",
            _default_max_retries,
        )
        MAX_RETRIES = _default_max_retries


# Initialize OpenAI client (only if API key present)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None

if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=float(LLMConfig.TIMEOUT_SECONDS),
            max_retries=LLMConfig.MAX_RETRIES
        )
        logger.info(f"OpenAI client initialized with model: {LLMConfig.MODEL}")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenAI client: {e}. Will use fallback mode.")
else:
    logger.warning(
        "OPENAI_API_KEY not set. Explanation service will use template fallbacks. "
        "Set the environment variable to enable AI-powered explanations."
    )


# Sentinel value used in DB for "no cap" on bonus rewards
EFFECTIVELY_UNLIMITED_CAP = 99999999


# =============================================================================
# Explanation Service
# =============================================================================

class ExplanationService:
    """
    Service for generating natural language explanations for card recommendations.
    
    Pattern: Constructor injection for database session (facilitates testing)
    
    Usage:
        service = ExplanationService(db_session)
        context = service.build_context_from_db(card_id=3, category="Fashion", amount=120.00)
        response = service.generate_explanation(context)
    """
    
    def __init__(self, db: Session):
        """
        Initialize service with database session.
        
        Args:
            db: SQLAlchemy session for querying card data
        """
        self.db = db
    
    def build_context_from_db(
        self,
        card_id: int,
        category: str,
        transaction_amount: Decimal,
        merchant_name: Optional[str] = None
    ) -> RecommendationContext:
        """
        Query database to build a complete RecommendationContext with ground truth.
        
        This method is the bridge between the recommender engine and the explanation engine.
        It ensures all rates and caps come from the database, not from user input.
        
        Args:
            card_id: Primary key from card_catalogue
            category: Transaction category (e.g., "Fashion", "Food")
            transaction_amount: Transaction value in SGD
            merchant_name: Optional merchant identifier
        
        Returns:
            RecommendationContext with all ground truth fields populated
        
        Raises:
            ValueError: If card_id not found in database
        """
        # Step 1: Get card master data
        card = self.db.query(CardCatalogue).filter(CardCatalogue.card_id == card_id).first()
        if not card:
            raise ValueError(f"Card ID {card_id} not found in card_catalogue")
        
        # Step 2: Get bonus category data (if applicable)
        bonus_data = self._get_bonus_for_category(card_id, category)
        
        # Step 3: Compute reward value
        bonus_min_spend_sgd = Decimal(str(bonus_data.get("bonus_min_spend_sgd") or 0))
        is_bonus_eligible = (
            bonus_data["is_bonus_eligible"]
            and transaction_amount >= bonus_min_spend_sgd
        )
        if is_bonus_eligible and bonus_data.get("bonus_rate"):
            effective_rate = bonus_data["bonus_rate"]
        else:
            effective_rate = Decimal(str(card.base_benefit_rate))

        # Normalize cashback fraction (supports both 0.015 and 1.5 representations)
        benefit_type = card.benefit_type  # type: ignore[assignment]
        if benefit_type == BenefitType.CASHBACK:
            if effective_rate > Decimal("1"):
                cashback_fraction = effective_rate / Decimal("100")
            else:
                cashback_fraction = effective_rate
            total_reward = transaction_amount * cashback_fraction
            # Apply cap only for cashback rewards
            if bonus_data.get("bonus_cap_sgd") and bonus_data["bonus_cap_sgd"] < EFFECTIVELY_UNLIMITED_CAP:
                bonus_cap_sgd_decimal = Decimal(str(bonus_data["bonus_cap_sgd"]))
                if total_reward > bonus_cap_sgd_decimal:
                    total_reward = bonus_cap_sgd_decimal
        else:
            # Miles: effective_rate is miles per dollar (mpd), no cap
            total_reward = transaction_amount * effective_rate
        
        # Step 4: Build context (type: ignore for SQLAlchemy ORM attribute access)
        return RecommendationContext(
            card_id=card.card_id,  # type: ignore[arg-type]
            card_name=card.card_name,  # type: ignore[arg-type]
            bank=card.bank.value,
            benefit_type=benefit_type,
            category=category,
            transaction_amount=transaction_amount,
            merchant_name=merchant_name,
            base_rate=card.base_benefit_rate,  # type: ignore[arg-type]
            bonus_rate=bonus_data.get("bonus_rate"),
            is_bonus_eligible=is_bonus_eligible,
            bonus_cap_sgd=bonus_data.get("bonus_cap_sgd"),
            bonus_min_spend_sgd=bonus_data.get("bonus_min_spend_sgd"),
            total_reward_value=total_reward  # type: ignore[arg-type]
        )
    
    def _get_bonus_for_category(self, card_id: int, category: str) -> Dict[str, Any]:
        """
        Query CardBonusCategory table for category-specific bonus rates.
        
        Args:
            card_id: Card ID to query
            category: Transaction category (e.g., "Fashion")
        
        Returns:
            Dict with bonus_rate, is_bonus_eligible, bonus_cap_sgd, bonus_min_spend_sgd
        """
        # Normalize category to match BonusCategory enum
        try:
            normalized_category = BonusCategory[category]
        except KeyError:
            # Category doesn't match any bonus category
            return {
                "is_bonus_eligible": False,
                "bonus_rate": None,
                "bonus_cap_sgd": None,
                "bonus_min_spend_sgd": None
            }
        
        # Query for specific category or "All" category
        bonus = self.db.query(CardBonusCategory).filter(
            CardBonusCategory.card_id == card_id,
            CardBonusCategory.bonus_category.in_([normalized_category, BonusCategory.All])
        ).order_by(
            CardBonusCategory.bonus_benefit_rate.desc()  # Prioritize higher rate
        ).first()
        
        if bonus:
            return {
                "is_bonus_eligible": True,
                "bonus_rate": bonus.bonus_benefit_rate,
                "bonus_cap_sgd": bonus.bonus_cap_in_dollar,
                "bonus_min_spend_sgd": bonus.bonus_minimum_spend_in_dollar
            }
        
        return {
            "is_bonus_eligible": False,
            "bonus_rate": None,
            "bonus_cap_sgd": None,
            "bonus_min_spend_sgd": None
        }
    
    def generate_explanation(
        self,
        request: ExplanationRequest
    ) -> ExplanationResponse:
        """
        Generate natural language explanation for a card recommendation.
        
        Flow:
        1. Build prompt from RecommendationContext
        2. Attempt LLM call (if API key available)
        3. Fallback to template if LLM fails
        4. Return structured response with metadata
        
        Args:
            request: ExplanationRequest with recommendation context
        
        Returns:
            ExplanationResponse with explanation and metadata
        """
        start_time = time.time()
        context = request.recommendation
        
        # Build prompt
        prompt = self._build_prompt(context, request.comparison_cards)
        
        # Try LLM generation
        explanation_text, model_used, is_fallback = self._try_llm_generation(prompt, context)
        
        # Calculate generation time
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        return ExplanationResponse(
            explanation=explanation_text,
            card_id=context.card_id,
            category=context.category,
            total_reward=context.total_reward_value,
            model_used=model_used,
            is_fallback=is_fallback,
            generation_time_ms=generation_time_ms
        )
    
    def _build_prompt(
        self,
        context: RecommendationContext,
        comparison_cards: list[RecommendationContext]
    ) -> str:
        """
        Construct a factual, grounded prompt for the LLM.
        
        Prompt Engineering Principles:
        - Lead with context (Singapore credit cards)
        - Provide explicit numerical ground truth
        - Request brevity and clarity
        - Avoid open-ended questions that invite hallucinations
        
        Args:
            context: Primary recommendation context
            comparison_cards: Alternative cards for comparison
        
        Returns:
            Complete prompt string
        """
        # Compute effective rate value for display/LLM
        effective_rate = context.bonus_rate if context.is_bonus_eligible and context.bonus_rate else context.base_rate
        
        # Build core explanation request
        benefit_label = "cashback" if context.benefit_type == BenefitType.CASHBACK else "miles"
        
        if context.benefit_type == BenefitType.CASHBACK:
            # Cashback: support both fractional (<= 1.0) and percent (> 1.0) representations
            rate_display_pct = float(effective_rate * 100) if effective_rate <= 1 else float(effective_rate)
            rate_str = f"{rate_display_pct:.2f}%"
        else:
            # Miles: effective_rate is miles per dollar (mpd)
            rate_display_pct = float(effective_rate)
            rate_str = f"{rate_display_pct:.2f} mpd"
        
        prompt = f"""You are a Singapore credit card advisor. Explain why the {context.bank} {context.card_name} is the best choice for a SGD {float(context.transaction_amount):.2f} {context.category} purchase.

Ground Truth Facts:
- Card: {context.bank} {context.card_name}
- Benefit Type: {benefit_label}
- Category: {context.category}
- Effective Rate: {rate_str}"""

        if context.is_bonus_eligible and context.bonus_rate:
            if context.benefit_type == BenefitType.CASHBACK:
                base_pct = float(context.base_rate * 100) if context.base_rate <= 1 else float(context.base_rate)
                bonus_pct = float(context.bonus_rate * 100) if context.bonus_rate <= 1 else float(context.bonus_rate)
                prompt += f"""
- Base Rate: {base_pct:.2f}%
- Bonus Rate: {bonus_pct:.2f}% (bonus category applied)"""
            else:
                prompt += f"""
- Base Rate: {float(context.base_rate):.2f} mpd
- Bonus Rate: {float(context.bonus_rate):.2f} mpd (bonus category applied)"""
        
        if context.bonus_cap_sgd:
            prompt += f"\n- Monthly Cap: SGD {context.bonus_cap_sgd}"
        
        if context.total_reward_value:
            if context.benefit_type == BenefitType.CASHBACK:
                prompt += f"\n- Total Reward: SGD {float(context.total_reward_value):.2f}"
            else:
                prompt += f"\n- Total Reward: {float(context.total_reward_value):.0f} miles"
        
        # Add comparison if available
        if comparison_cards:
            prompt += "\n\nAlternative Considered:"
            for alt in comparison_cards[:2]:  # Limit to top 2 for brevity
                alt_rate = alt.bonus_rate if alt.is_bonus_eligible and alt.bonus_rate else alt.base_rate
                alt_reward = alt.transaction_amount * alt_rate
                if alt.benefit_type == BenefitType.CASHBACK:
                    alt_rate_str = f"{float(alt_rate * 100) if alt_rate <= 1 else float(alt_rate):.2f}%"
                    alt_reward_str = f"SGD {float(alt_reward):.2f}"
                else:
                    alt_rate_str = f"{float(alt_rate):.2f} mpd"
                    alt_reward_str = f"{float(alt_reward):.0f} miles"
                prompt += f"\n- {alt.bank} {alt.card_name}: {alt_rate_str} = {alt_reward_str}"
        
        prompt += "\n\nProvide a concise explanation (2-3 sentences) in simple English suitable for general consumers. Focus on the value difference."
        
        return prompt
    
    def _try_llm_generation(
        self,
        prompt: str,
        context: RecommendationContext
    ) -> tuple[str, str, bool]:
        """
        Attempt LLM call with graceful fallback to template.
        
        Args:
            prompt: Constructed prompt
            context: Recommendation context for fallback
        
        Returns:
            Tuple of (explanation_text, model_used, is_fallback)
        """
        if not openai_client:
            logger.debug("OpenAI client not available, using template fallback")
            return self._generate_template_fallback(context), "template", True
        
        try:
            response = openai_client.chat.completions.create(
                model=LLMConfig.MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful Singapore credit card advisor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=LLMConfig.TEMPERATURE,
                max_tokens=LLMConfig.MAX_TOKENS
            )
            
            explanation = (response.choices[0].message.content or "").strip()
            if not explanation:
                logger.warning("LLM returned empty explanation, using template fallback")
                return self._generate_template_fallback(context), "template_empty", True
            logger.info(f"LLM explanation generated successfully (model: {LLMConfig.MODEL})")
            return explanation, LLMConfig.MODEL, False
        
        except APITimeoutError:
            logger.warning(f"OpenAI API timeout after {LLMConfig.TIMEOUT_SECONDS}s, using fallback")
            return self._generate_template_fallback(context), "template_timeout", True
        
        except APIError as e:
            logger.error(f"OpenAI API error: {e}, using fallback")
            return self._generate_template_fallback(context), "template_error", True
        
        except Exception as e:
            logger.error(f"Unexpected error during LLM generation: {e}, using fallback")
            return self._generate_template_fallback(context), "template_exception", True
    
    def _generate_template_fallback(self, context: RecommendationContext) -> str:
        """
        Generate a factual, template-based explanation when LLM is unavailable.
        
        This ensures the system always provides value even without an API key.
        
        Args:
            context: Recommendation context with ground truth
        
        Returns:
            Template-generated explanation string
        """
        effective_rate = context.bonus_rate if context.is_bonus_eligible and context.bonus_rate else context.base_rate
        benefit_label = "cashback" if context.benefit_type == BenefitType.CASHBACK else "miles"
        reward_value = float(context.total_reward_value) if context.total_reward_value else 0.0
        spend_amount = f"SGD {float(context.transaction_amount):.2f}"

        if context.benefit_type == BenefitType.CASHBACK:
            rate_numeric = float(effective_rate * 100) if effective_rate <= 1 else float(effective_rate)
            rate_display = f"{rate_numeric:.2f}% {benefit_label}"
            reward_phrase = f"SGD {reward_value:.2f} in {benefit_label}"
        else:
            # Miles: rate is miles per dollar (mpd), not a percentage
            rate_display = f"{float(effective_rate):.2f} miles per dollar"
            reward_phrase = f"{reward_value:.0f} {benefit_label}"

        if context.is_bonus_eligible:
            explanation = (
                f"The {context.bank} {context.card_name} offers {rate_display} "
                f"on {context.category} purchases (bonus category). "
                f"For this {spend_amount} transaction, you'll earn {reward_phrase}."
            )
        else:
            explanation = (
                f"The {context.bank} {context.card_name} provides {rate_display} "
                f"on all purchases. For this {spend_amount} transaction, "
                f"you'll receive {reward_phrase}."
            )
        
        if context.bonus_cap_sgd and context.bonus_cap_sgd < EFFECTIVELY_UNLIMITED_CAP:
            explanation += f" (Subject to monthly cap of SGD {context.bonus_cap_sgd})"
        
        return explanation
    
    def create_audit_log(
        self,
        response: ExplanationResponse,
        user_id: Optional[int] = None,
        prompt: Optional[str] = None
    ) -> AuditLogEntry:
        """
        Create structured audit log entry for compliance and analytics.
        
        Args:
            response: Generated explanation response
            user_id: Optional user ID
            prompt: Optional prompt for hash generation
        
        Returns:
            AuditLogEntry for persistence
        """
        prompt_hash = None
        if prompt:
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        
        return AuditLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="explanation_generated",
            user_id=user_id,
            card_id=response.card_id,
            category=response.category,
            model_used=response.model_used,
            prompt_hash=prompt_hash,
            response_length=len(response.explanation)
        )
