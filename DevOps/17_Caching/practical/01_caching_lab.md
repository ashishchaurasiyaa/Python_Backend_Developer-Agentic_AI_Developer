# Caching — Hands-On Lab
**DevOps Track · Phase 17 Practical**

## Prerequisites

All local, no cloud spend.

- Docker + Docker Compose (Redis, Memcached, Postgres all run as containers)
- Python 3.10+ with `redis`, `pymemcache` (or `python-memcached`), `psycopg2-binary`, `flask` or plain scripts — a couple of small scripts are enough, no framework required
- `redis-cli` and `memcached-tool` (or just `nc`/`telnet` for a quick Memcached check) on your host or via `docker exec`
- Basic Python threading/`concurrent.futures` knowledge for the stampede simulation in Lab 3
- A simple load-generation tool: `ab` (ApacheBench, usually preinstalled on macOS/Linux) or a small Python script with `concurrent.futures.ThreadPoolExecutor` — either works for the stampede lab

---

## Lab 1: Redis vs Memcached — Eviction Policy Behavior Under Memory Pressure

**Objective:** Directly observe the difference the lesson calls out as the most dangerous default: `noeviction` causing writes to fail vs. `allkeys-lru` evicting gracefully.

**Task:**
1. Start a Redis container with `maxmemory 10mb` and `maxmemory-policy noeviction`.
2. Write a script that writes keys in a loop (`key:1`, `key:2`, ...) each holding ~50KB of data, until you hit an error. Record the exact error Redis returns.
3. Restart Redis (or `FLUSHALL`) with `maxmemory-policy allkeys-lru` instead, same `maxmemory 10mb`.
4. Re-run the same write loop for the same duration/key count. Confirm it does NOT error — instead check `INFO stats` for `evicted_keys` growing.
5. Read back `key:1` (the very first key written) after the loop — is it still there? Explain why or why not, tying it to LRU semantics.
6. Repeat with `volatile-lru` and note the difference: write half your keys WITH a TTL and half WITHOUT, and confirm only the ones with a TTL are eligible for eviction (the no-TTL keys should survive even as memory fills, until you eventually hit an OOM error again since nothing else is evictable).

<details>
<summary>Solution / walkthrough</summary>

```bash
docker run -d --name redis-noevict -p 6379:6379 redis:7 \
    redis-server --maxmemory 10mb --maxmemory-policy noeviction
```

```python
# fill.py
import redis, sys
r = redis.Redis(host="localhost", port=6379)
payload = "x" * 50_000   # ~50KB per key
i = 0
try:
    while True:
        r.set(f"key:{i}", payload)
        i += 1
except redis.exceptions.ResponseError as e:
    print(f"Stopped at key:{i} — error: {e}")
```

```bash
python fill.py
# Stopped at key:190 — error: OOM command not allowed when used memory > 'maxmemory'.
# This is the exact failure mode the lesson warns about: WRITES START FAILING.
```

```bash
docker exec redis-noevict redis-cli CONFIG SET maxmemory-policy allkeys-lru
docker exec redis-noevict redis-cli FLUSHALL
python fill.py
# runs to completion (or until you stop it) with no exception — Redis silently
# evicts old keys instead of rejecting writes

docker exec redis-noevict redis-cli INFO stats | grep evicted_keys
# evicted_keys:143   (or similar — grows as new writes push out old ones)
```

```bash
docker exec redis-noevict redis-cli GET key:1
# (nil) — key:1 was evicted early since allkeys-lru evicts least-recently-used
# across ALL keys, and key:1 was never re-read after being written, making it
# the oldest/coldest key in the dataset
```

```bash
docker exec redis-noevict redis-cli CONFIG SET maxmemory-policy volatile-lru
docker exec redis-noevict redis-cli FLUSHALL
```

```python
# half with TTL, half without
import redis
r = redis.Redis(host="localhost", port=6379)
for i in range(200):
    if i % 2 == 0:
        r.set(f"ttlkey:{i}", "x"*50_000, ex=3600)
    else:
        r.set(f"permkey:{i}", "x"*50_000)   # no TTL — NOT eligible for volatile-lru eviction
```

