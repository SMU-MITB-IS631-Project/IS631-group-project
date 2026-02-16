from .transactions import router as transactions_router
from .catalog import router as catalog_router
from .wallet import router as wallet_router
from .user_card_management import router as user_card_router
from .recommendation import router as recommendation_router

__all__ = [
	"transactions_router",
	"wallet_router",
	"catalog_router",
	"user_card_router",
	"recommendation_router",
]