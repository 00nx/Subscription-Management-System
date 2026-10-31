# Architecture

Modular monolith: one FastAPI app, one PostgreSQL database, one Celery worker image (+ one beat scheduler), one React SPA. No microservices.

```
Browser (React + TS) ──HTTP/JSON──▶ FastAPI ──SQLAlchemy──▶ PostgreSQL
                                       │
                                       └─enqueue─▶ Redis ◀── Celery worker  (billing, reminders, expiry)
                                                      ▲
                                              Celery beat (schedule)
```

## Frontend ↔ backend

- One Axios instance (`frontend/src/services/api.ts`): base URL from `VITE_API_URL`, 10 s timeout, bearer + CSRF headers, single-flight refresh on 401, every failure normalised to `ApiError`. Services in `services/*.service.ts` wrap endpoints and return typed, unwrapped data; components never call Axios.
- Server state is TanStack Query; keys come from `lib/queryKeys.ts`. Mutations go through `useApiMutation` (toast + invalidation), lists through `useListQuery` + `QueryTable` (loading / error / empty / pagination for free). List filters live in the URL (`useUrlState`).
- The user and role come from the backend (`/auth/me` via the refresh flow). Route guards only shape navigation; **FastAPI authorises every request independently** and reads the role from the database, never from the token.

## Backend layout

```
app/main.py              app factory (CORS, handlers, router, bootstrap admin)
app/core/                config, DB session, security, dependencies, exceptions, rate limit, logging, enums, money, pagination, email
app/api/v1/router.py     mounts each module's router under /api/v1
app/modules/<name>/      models.py, schemas.py, service.py, router.py
app/models/registry.py   imports every module's models (Alembic, Celery workers)
app/tasks/               celery_app.py (+ beat schedule), billing_tasks.py, sample_tasks.py
app/seed.py              demo + bulk data
```

Layering: router (HTTP, auth, validation) → service (rules, transactions) → models. Services never import routers.

## Modules

| Module | Owns | Notes |
|---|---|---|
| `accounts` | User, RefreshToken, PasswordResetToken, Notification | auth, users, notifications |
| `customers` | CustomerProfile | profiles, `scope_customer_id()` ownership helper |
| `products` | Product, ProductVariant | variant price = base + configurable amount |
| `billing` | Tax, billing engine (`service.py`) | taxes CRUD; engine functions used by Celery |
| `discounts` | Discount, DiscountProduct, DiscountSubscription, DiscountUsage | pure eligibility/amount functions |
| `subscriptions` | SubscriptionPlan, PlanProduct, Subscription(+Line, Event, Request) | lifecycle state machine, period calendar |
| `quotations` | QuotationTemplate(+Line), Quotation(+Line) | workflow, conversion |
| `invoices` | Invoice, InvoiceLine | snapshots, status, PDF |
| `payments` | Payment, PaymentTransaction, providers | simulated gateway behind a provider interface |
| `analytics` | AuditLog | dashboard/report aggregation, audit |

Rules: a module owns its tables and service; others call its **service functions**, not its tables. Shared contracts (`core/`, `schemas/common.py`) change by PR reviewed by everyone.

## Billing engine (the core)

`billing/service.py`, run by Celery beat hourly (`billing.generate_due_invoices`) or by an admin ("Run billing now", same code).

1. Find ACTIVE subscriptions with `next_billing_date <= today` (and not past expiry).
2. For each subscription, **in its own transaction**: lock the row (`FOR UPDATE SKIP LOCKED`), build the invoice from the subscription's price/tax **snapshot**, apply eligible discounts (discount rows locked and refreshed, usage incremented, `DiscountUsage` written), insert the invoice, advance `next_billing_date`, write events/notification/audit. Up to 12 overdue periods are caught up per run.
3. On error: roll back, record a `BILLING_FAILED` event, continue with the other subscriptions. The failed one is still due, so the next run (and the task's own backoff retry) tries again. The task fails loudly if anything failed.
4. Then `run_expiry`: auto-renew or expire subscriptions past their term (after billing, so in-term periods are never lost).

**Duplicate prevention (defence in depth):** unique constraint `uq_invoice_subscription_period (subscription_id, period_start)`; per-subscription row lock; the date advances in the same transaction as the invoice; an already-invoiced period is skipped; the whole job is idempotent (re-running is a no-op). Tested with concurrent runs, retries and a rolled-back schedule.

**Calculation** (per line, `Decimal`, half-up to 2 places): `subtotal = qty × unit price`; `taxable = subtotal − discount`; `tax = taxable × rate`; `total = taxable + tax`. Discounts are allocated to lines proportionally and capped at what is left, so totals never go negative. Rate, price, description and customer details are copied onto the invoice; later edits never change issued invoices.

## Payments

`payments/providers.py` defines the provider interface (`initiate`, `complete`); `SimulatedProvider` is registered. Add a Razorpay/Stripe class there to go live. The frontend only picks a *test outcome*; the backend validates it, locks the payment and invoice rows, re-checks the balance and records the result. A frontend "success" is never evidence of payment. Only `SUCCESS` payments count as money received.

## Background processing

Celery + Redis (`task_acks_late`, idempotent tasks). Schedule: billing hourly (:05), payment reminders daily 08:00 UTC, overdue detection 00:30, discount expiry 01:00. Reminders/overdue are guarded by per-invoice flags so they fire once. Workers register every model via `app.models.registry` (a worker never imports `app.main`).

## Design decisions (simplest option consistent with the PRD)

- **Plan price:** a plan has one primary product and a price. A new subscription line for that product defaults to `plan.price + variant additional price`; other allowed products default to their sales price. Lines store the agreed price, so plan/product/tax edits never alter existing subscriptions.
- **Discount targeting:** a discount applies if it is attached to the subscription, or targets products the subscription contains (and is not restricted to other subscriptions). A discount with no targets never auto-applies (a quotation can attach it explicitly).
- **Month-end/leap rules:** periods are anchored to the start date (31 Jan → 28/29 Feb → 31 Mar; 29 Feb yearly → 28 Feb in non-leap years). See `subscriptions/periods.py`.
- **Pause:** billing doesn't run while paused; periods that elapse are skipped on resume (not back-billed), with an event recording it.
- **Expiry policy:** `auto_close` plans set EXPIRED at term end (auto-renew if enabled); otherwise the subscription stays ACTIVE but no period beyond the term is invoiced.
- **Invoices:** recurring invoices are created `CONFIRMED` (issued). Manual ones start `DRAFT`. `PARTIALLY_PAID` is a stored status; **overdue is derived**. A cancelled invoice keeps its period (not re-billed); issue a manual invoice instead.
- **Customer requests:** customers cannot change lifecycle state; they submit cancel/pause/resume requests that staff approve (which runs the same checks as a direct action).
- **Quotation conversion:** requires CONFIRMED and not expired; one subscription per quotation (unique FK + row lock).
- **Overpayment:** rejected unless `ALLOW_OVERPAYMENT=true`.
- **Reports:** CSV export only; no PDF reports (invoices have PDFs).
