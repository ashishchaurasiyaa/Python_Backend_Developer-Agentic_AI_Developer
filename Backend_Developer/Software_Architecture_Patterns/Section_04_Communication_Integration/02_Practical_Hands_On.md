# Lecture 2 — Practical Hands-On: API Gateway & BFF

> **Theory file:** [02_API_Gateway_BFF.md](02_API_Gateway_BFF.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production-ready gateway + BFF setup:

1. ✅ **Custom API Gateway** in FastAPI (full features)
2. ✅ **Routing strategies** (path, host, header-based)
3. ✅ **JWT authentication** at gateway level
4. ✅ **Rate limiting** per user/IP (Redis-backed)
5. ✅ **Request/response transformation**
6. ✅ **Mobile BFF** + **Web BFF** with different responses
7. ✅ **Aggregation pattern** in BFF
8. ✅ **Anti-corruption layer** over legacy
9. ✅ **Kong API Gateway** real-world example
10. ✅ **mTLS** for internal services

By end: aap **production-ready gateway + BFF** likh sakte ho.

---

## 1. Project Structure

```
gateway_bff_demo/
├── docker-compose.yml
├── README.md
│
├── gateway/
│   ├── main.py                  # Custom gateway
│   ├── auth.py
│   ├── rate_limit.py
│   ├── routing.py
│   └── transformations.py
│
├── bffs/
│   ├── mobile_bff/
│   │   └── main.py
│   ├── web_bff/
│   │   └── main.py
│   └── partner_bff/
│       └── main.py
│
├── core_services/
│   ├── user_service/
│   │   └── main.py
│   ├── order_service/
│   │   └── main.py
│   ├── catalog_service/
│   │   └── main.py
│   └── legacy_crm/             # Simulated legacy system
│       └── main.py
│
└── kong_config/
    └── kong.yml                 # Kong declarative config
```

---

## 2. Setup & Dependencies

```bash
pip install fastapi uvicorn httpx
pip install pyjwt[crypto] passlib
pip install redis aioredis
pip install python-multipart
```

---

## 3. 🚪 Custom API Gateway (FastAPI)

### `gateway/main.py`

```python
"""
Production-grade API Gateway in FastAPI.
Demonstrates: routing, auth, rate limiting, transformation, logging.
"""
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.responses import Response
import httpx
import time
import uuid
import json
import logging
from contextlib import asynccontextmanager
import redis.asyncio as redis

from .auth import verify_token, AuthClaims
from .rate_limit import RateLimiter
from .routing import RouteResolver
from .transformations import transform_request, transform_response

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger("gateway")

# ─────────────────────────────────────────────────────────────
# LIFESPAN: Setup connections
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=30.0)
    app.state.redis = redis.from_url("redis://localhost")
    app.state.rate_limiter = RateLimiter(app.state.redis)
    app.state.router = RouteResolver()
    yield
    await app.state.http.aclose()
    await app.state.redis.close()

app = FastAPI(title="API Gateway", lifespan=lifespan)

# ─────────────────────────────────────────────────────────────
# MIDDLEWARE: Logging + Request ID
# ─────────────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    
    response.headers["X-Request-Id"] = request_id
    
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration:.0f}ms)"
    )
    
    return response

# ─────────────────────────────────────────────────────────────
# GATEWAY: Main proxy endpoint
# ─────────────────────────────────────────────────────────────
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def gateway_proxy(path: str, request: Request):
    """
    Gateway pipeline:
    1. Authentication
    2. Rate limiting
    3. Routing
    4. Request transformation
    5. Forward to backend
    6. Response transformation
    7. Return to client
    """
    # ── 1. AUTHENTICATION ──
    public_paths = ["/health", "/docs", "/openapi.json", "/login"]
    claims = None
    if not any(path.startswith(p.lstrip('/')) for p in public_paths):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(401, "Missing Authorization header")
        try:
            claims = verify_token(auth_header.replace("Bearer ", ""))
        except Exception as e:
            raise HTTPException(401, f"Invalid token: {e}")
    
    # ── 2. RATE LIMITING ──
    if claims:
        limit_key = f"user:{claims.user_id}"
    else:
        limit_key = f"ip:{request.client.host}"
    
    allowed, remaining = await app.state.rate_limiter.check(limit_key)
    if not allowed:
        raise HTTPException(429, "Rate limit exceeded")
    
    # ── 3. ROUTING ──
    target_url = app.state.router.resolve(
        path=path,
        method=request.method,
        host=request.headers.get("host"),
        user_agent=request.headers.get("user-agent", ""),
    )
    if not target_url:
        raise HTTPException(404, f"No route for {path}")
    
    # ── 4. REQUEST TRANSFORMATION ──
    body = await request.body()
    if body:
        body = transform_request(body, target_url)
    
    # ── 5. FORWARD TO BACKEND ──
    headers = dict(request.headers)
    headers.pop("host", None)  # Don't forward original host
    
    # Inject identity for backend
    if claims:
        headers["X-User-Id"] = str(claims.user_id)
        headers["X-User-Role"] = claims.role
        headers["X-Request-Id"] = request.state.request_id
    
    try:
        backend_response = await app.state.http.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
            params=request.query_params,
        )
    except httpx.RequestError as e:
        logger.error(f"Backend error: {e}")
        raise HTTPException(502, "Backend service unavailable")
    
    # ── 6. RESPONSE TRANSFORMATION ──
    response_body = backend_response.content
    if backend_response.headers.get("content-type", "").startswith("application/json"):
        response_body = transform_response(response_body, target_url)
    
    # ── 7. RETURN ──
    return Response(
        content=response_body,
        status_code=backend_response.status_code,
        headers={
            "X-RateLimit-Remaining": str(remaining),
            "Content-Type": backend_response.headers.get("content-type", "application/json"),
        }
    )

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-gateway"}
```

### `gateway/auth.py`

```python
"""JWT authentication for the gateway"""
import jwt
from pydantic import BaseModel
from datetime import datetime, timedelta

SECRET_KEY = "your-super-secret-key"  # In prod: from vault
ALGORITHM = "HS256"

class AuthClaims(BaseModel):
    user_id: int
    role: str
    exp: datetime

def create_token(user_id: int, role: str = "user") -> str:
    """Create JWT token (for /login endpoint)"""
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> AuthClaims:
    """Verify JWT and return claims"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return AuthClaims(
            user_id=payload["user_id"],
            role=payload["role"],
            exp=datetime.fromtimestamp(payload["exp"]),
        )
    except jwt.ExpiredSignatureError:
        raise Exception("Token expired")
    except jwt.InvalidTokenError as e:
        raise Exception(f"Invalid token: {e}")
```

### `gateway/rate_limit.py`

```python
"""Redis-backed rate limiter (sliding window)"""
import time

class RateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.
    """
    
    def __init__(self, redis_client, limit: int = 60, window_seconds: int = 60):
        self.redis = redis_client
        self.limit = limit
        self.window = window_seconds
    
    async def check(self, key: str) -> tuple[bool, int]:
        """
        Returns (allowed, remaining)
        Uses sliding window with sorted set.
        """
        now = time.time()
        window_start = now - self.window
        
        pipe = self.redis.pipeline()
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries in window
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {f"{now}:{id(now)}": now})
        # Set expiry
        pipe.expire(key, self.window)
        
        results = await pipe.execute()
        current_count = results[1]
        
        allowed = current_count < self.limit
        remaining = max(0, self.limit - current_count - 1)
        
        return allowed, remaining
```

### `gateway/routing.py`

```python
"""Route resolution: path/host/header-based"""
from typing import Optional

class RouteResolver:
    """
    Resolves backend URL based on:
    - Path patterns
    - Host
    - User-Agent (mobile vs web)
    """
    
    def __init__(self):
        self.routes = {
            # Path-based routes
            "users": "http://user-service:8001",
            "orders": "http://order-service:8002",
            "products": "http://catalog-service:8003",
            "payments": "http://payment-service:8004",
            
            # BFFs
            "mobile": "http://mobile-bff:9001",
            "web": "http://web-bff:9002",
            "partner": "http://partner-bff:9003",
        }
    
    def resolve(self, path: str, method: str, host: str, user_agent: str) -> Optional[str]:
        """Determine target URL"""
        
        # 1. Host-based routing
        if host:
            if "api.mobile" in host:
                return f"{self.routes['mobile']}/{path}"
            elif "api.partner" in host:
                return f"{self.routes['partner']}/{path}"
        
        # 2. User-Agent based (smart detection)
        is_mobile = any(m in user_agent.lower() for m in ["mobile", "iphone", "android"])
        
        # 3. Path-based
        parts = path.strip('/').split('/')
        if not parts:
            return None
        
        first_segment = parts[0]
        
        # Mobile clients → mobile BFF for aggregate paths
        if is_mobile and first_segment in ["dashboard", "feed"]:
            return f"{self.routes['mobile']}/{path}"
        
        # Direct service routing
        if first_segment in self.routes:
            return f"{self.routes[first_segment]}/{path}"
        
        return None
```

### `gateway/transformations.py`

```python
"""Request/response transformation"""
import json
import re

def camel_to_snake(name: str) -> str:
    """firstName → first_name"""
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()

def snake_to_camel(name: str) -> str:
    """first_name → firstName"""
    parts = name.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])

def transform_keys(obj, transformer):
    """Recursively transform dict keys"""
    if isinstance(obj, dict):
        return {transformer(k): transform_keys(v, transformer) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [transform_keys(item, transformer) for item in obj]
    return obj

def transform_request(body: bytes, target_url: str) -> bytes:
    """
    Frontend uses camelCase, backend uses snake_case.
    Convert request from camel → snake.
    """
    try:
        data = json.loads(body)
        transformed = transform_keys(data, camel_to_snake)
        return json.dumps(transformed).encode()
    except json.JSONDecodeError:
        return body

def transform_response(body: bytes, target_url: str) -> bytes:
    """
    Convert response from snake → camel for frontend.
    """
    try:
        data = json.loads(body)
        transformed = transform_keys(data, snake_to_camel)
        return json.dumps(transformed).encode()
    except json.JSONDecodeError:
        return body
```

---

## 4. 📱 Mobile BFF

### `bffs/mobile_bff/main.py`

```python
"""
Mobile BFF - optimized for mobile bandwidth.
Returns MINIMAL data, aggregated in one call.
"""
from fastapi import FastAPI, Header, HTTPException
import httpx
import asyncio

app = FastAPI(title="Mobile BFF")

USER_SVC = "http://user-service:8001"
ORDER_SVC = "http://order-service:8002"
CATALOG_SVC = "http://catalog-service:8003"

@app.get("/dashboard")
async def mobile_dashboard(x_user_id: int = Header(...)):
    """
    Aggregate data for mobile dashboard.
    Mobile sees ONLY essential fields → save bandwidth.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Parallel fetch
        user_task = client.get(f"{USER_SVC}/users/{x_user_id}")
        orders_task = client.get(f"{ORDER_SVC}/users/{x_user_id}/orders?limit=3")
        
        user_resp, orders_resp = await asyncio.gather(
            user_task, orders_task, return_exceptions=True
        )
    
    if isinstance(user_resp, Exception):
        raise HTTPException(503, "User service down")
    
    user_data = user_resp.json()
    
    # Mobile-optimized response (minimal fields)
    return {
        "user": {
            "name": user_data["name"],
            "avatar": user_data.get("avatar_url"),
        },
        "recent_orders": [
            {
                "id": o["id"],
                "status": o["status"],
                "total": o["total"],
            }
            for o in (orders_resp.json() if not isinstance(orders_resp, Exception) else [])
        ],
        "notifications_count": user_data.get("unread_count", 0),
    }

@app.get("/products/{product_id}")
async def mobile_product(product_id: str):
    """Mobile sees product with compressed image and minimal description"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CATALOG_SVC}/products/{product_id}")
    
    product = resp.json()
    
    # Mobile-optimized
    return {
        "id": product["id"],
        "name": product["name"],
        "price": product["price"],
        "thumbnail": product["images"]["mobile"],  # Compressed image
        "in_stock": product["stock"] > 0,
        # Skip: full description, all images, reviews list, etc.
    }
```

---

## 5. 💻 Web BFF

### `bffs/web_bff/main.py`

```python
"""
Web BFF - rich data for web dashboard.
Returns COMPREHENSIVE data optimized for large screens.
"""
from fastapi import FastAPI, Header
import httpx
import asyncio

app = FastAPI(title="Web BFF")

USER_SVC = "http://user-service:8001"
ORDER_SVC = "http://order-service:8002"
CATALOG_SVC = "http://catalog-service:8003"

@app.get("/dashboard")
async def web_dashboard(x_user_id: int = Header(...)):
    """Web sees comprehensive dashboard data"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Parallel fetch from more services
        tasks = [
            client.get(f"{USER_SVC}/users/{x_user_id}"),
            client.get(f"{ORDER_SVC}/users/{x_user_id}/orders?limit=20"),
            client.get(f"{ORDER_SVC}/users/{x_user_id}/analytics"),
            client.get(f"{CATALOG_SVC}/recommendations/{x_user_id}?count=10"),
        ]
        user_resp, orders_resp, analytics_resp, recs_resp = await asyncio.gather(*tasks)
    
    user = user_resp.json()
    orders = orders_resp.json()
    
    return {
        "user": user,  # Full user object
        "orders": {
            "recent": orders,
            "analytics": analytics_resp.json(),
            "summary": {
                "total_orders": len(orders),
                "total_spent": sum(o["total"] for o in orders),
            }
        },
        "recommendations": recs_resp.json(),
        "metadata": {
            "generated_at": "2026-05-26T10:00:00Z",
            "version": "v2",
        }
    }
```

---

## 6. 🤝 Partner BFF (Anti-Corruption Layer)

### `bffs/partner_bff/main.py`

```python
"""
Partner BFF - translates legacy CRM format to modern API.
Acts as ANTI-CORRUPTION LAYER.
"""
from fastapi import FastAPI, HTTPException
import httpx
from typing import Optional

app = FastAPI(title="Partner BFF (Anti-Corruption Layer)")

LEGACY_CRM = "http://legacy-crm:8500"  # Old SOAP/XML system

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    """Translate legacy CRM ugliness to modern API"""
    async with httpx.AsyncClient() as client:
        # Call legacy system with its weird conventions
        resp = await client.get(
            f"{LEGACY_CRM}/CUST_LOOKUP",
            params={"CUST_ID": customer_id.zfill(10)}  # Legacy needs zero-padded
        )
    
    if resp.status_code != 200:
        raise HTTPException(404, "Customer not found")
    
    # Legacy response (UGLY!):
    # {
    #     "CUST_ID": "0000000123",
    #     "CUST_NM_FRST": "ASHISH",
    #     "CUST_NM_LST": "CHAURASIYA",
    #     "CUST_EMAIL_ADDR": "ASHISH@EXAMPLE.COM",
    #     "CUST_STAT_CD": "A",
    #     "CUST_CRT_DT": "20240115",
    #     "CUST_LST_LOGIN_DT": "20260526"
    # }
    legacy_data = resp.json()
    
    # Translate to modern shape (CLEAN!)
    return {
        "id": str(int(legacy_data["CUST_ID"])),  # Remove zero padding
        "firstName": legacy_data["CUST_NM_FRST"].title(),
        "lastName": legacy_data["CUST_NM_LST"].title(),
        "email": legacy_data["CUST_EMAIL_ADDR"].lower(),
        "isActive": legacy_data["CUST_STAT_CD"] == "A",
        "createdAt": _parse_legacy_date(legacy_data["CUST_CRT_DT"]),
        "lastLogin": _parse_legacy_date(legacy_data["CUST_LST_LOGIN_DT"]),
    }

def _parse_legacy_date(date_str: str) -> str:
    """Convert YYYYMMDD to ISO 8601"""
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
```

---

## 7. 🏗 Backend Services

### `core_services/user_service/main.py`

```python
"""Core user service - backend behind gateway"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="User Service")

USERS = {
    1: {
        "id": 1,
        "name": "Ashish Chaurasiya",
        "email": "ashish@example.com",
        "avatar_url": "https://cdn/avatars/1.jpg",
        "unread_count": 5,
        "tier": "GOLD",
    },
    2: {
        "id": 2,
        "name": "Rahul Singh",
        "email": "rahul@example.com",
        "avatar_url": "https://cdn/avatars/2.jpg",
        "unread_count": 0,
        "tier": "SILVER",
    },
}

@app.get("/users/{user_id}")
def get_user(user_id: int, x_user_id: int = Header(...)):
    """Get user (gateway injects X-User-Id from auth)"""
    # Only return data for authenticated user
    if user_id != x_user_id:
        raise HTTPException(403, "Forbidden")
    
    user = USERS.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user
```

---

## 8. 🐳 Docker Compose

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ───── Infrastructure ─────
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  # ───── Gateway ─────
  gateway:
    build: ./gateway
    ports: ["8000:8000"]
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on: [redis]
  
  # ───── BFFs ─────
  mobile_bff:
    build: ./bffs/mobile_bff
    ports: ["9001:9001"]
    depends_on: [user_service, order_service]
  
  web_bff:
    build: ./bffs/web_bff
    ports: ["9002:9002"]
    depends_on: [user_service, order_service, catalog_service]
  
  partner_bff:
    build: ./bffs/partner_bff
    ports: ["9003:9003"]
    depends_on: [legacy_crm]
  
  # ───── Core Services ─────
  user_service:
    build: ./core_services/user_service
    ports: ["8001:8001"]
  
  order_service:
    build: ./core_services/order_service
    ports: ["8002:8002"]
  
  catalog_service:
    build: ./core_services/catalog_service
    ports: ["8003:8003"]
  
  legacy_crm:
    build: ./core_services/legacy_crm
    ports: ["8500:8500"]
```

---

## 9. 🧪 Testing the Setup

### Get a Token

```bash
# Login (mock endpoint - returns JWT)
$ curl -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" \
    -d '{"username": "ashish", "password": "test"}'

{
    "access_token": "eyJ0eXAi...",
    "token_type": "bearer"
}
```

### Mobile vs Web Dashboard

```bash
# Web call (rich data)
$ curl -H "Authorization: Bearer $TOKEN" \
       -H "User-Agent: Mozilla/5.0 Desktop" \
       http://localhost:8000/dashboard

{
    "user": { "id": 1, "name": "...", "email": "...", "avatar_url": "...", ... },
    "orders": { "recent": [...20 orders...], "analytics": {...}, "summary": {...} },
    "recommendations": [...10 items...],
    "metadata": {...}
}

# Mobile call (minimal data) — same endpoint, different response!
$ curl -H "Authorization: Bearer $TOKEN" \
       -H "User-Agent: iPhone iOS" \
       http://localhost:8000/dashboard

{
    "user": { "name": "Ashish", "avatar": "..." },
    "recent_orders": [...3 minimal orders...],
    "notifications_count": 5
}
```

### Rate Limiting in Action

```bash
# Hit rapidly
$ for i in {1..100}; do
    curl -s -o /dev/null -w "%{http_code}\n" \
      -H "Authorization: Bearer $TOKEN" \
      http://localhost:8000/users/1
  done

200
200
200
... (60 OK)
429  ← rate limited!
429
...
```

### Camel ↔ Snake Translation

```bash
# Frontend sends camelCase
$ curl -X POST http://localhost:8000/users \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"firstName": "Ashish", "lastName": "Chaurasiya"}'

# Backend receives snake_case (transformed by gateway):
# {"first_name": "Ashish", "last_name": "Chaurasiya"}

# Backend responds in snake_case
# Frontend sees camelCase (transformed back):
{
    "firstName": "Ashish",
    "lastName": "Chaurasiya"
}
```

---

## 10. 🦁 Real-World: Kong API Gateway

### Why Kong?

```
✓ Production-ready
✓ Plugins for everything (auth, rate limit, caching, JWT, etc.)
✓ Declarative config
✓ Kubernetes-native
✓ Massive community
```

### `kong_config/kong.yml`

```yaml
_format_version: "3.0"

services:
  - name: user-service
    url: http://user-service:8001
    routes:
      - name: users-route
        paths: ["/users"]
        strip_path: false
    plugins:
      - name: rate-limiting
        config:
          minute: 60
          policy: redis
          redis_host: redis
      
      - name: jwt
        config:
          secret_is_base64: false
      
      - name: request-transformer
        config:
          add:
            headers:
              - "X-Gateway: Kong"
      
      - name: cors
        config:
          origins: ["https://example.com"]
          methods: ["GET", "POST", "PUT", "DELETE"]

  - name: mobile-bff
    url: http://mobile-bff:9001
    routes:
      - name: mobile-route
        hosts: ["api.mobile.example.com"]
    plugins:
      - name: jwt
      - name: rate-limiting
        config:
          minute: 100

consumers:
  - username: web-app
    jwt_secrets:
      - key: web-app-key
        secret: webappsecret123
  
  - username: mobile-app
    jwt_secrets:
      - key: mobile-app-key
        secret: mobileappsecret456
```

### Run Kong

```bash
docker run -d \
  --name kong \
  -v $(pwd)/kong_config:/usr/local/kong/declarative \
  -e KONG_DATABASE=off \
  -e KONG_DECLARATIVE_CONFIG=/usr/local/kong/declarative/kong.yml \
  -p 8000:8000 \
  -p 8001:8001 \
  kong:3.5

# 8000 = proxy
# 8001 = admin API
```

### Test

```bash
# Get token (configured in kong.yml)
$ TOKEN=$(jwt encode --secret=webappsecret123 \
    --payload='{"iss":"web-app-key","exp":1735689600}')

# Make request through Kong
$ curl http://localhost:8000/users/1 \
    -H "Authorization: Bearer $TOKEN"
```

---

## 11. 🔒 Internal mTLS

### Secure BFF → Service Communication

```python
"""
mTLS - both gateway/BFF and service authenticate each other.
"""
import httpx
import ssl

# Create mTLS context
ssl_context = ssl.create_default_context(
    cafile="/etc/ssl/ca.crt"  # CA that signed both certs
)
ssl_context.load_cert_chain(
    certfile="/etc/ssl/bff-client.crt",
    keyfile="/etc/ssl/bff-client.key"
)

async with httpx.AsyncClient(verify=ssl_context) as client:
    # Service will verify our client cert
    response = await client.get("https://user-service:8443/users/1")
```

### With Service Mesh (Istio)

```yaml
# Automatic mTLS via Istio sidecar
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT  # Require mTLS for all traffic
```

---

## 12. 🧪 Integration Tests

### `tests/test_gateway.py`

```python
import pytest
import httpx

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/users/1")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_mobile_user_agent_routes_to_mobile_bff():
    token = get_test_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/dashboard",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mobile Safari/iOS 17"
            }
        )
        data = response.json()
        # Mobile BFF returns minimal data
        assert "recent_orders" in data
        assert len(data.get("user", {})) <= 3  # name + avatar + maybe one more

