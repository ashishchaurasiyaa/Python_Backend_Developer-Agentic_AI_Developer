"""
Microservices Observability & Resilience — Practical Demo
==========================================================
Sab demos standalone hain — koi external service needed nahi.

Usage:
    python 03_observability_resilience.py logging
    python 03_observability_resilience.py metrics
    python 03_observability_resilience.py tracing
    python 03_observability_resilience.py health
    python 03_observability_resilience.py resilience
    python 03_observability_resilience.py all
"""

import sys
import asyncio
import json
import time
import random
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Optional, Any


# ─────────────────────────────────────────────
# DEMO 1 — STRUCTURED LOGGING
# ─────────────────────────────────────────────

def demo_structured_logging():
    """
    Structlog demo — development (pretty) aur production (JSON) format.
    Context vars automatically logs mein merge hote hain.
    """
    print("\n" + "=" * 60)
    print("DEMO 1: STRUCTURED LOGGING")
    print("=" * 60)

    try:
        import structlog

        # ── Development renderer (pretty coloured output) ──────────
        print("\n[Dev Mode — ConsoleRenderer]")
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ]
        )
        logger = structlog.get_logger()

        # Bind context — ye trace_id ab har log mein automatically aayega
        structlog.contextvars.bind_contextvars(
            trace_id=str(uuid.uuid4())[:8],
            service="order-service",
        )

        logger.info("app.started", version="1.0.0", env="development")
        logger.info("order.created", order_id=1001, user_id=42, amount=4999)
        logger.warning("inventory.low", product_id=555, remaining=3)
        logger.error("payment.failed", order_id=1001, reason="gateway_timeout")

        structlog.contextvars.clear_contextvars()

        # ── Production renderer (JSON) ──────────────────────────────
        print("\n[Production Mode — JSONRenderer]")
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),  # Machine-parseable
            ]
        )
        logger = structlog.get_logger()

        # Simulate request middleware — trace_id request pe bind karo
        trace_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            service="payment-service",
            path="/payments/charge",
            method="POST",
        )
        logger.info("request.received", content_length=256)
        logger.info("db.query", query_type="SELECT", table="payments", duration_ms=12.4)
        logger.info("request.completed", status_code=200, duration_ms=45.2)

        structlog.contextvars.clear_contextvars()

        # ── Simulate how middleware would log multiple requests ──────
        print("\n[Simulating 3 requests through logging middleware]")
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ]
        )
        logger = structlog.get_logger()

        requests_data = [
            {"method": "POST", "path": "/orders",       "status": 201, "ms": 55.1},
            {"method": "GET",  "path": "/orders/1001",  "status": 200, "ms": 12.3},
            {"method": "GET",  "path": "/orders/9999",  "status": 404, "ms": 8.7},
        ]

        for req in requests_data:
            structlog.contextvars.bind_contextvars(
                trace_id=str(uuid.uuid4())[:8],
                service="order-service",
                path=req["path"],
                method=req["method"],
            )
            logger.info(
                "request.completed",
                status_code=req["status"],
                duration_ms=req["ms"],
            )
            structlog.contextvars.clear_contextvars()

    except ImportError:
        print("structlog not installed — pip install structlog")
        print("Showing plain dict simulation instead:\n")

        # Fallback — manually JSON logs simulate karo
        def log_event(level, event, **kwargs):
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "level": level,
                "event": event,
                **kwargs,
            }
            print(json.dumps(entry))

        trace_id = str(uuid.uuid4())[:8]
        log_event("info", "request.received",   trace_id=trace_id, path="/orders", method="POST", service="order-service")
        log_event("info", "order.created",       trace_id=trace_id, order_id=1001, user_id=42, amount=4999, service="order-service")
        log_event("info", "request.completed",   trace_id=trace_id, status_code=201, duration_ms=55.1, service="order-service")
        log_event("warning", "inventory.low",    trace_id=trace_id, product_id=555, remaining=3, service="inventory-service")
        log_event("error", "payment.failed",     trace_id=trace_id, order_id=1001, reason="gateway_timeout", service="payment-service")

    print("\n[Key Takeaways]")
    print("  - trace_id bind karo — saari logs ek request ke liye linked rahegi")
    print("  - Dev mein ConsoleRenderer, Production mein JSONRenderer")
    print("  - Event names use karo: 'order.created' not 'Order was created'")
    print("  - clear_contextvars() each request ke end mein — leak mat karo")


