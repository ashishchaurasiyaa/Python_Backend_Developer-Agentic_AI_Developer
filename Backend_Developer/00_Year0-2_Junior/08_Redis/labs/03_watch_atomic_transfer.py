"""
Redis Lab 03 — WATCH/MULTI/EXEC Optimistic-Lock Retry Loop
==============================================================
OBJECTIVE: khud likho ek atomic transfer jo WATCH se optimistic locking
karta hai — agar koi concurrent client beech me `acct:from` badal de, hamara
EXEC WatchError se fail ho, aur hum sahi se retry karein (money create/destroy
na ho).

TASK:
  1. TODO 1: `pipe.watch(from_key)` se watch shuru karo, balance read karo
  2. TODO 2: `pipe.multi()` + decrby/incrby queue karo + `pipe.execute()`
  3. TODO 3: `redis.WatchError` catch karke retry loop continue karo
  4. Run: python 03_watch_atomic_transfer.py

Prereq: docker compose up -d   |   pip install "redis[hiredis]>=5.0"
"""

import threading
import time
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

FROM_KEY = "lab:watch:acct:from"
TO_KEY = "lab:watch:acct:to"
START_BALANCE = 100
TRANSFER_AMOUNT = 50
INJECTED_DELTA = -30   # background thread ne concurrently from_key ko itna ghataya


def transfer(from_key: str, to_key: str, amount: int, inject_conflict_once: dict) -> bool:
    """
    Classic read-modify-write CAS loop: WATCH -> GET -> decide -> MULTI ->
    write -> EXEC -> agar WatchError aaye to retry.
    """
    attempts = 0
    with r.pipeline() as pipe:
        while True:
            attempts += 1
            try:
                # ─────────────────────────────────────────────────
                # TODO 1: `from_key` ko WATCH karo, phir uska current
                #         balance read karo (int me convert karo, None
                #         ho to 0 maano).
                #         Hint: pipe.watch(from_key); pipe.get(from_key)
                # ─────────────────────────────────────────────────
                pipe.watch(from_key)
                raw = pipe.get(from_key)
                balance = int(raw) if raw is not None else 0
                # ─────────────────────────────────────────────────

                if balance is None:
                    print("❌ TODO 1 abhi bharna hai")
                    return False

                # ── inject a real concurrent write AFTER our WATCH+GET,
                #    BEFORE our EXEC — this should bust the WATCH ──
                if attempts == 1 and not inject_conflict_once["done"]:
                    inject_conflict_once["done"] = True
                    other = redis.Redis(host="localhost", port=6379, decode_responses=True)
                    other.incrby(from_key, INJECTED_DELTA)
                    print(f"   ⚠️  [background thread] injected concurrent write "
                          f"({INJECTED_DELTA:+d}) mid-transaction")

                if balance < amount:
                    pipe.unwatch()
                    print(f"   ❌ attempt {attempts}: insufficient funds (balance={balance})")
                    return False

                # ─────────────────────────────────────────────────
                # TODO 2: transaction queue karo aur execute karo —
                #         from_key se `amount` ghatao, to_key me
                #         `amount` jodo, phir execute() call karo.
                #         Hint: pipe.multi(); pipe.decrby(from_key, amount)
                #               pipe.incrby(to_key, amount); pipe.execute()
                # ─────────────────────────────────────────────────
                pipe.multi()
                pipe.decrby(from_key, amount)
                pipe.incrby(to_key, amount)
                pipe.execute()
                committed = True
                # ─────────────────────────────────────────────────

                if not committed:
                    print("❌ TODO 2 abhi bharna hai")
                    return False

                print(f"   ✅ attempt {attempts}: committed (read balance was {balance})")
                return True

            except redis.WatchError:
                # ─────────────────────────────────────────────────
                # TODO 3: WatchError aaya matlab from_key humare
                #         WATCH ke baad badal gaya — sirf `continue`
                #         karo taaki loop dobara WATCH+read+decide kare.
                # ─────────────────────────────────────────────────
                print(f"   🔁 attempt {attempts}: WatchError — from_key badal gaya, retrying")
                continue


def main() -> None:
    r.set(FROM_KEY, START_BALANCE)
    r.set(TO_KEY, 0)
    print(f"\n[1] Starting balances: from={r.get(FROM_KEY)} to={r.get(TO_KEY)}")

    print(f"\n[2] Transferring {TRANSFER_AMOUNT} with a forced mid-flight conflict...")
    inject_conflict_once = {"done": False}
    ok = transfer(FROM_KEY, TO_KEY, TRANSFER_AMOUNT, inject_conflict_once)

    final_from = int(r.get(FROM_KEY) or 0)
    final_to = int(r.get(TO_KEY) or 0)
    total = final_from + final_to
    expected_total = START_BALANCE + INJECTED_DELTA

    print(f"\n[3] Final balances: from={final_from} to={final_to} (sum={total})")

    print("\n" + "─" * 55)
    if ok and total == expected_total and inject_conflict_once["done"]:
        print(f"✅ PASS — WatchError forced a retry, transfer recovered, and "
              f"from+to sum stayed conserved at {total} "
              f"(={START_BALANCE}{INJECTED_DELTA:+d} injected). No money created/destroyed.")
    else:
        print(f"❌ FAIL — ok={ok}, sum={total} (expected {expected_total}), "
              f"conflict_injected={inject_conflict_once['done']}")
        print("   Agar ok=False turant fail hua: TODO 1/2/3 check karo.")
        print("   Agar sum match nahi karta: TODO 2 ka MULTI/EXEC galat hai, ya")
        print("   TODO 3 retry ki jagah stale data pe commit kar raha hai.")

    r.delete(FROM_KEY, TO_KEY)

    print("""
SOCH (bolke jawab do):
  1. WATCH kya guarantee deta hai — "read lock" hai ya "conflict detector"?
     Farak samjhao.
  2. Retry loop infinite ho sakta hai agar contention bahut high ho —
     production me isko kaise bound karoge (max attempts, backoff)?
  3. Yeh optimistic locking hai. Pessimistic locking (SET NX lock) se kab
     better hai, kab worse (Lab 02 ka stampede lock yaad karo)?
  4. Agar WATCH ke baad koi UNRELATED key badal jaaye (jo humne watch nahi
     kiya), kya EXEC fail hoga? Kyun/kyun nahi?
""")


if __name__ == "__main__":
    main()
