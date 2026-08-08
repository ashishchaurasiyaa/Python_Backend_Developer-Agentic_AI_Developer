"""
Redis Practical 19 — Distributed Locks & Redlock
Run: python 19_redlock_distributed_locks.py [singlelock|baredel_bug|redlock_quorum|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine

IMPORTANT TRADEOFF (read this before the redlock_quorum section):
  Real Redlock needs N=5 INDEPENDENT Redis processes on separate hosts/failure
  domains — that's the whole point (see theory/19_redlock_distributed_locks.md,
  Core Concepts #3 and "Why No Replication Between Instances"). Spinning up 5
  real dockerized Redis nodes is impractical for a throwaway local demo script,
  so SECTION 3 below simulates "5 nodes" as 5 separate logical DB indices
  (db=0..4) inside the SAME single local Redis instance/process.
  This is a SIMPLIFICATION for demonstrating the quorum + timing-budget LOGIC
  only — it does NOT simulate independent failure domains (if this one Redis
  process/host dies, all 5 "pseudo-nodes" die together, which defeats the
  actual purpose of Redlock). Do not mistake this demo for a production
  Redlock deployment. For production, use 5 real independent Redis instances
  (or a maintained Redlock client library) on separate machines.
"""

import sys
import time
import secrets
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: SINGLE-INSTANCE LOCK — correct acquire/release
# (recap of theory/08_lua_scripting.md pattern, standalone here for the demo)
# ════════════════════════════════════════════

ACQUIRE_LOCK_SCRIPT = r.register_script("""
return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', tonumber(ARGV[2]))
""")

