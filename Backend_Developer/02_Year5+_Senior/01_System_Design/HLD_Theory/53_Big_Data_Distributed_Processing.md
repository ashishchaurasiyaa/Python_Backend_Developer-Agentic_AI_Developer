# 53. Big Data — Hadoop, Spark, Flink, MapReduce, Streaming

## What is "Big Data"?

```
Data that's too big / fast / varied for single-machine processing.

The 5 Vs:
- Volume:    TB to PB scale
- Velocity:  events/sec to millions/sec
- Variety:   structured + semi-structured + unstructured
- Veracity:  reliability of data
- Value:     deriving insights / decisions
```

**When you need Big Data tools:**
- Data > RAM of biggest available machine
- Processing takes hours/days on single node
- Multiple teams need same data
- Need historical (years) + real-time

---

## Batch vs Stream Processing

```
BATCH:                          STREAM:
─────                           ──────
Process bounded dataset         Process unbounded stream
"Run nightly job"               "Process events as they arrive"
High latency (mins-hours)       Low latency (ms-sec)
Higher throughput per record    Lower throughput per record
Easy to retry / reproducible    Hard to retry exact state
Hadoop, Spark batch              Flink, Spark Streaming, Kafka Streams

Use cases:                       Use cases:
- ETL pipelines                  - Fraud detection
- Reports                        - Real-time dashboards
- ML training                    - Live recommendations
- Data warehousing               - Anomaly detection
```

**Lambda Architecture:** combine batch (accurate, slow) + stream (approximate, fast).
**Kappa Architecture:** stream only; replay for batch-like use cases.

---

## The Big Data Ecosystem

```
┌─────────────────────────────────────────┐
│              VISUALIZATION                │
│  Tableau, Looker, Superset, Metabase     │
└─────────────────────────────────────────┘
              ▲
┌─────────────────────────────────────────┐
│              ANALYTICS                    │
│  Snowflake, BigQuery, Redshift, Trino    │
└─────────────────────────────────────────┘
              ▲
┌─────────────────────────────────────────┐
│              PROCESSING                   │
│  Spark, Flink, Hadoop, Beam, Airflow      │
└─────────────────────────────────────────┘
              ▲
┌─────────────────────────────────────────┐
│              STORAGE                      │
│  HDFS, S3, GCS, Delta Lake, Iceberg       │
└─────────────────────────────────────────┘
              ▲
┌─────────────────────────────────────────┐
│              INGESTION                    │
│  Kafka, Kinesis, Pulsar, Flume, CDC       │
└─────────────────────────────────────────┘
              ▲
┌─────────────────────────────────────────┐
│              SOURCES                      │
│  Apps, DBs, Logs, IoT, External APIs      │
└─────────────────────────────────────────┘
```

---

## Hadoop Ecosystem (the OG)

### HDFS (Hadoop Distributed File System)

```
Cluster:
┌──────────────┐
│  NameNode    │  metadata (file → block locations)
└──────┬───────┘
       │
┌──────▼────────────────────────────┐
│  DataNodes (many)                   │
│  ┌───────┐ ┌───────┐ ┌───────┐    │
│  │ Block │ │ Block │ │ Block │    │  128 MB blocks
│  │ 1 (3x)│ │ 2 (3x)│ │ 3 (3x)│    │  replicated 3x
│  └───────┘ └───────┘ └───────┘    │
└────────────────────────────────────┘

Properties:
- Append-only (no in-place updates)
- High throughput, high latency
- Fault tolerant (replication)
- Block size: 128 MB (large for sequential scan)
```

**S3 vs HDFS today:**
| | HDFS | S3 |
|---|---|---|
| Cost | Compute + storage | Storage only |
| Throughput | High (10s GB/s) | Varies |
| Decoupled | No | Yes |
| Ops | Manage cluster | Managed |

**2026 reality:** Most use S3 (or GCS/ADLS) as data lake; HDFS in decline.

### MapReduce — the Programming Model

```
Input → Map → Shuffle/Sort → Reduce → Output

Example: Word count
─────
Input file:
"hello world hello"

Map phase (each mapper processes a chunk):
hello → 1
world → 1
hello → 1

Shuffle (group by key):
hello → [1, 1]
world → [1]

Reduce phase:
hello → 2
world → 1
```

