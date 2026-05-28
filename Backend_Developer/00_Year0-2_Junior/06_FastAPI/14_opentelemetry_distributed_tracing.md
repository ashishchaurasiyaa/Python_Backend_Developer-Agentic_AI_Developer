# OpenTelemetry + Distributed Tracing in FastAPI

> **Interview angle:** "Microservices mein request slow ho rahi — kis service mein hai ye kaise pata karoge?"

---

## 1. The Problem — "Where Did Time Go?"

Microservices request flow:
```
Client → API Gateway → Service A → Service B → Database
                                 ↓
                             Service C → Redis
```

Total latency = 800ms. **Where?** Without tracing, you're blind.

**Distributed tracing** = follow a request across service boundaries.

---

## 2. Three Pillars of Observability

| Pillar | Purpose | Tool |
|---|---|---|
| **Logs** | What happened | Loki, ELK, CloudWatch |
| **Metrics** | How much / how fast | Prometheus, Grafana |
| **Traces** | Where time was spent | Jaeger, Tempo, Datadog APM |

**OpenTelemetry (OTel)** = unified standard for all three.

---

## 3. Core Concepts

### Trace
A complete journey of a single request through the system.

### Span
A single unit of work — represents one operation.
```
Trace ID: abc-123
├── Span: API Gateway (10ms)
│   └── Span: Service A endpoint (200ms)
│       ├── Span: DB query (150ms)
│       └── Span: Service B HTTP call (40ms)
│           └── Span: Service B endpoint (35ms)
└── Span: Total: 250ms
```

### Span Attributes
Key-value metadata: `http.status_code=200`, `db.statement="SELECT..."`, `user.id=42`.

### Context Propagation
Trace ID + parent Span ID passed in HTTP headers (W3C TraceContext):
```
traceparent: 00-abc123...-def456...-01
tracestate: vendor1=...
```

---

## 4. OpenTelemetry Architecture

```
┌──────────────────┐
│   Your Service   │
│  ┌─────────────┐ │
│  │ OTel SDK    │ │  ← creates spans
│  └─────────────┘ │
└────────┬─────────┘
         │ OTLP protocol (gRPC/HTTP)
         ▼
┌──────────────────┐
│  OTel Collector  │  ← receive, process, export
└────────┬─────────┘
         │
    ┌────┼────┬───────┐
    ▼    ▼    ▼       ▼
  Jaeger Tempo Datadog  S3
  (traces) (traces) (APM)  (long-term)
```

---

## 5. Setup in FastAPI

### Install
```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-sqlalchemy
pip install opentelemetry-instrumentation-redis
pip install opentelemetry-instrumentation-httpx
opentelemetry-bootstrap --action=install   # auto-install all
```

### Manual Instrumentation
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Setup once at startup
resource = Resource.create({
    "service.name": "user-api",
    "service.version": "1.0.0",
    "deployment.environment": "production",
})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
```

### Auto-instrumentation
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=db_engine)
RedisInstrumentor().instrument()
# Now every request/query/Redis op = automatic span!
```

### Custom Span (manual)
```python
@app.get("/orders/{id}")
async def get_order(id: int):
    with tracer.start_as_current_span("validate_order") as span:
        span.set_attribute("order.id", id)
        valid = await validate(id)
        span.set_attribute("order.valid", valid)

    with tracer.start_as_current_span("fetch_order_details"):
        order = await fetch_from_db(id)

    return order
```

---

## 6. Context Propagation (Multi-Service)

### Service A — outgoing call
```python
import httpx
# httpx auto-instrumented → adds traceparent header
async with httpx.AsyncClient() as client:
    resp = await client.get("http://service-b/api/data")
```

### Service B — incoming
```python
# FastAPIInstrumentor reads traceparent header, continues the trace
```

### Manual Injection (for non-instrumented clients)
```python
from opentelemetry.propagate import inject

headers = {}
inject(headers)   # adds traceparent
await send_kafka_message(payload, headers=headers)
```

### Manual Extraction
```python
from opentelemetry.propagate import extract

ctx = extract(carrier_headers)
with tracer.start_as_current_span("consume", context=ctx):
    process_message()
```

---

## 7. Span Attributes (Semantic Conventions)

Use **standard names** so tools recognize them:

| Type | Attribute | Example |
|---|---|---|
| HTTP | `http.method` | "GET" |
| HTTP | `http.status_code` | 200 |
| HTTP | `http.url` | "/api/users" |
| DB | `db.system` | "postgresql" |
| DB | `db.statement` | "SELECT * FROM users" |
| DB | `db.operation` | "SELECT" |
| Messaging | `messaging.system` | "kafka" |
| Messaging | `messaging.destination` | "orders.topic" |
| User | `enduser.id` | "42" |
| Error | `exception.type`, `exception.message` | |

