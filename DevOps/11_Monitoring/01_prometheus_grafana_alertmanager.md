# Monitoring — Prometheus, Grafana, Alertmanager
**DevOps Track · Phase 11: Monitoring**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller tool/architecture picture.

## Quick Concepts

- **Prometheus** = open-source metrics collection + time-series database + query engine; pulls (scrapes) metrics from targets over HTTP
- **Exporter** = an HTTP endpoint exposing metrics in Prometheus text format (`/metrics`) that Prometheus scrapes
- **Metric** = a named, labeled time series (e.g., `http_requests_total{method="GET", status="200"}`)
- **PromQL** = Prometheus's query language for slicing/aggregating time series
- **Grafana** = visualization layer — dashboards, panels, alerting UI, sits on top of Prometheus (and other data sources)
- **Alertmanager** = separate component that receives firing alerts from Prometheus, deduplicates/groups/routes them, and sends notifications (Slack, PagerDuty, email)
- **RED Method** = Rate, Errors, Duration — the three numbers to watch for any request-driven service
- **USE Method** = Utilization, Saturation, Errors — the three numbers to watch for any resource (CPU, disk, memory)
- **Recording rule** = pre-computes an expensive query on a schedule, saving the result as a new time series
- **Silence** = a time-boxed rule telling Alertmanager not to notify for matching alerts — the tool for planned maintenance
- **Inhibition** = suppressing lower-severity alerts when a related, more-severe alert is already firing for the same root cause

---

## Why This Matters

```
"We have Grafana dashboards" is not the same as understanding what
you're looking at. Interviewers probe:
   - What's the difference between a counter and a gauge, and why
     does it matter for the query you'd write?
   - Write a PromQL query for p95 latency. Right now. On the board.
   - How does Alertmanager route a critical alert to PagerDuty but a
     warning to a Slack channel, without duplicating alert rules?

This file goes past "I looked at a dashboard someone else built" to
"I can build the exporter, write the query, and configure the routing."
```

---

## Prometheus: Metric Types

### Counter

Monotonically increasing value — only goes up (or resets to 0 on restart). Never use it raw; always wrap in `rate()` or `increase()`.

```python
from prometheus_client import Counter

http_requests_total = Counter(
    'http_requests_total', 'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
http_requests_total.labels(method='GET', endpoint='/orders', status='200').inc()
```
Use for: total requests served, total errors, total bytes sent.

### Gauge

A value that can go up or down — a snapshot at scrape time.

```python
from prometheus_client import Gauge

active_connections = Gauge('active_connections', 'Currently open connections')
active_connections.inc()   # +1
active_connections.dec()   # -1
active_connections.set(42) # absolute value
```
Use for: queue depth, active DB connections, memory in use, goroutines/threads running.

### Histogram

Samples observations into configurable buckets, and also exposes `_sum` and `_count`. Server-side, cheap to compute; quantiles are approximate (interpolated from buckets) and cannot be aggregated across instances after the fact with full accuracy.

```python
from prometheus_client import Histogram

request_duration = Histogram(
    'http_request_duration_seconds', 'Request latency',
    ['endpoint'], buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
)

@request_duration.labels(endpoint='/orders').time()
def handle_request():
    ...
```
Use for: request latency, response size — anything you'll want a percentile of.

### Summary

Like a histogram, but computes exact quantiles **client-side** at scrape time. More accurate per-instance, but quantiles can't be meaningfully averaged/aggregated across multiple instances (each instance computed its own). Also costlier on the client.

```python
from prometheus_client import Summary

REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing')

@REQUEST_TIME.time()
def process():
    ...
```

**Rule of thumb**: prefer Histogram in almost all modern setups — you can aggregate `histogram_quantile()` across all replicas of a service, which is what you actually want in a multi-instance production system. Summary is only preferable for single-instance, precision-critical measurements.

---

## Exporters

An exporter is just a process serving `/metrics` in Prometheus's text exposition format. Two flavors:

### `node_exporter` — Host-Level Metrics

Runs on every VM/bare-metal host, exposes CPU, memory, disk, network, filesystem metrics without any app code changes.

