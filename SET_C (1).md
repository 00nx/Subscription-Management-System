# Set C - Backend Data and Session Behaviour

> Private organiser notes. `/bugs/` is in `.gitignore` and must not be committed or shared with participants.

**3 bugs.** The app still starts and the existing test suite is intentionally left green: these defects live in edge paths that the current tests do not exercise. Line numbers are from the current working tree and may move after future edits.

## Summary

| ID | Area | Severity | Location | Function | Symptom |
| --- | --- | --- | --- | --- | --- |
| C1 | Backend | High | `backend/app/schemas/common.py:34` | `PageParams.offset` | Page 1 starts at the second page of results; the first page of rows is never shown. |
| C2 | Backend | Medium | `backend/app/core/ratelimit.py:15` | `rate_limit` | Rate-limit buckets are shared by endpoint instead of per client IP. |
| C3 | Backend | Medium | `backend/app/modules/accounts/service.py:77` | `revoke_refresh_token` | Logging out on one device revokes every session for that user. |

---

## C1 - Pagination offset skips page 1

- **Where:** `backend/app/schemas/common.py:34`, `PageParams.offset`
- **What:** The offset is `page * page_size` instead of `(page - 1) * page_size`.
- **Why it matters:** The first request with `page=1` starts at row `page_size`, so the first page of rows is never returned. The existing pagination test only asserts that one row comes back on page 1, which still passes with two users in the database.
- **Fix:**

```python
@property
def offset(self) -> int:
    return (self.page - 1) * self.page_size
```

## C2 - Rate limiting is global per endpoint

- **Where:** `backend/app/core/ratelimit.py:15`, `rate_limit`
- **What:** The bucket key is only `request.url.path`; the client IP was removed.
- **Why it matters:** One client (or one attacker) hitting `/auth/login/` can exhaust the shared bucket and rate-limit every other user of that endpoint.
- **Fix:** Key by client IP and path:

```python
hits = _hits[f"{request.client.host if request.client else '?'}:{request.url.path}"]
```

## C3 - Logout revokes every session for the user

- **Where:** `backend/app/modules/accounts/service.py:77`, `revoke_refresh_token`
- **What:** The query updates every unrevoked refresh token for `row.user_id` instead of revoking only the token's rotation family.
- **Why it matters:** Logging out on one device signs the user out of every device/session. The current logout test only has one session, so it still passes.
- **Fix:** Revoke only the family that owns the presented token:

```python
def revoke_refresh_token(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if row:
        _revoke_family(db, row.family_id)
```

---

## Set C fix checklist

- [x] C1 - Use `(page - 1) * page_size` for the offset.
- [x] C2 - Include the client host in the rate-limit key.
- [x] C3 - Revoke only the current refresh-token family on logout.
