# PostgreSQL Partitioning + Sharding

> **Interview angle:** "Table 500M rows ho gaya — queries slow. Kya karoge?"

---

## 1. Partitioning vs Sharding

| | **Partitioning** | **Sharding** |
|---|---|---|
| What | Split table within ONE DB | Split across MULTIPLE DBs |
| Hardware | Single server | Multiple servers |
| Native Postgres | ✅ Yes (PARTITION BY) | ❌ No (use Citus) |
| Query routing | Postgres automatic | App or proxy decides |
| Scaling axis | Vertical (more disk, RAM) | Horizontal (more nodes) |
| Use when | Single table > 100M rows | Whole DB > 1TB |

**Typical progression:**
1. Single table, indexes → fine up to ~100M rows
2. **Partitioning** → 100M-10B rows
3. **Sharding** → 10B+ rows, multi-TB

---

## 2. Why Partition?

Big table problems:
- Vacuum takes hours
- Indexes become huge (don't fit in cache)
- Queries scan more pages
- DELETE old data is expensive
- Backups slow

Partitioning **splits one logical table into many physical tables** ("partitions"). Queries automatically target relevant partition(s) only.

---

## 3. Three Partition Strategies

### Range Partitioning (most common)
Split by ranges of a column value.
```sql
CREATE TABLE events (
    id BIGSERIAL,
    event_time TIMESTAMPTZ NOT NULL,
    user_id INT,
    data JSONB
) PARTITION BY RANGE (event_time);

CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

**Best for:** time-series, logs, events.

### List Partitioning
Split by enumerated values.
```sql
CREATE TABLE orders (
    id BIGSERIAL,
    country TEXT NOT NULL,
    amount NUMERIC
) PARTITION BY LIST (country);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('FR', 'DE', 'IT');
CREATE TABLE orders_default PARTITION OF orders DEFAULT;
```

**Best for:** geographic/tenant grouping.

### Hash Partitioning
Split by hash of column.
```sql
CREATE TABLE users (
    id BIGSERIAL,
    email TEXT NOT NULL
) PARTITION BY HASH (id);

CREATE TABLE users_p0 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE users_p1 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE users_p2 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE users_p3 PARTITION OF users FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

**Best for:** even distribution, no natural range.

---

## 4. Partition Pruning (Magic)

Query optimizer skips irrelevant partitions:
```sql
EXPLAIN SELECT * FROM events WHERE event_time = '2024-01-15';
-- Only scans events_2024_01, ignores others
```

**Critical:** Partition key MUST be in WHERE clause for pruning.

---

## 5. Subpartitioning

Two-level partitioning — range, then hash within each range:
```sql
CREATE TABLE logs (...)
    PARTITION BY RANGE (created_at);

CREATE TABLE logs_2024_01 PARTITION OF logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')
    PARTITION BY HASH (user_id);

CREATE TABLE logs_2024_01_p0 PARTITION OF logs_2024_01
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
```

---

## 6. Automatic Partition Management

Manually creating monthly partitions = pain. Use **`pg_partman`** extension:

```sql
CREATE EXTENSION pg_partman;

SELECT partman.create_parent(
    p_parent_table => 'public.events',
    p_control => 'event_time',
    p_type => 'native',
    p_interval => '1 month',
    p_premake => 4   -- pre-create 4 future partitions
);

-- Run periodically (Postgres cron or external)
SELECT partman.run_maintenance();
```

Or write a script:
```sql
-- Drop partitions older than 90 days
DROP TABLE events_2023_10;

-- DROP partition = INSTANT (no table scan)
-- vs DELETE FROM events WHERE event_time < ... = SLOW
```

---

## 7. Partitioning Gotchas

### Gotcha 1: Unique constraints
Unique across whole table = must include partition key.
```sql
-- ❌ This doesn't enforce uniqueness across partitions
UNIQUE (id)

-- ✅ Must include partition column
UNIQUE (id, event_time)
```

### Gotcha 2: Foreign keys TO partitioned tables
Postgres 11+: Supported but with limitations.
```sql
CREATE TABLE order_items (
    order_id BIGINT REFERENCES orders (id, created_at)  -- include partition key
);
```

### Gotcha 3: All queries need partition key
Without WHERE on event_time → scans ALL partitions = slower than no partitioning!

### Gotcha 4: Default partition is dangerous
Rows that don't match any partition land in default. If you DON'T have one → INSERT fails!

### Gotcha 5: Detach + re-attach
Move data between partitions = detach old, attach new. Atomic.

---

## 8. Migration Strategy: Adopting Partitioning

You have an existing huge table. How to partition without downtime?

```sql
-- 1. Create new partitioned table
CREATE TABLE events_new (... ) PARTITION BY RANGE (event_time);
CREATE TABLE events_new_2024_01 PARTITION OF events_new
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ... etc

-- 2. Backfill in batches (avoid bloating WAL)
INSERT INTO events_new SELECT * FROM events WHERE event_time >= '2024-01-01' AND event_time < '2024-02-01';

-- 3. Set up triggers on old table → forward writes to new (during transition)
CREATE TRIGGER forward_to_new BEFORE INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION forward_insert();

-- 4. Swap tables in single transaction
BEGIN;
ALTER TABLE events RENAME TO events_old;
ALTER TABLE events_new RENAME TO events;
COMMIT;

-- 5. Drop old table after verification
DROP TABLE events_old;
```

**Tools that automate this:** `pg_partman`, `pg_repack`.

---

## 9. SHARDING — Beyond Single Server

When even partitioning doesn't help (too big for one machine):

### Sharding key = column used to determine which shard
- `user_id` (per-user data on one shard)
- `tenant_id` (per-tenant)
- `geographical region`

### Sharding strategies
1. **Range** — user_id 1-1M on shard 1, 1M-2M on shard 2
2. **Hash** — hash(user_id) % N → shard number
3. **Lookup table** — directory service tells which shard
4. **Consistent hashing** — auto-rebalance on shard add/remove

### Architectures
- **App-level sharding** — app routes queries
- **Citus** — Postgres extension that makes cluster look like single DB
- **Vitess** — sharding for MySQL (also works for Postgres)
- **CockroachDB** — Postgres-compatible, auto-sharded

---

## 10. Citus — Postgres-Native Sharding

```sql
-- Install Citus extension
CREATE EXTENSION citus;

-- Mark table as distributed
SELECT create_distributed_table('events', 'user_id');

-- Coordinator routes queries based on user_id hash
SELECT * FROM events WHERE user_id = 42;
-- → Citus sends only to shard holding user 42
```

**How Citus works:**
- Coordinator node + N worker nodes
- Each worker has subset of data (shards)
- Coordinator parses query, routes to relevant workers
- Aggregates results

**Limitations:**
- Cross-shard joins limited (must be on shard key)
- DDL must propagate to all nodes
- Costs more than vanilla Postgres

---

## 11. App-Level Sharding Example

```python
# Hash-based shard router
def get_shard(user_id: int) -> str:
    shard_num = hash(user_id) % 4
    return f"db-shard-{shard_num}"

class ShardRouter:
    def __init__(self):
        self.engines = {
            "db-shard-0": create_engine("postgresql://shard0/db"),
            "db-shard-1": create_engine("postgresql://shard1/db"),
            "db-shard-2": create_engine("postgresql://shard2/db"),
            "db-shard-3": create_engine("postgresql://shard3/db"),
        }

    def get_engine(self, user_id: int):
        return self.engines[get_shard(user_id)]
```

Cross-shard query:
```python
# Run query on all shards in parallel
async def search_all_shards(query):
    tasks = [run_on_shard(engine, query) for engine in shards]
    results = await asyncio.gather(*tasks)
    return merge(results)
```

---

## 12. Resharding (when shards fill up)

**Hardest problem in sharding.**

### Approach 1: Add more shards, rebalance
- Add shard 5, 6, 7
- Rebalance data across all shards
- Downtime or dual-write phase

### Approach 2: Consistent hashing
- Add node → only ~1/N keys move
- Less rebalancing

### Approach 3: Lookup table
- Each user → shard mapping in directory service
- Just update directory entries

### Practical tip
**Pre-shard generously.** Start with 64 logical shards on 4 physical servers. Later, move shards to new servers without rebalancing.

---

## 13. Indexes on Partitioned Tables

```sql
-- Create index on parent → propagates to all partitions
CREATE INDEX idx_events_user ON events (user_id);

-- Postgres 11+ creates corresponding index on each partition
-- Doing CONCURRENTLY on partitioned table = Postgres 12+
```

Per-partition indexes ok for different access patterns:
```sql
-- Old partitions: index on user_id (for archival queries)
CREATE INDEX ON events_2023_01 (user_id);
-- New partitions: index on user_id + status (for active queries)
CREATE INDEX ON events_2024_01 (user_id, status);
```

---

## 14. Real-World Patterns

### Pattern: Time-series with partition rotation
```sql
-- Daily partitions for hot data, monthly for cold
-- Drop partitions > 90 days old (compliance, cost)
CREATE TABLE events_2024_05_15 PARTITION OF events FOR VALUES FROM (...) TO (...);
-- After 30 days: COMPRESS by moving to slower disk
-- After 90 days: DROP TABLE
```

### Pattern: Multi-tenant by hash partition
```sql
PARTITION BY HASH (tenant_id) (16 partitions)
-- Each tenant lands on specific partition
-- Easy to detach + move noisy tenants to dedicated DB
```

### Pattern: Hot/cold separation
```sql
PARTITION BY LIST (status)
-- 'active' partition on SSD
-- 'archived' partition on cheaper storage
```

---

## 15. Interview Questions

**Q1: Partitioning vs sharding?**
Partitioning = split table within one DB. Sharding = split DB across servers.

**Q2: Range, list, hash partition kab use karte?**
Range: time-series. List: geographic/category. Hash: even distribution.

**Q3: Partition pruning kya hai?**
Optimizer skips irrelevant partitions based on WHERE clause. Query must include partition key.

**Q4: pg_partman kya karta?**
Automatic creation + dropping of partitions on schedule (e.g., monthly).

**Q5: Sharding hardest problem?**
Resharding. Adding shard = rebalancing data. Use consistent hashing or pre-shard.

**Q6: Citus vs vanilla Postgres?**
Citus = transparent sharding extension. Workers + coordinator. App sees single DB. Limits on cross-shard joins.

**Q7: Existing 500M row table partition kaise karein?**
Create new partitioned table → backfill in batches → switch via rename → drop old. Use pg_partman to automate.

---

## 16. Best Practices

1. **Pick partition key in queries** — without it, partitioning hurts
2. **Pre-create future partitions** — pg_partman premake=N
3. **DROP old partitions instead of DELETE** — instant
4. **Time-based for hot/cold data**
5. **Keep partitions reasonable size** — 10-100M rows each
6. **Indexes on partitioned table** — Postgres 11+ propagates
7. **Sharding only when partitioning insufficient**
8. **Use Citus for transparent sharding** vs app-level routing
9. **Plan resharding upfront** — over-shard initially
10. **Monitor partition sizes** — detect skew

---

## Related
- [[09_postgresql_ha_read_replicas]]
- [[13_postgresql_performance_tuning]]
- [[../../PythonBackend_SystemDesign/HLD_Code/05_consistent_hashing]]
