# Monitoring — Hands-On Lab
**DevOps Track · Phase 11 Practical**

## Prerequisites

- Docker + Docker Compose installed — the entire stack (Prometheus, Grafana, Alertmanager, node_exporter) runs locally at zero cost, no cloud account needed
- Basic Python (for the sample instrumented app) — `pip install fastapi uvicorn prometheus_client`
- Optional: a free Grafana Cloud account if you'd rather not run Grafana locally, but local docker-compose is the recommended path for this lab — faster iteration, no signup
- A `curl` or `ab`/`hey`/`wrk` load-generation tool to produce traffic for your metrics to actually show something interesting (`brew install hey` or just a `for` loop of `curl`)

Create a working directory `monitoring-lab/` for all labs below.

---

## Lab 1: Stand Up the Stack — Prometheus + node_exporter + Grafana

**Objective:** Get metrics flowing end to end: an exporter exposing `/metrics`, Prometheus scraping it, Grafana visualizing it. This is the skeleton every later lab builds on.

**Task:**
1. Write a `docker-compose.yml` with three services: `prometheus`, `node-exporter`, `grafana`.
2. Write `prometheus.yml` with a scrape config for `node-exporter` on its default port.
3. Bring the stack up, open Prometheus's UI (`:9090`), and confirm the `node_exporter` target shows `UP` under Status → Targets.
4. Run a raw PromQL query in the Prometheus UI: `node_memory_MemAvailable_bytes`. Confirm you get a real number back.
5. Open Grafana (`:3000`, default login `admin`/`admin`), add Prometheus as a data source (`http://prometheus:9090`), and build one panel showing CPU usage over time using `rate(node_cpu_seconds_total{mode="idle"}[5m])`.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  node-exporter:
    image: prom/node-exporter:latest
    ports: ["9100:9100"]

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

```bash
docker compose up -d
open http://localhost:9090/targets     # both jobs should show State: UP
open http://localhost:3000             # Grafana, admin/admin
```

Grafana data source setup: Connections → Data Sources → Add → Prometheus → URL `http://prometheus:9090` → Save & Test (should say "Successfully queried the Prometheus API").

Panel query: `rate(node_cpu_seconds_total{mode="idle"}[5m])` — note this shows idle time, so a HEALTHY low-load box shows values close to 1 (100% idle); you'd invert it (`1 - rate(...)`) to show actual busy CPU%, which is worth doing once you understand why the raw metric alone is misleading.

**Why containers talk to each other by service name** (`node-exporter:9100`, not `localhost:9100`): Docker Compose puts all services on a shared network and provides DNS resolution by service name — this is a real pattern you'll rely on constantly, not lab-specific magic.
</details>

---

## Lab 2: Instrument a Real App with the RED Method

**Objective:** Move from "scraping infrastructure metrics someone else wrote" to "instrumenting your own application" — the skill an interviewer actually wants to see.

**Task:**
1. Write a minimal FastAPI app with 2-3 endpoints (e.g. `/orders`, `/orders/{id}`, `/health`), one of which sometimes returns a 500 (simulate with a random failure ~10% of the time) and one with artificial latency (`time.sleep(random.uniform(0, 0.3))`).
2. Instrument it with `prometheus_client`: a `Counter` for `http_requests_total` labeled by `method`, `path`, `status`, and a `Histogram` for `http_request_duration_seconds` labeled by `path`, with buckets tuned around your app's actual latency range.
3. Mount `/metrics` and add the middleware pattern from the lesson file to record both on every request.
4. Add the app as a fourth service in your `docker-compose.yml`, and add a scrape job for it in `prometheus.yml`.
5. Generate load against it (`hey -n 500 -c 10 http://localhost:8000/orders` or a curl loop) so there's real data.
6. In Grafana, build a dashboard with three panels implementing RED: Rate (`sum(rate(http_requests_total[5m]))`), Errors (error % using the `status=~"5.."` pattern), Duration (p95 via `histogram_quantile`).

<details>
<summary>Solution / walkthrough</summary>

```python
# app.py
import random
import time
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

REQUESTS = Counter('http_requests_total', 'Total requests', ['method', 'path', 'status'])
LATENCY = Histogram(
    'http_request_duration_seconds', 'Request latency', ['path'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1]
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    LATENCY.labels(path=request.url.path).observe(time.time() - start)
    REQUESTS.labels(method=request.method, path=request.url.path, status=response.status_code).inc()
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/orders")
def list_orders():
    time.sleep(random.uniform(0, 0.3))
    if random.random() < 0.1:
        return Response(status_code=500)
    return {"orders": [1, 2, 3]}
```

