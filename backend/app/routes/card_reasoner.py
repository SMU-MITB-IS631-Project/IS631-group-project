"""
Card Reasoner Route - API endpoints for credit card recommendation explanations.

Endpoints:
- POST /api/v1/card-reasoner/explain - Generate explanation (sync) [Legacy]
- POST /api/v1/card-reasoner/explain-db - Generate explanation from DB ground truth [NEW - TDD]
"""

from decimal import Decimal
import logging

from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.services.card_reasoner_service import (
    ExplanationRequest as LegacyExplanationRequest,
    ExplanationResponse as LegacyExplanationResponse,
    generate_explanation,
    generate_explanation_async,
    save_audit_log
)
from app.services.explanation_service import ExplanationService
from app.services.security_log_service import log_genai_access_event
from app.schemas.ai_schemas import ExplanationRequest, ExplanationResponse
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/card-reasoner",
    tags=["card-reasoner"]
)
logger = logging.getLogger(__name__)


def _safe_log_genai_event(
    db: Session,
    *,
    status: str,
    request: Request,
    source: str,
    user_id: int | None = None,
    endpoint: str,
    details: dict | None = None,
    error_message: str | None = None,
) -> None:
    # Security logging must never block explanation flows.
    try:
        log_genai_access_event(
            db,
            status=status,
            source=source,
            request=request,
            user_id=user_id,
            endpoint=endpoint,
            details=details,
            error_message=error_message,
        )
    except Exception:
        logger.exception("Failed to write GenAI security log")


def _header_user_id(request: Request) -> int | None:
    value = request.headers.get("x-user-id")
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


# =============================================================================
# Request/Response Models for DB-Grounded Endpoint
# =============================================================================

class ExplainFromDBRequest(BaseModel):
    """
    Simplified request for DB-grounded explanation.
    Service queries all data from database using card_id + category.
    """
    card_id: int = Field(..., description="Card ID from card_catalogue")
    category: str = Field(..., description="Transaction category. Allowed values: Food, Transport, Entertainment, Fashion, All.")
    transaction_amount: Decimal = Field(..., gt=0, description="Transaction amount in SGD")
    merchant_name: str | None = Field(None, description="Optional merchant name")
    user_id: int | None = Field(None, description="Optional user ID for audit")
    
    model_config = {"json_schema_extra": {"examples": [{"card_id": 3, "category": "Fashion", "transaction_amount": 120.00, "merchant_name": "ZARA"}]}}


@router.post("/explain", response_model=LegacyExplanationResponse)
def explain_recommendation(
    payload: LegacyExplanationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LegacyExplanationResponse:
    """
    Generate a natural language explanation for why a credit card was recommended.
    
    Args:
        request: ExplanationRequest containing:
            - transaction: Transaction details (merchant, amount, category)
            - recommended_card: The recommended card with calculated value
            - comparison_cards: Optional list of alternative cards considered
    
    Returns:
        ExplanationResponse with:
            - explanation: Natural language explanation for general users
            - audit_log_entry: Audit trail entry for compliance/analytics
    
    Example:
        POST /api/v1/card-reasoner/explain
        {
            "transaction": {
                "merchant_name": "ZARA",
                "amount": 120.00,
                "category": "Fashion"
            },
            "recommended_card": {
                "Card_ID": 3,
                "Bank": "DBS",
                "Card_Name": "DBS Live Fresh",
                "Benefit_type": "Cashback",
                "base_benefit_rate": 0.01,
                "applied_bonus_rate": 0.035,
                "total_calculated_value": 4.32
            },
            "comparison_cards": [
                {
                    "Card_ID": 5,
                    "Bank": "OCBC",
                    "Card_Name": "OCBC 365",
                    "Benefit_type": "Cashback",
                    "base_benefit_rate": 0.005,
                    "applied_bonus_rate": 0.03,
                    "total_calculated_value": 4.20
                }
            ]
        }
    """
    source = "card_reasoner.explain"
    user_id = _header_user_id(request)
    try:
        response = generate_explanation(payload)
        
        # Optionally persist audit log (can be enhanced to write to database)
        save_audit_log(response.audit_log_entry)

        _safe_log_genai_event(
            db,
            status="success",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain",
            details={
                "category": payload.transaction.category,
                "merchant_name": payload.transaction.merchant_name,
                "recommended_card_id": payload.recommended_card.Card_ID,
                "comparison_count": len(payload.comparison_cards),
                "model_used": response.audit_log_entry.model_used,
                "is_fallback": bool(response.audit_log_entry.error),
            },
        )
        
        return response
    except ValueError as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain",
            details={"reason": "validation_error"},
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid input: {str(e)}",
                    "details": {}
                }
            }
        )
    except Exception as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain",
            details={"reason": "genai_error"},
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GENAI_ERROR",
                    "message": "Failed to generate explanation",
                    "details": {"error_type": type(e).__name__}
                }
            }
        )


