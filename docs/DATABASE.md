# Database

## Configuration

PostgreSQL 16 via SQLAlchemy 2.0 (sync, `psycopg` 3 driver). `DATABASE_URL` format: `postgresql+psycopg://user:pass@host:5432/db`.
Sessions: one per request through the `get_db` dependency; services commit explicitly.
Migrations: Alembic (`backend/alembic`). `env.py` reads the URL from settings and imports `app/models/registry.py`.

```bash
alembic revision --autogenerate -m "message"   # then READ the generated file
alembic upgrade head
alembic downgrade -1
```

Run `alembic upgrade head` after pulling new migrations and before starting the backend.

## Conventions

- UUID primary keys (`uuid.uuid4`) for business entities.
- `created_at` / `updated_at` (timestamptz, server default `now()`) via the `Timestamps` mixin.
- Emails are stored lowercase with a unique index.
- **Money is `NUMERIC(12,2)` / `Decimal`, never float.** Rates (tax %) are `NUMERIC(5,2)`. Currency is a 3-letter ISO code column where relevant.
- Foreign keys are always declared; index every FK and every column used for filtering.
- Enums are stored as strings with a length (`native_enum=False`) so adding a value doesn't need `ALTER TYPE`.
- Table names are plural snake_case.

## Implemented (Phase 1)

| Table | Purpose |
|---|---|
| `users` | id, email (unique), hashed_password (argon2id), full_name, role (`ADMIN`/`STAFF`/`CUSTOMER`), is_active, timestamps |
| `refresh_tokens` | id, user_id → users (cascade), family_id, token_hash (SHA-256, unique), expires_at, revoked_at, created_at |

## Planned entities (Phase 2, not yet created)

| Entity | Owner | Key fields / relations |
|---|---|---|
| CustomerProfile | M1 | user_id (1:1 → User), company, phone, billing address, tax id |
| Product | M2 | name, description, is_active |
| ProductVariant | M2 | product_id → Product, sku (unique), name, unit_price `NUMERIC(12,2)` |
| SubscriptionPlan | M2 | name, billing_period (monthly/yearly…), price, min_commitment, is_active |
| Quotation | M2 | customer_id → CustomerProfile, plan_id → SubscriptionPlan, status, valid_until, total |
| QuotationLine | M2 | quotation_id, variant_id → ProductVariant, quantity, unit_price, tax_id, discount_id |
| Subscription | M2 | customer_id, plan_id, quotation_id (nullable), status, start/next_billing/end dates |
| SubscriptionLine | M2 | subscription_id, variant_id, quantity, unit_price |
| Invoice | M3 | subscription_id, customer_id, number (unique), status, issue/due dates, subtotal, tax_total, discount_total, total |
| InvoiceLine | M3 | invoice_id, description, quantity, unit_price, tax_id, discount_id, line_total |
| Tax | M3 | name, rate `NUMERIC(5,2)`, is_active |
| Discount | M3 | code (unique), type (percent/fixed), value, valid_from/until, usage limit |
| Payment | M3 | invoice_id, amount `NUMERIC(12,2)`, method, paid_at, reference |

```
User 1─1 CustomerProfile 1─* Quotation 1─* QuotationLine
CustomerProfile 1─* Subscription 1─* SubscriptionLine ─* ProductVariant *─1 Product
SubscriptionPlan 1─* Subscription ;  Quotation 0..1─1 Subscription
Subscription 1─* Invoice 1─* InvoiceLine ;  Invoice 1─* Payment
Tax / Discount referenced by QuotationLine and InvoiceLine
```
