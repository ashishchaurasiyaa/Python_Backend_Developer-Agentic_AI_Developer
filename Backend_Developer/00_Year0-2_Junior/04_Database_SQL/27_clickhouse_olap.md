# Database — ClickHouse for OLAP Backends
**Database · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts

- **OLTP** = Online Transaction Processing (rows, lots of writes, point reads) — Postgres/MySQL territory
- **OLAP** = Online Analytical Processing (columns, scans, aggregations over billions of rows) — ClickHouse territory
- **Columnar storage** = data stored per column, not per row (compresses 10-100x better for analytics)
- **MergeTree** = ClickHouse's main table engine (sorted, columnar, partitioned)
- **Primary key** in ClickHouse = sparse index, NOT unique (different from Postgres!)
- **Skipping indexes** = secondary indexes for filtering (min-max, bloom, set)
- **Materialized view** = pre-aggregation pipeline, updates on insert
- **Replicated tables** = HA via Keeper (Raft) / ZooKeeper
- **Distributed table** = sharding across nodes

---

## When Backend Devs Need ClickHouse

```
You'll reach for ClickHouse when:
─────────────────────────────────
✓ Analytics dashboard over 100M+ events
✓ Log/metric storage at terabyte scale
✓ User behavior analytics (clicks, page views)
✓ Real-time aggregations (per-minute, per-hour)
✓ Replacing Postgres for "SELECT count(*), avg(x) GROUP BY date"
  queries that take minutes

You'll NOT use ClickHouse for:
─────────────────────────────────
✗ Transactional writes (ACID single-row)
✗ Frequent updates / deletes (eventual via mutations, slow)
✗ Row-by-row lookups (use Postgres / KV store)
✗ Joins with high cardinality (limited join engine)
```

**Common 2026 use case:** product analytics, observability backends (Signoz, Tinybird), AI usage logs, fintech transaction analytics.

---

## ClickHouse vs Postgres — Side-by-Side

| Aspect | Postgres | ClickHouse |
|---|---|---|
| Storage | Row-based | Columnar |
| Use case | OLTP | OLAP |
| Writes/sec | ~10k (single node) | ~1M+ (single node) |
| Read pattern | Point queries | Aggregation scans |
| Compression | ~3-5x | ~10-100x |
| Transactions | Full ACID | Limited (atomic inserts only) |
| Updates | Cheap | Expensive (mutation) |
| Deletes | Cheap | Expensive (TTL preferred) |
| Joins | Excellent | Limited (use denormalized) |
| Indexes | B-tree, GIN, etc. | Sparse PK + skipping |
| Best query type | `WHERE id = ?` | `GROUP BY day` |

---

## Architecture Overview

```
                  ┌──────────────┐
                  │  FastAPI App │
                  └──────┬───────┘
                         │ INSERT batches
                         ▼
       ┌──────────────────────────────────────┐
       │           ClickHouse Cluster          │
       │                                       │
       │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
       │  │Shard1│ │Shard2│ │Shard3│ │Shard4│ │
       │  │      │ │      │ │      │ │      │ │
       │  │ rep1 │ │ rep1 │ │ rep1 │ │ rep1 │ │
       │  │ rep2 │ │ rep2 │ │ rep2 │ │ rep2 │ │
       │  └──────┘ └──────┘ └──────┘ └──────┘ │
       │           ▲                            │
       │           │ Replication via            │
       │           │ ClickHouse Keeper (Raft)   │
       └──────────────────────────────────────┘
                         │
                         │ SELECT (aggregations)
                         ▼
                  ┌──────────────┐
                  │   BI / API   │
                  └──────────────┘
```

---

## Schema Design Patterns

### Pattern 1: Event Log (most common)

