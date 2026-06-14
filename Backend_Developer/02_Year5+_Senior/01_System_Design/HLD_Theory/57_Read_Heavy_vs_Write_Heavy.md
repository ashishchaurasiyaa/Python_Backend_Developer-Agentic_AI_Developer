# Read-Heavy vs Write-Heavy Systems — Workload pehchaano, architecture chuno

## WHAT

Kisi bhi system ko design karne se pehle ek number nikaalo: **read:write ratio**. Yeh ratio hi decide karta hai ki kahan optimize karna hai.

- **Read-heavy** = reads >> writes (e.g. 100:1). Log padhte zyada hain, likhte kam. (news site, product catalog, social feed)
- **Write-heavy** = writes heavy/lagataar (e.g. 1:1 ya write-dominant). Data constantly aa raha hai. (logging, IoT sensors, analytics ingestion, chat)

| | Read-Heavy | Write-Heavy |
|---|---|---|
| Bottleneck | Read throughput / latency | Write throughput / disk I/O |
| Best friend | **Caching, replicas** | **Sharding, async, batching** |
| DB choice | RDBMS + read replicas, cache | LSM-tree stores (Cassandra), TSDB |
| Scaling trick | Add read replicas / CDN | Partition writes across shards |
| Examples | News, catalog, blog, feed | Logs, metrics, IoT, chat, clickstream |

---

## READ-HEAVY — Strategies

Goal: read ko **DB tak pahunchne hi mat do**, ya cheap bana do.

```
1. CACHING          → Redis/Memcache. 90%+ reads cache se. (sabse bada lever)
2. READ REPLICAS    → writes primary pe, reads N replicas pe distribute
3. CDN              → static/media edge pe cache (DB tak request aati hi nahi)
4. DENORMALIZATION  → joins mehnge; data pehle se "ready" rakho (HLD_Theory/19)
5. MATERIALIZED VIEW→ precomputed query results
```
**Trade-off:** caching/replicas = **stale data** (eventual consistency) ka risk. Read-heavy me yeh aksar acceptable hota hai (±100 views matter nahi karte).

---

## WRITE-HEAVY — Strategies

Goal: writes ko **fast accept karo**, heavy work baad me/parallel me karo.

```
1. SHARDING         → writes ko kai DB nodes pe baant do (HLD_Theory/38)
2. ASYNC + QUEUE    → write ko Kafka/queue me daal do, turant ack;
                      consumer baad me DB me likhe (write buffering)
3. BATCHING         → 1000 writes ek saath flush karo (per-write overhead kam)
4. LSM-TREE STORES  → Cassandra/RocksDB writes ko sequential append karte hain
                      (random disk writes se bahut fast)
5. WAL              → pehle log me append (sequential), DB update baad me
```
**Trade-off:** async/batching = data thodi der **durable na dikhe**, aur read-your-own-write tricky ho jaata hai.

### Kyun LSM-tree write-heavy ke liye accha?
B-tree (RDBMS) har write pe random disk location update karta hai (slow). LSM-tree writes ko memory me jamaa karke **sequential bulk** me disk pe likhta hai — disk ke liye yeh bahut tez. Isliye Cassandra/ScyllaDB write-heavy ingestion me rule karte hain.

---

## REAL LIFE ANALOGY

**Read-heavy = public library.** Hazaaron log ek hi popular book padhna chahte hain. Solution: us book ki **kai copies** rakho (replicas) aur ek **photocopy summary** counter pe rakho (cache). Likhna (nayi book aana) kabhi-kabhi hota hai.

**Write-heavy = post office sorting center.** Lagataar dher saari chitthiyan aa rahi hain. Tum ek-ek karke process nahi karte — **batch** me sort karte ho, aur kai counters (shards) pe baant dete ho.

---

## WHEN TO USE WHAT

