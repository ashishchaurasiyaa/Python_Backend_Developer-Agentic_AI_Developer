# 03 — Kafka Streams & Stream Processing

> Process unbounded streams of data. Aggregations, windowing, joins — all stateful, all in real-time.

---

## Stream Processing vs Batch

| | Batch (Spark, Airflow) | Stream (Kafka Streams, Flink) |
|---|---|---|
| Data | Bounded (finite) | Unbounded (continuous) |
| Latency | Minutes-hours | Milliseconds |
| Re-run on bad data | Easy | Replay via offset |
| Use case | Daily reports, ETL | Real-time analytics, fraud detection |

---

## Python Options

Kafka Streams is **Java-only**. Python alternatives:

| Tool | Approach | Use case |
|---|---|---|
| **Faust** | Kafka Streams-like, async Python | Pure Python event processing |
| **Bytewax** | Python stream processor | Modern, Dataflow-style |
| **PyFlink** | Python wrapper for Flink | Heavy stream processing |
| **Quix Streams** | Kafka-native Python streams | Production stream apps |
| Custom consumer + state | DIY | Simple cases |

---

## Faust Basics

```python
import faust

app = faust.App(
    "order-stream",
    broker="kafka://localhost:9092",
    value_serializer="json"
)

class Order(faust.Record):
    order_id: str
    amount: float

orders_topic = app.topic("orders", value_type=Order)

# Simple processor
@app.agent(orders_topic)
async def process(orders):
    async for order in orders:
        print(f"Got order {order.order_id}, amount={order.amount}")

if __name__ == "__main__":
    app.main()
```

Run: `faust -A myapp worker -l info`

Faust auto-handles offset management, partition assignment, rebalancing.

---

## Aggregations

Sum total orders per user, in real time:

```python
totals = app.Table("user_totals", default=float, partitions=4)

@app.agent(orders_topic)
async def aggregate(orders):
    async for order in orders.group_by(Order.user_id):
        totals[order.user_id] += order.amount
```

`app.Table` is a stateful store backed by RocksDB locally and a Kafka changelog topic for fault-tolerance.

---

## Windowing

Group events by time windows.

### Tumbling window (non-overlapping fixed-size)

```python
from faust.windows import TumblingWindow

orders_5min = app.Table(
    "orders_5min",
    default=float,
).tumbling(timedelta(minutes=5), expires=timedelta(hours=1))

@app.agent(orders_topic)
async def windowed(orders):
    async for order in orders.group_by(Order.user_id):
        orders_5min[order.user_id] += order.amount

# Read current window for user
current_total = orders_5min[user_id].current()
```

### Hopping window (overlapping)
Window size = 1 hour, step = 5 min → 12 overlapping windows.

```python
orders_hopping = app.Table("h", default=float).hopping(
    size=timedelta(hours=1),
    step=timedelta(minutes=5)
)
```

### Sliding window (event-driven)
Window slides based on events, not time.

---

## Filtering & Transformations

```python
@app.agent(orders_topic)
async def high_value(orders):
    async for order in orders:
        if order.amount > 1000:
            await high_value_topic.send(value=order)
```

Or stream operators:
```python
high = orders.filter(lambda o: o.amount > 1000)
mapped = orders.map(lambda o: {"id": o.order_id, "doubled": o.amount * 2})
```

---

## Joins

### Stream-stream join (within time window)
```python
@app.agent()
async def joined(stream1, stream2):
    async for s1, s2 in stream1.join(stream2, on=Order.order_id, within=timedelta(minutes=5)):
        ...
```

### Stream-table join (enrichment)
```python
users_table = app.Table("users", default=None)  # populated by user updates

@app.agent(orders_topic)
async def enrich(orders):
    async for order in orders:
        user = users_table[order.user_id]
        enriched = {**order.asdict(), "user_name": user.name}
        await enriched_topic.send(value=enriched)
```

---

## Stateful Processing & Changelogs

Faust `Table` state is backed by:
- Local RocksDB (fast reads).
- Kafka changelog topic (durability).

On worker crash, state rebuilt from changelog topic. No data loss.

```python
orders_count = app.Table(
    "orders_count",
    default=int,
    partitions=4,
    # State changelog: orders_count-changelog topic
)
```

---

## Exactly-Once Processing

Faust supports exactly-once via Kafka transactions.

```python
app = faust.App(..., processing_guarantee="exactly_once")
```

Every consume → process → produce cycle is one atomic Kafka transaction.

Cost: ~10-20% throughput. Use when correctness critical (financial pipelines).

---

## Time Semantics

### Event time vs Processing time

- **Event time:** when event happened (timestamp in payload).
- **Processing time:** when we processed it.

