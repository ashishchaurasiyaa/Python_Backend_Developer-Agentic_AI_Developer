# Testing — Load Testing with Locust + k6 (Performance & Stress)
**Phase 2 Testing | Senior Backend + Agentic AI**

## Quick Concepts
- **Load testing** = simulate expected user traffic — verify SLOs met
- **Stress testing** = push beyond expected load — find breaking point
- **Spike testing** = sudden traffic surge — verify autoscaling/circuit breakers
- **Soak testing** = sustained load for hours — find memory leaks
- **Locust** = Python-based, code-first; great for complex scenarios
- **k6** = JavaScript-based by Grafana; lower resource use, CI-friendly
- **Vegeta / Wrk / Bombardier** = HTTP-only, simpler
- **RPS** = Requests Per Second
- **p50, p95, p99** = latency percentiles (50%/95%/99% of requests faster than X)
- **Apdex** = application performance index (0-1 score)

---

## Why Two Tools

| Aspect | Locust | k6 |
|---|---|---|
| Language | Python | JavaScript (ES6) |
| Resource use | Higher (1 worker/user) | Lower (Goroutines under hood) |
| Distributed | Master + workers | Built-in cloud (k6 Cloud) |
| Best for | Python teams, complex flows | CI/CD, high concurrency |
| Reporting | Web UI + logs | Beautiful CLI + Grafana |

**Recommendation:** Use both — Locust for dev/scenarios, k6 for CI gates.

---

## Performance SLO Examples

| Endpoint | p50 | p95 | p99 | RPS |
|---|---|---|---|---|
| `GET /api/users/:id` | < 50ms | < 200ms | < 500ms | 5000 |
| `POST /api/orders` | < 100ms | < 500ms | < 1s | 500 |
| `GET /api/search` | < 200ms | < 1s | < 2s | 1000 |
| `POST /api/llm/chat` | < 500ms TTFB | < 2s TTFB | < 5s TTFB | 100 |

---

## Interview Questions & Answers

### Q1: Locust se basic load test kaise likhte hain?

**Answer:**
```bash
pip install locust
```

```python
# locustfile.py
from locust import HttpUser, task, between, events
import random

class APIUser(HttpUser):
    wait_time = between(1, 3)  # users wait 1-3s between requests

    def on_start(self):
        """Run once per simulated user — login."""
        response = self.client.post("/auth/login", json={
            "email": f"user_{random.randint(1, 10000)}@test.com",
            "password": "test123",
        })
        self.token = response.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(3)  # weight 3 — runs 3x more than weight 1
    def view_products(self):
        self.client.get("/api/products?limit=20", name="GET /api/products")

    @task(2)
    def view_product_detail(self):
        product_id = random.randint(1, 1000)
        self.client.get(f"/api/products/{product_id}", name="GET /api/products/:id")

    @task(1)
    def create_order(self):
        with self.client.post(
            "/api/orders",
            json={"items": [{"product_id": 42, "quantity": 1}]},
            name="POST /api/orders",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 429:
                response.success()  # rate limited = expected
            else:
                response.failure(f"Unexpected {response.status_code}")

    @task(1)
    def search(self):
        queries = ["laptop", "phone", "headphones", "book"]
        self.client.get(f"/api/search?q={random.choice(queries)}", name="GET /api/search")
```

**Run interactively:**
```bash
locust -f locustfile.py --host=https://staging.acme.com
# Open http://localhost:8089
```

**Run headless (CI):**
```bash
locust -f locustfile.py --host=https://staging.acme.com \
  --users 100 --spawn-rate 10 --run-time 5m \
  --headless --html report.html --csv results
```

---

### Q2: Distributed Locust (master + workers)?

**Answer:** Single machine ~5000 users max — distribute for higher load.

```yaml
# docker-compose.yml
version: '3'
services:
  locust-master:
    image: locustio/locust
    ports: ["8089:8089"]
    volumes:
      - ./:/mnt/locust
    command: >
      -f /mnt/locust/locustfile.py
      --master
      --host=https://target.com

  locust-worker:
    image: locustio/locust
    volumes:
      - ./:/mnt/locust
    command: >
      -f /mnt/locust/locustfile.py
      --worker
      --master-host=locust-master
    deploy:
      replicas: 8  # 8 workers
```

```bash
docker-compose up --scale locust-worker=10
```

