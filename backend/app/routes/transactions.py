from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.security import normalize_user_id, require_user_id_header
from app.models.transaction import TransactionRequest
from app.services.errors import ServiceError
from app.services.transaction_service import TransactionService

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"]
)


class TransactionStatusUpdate(BaseModel):
    """Update transaction status"""
    status: str  # "active" or "deleted_with_card"


class BulkTransactionStatusUpdate(BaseModel):
    """Bulk update multiple transactions status"""
    transaction_ids: list[int]
    status: str  # "active" or "deleted_with_card"


@router.post("", status_code=201)
def create_transaction(
    request: TransactionRequest,
    authenticated_user_id: str = Depends(require_user_id_header),
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
    try:
        service = TransactionService(db)
        transaction = service.create_transaction(authenticated_user_id, request.transaction)
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
    authenticated_user_id: str = Depends(require_user_id_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    List all transactions for current user.
    """
    try:
        service = TransactionService(db)
        transactions = service.get_user_transactions(authenticated_user_id, sort_by_date_desc=True)
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
    authenticated_user_id: str = Depends(require_user_id_header),
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
    if normalize_user_id(authenticated_user_id) != normalize_user_id(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not allowed to access another user's transactions.",
                    "details": {},
                }
            },
        )
    
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


@router.put("/{transaction_id}")
def update_transaction_status(
    transaction_id: int,
    status_update: TransactionStatusUpdate,
    authenticated_user_id: str = Depends(require_user_id_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Update a transaction's status (e.g., mark as deleted_with_card).
    
    Path Parameters:
    - transaction_id: The transaction ID to update
    
    Request body:
    {
        "status": "deleted_with_card"
    }
    """
    try:
        service = TransactionService(db)
        transaction = service.update_transaction_status(authenticated_user_id, transaction_id, status_update.status)
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


@router.put("/bulk/status")
def bulk_update_transaction_status(
    bulk_update: BulkTransactionStatusUpdate,
    authenticated_user_id: str = Depends(require_user_id_header),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Bulk update multiple transactions' status.
    
    Request body:
    {
        "transaction_ids": [1, 2, 3],
        "status": "deleted_with_card"
    }
    
    Returns:
    - count: Number of transactions updated
    """
    try:
        service = TransactionService(db)
        count = service.bulk_update_transaction_status(authenticated_user_id, bulk_update.transaction_ids, bulk_update.status)
        return {"count": count, "status": bulk_update.status}
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

