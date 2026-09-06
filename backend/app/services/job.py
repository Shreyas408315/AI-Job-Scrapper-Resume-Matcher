"""
Job Service — handles fetching, embedding, and upserting jobs into the database.

DESIGN DECISIONS:
- Upsert Logic: We use PostgreSQL's native `ON CONFLICT` via SQLAlchemy's `insert().on_conflict_do_update`.
  This allows us to run the sync endpoint multiple times without duplicating jobs.
- Inter-request Delay: We insert a small 0.2s pause between embedding requests to
  stay well under the LLM provider's rate limit *proactively*. The exponential backoff
  in embedding.py handles cases where we still get throttled.
- Graceful Degradation: If one job fails to embed (e.g., after all retries are exhausted),
  we skip it and continue with the remaining jobs rather than crashing the entire sync.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.services.embedding import generate_embedding
from app.services.greenhouse import fetch_jobs_from_greenhouse

logger = logging.getLogger(__name__)

# Small delay between sequential embedding calls to avoid hitting rate limits
INTER_REQUEST_DELAY = 0.2  # seconds


async def sync_greenhouse_jobs(board_token: str, db: AsyncSession) -> dict:
    """
    Fetch jobs from Greenhouse, generate embeddings, and upsert them into the DB.
    
    Returns a summary dict of how many jobs were processed.
    """
    normalized_token = board_token.strip().lower()
    if normalized_token not in get_settings().greenhouse_whitelist:
        raise ValueError("Greenhouse board is not allowed")

    # 1. Fetch from Greenhouse
    fetched_jobs = await fetch_jobs_from_greenhouse(normalized_token)
    
    if not fetched_jobs:
        return {"processed": 0, "skipped": 0, "message": "No jobs found"}
        
    processed_count = 0
    skipped_count = 0
    
    # 2. Process and Upsert
    for i, job_data in enumerate(fetched_jobs):
        try:
            embedding = await generate_embedding(job_data["description"])
        except Exception as e:
            # After all retries are exhausted, skip this job gracefully
            logger.warning(
                "Skipping job %s (external_id=%s): embedding failed after retries: %s",
                job_data["title"], job_data["external_id"], e,
            )
            skipped_count += 1
            continue
            
        # 3. Upsert into database
        stmt = insert(Job).values(
            external_id=job_data["external_id"],
            title=job_data["title"],
            company=job_data["company"],
            description=job_data["description"],
            location=job_data["location"],
            url=job_data["url"],
            embedding=embedding
        )
        
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['external_id'],
            set_={
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "location": stmt.excluded.location,
                "url": stmt.excluded.url,
                "embedding": stmt.excluded.embedding,
                "fetched_at": stmt.excluded.fetched_at
            }
        )
        
        await db.execute(upsert_stmt)
        processed_count += 1

        # Proactive rate-limit avoidance: small pause between embedding calls
        if i < len(fetched_jobs) - 1:
            await asyncio.sleep(INTER_REQUEST_DELAY)
        
    await db.commit()
    
    logger.info(
        "Greenhouse sync complete for '%s': %d processed, %d skipped",
        normalized_token, processed_count, skipped_count,
    )
    
    return {
        "processed": processed_count,
        "skipped": skipped_count,
        "message": "Jobs synced successfully"
    }


async def list_jobs(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Job]:
    """Retrieve a paginated list of all jobs."""
    query = select(Job).order_by(Job.fetched_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())

