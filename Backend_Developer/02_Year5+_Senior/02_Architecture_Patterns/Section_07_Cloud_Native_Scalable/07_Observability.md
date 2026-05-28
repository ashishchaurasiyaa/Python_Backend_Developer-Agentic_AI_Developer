# Lecture 7: Observability — Logs, Metrics, and Tracing

> *"You can't manage what you can't measure. You can't fix what you can't see."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why observability matters** in cloud architecture
- **Three pillars** — logs, metrics, tracing
- **OpenTelemetry** — the unified standard
- **SLI / SLO / SLA** — designing for reliability
- **Health checks** + alerting
- **Best practices** for observable systems

---

## 1. Why Observability Matters

### Cloud Reality

```
Modern cloud systems:
   ✓ Containers spin up + down
   ✓ Services talk across network
   ✓ Traffic patterns change
   ✓ Multiple cloud regions
   ✓ Many moving parts
```

### Failure Modes

```
Failures cascade:
   ✗ One slow service → cascading slowness
   ✗ One bad release → ripple effect
   ✗ Network blip → multiple service errors
   
Hard to debug without VISIBILITY.
```

### What Observability Provides

```
✓ Real-time understanding of system behavior
✓ Catch problems BEFORE outages
✓ Diagnose issues quickly
✓ Scale intelligently based on usage
✓ Validate that fixes worked
```

### Monitoring vs Observability

```
MONITORING:
   ✓ Predefined dashboards
   ✓ Known questions ("Is CPU high?")
   ✓ Alerting on thresholds

OBSERVABILITY:
   ✓ Ad-hoc exploration
   ✓ Unknown questions
   ✓ Debug new issues
   ✓ Rich context everywhere

→ Modern systems need BOTH.
```

---

## 2. The Three Pillars

### Pillar 1: Logs

```
✓ DISCRETE EVENTS
   - Errors, warnings, actions
   - Timestamped records
   
✓ Use case: WHAT happened?
   - Root cause analysis
   - Audit trail
   - Forensic analysis
   
✓ Tools: ELK, Loki, Splunk, Datadog
```

### Pillar 2: Metrics

```
✓ TIME-SERIES DATA
   - CPU, memory, request rate
   - Aggregated numbers
   
✓ Use case: HOW MUCH? HOW FAST?
   - Dashboards
   - Alerting
   - Auto-scaling decisions
   
✓ Tools: Prometheus, Grafana, Datadog
```

### Pillar 3: Tracing

```
✓ REQUEST FLOWS
   - Follow request across services
   - See each hop's latency
   
✓ Use case: WHY was it slow?
   - Performance issues
   - Service dependencies
   - Distributed bottlenecks
   
✓ Tools: Jaeger, Zipkin, AWS X-Ray
```

### Visual

```
   ┌────────────────────────────────────────────┐
   │      THREE PILLARS OF OBSERVABILITY          │
   ├────────────────────────────────────────────┤
   │                                              │
   │   LOGS    │   METRICS   │   TRACES          │
   │   "What   │   "How      │   "Why was it     │
   │   happened│   fast/many"│   slow?"          │
   │   ?"      │             │                   │
   │           │             │                   │
   │   Events  │   Time      │   Request         │
   │           │   series    │   flow            │
   │                                              │
   └────────────────────────────────────────────┘
   
   Together: COMPLETE visibility
```

---

## 3. Logs — Deep Dive

### What to Log

```
SECURITY EVENTS:
   ✓ Auth attempts (success + failure)
   ✓ Permission denied
   ✓ Account changes
   ✓ Sensitive data access

BUSINESS EVENTS:
   ✓ Orders placed
   ✓ Payments processed
   ✓ User signups
   ✓ Important actions

ERRORS:
   ✓ Exceptions
   ✓ Failed external calls
   ✓ Validation errors
   ✓ Stack traces

DEBUGGING:
   ✓ State changes
   ✓ Function entry/exit (DEBUG level)
   ✓ External call params
```

### What NOT to Log

