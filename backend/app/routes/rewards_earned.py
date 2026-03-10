from datetime import date
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query
from typing import Optional, Dict, Any
from app.dependencies.services import get_rewards_earned_service
from app.services.rewards_earned_service import RewardsEarnedService

# Attempt to import ServiceException; provide fallback if module not available
try:
    from app.exceptions import ServiceException
except ImportError:
    class ServiceException(Exception):
        """Fallback exception used when app.exceptions is missing (e.g., during tests)"""
        pass

router = APIRouter(
    prefix="/api/v1/rewards",
    tags=["rewards"]
)

DEFAULT_USER_ID = 0 # non-existent user ID to trigger 404 if not provided


@router.get("", response_model=Dict[str, float])
def get_rewards_earned(
    x_user_id: Optional[str] = Header(default=None),
    service: RewardsEarnedService = Depends(get_rewards_earned_service)
):
    """
    Calculate and return the rewards earned for the current user's active cards
    in their latest billing cycle based on transactions.
    
    Parameters:
    - x_user_id: User ID from header (optional; defaults to 1 if not provided)
    
    Returns:
    - Dictionary mapping card names to rewards amounts earned
    
    Raises:
    - 404: If user has no active cards
    - 500: If error occurs during rewards calculation
    """
    try:
        user_id = int(x_user_id) if x_user_id else DEFAULT_USER_ID
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid user ID in x-user-id header.",
                    "details": {"field": "x-user-id"}
                }
            }
        )
    
    try:
        rewards = service.calculate_rewards_earned(user_id=user_id)
        
        # If no active cards, return 404
        if not rewards:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "No active cards found for user.",
                        "details": {}
                    }
                }
            )
        
        return rewards
        
    except ServiceException as e:
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


@router.get("/historical", response_model=list[Dict[str, Any]])
def get_historical_rewards(
    x_user_id: Optional[str] = Header(default=None),
    card_id: Optional[int] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    group_by: str = Query(default="month"),
    service: RewardsEarnedService = Depends(get_rewards_earned_service),
):
    """
    Return historical rewards aggregated from stored transaction.total_reward.
    """
    try:
        user_id = int(x_user_id) if x_user_id else DEFAULT_USER_ID
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid user ID in x-user-id header.",
                    "details": {"field": "x-user-id"},
                }
            },
        )

    try:
        return service.get_historical_rewards(
            user_id=user_id,
            card_id=card_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )
    except ServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "details": {},
                }
            },
        )