@pytest.mark.asyncio
async def test_web_routes_to_web_bff():
    token = get_test_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/dashboard",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (Macintosh)"
            }
        )
        data = response.json()
        # Web BFF returns rich data
        assert "recommendations" in data
        assert len(data.get("orders", {}).get("recent", [])) > 3

@pytest.mark.asyncio
async def test_rate_limiting():
    token = get_test_token()
    async with httpx.AsyncClient() as client:
        # Hit rate limit
        results = []
        for _ in range(100):
            r = await client.get(
                "http://localhost:8000/users/1",
                headers={"Authorization": f"Bearer {token}"}
            )
            results.append(r.status_code)
        
        # Should see some 429s
        assert 429 in results
```

---

## 13. Key Learnings Summary

```
✅ Custom gateway in FastAPI: auth + rate limit + routing + transform
✅ BFF pattern: tailored response per client (mobile/web/partner)
✅ Anti-corruption layer: shield modern frontend from legacy
✅ Camel ↔ snake case translation at gateway
✅ JWT auth + Redis rate limiting
✅ Kong for production-grade API gateway
✅ mTLS for secure internal communication

🎯 Production stack:
   Client → Kong (auth, rate limit) → BFF (orchestrate, format) → Services
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll dive into **Messaging and Event Brokers** — how services communicate asynchronously through queues and streams.

> **Next lecture:** [03_Messaging_Event_Brokers.md](03_Messaging_Event_Brokers.md)

---

## 📚 Try It Yourself

1. Add **caching plugin** to gateway (Redis-backed)
2. Implement **circuit breaker** for backend failures
3. Build a **GraphQL BFF** that exposes REST services
4. Add **API key management** alongside JWT
5. Deploy Kong to **Kubernetes with Helm chart**
