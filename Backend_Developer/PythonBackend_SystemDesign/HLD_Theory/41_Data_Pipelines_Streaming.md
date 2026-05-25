# 41 — Data Pipelines & Streaming

---

## What & Why

**Data Pipeline** = series of processing steps that move/transform data from source to destination.

```
Batch Pipeline:         Source → ETL Job (hourly/daily) → Data Warehouse
Streaming Pipeline:     Source → Stream Processor (milliseconds) → Sink
```

**When to use each:**
- Batch: nightly reports, ML training, historical analytics (Spark, Airflow)
- Streaming: real-time dashboards, fraud detection, alerting, recommendations (Kafka Streams, Flink)

---

## 1. Lambda Architecture

```
                    ┌──────────────────────────────────┐
                    │           Lambda Architecture      │
                    │                                    │
Raw Data ──────────►├──► Batch Layer (Spark/Hadoop)     │
(Kafka/S3)          │    → Processes ALL historical data │
                    │    → Recomputes every few hours    │
                    │                                    │
                    ├──► Speed Layer (Kafka Streams)     │
                    │    → Processes recent data only    │
                    │    → Approximate/real-time results  │
                    │                                    │
                    └──► Serving Layer (Redis/Cassandra)  │
                         Batch results + Speed layer     │
                         results MERGED for query        │
                    └──────────────────────────────────┘

Problem: code duplication (same logic in batch + speed)
```

---

## 2. Kappa Architecture

```
                    ┌──────────────────────────────────┐
                    │           Kappa Architecture       │
                    │                                    │
Raw Data ──────────►│  Single Stream Processing Layer    │
(Kafka)             │  (Flink / Kafka Streams)           │
                    │                                    │
                    │  For historical reprocessing:      │
                    │  → Replay Kafka from offset 0      │
                    │  → Use 2nd consumer group          │
                    │  → Swap output when done           │
                    └──────────────────────────────────┘

Advantage: ONE codebase for both real-time and historical.
Kafka as source of truth (retain 30 days+).
```

---

## 3. Kafka Core Concepts

```python
"""
Kafka: distributed event streaming platform.
- Producer: publishes events to topics
- Topic: named stream (like a database table)
- Partition: ordered, immutable log within topic (enables parallelism)
- Consumer Group: each group processes each message once (load balanced)
- Offset: position in partition log

Key properties:
- Durable: messages retained on disk (configurable, default 7 days)
- Ordered: within a partition (not across partitions)
- Scalable: add partitions = add parallelism
"""

import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

class KafkaProducerClient:
    """Async Kafka producer with JSON serialization and error handling."""

    def __init__(self, bootstrap_servers: str):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            acks="all",                    # wait for all replicas (durability)
            enable_idempotence=True,       # exactly-once producer semantics
            compression_type="gzip",       # compress messages
            max_batch_size=16384,          # 16KB batches
            linger_ms=10                   # wait 10ms to fill batch
        )

    async def send(self, topic: str, value: dict,
                    key: str = None, partition: int = None):
        """
        Send message. Key determines partition (same key → same partition).
        Use key for ordering guarantees (e.g., user_id as key).
        """
        await self.producer.send(
            topic, value=value, key=key,
            partition=partition
        )

    async def send_and_wait(self, topic: str, value: dict, key: str = None):
        """Send and wait for broker acknowledgment."""
        future = await self.producer.send(topic, value=value, key=key)
        record_metadata = await future
        return {
            "topic":     record_metadata.topic,
            "partition": record_metadata.partition,
            "offset":    record_metadata.offset
        }


class KafkaConsumerClient:
    """Async Kafka consumer with manual offset management."""

    def __init__(self, topics: list[str], group_id: str,
                  bootstrap_servers: str):
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="earliest",   # start from beginning if no committed offset
            enable_auto_commit=False,       # manual commit for exactly-once processing
            max_poll_records=100
        )

    async def consume(self, handler):
        """
        Consume messages with manual offset commit.
        Commit only after successful processing.
        """
        async for message in self.consumer:
            try:
                await handler(message.value)
                # Commit offset after successful processing
                await self.consumer.commit()
            except Exception as e:
                # Don't commit → message will be redelivered
                print(f"Processing error: {e}. Offset not committed.")
                # In production: send to DLQ after N failures

    async def consume_batch(self, handler, batch_size: int = 100):
        """Process messages in batches for throughput efficiency."""
        while True:
            messages = await self.consumer.getmany(
                max_records=batch_size,
                timeout_ms=1000
            )
            batch = [msg.value for msgs in messages.values() for msg in msgs]
            if batch:
                await handler(batch)
                await self.consumer.commit()
```

