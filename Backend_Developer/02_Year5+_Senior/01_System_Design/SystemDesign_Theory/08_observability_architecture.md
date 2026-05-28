# 🔭 Observability Architecture — Logs, Metrics, Traces

> **Target:** 3-5 YOE | **Goal:** Production systems ko kaise observe karein, debug karein, monitor karein.

---

## Part 1: WHAT — Observability Kya Hai?

### Definition

> **Observability** = ability to **understand system's internal state** by examining outputs (logs, metrics, traces).

### Real-Life Analogy 🚗

Soch ek **car dashboard**:
- Speedometer (metrics)
- Engine warning lights (alerts)
- Trip computer (logs)
- Diagnostic codes (traces)

**Without dashboard**: drive blind, surprise breakdowns.
**With dashboard**: know everything happening.

**Production system without observability = driving blind.**

### Monitoring vs Observability

#### Monitoring
> Known unknowns. Pre-defined alerts.

"Is the server up?"

#### Observability
> Unknown unknowns. Investigate anything.

"Why is response time slow for users in Mumbai during 2-4 PM?"

---

## Part 2: WHY — Observability Critical?

### Reason 1: Detect Problems

Issue happening → know immediately.

### Reason 2: Debug Faster

Production bug → find root cause.

### Reason 3: Understand Performance

Bottlenecks, slow queries.

### Reason 4: Capacity Planning

Trends predict future needs.

### Reason 5: Business Insights

User behavior, feature usage.

### Reason 6: Reliability

Better visibility = better reliability.

### Reason 7: Senior Skill

Junior writes code.
Senior runs systems.

---

## Part 3: THE THREE PILLARS

### Pillar 1: Logs

> **Discrete events with context.**

```
2024-01-15 14:32:01 INFO User 123 logged in from IP 1.2.3.4
2024-01-15 14:32:02 ERROR Payment failed: insufficient funds for user 123
```

### Pillar 2: Metrics

> **Numerical measurements over time.**

```
http_requests_total{method="GET", status="200"} = 152345
response_time_seconds{p99} = 0.234
cpu_usage_percent = 65
```

### Pillar 3: Traces

> **Request journey through distributed system.**

```
Request → API Gateway → Auth Service → User Service → DB
           ↓             ↓               ↓             ↓
          10ms         50ms            30ms          15ms
```

### How They Work Together

```
ALERT (metric): "Error rate spike!"
   ↓
LOGS: "What errors specifically?"
   ↓
TRACES: "Which requests, which services?"
   ↓
RESOLUTION
```

---

## Part 4: LOGS DEEP

### What to Log

#### Information
- Request received
- Operations performed
- Decisions made
- Errors

#### Don't Log
- Passwords
- Credit cards
- PII (personally identifiable info)
- Tokens

### Log Levels

```
DEBUG    - Verbose, dev/troubleshoot
INFO     - Normal flow
WARN     - Concerning but works
ERROR    - Failed operation
CRITICAL - System failure
```

### Structured Logs

#### Bad (Unstructured)

```
User Bhai logged in from IP 1.2.3.4
```

Hard to query.

#### Good (Structured)

```json
{
  "timestamp": "2024-01-15T14:32:01Z",
  "level": "INFO",
  "message": "User logged in",
  "user_id": 123,
  "username": "bhai",
  "ip": "1.2.3.4",
  "service": "auth-service",
  "trace_id": "abc123"
}
```

Searchable, filterable.

### Log Aggregation

> **Centralize logs from all services.**

#### Architecture

```
Each Service
   ↓
Log Shipper (Fluentd, Logstash)
   ↓
Centralized Storage (Elasticsearch, Loki)
   ↓
Visualization (Kibana, Grafana)
```

### Popular Stacks

#### ELK
- Elasticsearch (storage)
- Logstash (processing)
- Kibana (UI)

#### EFK
- Replace Logstash with Fluentd

#### Grafana Loki
- Cheaper for high volume
- Index labels, not content
- Grafana UI

