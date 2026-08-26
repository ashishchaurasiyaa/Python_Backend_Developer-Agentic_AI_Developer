"""
RabbitMQ Exercise 08 — Verify: Idempotent Consumer
===================================================
Three proofs:
  A. Queue empty hai (saare 3 deliveries processed + ACKed)
  B. DB mein exactly 1 row hai (same payment_id only once charged)
  C. Subscriber output shows "DUPLICATE" for 2nd and 3rd delivery

Run: python verify.py
"""

import base64, json, os, sqlite3, subprocess, sys, time, urllib.error, urllib.request

HERE    = os.path.dirname(os.path.abspath(__file__))
MGMT    = "http://localhost:15672/api"
AUTH    = base64.b64encode(b"guest:guest").decode()
DB_PATH = os.path.join(HERE, "payments.db")


def api(path):
    req = urllib.request.Request(f"{MGMT}{path}")
    req.add_header("Authorization", f"Basic {AUTH}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        return getattr(e, "code", None), {}


def queue_depth(name: str) -> int:
    _, data = api(f"/queues/%2f/{name}")
    return data.get("messages", -1)


def main():
    if api("/overview")[0] != 200:
        print("❌ RabbitMQ management API unreachable. docker compose up -d?")
        sys.exit(1)

    # ── Clean DB from previous runs ─────────────────────────────────────
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("[CLEAN] Purana payments.db delete kiya")

    # ── Step 1: publish 3 deliveries ────────────────────────────────────
    print("[SETUP] publisher.py se 3 deliveries publish kar rahe hain...")
    r = subprocess.run([sys.executable, os.path.join(HERE, "publisher.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ publisher.py failed:", r.stderr)
        sys.exit(1)
    print(r.stdout.strip())
    time.sleep(0.3)

    # ── Step 2: subscriber processes all 3 ──────────────────────────────
    print("\n[RUN] subscriber.py chala rahe hain...")
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "subscriber.py")],
        capture_output=True, text=True, timeout=15,
    )
    output = r.stdout
    print(output)

    # ── Step 3: verify ──────────────────────────────────────────────────
    results = {}
    print("[CHECK] Verifying...")

    # A: Queue empty
    main_depth = queue_depth("payment_queue_demo")
    results["A"] = main_depth == 0
    print(f"  A) Queue empty:                {'✅' if results['A'] else '❌'} ({main_depth} messages)")

    # B: DB has exactly 1 row
    db_rows = 0
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        db_rows = conn.execute("SELECT COUNT(*) FROM processed_payments").fetchone()[0]
        conn.close()
    results["B"] = (db_rows == 1)
    print(f"  B) DB has exactly 1 payment:   {'✅' if results['B'] else '❌'} ({db_rows} rows)")

    # C: Output shows "DUPLICATE" for 2 deliveries
    duplicate_count = output.count("DUPLICATE")
    results["C"] = (duplicate_count >= 2)
    print(f"  C) 2 duplicates skipped:       {'✅' if results['C'] else '❌'} ({duplicate_count} 'DUPLICATE' mentions)")

    print("-" * 55)
    if all(results.values()):
        print("✅ PASS — idempotent consumer correctly deduplicates payments")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"❌ FAIL — checks {failed} fail hue")
        if not results["B"]:
            if db_rows == 0:
                print("   DB mein koi row nahi — TODO 2 (charge_customer + INSERT) fill karo")
            elif db_rows > 1:
                print(f"   DB mein {db_rows} rows hain — TODO 1 (duplicate check) fill karo")
        if not results["C"]:
            print("   'DUPLICATE' output nahi dikha — TODO 1 (row check + skip) fill karo")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. INSERT karo phir ACK, ya pehle ACK phir INSERT — kaunsa sahi hai aur kyun?
  2. Agar DB INSERT fail ho (disk full) aur ACK pehle ho gaya — kya problem?
  3. Idempotency key sirf message_id pe depend karna safe hai? Alternative kya hai?
  4. Redis mein idempotency key store karo ya PostgreSQL mein? Trade-offs?
  5. Real Stripe/Razorpay payments mein idempotency key kahan set hoti hai?
""")


if __name__ == "__main__":
    main()
