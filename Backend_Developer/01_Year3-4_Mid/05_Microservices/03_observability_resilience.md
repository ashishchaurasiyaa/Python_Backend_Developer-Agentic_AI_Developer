# Microservices — Observability & Resilience Patterns
**Advanced | What, Why, How**

---

## Quick Concepts

| Term | Hinglish Explanation |
|------|----------------------|
| **Observability** | System ke andar kya ho raha hai — bahar se samajhna. Logs + Metrics + Traces = teen pillars |
| **OpenTelemetry** | Vendor-neutral observability standard — ek hi code se Jaeger, Zipkin, Grafana — sab pe bhej do |
| **Distributed Tracing** | Ek request ka ek service se dusri service tak ka poora path track karo |
| **Trace ID** | Ek request ka unique ID — saari services mein same rahega, request end tak |
| **Span** | Ek operation ka time measurement — one service call = one span |
| **Health Check** | Service alive hai kya? Ready hai kya? Kubernetes poochta hai |
| **Bulkhead** | Thread pool isolation — ek service fail ho jaaye toh baaki services safe rahein |
| **Retry with Backoff** | Failed call → thoda wait karo → dobara try karo (har baar wait badhao) |
| **Timeout** | Zyada wait mat karo — fixed time ke baad fast fail karo |
| **Circuit Breaker** | Baar baar fail ho rahi service ko calls karna band karo — electric circuit ki tarah |

---

## Section A — Three Pillars of Observability

### 1. Structured Logging

Plain text logs useless hote hain distributed systems mein. Structured logs (JSON) machine-parseable hote hain — Elasticsearch, Loki mein index ho sakte hain.

```python
import structlog
import logging
import uuid
import time
from fastapi import FastAPI, Request, Response

# structlog setup
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,      # request-level context automatically merge
        structlog.processors.add_log_level,            # level field add karo
        structlog.processors.TimeStamper(fmt="iso"),   # timestamp ISO format mein
        structlog.dev.ConsoleRenderer()                # Dev mein pretty print, Production mein JSONRenderer
    ]
)

logger = structlog.get_logger()

app = FastAPI()

# Structured log — key-value pairs, not plain strings
logger.info(
    "order.created",
    order_id=12345,
    user_id=456,
    amount=5000,
    service="order-service",
    trace_id="abc123"  # distributed tracing ke liye — same across services
)

# FastAPI middleware for request logging
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

    # Context mein bind karo — is request ke sab logs mein automatically aayega
    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        path=request.url.path,
        method=request.method,
    )

    start = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        logger.info("request.completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2)
        )
        response.headers["X-Trace-ID"] = trace_id
        return response
    except Exception as e:
        logger.error("request.failed", error=str(e))
        raise
    finally:
        structlog.contextvars.clear_contextvars()  # next request ke liye clean karo
```

**Key points:**
- `merge_contextvars` — `bind_contextvars()` se bind kiya trace_id har log mein automatically aayega
- Production mein `JSONRenderer` use karo — Loki/Elasticsearch parse kar sake
- Log event name `"order.created"` style use karo — searchable aur consistent

---

### 2. Metrics with Prometheus

Metrics = numbers over time. Graphs banao, alerts set karo. Prometheus pull-based hai — service `/metrics` endpoint expose karo, Prometheus scrape karega.

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
import time

app = FastAPI()

# Counter — sirf badhta hai (requests, errors)
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['service', 'method', 'endpoint', 'status_code']
)

