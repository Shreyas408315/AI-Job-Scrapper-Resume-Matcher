"""
Job request/response schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    """Job posting as returned by the API."""
    id: uuid.UUID
    external_id: int
    title: str
    company: str
    description: str
    location: str | None
    url: str
    fetched_at: datetime
    has_embedding: bool

    model_config = {"from_attributes": True}


class JobFetchRequest(BaseModel):
    """Request to fetch jobs from a Greenhouse board."""
    board_token: str  # e.g., "airbnb", "spotify"


class JobFetchResponse(BaseModel):
    """Result of a job fetch operation."""
    jobs_fetched: int
    jobs_new: int
    board_token: str
