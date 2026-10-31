# API

Base path `/api/v1/`. Interactive docs: `/docs` (Swagger), `/redoc`; schema `/openapi.json`. Paths end with `/`. **98 operations.**
Request/response schemas, filters and status codes are in the OpenAPI document (the source of truth); this page explains the conventions.

## Response envelope and errors

```json
{ "success": true,  "message": "Request successful", "data": {} }
{ "success": false, "message": "Validation failed", "errors": { "password": ["Password must contain an uppercase letter"] } }
```

401 not authenticated · 403 forbidden (role, CSRF) · 404 not found (also used for other people's records) · 409 conflict (duplicate, invalid state transition) · 422 validation (or a business rule such as overpayment) · 429 rate limited · 500 generic message (details only in logs).
Money is a **decimal string** (`"999.00"`); never a float.

**Pagination:** `?page=1&page_size=20` (page ≥ 1, page_size 1-100) → `data = {items, total, page, page_size}`. **Sorting:** `?sort=field` / `?sort=-field` (whitelisted per endpoint). **Search/filter:** `q`, `status`, date ranges, etc. per endpoint.

## Authentication

1. `POST /auth/login/` returns a 15-minute JWT access token (body) and sets two cookies: `refresh_token` (opaque, **HttpOnly**, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`, path `/api/v1/auth`, 7 days) and `csrf_token` (readable by JS).
2. The SPA keeps the access token in memory and sends `Authorization: Bearer`.
3. On 401, or on page load, `POST /auth/refresh/` with `X-CSRF-Token` equal to the cookie (double-submit; mismatch → 403). The refresh token **rotates**; reusing a rotated token revokes the whole family. Only SHA-256 hashes are stored.
4. `POST /auth/logout/` (CSRF-checked) revokes the family. Changing or resetting a password revokes all sessions.
5. **Password reset:** `POST /auth/password-reset/` always answers identically, emails a 1-hour single-use link to `{FRONTEND_URL}/reset-password?token=…` (SMTP via env; **without `SMTP_HOST` the email is written to the backend log** for development). `POST /auth/password-reset/confirm/` sets the new password.
6. Roles are read from the database on every request (demotion is immediate). Register always creates a CUSTOMER; only an ADMIN can create STAFF/ADMIN (`POST /users/`).
7. Rate limits (per IP, per path): login/register/reset 10/min, refresh 60/min (`RATE_LIMIT_*` env).

Password rules (backend authoritative, mirrored in the form): more than 8 characters, an uppercase, a lowercase, a special character.

## Permissions

| Area | ADMIN | STAFF | CUSTOMER |
|---|---|---|---|
| Users (list/create/update roles) | yes | no | no |
| Customers | all | all (read/update) | own profile (`/customers/me/`) |
| Products, variants, plans, taxes | write | read | plans: only those open for subscription |
| Discounts | write | read | no |
| Quotations / templates | all | all | view own (non-draft) |
| Subscriptions | all | all | view own (non-draft); **requests** for cancel/pause/resume |
| Invoices | all | all | own, non-draft; PDF; pay |
| Payments | record + view | record + view | own; initiate/complete via gateway |
| Billing run / failures | run + view | view due/failures | no |
| Dashboard / reports | all | operational only (no MRR/ARR/revenue, no revenue report) | no |
| Audit log | read | no | no |
| Notifications | own | own | own |

Customer ownership is enforced server-side (`scope_customer_id`): a client-supplied `customer_id` is ignored for customers, and other people's records return 404.

## Endpoints

### analytics

| Method | Path |
|---|---|
| `GET` | `/api/v1/analytics/dashboard/` |
| `GET` | `/api/v1/analytics/payments/` |
| `GET` | `/api/v1/analytics/revenue/` |
| `GET` | `/api/v1/analytics/subscriptions/` |

### audit-logs

| Method | Path |
|---|---|
| `GET` | `/api/v1/audit-logs/` |

### auth

| Method | Path |
|---|---|
| `POST` | `/api/v1/auth/change-password/` |
| `POST` | `/api/v1/auth/login/` |
| `POST` | `/api/v1/auth/logout/` |
| `GET` | `/api/v1/auth/me/` |
| `POST` | `/api/v1/auth/password-reset/` |
| `POST` | `/api/v1/auth/password-reset/confirm/` |
| `POST` | `/api/v1/auth/refresh/` |
| `POST` | `/api/v1/auth/register/` |

### billing

| Method | Path |
|---|---|
| `GET` | `/api/v1/billing/due/` |
| `GET` | `/api/v1/billing/failures/` |
| `POST` | `/api/v1/billing/run/` |

### customers

| Method | Path |
|---|---|
| `GET` | `/api/v1/customers/` |
| `GET` | `/api/v1/customers/me/` |
| `PATCH` | `/api/v1/customers/me/` |
| `GET` | `/api/v1/customers/me/summary/` |
| `GET` | `/api/v1/customers/{customer_id}/` |
| `PATCH` | `/api/v1/customers/{customer_id}/` |

### discounts

| Method | Path |
|---|---|
| `GET` | `/api/v1/discounts/` |
| `POST` | `/api/v1/discounts/` |
| `GET` | `/api/v1/discounts/{discount_id}/` |
| `PATCH` | `/api/v1/discounts/{discount_id}/` |
| `GET` | `/api/v1/discounts/{discount_id}/usages/` |

### health

| Method | Path |
|---|---|
| `GET` | `/api/v1/health/` |
| `POST` | `/api/v1/health/celery/` |

### invoices

| Method | Path |
|---|---|
| `GET` | `/api/v1/invoices/` |
| `POST` | `/api/v1/invoices/` |
| `GET` | `/api/v1/invoices/{invoice_id}/` |
| `POST` | `/api/v1/invoices/{invoice_id}/cancel/` |
| `POST` | `/api/v1/invoices/{invoice_id}/confirm/` |
| `GET` | `/api/v1/invoices/{invoice_id}/pdf/` |
| `POST` | `/api/v1/invoices/{invoice_id}/send/` |

### notifications

| Method | Path |
|---|---|
| `GET` | `/api/v1/notifications/` |
| `POST` | `/api/v1/notifications/read-all/` |
| `GET` | `/api/v1/notifications/unread-count/` |
| `POST` | `/api/v1/notifications/{notification_id}/read/` |

### payments

| Method | Path |
|---|---|
| `GET` | `/api/v1/payments/` |
| `POST` | `/api/v1/payments/` |
| `POST` | `/api/v1/payments/initiate/` |
| `GET` | `/api/v1/payments/{payment_id}/` |
| `POST` | `/api/v1/payments/{payment_id}/simulate/` |
| `GET` | `/api/v1/payments/{payment_id}/status/` |

### plans

| Method | Path |
|---|---|
| `GET` | `/api/v1/plans/` |
| `POST` | `/api/v1/plans/` |
| `GET` | `/api/v1/plans/{plan_id}/` |
| `PATCH` | `/api/v1/plans/{plan_id}/` |

### products

| Method | Path |
|---|---|
| `GET` | `/api/v1/products/` |
| `POST` | `/api/v1/products/` |
| `GET` | `/api/v1/products/{product_id}/` |
| `PATCH` | `/api/v1/products/{product_id}/` |
| `DELETE` | `/api/v1/products/{product_id}/` |
| `POST` | `/api/v1/products/{product_id}/archive/` |
| `GET` | `/api/v1/products/{product_id}/variants/` |
| `POST` | `/api/v1/products/{product_id}/variants/` |
| `PATCH` | `/api/v1/products/{product_id}/variants/{variant_id}/` |
| `DELETE` | `/api/v1/products/{product_id}/variants/{variant_id}/` |

### quotation-templates

| Method | Path |
|---|---|
| `GET` | `/api/v1/quotation-templates/` |
| `POST` | `/api/v1/quotation-templates/` |
| `GET` | `/api/v1/quotation-templates/{template_id}/` |
| `PATCH` | `/api/v1/quotation-templates/{template_id}/` |

### quotations

| Method | Path |
|---|---|
| `GET` | `/api/v1/quotations/` |
| `POST` | `/api/v1/quotations/` |
| `GET` | `/api/v1/quotations/{qid}/` |
| `PATCH` | `/api/v1/quotations/{qid}/` |
| `POST` | `/api/v1/quotations/{qid}/confirm/` |
| `POST` | `/api/v1/quotations/{qid}/convert/` |
| `POST` | `/api/v1/quotations/{qid}/send/` |

### reports

| Method | Path |
|---|---|
| `GET` | `/api/v1/reports/invoices/` |
| `GET` | `/api/v1/reports/payments/` |
| `GET` | `/api/v1/reports/revenue/` |
| `GET` | `/api/v1/reports/subscriptions/` |

### subscription-requests

| Method | Path |
|---|---|
| `GET` | `/api/v1/subscription-requests/` |
| `POST` | `/api/v1/subscription-requests/{req_id}/approve/` |
| `POST` | `/api/v1/subscription-requests/{req_id}/reject/` |

### subscriptions

| Method | Path |
|---|---|
| `GET` | `/api/v1/subscriptions/` |
| `POST` | `/api/v1/subscriptions/` |
| `GET` | `/api/v1/subscriptions/{sub_id}/` |
| `PATCH` | `/api/v1/subscriptions/{sub_id}/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/activate/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/cancel/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/confirm/` |
| `GET` | `/api/v1/subscriptions/{sub_id}/events/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/pause/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/renew/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/requests/` |
| `POST` | `/api/v1/subscriptions/{sub_id}/resume/` |

### taxes

| Method | Path |
|---|---|
| `GET` | `/api/v1/taxes/` |
| `POST` | `/api/v1/taxes/` |
| `GET` | `/api/v1/taxes/{tax_id}/` |
| `PATCH` | `/api/v1/taxes/{tax_id}/` |

### users

| Method | Path |
|---|---|
| `GET` | `/api/v1/users/` |
| `POST` | `/api/v1/users/` |
| `GET` | `/api/v1/users/{user_id}/` |
| `PATCH` | `/api/v1/users/{user_id}/` |