# ─────────────────────────────────────────────
# DEMO 2 — PROMETHEUS METRICS
# ─────────────────────────────────────────────

def demo_metrics():
    """
    Prometheus metrics — Counter, Histogram, Gauge.
    20 requests simulate karo, then scrape output dikhao.
    """
    print("\n" + "=" * 60)
    print("DEMO 2: METRICS WITH PROMETHEUS")
    print("=" * 60)

    try:
        from prometheus_client import (
            Counter, Histogram, Gauge,
            CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
        )

        # Isolated registry taaki global state pollute na ho
        registry = CollectorRegistry()

        REQUEST_COUNT = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["service", "method", "endpoint", "status_code"],
            registry=registry,
        )
        REQUEST_DURATION = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["service", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=registry,
        )
        ACTIVE_REQUESTS = Gauge(
            "active_requests",
            "Currently active requests",
            ["service"],
            registry=registry,
        )
        BUSINESS_METRIC = Counter(
            "orders_created_total",
            "Total orders created",
            ["service"],
            registry=registry,
        )

        # Simulate 20 HTTP requests
        print("\n[Simulating 20 HTTP requests...]")
        scenarios = [
            ("GET",  "/health",          200, 0.005),
            ("POST", "/orders",          201, 0.055),
            ("GET",  "/orders/1001",     200, 0.012),
            ("GET",  "/orders/9999",     404, 0.008),
            ("POST", "/orders",          201, 0.120),
            ("GET",  "/products",        200, 0.035),
            ("POST", "/orders",          500, 0.250),
            ("GET",  "/orders/1002",     200, 0.015),
            ("POST", "/orders",          201, 0.045),
            ("GET",  "/health",          200, 0.003),
            ("POST", "/orders",          422, 0.010),
            ("GET",  "/orders/1003",     200, 0.022),
            ("POST", "/orders",          201, 0.065),
            ("GET",  "/products/55",     200, 0.018),
            ("POST", "/orders",          201, 0.480),
            ("GET",  "/orders/1004",     500, 0.095),
            ("POST", "/orders",          201, 0.033),
            ("GET",  "/products",        200, 0.028),
            ("POST", "/orders",          201, 0.077),
            ("GET",  "/health",          200, 0.004),
        ]

        for method, endpoint, status, duration in scenarios:
            ACTIVE_REQUESTS.labels(service="order-service").inc()
            REQUEST_COUNT.labels(
                service="order-service",
                method=method,
                endpoint=endpoint,
                status_code=str(status),
            ).inc()
            REQUEST_DURATION.labels(service="order-service", endpoint=endpoint).observe(duration)
            ACTIVE_REQUESTS.labels(service="order-service").dec()

            if method == "POST" and endpoint == "/orders" and status == 201:
                BUSINESS_METRIC.labels(service="order-service").inc()

        # Summary
        print("\n[Requests Simulated Summary]")
        total = len(scenarios)
        errors = sum(1 for _, _, s, _ in scenarios if s >= 500)
        successes = sum(1 for _, _, s, _ in scenarios if s < 400)
        avg_duration = sum(d for _, _, _, d in scenarios) / total * 1000
        print(f"  Total requests: {total}")
        print(f"  Success (2xx/3xx): {successes}")
        print(f"  Errors (5xx): {errors}")
        print(f"  Avg duration: {avg_duration:.1f}ms")

        # What Prometheus would scrape
        print("\n[/metrics endpoint output (what Prometheus scrapes)]")
        print("-" * 60)
        raw = generate_latest(registry).decode("utf-8")
        # Print only relevant lines — skip comments and zeroed buckets for clarity
        for line in raw.split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            print(line)

        # Show histogram bucket interpretation
        print("\n[Histogram bucket interpretation]")
        print("  http_request_duration_seconds_bucket{le='0.05'} = N")
        print("  -> N requests completed in <= 50ms")
        print("  histogram_quantile(0.95, rate(metric_bucket[5m])) in PromQL")
        print("  -> p95 latency calculate hoga")

    except ImportError:
        print("prometheus_client not installed — pip install prometheus-client")
        print("\nManually simulating metric output:\n")

        # Manually simulate metric counting
        counters = {}
        def inc(name, labels):
            key = (name, frozenset(labels.items()))
            counters[key] = counters.get(key, 0) + 1

        for method, endpoint, status, _ in [
            ("POST", "/orders", "201", 0.05),
            ("POST", "/orders", "201", 0.06),
            ("POST", "/orders", "500", 0.25),
            ("GET",  "/health", "200", 0.005),
        ]:
            inc("http_requests_total", {"method": method, "endpoint": endpoint, "status": status})

        print("Simulated counter values:")
        for (name, labels), count in counters.items():
            label_str = ",".join(f'{k}="{v}"' for k, v in labels)
            print(f"  {name}{{{label_str}}} {count}")

    print("\n[Key Takeaways]")
    print("  - Counter: sirf badhta hai (requests, errors)")
    print("  - Histogram: latency distribution + percentiles")
    print("  - Gauge: up/down (active connections, queue depth)")
    print("  - Labels use karo filtering ke liye — per endpoint/service")


