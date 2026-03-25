from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.user_context import get_x_user_id
from app.models.transaction import TransactionCreateRequest, TransactionUpdateRequest
from app.services.errors import ServiceError
from app.services.transaction_service import TransactionService
from app.dependencies.auth import required_authenticated

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


@router.post("", status_code=201, dependencies=[Depends(required_authenticated)])
def create_transaction(
    request: TransactionCreateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(required_authenticated),
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
    user_id = claims.get("sub")
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


@router.get("", dependencies=[Depends(required_authenticated)])
def list_transactions(
    request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(required_authenticated),
) -> Dict[str, Any]:
    """
    List all transactions for current user.
    """
    user_id = claims.get("sub")
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


@router.put("/{transaction_id:int}", dependencies=[Depends(required_authenticated)])
def update_transaction(
    transaction_id: int,
    request: TransactionUpdateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(required_authenticated),
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
    user_id = claims.get("sub")
    if not user_id:
        return _unauthorized_response()
    try:
        service = TransactionService(db)
        transaction = service.update_transaction(user_id, transaction_id, request.transaction)
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


@router.delete("/{transaction_id:int}", dependencies=[Depends(required_authenticated)])
def delete_transaction(
    transaction_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(required_authenticated),
) -> Dict[str, Any]:
    """
    Delete a transaction that was mistakenly added.
    
    Path Parameters:
    - transaction_id: The transaction ID to delete
    
    Returns:
    - The deleted transaction object
    """
    user_id = claims.get("sub")
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

