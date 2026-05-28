# Lecture 3 — Practical Hands-On: Quality Attributes Code

> **Theory file:** [03_Quality_Attributes.md](03_Quality_Attributes.md)

---

## 🎯 Is Practical Mein Kya Karenge?

Har quality attribute ke liye **working code** likhenge:

1. **📈 Scalability** — horizontal scale config, stateless services, sharding
2. **⚡ Performance** — caching (Redis), connection pooling, async, query optimization
3. **✅ Availability** — circuit breakers, health checks, retries, failover
4. **🔒 Security** — auth (JWT), rate limiting, input validation, encryption
5. **🔧 Maintainability** — clean code, testing, monitoring

Plus **measurement tools** — kaise validate karein ki quality attribute achieve ho rahi hai.

---

## 1. 📈 Scalability — Practical Code

### A. Stateless FastAPI Service (Horizontal Scaling-Ready)

**Why stateless?** Multiple replicas should be interchangeable. No session in memory.

```python
# ❌ BAD — stateful (can't scale horizontally)
from fastapi import FastAPI

app = FastAPI()
user_sessions = {}  # in-memory state ← BREAKS multiple replicas!

@app.post("/login")
async def login(user_id: int):
    token = generate_token()
    user_sessions[token] = user_id  # ❌ Only this replica knows!
    return {"token": token}


# ✅ GOOD — stateless via Redis
import redis.asyncio as aioredis

redis = aioredis.from_url("redis://redis:6379")

@app.post("/login")
async def login(user_id: int):
    token = generate_token()
    await redis.setex(f"session:{token}", 3600, str(user_id))
    return {"token": token}

@app.get("/me")
async def me(token: str):
    user_id = await redis.get(f"session:{token}")  # Any replica can read
    if not user_id:
        raise HTTPException(401)
    return {"user_id": int(user_id)}
```

### B. Horizontal Scaling Config (Kubernetes HPA)

```yaml
# k8s/order-service-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3      # always at least 3
  maxReplicas: 50     # scale up to 50 on demand
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70   # scale when CPU > 70%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_pod
      target:
        type: AverageValue
        averageValue: "1000"     # scale when > 1000 req/sec per pod
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60     # wait 60s before scaling up again
      policies:
      - type: Percent
        value: 50                          # max 50% increase per minute
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300    # wait 5 min before scaling down
      policies:
      - type: Pods
        value: 2                           # max 2 pods removed per minute
        periodSeconds: 60
```

### C. Database Sharding by User ID

```python
# src/db/sharding.py
import hashlib
import asyncpg
from typing import Optional


class ShardedDB:
    """
    Shard PostgreSQL by user_id.
    Each shard is a separate PostgreSQL instance.
    """

    def __init__(self, shard_urls: list[str]):
        """
        shard_urls: ['postgres://shard0', 'postgres://shard1', ...]
        """
        self.shard_urls = shard_urls
        self.num_shards = len(shard_urls)
        self.pools: dict[int, asyncpg.Pool] = {}

    async def initialize(self):
        for i, url in enumerate(self.shard_urls):
            self.pools[i] = await asyncpg.create_pool(url, min_size=10, max_size=50)

    def get_shard_id(self, user_id: int) -> int:
        """Consistent hashing to pick shard."""
        # Hash user_id
        hash_val = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16)
        return hash_val % self.num_shards

    def get_pool(self, user_id: int) -> asyncpg.Pool:
        shard_id = self.get_shard_id(user_id)
        return self.pools[shard_id]

    async def fetch_user(self, user_id: int) -> Optional[dict]:
        pool = self.get_pool(user_id)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id,
            )
            return dict(row) if row else None

    async def insert_user(self, user_id: int, data: dict):
        pool = self.get_pool(user_id)
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (id, name, email) VALUES ($1, $2, $3)",
                user_id, data["name"], data["email"],
            )


# Usage
db = ShardedDB([
    "postgres://shard0.acme.com/users",
    "postgres://shard1.acme.com/users",
    "postgres://shard2.acme.com/users",
    "postgres://shard3.acme.com/users",
])

await db.initialize()
user = await db.fetch_user(user_id=12345)  # Auto-routed to right shard
```