| System | Type | Primary tactic |
|---|---|---|
| News / Blog / Wikipedia | Read-heavy | CDN + cache + replicas |
| E-commerce catalog | Read-heavy | Cache + denormalized read model |
| Social feed | Read-heavy | Fan-out + cache (precompute feed) |
| Application logging | Write-heavy | Async queue + batch + TSDB |
| IoT / sensor data | Write-heavy | Sharding + LSM/time-series DB |
| Chat / messaging | Write-heavy | Sharded by conversation + queue |
| Analytics clickstream | Write-heavy | Kafka ingest + batch to warehouse |

**Mixed?** Bahut systems dono hote hain → **CQRS** (Command Query Responsibility Segregation): write-path aur read-path ko alag-alag optimize karo (write→normalized store, read→denormalized cache/view). Dekho LLD_Theory/Event_Sourcing_CQRS.

---

## Illustrative Code (concept)

```python
# READ-HEAVY: cache-aside — DB ko bachao
def get_product(pid):
    p = redis.get(f"prod:{pid}")
    if p:                      # 90%+ reads yahin se
        return p
    p = db.query(pid)          # cache miss → DB
    redis.setex(f"prod:{pid}", 300, p)   # 5 min cache
    return p

# WRITE-HEAVY: async buffer — turant ack, DB likhna defer
def ingest_event(evt):
    queue.push(evt)            # O(1), turant return
    # alag consumer process batch me DB/warehouse me likhega

def consumer_loop():
    batch = queue.pop_many(1000)   # 1000 ek saath
    db.bulk_insert(batch)          # ek round-trip
```

---

## Connection to Other Topics

- **Caching** (HLD_Theory/13) — read-heavy ka #1 hathiyaar.
- **Database Sharding** (HLD_Theory/38) — write-heavy scaling ka core.
- **Replication** (HLD_Theory/11) — read replicas se read scale.
- **CQRS / Event Sourcing** (LLD_Theory) — read aur write path alag karna.
- **Message Queues** (SD_Theory/05) — write buffering/async ingestion.

---

## Interview Q&A

**Q: System read-heavy hai ya write-heavy — pehle kaise decide karoge?**
A: Read:write ratio estimate karo (back-of-envelope). Feed/catalog/news = read-heavy (cache+replicas). Logs/IoT/metrics/chat = write-heavy (shard+async+batch). Yeh ratio architecture choices drive karta hai.

**Q: Read replicas add karne se kaunsi problem aati hai?**
A: **Replication lag** → replica thoda stale ho sakta hai. "Read-your-own-write" tootta hai (user ne likha, replica se padha, purana dikha). Solution: critical reads primary se, ya session ko primary pe pin karo.

**Q: Write-heavy me RDBMS kab fail karta hai, kya use karein?**
A: Single primary ka write throughput cap ho jaata hai (B-tree random I/O). Tab sharding, ya LSM-tree based stores (Cassandra/ScyllaDB), time-series DB (InfluxDB), ya Kafka-buffered ingestion use karte hain.

**Q: CQRS read/write-heavy me kaise madad karta hai?**
A: Write model aur read model alag — write side normalized + consistent, read side denormalized + cached. Dono ko independently scale aur optimize kar sakte ho.

---

## DEEP DIVE: READ REPLICAS

### Kaam kaise karta hai?

```
PRIMARY (write)
    │
    │  replication stream (binlog / WAL)
    ▼
REPLICA 1 (read)   REPLICA 2 (read)   REPLICA 3 (read)
```

- **Primary** pe sirf writes jaate hain (INSERT / UPDATE / DELETE).
- **Replicas** primary ka transaction log apply karte hain aur reads serve karte hain.
- App layer (ya load balancer) decide karta hai: write → primary, read → round-robin replicas.

### Replication Modes

| Mode | Consistency | Latency | Use when |
|---|---|---|---|
| Async (default) | Eventual — replica lag sakta hai ms–sec | Primary fast | Read-heavy, lag tolerable |
| Semi-sync | At least 1 replica confirmed | Slightly slower | Safer, moderate lag ok |
| Sync | All replicas confirmed | Slowest write | Strict durability required |

### Replication Lag — Main Gotcha

