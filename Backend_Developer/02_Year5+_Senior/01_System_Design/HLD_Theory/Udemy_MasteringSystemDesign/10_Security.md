# 10. Security — Auth, Encryption, OWASP, Network Security

## Security Mindset

```
Defense in depth — multiple layers, not single barrier
─────────────────
Layer 1: Network (firewall, VPC)
Layer 2: Identity (auth, MFA)
Layer 3: Authorization (RBAC, policies)
Layer 4: Data (encryption at rest + in transit)
Layer 5: Application (input validation, output sanitization)
Layer 6: Audit (logging, monitoring)
Layer 7: Response (incident plan)

If one layer fails, others still protect.
```

**Threat modeling — STRIDE:**
- **S**poofing — pretending to be someone else
- **T**ampering — modifying data in transit/rest
- **R**epudiation — denying actions you took
- **I**nformation disclosure — leaking data
- **D**enial of service — making system unavailable
- **E**levation of privilege — gaining unauthorized access

---

## CIA Triad

| Property | Means | Mechanisms |
|---|---|---|
| **Confidentiality** | Only authorized see data | Encryption, access control |
| **Integrity** | Data isn't tampered | Hashing, signatures, MAC |
| **Availability** | System accessible when needed | Redundancy, DDoS protection |

---

## Authentication vs Authorization

| Authentication (AuthN) | Authorization (AuthZ) |
|---|---|
| Who are you? | What can you do? |
| Login, MFA | RBAC, ABAC |
| Once per session | Every request |
| Identity tokens (JWT) | Permissions check |

```python
# Pseudo-flow
def authenticate(request):
    token = request.headers["Authorization"]
    user = verify_jwt(token)              # AuthN
    return user

def authorize(user, resource, action):
    if not user.has_permission(resource, action):  # AuthZ
        raise Forbidden()
```

---

## Authentication Methods

### 1. Password (Basic — never alone in 2026)

```python
# Storage — never plain text!
from passlib.hash import bcrypt

# Sign-up
password_hash = bcrypt.hash(user_password, rounds=12)
# Store password_hash in DB

# Login
if bcrypt.verify(user_input, password_hash):
    # ✓ correct
    pass
```

**Rules:**
- bcrypt or argon2 (NOT MD5, SHA1, plain SHA256)
- Cost factor 12+ for bcrypt
- Salt automatically included
- Never log passwords (sanitize loggers)

### 2. JWT (JSON Web Tokens)

```python
import jwt

# Issue
token = jwt.encode(
    {
        "sub": user_id,
        "email": user.email,
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "iss": "myapp.com",
    },
    SECRET_KEY,
    algorithm="HS256",  # or RS256 for asymmetric
)

# Verify
try:
    claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
except jwt.ExpiredSignatureError:
    raise Unauthorized("Token expired")
except jwt.InvalidTokenError:
    raise Unauthorized("Invalid token")
```

**Pros:** Stateless, scalable, works across services
**Cons:** Can't easily revoke; size bigger than session ID; secret leak = catastrophe

**Best practice:**
- Short expiry (15 min) for access token
- Long-lived refresh token (7-30 days) — stored secure (httpOnly cookie)
- Asymmetric signing (RS256) → public key verification, private key only on auth server

### 3. OAuth 2.0 / OIDC

```
User wants to login to YourApp using Google
─────────────────
1. User clicks "Sign in with Google"
2. YourApp → redirect to Google with: client_id, redirect_uri, scope, state, PKCE
3. User authenticates with Google
4. Google → redirect back with authorization code
5. YourApp exchanges code + client_secret for tokens
6. YourApp gets access_token + id_token (OIDC) + refresh_token
7. YourApp creates session
```

**Flows:**
- **Authorization Code + PKCE** — for SPAs, mobile (most common today)
- **Authorization Code** — traditional web apps
- **Client Credentials** — service-to-service
- **Device Code** — for TVs, IoT devices
- ~~Implicit flow~~ (deprecated)
- ~~Password grant~~ (deprecated)

