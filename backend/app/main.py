import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.routes import (
    transactions_router,
    wallet_router,
    catalog_router,
    user_card_router,
    recommendation_router,
    card_reasoner_router,
    user_profile_router,
)
from app.services import init_sample_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler - runs on startup and shutdown"""
    # Startup
    init_sample_data()
    yield
    # Shutdown


app = FastAPI(
    title="CardTrack API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS middleware - MUST be added first before other middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):  # type: ignore[override]
    """Handle validation errors with HTTP 400 to maintain backward compatibility with API contract."""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request payload.",
                "details": {"errors": exc.errors()}
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):  # type: ignore[override]
    """Handle general exceptions - log and return 500 error"""
    import traceback
    traceback.print_exc()
    print(f"Error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Internal server error.",
                "details": {}
            }
        }
    )


# Register routers
app.include_router(transactions_router)
app.include_router(catalog_router)
app.include_router(wallet_router)
app.include_router(user_card_router)
app.include_router(user_profile_router)
app.include_router(recommendation_router)
app.include_router(card_reasoner_router)
app.include_router(user_profile_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
