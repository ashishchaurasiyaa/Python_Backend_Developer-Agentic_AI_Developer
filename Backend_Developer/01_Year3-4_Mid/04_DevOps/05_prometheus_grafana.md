# Prometheus + Grafana — Metrics & Monitoring

## Quick Concepts
- **Prometheus** = time-series metrics database — services se metrics scrape karta hai
- **Grafana** = metrics visualize karta hai — dashboards banata hai
- **Exporter** = application jo Prometheus ke liye metrics expose karta hai
- **PromQL** = Prometheus Query Language
- **Alertmanager** = alerts define karo — Slack/email notifications

---

## Interview Questions & Answers

### Q1: Prometheus + Grafana architecture kaise kaam karta hai?
**Answer:**
```
FastAPI App (/metrics) ←── Prometheus (scrapes every 15s)
                                    ↓
                               Grafana (queries Prometheus)
                                    ↓
                           Alertmanager → Slack/Email
```

1. App `/metrics` endpoint expose karta hai (Prometheus format)
2. Prometheus har 15 seconds mein scrape karta hai
3. Grafana Prometheus se query karta hai dashboards ke liye
4. Alertmanager rules check karta hai aur notifications bhejta hai

---

### Q2: FastAPI mein Prometheus metrics kaise add karte hain?
**Answer:**
```bash
pip install prometheus-client starlette-prometheus
```

```python
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time

app = FastAPI()

# Metrics define karo
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Currently active requests"
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"]
)

# Middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ACTIVE_REQUESTS.inc()
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    ACTIVE_REQUESTS.dec()

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response

# Metrics endpoint
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Business metric example
ORDERS_PROCESSED = Counter("orders_processed_total", "Total orders", ["status"])

@app.post("/orders")
async def create_order(order: dict):
    # ... process order
    ORDERS_PROCESSED.labels(status="success").inc()
    return {"id": "123"}
```

---

### Q3: Prometheus configuration (prometheus.yml) kaise likhte hain?
**Answer:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  # FastAPI app
  - job_name: "fastapi"
    static_configs:
      - targets: ["app:8000"]
    metrics_path: /metrics

  # PostgreSQL exporter
  - job_name: "postgres"
    static_configs:
      - targets: ["postgres-exporter:9187"]

  # Redis exporter
  - job_name: "redis"
    static_configs:
      - targets: ["redis-exporter:9121"]

  # Node exporter (system metrics)
  - job_name: "node"
    static_configs:
      - targets: ["node-exporter:9100"]
```

---

### Q4: Alert rules kaise define karte hain?
**Answer:**
```yaml
# alerts.yml
groups:
  - name: fastapi_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.endpoint }}"
          description: "Error rate is {{ $value }} errors/second"

      # Slow response
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95 response time > 1s"

      # Instance down
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"
```

---

### Q5: PromQL important queries kya hain?
**Answer:**
```promql
# Request rate (per second, last 5 min)
rate(http_requests_total[5m])

# Error rate percentage
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m])) * 100

# P95 response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# P99 response time
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Requests per endpoint
sum by (endpoint) (rate(http_requests_total[5m]))

# CPU usage
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Memory usage
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100

# DB connections
pg_stat_activity_count
```

---

### Q6: Docker Compose mein full monitoring stack kaise setup karte hain?
**Answer:**
```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=15d"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_AUTH_ANONYMOUS_ENABLED=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus

  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro

  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    command:
      - "--path.procfs=/host/proc"
      - "--path.sysfs=/host/sys"

volumes:
  prometheus_data:
  grafana_data:
```

---

### Q7: Alertmanager Slack notifications kaise configure karte hain?
**Answer:**
```yaml
# alertmanager.yml
global:
  slack_api_url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

route:
  group_by: ["alertname", "job"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: "slack-notifications"
  routes:
    - match:
        severity: critical
      receiver: "slack-critical"

receivers:
  - name: "slack-notifications"
    slack_configs:
      - channel: "#monitoring"
        title: "{{ .GroupLabels.alertname }}"
        text: "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"

  - name: "slack-critical"
    slack_configs:
      - channel: "#alerts-critical"
        send_resolved: true
```

---

## Metric Types — When to Use Which

| Type | Use Case | Example |
|---|---|---|
| **Counter** | Sirf badhta hai — requests, errors | `http_requests_total` |
| **Gauge** | Up/down ja sakta hai — active connections | `active_connections` |
| **Histogram** | Distribution + percentiles — latency | `request_duration_seconds` |
| **Summary** | Percentiles (client-side) — rare use | `rpc_duration_seconds` |
