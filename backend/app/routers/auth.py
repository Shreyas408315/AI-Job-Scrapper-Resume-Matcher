"""
Auth router — register and login endpoints.

These are the ONLY public endpoints (no JWT required).
All other endpoints require authentication via get_current_user dependency.

DESIGN: "Thin routers" pattern — the router handles HTTP concerns (parsing
request, returning response), while business logic lives in services/auth.py.
This makes the logic testable without needing HTTP.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth import create_access_token, login_user, register_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.

    Returns a JWT token immediately so the user doesn't need to
    log in again after registration.
    """
    user = await register_user(request.email, request.password, db)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Log in with email and password.

    Returns a JWT token valid for 24 hours (configurable via JWT_EXPIRY_MINUTES).
    """
    token = await login_user(request.email, request.password, db)
    return TokenResponse(access_token=token)
