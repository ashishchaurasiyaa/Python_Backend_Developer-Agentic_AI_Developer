# API Security Hardening — OWASP API Top 10 Production

## Why It Matters

APIs = #1 attack surface for modern apps. Every senior backend role asks about:
- Authentication strategies (JWT, OAuth, mTLS)
- Authorization (RBAC, ABAC, ReBAC)
- Common vulnerabilities (BOLA, mass assignment, SSRF)
- Defense in depth (edge + app + DB)

Senior interview: "Walk through securing your API end-to-end."

---

## OWASP API Security Top 10 (2023)

### API1 — Broken Object Level Authorization (BOLA)

Most common API vulnerability. Endpoint accepts ID, returns data without ownership check.

```python
# VULNERABLE
@app.get('/orders/{order_id}')
def get_order(order_id, user=Depends(get_current_user)):
    return db.get_order(order_id)   # any user can read any order


# FIXED
@app.get('/orders/{order_id}')
def get_order(order_id, user=Depends(get_current_user)):
    order = db.get_order(order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(404)    # 404 not 403 — don't leak existence
    return order
```

### API2 — Broken Authentication

- Weak JWT secrets, missing exp claim
- Predictable password reset tokens
- No rate limit on /login
- Tokens in URL

```python
# Strong JWT validation
jwt.decode(
    token,
    key=os.environ['JWT_SECRET'],      # 256+ bit secret
    algorithms=['HS256'],               # explicit, no 'none'
    options={
        'verify_signature': True,
        'verify_exp': True,
        'verify_iat': True,
        'require': ['exp', 'iat', 'sub'],
    },
)
```

### API3 — Broken Object Property-Level Authorization (Mass Assignment)

```python
# VULNERABLE
@app.patch('/users/me')
def update_me(payload: dict, user=Depends(get_current_user)):
    for key, val in payload.items():
        setattr(user, key, val)    # client can set is_admin=True
    db.save(user)


# FIXED
class UserSelfUpdate(BaseModel):
    """Whitelist — only user-editable fields."""
    name: str | None = None
    bio: str | None = None
    # NO is_admin, is_staff, password_hash


@app.patch('/users/me')
def update_me(payload: UserSelfUpdate, user=Depends(get_current_user)):
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, val)
    db.save(user)
```

### API4 — Unrestricted Resource Consumption

- File upload without size limit
- Pagination without max page size
- LLM endpoints without token budget
- DB queries without timeout

```python
# Page size enforcement
@app.get('/items')
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),   # MAX 100
):
    ...


# Upload size
async def upload(file: UploadFile = File(..., max_length=10 * 1024 * 1024)):
    ...


# DB timeout
DATABASES = {
    'default': {
        'OPTIONS': {
            'options': '-c statement_timeout=30000',
        },
    },
}
```

### API5 — Broken Function-Level Authorization

```python
# VULNERABLE — admin endpoint just hidden, not protected
@app.delete('/admin/users/{user_id}')
def admin_delete(user_id):
    db.delete_user(user_id)


# FIXED
def require_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403)
    return user


@app.delete('/admin/users/{user_id}', dependencies=[Depends(require_admin)])
def admin_delete(user_id):
    db.delete_user(user_id)
```

### API6 — Unrestricted Access to Sensitive Business Flows

- Bulk purchase API → scalper bots
- Bulk friend requests → spam
- Password reset spam → DoS
- Coupon stacking → revenue loss

Mitigations: CAPTCHA, IP rate limit, velocity checks, anomaly detection.

### API7 — SSRF (Server-Side Request Forgery)

```python
# VULNERABLE
@app.post('/webhook-test')
async def webhook_test(url: str):
    resp = await httpx.get(url)   # attacker: http://169.254.169.254/...
    return resp.text


# FIXED — validate URL
import ipaddress, socket
from urllib.parse import urlparse


BLOCKED = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # AWS metadata
]


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('Invalid scheme')
    for info in socket.getaddrinfo(parsed.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        for net in BLOCKED:
            if ip in net:
                raise ValueError(f'Blocked: {ip}')


@app.post('/webhook-test')
async def webhook_test(url: str):
    validate_url(url)
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as c:
        resp = await c.get(url)
    return resp.text
```

### API8 — Security Misconfiguration

- DEBUG=True in prod
- Default credentials
- Verbose error messages
- Missing CORS restrictions
- Outdated TLS

