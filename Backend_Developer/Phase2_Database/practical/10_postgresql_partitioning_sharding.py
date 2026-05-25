"""
============================================================
POSTGRESQL PARTITIONING + SHARDING — Practical
============================================================
Includes:
1. SQL templates for range/list/hash partitioning
2. Auto-partition management with pg_partman
3. Migration script (existing huge table → partitioned)
4. App-level sharding router (Python)
5. Citus extension usage

All SQL templates are runnable on Postgres 14+
"""


# ============================================================
# 1. RANGE PARTITIONING — Time-series events
# ============================================================
RANGE_PARTITION_SQL = """
-- Parent table (no data, just schema)
CREATE TABLE events (
    id BIGSERIAL,
    event_time TIMESTAMPTZ NOT NULL,
    user_id INT NOT NULL,
    event_type TEXT,
    data JSONB,
    PRIMARY KEY (id, event_time)   -- must include partition key!
) PARTITION BY RANGE (event_time);

-- Monthly partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE events_2024_03 PARTITION OF events
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

-- Default partition catches rows that don't match
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Indexes — propagate to all partitions
CREATE INDEX ON events (user_id);
CREATE INDEX ON events (event_type);
CREATE INDEX ON events USING GIN (data);

-- Query with partition pruning
EXPLAIN ANALYZE
SELECT count(*) FROM events
WHERE event_time >= '2024-01-15' AND event_time < '2024-01-20';
-- ↑ Only scans events_2024_01 (NOT all partitions)
"""


# ============================================================
# 2. LIST PARTITIONING — by country
# ============================================================
LIST_PARTITION_SQL = """
CREATE TABLE orders (
    id BIGSERIAL,
    country_code TEXT NOT NULL,
    amount NUMERIC,
    created_at TIMESTAMPTZ,
    PRIMARY KEY (id, country_code)
) PARTITION BY LIST (country_code);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US');
CREATE TABLE orders_in PARTITION OF orders FOR VALUES IN ('IN');
CREATE TABLE orders_eu PARTITION OF orders
    FOR VALUES IN ('DE', 'FR', 'IT', 'ES', 'NL');
CREATE TABLE orders_other PARTITION OF orders DEFAULT;

-- Different storage strategy per region!
ALTER TABLE orders_us SET TABLESPACE fast_ssd;
ALTER TABLE orders_eu SET TABLESPACE eu_compliant_storage;
"""


# ============================================================
# 3. HASH PARTITIONING — even distribution
# ============================================================
HASH_PARTITION_SQL = """
CREATE TABLE users (
    id BIGSERIAL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id)
) PARTITION BY HASH (id);

-- 8 partitions for parallelism
DO $$
BEGIN
    FOR i IN 0..7 LOOP
        EXECUTE format(
            'CREATE TABLE users_p%s PARTITION OF users
             FOR VALUES WITH (MODULUS 8, REMAINDER %s)',
            i, i
        );
    END LOOP;
END $$;

-- Even data distribution check
SELECT
    schemaname || '.' || tablename AS partition,
    pg_size_pretty(pg_relation_size(schemaname || '.' || tablename))
FROM pg_tables
WHERE tablename LIKE 'users_p%'
ORDER BY tablename;
"""


# ============================================================
# 4. SUBPARTITIONING — range + hash
# ============================================================
SUBPARTITION_SQL = """
-- Outer: by month
-- Inner: by hash of user_id
CREATE TABLE logs (
    id BIGSERIAL,
    user_id INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    message TEXT,
    PRIMARY KEY (id, created_at, user_id)
) PARTITION BY RANGE (created_at);

CREATE TABLE logs_2024_05 PARTITION OF logs
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01')
    PARTITION BY HASH (user_id);

-- 4 sub-partitions for May 2024
CREATE TABLE logs_2024_05_h0 PARTITION OF logs_2024_05
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE logs_2024_05_h1 PARTITION OF logs_2024_05
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE logs_2024_05_h2 PARTITION OF logs_2024_05
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE logs_2024_05_h3 PARTITION OF logs_2024_05
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);
"""