# Histogram — distribution measure karo (latency, size)
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['service', 'method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Gauge — up/down dono ja sakta hai (active connections, queue size)
ACTIVE_REQUESTS = Gauge(
    'active_requests',
    'Currently processing requests',
    ['service']
)

DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['service', 'query_type']
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    service = "order-service"
    endpoint = request.url.path

    ACTIVE_REQUESTS.labels(service=service).inc()
    start = time.time()

    response = await call_next(request)

    duration = time.time() - start
    REQUEST_COUNT.labels(
        service=service,
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code
    ).inc()
    REQUEST_DURATION.labels(
        service=service,
        method=request.method,
        endpoint=endpoint
    ).observe(duration)
    ACTIVE_REQUESTS.labels(service=service).dec()

    return response

# Prometheus yahan se scrape karega
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**Metric Types:**

| Type | Use Case | Example |
|------|----------|---------|
| **Counter** | Sirf increase (never reset) | total requests, total errors |
| **Gauge** | Up/down dono | active connections, memory usage |
| **Histogram** | Distribution + percentiles | request latency, response size |
| **Summary** | Client-side percentiles | pre-calculated p99 |

**Useful Prometheus Queries (PromQL):**
```promql
# Request rate per second (last 5 min)
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m])

# 99th percentile latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

---

### 3. Distributed Tracing with OpenTelemetry

Ek user request multiple services se hokar jaati hai. Tracing batata hai: kahan time laga, kahan fail hua, kaise services ek doosre ko call karti hain.

```python
# pip install opentelemetry-sdk opentelemetry-instrumentation-fastapi
# pip install opentelemetry-exporter-jaeger

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import inject, extract
import httpx

# Tracer provider setup — Jaeger ko spans bhejo
provider = TracerProvider()
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# FastAPI aur HTTPX auto-instrument — manually kuch nahi karna
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

# Manual spans — business logic ke liye
@app.post("/orders")
async def create_order(order: OrderCreate):
    with tracer.start_as_current_span("create_order") as span:
        # Span pe attributes set karo — Jaeger UI mein dikhenge
        span.set_attribute("order.product_id", order.product_id)
        span.set_attribute("order.quantity", order.quantity)

        # Child span — DB operation ke liye
        with tracer.start_as_current_span("db.insert_order"):
            result = await db.execute(insert_query)
            span.set_attribute("order.id", result.id)

        # Child span — event publish ke liye
        with tracer.start_as_current_span("event.publish"):
            await publish_event("order.placed", result.dict())

        return result

# Trace context propagation — service se service tak trace_id carry karo
async def call_inventory_service(product_id: int):
    headers = {}
    inject(headers)  # Current trace context ko outgoing headers mein inject karo

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://inventory-service/products/{product_id}",
            headers=headers  # Trace context doosri service ko milega
        )
    return response.json()
```

**Trace Hierarchy:**
```
Trace ID: abc-123
├── Span: POST /orders           [order-service]    0ms → 150ms
│   ├── Span: db.insert_order   [order-service]   10ms → 40ms
│   ├── Span: GET /inventory    [inventory-service] 45ms → 90ms
│   │   └── Span: db.select     [inventory-service] 47ms → 85ms
│   └── Span: event.publish     [order-service]   95ms → 110ms
```

---

## Section B — Health Checks

Kubernetes do types ke probes use karta hai:
- **Liveness**: Service alive hai? Agar fail → container restart karo
- **Readiness**: Service traffic le sakti hai? Agar fail → load balancer se remove karo

```python
from enum import Enum
from dataclasses import dataclass
import asyncio
import json
import time

class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"    # Kuch components slow/partial
    UNHEALTHY = "unhealthy"   # Critical component down

@dataclass
class ComponentHealth:
    name:       str
    status:     HealthStatus
    message:    str   = ""
    latency_ms: float = 0.0

