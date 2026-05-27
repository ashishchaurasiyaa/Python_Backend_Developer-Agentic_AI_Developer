# PostgreSQL — Change Data Capture (CDC) with Debezium + WAL Streaming
**Phase 2 Database | Senior Backend + Agentic AI**

## Quick Concepts
- **CDC** = Change Data Capture — stream every INSERT/UPDATE/DELETE as events
- **WAL** = Write-Ahead Log — PostgreSQL's append-only log of all changes
- **Logical replication** = decode WAL into row-level events (vs physical = byte-level)
- **Debezium** = Kafka Connect plugin that reads WAL and publishes to Kafka topics
- **Outbox pattern** = alternative — explicit events table polled by separate process
- **Replication slot** = persistent cursor into WAL (don't lose events on consumer restart)
- **Snapshot** = initial dump of existing data before streaming live changes
- **Eventually consistent** = downstream sees changes with seconds of lag

---

## Why CDC?

```
WITHOUT CDC:                          WITH CDC:
──────────                            ─────────
App writes to DB                      App writes to DB
   ↓                                     ↓
App ALSO publishes event              Debezium reads WAL
   ↓ (often forgotten/inconsistent)      ↓ (automatic)
Other services consume                Kafka topic
                                         ↓
                                      Other services consume
```

**Pain CDC solves:**
- ❌ Dual writes (write to DB + Kafka — one fails, inconsistency)
- ❌ Forgetting to publish events
- ❌ Coupling business logic with messaging
- ❌ No retroactive event stream (existing data ignored)

---

## Use Cases

| Use Case | Example |
|---|---|
| **Microservices sync** | User updates profile in user-service → notification-service updates cache |
| **Search indexing** | Product table changes → Elasticsearch index updated |
| **Analytics warehouse** | OLTP rows → BigQuery/Snowflake (ETL replacement) |
| **Audit log** | Compliance: every change captured immutably |
| **Cache invalidation** | DB change → Redis cache evicted |
| **Event sourcing** | Build event stream from existing transactional DB |
| **AI training data** | Stream rows to feature store / vector DB |

---

## Interview Questions & Answers

### Q1: PostgreSQL ko CDC ke liye configure kaise karte hain?

**Answer:** Enable logical replication + create replication slot + publication.

```bash
# 1. postgresql.conf
wal_level = logical                    # default 'replica' won't work
max_wal_senders = 10                   # concurrent replication connections
max_replication_slots = 10             # slot count
max_logical_replication_workers = 4

# Restart required
sudo systemctl restart postgresql
```

```sql
-- 2. Create user with replication permission
CREATE ROLE debezium WITH LOGIN REPLICATION PASSWORD 'secret';
GRANT CONNECT ON DATABASE mydb TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;

-- 3. Create publication (defines which tables to stream)
CREATE PUBLICATION my_publication FOR TABLE orders, users, products;
-- Or all tables:
-- CREATE PUBLICATION my_publication FOR ALL TABLES;

-- 4. Tables must have REPLICA IDENTITY (for UPDATE/DELETE events)
ALTER TABLE orders REPLICA IDENTITY FULL;  -- captures old + new row values
-- Default is DEFAULT (PK only) — fine if you only need PK
```

```sql
-- 5. Inspect / verify
SELECT * FROM pg_replication_slots;
SELECT * FROM pg_publication;
SELECT * FROM pg_publication_tables WHERE pubname='my_publication';
```

---

### Q2: Debezium ko Kafka Connect ke saath setup?

**Answer:** Docker compose stack — Kafka + Connect + Debezium plugin.

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    command: postgres -c wal_level=logical
    ports: ["5432:5432"]

  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  connect:
    image: debezium/connect:2.7
    depends_on: [kafka, postgres]
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect_configs
      OFFSET_STORAGE_TOPIC: connect_offsets
      STATUS_STORAGE_TOPIC: connect_statuses
    ports: ["8083:8083"]
```

**Register Debezium connector via REST API:**
```bash
curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d '{
  "name": "orders-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "secret",
    "database.dbname": "mydb",
    "topic.prefix": "myapp",
    "table.include.list": "public.orders,public.users",
    "plugin.name": "pgoutput",
    "publication.name": "my_publication",
    "slot.name": "debezium_slot",
    "snapshot.mode": "initial",
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "key.converter.schemas.enable": "false",
    "value.converter.schemas.enable": "false"
  }
}'
```

Kafka topics created:
- `myapp.public.orders`
- `myapp.public.users`

---

### Q3: Debezium CDC event format kya hota hai?

**Answer:** JSON with `before`, `after`, `op`, `source` metadata.

```json
{
  "before": null,
  "after": {
    "id": 42,
    "user_id": 7,
    "total": 999.99,
    "status": "pending",
    "created_at": 1714579200000000
  },
  "source": {
    "version": "2.7.0",
    "connector": "postgresql",
    "name": "myapp",
    "ts_ms": 1714579201234,
    "snapshot": "false",
    "db": "mydb",
    "schema": "public",
    "table": "orders",
    "lsn": 28473028,
    "xmin": null
  },
  "op": "c",
  "ts_ms": 1714579201250
}
```

**`op` field decoded:**
| Value | Meaning |
|---|---|
| `c` | Create (INSERT) |
| `u` | Update |
| `d` | Delete |
| `r` | Read (initial snapshot) |
| `t` | Truncate |

**UPDATE event** has both `before` and `after`:
```json
{
  "before": {"id": 42, "status": "pending"},
  "after": {"id": 42, "status": "shipped"},
  "op": "u",
  ...
}
```

---

### Q4: Python consumer for Debezium events?

**Answer:** `aiokafka` consumer with JSON parsing.

```python
import asyncio
import json
from typing import Callable
from aiokafka import AIOKafkaConsumer

