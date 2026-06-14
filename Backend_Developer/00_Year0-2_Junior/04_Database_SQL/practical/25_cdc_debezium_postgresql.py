"""
PostgreSQL Change Data Capture (CDC) with Debezium — Production Patterns
=========================================================================
Topics covered
--------------
1.  PostgreSQL WAL / logical-replication setup reference (SQL + config)
2.  Debezium connector registration via Kafka Connect REST API
3.  CDC event schema — before/after/op/source structure
4.  CDCEvent dataclass — typed wrapper around raw Debezium JSON
5.  CDCConsumer — async aiokafka consumer with per-table/per-op handler registry
6.  Schema-evolution-safe handler pattern (`.get()` with defaults)
7.  Idempotent handler — LSN-based dedup via Redis SET NX
8.  Outbox pattern — write domain events inside the same DB transaction
9.  Outbox publisher — polling loop that drains the outbox table to Kafka
10. Replication slot lag monitor — periodic alert when lag exceeds threshold
11. Dead-letter queue (DLQ) for failed event processing
12. Docker Compose reference string for local dev stack

External dependencies (none required to import this module):
  pip install aiokafka aioredis sqlalchemy[asyncio] asyncpg httpx
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

# ==========================================================================
# 0. LOGGING SETUP
# ==========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("cdc")

# ==========================================================================
# 1. POSTGRESQL WAL CONFIGURATION REFERENCE
# ==========================================================================

POSTGRESQL_CONF_CHANGES = """
# postgresql.conf — enable logical replication
wal_level = logical                     # 'replica' will NOT work for CDC
max_wal_senders = 10                    # concurrent replication connections
max_replication_slots = 10             # number of persistent slots
max_logical_replication_workers = 4    # background decoding workers

# Restart required after these changes:
# sudo systemctl restart postgresql
"""

POSTGRESQL_SETUP_SQL = """
-- ── 1. Create a dedicated replication user ──────────────────────────────────
CREATE ROLE debezium WITH LOGIN REPLICATION PASSWORD 'secret';
GRANT CONNECT ON DATABASE mydb TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;

-- ── 2. Create publication (explicit table list is safer than ALL TABLES) ────
CREATE PUBLICATION my_publication FOR TABLE orders, users, products;

-- ── 3. Set REPLICA IDENTITY so UPDATE/DELETE events carry the full old row ──
ALTER TABLE orders REPLICA IDENTITY FULL;
ALTER TABLE users  REPLICA IDENTITY FULL;

-- ── 4. Verify ───────────────────────────────────────────────────────────────
SELECT * FROM pg_replication_slots;
SELECT * FROM pg_publication;
SELECT * FROM pg_publication_tables WHERE pubname = 'my_publication';

-- ── 5. Monitor WAL lag per slot ─────────────────────────────────────────────
SELECT
    slot_name,
    plugin,
    active,
    pg_size_pretty(
        pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)
    ) AS lag_size
FROM pg_replication_slots;
"""

# ==========================================================================
# 2. DOCKER COMPOSE — LOCAL DEV STACK
# ==========================================================================

DOCKER_COMPOSE_YML = """
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
"""

# ==========================================================================
# 3. DEBEZIUM CONNECTOR REGISTRATION (Kafka Connect REST API)
# ==========================================================================

CONNECTOR_CONFIG: dict[str, Any] = {
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
        "plugin.name": "pgoutput",          # built into PostgreSQL >= 10
        "publication.name": "my_publication",
        "slot.name": "debezium_slot",
        "snapshot.mode": "initial",         # dump existing rows first, then stream
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "false",
        "value.converter.schemas.enable": "false",
        # Tombstone: emit null value for DELETE so compacted topics shrink
        "tombstones.on.delete": "true",
    },
}


async def register_debezium_connector(
    connect_base_url: str = "http://localhost:8083",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    POST a connector configuration to the Kafka Connect REST API.

    In production call this once during infrastructure provisioning, or on
    connector absence (idempotent: use PUT /connectors/{name}/config instead
    if the connector already exists).

    Requires: pip install httpx
    """
    # pip install httpx
    import httpx  # type: ignore

    payload = config or CONNECTOR_CONFIG
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{connect_base_url}/connectors",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        log.info("Connector registered: %s", result.get("name"))
        return result


