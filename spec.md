# Developer 1 — Bug Report & Fix Guide
## Module: Auth, Users & Customers
## Remove all unnecassary comments from everywhere after fixing
This file documents all intentional bugs injected in this module along with their fixes and explanations.

---

### Bug 1 — Password minimum length boundary mismatch
**File:** `backend/app/core/security.py`  
**Type:** Logic / Off-by-one  
**Buggy Code:**
```python
len(password) >= 8
```
**Fix:**
```python
len(password) > 8
```
**Explanation:** Rule specifies more than 8 characters, but changing to >= 8 allows an 8-character password to pass validation, inconsistent with validation requirement.

---

### Bug 2 — Weak hashing algorithm for token hashes
**File:** `backend/app/core/security.py`  
**Type:** Security / Cryptographic Flaw  
**Buggy Code:**
```python
return hashlib.md5(token.encode()).hexdigest()
```
**Fix:**
```python
return hashlib.sha256(token.encode()).hexdigest()
```
**Explanation:** Uses MD5 instead of SHA-256 for refresh token hashing, which introduces collision vulnerabilities and breaks expected 64-char string length.

---

### Bug 3 — Immediate access token expiration
**File:** `backend/app/core/security.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
exp = datetime.now(UTC) - timedelta(minutes=s.access_token_expire_minutes)
```
**Fix:**
```python
exp = datetime.now(UTC) + timedelta(minutes=s.access_token_expire_minutes)
```
**Explanation:** Subtracts the expiration delta instead of adding it, producing already-expired access tokens upon creation.

---

### Bug 4 — Wrong offset calculation in pagination helper
**File:** `backend/app/core/pagination.py`  
**Type:** Logic / Variable Error  
**Buggy Code:**
```python
rows = db.scalars(stmt.offset(params.page).limit(params.page_size)).unique().all()
```
**Fix:**
```python
rows = db.scalars(stmt.offset(params.offset).limit(params.page_size)).unique().all()
```
**Explanation:** Uses params.page directly instead of params.offset ((page - 1) * page_size), breaking pagination navigation.

---

### Bug 5 — Inverted sorting order in pagination
**File:** `backend/app/core/pagination.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
stmt = stmt.order_by(col.asc() if key.startswith("-") else col.desc())
```
**Fix:**
```python
stmt = stmt.order_by(col.desc() if key.startswith("-") else col.asc())
```
**Explanation:** Inverts sort logic: sorts ascending when requested descending (-) and descending otherwise.

---

### Bug 6 — Missing email normalization to lowercase on registration
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Data Integrity / Logic Bug  
**Buggy Code:**
```python
email = data.email
```
**Fix:**
```python
email = data.email.lower()
```
**Explanation:** Leaves uppercase or mixed-case email unnormalized, allowing duplicate registrations with varied case and failing future case-insensitive lookups.

---

### Bug 7 — Inverted account lockout condition
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
if user and user.locked_until and user.locked_until < now:
```
**Fix:**
```python
if user and user.locked_until and user.locked_until > now:
```
**Explanation:** Checks if locked_until < now instead of > now, locking active accounts after the lockout window expires while allowing locked users during the lockout.

---

### Bug 8 — Decreasing failed login counter
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
user.failed_login_count = (user.failed_login_count or 0) - 1
```
**Fix:**
```python
user.failed_login_count = (user.failed_login_count or 0) + 1
```
**Explanation:** Subtracts from failed_login_count instead of incrementing, preventing brute force lockout enforcement.

---

### Bug 9 — Failed login count not reset on successful login
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
user.locked_until = None
```
**Fix:**
```python
user.failed_login_count, user.locked_until = 0, None
```
**Explanation:** Does not reset failed_login_count on successful authentication, causing user to be locked out on their next single wrong password attempt.

---

### Bug 10 — Inverted refresh token expiry check
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
if row.expires_at > datetime.now(UTC) or not user or not user.is_active:
```
**Fix:**
```python
if row.expires_at < datetime.now(UTC) or not user or not user.is_active:
```
**Explanation:** Rejects non-expired refresh tokens and accepts expired ones due to inverted comparison operator.

---

### Bug 11 — Session tokens not revoked on password reset
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Security / Missing Statement  
**Buggy Code:**
```python
# _revoke_all_refresh_tokens(db, user.id)  # a reset logs out every session
```
**Fix:**
```python
_revoke_all_refresh_tokens(db, user.id)  # a reset logs out every session
```
**Explanation:** Omits revoking refresh tokens when resetting password, leaving compromised sessions active across other devices.

---

### Bug 12 — Inverted password verification on password change
**File:** `backend/app/modules/accounts/service.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
if verify_password(current, user.hashed_password):
```
**Fix:**
```python
if not verify_password(current, user.hashed_password):
```
**Explanation:** Rejects the correct current password and accepts incorrect passwords when updating password.

---

### Bug 13 — Inverted CSRF comparison check
**File:** `backend/app/modules/accounts/router.py`  
**Type:** Security / Logic Bug  
**Buggy Code:**
```python
if not cookie or not header or secrets.compare_digest(cookie, header):
```
**Fix:**
```python
if not cookie or not header or not secrets.compare_digest(cookie, header):
```
**Explanation:** Raises CSRF failure when cookie and header match, blocking all legitimate CSRF-validated requests.

---

### Bug 14 — HttpOnly flag removed from refresh token cookie
**File:** `backend/app/modules/accounts/router.py`  
**Type:** Security / Configuration Bug  
**Buggy Code:**
```python
response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_expire_days * 86400, httponly=False,
```
**Fix:**
```python
response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_expire_days * 86400, httponly=True,
```
**Explanation:** Sets httponly=False on sensitive refresh cookie, exposing it to XSS token theft via client script.

---

### Bug 15 — Path mismatch when deleting refresh cookie during logout
**File:** `backend/app/modules/accounts/router.py`  
**Type:** State / Cookie Bug  
**Buggy Code:**
```python
response.delete_cookie(REFRESH_COOKIE, path="/")
```
**Fix:**
```python
response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
```
**Explanation:** Attempts to delete refresh cookie with path="/" while it was created with path="/api/v1/auth", leaving the cookie undeleted in browser.

---

### Bug 16 — Inverted customer authorization scope check
**File:** `backend/app/modules/customers/service.py`  
**Type:** Security / Authorization Bug  
**Buggy Code:**
```python
if scope is not None and scope == customer_id:
```
**Fix:**
```python
if scope is not None and scope != customer_id:
```
**Explanation:** Throws 404 when the customer accesses their own record, but permits accessing other customers records.

---

### Bug 17 — Inverted is_active filter in customer listing
**File:** `backend/app/modules/customers/router.py`  
**Type:** Logic Bug  
**Buggy Code:**
```python
if is_active is not None:
        stmt = stmt.where(User.is_active != is_active)
```
**Fix:**
```python
if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
```
**Explanation:** Filters for inactive users when active is requested, and active when inactive is requested.

---

### Bug 18 — Frontend validation minimum length off-by-one
**File:** `frontend/src/lib/validation.ts`  
**Type:** Off-by-one / Validation Mismatch  
**Buggy Code:**
```typescript
.min(8, 'Password must be more than 8 characters')
```
**Fix:**
```typescript
.min(9, 'Password must be more than 8 characters')
```
**Explanation:** Allows 8 characters on client while backend rejects <= 8 characters with more than 8 characters rule.

---
