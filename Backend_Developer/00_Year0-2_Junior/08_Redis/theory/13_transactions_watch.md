# Redis Transactions — MULTI/EXEC/WATCH/DISCARD

## Why It Matters (Senior 5 YOE Context)

You've already seen `MULTI/EXEC` mentioned in passing in
`02_pipeline_connection_pool.md` (Q5 — pipeline vs transaction) as "ya dono
execute honge ya koi nahi" (either both run or neither). That's a useful
mental model for queuing behavior, but it's NOT the full truth about
runtime errors — and that gap is exactly where interviewers like to poke.
This doc gives transactions the full treatment: what atomicity actually
means in Redis, how `WATCH` gives you optimistic locking without a lock,
and where transactions stop being enough and you reach for Lua instead.

Senior interview: "Redis MULTI/EXEC — is it like a SQL transaction?" →
No. It's atomic in the sense that no other client's commands can be
interleaved between your queued commands during EXEC, but it does NOT do
rollback. If command 3 of 5 throws a runtime error (wrong type, etc.),
commands 1, 2, 4, and 5 still execute. That single fact trips up almost
everyone who assumes "transaction" means what it means in Postgres.

---

## Core Concepts

### MULTI/EXEC — queue then fire

```
MULTI                  → start queuing commands (client-side flag on the connection)
SET a 1                → queued, NOT executed yet (returns "QUEUED")
INCR b                 → queued
EXEC                   → Redis executes the ENTIRE queue as one atomic block
                          → no other client's command can be interleaved
                          → returns an array of results, one per queued command
```

```bash
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET a 1
QUEUED
127.0.0.1:6379> INCR b
QUEUED
127.0.0.1:6379> EXEC
1) OK
2) (integer) 1
```

Atomicity here means **isolation from other clients**, not **rollback on
failure**. Redis is single-threaded for command execution, so once EXEC
starts, no other client's command can slip in between your queued commands
— that part IS a real guarantee, and it's the main reason to reach for
MULTI/EXEC at all (read-modify-write without another client racing you in
the middle).

### Two failure modes — queue-time vs runtime

This distinction is the crux of the whole topic:

```python
# ─── Failure #1: QUEUE-TIME error (bad syntax) — ABORTS the whole transaction ───
r.execute_command("MULTI")
r.execute_command("NOTACOMMAND")   # Redis rejects this AT QUEUE TIME
r.execute_command("SET", "a", "1")
r.execute_command("EXEC")
# EXEC fails entirely with "EXECABORT" — NEITHER command runs.
# Redis caught the bad command while queuing, flags the whole transaction dirty.

# ─── Failure #2: RUNTIME error (wrong type) — does NOT abort the others ───
r.set("mystring", "hello")
pipe = r.pipeline(transaction=True)
pipe.set("a", "1")
pipe.lpush("mystring", "x")   # will fail at EXEC — mystring is a STRING not a LIST
pipe.set("b", "2")
results = pipe.execute()
# a IS set, b IS set. Only the LPUSH command itself errors.
# results = [True, WRONGTYPE error object, True]
# THIS is the part people get wrong assuming SQL-style rollback.
```

Queue-time errors (unknown command, wrong arity) are caught before EXEC
even runs and abort everything (`EXECABORT`). Runtime errors (wrong type,
out-of-range value) are only discovered while executing each command
inside EXEC, and Redis does NOT stop the batch or undo earlier commands —
it just records the error for that one command's slot in the results array
and moves to the next queued command.

### DISCARD — abandon a queued transaction

```bash
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET a 1
QUEUED
127.0.0.1:6379> DISCARD
OK
# Queue thrown away, connection back to normal mode, SET a 1 never ran.
```

Useful when your application logic decides mid-way (before EXEC) that the
transaction shouldn't proceed — e.g. a `WATCH`ed precondition already looks
wrong, or app-level validation fails after some commands were queued.

### WATCH — optimistic locking (compare-and-swap)

