# Redis — Performance Monitoring, Keyspace Notifications & Client-Side Caching

## Quick Concepts

- **INFO** = server ka health dashboard (memory, hits/misses, clients, replication) — pehla debugging stop
- **SLOWLOG** = slow commands ka log (microseconds me threshold) — "Redis slow kyun hai?" ka jawab
- **LATENCY** = latency spikes ka history + doctor
- **`--bigkeys` / `--hotkeys`** = redis-cli scans jo memory-hog aur traffic-hog keys dhundte hain
- **Keyspace notifications** = key events (SET/DEL/EXPIRE) pe Pub/Sub messages — event-driven invalidation
- **Client-side caching (CLIENT TRACKING)** = Redis 6+ / RESP3: app-local cache + server khud invalidation push karta hai

---

## 1. Performance Monitoring (production runbook)

### INFO — kya dekhna hai

```bash
redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
# hit rate = hits / (hits + misses) — < 80% = cache design pe sawaal

redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio|evicted"
# fragmentation > 1.5 = restart/activedefrag consider karo
# evicted_keys > 0   = maxmemory chhota hai ya TTL strategy galat

redis-cli INFO clients | grep -E "connected_clients|blocked_clients"
redis-cli INFO replication   # role, replica lag (offset diff)
```

### SLOWLOG — slow commands pakdo

```bash
CONFIG SET slowlog-log-slower-than 10000   # 10ms se slow log karo (microseconds!)
CONFIG SET slowlog-max-len 256
SLOWLOG GET 10        # last 10 slow commands — timestamp, duration, args
SLOWLOG RESET
```

```
Classic culprits jo SLOWLOG me milte hain:
  KEYS *            → SCAN use karo (non-blocking cursor)
  SMEMBERS huge-set → SSCAN
  LRANGE list 0 -1  → paginate
  DEL big-hash      → UNLINK (background delete)
  Lua loop          → script me unbounded iteration
Redis single-threaded hai — EK slow command sabko rokta hai. 10ms ka
command = 10ms ke liye poora Redis blocked.
```

### Latency & problem keys

```bash
CONFIG SET latency-monitor-threshold 100
LATENCY LATEST / LATENCY DOCTOR      # spikes ka source (fork? AOF? expire cycle?)

redis-cli --bigkeys                  # sampled scan — sabse badi keys per type
redis-cli --hotkeys                  # requires maxmemory-policy allkeys-lfu
MEMORY USAGE mykey                   # ek key ka exact size
MEMORY DOCTOR                        # human advice
MONITOR                              # ⚠️ har command live stream — CPU ~50% khata hai,
                                     # production me seconds ke liye hi, kabhi permanent nahi
```

**Prometheus setup:** `redis_exporter` sidecar → Grafana dashboard (hit rate, memory, evictions, connected clients, replication lag) — [DevOps 11_Monitoring](../../../../DevOps/11_Monitoring/01_prometheus_grafana_alertmanager.md) ka pattern yahan bhi same hai.

---

## 2. Keyspace Notifications (expiry-driven events)

By default **OFF** (CPU bachane ke liye). Enable karo to Redis har key-event pe Pub/Sub message publish karta hai.

```bash
CONFIG SET notify-keyspace-events "Ex"   # E = keyevent channel, x = expired events
# Flags: K=keyspace channel, E=keyevent channel, g=generic(DEL/EXPIRE),
#        $=string, l=list, s=set, h=hash, z=zset, x=expired, e=evicted, A=all
```

```python
import redis
r = redis.Redis(decode_responses=True)

# Session expire hone pe cleanup — polling ki zaroorat nahi
p = r.pubsub()
p.psubscribe("__keyevent@0__:expired")     # DB 0 ke expired events

for msg in p.listen():
    if msg["type"] == "pmessage":
        expired_key = msg["data"]           # e.g. "session:abc123"
        if expired_key.startswith("session:"):
            handle_logout(expired_key)      # audit log, presence update, cleanup
```

**Use cases:** session-expiry cleanup, cache invalidation fan-out, delayed jobs (set TTL, act on expiry), presence ("user offline when heartbeat key expires").

### Gotchas (yehi interview me poochte hain)

