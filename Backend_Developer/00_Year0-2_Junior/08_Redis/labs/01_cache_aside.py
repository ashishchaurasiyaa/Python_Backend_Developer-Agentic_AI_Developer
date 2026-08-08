"""
Redis Lab 01 — Cache-Aside (Lazy Loading)
===========================================
OBJECTIVE: khud likho get-or-set cache-aside logic — cache check karo, miss pe
"DB" se fetch karo, cache populate karo TTL ke saath.

TASK:
  1. TODO 1: cache HIT path — agar key Redis me mile to wahi return karo
  2. TODO 2: cache MISS path — DB se fetch karke Redis me TTL ke saath likho
  3. Run: python 01_cache_aside.py

Prereq: docker compose up -d   |   pip install "redis[hiredis]>=5.0"
"""

import json
import time
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

TTL_SECONDS = 300

# ─── simulated slow backend — real DB hote to network + disk seek lagta ───
FAKE_DB = {
    "1": {"id": 1, "name": "Alice", "plan": "pro"},
    "2": {"id": 2, "name": "Bob", "plan": "free"},
}
db_call_count = {"n": 0}


def db_fetch(user_id: str, delay: float = 0.15) -> dict:
    """Slow DB read — count karta hai kitni baar actually call hua."""
    db_call_count["n"] += 1
    time.sleep(delay)
    return FAKE_DB.get(user_id)


def get_user(user_id: str) -> tuple:
    """Cache-aside getter. Returns (value, status) jahan status HIT ya MISS hai."""
    cache_key = f"lab:cacheaside:user:{user_id}"

    cached = r.get(cache_key)

    # ─────────────────────────────────────────────────────
    # TODO 1: agar `cached` None nahi hai (cache HIT), to usse
    #         JSON se decode karke `(value, "HIT")` return karo.
    #         Hint: json.loads(cached)
    # ─────────────────────────────────────────────────────
    if cached is not None:
        value = json.loads(cached)
        if value is None:
            print("❌ TODO 1 abhi bharna hai")
            return None, "ERROR"
        return value, "HIT"

    # ─────────────────────────────────────────────────────
    # TODO 2: cache MISS — db_fetch() se value nikalo, Redis me
    #         cache_key pe TTL_SECONDS ke saath JSON string set
    #         karo, phir (value, "MISS") return karo.
    #         Hint: r.set(cache_key, json.dumps(value), ex=TTL_SECONDS)
    # ─────────────────────────────────────────────────────
    value = db_fetch(user_id)
    r.set(cache_key, json.dumps(value), ex=TTL_SECONDS)
    wrote_to_cache = True
    # ─────────────────────────────────────────────────────

    if not wrote_to_cache:
        print("❌ TODO 2 abhi bharna hai")
        return None, "ERROR"

    return value, "MISS"


def main() -> None:
    key = "lab:cacheaside:user:1"
    r.delete(key)
    db_call_count["n"] = 0

    print("\n[1] First call (expect MISS, DB hit)...")
    v1, status1 = get_user("1")
    print(f"  → {status1}: {v1}")

    print("\n[2] Second call, same key (expect HIT, no DB hit)...")
    v2, status2 = get_user("1")
    print(f"  → {status2}: {v2}")

    print("\n" + "─" * 55)
    if status1 == "MISS" and status2 == "HIT" and v1 == v2 and db_call_count["n"] == 1:
        print(f"✅ PASS — db_fetch() called {db_call_count['n']}x, both calls "
              f"returned same value: {v1}")
    else:
        print(f"❌ FAIL — status1={status1}, status2={status2}, "
              f"db_call_count={db_call_count['n']} (expected 1), v1==v2: {v1 == v2}")
        print("   Agar status1/status2 ERROR hai: TODO 1/2 check karo.")
        print("   Agar db_call_count != 1: TODO 2 me cache write missing ya TODO 1")
        print("   me HIT path DB ko phir se call kar raha hai.")

    r.delete(key)

    print("""
SOCH (bolke jawab do):
  1. Cache-aside me write path kaisa hota hai? DB update karne ke baad cache
     ko invalidate karoge ya update? Kyun (stale-write race se bachne ke liye)?
  2. TTL kitna rakhoge aur kyun? Bahut chhota TTL vs bahut bada TTL ka
     trade-off kya hai (staleness vs cache hit ratio)?
  3. Agar DB down ho jaaye, cache-aside get_user() kya karega? Isse
     "cache stampede on DB outage" jaisa scenario kaise bachta/nahi bachta?
""")


if __name__ == "__main__":
    main()
