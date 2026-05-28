# Lecture 1 — Practical Hands-On: Security Principles & Zero Trust

> **Theory file:** [01_Security_Principles_Zero_Trust.md](01_Security_Principles_Zero_Trust.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready security primitives:

1. ✅ **CIA implementation** — encryption, hashing, availability
2. ✅ **RBAC system** in FastAPI with decorators
3. ✅ **ABAC policies** with Open Policy Agent (OPA)
4. ✅ **MFA flow** — TOTP-based
5. ✅ **Threat model** with STRIDE for a real API
6. ✅ **Service-to-service mTLS** setup
7. ✅ **Network microsegmentation** with Kubernetes
8. ✅ **Audit logging** for compliance
9. ✅ **Defense in depth** stack
10. ✅ **DevSecOps** CI/CD pipeline

By end: aap **production-ready Zero Trust patterns** implement kar sakte ho.

---

## 1. Project Structure

```
zero_trust_demo/
├── docker-compose.yml
├── README.md
│
├── cia/
│   ├── encryption.py          # Confidentiality
│   ├── integrity.py            # Integrity (HMAC, signatures)
│   └── availability.py         # Rate limiting, health checks
│
├── rbac/
│   ├── models.py
│   ├── policies.py
│   └── decorators.py
│
├── abac/
│   ├── opa_policies/
│   │   └── policy.rego
│   ├── policy_engine.py
│   └── examples.py
│
├── mfa/
│   ├── totp.py
│   └── webauthn.py
│
├── threat_modeling/
│   ├── stride_example.md
│   └── dread_calculator.py
│
├── mtls/
│   ├── generate_certs.sh
│   ├── server.py
│   └── client.py
│
├── audit/
│   └── audit_logger.py
│
└── ci_cd/
    ├── .github/workflows/
    │   └── security.yml
    └── .pre-commit-config.yaml
```

---

## 2. Setup & Dependencies

```bash
pip install cryptography
pip install pyjwt[crypto]
pip install pyotp qrcode             # MFA
pip install fastapi uvicorn
pip install python-multipart
pip install httpx                    # mTLS client
pip install structlog                # Audit logging
```

---

## 3. 🔒 CIA Triad Implementation

### `cia/encryption.py` — Confidentiality

```python
"""
Confidentiality: encrypt sensitive data at rest and in transit.
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import base64

# ─────────────────────────────────────────────────────────────
# SYMMETRIC ENCRYPTION (Fernet - AES-128 in CBC mode)
# ─────────────────────────────────────────────────────────────
class FieldEncryption:
    """Encrypt specific fields (PII, payment info, etc.)"""
    
    def __init__(self, key: bytes = None):
        # In production: get from KMS/Vault, never hardcode!
        self.key = key or Fernet.generate_key()
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt and return base64-encoded ciphertext"""
        token = self.cipher.encrypt(plaintext.encode())
        return token.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt back to plaintext"""
        plaintext = self.cipher.decrypt(ciphertext.encode())
        return plaintext.decode()

# Usage
crypto = FieldEncryption()

# Store PII encrypted in DB
user_record = {
    "id": 123,
    "name": "Ashish Chaurasiya",
    "ssn_encrypted": crypto.encrypt("123-45-6789"),  # ← Sensitive!
    "phone_encrypted": crypto.encrypt("+91-9876543210"),
}

# Retrieve and decrypt only when needed
ssn = crypto.decrypt(user_record["ssn_encrypted"])

# ─────────────────────────────────────────────────────────────
# PASSWORD HASHING (One-way, NOT encryption!)
# ─────────────────────────────────────────────────────────────
import bcrypt

def hash_password(password: str) -> str:
    """Hash password with bcrypt (slow on purpose)"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())

# Never store plain passwords!
stored_hash = hash_password("user_password_123")
is_valid = verify_password("user_password_123", stored_hash)
```

### `cia/integrity.py` — Integrity

```python
"""
Integrity: ensure data hasn't been tampered with.
"""
import hmac
import hashlib
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

# ─────────────────────────────────────────────────────────────
# HMAC SIGNATURES (for API requests)
# ─────────────────────────────────────────────────────────────
class HMACSigner:
    """Sign API requests to prevent tampering"""
    
    def __init__(self, secret_key: bytes):
        self.secret = secret_key
    
    def sign(self, message: bytes) -> str:
        """Create HMAC-SHA256 signature"""
        signature = hmac.new(self.secret, message, hashlib.sha256).hexdigest()
        return signature
    
    def verify(self, message: bytes, signature: str) -> bool:
        """Verify HMAC matches"""
        expected = self.sign(message)
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected, signature)

# Usage in webhook receiver
signer = HMACSigner(b"shared-secret")

def verify_webhook(payload: bytes, signature_header: str) -> bool:
    """Verify webhook hasn't been tampered with"""
    return signer.verify(payload, signature_header)

# ─────────────────────────────────────────────────────────────
# DIGITAL SIGNATURES (asymmetric)
# ─────────────────────────────────────────────────────────────
class DocumentSigner:
    """Sign documents with private key"""
    
    def __init__(self):
        # In production: load from secure storage
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
    
    def sign(self, document: bytes) -> bytes:
        return self.private_key.sign(
            document,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    
    def verify(self, document: bytes, signature: bytes) -> bool:
        try:
            self.public_key.verify(
                signature,
                document,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
```

### `cia/availability.py` — Availability

```python
"""
Availability: keep systems running under attack/load.
"""
from fastapi import FastAPI, Request, HTTPException
from collections import defaultdict, deque
import time

app = FastAPI()

# ─────────────────────────────────────────────────────────────
# RATE LIMITING (protect against DoS)
# ─────────────────────────────────────────────────────────────
class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(deque)
    
    def check(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        
        # Remove old requests
        while self.requests[key] and self.requests[key][0] < cutoff:
            self.requests[key].popleft()
        
        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        self.requests[key].append(now)
        return True

limiter = RateLimiter(max_requests=100, window_seconds=60)

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client_ip = request.client.host
    if not limiter.check(client_ip):
        raise HTTPException(429, "Rate limit exceeded")
    return await call_next(request)

# ─────────────────────────────────────────────────────────────
# HEALTH CHECKS
# ─────────────────────────────────────────────────────────────
@app.get("/health/live")
def liveness():
    """Is the app alive? (basic check)"""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """Is the app ready to serve traffic?"""
    # Check dependencies
    db_ok = await check_database()
    redis_ok = await check_redis()
    
    if not (db_ok and redis_ok):
        raise HTTPException(503, "Not ready")
    
    return {"status": "ready", "db": db_ok, "redis": redis_ok}
```

---

## 4. 🔑 RBAC Implementation

### `rbac/models.py`

```python
"""Role-Based Access Control models"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Set, List

class Permission(str, Enum):
    # Resource: Orders
    ORDER_READ = "order:read"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"
    ORDER_DELETE = "order:delete"
    
    # Resource: Users
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # Admin
    ADMIN_FULL = "admin:*"

@dataclass
class Role:
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    
    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions or Permission.ADMIN_FULL in self.permissions

@dataclass
class User:
    id: int
    username: str
    roles: List[Role] = field(default_factory=list)
    
    def has_permission(self, perm: Permission) -> bool:
        return any(role.has_permission(perm) for role in self.roles)

# Define roles
VIEWER = Role(
    name="viewer",
    permissions={Permission.ORDER_READ, Permission.USER_READ}
)

EDITOR = Role(
    name="editor",
    permissions={
        Permission.ORDER_READ, Permission.ORDER_CREATE, Permission.ORDER_UPDATE,
        Permission.USER_READ,
    }
)

ADMIN = Role(
    name="admin",
    permissions={Permission.ADMIN_FULL}
)
```

### `rbac/decorators.py`

```python
"""Decorators to enforce RBAC"""
from functools import wraps
from fastapi import Depends, HTTPException
from .models import User, Permission

def require_permission(permission: Permission):
    """Decorator: require user to have permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = Depends(get_current_user), **kwargs):
            if not user.has_permission(permission):
                raise HTTPException(403, f"Missing permission: {permission}")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

def require_any(*permissions: Permission):
    """Require ANY of the permissions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User = Depends(get_current_user), **kwargs):
            if not any(user.has_permission(p) for p in permissions):
                raise HTTPException(403, "Insufficient permissions")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage
@app.delete("/orders/{order_id}")
@require_permission(Permission.ORDER_DELETE)
async def delete_order(order_id: str, user: User = Depends(get_current_user)):
    # Only users with ORDER_DELETE permission reach here
    return {"deleted": order_id}

@app.get("/admin/users")
@require_permission(Permission.ADMIN_FULL)
async def admin_list_users(user: User = Depends(get_current_user)):
    return {"users": [...]}
```

---

## 5. 🎯 ABAC with Open Policy Agent (OPA)

### `abac/opa_policies/policy.rego`

```rego
# OPA policy in Rego language
package authz

import future.keywords.if
import future.keywords.in

default allow = false

# Allow if user is admin
allow if {
    "admin" in input.user.roles
}

# Allow user to read their own resources
allow if {
    input.action == "read"
    input.resource.owner == input.user.id
}

# Allow finance department to read all orders
allow if {
    input.user.department == "finance"
    input.action == "read"
    input.resource.type == "order"
}

# Time-based: only allow access during work hours
allow if {
    input.action == "read"
    is_work_hours
}

is_work_hours if {
    hour := time.clock([time.now_ns(), "Asia/Kolkata"])[0]
    hour >= 9
    hour < 18
}

# Location-based: deny access from blocked countries
deny if {
    input.context.country in ["XX", "YY"]
}
```

### `abac/policy_engine.py`

```python
"""Python wrapper for OPA policy evaluation"""
import httpx
from typing import Any

class OPAClient:
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
    
    async def evaluate(self, policy: str, input_data: dict) -> bool:
        """Evaluate policy with given input"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.opa_url}/v1/data/{policy}/allow",
                json={"input": input_data}
            )
            result = response.json()
            return result.get("result", False)

opa = OPAClient()

# Usage
async def check_access(user, action, resource, context):
    """Use OPA to make access decision"""
    allowed = await opa.evaluate("authz", {
        "user": {
            "id": user.id,
            "roles": [r.name for r in user.roles],
            "department": user.department,
        },
        "action": action,
        "resource": {
            "type": resource.type,
            "owner": resource.owner,
        },
        "context": {
            "country": context.get("country"),
            "ip": context.get("ip"),
        }
    })
    return allowed
```

---

## 6. 📱 Multi-Factor Authentication (MFA)

### `mfa/totp.py`

```python
"""
Time-based One-Time Password (TOTP) implementation.
Works with Google Authenticator, Authy, etc.
"""
import pyotp
import qrcode
import io
import base64
from fastapi import FastAPI, HTTPException

app = FastAPI()

# In production: store in DB per user
USER_SECRETS = {}

@app.post("/mfa/setup/{user_id}")
def setup_mfa(user_id: int):
    """
    Generate secret + QR code for user to scan.
    """
    # Generate random secret
    secret = pyotp.random_base32()
    USER_SECRETS[user_id] = secret
    
    # Create provisioning URI for authenticator apps
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=f"user{user_id}@example.com",
        issuer_name="MyApp"
    )
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for inline display
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return {
        "secret": secret,  # Show once, never again!
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "manual_entry": secret,  # If QR can't be scanned
    }

@app.post("/mfa/verify/{user_id}")
def verify_mfa(user_id: int, code: str):
    """Verify TOTP code from user's authenticator"""
    if user_id not in USER_SECRETS:
        raise HTTPException(400, "MFA not set up")
    
    secret = USER_SECRETS[user_id]
    totp = pyotp.TOTP(secret)
    
    # Allow 1 step of clock drift (30s before/after)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(401, "Invalid MFA code")
    
    return {"verified": True}

# ─────────────────────────────────────────────────────────────
# COMBINED LOGIN + MFA FLOW
# ─────────────────────────────────────────────────────────────
@app.post("/login")
async def login(username: str, password: str, mfa_code: str = None):
    user = await authenticate(username, password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    if user.mfa_enabled:
        if not mfa_code:
            raise HTTPException(400, "MFA code required")
        
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(mfa_code, valid_window=1):
            raise HTTPException(401, "Invalid MFA code")
    
    # Generate session token
    return {"token": generate_jwt(user)}
```

---

## 7. 🎯 STRIDE Threat Modeling

### `threat_modeling/stride_example.md`

```markdown
# STRIDE Threat Model: Payment API

## Asset
User payment information (cards, bank details)

## Entry Points
1. POST /api/payments (web/mobile clients)
2. Webhook from payment gateway
3. Admin API for refunds

## STRIDE Analysis

### S - Spoofing
**Threat:** Attacker impersonates legitimate user
**Mitigation:**
- Strong authentication (JWT with short TTL)
- MFA for sensitive operations
- Mutual TLS for service-to-service
- API key + IP allowlist for admin API

### T - Tampering
**Threat:** Modify payment amount in transit
**Mitigation:**
- HTTPS everywhere
- HMAC signature on all requests
- Server-side amount validation (client cannot dictate)
- Audit log of all changes

### R - Repudiation
**Threat:** User denies making a payment
**Mitigation:**
- Comprehensive audit log
- Digital signature on transactions
- Time-stamped immutable records
- Email + SMS confirmation

### I - Information Disclosure
**Threat:** Leak card numbers, transaction history
**Mitigation:**
- PCI-DSS compliance
- Tokenization (never store raw card)
- Encryption at rest (AES-256)
- TLS 1.3+ in transit
- Mask in logs and UI

### D - Denial of Service
**Threat:** Flood API to disrupt service
**Mitigation:**
- Rate limiting per IP and per user
- CAPTCHAs for repeat failures
- WAF rules
- Auto-scaling
- Circuit breakers on downstream

### E - Elevation of Privilege
**Threat:** Regular user gains admin access
**Mitigation:**
- RBAC strictly enforced
- Server-side permission checks (never trust client)
- JWT signature verification
- Separation of admin endpoints
- Just-in-time admin access

## DREAD Scoring (1-10 each)

| Threat | D | R | E | A | D | Total |
|--------|---|---|---|---|---|-------|
| Spoofing | 9 | 8 | 6 | 9 | 7 | 39 (HIGH) |
| Information Disclosure | 10 | 7 | 5 | 10 | 8 | 40 (HIGH) |
| Tampering | 8 | 5 | 7 | 7 | 5 | 32 (MED) |
| DoS | 6 | 9 | 8 | 7 | 9 | 39 (HIGH) |
| Repudiation | 5 | 4 | 3 | 4 | 3 | 19 (LOW) |
| Privilege Escalation | 10 | 6 | 5 | 10 | 6 | 37 (HIGH) |

## Priority Actions
1. **HIGH:** Implement MFA, tokenization, rate limiting
2. **MEDIUM:** HMAC signatures, comprehensive audit log
3. **LOW:** Continue improvements based on monitoring
```

### `threat_modeling/dread_calculator.py`

```python
"""Programmatic DREAD scoring"""
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Threat:
    name: str
    damage: int          # 1-10
    reproducibility: int # 1-10
    exploitability: int  # 1-10
    affected_users: int  # 1-10
    discoverability: int # 1-10
    
    @property
    def total(self) -> int:
        return (self.damage + self.reproducibility + self.exploitability + 
                self.affected_users + self.discoverability)
    
    @property
    def severity(self) -> Severity:
        score = self.total
        if score >= 40:
            return Severity.CRITICAL
        elif score >= 30:
            return Severity.HIGH
        elif score >= 20:
            return Severity.MEDIUM
        else:
            return Severity.LOW

# Example
spoofing = Threat(
    name="Spoofing user identity",
    damage=9,
    reproducibility=8,
    exploitability=6,
    affected_users=9,
    discoverability=7,
)

print(f"{spoofing.name}: {spoofing.total} ({spoofing.severity.value})")
# Spoofing user identity: 39 (HIGH)
```

---

## 8. 🔐 Mutual TLS (mTLS)

### `mtls/generate_certs.sh`

```bash
#!/bin/bash
# Generate certificates for mTLS testing

# 1. Create CA (Certificate Authority)
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 365 -key ca-key.pem -out ca-cert.pem \
    -subj "/C=IN/ST=KA/O=MyCompany/CN=MyCA"

# 2. Generate server certificate
openssl genrsa -out server-key.pem 4096
openssl req -new -key server-key.pem -out server-csr.pem \
    -subj "/C=IN/ST=KA/O=MyCompany/CN=my-server"
openssl x509 -req -days 365 -in server-csr.pem \
    -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
    -out server-cert.pem

# 3. Generate client certificate
openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client-csr.pem \
    -subj "/C=IN/ST=KA/O=MyCompany/CN=my-client"
openssl x509 -req -days 365 -in client-csr.pem \
    -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
    -out client-cert.pem

echo "✓ Certificates generated:"
echo "  CA: ca-cert.pem"
echo "  Server: server-cert.pem + server-key.pem"
echo "  Client: client-cert.pem + client-key.pem"
```

### `mtls/server.py`

```python
"""HTTPS server requiring client certificates (mTLS)"""
import ssl
import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/secure")
def secure_endpoint(request: Request):
    """Only accessible with valid client cert"""
    # Get client cert from request
    client_cert = request.scope.get("client_cert")
    return {
        "message": "Access granted",
        "client_subject": client_cert.get("subject") if client_cert else None,
    }

if __name__ == "__main__":
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain("server-cert.pem", "server-key.pem")
    ssl_context.load_verify_locations(cafile="ca-cert.pem")
    ssl_context.verify_mode = ssl.CERT_REQUIRED  # Require client cert!
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_certfile="server-cert.pem",
        ssl_keyfile="server-key.pem",
        ssl_ca_certs="ca-cert.pem",
        ssl_cert_reqs=ssl.CERT_REQUIRED,
    )
```

### `mtls/client.py`

```python
"""Client that presents certificate"""
import httpx
import asyncio

async def call_mtls_endpoint():
    async with httpx.AsyncClient(
        verify="ca-cert.pem",  # Trust the CA
        cert=("client-cert.pem", "client-key.pem"),  # Present our cert
    ) as client:
        response = await client.get("https://localhost:8443/secure")
        print(response.json())

asyncio.run(call_mtls_endpoint())
```

---

## 9. 🛡 Kubernetes Network Microsegmentation

### `k8s/network-policies.yaml`

```yaml
# Default deny all traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress

---
# Allow web tier → API tier only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-from-web
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: web
    ports:
    - protocol: TCP
      port: 8000

---
# Allow API → Database only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-from-api
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: api
    ports:
    - protocol: TCP
      port: 5432

---
# Block all egress except specific destinations
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: production
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 169.254.169.254/32  # Block metadata service (SSRF prevention!)
    ports:
    - protocol: TCP
      port: 443  # Only HTTPS outbound
```

---

## 10. 📝 Audit Logging

### `audit/audit_logger.py`

```python
"""
Comprehensive audit logging for compliance.
"""
import json
import structlog
from datetime import datetime
from typing import Any
from enum import Enum

class AuditEventType(str, Enum):
    LOGIN_SUCCESS = "login.success"
    LOGIN_FAILURE = "login.failure"
    PERMISSION_GRANTED = "auth.permission_granted"
    PERMISSION_DENIED = "auth.permission_denied"
    DATA_ACCESS = "data.access"
    DATA_MODIFICATION = "data.modification"
    SENSITIVE_OPERATION = "sensitive.operation"
    SECURITY_ALERT = "security.alert"

# Structured logger
logger = structlog.get_logger("audit")

class AuditLogger:
    """Tamper-evident audit logger"""
    
    def log(
        self,
        event_type: AuditEventType,
        user_id: int = None,
        resource: str = None,
        action: str = None,
        outcome: str = "success",
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log security-relevant event"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "outcome": outcome,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        
        # Log to structured logger (forwards to SIEM)
        logger.info("audit_event", **event)
        
        # In production: also write to append-only store
        # for tamper-evidence (e.g., AWS CloudTrail, immutable S3)

audit = AuditLogger()

# ─────────────────────────────────────────────────────────────
# USAGE EXAMPLES
# ─────────────────────────────────────────────────────────────

# Failed login attempt
audit.log(
    event_type=AuditEventType.LOGIN_FAILURE,
    user_id=None,
    action="login",
    outcome="failure",
    details={"reason": "invalid_password", "attempt": 3},
    ip_address="203.0.113.5",
    user_agent="Mozilla/5.0...",
)

# Sensitive operation
audit.log(
    event_type=AuditEventType.SENSITIVE_OPERATION,
    user_id=123,
    resource="/api/admin/users/456",
    action="delete_user",
    outcome="success",
    details={"deleted_user_id": 456, "reason": "GDPR request"},
)

# Permission denied
audit.log(
    event_type=AuditEventType.PERMISSION_DENIED,
    user_id=789,
    resource="/api/admin/billing",
    action="access",
    outcome="denied",
    details={"required_permission": "admin:billing", "user_roles": ["viewer"]},
)
```

---

## 11. 🚀 DevSecOps CI/CD Pipeline

### `.github/workflows/security.yml`

```yaml
name: Security Pipeline

on: [push, pull_request]

jobs:
  # ─────────────────────────────────────────────
  # 1. SECRET SCANNING
  # ─────────────────────────────────────────────
  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for secret scanning
      
      - name: TruffleHog Secret Scan
        uses: trufflesecurity/trufflehog@main
        with:
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified

  # ─────────────────────────────────────────────
  # 2. STATIC ANALYSIS (SAST)
  # ─────────────────────────────────────────────
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Bandit Python SAST
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
      
      - name: Semgrep Scan
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/owasp-top-ten

  # ─────────────────────────────────────────────
  # 3. DEPENDENCY SCAN (SCA)
  # ─────────────────────────────────────────────
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Snyk Scan
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high

  # ─────────────────────────────────────────────
  # 4. CONTAINER SCAN
  # ─────────────────────────────────────────────
  container-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
      
      - name: Trivy Container Scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'myapp:${{ github.sha }}'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
      
      - name: Upload to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'

  # ─────────────────────────────────────────────
  # 5. INFRASTRUCTURE AS CODE SCAN
  # ─────────────────────────────────────────────
  iac-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Checkov Terraform Scan
        uses: bridgecrewio/checkov-action@master
        with:
          directory: terraform/
          framework: terraform

  # ─────────────────────────────────────────────
  # 6. DAST (only on staging deployments)
  # ─────────────────────────────────────────────
  dast:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    needs: [secrets-scan, sast, dependency-scan, container-scan]
    steps:
      - name: Deploy to staging
        run: ./deploy-staging.sh
      
      - name: OWASP ZAP Scan
        uses: zaproxy/action-baseline@v0.7.0
        with:
          target: 'https://staging.example.com'
```

### `.pre-commit-config.yaml`

```yaml
repos:
  # Secret scanning
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
  
  # Python security
  - repo: https://github.com/PyCQA/bandit
    rev: '1.7.5'
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
  
  # General quality
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-added-large-files
```

---

## 12. Key Learnings Summary

```
✅ CIA Triad: encrypt, sign, ensure availability
✅ RBAC: roles + permissions (simple, predictable)
✅ ABAC with OPA: context-aware (flexible)
✅ MFA via TOTP: prevent account takeover
✅ STRIDE: systematic threat modeling
✅ mTLS: zero-trust service-to-service
✅ K8s NetworkPolicies: microsegmentation
✅ Audit logging: tamper-evident records
✅ DevSecOps CI/CD: security at every stage

🎯 Production Zero Trust stack:
   - IdP with MFA (Auth0/Okta)
   - Service mesh with mTLS (Istio)
   - K8s NetworkPolicies (deny-by-default)
   - OPA for fine-grained policies
   - Centralized audit logs → SIEM
   - DevSecOps CI/CD with all scans
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll dive deep into **OAuth 2.0 and OpenID Connect** — the protocols that power modern authentication and authorization.

> **Next lecture:** [02_OAuth_OpenID_Connect.md](02_OAuth_OpenID_Connect.md)

---

## 📚 Try It Yourself

1. Build a **complete RBAC system** with hierarchical roles
2. Write **5 OPA policies** for different access scenarios
3. Implement **WebAuthn passkeys** (passwordless MFA)
4. Run a **STRIDE workshop** for your own API
5. Set up **k8s NetworkPolicies** for an existing app