```bash
docker run -d --name node-exporter -p 9100:9100 \
  -v "/proc:/host/proc:ro" -v "/sys:/host/sys:ro" -v "/:/rootfs:ro" \
  prom/node-exporter \
  --path.procfs=/host/proc --path.sysfs=/host/sys \
  --collector.filesystem.mount-points-exclude='^/(sys|proc|dev|host|etc)($$|/)'
```

Exposes metrics like `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_filesystem_avail_bytes`.

### `blackbox_exporter` — Probing From the Outside

Different from node_exporter/app exporters, which report metrics FROM INSIDE a host/process. `blackbox_exporter` probes a target from OUTSIDE — HTTP, TCP, ICMP, DNS — the same vantage point a real user or an upstream dependency has.

```yaml
# prometheus.yml — Prometheus scrapes blackbox_exporter, which itself
# probes the REAL target on Prometheus's behalf
scrape_configs:
  - job_name: 'blackbox-http'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://api.example.com/health
          - https://example.com
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115   # actually scrape the EXPORTER,
                                                 # passing the real target as a param
```

```
Why this matters beyond node_exporter/app metrics: an app exporter
only reports what the app CAN see about itself — if the load balancer
in front of it is misconfigured, or DNS resolution to the service is
broken, the app's own metrics look perfectly healthy while real users
can't reach it at all. blackbox_exporter catches exactly that class of
failure, because it's probing from the same external vantage point a
real client has.
```

### Custom App Exporter (Client Library)

Your application registers its own metrics and serves them itself — this is what the counter/gauge/histogram examples above wire up.

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Histogram
import time

app = FastAPI()
app.mount("/metrics", make_asgi_app())

REQUESTS = Counter('http_requests_total', 'Total requests', ['method', 'path', 'status'])
LATENCY = Histogram('http_request_duration_seconds', 'Latency', ['path'])

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    LATENCY.labels(path=request.url.path).observe(time.time() - start)
    REQUESTS.labels(method=request.method, path=request.url.path,
                     status=response.status_code).inc()
    return response
```

Prometheus is then configured to scrape it — the FULL config, not just the scrape section, because this is also where Prometheus learns where its alert rule files and Alertmanager actually live:

```yaml
# prometheus.yml — the complete picture
global:
  scrape_interval: 15s        # default for every job unless overridden per-job
  evaluation_interval: 15s      # how often alert/recording rules are evaluated

rule_files:
  - "alerts.yml"                 # loads the alert rules shown later in this file
  - "recording_rules.yml"          # loads recording rules (below)

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']    # WITHOUT this block, Prometheus
                                               # can evaluate alert rules and
                                               # mark them "firing" internally,
                                               # but NEVER actually notifies
                                               # anyone — this is the single
                                               # most common "why isn't my
                                               # alert reaching Slack" cause

scrape_configs:
  - job_name: 'backend-api'
    static_configs:
      - targets: ['backend-api:8000']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

```bash
promtool check config prometheus.yml       # validate the whole config BEFORE
                                              # restarting Prometheus with it —
                                              # same "validate before apply"
                                              # discipline as terraform validate
promtool check rules alerts.yml               # validate alert/recording rule
                                                 # syntax specifically
```

### Service Discovery — Beyond Hand-Listing Targets

`static_configs` (above) means hand-maintaining a target list — fine for 2 exporters, unworkable once instances come and go via Auto Scaling or Kubernetes scheduling.

```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true          # only scrape Pods explicitly annotated to opt in

  - job_name: 'ec2-instances'
    ec2_sd_configs:
      - region: ap-south-1
        filters:
          - name: tag:Environment
            values: [production]
    relabel_configs:
      - source_labels: [__meta_ec2_tag_Name]
        target_label: instance_name
```

```
Same relationship as Ansible's dynamic inventory (Phase 9) to a static
inventory file — kubernetes_sd_configs/ec2_sd_configs QUERY the
platform's API at scrape time and build the target list automatically,
keyed by tags/annotations, instead of someone editing static_configs
every time a Pod reschedules or an ASG scales. relabel_configs is what
turns raw discovery metadata (__meta_* labels) into the actual labels
your metrics carry.
```

---

## PromQL — The RED Method

RED = **R**ate, **E**rrors, **D**uration. For any request-serving service, these three answer "is it healthy?"