### 4. API Keys (service-to-service)

```python
# Generate
api_key = secrets.token_urlsafe(32)  # 256 bits
api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

# Store HASH in DB, return raw key to user ONCE
# (like passwords — never recoverable)

# Verify
async def verify_key(provided_key: str):
    hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return await db.fetch_one(
        "SELECT * FROM api_keys WHERE key_hash = :h AND revoked = FALSE",
        {"h": hash},
    )
```

### 5. Multi-Factor Authentication (MFA)

```python
# TOTP (Time-based One-Time Password) — Google Authenticator
import pyotp

# Setup
secret = pyotp.random_base32()
# Store secret per user; generate QR code
totp = pyotp.TOTP(secret)
qr_uri = totp.provisioning_uri(name=user.email, issuer_name="MyApp")

# Verify on login
if not totp.verify(user_input_code, valid_window=1):  # ±30s tolerance
    raise Unauthorized("Invalid MFA code")
```

**Stronger options:**
- **Hardware keys** (FIDO2/WebAuthn — YubiKey)
- **Passkeys** (modern, phishing-resistant)
- ~~SMS OTP~~ (vulnerable to SIM swap)

---

## Authorization Models

### RBAC (Role-Based)

```python
ROLES = {
    "admin": ["users.read", "users.write", "billing.write"],
    "manager": ["users.read", "billing.read"],
    "user": ["profile.read", "profile.write"],
}

def has_permission(user, permission):
    role_perms = ROLES.get(user.role, [])
    return permission in role_perms

# Usage
@app.delete("/users/{id}")
async def delete_user(id: int, user: User = Depends(get_user)):
    if not has_permission(user, "users.write"):
        raise Forbidden()
    # ...
```

### ABAC (Attribute-Based)

More flexible — based on user attributes + resource + context.

```python
def can_edit_document(user, document):
    return (
        document.owner_id == user.id
        or "admin" in user.roles
        or (document.is_team_doc and document.team_id in user.teams)
    )
```

### Policy-as-Code (OPA — Open Policy Agent)

```rego
# Rego language
package myapp.authz

allow {
    input.user.role == "admin"
}

allow {
    input.user.id == input.resource.owner_id
    input.action == "read"
}

allow {
    input.action == "read"
    input.resource.public == true
}
```

---

## Encryption

### Symmetric (same key encrypt + decrypt)

```python
from cryptography.fernet import Fernet

key = Fernet.generate_key()
f = Fernet(key)

encrypted = f.encrypt(b"sensitive data")
decrypted = f.decrypt(encrypted)
```

**Algorithms:**
- **AES-256-GCM** — current standard
- ~~DES, 3DES~~ — broken
- ~~RC4~~ — broken

### Asymmetric (public/private key)

```python
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

# Generate keypair
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=4096,
)
public_key = private_key.public_key()

# Encrypt with public key — only private key can decrypt
encrypted = public_key.encrypt(
    b"secret",
    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
)

# Decrypt with private key
decrypted = private_key.decrypt(encrypted, padding.OAEP(...))
```

**Use cases:**
- TLS handshake (exchange symmetric key)
- JWT signing (RS256)
- Digital signatures
- Email encryption (PGP)

### Hashing (one-way)

```python
import hashlib

# For passwords — use bcrypt/argon2, NOT raw SHA
# For data integrity — SHA-256
data_hash = hashlib.sha256(data).hexdigest()

# HMAC — hashing with key (for tamper detection)
import hmac
mac = hmac.new(secret_key, data, hashlib.sha256).hexdigest()
```

---

## Encryption At Rest

| Layer | Method |
|---|---|
| **Disk** | LUKS (Linux), BitLocker, FileVault (transparent) |
| **Database** | PostgreSQL TDE, AWS RDS encryption |
| **File system** | Encrypted FS |
| **S3** | SSE-S3, SSE-KMS, SSE-C |
| **Application** | Per-column encryption for sensitive fields |

**Application-level encryption (when DB-level not enough):**

