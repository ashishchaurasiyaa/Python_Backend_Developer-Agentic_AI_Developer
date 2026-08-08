"""
Redis Practical 15 — Rate Limiting Algorithm Comparison
Run: python 15_rate_limiting.py [fixed|log|counter|burst|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine

Covers: fixed window counter, sliding window log (ZADD/ZREMRANGEBYSCORE/ZCARD),
sliding window counter (weighted approximation), and a side-by-side burst
simulation showing the boundary-burst problem concretely.

Token bucket ka full atomic Lua implementation already `08_lua_scripting.py`
me hai (TOKEN_BUCKET script) — yahan repeat nahi kar rahe, sirf reference.
"""

import sys
import time
import uuid
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


def _cleanup(pattern):
    """DEL ke saath koi arg na ho to Redis error deta hai — empty match guard karo."""
    keys = r.keys(pattern)
    if keys:
        r.delete(*keys)


# ════════════════════════════════════════════
# SECTION 1: FIXED WINDOW COUNTER
# ════════════════════════════════════════════
def fixed_window_allow(key_prefix, user_id, limit=5, window_seconds=10, now=None):
    """
    Simplest rate limiter — INCR ek counter per time-bucket, EXPIRE laga do.
    INCR khud atomic hai, isliye counting step race-free hai.
    Problem: window boundary pe 2x burst allowed ho sakta hai (see demo_fixed).
    """
    now = now if now is not None else time.time()
    bucket = int(now // window_seconds)
    key = f"{key_prefix}:{user_id}:{bucket}"

    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)   # sirf pehli request pe TTL set karo

    return count <= limit


def demo_fixed():
    print("\n" + "=" * 50)
    print("  SECTION 1: FIXED WINDOW COUNTER")
    print("=" * 50)

    user = "fixed_demo_user"
    limit, window = 5, 10
    _cleanup(f"ratelimit:fixed:{user}:*")

    print(f"📊 Limit: {limit} req / {window}s window")
    for i in range(limit + 2):
        allowed = fixed_window_allow("ratelimit:fixed", user, limit, window)
        status = "✅ allowed" if allowed else "⚠️  REJECTED (over limit)"
        print(f"   request {i + 1}: {status}")

    print("\n   BOUNDARY BURST DEMO — requests straddling a window edge:")
    # ─── Simulate window edge: 5 requests just before boundary, 5 just after ───
    _cleanup(f"ratelimit:fixed:{user}_edge:*")
    edge_user = f"{user}_edge"
    base = 1000000.0   # arbitrary epoch-like base, bucket = base // window
    just_before = base - 0.5   # still in bucket N
    just_after = base + 0.5    # bucket N+1

    allowed_before = sum(
        fixed_window_allow("ratelimit:fixed", edge_user, limit, window, now=just_before)
        for _ in range(limit)
    )
    allowed_after = sum(
        fixed_window_allow("ratelimit:fixed", edge_user, limit, window, now=just_after)
        for _ in range(limit)
    )
    total = allowed_before + allowed_after
    print(f"   {allowed_before}/{limit} allowed just BEFORE boundary,"
          f" {allowed_after}/{limit} allowed just AFTER boundary")
    print(f"   → {total} requests allowed within ~1 second, against a"
          f" '{limit} per {window}s' limit!")
    print("   Yehi hai fixed window ka boundary burst problem — up to 2x limit.")


# ════════════════════════════════════════════
# SECTION 2: SLIDING WINDOW LOG (ZADD / ZREMRANGEBYSCORE / ZCARD)
# ════════════════════════════════════════════
def sliding_log_allow(key_prefix, user_id, limit=5, window_seconds=10, now=None):
    """
    Har request ka exact timestamp sorted set me store karo (score = timestamp).
    Precise — no boundary artifact — but O(N) memory: ek entry per request
    jo abhi window ke andar hai.

    NOTE: real production code me yeh Lua script me wrap karo (ZADD +
    ZREMRANGEBYSCORE + ZCARD teen alag round-trips hain, atomic nahi —
    see theory doc "Common Pitfalls #1" aur 08_lua_scripting.md).
    """
    now = now if now is not None else time.time()
    key = f"{key_prefix}:{user_id}"

    r.zremrangebyscore(key, 0, now - window_seconds)   # purani entries hatao
    count = r.zcard(key)

    if count >= limit:
        return False

    r.zadd(key, {f"{now}:{uuid.uuid4()}": now})
    r.expire(key, window_seconds)
    return True


def demo_log():
    print("\n" + "=" * 50)
    print("  SECTION 2: SLIDING WINDOW LOG")
    print("=" * 50)

    user = "log_demo_user"
    limit, window = 5, 10
    key = f"ratelimit:log:{user}"
    r.delete(key)

    print(f"📊 Limit: {limit} req / {window}s window (exact, ZSET-backed)")
    for i in range(limit + 2):
        allowed = sliding_log_allow("ratelimit:log", user, limit, window)
        status = "✅ allowed" if allowed else "⚠️  REJECTED (over limit)"
        print(f"   request {i + 1}: {status}  (ZCARD now = {r.zcard(key)})")

    print(f"\n   💾 Memory: {r.zcard(key)} sorted-set entries for this user"
          " — one per request in the window.")
    print("   Precise, no boundary burst — but scales linearly with request rate.")