```
✗ Passwords
✗ Credit card numbers
✗ SSN / PII
✗ JWT tokens (full)
✗ API keys

→ Always scrub sensitive data!
```

### Structured Logging

```python
# BAD: Unstructured
print(f"User {user_id} placed order {order_id} for ${amount}")
# Hard to parse, search, aggregate

# GOOD: Structured JSON
logger.info("Order placed", extra={
    "user_id": user_id,
    "order_id": order_id,
    "amount": amount,
    "items_count": len(items),
})
# Easy to query: "show me all orders > $100"
```

### Log Levels

```
TRACE: Very detailed (usually off in prod)
DEBUG: Detailed info (off in prod usually)
INFO:  Normal operations
WARN:  Something unusual but not an error
ERROR: Something failed
FATAL: System unusable
```

### Centralized Logging

```
   App 1 ──┐
   App 2 ──┤
   App 3 ──┼──► stdout ──► Collector ──► Central Store
   App N ──┘    (Fluentd,    (Elasticsearch,
                 Logstash)    Loki, S3)
                                 │
                                 ▼
                          Search, alert, analyze
```

---

## 4. Metrics — Deep Dive

### Types of Metrics

```
1. COUNTER (monotonic)
   ✓ requests_total
   ✓ errors_total
   ✓ orders_placed_total
   - Only goes up

2. GAUGE (current value)
   ✓ cpu_usage_percent
   ✓ memory_used_bytes
   ✓ active_connections
   - Can go up + down

3. HISTOGRAM (distribution)
   ✓ request_duration_seconds
   ✓ response_size_bytes
   - Buckets of values
   - Calculate percentiles

4. SUMMARY (similar to histogram)
   - Server-side percentiles
   - Less flexible than histogram
```

### Golden Signals (Google SRE)

```
For every service, track:

1. LATENCY
   ✓ How long requests take
   ✓ Track P50, P95, P99

2. TRAFFIC
   ✓ Requests per second
   ✓ Active connections

3. ERRORS
   ✓ Error rate
   ✓ Failed request count

4. SATURATION
   ✓ How "full" is the system
   ✓ CPU, memory, queue depth
```

### Prometheus Example

```python
from prometheus_client import Counter, Histogram, Gauge

# Counter
REQUESTS = Counter('http_requests_total', 'Total requests', ['method', 'endpoint', 'status'])

# Gauge
ACTIVE = Gauge('active_connections', 'Currently active connections')

# Histogram
LATENCY = Histogram('http_request_duration_seconds', 'Request latency',
                     buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])

@app.middleware("http")
async def metrics(request, call_next):
    ACTIVE.inc()
    start = time.time()
    
    try:
        response = await call_next(request)
        REQUESTS.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        return response
    finally:
        LATENCY.observe(time.time() - start)
        ACTIVE.dec()
```

### Querying Metrics (PromQL)

```promql
# Request rate (per second)
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) 
  / rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, 
  rate(http_request_duration_seconds_bucket[5m]))

# Top 5 slowest endpoints
topk(5, 
  histogram_quantile(0.95, 
    rate(http_request_duration_seconds_bucket[5m])) 
  by (endpoint))
```

---

## 5. Tracing — Deep Dive

### The Problem It Solves

```
Microservices request flow:
   User → API Gateway → Service A → Service B
                                  → Service C → DB
                       → Service D → Cache

Without tracing:
   ✗ Hard to know which service is slow
   ✗ Each service has separate logs
   ✗ Logs not correlated

With tracing:
   ✓ Follow request end-to-end
   ✓ See each hop's duration
   ✓ Identify bottlenecks
```

### Anatomy of a Trace

```
TRACE = the entire request journey
   Has unique trace_id

SPAN = one step in the trace
   Has unique span_id
   References parent span
   
Each service creates ONE span per operation.
```

### Visual

