# Observability — Hands-On Lab
**DevOps Track · Phase 19 Practical**

## Prerequisites

Local Docker + Python — no cloud spend, no SaaS observability vendor needed.

- Docker + Docker Compose (Jaeger, Prometheus run as containers)
- Python 3.10+ with `opentelemetry-distro`, `opentelemetry-exporter-otlp`, `flask` (or any tiny web framework), `requests`
- A browser to view the Jaeger UI (`localhost:16686`) and Prometheus UI (`localhost:9090`)
- Basic comfort reading JSON log lines and a trace waterfall view
- No Datadog/New Relic/Honeycomb account needed — Jaeger with an in-memory or local backend is enough to see everything the lesson describes

---

## Lab 1: Instrument a Python Script with OpenTelemetry and View a Real Trace

**Objective:** Do exactly what the lesson's "Real Python Auto-Instrumentation Snippet" describes end to end — auto-instrument a small app, ship spans to a Collector-less direct-to-Jaeger setup, and see the resulting trace in the Jaeger UI.

**Task:**
1. Start a Jaeger all-in-one container (includes UI + OTLP receiver, no separate Collector needed for this lab).
2. Write a tiny Flask app with two routes: `GET /order` (calls a fake "DB" function that sleeps 50ms) and `GET /checkout` (calls `/order`'s logic internally, then calls a fake "payment" function that sleeps 300ms — this becomes your bottleneck span).
3. Install `opentelemetry-distro` + `opentelemetry-exporter-otlp`, run `opentelemetry-bootstrap -a install`, then launch the app wrapped in `opentelemetry-instrument` pointed at Jaeger's OTLP endpoint.
4. Hit `/checkout` a few times with `curl`.
5. Open the Jaeger UI, find the trace, and confirm you can see the nested span structure with the payment call clearly taking the most time — visually reproducing the waterfall example from the lesson (`api-gateway [50ms]` → `orders-service.create_order [180ms]` → `payments-service.charge [4900ms]`).
6. Add ONE manual span (per the lesson's manual instrumentation example) around a business-logic function that auto-instrumentation wouldn't see (e.g., a discount-calculation function), with a custom attribute, and confirm it shows up in the trace tree too.

<details>
<summary>Solution / walkthrough</summary>

```bash
docker run -d --name jaeger \
  -p 16686:16686 -p 4317:4317 -p 4318:4318 \
  jaegertracing/all-in-one:1.57
# 16686 = UI, 4317 = OTLP gRPC receiver, 4318 = OTLP HTTP receiver
```

```python
# app.py
import time
from flask import Flask
from opentelemetry import trace

app = Flask(__name__)
tracer = trace.get_tracer("checkout-service")

def fake_db_call():
    time.sleep(0.05)
    return {"order_id": 123, "items": ["widget"]}

def apply_discount_rules(order):
    # manual span around business logic auto-instrumentation can't see
    with tracer.start_as_current_span("apply_discount_rules") as span:
        span.set_attribute("order.id", order["order_id"])
        span.set_attribute("discount.code", "SAVE10")
        time.sleep(0.02)
        discount = 1.99
        span.set_attribute("discount.amount", discount)
        return discount

def fake_payment_call():
    time.sleep(0.3)   # deliberately the slow one — this is the bottleneck to find
    return {"status": "charged"}

@app.route("/order")
def order():
    data = fake_db_call()
    return data

@app.route("/checkout")
def checkout():
    data = fake_db_call()
    discount = apply_discount_rules(data)
    payment = fake_payment_call()
    return {"order": data, "discount": discount, "payment": payment}

if __name__ == "__main__":
    app.run(port=8000)
```

```bash
pip install flask opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install

opentelemetry-instrument \
    --traces_exporter otlp \
    --exporter_otlp_endpoint http://localhost:4317 \
    --service_name checkout-service \
    python app.py
```

```bash
curl http://localhost:8000/checkout
curl http://localhost:8000/checkout
curl http://localhost:8000/checkout
```

```
Open http://localhost:16686
  -> Service: checkout-service -> Find Traces
  -> Click into a /checkout trace
  -> Expect to see:
       flask.checkout [~370ms]
         ├── apply_discount_rules [~20ms]   <- your manual span, with
         │      order.id, discount.code, discount.amount attributes visible
         └── (payment call, ~300ms — the clear bottleneck in the waterfall,
              just like the lesson's payments-service.charge example)
```

Why this matters: the lesson's waterfall example (`stripe-api.POST /charges ← THE BOTTLENECK`) stops being an abstract diagram once you've watched your own trace render the exact same shape — a small function you know takes 300ms visibly dominating the timeline, with the fast 50ms and 20ms spans barely visible slivers next to it. This is also the first time most engineers realize how CHEAP adding a manual span is (four lines of code) versus how much diagnostic value it adds.
</details>

---

## Lab 2: Structured Logging with `trace_id` — Jump From a Trace to the Exact Log Lines

**Objective:** Implement the lesson's "key discipline" — structured JSON logs carrying `trace_id` — and prove you can go from a slow trace straight to the matching log lines, which is the whole point of correlating the two pillars.

**Task:**
1. Extend the Flask app from Lab 1: add Python's `logging` module configured to output JSON (one line per event, matching the lesson's exact example shape: `timestamp`, `level`, `service`, `trace_id`, `message`, plus custom fields).
2. Inside `fake_payment_call`, pull the CURRENT trace's `trace_id` from the active OTel span context (`trace.get_current_span().get_span_context().trace_id`) and include it in a log line: `"Payment gateway call completed", duration_ms=..., order_id=...`.
3. Deliberately make `fake_payment_call` sometimes "fail" (raise an exception) for orders where `order_id` is even, logging an ERROR-level line with the same `trace_id` before re-raising.
4. Run several requests, some of which will error. In Jaeger, find a trace marked as an error (Jaeger flags error spans in red).
5. Copy that trace's `trace_id` from the Jaeger UI, then grep your application's stdout/log file for that exact `trace_id` — confirm you land on precisely the log line(s) for that one failed request, not a wall of unrelated log noise.

<details>
<summary>Solution / walkthrough</summary>

```python
# logging_setup.py
import logging, json, sys
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "checkout-service",
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload)

logger = logging.getLogger("checkout")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

```python
# in app.py
from opentelemetry import trace
from logging_setup import logger
import time

def current_trace_id():
    span = trace.get_current_span()
    ctx = span.get_span_context()
    return format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None

def fake_payment_call(order_id):
    start = time.time()
    tid = current_trace_id()
    if order_id % 2 == 0:
        logger.error("Payment gateway timeout", extra={
            "trace_id": tid,
            "extra_fields": {"order_id": order_id, "duration_ms": 5023}
        })
        raise RuntimeError("payment gateway timeout")
    time.sleep(0.3)
    logger.info("Payment gateway call completed", extra={
        "trace_id": tid,
        "extra_fields": {"order_id": order_id, "duration_ms": 300}
    })
    return {"status": "charged"}
```

```bash
# fire several requests, order_id alternates in your fake_db_call for this test
curl http://localhost:8000/checkout   # some succeed, some raise
```

```json
{"timestamp": "2026-07-25T10:20:01.123Z", "level": "ERROR", "service": "checkout-service",
 "message": "Payment gateway timeout", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
 "order_id": 124, "duration_ms": 5023}
```

```
In Jaeger UI: filter Tags by error=true, click into a red/error-flagged trace,
copy its Trace ID from the top of the page.

Then:
  grep "4bf92f3577b34da6a3ce929d0e0e4736" app.log
  -> returns exactly the log lines for THAT request, nothing else
```

Why this matters: this is the exact mechanic the lesson's Senior Tip calls the correct incident-investigation order — "TRACES to find WHICH span is throwing the error, LOGS filtered by trace_id to get the exact error/stack trace/payload." Doing this by hand once (copy trace_id from Jaeger, grep it) makes the abstract phrase "structured logging with a trace_id field" into a concrete skill instead of a checklist item.
</details>

---

## Lab 3: Production-Style — Prometheus Metrics + Alert on a Real Threshold Breach

**Objective:** Add the METRICS pillar to the same app (counters, gauge, histogram per the lesson's table), scrape them with Prometheus, and configure an alert rule that would actually fire — completing all three pillars end to end.

**Task:**
1. Add `prometheus-client` to the Flask app: a Counter `http_requests_total` (labeled by route and status), and a Histogram `http_request_duration_seconds`.
2. Expose a `/metrics` endpoint (standard Prometheus scrape target).
3. Start a Prometheus container with a `prometheus.yml` scrape config pointed at your app's `/metrics` endpoint.
4. Write a PromQL query for p99 latency using the histogram (`histogram_quantile(0.99, ...)`) and run it in the Prometheus UI's query browser.
5. Write a PromQL alerting rule: `error rate > 5% over a 2-minute window` (using the counter, `status=~"5.."` vs total).
6. Generate enough failed requests (using the even-`order_id` failure path from Lab 2) to cross that 5% threshold, and confirm in the Prometheus UI's Alerts tab that the rule transitions from inactive → pending → firing.

<details>
<summary>Solution / walkthrough</summary>

```python
# add to app.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Response
import time as time_module

REQUEST_COUNT = Counter("http_requests_total", "Total requests", ["route", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["route"])

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/checkout")
def checkout():
    start = time_module.time()
    status = "200"
    try:
        data = fake_db_call()
        discount = apply_discount_rules(data)
        payment = fake_payment_call(data["order_id"])
        return {"order": data, "discount": discount, "payment": payment}
    except Exception:
        status = "500"
        return {"error": "payment failed"}, 500
    finally:
        REQUEST_COUNT.labels(route="/checkout", status=status).inc()
        REQUEST_LATENCY.labels(route="/checkout").observe(time_module.time() - start)
```

```yaml
# prometheus.yml
global:
  scrape_interval: 5s
rule_files:
  - "alerts.yml"
scrape_configs:
  - job_name: "checkout-service"
    static_configs:
      - targets: ["host.docker.internal:8000"]   # or the app container's name if compose-networked
```

```yaml
# alerts.yml
groups:
  - name: checkout-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{route="/checkout",status="500"}[2m]))
          /
          sum(rate(http_requests_total{route="/checkout"}[2m]))
          > 0.05
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Checkout error rate above 5%"
```

```bash
docker run -d --name prometheus -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/alerts.yml:/etc/prometheus/alerts.yml \
  prom/prometheus
