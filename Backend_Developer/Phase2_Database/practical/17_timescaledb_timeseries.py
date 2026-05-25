"""
============================================================
TIMESCALEDB TIME-SERIES — Practical
============================================================
Setup:
    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password \\
        timescale/timescaledb:latest-pg16

    pip install psycopg2-binary asyncpg sqlalchemy
"""


# ============================================================
# 1. SETUP HYPERTABLE
# ============================================================
SETUP_SQL = """
-- Install extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

-- Sensor data table
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    sensor_id INT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION
);

-- Convert to hypertable
SELECT create_hypertable(
    'sensor_data',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Index (created on all chunks automatically)
CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_time
    ON sensor_data (sensor_id, time DESC);

-- Inspect
SELECT * FROM timescaledb_information.hypertables;
SELECT * FROM chunks_detailed_size('sensor_data');
"""


# ============================================================
# 2. BULK INSERT
# ============================================================
BULK_INSERT_PYTHON = '''
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import random

conn = psycopg2.connect("postgresql://postgres:password@localhost/postgres")

# Method 1: execute_values (fast)
def bulk_insert_sensors(conn, batch_size=10000):
    cur = conn.cursor()
    base = datetime.utcnow()
    rows = [
        (
            base - timedelta(seconds=i),
            random.randint(1, 100),
            20 + random.uniform(0, 10),
            50 + random.uniform(0, 20),
            1000 + random.uniform(-50, 50),
        )
        for i in range(batch_size)
    ]
    execute_values(
        cur,
        """INSERT INTO sensor_data (time, sensor_id, temperature, humidity, pressure)
           VALUES %s""",
        rows,
        page_size=1000,
    )
    conn.commit()


# Method 2: COPY (fastest)
def bulk_copy_sensors(conn, n_rows=100000):
    import io
    buffer = io.StringIO()
    base = datetime.utcnow()
    for i in range(n_rows):
        t = base - timedelta(seconds=i)
        buffer.write(f"{t}\\t{i % 100}\\t{20 + random.uniform(0, 10)}\\n")

    buffer.seek(0)
    cur = conn.cursor()
    cur.copy_from(
        buffer, "sensor_data",
        columns=["time", "sensor_id", "temperature"],
    )
    conn.commit()


# Async with asyncpg (best for high-volume real-time)
import asyncpg

async def async_bulk_insert(pool, readings):
    async with pool.acquire() as conn:
        await conn.copy_records_to_table(
            "sensor_data",
            records=[(r["time"], r["sensor_id"], r["temperature"])
                     for r in readings],
            columns=["time", "sensor_id", "temperature"],
        )

# Typical: 100K-1M rows/sec sustained
'''


# ============================================================
# 3. TIME-BUCKET AGGREGATIONS
# ============================================================
AGGREGATIONS = """
-- ===== AVG/MIN/MAX PER HOUR =====
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    AVG(temperature) AS avg_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) AS max_temp,
    COUNT(*) AS samples
FROM sensor_data
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY hour, sensor_id
ORDER BY hour DESC;

-- ===== PERCENTILES =====
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY temperature) AS p50,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY temperature) AS p95,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY temperature) AS p99
FROM sensor_data
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour, sensor_id;

-- ===== FIRST / LAST IN BUCKET =====
SELECT
    time_bucket('1 day', time) AS day,
    sensor_id,
    first(temperature, time) AS first_reading,
    last(temperature, time) AS last_reading
FROM sensor_data
GROUP BY day, sensor_id;

-- ===== GAP FILL (handle missing data) =====
SELECT
    time_bucket_gapfill(
        '1 minute', time,
        start := NOW() - INTERVAL '1 hour',
        finish := NOW()
    ) AS minute,
    sensor_id,
    AVG(temperature) AS temp,
    interpolate(AVG(temperature)) AS interpolated_temp,
    locf(AVG(temperature)) AS last_known_temp
FROM sensor_data
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY minute, sensor_id
ORDER BY minute;
"""