**Python (with mrjob):**
```python
from mrjob.job import MRJob

class WordCount(MRJob):
    def mapper(self, _, line):
        for word in line.split():
            yield word.lower(), 1

    def reducer(self, word, counts):
        yield word, sum(counts)

if __name__ == "__main__":
    WordCount.run()
```

**Pros:** Massively parallel, fault-tolerant
**Cons:** Slow (disk I/O per stage), Java-heavy, verbose

**2026 reality:** MapReduce mostly replaced by Spark.

### YARN — Resource Management

Schedules Hadoop jobs across cluster.

---

## Apache Spark — The Workhorse

Faster than MapReduce (100x for in-memory) + easier API.

### Concepts

```
RDD (Resilient Distributed Dataset):
- Distributed collection of objects
- Immutable
- Lazy evaluation
- Lineage tracking (recompute on failure)

DataFrame / Dataset:
- Typed table-like API (like pandas but distributed)
- Optimized via Catalyst optimizer

SparkSession:
- Entry point
- Creates DataFrames
```

### PySpark Example

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("analytics") \
    .config("spark.executor.memory", "8g") \
    .getOrCreate()

# Read
df = spark.read.parquet("s3://data/events/")

# Transform
df_agg = (
    df.filter(F.col("event_type") == "purchase")
      .withColumn("hour", F.hour("timestamp"))
      .groupBy("hour", "product_id")
      .agg(
          F.count("*").alias("purchases"),
          F.sum("amount").alias("revenue"),
      )
      .orderBy("revenue", ascending=False)
)

# Write
df_agg.write.mode("overwrite").parquet("s3://data/hourly_metrics/")
```

### Spark Architecture

```
Driver (orchestrator)
   │
   ├──→ Cluster Manager (YARN / K8s / Standalone)
   │
   ├──→ Executor 1 (worker)
   │     ├── Task 1
   │     ├── Task 2
   │     └── Cache
   │
   ├──→ Executor 2
   │
   └──→ Executor N
```

### Spark Streaming (micro-batch)

```python
from pyspark.sql.functions import window

stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "events") \
    .load()

# Tumbling window aggregations
agg = stream \
    .selectExpr("CAST(value AS STRING) as json") \
    .selectExpr("from_json(json, 'event_type STRING, amount DOUBLE, timestamp TIMESTAMP') as data") \
    .select("data.*") \
    .groupBy(window("timestamp", "1 minute"), "event_type") \
    .sum("amount")

# Write to sink
query = agg.writeStream \
    .outputMode("update") \
    .format("kafka") \
    .option("topic", "metrics") \
    .start()

query.awaitTermination()
```

**Spark vs Hadoop:**
| | Hadoop MR | Spark |
|---|---|---|
| Storage | HDFS | Memory + disk |
| Latency | Minutes-hours | Seconds-minutes |
| API | Java verbose | Python/Scala/SQL clean |
| Real-time | No | Yes (micro-batch) |

---

## Apache Flink — True Streaming

While Spark uses micro-batches, Flink processes events one-at-a-time.

### Why Flink

```
Spark Streaming:               Flink:
─────────                      ──────
Micro-batches (1-10s)          Event-by-event
Higher latency                 Sub-second
Throughput-focused             Latency-focused

Best for:                      Best for:
- Aggregations                  - Complex event processing
- Big batch + small stream      - State machines per entity
                                - Exactly-once semantics
```

### PyFlink Example

```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import TableEnvironment, EnvironmentSettings

env = StreamExecutionEnvironment.get_execution_environment()
t_env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())

# Define source
t_env.execute_sql("""
    CREATE TABLE events (
        user_id BIGINT,
        action STRING,
        ts TIMESTAMP(3),
        WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'events',
        'properties.bootstrap.servers' = 'kafka:9092',
        'format' = 'json'
    )
""")

