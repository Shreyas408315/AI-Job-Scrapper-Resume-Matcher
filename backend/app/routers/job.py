"""
Job Router — endpoints for syncing and listing jobs.

SECURITY:
- The sync endpoint could be vulnerable to SSRF (Server-Side Request Forgery) if we
  allow users to pass arbitrary URLs. By ONLY accepting the `board_token` string
  and hardcoding the base URL `https://boards-api.greenhouse.io` in the service,
  we eliminate SSRF risks completely.
- Only authenticated users can list or sync jobs.
"""

import httpx
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.job import JobResponse, JobSyncResponse
from app.services.job import list_jobs, sync_greenhouse_jobs

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/sync/{board_token}", response_model=JobSyncResponse, status_code=status.HTTP_200_OK)
async def trigger_job_sync(
    board_token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a manual sync of jobs from a specific Greenhouse board token.
    
    Example tokens: 'openai', 'stripe', 'discord'.
    This endpoint will fetch the JSON, extract descriptions, generate vectors,
    and upsert them into the database.
    """
    # Basic validation to prevent completely malformed tokens
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", board_token.lower()):
        raise HTTPException(status_code=400, detail="Invalid board token format.")
        
    try:
        result = await sync_greenhouse_jobs(board_token, db)
        return JobSyncResponse(**result)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Greenhouse board not found.")
        raise HTTPException(status_code=502, detail="Could not fetch jobs right now.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Greenhouse board is not allowed.")
    except Exception:
        raise HTTPException(status_code=500, detail="Could not sync jobs right now.")


@router.get("", response_model=list[JobResponse])
async def get_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all available jobs in the local database.
    Does not fetch from Greenhouse; only returns jobs we have already synced and embedded.
    """
    jobs = await list_jobs(db, limit, offset)
    return jobs