# ============================================================
# 4. CONTINUOUS AGGREGATES
# ============================================================
CONTINUOUS_AGGREGATES = """
-- ===== CREATE CONTINUOUS AGGREGATE (auto-refreshed materialized view) =====
CREATE MATERIALIZED VIEW sensor_data_hourly
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time) AS hour,
        sensor_id,
        AVG(temperature) AS avg_temp,
        MIN(temperature) AS min_temp,
        MAX(temperature) AS max_temp,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY temperature) AS p95_temp,
        COUNT(*) AS sample_count
    FROM sensor_data
    GROUP BY hour, sensor_id
    WITH NO DATA;   -- don't populate yet

-- ===== REFRESH POLICY (auto-update) =====
SELECT add_continuous_aggregate_policy('sensor_data_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- ===== MANUAL REFRESH =====
CALL refresh_continuous_aggregate(
    'sensor_data_hourly',
    NOW() - INTERVAL '1 day',
    NOW()
);

-- ===== QUERY (instant — uses pre-computed) =====
SELECT * FROM sensor_data_hourly
WHERE hour > NOW() - INTERVAL '7 days'
ORDER BY hour DESC;

-- ===== NESTED HIERARCHY =====
-- Daily aggregate from hourly aggregate
CREATE MATERIALIZED VIEW sensor_data_daily
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 day', hour) AS day,
        sensor_id,
        AVG(avg_temp) AS avg_temp,
        MAX(max_temp) AS max_temp
    FROM sensor_data_hourly
    GROUP BY day, sensor_id
    WITH NO DATA;
"""


# ============================================================
# 5. COMPRESSION
# ============================================================
COMPRESSION_SETUP = """
-- ===== ENABLE COMPRESSION =====
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'sensor_id',
    timescaledb.compress_orderby = 'time DESC'
);

-- ===== AUTO-COMPRESS OLD CHUNKS =====
SELECT add_compression_policy('sensor_data', INTERVAL '7 days');

-- Now chunks > 7 days old auto-compress

-- ===== CHECK STATS =====
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) AS before,
    pg_size_pretty(after_compression_total_bytes) AS after,
    ROUND(before_compression_total_bytes::numeric /
          NULLIF(after_compression_total_bytes, 0), 2) AS ratio
FROM hypertable_compression_stats('sensor_data');

-- ===== MANUAL COMPRESS =====
SELECT compress_chunk(chunk) FROM show_chunks('sensor_data') chunk
WHERE chunk::regclass::text NOT IN (
    SELECT format('%I.%I', schema_name, chunk_name)
    FROM chunks_detailed_size('sensor_data')
    WHERE is_compressed
);

-- ===== DECOMPRESS (rarely needed) =====
SELECT decompress_chunk('_timescaledb_internal._hyper_1_5_chunk');
"""


# ============================================================
# 6. DATA RETENTION
# ============================================================
RETENTION = """
-- ===== AUTO-DROP OLD DATA =====
SELECT add_retention_policy('sensor_data', INTERVAL '90 days');

-- ===== INSPECT POLICY =====
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_retention';

-- ===== MANUAL DROP =====
SELECT drop_chunks('sensor_data', older_than => INTERVAL '180 days');

-- DROP CHUNK = instant (no DELETE scan, no bloat)

-- ===== TIERED RETENTION =====
-- Raw 7 days, hourly 1 year, daily forever
SELECT add_retention_policy('sensor_data',       INTERVAL '7 days');
SELECT add_retention_policy('sensor_data_hourly', INTERVAL '1 year');
-- daily aggregate: no retention = kept forever
"""