```promql
# RATE — requests per second, 5-minute window
sum(rate(http_requests_total[5m]))

# RATE per endpoint
sum by (endpoint) (rate(http_requests_total[5m]))

# ERRORS — error rate as a percentage of total requests
sum(rate(http_requests_total{status=~"5.."}[5m]))
  /
sum(rate(http_requests_total[5m])) * 100

# DURATION — p95 latency using histogram_quantile
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)

# DURATION — p99, broken down per endpoint
histogram_quantile(0.99,
  sum by (le, endpoint) (rate(http_request_duration_seconds_bucket[5m]))
)
```

### Other Essentials

```promql
# Instant value (no rate needed — it's a gauge)
active_connections

# Predict disk full in 4 hours based on current trend
predict_linear(node_filesystem_avail_bytes[1h], 4 * 3600) < 0

# Increase over 1 hour (total, not per-second)
increase(http_requests_total[1h])

# Top 5 endpoints by request rate
topk(5, sum by (endpoint) (rate(http_requests_total[5m])))

# Alert condition: any instance down
up == 0
```

`rate()` requires a counter and a range vector (`[5m]`); it computes per-second average rate of increase, correctly handling counter resets (process restarts). `sum by (le)` groups histogram buckets by their `le` (less-than-or-equal) label before `histogram_quantile` interpolates the percentile.

---

## Grafana

### Dashboards & Panel Types

- **Time series** — the default, line/area graph over time (latency, request rate)
- **Stat** — single big number, optional sparkline (current error rate, uptime %)
- **Gauge** — dial visualization against thresholds (disk usage %)
- **Table** — raw rows, useful for top-N breakdowns
- **Heatmap** — distribution over time, great for latency histograms (see the "hot" latency band shift under load)
- **Bar gauge / Pie chart** — proportions (requests per status code)

### Data Source Setup

Grafana → Connections → Data Sources → Add → Prometheus:
```
URL: http://prometheus:9090
Access: Server (default)
Scrape interval: 15s (match Prometheus config)
```

### Grafana-Native Alerts vs Alertmanager

| | Grafana-native alerting | Prometheus + Alertmanager |
|---|---|---|
| Where rules live | Grafana UI/DB | `alerts.yml`, version-controlled with the rest of infra-as-code |
| Data sources | Any Grafana data source (Prometheus, MySQL, Loki, CloudWatch...) | Prometheus/Thanos metrics only |
| Routing/grouping/silencing | Built into Grafana (newer, improved in Grafana 9+) | Alertmanager's routing tree (mature, widely used) |
| Best fit | Multi-datasource shops, teams that live in the Grafana UI | Pure Prometheus shops wanting GitOps-managed, decoupled alerting |

Most mature Prometheus setups still prefer Alertmanager for the actual routing/dedup/notification because it decouples "what fires" (Prometheus rules) from "who gets notified how" (Alertmanager config) — you can change on-call routing without touching alert thresholds.

### Dashboard Variables (Templating)

Variables let one dashboard serve every environment/service instead of duplicating dashboards:

```
Variable: $environment
  Type: Query
  Query: label_values(up, environment)
  → populates a dropdown: production, staging, dev

Variable: $service
  Type: Query
  Query: label_values(http_requests_total{environment="$environment"}, job)
  → chained variable, filtered by the selected environment
```

Panels then reference `$environment`/`$service` in their PromQL:
```promql
sum(rate(http_requests_total{environment="$environment", job="$service"}[5m]))
```
Switching the dropdown re-renders every panel — one dashboard, N environments/services.

---

## Alertmanager

Prometheus evaluates alert rules and, when a condition is true, sends a "firing" alert to Alertmanager. Alertmanager owns **what happens next**: dedup, grouping, silencing, and routing to the right notification channel.

### Recording Rules — Pre-Computing Expensive Queries

Alert rules (below) fire notifications. **Recording rules** are a different thing entirely — they pre-compute a query on a schedule and save the RESULT as a new time series, so an expensive query (a `histogram_quantile` over a busy service, aggregated across many instances) doesn't get recalculated from raw data every single time a dashboard panel or another alert rule needs it.

