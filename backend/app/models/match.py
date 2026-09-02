"""
Match model — stores the result of comparing a resume against a job.

DESIGN DECISIONS:
- similarity_score is the cosine similarity (0 to 1) computed by pgvector.
  Higher = more similar. This is a pure math score, no LLM involved.
- llm_explanation is JSONB containing the LLM's structured analysis:
  {
      "match_score_reasoning": "string explaining why the score is what it is",
      "missing_skills": ["skill1", "skill2"],
      "resume_improvement_tips": ["tip1", "tip2", "tip3"]
  }
- The JSONB column is nullable because matching (Day 4) happens before
  LLM explanation (Day 5) — we fill it in a separate step.
- UniqueConstraint on (resume_id, job_id) prevents duplicate match records.

WHY JSONB (not separate columns):
- The LLM output is semi-structured — lists of varying length.
- JSONB lets us query into the JSON if needed (Postgres supports JSON operators).
- Simpler than creating extra tables for missing_skills and tips.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Match(Base):
    __tablename__ = "matches"

    # Prevent duplicate match records for the same resume-job pair
    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", name="uq_resume_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    llm_explanation: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,  # Filled by LLM service after initial matching
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    resume = relationship("Resume", back_populates="matches")
    job = relationship("Job", back_populates="matches")
