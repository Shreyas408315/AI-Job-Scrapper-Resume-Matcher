"""
FastAPI dependency injection — shared dependencies used across routers.

WHY DEPENDENCY INJECTION:
- get_db() provides a database session that's automatically committed on
  success and rolled back on error. Each request gets its own session.
- get_current_user() extracts and validates the JWT from the Authorization
  header. Adding it as a dependency to a route makes that route protected.

HOW IT WORKS:
  @router.get("/protected")
  async def protected_route(user: User = Depends(get_current_user)):
      # This only runs if the JWT is valid and the user exists
      return {"email": user.email}

SECURITY NOTES:
- HTTPBearer expects "Authorization: Bearer <token>" header format.
- JWT decode failures (expired, tampered, invalid) all return 401 with
  a generic "Invalid token" message — no details leaked.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session
from app.models.user import User

# FastAPI security scheme — adds the lock icon in OpenAPI docs
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for a single request.

    Uses a context manager to ensure the session is properly closed,
    even if an error occurs. Commits on success, rolls back on failure.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the request, return the authenticated User.

    This is used as a dependency on protected routes. If the token is invalid
    or the user doesn't exist, a 401 is raised and the route never executes.
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Look up the user in the database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