class CDCConsumer:
    def __init__(self, bootstrap_servers: str, topics: list[str], group_id: str):
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",  # process from beginning if no offset
            enable_auto_commit=False,       # manual commit for safety
            value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        )
        self.handlers: dict[str, dict[str, Callable]] = {}

    def on(self, table: str, op: str):
        """Decorator: @consumer.on('orders', 'c') for inserts."""
        def decorator(fn):
            self.handlers.setdefault(table, {})[op] = fn
            return fn
        return decorator

    async def start(self):
        await self.consumer.start()
        try:
            async for msg in self.consumer:
                await self._process(msg)
                await self.consumer.commit()  # commit after success
        finally:
            await self.consumer.stop()

    async def _process(self, msg):
        event = msg.value
        if not event:
            return  # tombstone

        op = event.get("op")
        table = event.get("source", {}).get("table")

        if table in self.handlers and op in self.handlers[table]:
            handler = self.handlers[table][op]
            try:
                await handler(event)
            except Exception as e:
                logging.exception(f"Handler failed for {table}/{op}")
                raise  # don't commit; will retry

# ─── Usage ───
consumer = CDCConsumer(
    bootstrap_servers="localhost:9092",
    topics=["myapp.public.orders", "myapp.public.users"],
    group_id="search-indexer",
)

@consumer.on("orders", "c")
async def on_order_created(event):
    order = event["after"]
    # Update search index
    await elasticsearch.index("orders", id=order["id"], document=order)
    # Send notification
    await send_notification(order["user_id"], f"Order #{order['id']} created")

@consumer.on("orders", "u")
async def on_order_updated(event):
    before, after = event["before"], event["after"]
    if before["status"] != after["status"]:
        await send_notification(after["user_id"], f"Order status: {after['status']}")
    await elasticsearch.update("orders", id=after["id"], document=after)

@consumer.on("orders", "d")
async def on_order_deleted(event):
    deleted = event["before"]
    await elasticsearch.delete("orders", id=deleted["id"])

if __name__ == "__main__":
    asyncio.run(consumer.start())
```

---

### Q5: Outbox pattern (alternative to Debezium)?

**Answer:** Application-level — write to `events` table in same transaction.

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,    -- 'order', 'user'
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- 'order_created', 'order_shipped'
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_outbox_unprocessed ON outbox_events(created_at) WHERE NOT processed;
```

**Application code:**
```python
async def create_order_with_outbox(session: AsyncSession, order_data: dict):
    async with session.begin():  # single transaction
        # 1. Insert order
        order_result = await session.execute(
            "INSERT INTO orders (user_id, total, status) VALUES (:uid, :tot, 'pending') RETURNING id",
            order_data,
        )
        order_id = order_result.scalar()

        # 2. Insert outbox event (same transaction!)
        await session.execute(
            """
            INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload)
            VALUES (:t, :id, :type, :payload)
            """,
            {
                "t": "order",
                "id": str(order_id),
                "type": "order_created",
                "payload": json.dumps({**order_data, "order_id": order_id}),
            },
        )
    return order_id
```

**Publisher (polling or via Debezium on outbox table):**
```python
async def outbox_publisher():
    while True:
        async with async_session() as session:
            events = await session.execute(
                "SELECT * FROM outbox_events WHERE NOT processed ORDER BY created_at LIMIT 100"
            )
            for event in events:
                await kafka_producer.send(
                    f"events.{event.aggregate_type}",
                    value=event.payload,
                    key=event.aggregate_id.encode(),
                )
                await session.execute(
                    "UPDATE outbox_events SET processed=TRUE WHERE id=:id",
                    {"id": event.id},
                )
            await session.commit()
        await asyncio.sleep(1)
```

**Best: Debezium on outbox table** — combines explicit events + automatic streaming.

---

### Q6: Replication slot management (production gotcha)?

**Answer:** Inactive slots → unbounded WAL growth → disk full.

```sql
-- Monitor replication slots
SELECT
    slot_name,
    plugin,
    slot_type,
    active,
    confirmed_flush_lsn,
    pg_size_pretty(
        pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)
    ) AS lag_size
FROM pg_replication_slots;

-- ⚠️ Drop unused slot (Debezium not consuming = WAL accumulates!)
SELECT pg_drop_replication_slot('debezium_slot');

-- Check WAL size
SELECT pg_size_pretty(pg_wal_size()) AS wal_size;
```