# ════════════════════════════════════════════
# SECTION 3: SLIDING WINDOW COUNTER (weighted approximation)
# ════════════════════════════════════════════
def sliding_counter_allow(key_prefix, user_id, limit=5, window_seconds=10, now=None):
    """
    Current + previous fixed-window counters ka weighted average.
    O(1) memory (do integers), boundary burst nahi — approximation hai
    (assumes uniform distribution within previous window) lekin production
    me yeh sabse common choice hai — cheap AND close to exact.
    """
    now = now if now is not None else time.time()
    current_bucket = int(now // window_seconds)
    previous_bucket = current_bucket - 1
    elapsed_in_current = now - (current_bucket * window_seconds)
    weight_previous = (window_seconds - elapsed_in_current) / window_seconds

    curr_key = f"{key_prefix}:{user_id}:{current_bucket}"
    prev_key = f"{key_prefix}:{user_id}:{previous_bucket}"

    prev_count = int(r.get(prev_key) or 0)
    curr_count = int(r.get(curr_key) or 0)
    weighted_count = curr_count + prev_count * weight_previous

    if weighted_count >= limit:
        return False

    pipe = r.pipeline()
    pipe.incr(curr_key)
    pipe.expire(curr_key, window_seconds * 2)   # agle window me "previous" ban ke zinda rahe
    pipe.execute()
    return True


def demo_counter():
    print("\n" + "=" * 50)
    print("  SECTION 3: SLIDING WINDOW COUNTER (weighted approximation)")
    print("=" * 50)

    user = "counter_demo_user"
    limit, window = 5, 10
    _cleanup(f"ratelimit:swc:{user}:*")

    print(f"📊 Limit: {limit} req / {window}s window (O(1) memory, weighted avg)")
    for i in range(limit + 2):
        allowed = sliding_counter_allow("ratelimit:swc", user, limit, window)
        status = "✅ allowed" if allowed else "⚠️  REJECTED (over limit)"
        print(f"   request {i + 1}: {status}")

    print("\n   💾 Memory: just 2 integer keys (current + previous bucket)"
          " regardless of request volume.")
    print("   Approximate, but no hard boundary edge like fixed window.")


# ════════════════════════════════════════════
# SECTION 4: BURST SIMULATION — all three side by side
# ════════════════════════════════════════════
def demo_burst():
    print("\n" + "=" * 50)
    print("  SECTION 4: BOUNDARY-BURST COMPARISON (fixed vs log vs counter)")
    print("=" * 50)

    limit, window = 10, 10   # 10 req / 10s
    base = 2_000_000.0       # arbitrary bucket-aligned epoch base
    # ─── Same simulated timestamp sequence for all 3 algorithms:
    #     10 requests just before the window boundary, 10 more just after ───
    timestamps = [base - 0.9 + i * 0.1 for i in range(10)] + \
                 [base + 0.1 + i * 0.1 for i in range(10)]

    algos = {
        "Fixed window   ": ("ratelimit:cmp:fixed", fixed_window_allow),
        "Sliding log    ": ("ratelimit:cmp:log", sliding_log_allow),
        "Sliding counter": ("ratelimit:cmp:swc", sliding_counter_allow),
    }

    print(f"📊 Simulating {len(timestamps)} requests straddling a window edge"
          f" (limit={limit}/{window}s)\n")

    for label, (prefix, fn) in algos.items():
        user = "burst_user"
        _cleanup(f"{prefix}:{user}*")

        allowed_count = 0
        for ts in timestamps:
            if fn(prefix, user, limit, window, now=ts):
                allowed_count += 1

        overshoot = allowed_count - limit
        flag = f"⚠️  {overshoot} OVER limit" if overshoot > 0 else "✅ within limit"
        print(f"   {label} → {allowed_count}/{len(timestamps)} requests allowed  ({flag})")

    print("\n   📌 Fixed window lets the full 2x burst through at the edge.")
    print("   📌 Sliding log stays exact — never exceeds the true limit.")
    print("   📌 Sliding counter stays close to the log — small approximation,")
    print("      NOT the full 2x burst — at a fraction of the log's memory cost.")
    print("\n   Token bucket / leaky bucket not shown here — they don't use")
    print("   fixed calendar windows at all (see theory/15_rate_limiting.md +")
    print("   08_lua_scripting.py TOKEN_BUCKET for the atomic Lua version).")


if __name__ == "__main__":
    sections = {
        "fixed": demo_fixed,
        "log": demo_log,
        "counter": demo_counter,
        "burst": demo_burst,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 15_rate_limiting.py [{'|'.join(sections)}|all]")