```
User ne product update kiya → primary pe write complete.
User turant apna profile refresh karta hai → replica se padha.
Replica 200ms peeche → purana data dikha.  ← "Read-your-own-write" problem
```

**Solutions:**

```
1. Session pinning  → write ke baad, us user ka next read bhi primary pe bhejo
                      (sticky routing, typically 1-5 sec)
2. Monotonic reads  → user ka read always same replica se (lag consistent rehta hai)
3. Read from primary for critical paths  → payment, stock check
4. Write timestamp piggyback  → response me "written_at: T" bhejo;
                                 replica ka lag T se kam hone par hi read karo
```

### Replica Scaling Math

```
Single DB: 1000 QPS reads
Add 4 replicas: 5000 QPS reads (5x)
Add 9 replicas: 10000 QPS reads (10x)

Cost: O(replicas) storage + compute. Writes still go to 1 primary.
Primary can become write bottleneck — tab sharding chahiye.
```

---

## DEEP DIVE: CQRS (Command Query Responsibility Segregation)

### The Core Idea

```
WITHOUT CQRS (single model):
  User.objects.get(id=1)   ← same ORM model for
  User.objects.create(...)  ← reads AND writes

WITH CQRS (separate models):
  WRITE SIDE              READ SIDE
  ──────────              ─────────
  UserCommand             UserReadModel
  (normalized,            (denormalized,
   validates,              precomputed,
   emits events)           cached, fast)
```

### Flow Diagram

```
Client WRITE request
    │
    ▼
Command Handler ──► Write DB (normalized, ACID)
    │                    │
    │              Domain Event emitted
    │                    │
    ▼                    ▼
  ACK          Event Handler / Projector
                         │
                         ▼
                   Read DB / Cache (denormalized view)
                         │
Client READ request ──►  ▼
                    Read Model returned (fast!)
```

### Practical Example: Social Feed

```
WRITE SIDE:
  POST /posts  →  posts table (normalized)
                  users table
                  (strict FK, constraints)

READ SIDE:
  GET /feed   →  Redis cache:
                  {user_id, posts: [{author_name, avatar, content, likes}]}
                  (everything prejoined, no DB query on read)

Projector (background):
  On new_post event → update Redis feed for all followers
  (fan-out write, but reads are instant)
```

### When CQRS is Overkill vs When it Shines

```
DO NOT USE for:
  Simple CRUD apps (todo list, admin panel)
  < 10k requests/day
  Team < 5 engineers (operational overhead bada hai)

USE when:
  Read pattern aur write pattern bahut alag (e.g., write normalized, read = feed/dashboard)
  Read scale >> write scale by 100x+
  Different SLAs: reads need <50ms, writes can be async
  Microservices: write service alag, read service alag
```

### CQRS + Event Sourcing

```
Event Sourcing: State mat store karo — sirf events store karo.
State = events ka replay.

WRITE: Append-only event log
  [UserCreated, EmailChanged, PasswordReset, ...]

READ: Materialize any view from events
  current_user_state = fold(events, initial_state)
  feed_view = project(post_events, follower_graph)

Benefit: Complete audit trail. Time-travel. Multiple read models from same events.
Cost: Replay time. Snapshot needed for long chains. Complexity.
```

---

## DEEP DIVE: CACHING LAYERS

### Caching Hierarchy — L1 to L5

```
L1: In-process cache (app server RAM)
    ├── Dictionary / LRU cache in Python (functools.lru_cache)
    ├── Latency: <0.01ms
    ├── Size: MB range, lost on restart
    └── Use: Per-instance, config, hot lookup

L2: Distributed cache (Redis / Memcached)
    ├── Shared across all app servers
    ├── Latency: ~0.5ms
    ├── Size: GB range, persists (Redis AOF/RDB)
    └── Use: Session, computed results, rate limiting

L3: CDN / Edge cache (Cloudflare, AWS CloudFront)
    ├── Geographically distributed PoPs
    ├── Latency: ~2-10ms (nearest PoP)
    ├── Size: TB range
    └── Use: Static assets, API responses, rendered HTML

L4: Read replicas (DB-level "cache")
    ├── Copy of full DB, read-optimized
    ├── Latency: ~5-20ms
    └── Use: Complex queries that can't be pre-cached

L5: Materialized views (DB-internal)
    ├── Precomputed query stored in DB
    ├── Latency: fast (like a table scan)
    └── Use: Expensive aggregates queried repeatedly
```

