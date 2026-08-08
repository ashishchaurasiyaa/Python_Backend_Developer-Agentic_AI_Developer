"""
Redis Practical 17 — Replication Fundamentals (master-replica)
Run: python 17_replication_fundamentals.py [attach|propagation|lag|all]

Prerequisites — this topic needs 2 Redis instances, a single localhost:6379
is NOT enough (unlike most other files in this repo):

  # Option A: Docker — two separate containers, master + replica
  docker run -d --name redis-master  -p 6379:6379 redis:7-alpine
  docker run -d --name redis-replica -p 6380:6379 redis:7-alpine

  # Option B: two local redis-server processes on different ports
  redis-server --port 6379 --daemonize yes
  redis-server --port 6380 --daemonize yes

  pip install "redis[hiredis]>=5.0"

This script attaches the replica to the master via REPLICAOF at RUNTIME
(no config file edits needed) — safe to re-run, REPLICAOF is idempotent.
No cluster / sentinel here — this is the raw primitive underneath both
(see 06_cluster_mode.py and 07_sentinel_ha.py for those layers on top).
"""

import sys
import time
import redis

MASTER_HOST, MASTER_PORT = "localhost", 6379
REPLICA_HOST, REPLICA_PORT = "localhost", 6380


def _connect(host, port, label):
    try:
        conn = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=2)
        conn.ping()
        return conn
    except redis.exceptions.ConnectionError:
        print(f"❌ Could not reach {label} at {host}:{port}")
        print("   Start both instances first — see docstring at top of this file.")
        sys.exit(1)


# ════════════════════════════════════════════
# SECTION 1: ATTACH REPLICA — REPLICAOF + INFO REPLICATION
# ════════════════════════════════════════════
def demo_attach():
    print("\n" + "=" * 50)
    print("  SECTION 1: REPLICAOF — ATTACH + INSPECT")
    print("=" * 50)

    master = _connect(MASTER_HOST, MASTER_PORT, "master")
    replica = _connect(REPLICA_HOST, REPLICA_PORT, "replica")

    # ─── Runtime attach — equivalent to `redis-cli -p 6380 REPLICAOF host port` ───
    replica.replicaof(MASTER_HOST, MASTER_PORT)
    print(f"🔗 Issued REPLICAOF {MASTER_HOST} {MASTER_PORT} on port {REPLICA_PORT} replica")

    # ─── Sync le sakti hai a moment — poll until link is up (full/partial resync) ───
    for _ in range(20):
        info = replica.info("replication")
        if info.get("master_link_status") == "up":
            break
        time.sleep(0.2)

    m_info = master.info("replication")
    r_info = replica.info("replication")

    print("\n📊 MASTER (INFO replication):")
    print(f"   role: {m_info['role']}")
    print(f"   connected_slaves: {m_info['connected_slaves']}")
    print(f"   master_repl_offset: {m_info['master_repl_offset']}")
    print(f"   master_replid: {m_info['master_replid']}")

    print("\n📊 REPLICA (INFO replication):")
    print(f"   role: {r_info['role']}")
    print(f"   master_link_status: {r_info.get('master_link_status')}")
    print(f"   master_host:master_port: {r_info.get('master_host')}:{r_info.get('master_port')}")
    print(f"   slave_repl_offset: {r_info.get('slave_repl_offset')}")
    print(f"   master_repl_offset (mirrored): {r_info.get('master_repl_offset')}")

    print("\n   role:master/role:slave + connected_slaves — yahi fields Sentinel bhi")
    print("   poll karta hai (INFO REPLICATION) health + failover decisions ke liye.")


