# OWASP Top 10, Brute Force Protection, CSRF

---

# PART 1: OWASP Top 10 (2021)

## What is OWASP Top 10?
- **OWASP** = Open Web Application Security Project
- **Top 10** = sabse zyada critical web security risks — industry standard reference
- Interview mein aksar puchha jata hai: "OWASP Top 10 kya hai?"
- Har 3-4 saal mein update hota hai

## Why Know It?
```
✓ Security code review ka framework
✓ Interview mein expected knowledge (5yr developer)
✓ Penetration testing checklist
✓ Compliance requirements (SOC2, ISO 27001)
```

## How — Each Vulnerability + Fix

### Q1: OWASP Top 10 explain karo with code examples?

**Answer:**

---

#### A01: Broken Access Control (Most Critical)
```python
# WHAT: User resources access kar sakta hai jo uske nahi hain

# BAD — koi bhi kisi ka order dekh sakta hai
@app.get("/orders/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    return await db.get(Order, order_id)  # no auth check!

# GOOD — owner check karo
@app.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")  # IDOR prevention
    return order

# INTERVIEW: IDOR kya hai?
# Insecure Direct Object Reference — /orders/1 → /orders/2 → someone else's order
# Fix: Always check ownership before returning resource
```

#### A02: Cryptographic Failures
```python
# WHAT: Sensitive data unencrypted — plaintext passwords, PII, credit cards

# BAD — plaintext password store
user.password = request.password          # NEVER!
user.password = md5(request.password)    # MD5 = broken, too fast

# GOOD — bcrypt (slow hash = brute force hard)
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
user.hashed_password = pwd_ctx.hash(request.password)

# BAD — sensitive data in logs
logger.info(f"User login: email={email} password={password}")

# GOOD — never log sensitive fields
logger.info(f"User login: user_id={user.id} email={email}")

# BAD — HTTP (no TLS)
# GOOD — always HTTPS + HSTS header
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

# BAD — JWT with weak algorithm or no signature
# GOOD — always verify algorithm + use strong secret
jwt.decode(token, SECRET_KEY, algorithms=["HS256"])  # specify algorithm explicitly
# NEVER: jwt.decode(token, options={"verify_signature": False})
```

#### A03: Injection (SQL, Command, LDAP)
```python
# WHAT: User input directly in query → attacker controls the query

# BAD — SQL Injection
query = f"SELECT * FROM users WHERE email = '{email}'"
# Attacker input: ' OR '1'='1 → returns all users!

# GOOD — parameterized queries (SQLAlchemy / asyncpg handle escaping)
result = await db.execute(
    select(User).where(User.email == email)
)
# Raw SQL: always use $1 placeholders
await conn.fetch("SELECT * FROM users WHERE email = $1", email)

# BAD — Command Injection
filename = request.query_params.get("file")
os.system(f"cat {filename}")  # input: "file; rm -rf /"

# GOOD — never shell=True with user input
import subprocess, shlex
subprocess.run(["cat", shlex.quote(filename)], shell=False, check=True)

# BAD — Template injection
from jinja2 import Template
Template(user_input).render()  # user can inject {{ config.SECRET_KEY }}

# GOOD — use autoescaping, never render user input as template
from jinja2 import Environment
env = Environment(autoescape=True)
```

#### A04: Insecure Design
```python
# WHAT: Missing security controls at design level

# Example: Password reset — guessable tokens
# BAD — sequential reset token
reset_token = str(user.id)  # attacker guesses others' tokens

# GOOD — cryptographically random token
import secrets
reset_token = secrets.token_urlsafe(32)
# Store: hash(reset_token) in DB, short TTL (15 min)
await redis.setex(f"reset:{hashlib.sha256(reset_token.encode()).hexdigest()}", 900, user.id)

# Example: File upload — no type validation
# BAD — trust Content-Type header (spoofable)
if file.content_type == "image/jpeg": ...

# GOOD — validate actual file content (magic bytes)
import magic
content = await file.read(512)
mime_type = magic.from_buffer(content, mime=True)
if mime_type not in {"image/jpeg", "image/png"}:
    raise HTTPException(415, "Invalid file type")
```

#### A05: Security Misconfiguration
```python
# WHAT: Default configs, debug mode, open cloud storage, verbose errors

# BAD
app = FastAPI(debug=True)  # stack traces in production!
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# GOOD
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
app = FastAPI(debug=DEBUG)

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS)

# BAD — detailed error to client
@app.exception_handler(Exception)
async def generic_error(req, exc):
    return JSONResponse(500, {"error": str(exc), "traceback": traceback.format_exc()})

# GOOD — generic message, log internally
@app.exception_handler(Exception)
async def generic_error(req, exc):
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# Remove server fingerprint
response.headers.pop("Server", None)
response.headers.pop("X-Powered-By", None)
```

