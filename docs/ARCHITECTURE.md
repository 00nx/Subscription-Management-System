# Architecture

Modular monolith: one FastAPI app, one PostgreSQL database, one Celery worker image, one React SPA. No microservices.

```
Browser (React + TS) ──HTTP/JSON──▶ FastAPI ──SQLAlchemy──▶ PostgreSQL
                                       │
                                       └──enqueue──▶ Redis ──▶ Celery worker
```

## Frontend ↔ backend

- All HTTP goes through one Axios instance (`frontend/src/services/api.ts`): base URL from `VITE_API_URL`, 10 s timeout, bearer header, CSRF header, single-flight token refresh on 401, and every failure normalised into `ApiError`.
- `services/*.service.ts` wrap endpoints and return unwrapped, typed data. Components never call Axios directly.
- Server state lives in TanStack Query; keys come from `lib/queryKeys.ts` (`['resource','list'|'detail',…]`). Mutations invalidate by resource prefix.
- The signed-in user and role are fetched from the backend (`/auth/me`, via the refresh flow on page load). Route guards in `routes/ProtectedRoute.tsx` only shape navigation; **FastAPI enforces authorization independently** on every endpoint.

## Backend layout

```
app/main.py            app factory: CORS, exception handlers, router, bootstrap admin
app/core/              config, database session, security (argon2/JWT), dependencies, exceptions, rate limit, logging
app/api/v1/router.py   mounts each module's router under /api/v1
app/modules/<name>/    models.py, schemas.py, service.py, router.py (+ tests in backend/tests)
app/models/registry.py imports all module models so Alembic sees them
app/schemas/common.py  ApiResponse / Page / PageParams shared contracts
app/tasks/             Celery app + tasks
```

Layering inside a module: router (HTTP, validation) → service (business rules, transactions) → models (ORM). Routers never touch the ORM directly beyond passing a session to the service.

## Module boundaries

`accounts` is implemented. `products`, `subscriptions`, `quotations`, `billing`, `invoices`, `payments`, `discounts`, `analytics` are empty packages. Rules:

- A module owns its tables, schemas, service and router. Other modules call its **service functions**, not its tables, and don't import its router.
- Shared contracts (`core/`, `schemas/common.py`) change only through a PR reviewed by all four members.
- Cross-module foreign keys are fine (they're one database); cross-module writes go through the owning service.
- Adding a module: create the files, add its models to `models/registry.py`, include its router in `api/v1/router.py`, generate a migration.

## Background processing

`app/tasks/celery_app.py` configures Celery with Redis as broker and result backend. `sample_tasks.ping` is the only task. Phase 2 will add scheduled work (recurring invoices, renewals, expiries, reminders) as tasks in this package, plus Celery beat. The worker shares the backend image and settings, and starts only after the backend (and therefore migrations) is healthy.