```yaml
# recording_rules.yml
groups:
  - name: api-recording-rules
    interval: 30s
    rules:
      - record: job:http_request_duration_seconds:p95
        expr: |
          histogram_quantile(0.95,
            sum by (le, job) (rate(http_request_duration_seconds_bucket[5m]))
          )

      - record: job:http_requests:error_rate5m
        expr: |
          sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
            / sum by (job) (rate(http_requests_total[5m]))
```

```
Naming convention (level:metric:operations) is a real Prometheus
community standard, not just style — job:http_requests:error_rate5m
reads as "aggregated at job level, of http_requests, rate over 5m."

Once recorded, `job:http_requests:error_rate5m` is just a normal
metric — a Grafana panel or an alert rule can reference it directly
instead of re-running the full histogram_quantile/rate/sum expression
every time. At real scale (dozens of dashboards and alert rules all
querying variations of the same expensive aggregation), recording
rules are the difference between Prometheus keeping up and falling
behind on evaluation.
```

### Alert Rule (defined in Prometheus, not Alertmanager)

```yaml
# alerts.yml
groups:
  - name: api-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
            / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5% for {{ $labels.job }}"
          description: "Current value: {{ $value | humanizePercentage }}"

      - alert: HighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 1s"
```

### Routing Tree (Matchers)

```yaml
# alertmanager.yml
route:
  receiver: 'default-slack'
  group_by: ['alertname', 'job']
  group_wait: 30s        # wait to batch related alerts before first notify
  group_interval: 5m     # wait before sending updates to an existing group
  repeat_interval: 4h    # resend if still firing after this long

  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-oncall'
      continue: true       # ALSO evaluate sibling routes below

    - match:
        severity: critical
      receiver: 'slack-critical'

    - match:
        severity: warning
      receiver: 'slack-warnings'
```

The route tree is evaluated top-down; the first matching route (by default) claims the alert unless `continue: true` lets it also fall through to later matching routes — that's how "critical goes to BOTH PagerDuty and a Slack channel" works without duplicating the alert rule itself.

### Notification Receivers

```yaml
receivers:
  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#alerts-critical'
        title: '{{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
        send_resolved: true

  - name: 'pagerduty-oncall'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_INTEGRATION_KEY>'
        description: '{{ .CommonAnnotations.summary }}'

  - name: 'default-slack'
    email_configs:
      - to: 'oncall@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alertmanager@example.com'
        auth_identity: 'alertmanager@example.com'
        auth_password: '<SMTP_PASSWORD>'
```

`send_resolved: true` sends a follow-up notification when the alert clears — critical for not leaving on-call wondering if it's still broken.

### Silences — Planned Maintenance Windows

