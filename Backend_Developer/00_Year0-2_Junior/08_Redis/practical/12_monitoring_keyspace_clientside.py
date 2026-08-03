"""
Redis Practical 12 — Monitoring, Keyspace Notifications & Client-Side Caching
Run: python 12_monitoring_keyspace_clientside.py [monitor|slowlog|keyspace|clientcache|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine
  (clientcache section needs redis-py 5+ for RESP3 CacheConfig)
"""

import sys
import time
import threading
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: MONITORING — INFO / hit rate / bigkeys
# ════════════════════════════════════════════
def demo_monitor():
    print("\n" + "=" * 50)
    print("  SECTION 1: INFO — PRODUCTION HEALTH CHECK")
    print("=" * 50)

    # ─── Traffic generate karo taaki stats me kuch dikhe ───
    r.set("mon:x", "1")
    for _ in range(20):
        r.get("mon:x")          # hits
        r.get("mon:missing")    # misses

    stats = r.info("stats")
    hits, misses = stats["keyspace_hits"], stats["keyspace_misses"]
    hit_rate = hits / (hits + misses) * 100 if (hits + misses) else 0
    print(f"📊 Hit rate: {hit_rate:.1f}%  (hits={hits:,} misses={misses:,})")
    print("   < 80% in production → cache keys/TTL design pe sawaal uthao")

    mem = r.info("memory")
    print(f"📊 used_memory: {mem['used_memory_human']}"
          f"   fragmentation: {mem.get('mem_fragmentation_ratio', 'n/a')}")
    print(f"   evicted_keys: {stats.get('evicted_keys', 0)} "
          "(> 0 = maxmemory pressure — TTLs/sizing dekho)")

    clients = r.info("clients")
    print(f"📊 connected_clients: {clients['connected_clients']}"
          f"   blocked: {clients['blocked_clients']}")

    # ─── Ek key ka exact memory + poore DB ka big-key hunt ───
    print(f"📊 MEMORY USAGE mon:x = {r.memory_usage('mon:x')} bytes")
    print("   Full scan CLI se: redis-cli --bigkeys   (sampled, prod-safe)")
    r.delete("mon:x")


# ════════════════════════════════════════════
# SECTION 2: SLOWLOG — slow command pakadna
# ════════════════════════════════════════════
def demo_slowlog():
    print("\n" + "=" * 50)
    print("  SECTION 2: SLOWLOG")
    print("=" * 50)

    # ─── Threshold 0 = HAR command log hoga (sirf demo ke liye!) ───
    r.config_set("slowlog-log-slower-than", 0)
    r.slowlog_reset()

    r.mset({f"slow:{i}": "x" * 100 for i in range(1000)})
    r.keys("slow:*")          # O(n) villain — production me SCAN use karo

    entries = r.slowlog_get(3)
    print("📊 Last slow commands:")
    for e in entries:
        cmd = " ".join(
            c.decode() if isinstance(c, bytes) else str(c) for c in e["command"][:2]
        )
        print(f"   {e['duration']:>6}µs  {cmd}...")

    # ─── Production threshold wapas set karo: 10ms ───
    r.config_set("slowlog-log-slower-than", 10000)
    print("✅ Threshold restored to 10ms — Redis single-threaded hai,")
    print("   ek 50ms KEYS call = 50ms me SAB requests blocked")

    for key in r.scan_iter("slow:*", count=500):    # SCAN — the right way
        r.delete(key)


# ════════════════════════════════════════════
# SECTION 3: KEYSPACE NOTIFICATIONS — expiry events
# ════════════════════════════════════════════
def demo_keyspace():
    print("\n" + "=" * 50)
    print("  SECTION 3: KEYSPACE NOTIFICATIONS")
    print("=" * 50)

    # ─── Enable expired-key events (default OFF) ───
    r.config_set("notify-keyspace-events", "Ex")

    received = []

    def listener():
        sub = redis.Redis(decode_responses=True)
        p = sub.pubsub()
        p.psubscribe("__keyevent@0__:expired")
        for msg in p.listen():
            if msg["type"] == "pmessage":
                received.append(msg["data"])
                break                      # demo: ek event ke baad exit

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)                        # listener subscribe ho jaye

    # ─── 1-second session banao, expire hone do ───
    r.setex("session:demo_user", 1, "logged_in")
    print("⏳ session:demo_user set with 1s TTL, waiting for expiry event...")
    t.join(timeout=5)

    if received:
        print(f"✅ Expired event received for: {received[0]}")
        print("   → yahi hook pe logout-audit / presence-update / cleanup chalta hai")
    else:
        print("⚠️ Event nahi mila (active-expire cycle lazy hai — dobara run karo)")

    print("\n   GOTCHA: Pub/Sub fire-and-forget hai — listener down = event LOST.")
    print("   Guaranteed processing chahiye to Streams (05_streams) use karo.")


# ════════════════════════════════════════════
# SECTION 4: CLIENT-SIDE CACHING — RESP3 tracking
# ════════════════════════════════════════════
def demo_clientcache():
    print("\n" + "=" * 50)
    print("  SECTION 4: CLIENT-SIDE CACHING (Redis 6+, redis-py 5+)")
    print("=" * 50)

    try:
        from redis.cache import CacheConfig
    except ImportError:
        print("⚠️ redis-py 5+ chahiye is section ke liye: pip install 'redis>=5.0'")
        return

    # ─── RESP3 + local cache: reads local dict se, invalidation Redis push karta hai ───
    cached = redis.Redis(protocol=3, cache_config=CacheConfig(), decode_responses=True)
    plain = redis.Redis(decode_responses=True)

    plain.set("config:feature_x", "on")

    v1 = cached.get("config:feature_x")            # network se, ab locally cached
    t0 = time.perf_counter()
    for _ in range(10_000):
        cached.get("config:feature_x")             # LOCAL reads — no network
    local_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(10_000):
        plain.get("config:feature_x")              # har read = network hop
    network_time = time.perf_counter() - t0

    print(f"📊 10K reads — local cache: {local_time*1000:.0f}ms"
          f"   vs network: {network_time*1000:.0f}ms"
          f"   ({network_time/local_time:.0f}x faster)")

    # ─── DOOSRA client write kare → Redis invalidation push → fresh read ───
    plain.set("config:feature_x", "off")
    time.sleep(0.1)                                # push process hone do
    v2 = cached.get("config:feature_x")
    print(f"✅ After external write: '{v1}' → '{v2}' (invalidation push ne stale copy uda di)")
    print("   Use for: config/feature-flags/catalog — hot + rarely-written keys")

    cached.close()


if __name__ == "__main__":
    sections = {
        "monitor": demo_monitor,
        "slowlog": demo_slowlog,
        "keyspace": demo_keyspace,
        "clientcache": demo_clientcache,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 12_monitoring_keyspace_clientside.py [{'|'.join(sections)}|all]")