**Alert pattern:**
```python
async def monitor_replication_lag():
    """Run as periodic Celery task."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT slot_name, pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes
            FROM pg_replication_slots
            WHERE active = TRUE
        """))
        for row in result:
            if row.lag_bytes > 1_000_000_000:  # 1GB lag
                await alert_oncall(f"Slot {row.slot_name} lag: {row.lag_bytes} bytes")
```

---

### Q7: Schema evolution — column added/dropped mid-stream?

**Answer:** Debezium handles automatically, but consumers need to be robust.

```python
@consumer.on("orders", "u")
async def safe_handler(event):
    # ❌ Brittle: KeyError if column added/removed
    # status = event["after"]["status"]

    # ✅ Robust: use .get() with defaults
    after = event["after"]
    status = after.get("status")
    if status is None:
        return  # column might not exist in older events

    # Handle new columns gracefully
    discount = after.get("discount_amount", 0)  # added later

    await process(status, discount)
```

**Schema registry option:** Use Avro + Confluent Schema Registry → schema versioned, compatibility enforced.

---

### Q8: Exactly-once semantics (idempotency)?

**Answer:** Kafka offers at-least-once → consumers must be idempotent.

```python
async def idempotent_handler(event):
    event_id = f"{event['source']['table']}_{event['source']['lsn']}"

    # Check if already processed (Redis SET NX or DB unique constraint)
    async with redis.lock(f"cdc:processed:{event_id}", timeout=10):
        already = await redis.get(f"cdc:done:{event_id}")
        if already:
            return  # skip duplicate

        # Process
        await process_event(event)

        # Mark done (TTL 7 days)
        await redis.setex(f"cdc:done:{event_id}", 7 * 24 * 3600, "1")
```

**Alternative: upsert pattern** — operation itself idempotent:
```python
@consumer.on("orders", "u")
async def upsert_es(event):
    # ES `index` is idempotent (replaces by ID)
    await elasticsearch.index(
        index="orders",
        id=event["after"]["id"],
        document=event["after"],
    )
```

---

## CDC vs Outbox Comparison

| Aspect | Debezium CDC | Outbox Pattern |
|---|---|---|
| **Setup complexity** | High (Kafka Connect cluster) | Low (just a table) |
| **Latency** | ~1s | Depends on polling interval |
| **Coupling** | Loose (DB internals) | Tight (app code) |
| **Event semantics** | Row-level changes | Domain events (richer) |
| **Existing data** | Snapshot supported | Manual backfill |
| **Best for** | Heterogeneous data sync | Microservices domain events |

**Production recommendation:** Outbox table + Debezium ON outbox table = best of both.

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Inactive slot → WAL grows forever | Monitor; drop unused slots |
| `REPLICA IDENTITY DEFAULT` only PK | Use `FULL` if need old row in UPDATE |
| Schema change breaks consumers | Use schema registry + compatibility rules |
| Huge initial snapshot blocks | Use `snapshot.mode=schema_only` if data already synced |
| Tombstones (delete + null) confuse consumers | Filter `op=d` separately |
| Duplicate events on consumer restart | Idempotent handlers; track LSN |
| TOAST columns null in UPDATE | Set `REPLICA IDENTITY FULL` or use Debezium options |
| Kafka topic compaction loses history | Use log-only retention for event sourcing |
| Network partition → stale slot | Health check + alert |

---

## When NOT to use CDC

- Sync only a few rows per day → polling is simpler
- Strict consistency required → CDC is eventually consistent
- Sensitive data → all rows go through Kafka (encryption needed)
- Tiny team without ops capacity → Kafka Connect is heavy

---

## Senior-level Checklist

- [ ] `wal_level=logical` configured
- [ ] Replication slot created + monitored
- [ ] `REPLICA IDENTITY` set per table (FULL if needed)
- [ ] Publication created with explicit table list
- [ ] Debezium connector with `pgoutput` plugin
- [ ] Consumer idempotent (LSN-based dedup or upsert)
- [ ] Schema evolution handled (`.get()` with defaults)
- [ ] Replication slot lag monitoring + alerts
- [ ] DLQ for failed event processing
- [ ] Outbox table for explicit domain events
- [ ] Snapshot strategy decided (`initial`, `schema_only`, `never`)
- [ ] Tombstone handling
- [ ] Encryption at rest + in transit (Kafka TLS)

---

## Related Docs
- `09_postgresql_ha_read_replicas.md` — replication concepts
- `04_window_functions_cte.md` — advanced SQL
- `Phase2_Kafka/` — Kafka deep dive
- `Phase3_Microservices/04_outbox_event_sourcing.md` — outbox pattern depth
- `Phase3_Microservices/05_event_sourcing_cqrs.md` — event-driven architecture