async def get_connector_status(
    connector_name: str,
    connect_base_url: str = "http://localhost:8083",
) -> dict[str, Any]:
    """Return the running status of a Debezium connector."""
    import httpx  # type: ignore

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{connect_base_url}/connectors/{connector_name}/status",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]


# ==========================================================================
# 4. CDC EVENT SCHEMA — typed wrapper around raw Debezium JSON
# ==========================================================================

class CDCOperation(str, Enum):
    """
    Debezium `op` field values.
    """
    CREATE = "c"     # INSERT
    UPDATE = "u"     # UPDATE
    DELETE = "d"     # DELETE
    READ = "r"       # Initial snapshot read
    TRUNCATE = "t"   # TRUNCATE TABLE


@dataclass
class CDCSource:
    """Metadata embedded in every Debezium event."""
    version: str
    connector: str
    name: str           # topic prefix / logical name
    ts_ms: int          # wall-clock time the change occurred in the DB
    snapshot: str       # 'true' | 'false' | 'last'
    db: str
    schema: str
    table: str
    lsn: int            # PostgreSQL Log Sequence Number — globally unique & ordered
    xmin: Optional[int] = None

    @property
    def occurred_at(self) -> datetime:
        """UTC datetime of the original DB change."""
        return datetime.fromtimestamp(self.ts_ms / 1000, tz=timezone.utc)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CDCSource":
        return cls(
            version=data.get("version", ""),
            connector=data.get("connector", ""),
            name=data.get("name", ""),
            ts_ms=data.get("ts_ms", 0),
            snapshot=str(data.get("snapshot", "false")),
            db=data.get("db", ""),
            schema=data.get("schema", "public"),
            table=data.get("table", ""),
            lsn=data.get("lsn", 0),
            xmin=data.get("xmin"),
        )


@dataclass
class CDCEvent:
    """
    Typed wrapper around a raw Debezium JSON payload.

    Structure:
        {
          "before": {...} | null,
          "after":  {...} | null,
          "source": {...},
          "op":     "c" | "u" | "d" | "r" | "t",
          "ts_ms":  1714579201250   # time Debezium emitted the event
        }
    """
    op: CDCOperation
    before: Optional[dict[str, Any]]
    after: Optional[dict[str, Any]]
    source: CDCSource
    ts_ms: int
    raw: dict[str, Any] = field(repr=False)

    @property
    def table(self) -> str:
        return self.source.table

    @property
    def lsn(self) -> int:
        """PostgreSQL Log Sequence Number — use for idempotent dedup."""
        return self.source.lsn

    @property
    def event_id(self) -> str:
        """Stable, unique string ID derived from table + LSN."""
        return f"{self.table}_{self.lsn}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CDCEvent":
        return cls(
            op=CDCOperation(data["op"]),
            before=data.get("before"),
            after=data.get("after"),
            source=CDCSource.from_dict(data.get("source", {})),
            ts_ms=data.get("ts_ms", 0),
            raw=data,
        )


# ==========================================================================
# 5. CDC CONSUMER — async Kafka consumer with handler registry
# ==========================================================================

# Handler type: async def handler(event: CDCEvent) -> None
HandlerFn = Callable[["CDCEvent"], Awaitable[None]]