async def check_database() -> ComponentHealth:
    try:
        start = time.time()
        await db.execute("SELECT 1")
        latency = (time.time() - start) * 1000
        return ComponentHealth("database", HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as e:
        return ComponentHealth("database", HealthStatus.UNHEALTHY, str(e))

async def check_redis() -> ComponentHealth:
    try:
        start = time.time()
        await redis.ping()
        latency = (time.time() - start) * 1000
        return ComponentHealth("redis", HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as e:
        return ComponentHealth("redis", HealthStatus.UNHEALTHY, str(e))

async def check_rabbitmq() -> ComponentHealth:
    try:
        import aio_pika
        conn = await aio_pika.connect_robust("amqp://localhost/", timeout=2)
        await conn.close()
        return ComponentHealth("rabbitmq", HealthStatus.HEALTHY)
    except Exception as e:
        return ComponentHealth("rabbitmq", HealthStatus.UNHEALTHY, str(e))

@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe — am I alive? (restart if fails)"""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe — am I ready for traffic? (remove from LB if fails)"""
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_rabbitmq(),
    )

    overall = HealthStatus.HEALTHY
    for check in checks:
        if check.status == HealthStatus.UNHEALTHY:
            overall = HealthStatus.UNHEALTHY
            break
        elif check.status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
            overall = HealthStatus.DEGRADED

    status_code = 200 if overall != HealthStatus.UNHEALTHY else 503

    return Response(
        content=json.dumps({
            "status": overall,
            "components": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2)
                }
                for c in checks
            ]
        }),
        status_code=status_code,
        media_type="application/json"
    )
```

---

## Section C — Resilience Patterns

### Retry with Exponential Backoff

```python
import asyncio
import random
from functools import wraps
import httpx

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    jitter: bool = True
):
    """
    Exponential backoff:
    Attempt 1 fail → wait 1s
    Attempt 2 fail → wait 2s
    Attempt 3 fail → wait 4s
    Jitter: random noise add karo — thundering herd problem avoid karo
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        raise  # Last attempt — ab raise karo

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        delay += random.uniform(0, delay * 0.1)  # 10% jitter

                    print(f"Retry {attempt+1}/{max_retries} after {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(httpx.HTTPError,))
async def call_payment_service(amount: float) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://payment-service/charge",
            json={"amount": amount},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
```

---

### Bulkhead Pattern

```python
import asyncio
from asyncio import Semaphore

class BulkheadExecutor:
    """
    Ship mein bulkheads hote hain — ek compartment mein paani bhar jaaye
    toh poora ship nahi doobta.

    Yahan: ek service ke saare concurrent slots bhar jaayein
    toh doosri services affect nahi hoti.
    """
    def __init__(self):
        self._semaphores: dict[str, Semaphore] = {}

    def get_semaphore(self, service_name: str, max_concurrent: int = 10) -> Semaphore:
        if service_name not in self._semaphores:
            self._semaphores[service_name] = Semaphore(max_concurrent)
        return self._semaphores[service_name]

    async def call(self, service_name: str, coro, max_concurrent: int = 10):
        semaphore = self.get_semaphore(service_name, max_concurrent)
        async with semaphore:
            return await coro

bulkhead = BulkheadExecutor()

@app.get("/dashboard")
async def dashboard():
    # User service mein zyada concurrent calls allow — less critical
    # Payment service mein kam — sensitive, protect karo
    users, payments = await asyncio.gather(
        bulkhead.call("user-service",    get_user_data(),    max_concurrent=10),
        bulkhead.call("payment-service", get_payment_data(), max_concurrent=5),
    )
    return {"users": users, "payments": payments}
```

---

### Timeout Pattern

```python
from fastapi import HTTPException

async def call_with_timeout(coro, timeout_seconds: float = 5.0, service_name: str = "unknown"):
    """
    Slow service ka indefinitely wait mat karo.
    Fast fail karo — user ko meaningful error do.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"{service_name} did not respond within {timeout_seconds}s"
        )

# Usage
result = await call_with_timeout(
    call_inventory_service(product_id=123),
    timeout_seconds=3.0,
    service_name="inventory-service"
)
```

---

### Circuit Breaker Pattern

```python
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED    = "CLOSED"     # Normal — sab calls allow
    OPEN      = "OPEN"       # Failure — sab calls block (fast fail)
    HALF_OPEN = "HALF_OPEN"  # Testing — ek call allow karo, dekho recover hua?

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30, success_threshold=2):
        self.failure_threshold  = failure_threshold   # Kitne fails pe OPEN ho
        self.recovery_timeout   = recovery_timeout    # Seconds — OPEN ke baad HALF_OPEN
        self.success_threshold  = success_threshold   # HALF_OPEN se CLOSED ke liye successes

        self.state             = CircuitState.CLOSED
        self.failure_count     = 0
        self.success_count     = 0
        self.last_failure_time = None

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                print("Circuit HALF_OPEN — testing recovery")
            else:
                raise Exception("Circuit OPEN — fast fail")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state         = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                print("Circuit CLOSED — service recovered!")
        else:
            self.failure_count = 0

    def _on_failure(self):
        self.failure_count    += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state         = CircuitState.OPEN
            self.success_count = 0
            print("Circuit back to OPEN — still failing")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"Circuit OPEN after {self.failure_count} failures!")