@router.post("/explain-async", response_model=LegacyExplanationResponse)
async def explain_recommendation_async(
    payload: LegacyExplanationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LegacyExplanationResponse:
    """
    Async variant for non-blocking LLM calls.
    Recommended for high-concurrency scenarios.
    
    Same request/response schema as /explain.
    """
    source = "card_reasoner.explain_async"
    user_id = _header_user_id(request)
    try:
        response = await generate_explanation_async(payload)
        save_audit_log(response.audit_log_entry)

        _safe_log_genai_event(
            db,
            status="success",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-async",
            details={
                "category": payload.transaction.category,
                "merchant_name": payload.transaction.merchant_name,
                "recommended_card_id": payload.recommended_card.Card_ID,
                "comparison_count": len(payload.comparison_cards),
                "model_used": response.audit_log_entry.model_used,
                "is_fallback": bool(response.audit_log_entry.error),
            },
        )
        return response
    except ValueError as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-async",
            details={"reason": "validation_error"},
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid input: {str(e)}",
                    "details": {}
                }
            }
        )
    except Exception as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-async",
            details={"reason": "genai_error"},
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GENAI_ERROR",
                    "message": "Failed to generate explanation",
                    "details": {"error_type": type(e).__name__}
                }
            }
        )


# =============================================================================
# NEW: DB-Grounded Explanation Endpoint (TDD Architecture)
# =============================================================================

@router.post("/explain-db", response_model=ExplanationResponse, status_code=status.HTTP_200_OK)
def explain_from_database(
    payload: ExplainFromDBRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> ExplanationResponse:
    """
    Generate explanation by querying ground truth from database.
    
    This endpoint demonstrates the TDD architecture:
    1. All rates/caps pulled from CardCatalogue + CardBonusCategory
    2. No user-provided rates accepted (prevents hallucination)
    3. Graceful LLM fallback (works without OpenAI API key)
    4. Fully testable with mocked database
    
    Example Request:
        POST /api/v1/card-reasoner/explain-db
        {
            "card_id": 3,
            "category": "Fashion",
            "transaction_amount": 120.00,
            "merchant_name": "ZARA"
        }
    
    Example Response:
        {
            "explanation": "The DBS Live Fresh card offers 3.5% cashback on Fashion...",
            "card_id": 3,
            "category": "Fashion",
            "total_reward": 4.20,
            "model_used": "gpt-4o-mini",
            "is_fallback": false,
            "generation_time_ms": 245
        }
    
    Security:
    - All rates verified against database
    - Bonus caps automatically applied
    - No possibility of rate hallucination
    """
    source = "card_reasoner.explain_db"
    user_id = payload.user_id if payload.user_id is not None else _header_user_id(request)
    try:
        # Initialize service with DB session
        service = ExplanationService(db)
        
        # Build context from database (ground truth)
        context = service.build_context_from_db(
            card_id=payload.card_id,
            category=payload.category,
            transaction_amount=payload.transaction_amount,
            merchant_name=payload.merchant_name
        )
        
        # Generate explanation
        explanation_request = ExplanationRequest(
            recommendation=context,
            comparison_cards=[],
            user_id=payload.user_id
        )
        response = service.generate_explanation(explanation_request)
        
        # Optional: Create audit log
        if payload.user_id:
            audit = service.create_audit_log(response, user_id=payload.user_id)
            # TODO: Persist audit log to database or file

        _safe_log_genai_event(
            db,
            status="success",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-db",
            details={
                "card_id": payload.card_id,
                "category": payload.category,
                "model_used": response.model_used,
                "is_fallback": response.is_fallback,
                "generation_time_ms": response.generation_time_ms,
            },
        )
        
        return response
    
    except ValueError as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-db",
            details={
                "card_id": payload.card_id,
                "category": payload.category,
                "reason": "not_found_or_invalid_input",
            },
            error_message=str(e),
        )
        # Card not found or invalid input
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Card or bonus data not found: {str(e)}",
                    "details": {"card_id": payload.card_id}
                }
            }
        )
    except Exception as e:
        _safe_log_genai_event(
            db,
            status="failed",
            request=request,
            source=source,
            user_id=user_id,
            endpoint="/api/v1/card-reasoner/explain-db",
            details={
                "card_id": payload.card_id,
                "category": payload.category,
                "reason": "internal_error",
            },
            error_message=str(e),
        )
        # Unexpected error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to generate explanation from database",
                    "details": {"error_type": type(e).__name__, "error_message": str(e)}
                }
            }
        )