```sql
CREATE TABLE events
(
    event_time DateTime CODEC(Delta, ZSTD),
    user_id    UInt64,
    event_type LowCardinality(String),  -- enum-like, super-compressed
    properties Map(String, String),
    request_id String,
    session_id String,
    -- partition key
    event_date Date DEFAULT toDate(event_time)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)        -- monthly partitions
ORDER BY (event_type, user_id, event_time)  -- sort order = primary key
TTL event_date + INTERVAL 90 DAY DELETE  -- auto-cleanup
SETTINGS index_granularity = 8192;
```

Key design rules:

```
✓ PARTITION BY     → manage data in chunks (drop old, attach new)
✓ ORDER BY         → sparse index, drives query performance
                     Put HIGH-cardinality columns LAST
                     Put commonly-filtered columns FIRST
✓ LowCardinality   → use for enums (event types, statuses) — huge gains
✓ CODEC            → Delta + ZSTD for timestamps, ZSTD(1) for strings
✓ TTL              → automatic data lifecycle
✓ Granularity 8192 → default, rarely needs tuning
```

### Pattern 2: Materialized View for Real-Time Aggregation

```sql
-- Raw events
CREATE TABLE events_raw (...) ENGINE = MergeTree ...;

-- Aggregating table (stores pre-aggregated state)
CREATE TABLE events_per_hour
(
    hour DateTime,
    event_type LowCardinality(String),
    user_count AggregateFunction(uniq, UInt64),
    event_count AggregateFunction(count, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (event_type, hour);

-- Materialized view auto-updates on inserts to events_raw
CREATE MATERIALIZED VIEW events_per_hour_mv TO events_per_hour AS
SELECT
    toStartOfHour(event_time) AS hour,
    event_type,
    uniqState(user_id) AS user_count,
    countState() AS event_count
FROM events_raw
GROUP BY hour, event_type;

-- Query (must use -Merge to finalize)
SELECT
    hour,
    event_type,
    uniqMerge(user_count) AS users,
    countMerge(event_count) AS events
FROM events_per_hour
WHERE hour >= now() - INTERVAL 24 HOUR
GROUP BY hour, event_type
ORDER BY hour;
```

**Why this is magic:** dashboards over billions of events return in milliseconds because aggregation already happened.

### Pattern 3: Replacing Updates (ReplacingMergeTree)

```sql
-- ClickHouse doesn't do UPDATE well — model it as inserts
CREATE TABLE user_state
(
    user_id UInt64,
    state String,
    version DateTime DEFAULT now(),
)
ENGINE = ReplacingMergeTree(version)  -- keeps latest version on merge
ORDER BY user_id;

-- "Update" = insert new row
INSERT INTO user_state VALUES (1, 'active', now());
INSERT INTO user_state VALUES (1, 'banned', now());  -- replaces in time

-- Query with FINAL to deduplicate (slow on large data)
SELECT * FROM user_state FINAL WHERE user_id = 1;

-- OR use argMax in queries
SELECT argMax(state, version) FROM user_state WHERE user_id = 1;
```

---

## Python Integration (clickhouse-connect)

### Install

```bash
pip install clickhouse-connect
```

### FastAPI Setup

```python
# db_clickhouse.py
import clickhouse_connect
from functools import lru_cache

@lru_cache(maxsize=1)
def get_client():
    return clickhouse_connect.get_client(
        host="localhost",
        port=8123,
        username="default",
        password="...",
        database="analytics",
        compression="lz4",
        # connection pool
        pool_mgr=clickhouse_connect.driver.httputil.get_pool_manager(
            maxsize=10,
        ),
    )
```

### Batched Inserts (Critical for ClickHouse)

