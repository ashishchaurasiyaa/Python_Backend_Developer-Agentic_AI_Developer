# Lecture 5 — Practical Hands-On: Real-World Security Scenarios

> **Theory file:** [05_Real_World_Security_OWASP.md](05_Real_World_Security_OWASP.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Defenses against each OWASP Top 10 risk:

1. ✅ **A01 — Broken Access Control** — BOLA + RBAC + audit
2. ✅ **A02 — Cryptographic Failures** — Argon2, AES-GCM, TLS
3. ✅ **A03 — Injection** — parameterized queries, ORM, validation
4. ✅ **A04 — Insecure Design** — threat model template
5. ✅ **A05 — Misconfig** — security headers, IaC scanning
6. ✅ **A06 — Vulnerable Components** — Dependabot, SBOM
7. ✅ **A07 — Auth Failures** — MFA, rate limit, HIBP check
8. ✅ **A08 — Integrity Failures** — code signing, lockfiles
9. ✅ **A09 — Logging Failures** — structured logs + SIEM
10. ✅ **A10 — SSRF** — URL validator + network policies

By end: aap **all OWASP Top 10** mitigations ko implement kar sakte ho.

---

## 1. Project Structure

```
owasp_defenses_demo/
├── README.md
├── docker-compose.yml
│
├── a01_access_control/
│   ├── bola_prevention.py
│   ├── rbac_enforcement.py
│   └── tests.py
│
├── a02_crypto/
│   ├── password_hashing.py
│   ├── encryption.py
│   └── tls_config.py
│
├── a03_injection/
│   ├── sql_safe_queries.py
│   ├── input_validation.py
│   └── xxe_prevention.py
│
├── a04_insecure_design/
│   ├── threat_model_template.md
│   └── rate_limiting.py
│
├── a05_misconfig/
│   ├── security_headers.py
│   ├── iac_scanning.yml
│   └── error_handling.py
│
├── a06_components/
│   ├── dependency_management.txt
│   ├── sbom_generation.sh
│   └── auto_patching.yml
│
├── a07_auth/
│   ├── strong_passwords.py
│   ├── mfa_required.py
│   └── breach_check.py
│
├── a08_integrity/
│   ├── code_signing.sh
│   ├── package_verification.py
│   └── deserialization_safe.py
│
├── a09_logging/
│   ├── audit_logger.py
│   ├── correlation_id.py
│   └── siem_integration.py
│
└── a10_ssrf/
    ├── url_validator.py
    └── network_policies.yaml
```

---

## 2. 🔓 A01: Preventing Broken Access Control

### `a01_access_control/bola_prevention.py`

```python
"""
BOLA (Broken Object Level Authorization) prevention.
"""
from fastapi import FastAPI, HTTPException, Depends
from functools import wraps
from typing import Callable, Awaitable

app = FastAPI()

# ─────────────────────────────────────────────────────────────
# PATTERN 1: Object ownership check
# ─────────────────────────────────────────────────────────────
async def get_order_with_ownership_check(order_id: str, user_id: int):
    """Get order ONLY if user owns it (or is admin)"""
    order = await db.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
    
    if not order:
        # Don't reveal existence!
        raise HTTPException(404, "Order not found")
    
    # ── BOLA CHECK ──
    if order["user_id"] != user_id and not is_admin(user_id):
        # Same 404 for both not-found and unauthorized
        # (prevents enumeration attacks)
        raise HTTPException(404, "Order not found")
    
    return order

# ─────────────────────────────────────────────────────────────
# PATTERN 2: Decorator for resource ownership
# ─────────────────────────────────────────────────────────────
def require_ownership(get_resource_owner_id: Callable):
    """Decorator enforcing resource ownership"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: dict = Depends(get_current_user), **kwargs):
            resource_owner_id = await get_resource_owner_id(*args, **kwargs)
            
            if resource_owner_id is None:
                raise HTTPException(404, "Resource not found")
            
            if resource_owner_id != user["id"] and not user.get("is_admin"):
                # Don't leak existence
                raise HTTPException(404, "Resource not found")
            
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage
async def get_order_owner(order_id: str):
    return await db.fetchval("SELECT user_id FROM orders WHERE id = $1", order_id)

@app.get("/orders/{order_id}")
@require_ownership(get_order_owner)
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    return await db.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)

# ─────────────────────────────────────────────────────────────
# PATTERN 3: Tenant isolation (multi-tenant SaaS)
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def tenant_isolation(request, call_next):
    """Ensure user can only access their tenant's data"""
    user = await get_current_user_from_request(request)
    request.state.user = user
    request.state.tenant_id = user.tenant_id
    
    response = await call_next(request)
    return response

# All queries automatically filter by tenant
async def get_user_data(user_id: int, tenant_id: int):
    return await db.fetchrow(
        "SELECT * FROM users WHERE id = $1 AND tenant_id = $2",
        user_id, tenant_id  # ← MUST include tenant_id!
    )
```

### Audit Log All Access Decisions

```python
"""Track every access decision for forensics"""
import structlog

audit_log = structlog.get_logger("access_audit")

async def log_access_decision(
    user_id: int,
    resource_type: str,
    resource_id: str,
    action: str,
    decision: str,  # ALLOWED, DENIED
    reason: str = None,
):
    audit_log.info(
        "access_decision",
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        decision=decision,
        reason=reason,
    )
```

---

## 3. 🔐 A02: Strong Cryptography

### `a02_crypto/password_hashing.py`

```python
"""
Password hashing with Argon2id (most modern, recommended by OWASP).
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

# Use Argon2id (best balance of resistance to GPU + side-channel attacks)
ph = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # 64 MiB memory
    parallelism=4,      # Number of threads
    hash_len=32,        # Output length
    salt_len=16,        # Salt length
)

def hash_password(password: str) -> str:
    """Hash password, return string suitable for storage"""
    if len(password) < 8:
        raise ValueError("Password too short (minimum 8 chars)")
    
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        ph.verify(hashed, password)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False

def needs_rehash(hashed: str) -> bool:
    """Check if hash uses outdated parameters"""
    return ph.check_needs_rehash(hashed)

# Usage
password_hash = hash_password("my_secure_password_123")
print(f"Hash: {password_hash}")
# $argon2id$v=19$m=65536,t=3,p=4$...

# Login flow
def login(username: str, password: str):
    user = db.get_user(username)
    if not user or not verify_password(password, user.password_hash):
        # Generic error - don't reveal which is wrong
        raise ValueError("Invalid credentials")
    
    # Re-hash with newer params if needed (transparent upgrade)
    if needs_rehash(user.password_hash):
        new_hash = hash_password(password)
        db.update_password_hash(user.id, new_hash)
    
    return user
```

### `a02_crypto/encryption.py`

```python
"""
AES-256-GCM for symmetric encryption (authenticated encryption).
"""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

class SymmetricEncryption:
    """AES-256-GCM - encrypts AND authenticates"""
    
    def __init__(self, key: bytes = None):
        # 256-bit key (32 bytes)
        self.key = key or AESGCM.generate_key(bit_length=256)
        self.cipher = AESGCM(self.key)
    
    def encrypt(self, plaintext: bytes, associated_data: bytes = None) -> str:
        """
        Encrypt with random nonce.
        Returns base64(nonce || ciphertext || tag).
        """
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = self.cipher.encrypt(nonce, plaintext, associated_data)
        # Combine nonce + ciphertext (tag included in ciphertext by AESGCM)
        return base64.b64encode(nonce + ciphertext).decode()
    
    def decrypt(self, encrypted: str, associated_data: bytes = None) -> bytes:
        """Decrypt and verify integrity"""
        raw = base64.b64decode(encrypted)
        nonce = raw[:12]
        ciphertext = raw[12:]
        return self.cipher.decrypt(nonce, ciphertext, associated_data)

# Usage
crypto = SymmetricEncryption()

# Encrypt sensitive data with associated context
encrypted = crypto.encrypt(
    b"Secret information",
    associated_data=b"user_id=123"  # Authenticated but not encrypted
)

# Decrypt - will FAIL if context is different (tampering detection)
decrypted = crypto.decrypt(encrypted, associated_data=b"user_id=123")
```

### TLS Configuration

```python
"""
Modern TLS configuration.
"""
import ssl

def create_secure_ssl_context():
    """Create modern, secure SSL context"""
    context = ssl.create_default_context()
    
    # Only TLS 1.2 and 1.3
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Strong cipher suites only
    context.set_ciphers(
        "TLS_AES_256_GCM_SHA384:"
        "TLS_CHACHA20_POLY1305_SHA256:"
        "TLS_AES_128_GCM_SHA256:"
        "ECDHE-ECDSA-AES256-GCM-SHA384:"
        "ECDHE-RSA-AES256-GCM-SHA384:"
        "ECDHE-ECDSA-CHACHA20-POLY1305:"
        "ECDHE-RSA-CHACHA20-POLY1305"
    )
    
    # Require valid certificates
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Disable insecure renegotiation
    context.options |= ssl.OP_NO_RENEGOTIATION
    
    return context
```

---

## 4. 💉 A03: Preventing Injection

### `a03_injection/sql_safe_queries.py`

```python
"""
Safe database queries using parameterization.
"""
import asyncpg

# ─────────────────────────────────────────────────────────────
# RAW SQL (with proper parameterization)
# ─────────────────────────────────────────────────────────────
async def get_user_safe(conn: asyncpg.Connection, user_id: int):
    """SAFE - parameterized query"""
    return await conn.fetchrow(
        "SELECT * FROM users WHERE id = $1",
        user_id,  # ← passed as parameter, not concatenated!
    )

async def search_users_safe(conn: asyncpg.Connection, search_term: str):
    """SAFE - parameterized with LIKE"""
    return await conn.fetch(
        "SELECT * FROM users WHERE name ILIKE $1",
        f"%{search_term}%",  # ← escaped by driver
    )

# ─────────────────────────────────────────────────────────────
# ❌ UNSAFE EXAMPLES (DON'T DO THIS!)
# ─────────────────────────────────────────────────────────────
async def get_user_UNSAFE(conn, user_id):
    # ❌ SQL injection vulnerability!
    return await conn.fetchrow(f"SELECT * FROM users WHERE id = {user_id}")

async def search_UNSAFE(conn, term):
    # ❌ String concatenation = injection!
    query = "SELECT * FROM users WHERE name LIKE '%" + term + "%'"
    return await conn.fetch(query)

# ─────────────────────────────────────────────────────────────
# ORM (SQLAlchemy)
# ─────────────────────────────────────────────────────────────
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_user_with_orm(session: AsyncSession, user_id: int):
    """ORM handles parameterization automatically"""
    result = await session.execute(
        select(User).where(User.id == user_id)  # ← Safe by default
    )
    return result.scalar_one_or_none()
```

### Input Validation

```python
"""
Strict input validation with Pydantic.
"""
from pydantic import BaseModel, Field, constr, validator
from typing import Optional
import re

class SafeUserInput(BaseModel):
    """Strict schema prevents injection"""
    
    # Whitelist allowed characters
    username: constr(regex="^[a-zA-Z0-9_]{3,30}$")
    
    # Email validation
    email: constr(regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    
    # Numeric only
    age: int = Field(..., ge=0, le=150)
    
    # Limit length
    bio: Optional[constr(max_length=500)] = None
    
    @validator("bio")
    def no_sql_keywords(cls, v):
        if v is None:
            return v
        # Extra defense - reject if contains SQL keywords
        sql_patterns = ["select ", "drop ", "union ", "exec(", "--"]
        for pattern in sql_patterns:
            if pattern.lower() in v.lower():
                raise ValueError("Invalid characters in bio")
        return v
    
    class Config:
        # CRITICAL: don't accept extra fields (mass assignment protection)
        extra = "forbid"
```

### XXE Prevention

```python
"""
Safe XML parsing (XXE prevention).
"""
from defusedxml import ElementTree as SafeET  # Use defusedxml!

def parse_xml_safe(xml_string: str):
    """SAFE - prevents XXE attacks"""
    # defusedxml automatically disables:
    # - External entity expansion
    # - DTD processing
    # - Network access
    return SafeET.fromstring(xml_string)

# ❌ UNSAFE:
# import xml.etree.ElementTree as ET
# tree = ET.fromstring(user_input)  # Can be XXE'd!
```

---

## 5. 🏗️ A04: Threat Modeling Template

### `a04_insecure_design/threat_model_template.md`

```markdown
# Threat Model: [Feature Name]

## Overview
Brief description of the feature/system.

## Assets
What's worth protecting?
- User data
- Payment information
- API keys
- etc.

## Trust Boundaries
Map out where data crosses trust boundaries:
- Internet → API Gateway
- Public services → Internal services
- App → Database

## STRIDE Analysis

### Spoofing
**Threat:** [How could someone impersonate?]
**Mitigation:** [What prevents this?]

### Tampering
**Threat:** [How could data be modified?]
**Mitigation:** [What prevents this?]

### Repudiation
**Threat:** [Can someone deny actions?]
**Mitigation:** [Audit logs, signatures]

### Information Disclosure
**Threat:** [What sensitive info could leak?]
**Mitigation:** [Encryption, access control]

### Denial of Service
**Threat:** [How could service be disrupted?]
**Mitigation:** [Rate limiting, scaling]

### Elevation of Privilege
**Threat:** [How could user gain unauthorized access?]
**Mitigation:** [Strict authorization]

## Misuse Cases
What if someone misuses this?
- Abuse case 1: ...
- Abuse case 2: ...

## Defense in Depth
- Layer 1 (edge): WAF, rate limiting
- Layer 2 (API): Authentication, validation
- Layer 3 (logic): Authorization, business rules
- Layer 4 (data): Encryption, access control
- Layer 5 (monitoring): Logging, alerts

## Action Items
- [ ] Implement specific mitigation 1
- [ ] Add tests for misuse cases
- [ ] Set up monitoring for X
```

---

## 6. ⚙️ A05: Security Misconfiguration

### Security Headers Middleware

```python
"""
Essential security headers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

@app.middleware("http")
async def security_headers(request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # HTTPS enforcement
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self' https://api.example.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions policy
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "camera=(), "
        "microphone=(), "
        "payment=()"
    )
    
    # Remove server info
    response.headers["Server"] = "MyApp"  # Hide actual server
    
    return response

# Strict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com", "https://app.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)
```

### Generic Error Handling

```python
"""
Don't leak internal info in errors.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Generic 500 errors, detailed logging"""
    # Log full details internally
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    # Return GENERIC message to user
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred",
            "request_id": request.headers.get("X-Request-Id"),
        }
    )
```

### IaC Scanning

```yaml
# .github/workflows/iac-scan.yml
name: Infrastructure Security

on: [push, pull_request]

jobs:
  checkov:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: terraform/
          framework: terraform,kubernetes,dockerfile
          output_format: cli,sarif
          output_file_path: console,results.sarif
      
      - name: Upload to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: results.sarif
```

---

## 7. 📦 A06: Managing Vulnerable Components

### GitHub Dependabot

```yaml
# .github/dependabot.yml
version: 2

updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    
    # Auto-merge security patches
    target-branch: "develop"
    
    # Group minor updates
    groups:
      production-deps:
        patterns: ["*"]
        update-types: ["minor", "patch"]
  
  # Docker base images
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
  
  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
```

### Generate SBOM

```bash
#!/bin/bash
# generate_sbom.sh - Software Bill of Materials

# For Python projects
pip-licenses --format=json > sbom-python.json

# Or use Syft (universal)
syft packages dir:. -o cyclonedx-json > sbom.json

# Sign the SBOM
cosign sign-blob --key cosign.key sbom.json > sbom.json.sig

# Upload as artifact
echo "✓ SBOM generated: sbom.json (signed: sbom.json.sig)"
```

### Auto-Patch Critical Vulnerabilities

```python
"""
Snyk integration for vulnerability scanning.
"""
# .github/workflows/snyk.yml
"""
name: Snyk Security

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  push:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Snyk
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high --fail-on=upgradable
      
      - name: Auto-fix
        if: always()
        run: snyk fix
"""
```

---

## 8. 🔐 A07: Strong Authentication

### Password Strength + HIBP Check

```python
"""
Check passwords against known breaches (Have I Been Pwned).
"""
import hashlib
import httpx

async def is_password_compromised(password: str) -> bool:
    """
    Check if password appears in HIBP breach database.
    Uses k-anonymity (only sends first 5 chars of SHA-1).
    """
    # SHA-1 hash
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix = sha1[:5]
    suffix = sha1[5:]
    
    # Query HIBP API (only first 5 chars sent)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"User-Agent": "MyApp Security Check"},
        )
    
    if response.status_code != 200:
        return False  # API down, allow but log
    
    # Response: each line is "SUFFIX:COUNT"
    for line in response.text.splitlines():
        line_suffix, count = line.split(":")
        if line_suffix == suffix:
            # Found in breach!
            return True
    
    return False

# Usage in registration
async def register(username: str, password: str):
    if len(password) < 8:
        raise ValueError("Password too short")
    
    if await is_password_compromised(password):
        raise ValueError(
            "This password appears in known breaches. Please choose another."
        )
    
    # Hash and store
    hashed = hash_password(password)
    await db.create_user(username, hashed)
```

### Rate Limiting Login

```python
"""
Brute force protection.
"""
from collections import defaultdict
import time

class LoginRateLimiter:
    """Lockout after failed attempts"""
    
    def __init__(self):
        self.failures: dict[str, list] = defaultdict(list)
        self.locked_until: dict[str, float] = {}
    
    def is_locked(self, key: str) -> bool:
        """Check if account/IP is locked"""
        if key in self.locked_until:
            if time.time() < self.locked_until[key]:
                return True
            del self.locked_until[key]
        return False
    
    def record_failure(self, key: str):
        """Track failed login"""
        now = time.time()
        
        # Remove failures older than 15 minutes
        self.failures[key] = [
            t for t in self.failures[key] 
            if t > now - 900
        ]
        
        # Add current failure
        self.failures[key].append(now)
        
        # Lock after 5 failures in 15 minutes
        if len(self.failures[key]) >= 5:
            self.locked_until[key] = now + 1800  # 30 min lockout
    
    def record_success(self, key: str):
        """Clear failures on success"""
        self.failures.pop(key, None)
        self.locked_until.pop(key, None)

limiter = LoginRateLimiter()

@app.post("/login")
async def login(request: dict, http_request: Request):
    # Use both username AND IP for rate limiting
    username = request["username"]
    ip = http_request.client.host
    
    # Check both
    if limiter.is_locked(username) or limiter.is_locked(ip):
        raise HTTPException(429, "Account temporarily locked")
    
    user = await authenticate(username, request["password"])
    
    if not user:
        limiter.record_failure(username)
        limiter.record_failure(ip)
        raise HTTPException(401, "Invalid credentials")
    
    limiter.record_success(username)
    limiter.record_success(ip)
    
    # MFA check
    if user.mfa_enabled and not verify_mfa(user, request.get("mfa_code")):
        raise HTTPException(401, "Invalid MFA code")
    
    return generate_session(user)
```

---

## 9. 🔏 A08: Code Signing & Verification

### Sign Container Images with Cosign

```bash
#!/bin/bash
# sign-and-deploy.sh

# Generate key pair (do once)
# cosign generate-key-pair

# Build image
docker build -t myapp:1.0.0 .

# Push to registry
docker push myregistry/myapp:1.0.0

# Sign with private key
cosign sign --key cosign.key myregistry/myapp:1.0.0

# Now verify before deploying
cosign verify --key cosign.pub myregistry/myapp:1.0.0
```

### Verify Package Integrity

```python
"""
Verify package signatures before installing.
"""
import hashlib
import requests

def verify_package_hash(package_url: str, expected_sha256: str) -> bytes:
    """Download package and verify SHA-256"""
    response = requests.get(package_url)
    response.raise_for_status()
    
    actual_hash = hashlib.sha256(response.content).hexdigest()
    
    if actual_hash != expected_sha256:
        raise ValueError(
            f"Package hash mismatch! "
            f"Expected: {expected_sha256}, Got: {actual_hash}"
        )
    
    return response.content
```

### Safe Deserialization

```python
"""
Never deserialize untrusted data.
"""
import json
import pickle
from typing import Any

# ❌ DANGEROUS - can execute arbitrary code
def unsafe_deserialize(data: bytes) -> Any:
    return pickle.loads(data)  # RCE if data is malicious!

# ✅ SAFE - JSON only
def safe_deserialize(data: str) -> Any:
    """Use JSON for untrusted data"""
    return json.loads(data)

# ✅ SAFE - Pydantic for structured data
from pydantic import BaseModel

class OrderData(BaseModel):
    order_id: int
    amount: float

def safe_parse_order(data: str) -> OrderData:
    """Strict schema validation"""
    return OrderData.parse_raw(data)
```

---

## 10. 📊 A09: Security Logging

### `a09_logging/audit_logger.py`

```python
"""
Comprehensive security audit logging.
"""
import structlog
import json
from datetime import datetime
from typing import Optional
from enum import Enum
import hashlib
import hmac

class SecurityEventType(str, Enum):
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    PERMISSION_GRANTED = "auth.permission_granted"
    PERMISSION_DENIED = "auth.permission_denied"
    PASSWORD_CHANGE = "user.password_change"
    MFA_ENABLED = "user.mfa_enabled"
    MFA_DISABLED = "user.mfa_disabled"
    ACCOUNT_LOCKED = "user.account_locked"
    SENSITIVE_DATA_ACCESS = "data.sensitive_access"
    CONFIG_CHANGE = "system.config_change"
    SECURITY_ALERT = "security.alert"
    BREACH_INDICATOR = "security.breach_indicator"

class SecurityAuditLogger:
    """
    Tamper-evident security logger.
    Uses HMAC chain for tamper detection.
    """
    
    def __init__(self, hmac_key: bytes):
        self.logger = structlog.get_logger("security_audit")
        self.hmac_key = hmac_key
        self.last_hash = b""
    
    def log_event(
        self,
        event_type: SecurityEventType,
        user_id: Optional[int] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        outcome: str = "success",
        severity: str = "info",  # info, warning, error, critical
        details: dict = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log security event with tamper-evident chain"""
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "outcome": outcome,
            "severity": severity,
            "details": details or {},
            "client_ip": client_ip,
            "user_agent": user_agent,
        }
        
        # Create tamper-evident hash chain
        event_data = json.dumps(event, sort_keys=True).encode()
        event_hash = hmac.new(
            self.hmac_key,
            self.last_hash + event_data,
            hashlib.sha256
        ).hexdigest()
        
        event["chain_hash"] = event_hash
        event["prev_hash"] = self.last_hash.hex() if self.last_hash else None
        
        self.last_hash = event_hash.encode()
        
        # Log it
        log_method = {
            "info": self.logger.info,
            "warning": self.logger.warning,
            "error": self.logger.error,
            "critical": self.logger.critical,
        }.get(severity, self.logger.info)
        
        log_method("security_event", **event)

audit = SecurityAuditLogger(hmac_key=b"your-hmac-secret-from-vault")

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
# Failed login
audit.log_event(
    event_type=SecurityEventType.AUTH_FAILURE,
    user_id=None,
    outcome="failure",
    severity="warning",
    details={"reason": "invalid_password", "attempts": 3},
    client_ip="203.0.113.5",
)

# Sensitive operation
audit.log_event(
    event_type=SecurityEventType.SENSITIVE_DATA_ACCESS,
    user_id=123,
    resource="/api/admin/users",
    action="export_all_users",
    severity="warning",
    details={"rows_exported": 1000},
)

# Critical security event
audit.log_event(
    event_type=SecurityEventType.BREACH_INDICATOR,
    severity="critical",
    details={"description": "Refresh token reuse detected", "user_id": 456},
)
```

### Correlation IDs Across Services

```python
"""
Correlation IDs trace requests across distributed system.
"""
import uuid
from fastapi import FastAPI, Request
from contextvars import ContextVar

# Context variable - automatically passed through async calls
correlation_id_var: ContextVar[str] = ContextVar("correlation_id")

app = FastAPI()

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to every request"""
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    
    return response

# Now logs auto-include correlation ID
structlog.configure(
    processors=[
        # Add correlation ID to every log
        lambda _, __, event_dict: {
            **event_dict,
            "correlation_id": correlation_id_var.get(None),
        },
        structlog.processors.JSONRenderer(),
    ]
)

# When calling other services, forward the ID
async def call_other_service(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"X-Correlation-Id": correlation_id_var.get()}
        )
        return response.json()
```

---

## 11. 🌐 A10: SSRF Prevention

### `a10_ssrf/url_validator.py`

```python
"""
SSRF-safe URL validation.
"""
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional

class URLValidator:
    """Validate URLs to prevent SSRF"""
    
    BLOCKED_SCHEMES = {"file", "ftp", "gopher", "dict"}
    
    # AWS/cloud metadata services
    BLOCKED_HOSTS = {
        "169.254.169.254",  # AWS, OpenStack, Oracle
        "metadata.google.internal",  # GCP
        "metadata.azure.com",
    }
    
    def __init__(self, allowed_hosts: Optional[set[str]] = None):
        self.allowed_hosts = allowed_hosts
    
    def is_safe(self, url: str) -> bool:
        """Check if URL is safe to fetch"""
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        
        # Check scheme
        if parsed.scheme not in {"http", "https"}:
            return False
        
        if parsed.scheme in self.BLOCKED_SCHEMES:
            return False
        
        # Get hostname
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Check blocked hosts
        if hostname in self.BLOCKED_HOSTS:
            return False
        
        # Resolve all IPs for hostname
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            ips = {info[4][0] for info in addr_info}
        except socket.error:
            return False
        
        # Check ALL IPs (defends against DNS rebinding)
        for ip in ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
            except ValueError:
                continue
            
            # Block private/internal
            if ip_obj.is_private:
                return False
            if ip_obj.is_loopback:
                return False
            if ip_obj.is_link_local:
                return False
            if ip_obj.is_multicast:
                return False
            if ip_obj.is_reserved:
                return False
            if ip_obj.is_unspecified:
                return False
            
            # Block AWS metadata IP
            if ip == "169.254.169.254":
                return False
        
        # Allowlist check (if configured)
        if self.allowed_hosts:
            if hostname not in self.allowed_hosts:
                return False
        
        return True
    
    async def fetch_safe(self, url: str, timeout: float = 10.0) -> bytes:
        """Fetch URL with SSRF protections"""
        if not self.is_safe(url):
            raise ValueError(f"URL not allowed: {url}")
        
        import httpx
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,  # CRITICAL: don't follow redirects
            verify=True,  # Verify TLS
        ) as client:
            response = await client.get(url)
            
            # Check for redirect
            if response.status_code in [301, 302, 307, 308]:
                # Don't auto-follow - validate the new URL too
                new_url = response.headers.get("location")
                if new_url:
                    raise ValueError(f"Redirect to {new_url} blocked")
            
            return response.content

# Usage
validator = URLValidator(
    allowed_hosts={"api.partner.com", "cdn.example.com"}
)

@app.post("/import")
async def import_data(url: str):
    try:
        content = await validator.fetch_safe(url)
        return {"imported": len(content), "bytes": content[:100]}
    except ValueError as e:
        raise HTTPException(400, str(e))
```

### IMDSv2 (AWS Metadata Protection)

```yaml
# Use IMDSv2 - requires session token, mitigates SSRF
# In Terraform:
resource "aws_instance" "app" {
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # Force IMDSv2
    http_put_response_hop_limit = 1            # Prevent container access
  }
}
```

### Network Policies for SSRF Defense

```yaml
# k8s NetworkPolicy - block internal access
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: prevent-ssrf
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
  - Egress
  egress:
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  
  # Allow specific external destinations
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        # Block AWS metadata
        - 169.254.0.0/16
        # Block all private ranges
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
    ports:
    - protocol: TCP
      port: 443
```

---

## 12. Key Learnings Summary

```
✅ A01: Server-side authorization + BOLA checks
✅ A02: Argon2id, AES-GCM, TLS 1.2+
✅ A03: Parameterized queries, strict validation
✅ A04: Threat modeling template
✅ A05: Security headers + IaC scanning
✅ A06: Dependabot + SBOM
✅ A07: HIBP check + MFA + rate limiting
✅ A08: Code signing + safe deserialization
✅ A09: Audit logging + correlation IDs
✅ A10: URL validator + network policies

🎯 OWASP defense stack:
   - Pre-commit: secret scan + lint
   - CI: SAST + SCA + container scan
   - Pre-deploy: signed artifacts + IaC scan
   - Runtime: WAF + rate limit + auth + audit
   - Post-deploy: DAST + monitoring + incident response
```

---

## 🎬 Section Complete!

You've completed **Section 5: Security & Governance in Architecture**!

### Files Created

```
Section_05_Security_Governance/
├── 01_Security_Principles_Zero_Trust.md     (theory)
├── 01_Practical_Hands_On.md                  (practical)
├── 02_OAuth_OpenID_Connect.md                (theory)
├── 02_Practical_Hands_On.md                  (practical)
├── 03_API_Service_Security.md                (theory)
├── 03_Practical_Hands_On.md                  (practical)
├── 04_Secrets_Token_Management.md            (theory)
├── 04_Practical_Hands_On.md                  (practical)
├── 05_Real_World_Security_OWASP.md           (theory)
└── 05_Practical_Hands_On.md                  (practical)  ← you are here
```

### What You Can Now Build

```
✓ Zero Trust architecture with mTLS + identity-based access
✓ OAuth 2.0 + OpenID Connect with Keycloak/Auth0
✓ JWT validation with key rotation (JWKS)
✓ API security: API keys + rate limiting + BOLA prevention
✓ Secrets management with Vault + rotation
✓ Refresh token rotation with reuse detection
✓ OWASP Top 10 defenses across all layers
✓ Security audit logging with tamper-evident chains
✓ SSRF-safe URL fetching
✓ DevSecOps pipeline with all security gates
```

---

## 🚀 Next Steps

Continue with:
- **Section 6**: Event-Driven & Reactive Systems
- **Section 7**: Cloud-Native & Scalable Architecture
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

---

## 📚 Try It Yourself

1. Run **OWASP ZAP** against your application
2. Implement **WebAuthn** passwordless login
3. Add **fine-grained authorization** with OPA
4. Set up **SIEM integration** with ELK
5. Run a **purple team exercise** combining offense + defense