# ─────────────────────────────────────────────
# DEMO 3 — DISTRIBUTED TRACING (in-memory)
# ─────────────────────────────────────────────

@dataclass
class Span:
    trace_id:       str
    span_id:        str
    parent_span_id: Optional[str]
    service:        str
    operation:      str
    start_time:     float
    end_time:       Optional[float] = None
    attributes:     dict = field(default_factory=dict)
    status:         str = "OK"

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000


class SimpleTracer:
    """
    In-memory distributed tracer — Jaeger required nahi.
    Spans collect karta hai, phir tree print karta hai.
    """
    def __init__(self, service_name: str):
        self.service = service_name
        self.spans: list[Span] = []
        self._current_span_id: Optional[str] = None

    @contextmanager
    def start_span(self, operation: str, parent_span_id=None, trace_id=None):
        span = Span(
            trace_id=trace_id or str(uuid.uuid4())[:8],
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent_span_id or self._current_span_id,
            service=self.service,
            operation=operation,
            start_time=time.time(),
        )
        prev_span_id = self._current_span_id
        self._current_span_id = span.span_id
        try:
            yield span
            span.status = "OK"
        except Exception as e:
            span.status = f"ERROR: {e}"
            raise
        finally:
            span.end_time = time.time()
            self._current_span_id = prev_span_id
            self.spans.append(span)


def print_trace_tree(all_spans: list[Span]):
    """Spans ko trace tree format mein print karo."""
    if not all_spans:
        return

    # Group by trace_id
    by_trace: dict[str, list[Span]] = {}
    for span in all_spans:
        by_trace.setdefault(span.trace_id, []).append(span)

    for trace_id, spans in by_trace.items():
        print(f"\n  Trace ID: {trace_id}")

        # Build parent → children map
        children: dict[Optional[str], list[Span]] = {}
        for span in spans:
            children.setdefault(span.parent_span_id, []).append(span)

        def print_span(span: Span, indent: int = 0):
            prefix = "  " * indent + ("└── " if indent > 0 else "")
            status_icon = "✓" if span.status == "OK" else "✗"
            print(
                f"  {prefix}{status_icon} [{span.service}] {span.operation}"
                f"  ({span.duration_ms:.1f}ms)  span={span.span_id}"
            )
            if span.attributes:
                attr_str = "  " * (indent + 1) + "    attrs: " + str(span.attributes)
                print(attr_str)
            for child in children.get(span.span_id, []):
                print_span(child, indent + 1)

        # Root spans (no parent)
        roots = children.get(None, [])
        for root in roots:
            print_span(root, indent=0)


