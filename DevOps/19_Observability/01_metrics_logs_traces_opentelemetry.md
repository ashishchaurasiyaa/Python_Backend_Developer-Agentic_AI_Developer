# Observability — Metrics, Logs, Traces & OpenTelemetry
**DevOps Track · Phase 19: Observability**

> Deep hands-on OpenTelemetry instrumentation (Python auto/manual instrumentation, context propagation, exporter config) already lives in `Backend_Developer/01_Year3-4_Mid/04_DevOps/19_opentelemetry_distributed_tracing.md`. This file keeps things at the conceptual/comparison level — what each pillar is for, how the pieces fit together, and when to reach for Jaeger vs Zipkin — and points to that file for implementation depth.

## Quick Concepts

- **Observability** = ability to understand a system's internal state from its external outputs (metrics, logs, traces), without shipping new code to answer a new question
- **Monitoring** = watching known failure modes (dashboards, alerts on known thresholds) — a subset of observability
- **Metric** = a numeric measurement over time (counter, gauge, histogram)
- **Log** = a discrete, timestamped event record (usually text/structured JSON)
- **Trace** = the end-to-end journey of one request across services
- **Span** = one unit of work within a trace (a single DB call, HTTP call, function)
- **Trace Context Propagation** = passing a trace/span ID across service/process boundaries so spans link into one trace
- **OpenTelemetry (OTel)** = CNCF vendor-neutral standard/SDK for producing metrics, logs, and traces
- **Collector** = a standalone process that receives, processes, and exports telemetry data
- **Exporter** = the piece that ships telemetry to a backend (Jaeger, Prometheus, Datadog, etc.)
- **Jaeger** = distributed tracing backend + UI, originally built at Uber
- **Zipkin** = distributed tracing backend + UI, originally built at Twitter, predates Jaeger

---

## Why This Matters

```
"It's slow" is not a debuggable statement on its own.

Three pillars answer three different questions:

   METRICS → "IS something wrong, and how bad?"
             (error rate spiked to 8%, p99 latency is 3x normal)

   LOGS    → "WHAT exactly happened?"
             (this specific request threw a NullPointerException
              at line 42 with this stack trace)

   TRACES  → "WHERE in the request path did it go wrong?"
             (the request spent 4.2s total: 50ms in API gateway,
              120ms in auth-service, 3.9s in the payments-service
              call to a third-party API — THAT'S your bottleneck)

Without all three, you're debugging production blind.
Metrics tell you to look. Traces tell you WHERE to look.
Logs tell you WHY once you're there.
```

A senior DevOps/backend engineer is expected to design this pipeline, not just "add some print statements" — that's the gap between junior and senior debugging.

---

## The Three Pillars — Detailed

### 1. Metrics

Numeric time-series data, cheap to store and query at scale, ideal for dashboards and alerting.

| Type | What it measures | Real example |
|---|---|---|
| **Counter** | Monotonically increasing value | `http_requests_total`, `orders_created_total` |
| **Gauge** | Value that goes up and down | `active_connections`, `queue_depth`, `memory_used_bytes` |
| **Histogram** | Distribution of values in buckets | `http_request_duration_seconds` (lets you compute p50/p95/p99) |
| **Summary** | Like histogram but computes quantiles client-side | Similar use case, less flexible for aggregation across instances |

**Answers:** "Is the error rate up? Is latency degrading? Is the queue backing up?"
**Backend:** Prometheus (pull-based scraping) + Grafana (visualization). Deep coverage: `Backend_Developer/01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md`.
**Cost profile:** cheap — aggregated numbers, not full event payloads. This is why metrics are your first alert layer, not logs.

### 2. Logs

Discrete events, usually free-text or structured JSON, one line per event.

```json
{"timestamp": "2026-07-25T10:15:32Z", "level": "ERROR", "service": "payments-api",
 "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "message": "Payment gateway timeout",
 "order_id": "ORD-8842", "duration_ms": 5023}
```