```

---

## Interview Questions & Answers

### Q1. Distributed tracing mein Trace ID kaise propagate karte hain services ke beech?

**Answer:**

HTTP headers ke through. Jab Service A, Service B ko call karta hai, outgoing request mein trace context inject karta hai. Service B receive karta hai aur same trace context ke under naya span create karta hai.

OpenTelemetry W3C TraceContext standard use karta hai — `traceparent` header:
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              ^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^  ^^
              version    trace-id (128-bit hex)      span-id (64-bit)  flags
```

Code mein:
```python
# Outgoing: inject karo
headers = {}
inject(headers)  # traceparent header automatically add hoga
await client.get(url, headers=headers)

# Incoming: extract karo
context = extract(request.headers)  # FastAPIInstrumentor ye automatically karta hai
```

**Key point**: Trace ID same rahega — sirf Span ID naya banega. Ye hierarchy maintain karta hai.

---

### Q2. Liveness vs Readiness probe kya fark hai? Dono kab fail hone chahiye?

**Answer:**

| | **Liveness** `/health/live` | **Readiness** `/health/ready` |
|---|---|---|
| **Matlab** | Service process alive hai? | Service traffic le sakti hai? |
| **Fail hone par** | Kubernetes container restart karta hai | Load balancer se service remove karta hai |
| **Fail kab karo** | Deadlock, infinite loop, OOM | DB down, Redis down, warming up |
| **Logic** | Minimal — sirf 200 return karo | Saari dependencies check karo |

**Galti mat karo**: Readiness logic Liveness mein mat daalo. Agar DB temporarily down ho aur Liveness fail karo — poori service restart ho jaayegi. Restart karne se DB connection nahi aayega.

---

### Q3. Bulkhead pattern kyu use karte hain? Bina iske kya hoga?

**Answer:**

**Without bulkhead:**
```
Dashboard endpoint calls User Service + Payment Service + Inventory Service
Payment Service slow ho gaya → saare threads wait kar rahe hain payment ke liye
→ User service ke requests bhi queue ho gaye (same thread pool)
→ Poora dashboard down
```

**With bulkhead:**
```
Payment Service ke liye alag semaphore (max 5 concurrent)
User Service ke liye alag semaphore (max 10 concurrent)
Payment slow → sirf 5 payment slots block, user data freely aata rahe
```

Real-world: Netflix ne bulkhead use kiya taaki ek slow microservice poore app ko na giraaye.

---

### Q4. Exponential backoff mein jitter kyu add karte hain?

**Answer:**

**Thundering herd problem**: Ek service down ho. 100 clients simultaneously fail. Sab same time pe retry karein (1s baad, 2s baad, 4s baad). Service recover hote hi — 100 requests ek saath aa jaate hain — phir down ho jaati.

**Jitter** random noise add karta hai:
```python
delay = base_delay * (2 ** attempt)         # Deterministic: 1, 2, 4, 8
delay += random.uniform(0, delay * 0.1)     # Jitter: 1.07, 2.15, 3.89, 8.23
```

Ab 100 clients alag-alag times pe retry karenge — service pe evenly load distribute hoga.

**AWS recommendation**: `full jitter` strategy sabse effective hai:
```python
delay = random.uniform(0, base_delay * (2 ** attempt))
```

---