#### A06: Vulnerable & Outdated Components
```
# What: Third-party libraries with known CVEs

# How to detect:
pip install safety
safety check                          # scan installed packages against CVE DB

pip install pip-audit
pip-audit                             # audit requirements for vulnerabilities

# CI/CD mein add karo:
# .github/workflows/security.yml
# - name: Security audit
#   run: pip-audit --requirement requirements.txt --format json

# Renovate / Dependabot: auto PR for dependency updates
```

#### A07: Identification & Authentication Failures
```python
# WHAT: Weak passwords, no MFA, session fixation, credential stuffing

# BAD — no password strength check
user.hashed_password = hash(password)  # "123456" allowed!

# GOOD — enforce strong passwords
import re
def validate_password_strength(password: str) -> bool:
    checks = [
        len(password) >= 8,           # min length
        re.search(r"[A-Z]", password),# uppercase
        re.search(r"[a-z]", password),# lowercase
        re.search(r"\d", password),   # digit
        re.search(r"[!@#$%^&*]", password),  # special char
    ]
    if not all(checks):
        raise ValueError("Password too weak")
    return True

# BAD — no brute force protection
@app.post("/auth/login")
async def login(credentials: LoginRequest): ...

# GOOD — rate limit + account lockout (see Part 2)

# BAD — long-lived sessions, no invalidation on logout
# GOOD — short JWT + revocation list, logout invalidates token
```

#### A08: Software and Data Integrity Failures
```python
# WHAT: Unsigned updates, deserialization of untrusted data, CI/CD tampering

# BAD — pickle deserialization (remote code execution risk!)
import pickle
data = pickle.loads(user_supplied_bytes)  # NEVER deserialize untrusted data!

# GOOD — JSON only for untrusted input
import json
data = json.loads(user_supplied_string)

# BAD — no signature verification on webhooks
@app.post("/webhook")
async def webhook(payload: dict): ...

# GOOD — always verify webhook signature (HMAC)
import hmac, hashlib
def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.replace("sha256=", ""))
```

#### A09: Security Logging & Monitoring Failures
```python
# WHAT: No audit logs → breach undetected for months

# GOOD — log security events
import structlog
logger = structlog.get_logger()

# Authentication events
logger.info("auth.login.success",   user_id=user.id, ip=request.client.host)
logger.warning("auth.login.failed", email=email,     ip=request.client.host, reason="wrong_password")
logger.warning("auth.login.locked", email=email,     ip=request.client.host)

# Authorization events
logger.warning("authz.denied",      user_id=user.id, resource=f"/orders/{order_id}", action="read")

# Data access events
logger.info("data.access",          user_id=user.id, resource="user_profile", record_id=profile_id)

# Suspicious activity
logger.error("security.anomaly",    user_id=user.id, event="unusual_location", ip=request.client.host)

# INTERVIEW: Kya log karna chahiye?
# ✓ Login success/failure (with IP, user-agent)
# ✓ Password changes, email changes
# ✓ Permission denied (403)
# ✓ Admin actions (delete, config change)
# ✓ Token revocations
# ✗ Never log: passwords, tokens, credit cards, PII
```

#### A10: Server-Side Request Forgery (SSRF)
```python
# WHAT: Attacker apna URL bhejta hai → server internal network fetch karta hai
# Risk: internal services (Redis, DB, cloud metadata) exposed

# BAD
@app.get("/fetch")
async def fetch_url(url: str):
    async with httpx.AsyncClient() as client:
        return await client.get(url)
# Attacker input: http://169.254.169.254/latest/meta-data/ (AWS metadata!)
# Or: http://localhost:6379/ (Redis!), http://internal-db:5432/

# GOOD — allowlist URLs
from urllib.parse import urlparse

ALLOWED_DOMAINS = {"api.trusted.com", "cdn.myapp.com"}

def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS allowed")
    if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        raise ValueError("Local addresses not allowed")
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"Domain not in allowlist: {parsed.hostname}")
    # Block private IP ranges
    import ipaddress
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("Private IP not allowed")
    except ValueError:
        pass  # hostname, not IP — OK
    return url
```

---

# PART 2: Brute Force Protection + Account Lockout