```
Trace: 4d1e0f9a2b3c4d5e6f
   ├─ [200ms] API Gateway
   │   ├─ [180ms] Auth check
   │   │   └─ [60ms]  validate_token
   │   ├─ [150ms] User Service call
   │   │   ├─ [80ms]  DB query
   │   │   └─ [30ms]  cache lookup
   │   └─ [120ms] Order Service call
   │       ├─ [50ms]  Payment Service
   │       └─ [30ms]  Inventory Service
   └─ [10ms]  Response serialization
```

### OpenTelemetry Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Set up
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    ))
)

# Auto-instrument
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()

# Custom spans
tracer = trace.get_tracer(__name__)

@app.post("/orders")
async def create_order(req):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("user.id", req.user_id)
        span.set_attribute("items.count", len(req.items))
        
        # Nested span
        with tracer.start_as_current_span("validate_inventory"):
            await inventory_service.check(req.items)
        
        with tracer.start_as_current_span("charge_payment"):
            await payment_service.charge(req.amount)
        
        return {"order_id": "..."}
```

---

## 6. OpenTelemetry — The Unified Standard

### Why It Matters

```
Before OpenTelemetry:
   ✗ Separate libraries for each backend
   ✗ Vendor-specific SDKs
   ✗ Hard to switch vendors
   ✗ Inconsistent across services
```

### OpenTelemetry Solution

```
✓ ONE SDK for logs, metrics, traces
✓ Vendor-neutral
✓ Wide language support
✓ Auto-instrumentation for common libs
✓ Industry standard (CNCF graduated)
```

### Architecture

```
   Your App
       │
       │ OpenTelemetry SDK
       ▼
   ┌─────────────┐
   │  Collector  │   ← Process, batch, route
   └──────┬──────┘
          │
   ┌──────┼──────┬──────┬──────┐
   ▼      ▼      ▼      ▼      ▼
 Prometheus Jaeger Datadog ES Splunk
 (metrics) (traces) (all)   (logs)
```

### Auto-Instrumentation

```python
# Just add the instrumentation, no code changes!
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
Psycopg2Instrumentor().instrument()

# Now ALL HTTP calls + DB queries auto-traced!
```

---

## 7. SLI / SLO / SLA

### Definitions

```
SLI (Service Level Indicator):
   A METRIC that measures service performance
   Example: "% of HTTP requests that succeed"

SLO (Service Level Objective):
   A TARGET for that SLI
   Example: "99.9% requests succeed in 30 days"
   (Internal goal)

SLA (Service Level Agreement):
   A CONTRACT with consequences
   Example: "99.5% uptime or refund"
   (External commitment)
```

### Relationship

```
   SLI: 99.95% currently  ← Reality
   SLO: 99.9% target       ← Internal goal
   SLA: 99.5% commitment   ← External contract
   
   SLA < SLO < 100%        ← Always have margin
```

### Error Budget

```
SLO = 99.9% (0.1% errors allowed)

In 30 days:
   Total time: 43,200 minutes
   Allowed downtime: 43.2 minutes ← ERROR BUDGET

If you've had 30 min downtime:
   Used: 30 min
   Remaining: 13.2 min
   
   "Slow down new releases" if depleting fast!
```

### Designing for SLOs

```
SLO: 99.9% requests succeed
   →
   Architecture decisions:
   ✓ Need redundancy
   ✓ Need health checks
   ✓ Need failover
   ✓ Need monitoring
   ✓ Need on-call

SLO drives DESIGN, not the other way around.
```

### Example SLIs/SLOs

```
SERVICE: User API

SLI 1: Availability
   "% of requests not returning 5xx"
SLO 1: 99.95% over 30 days

SLI 2: Latency
   "% of requests under 200ms"
SLO 2: 95% under 200ms

SLI 3: Quality
   "% of requests with valid response"
SLO 3: 99.99%
```

---

## 8. Health Checks + Alerting

### Health Checks

```
LIVENESS:
   "Is the app alive?"
   ✓ Restart on failure
   ✓ Should NOT check dependencies
   ✓ Just app responsiveness

READINESS:
   "Is the app ready to serve traffic?"
   ✓ Remove from LB on failure
   ✓ DOES check dependencies (DB, cache)
   ✓ Slow recovery acceptable