```python
# Encrypt sensitive columns in app before DB write
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.environ["DATA_KEY"]
cipher = Fernet(ENCRYPTION_KEY)

# Storage
encrypted_ssn = cipher.encrypt(ssn.encode()).decode()
await db.execute("INSERT INTO users (..., ssn_encrypted) VALUES (..., :ssn)", {...})

# Retrieval
row = await db.fetch_one("SELECT ssn_encrypted FROM users WHERE id = :id", {...})
ssn = cipher.decrypt(row.ssn_encrypted.encode()).decode()
```

**Key management:** Use **AWS KMS / GCP KMS / HashiCorp Vault** — never hard-code keys.

---

## Encryption In Transit

### TLS (Transport Layer Security)

**Always use TLS 1.3** (TLS 1.2 minimum, deprecate older).

```nginx
# Nginx
ssl_protocols TLSv1.3 TLSv1.2;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:...;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# HSTS — force HTTPS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
```

**Certificate management:**
- **Let's Encrypt** (free, auto-renewed via certbot or cert-manager)
- **ACM** (AWS) for AWS resources
- Pin certificates for high-security clients (mobile apps)

### mTLS (Mutual TLS)

Both client and server present certificates — used for service-to-service.

```python
import httpx

client = httpx.Client(
    cert=("/path/to/client.crt", "/path/to/client.key"),
    verify="/path/to/ca.crt",
)
```

Use cases:
- Internal microservices (zero-trust)
- B2B APIs
- IoT device authentication

---

## OWASP Top 10 (2021 — current)

### A01: Broken Access Control
**Issue:** Users can access what they shouldn't.
**Fix:** Verify authz on EVERY request server-side. Use deny-by-default.

### A02: Cryptographic Failures
**Issue:** Weak crypto, unencrypted data.
**Fix:** TLS 1.3, AES-256-GCM, bcrypt/argon2, key management via Vault/KMS.

### A03: Injection
**Issue:** SQL injection, command injection, LDAP injection.
**Fix:** Parameterized queries, input validation, output encoding.

```python
# BAD
query = f"SELECT * FROM users WHERE id = {user_input}"

# GOOD
query = "SELECT * FROM users WHERE id = :id"
await db.execute(query, {"id": user_input})
```

### A04: Insecure Design
**Issue:** Missing security controls in architecture.
**Fix:** Threat modeling early. Defense in depth. Secure design patterns.

### A05: Security Misconfiguration
**Issue:** Default credentials, open S3 buckets, verbose errors.
**Fix:** Hardening checklist; CIS benchmarks; security scanners (Checkov, Trivy).

### A06: Vulnerable Components
**Issue:** Outdated libraries with known CVEs.
**Fix:** Dependabot, Snyk, pip-audit, regular updates.

### A07: Authentication Failures
**Issue:** Weak passwords, no MFA, exposed session IDs.
**Fix:** MFA, strong passwords, rate limit auth, secure session management.

### A08: Software and Data Integrity Failures
**Issue:** Untrusted code, CI/CD insecure, deserialization bugs.
**Fix:** Sign artifacts (cosign), SBOM, SLSA, code signing.

### A09: Logging and Monitoring Failures
**Issue:** Can't detect attacks.
**Fix:** Audit logs, SIEM, alerts, runbooks.

### A10: SSRF (Server-Side Request Forgery)
**Issue:** App makes requests to attacker-chosen URLs.
**Fix:** Allowlist URLs, block private IPs, validate URLs.

---

## Input Validation

```python
# Use Pydantic — type + format + constraints
from pydantic import BaseModel, EmailStr, constr, validator

class UserCreate(BaseModel):
    email: EmailStr                              # validates format
    name: constr(min_length=1, max_length=100)
    age: int = Field(..., ge=13, le=120)

    @validator("name")
    def no_html(cls, v):
        if "<" in v or ">" in v:
            raise ValueError("HTML not allowed")
        return v

# Server-side validation ALWAYS — never trust client
@app.post("/users")
async def create_user(user: UserCreate):  # Pydantic validates automatically
    # ...
```

