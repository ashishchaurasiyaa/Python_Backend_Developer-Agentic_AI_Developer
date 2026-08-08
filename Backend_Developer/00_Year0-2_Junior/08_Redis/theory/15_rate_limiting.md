# Redis Rate Limiting — Algorithm Comparison

## Why It Matters (Senior 5 YOE Context)

"Design a rate limiter" is one of the most common Redis system-design
interview questions — not because it's hard to make SOMETHING that works,
but because there are 4-5 well-known algorithms with real tradeoffs, and
the interviewer is testing whether you know the tradeoffs, not just whether
you can `INCR` a counter.

You already have the Lua-atomic **token bucket** implementation in
`08_lua_scripting.md` (Real-World Use Cases → 1) — that doc shows HOW to
make it atomic. This doc is the missing piece: WHICH algorithm to reach
for, and why. Senior interview framing: "Naive rate limiter with `INCR` +
`EXPIRE` — what's wrong with it?" → boundary burst problem (2x traffic
possible right at a window edge). "How do you fix it without doubling your
memory cost?" → sliding window counter (weighted approximation), not the
full sliding window log.

---

## Core Concepts

### 1. Fixed Window Counter

Simplest possible implementation — one counter per time bucket.

```python
def is_allowed(user_id, limit=100, window_seconds=60):
    now = int(time.time())
    bucket = now // window_seconds
    key = f"ratelimit:{user_id}:{bucket}"

    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)   # only set TTL on first request in bucket

    return count <= limit
```

```bash
INCR ratelimit:user:123:29341200      # -> 1
EXPIRE ratelimit:user:123:29341200 60
```

**The boundary burst problem:** window `[0s, 60s)` allows 100 requests.
Client sends 100 requests at `t=59s` (all land in window 1, all allowed),
then 100 more at `t=61s` (new bucket, counter reset, all allowed again).
Result: 200 requests in a 2-second span, against a "100 requests/minute"
limit. The fixed window has NO memory of the previous window — this is
the #1 thing interviewers want you to name.

### 2. Sliding Window Log

Store every request's timestamp in a sorted set. Precise — no boundary
burst — because the "window" is always exactly `[now - window, now]`,
recomputed on every request.

```python
def is_allowed(user_id, limit=100, window_seconds=60):
    key = f"ratelimit:log:{user_id}"
    now = time.time()

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)   # drop entries outside window
    pipe.zcard(key)                                        # count what's left
    pipe.zadd(key, {str(uuid.uuid4()): now})                # tentatively log this request
    pipe.expire(key, window_seconds)
    _, count, _, _ = pipe.execute()

    if count >= limit:
        r.zrem(key, ...)   # roll back the entry we just added — see pitfall #1 below
        return False
    return True
```

Exact and correct, but **one sorted-set entry per request** — for
10,000 req/sec at a 60s window that's up to 600,000 entries in memory per
key. This is the "precise but expensive" option — mention it, but the
sliding window counter below is what production systems actually use.

### 3. Sliding Window Counter (Weighted Approximation)

Keep TWO fixed-window counters (current + previous) and take a weighted
average based on how far into the current window you are. Same cost as
fixed window (2 `INCR`s worth of state), no boundary-burst problem.

```python
def is_allowed(user_id, limit=100, window_seconds=60):
    now = time.time()
    current_bucket = int(now // window_seconds)
    previous_bucket = current_bucket - 1
    elapsed_in_current = now - (current_bucket * window_seconds)
    weight_previous = (window_seconds - elapsed_in_current) / window_seconds

    curr_key = f"ratelimit:sw:{user_id}:{current_bucket}"
    prev_key = f"ratelimit:sw:{user_id}:{previous_bucket}"

    prev_count = int(r.get(prev_key) or 0)
    curr_count = int(r.get(curr_key) or 0)

    weighted_count = curr_count + prev_count * weight_previous

    if weighted_count >= limit:
        return False

    pipe = r.pipeline()
    pipe.incr(curr_key)
    pipe.expire(curr_key, window_seconds * 2)   # keep around long enough to be "previous" next window
    pipe.execute()
    return True
```