**Kubernetes pattern:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: locust-worker }
spec:
  replicas: 20
  template:
    spec:
      containers:
      - name: locust
        image: locustio/locust
        args:
        - "--worker"
        - "--master-host=locust-master.default.svc.cluster.local"
        - "-f"
        - "/locust/locustfile.py"
        volumeMounts:
        - name: locustfile
          mountPath: /locust
      volumes:
      - name: locustfile
        configMap: { name: locust-script }
```

---

### Q3: k6 equivalent — basic test?

**Answer:**
```bash
brew install k6  # or apt install k6
```

```javascript
// test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const failureRate = new Rate('failure_rate');
const checkoutTime = new Trend('checkout_duration', true);

export const options = {
    stages: [
        { duration: '30s', target: 50 },    // ramp to 50 users
        { duration: '2m', target: 50 },     // hold for 2 min
        { duration: '30s', target: 200 },   // spike to 200
        { duration: '2m', target: 200 },    // hold
        { duration: '30s', target: 0 },     // ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<2000'],  // SLO assertions
        http_req_failed: ['rate<0.01'],                  // error rate < 1%
        failure_rate: ['rate<0.05'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'https://staging.acme.com';

export function setup() {
    // Login once, share token across VUs
    const res = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
        email: 'loadtest@acme.com',
        password: 'test123',
    }), { headers: { 'Content-Type': 'application/json' } });
    return { token: res.json('access_token') };
}

export default function (data) {
    const headers = { 'Authorization': `Bearer ${data.token}` };

    // 1. View products
    const productsRes = http.get(`${BASE_URL}/api/products?limit=20`, { headers });
    check(productsRes, {
        'products status 200': (r) => r.status === 200,
        'products fast': (r) => r.timings.duration < 500,
    });
    failureRate.add(productsRes.status !== 200);

    sleep(1);

    // 2. Create order (measure separately)
    const start = Date.now();
    const orderRes = http.post(
        `${BASE_URL}/api/orders`,
        JSON.stringify({ items: [{ product_id: 42, quantity: 1 }] }),
        { headers: { ...headers, 'Content-Type': 'application/json' } },
    );
    checkoutTime.add(Date.now() - start);
    check(orderRes, {
        'order created': (r) => r.status === 201,
    });

    sleep(Math.random() * 3 + 1);  // think time 1-4s
}

export function teardown(data) {
    console.log('Test complete');
}
```

**Run:**
```bash
k6 run test.js
k6 run --vus 100 --duration 5m test.js
k6 run -e BASE_URL=https://staging.acme.com test.js
```

**Output:**
```
checks.........................: 99.85% ✓ 14782   ✗ 22
http_req_duration..............: avg=234ms min=12ms med=180ms max=4.2s p(95)=489ms p(99)=1.8s
http_req_failed................: 0.15%  ✓ 22      ✗ 14782
checkout_duration..............: avg=180ms min=45ms med=160ms max=2.1s p(95)=380ms
iterations.....................: 7402   24.67/s
```

---

### Q4: Load testing scenarios — load, stress, spike, soak?

**Answer:** Different shapes for different goals.

**Load test (expected traffic):**
```javascript
export const options = {
    stages: [
        { duration: '5m', target: 500 },   // ramp
        { duration: '30m', target: 500 },  // steady at expected RPS
        { duration: '5m', target: 0 },
    ],
};
```

**Stress test (find breaking point):**
```javascript
export const options = {
    stages: [
        { duration: '5m', target: 500 },
        { duration: '10m', target: 1000 },
        { duration: '10m', target: 2000 },
        { duration: '10m', target: 4000 },
        { duration: '10m', target: 8000 },  // keep ramping until break
        { duration: '5m', target: 0 },
    ],
};
```

**Spike test (autoscaling check):**
```javascript
export const options = {
    stages: [
        { duration: '1m', target: 100 },
        { duration: '30s', target: 5000 },  // 50x spike
        { duration: '5m', target: 5000 },
        { duration: '1m', target: 100 },    // back to normal
    ],
};
```

**Soak test (memory leaks, slow DB growth):**
```javascript
export const options = {
    stages: [
        { duration: '10m', target: 300 },
        { duration: '8h', target: 300 },   // sustained 8 hours
        { duration: '10m', target: 0 },
    ],
};
```

---

### Q5: WebSocket / SSE load testing?

**Answer:** k6 supports natively; Locust needs custom user class.

**k6 WebSocket:**
```javascript
import ws from 'k6/ws';
import { check } from 'k6';

