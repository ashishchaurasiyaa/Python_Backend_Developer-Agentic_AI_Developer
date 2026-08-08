"""
Redis Lab 05 — Redlock Quorum Simulation (majority-acquire logic)
=====================================================================
OBJECTIVE: khud likho majority-acquire logic against 5 "pseudo-node" key
prefixes, aur prove karo ki minority failure tolerate hoti hai lekin
majority failure me lock FAIL hona chahiye.

  IMPORTANT — LOCAL SIMULATION, NOT REAL REDLOCK:
  Real Redlock ko N=5 INDEPENDENT Redis processes chahiye alag hosts/failure
  domains pe (theory/../02_redlock_distributed_locks.md dekho). 5 real
  dockerized nodes ek throwaway lab ke liye impractical hai, isliye yeh lab
  "5 nodes" ko 5 alag KEY PREFIXES ke roop me simulate karta hai — sab ek
  hi local Redis instance pe (matching practical/19_redlock_distributed_locks.py
  ka redlock_quorum simplification). Yeh sirf QUORUM-COUNTING LOGIC
  demonstrate karta hai, fault isolation NAHI (agar yeh ek Redis process
  down ho jaaye, saare "5 nodes" saath me marte hain — jo asli Redlock ka
  poora point defeat karta hai). Production me 5 real independent instances
  use karo alag machines pe.

TASK:
  1. TODO 1: har reachable pseudo-node pe `SET key token NX PX ttl` try karo
  2. TODO 2: quorum (majority) vote count check karo, acquired decide karo
  3. Run: python 05_redlock_quorum.py

Prereq: docker compose up -d   |   pip install "redis[hiredis]>=5.0"
"""

import secrets
import redis

NUM_NODES = 5
QUORUM = NUM_NODES // 2 + 1   # 3 of 5

# 5 "pseudo-nodes" = 5 key prefixes on the SAME local Redis instance.
# See module docstring — this is a simplification for quorum-LOGIC only.
_base = redis.Redis(host="localhost", port=6379, decode_responses=True)


def _node_key(prefix: str, i: int) -> str:
    return f"lab:redlock:node{i}:{prefix}"


def acquire(resource: str, token: str, ttl_ms: int, down_nodes: set = None) -> tuple:
    """
    Try to SET NX PX on every reachable pseudo-node. Returns (acquired, votes).
    down_nodes = set of node indices simulated as unreachable (skipped entirely,
    like a real network partition or crashed instance).
    """
    down_nodes = down_nodes or set()
    votes = 0

    for i in range(NUM_NODES):
        if i in down_nodes:
            continue   # simulated failure — this node is never even tried

        # ─────────────────────────────────────────────────────
        # TODO 1: is node (key = _node_key(resource, i)) pe lock
        #         lene ki koshish karo — SET NX PX. Safal ho to
        #         votes badhao.
        #         Hint: ok = _base.set(_node_key(resource, i), token,
        #                              nx=True, px=ttl_ms)
        # ─────────────────────────────────────────────────────
        pass
        # ─────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────
    # TODO 2: `votes` ke basis pe decide karo ki quorum mila ya
    #         nahi. QUORUM se >= votes chahiye.
    #         Hint: acquired = votes >= QUORUM
    # ─────────────────────────────────────────────────────
    acquired = None
    # ─────────────────────────────────────────────────────

    if acquired is None:
        print("❌ TODO 1/2 abhi bharna hai")
        return False, votes

    if not acquired:
        # partial acquire hua ho to us cleanup karo — locks leak mat hone do
        release(resource, token)

    return acquired, votes


def release(resource: str, token: str) -> None:
    """Token-compare release on every node (bare DEL would be racy — see practical/19)."""
    script = _base.register_script("""
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        end
        return 0
    """)
    for i in range(NUM_NODES):
        try:
            script(keys=[_node_key(resource, i)], args=[token])
        except redis.RedisError:
            pass


def _cleanup(resource: str) -> None:
    for i in range(NUM_NODES):
        _base.delete(_node_key(resource, i))


def main() -> None:
    resource = "shared_resource"
    _cleanup(resource)

    print(f"\n[1] All 5 nodes reachable (0 down) — expect ACQUIRED...")
    token1 = secrets.token_hex(8)
    acquired1, votes1 = acquire(resource, token1, ttl_ms=10_000)
    print(f"   votes={votes1}/{NUM_NODES}  → acquired={acquired1}")
    release(resource, token1)
    _cleanup(resource)

    print(f"\n[2] 2 of 5 nodes DOWN (minority failure, quorum={QUORUM} still "
          "reachable) — expect ACQUIRED...")
    token2 = secrets.token_hex(8)
    acquired2, votes2 = acquire(resource, token2, ttl_ms=10_000, down_nodes={0, 1})
    print(f"   votes={votes2}/{NUM_NODES - 2} reachable  → acquired={acquired2}")
    release(resource, token2)
    _cleanup(resource)

    print(f"\n[3] 3 of 5 nodes DOWN (majority failure, only "
          f"{NUM_NODES - 3} reachable < quorum={QUORUM}) — expect FAILS...")
    token3 = secrets.token_hex(8)
    acquired3, votes3 = acquire(resource, token3, ttl_ms=10_000, down_nodes={0, 1, 2})
    print(f"   votes={votes3}/{NUM_NODES - 3} reachable  → acquired={acquired3}")

    print("\n" + "─" * 55)
    if acquired1 and acquired2 and not acquired3:
        print("✅ PASS — quorum acquired with 0 and 2 nodes down (minority "
              "failure tolerated), correctly FAILED with 3 nodes down "
              "(majority failure, no quorum).")
    else:
        print(f"❌ FAIL — acquired1={acquired1} (expected True), "
              f"acquired2={acquired2} (expected True), "
              f"acquired3={acquired3} (expected False)")
        if not acquired1 or not acquired2:
            print("   TODO 1 check karo — SET NX PX per-node call sahi se")
            print("   ho raha hoga ya votes count nahi ho raha.")
        if acquired3:
            print("   TODO 2 check karo — quorum comparison galat hai, majority")
            print("   down hone ke baad bhi lock de raha hai (UNSAFE).")

    _cleanup(resource)

    print("""
SOCH (bolke jawab do):
  1. Yeh simulation 5 key-prefixes ek hi Redis process pe use karta hai —
     real Redlock se yeh kaise FUNDAMENTALLY different hai (fault isolation
     ke terms me)? Agar yeh ek process crash ho jaaye to kya hota hai?
  2. Quorum = N//2 + 1 kyun (aur N/2 nahi)? Split-brain se kaise bachata hai?
  3. Redlock critics (jaise Martin Kleppmann) ka main objection kya hai —
     clock drift aur GC pauses ke against yeh design kitna robust hai?
  4. Production me single Redis instance ka lock kaafi hota hai ya Redlock
     chahiye — kis scenario me kya choose karoge?
""")


if __name__ == "__main__":
    main()