# Windowed aggregation
result = t_env.sql_query("""
    SELECT
        TUMBLE_START(ts, INTERVAL '5' MINUTE) as window_start,
        user_id,
        COUNT(*) as actions
    FROM events
    GROUP BY TUMBLE(ts, INTERVAL '5' MINUTE), user_id
""")
```

### Flink Concepts

- **Watermarks**: how Flink handles out-of-order events
- **Windows**: tumbling, sliding, session
- **State**: per-key state (e.g., user's session)
- **Exactly-once**: via checkpointing
- **Savepoints**: explicit recovery points

**Companies using Flink:** Uber, Lyft, Alibaba, Netflix (state-of-art streaming).

---

## Kafka Streams — JVM Library

For lightweight stream processing **inside Kafka**.

```java
// Java — Python equivalent uses Faust or fastapi-streams
KStream<String, Order> orders = builder.stream("orders");
KTable<String, Long> orderCount = orders
    .groupByKey()
    .count();
orderCount.toStream().to("order-counts");
```

**Python alternative — Faust:**
```python
import faust

app = faust.App("orders-app", broker="kafka://localhost:9092")

class Order(faust.Record):
    user_id: int
    amount: float

orders_topic = app.topic("orders", value_type=Order)
counts = app.Table("order_counts", default=int)

@app.agent(orders_topic)
async def process(orders):
    async for order in orders:
        counts[order.user_id] += 1
```

---

## Workflow Orchestration

### Apache Airflow — Batch Workflow

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    "daily_etl",
    schedule="0 2 * * *",   # 2 AM daily
    start_date=datetime(2026, 1, 1),
) as dag:

    extract = PythonOperator(
        task_id="extract",
        python_callable=lambda: print("extracting"),
    )

    transform = PythonOperator(
        task_id="transform",
        python_callable=lambda: print("transforming"),
    )

    load = PythonOperator(
        task_id="load",
        python_callable=lambda: print("loading"),
    )

    extract >> transform >> load
```

**Alternatives:**
- **Prefect** (modern, Python-native)
- **Dagster** (data-asset focused)
- **Argo Workflows** (K8s-native)
- **Mage** (modern, opinionated)

---

## Data Lake vs Data Warehouse vs Lakehouse

### Data Warehouse
**Examples:** Snowflake, BigQuery, Redshift

- Structured data only
- Schema-on-write
- Expensive but fast queries
- For analytics / BI

### Data Lake
**Examples:** S3, ADLS, HDFS

- Raw data, any format
- Schema-on-read
- Cheap storage
- For ML, data science

### Lakehouse (modern hybrid)
**Examples:** Databricks (Delta Lake), Apache Iceberg, Apache Hudi

- Lake storage (S3/GCS)
- Warehouse-like features:
  - ACID transactions
  - Time travel (query historical state)
  - Schema evolution
  - Update/delete records

```python
# Delta Lake example
from delta import DeltaTable

# Write
df.write.format("delta").mode("overwrite").save("s3://lake/orders")

# Time travel
historical = spark.read.format("delta").option("versionAsOf", 12).load("s3://lake/orders")

# Upsert
delta_table = DeltaTable.forPath(spark, "s3://lake/orders")
delta_table.alias("old").merge(
    new_data.alias("new"),
    "old.id = new.id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
```

---

## File Formats for Big Data

| Format | Compression | Splittable | Columnar | Use |
|---|---|---|---|---|
| **CSV** | None | Yes | No | Universal, but inefficient |
| **JSON Lines** | gzip | Yes (gzip multi-stream) | No | Logs |
| **Avro** | snappy/zstd | Yes | No | Kafka, row-oriented |
| **Parquet** | snappy/zstd | Yes | **Yes** | Analytics (column-oriented) |
| **ORC** | zlib/snappy | Yes | **Yes** | Hive ecosystem |

**Why Parquet for analytics:**
```
Column-oriented:
- Query SELECT user_id, amount FROM events
- Only reads user_id + amount columns (not whole row)
- 10-100x faster for analytical queries

Compression:
- Same column = similar values → compresses well
- Often 10x smaller than CSV
```

```python
# Pandas
df.to_parquet("data.parquet", compression="snappy")
df = pd.read_parquet("data.parquet")

# Spark
df.write.parquet("s3://data/events/", mode="overwrite")
df = spark.read.parquet("s3://data/events/")
```

---

## Query Engines

### Trino / Presto

Query data **across multiple sources** without moving it.