A silence tells Alertmanager "don't notify for anything matching this, for now" — the correct tool for planned maintenance, NOT for permanently ignoring a noisy alert (that's a sign the alert rule itself needs fixing, per the Senior Tip below).

```bash
# Via amtool (Alertmanager's CLI)
amtool silence add alertname="HighErrorRate" job="backend-api" \
  --duration="2h" \
  --comment="Planned DB migration, expect elevated errors 14:00-16:00"

amtool silence query           # list active silences
amtool silence expire <id>       # end a silence early, once maintenance finishes ahead of schedule
```

```
Silences EXPIRE automatically after their duration — this matters
precisely because the failure mode of "someone silenced an alert
during an incident and forgot to remove it" is real and common. A
silence with an explicit, short duration and a comment explaining WHY
is the safe pattern; an indefinite silence someone meant to be
temporary is how a genuinely broken service goes unnoticed for days.
```

### Inhibition Rules — Suppressing Noise From a Known Root Cause

When a whole service is down, EVERY alert tied to it (high latency, high error rate, low throughput) can fire simultaneously — a wall of pages for one actual root cause. Inhibition suppresses the less-severe alerts when a more-severe, related one is already firing.

```yaml
# alertmanager.yml
inhibit_rules:
  - source_matchers:
      - severity="critical"
        alertname="ServiceDown"
    target_matchers:
      - severity=~"warning|critical"
    equal: ['job']       # only inhibit alerts sharing the SAME job label —
                            # don't suppress an unrelated service's alerts
```

```
Read as: if ServiceDown is FIRING for job="backend-api", suppress
HighErrorRate/HighLatencyP95/anything else also matching job="backend-api"
— because those are almost certainly just DOWNSTREAM SYMPTOMS of the
same outage, not independent problems needing their own page. The
on-call engineer gets ONE clear signal ("backend-api is down") instead
of five simultaneous pages all describing the same root cause from
different angles.
```

---

## Senior Tip

```
1. Alert on symptoms, not causes. "Error rate > 5%" (symptom, user
   impact) beats "CPU > 80%" (cause, may not even matter) — CPU can
   run hot all day with zero user impact if latency stays fine.

2. Always set `for: Nm` on alert rules. Without it, a single noisy
   scrape triggers a page. `for: 5m` requires the condition to hold
   for 5 minutes before firing — kills transient blips.

3. Histogram bucket boundaries matter. If your buckets are
   [0.1, 0.5, 1, 5] but your actual p99 sits at 1.2s, your
   histogram_quantile results are coarse/misleading in that range.
   Set buckets around your real SLO target.

4. Cardinality is the #1 way to accidentally kill Prometheus. Never
   put unbounded values (user_id, request_id, raw URL with query
   params) into a label — each unique label combination is a new
   time series, and Prometheus OOMs at scale.

5. `rate()` needs at least 2 data points in the window — a 1-minute
   rate on a 15s scrape interval is technically valid but noisy;
   `[5m]` is the common safe default.
```

## Interview Angle

**Q: "Counter vs Gauge — give a metric example for each and why it's the right type."**
Counter: `http_requests_total` — only increases, you derive rate with `rate()`. Gauge: `active_connections` — goes up and down, you read it directly as a snapshot. Using a gauge for requests-served would make `rate()` meaningless; using a counter for active connections would make no sense (can't "un-increment" a counter cleanly).

**Q: "Write a PromQL query for 5xx error rate over the last 5 minutes, grouped by service."**
```promql
sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
  /
sum by (job) (rate(http_requests_total[5m]))
```

**Q: "How do critical alerts reach PagerDuty while warnings only hit Slack, from one rule file?"**
Alert rules only set `severity` labels; Alertmanager's routing tree matches on `severity` and sends to different receivers — decoupling detection (Prometheus) from notification policy (Alertmanager).

**Q: "An alert rule fires correctly (you can see it 'pending'/'firing' in Prometheus's own UI), but nobody gets notified in Slack or PagerDuty. What's the most likely misconfiguration?"**
Prometheus's own `prometheus.yml` is missing (or misconfigured in) its `alerting.alertmanagers` block — Prometheus can evaluate rules and mark them firing entirely on its own, but without that block telling it WHERE Alertmanager lives, it never actually sends the alert anywhere. This is the single most common "why isn't my alert reaching anyone" cause, and it's easy to miss because the alert rule itself looks completely correct in isolation.

**Q: "A service outage causes 5 different alert rules to fire simultaneously, paging on-call 5 times for what's really one root cause. How do you fix this without deleting any of the alert rules?"**
An inhibition rule in Alertmanager — suppress the less-severe, downstream alerts (high latency, high error rate) whenever a more-severe, related alert (ServiceDown) is already firing for the same job. This keeps all 5 alert rules intact and independently useful (any one of them might fire alone in a different scenario) while collapsing simultaneous, correlated firings into a single clear signal during an actual outage.

**Q: "Why would you add a recording rule instead of just writing the same PromQL query directly into a Grafana panel and an alert rule?"**
If the underlying query is expensive (a `histogram_quantile` aggregated across many instances, say), computing it fresh every time a dashboard renders AND every time an alert rule evaluates it wastes real query load — at scale, across dozens of panels/rules referencing variations of the same aggregation, that adds up to Prometheus struggling to keep up with evaluation. A recording rule computes it once, on a schedule, and both the dashboard and the alert rule reference the pre-computed result as a plain metric instead.

---

## Related

- [`../19_Observability/01_metrics_logs_traces_opentelemetry.md`](../19_Observability/01_metrics_logs_traces_opentelemetry.md) — where metrics fit alongside logs and traces in the broader observability picture
- [`../09_Ansible/01_ansible_config_mgmt.md`](../09_Ansible/01_ansible_config_mgmt.md) — dynamic inventory, the same discovery-over-static-list pattern as Prometheus's `kubernetes_sd_configs`/`ec2_sd_configs`
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — the incident response/postmortem process these alerts feed into