### D. Async Worker for Write Scalability

```python
# src/workers/order_processor.py
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import json
import asyncio
import logging


class OrderEventProcessor:
    """
    Consume order events from Kafka, process async.
    Multiple worker instances can run in parallel.
    """

    def __init__(self, kafka_bootstrap: str):
        self.consumer = AIOKafkaConsumer(
            "order.created",
            bootstrap_servers=kafka_bootstrap,
            group_id="order-processor",       # consumer group for parallelism
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode()),
            enable_auto_commit=False,
        )
        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_bootstrap,
            value_serializer=lambda m: json.dumps(m).encode(),
        )
        self.logger = logging.getLogger(__name__)

    async def start(self):
        await self.consumer.start()
        await self.producer.start()

        try:
            async for msg in self.consumer:
                try:
                    await self._process(msg.value)
                    await self.consumer.commit()
                except Exception as e:
                    self.logger.exception("Processing failed")
                    # DLQ: dead letter queue
                    await self.producer.send_and_wait(
                        "order.dlq",
                        {"error": str(e), "original": msg.value},
                    )
                    await self.consumer.commit()
        finally:
            await self.consumer.stop()
            await self.producer.stop()

    async def _process(self, order: dict):
        # Process order asynchronously
        # Multiple workers process different orders in parallel
        # (Kafka partitions distribute the load)
        ...


# Deploy 10 workers; Kafka splits orders across them
if __name__ == "__main__":
    processor = OrderEventProcessor("kafka:9092")
    asyncio.run(processor.start())
```

---

## 2. ⚡ Performance — Practical Code

### A. Multi-Layer Caching

```python
# src/cache/layered_cache.py
from functools import lru_cache
import redis.asyncio as aioredis
import json
from typing import Optional


class LayeredCache:
    """
    L1 (in-process LRU) → L2 (Redis distributed) → DB

    Hit rates:
      L1: 60% (ultra-fast, single pod)
      L2: 30% (fast, all pods)
      Miss: 10% → DB
    """

    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url)
        # L1 cache is just an LRU dict (process-local)
        self._l1: dict[str, tuple[any, float]] = {}
        self._l1_max_size = 10000

    async def get(self, key: str) -> Optional[any]:
        # L1: in-process
        if key in self._l1:
            value, _ = self._l1[key]
            return value

        # L2: Redis (distributed)
        cached = await self.redis.get(key)
        if cached:
            value = json.loads(cached)
            self._set_l1(key, value)  # Populate L1
            return value

        return None

    async def set(self, key: str, value: any, ttl_seconds: int = 300):
        # Set in both layers
        self._set_l1(key, value)
        await self.redis.setex(key, ttl_seconds, json.dumps(value))

    async def delete(self, key: str):
        self._l1.pop(key, None)
        await self.redis.delete(key)

    def _set_l1(self, key: str, value: any):
        import time
        # Simple LRU eviction
        if len(self._l1) >= self._l1_max_size:
            # Remove oldest
            oldest_key = min(self._l1, key=lambda k: self._l1[k][1])
            del self._l1[oldest_key]
        self._l1[key] = (value, time.time())


# Usage
cache = LayeredCache("redis://redis:6379")

async def get_user(user_id: int) -> dict:
    # Try cache first
    user = await cache.get(f"user:{user_id}")
    if user:
        return user

    # Cache miss → DB
    user = await db.fetch_user(user_id)
    if user:
        await cache.set(f"user:{user_id}", user, ttl_seconds=600)

    return user
```

### B. Connection Pooling

```python
# src/db/pool.py
import asyncpg
from contextlib import asynccontextmanager

# Singleton pool — reused across requests
_pool: asyncpg.Pool = None


async def init_pool(database_url: str):
    global _pool
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=10,        # always 10 connections ready
        max_size=50,        # cap at 50 to not overwhelm DB
        max_inactive_connection_lifetime=300,
        command_timeout=10,
    )


@asynccontextmanager
async def get_connection():
    async with _pool.acquire() as conn:
        yield conn


# Without pool: TCP handshake every query = 50-100ms overhead
# With pool: < 1ms acquisition from pool
```