## What?
- **Brute force** = attacker thousands of password combinations try karta hai
- **Credential stuffing** = leaked password list use karke login try karo
- **Account lockout** = N failed attempts ke baad account temporarily lock karo

## Why?
```
Without protection:
  - Attacker script: 10,000 passwords/minute
  - Common passwords (123456, password) → account compromised in seconds

With protection:
  - Rate limiting: 5 attempts per minute → 10,000 attempts = 33 hours
  - Lockout: 5 failed → 15 min lockout → attacker gives up
```

## How

### Q1: Brute force protection + account lockout kaise implement karte hain?

**Answer:**
```python
import redis.asyncio as aioredis
from datetime import datetime

redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)

MAX_ATTEMPTS     = 5
LOCKOUT_DURATION = 15 * 60   # 15 minutes
ATTEMPT_WINDOW   = 60        # 1 minute window


async def check_brute_force(identifier: str) -> None:
    """
    INTERVIEW: Identifier kya hona chahiye?
    email + IP dono use karo:
    - email alone: attacker rotate kare IPs → bypass
    - IP alone:    shared IP (office, NAT) → innocent users locked
    - email + IP:  best balance
    """
    lockout_key  = f"lockout:{identifier}"
    attempts_key = f"attempts:{identifier}"

    # Check if locked
    if await redis.exists(lockout_key):
        ttl = await redis.ttl(lockout_key)
        raise HTTPException(
            status_code=429,
            detail=f"Account locked. Try again in {ttl} seconds.",
            headers={"Retry-After": str(ttl)},
        )

    # Check attempts in current window
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= MAX_ATTEMPTS:
        # Lock the account
        await redis.setex(lockout_key, LOCKOUT_DURATION, "locked")
        await redis.delete(attempts_key)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Account locked for {LOCKOUT_DURATION // 60} minutes.",
        )


async def record_failed_attempt(identifier: str) -> int:
    """Increment failed attempts counter."""
    attempts_key = f"attempts:{identifier}"
    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, ATTEMPT_WINDOW)
    return attempts


async def clear_failed_attempts(identifier: str) -> None:
    """Clear on successful login."""
    await redis.delete(f"attempts:{identifier}")
    await redis.delete(f"lockout:{identifier}")


# ─── Login endpoint with full protection ───
@app.post("/auth/login")
async def login(credentials: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Both email + IP as identifier
    identifier = f"{credentials.email}:{request.client.host}"

    # Check brute force BEFORE db query (timing attack prevention)
    await check_brute_force(identifier)
    await check_brute_force(f"ip:{request.client.host}")  # IP-level rate limit too

    user = await db.scalar(select(User).where(User.email == credentials.email))

    # TIMING ATTACK prevention: always verify (even if user not found)
    # This ensures response time is same whether user exists or not
    password_valid = False
    if user:
        password_valid = verify_password(credentials.password, user.hashed_password)

    if not user or not password_valid:
        remaining_attempts = await record_failed_attempt(identifier)
        remaining = MAX_ATTEMPTS - remaining_attempts
        raise HTTPException(
            status_code=401,
            detail=f"Invalid credentials. {max(0, remaining)} attempts remaining.",
        )

    # Success — clear attempts
    await clear_failed_attempts(identifier)

    # Log successful login
    logger.info("auth.login.success", user_id=user.id, ip=request.client.host)

    return {
        "access_token":  create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id),
        "token_type":    "bearer",
    }


# ─── Progressive delays (gentler than hard lockout) ───
DELAY_SCHEDULE = {1: 0, 2: 1, 3: 2, 4: 5, 5: 15}  # attempt → delay seconds

async def progressive_delay(identifier: str):
    """Add increasing delays instead of hard lockout (better UX)."""
    attempts_key = f"attempts:{identifier}"
    attempts = int(await redis.get(attempts_key) or 0)
    delay = DELAY_SCHEDULE.get(attempts, 30)
    if delay > 0:
        await asyncio.sleep(delay)
```

---

# PART 3: CSRF Protection

## What is CSRF?
- **CSRF** = Cross-Site Request Forgery
- Attacker ka site victim ke browser se request bhejta hai (with cookies!)
- Browser automatically session cookies attach karta hai
- Server ko lagta hai legitimate request hai

## Why It Matters?
```
Example attack:
  1. User: mybank.com mein logged in (session cookie)
  2. User: evil.com visit karta hai
  3. evil.com HTML form:
     <form action="https://mybank.com/transfer" method="POST">
       <input name="amount" value="10000">
       <input name="to" value="attacker_account">
     </form>
     <script>document.forms[0].submit()</script>
  4. Browser: request mybank.com ko bhejta hai WITH session cookie
  5. Bank: valid request process karta hai — $10,000 transferred!
```

