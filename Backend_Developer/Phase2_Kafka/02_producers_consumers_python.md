# 02 — Producers & Consumers (Python)

> Python clients for Kafka: aiokafka (async), confluent-kafka-python (best perf), kafka-python (pure Python).

---

## Library Choice

| Library | Lang | Pros | Cons |
|---|---|---|---|
| **confluent-kafka-python** | C wrapper (librdkafka) | Fastest, most features | Build deps, less Pythonic |
| **aiokafka** | Pure Python asyncio | Async-native, simple | Slower than librdkafka |
| **kafka-python** | Pure Python | Simple, well-known | Older, less active |

**Recommendation:**
- Async app: `aiokafka`.
- High throughput: `confluent-kafka-python`.
- Quick scripts: `kafka-python`.

---

## Producer with aiokafka

```python
import asyncio
from aiokafka import AIOKafkaProducer
import json

async def main():
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode(),
        key_serializer=lambda k: k.encode() if k else None,
        acks="all",                  # durability
        enable_idempotence=True,      # exactly-once-like semantics
        compression_type="lz4",       # cheap throughput win
        linger_ms=10,                 # batch within 10ms window
        max_batch_size=16384,
    )
    await producer.start()
    try:
        for i in range(100):
            await producer.send_and_wait(
                topic="orders",
                key=f"user-{i % 10}",
                value={"order_id": i, "amount": 100 + i},
                headers=[("trace_id", b"abc123")]
            )
    finally:
        await producer.stop()

asyncio.run(main())
```

### Fire-and-forget vs wait

```python
# Fire-and-forget (faster, no per-msg ack handling)
await producer.send("orders", {"id": 1})

# Wait for ack (slower, confirms delivery)
metadata = await producer.send_and_wait("orders", {"id": 1})
print(metadata.partition, metadata.offset)
```

For high throughput: batch many `send()` calls, then `await producer.flush()`.

---

## Consumer with aiokafka

```python
from aiokafka import AIOKafkaConsumer
import json

async def main():
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers="localhost:9092",
        group_id="order-processor",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",    # start from beginning if no offset
        enable_auto_commit=False,         # we'll commit manually
        max_poll_records=100,
    )
    await consumer.start()
    try:
        async for msg in consumer:
            await process(msg.value)
            await consumer.commit()       # commit after success
    finally:
        await consumer.stop()
```

### Batch processing

```python
async for batch in consumer.getmany(timeout_ms=1000, max_records=100):
    for tp, msgs in batch.items():
        for msg in msgs:
            await process(msg.value)
    await consumer.commit()
```

---

## Auto-commit vs Manual Commit

### Auto-commit (lossy)
```python
consumer = AIOKafkaConsumer(
    ..., enable_auto_commit=True, auto_commit_interval_ms=5000
)
```
Every 5s, commits current position. Messages between commits may be reprocessed on crash → at-least-once not guaranteed.

### Manual commit (safer)
```python
consumer = AIOKafkaConsumer(..., enable_auto_commit=False)

async for msg in consumer:
    try:
        await process(msg.value)
        await consumer.commit()  # after successful processing
    except Exception as e:
        # don't commit → next consumer reads this msg again
        await dead_letter_queue.send(msg)
```

---

## Idempotent Consumer

Consumers may see the same message multiple times. Make processing idempotent.

### Pattern 1: Database unique constraint
```python
async def process(msg):
    try:
        await db.execute(
            "INSERT INTO processed (msg_id, ...) VALUES ($1, ...)",
            msg.headers["msg_id"]
        )
    except UniqueViolationError:
        return  # already processed
```

### Pattern 2: Redis dedup
```python
async def process(msg):
    msg_id = msg.headers["msg_id"]
    if await redis.set(f"processed:{msg_id}", 1, nx=True, ex=86400):
        await actually_process(msg.value)
```

---

## Producer Idempotence + Transactions

### Idempotent producer (default in newer versions)
Avoids duplicate writes due to retries.
```python
producer = AIOKafkaProducer(
    ..., enable_idempotence=True, acks="all"
)
```

Kafka assigns producer ID + sequence numbers. Broker dedupes.

### Transactions (write to multiple partitions atomically)
```python
producer = AIOKafkaProducer(
    ..., transactional_id="order-processor-1",
    enable_idempotence=True
)
await producer.start()
await producer.init_transactions()

async with producer.transaction():
    await producer.send("orders", value={...})
    await producer.send("audit", value={...})
    # Either both commit or neither
```

(See file 05 for exactly-once deep dive.)

---

## Rebalance Listener

When consumer group changes (member added/removed), partitions get reassigned. Hook in:

```python
class MyListener(ConsumerRebalanceListener):
    async def on_partitions_revoked(self, revoked):
        # Save state, commit offsets before losing partition
        await consumer.commit()

    async def on_partitions_assigned(self, assigned):
        # Reset state for new partitions
        pass

consumer.subscribe(["orders"], listener=MyListener())
```

Use this to gracefully handle rebalances.

---

