# OpenTelemetry & Distributed Tracing — Production Backend

**DevOps · Year 3-4 | Senior Backend + Agentic AI**

---

## Quick Concepts

**WHAT:**
- **OpenTelemetry (OTel)** = CNCF standard for telemetry data — traces, metrics, logs ek unified API se
- **Distributed Tracing** = ek request ka poora journey trace karna across services
- **Span** = ek single operation (DB query, HTTP call) — start time + duration + metadata
- **Trace** = ek tree of spans — ek request ka complete lifecycle
- **Correlation ID / Trace ID** = har request ko ek unique 128-bit ID milta hai, sab services me propagate hota hai

**WHY (Senior interviews me kyun poochha jata hai):**
- Microservices me kisi ek service ka slow hona poori chain ko affect karta hai — bina tracing ke dhundna lagbhag impossible
- Alag-alag teams ke services ka performance ek hi dashboard me dikhna chahiye
- Production incidents me "which service introduced the latency spike" — tracing se seconds me pata chalta hai

**WHERE IT FITS:**
```
Request → [Service A] → [Service B] → [DB]
            span1          span2        span3
              └──────── trace_id ──────────┘
```

---

## Part 1: OTel Architecture

### Three Pillars
```
Traces   → req ka journey (spans linked by trace_id)
Metrics  → numeric measurements (latency p99, error rate)
Logs     → text events (existing logging, OTel bhi support karta hai)
```

### OTel Components
```
Your App Code
    │
    ▼
OTel SDK (instrumentation)
    │
    ▼
OTel Collector (agent sidecar ya daemonset)
    │         │
    ▼         ▼
 Jaeger    Prometheus
(traces)   (metrics)
    │
    ▼
 Grafana (unified dashboards)
```

### Collector kyun chahiye?
- App ko directly backend se couple mat karo
- Collector = fan-out, filtering, sampling, batching
- Backend change karo (Jaeger→Tempo) — app code nahi badla

---

## Part 2: Spans Deep Dive

### Span Anatomy
```python
span = {
    "trace_id":   "4bf92f3577b34da6a3ce929d0e0e4736",  # same for all spans in a request
    "span_id":    "00f067aa0ba902b7",                  # unique per span
    "parent_span_id": "b9c7c989f97918e1",              # parent span ka ID
    "name":       "DB query: SELECT users",
    "start_time": 1719123456000000000,
    "duration":   4500000,   # nanoseconds (4.5ms)
    "status":     "OK",
    "attributes": {
        "db.system": "postgresql",
        "db.statement": "SELECT * FROM users WHERE id = ?",
        "net.peer.name": "db.prod.internal",
    },
    "events": [
        {"name": "exception", "attributes": {"exception.message": "..."}}
    ]
}
```

### Span Kinds
| Kind     | Kab Use Hota Hai                    |
|----------|-------------------------------------|
| SERVER   | incoming HTTP request               |
| CLIENT   | outgoing HTTP/gRPC call             |
| PRODUCER | message queue pe publish karna      |
| CONSUMER | queue se message consume karna      |
| INTERNAL | internal function call              |

---

## Part 3: Python Implementation

### Install
```bash
pip install opentelemetry-api opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-django \
    opentelemetry-instrumentation-psycopg2 \
    opentelemetry-instrumentation-redis
```

### Basic Setup (Django/FastAPI)
```python
# tracing.py — app startup me yeh call karo
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

def configure_tracing(service_name: str, otlp_endpoint: str = "localhost:4317"):
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "production",
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)

# Usage
tracer = configure_tracing("user-service")
```

### Manual Instrumentation
```python
# Custom spans for business logic
def process_payment(order_id: str, amount: float):
    with tracer.start_as_current_span("process_payment") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("payment.amount", amount)
        span.set_attribute("payment.currency", "USD")

        try:
            # Child span for DB operation
            with tracer.start_as_current_span("db.save_payment") as db_span:
                db_span.set_attribute("db.operation", "INSERT")
                result = db.save(order_id, amount)

            # Child span for external API
            with tracer.start_as_current_span("stripe.charge") as stripe_span:
                stripe_span.set_attribute("stripe.customer_id", "cus_xxx")
                response = stripe.charge(amount)

            span.set_attribute("payment.status", "success")
            return result

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise
```

### Auto-Instrumentation (Django)
```python
# manage.py ya asgi.py se pehle
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

DjangoInstrumentor().instrument()
Psycopg2Instrumentor().instrument()
RedisInstrumentor().instrument()
# Ab automatically sab DB queries, Redis calls trace honge — zero code change
```

---

## Part 4: Correlation IDs (Service Boundary pe)

### HTTP Header Propagation (W3C TraceContext standard)
```
# Request header (OTel SDK automatically inject karta hai)
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              ^^ version  ^^^ trace_id (32 hex)    ^^ span_id (16)  ^^ flags

tracestate: vendorname=value   # optional custom state
```

