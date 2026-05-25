"""
============================================================
LOCUST LOAD TESTING — Practical
============================================================
Install:
    pip install locust faker

Run:
    locust -f 06_performance_testing_locust.py --host=http://api.example.com
    Open http://localhost:8089

Headless:
    locust -f 06_performance_testing_locust.py \\
        --host=http://api.example.com \\
        --users=500 --spawn-rate=50 --run-time=10m \\
        --headless --html=report.html
"""
import random
import json


# ============================================================
# 1. SIMPLE LOCUSTFILE
# ============================================================
SIMPLE_LOCUSTFILE = '''
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    """Simulates a user browsing the site."""
    wait_time = between(1, 3)    # 1-3s pause between actions

    @task                          # default weight = 1
    def get_homepage(self):
        self.client.get("/")

    @task(3)                       # weight 3 — 3x more frequent
    def list_products(self):
        self.client.get("/products")

    @task(2)
    def view_product(self):
        product_id = random.randint(1, 1000)
        self.client.get(f"/products/{product_id}",
                        name="/products/[id]")   # group in report

    def on_start(self):
        """Per-user setup (once when user starts)."""
        self.client.post("/login", json={"user": "test", "pass": "test"})

    def on_stop(self):
        """Cleanup."""
        self.client.post("/logout")
'''


# ============================================================
# 2. AUTHENTICATED USER WITH TOKEN
# ============================================================
AUTH_LOCUSTFILE = '''
from locust import HttpUser, task, between
import random


class AuthenticatedUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        # Login with random test account
        response = self.client.post("/auth/login", json={
            "email": f"loadtest{random.randint(1, 10000)}@example.com",
            "password": "Test@1234",
        })
        if response.status_code == 200:
            token = response.json()["access_token"]
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        else:
            print(f"Login failed: {response.status_code}")
            self.environment.runner.quit()

    @task(5)
    def get_profile(self):
        self.client.get("/api/me")

    @task(2)
    def update_profile(self):
        self.client.patch("/api/me", json={"bio": "Updated"})
'''


# ============================================================
# 3. SEQUENTIAL FLOW (realistic user journey)
# ============================================================
CHECKOUT_FLOW = '''
from locust import HttpUser, task, between
from locust.user.sequential_taskset import SequentialTaskSet


class CheckoutJourney(SequentialTaskSet):
    """Tasks run IN ORDER — realistic e-commerce flow."""

    def on_start(self):
        self.client.post("/login", json={"user": "test"})

    @task
    def browse(self):
        self.client.get("/products")

    @task
    def view_details(self):
        self.product_id = random.randint(1, 100)
        self.client.get(f"/products/{self.product_id}",
                        name="/products/[id]")

    @task
    def add_to_cart(self):
        self.client.post("/cart", json={
            "product_id": self.product_id,
            "quantity": random.randint(1, 5),
        })

    @task
    def view_cart(self):
        self.client.get("/cart")

    @task
    def checkout(self):
        with self.client.post("/checkout",
                               json={"payment_method": "card"},
                               catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
                self.interrupt()    # restart the journey
            else:
                resp.failure(f"Checkout failed: {resp.status_code}")


class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    tasks = [CheckoutJourney]
'''


# ============================================================
# 4. CUSTOM METRICS + VALIDATION
# ============================================================
CUSTOM_METRICS = '''
from locust import HttpUser, task

class APIUser(HttpUser):
    @task
    def search(self):
        with self.client.get("/search?q=python", catch_response=True) as response:
            # 1. Status check
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return

            # 2. Latency check
            if response.elapsed.total_seconds() > 1.0:
                response.failure(f"Too slow: {response.elapsed.total_seconds():.2f}s")
                return

            # 3. Content validation
            try:
                data = response.json()
                if not data.get("results"):
                    response.failure("Empty results")
                    return
                if len(data["results"]) < 5:
                    response.failure(f"Too few results: {len(data['results'])}")
                    return
            except Exception as e:
                response.failure(f"JSON parse: {e}")
                return

            response.success()
'''


# ============================================================
# 5. CUSTOM LOAD SHAPE
# ============================================================
LOAD_SHAPE = '''
from locust import LoadTestShape


class StagedLoad(LoadTestShape):
    """Complex traffic pattern simulating real-world load."""

    stages = [
        # (duration_seconds, users, spawn_rate)
        {"duration": 60,   "users": 100,  "spawn_rate": 10},     # warm-up
        {"duration": 300,  "users": 500,  "spawn_rate": 50},     # ramp-up
        {"duration": 600,  "users": 500,  "spawn_rate": 0},      # steady
        {"duration": 60,   "users": 2000, "spawn_rate": 200},    # spike
        {"duration": 300,  "users": 2000, "spawn_rate": 0},      # spike steady
        {"duration": 60,   "users": 100,  "spawn_rate": 30},     # ramp-down
    ]

    def tick(self):
        run_time = self.get_run_time()
        cumulative = 0
        for stage in self.stages:
            cumulative += stage["duration"]
            if run_time < cumulative:
                return stage["users"], stage["spawn_rate"]
        return None    # stop test
'''