```

```promql
# p99 latency, in the Prometheus UI query browser
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

```bash
# generate load with enough failures (even order_ids) to cross 5% error rate
for i in $(seq 1 50); do curl -s http://localhost:8000/checkout > /dev/null; done
```

```
Prometheus UI -> Alerts tab
  HighErrorRate: Inactive -> Pending (once expr is true) -> Firing (after the
  `for: 1m` duration has elapsed with the condition continuously true)
```

Why this matters: this is the concrete version of the lesson's core three-pillar claim — you now have a METRIC that would page you (error rate crossing threshold), a TRACE that shows exactly which span failed, and a LOG line with the `trace_id` explaining why. That's the full pipeline the lesson says a senior engineer is expected to design, built from scratch by you in under an hour.
</details>

---

## Lab 4: Troubleshooting — Diagnose a Broken Trace (Missing Child Span)

**Objective:** Reproduce the exact failure mode the lesson's Interview Angle question describes — "a span in service B doesn't show up under the parent span from service A" — and fix it, so you have hands-on grounding for that interview answer instead of a memorized list of causes.

**Task:**
1. Add a second tiny Flask service (`inventory-service`, a different process/port) with one route `GET /check-stock` that just returns `{"in_stock": true}`.
2. From `checkout-service`, call `inventory-service` using a PLAIN `requests.get()` call — deliberately do NOT rely on auto-instrumentation patching `requests` (simulate the scenario by calling it in a way that breaks propagation — see the walkthrough for the exact way to reproduce this cleanly).
3. Run both services under `opentelemetry-instrument` as in Lab 1, hit `/checkout`, and check Jaeger — is the `inventory-service` call showing up as a nested child span under the `checkout-service` trace, or as a SEPARATE, disconnected trace?
4. Diagnose why using ONLY what you can observe in Jaeger (trace IDs, timestamps, service list) — before reading the fix below.
5. Fix it (the walkthrough shows the actual cause and correction for this reproducible case) and confirm the span now nests correctly under one trace.