### C. Async Parallel Calls (Latency Optimization)

```python
# src/services/dashboard_service.py
import asyncio
import time
import logging


class DashboardService:
    """Show how to parallelize external calls."""

    def __init__(self, user_svc, order_svc, recommendation_svc, notification_svc):
        self.user_svc = user_svc
        self.order_svc = order_svc
        self.recommendation_svc = recommendation_svc
        self.notification_svc = notification_svc
        self.logger = logging.getLogger(__name__)

    async def get_dashboard(self, user_id: int) -> dict:
        """
        SEQUENTIAL: 400ms (100 + 150 + 100 + 50)
        PARALLEL:   150ms (max of all calls)
        """
        start = time.time()

        # All 4 calls run in parallel!
        results = await asyncio.gather(
            self.user_svc.get_user(user_id),
            self.order_svc.get_recent_orders(user_id),
            self.recommendation_svc.get_recommendations(user_id),
            self.notification_svc.get_unread_count(user_id),
            return_exceptions=True,  # one failure doesn't kill others
        )

        user, orders, recs, unread = results

        elapsed = (time.time() - start) * 1000
        self.logger.info(f"Dashboard fetched in {elapsed:.0f}ms")

        return {
            "user": user if not isinstance(user, Exception) else None,
            "recent_orders": orders if not isinstance(orders, Exception) else [],
            "recommendations": recs if not isinstance(recs, Exception) else [],
            "unread_notifications": unread if not isinstance(unread, Exception) else 0,
            "degraded": any(isinstance(r, Exception) for r in results),
        }
```

### D. Database Query Optimization

```sql
-- BAD: Full table scan
SELECT * FROM orders WHERE customer_email = 'user@example.com';

-- Solution 1: Add index
CREATE INDEX idx_orders_customer_email ON orders(customer_email);

-- After index: 100ms → 1ms

-- BAD: N+1 query
SELECT * FROM users LIMIT 100;
-- Then for each user:
SELECT * FROM orders WHERE user_id = ?

-- GOOD: Single JOIN
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
LIMIT 100;

-- GOOD: Or DataLoader pattern in code
async def get_users_with_orders(user_ids: list[int]):
    # Batch fetch users
    users = await db.fetch_all(
        "SELECT * FROM users WHERE id = ANY($1)",
        user_ids,
    )

    # Batch fetch orders
    orders = await db.fetch_all(
        "SELECT * FROM orders WHERE user_id = ANY($1)",
        user_ids,
    )

    # Group orders by user_id in memory
    orders_by_user = {}
    for o in orders:
        orders_by_user.setdefault(o["user_id"], []).append(o)

    # Combine
    return [
        {"user": u, "orders": orders_by_user.get(u["id"], [])}
        for u in users
    ]
```

### E. Performance Monitoring Middleware

```python
# src/middleware/performance.py
import time
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    # Record metrics
    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()

    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)

    # Log slow requests
    if duration > 1.0:
        logging.warning(f"SLOW: {request.method} {request.url.path} = {duration:.2f}s")

    return response


# Mount as middleware
app = FastAPI()
app.middleware("http")(metrics_middleware)


@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

## 3. ✅ Availability — Practical Code

### A. Circuit Breaker

```python
# src/resilience/circuit_breaker.py
import time
import asyncio
from enum import Enum
from typing import Callable
import logging


class CircuitState(Enum):
    CLOSED = "closed"       # normal operation
    OPEN = "open"           # failing, requests blocked
    HALF_OPEN = "half_open" # testing recovery


