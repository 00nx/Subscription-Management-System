# Brightloop

Subscription management system: products and variants, plans, quotations, subscriptions, **automated recurring billing**, invoices with PDFs, taxes, discounts, payments (manual, simulated gateway and **Razorpay Test Mode**), HTML emails with delivery tracking, a customer portal with self-service, overdue tracking, financial dashboards, reports (CSV + PDF), notifications and an audit log.

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui-style components (Radix), React Router, Axios, TanStack Query, React Hook Form + Zod, Recharts, Lucide |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, PyJWT, argon2-cffi, fpdf2 (invoice PDFs) |
| Data / jobs | PostgreSQL 16, Redis 7, Celery (worker + beat) |

Roles: **ADMIN** (everything), **STAFF** (daily operations, read-only catalogue, no revenue figures), **CUSTOMER** (own portal only). Authorisation is enforced by the API on every request.

## Quick start (no database install)

You need **only Python 3.12+** (tick "Add to PATH" on Windows) and **Node.js 20+**. The data lives in one SQLite file, so there is nothing else to install.

```bat
run.cmd                 rem Windows (double-click works; the window stays open)
```
```bash
python dev.py           # any OS
```

First run: creates a virtualenv and installs dependencies, writes `backend/.env` with a generated secret, creates the database (`brightloop-demo.db`), loads demo data, then starts the API and the frontend (and the Celery worker + scheduler if a Redis server happens to be running). Open **http://localhost:5173**. **Ctrl+C** stops everything; logs are in `logs/`.

Demo logins (development data only):

| Account | Password |
|---|---|
| `admin@brightloop.dev` | `Admin@12345` |
| `staff1@brightloop.dev`, `staff2@brightloop.dev` | `Staff@12345` |
| `alice@example.com` (also bob, chitra, dev, elena, farid) | `Customer@12345` |

Other commands: `python dev.py setup | seed | razorpay` (`razorpay` checks the Razorpay setup; run it in a second window). To start over, delete `brightloop-demo.db`.

**Redis is optional.** Without it everything works except the background worker and scheduler: use **Billing → Run billing now** instead of the hourly job.

**SQLite is the demo database.** It is perfect for trying and demoing the app, but it differs from PostgreSQL in ways that matter for real money:
- Money is stored as SQLite `REAL` and rounded back to 2 decimals when read (PostgreSQL stores exact `NUMERIC(12,2)`).
- There are no row-level locks: every write transaction takes a database-wide write lock instead, so concurrent writers queue. That is safe but serialises everything, and it was only tested at demo scale.
- The schema is created from the models (no Alembic migrations) and invoice/subscription numbers come from a counter table.
- The `--bulk` performance seed is PostgreSQL-only.

For real billing use PostgreSQL: `python dev.py --postgres` / `run-postgres.cmd` (install PostgreSQL 16 first; it asks once for the `postgres` password to create the app's role and database).



## Try the main workflow

1. Visit `/pricing` (public plans) or register at `/register`, log in, and subscribe to a plan yourself from **Plans** (active immediately, first invoice ready to pay). 2. As admin: **Products** (add a variant), **Plans**. 3. As staff/admin: **Quotations → New**, send, confirm, **Convert to subscription**, then **Activate** it. 4. **Billing → Run billing now** generates the invoice (the scheduler does this hourly on its own). 5. As the customer: **My Invoices** → download the PDF → **Pay** (test gateway: approve, decline or cancel; partial payments work). 6. As admin: **Dashboard** shows collected revenue, MRR, outstanding; **Reports** export CSV.

## Manual local development (PostgreSQL or SQLite)

With no `DATABASE_URL` the backend uses SQLite and creates its own schema. For PostgreSQL run Postgres (and Redis for Celery) and set `DATABASE_URL`, then:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set SECRET_KEY (32+ chars); DATABASE_URL only for PostgreSQL
alembic upgrade head              # PostgreSQL only; SQLite creates its schema on startup
python -m app.seed                # optional demo data
uvicorn app.main:app --reload     # terminal 1
celery -A app.tasks.celery_app worker -l info   # terminal 2
celery -A app.tasks.celery_app beat -l info     # terminal 3 (scheduler)
```

```bash
cd frontend && cp .env.example .env && npm ci && npm run dev    # http://localhost:5173
```

## Known limitations

- **Razorpay Test Mode** works end to end with your own `rzp_test_` keys (see [docs/RAZORPAY.md](docs/RAZORPAY.md)); live keys are refused by design. `run.cmd razorpay` checks the setup step by step.
- Outbound email goes through the console backend unless `SMTP_HOST` is set; real SMTP delivery has not been exercised. Emails are queued after commit and delivered by Celery (or a background thread without Redis); demo seed data never sends mail.
- `run.cmd` and its process handling were developed on Linux; Windows behaviour is what you see when you run it.
- The rate limiter is per process (use Redis for multiple backend workers). "Run billing now" runs synchronously.
- Tax model is configurable percentage taxes assigned per product (no category rules, no tax-inclusive pricing). Business details printed on invoice PDFs come from `BUSINESS_*` environment settings (no admin screen). Historical MRR uses current line prices.
- The repository has no automated tests and no CI pipeline.

## Documentation

[Architecture & decisions](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [API](docs/API.md) · [Financial metric definitions](docs/FINANCIAL_METRICS.md) · [Razorpay](docs/RAZORPAY.md) · [Contributing](docs/CONTRIBUTING.md)
