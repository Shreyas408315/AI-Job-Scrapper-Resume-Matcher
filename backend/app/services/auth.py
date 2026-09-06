"""
Auth service — handles user registration, login, and JWT token creation.

WHY BCRYPT:
- bcrypt is a slow-by-design hashing algorithm. "Slow" is a feature here:
  it makes brute-force password cracking expensive. Fast hashes like SHA-256
  can be cracked at billions of attempts/second; bcrypt limits to ~thousands.
- passlib's CryptContext handles salt generation, hash versioning, and
  algorithm upgrades automatically.

WHY JWT (not session cookies):
- Stateless: the server doesn't need to store session data. The token itself
  contains the user ID and expiration. This simplifies our single-service
  architecture.
- Standard: JWTs are widely understood, well-documented, and supported by
  every frontend framework. Easy to explain in interviews.

SECURITY NOTES:
- Tokens are signed with SECRET_KEY (HS256). Anyone with the key can forge tokens,
  so the SECRET_KEY must NEVER be committed or leaked.
- Token expiry (24h default) limits damage if a token is stolen.
- We return generic "Invalid credentials" on login failure — never revealing
  whether the email or password was wrong (prevents enumeration).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    salt = bcrypt.gensalt()
    pwd_bytes = password.encode('utf-8')
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT containing the user ID and expiration time.

    The "sub" (subject) claim holds the user ID. The "exp" claim is
    checked automatically by PyJWT on decode — expired tokens
    raise jwt.ExpiredSignatureError.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def register_user(email: str, password: str, db: AsyncSession) -> User:
    """
    Register a new user. Returns the created User object.

    Raises HTTP 400 if the email is already taken.
    """
    # Check for existing user
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()  # Assigns the UUID id without committing the transaction
    return user


async def login_user(email: str, password: str, db: AsyncSession) -> str:
    """
    Authenticate a user and return a JWT token.

    Returns generic error message on failure — never reveals whether
    the email exists or the password was wrong (prevents enumeration).
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        # SECURITY: Generic message — don't say "email not found" vs "wrong password"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return create_access_token(str(user.id))
