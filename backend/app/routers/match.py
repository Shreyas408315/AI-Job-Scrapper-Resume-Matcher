"""Authenticated endpoints for semantic resume matching."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.match import MatchExplanation, MatchRequest, MatchResponse, MatchResult
from app.services.match import explain_match, rank_matches

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.post("/{resume_id}", response_model=MatchResponse)
async def create_matches(
    resume_id: UUID,
    request: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the top jobs for an authenticated user's resume."""
    matches = await rank_matches(resume_id, current_user, request.top_n, db)
    results = [
        MatchResult(
            id=match.id,
            job_id=match.job_id,
            job_title=match.job.title,
            company=match.job.company,
            location=match.job.location,
            job_url=match.job.url,
            similarity_score=match.similarity_score,
            llm_explanation=match.llm_explanation,
        )
        for match in matches
    ]
    return MatchResponse(
        resume_id=resume_id,
        total_matches=len(results),
        matches=results,
    )


@router.post("/detail/{match_id}/explain", response_model=MatchExplanation)
async def create_match_explanation(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a validated LLM explanation for an owned match."""
    match = await explain_match(match_id, current_user, db)
    return MatchExplanation.model_validate(match.llm_explanation)