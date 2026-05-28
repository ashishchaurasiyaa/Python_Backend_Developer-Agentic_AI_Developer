# Performance Testing with Locust

> **Interview angle:** "Production launch se pehle load test karna hai — 10K concurrent users. Tool?"

---

## 1. Why Performance Testing?

- **Capacity planning:** How many users can we handle?
- **SLA validation:** Does p99 latency meet promise?
- **Regression detection:** Did deploy slow things down?
- **Bottleneck identification:** Where does it break?
- **Cost optimization:** Right-size infrastructure

**Common questions answered:**
- Can we handle Black Friday traffic?
- Will 10K WebSocket connections work?
- At what point does the DB become bottleneck?

---

## 2. Locust vs Other Tools

| Tool | Language | Pros | Cons |
|---|---|---|---|
| **Locust** | Python | Pythonic, WebUI, distributed | Single thread per worker |
| **k6** | JavaScript | Fast (Go runtime), modern | Need to learn JS DSL |
| **JMeter** | Java | Mature, plugins | Heavy GUI, XML config |
| **Gatling** | Scala | Fast, recordings | Scala/Java |
| **wrk/wrk2** | C | Very fast, simple | Limited scenarios |
| **ab (apache)** | C | Built-in, simple | Basic only |
| **Vegeta** | Go | Fast, CLI-friendly | Less DSL |

**Locust = best Python team choice.** k6 if team prefers JS.

---

## 3. Locust Basics

```bash
pip install locust
```

### Simple test (`locustfile.py`)
```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)    # 1-3 sec between actions

    @task
    def get_homepage(self):
        self.client.get("/")

    @task(3)                       # 3x weight — runs more often
    def get_products(self):
        self.client.get("/products")

    def on_start(self):
        """Called once per user when they start."""
        self.client.post("/login", json={"user": "test"})
```

### Run
```bash
locust -f locustfile.py
# Open http://localhost:8089 → set users + spawn rate
```

### Headless mode (CI)
```bash
locust -f locustfile.py \
    --host=http://api.example.com \
    --users=1000 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless \
    --html=report.html
```

---

## 4. Realistic User Scenarios

```python
import random
from locust import HttpUser, task, between, SequentialTaskSet

class CheckoutFlow(SequentialTaskSet):
    """Tasks run in order — realistic user journey."""

    @task
    def browse_products(self):
        self.client.get("/products")

    @task
    def view_product(self):
        product_id = random.randint(1, 1000)
        self.client.get(f"/products/{product_id}",
                        name="/products/[id]")    # group in metrics

    @task
    def add_to_cart(self):
        self.client.post("/cart", json={"product_id": 42})

    @task
    def checkout(self):
        with self.client.post("/checkout", catch_response=True) as response:
            if response.json().get("success"):
                response.success()
            else:
                response.failure("Checkout failed")


class WebsiteUser(HttpUser):
    wait_time = between(1, 5)
    tasks = [CheckoutFlow]

    def on_start(self):
        self.client.post("/login", json={
            "username": f"user_{random.randint(1, 10000)}",
            "password": "test123",
        })
```

---

## 5. Custom Metrics + Validation

```python
@task
def search(self):
    with self.client.get("/search?q=python", catch_response=True) as response:
        # Validate latency
        if response.elapsed.total_seconds() > 1.0:
            response.failure(f"Too slow: {response.elapsed.total_seconds()}s")

        # Validate content
        data = response.json()
        if not data.get("results"):
            response.failure("Empty results")
        else:
            response.success()
```

---

## 6. Authentication / Tokens

```python
class AuthenticatedUser(HttpUser):
    def on_start(self):
        # Login once per user
        response = self.client.post("/auth/login", json={
            "email": f"user{random.randint(1, 10000)}@test.com",
            "password": "password",
        })
        self.token = response.json()["token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
```

---

## 7. Distributed Locust (10K+ users)

Single Locust process limit: ~1000-5000 users (single Python thread).