```
1. Fire-and-forget Pub/Sub hai — listener down tha to event GAYA.
   Guaranteed delivery chahiye to Redis Streams use karo, yeh nahi.
2. Expired event LAZY hai — key ka event tab aata hai jab Redis usse
   actually expire karta hai (access pe ya active-expire cycle me),
   TTL ke exact moment pe nahi. Second-level precision mat maano.
3. Cluster me events us node se aate hain jahan key hai — har node
   pe subscribe karna padta hai.
4. "A" (all events) production me CPU cost — sirf jo chahiye wahi flag do.
```

---

## 3. Client-Side Caching — CLIENT TRACKING (Redis 6+, RESP3)

**Problem:** hot keys pe har GET bhi network round-trip hai (~0.5-1ms). **Solution:** app-process ke andar local dict me cache karo, aur **Redis khud batayega kab invalid hua** — yahi CLIENT TRACKING hai.

```
Without tracking:  App ──GET──► Redis  (har read = network hop)
With tracking:     App reads local dict (~ns)
                   Redis ──push invalidation──► App  (jab koi key change kare)
```

```python
# redis-py 5+: RESP3 protocol + built-in client-side cache
import redis
from redis.cache import CacheConfig

r = redis.Redis(
    protocol=3,                          # RESP3 required — push messages ke liye
    cache_config=CacheConfig(),          # local cache enable; redis-py invalidation
)                                        # push messages khud handle karta hai

r.set("config:feature_x", "on")
r.get("config:feature_x")   # 1st: Redis se, ab locally cached
r.get("config:feature_x")   # 2nd: LOCAL — network hop hi nahi hua
# Kisi aur client ne SET kiya → Redis push invalidation bhejta hai
# → local copy drop → next GET fresh value laata hai
```

```
Modes:
  Default tracking : server har client ke READ keys yaad rakhta hai
                     (invalidation table server-side memory leta hai)
  BCAST mode       : CLIENT TRACKING ON BCAST PREFIX "config:"
                     server kuch yaad nahi rakhta, prefix-match par sab
                     clients ko broadcast — kam server memory, zyada messages
```

### Kab use karo / kab nahi

| ✅ Use | ❌ Avoid |
|---|---|
| Hot, rarely-changing keys (config, feature flags, product catalog) | Frequently-written keys (invalidation storm) |
| Read-heavy fan-out (1000 pods same config read kar rahe) | Strict freshness requirement (push me ~ms lag hai) |
| Latency-critical hot path (local read = ns) | Bahut saare unique keys (server tracking table bloat — BCAST use karo) |

**vs manual local cache (dict + TTL):** manual me staleness window = TTL; tracking me Redis actively push karta hai → window ~network-latency tak girta hai, aur TTL-tuning ka guesswork khatam.

---

## Interview Q&A

**Q: Production me Redis suddenly slow — debugging order?**
`INFO stats` (hit rate, ops/sec) → `INFO memory` (fragmentation, evictions — memory pressure?) → `SLOWLOG GET` (kaunsa command? KEYS/SMEMBERS/big DEL?) → `LATENCY DOCTOR` (fork/AOF spikes?) → `--bigkeys`/`--hotkeys` (data-shape problem?). Single-threaded model yaad dilao — ek O(n) command sabko block karta hai, isliye SLOWLOG usually smoking gun hota hai.

**Q: Session expire hote hi DB me "last_seen" update karna hai — kaise?**
Keyspace notifications: `notify-keyspace-events Ex` + `__keyevent@0__:expired` pe psubscribe. Caveat batao: delivery guaranteed nahi (Pub/Sub fire-and-forget) aur expiry lazy hai — critical accuracy chahiye to backup sweep job bhi rakho.

**Q: Client-side caching vs sirf local dict+TTL — farq?**
TTL-based local cache me staleness = poora TTL window, aur har pod apna guess karta hai. CLIENT TRACKING me server ko pata hai kisne kya read kiya (ya BCAST prefix), write hote hi invalidation PUSH hota hai — staleness milliseconds me. Cost: RESP3 connection, server-side tracking memory (default mode), aur invalidation-storm risk on write-heavy keys.

---

**Related:** [10_pubsub_fundamentals.md](10_pubsub_fundamentals.md) (Pub/Sub delivery semantics) · [05_streams_consumer_groups.md](05_streams_consumer_groups.md) (guaranteed delivery alternative) · [09_persistence_memory.md](09_persistence_memory.md) (memory debugging) · [../../09_Caching/theory/07_multi_level_caching.md](../../09_Caching/theory/07_multi_level_caching.md) (L1 local + L2 Redis pattern)