class CDCConsumer:
    """
    Async Kafka consumer that routes Debezium events to registered handlers.

    Usage
    -----
    consumer = CDCConsumer(
        bootstrap_servers="localhost:9092",
        topics=["myapp.public.orders", "myapp.public.users"],
        group_id="search-indexer",
    )

    @consumer.on("orders", CDCOperation.CREATE)
    async def handle_order_created(event: CDCEvent) -> None:
        await index_order(event.after)

    asyncio.run(consumer.start())

    Requires: pip install aiokafka
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topics: list[str],
        group_id: str,
        dlq_topic: str | None = None,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topics = topics
        self._group_id = group_id
        self._dlq_topic = dlq_topic
        # { table_name: { CDCOperation: handler } }
        self._handlers: dict[str, dict[CDCOperation, HandlerFn]] = {}
        self._consumer: Any = None   # aiokafka.AIOKafkaConsumer
        self._producer: Any = None   # aiokafka.AIOKafkaProducer (DLQ)

    # ── Handler registration ──────────────────────────────────────────────

    def on(self, table: str, op: CDCOperation):
        """
        Decorator factory to register an event handler.

        @consumer.on("orders", CDCOperation.CREATE)
        async def created(event: CDCEvent) -> None: ...
        """
        def decorator(fn: HandlerFn) -> HandlerFn:
            self._handlers.setdefault(table, {})[op] = fn
            log.debug("Handler registered: table=%s op=%s fn=%s", table, op, fn.__name__)
            return fn
        return decorator

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start consuming.  Blocks until cancelled."""
        # pip install aiokafka
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore

        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            auto_offset_reset="earliest",   # catch up from beginning if no committed offset
            enable_auto_commit=False,        # manual commit — only after successful handling
            value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        )

        if self._dlq_topic:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()

        await self._consumer.start()
        log.info(
            "CDCConsumer started | topics=%s group=%s",
            self._topics,
            self._group_id,
        )
        try:
            async for msg in self._consumer:
                await self._dispatch(msg)
                await self._consumer.commit()   # commit offset only after success
        finally:
            await self._consumer.stop()
            if self._producer:
                await self._producer.stop()

    # ── Internal dispatch ─────────────────────────────────────────────────

    async def _dispatch(self, msg: Any) -> None:
        raw = msg.value
        if raw is None:
            # Tombstone message from Debezium (delete + compaction marker) — skip
            log.debug("Tombstone received on %s", msg.topic)
            return

        try:
            event = CDCEvent.from_dict(raw)
        except (KeyError, ValueError) as exc:
            log.error("Malformed CDC event on %s: %s — %r", msg.topic, exc, raw)
            await self._send_to_dlq(raw, error=str(exc))
            return

        table_handlers = self._handlers.get(event.table, {})
        handler = table_handlers.get(event.op)

        if handler is None:
            log.debug("No handler for table=%s op=%s — skipping", event.table, event.op)
            return

        try:
            await handler(event)
        except Exception as exc:
            log.exception(
                "Handler failed | table=%s op=%s lsn=%s: %s",
                event.table, event.op, event.lsn, exc,
            )
            await self._send_to_dlq(raw, error=str(exc))
            raise   # re-raise so offset is NOT committed — message will be retried

    async def _send_to_dlq(self, payload: dict[str, Any], error: str) -> None:
        """Forward unprocessable events to the Dead-Letter Queue topic."""
        if self._producer is None or self._dlq_topic is None:
            return
        dlq_payload = {"error": error, "original": payload}
        await self._producer.send(self._dlq_topic, value=dlq_payload)
        log.warning("Event sent to DLQ: %s", self._dlq_topic)


# ==========================================================================
# 6. SCHEMA-EVOLUTION-SAFE HANDLER PATTERN
# ==========================================================================