---

## Rate Limiting (anti-abuse)

```python
import redis.asyncio as aioredis

async def rate_limit(key: str, max_requests: int, window_seconds: int):
    """Token bucket via Redis."""
    count = await redis.incr(f"rl:{key}")
    if count == 1:
        await redis.expire(f"rl:{key}", window_seconds)
    if count > max_requests:
        raise HTTPException(429, "Rate limit exceeded")

# Per IP
await rate_limit(f"ip:{request.client.host}", 100, 60)   # 100 req/min per IP

# Per user
await rate_limit(f"user:{user_id}", 60, 60)              # 60 req/min per user

# Per endpoint
await rate_limit(f"endpoint:/login", 10, 60)             # 10/min global to /login
```

---

## DDoS Protection

```
Layers:
─────
1. Cloudflare/Fastly (anycast network absorbs attacks)
2. WAF (filter known patterns)
3. Rate limiting (per IP, per user)
4. Connection limits (kernel: net.core.somaxconn)
5. CAPTCHA on suspicious patterns
6. Auto-scaling (absorb legit traffic spikes)
```

**At application layer:**
- Bot detection (fingerprinting, behavior analysis)
- Captcha challenges (Cloudflare Turnstile, hCaptcha)
- IP reputation lists

---

## Session Management

```python
# Session ID storage
session_id = secrets.token_urlsafe(32)  # 256 bits
await redis.setex(f"session:{session_id}", 3600, json.dumps({
    "user_id": user.id,
    "ip": request.client.host,
    "user_agent": request.headers["user-agent"],
}))

# Cookie settings
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,        # JS can't access
    secure=True,          # HTTPS only
    samesite="lax",       # CSRF protection
    max_age=3600,
)
```

**Best practices:**
- Regenerate session ID on privilege change (after login)
- Invalidate on logout
- Idle timeout (15-30 min)
- Absolute timeout (8-24 hours)
- Detect anomalies (IP change, geolocation jump)

---

## CSRF (Cross-Site Request Forgery)

```python
# Attack: malicious site triggers actions on your app via user's session

# Defense 1: SameSite cookies
response.set_cookie("session_id", value, samesite="strict")

# Defense 2: CSRF tokens (legacy)
csrf_token = secrets.token_urlsafe(32)
# Render in form: <input name="csrf" value="..."/>
# Verify on server: token in form == token in session

# Defense 3: Custom header (modern SPAs)
# Server requires header like X-Requested-With: XMLHttpRequest
# Cross-site can't set custom headers
```

---

## XSS (Cross-Site Scripting)

```python
# Attack: inject JS into page → executes in victim's browser → steal session

# Defense 1: Output encoding
from html import escape
html_safe = escape(user_input)  # < becomes &lt;

# Defense 2: Content Security Policy
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'sha256-...'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "frame-ancestors 'none';"
)

# Defense 3: HTTPOnly cookies (JS can't read session)
response.set_cookie("session", value, httponly=True)
```

---

## SQL Injection

```python
# BAD — string interpolation
query = f"SELECT * FROM users WHERE email = '{email}'"
# Attacker provides: ' OR 1=1 --

# GOOD — parameterized
await db.execute("SELECT * FROM users WHERE email = :email", {"email": email})

# GOOD — ORM
user = await session.query(User).filter(User.email == email).first()
```

---

## Secrets Management

```
❌ BAD:
- Hardcoded in code
- In Git repo (.env committed)
- In environment vars (visible in /proc)
- Plain text in CI logs

✅ GOOD:
- AWS Secrets Manager / HashiCorp Vault
- Kubernetes Secrets (with encryption at rest)
- 1Password / LastPass for dev
- Auto-rotation
```

```python
# AWS Secrets Manager
import boto3

client = boto3.client("secretsmanager")
response = client.get_secret_value(SecretId="prod/db/credentials")
db_password = json.loads(response["SecretString"])["password"]

# HashiCorp Vault
import hvac
vault = hvac.Client(url="https://vault.acme.com", token=...)
secret = vault.secrets.kv.v2.read_secret_version(path="db")["data"]["data"]
```

