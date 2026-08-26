# Session Management — Cookies, JWT vs Sessions, Security

## Quick Concepts

**WHAT:**
- **Session** = Server-side state for authenticated user
- **Cookie** = Client-side storage (name/value, sent to server)
- **Session ID** = Reference to server-side session
- **JWT** = Self-contained token (no server lookup needed)
- **Session fixation** = Attacker sets known session ID
- **Session hijacking** = Stolen session ID used
- **HttpOnly cookie** = Not accessible via JavaScript (XSS protection)
- **SameSite cookie** = Cross-site request behavior

---

## Andar kya hota hai — Session Revoke Instant Kyun Hai, JWT Ka Kyun Nahi

### Cookie sirf ek LOOKUP KEY carry karta hai, actual data nahi

```
Session-based:
  Cookie = ek RANDOM opaque session_id string (jaise "sess_a8f3...")
  Actual session data (user_id, roles, etc.) SERVER-SIDE store hota hai
  (Redis/DB), keyed by session_id

Server logout/revoke: bas Redis/DB se us session_id ka record DELETE
  kar do — cookie ab kisi kaam ka nahi (server ke paas uska koi data
  hi nahi bacha), INSTANT revoke.

JWT-based: token khud mein SAARA data carry karta hai (self-contained) —
  server ke paas "yeh token abhi valid hai ya revoke ho chuka" check
  karne ke liye KOI centralized record nahi (yehi to JWT ka "stateless"
  fayda hai). Revoke karne ke liye ek ALAG blocklist/deny-list maintain
  karni padti hai (jo waapas stateful lookup ban jaata hai — JWT ka
  stateless fayda partially khatam ho jaata hai agar genuinely revoke
  karna hai).
```

### Session fixation — attacker session_id "fix" karta hai LOGIN se PEHLE

```
1. Attacker khud ek session_id generate karke, victim ko us session_id
   wale link pe bhejta hai (ya cookie inject karta hai)
2. Victim us session_id se login karta hai
3. Agar server login ke BAAD bhi WAHI session_id reuse karta hai (naya
   generate nahi karta), attacker ke paas ab EXACT wahi session_id hai
   jo ab AUTHENTICATED ban chuka — attacker use kar sakta hai
```

**Fix:** login/privilege-change ke turant BAAD server hamesha ek NAYA
session_id GENERATE kare (purana invalidate karke) — chahe request wahi
cookie use kar rahi thi. Yeh single-line fix isi poore attack class ko
rok deta hai.

**WHY session management matters:**
- ❌ Bad cookies = XSS steals all credentials
- ❌ No CSRF = attacker forges actions
- ❌ Session fixation = account takeover
- ❌ No logout = stolen tokens valid forever

**HOW Session vs JWT comparison:**

```
┌────────────────────┬─────────────┬──────────────┐
│                    │   Session   │     JWT      │
├────────────────────┼─────────────┼──────────────┤
│ State              │ Server      │ Stateless    │
│ Storage            │ Server-side │ Client-side  │
│ Revocation         │ Easy        │ Hard         │
│ Performance        │ DB lookup   │ Local verify │
│ Scaling            │ Sticky/Redis│ Easy         │
│ Size               │ Small ID    │ Larger token │
│ Best for           │ Web apps    │ APIs, SPA    │
└────────────────────┴─────────────┴──────────────┘
```

---

## Interview Questions & Answers

### Q1: Cookie security attributes — production setup?

**Answer:**

**WHAT:** Cookie flags that browser enforces.

**HOW — All security attributes:**

