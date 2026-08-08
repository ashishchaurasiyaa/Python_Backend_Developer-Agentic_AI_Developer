"""
Redis Practical 13 — Transactions (MULTI/EXEC/WATCH/DISCARD)
Run: python 13_transactions_watch.py [basic|watch_cas|no_rollback|discard|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import sys
import threading
import time
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: MULTI/EXEC BASICS — queuing + atomic batch execution
# ════════════════════════════════════════════
def demo_basic():
    print("\n" + "=" * 50)
    print("  SECTION 1: MULTI/EXEC BASICS")
    print("=" * 50)

    r.delete("tx:a", "tx:b")

    # ─── redis-py: pipeline(transaction=True) hi MULTI/EXEC wrap karta hai ───
    pipe = r.pipeline(transaction=True)
    pipe.set("tx:a", 1)
    pipe.incr("tx:b")
    pipe.incr("tx:b")
    results = pipe.execute()          # ek hi round trip, atomic block
    print(f"✅ Queued 3 commands, EXEC results: {results}")
    print(f"   tx:a = {r.get('tx:a')}   tx:b = {r.get('tx:b')}")
    print("   Isolation guarantee: EXEC ke beech koi doosra client")
    print("   ka command interleave nahi ho sakta (single-threaded exec).")

    r.delete("tx:a", "tx:b")


# ════════════════════════════════════════════
# SECTION 2: DISCARD — abandon a queued transaction
# ════════════════════════════════════════════
def demo_discard():
    print("\n" + "=" * 50)
    print("  SECTION 2: DISCARD — queued transaction abandon karna")
    print("=" * 50)

    r.delete("tx:discard_me")
    conn = r.connection_pool.get_connection()
    try:
        conn.send_command("MULTI")
        conn.read_response()
        conn.send_command("SET", "tx:discard_me", "should_not_persist")
        conn.read_response()          # "QUEUED"
        conn.send_command("DISCARD")
        conn.read_response()
        print("✅ MULTI...DISCARD — queue thrown away, SET never ran")
    finally:
        r.connection_pool.release(conn)

    val = r.get("tx:discard_me")
    print(f"   tx:discard_me = {val!r}  (expected: None — DISCARD ne queue ud a di)")


# ════════════════════════════════════════════
# SECTION 3: WATCH-BASED CAS — atomic transfer with retry on conflict
# ════════════════════════════════════════════
def demo_watch_cas():
    print("\n" + "=" * 50)
    print("  SECTION 3: WATCH-BASED CAS — atomic transfer + retry loop")
    print("=" * 50)

    r.set("acct:from", 100)
    r.set("acct:to", 0)
    print(f"📊 Starting balances: from={r.get('acct:from')} to={r.get('acct:to')}")

    conflict_injected = {"done": False}

    def transfer(from_key, to_key, amount):
        """
        Classic WATCH → GET → decide → MULTI → write → EXEC → retry-on-conflict
        pattern. Iska use: transfer, inventory reservation, capped counter —
        sab isi skeleton pe based hain.
        """
        attempts = 0
        with r.pipeline() as pipe:
            while True:
                attempts += 1
                try:
                    pipe.watch(from_key)
                    balance = int(pipe.get(from_key) or 0)

                    # ─── Attempt #1 par ek CONCURRENT write inject karo ───
                    # taaki prove ho sake ki WATCH sach me conflict detect karta hai
                    if attempts == 1 and not conflict_injected["done"]:
                        conflict_injected["done"] = True
                        other_client = redis.Redis(
                            host='localhost', port=6379, decode_responses=True
                        )
                        other_client.decrby(from_key, 30)  # "another request" races in
                        print("   ⚠️  [concurrent client] decremented from_key by 30 "
                              "mid-flight — this should bust our WATCH")

                    if balance < amount:
                        pipe.unwatch()
                        print(f"   ❌ Attempt {attempts}: insufficient funds "
                              f"(balance={balance}) — no retry needed")
                        return False

                    pipe.multi()
                    pipe.decrby(from_key, amount)
                    pipe.incrby(to_key, amount)
                    pipe.execute()   # WatchError raised if from_key changed since WATCH
                    print(f"   ✅ Attempt {attempts}: committed (read balance={balance})")
                    return True
                except redis.WatchError:
                    print(f"   🔁 Attempt {attempts}: WatchError — from_key changed "
                          "since WATCH, retrying read-modify-write loop")
                    continue

    transfer("acct:from", "acct:to", 50)
    print(f"📊 Final balances: from={r.get('acct:from')} to={r.get('acct:to')}")
    print("   Expected: from=100-30(injected)-50(transfer)=20, to=50")
    print("   Retry loop ne concurrent modification ke baad correct value")
    print("   se dobara read+decide kiya — CAS ne stale-read overwrite rokha.")

    r.delete("acct:from", "acct:to")


# ════════════════════════════════════════════
# SECTION 4: RUNTIME ERROR MID-TRANSACTION — proves NO rollback
# ════════════════════════════════════════════
def demo_no_rollback():
    print("\n" + "=" * 50)
    print("  SECTION 4: RUNTIME ERROR = NO ROLLBACK (SQL se alag!)")
    print("=" * 50)

    r.delete("tx:counter1", "tx:counter2", "tx:wrongtype")
    r.set("tx:wrongtype", "i_am_a_string")   # LPUSH ispe fail hoga (WRONGTYPE)

    pipe = r.pipeline(transaction=True)
    pipe.incr("tx:counter1")             # command 1 — succeeds
    pipe.lpush("tx:wrongtype", "x")      # command 2 — FAILS at runtime (WRONGTYPE)
    pipe.incr("tx:counter2")             # command 3 — succeeds anyway!
    results = pipe.execute(raise_on_error=False)

    print(f"📊 Raw EXEC results: {results}")
    for i, res in enumerate(results, 1):
        status = "❌ ERROR" if isinstance(res, Exception) else f"✅ OK → {res}"
        print(f"   Command {i}: {status}")

    print(f"\n   tx:counter1 = {r.get('tx:counter1')}  (expected 1 — ran fine)")
    print(f"   tx:counter2 = {r.get('tx:counter2')}  (expected 1 — ran fine, "
          "even though command BEFORE it failed)")
    print("   👉 Ek runtime error (WRONGTYPE) ne baaki queued commands ko")
    print("      block/rollback NAHI kiya. SQL transaction se yahi bada fark hai —")
    print("      queue-time error (bad syntax) puri transaction abort karta hai,")
    print("      but runtime error sirf uss ek command ka result-slot me error deta hai.")

    r.delete("tx:counter1", "tx:counter2", "tx:wrongtype")


if __name__ == "__main__":
    sections = {
        "basic": demo_basic,
        "discard": demo_discard,
        "watch_cas": demo_watch_cas,
        "no_rollback": demo_no_rollback,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 13_transactions_watch.py [{'|'.join(sections)}|all]")