## Cooperative Rebalancing (Kafka 2.4+)

Old: "stop the world" rebalance. New: cooperative — only changing partitions get revoked.

```python
consumer = AIOKafkaConsumer(
    ...,
    partition_assignment_strategy=[CooperativeStickyAssignor]
)
```

Reduces processing pause during rebalances.

---

## Manual Partition Assignment (Advanced)

Skip consumer group; assign partitions directly:
```python
consumer = AIOKafkaConsumer(bootstrap_servers="...")
await consumer.start()
consumer.assign([TopicPartition("orders", 0)])
async for msg in consumer:
    ...
```

Use case: deterministic partition processing, e.g., one consumer per shard.

---

## Headers (Metadata Propagation)

```python
await producer.send(
    "orders",
    value={...},
    headers=[
        ("trace_id", b"abc123"),
        ("source", b"checkout-service"),
        ("schema_version", b"v2"),
    ]
)
```

Consumer reads:
```python
async for msg in consumer:
    headers = dict(msg.headers)
    trace_id = headers.get(b"trace_id", b"").decode()
```

Use for trace propagation, schema versioning, routing hints.

---

## Compression

```python
producer = AIOKafkaProducer(..., compression_type="lz4")
```

| Type | CPU cost | Compression ratio |
|---|---|---|
| none | 0 | 1x |
| gzip | High | 8x |
| snappy | Low | 4x |
| lz4 | Very low | 4x |
| zstd | Medium | 6x |

**Default choice:** lz4 (best CPU/ratio tradeoff).

---

## Error Handling

### Retriable errors (transient)
Producer auto-retries. Set `retries=10` and `retry_backoff_ms=100`.

### Non-retriable errors (e.g., message too large)
Caught and surfaced:
```python
try:
    await producer.send_and_wait("orders", value=huge_dict)
except RecordTooLargeError:
    # Don't retry; fix the data
    pass
```

### Consumer errors
Handle in your processing function. If you raise without commit, message is re-delivered.

---

## Dead Letter Queue (DLQ)

After N failures, send to DLQ for manual investigation.

```python
async def process_with_dlq(msg, max_retries=3):
    for attempt in range(max_retries):
        try:
            await process(msg.value)
            return
        except RetriableError:
            await asyncio.sleep(2 ** attempt)
    # All retries failed → DLQ
    await dlq_producer.send("orders.dlq", value={
        "original_msg": msg.value,
        "headers": dict(msg.headers),
        "error": str(e),
        "failed_at": datetime.utcnow().isoformat()
    })
```

DLQ is just another topic; tooling consumes and surfaces to ops.

---

## Performance Tuning

### Producer
```python
producer = AIOKafkaProducer(
    linger_ms=20,             # accumulate up to 20ms for batching
    batch_size=65536,         # 64KB batches
    compression_type="lz4",
    max_request_size=1048576, # 1MB max
)
```

### Consumer
```python
consumer = AIOKafkaConsumer(
    fetch_min_bytes=10240,    # wait for 10KB before fetching
    fetch_max_wait_ms=500,
    max_poll_records=500,
)
```

### Throughput targets
| Setup | Single producer throughput |
|---|---|
| Default | ~10K msg/sec |
| Tuned (batching + lz4) | ~100K msg/sec |
| Multiple producers + tuning | 1M+ msg/sec per broker |

---

## confluent-kafka-python (Higher Performance)

```python
from confluent_kafka import Producer, Consumer

p = Producer({
    'bootstrap.servers': 'localhost:9092',
    'acks': 'all',
    'compression.type': 'lz4',
    'linger.ms': 10,
})

def delivery_report(err, msg):
    if err:
        print(f"Delivery failed: {err}")
    else:
        print(f"Delivered to {msg.topic()}[{msg.partition()}]")

p.produce("orders", value=b"...", callback=delivery_report)
p.flush()

c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
    'auto.offset.reset': 'earliest',
})
c.subscribe(['orders'])
while True:
    msg = c.poll(1.0)
    if msg is None: continue
    if msg.error(): continue
    process(msg.value())
    c.commit(asynchronous=False)
```

Synchronous; use threading or async wrapper for non-blocking apps.

---

## Testing Kafka Code

### Use testcontainers
```python
import pytest
from testcontainers.kafka import KafkaContainer

@pytest.fixture(scope="session")
def kafka():
    with KafkaContainer() as k:
        yield k.get_bootstrap_server()

@pytest.mark.asyncio
async def test_produce_consume(kafka):
    producer = AIOKafkaProducer(bootstrap_servers=kafka)
    consumer = AIOKafkaConsumer("test", bootstrap_servers=kafka, group_id="t")
    ...
```

Real Kafka in a Docker container for tests.

---

## TL;DR

- Use `aiokafka` for async Python apps.
- `enable_idempotence=True` + `acks="all"` = durability.
- Manual commit for at-least-once.
- Idempotent consumer logic (dedup via DB or Redis).
- Batch + compress for throughput.
- Handle rebalances with listener.
- DLQ for failed messages.
- Test with `testcontainers`.