# ============================================================
# 7. REAL-WORLD: API METRICS DASHBOARD
# ============================================================
API_METRICS = """
-- ===== TABLE =====
CREATE TABLE api_metrics (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint TEXT NOT NULL,
    method TEXT,
    status_code INT,
    duration_ms NUMERIC,
    user_id BIGINT,
    error_type TEXT
);

SELECT create_hypertable('api_metrics', 'time',
    chunk_time_interval => INTERVAL '1 hour'
);

CREATE INDEX ON api_metrics (endpoint, time DESC);
CREATE INDEX ON api_metrics (status_code, time DESC) WHERE status_code >= 400;

-- ===== HOURLY AGGREGATE =====
CREATE MATERIALIZED VIEW api_metrics_hourly WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time) AS hour,
        endpoint,
        method,
        COUNT(*) AS request_count,
        AVG(duration_ms) AS avg_ms,
        percentile_cont(0.5)  WITHIN GROUP (ORDER BY duration_ms) AS p50,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99,
        SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS error_5xx,
        SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) AS error_4xx
    FROM api_metrics
    GROUP BY hour, endpoint, method;

SELECT add_continuous_aggregate_policy('api_metrics_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'
);

-- Compression + retention
SELECT add_compression_policy('api_metrics', INTERVAL '1 day');
SELECT add_retention_policy('api_metrics', INTERVAL '7 days');

-- ===== DASHBOARD QUERIES =====
-- Slowest endpoints last 24h
SELECT endpoint, AVG(p99) AS avg_p99
FROM api_metrics_hourly
WHERE hour > NOW() - INTERVAL '24 hours'
GROUP BY endpoint
ORDER BY avg_p99 DESC
LIMIT 10;

-- Error rate trend
SELECT
    hour,
    SUM(error_5xx)::numeric / NULLIF(SUM(request_count), 0) AS error_rate
FROM api_metrics_hourly
WHERE hour > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;

-- Anomaly detection (latency spike)
WITH baseline AS (
    SELECT endpoint, AVG(p95) AS baseline_p95
    FROM api_metrics_hourly
    WHERE hour > NOW() - INTERVAL '7 days'
      AND hour < NOW() - INTERVAL '1 hour'
    GROUP BY endpoint
),
recent AS (
    SELECT endpoint, AVG(p95) AS recent_p95
    FROM api_metrics_hourly
    WHERE hour > NOW() - INTERVAL '1 hour'
    GROUP BY endpoint
)
SELECT
    r.endpoint,
    r.recent_p95,
    b.baseline_p95,
    r.recent_p95 / NULLIF(b.baseline_p95, 0) AS spike_ratio
FROM recent r JOIN baseline b USING (endpoint)
WHERE r.recent_p95 > b.baseline_p95 * 2   -- 2x spike
ORDER BY spike_ratio DESC;
"""


# ============================================================
# 8. FASTAPI INTEGRATION
# ============================================================
FASTAPI_INTEGRATION = '''
from fastapi import FastAPI, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone, timedelta

app = FastAPI()


@app.post("/metrics/ingest")
async def ingest_metric(
    endpoint: str,
    duration_ms: float,
    status_code: int,
    user_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text("""
        INSERT INTO api_metrics
            (time, endpoint, duration_ms, status_code, user_id)
        VALUES (:t, :e, :d, :s, :u)
    """), {
        "t": datetime.now(timezone.utc),
        "e": endpoint,
        "d": duration_ms,
        "s": status_code,
        "u": user_id,
    })
    await db.commit()


@app.get("/metrics/endpoint/{name}")
async def endpoint_metrics(
    name: str,
    interval: str = Query("1 hour", regex="^\\\\d+ (minute|hour|day)s?$"),
    lookback: str = Query("24 hours"),
    db: AsyncSession = Depends(get_db),
):
    """Return time-series for one endpoint."""
    result = await db.execute(text(f"""
        SELECT
            time_bucket('{interval}', time) AS bucket,
            COUNT(*) AS requests,
            AVG(duration_ms) AS avg_ms,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS errors
        FROM api_metrics
        WHERE endpoint = :name
          AND time > NOW() - INTERVAL '{lookback}'
        GROUP BY bucket
        ORDER BY bucket
    """), {"name": name})

    return [
        {"time": r.bucket, "requests": r.requests,
         "avg_ms": float(r.avg_ms), "p95": float(r.p95),
         "errors": r.errors}
        for r in result
    ]


@app.get("/metrics/top-slow")
async def top_slow_endpoints(
    hours: int = Query(24, le=720),
    limit: int = Query(10, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Slowest endpoints by p99 latency."""
    result = await db.execute(text("""
        SELECT endpoint,
               AVG(p99) AS avg_p99,
               SUM(request_count) AS total_requests
        FROM api_metrics_hourly
        WHERE hour > NOW() - INTERVAL :h
        GROUP BY endpoint
        ORDER BY avg_p99 DESC
        LIMIT :lim
    """), {"h": f"{hours} hours", "lim": limit})

    return [dict(r._mapping) for r in result]
'''