Result: as memory fills, only `ttlkey:*` entries get evicted under `volatile-lru`. If you keep writing past the point where all `ttlkey:*` are gone, you hit OOM again — because `permkey:*` entries have no TTL and volatile-lru refuses to touch them, functionally behaving like `noeviction` once the TTL'd keys are exhausted. This is a real production gotcha: `volatile-lru` looks safe but isn't a substitute for `allkeys-lru` unless every key genuinely has a TTL.
</details>

---

## Lab 2: Implement and Compare Cache-Aside, Write-Through, and Explicit Invalidation

**Objective:** Build the same small "user profile" read/write path three different ways against a real Postgres + Redis pair, and observe the staleness behavior each strategy produces.

**Task:**
1. Start Postgres and Redis containers. Create a `users` table with `id, name, email`.
2. Implement `get_user_cache_aside(user_id)` and `update_user_cache_aside(user_id, data)` exactly per the lesson's cache-aside pattern (check cache, miss → DB → populate cache with TTL; update writes DB only, cache goes stale until TTL expiry).
3. Implement `update_user_write_through(user_id, data)` that writes to DB and cache in the same call.
4. Implement `update_user_explicit_invalidation(user_id, data)` that writes DB then deletes the cache key.
5. Demonstrate the staleness bug: call `get_user_cache_aside` to warm the cache, then call the CACHE-ASIDE update function (not write-through/invalidation) with new data, then call `get_user_cache_aside` again immediately — show it returns STALE data because nothing invalidated the cache.
6. Now repeat the same sequence using the explicit-invalidation update function — show the read immediately after returns FRESH data.
7. Write 2-3 sentences on when you'd still choose cache-aside + TTL alone despite the staleness window it allows.

<details>
<summary>Solution / walkthrough</summary>

```bash
docker run -d --name pg-cache -e POSTGRES_PASSWORD=pass -p 5432:5432 postgres:16
docker run -d --name redis-cache -p 6379:6379 redis:7
```

```sql
CREATE TABLE users (id INT PRIMARY KEY, name TEXT, email TEXT);
INSERT INTO users VALUES (1, 'Ashish', 'ashish@example.com');
```

```python
import redis, psycopg2, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
conn = psycopg2.connect(host="localhost", user="postgres", password="pass")

def get_user_cache_aside(user_id):
    cached = r.get(f"user:{user_id}")
    if cached:
        print("CACHE HIT")
        return json.loads(cached)
    print("CACHE MISS -> DB")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
    data = {"id": row[0], "name": row[1], "email": row[2]}
    r.set(f"user:{user_id}", json.dumps(data), ex=300)
    return data

def update_user_cache_aside_BUGGY(user_id, name):
    # writes DB only — cache is now stale until TTL expiry, on purpose to demo the bug
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, user_id))
    conn.commit()

def update_user_write_through(user_id, name):
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, user_id))
    conn.commit()
    data = {"id": user_id, "name": name, "email": "ashish@example.com"}
    r.set(f"user:{user_id}", json.dumps(data), ex=300)   # keep cache in sync

def update_user_explicit_invalidation(user_id, name):
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, user_id))
    conn.commit()
    r.delete(f"user:{user_id}")   # force next read to repopulate via cache-aside
```

```python
# Step 5 — demonstrate the staleness bug
print(get_user_cache_aside(1))              # CACHE MISS -> DB, warms cache with "Ashish"
update_user_cache_aside_BUGGY(1, "Ashish Chaurasiya")
print(get_user_cache_aside(1))              # CACHE HIT -> still returns "Ashish" (STALE!)
```

```python
# Step 6 — same sequence with explicit invalidation instead
update_user_explicit_invalidation(1, "Ashish C.")
print(get_user_cache_aside(1))              # CACHE MISS -> DB -> "Ashish C." (FRESH)
```

**When cache-aside + bare TTL alone is still the right call:** for read-heavy data where a few minutes of staleness is genuinely harmless to the business (a user's "last seen" timestamp, a product's aggregate view count, a homepage feed) — the operational simplicity of never having to wire up invalidation on every write path outweighs the bounded staleness cost. It stops being fine the moment staleness has a real consequence (a price change, an order status, an access-control flag) — those need explicit invalidation or write-through.
</details>

---

## Lab 3: Production-Style — Reproduce and Fix a Cache Stampede

