"""
Auth request/response schemas — validated by Pydantic before reaching our code.

WHY PYDANTIC SCHEMAS (not raw dicts):
- Automatic validation: invalid email format, missing fields, wrong types
  are all caught BEFORE our business logic runs.
- Self-documenting: FastAPI auto-generates OpenAPI docs from these schemas.
- Separation of concerns: DB models (SQLAlchemy) vs API contracts (Pydantic)
  are kept separate, so internal DB changes don't leak to the API.
"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration payload."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login payload."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token returned after successful register/login."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user info (never includes password hash)."""
    id: str
    email: str

    model_config = {"from_attributes": True}
