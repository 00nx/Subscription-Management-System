# Set C - Rate Limiting, Input Validation and Infrastructure

> Private organiser notes. `/bugs/` is in `.gitignore` and must not be committed or shared with participants.

**3 bugs.** These defects affect server-side request throttling, input data integrity, and asynchronous worker health reporting.

## Summary

| ID | Area | Severity | Location | Function | Symptom |
| --- | --- | --- | --- | --- | --- |
| C1 | Rate Limiting | High | `backend/app/core/ratelimit.py:19` | `rate_limit` | All users share a single rate limit bucket per endpoint, allowing one client to cause a global denial of service. |
| C2 | Validation | Medium | `backend/app/modules/accounts/schemas.py:19` | `RegisterIn` | Whitespace-only full names (e.g., `"   "`) bypass the `min_length=1` check. |
| C3 | Infrastructure | Medium | `backend/app/api/v1/endpoints/health.py:40` | `celery_check` | Worker timeouts swallow exceptions and fail to distinguish gateway timeouts (504) from service outages (503). |

---

## C1 - Global rate limiting locks out all users

- **Where:** `backend/app/core/ratelimit.py:19`, `rate_limit`
- **What:** The sliding window tracks hits solely by `request.url.path` rather than composite `(client_ip, path)`.
- **Why it matters:** The docstring states "Sliding window per client IP + path". Because `request.client.host` is omitted, the dictionary key is identical for every visitor. When one user exhausts the limit (e.g. failing 5 logins), all legitimate users worldwide receive HTTP 429 on that route.
- **Fix:** Prefix the bucket key with the client IP address:

```python
client_ip = request.client.host if request.client else "unknown"
hits = _hits[f"{client_ip}:{request.url.path}"]
```

## C2 - Whitespace-only full name validation bypass

- **Where:** `backend/app/modules/accounts/schemas.py:19`, `RegisterIn`
- **What:** `full_name: str = Field(min_length=1, max_length=255)` accepts strings consisting entirely of spaces (e.g. `"   "`).
- **Why it matters:** Users can create anonymous accounts with blank display names, corrupting audit trails, greetings, invoices, and table listings.
- **Fix:** Add a field validator to strip leading/trailing whitespace before validation:

```python
full_name: str = Field(min_length=1, max_length=255)

@field_validator("full_name")
@classmethod
def _validate_full_name(cls, v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Full name cannot be blank")
    return cleaned
```

## C3 - Celery health check swallows timeout exceptions

- **Where:** `backend/app/api/v1/endpoints/health.py:40`, `celery_check`
- **What:** The endpoint catches all exceptions with a broad `except Exception:` and always raises a generic 503 error without distinguishing timeouts or logging root causes.
- **Why it matters:** Operations and automated probes cannot tell whether the Redis message broker is down or if the Celery worker simply timed out handling the queue.
- **Fix:** Catch `celery.exceptions.TimeoutError` separately and return an appropriate 504 Gateway Timeout:

```python
from celery.exceptions import TimeoutError as CeleryTimeoutError

try:
    result = ping.delay().get(timeout=10)
except CeleryTimeoutError:
    raise AppError("Celery worker timed out", 504)
except Exception:
    raise AppError("Celery worker did not respond", 503)
```

---

## Set C fix checklist

- [x] C1 - Include client IP in rate limit bucket key.
- [x] C2 - Strip and validate `full_name` against whitespace-only strings.
- [x] C3 - Differentiate Celery timeout errors with HTTP 504.