```yaml
# add to docker-compose.yml
  app:
    build: .
    ports: ["8000:8000"]
```

```yaml
# add to prometheus.yml scrape_configs
  - job_name: 'backend-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['app:8000']
```

```bash
hey -n 500 -c 10 http://localhost:8000/orders
```

Grafana panels (PromQL):
```promql
# Rate
sum(rate(http_requests_total[5m]))

# Errors — % of requests that are 5xx
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m])) * 100

# Duration — p95
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

**Why buckets matter here**: the histogram buckets (`[0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1]`) were chosen around the app's actual `sleep(0, 0.3)` range. If you'd left the lesson file's default `[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]` buckets (tuned for a slower service), your p95 for THIS app would sit inside one coarse bucket and the `histogram_quantile` interpolation would be far less precise — exactly the Senior Tip warning from the lesson file about setting buckets around your real SLO target.
</details>

---

## Lab 3: Write a Real Alert Rule + Alertmanager Routing

**Objective:** Turn a dashboard you're staring at into an alert that pages you — the actual point of monitoring, not just pretty graphs.

**Task:**
1. Add Alertmanager as a fourth (or fifth) service in `docker-compose.yml`, and point Prometheus at it via `alerting: alertmanagers:`.
2. Write an `alerts.yml` rule file with a `HighErrorRate` alert: fires when 5xx rate exceeds 5% of total requests, sustained `for: 5m` (not an instant blip).
3. Write a second rule `HighLatencyP95` firing when p95 latency exceeds 250ms for 10 minutes.
4. Label `HighErrorRate` as `severity: critical` and `HighLatencyP95` as `severity: warning`.
5. Write an `alertmanager.yml` routing tree: `critical` alerts go to a `slack-critical` receiver AND (via `continue: true`) also to a `pagerduty-oncall`-style receiver (use a webhook receiver or just a second Slack channel if you don't have a real PagerDuty key); `warning` alerts go only to `slack-warnings`.
6. Trigger the alert for real: hammer your `/orders` endpoint hard enough (or temporarily raise the random-500 rate in the app to 50%) that the error rate actually crosses 5% for 5 minutes, and watch it go from Prometheus's "pending" state to "firing" in the Alerts UI, then show up in Alertmanager.
7. Stop the load, and confirm the alert resolves and (if you set `send_resolved: true`) a resolution notification fires too.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# add to prometheus.yml
rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

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
          summary: "Error rate above 5%"
          description: "Current value: {{ $value | humanizePercentage }}"

      - alert: HighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 0.25
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 250ms"
```

```yaml
# alertmanager.yml
route:
  receiver: 'default-slack'
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match: { severity: critical }
      receiver: 'pagerduty-oncall'
      continue: true
    - match: { severity: critical }
      receiver: 'slack-critical'
    - match: { severity: warning }
      receiver: 'slack-warnings'

receivers:
  - name: 'default-slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#alerts'
  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#alerts-critical'
        send_resolved: true
  - name: 'slack-warnings'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#alerts-warnings'
  - name: 'pagerduty-oncall'
    webhook_configs:
      - url: 'http://example.com/fake-pagerduty-webhook'   # substitute a real PagerDuty integration key/URL if you have one
```

```bash
hey -n 2000 -c 20 -z 6m http://localhost:8000/orders    # sustained load for >5m to cross the `for:` threshold
open http://localhost:9090/alerts                        # watch pending -> firing
open http://localhost:9093                                # Alertmanager UI shows the routed alert
```

**Why `for: 5m` is not optional**: without it, a single noisy scrape crossing the threshold pages someone immediately — `for: 5m` requires the condition to hold continuously across multiple scrape intervals before firing, which is what turns "transient blip" into "silence" instead of a false alarm. You should be able to see this directly: watch the alert sit in Prometheus's `pending` state (condition true, timer not yet elapsed) before it flips to `firing`.

**Why `continue: true` matters**: without it, the FIRST matching route in the tree claims the alert and routing stops — `critical` would go to PagerDuty only, never reaching Slack too. `continue: true` on the first critical route lets evaluation fall through to the second matching route as well, which is exactly how "critical pages AND posts to Slack, from one alert rule" works without duplicating the rule itself.
</details>

---