```python
# Generic error handler
@app.exception_handler(Exception)
async def all_exception_handler(request, exc):
    log.exception('Unhandled', exc_info=exc)
    return JSONResponse(
        {'error': 'Internal error', 'trace_id': str(uuid.uuid4())},
        status_code=500,
    )
```

### API9 — Improper Inventory Management

- Old API versions still running (v1 after v2 launched)
- Internal endpoints exposed
- Undocumented routes
- Beta endpoints in prod

Mitigations: API gateway with explicit routing, audit endpoint list, sunset old versions.

### API10 — Unsafe Consumption of APIs

- Trusting 3rd party response without validation
- No timeout on external calls
- Following untrusted redirects

```python
async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as c:
    resp = await c.get(external_url)
    if int(resp.headers.get('content-length', 0)) > 1_000_000:
        raise ValueError('Response too large')


# Validate shape
validated = ExternalResponseSchema.model_validate(resp.json())
```

---

## Authentication Strategies

### JWT (Stateless)

```python
# Pros: stateless, scales easily, no DB lookup
# Cons: hard to revoke, payload visible to client
# Use for: short-lived access tokens

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


# Refresh token stored in DB (revocable)
# Access token: signed JWT (stateless)
```

### Session (Stateful)

```python
# Pros: easy revoke, opaque tokens (no info leak)
# Cons: DB/Redis lookup per request, harder to scale
# Use for: browser-based apps, internal tools
```

### API Keys

```python
# Pros: simple for machine-to-machine
# Cons: long-lived, leak risk
# Use for: server-to-server, API integrations


# Best practices:
# - Random 32+ bytes
# - Hashed in DB (like password)
# - Scoped (read-only, specific resources)
# - Rotatable + revocable
# - Logged usage


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def authenticate_api_key(provided_key):
    hashed = hash_api_key(provided_key)
    return ApiKey.objects.filter(key_hash=hashed, active=True).first()
```

### OAuth2 + PKCE

```
For SPA/mobile (covered in detail in Phase 2 FastAPI 19)
- Authorization Code + PKCE for public clients
- Refresh token rotation
- Short access token TTL
```

### mTLS (Mutual TLS)

```
Service-to-service authentication
Both sides present certs
No passwords/tokens — cryptographic identity
```

```python
# nginx config
ssl_verify_client on;
ssl_client_certificate /etc/ssl/ca-cert.pem;

# Access cert details
proxy_set_header X-SSL-Cert-Subject $ssl_client_s_dn;
```

---

## Authorization Models

### RBAC (Role-Based)

```python
class User:
    role = 'admin' | 'editor' | 'viewer'


PERMISSIONS = {
    'admin': {'read', 'write', 'delete', 'admin'},
    'editor': {'read', 'write'},
    'viewer': {'read'},
}


def has_permission(user, permission):
    return permission in PERMISSIONS.get(user.role, set())
```

### ABAC (Attribute-Based)

```python
def can_edit_article(user, article):
    # Multiple attributes
    return (
        user.id == article.author_id or
        user.is_admin or
        (user.tier == 'premium' and article.is_public) or
        user.organization_id == article.organization_id
    )
```

### ReBAC (Relationship-Based)

```
User → has role → in organization → has access to → resource
```

Google Zanzibar / OpenFGA / Permify pattern. Best for complex sharing graphs (Google Docs).

---

## Security Headers

```python
SECURITY_HEADERS = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'geolocation=(), camera=(), microphone=()',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'",
}


# FastAPI middleware
@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    return response
```

---

## CORS

```python
from fastapi.middleware.cors import CORSMiddleware


app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://app.example.com'],   # NEVER ['*'] with credentials
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type'],
    max_age=3600,
)
```

---

## Input Validation

```python
class UserCreateIn(BaseModel):
    """Strict validation via Pydantic."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100, pattern=r'^[\w\s.-]+$')
    age: int = Field(ge=13, le=150)

    @field_validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Need uppercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Need digit')
        return v
```

---

## Secret Management

```python
# NEVER
SECRET_KEY = 'hardcoded-secret'


# GOOD — env vars
SECRET_KEY = os.environ['JWT_SECRET']
if len(SECRET_KEY) < 32:
    raise RuntimeError('JWT_SECRET too weak')


# BETTER — secret manager (AWS, Vault)
import boto3


def get_secret(name):
    client = boto3.client('secretsmanager')
    return client.get_secret_value(SecretId=name)['SecretString']


SECRET_KEY = get_secret('prod/jwt-secret')
```