#### Datadog / Splunk
- Managed
- Expensive
- Powerful

### Retention

```
7 days: hot (fast queries)
30 days: warm (slower)
1 year: cold (archive, slow)
```

Save costs.

### Costs

Logs can cost MORE than compute:
- High volume
- Long retention
- Expensive storage

#### Optimize
- Log smartly (not everything)
- Sample where appropriate
- Compress
- Tier storage

---

## Part 5: METRICS DEEP

### Types of Metrics

#### Counter
> Monotonically increasing.

```
http_requests_total
errors_total
bytes_processed_total
```

Use for: counts, totals.

#### Gauge
> Value at point in time.

```
cpu_usage_percent
memory_used_bytes
queue_depth
active_users
```

Use for: instantaneous values.

#### Histogram
> Distribution of values.

```
response_time_seconds:
  - p50: 0.05
  - p95: 0.2
  - p99: 0.5
  - p99.9: 1.0
```

Use for: latencies, sizes.

#### Summary
> Similar to histogram, server-side computed.

### What to Measure

#### Four Golden Signals (Google SRE)

##### 1. Latency
- p50, p95, p99
- Per endpoint

##### 2. Traffic
- Requests/sec
- Per service

##### 3. Errors
- Error rate
- Per type

##### 4. Saturation
- Resource utilization
- CPU, memory, disk, network

#### USE Method (Brendan Gregg)

For each resource:
- **Utilization**: % busy
- **Saturation**: backlog
- **Errors**: error count

#### RED Method (Tom Wilkie)

For services:
- **Rate**: requests/sec
- **Errors**: errors/sec
- **Duration**: latency

### Metric Naming

```
service_subsystem_unit
Example:
  payment_service_request_duration_seconds
  http_request_total
  db_query_count
```

### Cardinality

> Number of unique time series.

#### High Cardinality (Bad)
```
metric{user_id="123"}
metric{user_id="124"}
...
Millions of unique series
```

Expensive to store.

#### Low Cardinality (Good)
```
metric{service="api", endpoint="/users", status="200"}
Few hundred unique series
```

Keep cardinality reasonable.

### Tools

#### Prometheus
> Open source. Pull-based.

#### Graphite
> Older. Push-based.

#### InfluxDB
> Time-series DB.

#### Datadog
> Managed. Comprehensive.

#### CloudWatch
> AWS native.

#### Victoria Metrics
> Prometheus-compatible, scalable.

---

## Part 6: TRACES DEEP

### What is a Trace?

> **Single request's journey** through services.

### Components

#### Trace
> The complete journey.

#### Span
> One operation within trace.

```
Trace: User login
  Span: HTTP request (50ms)
    Span: Auth check (10ms)
      Span: DB query (5ms)
    Span: Generate token (5ms)
  Total: 50ms
```

### Visualization

```
HTTP Request ──────────────────────────────── 100ms
  Auth Service ──── 20ms
    DB Query ── 10ms
  Token Generation ──── 30ms
  Response Building ──── 40ms
```

### Why Critical

#### Bottleneck Identification
> Which span slow?

#### Cross-Service Debugging
> Where did request fail?

#### Performance Analysis
> Where to optimize?

### Distributed Tracing

> Trace across microservices.

#### How

1. Generate trace ID at entry
2. Pass through all services
3. Each service adds spans
4. Collected centrally

### OpenTelemetry

> **Vendor-neutral standard.** Industry consolidating around.

Replaces:
- OpenTracing
- OpenCensus

### Tools

#### Jaeger
> Open source.
> Originated at Uber.

#### Zipkin
> Older.
> Twitter origin.

#### AWS X-Ray
> AWS managed.

#### Honeycomb
> Modern, advanced.

#### DataDog APM
> Comprehensive.

#### Tempo (Grafana)
> Open source.

---

## Part 7: ALERTS

### Alert Categories

#### Critical (Wake up at 3 AM)
- Service down
- Data loss
- Security breach