# ============================================================
# 5. PG_PARTMAN — automatic partition management
# ============================================================
PG_PARTMAN_SQL = """
-- Install extension
CREATE EXTENSION pg_partman;

-- Setup automatic monthly partitions for events
SELECT partman.create_parent(
    p_parent_table => 'public.events',
    p_control => 'event_time',
    p_type => 'native',
    p_interval => '1 month',
    p_premake => 4,           -- pre-create 4 future months
    p_start_partition => '2024-01-01'
);

-- Configure retention (drop partitions older than 6 months)
UPDATE partman.part_config
SET retention = '6 months',
    retention_keep_table = false
WHERE parent_table = 'public.events';

-- Run maintenance (call this from cron every hour)
SELECT partman.run_maintenance();

-- View what will be created/dropped
SELECT * FROM partman.show_partitions('public.events');
"""


# ============================================================
# 6. MIGRATION: Existing huge table → Partitioned
# ============================================================
MIGRATION_STRATEGY = """
-- STEP 1: Create new partitioned table (different name)
CREATE TABLE events_new (...)
PARTITION BY RANGE (event_time);

-- Create initial partitions covering existing data range
CREATE TABLE events_new_2023_q1 PARTITION OF events_new
    FOR VALUES FROM ('2023-01-01') TO ('2023-04-01');
-- ... etc for all months

-- STEP 2: Backfill in batches (avoid huge transactions)
DO $$
DECLARE
    chunk_start TIMESTAMPTZ := '2023-01-01';
    chunk_end TIMESTAMPTZ;
BEGIN
    WHILE chunk_start < now() LOOP
        chunk_end := chunk_start + INTERVAL '1 day';
        INSERT INTO events_new
        SELECT * FROM events
        WHERE event_time >= chunk_start AND event_time < chunk_end;
        chunk_start := chunk_end;
        COMMIT;       -- release locks, free WAL
    END LOOP;
END $$;

-- STEP 3: Dual-write during transition (via trigger)
CREATE OR REPLACE FUNCTION events_dual_write() RETURNS trigger AS $$
BEGIN
    INSERT INTO events_new VALUES (NEW.*);
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER events_dual_write_trg
    AFTER INSERT ON events
    FOR EACH ROW EXECUTE FUNCTION events_dual_write();

-- STEP 4: Verify counts match
SELECT
    (SELECT count(*) FROM events) AS old_count,
    (SELECT count(*) FROM events_new) AS new_count;

-- STEP 5: Swap atomically
BEGIN;
DROP TRIGGER events_dual_write_trg ON events;
ALTER TABLE events RENAME TO events_old;
ALTER TABLE events_new RENAME TO events;
COMMIT;

-- STEP 6: After verification, drop old
DROP TABLE events_old;
"""


# ============================================================
# 7. PARTITION HEALTH MONITORING
# ============================================================
PARTITION_HEALTH_SQL = """
-- Partition sizes
SELECT
    parent.relname AS parent_table,
    child.relname AS partition,
    pg_size_pretty(pg_relation_size(child.oid)) AS size,
    pg_stat_get_live_tuples(child.oid) AS live_rows
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
ORDER BY pg_relation_size(child.oid) DESC;

-- Partition skew detection (if hash partitioning)
SELECT
    tablename,
    pg_size_pretty(pg_relation_size(tablename::regclass)),
    pg_relation_size(tablename::regclass) AS bytes
FROM pg_tables
WHERE tablename LIKE 'users_p%'
ORDER BY bytes DESC;
"""


# ============================================================
# 8. APP-LEVEL SHARDING ROUTER (Python)
# ============================================================
import hashlib
import asyncio
from dataclasses import dataclass


@dataclass
class ShardConfig:
    name: str
    connection_url: str


class HashShardRouter:
    """Route requests to specific shard based on shard key hash."""

    def __init__(self, shards: list[ShardConfig]):
        self.shards = shards
        self.n = len(shards)

    def get_shard(self, key) -> ShardConfig:
        h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        return self.shards[h % self.n]

    def get_engine_url(self, key) -> str:
        return self.get_shard(key).connection_url


