"""
Resume model — stores uploaded resume metadata, extracted text, and embedding.

DESIGN DECISIONS:
- extracted_text is stored so we can re-embed if the embedding model changes,
  without requiring the user to re-upload.
- embedding is a pgvector VECTOR column. Dimension (1536) matches
  OpenAI's text-embedding-3-small model. If you switch models, update
  VECTOR_DIMENSIONS in .env and run a migration.
- The embedding is nullable because text extraction and embedding happen
  after the initial upload — it's filled in during processing.

SECURITY NOTES:
- extracted_text contains PII (personal resume data). It is NEVER logged.
- user_id FK with ON DELETE CASCADE ensures resume data is cleaned up
  when a user account is deleted (data rights compliance).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.config import get_settings


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(10),  # "pdf" or "docx"
        nullable=False,
    )
    extracted_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # pgvector column — stores the embedding as a float array
    # Dimension is configurable via VECTOR_DIMENSIONS env var
    embedding = mapped_column(
        Vector(get_settings().VECTOR_DIMENSIONS),
        nullable=True,  # Filled after text extraction + embedding generation
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    user = relationship("User", back_populates="resumes")
    matches = relationship("Match", back_populates="resume", cascade="all, delete-orphan")