```python
# ✗ DON'T — one INSERT per event = throws ClickHouse into "too many parts"
async def bad_insert(event):
    client.insert("events", [event])  # ONE row insert = bad

# ✓ DO — batch via queue + flush on size or time
from collections import deque
import asyncio


class EventBuffer:
    def __init__(self, flush_size=10_000, flush_interval=5.0):
        self.buffer = deque()
        self.flush_size = flush_size
        self.flush_interval = flush_interval
        self._lock = asyncio.Lock()

    async def push(self, event: dict):
        async with self._lock:
            self.buffer.append(event)
            if len(self.buffer) >= self.flush_size:
                await self._flush_locked()

    async def flusher(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            async with self._lock:
                if self.buffer:
                    await self._flush_locked()

    async def _flush_locked(self):
        rows = list(self.buffer)
        self.buffer.clear()
        # actual insert in thread pool (clickhouse-connect is sync)
        await asyncio.to_thread(
            get_client().insert,
            "events",
            rows,
            column_names=["event_time", "user_id", "event_type", "properties"],
        )


buffer = EventBuffer()
```

### FastAPI Endpoint

```python
from fastapi import FastAPI, BackgroundTasks
from datetime import datetime

app = FastAPI()


@app.on_event("startup")
async def start_flusher():
    asyncio.create_task(buffer.flusher())


@app.post("/track")
async def track_event(payload: dict):
    await buffer.push({
        "event_time": datetime.utcnow(),
        "user_id": payload["user_id"],
        "event_type": payload["event"],
        "properties": payload.get("props", {}),
    })
    return {"queued": True}


@app.get("/analytics/users_per_hour")
async def users_per_hour():
    client = get_client()
    rows = await asyncio.to_thread(client.query, """
        SELECT
            toStartOfHour(event_time) AS hour,
            uniqExact(user_id) AS users
        FROM events
        WHERE event_time >= now() - INTERVAL 24 HOUR
        GROUP BY hour
        ORDER BY hour
    """)
    return [{"hour": str(r[0]), "users": r[1]} for r in rows.result_rows]
```

---

## Performance Patterns

### Indexing — Sparse PK + Skipping Indexes

```sql
-- Primary key is SPARSE (one entry per 8192 rows)
-- It's the sort key, not a B-tree

-- Add secondary "skipping" indexes for non-sorted columns
ALTER TABLE events
    ADD INDEX idx_request bloom_filter(request_id)
    TYPE bloom_filter(0.01) GRANULARITY 4;

ALTER TABLE events
    ADD INDEX idx_props_keys mapKeys(properties)
    TYPE bloom_filter(0.01) GRANULARITY 4;

-- Materialize index for existing data
ALTER TABLE events MATERIALIZE INDEX idx_request;
```

### Projections (Sub-Tables With Different Sort Order)

```sql
-- Add a projection — another sort order for the same data
ALTER TABLE events ADD PROJECTION user_proj
(
    SELECT user_id, event_time, event_type
    ORDER BY user_id, event_time
);

ALTER TABLE events MATERIALIZE PROJECTION user_proj;

-- ClickHouse automatically uses the projection for user-centric queries
SELECT * FROM events WHERE user_id = 42 AND event_time > now() - INTERVAL 1 DAY;
-- → uses user_proj, fast
```

### Query Performance Checklist

```
1. ✓ Filter on PK columns first (in ORDER BY order)
2. ✓ Use LowCardinality for repeated strings
3. ✓ PREWHERE on highly selective conditions (before WHERE)
4. ✓ Avoid SELECT * — only the columns you need
5. ✓ Aggregate raw data in materialized views, not on read
6. ✓ Use uniqExact only when needed — uniq (HyperLogLog) is 10x faster
7. ✓ Use sample n for approximate queries
8. ✗ Avoid JOIN with large right table — denormalize or use Dictionary
```

---

## High Availability

### Setup

```
✓ ClickHouse Keeper (replacement for ZooKeeper, ships with CH)
✓ Replicated tables (ReplicatedMergeTree)
✓ Distributed table (cluster routing)

Recommended layout:
   2 shards × 3 replicas = 6 nodes
   Keeper quorum = 3 nodes (separate or co-located)
```

### Replicated Table