def safe_extract(row: dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Gracefully retrieve a column that may not exist in older CDC events.

    Columns added after the consumer was deployed will be absent from
    events captured before the schema migration, so KeyError must never
    propagate out of a handler.
    """
    return row.get(key, default)


async def example_schema_safe_handler(event: CDCEvent) -> None:
    """
    Demonstrates robust field access when columns may be added/dropped mid-stream.
    """
    if event.after is None:
        return

    # ✅ Always use .get() with sensible defaults
    status = safe_extract(event.after, "status")
    if status is None:
        return  # column might not exist in events replayed from old WAL

    # New column introduced in a later migration — default to 0.0
    discount = safe_extract(event.after, "discount_amount", 0.0)
    total = safe_extract(event.after, "total", 0.0)

    log.info(
        "Order id=%s status=%s total=%.2f discount=%.2f",
        event.after.get("id"),
        status,
        total,
        discount,
    )


# ==========================================================================
# 7. IDEMPOTENT HANDLER — LSN-BASED DEDUP VIA REDIS
# ==========================================================================

async def idempotent_handler_factory(
    redis_client: Any,   # aioredis.Redis
    inner: HandlerFn,
    dedup_ttl_seconds: int = 7 * 24 * 3600,
) -> HandlerFn:
    """
    Wraps a handler to make it exactly-once via Redis SET NX.

    Kafka provides at-least-once delivery — consumers MUST be idempotent.
    The PostgreSQL LSN acts as a globally ordered, unique event identifier.

    Requires: pip install aioredis
    """
    async def wrapped(event: CDCEvent) -> None:
        done_key = f"cdc:done:{event.event_id}"
        lock_key = f"cdc:lock:{event.event_id}"

        # Acquire lock to prevent concurrent worker races
        # pip install aioredis
        acquired = await redis_client.set(lock_key, "1", nx=True, ex=30)
        if not acquired:
            log.debug("Another worker is processing %s — skipping", event.event_id)
            return

        try:
            already_processed = await redis_client.get(done_key)
            if already_processed:
                log.debug("Duplicate event %s — skipping", event.event_id)
                return

            await inner(event)

            await redis_client.setex(done_key, dedup_ttl_seconds, "1")
        finally:
            await redis_client.delete(lock_key)

    return wrapped


# ==========================================================================
# 8. OUTBOX PATTERN — WRITE DOMAIN EVENTS ATOMICALLY WITH THE BUSINESS TX
# ==========================================================================

OUTBOX_TABLE_SQL = """
-- Run once via migration tooling (e.g. Alembic)
CREATE TABLE outbox_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  TEXT        NOT NULL,   -- e.g. 'order', 'user'
    aggregate_id    TEXT        NOT NULL,   -- PK of the changed row
    event_type      TEXT        NOT NULL,   -- e.g. 'order_created', 'order_shipped'
    payload         JSONB       NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN     DEFAULT FALSE
);

-- Partial index — only covers unprocessed rows, stays small after pruning
CREATE INDEX idx_outbox_unprocessed
    ON outbox_events(created_at)
    WHERE NOT processed;
