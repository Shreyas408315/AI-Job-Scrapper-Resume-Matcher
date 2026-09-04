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

The React frontend lives in `frontend/` and can be deployed as a static Vite site. Set `VITE_API_URL` to the deployed backend URL before building, then add the frontend URL to the backend's `ALLOWED_ORIGINS`.

For local development:

```powershell
cd frontend
copy .env.example .env
npm run dev
```

The local frontend runs at `http://localhost:5173` and calls the backend at `http://localhost:8000`.
