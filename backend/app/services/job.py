"""
Job Service — handles fetching, embedding, and upserting jobs into the database.

DESIGN DECISIONS:
- Upsert Logic: We use PostgreSQL's native `ON CONFLICT` via SQLAlchemy's `insert().on_conflict_do_update`.
  This allows us to run the sync endpoint multiple times without duplicating jobs.
- Batched Operations (MVP): For simplicity in the MVP, we generate embeddings sequentially.
  In a production system with hundreds of jobs, this should be sent to a Celery queue 
  or processed asynchronously in batches to avoid API rate limits.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.services.embedding import generate_embedding
from app.services.greenhouse import fetch_jobs_from_greenhouse


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
    
    # 2. Process and Upsert
    for job_data in fetched_jobs:
        # Generate the vector embedding from the cleaned description
        # Note: If the description is too long, OpenAI's API might throw an error.
        # text-embedding-3-small supports up to 8191 tokens (~32k characters).
        # We assume standard job descriptions fit within this limit.
        try:
            embedding = await generate_embedding(job_data["description"])
        except Exception as e:
            # If embedding fails (e.g. rate limit), skip this job and continue
            continue
            continue
            
        # 3. Upsert into database
        # We use Postgres INSERT ... ON CONFLICT to either create new jobs or update existing ones
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
        
    await db.commit()
    
    return {
        "processed": processed_count,
        "skipped": len(fetched_jobs) - processed_count,
        "message": "Jobs synced successfully"
    }


async def list_jobs(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Job]:
    """Retrieve a paginated list of all jobs."""
    query = select(Job).order_by(Job.fetched_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())