### Cache Strategy per Workload

```
READ-HEAVY product catalog:
  Request → L1 (in-process) → L2 (Redis) → L4 (replica) → Primary

READ-HEAVY with large media:
  Request → L3 (CDN edge) → Origin server → L2 (Redis) → DB

WRITE-HEAVY metrics ingestion:
  Writes → L2 (Redis counters, write-back) ─── flush → TimeSeries DB
  Reads  → L2 (latest N minutes from Redis) / DB (historical)
```

### Write Strategies Summary (for read-heavy vs write-heavy)

```
Cache-Aside:    Read-heavy. App populates on miss. Simple.
Write-Through:  Read-heavy where freshness critical. Slow writes.
Write-Back:     Write-heavy. Fast writes, async DB flush. Data loss risk.
Write-Around:   Write-once data. Don't pollute cache.
Read-Through:   Read-heavy. Cache fetches from DB on miss automatically.
```

---

## DEEP DIVE: WRITE-AHEAD LOGGING (WAL)

### Kya hai WAL?

```
"Pehle log me likho, phir actual data structure update karo"

WITHOUT WAL:
  Server crash mid-write → data structure half-updated → corruption!

WITH WAL:
  1. Write intent to log (sequential append — fast)
  2. Acknowledge write
  3. Apply to actual data pages (in background)
  4. On crash → replay log from last checkpoint → no data loss
```

### WAL ka Flow

```
Client INSERT
    │
    ▼
WAL Buffer (RAM)
    │ (periodic flush, every commit, or fsync)
    ▼
WAL File (disk — sequential write, FAST)
    │
    ▼ (background, asynchronous)
Heap / Data Pages (disk — random write, slower)

CRASH RECOVERY:
  Read WAL from last checkpoint
  Redo all committed transactions
  Undo uncommitted transactions
  DB state consistent!
```

### WAL aur Write Performance

```
Sequential writes (WAL) vs Random writes (heap updates):
  HDD: Sequential 100-200 MB/s vs Random 1-2 MB/s  → 100x difference!
  SSD: Sequential 500 MB/s vs Random 100 MB/s       → 5x difference

WAL batching: PostgreSQL flushes WAL on commit.
  Many small commits → many small fsyncs → slow
  Solution: group commit (batch multiple transactions' WAL writes)
  → High-write workload mein 3-5x improvement

PostgreSQL WAL settings:
  synchronous_commit = off   → ACK without fsync (risk: last ~30ms data loss)
  wal_buffers = 64MB         → Larger WAL buffer = fewer fsyncs
  checkpoint_completion_target = 0.9  → Spread checkpoint writes
```

### WAL in Replication

```
PostgreSQL streaming replication = WAL shipping:
  Primary → WAL stream → Replicas
  Replica applies same WAL → exact copy of primary

WAL archiving → point-in-time recovery (PITR):
  Archive every WAL file to S3
  Restore to any point: base backup + WAL replay to timestamp T
```

### LSM-Tree vs B-Tree — WAL angle

```
B-Tree (PostgreSQL, MySQL):
  WAL + random heap writes
  Reads: fast (tree traversal)
  Writes: WAL sequential + heap random

LSM-Tree (Cassandra, RocksDB):
  Writes: sequential append to MemTable → flush to SSTables
  No in-place update (immutable SSTables)
  Reads: slower (check MemTable + multiple SSTables + Bloom filters)
  Write amplification: lower per-write, but compaction cost later

Summary:
  B-Tree: read-optimized (good for read-heavy)
  LSM-Tree: write-optimized (good for write-heavy)
```

---

## DEEP DIVE: INDEXING TRADE-OFFS (READ vs WRITE COST)