```sql
CREATE TABLE events_local ON CLUSTER my_cluster
(
    event_time DateTime,
    user_id UInt64,
    event_type LowCardinality(String)
)
ENGINE = ReplicatedMergeTree(
    '/clickhouse/tables/{shard}/events',
    '{replica}'
)
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_type, user_id, event_time);


CREATE TABLE events ON CLUSTER my_cluster AS events_local
ENGINE = Distributed(my_cluster, default, events_local, rand());
```

→ Insert to `events` → automatically sharded across nodes.
→ Replicas keep each shard in sync via Keeper.

---

## Common Anti-Patterns

```
✗ Many small inserts (one row at a time)
   → "Too many parts" errors, slow merges
   ✓ Batch 10k-100k rows per insert

✗ Using ClickHouse as OLTP
   → Slow point lookups, no row-level locking
   ✓ Use Postgres for OLTP, CDC to ClickHouse

✗ Frequent UPDATE / DELETE
   → Mutations rewrite entire parts
   ✓ Use ReplacingMergeTree or CollapsingMergeTree
   ✓ Or insert "tombstones" and TTL them

✗ Wide rows (1000+ columns)
   → Slow compression, big merges
   ✓ Use Map(String, String) for sparse attributes

✗ Joining two huge tables
   → ClickHouse joins right table into memory
   ✓ Denormalize or use Dictionary

✗ ORDER BY with too many columns (10+)
   → Index granularity becomes useless
   ✓ Pick 3-5 highest-selectivity columns

✗ Not using LowCardinality for enums
   → 10x bigger storage, 5x slower queries
   ✓ ALWAYS use LowCardinality(String) for repeated values

✗ SELECT * in production
   → Reads all columns from disk
   ✓ Only the columns you need
```

---

## Ingestion Patterns

### 1. Direct from app (FastAPI buffer → CH)

```
Pros: simple
Cons: app crash loses buffer
```

### 2. Via Kafka (recommended at scale)

```
App → Kafka → Kafka Engine table → MergeTree (materialized view)
```

```sql
CREATE TABLE events_kafka
(
    raw String
)
ENGINE = Kafka(
    'kafka:9092',
    'events',
    'clickhouse-consumer',
    'JSONAsString'
);

CREATE MATERIALIZED VIEW events_mv TO events AS
SELECT
    JSONExtractInt(raw, 'user_id') AS user_id,
    parseDateTimeBestEffort(JSONExtractString(raw, 'event_time')) AS event_time,
    JSONExtractString(raw, 'event_type') AS event_type
FROM events_kafka;
```

### 3. CDC from Postgres (Debezium → Kafka → CH)

→ Replicate OLTP into OLAP automatically. See [25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md).

### 4. Bulk via S3 / Parquet

```sql
INSERT INTO events
SELECT * FROM s3('s3://my-bucket/events/*.parquet', 'Parquet');
```

---

## Operational Patterns

### Backups

```
✓ clickhouse-backup tool (https://github.com/AlexAkulov/clickhouse-backup)
✓ S3 backend supported
✓ Schedule via cron / Airflow / K8s CronJob
```

### Monitoring

```
✓ system.* tables (system.parts, system.queries, system.metrics)
✓ Prometheus endpoint on port 9363 (clickhouse-server)
✓ Grafana dashboards (official)

Key metrics to alert on:
   - DelayedInserts > 0
   - ReplicationLag > 30s
   - DiskUsage > 80%
   - "Too many parts" errors
   - QuerySlowTime p99 > SLO
```

### Schema Changes

```sql
-- ON CLUSTER spreads change across all replicas
ALTER TABLE events ON CLUSTER my_cluster ADD COLUMN extra String;

-- Mutations (UPDATE/DELETE) are async — track via system.mutations
ALTER TABLE events DELETE WHERE event_time < '2023-01-01';

SELECT * FROM system.mutations WHERE is_done = 0;
```

---

## When to Use ClickHouse vs Alternatives

