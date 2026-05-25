# Design Real-Time Analytics Platform

---

## 1. Requirements

### Functional
- Ingest events from web/mobile apps, services (clickstream, business events).
- Real-time dashboards (latency < 5s from event to chart).
- Ad-hoc OLAP queries on historical data.
- Aggregations: counts, sums, distinct users, percentiles.
- Funnels, retention cohorts, segmentation.
- Alerting on anomalies / thresholds.
- Export (CSV, BigQuery, Looker).

### Non-Functional
- 10M events/sec ingest.
- Dashboard refresh < 5s end-to-end.
- Ad-hoc query p95 < 10s for 1B-row scan.
- 1 year hot data, 7 years cold.
- 99.95% availability.
- Multi-tenant.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Events/sec | 10M |
| Events/day | 850B |
| Avg event size | 500 bytes |
| Daily raw volume | 425 TB/day |
| Compressed (5x) | 85 TB/day |
| 1 year hot | 30 PB |
| Distinct users tracked | 1B |
| Active dashboards | 10K |
| Concurrent queries | 1K |

---

## 3. High-Level Architecture (Kappa-style)

```
   Clients (web/mobile/services)
            │
            ▼
   ┌────────────────────┐
   │  Ingest API        │
   │  (collector)       │
   └────────┬───────────┘
            │
   ┌────────▼───────────┐
   │       Kafka         │  (5-day retention)
   └────────┬───────────┘
            │
        ┌───┼────────────┬───────────────┐
        │   │            │               │
   ┌────▼──┐ ┌───────────▼──────┐  ┌─────▼──────┐
   │Stream │ │ Real-time Loader │  │ Archive    │
   │Process│ │ (to OLAP store)  │  │ to S3      │
   │ (Flink│ │                  │  │ (Parquet)  │
   └───┬───┘ └────────┬─────────┘  └────────────┘
       │              │
       ▼              ▼
   ┌──────┐    ┌──────────────┐
   │Redis │    │  Druid /     │
   │(live │    │  Pinot /     │
   │metrics│   │  Clickhouse  │
   └──────┘    └──────────────┘
                      │
                      ▼
                ┌────────────┐
                │ Dashboard /│
                │ Query API  │
                └────────────┘
```

---

## 4. Lambda vs Kappa Architecture

### Lambda
- Two paths: batch (Hadoop/Spark) + speed (Flink).
- Speed serves recent; batch serves all (more accurate).
- Cons: duplicated logic, complex.

### Kappa (recommended)
- Single path through Kafka + stream processor.
- Re-process by replaying Kafka or backfilling from S3 archive.
- Simpler. Modern default.

---

## 5. Ingest API

High-throughput, low-latency event collector.

```python
@app.post("/track")
async def track(events: list[Event], api_key: str = Header()):
    # 1. Validate tenant
    tenant = await auth.verify(api_key)

    # 2. Enrich
    for e in events:
        e.tenant_id = tenant.id
        e.received_at = time.time()
        e.geo = await ip_to_geo(req.client.host)

    # 3. Publish to Kafka (batched, gzipped)
    await kafka.send_batch("events.raw", events, partition_key=tenant.id)

    return {"accepted": len(events)}
```

### Throughput tricks
- Async batch (collect 1s worth of events, send as batch).
- Compress before sending (lz4/zstd).
- HTTP/2 multiplexing.
- gRPC streaming for service-to-service.
- UDP for super-high throughput (StatsD pattern).

### SDK
Provide language SDKs that:
- Batch locally (every 10s or 100 events).
- Retry on failure.
- Drop oldest on full local buffer.

---

## 6. Kafka — The Backbone

### Topics
- `events.raw` — all events, partitioned by tenant_id.
- `events.enriched` — after enrichment.
- `events.dlq` — failed processing.

### Retention
- 5 days (acts as replay buffer).
- 3x replication.
- 1000s of partitions for parallelism.

---

## 7. Stream Processing (Flink/Spark)

Real-time aggregations.

### Use cases
- Per-minute event count per tenant.
- Distinct user count (HyperLogLog).
- Percentile latencies.
- Anomaly detection.

### Example (Flink Python — PyFlink)
```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.window import TumblingEventTimeWindows
from pyflink.common import Time

env = StreamExecutionEnvironment.get_execution_environment()
events = env.add_source(KafkaSource("events.raw"))

# 1-minute tumbling window count per (tenant, event_type)
counts = (events
    .key_by(lambda e: (e.tenant_id, e.event_type))
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .reduce(lambda a, b: a + b))

counts.add_sink(RedisSink())
```

