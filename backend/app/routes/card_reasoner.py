"""
Card Reasoner Route - API endpoints for credit card recommendation explanations.

Endpoints:
- POST /api/v1/card-reasoner/explain - Generate explanation (sync) [Legacy]
- POST /api/v1/card-reasoner/explain-db - Generate explanation from DB ground truth [NEW - TDD]
"""

from decimal import Decimal
from fastapi import APIRouter, HTTPException, status, Depends
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
from app.schemas.ai_schemas import ExplanationRequest, ExplanationResponse
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/card-reasoner",
    tags=["card-reasoner"]
)


# =============================================================================
# Request/Response Models for DB-Grounded Endpoint
# =============================================================================

class ExplainFromDBRequest(BaseModel):
    """
    Simplified request for DB-grounded explanation.
    Service queries all data from database using card_id + category.
    """
    card_id: int = Field(..., description="Card ID from card_catalogue")
    category: str = Field(..., description="Transaction category")
    transaction_amount: Decimal = Field(..., gt=0, description="Transaction amount in SGD")
    merchant_name: str | None = Field(None, description="Optional merchant name")
    user_id: int | None = Field(None, description="Optional user ID for audit")
    
    model_config = {"json_schema_extra": {"examples": [{"card_id": 3, "category": "Fashion", "transaction_amount": 120.00, "merchant_name": "ZARA"}]}}


@router.post("/explain", response_model=LegacyExplanationResponse)
def explain_recommendation(request: LegacyExplanationRequest) -> LegacyExplanationResponse:
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
    try:
        response = generate_explanation(request)
        
        # Optionally persist audit log (can be enhanced to write to database)
        save_audit_log(response.audit_log_entry)
        
        return response
    except ValueError as e:
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
async def explain_recommendation_async(request: LegacyExplanationRequest) -> LegacyExplanationResponse:
    """
    Async variant for non-blocking LLM calls.
    Recommended for high-concurrency scenarios.
    
    Same request/response schema as /explain.
    """
    try:
        response = await generate_explanation_async(request)
        save_audit_log(response.audit_log_entry)
        return response
    except ValueError as e:
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
    request: ExplainFromDBRequest,
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
    try:
        # Initialize service with DB session
        service = ExplanationService(db)
        
        # Build context from database (ground truth)
        context = service.build_context_from_db(
            card_id=request.card_id,
            category=request.category,
            transaction_amount=request.transaction_amount,
            merchant_name=request.merchant_name
        )
        
        # Generate explanation
        explanation_request = ExplanationRequest(
            recommendation=context,
            comparison_cards=[],
            user_id=request.user_id
        )
        response = service.generate_explanation(explanation_request)
        
        # Optional: Create audit log
        if request.user_id:
            audit = service.create_audit_log(response, user_id=request.user_id)
            # TODO: Persist audit log to database or file
        
        return response
    
    except ValueError as e:
        # Card not found or invalid input
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Card or bonus data not found: {str(e)}",
                    "details": {"card_id": request.card_id}
                }
            }
        )
    except Exception as e:
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