### Master + Workers
```bash
# Master (UI + aggregation)
locust -f locustfile.py --master

# Workers (do the actual load)
locust -f locustfile.py --worker --master-host=master.internal

# Or in CI
locust -f locustfile.py --master --headless \
    --expect-workers=4 --users=10000 --spawn-rate=100
```

### Docker Compose
```yaml
services:
  master:
    image: locustio/locust
    ports: ["8089:8089"]
    volumes: ["./locustfile.py:/mnt/locust/locustfile.py"]
    command: -f /mnt/locust/locustfile.py --master

  worker:
    image: locustio/locust
    volumes: ["./locustfile.py:/mnt/locust/locustfile.py"]
    command: -f /mnt/locust/locustfile.py --worker --master-host=master
    deploy:
      replicas: 8        # 8 worker processes
```

---

## 8. Reading Locust Results

### Per-endpoint stats
```
# Name              # reqs    # fails  Avg(ms)  Min  Max  Median  RPS
GET /              50000      0/0%     45      10   200  42      245.2
POST /checkout     5000       50/1%    250     50   2000 230     24.5
```

- **# reqs:** total requests
- **# fails:** count + % failed
- **Avg/Min/Max/Median:** latency stats
- **RPS:** requests per second

### Percentiles (more important!)
- p50: median latency (typical user experience)
- p95: 5% of users wait this long or more
- **p99: tail latency** — alert on this
- p99.9: extreme outliers

```
GET /             p50:42ms  p95:120ms  p99:250ms  p99.9:800ms
```

---

## 9. Load Testing Strategies

### Strategy 1: Baseline (steady state)
Constant load to see if it's sustainable.
```python
--users=100 --spawn-rate=10 --run-time=30m
```

### Strategy 2: Stress test (find breaking point)
Increase load until failure.
```bash
# Manual ramp via UI: 100 → 500 → 1000 → 5000 → fail
```

### Strategy 3: Spike test
Sudden burst (Black Friday simulation).
```bash
locust ... --users=10000 --spawn-rate=1000    # spawn 1000/sec
```

### Strategy 4: Soak test (endurance)
Sustained load for hours/days. Find memory leaks.
```bash
--users=1000 --run-time=24h
```

### Strategy 5: Breakpoint test
Increase until specific metric crosses threshold (e.g., p99 > 500ms).

---

## 10. Custom Load Shape

Use `LoadTestShape` for complex patterns:

```python
from locust import LoadTestShape

class StagedLoad(LoadTestShape):
    """Custom load progression."""
    stages = [
        {"duration": 60,   "users": 100,  "spawn_rate": 10},
        {"duration": 120,  "users": 500,  "spawn_rate": 50},
        {"duration": 180,  "users": 1000, "spawn_rate": 100},
        {"duration": 300,  "users": 1000, "spawn_rate": 0},   # steady
        {"duration": 60,   "users": 0,    "spawn_rate": 100}, # ramp down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None
```

---

## 11. CI Integration

```yaml
# .github/workflows/load-test.yml

name: Load Test
on:
  schedule:
    - cron: '0 2 * * *'    # nightly 2am
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5

      - run: pip install locust

      - name: Run load test
        run: |
          locust -f tests/load/locustfile.py \\
            --host=${{ vars.STAGING_URL }} \\
            --users=500 --spawn-rate=50 --run-time=10m \\
            --headless --html=report.html --csv=results

      - name: Check SLA
        run: |
          python -c "
          import csv
          with open('results_stats.csv') as f:
              for row in csv.DictReader(f):
                  if row['Name'] == 'Aggregated':
                      p99 = float(row['99%'])
                      assert p99 < 500, f'p99 {p99}ms exceeds 500ms SLA'
          "

      - uses: actions/upload-artifact@v4
        with:
          name: load-test-report
          path: |
            report.html
            results_*.csv
```

---

## 12. Best Practices