```python
from fastapi import Response

def set_session_cookie(response: Response, session_id: str):
    """
    INTERVIEW: Production-secure session cookie.
    """
    response.set_cookie(
        key="session_id",
        value=session_id,

        # ⭐ HttpOnly: JavaScript CANNOT read (XSS protection)
        httponly=True,

        # ⭐ Secure: Only sent over HTTPS
        secure=True,

        # ⭐ SameSite: Cross-site request behavior
        # - "strict": Never sent cross-site (best security)
        # - "lax": Sent on top-level navigation (default modern)
        # - "none": Always sent (requires Secure)
        samesite="lax",

        # ⭐ Domain: Which domain receives cookie
        # ".example.com" = available to all subdomains
        # Omit = only the exact domain
        domain=".example.com",

        # ⭐ Path: URL path restriction
        path="/",

        # ⭐ Max-Age: Cookie lifetime in seconds
        max_age=86400,  # 24 hours

        # OR ⭐ Expires (absolute time)
        # expires=datetime.now() + timedelta(days=1),
    )
```

**HOW — Cookie attribute decision matrix:**

| Use Case | HttpOnly | Secure | SameSite | Lifetime |
|---|---|---|---|---|
| Session ID | ✅ True | ✅ True | Strict | 24h-7d |
| Auth refresh token | ✅ True | ✅ True | Strict | 7-30d |
| CSRF token | ❌ False (JS reads) | ✅ True | Strict | Session |
| User preference | ❌ False | ✅ True | Lax | 1 year |
| OAuth state | ✅ True | ✅ True | Lax | 10 min |

**HOW — `__Host-` and `__Secure-` prefixes (extra security):**

```python
# __Host- prefix: STRICTEST
# - Must have Secure
# - Must have Path=/
# - Must NOT have Domain
# - Origin-bound

response.set_cookie(
    key="__Host-session",
    value=session_id,
    secure=True,
    httponly=True,
    samesite="strict",
    path="/",
    # NO domain attribute!
)


# __Secure- prefix
# - Must have Secure
# - Less strict than __Host-

response.set_cookie(
    key="__Secure-pref",
    value="dark-mode",
    secure=True,
    samesite="lax",
    domain=".example.com",
)
```

---

### Q2: Session storage — Redis vs DB vs in-memory?

**Answer:**

**WHY shared session storage:**
- Multi-instance deployment (load balanced)
- User can hit any instance
- All instances need access to same session data

**HOW — Redis-based sessions:**

```python
import json
import secrets
import time
from typing import Optional
import redis.asyncio as redis

class SessionManager:
    """
    INTERVIEW: Redis-backed sessions for FastAPI/Django.
    """
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def _make_id(self) -> str:
        """Cryptographically random session ID."""
        return secrets.token_urlsafe(32)   # 256 bits of randomness

    async def create(self, user_id: int, data: dict = None) -> str:
        """Create new session."""
        session_id = self._make_id()
        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "data": data or {},
        }
        await self.redis.setex(
            f"session:{session_id}",
            self.ttl,
            json.dumps(session_data)
        )
        return session_id

    async def get(self, session_id: str) -> Optional[dict]:
        """Retrieve session."""
        data = await self.redis.get(f"session:{session_id}")
        if not data:
            return None
        return json.loads(data)

    async def update(self, session_id: str, data: dict):
        """Update session data."""
        session = await self.get(session_id)
        if not session:
            return
        session["data"].update(data)
        await self.redis.setex(
            f"session:{session_id}",
            self.ttl,
            json.dumps(session)
        )

    async def extend(self, session_id: str):
        """Reset TTL (sliding expiration)."""
        await self.redis.expire(f"session:{session_id}", self.ttl)

    async def destroy(self, session_id: str):
        """Logout — delete session."""
        await self.redis.delete(f"session:{session_id}")

    async def destroy_all_user_sessions(self, user_id: int):
        """Global logout — destroy all user's sessions."""
        # Track sessions per user separately
        session_ids = await self.redis.smembers(f"user:{user_id}:sessions")
        if session_ids:
            keys = [f"session:{sid.decode()}" for sid in session_ids]
            await self.redis.delete(*keys)
            await self.redis.delete(f"user:{user_id}:sessions")
```

**HOW — Track sessions per user (for global logout):**

