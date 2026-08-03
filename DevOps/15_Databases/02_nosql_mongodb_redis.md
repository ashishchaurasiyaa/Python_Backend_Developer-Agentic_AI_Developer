# Databases — MongoDB & Redis Operations

**DevOps Track · Phase 15: Databases**

> Complementary to the app-level coverage in Backend_Developer/ — this covers the infra/ops angle: hardening, deployment, and operating these systems.

## Quick Concepts

- **Replica set (MongoDB)** = a primary + secondaries holding copies of the same data, with automatic failover election
- **Sharding (MongoDB)** = horizontal partitioning of data across multiple shards using a shard key, for datasets too large for one node
- **`mongodump`/`mongorestore`** = MongoDB's logical backup/restore tools, analogous to `mysqldump`/`pg_dump`
- **RDB (Redis Database file)** = point-in-time binary snapshot of Redis's dataset
- **AOF (Append Only File)** = Redis persistence mode that logs every write operation, replayed on restart
- **Redis Sentinel** = HA solution for Redis providing monitoring, automatic failover, and service discovery for a primary-replica set
- **Redis Cluster** = Redis's native sharding solution — splits the keyspace across multiple nodes with built-in replication per shard
- **`maxmemory-policy`** = what Redis does once it hits its memory ceiling — `noeviction` (the default) fails writes; `allkeys-lru` evicts old keys instead

---

## Why This Matters for Ops

```
Backend_Developer/08_Redis and Backend_Developer/10_MongoDB cover
"how do I query this from my app" — pymongo, redis-py, data modeling.

The ops job here:
   - Is this replica set going to survive losing its primary node?
   - Will Redis lose all its data on a restart, or does persistence
     actually work the way you assumed?
   - Can this MongoDB cluster handle the data volume, or does it
     need sharding before it falls over?
   - When Redis is down, does the WHOLE FLEET go down with it, or
     does Sentinel/Cluster fail over transparently?
```

---

## MongoDB Ops

### Replica Sets

```
A replica set = 1 primary (accepts writes) + N secondaries (replicate
from primary, serve reads if configured, vote in elections). If the
primary goes down, the remaining members hold an election and promote
a new primary automatically — usually within seconds.

Odd number of members (3, 5, 7) — avoids split-vote ties. A common
minimal prod setup is 3 members (primary + 2 secondaries), or
primary + secondary + arbiter (arbiter votes but holds no data,
used to break ties cheaply).
```

```javascript
// Initiate a replica set
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" },
    { _id: 2, host: "mongo3:27017" }
  ]
})

// Check status
rs.status()
rs.isMaster()          // who's currently primary

// Force a manual failover (e.g. before planned maintenance on primary)
rs.stepDown(60)        // steps down for 60s, triggers election
```

```yaml
# mongod.conf — replica set member
replication:
  replSetName: rs0
net:
  bindIp: 0.0.0.0
  port: 27017
security:
  authorization: enabled
```

### User & Role Management — What `authorization: enabled` Actually Requires

`security.authorization: enabled` (above) turns on access control — but MongoDB has NO default admin account, so the very first thing that must happen (before enabling it, in practice) is creating one.

```javascript
// Connect once WITHOUT authorization enabled, create the admin user first
use admin
db.createUser({
  user: "admin",
  pwd: "change-me",
  roles: [{ role: "root", db: "admin" }]
})
// NOW enable security.authorization: enabled and restart mongod

// Everyday app role — scoped to exactly one database, read/write only
use mydb
db.createUser({
  user: "app_user",
  pwd: "change-me",
  roles: [{ role: "readWrite", db: "mydb" }]
})

// Read-only role — same least-privilege idea as SQL's readonly_user
db.createUser({
  user: "readonly_user",
  pwd: "change-me",
  roles: [{ role: "read", db: "mydb" }]
})
```

```javascript
// See what's actually granted
db.getUsers()
db.getUser("app_user")
```

```
Built-in role hierarchy (narrowest to broadest): read → readWrite →
dbAdmin → dbOwner → root. Same principle as the SQL file's
app_user/readonly_user split and IAM least-privilege from Phase 7 —
the app connects with a role scoped to exactly what it needs, root is
reserved for actual administration, never the app's everyday connection.
```

### Sharding Basics

```
Sharding kicks in when a single replica set can't hold the data or
handle the write throughput. Data is partitioned across shards by
a shard key — choosing this key well is the single most consequential
decision in a sharded MongoDB deployment (a bad shard key creates
hot shards that defeat the purpose entirely).

Components:
   mongos      — query router, what the app connects to
   config servers — store cluster metadata (which shard has what)
   shards      — each one IS a replica set holding a portion of data
```

```javascript
// Enable sharding on a database, then shard a specific collection
sh.enableSharding("mydb")
sh.shardCollection("mydb.orders", { customer_id: "hashed" })

// Check shard distribution — look for imbalance
sh.status()
db.orders.getShardDistribution()
```

