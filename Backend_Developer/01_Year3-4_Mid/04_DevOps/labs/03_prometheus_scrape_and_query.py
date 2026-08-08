"""
DevOps Lab 03 — Prometheus Scrape & Query
=============================================
OBJECTIVE: end-to-end PROVE karo ki scrape pipeline kaam karta hai — app ka
Counter badhao, Prometheus ko scrape karne do, phir Prometheus ke apne HTTP
API se query karke wahi value nikalo. "YAML sahi lagti hai" kaafi nahi hai.

TASK:
  1. `configs/prometheus.yml` kholo — TODO bharo (scrape target).
  2. Run: python3 03_prometheus_scrape_and_query.py

Prereq: docker compose up -d prometheus metrics-app   (yeh script khud bhi chala dega)
"""

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent
PROM_CONF = LABS_DIR / "configs" / "prometheus.yml"
METRICS_APP_URL = "http://localhost:19091/"
PROM_QUERY_URL = "http://localhost:19090/api/v1/query"
N_REQUESTS = 7            # kitne "work" requests bhejenge metrics-app ko
SCRAPE_INTERVAL_S = 5      # configs/prometheus.yml me set kiya gaya interval


def check_todos_filled() -> bool:
    content = PROM_CONF.read_text()
    if "___TODO_1___" in content:
        print("❌ TODO 1 abhi baaki hai in configs/prometheus.yml (scrape target)")
        print('   Hint: targets: ["metrics-app:8000"]')
        return False
    return True


def compose(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(LABS_DIR / "docker-compose.yml"), *args],
        cwd=LABS_DIR, capture_output=True, text=True,
    )


def wait_for_http(url: str, timeout_s: int = 30):
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            return urllib.request.urlopen(url, timeout=2)
        except (urllib.error.URLError, ConnectionError) as e:
            last_err = e
            time.sleep(1)
    print(f"  (last connection error: {last_err})")
    return None


def query_prometheus(promql: str):
    url = f"{PROM_QUERY_URL}?{urllib.parse.urlencode({'query': promql})}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, ConnectionError) as e:
        print(f"  (prometheus query error: {e})")
        return None


def cleanup() -> None:
    compose("stop", "prometheus", "metrics-app")
    compose("rm", "-f", "prometheus", "metrics-app")


def main() -> None:
    if not check_todos_filled():
        return

    print("\n[1] Bringing up prometheus + metrics-app...")
    up = compose("up", "-d", "--build", "prometheus", "metrics-app")
    if up.returncode != 0:
        print("❌ FAIL — docker compose up nahi hua")
        print(up.stderr[-2000:])
        return

    try:
        print(f"\n[2] Waiting for metrics-app ({METRICS_APP_URL})...")
        # NOTE: /metrics use karte hain readiness check ke liye, kyunki woh
        # path REQUESTS Counter ko increment NAHI karta — hume clean count
        # chahiye jab hum N_REQUESTS bhejenge.
        if wait_for_http(f"{METRICS_APP_URL}metrics") is None:
            print("❌ FAIL — metrics-app up nahi hua. `docker compose logs metrics-app` dekho.")
            return

        print(f"\n[3] Sending {N_REQUESTS} real requests to metrics-app (Counter badhega)...")
        for i in range(N_REQUESTS):
            urllib.request.urlopen(f"{METRICS_APP_URL}work/{i}", timeout=2)
        print(f"  {N_REQUESTS} requests bhej diye")

        # Metrics-app ka apna /metrics endpoint bhi confirm karte hain (sanity)
        with urllib.request.urlopen(f"{METRICS_APP_URL}metrics", timeout=2) as resp:
            raw_metrics = resp.read().decode()
        direct_ok = f"lab_requests_total {float(N_REQUESTS)}" in raw_metrics or \
                    any(line.startswith("lab_requests_total") and line.strip().endswith(str(float(N_REQUESTS)))
                        for line in raw_metrics.splitlines())
        print(f"  metrics-app /metrics khud kehta hai: "
              f"{'✓ counter correct' if direct_ok else '⚠ counter mismatch dikh raha'}")

        print(f"\n[4] Prometheus ko scrape karne ka time de rahe hain "
              f"(~{SCRAPE_INTERVAL_S * 2}s)...")
        time.sleep(SCRAPE_INTERVAL_S * 2)

        print("\n[5] Prometheus API se query kar rahe hain: lab_requests_total ...")
        scraped_value = None
        deadline = time.time() + 20
        result = None
        while time.time() < deadline:
            result = query_prometheus("lab_requests_total")
            if result and result.get("status") == "success" and result["data"]["result"]:
                scraped_value = float(result["data"]["result"][0]["value"][1])
                if scraped_value >= N_REQUESTS:
                    break
            time.sleep(2)

        print(f"  Prometheus se mila value: {scraped_value}")

        print("\n" + "─" * 55)
        if scraped_value is not None and scraped_value == float(N_REQUESTS):
            print(f"✅ PASS — Prometheus ne exactly {N_REQUESTS} scrape kiya, "
                  "jo humne bheje the — scrape pipeline end-to-end kaam karta hai")
        else:
            print("❌ FAIL")
            if scraped_value is None:
                print("   Prometheus se metric mila hi nahi — TODO 1 (scrape target)")
                print("   check karo. http://localhost:19090/targets pe target UP hai?")
            else:
                print(f"   Value mismatch: Prometheus={scraped_value} vs sent={N_REQUESTS}")
                print("   Ho sakta hai extra scrape cycles ne stale/duplicate count uthaya —")
                print("   lab dobara chalao (fresh container = fresh counter).")

        print("""
SOCH (bolke jawab do):
  1. Agar TODO 1 me galat port likhte (e.g. 8080 instead of 8000) to
     `/targets` page pe kya dikhta? (Hint: DOWN, connection refused)
  2. `scrape_interval: 5s` production me kyun risky ho sakta hai high-
     cardinality metrics ke saath? (Hint: storage, network overhead)
  3. Counter sirf badhta hai — agar app restart ho jaaye to value 0 se
     shuru hoti hai. `rate()` function isse kaise deal karta hai?
  4. Prometheus khud "pull" model use karta hai (scrape karta hai), push
     nahi. Kab push-based (Pushgateway) chahiye hoga?
""")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