### The Fundamental Trade-off

```
INDEXES:
  Read  benefit: Query O(n) → O(log n) or O(1). 10x-100x faster.
  Write cost:    Every INSERT/UPDATE/DELETE must update ALL indexes.

Example: Table with 8 indexes
  INSERT 1 row → 8 B-Tree insertions (each O(log n))
  UPDATE indexed column → 8 old-entry removals + 8 new-entry insertions
  → Write throughput can drop 5-10x vs 0-index table
```

### Read-Heavy Indexing Strategy

```
Goal: Fast queries, many indexes ok.

READ-HEAVY recommendations:
  ✓ Index all frequently queried columns
  ✓ Composite indexes matching query patterns
  ✓ Covering indexes (eliminate heap fetch)
  ✓ Materialized views for complex aggregates
  ✓ Partial indexes for sparse conditions
     CREATE INDEX ON events(created_at) WHERE status = 'error'
     (only error events — small index, fast for error dashboard)

Acceptable because: reads >> writes, write overhead tolerable.
```

### Write-Heavy Indexing Strategy

```
Goal: Maximum write throughput. Minimize index overhead.

WRITE-HEAVY recommendations:
  ✓ Minimal indexes — only what's truly needed for queries
  ✓ Defer index creation: bulk load data → create index after
     (much faster than maintaining index during bulk insert)
  ✓ Partial indexes instead of full indexes
  ✓ Use LSM-tree stores (Cassandra) that batch index updates
  ✓ Disable auto-analyze during bulk inserts

Example:
  Log ingestion table: 100k inserts/sec
  With 5 indexes → 40k inserts/sec (56% throughput loss!)
  With 1 index (timestamp only) → 85k inserts/sec

  Strategy: Write raw to partitioned table (minimal indexes),
            then batch-transform to analytics table (rich indexes).
```

### Read vs Write Cost Comparison Table

| Index Count | Read Speed | Write Speed | Use Case |
|---|---|---|---|
| 0 indexes | Very slow (seq scan) | Maximum | Bulk ingest, ETL staging |
| 1-2 indexes | Good (primary queries) | Fast | Write-heavy + few query patterns |
| 3-5 indexes | Excellent | Moderate | Balanced OLTP |
| 6-10 indexes | Excellent | Slow | Read-heavy, reporting DB |
| 10+ indexes | Excellent | Very slow | Analytics replica only |

### Index Types and Write Cost

```
B-Tree (standard):
  Write cost: O(log n) per index per write
  Read benefit: O(log n) equality + range + ORDER BY
  Balance: medium write cost, high read benefit

Hash Index:
  Write cost: O(1) per index per write
  Read benefit: O(1) equality ONLY (no range)
  Balance: lowest write cost for equality lookups

Partial Index:
  Write cost: only when row matches WHERE clause
  Read benefit: smaller index → faster scans
  Balance: best write cost for sparse conditions

GIN (full-text / JSONB):
  Write cost: HIGH — many index entries per document
  Read benefit: fast full-text / array contains
  Use only where full-text needed

BRIN (block range):
  Write cost: VERY LOW — only min/max per block
  Read benefit: only for sequential data (timestamps, IDs)
  Balance: near-zero write cost for time-series data
```

---

## DEEP DIVE: SHARDING FOR WRITE-HEAVY SYSTEMS

### Why Sharding?

```
Single primary DB write limit:
  Typical PostgreSQL: 5,000-20,000 writes/sec
  High-end hardware: ~50,000 writes/sec

Write-heavy systems need:
  IoT platform: 500,000 sensor writes/sec
  Twitter-scale: 6,000 tweets/sec (each fan-out = 100k+ writes)
  Log aggregation: millions of events/sec

Solution: Horizontal partitioning (sharding) across N DB nodes.
  N = 10 nodes → 10x write capacity (ideal)
```

### Sharding Strategies