```sql
-- Query S3 (Parquet) + PostgreSQL + MySQL in one query
SELECT
    p.product_name,
    SUM(o.amount) as revenue
FROM postgres.public.products p
JOIN hive.lake.orders_parquet o ON p.id = o.product_id
WHERE o.date >= DATE '2026-01-01'
GROUP BY p.product_name
ORDER BY revenue DESC;
```

**Use:** Federated queries; data exploration; ad-hoc analytics.

### Apache Druid / ClickHouse

For real-time OLAP at massive scale.

```sql
-- ClickHouse — sub-second on billions of rows
SELECT
    toStartOfHour(timestamp) as hour,
    count() as events,
    uniq(user_id) as unique_users
FROM events
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY hour
ORDER BY hour;
```

---

## ML on Big Data

### Distributed Training

**Spark MLlib** — built-in ML:
```python
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.feature import VectorAssembler

assembler = VectorAssembler(inputCols=["age", "income"], outputCol="features")
train = assembler.transform(train_df)

lr = LogisticRegression(maxIter=10)
model = lr.fit(train)
```

**Modern alternatives:**
- **Ray** — distributed Python; modern
- **Dask** — pandas-compatible parallel
- **Horovod** — distributed deep learning
- **DeepSpeed** — Microsoft's LLM training framework

### Feature Store

Centralized store for ML features:
- **Feast** (open source)
- **Tecton** (commercial)
- **AWS SageMaker Feature Store**

```python
from feast import FeatureStore

fs = FeatureStore(repo_path="feature_repo/")
features = fs.get_online_features(
    features=["user_features:age", "user_features:total_spent"],
    entity_rows=[{"user_id": 42}],
).to_dict()
```

---

## Real-World Pipeline Example

```
SOURCE                              PROCESSING                    SINK
──────                              ──────────                    ────
App events ──→ Kafka topic ──→ Flink (stream)           ──→ Druid (real-time dashboard)
                  │
                  └──→ Kafka Connect ──→ S3 (raw)
                                              │
                                              └──→ Airflow nightly ──→ Spark batch
                                                                            │
                                                                            ├──→ Snowflake (BI)
                                                                            │
                                                                            └──→ Feature store (ML)
```

**Why this pattern:**
- Kafka = durable log (replayable)
- Flink = real-time aggregates (< 1 min latency)
- S3 = cheap historical storage
- Spark = batch ETL (complex transformations)
- Snowflake = BI / SQL analytics
- Druid = sub-second dashboards

---

## When NOT to Use Big Data

**Don't reach for Spark/Hadoop if:**
- Data fits in pandas (< 100GB)
- Single PostgreSQL handles it
- Latency < 1 sec needed (use OLAP DB)
- Team has no big data expertise

**"The biggest mistake in big data: using big data tools when you don't need them."**

PostgreSQL can handle 100s of GB. ClickHouse handles billions of rows with sub-second queries. Don't add Spark unless you NEED distributed compute.

---

## Decision Tree

```
Data size?
├── < 10 GB     → pandas / DuckDB
├── 10-100 GB   → Postgres / ClickHouse
├── 100GB-1TB   → ClickHouse / BigQuery / Snowflake
└── > 1 TB      → Spark / Flink / Snowflake

Latency need?
├── Hours OK    → Spark batch / Airflow
├── Minutes     → Spark Streaming
└── Seconds     → Flink / Kafka Streams

Real-time analytics?
├── Yes         → Druid / ClickHouse / Pinot
└── No          → Snowflake / BigQuery

Use case?
├── ETL         → Spark / Airflow
├── Streaming   → Flink / Kafka Streams / Beam
├── ML training → Spark MLlib / Ray
├── ML serving  → Real-time API + feature store
└── BI / SQL    → Snowflake / BigQuery / dbt
```

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Over-engineering for tiny data | Use simpler tools |
| Reinventing Spark in Python | Use Spark or Dask |
| Tiny files in S3 | Compaction; partition wisely |
| Skewed partitions | Salt the key; repartition |
| OOM in Spark | Increase executor memory; cache strategically |
| Slow stream processing | Check watermarks; reduce state |
| Unmanaged costs | Set query budgets; monitor cluster size |
| Data drift breaks pipeline | Schema validation; observability |
| Late events lost | Watermarks + allowed lateness |
| One huge table | Partition by date + key |