Example: window = 60s, limit = 100. At `t = 15s` into the current window,
75% of the previous window still "counts": `weighted_count = curr_count +
prev_count * 0.75`. As the current window fills up, the previous window's
influence smoothly decays to zero — no hard edge, no 2x burst. This is an
**approximation** (assumes uniform request distribution within the
previous window), but it's the standard production answer because it's
cheap (O(1) memory per user, just two integers) and close enough.

### 4. Token Bucket (reference — full impl in `08_lua_scripting.md`)

Conceptually different from the two window algorithms above: instead of
counting requests in a time bucket, you have a bucket with **capacity N
tokens** that **refills at a fixed rate** (e.g. 10 tokens/sec). Every
request consumes 1 token (or more, for weighted costs); if the bucket is
empty, reject.

```
Bucket capacity: 10 tokens, refill rate: 2 tokens/sec

t=0:  bucket full (10 tokens) → burst of 10 requests all allowed instantly
t=0:  bucket now at 0
t=1:  bucket refilled to 2 → 2 more requests allowed
t=5:  bucket refilled to 10 (capped at capacity) → another burst of 10 allowed
```

**This is the key differentiator vs. window counters:** token bucket
explicitly ALLOWS controlled bursting up to bucket capacity, as long as
the bucket has accumulated tokens (i.e., client was under the rate
recently). Window counters treat every window uniformly — no concept of
"saved up" capacity. See `08_lua_scripting.md` → Real-World Use Cases → 1
for the full atomic Lua implementation (`HMGET`/refill-math/`HMSET`
pattern) — not re-derived here since it's already covered there.

### 5. Leaky Bucket

The mirror image of token bucket. Requests arrive into a FIFO queue
(the "bucket") and are processed (leak out) at a **constant fixed rate**,
regardless of how bursty the arrivals were. If the queue is full, new
requests are dropped/rejected.

```
Leaky bucket: capacity 20, leak rate 5/sec (processed one every 200ms)

20 requests arrive simultaneously → all queued (bucket full)
21st request arrives → REJECTED (bucket at capacity)
Queue drains at exactly 5/sec, no matter how many more arrive after
```

Contrast with token bucket: token bucket lets a burst of requests through
to the backend immediately (as long as tokens are available) — it smooths
the RATE OF PERMISSION. Leaky bucket smooths the RATE OF PROCESSING —
output is always metronomic, even if input was bursty. Token bucket is
what you reach for at an API gateway (let bursts through, backend can
handle them). Leaky bucket is what you reach for when the downstream
consumer genuinely cannot handle bursts at all (e.g. a fixed-capacity
worker pool, a third-party API with a hard per-second cap) — it's Redis
Streams / a queue + a worker consuming at fixed pace, conceptually, more
than a pure counter pattern.

---

## How It Works Internally

### The Comparison Table (the actual interview answer)

| Algorithm | Memory Cost | Burst Handling | Precision | Implementation Complexity |
|---|---|---|---|---|
| **Fixed window counter** | O(1) per user — one counter | Allows 2x limit at window boundary | Low — boundary artifact | Trivial — `INCR` + `EXPIRE` |
| **Sliding window log** | O(N) per user — one entry per request in window | No burst artifact — exact | Exact/perfect | Medium — sorted set + `ZREMRANGEBYSCORE`/`ZCARD` |
| **Sliding window counter** | O(1) per user — two counters | Small residual imprecision, no hard boundary | Approximate (assumes uniform distribution) | Medium — weighted-average math |
| **Token bucket** | O(1) per user — tokens + last-refill timestamp | Explicitly ALLOWS bursts up to capacity | Exact for its own model | Medium-high — needs atomic refill math (Lua) |
| **Leaky bucket** | O(1) to O(queue size) | Explicitly SMOOTHS/disallows bursts — constant output rate | Exact for its own model | Medium-high — needs a queue + constant-rate worker |