Rotate regularly. Audit who accessed secrets.

---

## Defense in Depth Layers

```
Client → Edge (CDN/WAF) → Load Balancer → API Gateway → App → DB
            ↓                  ↓              ↓          ↓     ↓
        DDoS + Bot         TLS terminate   Auth      Validate  RLS
        rate limit                          AuthZ    Rate limit
                                            Routes   Audit
```

Each layer adds protection. Never rely on single layer.

---

## Common Pitfalls

### 1. Trusting Client Inputs

```python
user_id = request.headers.get('X-User-Id')   # client can lie!
```

Always derive from auth token, not headers.

### 2. Returning Sensitive Fields

```python
return user   # may include password_hash, internal_notes
```

Use Pydantic response_model to whitelist.

### 3. Verbose Errors in Prod

```python
return JSONResponse({'error': str(exc)}, 500)   # leaks stack, schema
```

Generic message + trace_id.

### 4. No Audit Trail

Security events (login fails, admin actions, perm changes) not logged → no forensics.

### 5. Hardcoded Secrets

In code or `.env` committed. Use env vars + secret manager.

### 6. Default Admin Accounts

`admin/admin` left from setup. Disable + force MFA on admin accounts.

---

## Interview Q&A

**Q1:** OWASP API Top 10 — most common?
**A:** BOLA (Broken Object Level Auth) — far most common. Always present in pentests. Pattern: URL accepts ID, server doesn't verify ownership. Mitigation: explicit ownership check in every endpoint, return 404 (not 403) for unauthorized.

**Q2:** JWT secret strength + rotation?
**A:** 256+ bits (32 random bytes base64-encoded). Env var, never in code. Rotate: support old + new during transition window. JWT library: pass list of keys, accept any. Force-revoke all sessions by changing key (logout everyone).

**Q3:** Mass assignment prevention?
**A:** Separate Pydantic models for user-input (UserSelfUpdate) vs admin (AdminUserUpdate). Never spread `request.body` into model. Whitelist editable fields per role. Code review checks for `**payload`-style updates.

**Q4:** SSRF mitigation?
**A:** Validate URL: scheme (http/https only), resolve IPs, block private/loopback/metadata ranges (10.x, 172.16.x, 192.168.x, 169.254.x, 127.x). Disable redirects on outbound calls. Use outbound proxy with allowlist for stricter control.

**Q5:** Authentication strategy choice — JWT vs session?
**A:** JWT: stateless, scales easy, mobile-friendly, but revocation hard (use short TTL + refresh tokens in DB). Session: easy revoke, cookie-based, simpler. Modern: JWT for SPA/mobile + session for server-rendered. Hybrid common.

**Q6:** RBAC vs ABAC vs ReBAC?
**A:** RBAC: roles → permissions. Simple, scales to medium complexity. ABAC: attribute-based (user.tier, time, location). Flexible. ReBAC: relationship graphs (user → org → resource). Best for sharing-heavy (Google Docs). Most apps: RBAC + ABAC mix.

**Q7:** API security testing tools?
**A:** OWASP ZAP (automated scanner). Burp Suite (manual). nuclei + custom templates. For Python: bandit (SAST), safety/pip-audit (deps), semgrep (custom rules). In CI: GitHub Advanced Security, Snyk. Pentest before major launches.

**Q8:** Edge vs app-level security split?
**A:** Edge (Cloudflare/AWS WAF): DDoS, bot, broad rate limit, geo restrictions. App: business logic auth, fine-grained authorization, audit. Edge catches volume; app catches sophistication. Don't rely only on edge — bypass possible (subdomain, IP leaks).

---

## Real-World Use Cases

### 1. Multi-Tenant SaaS

Every endpoint scoped to tenant via dependency:
```python
def get_tenant_db(user=Depends(get_current_user)):
    return Database(tenant_id=user.tenant_id)
```
+ PostgreSQL RLS as defense layer.

### 2. Public Payment API

mTLS for merchants + API keys for clients. IP allowlisting per merchant. HMAC webhook signing. Audit log every action.

### 3. Internal Microservices

Service mesh (Istio/Linkerd) for mTLS. JWT for user context propagation. OPA for policy decisions.

---

## References

- [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
- [OAuth2 best practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [JWT RFC 8725 best practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [Google Zanzibar (ReBAC)](https://research.google/pubs/pub48190/)