## How

### Q1: CSRF protection kaise implement karte hain?

**Answer:**
```python
# ─── Solution 1: SameSite Cookies (Modern browsers — best approach) ───
# SameSite=Lax:    GET requests cross-site allowed, POST nahi
# SameSite=Strict: No cross-site requests at all
# SameSite=None:   All allowed (needs Secure=True)

from fastapi import Response

@app.post("/auth/login")
async def login(response: Response, credentials: LoginRequest):
    # ... auth logic ...
    token = create_access_token(user.id, user.role)

    # Set JWT in httponly + SameSite cookie (CSRF protection)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,      # JS access nahi (XSS protection)
        secure=True,        # HTTPS only
        samesite="lax",     # CSRF protection
        max_age=1800,       # 30 min
        path="/",
    )
    return {"message": "Logged in"}


# ─── Solution 2: CSRF Token (Double Submit Cookie pattern) ───
import secrets

@app.get("/auth/csrf-token")
async def get_csrf_token(response: Response):
    """Client pehle CSRF token maange, phir state-changing requests mein bheje."""
    csrf_token = secrets.token_urlsafe(32)

    # Cookie mein store karo (httponly=False — JS ko read karna hai)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JS ko read karna hai (unlike access_token)
        secure=True,
        samesite="strict",
        max_age=3600,
    )
    return {"csrf_token": csrf_token}  # also return in body


def require_csrf(
    x_csrf_token: str = Header(...),
    csrf_token:   str = Cookie(...),
):
    """
    INTERVIEW: Double Submit Cookie kaise work karta hai?
    1. Server cookie mein CSRF token set karta hai
    2. Client JS cookie read karke X-CSRF-Token header mein bhejta hai
    3. Server dono compare karta hai
    4. Attacker: cross-origin se cookie read nahi kar sakta (SOP)
       → forged request mein valid CSRF token nahi hoga
    """
    if not hmac.compare_digest(x_csrf_token, csrf_token):
        raise HTTPException(403, "CSRF token mismatch")


@app.post("/transfer", dependencies=[Depends(require_csrf)])
async def transfer_money(payload: TransferRequest, current_user: CurrentUser):
    ...


# ─── Solution 3: Custom header check (APIs ke liye) ───
# APIS usually JSON use karte hain (Content-Type: application/json)
# Simple HTML forms JSON nahi bhej sakti → CSRF naturally protected
# But add custom header check for extra safety:

def require_json_content_type(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise HTTPException(415, "Only application/json accepted")

# ─── What NOT to use ───
# ✗ Referer header — spoofable, sometimes missing (privacy settings)
# ✗ Origin header alone — some proxies strip it
# ✓ SameSite cookies + CSRF token (defense in depth)

# ─── JWT + Bearer token = naturally CSRF-safe ───
# Authorization: Bearer <token>  ← custom header
# HTML forms/img tags: Bearer header nahi bhej sakti
# → No CSRF risk for Bearer token auth
# CSRF risk only when using cookies for auth!
```

---

## Summary

| OWASP Rank | Vulnerability | Key Fix |
|---|---|---|
| A01 | Broken Access Control | Always check ownership (IDOR prevention) |
| A02 | Cryptographic Failures | bcrypt passwords, HTTPS, HSTS |
| A03 | Injection | Parameterized queries, no shell=True |
| A04 | Insecure Design | Secure by design — random tokens, type validation |
| A05 | Security Misconfiguration | Debug=False in prod, specific CORS, no verbose errors |
| A06 | Vulnerable Components | pip-audit, Dependabot, regular updates |
| A07 | Auth Failures | Strong passwords, rate limiting, MFA |
| A08 | Data Integrity | No pickle deserialization, verify webhooks |
| A09 | Logging Failures | Log auth events, never log secrets |
| A10 | SSRF | URL allowlist, block private IPs |

| Auth Method | CSRF Risk | Fix |
|---|---|---|
| Cookie (session) | Yes | SameSite=Lax/Strict + CSRF token |
| Bearer JWT header | No | Custom header not auto-attached by browser |
| API Key header | No | Same as Bearer |

| Brute Force Defense | Use When |
|---|---|
| Rate limit (5/min per IP+email) | Always |
| Account lockout (15 min) | Login endpoints |
| Progressive delay | Gentler UX alternative to lockout |
| CAPTCHA | High-value accounts, after N failures |