async def demo_distributed_tracing():
    """
    Order Service → Inventory Service → Payment Service
    Trace context propagate karo across services.
    """
    print("\n" + "=" * 60)
    print("DEMO 3: DISTRIBUTED TRACING (In-Memory Simulation)")
    print("=" * 60)

    all_spans: list[Span] = []

    # ── Service tracers ────────────────────────────────────────────
    order_tracer     = SimpleTracer("order-service")
    inventory_tracer = SimpleTracer("inventory-service")
    payment_tracer   = SimpleTracer("payment-service")

    # ── Simulate: POST /orders ─────────────────────────────────────
    trace_id = str(uuid.uuid4())[:8]
    print(f"\n[Incoming request — trace_id={trace_id}]")

    with order_tracer.start_span("POST /orders", trace_id=trace_id) as root_span:
        root_span.attributes = {"user_id": 42, "product_id": 555, "quantity": 2}

        # DB insert order
        with order_tracer.start_span("db.insert_order") as db_span:
            await asyncio.sleep(0.015)  # simulate DB latency
            db_span.attributes = {"table": "orders", "rows_inserted": 1}

        # Call inventory service (propagate trace_id + span_id as parent)
        with inventory_tracer.start_span(
            "GET /inventory/555",
            trace_id=trace_id,
            parent_span_id=root_span.span_id
        ) as inv_span:
            inv_span.attributes = {"product_id": 555}

            # Inventory does its own DB query
            with inventory_tracer.start_span("db.select_stock") as stock_span:
                await asyncio.sleep(0.012)
                stock_span.attributes = {"product_id": 555, "stock": 98}

        # Call payment service
        with payment_tracer.start_span(
            "POST /payments/charge",
            trace_id=trace_id,
            parent_span_id=root_span.span_id
        ) as pay_span:
            pay_span.attributes = {"amount": 9998, "currency": "INR"}

            with payment_tracer.start_span("db.insert_transaction") as txn_span:
                await asyncio.sleep(0.020)
                txn_span.attributes = {"txn_id": "TXN_001", "status": "SUCCESS"}

        # Publish event
        with order_tracer.start_span("event.publish") as event_span:
            await asyncio.sleep(0.005)
            event_span.attributes = {"topic": "order.created", "event_id": "EVT_101"}

    all_spans.extend(order_tracer.spans)
    all_spans.extend(inventory_tracer.spans)
    all_spans.extend(payment_tracer.spans)

    print("\n[Trace Tree — Jaeger UI mein aisa dikhega]")
    print_trace_tree(all_spans)

    # Summary
    total_ms = sum(s.duration_ms for s in all_spans if s.parent_span_id is None)
    print(f"\n  Total request duration: {total_ms:.1f}ms")
    print(f"  Services involved: order-service, inventory-service, payment-service")
    print(f"  Total spans: {len(all_spans)}")

    # ── Failed trace ───────────────────────────────────────────────
    print("\n[Failed request trace — inventory out of stock]")
    all_spans_fail: list[Span] = []
    tracer_f = SimpleTracer("order-service")
    inv_f    = SimpleTracer("inventory-service")
    trace_id_f = str(uuid.uuid4())[:8]

    with tracer_f.start_span("POST /orders", trace_id=trace_id_f) as root:
        root.attributes = {"product_id": 9999, "quantity": 100}
        with tracer_f.start_span("db.insert_order"):
            await asyncio.sleep(0.010)

        with inv_f.start_span("GET /inventory/9999", trace_id=trace_id_f, parent_span_id=root.span_id) as inv_s:
            inv_s.attributes = {"product_id": 9999}
            with inv_f.start_span("db.select_stock") as stk:
                await asyncio.sleep(0.008)
                stk.attributes = {"product_id": 9999, "stock": 0}
            inv_s.status = "ERROR: InsufficientStock"

        root.status = "ERROR: order_failed"

    all_spans_fail.extend(tracer_f.spans)
    all_spans_fail.extend(inv_f.spans)
    print_trace_tree(all_spans_fail)

    print("\n[Key Takeaways]")
    print("  - Same trace_id across all services — ek request ek trace")
    print("  - Har service apna span create karta hai — parent_span_id propagate hota hai")
    print("  - W3C traceparent header se ye context HTTP ke through jaata hai")
    print("  - Jaeger/Tempo UI mein ye tree visually dikhti hai")


# ─────────────────────────────────────────────
# DEMO 4 — HEALTH CHECKS
# ─────────────────────────────────────────────