For accurate windowing, use event time. Set timestamp:
```python
class Order(faust.Record):
    order_id: str
    amount: float
    ts: float

@app.agent(orders_topic)
async def windowed(orders):
    async for order in orders:
        # Faust uses message timestamp by default
        ...
```

### Watermarks (late event handling)
"Wait 5 min after window closes for late events":
```python
orders_5min = app.Table("o").tumbling(
    timedelta(minutes=5),
    expires=timedelta(minutes=10)   # late tolerance
)
```

---

## Common Stream Patterns

### 1. Sessionization
Group events by user, separate sessions by inactivity gap.

```python
@app.agent(events_topic)
async def sessionize(events):
    async for event in events.group_by(Event.user_id):
        last_seen = sessions[event.user_id]
        if event.ts - last_seen > timedelta(minutes=30):
            # new session
            ...
        sessions[event.user_id] = event.ts
```

### 2. Top-K
Maintain top 10 hot products:

```python
top_products = app.Table("top10", default=int)

@app.agent(views_topic)
async def topk(views):
    async for view in views:
        top_products[view.product_id] += 1
    # Periodic emit top-10
```

### 3. Anomaly detection
EWMA (exponentially weighted moving average) per metric:

```python
@app.agent(metrics)
async def anomaly(stream):
    async for m in stream.group_by(Metric.host):
        baseline = ewma_table[m.host]
        new_ewma = 0.9 * baseline + 0.1 * m.value
        ewma_table[m.host] = new_ewma
        if abs(m.value - baseline) > 3 * baseline_stddev:
            await alerts_topic.send(value={"host": m.host, "spike": m.value})
```

### 4. Enrichment
Join stream with static lookup (Redis or Table).

### 5. Routing
Read from one topic, decide which downstream topic to write to.

---

## Bytewax — Modern Alternative

```python
import bytewax.operators as op
from bytewax.connectors.kafka import KafkaSource, KafkaSink
from bytewax.dataflow import Dataflow

flow = Dataflow("order_processor")
stream = op.input("in", flow, KafkaSource(brokers=["localhost:9092"], topics=["orders"]))

# Filter and transform
filtered = op.filter("hi_val", stream, lambda r: json.loads(r.value)["amount"] > 1000)

op.output("out", filtered, KafkaSink(brokers=["localhost:9092"], topic="high_value"))
```

Bytewax has Dataflow-style API, more modern feel.

---

## PyFlink (Heavy-Duty)

For complex stream processing at large scale, use Flink:

```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.typeinfo import Types

env = StreamExecutionEnvironment.get_execution_environment()
ds = env.add_source(KafkaSource(...))

ds.key_by(lambda x: x.user_id) \
  .time_window(TumblingEventTimeWindows.of(Time.minutes(5))) \
  .reduce(lambda a, b: ...)

env.execute("flink job")
```

Flink handles checkpointing, exactly-once, complex joins. Steeper learning curve.

---

## Production Considerations

### State size
Each Table can grow huge. Use:
- TTL on entries.
- Compaction.
- Sharding across workers.

### Scaling
Adding workers automatically rebalances partitions.

### Monitoring
- Consumer group lag.
- Faust app processing rate.
- State store size.

### Restart from snapshot
Faust replays changelog on restart. Can take time for huge state.

---

## Stream Processing vs Database

| | Stream processing | OLTP DB |
|---|---|---|
| Data | Continuous flow | Snapshots |
| Latency | ms | varies |
| Joins | Within window | Arbitrary |
| Replay | Yes (Kafka offsets) | No |

Sometimes you can replace daily Cron jobs with streams that update continuously.

---

## Real Use Cases

### LinkedIn
Activity feed generation, recommendation pipeline (Samza, now Kafka Streams).

### Uber
Surge pricing computation (Flink).

### Netflix
Real-time recommendation updates (Flink + Kafka).

### Confluent (Kafka company)
Sells Kafka Streams + Connect as managed service.

### Lyft
Stream processing for matching, surge, fraud (Flink).

---

## Faust vs Bytewax vs PyFlink

| | Faust | Bytewax | PyFlink |
|---|---|---|---|
| Maturity | Stable | Newer | Mature (Flink) |
| Style | Agents/Tables | Dataflow | DataStream API |
| Scale | Single process per partition | Distributed | Massive scale |
| Use case | Microservice-scale | Modern Python apps | Enterprise heavy |
| Best for | Simple-mid stream apps | Modern Pythonic | Complex pipelines |

---

## TL;DR

- Stream processing = real-time aggregations on unbounded data.
- Python options: Faust, Bytewax, PyFlink (in order of complexity).
- Stateful operations backed by changelog topics for durability.
- Windowing: tumbling, hopping, sliding.
- Use event time + watermarks for accuracy.
- Joins between streams and between stream + lookup tables.
- Exactly-once available via Kafka transactions.
