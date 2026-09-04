# Deployment

The backend is a containerized FastAPI service. It needs a hosted PostgreSQL database with the `vector` extension enabled.

## Required environment variables

Set these in the hosting provider dashboard. Do not commit a `.env` file.

- `DATABASE_URL`: hosted PostgreSQL connection URL
- `SECRET_KEY`: random value with at least 32 characters
- `OPENAI_API_KEY`: OpenAI API key for embeddings and explanations
- `ALLOWED_ORIGINS`: comma-separated frontend URL(s)
- `GREENHOUSE_BOARD_WHITELIST`: approved Greenhouse board tokens

Optional settings are documented in `.env.example`.

## Deploy the backend

1. Create a PostgreSQL database and enable the `vector` extension.
2. Create a web service from this repository using the root `Dockerfile`.
3. Expose port `8000`; the container also respects the provider's `PORT` variable.
4. Add the required environment variables.
5. Deploy. The container runs `alembic upgrade head` before starting FastAPI.
6. Verify `GET /api/health` and open `/api/docs`.

The local database remains available with:

```powershell
docker compose up -d
```

The current repository contains the backend only. The React frontend should be deployed separately after Day 6 and its URL added to `ALLOWED_ORIGINS`.