**Objective:** Actually trigger the exact stampede scenario described in the lesson ("5,000 requests per second, key expires, 1000 simultaneous identical DB queries") at a smaller reproducible scale, prove it hammers the DB, then fix it with the lock/single-flight pattern.

**Task:**
1. Start Postgres and Redis. Create a `products` table with one row, and add an artificial `pg_sleep(0.2)` into your "read from DB" function to simulate a slow query — this makes the stampede window big enough to observe reliably.
2. Write a naive `get_product(product_id)` using plain cache-aside with a short TTL (2 seconds) and NO stampede protection.
3. Add a counter (a simple Python `multiprocessing.Value` or just log lines with timestamps) inside the "read from DB" path so you can count how many times the DB is actually hit.
4. Let the cache populate once, then wait for the TTL to expire, and fire 50 concurrent requests at `get_product` in the same instant (`ThreadPoolExecutor` with 50 workers, or `ab -n 50 -c 50` against a small Flask wrapper). Record how many times the DB function actually ran — it should be close to 50, not 1.
5. Now implement the lock/single-flight version from the lesson (`cache.set(lock_key, "1", nx=True, ttl=10)`), repeat the same 50-concurrent-request test after TTL expiry, and confirm the DB function now runs close to ONCE, with the other 49 requests waiting briefly and reading the now-fresh cache.
6. Add TTL jitter (`ttl = base + random(0, base*0.1)`) and explain in 2-3 sentences why this matters for MANY hot keys expiring at once, not just one.

<details>
<summary>Solution / walkthrough</summary>

```sql
CREATE TABLE products (id INT PRIMARY KEY, name TEXT, price NUMERIC);
INSERT INTO products VALUES (1, 'Widget', 19.99);
```

```python
import time, redis, psycopg2, threading
from concurrent.futures import ThreadPoolExecutor

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
conn = psycopg2.connect(host="localhost", user="postgres", password="pass")
db_hit_count = 0
lock_count_lock = threading.Lock()

def read_from_db_slow(product_id):
    global db_hit_count
    with lock_count_lock:
        db_hit_count += 1
    with conn.cursor() as cur:
        cur.execute("SELECT pg_sleep(0.2), name, price FROM products WHERE id=%s", (product_id,))
        row = cur.fetchone()
    return {"id": product_id, "name": row[1], "price": float(row[2])}

# --- naive version, no stampede protection ---
def get_product_naive(product_id):
    cached = r.get(f"product:{product_id}")
    if cached:
        return cached
    data = read_from_db_slow(product_id)
    r.set(f"product:{product_id}", str(data), ex=2)
    return data
```

```python
# warm the cache, wait for expiry, then fire 50 concurrent requests
get_product_naive(1)
time.sleep(2.1)   # let the 2s TTL expire
db_hit_count = 0
with ThreadPoolExecutor(max_workers=50) as ex:
    list(ex.map(get_product_naive, [1]*50))
print(f"DB hits during stampede (naive): {db_hit_count}")
# DB hits during stampede (naive): 47   (or similarly close to 50 — nearly
# every one of the 50 requests missed the cache before the first DB read finished)
```

```python
# --- fixed version: lock / single-flight ---
def get_product_locked(product_id):
    cached = r.get(f"product:{product_id}")
    if cached:
        return cached
    lock_key = f"lock:product:{product_id}"
    if r.set(lock_key, "1", nx=True, ex=10):
        data = read_from_db_slow(product_id)
        r.set(f"product:{product_id}", str(data), ex=2)
        r.delete(lock_key)
        return data
    else:
        time.sleep(0.05)
        return get_product_locked(product_id)   # retry, most will now hit cache
```

```python
get_product_locked(1)
time.sleep(2.1)
db_hit_count = 0
with ThreadPoolExecutor(max_workers=50) as ex:
    list(ex.map(get_product_locked, [1]*50))
print(f"DB hits during stampede (locked): {db_hit_count}")
# DB hits during stampede (locked): 1   -- exactly the win the lesson promises:
# only the lock-winner reads the DB, everyone else waits briefly and reads cache
```

```python
import random
def ttl_with_jitter(base=60):
    return base + random.uniform(0, base * 0.1)
```

**Why jitter matters for many keys:** if 10,000 product pages are all cached with the exact same 60-second TTL because they were all populated by the same batch job or deploy, they ALL expire in the same one-second window — turning a single-key stampede into a fleet-wide one, all hitting the DB simultaneously. Jitter spreads those 10,000 expirations across a 6-second window instead of a 1-second spike, which is a much smaller, much more survivable load pattern even without per-key locking.
</details>

