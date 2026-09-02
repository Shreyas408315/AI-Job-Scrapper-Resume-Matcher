"""
Resume request/response schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    """Resume metadata returned to the frontend (never includes extracted_text)."""
    id: uuid.UUID
    filename: str
    file_type: str
    uploaded_at: datetime
    has_embedding: bool  # True if embedding has been generated

    model_config = {"from_attributes": True}


class ResumeUploadResponse(BaseModel):
    """Response after a successful resume upload."""
    id: uuid.UUID
    filename: str
    message: str = "Resume uploaded and processed successfully"
