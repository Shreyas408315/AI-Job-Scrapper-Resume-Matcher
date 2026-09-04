"""
Application configuration — loaded from environment variables via .env file.

WHY PYDANTIC SETTINGS:
- Type-safe: validates env vars at startup, not at runtime when they're first used.
- Single source of truth: every configurable value is declared in one place.
- Defaults: provides safe local-dev defaults so the app starts without a .env file.

SECURITY: All secrets (API keys, DB password, JWT secret) come from environment
variables. The .env file is in .gitignore and never committed. The JWT secret
is required at startup rather than having a predictable fallback.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings loaded from the .env file or environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/jobmatcher"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        """Accept hosted provider URLs while keeping SQLAlchemy async."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # --- Auth ---
    # No fallback is provided: a predictable signing key would let attackers
    # forge tokens in any environment where the setting was overlooked.
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 1440  # 24 hours

    # --- LLM Provider ---
    LLM_PROVIDER: str = "openai"  # "openai" or "anthropic"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # --- Embeddings ---
    VECTOR_DIMENSIONS: int = 1536  # Matches text-embedding-3-small
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- CORS ---
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- File Uploads ---
    MAX_UPLOAD_SIZE_MB: int = 5

    # --- Greenhouse Job Board ---
    GREENHOUSE_BOARD_WHITELIST: str = "airbnb,spotify,figma,cloudflare"

    # --- Derived properties (not loaded from env) ---

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def greenhouse_whitelist(self) -> list[str]:
        """Parse comma-separated board tokens into a lowercase list."""
        return [token.strip().lower() for token in self.GREENHOUSE_BOARD_WHITELIST.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        """Convert MB limit to bytes for file validation."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance — parsed once, reused everywhere.

    WHY LRU_CACHE: Parsing .env and validating types is work we only need to
    do once per process lifetime. lru_cache ensures Settings() is called exactly
    once, and all subsequent calls return the same object.
    """
    return Settings()
