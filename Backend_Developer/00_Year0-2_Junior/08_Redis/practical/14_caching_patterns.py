"""
Redis Practical 14 — Caching Patterns (cache-aside, stampede protection, TTL jitter)
Run: python 14_caching_patterns.py [asideAside|writethrough|writebehind|negative|stampede|jitter|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import sys
import time
import random
import threading
import json
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# "DB" — simulated slow backend (sleeps to mimic real DB latency)
# ════════════════════════════════════════════
FAKE_DB = {
    "1": {"id": 1, "name": "Alice", "plan": "pro"},
    "2": {"id": 2, "name": "Bob", "plan": "free"},
}
db_call_count = {"n": 0}


def slow_db_read(user_id, delay=0.2):
    """Real DB hote to network + disk seek + query time — yahan sleep se simulate."""
    db_call_count["n"] += 1
    time.sleep(delay)
    return FAKE_DB.get(user_id)


def slow_db_write(user_id, data, delay=0.1):
    time.sleep(delay)
    FAKE_DB[user_id] = data


# ════════════════════════════════════════════
# SECTION 1: CACHE-ASIDE (lazy loading)
# ════════════════════════════════════════════
def demo_aside():
    print("\n" + "=" * 50)
    print("  SECTION 1: CACHE-ASIDE")
    print("=" * 50)

    key = "user:1"
    r.delete(key)
    db_call_count["n"] = 0

    def get_user(user_id):
        cache_key = f"user:{user_id}"
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached), "HIT"
        value = slow_db_read(user_id)          # miss → DB
        r.set(cache_key, json.dumps(value), ex=300)
        return value, "MISS"

    t0 = time.perf_counter()
    v1, status1 = get_user("1")
    t1 = time.perf_counter()
    v2, status2 = get_user("1")                # should be cached now
    t2 = time.perf_counter()

    print(f"📊 1st call: {status1} — {(t1 - t0) * 1000:.0f}ms  → {v1}")
    print(f"📊 2nd call: {status2} — {(t2 - t1) * 1000:.0f}ms  → {v2}")
    print(f"✅ DB hit count: {db_call_count['n']} (should be 1 — 2nd read served from cache)")

    # ─── Write path: update DB, THEN invalidate cache (correct order) ───
    slow_db_write("1", {"id": 1, "name": "Alice", "plan": "enterprise"})
    r.delete(key)                              # invalidate AFTER db write, never before
    print("✅ DB updated → cache invalidated (write-then-invalidate, avoids stale-write race)")


# ════════════════════════════════════════════
# SECTION 2: WRITE-THROUGH
# ════════════════════════════════════════════
def demo_writethrough():
    print("\n" + "=" * 50)
    print("  SECTION 2: WRITE-THROUGH")
    print("=" * 50)

    def update_user_writethrough(user_id, data):
        slow_db_write(user_id, data)                       # DB first
        r.set(f"user:{user_id}", json.dumps(data), ex=300)  # then cache — one logical op
        return data

    t0 = time.perf_counter()
    update_user_writethrough("2", {"id": 2, "name": "Bob", "plan": "pro"})
    elapsed = (time.perf_counter() - t0) * 1000

    cached = json.loads(r.get("user:2"))
    print(f"📊 Write-through took {elapsed:.0f}ms (pays DB write + cache write latency together)")
    print(f"✅ Cache immediately consistent with DB: {cached}")
    print("   Trade-off: every write is slower, but reads are NEVER stale post-write")


# ════════════════════════════════════════════
# SECTION 3: WRITE-BEHIND (write-back)
# ════════════════════════════════════════════
def demo_writebehind():
    print("\n" + "=" * 50)
    print("  SECTION 3: WRITE-BEHIND (WRITE-BACK)")
    print("=" * 50)

    queue_key = "writebehind:queue"
    r.delete(queue_key)

    def update_user_writebehind(user_id, data):
        r.set(f"user:{user_id}", json.dumps(data), ex=300)         # fast: cache only
        r.rpush(queue_key, json.dumps({"user_id": user_id, "data": data}))
        return data

    t0 = time.perf_counter()
    update_user_writebehind("1", {"id": 1, "name": "Alice", "plan": "enterprise"})
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"📊 Write-behind returned in {elapsed:.0f}ms (cache-only write — fast path)")

    # ─── Background worker drains queue, batches DB writes ───
    def flush_worker():
        pending = r.lrange(queue_key, 0, -1)
        for item in pending:
            entry = json.loads(item)
            slow_db_write(entry["user_id"], entry["data"])
        r.delete(queue_key)
        print(f"✅ Flush worker persisted {len(pending)} queued write(s) to DB")

    worker = threading.Thread(target=flush_worker, daemon=True)
    worker.start()
    worker.join()
    print("⚠️ GOTCHA: agar cache crash ho jaaye is flush se PEHLE, ye writes LOST ho jaate")
    print("   hain — sirf tolerable-loss data (counters/analytics) ke liye use karo.")


# ════════════════════════════════════════════
# SECTION 4: NEGATIVE CACHING
# ════════════════════════════════════════════
def demo_negative():
    print("\n" + "=" * 50)
    print("  SECTION 4: NEGATIVE CACHING (cache penetration protection)")
    print("=" * 50)

    missing_id = "99999"
    key = f"user:{missing_id}"
    r.delete(key)
    db_call_count["n"] = 0

    def get_user_safe(user_id):
        cache_key = f"user:{user_id}"
        cached = r.get(cache_key)
        if cached is not None:
            return (None, "HIT-NEGATIVE") if cached == "__NULL__" else (json.loads(cached), "HIT")

        value = slow_db_read(user_id, delay=0.1)
        if value is None:
            r.set(cache_key, "__NULL__", ex=10)     # negative cache — SHORT ttl
            return None, "MISS-NEGATIVE"
        r.set(cache_key, json.dumps(value), ex=300)
        return value, "MISS"

    for i in range(5):
        _, status = get_user_safe(missing_id)
        print(f"   lookup #{i + 1} for non-existent id → {status}")

    print(f"✅ DB hit count for 5 repeated lookups of a missing key: {db_call_count['n']} "
          "(should be 1 — rest served from negative cache)")
    print("   At larger scale (ID-scanning attacks): Bloom filter of valid IDs instead of")
    print("   one negative-cache key per miss.")
    r.delete(key)


# ════════════════════════════════════════════
# SECTION 5: CACHE STAMPEDE PROTECTION — SET NX PX lock
# ════════════════════════════════════════════
def demo_stampede():
    print("\n" + "=" * 50)
    print("  SECTION 5: CACHE STAMPEDE PROTECTION")
    print("=" * 50)

    key = "product:hot"
    lock_key = f"lock:{key}"
    r.delete(key, lock_key)
    db_call_count["n"] = 0

    def get_product_with_lock(thread_id, results):
        cached = r.get(key)
        if cached:
            results.append((thread_id, "HIT", None))
            return

        # ─── SET NX PX — atomic "acquire lock only if free, auto-expire in 3s" ───
        got_lock = r.set(lock_key, str(thread_id), nx=True, px=3000)

        if got_lock:
            value = slow_db_read("1", delay=0.3)         # only the LOCK WINNER hits "DB"
            r.set(key, json.dumps(value), ex=60)
            r.delete(lock_key)
            results.append((thread_id, "MISS-REPOPULATED", value))
        else:
            # loser: brief wait + retry from cache instead of also hitting DB
            time.sleep(0.35)
            cached_after = r.get(key)
            results.append((thread_id, "WAITED-THEN-HIT" if cached_after else "WAITED-STILL-MISS", None))

    print("⏳ Simulating 20 concurrent requests all missing the same expired hot key...")
    results = []
    threads = [threading.Thread(target=get_product_with_lock, args=(i, results)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    repopulated = [x for x in results if x[1] == "MISS-REPOPULATED"]
    waited = [x for x in results if x[1].startswith("WAITED")]
    print(f"📊 Requests that actually hit the DB: {len(repopulated)} (should be 1 — the lock winner)")
    print(f"📊 Requests that waited + retried cache: {len(waited)}")
    print(f"✅ Total 'DB' calls this section: {db_call_count['n']} "
          "(WITHOUT the lock, this would've been ~20)")


# ════════════════════════════════════════════
# SECTION 6: TTL JITTER — synchronized vs jittered expiry
# ════════════════════════════════════════════
def demo_jitter():
    print("\n" + "=" * 50)
    print("  SECTION 6: TTL JITTER")
    print("=" * 50)

    n_keys = 50
    base_ttl = 2   # seconds — small for demo purposes

    # ─── Synchronized: every key gets the EXACT same TTL ───
    sync_keys = [f"sync:{i}" for i in range(n_keys)]
    for k in sync_keys:
        r.set(k, "v", ex=base_ttl)

    # ─── Jittered: TTL +/- random spread ───
    jitter_keys = [f"jit:{i}" for i in range(n_keys)]
    for k in jitter_keys:
        jitter = random.uniform(-0.8, 0.8)
        r.set(k, "v", ex=max(1, base_ttl + jitter))

    ttls_sync = [r.pttl(k) for k in sync_keys]
    ttls_jit = [r.pttl(k) for k in jitter_keys]

    print(f"📊 Synchronized TTLs — all {n_keys} keys expire within "
          f"{max(ttls_sync) - min(ttls_sync)}ms of each other")
    print(f"📊 Jittered TTLs      — {n_keys} keys spread across "
          f"{max(ttls_jit) - min(ttls_jit)}ms window")
    print("✅ Wider spread on jittered keys means expiry (and any resulting cache-repopulation")
    print("   load) is spread over time instead of arriving as one synchronized burst.")

    for k in sync_keys + jitter_keys:
        r.delete(k)


if __name__ == "__main__":
    sections = {
        "aside": demo_aside,
        "writethrough": demo_writethrough,
        "writebehind": demo_writebehind,
        "negative": demo_negative,
        "stampede": demo_stampede,
        "jitter": demo_jitter,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 14_caching_patterns.py [{'|'.join(sections)}|all]")