## Lab 4: Troubleshooting — Diagnosing a Cardinality Explosion

**Objective:** Reproduce and fix the #1 real-world way to accidentally kill Prometheus, called out explicitly in the lesson file's Senior Tip.

**Task:**
1. Modify your app's middleware to (deliberately, for this lab) add a high-cardinality label to the request counter — label by `request_id` (a random UUID generated per request) instead of just `method`/`path`/`status`.
2. Generate a burst of ~200 requests and watch what happens to Prometheus's memory/target scrape duration and the raw number of time series (`curl http://localhost:9090/api/v1/status/tsdb` or the "TSDB Status" page in the Prometheus UI, under `numSeries`).
3. Confirm `numSeries` grew by roughly one new series per request — each unique `request_id` value creates an entirely new time series, because a metric's identity is its name PLUS its full label set.
4. Revert the label to the low-cardinality version (`method`, `path`, `status` only — put `request_id` in application LOGS instead, correlated via the same identifier, not in a Prometheus label) and confirm `numSeries` growth stops.
5. Explain in your own words why this same failure mode applies to Loki labels too (see the Logging lab), and why "put IDs in the body, not in labels/index fields used for routing" is the shared rule across both systems.

<details>
<summary>Solution / walkthrough</summary>

**Broken (cardinality explosion):**
```python
import uuid

REQUESTS = Counter('http_requests_total', 'Total requests', ['method', 'path', 'status', 'request_id'])

@app.middleware("http")
async def metrics_middleware(request, call_next):
    response = await call_next(request)
    REQUESTS.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        request_id=str(uuid.uuid4())      # NEW time series on every single request
    ).inc()
    return response
```

```bash
hey -n 200 -c 5 http://localhost:8000/orders
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.headStats.numSeries'
# grows by ~200 — one new series per request, because request_id is different every time
```

**Why this is catastrophic at scale, not just untidy**: a metric's true identity in Prometheus is `metric_name{label1=x, label2=y, ...}` — the FULL combination of labels. Every unique combination is a separate, permanently-tracked time series in memory until it's scraped away by retention. `request_id` alone can produce millions of one-off series that are each queried exactly zero times after creation — pure memory waste that, at real production traffic volumes, is the textbook way teams have actually OOM'd their Prometheus server.

**Fixed:**
```python
REQUESTS = Counter('http_requests_total', 'Total requests', ['method', 'path', 'status'])
# request_id goes into structured application LOGS instead:
logger.info("request completed", extra={"request_id": req_id, "path": request.url.path, "status": response.status_code})
```
```bash
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.headStats.numSeries'
# stops growing — back to a small, bounded number of series (one per method+path+status combination)
```

**Why the same rule applies to Loki**: Loki's cost model depends on labels staying low-cardinality (it indexes ONLY labels, not log content) — putting `request_id` or `user_id` into a Loki label explodes the number of distinct log STREAMS Loki has to track, the direct analog of Prometheus's series explosion. Both systems solve this the same way: bounded/categorical values (`app`, `env`, `pod`, `method`, `path`) belong in labels because there are only ever a handful of distinct values; anything with effectively unlimited distinct values (`request_id`, `user_id`, raw URLs with query params) belongs in the metric/log BODY, correlated across tools via a shared `request_id`/`trace_id` field you can grep/filter on, not index on.
</details>

---

## Self-Check Checklist

- [ ] Can you explain the difference between Counter, Gauge, Histogram, and Summary, and give a correct real-world example of each?
- [ ] Can you write a scrape config from memory (job_name, targets, scrape_interval)?
- [ ] Can you write the RED method's three PromQL queries (rate, error %, p95 duration) without looking them up?
- [ ] Can you explain why `rate()` requires a counter and a range vector, and what it protects against (counter resets)?
- [ ] Can you write an alert rule with a `for:` clause and explain why omitting `for:` is a mistake?
- [ ] Can you explain how Alertmanager's routing tree decides which alerts reach which receiver, and what `continue: true` does?
- [ ] Can you explain what a cardinality explosion is, how to detect one (`numSeries`), and how to prevent one?
- [ ] Can you explain the tradeoff between Histogram and Summary, and why Histogram is preferred in almost all multi-instance production setups?
- [ ] Can you set up a Grafana dashboard variable (`$environment`) that filters a panel's PromQL query?
- [ ] Can you explain, unprompted, "alert on symptoms not causes" and give an example of each for a request-serving API?