---

## 4. Kafka Streams (Python equivalent)

```python
"""
Kafka Streams = processing topology on top of Kafka.
Python equivalent: use Faust (Kafka Streams for Python) or write manually.

Common stream operations:
- filter(): keep only matching events
- map(): transform events
- aggregate(): count/sum per key in time window
- join(): combine two streams

Example: real-time order analytics — count orders per seller per minute.
"""

import faust    # pip install faust-streaming
import time
from datetime import timedelta

app = faust.App("order-analytics", broker="kafka://localhost:9092")

# Define data models
class OrderEvent(faust.Record):
    order_id: str
    seller_id: str
    amount: float
    timestamp: float

class SellerStats(faust.Record):
    seller_id: str
    order_count: int
    total_revenue: float
    window_start: float

# Topics
orders_topic = app.topic("orders", value_type=OrderEvent)
seller_stats_topic = app.topic("seller_stats", value_type=SellerStats)

# State table: count per seller (backed by Kafka/RocksDB)
seller_order_counts = app.Table("seller_order_counts",
                                  default=int,
                                  partitions=8)
seller_revenue = app.Table("seller_revenue",
                            default=float,
                            partitions=8)

@app.agent(orders_topic)
async def process_orders(orders):
    """
    Stream processor: aggregate order stats per seller.
    Stateful: state stored in local RocksDB, changelog in Kafka.
    """
    async for order in orders:
        # Update running totals
        seller_order_counts[order.seller_id] += 1
        seller_revenue[order.seller_id] += order.amount

        # Emit aggregated stats every order (or use tumbling windows)
        await seller_stats_topic.send(
            key=order.seller_id,
            value=SellerStats(
                seller_id=order.seller_id,
                order_count=seller_order_counts[order.seller_id],
                total_revenue=seller_revenue[order.seller_id],
                window_start=time.time()
            )
        )


# Windowed aggregation (tumbling 1-minute windows)
@app.agent(orders_topic)
async def minute_aggregator(orders):
    """Count orders per seller in 1-minute tumbling windows."""
    async for order in orders.group_by(OrderEvent.seller_id):
        # In Faust: use hopping/tumbling windows for time-based aggregation
        pass


# Manual windowed aggregation approach:
class WindowedAggregator:
    """
    Manual tumbling window aggregator.
    Window: time-bucketed (e.g., count per minute).
    """

    def __init__(self, window_size_sec: int = 60):
        self.window_size = window_size_sec
        # {(seller_id, window_start): {count, revenue}}
        self.windows: dict = {}

    def get_window_start(self, ts: float) -> float:
        """Bucket timestamp into window start."""
        return ts - (ts % self.window_size)

    def add_event(self, seller_id: str, amount: float, ts: float):
        window_start = self.get_window_start(ts)
        key = (seller_id, window_start)
        if key not in self.windows:
            self.windows[key] = {"count": 0, "revenue": 0.0}
        self.windows[key]["count"] += 1
        self.windows[key]["revenue"] += amount

    def flush_closed_windows(self, current_ts: float) -> list[dict]:
        """Return and remove windows that have passed."""
        current_window = self.get_window_start(current_ts)
        closed = []
        for (seller_id, ws), stats in list(self.windows.items()):
            if ws < current_window:
                closed.append({
                    "seller_id":    seller_id,
                    "window_start": ws,
                    "window_end":   ws + self.window_size,
                    **stats
                })
                del self.windows[(seller_id, ws)]
        return closed
```