---

## Lab 4: Troubleshooting — Diagnose a "Cache Warm, DB Suddenly Overloaded" Incident

**Objective:** Given only symptoms (not a pre-labeled cause), diagnose which caching failure mode is happening — this mirrors how the problem actually shows up in an on-call rotation.

**Task:**
1. Set up the naive stampede scenario from Lab 3 but DON'T look at the code first — have a partner (or your past self, an hour later) run it against you blind, OR simulate this yourself by deliberately "forgetting" which version is active.
2. You're given only: a Grafana-style symptom description — "DB CPU spiked from 10% to 95% at exactly 14:32:00, lasting about 400ms, then dropped back to normal. App error rate briefly spiked. This has happened 3 times today, always for the same product page." Using ONLY `redis-cli` commands (no code reading), diagnose what's happening.
3. Check the TTL of the hot key with `TTL product:1` right when you'd expect it to be near expiry — correlate the pattern (spikes every ~60s if TTL=60) with the incident timestamps.
4. Propose and implement a fix using what you built in Lab 3, then verify with `MONITOR` (careful — noisy, use for a few seconds only, never in real production) that requests during the next expiry window now show cache hits instead of a burst of DB reads.

<details>
<summary>Solution / walkthrough</summary>

```bash
# Step 2-3: diagnose using only redis-cli, no code
redis-cli TTL product:1
# (integer) 58   -- run this a few times, watch it count down to 0 and cache
# repopulate — if incident timestamps line up with TTL resets, that's your signal

redis-cli --scan --pattern "product:*" | wc -l
# confirms this IS a cache-backed key, not some other subsystem

redis-cli CONFIG GET maxmemory-policy
# rules out an eviction-related cause (if this were noeviction and OOMing,
# that's a different diagnosis than a stampede)
```

Diagnosis: DB CPU spikes exactly periodically, same duration each time, same key implicated — classic cache stampede signature, not a capacity problem (capacity problems don't self-resolve in 400ms) and not a slow-query-creeping-up problem (those don't spike then vanish). Confirmed by `TTL` resetting to the same base value right after each incident.

```bash
# apply the Lab 3 lock-based fix in the app code, then verify live
redis-cli MONITOR
# in another terminal, wait for the TTL to expire naturally and watch traffic —
# you should see ONE "GET product:1" miss followed by a SET lock, then mostly
# "GET product:1" hits from other requests instead of a burst of DB-bound misses.
# Ctrl+C out of MONITOR quickly — it dumps every command Redis receives and
# is a real perf/security concern if left running.
```

Why this matters: this is precisely the failure mode the lesson's Senior Tip warns about — "cache expired and now the DB is getting the full uncached load it was never sized for, all at once." Being able to diagnose it from `redis-cli TTL` and pattern-matching against incident timestamps, without reading any application code, is a realistic on-call skill.
</details>

---

## Self-Check Checklist

- [ ] Can you explain why `noeviction` is a dangerous default for a pure-cache use case, and name the policy you'd actually use instead?
- [ ] Can you implement cache-aside, write-through, and explicit invalidation from memory, and state the tradeoff of each in one sentence?
- [ ] Can you explain consistent hashing well enough to say roughly what fraction of keys remap when a node is added to an N-node cluster?
- [ ] Can you describe a cache stampede in your own words and explain why it's dangerous specifically BECAUSE the cache is what protects the DB?
- [ ] Can you implement the lock/single-flight stampede mitigation pattern from memory (the `SET NX` + retry loop)?
- [ ] Can you explain what TTL jitter fixes that per-key locking alone does not (the many-keys-expiring-together case)?
- [ ] Given only `redis-cli` access (no app code), could you diagnose a periodic DB CPU spike as a likely cache stampede?
- [ ] Can you explain when you'd choose Memcached over Redis, and what capability you're explicitly giving up by doing so?
- [ ] Can you explain the difference between `allkeys-lru` and `volatile-lru`, and the gotcha where the latter can still OOM?
- [ ] Can you explain why "the cache is warm" and "the cache is correct" are two different claims, and give an example where the first is true but the second isn't?