<details>
<summary>Solution / walkthrough</summary>

```python
# inventory_service.py
from flask import Flask
app = Flask(__name__)

@app.route("/check-stock")
def check_stock():
    return {"in_stock": True}

if __name__ == "__main__":
    app.run(port=8001)
```

```bash
opentelemetry-instrument --traces_exporter otlp \
    --exporter_otlp_endpoint http://localhost:4317 \
    --service_name inventory-service \
    python inventory_service.py
```

```python
# in checkout-service's app.py — call inventory-service
import requests

@app.route("/checkout")
def checkout():
    ...
    stock = requests.get("http://localhost:8001/check-stock").json()
    ...
```

Run both, hit `/checkout`, check Jaeger's service list and trace view. With BOTH services under `opentelemetry-instrument` and the standard `requests` auto-instrumentor active, this actually DOES propagate correctly by default (the auto-instrumentor patches `requests` to inject `traceparent` headers automatically) — which is itself worth confirming, since it proves the auto-instrumentation is doing real work. To reproduce the BROKEN case the lesson describes, deliberately bypass it:

```python
import urllib.request   # NOT requests — a raw client the auto-instrumentor doesn't patch

@app.route("/checkout")
def checkout():
    ...
    with urllib.request.urlopen("http://localhost:8001/check-stock") as resp:
        stock = resp.read()
    ...
```