---

## Cost Optimization

```
S3 storage tiers:
- Standard:        $0.023/GB/month (frequent)
- Intelligent:     auto-tiers based on access
- Standard-IA:     $0.0125/GB (monthly access)
- Glacier:         $0.004/GB (yearly access)
- Glacier Deep:    $0.00099/GB (years)

Lifecycle:
- Move > 30 days old to IA
- Move > 90 days old to Glacier
- Delete after retention period
```

```
Compute (Spark):
- Spot instances    (60-70% cheaper)
- Right-size        (don't over-provision)
- Auto-scale        (down when idle)
- Use S3 directly   (don't HDFS unless needed)

Snowflake:
- Auto-suspend warehouses
- Right-size warehouse
- Materialized views for repeat queries
- Result cache (24h)
```

---

## Interview Q&A

### Q: When would you use Spark over a database?

**Answer:**
- Data > what fits in DB efficiently (1+ TB)
- Need parallel processing across many machines
- Complex transformations (ML, joins of huge tables)
- Reading from data lake (Parquet on S3)
- Integration with ML ecosystem

Use DB when:
- Data fits in DB
- Need real-time / low-latency queries
- ACID transactions
- OLTP workload

### Q: Batch vs Stream — how to choose?

**Answer:**
| Need | Choose |
|---|---|
| End-of-day reports | Batch |
| Hourly metrics | Batch (small) or stream |
| Real-time dashboard | Stream |
| Fraud detection | Stream |
| Recommendations | Hybrid (batch training + stream serving) |
| Compliance reports | Batch |

### Q: Spark vs Flink?

**Answer:**
- **Spark**: Better for batch + simple streaming; bigger ecosystem; easier to learn
- **Flink**: True streaming; lower latency; better state management; complex event processing

Many companies use both: Spark for ETL/ML, Flink for real-time.

### Q: How do you handle late events in streaming?

**Answer:**
- **Watermarks**: tell engine "no more events older than X"
- **Allowed lateness**: process late events up to threshold
- **Side outputs**: send late events to separate stream
- **Dead letter queue**: for very late / unprocessable

### Q: Lambda vs Kappa architecture?

**Answer:**
- **Lambda**: separate batch (accurate) + stream (fast) paths. Reconcile. Complex.
- **Kappa**: stream only. Replay for batch use cases. Simpler.

Modern preference: Kappa with Kafka as replayable source.

---

## Cheat Sheet

```
Storage:        S3 + Parquet
Stream:         Kafka → Flink → Druid/Snowflake
Batch:          Airflow → Spark → Snowflake
ML training:    Spark MLlib / Ray
ML features:    Feast / Tecton
BI:             dbt → Snowflake → Looker
Real-time BI:   ClickHouse / Druid
Federation:     Trino / Presto
Lakehouse:      Delta / Iceberg / Hudi
```

---

## Related Docs
- [41_Data_Pipelines_Streaming.md](41_Data_Pipelines_Streaming.md) — pipeline patterns
- [01_Year3-4_Mid/07_Kafka/](../../../01_Year3-4_Mid/07_Kafka) — Kafka deep
- [01_Year3-4_Mid/11_Elasticsearch/](../../../01_Year3-4_Mid/11_Elasticsearch) — search
- [00_Year0-2_Junior/04_Database_SQL/](../../../00_Year0-2_Junior/04_Database_SQL) — analytics tables
- [HLD_Problems/Design_Real_Time_Analytics.md](../HLD_Problems/Design_Real_Time_Analytics.md) — real-time system design
- [HLD_Problems/Design_Search_Engine.md](../HLD_Problems/Design_Search_Engine.md) — search at scale

## External References
- **Designing Data-Intensive Applications** — Martin Kleppmann
- Spark docs: https://spark.apache.org/docs/latest/
- Flink docs: https://nightlies.apache.org/flink/flink-docs-stable/
- Databricks blog: https://www.databricks.com/blog
- Confluent blog: https://www.confluent.io/blog
- ClickHouse docs: https://clickhouse.com/docs
