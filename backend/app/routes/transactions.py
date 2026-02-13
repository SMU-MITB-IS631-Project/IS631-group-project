from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from app.models.transaction import TransactionRequest, TransactionResponse
from app.services.data_service import (
    create_transaction,
    card_exists_in_wallet,
    get_user_transactions,
    get_transaction_by_id
)

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"]
)


@router.post("", status_code=201)
def create_transaction_endpoint(request: TransactionRequest) -> Dict[str, Any]:
    """
    Create a new transaction.
    
    Per API contract:
    - `item` required
    - `amount_sgd` required and > 0
    - `card_id` must be in user wallet
    - `channel` must be `online` | `offline`
    
    Server generates `id` and sets `date = today` if missing.
    """
    txn_data = request.transaction.model_dump()
    user_id = "u_001"  # TODO: Get from auth token
    
    # Validation: card_id must exist in user's wallet
    if not card_exists_in_wallet(txn_data['card_id'], user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"card_id '{txn_data['card_id']}' not found in user wallet",
                    "details": {}
                }
            }
        )
    
    # Create transaction
    try:
        transaction = create_transaction(txn_data, user_id)
        return {"transaction": transaction}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "details": {}
                }
            }
        )


@router.get("")
def list_transactions() -> Dict[str, Any]:
    """
    List all transactions for current user.
    """
    user_id = "u_001"  # TODO: Get from auth token
    transactions = get_user_transactions(user_id)
    return {"transactions": transactions}


@router.get("/{user_id}")
def get_user_transactions_by_id(user_id: str, sort: str = "date_desc") -> Dict[str, Any]:
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
    # Determine sort order
    sort_desc = sort.lower() != "date_asc" and sort.lower() != "none"
    
    # Get transactions filtered by user_id and sorted
    transactions = get_user_transactions(user_id, sort_by_date_desc=sort_desc)
    
    # Apply ascending sort if requested
    if sort.lower() == "date_asc":
        transactions = sorted(
            transactions,
            key=lambda t: t.get('date', '1900-01-01'),
            reverse=False
        )
    
    return {"transactions": transactions}