**One-line answer to memorize:** "Fixed window is cheap but bursts at the
edge. Sliding window log is exact but memory-heavy. Sliding window counter
gets you 95% of the precision of the log at the memory cost of the fixed
window — that's the production default. Token bucket and leaky bucket
aren't really about the window at all — they control burst SHAPE: token
bucket allows saved-up bursts, leaky bucket forces a constant output rate."

### Why Atomicity Matters

Every one of these algorithms is a **read-check-write** sequence:
read current count/tokens → check against limit → write incremented
value. Under concurrency, two requests from the same client can both read
the count BEFORE either writes — both see `count = 99` (under the limit
of 100), both proceed, and the real count ends up at 101. This is the
exact race condition class covered in `13_transactions_watch.md`
(optimistic locking via `WATCH`/`MULTI`/`EXEC`) and `08_lua_scripting.md`
(server-side atomic scripts).

- `INCR` alone is atomic (single command) — this is why the fixed window
  counter is naturally race-free for the counting step itself.
- `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD` as separate calls are NOT atomic
  together — two concurrent requests can both pass the `ZCARD` check
  before either's `ZADD` lands, letting both through over the limit. Wrap
  in a Lua script (`EVAL`) or pipeline them inside `MULTI`/`EXEC` with a
  `WATCH` on the key for true atomicity.
- Token bucket's refill-then-consume math is inherently multi-step (GET
  tokens, compute refill, compare, SET) — this is why the reference
  implementation in `08_lua_scripting.md` is a Lua script, not raw Python
  calls. Without Lua, this is the textbook GET-then-SET race.

---

## Common Pitfalls

### 1. Non-Atomic Check-Then-Act Race

```python
# WRONG — two concurrent requests can both read count=99 before either INCRs
count = int(r.get(key) or 0)
if count < limit:
    r.incr(key)
    allow_request()
```

Under load, this lets requests slip through over the limit — the classic
TOCTOU (time-of-check-to-time-of-use) bug. Fix: use `INCR` itself as the
atomic check (it returns the NEW value, so check the return value, don't
pre-read), or wrap multi-step logic (sliding window log, token bucket) in
a Lua script.

### 2. Clock Skew Across App Servers

```python
# WRONG — each app server's local clock may drift
now = time.time()
r.zadd(key, {req_id: now})
```

If timestamps are generated client-side (in the app process) rather than
by Redis itself, and you have multiple app servers behind a load balancer
with even a few hundred ms of clock drift between them, the sliding
window log/counter's boundaries become inconsistent — a request "in the
past" from one server's clock could be "in the future" relative to
another's. Fix: use `redis.call('TIME')` inside a Lua script (Redis's own
clock, single source of truth) instead of trusting each app server's
`time.time()`.

### 3. Wrong Key Granularity (per-user vs per-endpoint vs global)

```python
# Too coarse — one shared limit for ALL users hitting ANY endpoint
key = "ratelimit:global"

# Usually right — isolate by identity AND resource
key = f"ratelimit:{user_id}:{endpoint}"

# For unauthenticated traffic — fall back to IP
key = f"ratelimit:ip:{client_ip}:{endpoint}"
```

Picking the key design IS the rate-limiting design decision — per-user
protects fairness between users, per-endpoint protects a specific
expensive resource (e.g. search, export) independent of a user's overall
quota, global protects the whole system from aggregate overload. Most
production systems layer 2-3 of these simultaneously.

### 4. Forgetting `EXPIRE` — Rate-Limit Keys Leak Forever

```python
# WRONG — key never expires, memory grows unbounded across all users/buckets
r.incr(f"ratelimit:{user_id}:{bucket}")
```

Every algorithm above needs a TTL on its Redis key(s) — otherwise you
accumulate one key per user per time-bucket FOREVER (fixed/sliding window
counters) or an ever-growing sorted set (sliding window log). Always pair
the write with `EXPIRE`/`PEXPIRE` sized to the window (or slightly more,
for the sliding window counter which needs the "previous" bucket to
survive one extra window). This is the same gotcha called out in
`08_lua_scripting.md` Common Pitfalls #4.

---

## Interview Q&A