```
1. RANGE SHARDING:
   Shard by value range.
   user_id 1-1M → Shard 1
   user_id 1M-2M → Shard 2

   Pros: Simple, range queries on shard key fast
   Cons: Hot shard (new users always on last shard = uneven load)

2. HASH SHARDING:
   shard = hash(user_id) % N
   user_id 101 → hash → Shard 3

   Pros: Even distribution, no hot shards
   Cons: Range queries need all shards, resharding expensive

3. CONSISTENT HASHING:
   Nodes on a virtual ring. Key → closest node clockwise.
   Adding node: only neighboring keys move (not all keys)

   Pros: Minimal data movement on scale-out
   Cons: Slightly uneven (mitigated by virtual nodes)
   Used by: Cassandra, DynamoDB, Redis Cluster

4. DIRECTORY SHARDING:
   Lookup table: user_id → shard_id
   user_id 101 → "shard_3" (from directory DB)

   Pros: Full flexibility, easy rebalancing
   Cons: Directory = single point of failure, extra hop
```

### Sharding Key Selection — Write-Heavy

```
Good shard key criteria:
  1. HIGH CARDINALITY: millions of distinct values (not status/country)
  2. EVEN DISTRIBUTION: no hotspot (avoid timestamp as sole key)
  3. QUERY ALIGNMENT: most queries include shard key (avoid cross-shard)
  4. IMMUTABLE: shard key change = expensive re-route

Examples:
  Chat app       → shard by conversation_id (all messages of a convo on one shard)
  IoT sensors    → shard by device_id (all readings of device on one shard)
  E-commerce     → shard by user_id (all orders of user on one shard)
  Logging        → shard by service_id + time bucket (high write locality)

Anti-pattern:
  Shard by timestamp only → ALL writes go to "latest" shard → HOT SHARD!
  Fix: Composite shard key: (service_id, timestamp) or consistent hash of device_id
```

### Shard-Aware Write Path

```python
class ShardedDB:
    def __init__(self, shard_count=16):
        self.shards = [DB(f"shard-{i}") for i in range(shard_count)]

    def get_shard(self, key: str) -> DB:
        shard_id = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(self.shards)
        return self.shards[shard_id]

    def write_event(self, device_id: str, payload: dict):
        shard = self.get_shard(device_id)
        shard.insert("events", {"device_id": device_id, **payload})
        # All events for device_id go to same shard → local queries possible

    def read_device_history(self, device_id: str):
        shard = self.get_shard(device_id)
        return shard.query(f"SELECT * FROM events WHERE device_id = '{device_id}'")
        # Single-shard query — fast!
```

### Cross-Shard Challenges

```
PROBLEM 1: Cross-shard transactions
  Transfer from user A (shard 2) to user B (shard 7)
  → 2-phase commit (2PC) needed → slow, complex
  Solution: Design to avoid cross-shard transactions (same-shard data model)

PROBLEM 2: Cross-shard queries
  "Total orders across all users this month" → hit all shards → aggregate
  Solution: Separate analytics DB (all shards stream to data warehouse)

PROBLEM 3: Resharding (adding shard N+1)
  Must move ~1/N data to new shard
  Solution: Consistent hashing (minimize movement) or shard-split approach

PROBLEM 4: Hotspot
  Celebrity user (millions of followers) → 1 shard overloaded
  Solution: Sub-shard hot users, or move to separate "hot" cluster
```

---

## COMPREHENSIVE COMPARISON TABLE

| Dimension | Read-Heavy | Write-Heavy |
|---|---|---|
| R:W ratio | 100:1, 1000:1 | 1:1 to 1:100 |
| Bottleneck | Read throughput, latency | Write throughput, disk I/O |
| Primary DB | RDBMS + read replicas | LSM-tree (Cassandra), TSDB |
| Caching | Aggressive (Redis, CDN, L1) | Minimal or write-back only |
| Indexing | Many indexes (reads fast) | Few indexes (writes fast) |
| Sharding need | Later (replicas scale reads first) | Early (write bottleneck hits fast) |
| Consistency | Eventual OK for most reads | Eventual write ack → durable async |
| CQRS benefit | High (read model optimized) | High (write model optimized) |
| WAL tuning | Default fine | async commit, group commit, WAL batching |
| Queue/async | Optional | Essential (Kafka/queue buffers writes) |
| Examples | News, catalog, wiki, social feed | Logs, IoT, metrics, chat, clickstream |
| Scale pattern | Add replicas / CDN layers | Shard DB, async queue, batch flush |
| DB examples | PostgreSQL + replicas, MySQL | Cassandra, InfluxDB, ScyllaDB, ClickHouse |
| Cost driver | Cache/CDN cost | Storage + write IOPS |
| Data model | Normalized write + denorm read | Append-only / time-partitioned |

