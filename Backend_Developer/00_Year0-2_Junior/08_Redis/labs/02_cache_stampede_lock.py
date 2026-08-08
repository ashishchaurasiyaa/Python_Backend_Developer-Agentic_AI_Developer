"""
Redis Lab 02 — Cache Stampede Protection (SET NX PX lock)
============================================================
OBJECTIVE: 20 threads ek saath ek EXPIRED hot key maangte hain — bina lock ke
sab 20 "DB" ko hit karenge (stampede). TODO bharke sirf EK winner ko DB call
karne do, baaki wait/retry karke winner ka populate kiya value paayein.

TASK:
  1. TODO 1: `SET lock_key <token> NX PX <ms>` se lock lene ki koshish karo
  2. TODO 2: lock na mile to short sleep karke retry karo (cache dobara check)
  3. Run: python 02_cache_stampede_lock.py

Prereq: docker compose up -d   |   pip install "redis[hiredis]>=5.0"
"""

import json
import secrets
import threading
import time
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

KEY = "lab:stampede:hot_key"
LOCK_KEY = "lab:stampede:hot_key:lock"
LOCK_TTL_MS = 2000
NUM_THREADS = 20
RETRY_SLEEP_S = 0.02
MAX_RETRIES = 200   # generous — real DB fetch below takes ~200ms

db_call_count = {"n": 0}
db_lock = threading.Lock()


def db_fetch(delay: float = 0.2) -> dict:
    """Slow 'DB' — thread-safe counter increment to prove exactly 1 call happens."""
    with db_lock:
        db_call_count["n"] += 1
    time.sleep(delay)
    return {"computed_at": time.time(), "value": "expensive-result"}


def get_with_stampede_protection() -> dict:
    """
    Expired hot key ko repopulate karte time sirf EK caller DB ko hit kare —
    baaki wait karke winner ka populate kiya cache value read karein.
    """
    cached = r.get(KEY)
    if cached is not None:
        return json.loads(cached)

    token = secrets.token_hex(8)

    # ─────────────────────────────────────────────────────
    # TODO 1: NX+PX lock lene ki koshish karo — sirf EK thread
    #         True paayega, baaki sab False.
    #         Hint: r.set(LOCK_KEY, token, nx=True, px=LOCK_TTL_MS)
    # ─────────────────────────────────────────────────────
    got_lock = bool(r.set(LOCK_KEY, token, nx=True, px=LOCK_TTL_MS))
    # ─────────────────────────────────────────────────────

    if got_lock:
        try:
            # double-check: shayad kisi aur ne already populate kar diya ho
            cached = r.get(KEY)
            if cached is not None:
                return json.loads(cached)

            value = db_fetch()
            r.set(KEY, json.dumps(value), ex=60)
            return value
        finally:
            # token-compare release (bare DEL would risk deleting someone
            # else's lock if we overran the TTL — see practical/19_redlock)
            release_script = r.register_script("""
                if redis.call('GET', KEYS[1]) == ARGV[1] then
                    return redis.call('DEL', KEYS[1])
                end
                return 0
            """)
            release_script(keys=[LOCK_KEY], args=[token])

    # ─────────────────────────────────────────────────────
    # TODO 2: lock nahi mila — thoda so kar (RETRY_SLEEP_S) phir
    #         se KEY check karo. MAX_RETRIES tak loop karo. Jaise
    #         hi KEY populate ho jaaye, decode karke return karo.
    #         Hint: time.sleep(RETRY_SLEEP_S), phir r.get(KEY)
    # ─────────────────────────────────────────────────────
    for _ in range(MAX_RETRIES):
        time.sleep(RETRY_SLEEP_S)
        cached = r.get(KEY)
        if cached is not None:
            return json.loads(cached)
    # ─────────────────────────────────────────────────────

    final = r.get(KEY)
    if final is None:
        print("❌ TODO 2 abhi bharna hai (retry loop ne kabhi cache populate hote nahi dekha)")
        return None
    return json.loads(final)


def main() -> None:
    r.delete(KEY, LOCK_KEY)
    db_call_count["n"] = 0

    print(f"\n[1] {NUM_THREADS} threads racing on one expired hot key...")
    results = [None] * NUM_THREADS

    def worker(idx):
        results[idx] = get_with_stampede_protection()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(NUM_THREADS)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0

    print(f"  → all {NUM_THREADS} threads done in {elapsed:.2f}s, "
          f"db_fetch() called {db_call_count['n']}x")

    print("\n" + "─" * 55)
    all_none = any(res is None for res in results)
    same_value = len({json.dumps(res, sort_keys=True) for res in results if res}) == 1

    if not all_none and same_value and db_call_count["n"] == 1:
        print(f"✅ PASS — exactly 1 db_fetch() call despite {NUM_THREADS} concurrent "
              "callers; everyone got the winner's value.")
    else:
        print(f"❌ FAIL — db_call_count={db_call_count['n']} (expected exactly 1), "
              f"any None results: {all_none}, all same value: {same_value}")
        if db_call_count["n"] > 1:
            print("   TODO 1 check karo — lock (SET NX PX) sahi se acquire nahi ho raha,")
            print("   multiple threads DB ko parallel hit kar rahe hain.")
        if all_none:
            print("   TODO 2 check karo — retry loop cache ko sahi se poll/return nahi kar raha.")

    r.delete(KEY, LOCK_KEY)

    print("""
SOCH (bolke jawab do):
  1. Lock TTL (LOCK_TTL_MS) chhota rakha to kya risk hai agar DB fetch usse
     zyada slow ho jaaye? Bada rakha to kya risk hai agar lock-holder crash ho?
  2. Bare DEL se lock release karte to kya bug aa sakta tha (practical/19 ka
     baredel_bug section yaad karo)?
  3. Yeh "wait aur retry" approach hai — alternative kya hai (probabilistic
     early expiration / stale-while-revalidate)? Trade-off kya hai?
  4. Production me is lock ko kis granularity pe lete — per-key ya per-shard?
     Kyun?
""")


if __name__ == "__main__":
    main()