export const options = {
    vus: 1000,         // 1000 concurrent WebSocket connections
    duration: '5m',
};

export default function () {
    const url = 'wss://api.acme.com/chat/ws';
    const params = { headers: { 'Authorization': 'Bearer xxx' } };

    const res = ws.connect(url, params, function (socket) {
        socket.on('open', () => {
            socket.send(JSON.stringify({ type: 'join', room: 'general' }));
        });

        socket.on('message', (data) => {
            const msg = JSON.parse(data);
            check(msg, { 'has type': (m) => m.type !== undefined });
        });

        socket.setInterval(() => {
            socket.send(JSON.stringify({ type: 'ping' }));
        }, 5000);

        socket.setTimeout(() => socket.close(), 60000);  // 1 min per VU
    });

    check(res, { 'connected': (r) => r && r.status === 101 });
}
```

**Locust WebSocket** (with `locust-plugins`):
```python
from locust_plugins.users.socketio import SocketIOUser
from locust import task

class ChatUser(SocketIOUser):
    @task
    def chat(self):
        self.connect("wss://api.acme.com/chat/ws", header=[f"Authorization: Bearer {self.token}"])
        self.send({"type": "join", "room": "general"})
        # ... wait for messages
```

---

### Q6: LLM endpoint load testing (special considerations)?

**Answer:** LLM endpoints are slow + expensive — different metrics matter.

```javascript
// llm_load_test.js
import http from 'k6/http';
import { check, Trend } from 'k6';

const ttft = new Trend('time_to_first_token', true);   // Time To First Token
const totalLatency = new Trend('total_latency', true);
const tokensGenerated = new Trend('tokens_generated');

export const options = {
    scenarios: {
        concurrent_chat: {
            executor: 'constant-vus',
            vus: 50,                                   // 50 concurrent chats
            duration: '10m',
        },
    },
    thresholds: {
        time_to_first_token: ['p(95)<2000'],          // < 2s TTFT
        total_latency: ['p(95)<15000'],               // < 15s total
        'http_req_failed': ['rate<0.02'],
    },
};

const PROMPTS = [
    "Summarize the latest tech news",
    "Explain quantum computing simply",
    "Write a Python function to reverse a string",
    "What are the benefits of microservices?",
];

