# OWASP API Top 10 — FastAPI Hardening

## Why It Matters (Senior 5 YOE Context)

OWASP API Security Top 10 = **standard pentest checklist**. Every senior backend interview includes 1-2 of these. They're not theoretical — every breach has at least one.

2023 list:
1. **BOLA** (Broken Object-Level Authorization)
2. **Broken Authentication**
3. **Broken Object Property-Level Authorization**
4. **Unrestricted Resource Consumption**
5. **Broken Function-Level Authorization**
6. **Unrestricted Access to Sensitive Business Flows**
7. **SSRF** (Server-Side Request Forgery)
8. **Security Misconfiguration**
9. **Improper Inventory Management**
10. **Unsafe Consumption of APIs**

Senior asks: "What are the top API security risks and how does your stack mitigate each?"

---

## Core Concepts

### 1. BOLA (Broken Object-Level Authorization) — Most Common

```python
# VULNERABLE — anyone can read anyone's order
@app.get("/orders/{order_id}")
def get_order(order_id: int, user=Depends(get_current_user)):
    return db.get_order(order_id)
```

Attacker: changes `order_id=123` to `order_id=124` → reads another user's data.

```python
# SAFE — check ownership
@app.get("/orders/{order_id}")
def get_order(order_id: int, user=Depends(get_current_user)):
    order = db.get_order(order_id)
    if order is None:
        raise HTTPException(404, "Not found")
    if order.user_id != user.id and not user.is_admin:
        raise HTTPException(404, "Not found")  # 404, not 403, to avoid enum
    return order
```

**Tip:** Return 404 (not 403) for unauthorized — don't leak existence.

### 2. Broken Authentication

Common holes:
- Weak JWT secrets, no validation
- No rate limit on /login → brute force
- Predictable password reset tokens
- Tokens in URL
- No MFA on sensitive ops

```python
# Login rate limit
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

JWT validation pitfalls:

```python
# VULNERABLE — accepts 'none' algorithm
jwt.decode(token, key, algorithms=['HS256', 'none'])

# SAFE
jwt.decode(token, key, algorithms=['HS256'])
```

### 3. Broken Object Property-Level Authorization (Mass Assignment)

```python
# VULNERABLE
class UserUpdate(BaseModel):
    name: str
    email: str
    is_admin: bool  # user can promote themselves!


@app.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, user=Depends(get_current_user)):
    db.update_user(user_id, **payload.model_dump(exclude_unset=True))
```

Attacker sends `{"is_admin": true}` → privilege escalation.

```python
# SAFE — separate model for user-controllable fields
class UserSelfUpdate(BaseModel):
    name: str
    email: str
    # NO is_admin — only admin endpoint exposes that


class AdminUserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    is_admin: bool | None = None
```

### 4. Unrestricted Resource Consumption

- File upload without size limit
- Pagination without max page size
- LLM endpoints without token budget
- DB queries without timeouts

```python
@app.get("/articles/")
def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),  # MAX 100
):
    return db.articles[skip:skip + limit]


# DB query timeout
DATABASE_URL = "postgresql://...?options=-c%20statement_timeout%3D10000"  # 10s


# File upload
async def upload(file: UploadFile = File(..., max_length=10 * 1024 * 1024)):
    ...


# Body size limit (middleware or proxy)
# nginx: client_max_body_size 10M;
```

### 5. Broken Function-Level Authorization

```python
# VULNERABLE — admin endpoint just hidden, not protected
@app.delete("/admin/users/{user_id}")
def admin_delete(user_id: int):  # no auth check!
    db.delete_user(user_id)
```

```python
# SAFE — explicit admin check
@app.delete("/admin/users/{user_id}")
def admin_delete(
    user_id: int,
    user=Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(403)
    db.delete_user(user_id)


# Better: use Depends for admin
def require_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403)
    return user