---

## 5. ETL Pipeline (Batch — Apache Airflow + Spark)

```python
"""
ETL: Extract → Transform → Load

Extract: pull data from sources (PostgreSQL, APIs, S3)
Transform: clean, enrich, aggregate, join
Load: write to data warehouse (Snowflake, BigQuery, Redshift)

Airflow: orchestrates the DAG (Directed Acyclic Graph) of tasks.
Spark: distributed compute for large transformations.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "start_date":       datetime(2024, 1, 1),
    "email_on_failure": True,
    "email":            ["data-eng@company.com"],
    "retries":          3,
    "retry_delay":      timedelta(minutes=5)
}

dag = DAG(
    dag_id="daily_order_etl",
    default_args=default_args,
    description="Daily order data ETL to data warehouse",
    schedule_interval="0 2 * * *",   # 2 AM daily
    catchup=False
)


def extract_orders(**context):
    """Extract yesterday's orders from PostgreSQL."""
    from datetime import date, timedelta
    import pandas as pd

    execution_date = context["ds"]   # e.g., "2024-01-15"
    query = f"""
        SELECT order_id, user_id, seller_id, total_amount, status,
               created_at, items
        FROM orders
        WHERE DATE(created_at) = '{execution_date}'
    """
    df = pd.read_sql(query, con=get_postgres_connection())
    df.to_parquet(f"s3://data-lake/raw/orders/{execution_date}/orders.parquet")
    print(f"Extracted {len(df)} orders for {execution_date}")
    return len(df)


def transform_orders(**context):
    """Transform orders: clean, enrich, compute metrics."""
    import pandas as pd

    execution_date = context["ds"]
    df = pd.read_parquet(f"s3://data-lake/raw/orders/{execution_date}/orders.parquet")

    # Clean
    df = df.dropna(subset=["order_id", "user_id"])
    df["total_amount"] = df["total_amount"].clip(lower=0)

    # Enrich: join with users table (cached dim table)
    users_df = pd.read_parquet("s3://data-lake/dimensions/users_latest.parquet")
    df = df.merge(users_df[["user_id", "country", "tier"]], on="user_id", how="left")

    # Aggregate: revenue by seller_id for the day
    seller_summary = df.groupby("seller_id").agg(
        order_count=("order_id", "count"),
        total_revenue=("total_amount", "sum"),
        avg_order_value=("total_amount", "mean")
    ).reset_index()

    df.to_parquet(f"s3://data-lake/processed/orders/{execution_date}/orders.parquet")
    seller_summary.to_parquet(
        f"s3://data-lake/processed/seller_daily/{execution_date}/summary.parquet"
    )
    print(f"Transformed {len(df)} orders")


def load_to_warehouse(**context):
    """Load processed data to Snowflake/BigQuery."""
    execution_date = context["ds"]

    # COPY from S3 to Snowflake
    snowflake_query = f"""
    COPY INTO orders_fact
    FROM @s3_stage/processed/orders/{execution_date}/
    FILE_FORMAT = (TYPE = PARQUET)
    ON_ERROR = 'CONTINUE';
    """
    run_snowflake_query(snowflake_query)
    print(f"Loaded orders for {execution_date} to Snowflake")


# Define tasks
extract_task = PythonOperator(
    task_id="extract_orders",
    python_callable=extract_orders,
    dag=dag
)

transform_task = PythonOperator(
    task_id="transform_orders",
    python_callable=transform_orders,
    dag=dag
)

load_task = PythonOperator(
    task_id="load_to_warehouse",
    python_callable=load_to_warehouse,
    dag=dag
)

# Set dependencies
extract_task >> transform_task >> load_task
```

