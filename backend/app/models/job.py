"""
Job model — stores job postings fetched from Greenhouse's public API.

DESIGN DECISIONS:
- external_id stores the Greenhouse job ID. It's unique so we can upsert
  (skip jobs we've already fetched) instead of creating duplicates.
- description stores the raw HTML content from Greenhouse. We convert to
  plain text before embedding, but keep HTML for display if needed.
- company stores the board_token (e.g., "airbnb") which identifies the
  company on Greenhouse.
- embedding is pgvector VECTOR, same dimension as resume embeddings
  (must match for cosine similarity to work).

WHY GREENHOUSE:
- Public JSON API, no auth required for GET requests.
- Structured, reliable data — no HTML scraping, no ToS violations.
- URL: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.config import get_settings


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    external_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=True,  # Some jobs don't have a location
    )
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    # pgvector column — same dimensions as resume embeddings
    embedding = mapped_column(
        Vector(get_settings().VECTOR_DIMENSIONS),
        nullable=True,  # Filled after description is embedded
    )
    fetched_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    matches = relationship("Match", back_populates="job", cascade="all, delete-orphan")

    @property
    def has_embedding(self) -> bool:
        """Expose embedding availability without returning the vector itself."""
        return self.embedding is not None
