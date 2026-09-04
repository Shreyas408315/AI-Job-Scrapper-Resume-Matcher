# Matchwork frontend

React and Vite client for the AI Job Scraper and Resume Matcher.

## Run locally

```powershell
copy .env.example .env
npm install
npm run dev
```

Set `VITE_API_URL` to the FastAPI backend URL. The default is `http://localhost:8000`.

## Routes

- `/login`: register or sign in
- `/upload`: upload a PDF or DOCX resume
- `/dashboard`: sync jobs and view ranked matches
- `/matches/:matchId`: generate a match explanation

Build for deployment with `npm run build`.