```python
async def create_session_with_user_index(self, user_id: int) -> str:
    session_id = self._make_id()
    session_data = {"user_id": user_id, "created_at": time.time()}

    pipe = self.redis.pipeline()
    pipe.setex(f"session:{session_id}", self.ttl, json.dumps(session_data))
    # ⭐ Index sessions per user
    pipe.sadd(f"user:{user_id}:sessions", session_id)
    pipe.expire(f"user:{user_id}:sessions", self.ttl)
    await pipe.execute()

    return session_id
```

**Storage options comparison:**

| Storage | Pros | Cons | Best For |
|---|---|---|---|
| **Redis** | Fast, TTL built-in | Extra infra | Most production apps |
| **PostgreSQL** | Already have DB | Slower, DB load | Small scale |
| **In-memory** | Fastest | Lost on restart, no multi-instance | Single instance dev |
| **DynamoDB** | Managed, scalable | AWS-specific | AWS-native apps |
| **Memcached** | Fast | No persistence | Simple caching |

---

### Q3: Session fixation attack — prevention?

**Answer:**

**WHAT:** Attacker sets known session ID, victim logs in, attacker uses same session ID.

**HOW attack works:**

```
1. Attacker visits site, gets session ID: ABC123
2. Attacker sends victim link: site.com?session_id=ABC123
3. Victim visits, server attaches login to ABC123
4. Attacker uses ABC123 → logged in as victim!
```

**HOW — Prevention: regenerate session ID on login**

```python
class LoginHandler:
    """
    INTERVIEW: Always regenerate session ID after privilege changes.
    """
    async def login(self, request, response, username, password):
        # 1. Verify credentials
        user = await authenticate(username, password)
        if not user:
            raise HTTPException(401, "Invalid credentials")

        # 2. ⭐ DESTROY old anonymous session
        old_session_id = request.cookies.get("session_id")
        if old_session_id:
            await session_mgr.destroy(old_session_id)

        # 3. ⭐ CREATE new session (different ID)
        new_session_id = await session_mgr.create(user.id)

        # 4. Set new cookie
        response.set_cookie(
            "session_id", new_session_id,
            httponly=True, secure=True, samesite="strict"
        )

        return {"user": user.email}


    async def privilege_escalation(self, request, response):
        """Also regenerate on becoming admin, etc."""
        old_session_id = request.cookies.get("session_id")
        old_data = await session_mgr.get(old_session_id)

        # New session with elevated privileges
        await session_mgr.destroy(old_session_id)
        new_session_id = await session_mgr.create(old_data["user_id"])

        response.set_cookie("session_id", new_session_id, ...)
```

---

### Q4: Remember me — separate token strategy?

**Answer:**

**WHAT:** Long-lived auto-login token, separate from session.

**WHY:**
- Session: short (24h) for security
- Remember me: long (30-90 days) for UX
- Different security trade-offs

**HOW — Implementation:**