@app.delete("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def admin_delete(user_id: int):
    ...
```

### 6. Unrestricted Access to Sensitive Business Flows

```
- Bulk purchase API → scalper bots
- Bulk friend request → spam
- Password reset spam → DOS
- Coupon application → unlimited stacking
```

Mitigations: CAPTCHA, IP rate limit, per-user limits, anomaly detection.

### 7. SSRF (Server-Side Request Forgery)

```python
# VULNERABLE
@app.post("/webhook-test")
async def webhook_test(url: str):
    async with httpx.AsyncClient() as c:
        resp = await c.get(url)  # attacker provides http://169.254.169.254/latest/meta-data/
    return resp.text
```

Attacker reads AWS IAM role credentials. Mitigations:

```python
import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # link-local (AWS metadata!)
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fe80::/10'),
]


def validate_outbound_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('Invalid scheme')

    hostname = parsed.hostname
    if not hostname:
        raise ValueError('No hostname')

    # Resolve all A/AAAA — check each
    for info in socket.getaddrinfo(hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        for net in BLOCKED_NETWORKS:
            if ip in net:
                raise ValueError(f'Blocked: {ip}')
```

### 8. Security Misconfiguration

- DEBUG=True in prod
- Default credentials
- Verbose error messages
- Missing CORS restrictions
- Outdated TLS

```python
# Production checklist
app = FastAPI(
    debug=False,           # NEVER True in prod
    docs_url=None,         # disable /docs in prod (or behind auth)
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(Exception)
async def all_exception_handler(request, exc):
    # Don't leak stack traces
    return JSONResponse({'error': 'Internal error'}, status_code=500)
```

### 9. Improper Inventory Management

Old API versions still running, undocumented endpoints, internal endpoints exposed.

```python
# Document everything in OpenAPI
# Use API versioning (/v1, /v2)
# Sunset old versions
# Audit list of endpoints in CI
```

### 10. Unsafe Consumption of APIs

```python
# VULNERABLE — trusting 3rd party response blindly
external = httpx.get('https://api.example.com/data').json()
total = sum(external['amounts'])  # what if amounts is huge?
```

Validate responses; set size limits on responses:

```python
async with httpx.AsyncClient(timeout=5.0) as c:
    resp = await c.get(url)
    if int(resp.headers.get('content-length', 0)) > 1_000_000:
        raise HTTPException(502)
    data = resp.json()


# Validate response shape
from pydantic import BaseModel


class ExternalResponse(BaseModel):
    amount: float
    currency: str


validated = ExternalResponse.model_validate(data)
```

---

## How It Works Internally

### Common Attack Surface

- **Path traversal** — `../../etc/passwd` in filenames
- **Mass assignment** — JSON body overwrites privileged fields
- **JSON nesting bombs** — deeply nested `{"a": {"a": ...}}` → stack overflow
- **Polyglot files** — JPEG that's also valid PHP
- **HTTP smuggling** — Content-Length vs Transfer-Encoding mismatch

### Defense in Depth

```
Edge: Cloudflare WAF, DDoS protection
LB: nginx (rate limit, request size, header validation)
App: FastAPI (auth, validation, business logic)
DB: pgBouncer, statement timeouts, RLS
```

---

## Common Pitfalls

### 1. 403 vs 404 for Unauthorized

Returning 403 says "exists but not yours" — info leak. Use 404 ("not found") to be conservative.

### 2. Generic "User Not Found" vs "Invalid Password"

```python
# BAD — enables enumeration
if not user:
    raise HTTPException(404, "User not found")
if not check_password(password):
    raise HTTPException(401, "Wrong password")

# GOOD
if not user or not check_password(password, user.password_hash):
    raise HTTPException(401, "Invalid credentials")
```

### 3. CORS Wildcards + Credentials

```python
# VULNERABLE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # disallowed with *, but browsers may misbehave
)


# SAFE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
)
```

### 4. Logging Secrets

```python
# logs: "Login attempt: user=alice, password=secret123"
logger.info(f"Login attempt: user={u}, password={p}")  # NEVER
```

### 5. Error Messages Leak

```python
# Prod
raise HTTPException(500, f"DB error: {e}")  # leaks schema info
```

### 6. Missing Output Encoding

JSON responses safe by default. But if you ever return HTML / templates, XSS = real.

---

## Interview Q&A

**Q1:** OWASP API Top 10 mein sabse common kya hai?
**A:** BOLA (Broken Object-Level Authorization) — far most common. Pattern: user-provided ID in URL, server fetches by ID without verifying ownership. Mitigation: always check `obj.owner_id == current_user.id` (or use RBAC) before returning data. Return 404 for unauthorized to avoid info leak.

**Q2:** Mass assignment kaise prevent karoge FastAPI mein?
**A:** Separate Pydantic models — `UserSelfUpdate` (excludes `is_admin`), `AdminUserUpdate` (includes). Never share write models between admin and user endpoints. For DRF: use separate serializers per endpoint. For raw dicts: explicit allowlist of writable fields.

**Q3:** SSRF mitigation strategy?
**A:** (1) Validate URL scheme (http/https only). (2) Resolve all A/AAAA records, block private IPs (10.x, 172.16.x, 192.168.x, 169.254.x — AWS metadata!). (3) Outbound proxy that enforces allowlist. (4) Use httpx with explicit timeout. (5) Don't follow redirects (`follow_redirects=False`).

**Q4:** Rate limit production grade kaise?
**A:** Multi-layer: (1) Cloudflare/edge for DDoS. (2) nginx `limit_req` for IP-level. (3) App-level slowapi/redis-based per-user. (4) Per-endpoint scopes (login = strict, search = relaxed). (5) Token-based budgets for LLM/expensive endpoints. Return 429 with Retry-After header.

**Q5:** JWT vulnerabilities batao.
**A:** (1) `alg: none` accepted → use explicit `algorithms=['HS256']`. (2) Weak secret → 256+ bits, env var. (3) HS256 → RS256 confusion → bind algorithm to key type. (4) No expiry check → always validate `exp`. (5) Storing in localStorage → XSS risk → use httpOnly cookies. (6) No revocation → short TTL + denylist for sensitive logout.

**Q6:** Sensitive business flow protection kaise?
**A:** (1) CAPTCHA on bot-prone endpoints (signup, password reset). (2) Per-user limits (max 5 password resets / day). (3) Anomaly detection (multiple resets from same IP). (4) Step-up auth (MFA for sensitive ops). (5) Velocity checks (10 purchases in 1 min = suspicious).

**Q7:** Improper inventory management ka matlab?
**A:** Forgotten endpoints — v1 API still running after v2 launch, internal/debug routes exposed to public, undocumented admin endpoints. Mitigation: API gateway with explicit routing, audit list in CI, automated discovery tools (e.g., kiterunner), proper deprecation lifecycle (sunset header).

**Q8:** Unsafe third-party API consumption kaise handle karte ho?
**A:** (1) Timeout on every external call (`timeout=5.0`). (2) Response size limit. (3) Validate shape with Pydantic. (4) Treat upstream as untrusted — escape/sanitize before storing/rendering. (5) Cache + fallback for resilience. (6) Don't expose external errors to user — generic message.

---

## Real-World Use Cases

### 1. Multi-Tenant SaaS — Object Auth

Every endpoint scoped to tenant via dependency:

```python
def get_tenant_db(user: User = Depends(get_current_user)):
    return Database(tenant_id=user.tenant_id)


@app.get("/orders/{order_id}")
def get_order(order_id: int, db=Depends(get_tenant_db)):
    return db.get_order(order_id)  # scoped to user.tenant_id
```

### 2. Webhook Receiver — SSRF + Replay Protection

```python
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, signature: str = Header(...)):
    body = await request.body()
    # HMAC verify
    expected = compute_hmac(body, STRIPE_SECRET)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401)
    # Replay protection
    event_id = ...
    if cache.exists(f'webhook:{event_id}'):
        return  # idempotent
    cache.set(f'webhook:{event_id}', '1', ex=86400)
    # Process
```

### 3. File Upload — Multi-Layer Defense

Validate size, MIME (libmagic), filename, extension, store outside webroot, async virus scan.

---

## References

- [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
- [JWT best practices RFC 8725](https://datatracker.ietf.org/doc/html/rfc8725)
- [SSRF prevention cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- `bandit`, `safety`, `pip-audit` for Python security scanning