**Answers:** "What exactly happened, with what data, at what exact moment?"
**Backend:** ELK (Elasticsearch/Logstash/Kibana) or Loki (Grafana's log aggregator, cheaper — indexes labels not full text). Deep coverage: `Backend_Developer/01_Year3-4_Mid/04_DevOps/08_elk_loki_logging.md`.
**Key discipline:** structured logging (JSON, not free text) with a `trace_id` field on every log line — this is what lets you jump from a trace span straight to the exact log lines for that request. Unstructured logs at scale are just an expensive grep target.
**Cost profile:** expensive at high volume — full payloads, full retention. This is why you sample or set aggressive retention on DEBUG/INFO in production and keep ERROR/WARN longer.

### 3. Traces

The path a single request takes across every service, process, and thread it touches.

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
│
├── Span: api-gateway [50ms]
│   └── Span: auth-service.verify_token [12ms]
│
├── Span: orders-service.create_order [180ms]
│   ├── Span: db.insert order [15ms]
│   └── Span: payments-service.charge [4900ms]  ← THE BOTTLENECK
│       └── Span: stripe-api.POST /charges [4870ms]
│
Total: 5.13s
```

**Answers:** "Where in this distributed call chain did the time go, and which service is the actual culprit?"
**Backend:** Jaeger or Zipkin (below) for visualization, OpenTelemetry for instrumentation.
**Key mechanic — context propagation:** each incoming request either starts a new trace or continues one, via a `trace_id` passed in HTTP headers (commonly `traceparent`, the W3C Trace Context standard). Every service that receives that header creates child spans under the same trace, so a request through 6 microservices still renders as ONE tree, not 6 disconnected logs.

---

## OpenTelemetry (OTel) — The Vendor-Neutral Standard

**The problem it solves:** before OTel, every vendor (Datadog, New Relic, Jaeger's own SDK) had its own instrumentation library. Switching backends meant re-instrumenting your entire codebase. OTel decouples "how you instrument code" from "where the data ends up."

### Architecture

```
Your App
   │  (OTel SDK: auto-instrumentation + manual spans)
   ▼
OTel SDK ──exports──> OTel Collector ──exports──> Backend(s)
                       (batches, filters,           (Jaeger, Prometheus,
                        adds attributes,              Datadog, Honeycomb,
                        routes to multiple             CloudWatch...)
                        backends)
```

- **SDK** — lives in your application process. Auto-instrumentation hooks common frameworks (Django, FastAPI, requests, psycopg2, SQLAlchemy) without code changes; manual instrumentation lets you add custom spans/attributes for business-specific logic.
- **Collector** — a separate deployable process (usually a sidecar or a cluster-wide DaemonSet in K8s) that receives telemetry over OTLP (OpenTelemetry Protocol), can batch/filter/enrich it, and fans it out to one or more backends. This decoupling means you can switch from Jaeger to Datadog by changing a Collector config, not your application code.
- **Exporter** — the piece (in the SDK or the Collector) that speaks the specific backend's wire format (Jaeger exporter, Prometheus remote-write exporter, OTLP exporter).

### Real Python Auto-Instrumentation Snippet

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install   # auto-installs instrumentors for detected libs (Django, requests, etc.)
```

```bash
opentelemetry-instrument \
    --traces_exporter otlp \
    --metrics_exporter otlp \
    --exporter_otlp_endpoint http://otel-collector:4317 \
    --service_name orders-api \
    python manage.py runserver 0.0.0.0:8000
```

This wraps your process, patches known libraries (Django ORM, `requests`, `psycopg2`) to auto-generate spans, and ships them to the Collector — zero application code changes for the common case. Manual spans (for business logic OTel can't see) look like:

```python
from opentelemetry import trace
tracer = trace.get_tracer("orders-api")

with tracer.start_as_current_span("apply_discount_rules") as span:
    span.set_attribute("order.id", order.id)
    span.set_attribute("discount.code", code)
    discount = calculate_discount(order, code)
    span.set_attribute("discount.amount", discount)
```

For full production wiring (Collector config YAML, sampling strategies, context propagation across Celery/message queues, correlating logs+traces), see `Backend_Developer/01_Year3-4_Mid/04_DevOps/19_opentelemetry_distributed_tracing.md`.

---

## Jaeger

- CNCF project, originally built at **Uber** for their microservices scale
- Stores and visualizes traces as a **Gantt-chart-style timeline** — this repo's example above (nested spans with durations) is exactly what Jaeger's UI renders
- Backend storage: Elasticsearch, Cassandra, or in-memory (dev only)
- Speaks OTLP natively — the standard target when you're OTel-instrumented and self-hosting rather than paying a SaaS vendor
- **Where you'll deploy it:** as a Collector export target inside a K8s cluster, often alongside Prometheus/Grafana for a full self-hosted observability stack

## Zipkin

- Older than Jaeger — built at **Twitter**, inspired by Google's Dapper paper (same paper that inspired Jaeger)
- Simpler architecture, smaller footprint, less actively evolving than Jaeger in the CNCF ecosystem
- Uses its own `B3` propagation header format (`X-B3-TraceId`, `X-B3-SpanId`) as opposed to Jaeger/OTel's default W3C `traceparent` — though both now support each other's formats via OTel's propagator config
- **When teams still pick it:** legacy systems already instrumented with Zipkin/B3 headers, teams that want a lighter-weight single-binary tracing backend without Elasticsearch/Cassandra as a storage dependency, or Spring Cloud Sleuth shops (Zipkin has long-standing first-class Spring integration)
- **Practical take:** if you're starting fresh in 2026, default to Jaeger (or a SaaS OTel backend) — it has stronger CNCF momentum and native OTLP support. Know Zipkin exists mainly to recognize it in a legacy stack and know its headers aren't W3C by default.

---

## Comparison Table — Choosing a Backend

| | Prometheus | ELK / Loki | Jaeger | Zipkin |
|---|---|---|---|---|
| Pillar | Metrics | Logs | Traces | Traces |
| Data model | Time-series, pull-based scrape | Full-text / labeled log lines | Span trees per trace ID | Span trees per trace ID |
| Storage cost | Low | High (ELK) / Medium (Loki) | Medium-High | Medium |
| Query language | PromQL | KQL/Lucene (ELK), LogQL (Loki) | Trace/tag search, service graph | Trace/tag search |
| Primary use | Dashboards + alerting | Root-cause detail, audit | Cross-service latency debugging | Cross-service latency debugging (legacy/simpler) |
| OTel-native | Yes (via remote-write exporter) | Yes (via OTLP log exporter) | Yes (OTLP native) | Partial (B3 propagation legacy) |

---

## Senior Tip

```
When an incident hits, the correct order of investigation is usually:

1. METRICS dashboard — confirm the blast radius (which service, since when,
   how bad). This is where alerting fired from.

2. TRACES — for a handful of slow/failed request IDs, find WHICH span
   in the chain is eating the time or throwing the error.

3. LOGS — jump into that specific service's logs FILTERED BY trace_id
   to get the exact error/stack trace/payload.

Doing this backwards (grepping logs across 12 services with no trace_id
to anchor on) is what turns a 10-minute incident into a 2-hour one.
This progression — metrics to narrow, traces to localize, logs to explain —
is the single most senior-signaling answer in an observability interview.
```

## Interview Angle

**Q: "We added OpenTelemetry but our traces show gaps — a span in service B doesn't show up under the parent span from service A. What's likely wrong?"**

Most common causes: (1) context isn't being propagated across the boundary — e.g., a message queue hop (Celery, SQS, Kafka) where the trace headers weren't carried in the message metadata, so service B starts a brand-new trace instead of continuing the old one; (2) a manual HTTP client that doesn't inject the `traceparent` header (raw `requests.get()` without the auto-instrumentation patch applied); (3) sampling — if each service samples independently instead of using head-based sampling decided once at the entry point, you can get partial traces where some services sampled the request and others didn't.

---

## Related

- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/19_opentelemetry_distributed_tracing.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/19_opentelemetry_distributed_tracing.md) — full instrumentation depth, Collector YAML, Celery/queue propagation
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md) — metrics stack in depth
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/08_elk_loki_logging.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/08_elk_loki_logging.md) — logging stack in depth
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md) — turning metrics into SLIs/SLOs and error budgets
- [`../18_System_Design/01_system_design_fundamentals.md`](../18_System_Design/01_system_design_fundamentals.md) — the architectures you're observing