class RangeShardRouter:
    """Route by ID ranges."""

    def __init__(self, ranges: list[tuple[int, int, ShardConfig]]):
        self.ranges = sorted(ranges, key=lambda x: x[0])

    def get_shard(self, key: int) -> ShardConfig:
        for low, high, shard in self.ranges:
            if low <= key < high:
                return shard
        raise ValueError(f"No shard for key {key}")


def demo_shard_routing():
    shards = [
        ShardConfig("shard-0", "postgresql://shard0/db"),
        ShardConfig("shard-1", "postgresql://shard1/db"),
        ShardConfig("shard-2", "postgresql://shard2/db"),
        ShardConfig("shard-3", "postgresql://shard3/db"),
    ]

    router = HashShardRouter(shards)
    print("=" * 60)
    print("HASH-BASED SHARDING DEMO")
    print("=" * 60)
    for user_id in range(1, 11):
        shard = router.get_shard(user_id)
        print(f"  user_id={user_id:3d} → {shard.name}")

    # Range-based
    range_router = RangeShardRouter([
        (1, 1_000_000, shards[0]),
        (1_000_000, 2_000_000, shards[1]),
        (2_000_000, 3_000_000, shards[2]),
        (3_000_000, 10_000_000, shards[3]),
    ])
    print("\nRange-based:")
    for user_id in [500_000, 1_500_000, 2_500_000, 5_000_000]:
        print(f"  user_id={user_id:8d} → {range_router.get_shard(user_id).name}")


# ============================================================
# 9. CROSS-SHARD QUERIES (Scatter-Gather)
# ============================================================
async def query_all_shards(shards, sql):
    """Run same query on all shards, aggregate results."""
    async def run_one(shard):
        # await engine.execute(sql)
        return f"results from {shard.name}"

    tasks = [run_one(s) for s in shards]
    return await asyncio.gather(*tasks)


# ============================================================
# 10. CITUS — Transparent Sharding
# ============================================================
CITUS_SETUP = """
-- On coordinator node
CREATE EXTENSION citus;

-- Add worker nodes
SELECT * FROM master_add_node('worker-1', 5432);
SELECT * FROM master_add_node('worker-2', 5432);
SELECT * FROM master_add_node('worker-3', 5432);

-- Distribute a table (by user_id hash)
SELECT create_distributed_table('events', 'user_id');

-- Reference table (small, replicated to all workers)
SELECT create_reference_table('countries');

-- Now queries work like single Postgres
SELECT count(*) FROM events;           -- aggregated across all workers
SELECT * FROM events WHERE user_id = 42;  -- routed to one worker

-- View distribution
SELECT * FROM citus_shards;
"""


# ============================================================
# 11. RESHARDING STRATEGIES
# ============================================================
RESHARDING_NOTES = """
RESHARDING PATTERNS:

1. ADD MORE SHARDS + REBALANCE (downtime)
   - Add shard 5, 6, 7
   - For each row: compute new shard, move it
   - Read-only mode during reshard

2. CONSISTENT HASHING
   - Add node → only ~1/N keys move
   - Use hash ring, virtual nodes
   - See: PythonBackend_SystemDesign/HLD_Code/05_consistent_hashing

3. DOUBLE-WRITE PATTERN (zero downtime)
   - Phase 1: Write to old AND new sharding scheme
   - Phase 2: Backfill old data to new shards
   - Phase 3: Switch reads to new
   - Phase 4: Stop writing to old

4. PRE-SHARD OVERPROVISIONING
   - Create 64 logical shards on 4 physical servers
   - Each server hosts 16 shards
   - Add server → move shards (no resharding!)
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_shard_routing()

    print("\n" + "=" * 60)
    print("SQL TEMPLATES")
    print("=" * 60)
    print("\n--- RANGE PARTITIONING ---")
    print(RANGE_PARTITION_SQL)
    print("\n--- HASH PARTITIONING ---")
    print(HASH_PARTITION_SQL)
    print("\n--- PG_PARTMAN AUTO-MANAGEMENT ---")
    print(PG_PARTMAN_SQL)
    print("\n--- MIGRATION STRATEGY ---")
    print(MIGRATION_STRATEGY)
    print("\n--- CITUS SETUP ---")
    print(CITUS_SETUP)
    print("\n--- RESHARDING ---")
    print(RESHARDING_NOTES)
