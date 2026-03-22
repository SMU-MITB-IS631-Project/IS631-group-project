import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables from backend/.env (if present).
# NOTE: This must run before importing FastAPI routes/services because some
# modules (e.g., ExplanationService via card_reasoner_router) initialize the
# OpenAI client at import time and rely on these environment variables.
load_dotenv()

from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.routes import (
    transactions_router,
    catalog_router,
    user_card_router,
    recommendation_router,
    card_reasoner_router,
    user_profile_router,
    rewards_earned_router,
    auth_router,
    notifications_router,
)
from app.services.errors import ServiceError
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
        "http://localhost:5176",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
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


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):  # type: ignore[override]
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            }
        },
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

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Try again later.",
                "details": {},
            }
        },
    )

# Register routers
app.include_router(transactions_router)
app.include_router(catalog_router)
app.include_router(user_card_router)
app.include_router(user_profile_router)
app.include_router(recommendation_router)
app.include_router(card_reasoner_router)
app.include_router(rewards_earned_router)
app.include_router(auth_router, prefix="", tags=["Auth"])
app.include_router(notifications_router)

# Mount the built frontend after API routes so /api endpoints keep priority.
static_dir = (Path(__file__).resolve().parents[1] / "static")
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
