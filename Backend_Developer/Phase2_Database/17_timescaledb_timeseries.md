# TimescaleDB — Time-Series in PostgreSQL

> **Interview angle:** "IoT sensors 100K events/sec. InfluxDB ya Postgres? Both have limits."
>
> Answer: **TimescaleDB** = Postgres + time-series superpowers.

---

## 1. Why Time-Series Needs Special Handling

Time-series data:
- **Append-only** (rarely update old data)
- **Huge volume** (sensors, metrics, logs)
- **Time-based queries** (last hour, day, week)
- **Aggregations** (avg per minute, 95th percentile)

Vanilla Postgres struggles at:
- 100M+ rows in one table
- Time-range queries slow without partitioning
- Storage costs balloon

---

## 2. TimescaleDB = Postgres Extension

```sql
CREATE EXTENSION timescaledb;
```

Adds:
- **Hypertables** = auto-partitioned tables by time
- **Continuous aggregates** = materialized views that update
- **Compression** (10-100x storage savings)
- **Data retention policies**
- **Time-bucket functions**

You write **regular SQL**. TimescaleDB transparently partitions.

---

## 3. Hypertable Setup

```sql
-- Create regular table
CREATE TABLE sensor_data (
    time TIMESTAMPTZ NOT NULL,
    sensor_id INT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION
);

-- Convert to hypertable (auto-partitions by time)
SELECT create_hypertable('sensor_data', 'time');

-- Custom chunk interval (default: 7 days)
SELECT create_hypertable(
    'sensor_data',
    'time',
    chunk_time_interval => INTERVAL '1 day'
);
```

Now Postgres creates **chunks** (child partitions) per time interval.
Queries on time range hit only relevant chunks.

---

## 4. Inserting Data

Same as regular Postgres:
```sql
INSERT INTO sensor_data (time, sensor_id, temperature) VALUES
    (NOW(), 1, 23.5),
    (NOW() - INTERVAL '1 minute', 1, 23.3);

-- Bulk insert (fastest)
COPY sensor_data FROM '/data/sensors.csv' WITH (FORMAT csv);

-- Python
from psycopg2.extras import execute_values
execute_values(cur, "INSERT INTO sensor_data VALUES %s", batch)
```

TimescaleDB sustained ingest: **1M+ rows/sec** with proper config.

---

## 5. Time-Bucket Aggregations

```sql
-- Average temperature per hour
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    AVG(temperature) AS avg_temp,
    MAX(temperature) AS max_temp,
    MIN(temperature) AS min_temp
FROM sensor_data
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY hour, sensor_id
ORDER BY hour DESC;

-- Sub-minute granularity
time_bucket('15 seconds', time)
time_bucket('1 minute',  time)
time_bucket('5 minutes', time)
time_bucket('1 day',     time)
```

---

## 6. Continuous Aggregates (Materialized View)

Pre-computed aggregations, auto-refreshed.

```sql
-- Create continuous aggregate
CREATE MATERIALIZED VIEW sensor_data_hourly
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time) AS hour,
        sensor_id,
        AVG(temperature) AS avg_temp,
        MIN(temperature) AS min_temp,
        MAX(temperature) AS max_temp,
        COUNT(*) AS sample_count
    FROM sensor_data
    GROUP BY hour, sensor_id
    WITH NO DATA;

-- Refresh policy (auto-refresh)
SELECT add_continuous_aggregate_policy('sensor_data_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- Query is fast — uses pre-computed
SELECT * FROM sensor_data_hourly
WHERE hour > NOW() - INTERVAL '7 days';
```

**Performance:** 1000x faster than raw aggregation on huge tables.

---

## 7. Compression

Old data compressed 10-100x with columnar format.

```sql
-- Enable compression on hypertable
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'sensor_id',     -- group by this
    timescaledb.compress_orderby = 'time DESC'         -- order within
);

-- Compress chunks older than 7 days
SELECT add_compression_policy('sensor_data', INTERVAL '7 days');

-- Check compression ratio
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) AS before,
    pg_size_pretty(after_compression_total_bytes) AS after,
    ROUND(before_compression_total_bytes::numeric / after_compression_total_bytes, 2) AS ratio
FROM hypertable_compression_stats('sensor_data');
-- Result: 10-100x compression typical
```

**Note:** Compressed chunks are queryable but slower to UPDATE.

---

## 8. Data Retention Policies

```sql
-- Drop data older than 30 days
SELECT add_retention_policy('sensor_data', INTERVAL '30 days');

-- Manually drop chunks older than N
SELECT drop_chunks('sensor_data', INTERVAL '90 days');
```

Drop chunks is **instant** (vs DELETE which is slow + bloat).

---

## 9. Hierarchical Aggregation Pattern

Best practice for IoT/metrics:

```
Raw data (5min retention)
  → 1-minute continuous aggregate (1-day retention)
    → 1-hour continuous aggregate (7-day retention)
      → 1-day continuous aggregate (1-year retention)
```