# ============================================================
# 6. DISTRIBUTED LOCUST (Master + Workers)
# ============================================================
DISTRIBUTED_SETUP = """
# Master (UI + aggregation)
locust -f locustfile.py --master \\
    --expect-workers=4 \\
    --host=http://api.example.com

# Workers (the actual load generators)
locust -f locustfile.py --worker --master-host=master.internal

# Run multiple workers per machine (one per CPU)
for i in {1..8}; do
    locust -f locustfile.py --worker --master-host=master &
done

# Headless distributed (CI)
locust -f locustfile.py --master --headless \\
    --expect-workers=4 \\
    --users=10000 --spawn-rate=100 --run-time=15m \\
    --csv=results
"""


# ============================================================
# 7. DOCKER COMPOSE FOR DISTRIBUTED
# ============================================================
DOCKER_COMPOSE = """
# docker-compose.yml

version: '3'
services:
  master:
    image: locustio/locust
    ports: ["8089:8089"]
    volumes: ["./locustfile.py:/mnt/locust/locustfile.py"]
    command: -f /mnt/locust/locustfile.py --master \\
             --host=http://api.example.com

  worker:
    image: locustio/locust
    volumes: ["./locustfile.py:/mnt/locust/locustfile.py"]
    command: -f /mnt/locust/locustfile.py --worker --master-host=master
    deploy:
      replicas: 8        # scale workers
    depends_on: [master]

# Start
# docker-compose up --scale worker=8
"""


# ============================================================
# 8. WEBSOCKET LOAD TESTING
# ============================================================
WEBSOCKET_LOAD = '''
from locust import User, task, between
import websocket
import json
import time


class WebSocketUser(User):
    wait_time = between(1, 3)

    def on_start(self):
        try:
            self.ws = websocket.create_connection(
                "ws://api.example.com/ws/chat",
                header={"Authorization": "Bearer token"},
            )
        except Exception as e:
            print(f"WS connect failed: {e}")
            self.environment.runner.quit()

    def on_stop(self):
        if hasattr(self, "ws"):
            self.ws.close()

    @task
    def send_message(self):
        start = time.time()
        try:
            self.ws.send(json.dumps({
                "type": "message",
                "text": "Hello from load test",
            }))
            response = self.ws.recv()
            duration = (time.time() - start) * 1000
            self.environment.events.request.fire(
                request_type="WS",
                name="send_message",
                response_time=duration,
                response_length=len(response),
                exception=None,
            )
        except Exception as e:
            self.environment.events.request.fire(
                request_type="WS",
                name="send_message",
                response_time=0,
                response_length=0,
                exception=e,
            )
'''


# ============================================================
# 9. CI INTEGRATION
# ============================================================
CI_WORKFLOW = """
# .github/workflows/load-test.yml

name: Load Test

on:
  schedule:
    - cron: '0 2 * * *'   # nightly 2 AM
  workflow_dispatch:
    inputs:
      users:
        description: 'Number of users'
        default: '500'

jobs:
  load-test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - run: pip install locust

      - name: Run load test
        run: |
          locust -f tests/load/locustfile.py \\
            --host=${{ vars.STAGING_URL }} \\
            --users=${{ inputs.users || 500 }} \\
            --spawn-rate=50 \\
            --run-time=10m \\
            --headless \\
            --html=report.html \\
            --csv=results \\
            --logfile=locust.log

      - name: Validate SLAs
        run: |
          python <<'EOF'
          import csv
          SLAs = {"p99_ms": 500, "p95_ms": 200, "fail_rate": 0.01}

          with open('results_stats.csv') as f:
              for row in csv.DictReader(f):
                  if row['Name'] == 'Aggregated':
                      p99 = float(row['99%'])
                      p95 = float(row['95%'])
                      fails = int(row['Failure Count'])
                      total = int(row['Request Count'])
                      fail_rate = fails / total if total else 0

                      print(f"p99: {p99}ms (target < {SLAs['p99_ms']})")
                      print(f"p95: {p95}ms (target < {SLAs['p95_ms']})")
                      print(f"Fail rate: {fail_rate:.2%}")

                      assert p99 < SLAs['p99_ms'], f"p99 SLA breach"
                      assert p95 < SLAs['p95_ms'], f"p95 SLA breach"
                      assert fail_rate < SLAs['fail_rate'], "Fail rate SLA breach"
          EOF

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: load-test-results
          path: |
            report.html
            results_*.csv
            locust.log

      - name: Slack notify on regression
        if: failure()
        run: |
          curl -X POST -d '{"text":"Load test SLA breach! ${{ github.run_id }}"}' \\
               ${{ secrets.SLACK_WEBHOOK }}
"""