# Correct release: GET + compare token + DEL, all atomic in Lua.
# Bare `redis.DEL` from app code would be racy — see SECTION 2 for the bug.
RELEASE_LOCK_SCRIPT = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
""")


class SingleInstanceLock:
    """Correct token-compare lock. Mirrors DistributedLock in practical/08_lua_scripting.py."""

    def __init__(self, key, ttl_ms=10_000):
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = secrets.token_hex(16)
        self.acquired = False

    def acquire(self) -> bool:
        result = ACQUIRE_LOCK_SCRIPT(keys=[self.key], args=[self.token, self.ttl_ms])
        self.acquired = bool(result)
        return self.acquired

    def release(self) -> bool:
        """Only deletes the key if OUR token still matches — safe even after TTL races."""
        result = RELEASE_LOCK_SCRIPT(keys=[self.key], args=[self.token])
        self.acquired = False
        return bool(result)


def demo_singlelock():
    print("\n" + "=" * 50)
    print("  SECTION 1: SINGLE-INSTANCE LOCK (correct pattern)")
    print("=" * 50)

    key = "lock:demo:resource"
    r.delete(key)

    lock_a = SingleInstanceLock(key, ttl_ms=5000)
    lock_b = SingleInstanceLock(key, ttl_ms=5000)

    print(f"Client A acquire → {lock_a.acquire()}   (token={lock_a.token[:8]}...)")
    print(f"Client B acquire (should FAIL, A still holds it) → {lock_b.acquire()}")

    print(f"Client B release (not owner, token mismatch) → {lock_b.release()}   (expect False/0)")
    print(f"Client A release (owner, token matches) → {lock_a.release()}   (expect True/1)")

    print(f"Client B acquire NOW (A released, key free) → {lock_b.acquire()}")
    lock_b.release()
    print("✅ Token-compare release means only the actual holder can ever delete its own lock.")


# ════════════════════════════════════════════
# SECTION 2: THE BARE-DEL BUG — concrete demonstration
# ════════════════════════════════════════════
def demo_baredel_bug():
    print("\n" + "=" * 50)
    print("  SECTION 2: BARE DEL BUG (deletes someone ELSE's lock)")
    print("=" * 50)

    key = "lock:demo:baredel_bug"
    r.delete(key)

    # ─── Client A acquires with a SHORT ttl, then gets "slow" (simulated) ───
    token_a = secrets.token_hex(8)
    r.set(key, token_a, nx=True, px=500)   # 500ms TTL — deliberately short
    print(f"Client A acquired lock, token={token_a[:8]}..., TTL=500ms")
    print("Client A now does 'slow work' (simulated sleep 700ms > TTL)...")
    time.sleep(0.7)   # critical section takes LONGER than the TTL — classic pitfall #3

    # ─── Meanwhile the key has expired. Client B acquires it fresh. ───
    token_b = secrets.token_hex(8)
    acquired_b = r.set(key, token_b, nx=True, px=10_000)
    print(f"Client B acquired lock AFTER A's TTL expired → {bool(acquired_b)}, "
          f"token={token_b[:8]}...")

    # ─── Client A finally finishes "slow work" and releases with a BARE DEL. ───
    # This is the bug: A never checks whose token is currently on the key.
    print("Client A finishes work, calls bare DEL (the WRONG way to release)...")
    r.delete(key)   # <-- THE BUG: no token check, deletes whatever is there NOW

    # ─── Verify: B's lock is GONE, even though B never released it. ───
    still_there = r.get(key)
    print(f"Key after A's bare DEL: {still_there!r}   (expect None — B's still-valid lock got wiped)")

    if still_there is None:
        print("❌ CONFIRMED BUG: Client A's bare DEL deleted Client B's active lock.")
        print("   B believes it still holds the lock (its TTL had 10s left) — but the")
        print("   key is gone. A THIRD client could now acquire the 'held' lock too.")
    else:
        print("   (unexpected timing — re-run, the race depends on sleep vs TTL)")

    print("\n   FIX: release must be the Lua compare-then-DEL script from SECTION 1 —")
    print("   `if GET(key) == my_token then DEL(key)` — A's token wouldn't match")
    print("   B's token, so the correct release would have been a safe no-op.")

    r.delete(key)   # cleanup


# ════════════════════════════════════════════
# SECTION 3: REDLOCK QUORUM SIMULATION (simplified — see module docstring)
# ════════════════════════════════════════════

NUM_PSEUDO_NODES = 5
QUORUM = NUM_PSEUDO_NODES // 2 + 1   # 3 of 5

# 5 "pseudo-nodes" = 5 separate logical DB indices on the SAME local Redis
# process. Real Redlock requires independent physical instances — this only
# demonstrates the quorum-counting + timing-budget LOGIC, not fault isolation.
PSEUDO_NODES = [redis.Redis(host='localhost', port=6379, db=i, decode_responses=True)
                for i in range(NUM_PSEUDO_NODES)]

PER_NODE_TIMEOUT_S = 0.05   # small timeout per node so one slow/down node can't
                             # stall the whole acquire attempt (real Redlock: same idea)

SAFETY_MARGIN_MS = 10   # stand-in for Antirez's "clock drift" margin — even a
                         # full quorum is rejected if too little validity remains


def _redlock_acquire(key, token, ttl_ms, simulate_down_nodes=None, simulate_latency_ms=0):
    """
    Try SET NX PX on every pseudo-node. Returns (acquired, elapsed_ms, votes,
    remaining_validity_ms). simulate_down_nodes = node indices to skip (models
    those instances being unreachable). simulate_latency_ms = artificial delay
    injected before each node call, so the timing-budget check has something
    real to bite on (a same-process local Redis round trip is sub-millisecond,
    which would never exercise the "took too long" branch otherwise).
    """
    simulate_down_nodes = simulate_down_nodes or set()
    votes = 0
    t_start = time.monotonic()

    for i, node in enumerate(PSEUDO_NODES):
        if i in simulate_down_nodes:
            continue   # simulated failure — this node never gets tried
        if simulate_latency_ms:
            time.sleep(simulate_latency_ms / 1000)   # simulate slow network hop
        try:
            ok = node.set(key, token, nx=True, px=ttl_ms)
            if ok:
                votes += 1
        except redis.RedisError:
            pass   # unreachable node — doesn't count, doesn't block the others

    elapsed_ms = (time.monotonic() - t_start) * 1000
    remaining_validity_ms = ttl_ms - elapsed_ms

    # Redlock success condition: majority AND enough time budget left
    # (Antirez's spec: subtract elapsed time AND a clock-drift safety margin)
    acquired = votes >= QUORUM and remaining_validity_ms > SAFETY_MARGIN_MS

    if not acquired:
        # Release whatever we DID acquire on partial success — don't leak locks
        _redlock_release(key, token)

    return acquired, elapsed_ms, votes, remaining_validity_ms


def _redlock_release(key, token):
    """Release on every pseudo-node — token-compare, same safety as SECTION 1."""
    for node in PSEUDO_NODES:
        try:
            release_script = node.register_script("""
                if redis.call('GET', KEYS[1]) == ARGV[1] then
                    return redis.call('DEL', KEYS[1])
                end
                return 0
            """)
            release_script(keys=[key], args=[token])
        except redis.RedisError:
            pass


def demo_redlock_quorum():
    print("\n" + "=" * 50)
    print("  SECTION 3: REDLOCK QUORUM SIMULATION (simplified — see docstring)")
    print("=" * 50)
    print(f"Pseudo-nodes: {NUM_PSEUDO_NODES} (db=0..{NUM_PSEUDO_NODES - 1} on local Redis)"
          f"   Quorum needed: {QUORUM}")

    key = "lock:redlock:demo_resource"
    for node in PSEUDO_NODES:
        node.delete(key)

    # ─── Case 1: all nodes up → full quorum, easy win ───
    token1 = secrets.token_hex(8)
    acquired, elapsed, votes, remaining = _redlock_acquire(key, token1, ttl_ms=10_000)
    print(f"\nCase 1 — all 5 nodes reachable:")
    print(f"  votes={votes}/{NUM_PSEUDO_NODES}  elapsed={elapsed:.1f}ms  "
          f"remaining_validity={remaining:.0f}ms  → ACQUIRED={acquired}")
    _redlock_release(key, token1)

    # ─── Case 2: minority (2 of 5) down → quorum still reachable (3 of 5) ───
    token2 = secrets.token_hex(8)
    acquired, elapsed, votes, remaining = _redlock_acquire(
        key, token2, ttl_ms=10_000, simulate_down_nodes={0, 1}
    )
    print(f"\nCase 2 — 2 of 5 nodes simulated DOWN (minority failure):")
    print(f"  votes={votes}/{NUM_PSEUDO_NODES - 2} reachable  elapsed={elapsed:.1f}ms  "
          f"remaining_validity={remaining:.0f}ms  → ACQUIRED={acquired}")
    print("  ✅ Majority tolerates a MINORITY of nodes being down — this is the")
    print("     whole point of Redlock over a single instance.")
    _redlock_release(key, token2)

    # ─── Case 3: majority (3 of 5) down → quorum FAILS, must not acquire ───
    token3 = secrets.token_hex(8)
    acquired, elapsed, votes, remaining = _redlock_acquire(
        key, token3, ttl_ms=10_000, simulate_down_nodes={0, 1, 2}
    )
    print(f"\nCase 3 — 3 of 5 nodes simulated DOWN (majority failure):")
    print(f"  votes={votes}/{NUM_PSEUDO_NODES - 3} reachable  elapsed={elapsed:.1f}ms  "
          f"remaining_validity={remaining:.0f}ms  → ACQUIRED={acquired}")
    print("  ❌ Can't reach quorum (need 3, only 2 nodes even reachable) → correctly refuses.")

    # ─── Case 4: time-budget safety check — inject artificial per-node latency ───
    # A same-process local Redis round trip is sub-millisecond, so the timing
    # check would never fail on its own here — we inject a small simulated
    # network delay per node (simulate_latency_ms) to make "acquire took too
    # long relative to TTL" concretely reproducible, same as a real slow/
    # congested network would do against 5 real remote instances.
    print(f"\nCase 4 — timing-budget safety check (simulated network latency vs small TTL):")
    token4 = secrets.token_hex(8)
    small_ttl_ms = 20
    acquired, elapsed, votes, remaining = _redlock_acquire(
        key, token4, ttl_ms=small_ttl_ms, simulate_latency_ms=5
    )
    print(f"  votes={votes}/{NUM_PSEUDO_NODES}  elapsed={elapsed:.1f}ms  ttl={small_ttl_ms}ms  "
          f"safety_margin={SAFETY_MARGIN_MS}ms  remaining_validity={remaining:.1f}ms  "
          f"→ ACQUIRED={acquired}")
    print("  ❌ Full quorum reached, but remaining_validity <= safety margin —")
    print("     Redlock must treat this as a FAILED acquire (release everything, retry),")
    print("     per theory/19_redlock_distributed_locks.md Core Concepts #3.")

    for node in PSEUDO_NODES:
        node.delete(key)


if __name__ == "__main__":
    sections = {
        "singlelock": demo_singlelock,
        "baredel_bug": demo_baredel_bug,
        "redlock_quorum": demo_redlock_quorum,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 19_redlock_distributed_locks.py [{'|'.join(sections)}|all]")
