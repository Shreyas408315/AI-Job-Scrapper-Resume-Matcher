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


class JobSyncResponse(BaseModel):
    """Summary returned after syncing a Greenhouse board."""
    processed: int
    skipped: int
    message: str