```sql
-- Tier 1: raw (5min retention)
CREATE TABLE metrics (...);
SELECT add_retention_policy('metrics', INTERVAL '5 minutes');

-- Tier 2: 1-minute aggregate
CREATE MATERIALIZED VIEW metrics_1m WITH (timescaledb.continuous) AS
    SELECT time_bucket('1 minute', time) AS time, ...

-- Tier 3: 1-hour aggregate
CREATE MATERIALIZED VIEW metrics_1h WITH (timescaledb.continuous) AS
    SELECT time_bucket('1 hour', time) AS time, ...

-- Tier 4: 1-day aggregate (kept forever)
```

---

## 10. Advanced Functions

```sql
-- TIME-WEIGHTED AVERAGE (better than simple AVG for irregular intervals)
SELECT time_bucket('1 hour', time) AS hour,
       time_weight('LOCF', time, temperature) AS weighted_avg
FROM sensor_data
GROUP BY hour;

-- GAP FILL (handle missing data points)
SELECT
    time_bucket_gapfill('1 minute', time) AS minute,
    sensor_id,
    AVG(temperature),
    -- LOCF = Last Observation Carried Forward
    interpolate(AVG(temperature)) AS interpolated_temp
FROM sensor_data
WHERE time > NOW() - INTERVAL '1 day'
GROUP BY minute, sensor_id;

-- FIRST / LAST in time window
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    first(temperature, time) AS first_reading,
    last(temperature, time) AS last_reading
FROM sensor_data
GROUP BY hour, sensor_id;

-- PERCENTILES (with TimescaleDB Toolkit)
SELECT
    time_bucket('1 hour', time) AS hour,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY response_time) AS p95
FROM api_requests
GROUP BY hour;

-- COUNT_MIN_SKETCH (approximate top-K)
SELECT toolkit_experimental.count_min_sketch(value, 0.01, 0.99)
FROM events;
```

---

## 11. Real-World Example: API Metrics

```sql
-- Schema
CREATE TABLE api_metrics (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint TEXT NOT NULL,
    method TEXT,
    status_code INT,
    duration_ms NUMERIC,
    user_id BIGINT
);

SELECT create_hypertable('api_metrics', 'time',
    chunk_time_interval => INTERVAL '1 hour'
);

CREATE INDEX ON api_metrics (endpoint, time DESC);

-- Hourly aggregate
CREATE MATERIALIZED VIEW api_metrics_hourly WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time) AS hour,
        endpoint,
        method,
        COUNT(*) AS request_count,
        AVG(duration_ms) AS avg_duration,
        percentile_cont(0.5)  WITHIN GROUP (ORDER BY duration_ms) AS p50,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
        SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors
    FROM api_metrics
    GROUP BY hour, endpoint, method;

-- Refresh every 5 min
SELECT add_continuous_aggregate_policy('api_metrics_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'
);

-- Retention: raw 7 days, hourly 1 year
SELECT add_retention_policy('api_metrics', INTERVAL '7 days');
SELECT add_compression_policy('api_metrics', INTERVAL '1 day');

-- Query: p99 latency by endpoint last 24h
SELECT endpoint, AVG(p99) AS avg_p99
FROM api_metrics_hourly
WHERE hour > NOW() - INTERVAL '24 hours'
GROUP BY endpoint
ORDER BY avg_p99 DESC;
```

---

## 12. Python: SQLAlchemy

```python
from sqlalchemy import Column, BigInteger, DateTime, Float, String, Integer, Index, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SensorReading(Base):
    __tablename__ = "sensor_data"
    time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    sensor_id = Column(Integer, nullable=False, primary_key=True)
    temperature = Column(Float)
    humidity = Column(Float)


# Setup hypertable (after creating)
def setup_timescale(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.execute(text("""
            SELECT create_hypertable(
                'sensor_data', 'time',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            )
        """))


# Bulk insert (FAST)
from psycopg2.extras import execute_values

def bulk_insert(conn, readings):
    cur = conn.cursor()
    execute_values(
        cur,
        "INSERT INTO sensor_data (time, sensor_id, temperature) VALUES %s",
        [(r.time, r.sensor_id, r.temperature) for r in readings],
        page_size=10000,
    )
    conn.commit()


# Async with asyncpg
async def bulk_insert_async(pool, readings):
    async with pool.acquire() as conn:
        await conn.copy_records_to_table(
            "sensor_data",
            records=[(r.time, r.sensor_id, r.temperature) for r in readings],
            columns=["time", "sensor_id", "temperature"],
        )
```

---

## 13. TimescaleDB vs Alternatives