Redis has no `LOCK key` primitive for this — instead it gives you
**optimistic concurrency control**. You watch a key, read it, decide what
you want to write based on what you read, then try to commit atomically.
If ANYONE changed the watched key between your `WATCH` and your `EXEC`,
Redis aborts your transaction (EXEC returns `nil`) and you retry the whole
read-modify-write loop.

```
1. WATCH balance:user:1              # "tell me if this key changes"
2. GET balance:user:1                # read current value → decide new value
3. MULTI
4. SET balance:user:1 <new_value>    # queue the write
5. EXEC                              # atomically: check if watched key changed
                                      #   - unchanged → commit, return results
                                      #   - changed by ANYONE since WATCH → abort, return nil
6. If nil → UNWATCH (auto after EXEC anyway) → retry from step 1
```

```bash
# Client A                          # Client B (races in between)
WATCH balance:user:1
GET balance:user:1        # → "100"
                                     SET balance:user:1 90   # concurrent write!
MULTI
SET balance:user:1 110    # queued (A thinks balance is still 100)
EXEC                      # → nil — ABORTED, because B changed the watched key
# Client A must retry: WATCH again, re-read (now sees 90), recompute, EXEC again
```

This is the classic **CAS (compare-and-swap) retry loop** — same pattern
as `AtomicInteger.compareAndSet()` in Java or a version-column optimistic
lock in SQL, just expressed with Redis primitives.

---

## How It Works Internally

- `MULTI` sets a flag on the **client connection** — every subsequent
  command from that connection is queued (buffered server-side), not
  executed, until `EXEC` or `DISCARD`.
- `WATCH key1 key2 ...` registers the connection as a watcher on those
  keys. Internally Redis just needs to know "has this key been touched
  since watch started" — it does NOT snapshot the value, it tracks
  modification, so any write (even `SET key <same value>`) counts as a
  change and busts the watch.
- Any command that MODIFIES a watched key — from any client, including a
  key expiring — flags the watch as "dirty." This includes the watching
  client's own writes if done outside the MULTI block, and includes a TTL
  expiry event.
