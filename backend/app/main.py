"""
FastAPI application entry point.

This is the top-level module that:
1. Creates the FastAPI app instance
2. Configures CORS middleware (restricted to frontend origin)
3. Includes all route handlers
4. Sets up exception handling for generic error responses

SECURITY: CORS is configured with explicit allowed origins from .env,
NOT "*" (wildcard). This prevents other websites from making API calls
on behalf of a logged-in user (cross-origin attacks).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401 - ensures all models are registered in SQLAlchemy
from app.config import get_settings
from app.routers import auth, health, resume

# Configure logging — server-side only, never expose to client
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="AI Job Scraper & Resume Matcher",
    description="Upload your resume, match it against job postings, and get AI-powered improvement suggestions.",
    version="0.1.0",
    docs_url="/api/docs",    # Swagger UI
    redoc_url="/api/redoc",  # ReDoc
)

# ------------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------------
# SECURITY: Only allow requests from our frontend origin(s).
# If ALLOWED_ORIGINS=http://localhost:3000, only that origin can call
# our API from a browser. Other origins get blocked by the browser's
# CORS policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Global Exception Handler
# ------------------------------------------------------------------
# SECURITY: Catch unhandled exceptions and return a generic message.
# Never leak stack traces, SQL errors, or internal details to the client.
# The actual error is logged server-side for debugging.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )

# ------------------------------------------------------------------
# Include Routers
# ------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(resume.router)

# Future routers will be added here:
# app.include_router(jobs.router)
# app.include_router(match.router)