class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    name:       str
    status:     HealthStatus
    message:    str   = ""
    latency_ms: float = 0.0


class MockDatabase:
    def __init__(self, available: bool = True, latency_ms: float = 5.0):
        self.available  = available
        self.latency_ms = latency_ms

    async def execute(self, query: str):
        await asyncio.sleep(self.latency_ms / 1000)
        if not self.available:
            raise ConnectionError("Database connection refused")
        return {"rows": [{"1": 1}]}


class MockRedis:
    def __init__(self, available: bool = True, latency_ms: float = 2.0):
        self.available  = available
        self.latency_ms = latency_ms

    async def ping(self):
        await asyncio.sleep(self.latency_ms / 1000)
        if not self.available:
            raise ConnectionError("Redis NOCONN")
        return "PONG"


class MockRabbitMQ:
    def __init__(self, available: bool = True):
        self.available = available

    async def connect(self):
        if not self.available:
            raise ConnectionError("RabbitMQ connection refused port 5672")
        await asyncio.sleep(0.003)
        return self


async def health_check_system(db: MockDatabase, redis: MockRedis, mq: MockRabbitMQ):
    async def check_db() -> ComponentHealth:
        try:
            start = time.time()
            await db.execute("SELECT 1")
            return ComponentHealth("database", HealthStatus.HEALTHY, latency_ms=(time.time()-start)*1000)
        except Exception as e:
            return ComponentHealth("database", HealthStatus.UNHEALTHY, str(e))

    async def check_redis() -> ComponentHealth:
        try:
            start = time.time()
            await redis.ping()
            return ComponentHealth("redis", HealthStatus.HEALTHY, latency_ms=(time.time()-start)*1000)
        except Exception as e:
            return ComponentHealth("redis", HealthStatus.UNHEALTHY, str(e))

    async def check_mq() -> ComponentHealth:
        try:
            start = time.time()
            await mq.connect()
            return ComponentHealth("rabbitmq", HealthStatus.HEALTHY, latency_ms=(time.time()-start)*1000)
        except Exception as e:
            return ComponentHealth("rabbitmq", HealthStatus.UNHEALTHY, str(e))

    checks = await asyncio.gather(check_db(), check_redis(), check_mq())

    overall = HealthStatus.HEALTHY
    for c in checks:
        if c.status == HealthStatus.UNHEALTHY:
            overall = HealthStatus.UNHEALTHY
            break
        elif c.status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
            overall = HealthStatus.DEGRADED

    return overall, checks