```python
import secrets
import hashlib
from datetime import datetime, timedelta

class RememberMeManager:
    """
    INTERVIEW: Persistent login with rotating tokens.
    """
    REMEMBER_ME_TTL = timedelta(days=30)

    async def create_remember_me(self, user_id: int, response: Response) -> str:
        """Create remember-me token (called on login if 'Remember me' checked)."""
        # Token = random selector + random validator
        selector = secrets.token_urlsafe(12)
        validator = secrets.token_urlsafe(32)

        # Store HASH of validator (defense if DB stolen)
        validator_hash = hashlib.sha256(validator.encode()).hexdigest()

        await db.remember_me_tokens.create(
            user_id=user_id,
            selector=selector,
            validator_hash=validator_hash,
            expires_at=datetime.utcnow() + self.REMEMBER_ME_TTL,
        )

        # Cookie: selector:validator
        token = f"{selector}:{validator}"
        response.set_cookie(
            key="remember_me",
            value=token,
            max_age=int(self.REMEMBER_ME_TTL.total_seconds()),
            httponly=True,
            secure=True,
            samesite="strict",
        )

    async def auto_login_from_remember_me(self, request, response) -> Optional[int]:
        """
        Validate remember-me cookie, return user_id if valid.
        ⭐ ROTATE token on each use (theft detection).
        """
        token = request.cookies.get("remember_me")
        if not token or ":" not in token:
            return None

        selector, validator = token.split(":", 1)

        # Look up by selector
        record = await db.remember_me_tokens.find_by_selector(selector)
        if not record:
            return None

        # ⭐ Constant-time comparison of validator
        provided_hash = hashlib.sha256(validator.encode()).hexdigest()
        if not hmac.compare_digest(provided_hash, record.validator_hash):
            # ⚠️ Selector found but validator wrong = THEFT
            # Delete ALL user's remember-me tokens
            await db.remember_me_tokens.delete_all_for_user(record.user_id)
            return None

        # Check expiration
        if record.expires_at < datetime.utcnow():
            await db.remember_me_tokens.delete(record.id)
            return None

        # ⭐ ROTATE: Delete old, issue new (defense if token leaked)
        await db.remember_me_tokens.delete(record.id)
        await self.create_remember_me(record.user_id, response)

        return record.user_id
```

---

### Q5: Logout strategies — single + global logout?

**Answer:**

**WHAT:**
- **Single logout** = This device only
- **Global logout** = All devices for this user

**HOW — Single logout:**

```python
@app.post("/api/logout")
async def logout(request: Request, response: Response):
    """Logout from this device only."""
    session_id = request.cookies.get("session_id")
    if session_id:
        await session_mgr.destroy(session_id)

    # Clear cookies
    response.delete_cookie("session_id")
    response.delete_cookie("remember_me")

    return {"status": "logged_out"}
```

**HOW — Global logout (all devices):**

```python
@app.post("/api/logout-all")
async def logout_all_devices(request: Request, response: Response, user=Depends(get_current_user)):
    """Logout from ALL devices."""
    # 1. Destroy all sessions for user
    await session_mgr.destroy_all_user_sessions(user.id)

    # 2. Revoke all refresh tokens
    await db.refresh_tokens.revoke_all_for_user(user.id)

    # 3. Delete all remember-me tokens
    await db.remember_me_tokens.delete_all_for_user(user.id)

    # 4. (Optional) Increment "token_version" — invalidates JWTs
    await db.users.increment_token_version(user.id)

    # 5. Clear cookies (this device)
    response.delete_cookie("session_id")
    response.delete_cookie("remember_me")

    return {"status": "logged_out_all_devices"}
```

**HOW — JWT global logout (harder without DB lookup):**

```python
# Strategy 1: Token version in DB
# JWT contains "token_version" claim
# Server checks JWT.token_version == DB.user.token_version
# Increment DB version on global logout → all JWTs invalid

class TokenManager:
    def create_jwt(self, user):
        return jwt.encode({
            "sub": user.id,
            "token_version": user.token_version,   # ⭐
            "exp": ...
        }, SECRET_KEY)

    def verify_jwt(self, token):
        payload = jwt.decode(token, SECRET_KEY, ...)
        user = db.users.get(payload["sub"])
        if payload["token_version"] != user.token_version:
            raise InvalidTokenError("Token revoked")
        return payload


# Strategy 2: JTI (JWT ID) blacklist in Redis
# Add JWT JTI to Redis on logout
# Verify checks Redis blacklist

async def logout_jwt(token):
    payload = jwt.decode(token, SECRET_KEY, options={"verify_signature": False})
    jti = payload["jti"]
    exp = payload["exp"]
    ttl = exp - time.time()

    # Blacklist until token expires
    await redis.setex(f"blacklist:{jti}", int(ttl), "1")


async def verify_jwt_with_blacklist(token):
    payload = jwt.decode(token, SECRET_KEY)
    jti = payload["jti"]
    if await redis.get(f"blacklist:{jti}"):
        raise InvalidTokenError("Token revoked")
    return payload
```