class CircuitBreaker:
    """
    Prevents cascading failures when downstream is broken.

    State machine:
      CLOSED → (failures > threshold) → OPEN
      OPEN → (after timeout) → HALF_OPEN
      HALF_OPEN → success → CLOSED
      HALF_OPEN → failure → OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.logger = logging.getLogger(__name__)

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.logger.info("Circuit transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpen(f"Circuit is OPEN. Try after {self.recovery_timeout}s")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        if self.state != CircuitState.CLOSED:
            self.logger.info("Circuit CLOSED (recovered)")
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.logger.warning(f"Circuit OPEN after {self.failure_count} failures")
            self.state = CircuitState.OPEN


class CircuitBreakerOpen(Exception):
    pass


# Usage
payment_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=httpx.HTTPStatusError,
)


async def charge_payment(amount: float):
    """Wrapped in circuit breaker."""
    return await payment_breaker.call(
        lambda: stripe_api.charge(amount),
    )
```

### B. Retry with Exponential Backoff

```python
# src/resilience/retry.py
import asyncio
import logging
from typing import Callable
from functools import wraps


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Retry async function with exponential backoff.

    Attempt 1: immediate
    Attempt 2: 1s delay
    Attempt 3: 2s delay
    Attempt 4: 4s delay (capped at max_delay)
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e

                    if attempt == max_attempts:
                        logging.error(f"Max attempts reached for {func.__name__}")
                        raise

                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    # Add jitter to avoid thundering herd
                    import random
                    delay = delay * (0.5 + random.random())

                    logging.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

            raise last_exc

        return wrapper

    return decorator


# Usage
@retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(httpx.HTTPError,))
async def call_external_api(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
```

### C. Health Checks

```python
# src/health/checks.py
from enum import Enum
from typing import Dict
from fastapi import FastAPI, status as http_status
from fastapi.responses import JSONResponse


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    def __init__(self):
        self.checks: Dict[str, callable] = {}

    def register(self, name: str, check_func: callable):
        self.checks[name] = check_func

    async def check_all(self) -> Dict:
        results = {}
        statuses = []

        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": HealthStatus.HEALTHY,
                    "details": result,
                }
                statuses.append(HealthStatus.HEALTHY)
            except Exception as e:
                results[name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(e),
                }
                statuses.append(HealthStatus.UNHEALTHY)

        # Determine overall status
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            # Critical service down
            critical_unhealthy = any(
                results[name]["status"] == HealthStatus.UNHEALTHY
                for name in ["db_primary", "auth"]  # critical deps
                if name in results
            )
            overall = HealthStatus.UNHEALTHY if critical_unhealthy else HealthStatus.DEGRADED
        else:
            overall = HealthStatus.DEGRADED

        return {
            "status": overall,
            "checks": results,
        }


health = HealthChecker()


# Register checks
async def check_database():
    async with db_pool.acquire() as conn:
        await conn.execute("SELECT 1")
    return {"latency_ms": 5}


async def check_redis():
    await redis.ping()
    return {"connected": True}


async def check_kafka():
    # Check Kafka connectivity
    return {"brokers": 3}


health.register("db_primary", check_database)
health.register("redis", check_redis)
health.register("kafka", check_kafka)


# K8s liveness probe: am I alive?
@app.get("/health/live")
async def liveness():
    """Always returns OK if process is running."""
    return {"status": "alive"}


# K8s readiness probe: ready for traffic?
@app.get("/health/ready")
async def readiness():
    """Check dependencies — only return ready if can serve requests."""
    result = await health.check_all()
    if result["status"] == HealthStatus.HEALTHY:
        return result
    elif result["status"] == HealthStatus.DEGRADED:
        return JSONResponse(result, status_code=http_status.HTTP_200_OK)
    else:
        return JSONResponse(result, status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE)


# Deep health check (for ops debugging)
@app.get("/health/deep")
async def deep_health():
    return await health.check_all()
```

### D. Kubernetes Readiness/Liveness Probes

```yaml
# k8s/order-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: order-service
        image: acme/order-service:latest
        ports:
        - containerPort: 8000

        # Liveness: K8s restarts container if this fails
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3   # 30s before restart

        # Readiness: K8s removes from LB if this fails
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 1   # remove from LB immediately on fail
          successThreshold: 1
```

---

## 4. 🔒 Security — Practical Code

### A. JWT Authentication

```python
# src/auth/jwt_auth.py
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


JWT_SECRET = "your-secret-key-from-vault"  # In production, from env/vault
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 30


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str


def create_access_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "iat": datetime.now(timezone.utc),
        "iss": "acme.com",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenData(
            user_id=int(payload["sub"]),
            email=payload["email"],
            role=payload["role"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")


bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    """FastAPI dependency to inject authenticated user."""
    return verify_token(credentials.credentials)


# Usage
@app.get("/protected")
async def protected_route(user: TokenData = Depends(get_current_user)):
    return {"message": f"Hello {user.email}"}
```

### B. Role-Based Authorization

```python
# src/auth/rbac.py
from functools import wraps
from fastapi import HTTPException, Depends, status


def require_role(*allowed_roles: str):
    """Decorator to enforce role-based access."""

    def dependency(user: TokenData = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Required role: {allowed_roles}, your role: {user.role}",
            )
        return user

    return dependency


# Usage
@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: TokenData = Depends(require_role("admin", "super_admin")),
):
    # Only admins can call this
    ...


@app.get("/admin/reports")
async def admin_reports(admin: TokenData = Depends(require_role("admin"))):
    ...
```

### C. Rate Limiting

```python
# src/security/rate_limit.py
from fastapi import Request, HTTPException, status
import redis.asyncio as aioredis
import time


redis = aioredis.from_url("redis://redis:6379")


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        key_prefix: str = "ratelimit",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    async def check(self, identifier: str) -> bool:
        """Returns True if allowed, raises HTTPException if rate limited."""
        key = f"{self.key_prefix}:{identifier}"
        now = int(time.time())
        window_start = now - self.window_seconds

        # Use Redis sorted set as sliding window
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)  # remove old entries
        pipe.zadd(key, {str(now): now})              # add current request
        pipe.zcard(key)                               # count requests in window
        pipe.expire(key, self.window_seconds)
        results = await pipe.execute()

        request_count = results[2]

        if request_count > self.max_requests:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.max_requests} per {self.window_seconds}s",
                headers={"Retry-After": str(self.window_seconds)},
            )

        return True


# Per-IP rate limit
ip_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Per-user rate limit
user_limiter = RateLimiter(max_requests=1000, window_seconds=60, key_prefix="ratelimit:user")

# Per-endpoint rate limit (more strict)
login_limiter = RateLimiter(max_requests=5, window_seconds=60, key_prefix="ratelimit:login")


# As middleware
async def rate_limit_middleware(request: Request, call_next):
    # Per IP
    ip = request.client.host
    await ip_limiter.check(ip)

    response = await call_next(request)
    return response


app.middleware("http")(rate_limit_middleware)


# Per-endpoint
@app.post("/login")
async def login(request: Request):
    await login_limiter.check(request.client.host)
    # Process login
    ...
```

### D. Input Validation with Pydantic

```python
# src/models/user_input.py
from pydantic import BaseModel, EmailStr, Field, validator
import re


class UserRegistration(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = None

    @validator("password")
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must have uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must have lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must have digit")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("Password must have special character")
        return v

    @validator("name")
    def name_no_html(cls, v):
        if re.search(r"[<>]", v):
            raise ValueError("Name cannot contain HTML")
        return v

    @validator("phone")
    def valid_phone(cls, v):
        if v and not re.match(r"^\+?\d{10,15}$", v):
            raise ValueError("Invalid phone number")
        return v


# Pydantic auto-validates on FastAPI endpoint
@app.post("/users/register")
async def register(user: UserRegistration):
    # If we reach here, input is validated
    ...
```

### E. PII Encryption at Rest

```python
# src/security/encryption.py
from cryptography.fernet import Fernet
import os
import base64


class PIIEncryption:
    """Encrypt PII fields before storing in DB."""

    def __init__(self, key: bytes = None):
        if key is None:
            key = os.environ.get("PII_ENCRYPTION_KEY", "").encode()
            if not key:
                raise ValueError("PII_ENCRYPTION_KEY not set")
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> str:
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        return self.cipher.decrypt(encrypted).decode()


# Usage in SQLAlchemy model
from sqlalchemy import Column, String, Integer
from sqlalchemy.types import TypeDecorator


pii = PIIEncryption()


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that encrypts on write, decrypts on read."""
    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return pii.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return pii.decrypt(value)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    name = Column(EncryptedString(500))      # encrypted!
    phone = Column(EncryptedString(50))      # encrypted!
    aadhaar_last_4 = Column(EncryptedString(20))