async def demo_health_checks():
    print("\n" + "=" * 60)
    print("DEMO 4: HEALTH CHECKS")
    print("=" * 60)

    # ── Scenario 1: All healthy ─────────────────────────────────────
    print("\n[Scenario 1: All components healthy]")
    overall, checks = await health_check_system(
        MockDatabase(available=True, latency_ms=5),
        MockRedis(available=True, latency_ms=2),
        MockRabbitMQ(available=True),
    )
    status_code = 200 if overall != HealthStatus.UNHEALTHY else 503
    result = {
        "status": overall,
        "components": [
            {"name": c.name, "status": c.status, "latency_ms": round(c.latency_ms, 2), "message": c.message}
            for c in checks
        ]
    }
    print(f"  HTTP Status: {status_code}")
    print(json.dumps(result, indent=4))

    # ── Scenario 2: Redis down (DEGRADED — still serve traffic) ─────
    print("\n[Scenario 2: Redis down — DEGRADED (caching unavailable)]")
    print("  Note: Redis down = caching miss but service can still work")
    # In real systems you'd mark redis as DEGRADED not UNHEALTHY
    # For demo, we show the response with redis unhealthy
    overall2, checks2 = await health_check_system(
        MockDatabase(available=True, latency_ms=6),
        MockRedis(available=False),       # Redis DOWN
        MockRabbitMQ(available=True),
    )
    # Manually mark as degraded if only Redis failed
    for c in checks2:
        if c.name == "redis" and c.status == HealthStatus.UNHEALTHY:
            c.status = HealthStatus.DEGRADED
            c.message = "Cache unavailable — falling back to DB"
    overall2 = HealthStatus.DEGRADED
    status_code2 = 200  # Still accepting traffic
    result2 = {
        "status": overall2,
        "components": [
            {"name": c.name, "status": c.status, "latency_ms": round(c.latency_ms, 2), "message": c.message}
            for c in checks2
        ]
    }
    print(f"  HTTP Status: {status_code2}")
    print(json.dumps(result2, indent=4))

    # ── Scenario 3: Database down (UNHEALTHY — stop traffic) ────────
    print("\n[Scenario 3: Database down — UNHEALTHY (stop sending traffic)]")
    overall3, checks3 = await health_check_system(
        MockDatabase(available=False),    # DB DOWN
        MockRedis(available=True, latency_ms=2),
        MockRabbitMQ(available=True),
    )
    status_code3 = 503  # Service Unavailable
    result3 = {
        "status": overall3,
        "components": [
            {"name": c.name, "status": c.status, "latency_ms": round(c.latency_ms, 2), "message": c.message}
            for c in checks3
        ]
    }
    print(f"  HTTP Status: {status_code3}")
    print(json.dumps(result3, indent=4))

    # ── Liveness vs Readiness ─────────────────────────────────────
    print("\n[Liveness vs Readiness endpoints]")
    print("  GET /health/live  -> {\"status\": \"alive\"}  (always 200)")
    print("  GET /health/ready -> full component check above")
    print()
    print("  Kubernetes config:")
    print("    livenessProbe:  httpGet path: /health/live  — restart if fails")
    print("    readinessProbe: httpGet path: /health/ready — remove from LB if fails")

    print("\n[Key Takeaways]")
    print("  - /health/live sirf process alive check — minimal logic")
    print("  - /health/ready all dependencies check")
    print("  - DB down = 503 (UNHEALTHY), Redis down = 200 (DEGRADED)")
    print("  - asyncio.gather se parallel check karo — serial mat karo")


# ─────────────────────────────────────────────
# DEMO 5 — RESILIENCE PATTERNS
# ─────────────────────────────────────────────

# ── Retry with exponential backoff ────────────────────────────────

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,),
    jitter: bool = True,
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        print(f"    [SUCCESS on attempt {attempt + 1}]")
                    return result
                except exceptions as e:
                    if attempt == max_retries:
                        print(f"    [FAILED after {max_retries + 1} attempts] raising: {e}")
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        jitter_amount = random.uniform(0, delay * 0.2)
                        delay += jitter_amount
                    print(
                        f"    Attempt {attempt + 1} failed: {e}"
                        f" — retrying in {delay:.2f}s"
                        f" (base={base_delay * (2**attempt):.2f}s + jitter={delay - base_delay * (2**attempt):.2f}s)"
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator


# ── Bulkhead (Semaphore isolation) ─────────────────────────────────

class BulkheadExecutor:
    def __init__(self):
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._call_counts: dict[str, int] = {}

    def get_semaphore(self, service: str, max_concurrent: int) -> asyncio.Semaphore:
        if service not in self._semaphores:
            self._semaphores[service] = asyncio.Semaphore(max_concurrent)
        return self._semaphores[service]

    async def call(self, service: str, coro, max_concurrent: int = 5):
        sem = self.get_semaphore(service, max_concurrent)
        self._call_counts[service] = self._call_counts.get(service, 0) + 1
        async with sem:
            return await coro


# ── Circuit Breaker ────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold=3, recovery_timeout=5.0, success_threshold=2):
        self.name               = name
        self.failure_threshold  = failure_threshold
        self.recovery_timeout   = recovery_timeout
        self.success_threshold  = success_threshold
        self.state              = CircuitState.CLOSED
        self.failure_count      = 0
        self.success_count      = 0
        self.last_failure_time: Optional[float] = None
        self.call_count         = 0
        self.rejected_count     = 0

    async def call(self, func, *args, **kwargs):
        self.call_count += 1

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                print(f"    [{self.name}] OPEN → HALF_OPEN (testing after {elapsed:.1f}s)")
                self.state         = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                self.rejected_count += 1
                remaining = self.recovery_timeout - elapsed
                print(f"    [{self.name}] Circuit OPEN — fast fail (opens again in {remaining:.1f}s)")
                raise Exception(f"CircuitBreaker OPEN: {self.name}")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if "CircuitBreaker OPEN" in str(e):
                raise
            self._on_failure(str(e))
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            print(f"    [{self.name}] HALF_OPEN success {self.success_count}/{self.success_threshold}")
            if self.success_count >= self.success_threshold:
                self.state         = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                print(f"    [{self.name}] HALF_OPEN → CLOSED (recovered!)")
        else:
            self.failure_count = 0

    def _on_failure(self, error: str):
        self.failure_count    += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state         = CircuitState.OPEN
            self.success_count = 0
            print(f"    [{self.name}] HALF_OPEN → OPEN (still failing: {error})")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"    [{self.name}] CLOSED → OPEN after {self.failure_count} failures!")
        else:
            print(f"    [{self.name}] Failure {self.failure_count}/{self.failure_threshold}: {error}")