```
Real ops mistake: sharding on a monotonically increasing key
(e.g. _id, created_at) sends all new writes to ONE shard — the
"hot shard" problem. Hashed shard keys (as above) distribute writes
evenly but sacrifice efficient range queries. This tradeoff should
be a deliberate decision, not a default.
```

### Backup with `mongodump`

```bash
# Full logical backup
mongodump --uri="mongodb://user:pass@host:27017" --out=/backup/$(date +%Y%m%d)

# Restore
mongorestore --uri="mongodb://user:pass@host:27017" /backup/20260725

# Backup a single database/collection
mongodump --db=mydb --collection=orders --out=/backup

# For sharded clusters or point-in-time needs, physical backups
# (filesystem snapshot of each shard's data dir, taken consistently)
# or a managed service (Atlas continuous backup) are used instead —
# mongodump doesn't scale well past a few hundred GB.
```

```bash
# Automate with retention, off-box copy — same pattern as SQL backups
mongodump --uri="$MONGO_URI" --archive=/backup/mongo-$(date +%Y%m%d).gz --gzip
aws s3 cp /backup/mongo-$(date +%Y%m%d).gz s3://backups-bucket/mongo/
find /backup -name "mongo-*.gz" -mtime +7 -delete
```

---

## Redis Ops

### Persistence: RDB vs AOF

```
RDB (snapshotting):
   Periodic point-in-time binary dump of the whole dataset.
   + Fast restarts (single compact file to load)
   + Good for backups (single file to copy off-box)
   - Data since the last snapshot is LOST on a crash
     (default: snapshot every 60s if >=1000 keys changed, configurable)

AOF (append-only log):
   Every write command logged to a file, replayed on restart.
   + Much better durability — configurable fsync policy down to
     "every write" (at most 1 command lost)
   - Larger file, slower restart (replaying the whole log)
   - Needs periodic rewrite/compaction (AOF rewrite) to stay manageable

Most production setups: BOTH enabled. RDB for fast full restores
and portable backups, AOF for minimizing data loss window.
```

```conf
# redis.conf

# RDB
save 900 1        # snapshot if >=1 key changed in 900s
save 300 10        # AND if >=10 keys changed in 300s
save 60 10000       # AND if >=10000 keys changed in 60s
dbfilename dump.rdb
dir /var/lib/redis

# AOF
appendonly yes
appendfsync everysec    # fsync policy: always | everysec | no
                         # "always" = safest, slowest
                         # "everysec" = good default, up to 1s loss
appendfilename "appendonly.aof"
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

```bash
# Manual snapshot / trigger AOF rewrite
redis-cli BGSAVE
redis-cli BGREWRITEAOF

# Check persistence status
redis-cli INFO persistence
```

### `maxmemory` and Eviction Policy — What Happens When Redis Fills Up

Persistence (above) answers "what survives a restart." This answers a completely different question: "what happens when Redis runs out of memory while still running."

```conf
# redis.conf
maxmemory 2gb                     # hard ceiling — Redis will not exceed this
maxmemory-policy allkeys-lru        # WHAT to do once the ceiling is hit
```

```
maxmemory-policy options — the ones that actually matter:

noeviction        → THE DEFAULT. Once maxmemory is hit, Redis returns
                     an error on every WRITE command instead of evicting
                     anything — reads still work, writes fail loudly.
                     Appropriate when Redis holds data that must NOT be
                     silently lost (a queue, a rate-limit counter, a
                     session store with no other source of truth).

allkeys-lru        → evicts the Least Recently Used key across the
                      ENTIRE keyspace to make room — the standard choice
                      for a PURE cache, where losing any key is fine
                      because it can be recomputed/refetched from the
                      real source of truth.

volatile-lru        → same LRU eviction, but ONLY among keys that have
                       a TTL set — keys with no expiry are never evicted.
                       Useful when Redis mixes cache-like keys (with TTL)
                       and must-not-lose keys (no TTL) in the same instance.

allkeys-random       → evict a random key — rarely the right choice,
                        occasionally used when LRU tracking overhead
                        itself matters at extreme scale.
```

```
The real ops incident this section prevents: a team runs Redis purely
as a cache but leaves the DEFAULT policy (noeviction) in place. Once
the dataset grows past maxmemory, every SET/LPUSH/HSET call starts
failing with OOM errors — not a graceful "cache just evicted something
old," but the APPLICATION itself breaking, because the ops-level
config never matched the actual usage pattern. Match the policy to
what Redis is actually being used for, don't leave the default by
accident.
```

```bash
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy
redis-cli INFO memory | grep used_memory_human    # current usage vs the ceiling
```

### Redis Sentinel vs Redis Cluster — Which HA Model

```
Sentinel:
   A set of Sentinel processes monitor a primary + replicas, and
   automatically promote a replica to primary on failure. Data is
   NOT sharded — every node holds the full dataset. Clients connect
   to Sentinel to discover the current primary's address.

   Good fit: dataset fits comfortably on one node, you need HA/failover
   but not horizontal scaling of capacity/throughput.