**Q: Naive `INCR` + `EXPIRE` rate limiter — what's the concrete failure mode?**
A: Boundary burst. A "100 req/min" limit backed by a fixed window can let
through up to 200 requests in a short span if the burst straddles the
window edge — e.g. 100 requests at `t=59s` (end of window 1) plus 100 more
at `t=61s` (start of window 2). The counter resets at the boundary with no
memory of the previous window's traffic.

**Q: How do you fix the boundary burst problem without the memory cost of storing every request timestamp?**
A: Sliding window counter — keep the current AND previous fixed-window
counts, and compute a weighted average based on how far into the current
window "now" is. It approximates a true sliding window (assumes fairly
uniform request distribution within a window) at O(1) memory per user,
versus the sliding window log's O(N) — one sorted-set entry per request.

**Q: When would you pick token bucket over a sliding window counter?**
A: When you WANT to allow controlled bursts — e.g. a client that's been
idle should be able to send a burst of requests up to the bucket capacity
without being throttled, then get rate-limited back down to the steady
refill rate. Window counters (sliding or fixed) treat all traffic
uniformly within a window and don't have this "saved up capacity" concept.
Token bucket is the standard choice for API gateway per-key limits where
bursty-but-bounded client behavior is expected and fine.

**Q: Token bucket vs leaky bucket — what's actually different?**
A: Token bucket controls the rate of PERMISSION — it lets bursts through
to the backend as long as tokens are banked. Leaky bucket controls the
rate of PROCESSING — requests queue up and drain at a strictly constant
rate no matter how bursty the arrivals were, so the backend never sees a
burst at all. Token bucket assumes the backend can absorb occasional
bursts; leaky bucket assumes it categorically cannot.

**Q: Why does the sliding window log's `ZADD`/`ZREMRANGEBYSCORE`/`ZCARD` sequence need to be atomic, and how do you make it so?**
A: Each is a separate round-trip; under concurrent requests from the same
client, two requests can both `ZCARD` and see a count under the limit
before either's `ZADD` commits, letting both through over the limit — the
same class of race as any check-then-act pattern. Fix with a Lua script
(single atomic `EVAL`, as shown in `08_lua_scripting.md`'s sliding-window
rate limiter) or `WATCH`/`MULTI`/`EXEC` optimistic locking on the key.

---

## Real-World Use Cases

### 1. API Gateway — Per-API-Key Rate Limiting

```python
def gateway_allow(api_key, tier="free"):
    limits = {"free": (60, 60), "pro": (1000, 60)}   # (limit, window_seconds)
    limit, window = limits.get(tier, limits["free"])
    return sliding_window_counter_allow(f"gw:{api_key}", limit, window)
```

Token bucket is the more common real-world choice here specifically
because API clients are naturally bursty (a script fires 10 requests in a
tight loop, then goes quiet) — a sliding window counter would throttle
that burst even though the client's average rate is well within budget.

### 2. Login-Attempt Throttling (Brute-Force Protection)

```python
def login_attempt_allowed(username_or_ip):
    # Tight limit, longer window, per-identity AND per-IP simultaneously —
    # defends both "one attacker hammering one account" and "one attacker
    # spraying many accounts from one IP"
    return (
        fixed_window_allow(f"loginattempt:user:{username_or_ip}", limit=5, window_seconds=300)
        and fixed_window_allow(f"loginattempt:ip:{get_client_ip()}", limit=20, window_seconds=300)
    )
```

Fixed window is often good enough here — the goal is coarse throttling to
slow down brute force, not precise fairness, and the boundary-burst
weakness (letting a short extra burst through) matters far less than it
would for a paid-tier API quota.

---

## References

- [Redis Rate Limiting Patterns](https://redis.io/glossary/rate-limiting/)
- [System Design Primer — Rate Limiting](https://github.com/donnemartin/system-design-primer)
- `08_lua_scripting.md` — atomic token bucket + sliding window log Lua implementations
- `13_transactions_watch.md` — `WATCH`/`MULTI`/`EXEC` optimistic locking, the non-Lua alternative to atomic check-and-increment