#### Warning (Investigate during day)
- Latency degraded
- Error rate up
- Resource constraint

#### Info (Awareness only)
- Deploy completed
- Status changes

### Alert Best Practices

#### 1. Actionable

❌ "CPU is 90%"
✅ "CPU 90% sustained 10 min, response time degrading, scale up"

#### 2. Specific

❌ "Something is wrong"
✅ "Payment service error rate 5%, affecting checkout flow"

#### 3. Contextual

```
Alert: High error rate
Context:
  - Service: payment-service
  - Rate: 5% (normal 0.5%)
  - Started: 14:32 UTC
  - Recent deploy: 14:25 UTC
  - Runbook: [link]
```

### Alert Fatigue

> Too many alerts → ignored.

Solutions:
- Only critical alerts page on-call
- Severity tiers
- Alert routing
- Periodic review

### Alert Strategy

#### SLI / SLO / SLA

##### SLI (Service Level Indicator)
> Metric being tracked.

##### SLO (Service Level Objective)
> Target. Internal.

##### SLA (Service Level Agreement)
> Promised. Customer contract.

```
SLI: API success rate
SLO: 99.9% over 30 days
SLA: 99.5% (customer-facing, looser)
```

Alert when SLO at risk.

---

## Part 8: DASHBOARDS

### Purpose

> Visual at-a-glance.

### Hierarchy

#### Executive
> Business-level. CEO-facing.

- Revenue
- Active users
- Major outages

#### Service
> Engineering team.

- Service health
- Error rates
- Latencies

#### Operational
> SRE/DevOps.

- Infrastructure
- Resources
- Capacity

### Best Practices

#### Less is More

5-10 panels per dashboard max.
Too many = useless.

#### Time Range Important

- Real-time (last 15 min)
- Trends (last 24h)
- Comparisons (week-over-week)

#### Annotations

Mark deploys, incidents, changes.
Context for spikes.

### Tools

- **Grafana** (most popular)
- **Kibana** (with Elasticsearch)
- **Datadog** (managed)

---

## Part 9: REAL OBSERVABILITY EXAMPLE

### Incident Response

#### Alert Fires
```
Alert: High error rate
Service: payment-service
Severity: Critical
```

#### Step 1: Dashboard
```
Open payment-service dashboard.
See: Error rate spiked at 14:35
Latency normal
Traffic normal
```

#### Step 2: Logs
```
Search payment-service logs since 14:35:
  - Many "database connection timeout"
  - Errors point to user-service DB
```

#### Step 3: Trace
```
Pick failed request.
Trace shows:
  - API call → 30ms ✓
  - Payment processing → 50ms ✓
  - User lookup → TIMEOUT
```

#### Step 4: User-Service
```
Check user-service:
  - DB connections exhausted
  - Recent deploy at 14:33!
```

#### Step 5: Action
```
Rollback user-service deploy.
Errors stop.
Incident resolved.
```

#### Step 6: Post-mortem
- Add DB connection monitoring
- Better deploy validation
- Runbook for this scenario

---

## Part 10: OBSERVABILITY MATURITY

### Stage 1: Minimal

```
- Print statements
- Server logs
- Basic uptime check
```

Small startups.

### Stage 2: Basic Monitoring

```
- Aggregated logs
- Basic metrics (CPU, memory)
- Email alerts
```

Most companies start.

### Stage 3: Production Monitoring

```
- Structured logs centralized
- Custom metrics
- Dashboards
- Slack/PagerDuty alerts
- Some tracing
```

Mid-size companies.

### Stage 4: Mature Observability

```
- Distributed tracing
- SLOs defined
- Anomaly detection
- Continuous profiling
- Synthetics monitoring
```

Senior tech orgs.

### Stage 5: Observability Platform

```
- Self-service for engineers
- Auto-instrumentation
- AIOps
- Real user monitoring
- Business observability
```

Industry leaders.

---

## Part 11: COSTS

### Logs

> Can cost more than compute!

