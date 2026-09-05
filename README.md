# AI Job Scraper & Resume Matcher

A focused MVP that uploads a PDF/DOCX resume, embeds it, imports structured Greenhouse job postings, ranks jobs with pgvector cosine similarity, and generates validated LLM match explanations.

## Architecture

- FastAPI monolith in `backend/`
- PostgreSQL with the pgvector extension
- SQLAlchemy async ORM and Alembic migrations
- OpenAI embeddings and structured match explanations
- React + Vite frontend in `frontend/`
- Docker Compose for local PostgreSQL; Dockerfile for backend deployment

The system deliberately avoids microservices, queues, OAuth, and HTML scraping. Greenhouse's public JSON board API is more stable and legally clearer than scraping major job boards.

## Run locally

Start PostgreSQL and pgvector:

```powershell
docker compose up -d
```

Configure the backend:

```powershell
copy .env.example backend/.env
```

Set a random `SECRET_KEY` of at least 32 characters and add `OPENAI_API_KEY` in `backend/.env`. Then run migrations and the API:

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Run the React client separately:

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

API docs are available at `http://localhost:8000/api/docs`; the frontend runs at `http://localhost:5173`.

## Verification

```powershell
cd backend
$env:SECRET_KEY = "a-local-development-secret-that-is-at-least-32-chars"
python -m pytest -q
python -m compileall -q app

cd ..\frontend
npm run build
```

## Security controls

- Secrets load from environment variables; `.env` is ignored.
- JWT-protected resume, job, and match endpoints.
- Uploaded files are bounded to 5 MB and checked by content signatures.
- Resume access is scoped to the owning user; deletion cascades matches.
- SQLAlchemy ORM avoids string-formatted SQL.
- Greenhouse board tokens are allowlisted; arbitrary URLs are never fetched.
- Job sync and match/LLM routes have an in-memory MVP rate limiter.
- LLM prompts use a fixed system instruction and pass scraped text as untrusted JSON data.
- CORS uses explicit configured origins, not `*`.
- Generic client errors avoid exposing parser, database, or provider details.
- HTTPS is required when deployed.

The rate limiter is intentionally process-local for this MVP. A multi-instance deployment should replace it with a shared Redis-backed limiter.

## Interview notes

- **Embeddings + cosine similarity:** semantic similarity catches related experience even when resume and job wording differs; keyword matching is brittle.
- **Structured LLM output:** Pydantic validation gives the frontend a predictable contract instead of parsing fragile free text.
- **Structured job API:** Greenhouse JSON is reliable and avoids scraping ToS and maintenance problems.
- **pgvector trade-off:** storing vectors in Postgres keeps the MVP to one database; a separate vector store could scale independently but adds operational complexity.
- **Next improvements:** shared rate limiting, background job processing, refresh-token/session strategy, stronger upload malware scanning, and observability.

Deployment instructions are in [DEPLOYMENT.md](DEPLOYMENT.md).