---

## 6. Stream Processing Patterns

```python
"""
Key streaming patterns for interviews:
"""

# 1. Event Deduplication
class StreamDeduplicator:
    """Deduplicate events in a stream using Redis with TTL."""

    def __init__(self, redis_client, ttl_sec: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_sec

    async def is_duplicate(self, event_id: str) -> bool:
        key = f"seen:{event_id}"
        result = await self.redis.set(key, "1", ex=self.ttl, nx=True)
        return result is None   # None = key already existed = duplicate


# 2. Exactly-Once Processing (Transactional outbox pattern)
class TransactionalOutbox:
    """
    Problem: write to DB + publish to Kafka must be atomic.
    Solution: write event to DB first (outbox table), then relay to Kafka.
    """

    async def process_order(self, order: dict, db):
        async with db.transaction():
            # Write to business table
            await db.execute("INSERT INTO orders VALUES ($1, $2, $3)",
                              order["id"], order["user_id"], order["total"])

            # Write to outbox (same transaction = atomic)
            await db.execute(
                "INSERT INTO outbox(event_id, topic, payload, created_at) "
                "VALUES($1,$2,$3,NOW())",
                order["id"], "orders", __import__("json").dumps(order)
            )
        # Relay process reads outbox and publishes to Kafka separately

    async def relay_outbox(self, db, kafka):
        """Background process: read outbox → publish to Kafka → mark as sent."""
        rows = await db.query_many(
            "SELECT * FROM outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT 100"
        )
        for row in rows:
            await kafka.send(row["topic"], __import__("json").loads(row["payload"]))
            await db.execute(
                "UPDATE outbox SET sent_at=NOW() WHERE event_id=$1",
                row["event_id"]
            )


# 3. Change Data Capture (CDC)
"""
CDC: capture every INSERT/UPDATE/DELETE from database and stream them.
Use case: sync DB to Elasticsearch, warm caches, audit log.

Tool: Debezium (reads PostgreSQL WAL → publishes to Kafka)

Flow:
PostgreSQL → WAL → Debezium → Kafka topic "postgres.public.users"
  → Consumer 1: update Elasticsearch
  → Consumer 2: invalidate Redis cache
  → Consumer 3: audit log in BigQuery
"""


# 4. Real-Time Fraud Detection Pipeline
class FraudDetectionPipeline:
    """
    Streaming fraud detection: flag suspicious transactions in real-time.
    Rules engine + ML model.
    """

    def __init__(self, redis_client, model):
        self.redis = redis_client
        self.model = model

    async def evaluate_transaction(self, txn: dict) -> dict:
        user_id = txn["user_id"]
        amount  = txn["amount"]

        # Feature extraction
        features = await self._extract_features(user_id, txn)

        # Rule-based checks (fast)
        rules_result = self._check_rules(features, txn)
        if rules_result["flagged"]:
            return {**rules_result, "action": "block",
                    "reason": rules_result["rule"]}

        # ML model score (slower, run only if rules pass)
        fraud_score = await self.model.predict(features)
        if fraud_score > 0.9:
            return {"flagged": True, "score": fraud_score,
                    "action": "block", "reason": "ml_model_high_score"}

        return {"flagged": False, "score": fraud_score, "action": "allow"}

    async def _extract_features(self, user_id: str, txn: dict) -> dict:
        """Compute real-time features from Redis counters."""
        now = __import__("time").time()
        window_1h = f"txn_count:{user_id}:{int(now // 3600)}"
        window_24h = f"txn_amount:{user_id}:{int(now // 86400)}"

        txn_count_1h = int(await self.redis.get(window_1h) or 0)
        txn_amount_24h = float(await self.redis.get(window_24h) or 0)

        # Update counters
        await self.redis.incr(window_1h)
        await self.redis.expire(window_1h, 7200)
        await self.redis.incrbyfloat(window_24h, txn["amount"])
        await self.redis.expire(window_24h, 172800)

        return {
            "amount":          txn["amount"],
            "txn_count_1h":    txn_count_1h + 1,
            "txn_amount_24h":  txn_amount_24h + txn["amount"],
            "user_country":    txn.get("country"),
            "merchant_category": txn.get("merchant_category")
        }

    def _check_rules(self, features: dict, txn: dict) -> dict:
        """Fast rule-based fraud checks."""
        rules = [
            (features["amount"] > 50000, "transaction_too_large"),
            (features["txn_count_1h"] > 20, "too_many_transactions_1h"),
            (features["txn_amount_24h"] > 100000, "daily_limit_exceeded"),
        ]
        for flagged, rule in rules:
            if flagged:
                return {"flagged": True, "rule": rule}
        return {"flagged": False}
```

