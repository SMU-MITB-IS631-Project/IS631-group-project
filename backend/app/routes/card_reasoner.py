"""
Card Reasoner Route - API endpoints for credit card recommendation explanations.

Endpoints:
- POST /api/v1/card-reasoner/explain - Generate explanation (sync)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies.security import require_user_id_header
from app.services.card_reasoner_service import (
    ExplanationRequest,
    ExplanationResponse,
    generate_explanation,
    generate_explanation_async,
    save_audit_log
)

router = APIRouter(
    prefix="/api/v1/card-reasoner",
    tags=["card-reasoner"]
)


@router.post("/explain", response_model=ExplanationResponse)
def explain_recommendation(
    request: ExplanationRequest,
    authenticated_user_id: str = Depends(require_user_id_header),
) -> ExplanationResponse:
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


@router.post("/explain-async", response_model=ExplanationResponse)
async def explain_recommendation_async(
    request: ExplanationRequest,
    authenticated_user_id: str = Depends(require_user_id_header),
) -> ExplanationResponse:
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
