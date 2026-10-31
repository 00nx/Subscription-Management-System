# API

Base path `/api/v1/`. Interactive docs: `/docs` (Swagger), `/redoc`; schema: `/openapi.json`. Paths end with `/`.

## Response envelope

```json
{ "success": true,  "message": "Request successful", "data": {} }
{ "success": false, "message": "Validation failed", "errors": { "password": ["Password must contain an uppercase letter"] } }
```

Status codes: 200/201 success · 401 not authenticated · 403 forbidden (role, CSRF) · 409 conflict (duplicate email) · 422 validation · 429 rate limited · 500 unexpected (generic message; details only in server logs).

Pagination: query `?page=1&page_size=20` (page ≥ 1, page_size 1–100). Response `data` is `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`.

## Authentication

1. **Login** returns a short-lived JWT access token (15 min, in the JSON body) and sets two cookies:
   - `refresh_token`: opaque random string, `HttpOnly`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`, path `/api/v1/auth`, 7 days.
   - `csrf_token`: random, readable by JS, path `/`.
2. The SPA keeps the access token **in memory only** and sends `Authorization: Bearer <token>`.
3. On 401, or on page load, the SPA calls **refresh** with `X-CSRF-Token` equal to the `csrf_token` cookie (double-submit CSRF check; mismatched/missing → 403). The refresh token is **rotated**: the old one is revoked, a new one set.
4. Only the SHA-256 of each refresh token is stored. If an already-rotated token is presented again (replay/theft), the entire token family is revoked.
5. **Logout** (also CSRF-checked) revokes the family and clears cookies.
6. Roles are read from the database on every request, not from token claims, so demotion or deactivation takes effect immediately.

Limitations: the CSRF cookie is readable by JS on the API's host, so the SPA and API must share a site (e.g. `localhost` or `app.example.com` + `api.example.com`). The rate limiter is per process (see `core/ratelimit.py`).

Password rules: more than 8 characters, one uppercase, one lowercase, one special character. Enforced by the backend (and mirrored in the frontend form).

## Endpoints

| Method & path | Auth | Description |
|---|---|---|
| `GET /health/` | none | `{database, redis}` status; 503 if either is down |
| `POST /health/celery/` | ADMIN | Enqueues the sample Celery task and waits for `"pong"` |
| `POST /auth/register/` | none, rate limited | Creates a **CUSTOMER** (role in payload ignored). 201 |
| `POST /auth/login/` | none, rate limited | Body `{email, password}` → `{access_token, token_type, expires_in, user}` + cookies |
| `POST /auth/refresh/` | refresh cookie + `X-CSRF-Token` | Rotates refresh token, returns same shape as login |
| `POST /auth/logout/` | refresh cookie + `X-CSRF-Token` | Revokes token family |
| `POST /auth/password-reset/` | none, rate limited | Always returns the same message; **no email is sent yet** (Phase 2) |
| `GET /auth/me/` | any user | Current user |
| `GET /users/` | ADMIN, STAFF | Paginated users |
| `POST /users/` | ADMIN | Create a user with a chosen role (the only way to create STAFF/ADMIN) |

Authorization matrix: customers only ever reach their own data (customer-scoped subscription/invoice endpoints must filter by `current_user.id`; use `Depends(get_current_user)` and `require_roles(...)` from `app/core/dependencies.py`). Staff have limited operational access; admins have everything.

## Adding an endpoint

Put the router in your module, return `ApiResponse[...]`, declare `responses` for 401/403, protect with `require_roles`, include it in `api/v1/router.py`.