### Time semantics
- **Event time** (when event happened) — required for accuracy.
- **Processing time** (when we processed) — easier but inaccurate.
- **Watermarks**: tolerance for late events (e.g., wait 10s after window closes).

---

## 8. OLAP Storage Layer

Choice of one:

### Apache Druid
- Time-series first.
- Pre-aggregation at ingest.
- Fast queries on time-bucketed data.
- Used by Netflix, Airbnb.

### Apache Pinot
- Real-time + batch ingestion.
- Better for low-latency dashboards.
- Used by LinkedIn, Uber.

### ClickHouse
- General OLAP.
- Columnar, very fast scans.
- Simpler ops than Druid/Pinot.
- Used by Cloudflare, Yandex.

### Comparison

| Feature | Druid | Pinot | ClickHouse |
|---|---|---|---|
| Time-series first | ✓ | partial | partial |
| Realtime ingestion | ✓ | ✓ | ✓ |
| SQL | partial | ✓ | ✓ |
| Operational complexity | High | High | Medium |
| Query latency | < 1s | < 1s | < 5s |
| Best for | Multi-dim slice | Low-latency dashboards | General OLAP |

**Pick ClickHouse** for general use. **Pinot** for sub-second dashboards. **Druid** for time-series heavy.

### Schema (ClickHouse)
```sql
CREATE TABLE events (
    tenant_id    UInt32,
    event_time   DateTime,
    event_type   String,
    user_id      String,
    session_id   String,
    properties   String,    -- JSON
    geo_country  LowCardinality(String),
    device       LowCardinality(String),
    INDEX user_idx user_id TYPE bloom_filter GRANULARITY 64
)
ENGINE = MergeTree()
PARTITION BY (tenant_id, toYYYYMMDD(event_time))
ORDER BY (tenant_id, event_type, event_time)
TTL event_time + INTERVAL 1 YEAR;
```

---

## 9. Pre-Aggregation Strategy

Raw events: too granular for fast dashboard queries.

### Materialized views (ClickHouse)
```sql
CREATE MATERIALIZED VIEW events_5min_agg
ENGINE = SummingMergeTree()
PARTITION BY (tenant_id, toYYYYMMDD(t))
ORDER BY (tenant_id, event_type, t)
AS
SELECT
    tenant_id,
    event_type,
    toStartOfFiveMinute(event_time) AS t,
    count() AS cnt,
    uniqExact(user_id) AS uniq_users
FROM events
GROUP BY tenant_id, event_type, t;
```

Now dashboard queries hit `events_5min_agg` → 5-min granularity, milliseconds to query.

### Multi-resolution
- Raw events (1 day retention).
- 1-min aggregates (7 days).
- 5-min aggregates (30 days).
- 1-hour aggregates (1 year).

---

## 10. Approximate Algorithms

### HyperLogLog (distinct count)
- Estimate distinct users without storing all IDs.
- ~1.6% error with 16KB state.
- Mergeable across partitions.

```sql
SELECT uniqHLL12(user_id) FROM events;
```

### Count-Min Sketch (heavy hitters)
- Frequency estimation for top-N analysis.
- Sub-linear memory.

### t-digest / DDSketch (percentiles)
- Approximate p50/p95/p99 without storing all samples.

These are essential at 10M events/sec — exact algorithms don't fit memory.

---

## 11. Dashboard / Query API

### Architecture
```
Dashboard UI → Query API → SQL → ClickHouse → Result
                     ↓
                  Cache (Redis)
```

### Query semantics
- Cache identical queries for 30-60s.
- Invalidate on new data threshold.

```python
async def query_dashboard(tenant_id, sql_template, params):
    cache_key = hash((sql_template, params))
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await clickhouse.execute(sql_template, params)
    await redis.set(cache_key, json.dumps(result), ex=60)
    return result
```

---

## 12. Funnels & Cohorts (Complex Analytics)

### Funnel: % users completing step A → B → C in order, within window

```sql
SELECT
    countIf(stepReachedA) AS started,
    countIf(stepReachedB) AS step2,
    countIf(stepReachedC) AS completed,
    step2 / started AS conv_a_to_b,
    completed / started AS conv_a_to_c
FROM (
    SELECT user_id,
        max(if(event_type='page_view', event_time, NULL)) AS view_at,
        max(if(event_type='add_to_cart' AND event_time > view_at, event_time, NULL)) AS cart_at,
        max(if(event_type='purchase' AND event_time > cart_at, event_time, NULL)) AS purchase_at,
        notNull(view_at) AS stepReachedA,
        notNull(cart_at) AS stepReachedB,
        notNull(purchase_at) AS stepReachedC
    FROM events
    WHERE event_time > now() - INTERVAL 7 DAY
    GROUP BY user_id
);
```