# In DB: ciphertext
# In Python: plaintext (auto-decrypt on read)
```

---

## 5. 🔧 Maintainability — Practical Code

### A. Structured Logging

```python
# src/logging_config.py
import logging
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON logs for easy parsing."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "order-service",
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.pathname,
            "line": record.lineno,
        }

        # Add extra context
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO"):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


# Usage
import logging
logger = logging.getLogger(__name__)

logger.info(
    "Order created",
    extra={"user_id": 42, "order_id": "abc", "duration_ms": 150},
)
```

### B. Dependency Injection (Testability)

```python
# src/dependencies.py
from fastapi import Depends
from typing import Annotated


# Define interfaces (Protocols)
from typing import Protocol


class OrderRepositoryProtocol(Protocol):
    async def save(self, order): ...
    async def get(self, order_id): ...


class PaymentClientProtocol(Protocol):
    async def charge(self, amount, customer): ...


# Production implementations
class PostgresOrderRepository:
    def __init__(self, pool):
        self.pool = pool

    async def save(self, order):
        # PostgreSQL implementation
        ...


class HTTPPaymentClient:
    def __init__(self, base_url):
        self.base_url = base_url

    async def charge(self, amount, customer):
        # Real HTTP call
        ...


# FastAPI dependency providers
async def get_order_repository() -> OrderRepositoryProtocol:
    return PostgresOrderRepository(pool=app.state.pool)


