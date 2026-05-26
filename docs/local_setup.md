# Local Setup

## Option 1: Fast local mode

1. Copy `.env.example` to `.env`
   - for production-like local testing, set `FIELD_ENCRYPTION_KEY` so provider tokens and webhook secrets are encrypted with a dedicated key at rest
   - to enable Google sign-in and Google Meet integration, fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_AUTH_REDIRECT_URI`, and `GOOGLE_OAUTH_REDIRECT_URI`
   - to enable Zoom auto-scheduling with real meeting creation, fill in `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, and `ZOOM_OAUTH_REDIRECT_URI`
   - to enable HireOS-delivered interview invite emails, fill in `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, and `SMTP_USE_TLS`
   - if SMTP is not configured, HireOS falls back to writing invite payloads to `data/email_outbox/` for local testing
   - to tune outbound ATS webhook behavior, optionally set `ATS_WEBHOOK_TIMEOUT_SECONDS`; the actual webhook URL, token, and signing secret are configured from the in-app `Settings` page
2. One command:
   - `bash scripts/run_everything.sh`
   - or `make run-all`
   - the script auto-clears stale listeners on ports `3000` and `8000` before starting, and removes an old project-local `Next.js` dev lock when necessary
3. Backend:
   - `cd backend`
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `python seed.py`
   - `python -m uvicorn app.main:app --reload`
4. Frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`

## Option 2: Full local stack

- `make up`
- `make kafka-topics`

This brings up frontend, backend, PostgreSQL, Redis, Qdrant, Redpanda, Kafka UI, MinIO, Prometheus, and Grafana.

## Demo credentials

- Recruiter: `recruiter1@hireos.ai / Demo@123`
- Admin: `admin@hireos.ai / Demo@123`