| Tool | Pros | Cons |
|---|---|---|
| **TimescaleDB** | SQL, ACID, joins with relational data, free | Vertical scaling first |
| **InfluxDB** | Purpose-built TSDB, fast | Custom query lang, ops |
| **Prometheus** | Built-in metrics ecosystem | Local-only, 15-day default |
| **ClickHouse** | Columnar, fast analytics | Complex setup |
| **AWS Timestream** | Managed, serverless | AWS lock-in, cost |
| **Apache Druid** | Real-time analytics, fast | Heavy stack |

**Choose TimescaleDB when:**
- Already using Postgres
- Need ACID + joins with other tables
- Want SQL (no custom query language)
- Time-series < 10TB

---

## 14. Performance Tuning

### Chunk size sweet spot
- Too small → many chunks, planning overhead
- Too large → slow scans
- **Rule:** chunk_time_interval such that each chunk fits in `shared_buffers / 2`

```sql
-- Inspect chunk sizes
SELECT
    chunk_name,
    pg_size_pretty(total_bytes) AS size,
    range_start, range_end
FROM chunk_relation_size('sensor_data');
```

### Indexes on hypertables
```sql
-- Created on all chunks
CREATE INDEX ON sensor_data (sensor_id, time DESC);
```

### Parallel queries
```sql
SET max_parallel_workers_per_gather = 4;
-- Aggregations parallelize across chunks
```

---

## 15. Migration Path

From regular table:
```sql
-- Step 1: Add timestamp column if not exists
ALTER TABLE events ADD COLUMN time TIMESTAMPTZ DEFAULT NOW();

-- Step 2: Convert
SELECT create_hypertable('events', 'time',
    migrate_data => TRUE,         -- migrates existing rows
    chunk_time_interval => INTERVAL '1 day'
);
```

From InfluxDB:
```bash
# Use Telegraf with PostgreSQL output
# Or write migration script
```

---

## 16. Backup Strategy

```sql
-- Per-chunk backup
SELECT show_chunks('sensor_data', older_than => INTERVAL '30 days');

-- Export single chunk
COPY (
    SELECT * FROM sensor_data WHERE time < '2024-01-01'
) TO '/backup/sensor_2023.csv';

-- Or pg_dump for full backup (with TimescaleDB metadata)
pg_dump -d mydb -Fc -f backup.dump
```

---

## 17. Common Pitfalls

### Pitfall 1: Updates on compressed chunks
Slow. Decompress, update, recompress.
**Best practice:** Treat time-series as append-only.

### Pitfall 2: Too small chunks
1-hour chunks for low-volume data = 8760 chunks/year = planning overhead.

### Pitfall 3: Missing time-based predicates
```sql
-- ❌ Scans ALL chunks
SELECT * FROM sensor_data WHERE sensor_id = 42;

-- ✅ Scans only relevant
SELECT * FROM sensor_data
WHERE sensor_id = 42 AND time > NOW() - INTERVAL '1 day';
```

### Pitfall 4: JOIN with non-time-bucketed data
```sql
-- ❌ Bad — joins large table with sensor_data
SELECT * FROM sensor_data JOIN sensors ON ...

-- ✅ Filter first
SELECT * FROM sensor_data
WHERE time > NOW() - INTERVAL '1 hour'
JOIN sensors ON ...
```

### Pitfall 5: Not using continuous aggregates
Hitting raw 1B-row hypertable for every dashboard query.

---

## 18. Interview Questions

**Q1: TimescaleDB kya hai?**
Postgres extension for time-series. Auto-partitions by time (hypertables), columnar compression, continuous aggregates.

**Q2: Hypertable kya?**
Auto-partitioned table by time. Each partition = chunk. Queries hit only relevant chunks.

**Q3: Continuous aggregates?**
Materialized views that auto-refresh. Pre-computed time-bucket aggregations. 1000x faster than raw scans.

**Q4: Compression ratio?**
10-100x with columnar format. Best for old, repeated data.

**Q5: TimescaleDB vs InfluxDB?**
TimescaleDB = SQL, ACID, joins. InfluxDB = custom query lang, purpose-built.

**Q6: Chunk size?**
Match `shared_buffers / 2`. Default 7 days OK for moderate volume.

**Q7: When NOT to use?**
- Pure analytics (use ClickHouse)
- Need < 1s real-time (use Druid/Pinot)
- No time dimension at all (regular Postgres)

---

## 19. Best Practices

1. **Always include time** in WHERE clauses (chunk pruning)
2. **Continuous aggregates** for dashboard queries
3. **Compression** for data > 7 days old
4. **Retention policies** to control storage
5. **Hierarchical aggregation** (1m → 1h → 1d)
6. **Bulk insert** via COPY (10x faster than INSERT)
7. **Chunk size** matched to memory
8. **Treat as append-only** — no updates
9. **Index by (entity, time)** for entity-specific queries
10. **Use Toolkit functions** for percentiles, gap-fill

---

## Related
- [[01_postgresql_advanced]]
- [[10_postgresql_partitioning_sharding]]
- [[13_postgresql_performance_tuning]]
