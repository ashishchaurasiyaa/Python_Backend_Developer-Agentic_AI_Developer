"""
Redis Lab 04 — Sliding Window Log Rate Limiter (ZADD/ZREMRANGEBYSCORE/ZCARD)
================================================================================
OBJECTIVE: khud likho ek exact sliding-window-log rate limiter — har request ka
timestamp ek sorted set me store hota hai, purani entries drop hoti hain, aur
limit se zyada requests reject hoti hain.

TASK:
  1. TODO 1: window se purani entries hatao (ZREMRANGEBYSCORE)
  2. TODO 2: current count check karo (ZCARD), limit se upar to reject
  3. TODO 3: allowed request ka timestamp ZSET me add karo (ZADD) + TTL
  4. Run: python 04_sliding_window_rate_limiter.py

Prereq: docker compose up -d   |   pip install "redis[hiredis]>=5.0"
"""

import time
import uuid
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

KEY = "lab:ratelimit:sliding:user1"
LIMIT = 5
WINDOW_SECONDS = 3


def allow_request(now: float = None) -> bool:
    """
    Sliding-window-log: sirf window ke andar wale timestamps count hote hain.
    Boundary burst nahi hota (fixed-window ke unlike) kyunki koi bucket
    boundary nahi hai — window hamesha "ab se WINDOW_SECONDS pehle" tak hota hai.
    """
    now = now if now is not None else time.time()

    # ─────────────────────────────────────────────────────
    # TODO 1: window se purani entries hatao — score range
    #         0 se (now - WINDOW_SECONDS) tak sab remove karo.
    #         Hint: r.zremrangebyscore(KEY, 0, now - WINDOW_SECONDS)
    # ─────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────
    # TODO 2: current window me kitni entries hain count karo.
    #         Agar count >= LIMIT hai to False return karo (reject).
    #         Hint: count = r.zcard(KEY)
    # ─────────────────────────────────────────────────────
    count = None
    if count is None:
        print("❌ TODO 1/2 abhi bharna hai")
        return False
    if count >= LIMIT:
        return False

    # ─────────────────────────────────────────────────────
    # TODO 3: is request ko allow karo — ZSET me unique member
    #         add karo (score=now, member must be unique per
    #         request — timestamp akela dedup ho sakta hai agar
    #         2 requests same ms pe aayein, isliye uuid jodo),
    #         phir key pe TTL set karo (WINDOW_SECONDS).
    #         Hint: r.zadd(KEY, {f"{now}:{uuid.uuid4()}": now})
    #               r.expire(KEY, WINDOW_SECONDS)
    # ─────────────────────────────────────────────────────

    return True


def main() -> None:
    r.delete(KEY)

    print(f"\n[1] Firing a burst of {LIMIT + 5} requests within the "
          f"{WINDOW_SECONDS}s window (limit={LIMIT})...")
    allowed_count = 0
    rejected_count = 0
    for i in range(LIMIT + 5):
        ok = allow_request()
        status = "✅ allowed" if ok else "⚠️  rejected"
        print(f"   request {i + 1}: {status}")
        if ok:
            allowed_count += 1
        else:
            rejected_count += 1

    print(f"\n  → {allowed_count} allowed, {rejected_count} rejected "
          f"(out of {LIMIT + 5} fired)")

    burst_ok = allowed_count == LIMIT and rejected_count == 5

    print(f"\n[2] Waiting {WINDOW_SECONDS + 1}s for the window to fully slide past...")
    time.sleep(WINDOW_SECONDS + 1)

    print("[3] Firing one more request — should be allowed again...")
    post_window_ok = allow_request()
    print(f"   → {'✅ allowed' if post_window_ok else '⚠️  rejected'}")

    print("\n" + "─" * 55)
    if burst_ok and post_window_ok:
        print(f"✅ PASS — exactly {LIMIT}/{LIMIT + 5} allowed during the burst, "
              "and a fresh request after the window slid past was allowed again.")
    else:
        print(f"❌ FAIL — burst allowed={allowed_count} (expected {LIMIT}), "
              f"rejected={rejected_count} (expected 5), "
              f"post_window_allowed={post_window_ok} (expected True)")
        if allowed_count != LIMIT:
            print("   TODO 2 check karo — count/limit comparison galat ho sakta hai.")
        if not post_window_ok:
            print("   TODO 1 check karo — purani entries ZREMRANGEBYSCORE se")
            print("   hat nahi rahi, isliye window 'slide' nahi ho raha.")

    r.delete(KEY)

    print("""
SOCH (bolke jawab do):
  1. Sliding-window-log ka memory cost kya hai (relative to fixed-window
     counter)? Har request ek ZSET entry — high-traffic user ke liye yeh
     kitna scale karega?
  2. ZREMRANGEBYSCORE + ZCARD + ZADD teen alag round-trips hain — inke beech
     koi doosra client interleave ho sakta hai kya? Isko atomic kaise
     banaoge (Hint: Lua script, jaisa 08_lua_scripting.md me TOKEN_BUCKET)?
  3. Fixed-window counter (INCR + EXPIRE) ka boundary-burst problem yeh
     design kaise solve karta hai? (practical/15_rate_limiting.py ka
     demo_fixed se compare karo)
""")


if __name__ == "__main__":
    main()