Cluster:
   Data is sharded across multiple primary nodes (each with its own
   replicas) using hash slots (16384 total, distributed across
   primaries). Provides both HA (per-shard replica failover) AND
   horizontal scaling.

   Good fit: dataset or throughput exceeds what one node can handle.
   More operational complexity — client must be cluster-aware
   (redis-py-cluster, or modern redis-py with cluster mode).
```

| | Redis Sentinel | Redis Cluster |
|---|---|---|
| Data sharding | No — full dataset per node | Yes — 16384 hash slots across primaries |
| HA / auto-failover | Yes | Yes (per shard) |
| Horizontal write scaling | No | Yes |
| Client complexity | Simple — connect via Sentinel for discovery | Higher — cluster-aware client required |
| Multi-key operations (MULTI, Lua across keys) | Unrestricted | Restricted to same hash slot (use hash tags `{}`) |
| Operational complexity | Lower | Higher |
| When to use | Dataset fits one node, need failover | Dataset/throughput exceeds one node |

```bash
# Sentinel config (sentinel.conf)
sentinel monitor mymaster 10.0.0.1 6379 2   # quorum of 2 sentinels to agree on failure
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000

redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

```bash
# Cluster setup (6 nodes: 3 primaries + 3 replicas)
redis-cli --cluster create \
  10.0.0.1:6379 10.0.0.2:6379 10.0.0.3:6379 \
  10.0.0.4:6379 10.0.0.5:6379 10.0.0.6:6379 \
  --cluster-replicas 1

redis-cli -c -p 6379 CLUSTER NODES
redis-cli -c -p 6379 CLUSTER INFO
# key hash tags to force related keys onto the same slot:
# user:{123}:profile and user:{123}:sessions → same slot, safe for MULTI
```

---

## Senior Tip

```
"We use Redis" is not the same as "Redis data survives a restart."
Default RDB-only config with wide save intervals means a container
restart during a rolling deploy can silently drop the last minute
of writes. If Redis is used as anything more than a pure cache
(session store, queue, rate-limit counters that matter), verify
AOF is on with a sane fsync policy — don't assume.
```

## Interview Angle

**Q: When would you choose Redis Sentinel over Redis Cluster?**
When the dataset comfortably fits on a single node and the requirement
is HA/failover, not horizontal scaling. Sentinel is operationally
simpler and avoids the hash-slot constraints Cluster imposes on
multi-key operations.

**Q: If Redis is purely a cache, do you need AOF?**
Usually no — if a cache miss just falls back to the source of truth,
losing cached data on crash is an acceptable, self-healing cost, and
RDB-only (or even no persistence) is fine and faster. AOF matters when
Redis holds data that isn't reconstructable elsewhere (queues, unique
session state, rate-limit windows that must not reset).

**Q: What's the risk of choosing `created_at` as a MongoDB shard key?**
It's monotonically increasing, so all new document inserts land on
whichever shard owns the current high end of the range — a "hot shard"
that absorbs all write traffic while other shards sit idle, defeating
the point of sharding. A hashed key (or a compound key with better
write distribution) avoids this at the cost of efficient range scans.

**Q: Redis is used purely as a cache, but once the dataset grows large enough, the application itself starts throwing errors on every write — not just cache misses. What's misconfigured?**
`maxmemory-policy` is still set to its default, `noeviction` — once Redis hits its `maxmemory` ceiling, `noeviction` fails every write command with an OOM error instead of evicting anything, which is the correct behavior for data that must not be silently lost but the wrong behavior for a pure cache. Switching to `allkeys-lru` makes Redis evict the least-recently-used key to make room instead, which is safe precisely because a cache miss just falls back to the real source of truth.

**Q: You just enabled `security.authorization: enabled` on a fresh MongoDB deployment and now can't connect at all, even as an admin. What went wrong?**
MongoDB has no default admin account — a user with the `root` role must be created BEFORE authorization is enabled (connecting without auth, since none exists yet), otherwise there's no credential that can authenticate once access control turns on. The fix is restarting temporarily without `authorization: enabled`, creating the admin user, then re-enabling it.

---

## Related

- [01_sql_mysql_postgresql.md](01_sql_mysql_postgresql.md) — MySQL/PostgreSQL ops
- [../17_Caching/01_caching.md](../17_Caching/01_caching.md) — Redis as a cache layer, invalidation strategies
- [../../Backend_Developer/01_Year3-4_Mid/10_MongoDB/](../../Backend_Developer/01_Year3-4_Mid/10_MongoDB/) — app-level MongoDB usage
- [../../Backend_Developer/00_Year0-2_Junior/08_Redis/](../../Backend_Developer/00_Year0-2_Junior/08_Redis/) — app-level Redis usage