Optimize:
- Sample
- Filter at source
- Tier storage
- Shorter retention

### Metrics

> Cheaper than logs typically.

Watch cardinality.

### Traces

> Sampling critical.

Don't trace 100% — too expensive.
Sample 1% + always errors.

### Tools

#### Managed (Datadog, etc.)
- $$$
- Lower ops burden

#### Self-Hosted (Prometheus, ELK)
- $
- Higher ops burden

Trade-off.

---

## Part 12: TESTING OBSERVABILITY

### Synthetic Monitoring

> Fake users making requests.

- Detect issues before real users
- Test critical paths
- 24/7

### Real User Monitoring (RUM)

> Actual users' experience.

- Frontend metrics
- Geographic perspective
- Real-world data

### Chaos Engineering

> Intentionally break things.

Tests observability:
- Did alerts fire?
- Could you debug?
- Recovery worked?

---

## Part 13: OBSERVABILITY IN MICROSERVICES

### Challenges

- Many services
- Distributed
- Cross-service tracing
- Aggregation needed

### Solutions

#### Service Mesh
> Automatic observability for all services.

Istio, Linkerd provide.

#### OpenTelemetry
> Standard instrumentation.

#### Centralized Logging
> Required for microservices.

---

## Part 14: AI-POWERED OBSERVABILITY (2026)

### AIOps

> AI helps analyze observability data.

- Anomaly detection
- Root cause analysis
- Predictive alerts
- Noise reduction

### Tools

- Datadog Watchdog
- Dynatrace Davis
- New Relic AI

---

## Part 15: PRIVACY & COMPLIANCE

### PII in Logs

❌ Don't log:
- Names, emails
- Credit cards
- SSN
- Passwords

✅ Log:
- User IDs (not PII)
- Hashed values
- Sanitized data

### Compliance

#### GDPR
- Right to deletion
- Logs must comply

#### HIPAA
- Healthcare data
- Special handling

#### PCI-DSS
- Payment data
- Audit trails required

---

## Part 16: COMMON PITFALLS

### Pitfall 1: No Observability

> "We'll add later."

By then, too late.

### Pitfall 2: Too Much

> Log everything, alert on everything.

Alert fatigue. Costly.

### Pitfall 3: Wrong Metrics

> Vanity metrics (lines of code).

Not actionable.

### Pitfall 4: Sampling Wrong

> Sample errors out.

Lose visibility.

### Pitfall 5: No Documentation

> Dashboard exists, nobody knows.

Document everything.

### Pitfall 6: Reactive Only

> Wait for problems.

Better: proactive monitoring.

---

## Part 17: OBSERVABILITY CULTURE

### Make it Easy

- Auto-instrumentation
- Standardized formats
- Easy to add metrics

### Make it Used

- Onboarding includes
- Discussions reference dashboards
- Post-mortems use traces

### Make it Owned

- Each service has owner
- Owner ensures observability
- Reviews periodically

---

## Part 18: Q&A

### Q: Where to start observability?
**A**: Structured logs + basic metrics + uptime alerts. Add tracing as you grow.

### Q: Datadog or self-host?
**A**: Datadog faster setup. Self-host cheaper at scale.

### Q: How many alerts?
**A**: Few. Only actionable. Each requires response.

### Q: Trace sampling rate?
**A**: 1-10% normal traffic. 100% errors.

### Q: Log retention?
**A**: 7-30 days hot, 90-365 cold.

### Q: SRE vs DevOps?
**A**: SRE = focus on reliability. DevOps = broader. Overlap.

### Q: Distributed tracing necessary?
**A**: For microservices, yes. Otherwise optional.

---

## 🎯 Bhai's Final Words

> **You can't fix what you can't see. Observability is the eyes of production systems. Senior engineers prioritize it.**

3 Mantras:
1. **Structured logs** (queryable)
2. **Four golden signals** (basics)
3. **Trace critical paths** (distributed)

After mastering observability, you'll debug production incidents in minutes, not hours. 🚀