export default function () {
    const start = Date.now();
    const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];

    // For streaming, k6 doesn't fully support SSE — use timing tricks
    const res = http.post(
        'https://api.acme.com/chat/stream',
        JSON.stringify({ message: prompt }),
        {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${__ENV.TOKEN}`,
            },
            timeout: '60s',
        },
    );

    totalLatency.add(Date.now() - start);
    check(res, {
        'status 200': (r) => r.status === 200,
        'has content': (r) => r.body.length > 0,
    });

    // Parse SSE body for token count
    const tokens = (res.body.match(/data:/g) || []).length;
    tokensGenerated.add(tokens);
}
```

**LLM-specific metrics to track:**
- **TTFT** — Time to first token (UX critical)
- **Tokens/sec** — generation throughput
- **Cost per request** — LLM API spend
- **Cache hit rate** — % served from semantic cache
- **Queue depth** — pending background jobs

---

### Q7: CI integration — fail builds on perf regression?

**Answer:** k6 thresholds as CI gates.

```yaml
# .github/workflows/perf.yml
name: Performance Tests
on:
  push:
    branches: [main]
  pull_request:

jobs:
  k6:
    runs-on: ubuntu-latest
    services:
      app:
        image: yourorg/api:latest
        ports: ["8000:8000"]
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres }

    steps:
      - uses: actions/checkout@v4

      - name: Wait for app
        run: |
          timeout 30 bash -c 'until curl -f http://localhost:8000/health; do sleep 1; done'

      - name: Seed test data
        run: psql -h localhost -U postgres -f tests/fixtures/seed.sql

      - name: Run k6 smoke test
        uses: grafana/k6-action@v0.3.1
        with:
          filename: tests/load/smoke.js
          flags: --vus 10 --duration 30s

      - name: Run k6 load test
        uses: grafana/k6-action@v0.3.1
        with:
          filename: tests/load/load.js
          flags: --vus 100 --duration 5m
        env:
          BASE_URL: http://localhost:8000

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: k6-report
          path: ./summary.json
```

**Smoke test (every commit):**
```javascript
// smoke.js — fast, 30s
export const options = {
    vus: 5,
    duration: '30s',
    thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.01'],
    },
};
```

**Full load test (nightly):**
```javascript
// nightly.js — full simulation
export const options = {
    stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 500 },
        { duration: '10m', target: 500 },
        { duration: '2m', target: 0 },
    ],
};
```

---

### Q8: Bottleneck identification — APM + load test combo?

**Answer:** Run load test → watch APM (Prometheus/Grafana/Datadog) → find what saturates first.

```python
# Locust + Prometheus exporter
from prometheus_client import start_http_server, Counter, Histogram
from locust import events

REQUESTS_TOTAL = Counter("locust_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_DURATION = Histogram("locust_request_duration_seconds", "Request duration", ["endpoint"])

@events.test_start.add_listener
def on_test_start(**kwargs):
    start_http_server(9090)  # expose /metrics

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, **kwargs):
    REQUESTS_TOTAL.labels(endpoint=name, status=response.status_code).inc()
    REQUEST_DURATION.labels(endpoint=name).observe(response_time / 1000)
```

**Watch for during load:**

| Symptom | Likely bottleneck |
|---|---|
| CPU 100% on app server | App code (profile with py-spy) |
| CPU 100% on DB | Bad query, missing index |
| High DB connections, low CPU | Connection pool exhausted (use PgBouncer) |
| High p99, normal p50 | GC pauses, occasional slow query |
| Memory steadily grows | Memory leak (test for 4+ hours) |
| Network out > 100 Mbps | Response size too big — paginate |
| Disk I/O 100% | Logging too verbose or no DB tuning |
| Rate of 429 increases | Rate limiter triggering — review limits |

---

## Tool Comparison Cheatsheet

| Need | Tool |
|---|---|
| Smoke test in CI (fast) | k6 |
| Complex multi-step user flows | Locust |
| Distributed 100K+ users | k6 Cloud or Locust on K8s |
| WebSocket load | k6 (native) |
| Python-only team | Locust |
| Cost-conscious (CI minutes) | k6 (lower resource use) |
| Beautiful dashboard | k6 + Grafana |
| Random scenarios | Locust |
| HTTP-only quick test | wrk, hey, bombardier |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Testing prod = bad day | Use staging or shadow prod |
| Load test from same network as app | Test from different region (real conditions) |
| No warm-up phase | Add 30s ramp before measuring |
| All users hit same data | Randomize user IDs, products |
| Hardcoded auth token expires | Refresh in `setup()` |
| Local DNS caching skews results | Use IP or disable DNS cache |
| Single machine maxed out | Use distributed mode or k6 Cloud |
| Locust workers OOM | Reduce users per worker; more workers |
| Test creates 1M orders in prod-like DB | Use a separate DB; clean up |
| Reports lost after run | `--csv`, `--html`, send to S3 |

---

## Senior-level Checklist

- [ ] SLOs defined for each endpoint (p50, p95, p99, RPS)
- [ ] Smoke test in CI (every commit, < 1 min)
- [ ] Load test in nightly CI (5-10 min)
- [ ] Stress test before major releases (find breaking point)
- [ ] Soak test before launches (memory leaks)
- [ ] Spike test for autoscaling validation
- [ ] APM (Prometheus/Datadog) watched during tests
- [ ] Realistic data distribution (not all users hit same row)
- [ ] Auth refresh handled
- [ ] Think time between requests (`sleep(1-3s)`)
- [ ] Thresholds fail the build on regression
- [ ] Reports archived (Grafana, S3, artifacts)
- [ ] Test in staging that mirrors prod (size, region)
- [ ] WebSocket / SSE / LLM endpoints have dedicated tests

---

## Related Docs
- `contract_testing_pact.md` — contract-level testing
- `property_based_testing_hypothesis.md` — input-driven testing
- `Phase3_DevOps/05_prometheus_grafana.md` — monitoring during load tests
- `Phase3_DevOps/14_chaos_engineering.md` — chaos + load combined
- `Phase3_API_Design/13_api_monitoring_slo.md` — SLO definitions

## External References
- Locust: https://locust.io
- k6: https://k6.io
- Grafana k6 Cloud: https://k6.io/cloud
- Locust plugins: https://github.com/SvenskaSpel/locust-plugins