# ============================================================
# 10. K6 ALTERNATIVE (modern, fast)
# ============================================================
K6_EXAMPLE = """
// loadtest.js

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },    // ramp to 100 users
    { duration: '5m', target: 100 },    // stay at 100
    { duration: '2m', target: 500 },    // ramp to 500
    { duration: '5m', target: 500 },    // stay
    { duration: '2m', target: 0 },      // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(99)<500'],   // p99 < 500ms
    http_req_failed:   ['rate<0.01'],   // < 1% errors
  },
};

export default function () {
  const res = http.get('https://api.example.com/products');
  check(res, {
    'status 200': r => r.status === 200,
    'fast enough': r => r.timings.duration < 1000,
  });
  sleep(1);
}

// Run:
// k6 run loadtest.js
// k6 run --vus 100 --duration 10m loadtest.js
// k6 cloud loadtest.js   (k6 Cloud)
"""


# ============================================================
# 11. RESULT INTERPRETATION
# ============================================================
RESULT_GUIDE = """
================================================================
INTERPRETING LOCUST RESULTS
================================================================

Sample output:
  # Name           # reqs   # fails   Avg    Min   Max    Median  RPS
  GET /            50000    0/0%      45ms   10ms  200ms  42ms    245
  POST /checkout   5000     50/1%     250ms  50ms  2000ms 230ms   24

KEY METRICS:
  RPS         = throughput (your capacity)
  Median      = typical user experience
  p95/p99     = tail latency (CRITICAL for SLA)
  # fails     = error rate

GOOD RESULTS:
  - p99 < 500ms for reads
  - p99 < 1000ms for writes
  - Error rate < 0.1%
  - Linear scaling (2x users → ~2x RPS)

BAD SIGNS:
  - p99 grows non-linearly with load → bottleneck
  - Errors increase → resource exhaustion
  - RPS plateaus while users grow → saturation
  - p99/median ratio > 10 → bad tail latency

SERVER-SIDE TO WATCH:
  - DB connection pool (saturation)
  - CPU on app servers
  - Memory growth (leaks)
  - Network I/O
  - Cache hit ratio
================================================================
"""


# ============================================================
# 12. SLA TARGETS BY TYPE
# ============================================================
SLA_TARGETS = """
================================================================
TYPICAL SLA TARGETS
================================================================

API endpoints:
  Read (cache hit):       p99 < 50ms
  Read (DB query):        p99 < 200ms
  Write (simple):         p99 < 300ms
  Write (complex):        p99 < 1000ms
  Search (Elasticsearch): p99 < 500ms
  Aggregation queries:    p99 < 2000ms

WebSocket:
  Connect:                p99 < 500ms
  Message round-trip:     p99 < 100ms

External APIs:
  Stripe payment:         p99 < 3000ms
  Email send (async):     fire-and-forget

Error rates:
  5xx errors:             < 0.1%
  4xx (excluding 404):    < 1%
  Total fail rate:        < 0.5%

Availability:
  3 nines (99.9%):        43 min downtime/month
  4 nines (99.99%):       4 min downtime/month
  5 nines (99.999%):      26 sec downtime/month
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("LOCUST LOAD TESTING")
    print("=" * 60)

    print("\nQuick start:")
    print("  pip install locust")
    print("  locust -f locustfile.py --host=http://api.example.com")

    print("\n--- SIMPLE LOCUSTFILE ---")
    print(SIMPLE_LOCUSTFILE)
    print("\n--- AUTH LOCUSTFILE ---")
    print(AUTH_LOCUSTFILE)
    print("\n--- CHECKOUT FLOW ---")
    print(CHECKOUT_FLOW)
    print("\n--- CUSTOM METRICS ---")
    print(CUSTOM_METRICS)
    print("\n--- LOAD SHAPE ---")
    print(LOAD_SHAPE)
    print("\n--- DISTRIBUTED SETUP ---")
    print(DISTRIBUTED_SETUP)
    print("\n--- DOCKER COMPOSE ---")
    print(DOCKER_COMPOSE)
    print("\n--- WEBSOCKET LOAD ---")
    print(WEBSOCKET_LOAD)
    print("\n--- CI WORKFLOW ---")
    print(CI_WORKFLOW)
    print("\n--- K6 ALTERNATIVE ---")
    print(K6_EXAMPLE)
    print(RESULT_GUIDE)
    print(SLA_TARGETS)
