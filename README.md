# Brightloop

Subscription management system (products, plans, quotations, subscriptions, recurring billing, invoices, payments, analytics).

**Status: Phase 1 scaffolding.** Auth, roles, infrastructure and placeholder screens work; business modules are empty packages for Phase 2. See [docs/](docs/).

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui-style components (Radix), React Router, Axios, TanStack Query, React Hook Form + Zod, Recharts, Lucide |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, PyJWT, argon2-cffi |
| Data / jobs | PostgreSQL 16, Redis 7, Celery |

## Prerequisites

Python 3.12+, Node 22+, PostgreSQL 16 and Redis 7.

## Quick start

Create the database (once):

```bash
createdb -O brightloop brightloop
```

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # set SECRET_KEY (32+ chars) and DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload   # terminal 1
celery -A app.tasks.celery_app worker -l info   # terminal 2
```

Frontend:

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

| URL | What |
|---|---|
| http://localhost:5173 | Frontend |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/api/v1/health/ | DB + Redis health |

Verify the stack:

1. Open the frontend, **Create account**, then **Log in** (you land on the customer dashboard).
2. Log in as the bootstrap admin (`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`); **Users** lists real accounts from the API.
3. Check Celery end to end (admin only), after logging in via Swagger's *Authorize* button:
   `POST /api/v1/health/celery/` → `{"result": "pong"}`. Or from a shell:
   ```bash
   cd backend && celery -A app.tasks.celery_app call app.tasks.sample_tasks.ping
   ```
4. PostgreSQL: `GET /api/v1/health/` returns `"database": "ok"`.

## Tests

```bash
# Backend: needs Postgres + Redis. Uses the `brightloop_test` database (created beforehand) and runs the Alembic migrations.
cd backend && python -m pytest
# override the target DB/Redis with DATABASE_URL / REDIS_URL if yours differ from the defaults in tests/conftest.py

# Frontend
cd frontend && npm test && npm run typecheck
```

Create the test database once: `createdb -O brightloop brightloop_test` (or `CREATE DATABASE brightloop_test;`).

## Docs

[ARCHITECTURE](docs/ARCHITECTURE.md) · [DATABASE](docs/DATABASE.md) · [API](docs/API.md) · [CONTRIBUTING](docs/CONTRIBUTING.md)