# ============================================================
# 9. INSPECTION QUERIES
# ============================================================
INSPECTION = """
-- ===== HYPERTABLE INFO =====
SELECT * FROM timescaledb_information.hypertables;

-- ===== CHUNK SIZES =====
SELECT
    chunk_name,
    pg_size_pretty(total_bytes) AS size,
    range_start, range_end,
    is_compressed
FROM chunks_detailed_size('sensor_data')
ORDER BY range_start DESC
LIMIT 10;

-- ===== TOTAL SIZE =====
SELECT
    hypertable_name,
    pg_size_pretty(total_bytes) AS total_size,
    pg_size_pretty(index_bytes) AS index_size,
    pg_size_pretty(toast_bytes) AS toast_size
FROM hypertable_detailed_size('sensor_data');

-- ===== CONTINUOUS AGGREGATE STATUS =====
SELECT * FROM timescaledb_information.continuous_aggregates;

-- ===== JOBS (auto-policies) =====
SELECT * FROM timescaledb_information.jobs;

-- ===== JOB STATS =====
SELECT * FROM timescaledb_information.job_stats;
"""


# ============================================================
# 10. PERFORMANCE TIPS
# ============================================================
PERFORMANCE = """
-- ===== EXPLAIN ANALYZE — verify chunk pruning =====
EXPLAIN ANALYZE
SELECT AVG(temperature)
FROM sensor_data
WHERE time > NOW() - INTERVAL '1 hour';

-- Look for: "Chunks excluded: 360" (good — only scans recent chunk)

-- ===== POSTGRESQL.CONF tuning =====
-- shared_buffers = 25% of RAM
-- effective_cache_size = 75% of RAM
-- max_parallel_workers_per_gather = 4
-- max_worker_processes = 8

-- ===== CHUNK SIZE TUNING =====
-- Rule: each chunk should fit in shared_buffers/2

-- Check current
SELECT chunk_name,
       pg_size_pretty(total_bytes) AS size
FROM chunks_detailed_size('sensor_data')
ORDER BY total_bytes DESC LIMIT 5;

-- Adjust
SELECT set_chunk_time_interval('sensor_data', INTERVAL '12 hours');

-- ===== PARALLEL CHUNK PROCESSING =====
SET max_parallel_workers_per_gather = 4;
-- Aggregations parallelize across chunks
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TIMESCALEDB TIME-SERIES — Practical")
    print("=" * 60)

    print("\n--- SETUP ---")
    print(SETUP_SQL)
    print("\n--- BULK INSERT ---")
    print(BULK_INSERT_PYTHON)
    print("\n--- AGGREGATIONS ---")
    print(AGGREGATIONS)
    print("\n--- CONTINUOUS AGGREGATES ---")
    print(CONTINUOUS_AGGREGATES)
    print("\n--- COMPRESSION ---")
    print(COMPRESSION_SETUP)
    print("\n--- RETENTION ---")
    print(RETENTION)
    print("\n--- API METRICS DASHBOARD ---")
    print(API_METRICS)
    print("\n--- FASTAPI INTEGRATION ---")
    print(FASTAPI_INTEGRATION)
    print("\n--- INSPECTION ---")
    print(INSPECTION)
    print("\n--- PERFORMANCE ---")
    print(PERFORMANCE)