### Q5. OpenTelemetry vs Prometheus — kya fark hai? Dono use karte hain ya ek?

**Answer:**

Ye alag cheezein solve karte hain — complementary hain, competing nahi:

| | **OpenTelemetry** | **Prometheus** |
|---|---|---|
| **Kya hai** | Observability framework (vendor-neutral SDK) | Metrics storage + query system |
| **Kya karta hai** | Traces, Metrics, Logs collect + export | Metrics scrape, store, alert |
| **Format** | OTLP protocol | Prometheus text format |
| **Push/Pull** | Push (OTLP exporter) | Pull (scrapes /metrics) |
| **Best for** | Distributed tracing, unified observability | Time-series metrics, alerting |

**Production setup:**
```
App (OpenTelemetry SDK)
  → Traces → Jaeger/Tempo
  → Metrics → Prometheus (ya OTLP receiver)
  → Logs → Loki

Grafana → sab dashboards ek jagah
```

OpenTelemetry ek standard hai — backend switch kar sakte ho bina code change kiye.

---

### Q6. Kaunse 3 log fields har microservice log mein hone chahiye?

**Answer:**

1. **`trace_id`** — Request ka unique identifier, across all services same. Bina iske distributed systems mein debug impossible.

2. **`service`** — Kon sa service tha (order-service, payment-service). Multiple services ek hi log aggregation system mein hain.

3. **`timestamp` (ISO 8601)** — Exactly kab hua. Event ordering ke liye critical — especially across timezones.

**Bonus fields:**
- `level` (INFO, ERROR, WARN)
- `user_id` — kiske request pe hua
- `duration_ms` — performance tracking

**Format:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "ERROR",
  "event": "order.payment_failed",
  "trace_id": "4bf92f3577b34da6",
  "service": "order-service",
  "user_id": 12345,
  "order_id": 67890,
  "error": "Payment gateway timeout"
}
```

---

### Q7. Circuit Breaker ke teen states explain karo. HALF_OPEN kyu zaroori hai?

**Answer:**

```
Normal operation
     ↓
[CLOSED] ←──────────────────────────────────────────┐
  │ sab calls allow                                  │
  │ failure_count badhta hai                         │
  │ threshold cross →                                │
  ↓                                                  │
[OPEN]                                               │ successes >= threshold
  │ sab calls fast-fail                              │
  │ recovery_timeout (30s) ke baad →                 │
  ↓                                                  │
[HALF_OPEN] ──────────────────────────────────────→─┘
  │ ek test call allow karo                  success │
  │ fail hua →                                       │
  └──────────────────────────────────────────────────→ [OPEN] (back)
```

**HALF_OPEN kyu?**

OPEN se directly CLOSED mat jaao — service ne genuinely recover kiya hai kya? Check karo. Ek test call karo. Succeed hua → CLOSED. Fail hua → OPEN rehne do.

**Bina HALF_OPEN ke**: 30s baad blindly CLOSED → service abhi bhi recovering → phir failures → phir OPEN. Infinite loop.

---

## Summary Table

| Pattern | Problem Solve Karta Hai | Implementation |
|---------|------------------------|----------------|
| **Structured Logging** | Debug impossible in distributed systems | structlog + JSON format + trace_id |
| **Metrics** | Service health visibility, alerts | Prometheus Counter/Histogram/Gauge |
| **Distributed Tracing** | Request path across services | OpenTelemetry + Jaeger |
| **Health Checks** | Kubernetes pod management | /health/live + /health/ready |
| **Retry + Backoff** | Transient failures handle karo | Exponential delay + jitter |
| **Bulkhead** | One service failure isolate karo | asyncio.Semaphore per service |
| **Timeout** | Slow service se protect karo | asyncio.wait_for |
| **Circuit Breaker** | Cascade failures rok do | CLOSED → OPEN → HALF_OPEN |

**Golden Rule**: Agar aap production system mein kisi bhi service ka behavior explain nahi kar sakte logs/metrics/traces ke bina — aapka system observable nahi hai. Fix this first.
