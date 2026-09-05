"""
Match request/response schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    """A single match between a resume and a job."""
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company: str
    location: str | None
    job_url: str
    job_description: str
    similarity_score: float
    llm_explanation: dict | None  # Populated after LLM analysis

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    """Ranked list of matches for a resume."""
    resume_id: uuid.UUID
    total_matches: int
    matches: list[MatchResult]


class MatchRequest(BaseModel):
    """Request to trigger matching for a resume."""
    top_n: int = Field(default=10, ge=1, le=100)  # How many top matches to return


class MatchExplanation(BaseModel):
    """Validated structured output returned by the explanation model."""
    match_score_reasoning: str = Field(min_length=1, max_length=4000)
    missing_skills: list[str] = Field(default_factory=list, max_length=30)
    resume_improvement_tips: list[str] = Field(min_length=2, max_length=4)