```
ClickHouse        → high throughput inserts, complex aggregations, BI
DuckDB            → embedded analytics, < 1TB data, single-machine
Snowflake/BigQuery→ managed cloud, SQL warehouse, lazy ad-hoc
Druid             → real-time + sub-second response, complex
Pinot             → similar to Druid, LinkedIn-pedigree
StarRocks         → MySQL-compatible, evolving competitor
TimescaleDB       → time-series on Postgres, OLTP-OLAP hybrid
Postgres          → 100 GB analytics, hot data, complex joins
```

**Senior decision matrix:**

```
< 100 GB data + Postgres team   → stay on Postgres
< 1 TB + lots of writes         → ClickHouse self-hosted
> 1 TB + cloud-first            → BigQuery / Snowflake
Need sub-second on huge data    → Druid / Pinot
Need OLTP + analytics same DB   → TimescaleDB
```

---

## Interview Questions & Answers

### Q1: Why is ClickHouse so fast on aggregations?

**Answer:**

```
1. Columnar storage — reads only needed columns from disk
2. Compression — ZSTD/Delta gives 10-100x, less I/O
3. Vectorized execution — SIMD on column batches
4. Sparse PK — skips entire blocks quickly
5. Materialized views — pre-aggregate at insert time
6. LowCardinality — dictionary-encoded strings
7. No row overhead — no MVCC tuples, no transaction logs
```

### Q2: Why doesn't ClickHouse do UPDATEs well?

**Answer:** Mutations rewrite entire data parts. For a million-row part, updating 1 row rewrites all million. Designed for append-mostly workloads. Use `ReplacingMergeTree`, `CollapsingMergeTree`, or `VersionedCollapsingMergeTree` to model updates as inserts.

### Q3: How do you pick the ORDER BY columns?

**Answer:**

```
Rules:
   1. Most-frequently-filtered columns first
   2. Low cardinality before high cardinality
      (event_type before user_id before event_time)
   3. Time column LAST (high cardinality but useful for range)
   4. Keep ORDER BY short (3-5 columns)

Example: ORDER BY (event_type, user_id, event_time)
   ✓ Queries filtering by event_type are fastest
   ✓ Filtering by user_id within event_type is fast
   ✗ Filtering by ONLY user_id without event_type is slow
     → Add a projection or skipping index
```

### Q4: ClickHouse vs TimescaleDB — when to pick which?

**Answer:**

```
Both: time-series + analytics

ClickHouse:
   ✓ Higher throughput (10x faster inserts at scale)
   ✓ Better compression
   ✓ Pure OLAP focus
   ✗ Separate DB from OLTP — needs CDC

TimescaleDB:
   ✓ Postgres compatible — same DB for OLTP + time-series
   ✓ Easier to operate if already on Postgres
   ✓ Full SQL + joins + ACID
   ✗ Lower throughput on huge data
   ✗ Not as good at multi-billion row aggregations

Rule: < 1 TB time-series + Postgres team → TimescaleDB
      > 1 TB time-series + dedicated team → ClickHouse
```

### Q5: How do you handle GDPR / DPDP "right to delete" in ClickHouse?

**Answer:**

```python
# ClickHouse DELETEs are slow (mutations)
# Strategies:

# 1. Soft delete: insert tombstone
INSERT INTO events VALUES (..., is_deleted=true)

# 2. Lightweight DELETE (CH 23.x+)
DELETE FROM events WHERE user_id = 12345;
# → uses _row_exists column, fast

# 3. TTL by user (advanced)
ALTER TABLE events MODIFY TTL
    event_date + INTERVAL 90 DAY DELETE
    WHERE NOT marked_for_retention;

# 4. Partition drop (fastest if data partitioned per user/tenant)
ALTER TABLE events DROP PARTITION 'user_12345';
```

For DPDP, document the deletion process in your data inventory.

### Q6: How do you scale ClickHouse beyond a single node?

**Answer:**

