"""Resume-to-job matching using pgvector cosine similarity."""

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.services.llm import generate_match_explanation

logger = logging.getLogger(__name__)


async def rank_matches(
    resume_id: UUID,
    user: User,
    top_n: int,
    db: AsyncSession,
) -> list[Match]:
    """Rank jobs for an owned, embedded resume and persist the results."""
    resume_query = select(Resume).where(
        Resume.id == resume_id,
        Resume.user_id == user.id,
    )
    resume = (await db.execute(resume_query)).scalar_one_or_none()

    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    if resume.embedding is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume does not have an embedding yet.",
        )

    similarity = (1 - Job.embedding.cosine_distance(resume.embedding)).label("similarity_score")
    ranked_query = (
        select(Job, similarity)
        .where(Job.embedding.is_not(None))
        .order_by(similarity.desc())
        .limit(top_n)
    )
    ranked_jobs = (await db.execute(ranked_query)).all()

    for job, score in ranked_jobs:
        match_insert = insert(Match).values(
            resume_id=resume.id,
            job_id=job.id,
            similarity_score=float(score),
        )
        match_upsert = match_insert.on_conflict_do_update(
            constraint="uq_resume_job",
            set_={"similarity_score": match_insert.excluded.similarity_score},
        )
        await db.execute(match_upsert)

    if not ranked_jobs:
        return []

    job_ids = [job.id for job, _ in ranked_jobs]
    matches_query = (
        select(Match).options(selectinload(Match.job))
        .where(Match.resume_id == resume.id, Match.job_id.in_(job_ids))
        .order_by(Match.similarity_score.desc())
    )
    return list((await db.execute(matches_query)).scalars().all())


async def explain_match(match_id: UUID, user: User, db: AsyncSession) -> Match:
    """Generate and persist an explanation for an owned match."""
    match_query = (
        select(Match)
        .options(selectinload(Match.resume), selectinload(Match.job))
        .join(Resume, Match.resume_id == Resume.id)
        .where(Match.id == match_id, Resume.user_id == user.id)
    )
    match = (await db.execute(match_query)).scalar_one_or_none()

    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")

    try:
        explanation = await generate_match_explanation(
            match.resume.extracted_text,
            match.job.title,
            match.job.description,
        )
    except Exception as exc:
        logger.exception("Match explanation generation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate match explanation right now.",
        ) from exc

    match.llm_explanation = explanation.model_dump()
    await db.flush()
    return match


async def get_owned_match(match_id: UUID, user: User, db: AsyncSession) -> Match:
    """Load one match and its job only when it belongs to the user."""
    match_query = (
        select(Match)
        .options(selectinload(Match.job))
        .join(Resume, Match.resume_id == Resume.id)
        .where(Match.id == match_id, Resume.user_id == user.id)
    )
    match = (await db.execute(match_query)).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    return match