---

## EXTENDED INTERVIEW Q&A

**Q: Read replicas add karne ke baad bhi DB slow hai — kya karein?**
A: Replicas reads scale karte hain, writes nahi. Agar writes slow hain → sharding ya write-optimized DB (Cassandra/ScyllaDB) chahiye. Agar reads still slow → caching layer (Redis) check karo — cache hit rate low ho sakti hai, ya cache stampede ho raha ho sakta hai. Also check replication lag — agar replica bahut behind hai to stale reads aur latency spike ho sakta hai.

**Q: CQRS ke bina bhi mixed read/write system scale ho sakta hai?**
A: Haan, simpler options pehle try karo: (1) DB-level materialized views — read-heavy queries ko pre-compute karo, (2) Read replicas — writes primary, reads replica, (3) Redis caching — expensive computed results cache karo. CQRS tab lo jab yeh sab na chale — alag write model aur read model maintain karna operational complexity badhaata hai.

**Q: Write-heavy system me indexing strategy kya honi chahiye?**
A: Minimum indexes principle: sirf woh indexes jo production queries ke liye zaroori hain. Har extra index = INSERT/UPDATE/DELETE slow. Tactics: (1) BRIN indexes for time-series (near-zero write cost), (2) Partial indexes for sparse conditions, (3) Bulk load karo, phir index banao (CREATE INDEX CONCURRENTLY), (4) LSM-tree stores use karo (Cassandra) — B-tree random writes se 10x faster sequential writes.

**Q: WAL aur LSM-tree dono sequential writes use karte hain — fark kya hai?**
A: WAL = durability mechanism for B-tree based DB. Writes first go to WAL (sequential), then applied to heap pages (random). Data pages ka random I/O still hota hai background me. LSM-tree = completely different storage engine — writes sequentially to MemTable → SSTable, koi random writes nahi. Compaction baad me SSTables merge karta hai. LSM pure write throughput me WAL+B-tree se better hai, lekin reads me bloom filters + multiple SSTables check karne padte hain (zyada seek).

**Q: Sharding me shard key change karna ho to kya karo?**
A: Shard key change karna ek major operation hai. Approach: (1) Double-write — dono old aur new shard ke according rows likhna shuru karo, (2) Backfill — existing data new shard scheme ke according copy karo, (3) Cutover — reads new scheme pe switch karo, (4) Cleanup — old data hatao. Ise minimize karne ke liye: shard key upfront carefully choose karo, consistent hashing use karo (minimize data movement on scaling).

**Q: Read replicas vs sharding — kab kaunsa?**
A: Read replicas pehle try karo — simpler. Jab writes saturate hone lagein (CPU 80%+ on primary, write latency badhe) tab sharding karo. Rule: 1 primary + 5 replicas = 5x read scale. Write scale chahiye = shard primary. Typically: reads >> writes → replicas suffice. Writes heavy too → shard + replicas per shard.

**Q: CQRS implement karte waqt consistency kaise handle karo?**
A: Write side pe write hota hai, read side eventually consistent hota hai (event propagation lag). Solutions: (1) Optimistic UI — frontend write ke baad turant new state dikhao (assume success), event confirm aane se pehle. (2) Read-your-own-write — write ke baad short window me primary se padho. (3) Versioning — event me version number bhejo; read model version check kare aur discard kare out-of-order events. (4) Saga/choreography — complex multi-step operations ko event chain se handle karo.