---

## Audit Logging

```python
async def audit(actor, action, resource, result, metadata=None):
    await db.execute("""
        INSERT INTO audit_log (actor_id, action, resource, result, metadata, timestamp, ip)
        VALUES (:actor, :action, :resource, :result, :meta, NOW(), :ip)
    """, {
        "actor": actor.id if actor else None,
        "action": action,
        "resource": resource,
        "result": result,
        "meta": json.dumps(metadata or {}),
        "ip": current_request_ip(),
    })

# Use on sensitive actions
@app.post("/admin/users/{id}/delete")
async def delete_user(id: int, admin: User = Depends(get_admin)):
    await db.execute("DELETE FROM users WHERE id = :id", {"id": id})
    await audit(admin, "delete_user", f"user:{id}", "success")
```

**Audit log requirements:**
- Immutable (append-only; separate DB or S3)
- Includes: actor, action, resource, timestamp, IP, result
- Retention per compliance (SOC2: 1 year, HIPAA: 6 years)
- Tamper-evident (HMAC or blockchain in extreme cases)

---

## Network Security

### VPC / Private Networks

```
Public subnet:                Private subnet:
- Load balancers              - App servers
- NAT gateway                 - Databases
- Bastion host                - Caches
                              - Internal queues
```

### Security Groups (AWS) / Firewall Rules

```yaml
# Allow only what's needed
app_server_sg:
  ingress:
    - port: 8000
      source: lb_sg                # only from load balancer
  egress:
    - port: 5432
      destination: db_sg            # to DB
    - port: 443
      destination: 0.0.0.0/0       # HTTPS out for APIs
```

### Zero-Trust Architecture

```
Old model (perimeter):
- VPN/firewall = trusted boundary
- Inside = trusted
- Outside = untrusted

Zero-trust:
- No implicit trust
- Verify every request (auth + authz)
- Encrypt everywhere (mTLS internal)
- Least privilege
```

**Implementation:**
- **SPIFFE/SPIRE** for service identity
- **mTLS** between services
- **Service mesh** (Istio, Linkerd) enforces policy

---

## Container & Cloud Security

```
Container:
- Don't run as root
- Read-only file system
- Minimal base image (distroless, alpine)
- Scan for CVEs (Trivy, Grype)
- Sign images (cosign)

Cloud:
- IAM least-privilege
- No long-lived credentials
- Use IAM roles (not access keys)
- S3 buckets private by default
- Disable public ECR/GCR images
- Enable CloudTrail / Audit Logs
```

---

## Compliance Quick Reference

| Standard | Domain | Key requirements |
|---|---|---|
| **GDPR** (EU) | Personal data | Consent, right to erasure, breach notification 72h |
| **DPDP** (India 2023) | Personal data | Similar to GDPR, ₹250 cr penalty |
| **CCPA** (California) | Personal data | Right to know, delete, opt-out |
| **HIPAA** (US) | Healthcare | BAA, audit logs 6yr, encryption |
| **PCI-DSS** | Payment cards | Tokenize CC, segment network, quarterly scans |
| **SOC 2 Type II** | SaaS | 12-month audit, control documentation |
| **ISO 27001** | InfoSec | Risk management, policies, audits |

---

## Security Testing

### SAST (Static)
- **Bandit** (Python)
- **Semgrep** (multi-language with rules)
- **SonarQube** (commercial)
- Scan in CI/CD

### DAST (Dynamic)
- **OWASP ZAP**
- **Burp Suite**
- Scan deployed app

### Dependency Scanning
- **pip-audit, Safety** (Python)
- **OSV-Scanner** (multi-language)
- **Snyk, Dependabot**

### Penetration Testing
- Annual external pen test
- Internal red team exercises
- Bug bounty (HackerOne, Bugcrowd)

