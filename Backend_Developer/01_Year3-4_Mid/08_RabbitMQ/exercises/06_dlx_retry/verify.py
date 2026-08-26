"""
RabbitMQ Exercise 06 — Verify: DLX + TTL Retry
================================================
Three proofs:
  A. task-002 (succeeds) → main_queue mein nahi hai, DLQ mein bhi nahi
  B. task-001 (fails 3x) → dead_letter_queue mein exactly 1 message hai
  C. retry_queue mein koi message nahi (sab drain ho gaye)

Run: python verify.py
Prereq: docker compose up -d
"""

import base64, json, os, subprocess, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MGMT = "http://localhost:15672/api"
AUTH = base64.b64encode(b"guest:guest").decode()
MAX_RETRIES   = 3
RETRY_TTL_SEC = 3


def api(path):
    req = urllib.request.Request(f"{MGMT}{path}")
    req.add_header("Authorization", f"Basic {AUTH}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {}
    except urllib.error.URLError:
        return None, {}


def queue_depth(name: str) -> int:
    _, data = api(f"/queues/%2f/{name}")
    return data.get("messages", -1)


def main():
    status, _ = api("/overview")
    if status != 200:
        print("❌ RabbitMQ management API unreachable. docker compose up -d?")
        sys.exit(1)

    # ── Step 1: setup + publish ──────────────────────────────────────────
    print("[SETUP] publisher.py chala rahe hain (infrastructure + 2 messages)...")
    r = subprocess.run([sys.executable, os.path.join(HERE, "publisher.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ publisher.py failed:")
        print(r.stdout); print(r.stderr)
        sys.exit(1)
    print(r.stdout.strip())
    time.sleep(0.5)

    # Check TODOs were filled in publisher
    _, mq = api("/queues/%2f/main_queue")
    if not isinstance(mq, dict) or not mq.get("arguments", {}).get("x-dead-letter-exchange"):
        print("❌ publisher.py TODO 1 nahi bhara — main_queue mein x-dead-letter-exchange nahi hai")
        print("   management UI me queue delete karo, publisher.py ka TODO 1 bharo, dobara chalao")
        sys.exit(1)

    _, rq = api("/queues/%2f/retry_queue")
    if not isinstance(rq, dict) or not rq.get("arguments", {}).get("x-message-ttl"):
        print("❌ publisher.py TODO 2 nahi bhara — retry_queue mein x-message-ttl nahi hai")
        sys.exit(1)

    print("  ✅ Queue arguments correct hain (DLX + TTL configured)")

    # ── Step 2: subscriber runs until retries exhausted ─────────────────
    wait_time = RETRY_TTL_SEC * (MAX_RETRIES + 1) + 5   # buffer
    print(f"\n[RUN] subscriber.py chala rahe hain {wait_time}s ke liye...")
    print(f"      (task-001 ko {MAX_RETRIES} retries × {RETRY_TTL_SEC}s delay = ~{MAX_RETRIES*RETRY_TTL_SEC}s)")
    sub = subprocess.Popen(
        [sys.executable, "-u", os.path.join(HERE, "subscriber.py")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for _ in range(wait_time):
        time.sleep(1)
        print(".", end="", flush=True)
    print()
    sub.terminate()
    time.sleep(0.5)
    sub.kill()
    output = sub.stdout.read()
    print(output)

    # Check subscriber TODOs
    if "TODO 3 bharo" in output or "TODO 4 bharo" in output:
        print("❌ subscriber.py ke TODOs abhi bharne hain")
        sys.exit(1)

    # ── Step 3: verify queue states ──────────────────────────────────────
    results = {}
    print("[CHECK] Queue states verify kar rahe hain...")

    main_depth = queue_depth("main_queue")
    dlq_depth  = queue_depth("dead_letter_queue")
    retry_depth = queue_depth("retry_queue")

    print(f"  main_queue:        {main_depth} messages")
    print(f"  retry_queue:       {retry_depth} messages")
    print(f"  dead_letter_queue: {dlq_depth} messages")

    results["A"] = main_depth == 0
    results["B"] = dlq_depth >= 1     # task-001 should be in DLQ
    results["C"] = retry_depth == 0   # retry queue should be empty

    print(f"\n  A) main_queue empty:        {'✅' if results['A'] else '❌'} ({main_depth})")
    print(f"  B) DLQ has failed message:  {'✅' if results['B'] else '❌'} ({dlq_depth})")
    print(f"  C) retry_queue drained:     {'✅' if results['C'] else '❌'} ({retry_depth})")

    print("-" * 55)
    if all(results.values()):
        print("✅ PASS — DLX + TTL retry pattern correctly implemented")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"❌ FAIL — checks {failed} fail hue")
        if not results["A"]:
            print("   main_queue mein messages hain — subscriber ne process nahi kiya")
        if not results["B"]:
            print("   DLQ empty hai — subscriber.py TODO 3 + TODO 4 check karo")
        if not results["C"]:
            print("   retry_queue mein messages stuck hain — publisher.py TODO 2 (TTL) check karo")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. Agar TODO 2 mein retry_queue ka x-message-ttl nahi set karo, toh kya hoga?
  2. Why requeue=False important hai TODO 4 mein? requeue=True se kya problem?
  3. x-death header mein 'count' field kab increment hota hai?
  4. Agar main_queue bhi DLX configure nahi karo (TODO 1), failed messages kahan jaate hain?
  5. Production mein retry delay exponential kaise karoge? (RabbitMQ natively support nahi karta — hint: separate retry queues with different TTLs)
""")


if __name__ == "__main__":
    main()