Funnel queries are expensive — pre-compute periodically for common funnels.

### Cohort analysis
- "Users who signed up Jan 1 — what % returned each subsequent week?"
- Group by signup date + activity date → matrix.

---

## 13. Real-Time Counters (Redis)

For instantly-visible metrics (homepage counters):
```python
await redis.incr(f"events:{tenant}:{event_type}:{minute}")
```

Use Redis TIME, sorted sets for time-windowed counts:
```python
# Window of last 5 minutes
now = int(time.time())
count = await redis.zcount(f"events:{tenant}", now - 300, now)
```

---

## 14. Alerting

### Threshold-based
- "Page view rate < 1000/min → alert."
- Evaluator queries OLAP every 30s, compares to threshold.

### Anomaly detection
- Train baseline (rolling mean + stddev).
- Alert on > 3σ deviation.
- Seasonal decomposition (workday vs weekend patterns).

### Alert dedup
- Same alert within 10 min → suppress.
- Auto-resolve when metric returns to normal.

---

## 15. Late-Arriving Events

Events from mobile devices may arrive minutes late (offline → reconnect).

### Handling
- Watermark + allowed lateness (e.g., 10 min).
- Re-emit corrected aggregations.
- Or: accept incomplete data, mark windows as "final" after watermark passes.

```python
# Flink: allowed lateness
events.key_by(...).window(TumblingEventTimeWindows.of(Time.minutes(1))).allowed_lateness(Time.minutes(10))
```

---

## 16. Backfilling

Bug found in stream processor; need to reprocess last 7 days.

### Strategy
1. Fix processor.
2. Reset Kafka consumer offset to 7 days ago.
3. Reprocess → writes to new MV / table.
4. Atomic swap.

Kafka retention of 5+ days is critical for this.

For >Kafka retention: replay from S3 archive.

---

## 17. Multi-Tenant

### Isolation levels
- Tenant ID in every event.
- Quotas per tenant (rate limit ingest).
- Separate Kafka partitions (noisy neighbor isolation).
- Query-level filter `WHERE tenant_id = ?` enforced at API.

### Pricing tiers
- Free: 10K events/day, 5-min dashboard refresh.
- Pro: 1M/day, 1-min refresh.
- Enterprise: unlimited, real-time, dedicated cluster.

---

## 18. Cold Tier (S3 Archive)

After 1 year, move to S3 in Parquet.
- Same query SQL via Trino/Athena (slower).
- 100x cheaper storage than OLAP cluster.

### Tiering pipeline
```
Daily:
  For partition older than 1yr in ClickHouse:
    Export to Parquet → S3
    Verify count match
    Drop partition
```

---

## 19. APIs

```
POST /track                      # ingest events (batch)
GET  /v1/dashboards/{id}/data    # render dashboard
POST /v1/query                   # ad-hoc SQL
GET  /v1/funnel?steps=[...]      # pre-built funnel
GET  /v1/cohort?type=...         # cohort
POST /v1/alerts                  # rule
POST /v1/export                  # async export job
```

---

## 20. Trade-offs

| Decision | Trade-off |
|---|---|
| Kappa over Lambda | Simpler, harder for complex re-aggregations |
| Pre-aggregation MV | Fast reads, expensive on writes |
| Approximate algorithms | Massive scale enabler, slight inaccuracy |
| Materialized views | Auto-updated, more storage |
| Hot-cold tiering | Cost-effective, slower historical queries |

---

## 21. Follow-up Questions

- **"How to support custom user-defined aggregations?"** → SQL-based dashboards where users write own queries; sandbox SQL with allowlist of functions.
- **"What about exactly-once semantics?"** → Idempotent writes + transactional sinks (Flink + Kafka transactions). Achievable.
- **"How to compare Pinot vs Druid?"** → Pinot: lower latency, simpler dev. Druid: richer query primitives, more mature.
- **"Cardinality explosion (e.g., 1M unique URLs)?"** → Reject high-cardinality dimensions or hash them. HyperLogLog handles unique count without storing values.
- **"How to share data with BigQuery / Snowflake?"** → Periodic export from S3 (Parquet directly readable) or Kafka-Connect sinks.
- **"Real-time machine learning on streams?"** → Online learning models updated incrementally; or batch-trained models, real-time inference.