STARTUP:
   "Has app started?"
   ✓ Slower threshold during startup
   ✓ Prevents premature liveness fails
```

### Implementation

```python
@app.get("/health/live")
async def liveness():
    """Just is the app alive?"""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """Are we ready for traffic?"""
    try:
        # Check critical dependencies
        await db.fetchval("SELECT 1")
        await cache.ping()
        return {"status": "ready"}
    except Exception as e:
        return Response(
            status_code=503,
            content={"status": "not ready", "error": str(e)}
        )

@app.get("/health/startup")
async def startup():
    """Have we fully started?"""
    if not app.state.initialization_complete:
        return Response(status_code=503)
    return {"status": "started"}
```

### Alerting Strategy

```
ALERT ON SYMPTOMS, NOT CAUSES:

✓ "Error rate increased to 5%" (symptom)
✗ "CPU at 90%" (potential cause - may be fine)

✓ "P99 latency > 2 seconds" (symptom)
✗ "Memory at 80%" (might be normal)

→ Alerts should mean: "User experience is affected"
```

### Alert Quality

```
GOOD ALERTS:
   ✓ Actionable
   ✓ Specific
   ✓ Useful context
   ✓ Clear severity

BAD ALERTS:
   ✗ Vague ("Something's wrong")
   ✗ Constant (alert fatigue)
   ✗ Not actionable
   ✗ Wake up at 3 AM unnecessarily
```

### On-Call Best Practices

```
✓ Rotate on-call duty
✓ Clear runbooks per alert
✓ Auto-remediation where possible
✓ Postmortem culture
✓ Page the right person
✓ Keep alert volume manageable
```

---

## 9. Tooling Ecosystem

### Logs

```
✓ ELK Stack (Elasticsearch + Logstash + Kibana)
✓ Loki + Grafana (lightweight)
✓ Splunk (enterprise)
✓ Datadog (managed)
✓ CloudWatch Logs
✓ Azure Monitor Logs
✓ Sumo Logic
```

### Metrics

```
✓ Prometheus + Grafana (cloud-native standard)
✓ Datadog
✓ New Relic
✓ CloudWatch Metrics
✓ Azure Monitor
✓ Stackdriver (GCP)
✓ Wavefront
```

### Tracing

```
✓ Jaeger (open-source)
✓ Zipkin (open-source)
✓ AWS X-Ray
✓ Google Cloud Trace
✓ Azure Application Insights
✓ Datadog APM
✓ New Relic APM
```

### All-in-One

```
✓ Datadog (logs + metrics + traces)
✓ New Relic (full observability)
✓ Dynatrace (AI-powered)
✓ Honeycomb (event-based)
✓ Lightstep (now ServiceNow)
✓ Grafana Cloud (open-source friendly)
```

---

## 10. Best Practices

### Practice 1: Instrument Everything

```
✓ All HTTP endpoints (auto-instrument)
✓ All database queries
✓ All external API calls
✓ All async tasks
✓ Custom business logic

→ Default to "instrument", opt out where needed
```

### Practice 2: Use Correlation IDs

```python
# Add to every request
@app.middleware("http")
async def correlation_id(request, call_next):
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    request.state.correlation_id = cid
    
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response

# Include in ALL logs
logger.info("Action", extra={"correlation_id": request.state.correlation_id})

# Forward to downstream
await httpx.get(url, headers={"X-Correlation-Id": request.state.correlation_id})
```

### Practice 3: Structured Logging Everywhere

```python
# JSON logs everywhere
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()
logger.info("user_login", user_id=123, ip="1.2.3.4")
# {"timestamp": "...", "level": "info", "event": "user_login", ...}
```

### Practice 4: Dashboards

```
Per service, create:
   ✓ Golden signals (latency, traffic, errors, saturation)
   ✓ Business metrics (orders, signups, etc.)
   ✓ Dependency health
   ✓ Resource usage

Per team:
   ✓ Service overview
   ✓ SLO tracking
   ✓ Active incidents