- On `EXEC`, Redis checks: is any watched key dirty? If yes → skip running
  the queue entirely, return `nil` (redis-py: `execute()` raises
  `WatchError` when using the high-level `pipeline()` API, or the queue
  simply isn't executed with raw commands). If no → execute the queued
  commands atomically (single-threaded, no other command interleaves).
- `WATCH` state is cleared automatically after `EXEC`, `DISCARD`, or the
  connection closing. `UNWATCH` clears it manually without running/discarding
  a transaction.
- Because this is single-threaded execution, "atomic" for Redis really
  means "no other command can execute in between your queued commands" —
  there's no separate transaction log, no undo/rollback machinery, because
  there's nothing to protect against concurrent modification mid-execution
  (nothing else can run mid-execution in the first place).

---

## Transactions vs Pipelining

Pipelining and transactions solve DIFFERENT problems and people conflate
them because redis-py's `pipeline()` object does both:

| | **Pipelining (`transaction=False`)** | **Transaction (`transaction=True` / MULTI-EXEC)** |
|---|---|---|
| What it does | Batches N commands into 1 round trip | Batches N commands into 1 round trip **AND** wraps them in MULTI/EXEC |
| Atomicity / isolation | None — another client's command CAN interleave between yours | Yes — no other client's command can run between your queued commands |
| Purpose | Reduce network round-trip latency | Guarantee isolation for read-modify-write logic |
| Failure behavior | Each command independent, no queuing semantics | Queue-time error aborts all; runtime error only affects that command |
| Use when | Bulk insert, warm a cache, read many unrelated keys — speed only | Multiple writes must be seen as one unit (transfer, counter+cap) |

```python
# Pipelining only — fast, but B could see a write from another client
# land between pipe.set("a") and pipe.set("b") from a DIFFERENT connection
pipe = r.pipeline(transaction=False)
pipe.set("a", 1)
pipe.set("b", 2)
pipe.execute()

# Transaction — same 1 round trip, PLUS isolation guarantee
pipe = r.pipeline(transaction=True)   # this is just MULTI/EXEC under the hood
pipe.set("a", 1)
pipe.set("b", 2)
pipe.execute()
```

The one-line answer: pipelining is purely a network optimization (fewer
round trips); MULTI/EXEC is a correctness/isolation guarantee that happens
to also batch into one round trip. `transaction=True` gets you both.

---

## Transactions vs Lua Scripting

This is where seniors need to know the actual limitation of WATCH-based
CAS: **you cannot branch on the value you read, inside the atomic unit.**

```
WATCH-based CAS:
  1. WATCH key          ┐
  2. GET key             │  OUTSIDE the atomic unit —
  3. <decide logic here>  │  your app code runs here, Redis
  4. MULTI               │  isn't "holding" anything except a dirty-flag
  5. SET key <computed>  ┘
  6. EXEC                 ← atomic unit is ONLY steps 4-6

  The read (step 2) and the decision (step 3) happen in your app process,
  NOT inside Redis. If your app is slow between step 2 and step 6, that's
  fine (retry handles conflicts) — but you can't write "if GET returns X,
  do A, else do B" as a single atomic Redis operation this way, only as
  an app-level retry loop around it.
```

```lua
-- Lua (EVAL) — conditional logic runs INSIDE Redis, atomically, no retry loop needed
-- Redis guarantees the whole script runs as one atomic step (single-threaded)
local current = redis.call('GET', KEYS[1])
if tonumber(current) + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
    return -1  -- would exceed cap, reject
else
    return redis.call('INCRBY', KEYS[1], ARGV[1])
end
```

```python
# Python side — one round trip, no WATCH, no retry loop, atomic branching
incr_with_cap = r.register_script("""
local current = redis.call('GET', KEYS[1])
if not current then current = 0 end
if tonumber(current) + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
    return -1
else
    return redis.call('INCRBY', KEYS[1], ARGV[1])
end
""")
result = incr_with_cap(keys=["counter:api_calls"], args=[1, 1000])
```

| | **MULTI/EXEC + WATCH** | **Lua (EVAL/EVALSHA)** |
|---|---|---|
| Conditional logic on the value read | Only OUTSIDE the atomic block, in your app — needs a retry loop | INSIDE the atomic block — `if`/`else` directly in the script |
| Round trips | WATCH + GET + MULTI...EXEC = multiple round trips, and MORE on retry (conflict) | 1 round trip, always, no retry needed for the logic itself |
| Retry logic needed | Yes — app must loop on `nil`/`WatchError` | No — the whole decision is atomic by construction |
| Readability | Familiar imperative code in your app language | Lua — a second language, harder to debug/test |
| Right for | Simple CAS: read one/few keys, write based on that read, low contention | Complex conditional writes, multiple related keys, high contention (avoids retry storms), reusable atomic building blocks (rate limiters, distributed locks) |

**The one-line answer to memorize:** "WATCH-based CAS is a client-side
retry loop around a server-side isolation check — the decision logic lives
in your app. Lua moves the decision logic itself into Redis, so it's
atomic by construction and needs no retry — reach for Lua when the
conditional logic is complex or contention is high enough that retries
would be expensive."

---

## Common Pitfalls

### 1. Assuming EXEC gives per-command rollback like SQL

```python
r.set("mystring", "hello")
pipe = r.pipeline(transaction=True)
pipe.incr("counter")        # succeeds
pipe.lpush("mystring", "x")  # WRONGTYPE — fails at runtime
pipe.incr("counter2")       # still succeeds — NOT rolled back
results = pipe.execute()
# counter and counter2 ARE incremented. Only the LPUSH failed.
```

There is no rollback. If your business logic needs "all-or-nothing on
runtime failure," you must validate types/values BEFORE queuing, or use
Lua where you can `return` early to abort the whole script's effect for
commands not yet executed (though even Lua doesn't undo Redis calls already
made earlier in the same script — same principle, smaller blast radius
since you control the ordering and can check-before-write inside the script).

### 2. Forgetting to UNWATCH after a failed/aborted attempt on a reused connection

```python
conn = r.connection_pool.get_connection("_")
# ... WATCH key, then something goes wrong before EXEC (exception, early return)
# If you don't UNWATCH or call EXEC/DISCARD, the watch state lingers on
# this connection. If the connection is reused (pool) for unrelated code
# that also does WATCH/MULTI/EXEC, stale watch state causes confusing
# spurious aborts.
```

Always wrap in try/finally, or use redis-py's `pipeline()` context manager
(`with r.pipeline() as pipe:`) which calls `reset()` (which unwatches)
automatically on exit — this is why the practical demo uses the context
manager form rather than raw WATCH/MULTI/EXEC commands.

### 3. Using WATCH/MULTI/EXEC across a Redis Cluster with keys on different nodes

```
WATCH balance:user:1     # hashes to slot X, node A
MULTI
SET balance:user:2 ...   # hashes to slot Y, node B — CROSSSLOT error
EXEC
```

In Cluster mode, all keys touched by a transaction (watched keys AND
queued command keys) must live in the SAME hash slot, which usually means
the same node. Use hash tags (`{user:1}.balance` and `{user:1}.history`)
to force related keys into the same slot if they need to participate in
the same transaction. This mirrors the same constraint Lua scripts have
in Cluster mode.

### 4. Not checking `EXEC`'s return for `nil` (transaction aborted)

```python
# Raw command style — EXEC returns None if a watched key changed
result = conn.execute_command("EXEC")
if result is None:
    # transaction was aborted — MUST retry, don't assume it silently succeeded
    ...
```

With redis-py's high-level `pipeline()`, this surfaces as a `WatchError`
exception instead of a `None` return — either way, silently ignoring it
means you think a write happened when it didn't.

### 5. Retrying forever with no backoff/cap under high contention

A tight `while True: try WATCH/MULTI/EXEC except WatchError: continue` loop
on a hot key can spin indefinitely under heavy concurrent writers. Cap
retry attempts and consider Lua instead if you're seeing frequent aborts —
that's a signal the contention is high enough that the retry-based
approach is the wrong tool.

---

## Interview Q&A

**Q: Is Redis MULTI/EXEC the same as a SQL transaction (BEGIN/COMMIT/ROLLBACK)?**
A: No, and this is the most commonly missed detail. SQL transactions
roll back ALL changes if any statement fails. Redis MULTI/EXEC only
guarantees isolation — no other client's commands interleave between your
queued commands during EXEC — but if one queued command has a runtime
error (e.g. wrong type), the OTHER queued commands still execute normally.
There's no rollback. Only a queue-time error (bad syntax/unknown command)
aborts the whole transaction, and it aborts before EXEC even starts running
anything.

**Q: How does WATCH implement optimistic locking without an actual lock?**
A: You WATCH a key, read its value, compute what you want to write based
on that read, then MULTI/EXEC the write. Redis tracks whether the watched
key was modified by ANYONE (including via expiry) between WATCH and EXEC.
If it was, EXEC aborts and returns nil/raises WatchError instead of
running the queued commands — no data is corrupted, no lock was ever held,
but your write is rejected so you know to re-read and retry. It's
compare-and-swap: cheap in the uncontended case, requires a retry loop in
the contended case, and never blocks other clients the way a real lock would.

**Q: When would you use Lua/EVAL instead of WATCH-based transactions?**
A: When you need to branch on the value you just read AS PART OF the
atomic operation itself. WATCH-based CAS reads and decides in your
application code, outside the atomic unit — the atomic part is only the
final MULTI...EXEC write, so you need an app-level retry loop for
conflicts. Lua scripts run entirely inside Redis as one atomic step,
so `if current + delta > cap then return -1 else INCRBY end` is a single
round trip with no retry loop needed at all. Reach for Lua when the logic
is more than a simple read-then-write, when multiple related keys need
coordinated conditional updates, or when contention is high enough that a
retry-based approach would thrash.

**Q: Walk me through what happens if I forget to call UNWATCH after a failed transaction on a pooled connection.**
A: The WATCH state stays attached to that physical connection. If the
connection pool hands that same connection to unrelated code later, and
that code does its own MULTI/EXEC without realizing a stale watch is still
active, its EXEC can spuriously abort because of the leftover watch — very
confusing to debug since the failure looks unrelated to the code that's
actually running. `EXEC` and `DISCARD` both auto-clear watches, so the
real risk is exiting via an exception or early return between WATCH and
EXEC/DISCARD without an explicit UNWATCH in a finally block — which is why
redis-py's `pipeline()` context manager (auto-reset on exit) is the safer
default over raw WATCH/MULTI/EXEC command calls.

**Q: Can you WATCH and transact across keys on different Redis Cluster nodes?**
A: No. All keys involved — watched keys and any keys touched by the
queued commands — must hash to the same slot, which in practice means the
same node, or you get a CROSSSLOT error. If your transaction genuinely
needs multiple logical keys (e.g. a user's balance and their transaction
history), use hash tags like `{user:123}:balance` and `{user:123}:history`
so the `{...}` portion forces both into the same slot regardless of the
rest of the key name. Same constraint applies to Lua scripts in Cluster mode.

---

## Real-World Use Cases

### 1. Atomic transfer between two balance keys (the classic CAS example)

```python
def transfer(from_key, to_key, amount):
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(from_key)
                balance = int(pipe.get(from_key) or 0)
                if balance < amount:
                    pipe.unwatch()
                    return False   # insufficient funds, no retry needed
                pipe.multi()
                pipe.decrby(from_key, amount)
                pipe.incrby(to_key, amount)
                pipe.execute()     # raises WatchError if from_key changed
                return True
            except redis.WatchError:
                continue  # someone else touched from_key — retry the whole read-decide-write
```

### 2. Atomic counter WITH a cap (don't increment past a limit)

The naive approach — `INCR` then check-and-decrement-back if over — has a
real race window:

```python
# NAIVE — has a race condition
new_val = r.incr("api_calls:user:1")
if new_val > 1000:
    r.decr("api_calls:user:1")   # "undo" — but between INCR and this DECR,
    raise RateLimitExceeded()     # OTHER clients may have already read the
                                   # over-limit value and made decisions on it,
                                   # or incremented further — the cap was
                                   # briefly violated for anyone observing it.
```

```python
# WATCH-based CAS — never lets the value cross the cap even momentarily
def incr_with_cap(key, cap):
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(key)
                current = int(pipe.get(key) or 0)
                if current >= cap:
                    pipe.unwatch()
                    return None   # reject — over cap, no write happens at all
                pipe.multi()
                pipe.incr(key)
                return pipe.execute()[0]   # WatchError if raced, retry
            except redis.WatchError:
                continue
```

(In production, the Lua version of this — shown in the "Transactions vs
Lua" section above — is usually preferred for a hot rate-limiter key,
since it's 1 round trip with no retry loop, versus WATCH-CAS's 2-4 round
trips per attempt plus potential retries under contention.)

### 3. Inventory reservation (e-commerce checkout)

```python
def reserve_stock(sku_key, qty):
    with r.pipeline() as pipe:
        while True:
            try:
                pipe.watch(sku_key)
                available = int(pipe.get(sku_key) or 0)
                if available < qty:
                    pipe.unwatch()
                    return False   # out of stock — don't oversell
                pipe.multi()
                pipe.decrby(sku_key, qty)
                pipe.execute()
                return True
            except redis.WatchError:
                continue   # someone else reserved concurrently, re-check stock
```

Same shape every time: WATCH → read → decide → MULTI → write → EXEC →
retry on WatchError. This is the pattern to have memorized cold for
interviews — transfers, caps, and reservations are all the same skeleton.

---

## References

- [Redis Transactions](https://redis.io/docs/manual/transactions/)
- [WATCH command](https://redis.io/commands/watch/)
- [EXEC command](https://redis.io/commands/exec/)
- redis-py `Pipeline` docs (`transaction=True`, `watch()`, `WatchError`)
- Related: `02_pipeline_connection_pool.md` (pipelining vs transactions),
  `08_lua_scripting.md` (the atomic-conditional-logic alternative),
  `06_cluster_mode.md` (hash slots — why cross-node transactions fail)