### Custom Correlation ID (Business-level)
```python
import uuid
from opentelemetry import trace, baggage
from opentelemetry.propagate import inject, extract

# Incoming request pe correlation ID extract ya generate
class CorrelationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Agar incoming request me hai to use karo, warna generate karo
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.correlation_id = correlation_id

        # Current span me add karo
        span = trace.get_current_span()
        span.set_attribute("correlation.id", correlation_id)

        response = self.get_response(request)
        response["X-Correlation-ID"] = correlation_id  # downstream me pass karo
        return response

# Outgoing HTTP calls me inject karo
import httpx
from opentelemetry.propagate import inject

def call_downstream(url: str, correlation_id: str):
    headers = {"X-Correlation-ID": correlation_id}
    inject(headers)  # traceparent header bhi add ho jayega
    return httpx.get(url, headers=headers)
```

---

## Part 5: Jaeger (Tracing Backend)

### Local Setup (Docker)
```bash
docker run -d --name jaeger \
  -p 16686:16686 \   # UI
  -p 4317:4317 \     # OTLP gRPC
  -p 4318:4318 \     # OTLP HTTP
  jaegertracing/all-in-one:latest
```

### Jaeger UI me kya dekhte hain
- **Service Map** → kaun kaun se services baat karti hain
- **Trace Timeline** → spans ka waterfall view — bottleneck visible hota hai
- **Compare Traces** → slow request vs fast request side-by-side
- **Search by tag** → `error=true` → sirf failed traces

### Production: Jaeger vs Grafana Tempo
| Feature          | Jaeger                | Grafana Tempo        |
|------------------|-----------------------|----------------------|
| Storage          | Cassandra/ES          | Object storage (S3)  |
| Cost (scale)     | Expensive             | Cheap                |
| Grafana Native   | No (separate UI)      | Yes (direct link)    |
| Query Language   | Jaeger Query          | TraceQL              |
| Recommendation   | Smaller teams         | Production at scale  |

---

## Part 6: Sampling Strategy

```python
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased,  # % of requests trace karo
    ParentBased,        # parent ka decision inherit karo
    ALWAYS_ON,
    ALWAYS_OFF,
)

# Production: sirf 10% requests trace karo (high traffic pe)
sampler = ParentBased(root=TraceIdRatioBased(0.1))

# Health checks never trace karo
class FilteringSampler(Sampler):
    def should_sample(self, parent_context, trace_id, name, *args, **kwargs):
        if name in ["/health", "/metrics"]:
            return SamplingResult(Decision.DROP)
        return SamplingResult(Decision.RECORD_AND_SAMPLE)
```

---

## Part 7: Grafana + OTel (Unified Observability)

### Three in One
```yaml
# docker-compose.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib
    volumes:
      - ./otel-config.yaml:/etc/otelcol/config.yaml
    ports:
      - "4317:4317"

  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

```yaml
# otel-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      exporters: [prometheus]
```

---

## Part 8: SRE Workflow with Tracing

### Incident Investigation Flow
```
Alert fires (p99 latency > 2s)
    │
    ▼
Grafana dashboard → latency spike dekho → kis service?
    │
    ▼
Jaeger search → time range me slow traces dhundo
    │
    ▼
Trace detail → waterfall → span #3 = DB query (1.8s)
    │
    ▼
Span attributes → db.statement = "SELECT * FROM orders JOIN ..."
    │
    ▼
EXPLAIN ANALYZE → missing index ya N+1 found
    │
    ▼
Fix → deploy → trace latency drop confirm karo
```

---

## Interview Q&A

**Q: Trace ID aur Correlation ID me kya fark hai?**
A: Trace ID = OTel ka standard UUID (128-bit) jo automatically propagate hota hai `traceparent` header se. Correlation ID = business-level custom ID jo tumhari team define karti hai (UUID v4). Dono saath use kar sakte ho — trace_id technical debugging ke liye, correlation_id business logs ko cross-reference karne ke liye.

**Q: High-traffic service me 100% sampling feasible hai?**
A: Nahi. 10k req/s pe 100% sampling = terabytes/day storage. Tail-based sampling prefer karo: failed/slow requests 100% sample karo, healthy requests 1-5%. OTel Collector ya Grafana Tempo me tail sampling support hai.

**Q: Microservices me distributed tracing ka biggest challenge?**
A: Context propagation — har service ko `traceparent` header forward karna hota hai. Ek bhi service header drop kare to trace break ho jati hai. OTel auto-instrumentation mostly handle kar leta hai, par legacy services ya message queues me manual karna padta hai.

**Q: OpenTelemetry vs Zipkin vs Jaeger — interview me poochhein to?**
A: OTel = vendor-neutral SDK/specification (sirf data collect/export karta hai). Jaeger aur Zipkin = backends (data store aur visualize karte hain). OTel + Jaeger/Tempo = standard combination. Zipkin older hai, Jaeger CNCF project hai.

**Q: Logs aur Traces ek saath use karna?**
A: Trace ID ko log entries me add karo — phir ek log line se directly Jaeger trace me jump kar sakte ho. Structured logging me `trace_id` field mandatory hona chahiye production me.

---

## Related Topics
- `03_observability_resilience.md` — Microservices observability patterns
- `05_prometheus_grafana.md` — Metrics layer
- `17_ebpf_observability.md` — Low-level kernel tracing
- `16_sre_practices_sli_slo.md` — SLI/SLO/Error Budgets