---

## 8. Error Recording

```python
from opentelemetry.trace import Status, StatusCode

@app.post("/payment")
async def pay():
    with tracer.start_as_current_span("process_payment") as span:
        try:
            await charge_card()
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

---

## 9. Sampling Strategies

In production, tracing 100% of requests is **expensive**. Sample wisely:

### Strategies
1. **Always On** — dev/staging
2. **Always Off** — disable (rare)
3. **Trace ID Ratio** — 10% of traces
4. **Parent-Based** — if upstream sampled, sample here too
5. **Adaptive** — sample more errors, less success

### Config
```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased

sampler = ParentBased(TraceIdRatioBased(0.1))   # sample 10%
provider = TracerProvider(resource=resource, sampler=sampler)
```

### Always trace specific endpoints
```python
# Force trace for critical paths (override sampler)
@app.post("/checkout")
async def checkout():
    with tracer.start_as_current_span(
        "checkout",
        attributes={"sampling.priority": 1}    # always sample
    ):
        ...
```

---

## 10. Connecting Logs ↔ Traces ↔ Metrics

### Add trace_id to log lines
```python
import logging
from opentelemetry.trace import get_current_span

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = get_current_span()
        ctx = span.get_span_context()
        record.trace_id = format(ctx.trace_id, '032x') if ctx.is_valid else ""
        record.span_id = format(ctx.span_id, '016x') if ctx.is_valid else ""
        return True

logging.basicConfig(
    format="%(asctime)s [trace=%(trace_id)s] %(message)s"
)
logger.addFilter(TraceIdFilter())
```

Now logs are searchable by trace ID. Click trace in Jaeger → find correlated logs in Loki.

### Exemplars (link metrics ↔ traces)
Prometheus + OTel → exemplars: a metric data point with a trace ID attached.
"Latency p99 spike at 15:42 → click to jump to trace".

---

## 11. Common Production Setup

### Stack: FastAPI → OTel → Jaeger
```yaml
# docker-compose.yml
services:
  app:
    build: .
    environment:
      - OTEL_SERVICE_NAME=user-api
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_TRACES_SAMPLER=parentbased_traceidratio
      - OTEL_TRACES_SAMPLER_ARG=0.1

  otel-collector:
    image: otel/opentelemetry-collector-contrib
    volumes:
      - ./otel-config.yaml:/etc/otelcol-contrib/config.yaml

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"   # UI
```

### OTel Collector config
```yaml
receivers:
  otlp:
    protocols:
      grpc:
exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
processors:
  batch:
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
```

---

## 12. Performance Impact

- Auto-instrumentation: ~5-10% latency overhead
- Sampling 10% → ~1% overhead
- Batch export → fewer flushes → less overhead
- Use **async exporter** (BatchSpanProcessor) — non-blocking

---

## 13. Interview Questions

**Q1: Distributed tracing kya hai?**
End-to-end view of a single request across services. Each operation = span. All spans of one request share trace ID.

**Q2: OpenTelemetry vs vendor-specific APM?**
OTel = vendor-neutral standard. Export to Jaeger, Datadog, NewRelic, Honeycomb — same code.

**Q3: Trace ID kaise propagate hota?**
HTTP header `traceparent` (W3C TraceContext). Auto-injected by instrumented HTTP clients.

**Q4: 100% sampling production mein?**
No — expensive. Use 5-10% sampling + always-trace errors + always-trace critical paths.

**Q5: Logs ↔ Traces kaise link?**
Inject trace_id + span_id into log format. Both stored in same observability platform (Loki, Datadog) → click-through navigation.

**Q6: Span attributes kya hote?**
Key-value metadata. Use semantic conventions: `http.method`, `db.statement`, `enduser.id` for tool compatibility.

**Q7: BatchSpanProcessor vs SimpleSpanProcessor?**
Batch = async, batched, faster (production). Simple = sync, blocking, dev/debug.

---

## 14. Best Practices

1. **Always set service.name + version** — distinguish services
2. **Sample wisely** — 10% is typical sweet spot
3. **Always trace errors** — override sampler for exceptions
4. **Use semantic conventions** — for tool compatibility
5. **Auto-instrument first** — manual spans only for business logic
6. **Inject trace ID into logs** — bridge between observability tools
7. **Set deployment.environment** attribute — separate prod/staging
8. **Monitor collector** — if collector down, traces lost
9. **Don't log PII in spans** — they may persist in storage
10. **Test instrumentation in CI** — verify traces are emitted

---

## Related
- [[13_asgi_internals_uvicorn_tuning]]
- [[../01_Year3-4_Mid/04_DevOps/05_prometheus_grafana]] — metrics complement
- [[../01_Year3-4_Mid/05_Microservices/03_observability_resilience]] — broader observability