async def get_payment_client() -> PaymentClientProtocol:
    return HTTPPaymentClient(base_url="http://payment-service")


# Endpoint uses interfaces (not concrete classes)
@app.post("/orders")
async def create_order(
    repo: Annotated[OrderRepositoryProtocol, Depends(get_order_repository)],
    payment: Annotated[PaymentClientProtocol, Depends(get_payment_client)],
):
    ...


# Tests can use mocks
async def test_create_order():
    mock_repo = AsyncMock(spec=OrderRepositoryProtocol)
    mock_payment = AsyncMock(spec=PaymentClientProtocol)

    # Override dependencies in test
    app.dependency_overrides[get_order_repository] = lambda: mock_repo
    app.dependency_overrides[get_payment_client] = lambda: mock_payment

    # Test as normal
    response = await client.post("/orders", json={...})
    assert response.status_code == 200
```

### C. Comprehensive Testing

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db():
    """Test database (uses transactions, rolls back)."""
    async with test_db_pool.acquire() as conn:
        async with conn.transaction(force_rollback=True):
            yield conn


# tests/unit/test_order_service.py
@pytest.mark.asyncio
async def test_create_order_idempotent():
    """Same idempotency key → same result."""
    mock_repo = AsyncMock()
    mock_payment = AsyncMock()
    service = OrderService(mock_repo, mock_payment)

    # First call
    order1 = await service.create_order(
        customer_id=1, restaurant_id=10, items=[],
        delivery_address="addr", payment_method="upi",
        idempotency_key="abc-123",
    )

    # Second call with same key
    mock_repo.get_by_idempotency_key.return_value = order1
    order2 = await service.create_order(
        customer_id=1, restaurant_id=10, items=[],
        delivery_address="addr", payment_method="upi",
        idempotency_key="abc-123",
    )

    assert order1.id == order2.id
    # Payment NOT charged twice
    mock_payment.charge.assert_called_once()


# tests/integration/test_orders_api.py
@pytest.mark.asyncio
async def test_create_order_full_flow(client, db):
    response = await client.post(
        "/orders",
        json={
            "customer_id": 1,
            "restaurant_id": 100,
            "items": [{"product_id": 1, "quantity": 2, "price": 250}],
            "delivery_address": "Mumbai",
            "payment_method": "upi",
        },
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "confirmed"

    # Verify in DB
    db_order = await db.fetchrow("SELECT * FROM orders WHERE id = $1", data["order_id"])
    assert db_order["total_amount"] == 500
```

---

