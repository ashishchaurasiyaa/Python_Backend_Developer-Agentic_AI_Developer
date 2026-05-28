# API Gateway — Entry Point for Microservices

## WHAT

An **API Gateway** is a single entry point that sits in front of all your backend services. Clients call the gateway; the gateway routes requests to the correct microservice.

```
Client → API Gateway → [Auth Service]
                    → [User Service]  
                    → [Order Service]
                    → [Payment Service]
                    → [LLM Service]
```

**Examples:** AWS API Gateway, Kong, NGINX, Traefik, FastAPI + custom middleware

---

## WHY Use It

Without API Gateway (problems):
- Every service must implement its own auth, rate limiting, logging
- Client knows internal service addresses
- Adding a new service requires client updates

With API Gateway:
| Feature | Without | With Gateway |
|---|---|---|
| Auth | Each service implements | Gateway handles once |
| Rate limiting | Each service | Gateway enforces |
| SSL termination | Each service | Gateway only |
| Load balancing | Client manages | Gateway routes |
| Logging/tracing | Per service | Centralised |
| API versioning | Scattered | Gateway routes /v1 vs /v2 |

---

## HOW — Key Functions

### 1. Request Routing
```
POST /api/v1/users   → User Service :8001
POST /api/v1/orders  → Order Service :8002
POST /api/v1/llm     → LLM Service :8003
```

### 2. Authentication & Authorization
```python
# Gateway validates JWT before forwarding
async def gateway_middleware(request: Request) -> Response:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    
    # Verify token (could call Auth Service or verify locally)
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    request.state.user_id = payload["sub"]
    
    # Forward with user context header
    return await forward_to_service(request, extra_headers={
        "X-User-ID": payload["sub"],
        "X-User-Role": payload["role"],
    })
```

### 3. Rate Limiting
```python
# Gateway-level rate limiting (Redis-backed)
import redis
r = redis.Redis()

def check_rate_limit(user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"rate:{user_id}:{int(time.time()) // window}"
    count = r.incr(key)
    r.expire(key, window)
    return count <= limit
```

### 4. Request/Response Transformation
```python
# Translate between API versions
# Client sends v1 format → Gateway transforms → Service uses v2 format
async def v1_to_v2_transform(request_body: dict) -> dict:
    # v1: {"query": "Hello"}
    # v2: {"messages": [{"role": "user", "content": "Hello"}]}
    return {
        "messages": [{"role": "user", "content": request_body["query"]}],
        "model": "gpt-4o-mini",
    }
```

### 5. Circuit Breaker at Gateway
```python
import asyncio
from enum import Enum, auto

class CircuitState(Enum):
    CLOSED   = auto()   # normal operation
    OPEN     = auto()   # failing → reject all
    HALF_OPEN = auto()  # testing recovery

class CircuitBreaker:
    def __init__(self, threshold: int = 5, timeout: float = 30.0):
        self.threshold = threshold
        self.timeout   = timeout
        self.failures  = 0
        self.state     = CircuitState.CLOSED
        self.last_fail = 0

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_fail > self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit OPEN — service unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self.failures = 0
            self.state = CircuitState.CLOSED
            return result
        except Exception:
            self.failures += 1
            self.last_fail = time.time()
            if self.failures >= self.threshold:
                self.state = CircuitState.OPEN
            raise
```

---

## FastAPI as API Gateway

```python
# gateway/main.py
import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

app = FastAPI(title="API Gateway")

SERVICES = {
    "users":   "http://user-service:8001",
    "orders":  "http://order-service:8002",
    "llm":     "http://llm-service:8003",
}

async def verify_token(request: Request) -> dict:
    """Auth middleware — runs for every request."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    # ... verify JWT ...
    return {"user_id": "user-123", "role": "user"}


@app.api_route("/{service}/{path:path}",
               methods=["GET","POST","PUT","DELETE","PATCH"])
async def proxy(service: str, path: str, request: Request,
                user: dict = Depends(verify_token)):
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    target = f"{SERVICES[service]}/{path}"
    body   = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method  = request.method,
            url     = target,
            headers = {**dict(request.headers),
                       "X-User-ID": user["user_id"],
                       "X-User-Role": user["role"]},
            content = body,
            timeout = 30.0,
        )

    return JSONResponse(
        content    = response.json(),
        status_code = response.status_code,
    )
```

---

## API Gateway vs Load Balancer

| Feature | Load Balancer | API Gateway |
|---|---|---|
| Purpose | Distribute traffic | Route + transform |
| Auth | ❌ No | ✅ Yes |
| Rate limiting | ❌ No | ✅ Yes |
| Protocol | L4 (TCP/UDP) | L7 (HTTP) |
| Business logic | ❌ No | ✅ Yes |
| Example | NGINX upstream | Kong, AWS API GW |

**Typical setup:** Load Balancer → API Gateway → Services

---

## REAL LIFE ANALOGY

API Gateway = **Hotel Concierge**  
You (client) talk to ONE concierge.  
The concierge: verifies who you are (auth), handles your request (routing), ensures you don't abuse services (rate limit), and contacts the right department (service) on your behalf.  
You never directly interact with the kitchen, housekeeping, or maintenance.

---

## Interview Q&A

**Q: What is the difference between API Gateway and Service Mesh?**
A: API Gateway handles **north-south** traffic (client → services). Service Mesh handles **east-west** traffic (service ↔ service). Gateway focuses on external-facing concerns; Service Mesh on internal communication, mTLS, retries.

**Q: What is the single point of failure problem with API Gateway?**
A: If the gateway goes down, all services are unreachable. Mitigate with: multiple gateway instances behind a load balancer, health checks, auto-scaling, and circuit breakers.

**Q: Can an API Gateway do response aggregation?**
A: Yes (BFF pattern — Backend for Frontend). Gateway calls multiple services and merges the response:
`GET /dashboard → calls user-service + order-service + analytics → merges into one response`

**Q: How do you handle API versioning at the gateway?**
A: Route by URL prefix: `/v1/*` → v1 services, `/v2/*` → v2 services. Or use request headers: `API-Version: 2`. Gateway translates and forwards to correct service version.
