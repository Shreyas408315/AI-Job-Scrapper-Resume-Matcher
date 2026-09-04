from uuid import uuid4

import pytest
import pytest_asyncio

from app.database import async_session, engine
from fastapi import HTTPException
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.match import MatchRequest
from app.services.auth import hash_password
from app.services.match import rank_matches


VECTOR_SIZE = 1536


@pytest_asyncio.fixture(autouse=True)
async def dispose_database_pool():
    await engine.dispose()
    yield
    await engine.dispose()


def vector(index: int, second_index: int | None = None) -> list[float]:
    values = [0.0] * VECTOR_SIZE
    values[index] = 1.0
    if second_index is not None:
        values[second_index] = 1.0
    return values


@pytest.mark.asyncio
async def test_rank_matches_orders_by_cosine_similarity_and_upserts():
    async with async_session() as db:
        unique_index = uuid4().int % VECTOR_SIZE
        weaker_index = (unique_index + 1) % VECTOR_SIZE
        user = User(
            email=f"day4-{uuid4()}@example.com",
            hashed_password=hash_password("SuperSecretPassword123"),
        )
        resume = Resume(
            user=user,
            filename="resume.pdf",
            file_type="pdf",
            extracted_text="backend engineer",
            embedding=vector(unique_index),
        )
        best_job = Job(
            external_id=uuid4().int % 2_000_000_000,
            title="Backend Engineer",
            company="Day4 Test",
            description="Build APIs",
            location="Remote",
            url="https://example.com/best",
            embedding=vector(unique_index),
        )
        weaker_job = Job(
            external_id=uuid4().int % 2_000_000_000,
            title="Data Analyst",
            company="Day4 Test",
            description="Analyze reports",
            location="Remote",
            url="https://example.com/weaker",
            embedding=vector(unique_index, weaker_index),
        )
        db.add_all([user, resume, best_job, weaker_job])
        await db.flush()

        try:
            matches = await rank_matches(resume.id, user, 2, db)
            await db.flush()

            assert [match.job_id for match in matches] == [best_job.id, weaker_job.id]
            assert matches[0].similarity_score > matches[1].similarity_score

            first_run_ids = [match.id for match in matches]
            second_run = await rank_matches(resume.id, user, 2, db)
            assert [match.id for match in second_run] == first_run_ids
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_rank_matches_rejects_resume_owned_by_another_user():
    async with async_session() as db:
        owner = User(
            email=f"day4-owner-{uuid4()}@example.com",
            hashed_password=hash_password("SuperSecretPassword123"),
        )
        other_user = User(
            email=f"day4-other-{uuid4()}@example.com",
            hashed_password=hash_password("SuperSecretPassword123"),
        )
        resume = Resume(
            user=owner,
            filename="resume.pdf",
            file_type="pdf",
            extracted_text="backend engineer",
            embedding=vector(0),
        )
        db.add_all([owner, other_user, resume])
        await db.flush()

        with pytest.raises(HTTPException) as error:
            await rank_matches(resume.id, other_user, 10, db)

        assert error.value.status_code == 404


def test_match_request_limits_top_n():
    assert MatchRequest().top_n == 10
    with pytest.raises(ValueError):
        MatchRequest(top_n=0)
    with pytest.raises(ValueError):
        MatchRequest(top_n=101)