async def demo_resilience_patterns():
    print("\n" + "=" * 60)
    print("DEMO 5: RESILIENCE PATTERNS")
    print("=" * 60)

    # ── 1. Retry with Exponential Backoff ─────────────────────────
    print("\n[Pattern 1: Retry with Exponential Backoff + Jitter]")
    print("-" * 50)

    call_count = {"n": 0}

    @retry_with_backoff(max_retries=3, base_delay=0.3, jitter=True, exceptions=(ValueError,))
    async def flaky_payment_api(amount: float) -> dict:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise ValueError(f"Payment gateway timeout (attempt {call_count['n']})")
        return {"status": "charged", "amount": amount, "txn_id": "TXN_999"}

    print("  Calling flaky payment API (fails first 2 times)...")
    result = await flaky_payment_api(4999.0)
    print(f"  Final result: {result}")

    # Always fails scenario
    print("\n  Calling always-failing API...")
    always_fail_count = {"n": 0}

    @retry_with_backoff(max_retries=2, base_delay=0.2, jitter=False, exceptions=(ConnectionError,))
    async def always_failing():
        always_fail_count["n"] += 1
        raise ConnectionError(f"Service unavailable (attempt {always_fail_count['n']})")

    try:
        await always_failing()
    except ConnectionError as e:
        print(f"  Expected final failure: {e}")

    # ── 2. Bulkhead Pattern ─────────────────────────────────────────
    print("\n[Pattern 2: Bulkhead — Semaphore Isolation]")
    print("-" * 50)

    bulkhead = BulkheadExecutor()
    results = {"user": 0, "payment": 0, "blocked": 0}

    async def slow_user_call(i: int):
        await asyncio.sleep(0.05)
        results["user"] += 1
        return f"user_data_{i}"

    async def slow_payment_call(i: int):
        await asyncio.sleep(0.1)
        results["payment"] += 1
        return f"payment_data_{i}"

    print("  Sending 15 concurrent requests:")
    print("    user-service    max_concurrent=5")
    print("    payment-service max_concurrent=3 (sensitive — stricter limit)")

    start = time.time()
    tasks = []
    for i in range(8):
        tasks.append(bulkhead.call("user-service",    slow_user_call(i),    max_concurrent=5))
    for i in range(7):
        tasks.append(bulkhead.call("payment-service", slow_payment_call(i), max_concurrent=3))

    await asyncio.gather(*tasks)
    elapsed = (time.time() - start) * 1000

    print(f"  Completed in {elapsed:.1f}ms")
    print(f"  User calls completed:    {results['user']}/8")
    print(f"  Payment calls completed: {results['payment']}/7")
    print("  Note: Payment service slow hota toh sirf payment slots block hote")
    print("        User service calls unaffected rahte — that's bulkhead!")

    # ── 3. Timeout Pattern ─────────────────────────────────────────
    print("\n[Pattern 3: Timeout — Fast Fail]")
    print("-" * 50)

    async def slow_service(delay: float):
        await asyncio.sleep(delay)
        return {"data": "slow_result"}

    async def call_with_timeout(coro, timeout_secs: float, service: str):
        try:
            result = await asyncio.wait_for(coro, timeout=timeout_secs)
            print(f"  [{service}] Success within {timeout_secs}s")
            return result
        except asyncio.TimeoutError:
            print(f"  [{service}] TIMEOUT after {timeout_secs}s — HTTP 504 return karo")
            return None

    await call_with_timeout(slow_service(0.1), timeout_secs=1.0,  service="inventory-service (fast)")
    await call_with_timeout(slow_service(2.0), timeout_secs=0.5,  service="recommendation-service (slow)")
    await call_with_timeout(slow_service(0.3), timeout_secs=5.0,  service="user-service (acceptable)")

    # ── 4. Circuit Breaker ──────────────────────────────────────────
    print("\n[Pattern 4: Circuit Breaker — CLOSED → OPEN → HALF_OPEN → CLOSED]")
    print("-" * 50)

    cb = CircuitBreaker("payment-service", failure_threshold=3, recovery_timeout=2.0, success_threshold=2)
    failure_mode = {"active": True, "count": 0}

    async def payment_service():
        failure_mode["count"] += 1
        if failure_mode["active"]:
            await asyncio.sleep(0.01)
            raise ConnectionError("Payment gateway unreachable")
        return {"status": "charged"}

    print("  Phase 1: Normal calls — accumulating failures")
    for i in range(5):
        try:
            result = await cb.call(payment_service)
            print(f"    Call {i+1}: Success -> {result}")
        except Exception as e:
            if "CircuitBreaker OPEN" in str(e):
                print(f"    Call {i+1}: Fast-failed (circuit open)")
            # else already printed by circuit breaker

    print(f"\n  Circuit state: {cb.state.value}")
    print(f"  Calls attempted: {cb.call_count}, Rejected (fast-fail): {cb.rejected_count}")

    print("\n  Phase 2: Service recovered — waiting for recovery timeout...")
    await asyncio.sleep(2.1)  # recovery_timeout se thoda zyada

    failure_mode["active"] = False  # Service recovered
    print("  Service recovery simulate kiya — calling again...")

    for i in range(4):
        try:
            result = await cb.call(payment_service)
            print(f"    Call {i+1}: Success -> {result}")
        except Exception as e:
            print(f"    Call {i+1}: Failed -> {e}")

    print(f"\n  Final circuit state: {cb.state.value}")

    # ── Pattern comparison summary ──────────────────────────────────
    print("\n[Resilience Patterns Summary]")
    print("-" * 50)
    patterns = [
        ("Retry + Backoff",  "Transient failures",     "Jitter add karo — thundering herd avoid karo"),
        ("Bulkhead",         "Cascade failures",        "Per-service semaphore — isolation"),
        ("Timeout",          "Slow/hung services",      "asyncio.wait_for — fast fail"),
        ("Circuit Breaker",  "Repeated failures",       "CLOSED→OPEN→HALF_OPEN — smart recovery"),
    ]
    for name, problem, note in patterns:
        print(f"  {name:<20} | Solves: {problem:<25} | {note}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

DEMOS = {
    "logging":    (demo_structured_logging, False),
    "metrics":    (demo_metrics, False),
    "tracing":    (demo_distributed_tracing, True),
    "health":     (demo_health_checks, True),
    "resilience": (demo_resilience_patterns, True),
}


async def run_all():
    demo_structured_logging()
    demo_metrics()
    await demo_distributed_tracing()
    await demo_health_checks()
    await demo_resilience_patterns()

    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  pip install structlog prometheus-client opentelemetry-sdk")
    print("  pip install opentelemetry-instrumentation-fastapi httpx")
    print("  docker run -p 16686:16686 -p 6831:6831/udp jaegertracing/all-in-one")
    print("  docker run -p 9090:9090 prom/prometheus")
    print("  docker run -p 3000:3000 grafana/grafana")


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if mode == "all":
        asyncio.run(run_all())
    elif mode in DEMOS:
        fn, is_async = DEMOS[mode]
        if is_async:
            asyncio.run(fn())
        else:
            fn()
    else:
        print(f"Unknown mode: {mode}")
        print(f"Available: {', '.join(DEMOS)} | all")
        sys.exit(1)
