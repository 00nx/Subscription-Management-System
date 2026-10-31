# Database

**Default: SQLite** (one file, zero install; demo/dev). **PostgreSQL 16 is supported and recommended for real billing.** SQLAlchemy 2.0 (sync, psycopg 3 for PostgreSQL), Alembic migrations (PostgreSQL) (`backend/alembic/versions`: `0001` users/tokens, `0002` customers/notifications/audit/reset + number sequences, `0003` catalogue, subscriptions, quotations, billing, invoices, payments).
`DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db`. `alembic upgrade head` applies the migrations on PostgreSQL (SQLite creates its schema from the models).

```bash
alembic revision --autogenerate -m "message"   # then READ the file
alembic upgrade head   |   alembic downgrade -1
```

## Conventions

- UUID primary keys; `created_at`/`updated_at` timestamptz (server default `now()`).
- **Money: `NUMERIC(12,2)`/`Decimal`, never float.** Tax rates `NUMERIC(5,2)`. Currency INR (3-letter code stored on invoices).
- Dates are `DATE` in UTC; timestamps are timestamptz.
- Enums are stored as strings (`native_enum=False`), shared definitions in `app/core/enums.py`.
- Human numbers from Postgres sequences: `CUS-`, `QUO-`, `SUB-`, `INV-` + 6 digits.
- Foreign keys everywhere; historical financial rows use `RESTRICT` (nothing referenced by invoices/payments can be deleted); products/plans/taxes are archived, not deleted.
- Check constraints guard money and counts (non-negative amounts, percentage ≤ 100, `usage_count ≤ max_usage`, payment amount > 0).

## Tables

| Table | Purpose / key points |
|---|---|
| `users` | email (unique, lowercase), argon2 hash, role `ADMIN/STAFF/CUSTOMER`, is_active |
| `refresh_tokens` | SHA-256 of the token, `family_id` (rotation chain), expires/revoked |
| `password_reset_tokens` | SHA-256 of token, 1 h expiry, single use |
| `customer_profiles` | 1:1 with a CUSTOMER user; `customer_number`, phone, company, billing address, tax id |
| `notifications` | per user, type, read_at, optional entity link |
| `audit_logs` | append-only: user, action, entity, summary, JSON changes (never secrets) |
| `taxes` | name (unique), rate %, status |
| `products`, `product_variants` | sales/cost price, type, status, `tax_id`; variant `additional_price`, unique (product, attribute, value) |
| `subscription_plans`, `plan_products` | price, frequency, min quantity, availability window, auto-close/early-closure/pause/renewal flags |
| `quotation_templates`, `quotation_template_lines` | reusable defaults |
| `quotations`, `quotation_lines` | status DRAFT→QUOTATION→CONFIRMED, expiry, totals, tax-rate snapshots |
| `subscriptions`, `subscription_lines` | lifecycle status, dates, billing schedule (`next_billing_date`, `periods_billed`), per-period totals; **unique `quotation_id`** (one conversion) ; index `(status, next_billing_date)` |
| `subscription_events` | history + billing events (`INVOICE_GENERATED`, `BILLING_FAILED`, …) |
| `subscription_requests` | customer cancel/pause/resume requests |
| `discounts`, `discount_products`, `discount_subscriptions`, `discount_usages` | rules, targets, and an audit row per application (**unique (discount, invoice)**) |
| `invoices`, `invoice_lines` | snapshot of customer, prices, tax, discount; **unique (subscription_id, period_start)**; `amount_paid` updated under a row lock |
| `payments`, `payment_transactions` | status, method, unique `transaction_reference` and `idempotency_key`; provider interaction log |

## Relationships (short)

```
User 1─1 CustomerProfile 1─* Quotation 1─* QuotationLine        Product 1─* ProductVariant
CustomerProfile 1─* Subscription 1─* SubscriptionLine ─▶ Product/Variant/Tax
SubscriptionPlan 1─* Subscription ;  Quotation 0..1─1 Subscription
Subscription 1─* Invoice 1─* InvoiceLine ;  Invoice 1─* Payment 1─* PaymentTransaction
Discount ─* DiscountUsage ─▶ Invoice ;  Tax ─* Product / lines
```

## Demo data

`python -m app.seed [--reset] [--bulk N]` (refuses to run when `ENVIRONMENT=production`).
Development-only accounts: `admin@brightloop.dev / Admin@12345`, `staff1@brightloop.dev` and `staff2@brightloop.dev / Staff@12345`, `alice@example.com` (and Bob, Chitra, Dev, Elena, Farid) `/ Customer@12345`.
`--reset` wipes every table and restarts the number sequences, so the demo is resettable at any time.

## SQLite (the default) vs PostgreSQL

With no `DATABASE_URL` (or `python dev.py`, `run.cmd`) the same code runs on SQLite. It is meant for demos and development and is **not** recommended for real billing.

How the code stays portable (all behaviour on PostgreSQL is unchanged; the full suite passes on both):
- `UTCDateTime`, `GUID`, `JSONType` (`app/models/base.py`): timestamptz/uuid/JSONB on PostgreSQL; naive-UTC text, CHAR(32) and JSON on SQLite.
- `next_number()` (`app/core/database.py`): sequence on PostgreSQL, atomic counter row on SQLite.
- Date bucketing and "latest event per subscription" use portable SQL (`date_bucket`, `row_number()`), not `date_trunc` / `DISTINCT ON`.
- SQLite connections use WAL, `busy_timeout`, `foreign_keys=ON` and `BEGIN IMMEDIATE` so concurrent writers (API, worker, scheduler) queue rather than fail.
- Schema comes from `Base.metadata.create_all` (`python -m app.sqlite_init`); Alembic migrations are PostgreSQL-only.

Known differences: money is REAL rounded to 2 places on read (no exact decimal storage), no row-level locking (a database-wide write lock instead), `--bulk` seeding unavailable.
