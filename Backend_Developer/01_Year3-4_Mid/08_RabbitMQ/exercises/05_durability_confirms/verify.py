"""
RabbitMQ Exercise 05 — Verify: durable queue + persistent + confirms
=========================================================================
Teen alag proofs, broker ki REAL state se (management HTTP API),
na ki sirf "code chal gaya bina crash ke":

  A. subscriber.py ki queue "task_queue" durable=true hai (management API)
  B. publisher.py se bheja gaya message ACTUALLY delivery_mode=2
     (persistent) leke broker pe pahuncha (message ko fetch karke
     property check karte hain, apni khud ki claim par bharosa nahi
     karte)
  C. publisher confirms ACTUALLY kaam kar rahe hain — ek unroutable
     mandatory publish pe UnroutableError aani chahiye (fire-and-forget
     hota to silently drop ho jaata, koi exception nahi aati)

Prereq: RabbitMQ management plugin ON (docker-compose.yml me by default,
        rabbitmq:3-management image) — http://localhost:15672
Run: python verify.py
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pika

HERE = os.path.dirname(os.path.abspath(__file__))
MGMT = "http://localhost:15672/api"
AUTH = base64.b64encode(b"guest:guest").decode()
PROBE_QUEUE = "verify_durability_probe"


def api(path, method="GET", body=None):
    req = urllib.request.Request(f"{MGMT}{path}", method=method)
    req.add_header("Authorization", f"Basic {AUTH}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=5) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None
    except urllib.error.URLError:
        return None, None


def main():
    status, _ = api("/overview")
    if status != 200:
        print(f"❌ RabbitMQ management API (localhost:15672) tak nahi pahunch paaye (status={status}).")
        print("   Management plugin ON hai? docker-compose.yml 'rabbitmq:3-management' use karta hai.")
        print("   Check: curl -u guest:guest http://localhost:15672/api/overview")
        sys.exit(1)

    results = {}

    # ── Test A: subscriber.py ki queue durable hai? ──────────────────
    print("[A] subscriber.py chala rahe hain (sirf queue declare hone tak)...")
    sub = subprocess.Popen(
        [sys.executable, "-u", os.path.join(HERE, "subscriber.py")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(1.5)
    out_lines = []
    if sub.poll() is not None:
        out_lines = sub.stdout.read().splitlines()
    sub.terminate()
    time.sleep(0.3)
    sub.kill()

    if any("❌ TODO" in l for l in out_lines):
        print("❌ subscriber.py ka TODO 3 abhi bharna hai:")
        print("\n".join(out_lines))
        sys.exit(1)

    status, q = api("/queues/%2f/task_queue")
    durable = isinstance(q, dict) and q.get("durable") is True
    results["A"] = durable
    shown = q.get("durable") if isinstance(q, dict) else "queue not found"
    print(f"  task_queue durable={shown} -> {'✅' if durable else '❌'}")

    # ── Test B + C: publisher.py ka function-level access chahiye ────
    print("[B/C] publisher.py import kar rahe hain...")
    sys.path.insert(0, HERE)
    try:
        import publisher
    except SystemExit:
        print("❌ publisher.py ka TODO 1 abhi bharna hai (import ke time crash hua)")
        sys.exit(1)

    # verify-only durable queue, "Error" se bound — publisher ka asli
    # message yahin pakadenge inspect karne ke liye.
    vch = publisher.connection.channel()
    vch.queue_declare(queue=PROBE_QUEUE, durable=True)
    vch.queue_bind(exchange="logs_exchange", queue=PROBE_QUEUE, routing_key="Error")

    print("[B] ek persistent message publish kar rahe hain (routing_key=Error)...")
    try:
        publisher.publish_message("Error", "EMsg")
    except SystemExit:
        print("❌ publisher.py ka TODO 2 abhi bharna hai")
        sys.exit(1)
    time.sleep(0.5)

    status, fetched = api(
        f"/queues/%2f/{PROBE_QUEUE}/get",
        method="POST",
        body={"count": 1, "ackmode": "ack_requeue_false", "encoding": "auto"},
    )
    delivery_mode = None
    if isinstance(fetched, list) and fetched:
        delivery_mode = fetched[0].get("properties", {}).get("delivery_mode")
    persistent = (delivery_mode == 2)
    results["B"] = persistent
    print(f"  message properties.delivery_mode={delivery_mode} (2=persistent) "
          f"-> {'✅' if persistent else '❌'}")

    print("[C] confirms test — mandatory publish to a routing_key nobody is bound to...")
    confirms_ok = False
    try:
        publisher.publish_message("nobody-bound-to-this-key", "ping", mandatory=True)
        # koi exception nahi aayi = message silently drop ho gaya (fire-and-forget)
    except SystemExit:
        print("❌ publisher.py ka TODO 1 (CONFIRMS_ENABLED) abhi bharna hai")
        sys.exit(1)
    except pika.exceptions.UnroutableError:
        confirms_ok = True
    results["C"] = confirms_ok
    outcome = "raised UnroutableError" if confirms_ok else "silently succeeded (no exception)"
    print(f"  unroutable+mandatory publish {outcome} -> {'✅' if confirms_ok else '❌'}")

    vch.queue_delete(queue=PROBE_QUEUE)
    publisher.connection.close()

    print("-" * 55)
    if all(results.values()):
        print("✅ PASS — durable queue + persistent delivery + publisher confirms, teeno sahi hain")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"❌ FAIL — test(s) {failed} fail hue.")
        if "A" in failed:
            print("   subscriber.py TODO 3 (QUEUE_DURABLE) check karo")
        if "B" in failed:
            print("   publisher.py TODO 2 (DELIVERY_MODE) check karo")
        if "C" in failed:
            print("   publisher.py TODO 1 (CONFIRMS_ENABLED) check karo")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. Agar sirf delivery_mode=2 ho par queue durable=False ho, broker
     restart ke baad kya bachega?
  2. mandatory=True flag ke bina, confirms ON hone par bhi kya
     unroutable message silently drop ho sakta hai? (Hint: confirms
     sirf "broker ne accept kiya" confirm karte hain, "kisi queue tak
     pahuncha" nahi — mandatory alag guarantee hai)
  3. Yahan humne sync/exception-based confirms dekhe (mandatory +
     UnroutableError). Async callback-based confirms bhi hote hain —
     throughput trade-off kya hoga high-volume publishing me?
""")


if __name__ == "__main__":
    main()