```
Vertical first:
   ✓ Add CPU + RAM + NVMe SSD
   ✓ Single node handles ~10 TB easily

Then shard:
   1. Set up Keeper (3+ nodes for quorum)
   2. ReplicatedMergeTree on each shard (2-3 replicas)
   3. Distributed table for routing
   4. Sharding key: high-cardinality, well-distributed
                    (e.g., cityHash64(user_id))

Common topology:
   - 4 shards × 3 replicas = 12 data nodes
   - 3 keeper nodes (separate)
   - Handles ~100 TB
```

### Q7: How do you keep Postgres and ClickHouse in sync?

**Answer:**

```
Pattern: CDC pipeline

Postgres (OLTP)
    ↓ WAL stream
Debezium (Kafka Connect)
    ↓ events
Kafka topic
    ↓ Kafka Engine table
ClickHouse
    ↓ MATERIALIZED VIEW
Analytics tables (deduplicated, transformed)

Considerations:
   ✓ Latency: 1-10s typically
   ✓ Idempotency: use ReplacingMergeTree with event timestamp
   ✓ Backfill: initial snapshot from Postgres dump
   ✓ Monitoring: replication lag in Debezium
```

### Q8: Production gotchas you've hit?

**Answer:** (Common interview probe)

```
1. "Too many parts" error
   Cause: inserting too frequently (small batches)
   Fix: increase batch size, lower insert frequency

2. Slow query on filter not in ORDER BY
   Cause: full table scan
   Fix: add skipping index, projection, or change ORDER BY

3. Disk filled by old parts
   Cause: TTL not configured
   Fix: ALTER TABLE ... MODIFY TTL

4. Replication lag growing
   Cause: slow merges or Keeper issues
   Fix: check system.replication_queue, scale Keeper

5. Quorum write failures
   Cause: replicas down
   Fix: insert_quorum=1 (less safe) or fix replica

6. Memory exceeded on JOIN
   Cause: large right table loaded fully
   Fix: switch to Dictionary or denormalize

7. Query returns wrong count after UPDATE
   Cause: mutation not yet applied
   Fix: SELECT ... FINAL or check system.mutations
```

---

## Senior Mantras

```
1. Insert in batches. ClickHouse hates many small inserts.

2. Pick ORDER BY columns based on QUERY patterns, not data shape.

3. LowCardinality for repeated strings — always.

4. Don't UPDATE. Model as inserts + ReplacingMergeTree.

5. Materialized views = pre-aggregation = millisecond dashboards.

6. Use ClickHouse for OLAP. Postgres for OLTP. Don't mix.

7. Plan partitions for data lifecycle (DROP PARTITION = O(1) cleanup).

8. Monitor system.parts, system.mutations, system.replication_queue.

9. For "delete user data" (DPDP/GDPR), use lightweight DELETE or partition drop.

10. Production deploy = Keeper quorum + Replicated tables + Distributed table.
```

---

## Resources

```
✓ https://clickhouse.com/docs — official, excellent
✓ https://github.com/ClickHouse/clickhouse-connect — Python client
✓ Altinity blog — production patterns
✓ ClickHouse YouTube — query optimization talks
✓ system.* tables — best self-diagnostic source
```

---

## Related Topics

- [08_cap_theorem_db_selection.md](08_cap_theorem_db_selection.md) — when to choose ClickHouse
- [17_timescaledb_timeseries.md](17_timescaledb_timeseries.md) — alternative for time-series
- [25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md) — CDC pipeline to ClickHouse
- [28_vector_databases_comparison.md](28_vector_databases_comparison.md) — sister doc
- [../01_Year3-4_Mid/07_Kafka/](../../01_Year3-4_Mid/07_Kafka) — Kafka feeding ClickHouse
- [../01_Year3-4_Mid/04_DevOps/](../../01_Year3-4_Mid/04_DevOps) — observability stacks built on ClickHouse