---

### Q6: Concurrent session handling — multiple devices?

**Answer:**

**WHAT:** Strategies for users logged in on multiple devices.

**HOW — Strategies:**

**Strategy 1: Allow unlimited sessions (most apps)**
- User can be on 5 devices simultaneously
- All sessions independent
- Logout = single device

**Strategy 2: Limit concurrent sessions**
```python
class SessionManager:
    MAX_SESSIONS_PER_USER = 5

    async def create_with_limit(self, user_id: int) -> str:
        # Get existing sessions
        sessions = await self.redis.smembers(f"user:{user_id}:sessions")

        # If limit exceeded, destroy oldest
        if len(sessions) >= self.MAX_SESSIONS_PER_USER:
            # Get session timestamps
            sessions_with_times = []
            for sid in sessions:
                data = await self.get(sid.decode())
                if data:
                    sessions_with_times.append((sid.decode(), data["created_at"]))

            # Sort by age, destroy oldest
            sessions_with_times.sort(key=lambda x: x[1])
            for sid, _ in sessions_with_times[:-self.MAX_SESSIONS_PER_USER + 1]:
                await self.destroy(sid)

        return await self.create(user_id)
```

**Strategy 3: Single active session (kick others)**
```python
async def create_single_session(self, user_id: int) -> str:
    """Login from new device kicks old sessions."""
    # Destroy all existing
    await self.destroy_all_user_sessions(user_id)
    # Create new
    return await self.create(user_id)
```

**Strategy 4: List active sessions (security UX)**
```python
@app.get("/api/account/sessions")
async def list_my_sessions(user=Depends(get_current_user)):
    """Show all active sessions (for user to manage)."""
    session_ids = await redis.smembers(f"user:{user.id}:sessions")
    sessions = []
    for sid in session_ids:
        data = await redis.get(f"session:{sid.decode()}")
        if data:
            session = json.loads(data)
            sessions.append({
                "id": sid.decode()[-8:],   # Show partial ID
                "created_at": session["created_at"],
                "last_seen": session.get("last_seen"),
                "ip": session.get("ip"),
                "user_agent": session.get("user_agent"),
                "is_current": sid.decode() == current_session_id,
            })
    return sessions


@app.delete("/api/account/sessions/{session_id_suffix}")
async def revoke_session(session_id_suffix: str, user=Depends(get_current_user)):
    """User revokes specific session."""
    session_ids = await redis.smembers(f"user:{user.id}:sessions")
    for sid in session_ids:
        sid_str = sid.decode()
        if sid_str.endswith(session_id_suffix):
            await session_mgr.destroy(sid_str)
            return {"status": "revoked"}
    raise HTTPException(404)
```

---

### Q7: Session metadata — IP binding, device fingerprinting?

**Answer:**

**WHAT:** Extra session data to detect theft.

**HOW — IP/device tracking:**

```python
class SecureSessionManager:
    async def create_with_metadata(self, request: Request, user_id: int):
        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "ip": request.client.host,
            "user_agent": request.headers.get("User-Agent", ""),
            "fingerprint": self._compute_fingerprint(request),
        }
        # ...

    def _compute_fingerprint(self, request) -> str:
        """Device fingerprint from headers."""
        components = [
            request.headers.get("User-Agent", ""),
            request.headers.get("Accept-Language", ""),
            request.headers.get("Accept-Encoding", ""),
            request.headers.get("Accept", ""),
        ]
        return hashlib.sha256("|".join(components).encode()).hexdigest()[:16]

    async def validate(self, request: Request, session_id: str) -> dict:
        session = await self.get(session_id)
        if not session:
            return None

        # ⭐ Detect suspicious activity
        current_ip = request.client.host
        current_fp = self._compute_fingerprint(request)

        if session["ip"] != current_ip:
            # IP changed - could be:
            # - User moved (WiFi → mobile)
            # - Attacker stole session
            # Strategy: Warn user, require re-auth for sensitive actions

            await self._alert_user(session["user_id"], current_ip, session["ip"])
            session["ip_changed"] = True

        if session["fingerprint"] != current_fp:
            # Different browser/device with same session — RED FLAG
            # Probably stolen — destroy session
            await self.destroy(session_id)
            return None

        # Update last seen
        session["last_seen"] = time.time()
        await self.update(session_id, session)

        return session
```