## 6. Quality Attribute Measurement Tools

### A. Load Testing (k6)

```javascript
// load-tests/order-creation.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '1m', target: 100 },   // ramp up
        { duration: '3m', target: 500 },   // sustain
        { duration: '1m', target: 0 },     // ramp down
    ],
    thresholds: {
        // SLA: p95 < 500ms
        http_req_duration: ['p(95)<500', 'p(99)<2000'],
        // Error rate < 1%
        http_req_failed: ['rate<0.01'],
    },
};

export default function () {
    const payload = JSON.stringify({
        customer_id: Math.floor(Math.random() * 10000),
        restaurant_id: 100,
        items: [{product_id: 1, quantity: 1, price: 250}],
        delivery_address: "Mumbai",
        payment_method: "upi",
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token',
        },
    };

    const res = http.post('http://localhost:8000/orders', payload, params);

    check(res, {
        'status is 201': (r) => r.status === 201,
        'response time OK': (r) => r.timings.duration < 500,
    });

    sleep(1);
}

// Run: k6 run load-tests/order-creation.js
```

### B. Security Scanning (Bandit)

```bash
# Install
pip install bandit

# Scan
bandit -r src/ -f json -o security-report.json

# CI integration (GitHub Actions)
- name: Security scan
  run: |
    pip install bandit
    bandit -r src/ -ll
```

### C. Code Quality (Ruff + MyPy)

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"
select = ["E", "F", "I", "W", "B", "C4", "UP", "ASYNC"]

[tool.mypy]
python_version = "3.12"
strict = true
disallow_untyped_defs = true
no_implicit_optional = true
```

### D. Monitoring Dashboard (Grafana)

```yaml
# monitoring/grafana-dashboards/quality-attributes.json
{
  "panels": [
    {
      "title": "Performance: p95 Latency",
      "targets": [{
        "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
      }]
    },
    {
      "title": "Availability: Success Rate",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=~\"2..\"}[5m])) / sum(rate(http_requests_total[5m]))"
      }]
    },
    {
      "title": "Scalability: Active Pods",
      "targets": [{
        "expr": "count(up{job=\"order-service\"})"
      }]
    },
    {
      "title": "Security: Auth Failures",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=\"401\"}[5m]))"
      }]
    }
  ]
}
```

---

## 7. Summary

```
Quality Attribute    | Practical Code
─────────────────────────────────────
📈 Scalability       | Stateless services + Redis sessions
                     | Sharding by user_id (consistent hashing)
                     | K8s HPA with CPU/memory metrics
                     | Async workers (Kafka consumers)

⚡ Performance       | Multi-layer cache (L1 + L2 + DB)
                     | Connection pooling (asyncpg)
                     | Parallel async calls (asyncio.gather)
                     | DB indexes + DataLoader pattern

✅ Availability      | Circuit breaker
                     | Retry with backoff + jitter
                     | K8s health checks (liveness + readiness)
                     | Graceful degradation

🔒 Security          | JWT auth + RBAC
                     | Rate limiting (sliding window)
                     | Pydantic input validation
                     | PII encryption at rest

🔧 Maintainability   | Structured JSON logs
                     | Dependency injection (testable)
                     | Comprehensive tests
                     | Code quality tools (ruff, mypy)
```

### Action Items

1. ✅ **Add Redis caching** to one of your existing endpoints
2. ✅ **Add circuit breaker** to an external API call
3. ✅ **Add JWT auth** to a route
4. ✅ **Write 1 load test** with k6
5. ✅ **Set up Prometheus metrics**

---

## 8. Related Resources

- [00_Year0-2_Junior/09_Caching/](../../../00_Year0-2_Junior/09_Caching) — Caching deep
- [01_Year3-4_Mid/03_Security/](../../../01_Year3-4_Mid/03_Security) — Security patterns
- [00_Year0-2_Junior/06_FastAPI/06_security_jwt_rbac.md](../../../00_Year0-2_Junior/06_FastAPI/06_security_jwt_rbac.md) — JWT + RBAC
- [00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md](../../../00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md) — Load testing
- [01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md](../../../01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md) — Monitoring
