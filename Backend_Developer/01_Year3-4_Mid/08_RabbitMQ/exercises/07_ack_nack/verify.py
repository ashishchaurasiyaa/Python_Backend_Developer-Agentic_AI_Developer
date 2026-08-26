"""
RabbitMQ Exercise 07 — Verify: ACK / NACK Behavior
====================================================
Three proofs (all from broker state, not just "code ran"):
  A. "success" message consumed (ack_demo_queue depth decreased)
  B. "requeue" message back in queue (NACK+requeue=True puts it back)
  C. "drop" message in DLQ (NACK+requeue=False → DLX → ack_demo_dlq)

Run: python verify.py
"""

import base64, json, os, subprocess, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MGMT = "http://localhost:15672/api"
AUTH = base64.b64encode(b"guest:guest").decode()


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
    if api("/overview")[0] != 200:
        print("❌ RabbitMQ management API unreachable. docker compose up -d?")
        sys.exit(1)

    # ── Step 1: publish messages ────────────────────────────────────────
    print("[SETUP] publisher.py se 3 messages publish kar rahe hain...")
    r = subprocess.run([sys.executable, os.path.join(HERE, "publisher.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ publisher.py failed:", r.stderr)
        sys.exit(1)
    print(r.stdout.strip())
    time.sleep(0.3)
    before_depth = queue_depth("ack_demo_queue")
    print(f"  Queue depth before subscriber: {before_depth}")

    # ── Step 2: subscriber processes ───────────────────────────────────
    print("\n[RUN] subscriber.py chala rahe hain (3 messages process karega)...")
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "subscriber.py")],
        capture_output=True, text=True, timeout=15,
    )
    print(r.stdout.strip())
    time.sleep(0.5)

    # ── Step 3: verify ─────────────────────────────────────────────────
    main_depth = queue_depth("ack_demo_queue")
    dlq_depth  = queue_depth("ack_demo_dlq")
    print(f"\n[CHECK] ack_demo_queue:  {main_depth} messages")
    print(f"[CHECK] ack_demo_dlq:    {dlq_depth} messages")

    results = {}

    # A: "success" message consumed → one less in main queue
    # B: "requeue" message back in queue → main_depth includes it
    # C: "drop" message in DLQ → dlq_depth >= 1
    # After subscriber: success=ACKed(gone), requeue=NACKed+requeued(back), drop=NACKed+DLQ
    # So main_queue should have exactly 1 message (the requeued one)
    results["A_and_B"] = main_depth == 1    # success gone, requeue back
    results["C"]       = dlq_depth >= 1     # drop message in DLQ

    print(f"\n  A) 'success' ACKed (removed):          {'✅' if main_depth < before_depth else '❌'}")
    print(f"  B) 'requeue' back in main_queue:       {'✅' if main_depth == 1 else '❌'} (depth={main_depth})")
    print(f"  C) 'drop' message in DLQ:              {'✅' if results['C'] else '❌'} (dlq={dlq_depth})")

    print("-" * 55)
    all_pass = (main_depth == 1 and dlq_depth >= 1)
    if all_pass:
        print("✅ PASS — ACK/NACK/requeue behavior sahi hai")
    else:
        print("❌ FAIL — subscriber.py ke TODOs check karo:")
        if main_depth == before_depth:
            print("   TODO 1 (basic_ack) ya TODO 2 (basic_nack+requeue) fill nahi hua")
        if dlq_depth == 0:
            print("   TODO 3 (basic_nack+requeue=False) fill nahi hua — message DLQ nahi gaya")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. basic_ack, basic_nack(requeue=True), basic_nack(requeue=False) — teeno ka real-world use case kya hai?
  2. basic_reject vs basic_nack mein kya fark hai?
  3. auto_ack=True ke saath consumer crash hone pe kya hota hai?
  4. Agar "requeue" message pe koi retry limit nahi hai, kya problem ho sakti hai?
  5. DLX configure nahi hota aur requeue=False use karo toh message kahan jaata hai?
""")


if __name__ == "__main__":
    main()