"""


async def create_order_with_outbox(
    session: Any,       # sqlalchemy.ext.asyncio.AsyncSession
    order_data: dict[str, Any],
) -> int:
    """
    Create an order AND queue a domain event in the SAME database transaction.

    This is the core Outbox guarantee: the business row and the event record
    are either both committed or both rolled back — no dual-write inconsistency.

    Requires: pip install sqlalchemy[asyncio] asyncpg
    """
    from sqlalchemy import text  # type: ignore

    async with session.begin():
        # ── Step 1: write the business row ────────────────────────────────
        order_result = await session.execute(
            text(
                "INSERT INTO orders (user_id, total, status) "
                "VALUES (:user_id, :total, 'pending') RETURNING id"
            ),
            {"user_id": order_data["user_id"], "total": order_data["total"]},
        )
        order_id: int = order_result.scalar_one()

        # ── Step 2: write the outbox event (same transaction!) ────────────
        await session.execute(
            text(
                "INSERT INTO outbox_events "
                "(aggregate_type, aggregate_id, event_type, payload) "
                "VALUES (:agg_type, :agg_id, :evt_type, CAST(:payload AS jsonb))"
            ),
            {
                "agg_type": "order",
                "agg_id": str(order_id),
                "evt_type": "order_created",
                "payload": json.dumps({**order_data, "order_id": order_id}),
            },
        )
        # Both writes committed atomically here
    log.info("Order %s created with outbox event", order_id)
    return order_id


# ==========================================================================
# 9. OUTBOX PUBLISHER — POLLING LOOP
# ==========================================================================

async def outbox_publisher(
    async_session_factory: Any,    # async_sessionmaker
    kafka_producer: Any,           # aiokafka.AIOKafkaProducer
    poll_interval_seconds: float = 1.0,
    batch_size: int = 100,
) -> None:
    """
    Background task that drains pending outbox rows to Kafka.

    Run as a standalone service (or Celery beat task) alongside the main app.
    For production, prefer pointing Debezium at the outbox table instead of
    polling — eliminates this loop entirely while keeping domain-event semantics.

    Requires: pip install aiokafka sqlalchemy[asyncio] asyncpg
    """
    from sqlalchemy import text  # type: ignore

    log.info("Outbox publisher started (poll_interval=%.1fs)", poll_interval_seconds)
    while True:
        try:
            async with async_session_factory() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, aggregate_type, aggregate_id, event_type, payload "
                            "FROM outbox_events "
                            "WHERE NOT processed "
                            "ORDER BY created_at "
                            f"LIMIT {batch_size} "
                            "FOR UPDATE SKIP LOCKED"   # safe for concurrent publishers
                        )
                    )
                ).fetchall()

                for row in rows:
                    topic = f"events.{row.aggregate_type}"
                    await kafka_producer.send(
                        topic,
                        value=json.dumps(row.payload).encode("utf-8"),
                        key=row.aggregate_id.encode("utf-8"),
                    )
                    await session.execute(
                        text("UPDATE outbox_events SET processed = TRUE WHERE id = :id"),
                        {"id": row.id},
                    )
                    log.debug("Published %s → %s", row.event_type, topic)

                await session.commit()
                if rows:
                    log.info("Outbox flushed %d event(s)", len(rows))

        except Exception:
            log.exception("Outbox publisher error — will retry")

        await asyncio.sleep(poll_interval_seconds)


# ==========================================================================
# 10. REPLICATION SLOT LAG MONITOR
# ==========================================================================

async def monitor_replication_lag(
    async_session_factory: Any,    # async_sessionmaker
    alert_fn: Callable[[str], Awaitable[None]],
    lag_threshold_bytes: int = 1_000_000_000,   # 1 GB
    check_interval_seconds: float = 60.0,
) -> None:
    """
    Periodically query pg_replication_slots and alert when WAL lag is excessive.

    PRODUCTION CRITICAL: an inactive replication slot causes WAL to accumulate
    indefinitely.  If Debezium stops consuming, the PostgreSQL disk fills up.

    Run as a Celery beat task, Kubernetes CronJob, or background asyncio task.

    Requires: pip install sqlalchemy[asyncio] asyncpg
    """
    from sqlalchemy import text  # type: ignore

    log.info(
        "Slot lag monitor started (threshold=%d bytes, interval=%.0fs)",
        lag_threshold_bytes,
        check_interval_seconds,
    )
    while True:
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    text("""
                        SELECT
                            slot_name,
                            active,
                            pg_wal_lsn_diff(
                                pg_current_wal_lsn(),
                                confirmed_flush_lsn
                            ) AS lag_bytes
                        FROM pg_replication_slots
                    """)
                )
                for row in result:
                    log.info(
                        "Slot %-30s active=%-5s lag=%s",
                        row.slot_name,
                        row.active,
                        f"{row.lag_bytes:,} bytes" if row.lag_bytes else "N/A",
                    )
                    if row.lag_bytes and row.lag_bytes > lag_threshold_bytes:
                        msg = (
                            f"[CDC ALERT] Replication slot '{row.slot_name}' "
                            f"lag={row.lag_bytes:,} bytes — consumer may be down!"
                        )
                        log.warning(msg)
                        await alert_fn(msg)

        except Exception:
            log.exception("Replication slot monitor error")

        await asyncio.sleep(check_interval_seconds)


# ==========================================================================
# 11. CONCRETE HANDLER EXAMPLES (wired to a CDCConsumer)
# ==========================================================================

def build_consumer(
    bootstrap_servers: str = "localhost:9092",
    topic_prefix: str = "myapp",
    group_id: str = "search-indexer",
    dlq_topic: str = "cdc.dlq",
) -> CDCConsumer:
    """
    Factory that creates and wires a CDCConsumer with example handlers.

    Demonstrates the full lifecycle:
      - order INSERT  → index in Elasticsearch
      - order UPDATE  → update index + notify user on status change
      - order DELETE  → remove from index
      - user  INSERT  → provision resources in downstream service
    """
    consumer = CDCConsumer(
        bootstrap_servers=bootstrap_servers,
        topics=[
            f"{topic_prefix}.public.orders",
            f"{topic_prefix}.public.users",
        ],
        group_id=group_id,
        dlq_topic=dlq_topic,
    )

    # ── Orders ────────────────────────────────────────────────────────────

    @consumer.on("orders", CDCOperation.CREATE)
    async def on_order_created(event: CDCEvent) -> None:
        order = event.after
        if order is None:
            return
        log.info("[orders/c] New order id=%s user=%s total=%s",
                 order.get("id"), order.get("user_id"), order.get("total"))
        # In production:
        #   await elasticsearch.index("orders", id=order["id"], document=order)
        #   await notifications.send(order["user_id"], f"Order #{order['id']} created")

    @consumer.on("orders", CDCOperation.UPDATE)
    async def on_order_updated(event: CDCEvent) -> None:
        before = event.before or {}
        after = event.after or {}

        # Detect status transitions — schema-safe with .get()
        old_status = safe_extract(before, "status")
        new_status = safe_extract(after, "status")

        if old_status != new_status and new_status is not None:
            log.info("[orders/u] Status change id=%s %s → %s",
                     after.get("id"), old_status, new_status)
            # await notifications.send(after["user_id"], f"Order status: {new_status}")

        # Upsert is naturally idempotent — safe to replay
        # await elasticsearch.index("orders", id=after["id"], document=after)

    @consumer.on("orders", CDCOperation.DELETE)
    async def on_order_deleted(event: CDCEvent) -> None:
        deleted = event.before or {}
        log.info("[orders/d] Order deleted id=%s", deleted.get("id"))
        # await elasticsearch.delete("orders", id=deleted["id"])

    # ── Users ─────────────────────────────────────────────────────────────

    @consumer.on("users", CDCOperation.CREATE)
    async def on_user_created(event: CDCEvent) -> None:
        user = event.after or {}
        log.info("[users/c] New user id=%s email=%s",
                 user.get("id"), user.get("email"))
        # await provision_user_resources(user)

    @consumer.on("users", CDCOperation.READ)
    async def on_user_snapshot(event: CDCEvent) -> None:
        """Handles 'r' events from the initial Debezium snapshot."""
        user = event.after or {}
        log.debug("[users/r] Snapshot user id=%s", user.get("id"))
        # await backfill_search_index("users", user)

    return consumer


# ==========================================================================
# 12. CDC vs OUTBOX COMPARISON (as runtime-readable dict)
# ==========================================================================

CDC_VS_OUTBOX: list[dict[str, str]] = [
    {
        "aspect": "Setup complexity",
        "debezium_cdc": "High — Kafka Connect cluster required",
        "outbox_pattern": "Low — just an extra table",
    },
    {
        "aspect": "Latency",
        "debezium_cdc": "~1 second (WAL-to-Kafka pipeline)",
        "outbox_pattern": "Depends on polling interval (1s typical)",
    },
    {
        "aspect": "Coupling",
        "debezium_cdc": "Loose — business code unaware of downstream",
        "outbox_pattern": "Tight — app code inserts event rows explicitly",
    },
    {
        "aspect": "Event semantics",
        "debezium_cdc": "Row-level (before/after columns)",
        "outbox_pattern": "Domain events (richer, explicit payload)",
    },
    {
        "aspect": "Existing data",
        "debezium_cdc": "Snapshot supported (snapshot.mode=initial)",
        "outbox_pattern": "Manual backfill required",
    },
    {
        "aspect": "Best for",
        "debezium_cdc": "Heterogeneous data sync, search indexing, ETL",
        "outbox_pattern": "Microservices domain events, audit log",
    },
    {
        "aspect": "Production recommendation",
        "debezium_cdc": "Outbox table PLUS Debezium ON outbox",
        "outbox_pattern": "Best of both worlds",
    },
]


def print_comparison() -> None:
    """Print CDC vs Outbox comparison to stdout."""
    print("\n" + "=" * 72)
    print("  CDC (Debezium) vs Outbox Pattern")
    print("=" * 72)
    col_w = 20
    print(f"{'Aspect':<{col_w}} {'Debezium CDC':<28} {'Outbox Pattern'}")
    print("-" * 72)
    for row in CDC_VS_OUTBOX:
        print(
            f"{row['aspect']:<{col_w}} "
            f"{row['debezium_cdc'][:27]:<28} "
            f"{row['outbox_pattern']}"
        )
    print("=" * 72 + "\n")


# ==========================================================================
# 13. PRODUCTION GOTCHAS REFERENCE
# ==========================================================================

PRODUCTION_GOTCHAS: list[dict[str, str]] = [
    {
        "gotcha": "Inactive replication slot → WAL grows forever",
        "fix": "Monitor lag; drop unused slots with pg_drop_replication_slot()",
    },
    {
        "gotcha": "REPLICA IDENTITY DEFAULT only carries PK in UPDATE/DELETE",
        "fix": "ALTER TABLE ... REPLICA IDENTITY FULL for old-row values",
    },
    {
        "gotcha": "Schema change breaks consumer (KeyError on new/removed column)",
        "fix": "Always use .get() with defaults; consider Confluent Schema Registry",
    },
    {
        "gotcha": "Huge initial snapshot blocks WAL slot for hours",
        "fix": "Use snapshot.mode=schema_only if data already seeded elsewhere",
    },
    {
        "gotcha": "Tombstone messages (op=d, value=null) confuse consumers",
        "fix": "Guard with 'if raw is None: return' before parsing",
    },
    {
        "gotcha": "Duplicate events on consumer restart (at-least-once delivery)",
        "fix": "Idempotent handlers — LSN-based dedup in Redis or upsert pattern",
    },
    {
        "gotcha": "TOAST columns appear as null in UPDATE events",
        "fix": "REPLICA IDENTITY FULL or Debezium TOAST handling options",
    },
    {
        "gotcha": "Kafka topic compaction removes intermediate events",
        "fix": "Use log-only (non-compacted) retention for event sourcing topics",
    },
]


# ==========================================================================
# 14. DEMONSTRATION — runs without external infra (simulates event processing)
# ==========================================================================

def _make_sample_event(op: str, table: str = "orders") -> dict[str, Any]:
    """Build a realistic Debezium event dict for local testing."""
    common_source = {
        "version": "2.7.0",
        "connector": "postgresql",
        "name": "myapp",
        "ts_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "snapshot": "false",
        "db": "mydb",
        "schema": "public",
        "table": table,
        "lsn": 28_473_028,
        "xmin": None,
    }

    if op == "c":
        return {
            "before": None,
            "after": {
                "id": 42, "user_id": 7, "total": 999.99,
                "status": "pending", "created_at": 1_714_579_200_000_000,
            },
            "source": common_source,
            "op": "c",
            "ts_ms": common_source["ts_ms"] + 16,
        }

    if op == "u":
        return {
            "before": {"id": 42, "user_id": 7, "total": 999.99, "status": "pending"},
            "after":  {"id": 42, "user_id": 7, "total": 999.99, "status": "shipped",
                       "discount_amount": 50.0},
            "source": common_source,
            "op": "u",
            "ts_ms": common_source["ts_ms"] + 16,
        }

    if op == "d":
        return {
            "before": {"id": 42, "user_id": 7, "total": 999.99, "status": "shipped"},
            "after":  None,
            "source": common_source,
            "op": "d",
            "ts_ms": common_source["ts_ms"] + 16,
        }

    raise ValueError(f"Unknown op: {op!r}")


async def _demo_event_parsing() -> None:
    """Parse and inspect sample CDC events without any external services."""
    print("\n" + "=" * 60)
    print("  CDC Event Parsing Demo (no Kafka required)")
    print("=" * 60)

    for op_code, label in [("c", "CREATE"), ("u", "UPDATE"), ("d", "DELETE")]:
        raw = _make_sample_event(op_code)
        event = CDCEvent.from_dict(raw)

        print(f"\n[{label}]")
        print(f"  table      : {event.table}")
        print(f"  op         : {event.op}")
        print(f"  lsn        : {event.lsn}")
        print(f"  event_id   : {event.event_id}")
        print(f"  occurred_at: {event.source.occurred_at.isoformat()}")
        print(f"  before     : {event.before}")
        print(f"  after      : {event.after}")

        # Demonstrate schema-safe extraction on UPDATE
        if op_code == "u" and event.after:
            status = safe_extract(event.after, "status")
            discount = safe_extract(event.after, "discount_amount", 0.0)
            print(f"  status (safe_extract) : {status}")
            print(f"  discount (safe_extract, default=0.0) : {discount}")


async def _demo_consumer_dispatch() -> None:
    """
    Simulate the CDCConsumer dispatch loop without connecting to Kafka.
    Calls _dispatch directly with synthetic messages.
    """
    print("\n" + "=" * 60)
    print("  CDCConsumer Dispatch Demo (no Kafka required)")
    print("=" * 60)

    consumer = build_consumer()

    # Simulate a message object
    class FakeMsg:
        def __init__(self, value: dict[str, Any], topic: str = "myapp.public.orders") -> None:
            self.value = value
            self.topic = topic

    events_to_simulate = [
        FakeMsg(_make_sample_event("c"), "myapp.public.orders"),
        FakeMsg(_make_sample_event("u"), "myapp.public.orders"),
        FakeMsg(_make_sample_event("d"), "myapp.public.orders"),
        FakeMsg(None, "myapp.public.orders"),   # tombstone
    ]

    for msg in events_to_simulate:
        print(f"\n  Dispatching topic={msg.topic} value={msg.value!r:.80}")
        await consumer._dispatch(msg)

    print("\n  All events dispatched successfully.")


if __name__ == "__main__":
    async def main() -> None:
        print_comparison()

        print("\nProduction Gotchas:")
        print("-" * 60)
        for g in PRODUCTION_GOTCHAS:
            print(f"  GOTCHA : {g['gotcha']}")
            print(f"  FIX    : {g['fix']}")
            print()

        await _demo_event_parsing()
        await _demo_consumer_dispatch()

        print("\n" + "=" * 60)
        print("  Configuration Summaries")
        print("=" * 60)
        print("\n[PostgreSQL WAL config changes]")
        print(POSTGRESQL_CONF_CHANGES)
        print("\n[Debezium connector config preview]")
        print(json.dumps(CONNECTOR_CONFIG, indent=2)[:800], "...")
        print("\nDone. For full CDC pipeline, start the Docker Compose stack and")
        print("call: asyncio.run(build_consumer().start())")

    asyncio.run(main())