```

### Practice 5: Test Failures

```
Chaos engineering:
   ✓ Kill instances randomly
   ✓ Inject latency
   ✓ Simulate failures
   ✓ Verify observability captures it
   
Reveal blind spots BEFORE production issues!
```

### Practice 6: Cardinality Awareness

```
✗ DON'T use high-cardinality labels:
   - user_id (millions of values)
   - order_id (millions)
   - URL with IDs

✓ DO use bounded cardinality:
   - endpoint pattern (/users/:id, not /users/123)
   - HTTP method
   - Status code
   - Service name

→ High cardinality kills your TSDB
```

---

## 11. Common Anti-Patterns

### Anti-Pattern 1: Log Everything

```
❌ DEBUG logs in production
❌ Logging full request bodies
❌ Logging every function call

Result:
   ✗ Storage costs explode
   ✗ Hard to find what matters
   ✗ Performance impact

✅ Log meaningful events
✅ Adjust levels per environment
```

### Anti-Pattern 2: Alert On Causes, Not Symptoms

```
❌ "Alert when CPU > 80%"

Problem: CPU 80% may be FINE
   - Auto-scaling will handle it
   - User experience may not be affected

✅ "Alert when error rate > 1%"
✅ "Alert when P95 latency > 1s"
   → User experience IS affected
```

### Anti-Pattern 3: No Correlation IDs

```
❌ Logs from different services not connected

Result: Can't follow a request across services

✅ Pass correlation ID everywhere
✅ Include in every log entry
```

### Anti-Pattern 4: Missing Context

```
❌ "Database error"

Result: Useless

✅ "Database error",
   query="SELECT...", 
   duration_ms=5000, 
   error="connection timeout"

→ Now actionable!
```

### Anti-Pattern 5: Not Practicing Incident Response

```
❌ "Hope incidents don't happen"

Reality: They WILL happen

✅ Game days
✅ Runbooks
✅ On-call training
✅ Postmortems
```

---

## 12. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Observability = real-time understanding of behavior        │
│  ✅ Three pillars: logs, metrics, traces                       │
│  ✅ Logs: what happened (events)                               │
│  ✅ Metrics: how much/fast (time-series)                       │
│  ✅ Traces: why slow (request flows)                           │
│  ✅ OpenTelemetry is the unified standard                      │
│  ✅ SLI → SLO → SLA hierarchy                                  │
│  ✅ Error budgets enable risk management                       │
│  ✅ Health checks: liveness + readiness + startup              │
│  ✅ Alert on SYMPTOMS, not causes                              │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. INSTRUMENT everything (auto + custom)
2. Use STRUCTURED logs (JSON)
3. Include CORRELATION IDs in all logs
4. Track GOLDEN SIGNALS (latency, traffic, errors, saturation)
5. Use OPENTELEMETRY for standardization
6. Define SLOs based on user experience
7. Track ERROR BUDGETS
8. Alert on SYMPTOMS not causes
9. Practice INCIDENT RESPONSE
10. CHAOS test to reveal blind spots
```

---

## 🎬 Section Complete!

Congratulations! You've completed **Section 7: Cloud-Native & Scalable Architecture Styles**!

### What You've Learned

```
✓ Cloud service models (IaaS, PaaS, SaaS)
✓ 12-Factor App methodology
✓ Serverless architecture (FaaS)
✓ Docker + Kubernetes
✓ Load balancing + auto-scaling
✓ Edge architecture (CDN + edge functions)
✓ Observability (logs, metrics, traces)
```

### Practical file: [07_Practical_Hands_On.md](07_Practical_Hands_On.md)

---

## 🚀 What's Next?

Continue with:
- **Section 8**: UI Architecture Patterns for Apps
- **Section 9**: Architectural Decision-Making & Trade-Offs
- **Section 10**: Conclusion & Next Steps

---

## 📚 References

- *Observability Engineering* — Charity Majors et al.
- *Site Reliability Engineering* — Google
- OpenTelemetry documentation
- Prometheus + Grafana docs
- *Distributed Tracing in Practice* — Austin Parker
- Honeycomb blog (excellent observability content)