### 1. Test like production
- Production-like data volume
- Production-like network (cross-AZ, not localhost)
- Production-similar dependencies (real DB, not SQLite)

### 2. Realistic user mix
80% browsing, 15% searching, 5% checking out. Don't slam single endpoint.

### 3. Warmup phase
Skip first 30 seconds of metrics (cache warming).

### 4. Monitor server-side
While Locust hammers, watch:
- DB connections (might exhaust)
- CPU on app servers
- Memory growth
- Database query duration

### 5. SLA targets
Define BEFORE testing:
- p99 < 200ms for reads
- p99 < 500ms for writes
- Error rate < 0.1%

---

## 13. Locust + Real Data Generation

```python
from faker import Faker
fake = Faker()

@task
def signup(self):
    self.client.post("/signup", json={
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
    })
```

---

## 14. WebSocket Load Testing

```python
from locust import User, task, between
import websocket

class WSUser(User):
    wait_time = between(1, 3)

    def on_start(self):
        self.ws = websocket.create_connection("ws://api.example.com/ws")

    def on_stop(self):
        self.ws.close()

    @task
    def send_message(self):
        self.ws.send(json.dumps({"type": "ping"}))
        response = self.ws.recv()
        # Validate response
```

---

## 15. Common Pitfalls

### Pitfall 1: Single-machine bottleneck
Locust runs on your laptop → laptop CPU maxes out before server. Use distributed mode.

### Pitfall 2: Test data identical for all users
All users login as `user_1` → DB row contention → false slowness. Randomize.

### Pitfall 3: Ignoring failure rate
"p99 50ms" but 30% of requests failed. Worse than slow but successful.

### Pitfall 4: Hitting wrong environment
Always confirm `--host=staging.example.com` not prod.

### Pitfall 5: No cleanup
Each run creates test users in DB → fills up.

---

## 16. k6 — Modern Alternative

```javascript
// loadtest.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 100 },
    { duration: '5m', target: 500 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<500'],   // p99 < 500ms
    http_req_failed: ['rate<0.01'],     // error rate < 1%
  },
};

export default function() {
  const res = http.get('https://api.example.com');
  check(res, { 'status was 200': r => r.status === 200 });
  sleep(1);
}

// Run: k6 run loadtest.js
```

**k6 vs Locust:**
- k6: faster, Go runtime, JS DSL, less RAM
- Locust: Pythonic, UI, mix easily with existing Python code

---

## 17. Interview Questions

**Q1: Load test kya measure?**
RPS, latency (p50/p95/p99), error rate, resource usage. SLAs validate.

**Q2: Locust vs JMeter?**
Locust = Pythonic, distributed easy. JMeter = mature, GUI, heavy.

**Q3: Single Locust limit?**
~1000-5000 users per Python process. Distributed for more.

**Q4: p99 important kyu?**
Tail latency = bad UX for some users. Avg can hide slow tails. SLO usually p99.

**Q5: Realistic test?**
Mix endpoints (80/15/5), random data, production-like infra, soak duration.

**Q6: CI integration?**
Nightly load test on staging. Threshold checks (p99, error rate). Fail PR if regression.

**Q7: SLA targets?**
Define BEFORE. Typical: p99 < 200ms read, < 500ms write, < 0.1% errors.

---

## 18. Best Practices

1. **Test in staging**, never prod (unless mirror)
2. **Realistic scenarios** (user journeys, weighted tasks)
3. **Random data** — no contention
4. **Distributed Locust** for > 1000 users
5. **Monitor server-side** during test (Grafana)
6. **Soak test for memory leaks** (24h+)
7. **CI nightly** with SLA gates
8. **Define SLA before testing**
9. **Spike + steady + ramp** all tested
10. **Iterate based on findings** — tune, retest

---

## Related
- [[01_pytest_advanced]]
- [[../../00_Year0-2_Junior/06_FastAPI/13_asgi_internals_uvicorn_tuning]]
- [[../../01_Year3-4_Mid/04_DevOps/05_prometheus_grafana]]
