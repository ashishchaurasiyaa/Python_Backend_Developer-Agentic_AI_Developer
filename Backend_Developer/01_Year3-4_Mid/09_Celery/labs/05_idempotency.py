"""
Celery Lab 05 — Idempotency
============================
OBJECTIVE: samjho ki same task dobara chalane pe kya hota hai — aur isse kaise rokein.

SCENARIO:
  Payment task chal raha hai → worker crash → broker task wapas deliver karta hai
  → task DOBARA chalta hai → customer DOUBLE CHARGE ho jaata hai.

TASK:
  1. tasks.py me process_payment_idempotent ke TODO A aur TODO B bharo
  2. Terminal 1: celery -A tasks worker --loglevel=info --concurrency=2
     Terminal 2: python 05_idempotency.py

Prereq: docker compose up -d   |   pip install "celery[redis]" redis

TODO A (tasks.py line ~131):
    existing = r.get(cache_key)
    if existing:
        return {"order_id": order_id, "tx_id": existing, "idempotent": True,
                "status": "ALREADY_PROCESSED"}

TODO B (tasks.py line ~145):
    r.setex(cache_key, 86400, tx_id)   # store result 24h
"""

import uuid
from tasks import process_payment_naive, process_payment_idempotent


# ─────────────────────────────────────────────────────────────
# PART 1 — Naive (NOT idempotent)
# ─────────────────────────────────────────────────────────────
def demo_naive_double_charge():
    print("\n[PART 1] Naive payment — NOT idempotent")
    print("  Same order submit karo TWICE (simulates retry-on-crash)")

    order_id = 1001
    amount   = 999.0

    r1 = process_payment_naive.delay(order_id, amount)
    r2 = process_payment_naive.delay(order_id, amount)  # "retry"

    res1 = r1.get(timeout=10)
    res2 = r2.get(timeout=10)

    print(f"  Attempt 1: tx_id={res1['tx_id']}, charged={res1['charged']}")
    print(f"  Attempt 2: tx_id={res2['tx_id']}, charged={res2['charged']}")

    if res1["tx_id"] != res2["tx_id"]:
        print("  ❌ DOUBLE CHARGE! Dono tx_id alag hain — customer ne 2x pay kiya")
    else:
        print("  ✅ tx_id same raha (unlikely for naive)")


# ─────────────────────────────────────────────────────────────
# PART 2 — Idempotent via idempotency_key
# ─────────────────────────────────────────────────────────────
def demo_idempotent():
    print("\n[PART 2] Idempotent payment — same key = same result")

    order_id       = 2001
    amount         = 1500.0
    idempotency_key = str(uuid.uuid4())   # client generates once, reuses on retry

    print(f"  idempotency_key = {idempotency_key}")

    # ─────────────────────────────────────────────────────
    # TODO 1: process_payment_idempotent ko PEHLI BAAR call karo
    r1 = None   # ← isse badlo: process_payment_idempotent.delay(...)
    # ─────────────────────────────────────────────────────

    if r1 is None:
        print("  ❌ TODO 1 abhi bharna hai")
        return

    res1 = r1.get(timeout=10)
    print(f"  First call:  tx_id={res1['tx_id']}, status={res1['status']}, idempotent={res1['idempotent']}")

    # ─────────────────────────────────────────────────────
    # TODO 2: SAME idempotency_key ke saath DOBARA call karo (retry simulate)
    r2 = None   # ← isse badlo: same key use karo
    # ─────────────────────────────────────────────────────

    if r2 is None:
        print("  ❌ TODO 2 abhi bharna hai")
        return

    res2 = r2.get(timeout=10)
    print(f"  Second call: tx_id={res2['tx_id']}, status={res2['status']}, idempotent={res2['idempotent']}")

    if res1["tx_id"] == res2["tx_id"] and res2["idempotent"] is True:
        print("  ✅ PASS — dobara call ka same tx_id aaya, customer charge nahi hua dobara")
    else:
        print("  ❌ tasks.py ke TODO A aur TODO B bharo (Redis check + setex)")


# ─────────────────────────────────────────────────────────────
# PART 3 — Different orders → different results
# ─────────────────────────────────────────────────────────────
def demo_different_keys():
    print("\n[PART 3] Alag orders → alag tx_id (idempotency sirf same key pe)")

    key_a = str(uuid.uuid4())
    key_b = str(uuid.uuid4())

    ra = process_payment_idempotent.delay(3001, 500.0, key_a)
    rb = process_payment_idempotent.delay(3002, 750.0, key_b)

    res_a = ra.get(timeout=10)
    res_b = rb.get(timeout=10)

    print(f"  Order 3001: tx_id={res_a['tx_id']}, status={res_a['status']}")
    print(f"  Order 3002: tx_id={res_b['tx_id']}, status={res_b['status']}")

    if res_a["tx_id"] != res_b["tx_id"]:
        print("  ✅ Alag orders → alag tx_id (correct)")
    else:
        print("  ⚠️  Unexpected: alag keys pe same tx_id")


# ─────────────────────────────────────────────────────────────
# SOCH QUESTIONS (answer aloud before running):
# 1. Agar tasks.py me TODO A nahi bhara to PART 2 ka result kya hoga?
# 2. Idempotency key kahan store karna best hai — Redis ya PostgreSQL? Kyun?
# 3. acks_late=True ke saath idempotency kyun zaroori hai?
# 4. External payment API (Razorpay/Stripe) ka idempotency key kaise bhejte hain?
# 5. 24h TTL ke baad kya hoga agar same key dobara aaye?
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_naive_double_charge()
    demo_idempotent()
    demo_different_keys()

    print("\n" + "─" * 55)
    print("SOCH QUESTIONS upar dekho — answer aloud karo before next lab.")