(See [01_Year3-4_Mid/03_Security/16_sast_dast_supply_chain.md](../../../../01_Year3-4_Mid/03_Security/16_sast_dast_supply_chain.md))

---

## Incident Response Plan

```
1. Detection (monitoring catches anomaly)
2. Triage (severity, scope)
3. Containment (isolate affected systems)
4. Eradication (remove cause)
5. Recovery (restore systems)
6. Lessons learned (postmortem)

Roles:
- Incident commander
- Technical lead
- Communications (customers, regulators)
- Legal / compliance
- Forensics
```

**Breach notification:**
- GDPR: 72 hours to authority + affected users
- DPDP: "as soon as possible"
- CCPA: notify users without unreasonable delay

---

## Interview Q&A

### Q: How do you store passwords securely?

**Answer:**
- Use bcrypt or argon2 (NOT MD5/SHA1)
- Cost factor 12+
- Salt automatically included
- Never log raw passwords
- HTTPS for transmission
- Never expose hashes in API responses

### Q: JWT vs Session — which is better?

**Answer:** Depends.

| Aspect | JWT | Session |
|---|---|---|
| Storage | Client | Server (Redis/DB) |
| Scaling | Stateless ✅ | Needs shared store |
| Revocation | Hard | Easy |
| Size | Larger (~1KB) | Smaller (32 bytes) |
| Mobile-friendly | ✅ | Need cookies |

**Choose JWT for:** APIs, microservices, mobile, stateless scale
**Choose session for:** Traditional web apps, when revocation matters

**Common hybrid:** Short JWT access (15min) + long refresh token + revocation list

### Q: How do you prevent SQL injection?

**Answer:**
1. **Parameterized queries** (PRIMARY defense)
2. **ORM** (automatically parameterized)
3. **Input validation** (whitelist, type checks)
4. **Least privilege** DB user
5. **WAF** as backup layer

NEVER concatenate user input into SQL.

### Q: How do you secure secrets in CI/CD?

**Answer:**
- Use CI's secret store (GitHub Secrets, GitLab CI variables)
- For production: pull from Vault/Secrets Manager at runtime
- Never echo secrets in logs (`set +x`)
- Rotate regularly
- Audit access
- Use OIDC for cloud auth (no long-lived keys)

### Q: How do you protect against DDoS?

**Answer:** Layered:
1. **CDN** (Cloudflare/Akamai) — absorbs volumetric attacks
2. **WAF** — filters bad patterns
3. **Rate limiting** — per-IP, per-user
4. **Captcha** — for suspicious traffic
5. **Auto-scaling** — absorb spikes
6. **Network ACLs** — block known bad IPs
7. **Bot detection** — fingerprinting

---

## Cheat Sheet

```
✅ Always:
- HTTPS (TLS 1.3)
- Parameterized SQL
- Hash passwords (bcrypt)
- Validate input (Pydantic)
- Rate limit auth endpoints
- Audit log sensitive ops
- Encrypt PII at rest
- MFA for admin
- Keep dependencies updated
- Threat model new features

❌ Never:
- Commit secrets to git
- Use MD5/SHA1 for passwords
- Trust client-side validation alone
- eval() user input
- Use HTTP for sensitive data
- Disable TLS verification
- Run as root in containers
- Use default credentials
- Log passwords/tokens
- Auto-deserialize untrusted data
```

---

## Related Docs
- [24_Authentication_vs_Authorization.md](../24_Authentication_vs_Authorization.md)
- [25_Basic_Authentication.md](../25_Basic_Authentication.md)
- [26_Token_Based_Authentication.md](../26_Token_Based_Authentication.md)
- [27_OAuth_Authentication.md](../27_OAuth_Authentication.md)
- [36_RBAC_Design.md](../36_RBAC_Design.md)
- [01_Year3-4_Mid/03_Security/](../../../../01_Year3-4_Mid/03_Security) — 17 detailed docs
- [01_Year3-4_Mid/03_Security/17_india_dpdp_compliance.md](../../../../01_Year3-4_Mid/03_Security/17_india_dpdp_compliance.md) — India compliance