---

## 7. Comparison: Lambda vs Kappa

| Aspect | Lambda Architecture | Kappa Architecture |
|--------|--------------------|--------------------|
| Layers | Batch + Speed + Serving | Single stream layer |
| Complexity | High (2 codebases) | Lower |
| Historical reprocessing | Batch re-runs | Replay Kafka from offset |
| Latency | Seconds (speed layer) | Milliseconds |
| Correctness | Batch eventually corrects speed | Single source of truth |
| Use case | Complex ML, heavy analytics | Real-time processing |

---

## 8. Interview Questions

**Q1: What is the difference between stream and batch processing?**
> Batch: process a bounded dataset at once (e.g., all orders from yesterday). High throughput, higher latency. Stream: process events as they arrive (unbounded dataset). Low latency (milliseconds), results continuously updated. Batch is simpler and great for analytics; streaming is necessary for real-time features (fraud detection, dashboards, recommendations).

**Q2: What is exactly-once processing in Kafka?**
> By default, Kafka provides at-least-once delivery (messages can be reprocessed on failure). Exactly-once requires: (1) Idempotent producer (enable_idempotence=True) — each message has a unique producer ID + sequence, broker deduplicates. (2) Transactional API — producer commits offsets + messages atomically across partitions. (3) Consumer: disable auto-commit, commit only after processing. Combined gives exactly-once end-to-end.

**Q3: What is Change Data Capture and when do you use it?**
> CDC: reads the database write-ahead log (WAL) to capture every data change (insert/update/delete) as a stream of events. Use when: syncing DB to Elasticsearch (search index), warming caches on data change, building audit logs, replicating to another DB. Debezium is the standard tool (PostgreSQL WAL → Kafka). Advantage over polling: captures ALL changes including deletes, low overhead, real-time.

**Q4: How does Kafka handle partition ordering?**
> Within a single partition, messages are strictly ordered. Across partitions, no ordering guarantee. For ordering: use consistent partition key (e.g., user_id or order_id). All messages with the same key go to the same partition. Consumer processes one partition sequentially. For global ordering: use single partition (sacrifices parallelism). Trade-off: more partitions = more parallelism but no cross-partition ordering.

**Q5: What is windowing in stream processing?**
> Grouping events by time window for aggregations (count orders per minute). Types: (1) Tumbling: fixed non-overlapping windows (0:00-0:01, 0:01-0:02). (2) Sliding: fixed size, moves every step (0:00-0:05, 0:01-0:06). (3) Session: variable, groups events with idle gap between sessions. Out-of-order events handled by watermarks (Flink/Kafka Streams delay window close for late arrivals).

**Q6: How would you design a real-time leaderboard using Kafka?**
> Producer: game servers emit `{user_id, score, timestamp}` events to Kafka. Stream processor (Faust/Kafka Streams): consume events, aggregate total score per user in Redis sorted set (`ZINCRBY leaderboard user_id delta_score`). API: `ZREVRANGE leaderboard 0 99 WITHSCORES` returns top 100. Periodic snapshot to PostgreSQL for durability. Redis sorted set O(log n) for updates, O(log n + k) for range queries.
