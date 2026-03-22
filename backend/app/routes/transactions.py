from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.user_context import get_x_user_id
from app.models.transaction import TransactionRequest, TransactionUpdate, TransactionStatus
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


class TransactionUpdateRequest(BaseModel):
    """Wrapper for transaction update API"""
    transaction: TransactionUpdate


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


def _forbidden_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": {
                "code": "FORBIDDEN",
                "message": "Cannot access transactions for another user.",
                "details": {},
            }
        },
    )


def _parse_sort_to_desc(sort: str) -> Optional[bool]:
    sort_value = sort.lower()
    if sort_value == "none":
        return None
    return sort_value != "date_asc"


def _list_transactions_for_user(
    *,
    target_user_id: str,
    requester_user_id: str,
    sort: str,
    db: Session,
) -> Dict[str, Any] | JSONResponse:
    service = TransactionService(db)
    if service._resolve_user_id(requester_user_id) != service._resolve_user_id(target_user_id):
        return _forbidden_response()

    transactions = service.get_user_transactions(
        target_user_id,
        sort_by_date_desc=_parse_sort_to_desc(sort),
    )
    return {"transactions": transactions}


@router.post("", status_code=201)
def create_transaction(
    request: TransactionRequest,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {}
                }
            }
        )


@router.get("")
def list_transactions(
    request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
) -> Dict[str, Any]:
    """
    List all transactions for current user.
    """
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
    header_user_id: Optional[str] = Depends(get_x_user_id),
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
    if not header_user_id:
        return _unauthorized_response()

    try:
        return _list_transactions_for_user(
            target_user_id=user_id,
            requester_user_id=header_user_id,
            sort=sort,
            db=db,
        )
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


@router.get("/user/{user_id}")
def list_transactions_by_user_id(
    user_id: str,
    request: Request,
    sort: str = "date_desc",
    db: Session = Depends(get_db),
    header_user_id: Optional[str] = Depends(get_x_user_id),
) -> Dict[str, Any]:
    """List all transactions for the specified user_id.

    Requires x-user-id header and only allows requesting your own transactions.
    """
    if not header_user_id:
        return _unauthorized_response()

    try:
        return _list_transactions_for_user(
            target_user_id=user_id,
            requester_user_id=header_user_id,
            sort=sort,
            db=db,
        )
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
def update_transaction(
    transaction_id: int,
    request: TransactionUpdateRequest | TransactionStatusUpdate,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
) -> Dict[str, Any]:
    """
    Update a transaction's fields (item, amount, category, etc.).
    
    Path Parameters:
    - transaction_id: The transaction ID to update
    
    Request body:
    {
        "transaction": {
            "item": "Updated item",
            "amount_sgd": 150.00,
            "category": "shopping",
            "channel": "online",
            "is_overseas": false,
            "date": "2026-02-20"
        }
    }
    """
    if not user_id:
        return _unauthorized_response()
    
    try:
        service = TransactionService(db)

        # Backward-compatible: some clients/tests send only {"status": "..."}
        # to this endpoint instead of the newer {"transaction": {...}} wrapper.
        if isinstance(request, TransactionStatusUpdate):
            transaction = service.update_transaction_status(user_id, transaction_id, request.status)
            return {"transaction": transaction}

        updates = request.transaction.model_dump(exclude_unset=True, by_alias=False)
        transaction = service.update_transaction(user_id, transaction_id, updates)
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {}
                }
            }
        )


@router.put("/bulk/status")
def bulk_update_transaction_status(
    bulk_update: BulkTransactionStatusUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
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
    if not user_id:
        return _unauthorized_response()
    
    try:
        service = TransactionService(db)
        count = service.bulk_update_transaction_status(user_id, bulk_update.transaction_ids, bulk_update.status)
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {}
                }
            }
        )


@router.put("/{transaction_id}/status")
def update_transaction_status(
    transaction_id: int,
    status_update: TransactionStatusUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
) -> Dict[str, Any]:
    """
    Update only a transaction's status (e.g., mark as deleted_with_card).

    Path Parameters:
    - transaction_id: The transaction ID to update

    Request body:
    {
        "status": "deleted_with_card"
    }
    """
    if not user_id:
        return _unauthorized_response()

    try:
        service = TransactionService(db)
        transaction = service.update_transaction_status(user_id, transaction_id, status_update.status)
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {},
                }
            },
        )


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_x_user_id),
) -> Dict[str, Any]:
    """
    Delete a transaction that was mistakenly added.
    
    Path Parameters:
    - transaction_id: The transaction ID to delete
    
    Returns:
    - The deleted transaction object
    """
    if not user_id:
        return _unauthorized_response()
    
    try:
        service = TransactionService(db)
        deleted_transaction = service.delete_transaction(user_id, transaction_id)
        return {"transaction": deleted_transaction}
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error.",
                    "details": {}
                }
            }
        )

