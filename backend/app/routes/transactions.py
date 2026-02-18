from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.models.transaction import TransactionRequest
from app.services.transaction_service import ServiceError, TransactionService

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"]
)


def _unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid user context.",
                "details": {"required_header": "x-user-id"},
            }
        },
    )


@router.post("", status_code=201)
def create_transaction(
    request: TransactionRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Create a new transaction.
    
    Request body:
    {
        "transaction": {
            "card_id": 1,
            "amount_sgd": 12.50,
            "item": "GrabFood",
            "channel": "online",
            "category": "food",
            "is_overseas": false,
            "date": "2026-02-18"
        }
    }
    """
    user_id = http_request.headers.get("x-user-id")
    if not user_id:
        return _unauthorized_response()
    
    try:
        service = TransactionService(db)
        transaction = service.create_transaction(user_id, request.transaction)
        return {"transaction": transaction}
    except ServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                    "details": {}
                }
            }
        )


@router.get("")
def list_transactions(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List all transactions for current user.
    """
    user_id = request.headers.get("x-user-id")
    if not user_id:
        return _unauthorized_response()
    
    try:
        service = TransactionService(db)
        transactions = service.get_user_transactions(user_id, sort_by_date_desc=True)
        return {"transactions": transactions}
    except ServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )


@router.get("/{user_id}")
def get_user_transactions_by_id(
    user_id: str,
    request: Request,
    sort: str = "date_desc",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all transactions for a specific user.
    
    Path Parameters:
    - user_id: The user ID to fetch transactions for
    
    Query Parameters:
    - sort: Sort order. Options: "date_desc" (default), "date_asc", "none"
    
    Returns:
    - transactions: List of user's transactions, sorted by date DESC by default
    
    Security:
    - Only returns transactions for the specified user
    """
    header_user_id = request.headers.get("x-user-id")
    if not header_user_id:
        return _unauthorized_response()
    
    sort_value = sort.lower()
    if sort_value == "none":
        sort_desc = None
    else:
        sort_desc = sort_value != "date_asc"
    
    try:
        service = TransactionService(db)
        transactions = service.get_user_transactions(user_id, sort_by_date_desc=sort_desc)
        return {"transactions": transactions}
    except ServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