Now check Jaeger: `inventory-service`'s `/check-stock` span appears as its OWN separate trace with a different Trace ID, not nested under `checkout-service`'s `/checkout` trace — exactly the symptom in the lesson's interview question.

**Diagnosis from Jaeger alone:** two disconnected traces with overlapping timestamps, one from each service, no parent-child link — the giveaway is that `inventory-service`'s trace has no parent span reference at all (it looks like a fresh, top-level trace), meaning nothing told it "you're continuing an existing trace." That's specifically cause #2 from the lesson's own answer: "a manual HTTP client that doesn't inject the `traceparent` header."

**Fix:** either use `requests` (which the auto-instrumentor DOES patch) instead of raw `urllib`, or if you must use an unpatched client, manually inject the header:

```python
from opentelemetry.propagate import inject

headers = {}
inject(headers)   # populates headers with 'traceparent' from the current span context
with urllib.request.urlopen(urllib.request.Request(
        "http://localhost:8001/check-stock", headers=headers)) as resp:
    stock = resp.read()
```

Re-run — now `inventory-service`'s span nests correctly under the same Trace ID as `checkout-service`'s `/checkout` span.

Why this matters: you've now actually caused and fixed the exact bug the lesson's hardest interview question describes, instead of reciting the three listed causes from memory. If asked this in an interview, you can say "I've hit this — it was a raw HTTP client not injecting `traceparent`" instead of reasoning from first principles under pressure.
</details>

---

## Self-Check Checklist

- [ ] Can you explain, in one sentence each, what question metrics, logs, and traces each answer, and in what order you'd check them during an incident?
- [ ] Can you set up `opentelemetry-instrument` against a real app and get a trace into Jaeger without referencing this lab?
- [ ] Can you write a manual span with custom attributes for business logic auto-instrumentation can't see?
- [ ] Can you implement structured JSON logging with a `trace_id` field, and explain why that field specifically is what makes logs and traces useful together?
- [ ] Can you write a PromQL query for p99 latency from a histogram, and explain what `histogram_quantile` needs from your metric (the `_bucket` suffix, `le` label) to work?
- [ ] Can you write a Prometheus alerting rule for an error-rate threshold, including the `for:` duration and why it matters (avoiding flapping alerts on a single bad second)?
- [ ] Can you name at least two real causes of a broken/disconnected trace (missing propagation across a queue hop, an unpatched HTTP client, independent per-service sampling) and have you personally reproduced at least one?
- [ ] Can you explain what an OTel Collector does that the SDK alone doesn't, and why that decoupling matters when switching observability backends?
- [ ] Can you explain the cost-profile difference between metrics and logs, and why that shapes which one you alert on first?
- [ ] Given a trace_id from a Jaeger error trace, can you actually go find the matching log lines using nothing but `grep`?