**Trade-offs:**
- ⚠️ IP changes legitimately (mobile, VPN, NAT)
- ⚠️ Don't fail hard on IP change → false positives
- ✅ Require step-up auth (2FA) for sensitive actions if IP changed

---

### Q8: Django session framework — production setup?

**Answer:**

**HOW — Django sessions config:**

```python
# settings.py

# Backend choice
SESSION_ENGINE = "django.contrib.sessions.backends.cache"   # Redis-backed
# Other options:
# - "django.contrib.sessions.backends.db"           # Database
# - "django.contrib.sessions.backends.cached_db"   # Cache + DB fallback
# - "django.contrib.sessions.backends.file"        # File system
# - "django.contrib.sessions.backends.signed_cookies"  # Cookie-only (signed)

# Cache config for Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/0",
    }
}

# Cookie attributes
SESSION_COOKIE_NAME = "sessionid"
SESSION_COOKIE_AGE = 86400              # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True            # ⭐ HTTPS only
SESSION_COOKIE_SAMESITE = "Lax"         # ⭐ CSRF defense
SESSION_COOKIE_DOMAIN = None            # Or ".example.com" for subdomains
SESSION_COOKIE_PATH = "/"

# Session behavior
SESSION_EXPIRE_AT_BROWSER_CLOSE = False     # True = expires on browser close
SESSION_SAVE_EVERY_REQUEST = False          # True = refresh TTL on each request

# CSRF (separate from session)
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False                # ⭐ JS reads this for AJAX
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = ["https://app.example.com"]
```

---

## Session Management Checklist

```markdown
### Cookies
- [ ] HttpOnly (XSS defense)
- [ ] Secure (HTTPS only)
- [ ] SameSite=Strict or Lax (CSRF defense)
- [ ] __Host- prefix for session cookies (optional)
- [ ] Reasonable Max-Age (24h-7d)

### Session ID
- [ ] Cryptographically random (256 bits)
- [ ] Regenerated on login (fixation defense)
- [ ] Regenerated on privilege escalation
- [ ] Stored hashed in DB (optional defense)

### Storage
- [ ] Server-side (Redis recommended)
- [ ] TTL enforced (auto-cleanup)
- [ ] Per-user index (for global logout)

### Logout
- [ ] Single logout: destroy session
- [ ] Global logout: destroy all + revoke refresh tokens
- [ ] Clear cookies (delete_cookie)
- [ ] List active sessions UI

### Remember Me
- [ ] Separate from session
- [ ] Long TTL (30-90 days)
- [ ] Rotate token on each use
- [ ] Detect theft (validator mismatch)

### Security
- [ ] IP/device fingerprint tracking (optional)
- [ ] Step-up auth for sensitive ops
- [ ] Rate limit login attempts
- [ ] Notify user of new device login
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| `httponly=False` for session | XSS steals session | Always `httponly=True` |
| No `Secure` flag | Cookie sent over HTTP | Always `secure=True` in prod |
| `SameSite=None` without Secure | Cookie blocked | Add Secure flag |
| Predictable session ID | Brute force | Use `secrets.token_urlsafe(32)` |
| No regeneration on login | Session fixation | Destroy + create new |
| Session never expires | Stolen tokens forever | TTL + sliding expiration |
| Same session ID in URL | Logged in referer | Always cookies |
| No global logout | Stolen device still active | Implement logout-all |
