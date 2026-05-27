# Lecture 3 — Practical Hands-On: API & Service Security

> **Theory file:** [03_API_Service_Security.md](03_API_Service_Security.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready API security:

1. ✅ **API key management** with scoping + rotation
2. ✅ **JWT validation** done RIGHT (algorithm lock-in, kid check)
3. ✅ **mTLS** for service-to-service
4. ✅ **Rate limiting** per key/user
5. ✅ **WAF rules** via Cloudflare / OWASP CRS
6. ✅ **Input validation** with Pydantic
7. ✅ **Object-level authorization** (BOLA prevention)
8. ✅ **API gateway** security with Kong
9. ✅ **Webhook signature** verification (HMAC)
10. ✅ **Security audit logging**

By end: aap **production-grade API security** ko implement kar sakte ho.

---

## 1. Project Structure

```
api_security_demo/
├── docker-compose.yml
├── README.md
│
├── api_keys/
│   ├── key_manager.py
│   ├── rotation.py
│   └── usage_tracking.py
│
├── jwt/
│   ├── validator.py
│   ├── jwks_client.py
│   └── tests.py
│
├── mtls/
│   ├── certs/
│   ├── server.py
│   └── client.py
│
├── rate_limiting/
│   ├── token_bucket.py
│   └── sliding_window.py
│
├── input_validation/
│   ├── schemas.py
│   └── sanitization.py
│
├── authorization/
│   ├── bola_check.py
│   └── scope_check.py
│
├── webhooks/
│   ├── sender.py
│   └── receiver.py
│
└── audit/
    └── api_audit.py
```

---

## 2. 🔑 API Key Management

### `api_keys/key_manager.py`

```python
"""
Production-grade API key management.
"""
import secrets
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Set
from datetime import datetime, timedelta
from enum import Enum

class KeyScope(str, Enum):
    READ_USERS = "read:users"
    WRITE_USERS = "write:users"
    READ_ORDERS = "read:orders"
    WRITE_ORDERS = "write:orders"
    ADMIN = "admin:*"

@dataclass
class APIKey:
    """API key with metadata"""
    id: str
    key_hash: str             # NEVER store plain key
    name: str
    scopes: Set[KeyScope] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    
    # Restrictions
    ip_allowlist: Set[str] = field(default_factory=set)
    rate_limit_per_minute: int = 100
    
    # Tracking
    total_requests: int = 0
    revoked: bool = False

class APIKeyManager:
    """Manage API keys lifecycle"""
    
    PREFIX_LIVE = "ak_live_"
    PREFIX_TEST = "ak_test_"
    
    def __init__(self):
        self.keys: dict[str, APIKey] = {}  # In prod: use DB
    
    def generate(
        self,
        name: str,
        scopes: Set[KeyScope],
        expires_in_days: int = 90,
        ip_allowlist: Set[str] = None,
        is_test: bool = False,
    ) -> tuple[str, APIKey]:
        """
        Generate a new API key.
        Returns (raw_key, metadata).
        IMPORTANT: raw_key shown ONCE. After that, only hash stored.
        """
        # Generate strong random key
        raw_key = secrets.token_urlsafe(32)
        prefix = self.PREFIX_TEST if is_test else self.PREFIX_LIVE
        full_key = f"{prefix}{raw_key}"
        
        # Hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        # Create metadata
        api_key = APIKey(
            id=f"key_{secrets.token_hex(8)}",
            key_hash=key_hash,
            name=name,
            scopes=scopes,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            ip_allowlist=ip_allowlist or set(),
        )
        
        self.keys[key_hash] = api_key
        return full_key, api_key
    
    def verify(
        self,
        provided_key: str,
        required_scope: KeyScope,
        client_ip: str,
    ) -> Optional[APIKey]:
        """Verify API key and check permissions"""
        # Hash provided key
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        
        # Lookup
        api_key = self.keys.get(provided_hash)
        if not api_key:
            return None  # Key doesn't exist
        
        # Check revocation
        if api_key.revoked:
            return None
        
        # Check expiry
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None
        
        # Check IP allowlist
        if api_key.ip_allowlist and client_ip not in api_key.ip_allowlist:
            return None
        
        # Check scope
        if required_scope not in api_key.scopes and KeyScope.ADMIN not in api_key.scopes:
            return None
        
        # Update tracking
        api_key.last_used_at = datetime.utcnow()
        api_key.total_requests += 1
        
        return api_key
    
    def revoke(self, key_id: str):
        """Immediate revocation"""
        for key in self.keys.values():
            if key.id == key_id:
                key.revoked = True
                break
    
    def rotate(self, old_key_id: str) -> tuple[str, APIKey]:
        """Rotate: create new key, schedule old for revocation"""
        old_key = next((k for k in self.keys.values() if k.id == old_key_id), None)
        if not old_key:
            raise ValueError("Key not found")
        
        # Create new with same scopes
        new_key, new_metadata = self.generate(
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes,
            ip_allowlist=old_key.ip_allowlist,
        )
        
        # Schedule old key for revocation (after grace period)
        old_key.expires_at = datetime.utcnow() + timedelta(hours=24)
        
        return new_key, new_metadata

# Usage
manager = APIKeyManager()

# Generate key (show ONCE to user)
key, metadata = manager.generate(
    name="Mobile App",
    scopes={KeyScope.READ_USERS, KeyScope.READ_ORDERS},
    expires_in_days=90,
    ip_allowlist={"203.0.113.5"},
)
print(f"YOUR KEY (save now, won't be shown again): {key}")
print(f"Key ID: {metadata.id}")
```

### FastAPI Integration

```python
"""API endpoints protected by API keys"""
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()
manager = APIKeyManager()

def get_api_key(
    request: Request,
    x_api_key: str = Header(...),
    required_scope: KeyScope = KeyScope.READ_USERS,
):
    """Dependency to verify API key"""
    api_key = manager.verify(
        provided_key=x_api_key,
        required_scope=required_scope,
        client_ip=request.client.host,
    )
    if not api_key:
        raise HTTPException(401, "Invalid API key")
    return api_key

@app.get("/api/users")
def list_users(
    api_key: APIKey = Depends(
        lambda r, k=Header(...): get_api_key(r, k, KeyScope.READ_USERS)
    )
):
    return {"users": [...]}
```

---

## 3. 🔒 JWT Validation Done Right

### `jwt/validator.py`

```python
"""
Production-grade JWT validation.
Handles all the pitfalls correctly.
"""
import jwt
from jwt import PyJWKClient
import requests
from typing import Optional

class JWTValidator:
    """
    Secure JWT validator with:
    - Algorithm whitelist (prevents alg=none)
    - JWKS fetching (key rotation support)
    - Audience verification
    - Issuer verification
    - Expiry check
    """
    
    def __init__(
        self,
        jwks_url: str,
        expected_audience: str,
        expected_issuer: str,
        allowed_algorithms: list[str] = None,
    ):
        self.jwks_url = jwks_url
        self.audience = expected_audience
        self.issuer = expected_issuer
        self.allowed_algorithms = allowed_algorithms or ["RS256"]
        # JWKS client with caching
        self.jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    
    def validate(self, token: str) -> dict:
        """
        Validate JWT and return claims.
        Raises ValueError on any failure.
        """
        # ── 1. Get header WITHOUT verification ──
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.DecodeError:
            raise ValueError("Malformed token")
        
        # ── 2. Validate algorithm (CRITICAL!) ──
        alg = unverified_header.get("alg")
        if alg not in self.allowed_algorithms:
            # This prevents:
            # - alg=none attacks
            # - HMAC/RSA confusion
            raise ValueError(f"Algorithm '{alg}' not allowed")
        
        # ── 3. Get key by kid ──
        kid = unverified_header.get("kid")
        if not kid:
            raise ValueError("Missing 'kid' header")
        
        # ── 4. Fetch public key from JWKS ──
        try:
            signing_key = self.jwks_client.get_signing_key(kid)
        except jwt.PyJWKClientError:
            raise ValueError(f"Unknown kid: {kid}")
        
        # ── 5. Verify everything ──
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self.allowed_algorithms,  # HARDCODED, not from token!
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                }
            )
            return payload
        
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidAudienceError:
            raise ValueError("Invalid audience")
        except jwt.InvalidIssuerError:
            raise ValueError("Invalid issuer")
        except jwt.InvalidSignatureError:
            raise ValueError("Invalid signature")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
validator = JWTValidator(
    jwks_url="https://auth.example.com/.well-known/jwks.json",
    expected_audience="https://api.example.com",
    expected_issuer="https://auth.example.com",
    allowed_algorithms=["RS256"],  # ONLY RS256!
)

try:
    claims = validator.validate(token)
    print(f"User: {claims['sub']}, Scopes: {claims.get('scope')}")
except ValueError as e:
    print(f"Token validation failed: {e}")
```

### Test for Algorithm Confusion

```python
"""tests/test_jwt_security.py"""
import pytest
import jwt as pyjwt

def test_alg_none_rejected():
    """Tokens with alg=none must be rejected"""
    # Forge token with alg=none
    forged = pyjwt.encode(
        {"sub": "attacker", "is_admin": True},
        "",  # No key needed for alg=none
        algorithm="none"
    )
    
    with pytest.raises(ValueError, match="not allowed"):
        validator.validate(forged)

def test_wrong_algorithm_rejected():
    """HS256 token rejected when only RS256 allowed"""
    forged = pyjwt.encode(
        {"sub": "attacker"},
        "secret",
        algorithm="HS256"
    )
    
    with pytest.raises(ValueError, match="not allowed"):
        validator.validate(forged)

def test_wrong_audience_rejected():
    valid_for_other_api = create_valid_token(audience="other_api")
    
    with pytest.raises(ValueError, match="audience"):
        validator.validate(valid_for_other_api)

def test_expired_rejected():
    expired = create_expired_token()
    
    with pytest.raises(ValueError, match="expired"):
        validator.validate(expired)
```

---

## 4. 🔐 mTLS Implementation

### Generate Certs

```bash
#!/bin/bash
# Generate CA + server + client certificates

set -e

mkdir -p certs && cd certs

# 1. CA (Root)
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 365 -key ca-key.pem -out ca-cert.pem \
    -subj "/C=IN/O=MyCompany/CN=MyCA"

# 2. Server cert
openssl genrsa -out server-key.pem 4096
openssl req -new -key server-key.pem -out server-csr.pem \
    -subj "/C=IN/O=MyCompany/CN=my-service"
openssl x509 -req -days 365 -in server-csr.pem \
    -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
    -out server-cert.pem

# 3. Client cert (per service)
openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client-csr.pem \
    -subj "/C=IN/O=MyCompany/CN=billing-service"
openssl x509 -req -days 365 -in client-csr.pem \
    -CA ca-cert.pem -CAkey ca-key.pem \
    -out client-cert.pem

echo "✓ All certs in ./certs/"
```

### mTLS Server (FastAPI)

```python
"""HTTPS server requiring valid client certificate"""
import ssl
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import binascii

app = FastAPI()

@app.middleware("http")
async def extract_client_cert(request: Request, call_next):
    """Extract client cert info"""
    transport = request.scope.get("transport")
    if transport:
        peer_cert = transport.get_extra_info("peercert")
        if peer_cert:
            # Get subject
            subject_dict = {}
            for component in peer_cert.get("subject", []):
                key, value = component[0]
                subject_dict[key] = value
            
            request.state.client_subject = subject_dict
    
    return await call_next(request)

@app.get("/internal/api")
async def internal_endpoint(request: Request):
    """Only accessible with valid client cert"""
    client = getattr(request.state, "client_subject", None)
    if not client:
        raise HTTPException(401, "Client certificate required")
    
    # Authorize based on cert CN
    common_name = client.get("commonName")
    if common_name not in ["billing-service", "order-service"]:
        raise HTTPException(403, f"Service {common_name} not authorized")
    
    return {
        "message": "Authorized",
        "service": common_name,
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_certfile="certs/server-cert.pem",
        ssl_keyfile="certs/server-key.pem",
        ssl_ca_certs="certs/ca-cert.pem",
        ssl_cert_reqs=ssl.CERT_REQUIRED,  # REQUIRE client cert!
    )
```

### mTLS Client

```python
"""Client presenting its certificate"""
import httpx
import asyncio

async def call_internal_api():
    async with httpx.AsyncClient(
        verify="certs/ca-cert.pem",
        cert=("certs/client-cert.pem", "certs/client-key.pem"),
    ) as client:
        response = await client.get("https://my-service:8443/internal/api")
        print(response.json())

asyncio.run(call_internal_api())
```

---

## 5. 📈 Rate Limiting

### Token Bucket Algorithm

```python
"""
Token bucket rate limiter.
Each user gets N tokens, refilled over time.
"""
import time
import redis.asyncio as redis

class TokenBucketLimiter:
    """
    Lua script for atomic operations on Redis.
    """
    
    LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local tokens_to_consume = tonumber(ARGV[4])
    
    local data = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(data[1]) or capacity
    local last_refill = tonumber(data[2]) or now
    
    -- Refill tokens
    local elapsed = now - last_refill
    tokens = math.min(capacity, tokens + (elapsed * refill_rate))
    
    if tokens >= tokens_to_consume then
        tokens = tokens - tokens_to_consume
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)
        return {1, tokens}
    else
        return {0, tokens}
    end
    """
    
    def __init__(self, redis_client, capacity: int = 100, refill_per_second: float = 10):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_per_second
        self.script_sha = None
    
    async def _load_script(self):
        if not self.script_sha:
            self.script_sha = await self.redis.script_load(self.LUA_SCRIPT)
    
    async def allow_request(self, key: str, tokens: int = 1) -> tuple[bool, dict]:
        """Returns (allowed, headers_dict)"""
        await self._load_script()
        
        now = time.time()
        result = await self.redis.evalsha(
            self.script_sha,
            1,
            key,
            str(self.capacity),
            str(self.refill_rate),
            str(now),
            str(tokens),
        )
        
        allowed = bool(result[0])
        remaining = int(result[1])
        
        return allowed, {
            "X-RateLimit-Limit": str(self.capacity),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + ((self.capacity - remaining) / self.refill_rate))),
        }

# ─────────────────────────────────────────────────────────────
# USAGE IN FASTAPI
# ─────────────────────────────────────────────────────────────
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()
limiter = TokenBucketLimiter(redis_client, capacity=100, refill_per_second=10/60)  # 10/min

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Use API key if present, else IP
    api_key = request.headers.get("X-API-Key")
    user_id = request.headers.get("X-User-Id")
    key = f"rl:{api_key or user_id or request.client.host}"
    
    allowed, headers = await limiter.allow_request(key)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers=headers,
        )
    
    response = await call_next(request)
    for k, v in headers.items():
        response.headers[k] = v
    
    return response
```

---

## 6. ✅ Input Validation with Pydantic

```python
"""
Strict input validation = first line of defense.
"""
from pydantic import BaseModel, EmailStr, Field, validator, constr
from typing import Optional, List
from datetime import datetime

class CreateOrderRequest(BaseModel):
    """Strict schema for order creation"""
    user_id: int = Field(..., gt=0, le=1_000_000_000)
    items: List[OrderItem] = Field(..., min_items=1, max_items=100)
    
    # Money: use Decimal in real code
    total: float = Field(..., gt=0, lt=1_000_000)
    
    # Whitelist allowed currencies
    currency: constr(regex="^(USD|EUR|INR|GBP)$") = "USD"
    
    # Optional comment with length limit
    comment: Optional[constr(max_length=500)] = None
    
    @validator("total")
    def total_must_match_items(cls, v, values):
        if "items" in values:
            calculated = sum(i.price * i.quantity for i in values["items"])
            if abs(v - calculated) > 0.01:
                raise ValueError("Total doesn't match items")
        return v
    
    class Config:
        # IMPORTANT: Don't allow extra fields (mass assignment protection)
        extra = "forbid"

class OrderItem(BaseModel):
    sku: constr(regex="^SKU-[A-Z0-9]+$", max_length=50)
    quantity: int = Field(..., gt=0, le=10_000)
    price: float = Field(..., gt=0, lt=100_000)
    
    class Config:
        extra = "forbid"

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException

@app.post("/orders")
async def create_order(req: CreateOrderRequest):
    """
    Pydantic auto-validates everything.
    Attempts like:
       {"user_id": 1, "items": [...], "is_admin": true}
    will be REJECTED (extra="forbid")
    """
    return {"order_id": "..."}
```

---

## 7. 🛡 BOLA (Broken Object Level Authorization)

```python
"""
Object-level authorization - the #1 API vulnerability.
"""
from fastapi import FastAPI, Depends, HTTPException
from typing import Optional

@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
):
    # Get order
    order = await db.get_order(order_id)
    if not order:
        # Return same response for not-found and unauthorized
        # (don't leak existence!)
        raise HTTPException(404, "Order not found")
    
    # ── BOLA CHECK ──
    # User can only access their OWN orders
    if order.user_id != user.id:
        # Don't reveal it exists for other users
        raise HTTPException(404, "Order not found")
    
    return order

@app.delete("/api/orders/{order_id}")
async def delete_order(
    order_id: str,
    user: User = Depends(get_current_user),
):
    order = await db.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    
    # ── BOLA CHECK ──
    # Owner OR admin can delete
    if order.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "Cannot delete others' orders")
    
    await db.delete_order(order_id)
    return {"status": "deleted"}
```

### Generic BOLA Decorator

```python
from functools import wraps

def require_ownership(get_resource_owner_id):
    """Decorator that enforces resource ownership"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: User, **kwargs):
            resource_owner_id = await get_resource_owner_id(*args, **kwargs)
            if resource_owner_id != user.id and not user.is_admin:
                raise HTTPException(404, "Resource not found")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage
async def order_owner(order_id: str):
    order = await db.get_order(order_id)
    return order.user_id if order else None

@app.put("/api/orders/{order_id}")
@require_ownership(order_owner)
async def update_order(order_id: str, user: User = Depends(get_current_user)):
    # User is guaranteed to own this order (or be admin)
    return {"updated": order_id}
```

---

## 8. 🪝 Webhook Signature Verification

### Sender

```python
"""Send webhooks with HMAC signature"""
import hmac
import hashlib
import time
import httpx
import json

class WebhookSender:
    def __init__(self, secret: bytes):
        self.secret = secret
    
    async def send(self, url: str, event: dict):
        body = json.dumps(event)
        timestamp = str(int(time.time()))
        
        # Create signature: HMAC-SHA256 of timestamp.body
        signature = hmac.new(
            self.secret,
            f"{timestamp}.{body}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Timestamp": timestamp,
                    "X-Signature": f"sha256={signature}",
                }
            )
            response.raise_for_status()
```

### Receiver

```python
"""Verify webhook signatures"""
from fastapi import FastAPI, Request, HTTPException, Header
import hmac
import hashlib
import time

app = FastAPI()
WEBHOOK_SECRET = b"shared-secret-from-vault"

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_timestamp: str = Header(...),
    x_signature: str = Header(...),
):
    body = await request.body()
    
    # 1. Check timestamp (prevent replay attacks)
    now = int(time.time())
    if abs(now - int(x_timestamp)) > 300:  # 5-minute window
        raise HTTPException(401, "Stale request")
    
    # 2. Compute expected signature
    expected_sig = "sha256=" + hmac.new(
        WEBHOOK_SECRET,
        f"{x_timestamp}.{body.decode()}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    # 3. Compare in constant time (prevent timing attacks!)
    if not hmac.compare_digest(expected_sig, x_signature):
        raise HTTPException(401, "Invalid signature")
    
    # Process event
    event = json.loads(body)
    return {"received": True}
```

---

## 9. 🦁 Kong API Gateway Security

### `kong.yml`

```yaml
_format_version: "3.0"

services:
  - name: user-api
    url: http://user-service:8001
    
    routes:
      - name: users-route
        paths: ["/api/v1/users"]
    
    plugins:
      # JWT validation
      - name: jwt
        config:
          uri_param_names: []
          cookie_names: []
          claims_to_verify: ["exp"]
          key_claim_name: kid
          secret_is_base64: false
      
      # Rate limiting
      - name: rate-limiting
        config:
          minute: 60
          hour: 1000
          policy: redis
          redis_host: redis
          fault_tolerant: true
      
      # Request size limit
      - name: request-size-limiting
        config:
          allowed_payload_size: 1  # 1 MB
      
      # IP restrictions
      - name: ip-restriction
        config:
          deny: ["192.168.0.0/16"]  # Block specific ranges
      
      # CORS
      - name: cors
        config:
          origins: ["https://app.example.com"]
          methods: ["GET", "POST", "PUT", "DELETE"]
          headers: ["Authorization", "Content-Type"]
          credentials: true
      
      # Bot detection
      - name: bot-detection
        config:
          allow: []
          deny: ["bad-bot", "scraper"]

# Consumers (API key clients)
consumers:
  - username: mobile-app
    keyauth_credentials:
      - key: mobile-key-xxx
    plugins:
      - name: rate-limiting
        config:
          minute: 100  # Higher limit for mobile
  
  - username: web-app
    keyauth_credentials:
      - key: web-key-yyy
```

---

## 10. 📝 Security Audit Logging

```python
"""
Comprehensive API audit logging.
"""
import structlog
import time
from fastapi import Request

logger = structlog.get_logger("api_audit")

@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    start = time.time()
    
    # Capture request info BEFORE processing
    audit_event = {
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "api_key": request.headers.get("X-API-Key"),  # Will be masked
        "request_id": request.headers.get("X-Request-Id"),
    }
    
    # Process request
    try:
        response = await call_next(request)
        audit_event["status_code"] = response.status_code
        audit_event["latency_ms"] = (time.time() - start) * 1000
    
    except Exception as e:
        audit_event["status_code"] = 500
        audit_event["error"] = str(e)
        raise
    
    finally:
        # Mask sensitive fields
        if audit_event.get("api_key"):
            key = audit_event["api_key"]
            audit_event["api_key"] = f"{key[:10]}...{key[-4:]}" if len(key) > 14 else "***"
        
        # Log security-relevant events with HIGH severity
        if audit_event["status_code"] in [401, 403, 429]:
            logger.warning("api_security_event", **audit_event)
        elif audit_event["status_code"] >= 500:
            logger.error("api_error", **audit_event)
        else:
            logger.info("api_request", **audit_event)
    
    return response
```

### SIEM Integration

```python
# Send to Splunk / Elasticsearch / Datadog
import structlog
import logging

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),  # JSON for SIEM
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

# Logs forwarded to:
# - Fluentd / Logstash → Elasticsearch
# - Splunk Forwarder
# - Datadog Agent
# - CloudWatch Logs
```

---

## 11. Key Learnings Summary

```
✅ API keys: scope, rotate, bind to IP
✅ JWT validation: hardcode algorithm, validate kid
✅ mTLS for service-to-service
✅ Token bucket rate limiting (Redis Lua)
✅ Pydantic strict validation (extra=forbid)
✅ BOLA prevention: object-level checks
✅ Webhook HMAC signatures + timestamp
✅ Kong API gateway with security plugins
✅ Structured audit logging → SIEM

🎯 Production API security stack:
   CDN (Cloudflare) → WAF → Kong (auth + rate limit) → 
   Service Mesh (mTLS) → Service (BOLA + validation) → 
   Audit logs → SIEM
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll cover **Secrets and Token Management** — vaults, rotation, encryption strategies.

> **Next lecture:** [04_Secrets_Token_Management.md](04_Secrets_Token_Management.md)

---

## 📚 Try It Yourself

1. Build complete **API key management** UI
2. Implement **JWT** with key rotation via JWKS
3. Set up **mTLS** between 3 microservices
4. Add **CAPTCHA** to login API after failures
5. Build **anomaly detection** on API usage patterns