# ════════════════════════════════════════════
# SECTION 2: ASYNC PROPAGATION — write master, read replica
# ════════════════════════════════════════════
def demo_propagation():
    print("\n" + "=" * 50)
    print("  SECTION 2: ASYNC PROPAGATION (write → replica lag)")
    print("=" * 50)

    master = _connect(MASTER_HOST, MASTER_PORT, "master")
    replica = _connect(REPLICA_HOST, REPLICA_PORT, "replica")

    if replica.info("replication").get("master_link_status") != "up":
        print("⚠️ Replica master se linked nahi hai — pehle 'attach' section chalao.")
        return

    key = "repl:demo:order_status"
    master.set(key, "pending")

    # ─── Turant likho master pe, TURANT hi replica se padho — no wait ───
    master.set(key, "paid")
    immediate = replica.get(key)
    print(f"✍️  master.set('{key}', 'paid')")
    print(f"📖 replica.get() IMMEDIATELY after write → {immediate!r}")
    print("   (async replication — replica shayad abhi bhi purana/None value de,")
    print("    read-after-write consistency ki koi guarantee nahi hai)")

    # ─── Ab thoda sa wait karo — replication stream ko pahunchne do ───
    time.sleep(0.05)
    settled = replica.get(key)
    print(f"\n⏳ 50ms sleep ke baad → replica.get() = {settled!r}")
    print("   Propagate ho gaya — typical LAN lag sub-millisecond se low-ms tak hoti hai,")
    print("   par koi HARD bound nahi hai (network/master load pe depend karta hai).")

    # ─── WAIT command — opt-in stronger guarantee (still not synchronous replication) ───
    master.set(key, "shipped")
    acked = master.execute_command("WAIT", 1, 1000)  # 1 replica, 1000ms timeout
    print(f"\n🔒 master.set(...) + WAIT 1 1000 → {acked} replica(s) acked")
    print("   WAIT blocks tab tak jab tak N replicas is offset tak ack na karein,")
    print("   ya timeout na ho jaye — best-effort, Raft-style hard commit guarantee NAHI.")

    master.delete(key)


# ════════════════════════════════════════════
# SECTION 3: REPLICATION LAG — INFO replication ke fields se measure
# ════════════════════════════════════════════
def demo_lag():
    print("\n" + "=" * 50)
    print("  SECTION 3: REPLICATION LAG INSPECTION")
    print("=" * 50)

    master = _connect(MASTER_HOST, MASTER_PORT, "master")
    replica = _connect(REPLICA_HOST, REPLICA_PORT, "replica")

    if replica.info("replication").get("master_link_status") != "up":
        print("⚠️ Replica master se linked nahi hai — pehle 'attach' section chalao.")
        return

    # ─── Burst of writes on master to create a measurable offset gap ───
    print("✍️  Writing 5,000 keys to master in a tight loop...")
    pipe = master.pipeline(transaction=False)
    for i in range(5000):
        pipe.set(f"repl:lag:{i}", "x" * 50)
    pipe.execute()

    # ─── Master side: connected_slaves ke andar per-replica offset + lag dikhta hai ───
    m_info = master.info("replication")
    print(f"\n📊 MASTER master_repl_offset: {m_info['master_repl_offset']}")
    for i in range(m_info.get("connected_slaves", 0)):
        slave = m_info.get(f"slave{i}")
        if slave:
            print(f"   slave{i}: {slave}")   # ip=..,port=..,state=..,offset=..,lag=..

    # ─── Replica side: poll until it catches up, print the shrinking gap ───
    print("\n📊 Polling replica offset until it catches up to master...")
    for _ in range(20):
        m_offset = master.info("replication")["master_repl_offset"]
        r_offset = replica.info("replication").get("slave_repl_offset", 0)
        gap = m_offset - r_offset
        print(f"   master_repl_offset={m_offset}  slave_repl_offset={r_offset}  gap={gap} bytes")
        if gap <= 0:
            print("   ✅ Replica caught up — gap=0")
            break
        time.sleep(0.1)
    else:
        print("   ⚠️ Still lagging after 2s — check network/CPU on replica")

    print("\n   Production mein isi gap (aur 'lag' seconds field slaveN line mein) pe")
    print("   alerting lagao — sudden spike = replica CPU-bound ya network issue.")

    # ─── Cleanup demo keys ───
    for i in range(0, 5000, 500):
        master.delete(*[f"repl:lag:{j}" for j in range(i, min(i + 500, 5000))])


if __name__ == "__main__":
    sections = {
        "attach": demo_attach,
        "propagation": demo_propagation,
        "lag": demo_lag,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 17_replication_fundamentals.py [{'|'.join(sections)}|all]")
