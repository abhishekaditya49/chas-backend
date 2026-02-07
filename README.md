# CHAS Backend

Production-ready FastAPI backend for CHAS (Bureau of Declared Joy), backed by Supabase for PostgreSQL, Auth, and Realtime.

## Stack

- Python 3.11+
- FastAPI
- Supabase Python SDK (`supabase`)
- APScheduler
- Pydantic v2

## Project Structure

```text
chas-backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── routers/
│   ├── services/
│   ├── jobs/
│   ├── schemas/
│   └── utils/
├── supabase/migrations/001_initial_schema.sql
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Environment Variables

Copy `.env.example` to `.env` and fill values:

```bash
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_KEY=<service-role-key>
SUPABASE_HTTP_MAX_CONNECTIONS=100
SUPABASE_HTTP_MAX_KEEPALIVE_CONNECTIONS=50
SUPABASE_POSTGREST_TIMEOUT_SECONDS=30

APP_NAME=CHAS API
APP_VERSION=1.0.0
ENVIRONMENT=development
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:3000
ENABLE_SCHEDULER=true
TIMEZONE=UTC
AUTH_TOKEN_CACHE_TTL_SECONDS=15
AUTH_TOKEN_CACHE_MAX_ENTRIES=1024
SLOW_REQUEST_LOG_THRESHOLD_MS=0
SLOW_QUERY_LOG_THRESHOLD_MS=0
MEMBERSHIP_CACHE_TTL_SECONDS=20
USER_CACHE_TTL_SECONDS=30
DATA_CACHE_MAX_ENTRIES=5000
ENFORCE_INVITE_WHITELIST=true
WHITELIST_CACHE_TTL_SECONDS=300
```

## Local Development

```bash
cd chas-backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Running Tests and Lint

```bash
pytest -v
ruff check .
```

## API Overview

- Auth: `/auth/*` (session, access status, invite redemption)
- Communities: `/communities/*`
- Chamber: `/communities/{community_id}/chamber/*`
- Gazette: `/communities/{community_id}/gazette/*`
- Ledger: `/communities/{community_id}/ledger`
- Members: `/communities/{community_id}/members/*`
- Leaderboard/Jashn: `/communities/{community_id}/leaderboard`, `/jashn`
- Elections: `/communities/{community_id}/elections/*`
- Notifications: `/notifications/*`
- Sunset: `/communities/{community_id}/sunset`
- Balance: `/communities/{community_id}/balance`

All non-public endpoints require:

```text
Authorization: Bearer <supabase_jwt>
```

## Supabase Integration Model

- Frontend authenticates directly with Supabase Auth.
- Backend validates bearer JWT using `supabase.auth.get_user(token)`.
- Backend enforces invite-whitelist access before protected routes.
- Backend performs business logic writes with the service-role key.
- Frontend receives realtime updates directly from Supabase Realtime.

## Scheduled Jobs

Configured with APScheduler in `app/jobs/scheduler.py`:

- `daily_reset` at 00:00
- `daily_sunset` at 23:59
- `weekly_jashn` Sunday 00:05
- `tip_to_tip_expiry` every 15 minutes

Set `ENABLE_SCHEDULER=false` for horizontally scaled worker replicas where only one instance should run jobs.

## Deployment

### Docker

```bash
docker build -t chas-backend .
docker run -p 8000:8000 --env-file .env chas-backend
```

### Production Checklist

- Set `ENVIRONMENT=production`
- Restrict `ALLOWED_ORIGINS`
- Apply Supabase migrations in `supabase/migrations/*.sql`
- Enable Realtime replication for required tables
- Configure Google OAuth provider in Supabase
- Run one scheduler instance only
- Monitor logs and error rates
