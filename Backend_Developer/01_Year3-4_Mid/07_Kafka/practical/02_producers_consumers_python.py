"""
Kafka Producers & Consumers — Python Client Patterns
======================================================
Covers every concept from 02_producers_consumers_python.md:

  * aiokafka async producer — fire-and-forget vs send_and_wait
  * aiokafka async consumer — per-message and batch processing
  * Auto-commit vs manual commit semantics
  * Idempotent consumer (DB unique-constraint + Redis dedup patterns)
  * Idempotent producer + Kafka transactions
  * ConsumerRebalanceListener — graceful partition handoff
  * Cooperative sticky rebalancing (Kafka 2.4+)
  * Manual partition assignment (bypass consumer group)
  * Message headers for trace propagation / schema versioning
  * Compression types and trade-offs
  * Error handling — retriable vs non-retriable, dead-letter queue
  * Producer performance tuning (linger_ms, batch_size, lz4)
  * Consumer performance tuning (fetch_min_bytes, max_poll_records)
  * confluent-kafka-python synchronous producer/consumer example
  * pytest / testcontainers fixture skeleton

All classes and functions are production-quality, illustrative modules.
A lightweight __main__ demo runs without any external Kafka broker —
it exercises the helper utilities that do not require network I/O.

Dependencies (none are required to *import* this module at study time):
  pip install aiokafka                  # async Kafka client
  pip install confluent-kafka           # librdkafka-backed high-performance client
  pip install redis                     # Redis dedup helper
  pip install testcontainers[kafka]     # Docker-based integration testing
  pip install pytest pytest-asyncio     # async test runner
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# ==========================================================================
# LOGGING SETUP
# ==========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# ==========================================================================
# 1. SERIALIZATION HELPERS
# ==========================================================================

def json_serializer(value: Any) -> bytes:
    """Serialize a Python object to UTF-8 JSON bytes for Kafka values."""
    return json.dumps(value, default=str).encode("utf-8")


def json_deserializer(data: bytes) -> Any:
    """Deserialize UTF-8 JSON bytes from Kafka into a Python object."""
    return json.loads(data.decode("utf-8"))


def key_serializer(key: str | None) -> bytes | None:
    """Encode a string partition key to bytes, or return None."""
    return key.encode("utf-8") if key else None


# ==========================================================================
# 2. AIOKAFKA PRODUCER — PRODUCTION CONFIGURATION
# ==========================================================================

# pip install aiokafka
try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.errors import RecordTooLargeError, KafkaConnectionError
    _AIOKAFKA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AIOKAFKA_AVAILABLE = False


def build_producer(
    bootstrap_servers: str = "localhost:9092",
    *,
    linger_ms: int = 10,
    batch_size: int = 16_384,
    compression_type: str = "lz4",
    enable_idempotence: bool = True,
    acks: str = "all",
    retries: int = 10,
    retry_backoff_ms: int = 100,
    max_request_size: int = 1_048_576,
) -> "AIOKafkaProducer":
    """
    Construct a tuned AIOKafkaProducer.

    Key parameters
    --------------
    linger_ms         — accumulate messages up to this window before flushing.
                        Increases throughput by building larger batches.
    batch_size        — maximum bytes per batch per partition.
    compression_type  — 'lz4' gives the best CPU / ratio trade-off;
                        use 'gzip' for maximum compression (higher CPU).
    enable_idempotence — prevents duplicate writes caused by retries.
                         Requires acks='all'.
    acks              — 'all' waits for all in-sync replicas; most durable.
    retries           — automatic retry count for transient broker errors.
    max_request_size  — cap on a single produce request payload.
    """
    if not _AIOKAFKA_AVAILABLE:
        raise RuntimeError("aiokafka is not installed — pip install aiokafka")

    return AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=json_serializer,
        key_serializer=key_serializer,
        acks=acks,
        enable_idempotence=enable_idempotence,
        compression_type=compression_type,
        linger_ms=linger_ms,
        max_batch_size=batch_size,
        retries=retries,
        retry_backoff_ms=retry_backoff_ms,
        max_request_size=max_request_size,
    )


# --------------------------------------------------------------------------
# 2a. FIRE-AND-FORGET vs SEND-AND-WAIT
# --------------------------------------------------------------------------

async def produce_fire_and_forget(
    producer: "AIOKafkaProducer",
    topic: str,
    messages: list[dict[str, Any]],
) -> None:
    """
    Send messages without waiting for per-message acknowledgement.

    Use when maximum throughput matters and you are willing to rely on
    the producer's internal retry mechanism rather than individual ACKs.
    Call producer.flush() at the end to drain the internal buffer.
    """
    for i, payload in enumerate(messages):
        # send() returns a Future but we do NOT await it here
        await producer.send(
            topic=topic,
            key=f"user-{i % 10}",
            value=payload,
            headers=[("trace_id", uuid.uuid4().bytes)],
        )
    # Drain remaining buffered records so we do not lose data on exit
    await producer.flush()
    log.info("Fire-and-forget: flushed %d messages to %s", len(messages), topic)


async def produce_with_ack(
    producer: "AIOKafkaProducer",
    topic: str,
    payload: dict[str, Any],
    key: str | None = None,
    trace_id: str | None = None,
) -> tuple[int, int]:
    """
    Send a single message and wait for broker acknowledgement.

    Returns (partition, offset) of the written record.
    Use when you need confirmation that a specific message was persisted
    before proceeding (e.g., after a database write).
    """
    headers = []
    if trace_id:
        headers.append(("trace_id", trace_id.encode("utf-8")))
    headers.append(("source", b"checkout-service"))
    headers.append(("schema_version", b"v2"))

    record_metadata = await producer.send_and_wait(
        topic=topic,
        key=key,
        value=payload,
        headers=headers,
    )
    log.info(
        "Delivered: topic=%s partition=%d offset=%d",
        record_metadata.topic,
        record_metadata.partition,
        record_metadata.offset,
    )
    return record_metadata.partition, record_metadata.offset


async def run_producer_demo(
    bootstrap_servers: str = "localhost:9092",
    topic: str = "orders",
    count: int = 100,
) -> None:
    """
    Full producer lifecycle: start → produce 100 orders → stop.

    Demonstrates both fire-and-forget batching and awaited delivery.
    """
    producer = build_producer(bootstrap_servers)
    await producer.start()
    try:
        # Batch of fire-and-forget messages
        messages = [{"order_id": i, "amount": 100 + i} for i in range(count)]
        await produce_fire_and_forget(producer, topic, messages)

        # Single critical message with ACK
        await produce_with_ack(
            producer,
            topic,
            payload={"order_id": count, "amount": 9999, "priority": "high"},
            key="user-vip",
            trace_id=str(uuid.uuid4()),
        )
    except RecordTooLargeError as exc:
        # Non-retriable — the message itself is too large; fix the data, not the retry
        log.error("Message too large, skipping: %s", exc)
    except KafkaConnectionError as exc:
        log.error("Cannot reach broker: %s", exc)
    finally:
        await producer.stop()


# ==========================================================================
# 3. AIOKAFKA CONSUMER — PRODUCTION CONFIGURATION
# ==========================================================================

try:
    from aiokafka import AIOKafkaConsumer
    _CONSUMER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CONSUMER_AVAILABLE = False


def build_consumer(
    *topics: str,
    bootstrap_servers: str = "localhost:9092",
    group_id: str = "order-processor",
    auto_offset_reset: str = "earliest",
    enable_auto_commit: bool = False,
    max_poll_records: int = 100,
    fetch_min_bytes: int = 10_240,
    fetch_max_wait_ms: int = 500,
) -> "AIOKafkaConsumer":
    """
    Construct a tuned AIOKafkaConsumer.

    Key parameters
    --------------
    enable_auto_commit  — set False for manual commit (at-least-once safety).
    auto_offset_reset   — 'earliest' replays from the beginning when no
                          committed offset is found; 'latest' skips old data.
    max_poll_records    — upper bound of records returned per poll call.
    fetch_min_bytes     — broker waits until this many bytes are available,
                          reducing round-trips for low-volume topics.
    fetch_max_wait_ms   — maximum wait time at the broker when fetch_min_bytes
                          is not yet satisfied.
    """
    if not _CONSUMER_AVAILABLE:
        raise RuntimeError("aiokafka is not installed — pip install aiokafka")

    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=json_deserializer,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=enable_auto_commit,
        max_poll_records=max_poll_records,
        fetch_min_bytes=fetch_min_bytes,
        fetch_max_wait_ms=fetch_max_wait_ms,
    )


# --------------------------------------------------------------------------
# 3a. PER-MESSAGE CONSUMER LOOP (manual commit)
# --------------------------------------------------------------------------

async def consume_per_message(
    consumer: "AIOKafkaConsumer",
    process_fn: Any,
    dlq_producer: "AIOKafkaProducer | None" = None,
    max_messages: int | None = None,
) -> None:
    """
    Process one message at a time; commit only after successful handling.

    If processing raises an exception the offset is NOT committed, so the
    broker will redeliver the message to the next consumer in the group —
    at-least-once delivery guarantee.

    Messages that cannot be processed after MAX_RETRIES are forwarded to
    the dead-letter queue topic so they do not block the main consumer.
    """
    processed = 0
    async for msg in consumer:
        try:
            await process_fn(msg.value, _extract_headers(msg))
            await consumer.commit()
            processed += 1
            log.debug("Committed offset %d on partition %d", msg.offset, msg.partition)
        except Exception as exc:
            log.error(
                "Processing failed for offset %d: %s — not committing",
                msg.offset,
                exc,
            )
            if dlq_producer is not None:
                await _send_to_dlq(dlq_producer, msg, str(exc))
        if max_messages is not None and processed >= max_messages:
            break


# --------------------------------------------------------------------------
# 3b. BATCH CONSUMER LOOP
# --------------------------------------------------------------------------

async def consume_in_batches(
    consumer: "AIOKafkaConsumer",
    process_fn: Any,
    timeout_ms: int = 1000,
    max_records: int = 100,
) -> None:
    """
    Fetch multiple messages at once using getmany().

    More efficient than per-message polling when processing is fast and
    you want to amortise commit overhead across many records.
    Commit is issued once per batch after all records are processed.
    """
    while True:
        batch: dict[Any, list[Any]] = await consumer.getmany(
            timeout_ms=timeout_ms,
            max_records=max_records,
        )
        if not batch:
            continue

        for topic_partition, messages in batch.items():
            log.info(
                "Processing batch of %d from %s",
                len(messages),
                topic_partition,
            )
            for msg in messages:
                await process_fn(msg.value, _extract_headers(msg))

        # Commit the entire batch atomically after all records succeed
        await consumer.commit()


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def _extract_headers(msg: Any) -> dict[str, str]:
    """Convert raw Kafka header bytes to a plain string dict."""
    return {
        k.decode("utf-8") if isinstance(k, bytes) else k: (
            v.decode("utf-8") if isinstance(v, bytes) else str(v)
        )
        for k, v in (msg.headers or [])
    }


# ==========================================================================
# 4. AUTO-COMMIT vs MANUAL COMMIT
# ==========================================================================

async def consumer_auto_commit_example(bootstrap_servers: str = "localhost:9092") -> None:
    """
    Auto-commit consumer — simple but lossy.

    Every auto_commit_interval_ms milliseconds the consumer commits the
    current position regardless of whether those messages were processed
    successfully.  A crash between commits means those messages are lost,
    so this does NOT guarantee at-least-once delivery.

    Use only when occasional message loss is acceptable (e.g., metrics
    aggregation where eventual consistency is enough).
    """
    consumer = AIOKafkaConsumer(  # type: ignore[name-defined]
        "orders",
        bootstrap_servers=bootstrap_servers,
        group_id="orders-auto",
        value_deserializer=json_deserializer,
        enable_auto_commit=True,
        auto_commit_interval_ms=5000,  # flush committed offset every 5 seconds
    )
    await consumer.start()
    try:
        async for msg in consumer:
            log.info("Auto-commit consumer received: %s", msg.value)
            # No explicit commit — the background task handles it
    finally:
        await consumer.stop()


# ==========================================================================
# 5. IDEMPOTENT CONSUMER PATTERNS
# ==========================================================================

class DatabaseIdempotencyStore:
    """
    Pattern 1: Track processed message IDs in a relational database.

    The processed table has a UNIQUE constraint on msg_id; inserting a
    duplicate raises an integrity error that we catch and ignore.
    This makes the consumer idempotent regardless of how many times the
    broker delivers the same message.

    Production implementation uses asyncpg or SQLAlchemy async.
    """

    def __init__(self) -> None:
        # In-memory stand-in for the DB unique constraint
        self._seen: set[str] = set()

    async def process(self, msg_id: str, payload: dict[str, Any]) -> bool:
        """
        Return True if the message was processed; False if it was a duplicate.

        In production replace the set operations with:
            await db.execute(
                "INSERT INTO processed (msg_id, ...) VALUES ($1, ...)",
                msg_id
            )
        and catch asyncpg.UniqueViolationError instead of ValueError.
        """
        if msg_id in self._seen:
            log.info("Duplicate message %s — skipping", msg_id)
            return False
        self._seen.add(msg_id)
        # --- actual business logic here ---
        log.info("DB-idempotent: processed msg_id=%s  payload=%s", msg_id, payload)
        return True


class RedisIdempotencyStore:
    """
    Pattern 2: Use Redis SET NX (set-if-not-exists) for deduplication.

    Redis SET with NX + EX is atomic: only one consumer in a fleet will
    succeed; others see a False return and skip processing.  The key
    expires after `ttl_seconds` to avoid unbounded memory growth.

    pip install redis
    """

    def __init__(self, redis_client: Any, ttl_seconds: int = 86_400) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def process(self, msg_id: str, payload: dict[str, Any]) -> bool:
        """
        Return True if this instance 'won' the dedup race and processed the
        message; False if another consumer or a retry already handled it.
        """
        key = f"processed:{msg_id}"
        # redis-py async: await self._redis.set(key, 1, nx=True, ex=self._ttl)
        # Sync simulation for illustrative purposes:
        acquired = getattr(self._redis, "set", None)
        if acquired is not None:
            result = self._redis.set(key, 1, nx=True, ex=self._ttl)
            if not result:
                log.info("Redis dedup: msg %s already processed", msg_id)
                return False
        log.info("Redis-idempotent: processed msg_id=%s  payload=%s", msg_id, payload)
        return True


# ==========================================================================
# 6. IDEMPOTENT PRODUCER + KAFKA TRANSACTIONS
# ==========================================================================

async def run_transactional_producer(
    bootstrap_servers: str = "localhost:9092",
    transactional_id: str = "order-processor-1",
) -> None:
    """
    Write to multiple topics atomically using Kafka transactions.

    The transactional producer guarantees that either ALL sends inside
    the transaction are committed to the broker, or NONE are.  This is
    the backbone of exactly-once processing pipelines (see file 05).

    transactional_id must be unique per logical producer instance so
    Kafka can fence zombie producers after a restart.
    """
    if not _AIOKAFKA_AVAILABLE:
        log.warning("aiokafka unavailable — skipping transactional demo")
        return

    producer = AIOKafkaProducer(  # type: ignore[name-defined]
        bootstrap_servers=bootstrap_servers,
        transactional_id=transactional_id,
        enable_idempotence=True,
        acks="all",
        value_serializer=json_serializer,
        key_serializer=key_serializer,
    )
    await producer.start()
    await producer.init_transactions()
    try:
        async with producer.transaction():
            await producer.send(
                "orders",
                value={"order_id": 1001, "status": "confirmed"},
                key="user-42",
            )
            await producer.send(
                "audit",
                value={"event": "order_confirmed", "order_id": 1001, "ts": datetime.now(timezone.utc).isoformat()},
            )
            # Both writes commit together or neither commits
            log.info("Transaction committed: orders + audit")
    except Exception as exc:
        log.error("Transaction aborted: %s", exc)
        raise
    finally:
        await producer.stop()


# ==========================================================================
# 7. REBALANCE LISTENER — GRACEFUL PARTITION HANDOFF
# ==========================================================================

try:
    from aiokafka import ConsumerRebalanceListener
    _LISTENER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LISTENER_AVAILABLE = False


class GracefulRebalanceListener:
    """
    Hook into consumer group rebalance events.

    on_partitions_revoked  — called BEFORE partitions are taken away.
                             Commit offsets and flush any in-progress state
                             so the next consumer starts cleanly.
    on_partitions_assigned — called AFTER new partitions are assigned.
                             Initialise per-partition state (e.g., load
                             a local cache for the new shard).

    Register with: consumer.subscribe(["orders"], listener=listener)
    """

    def __init__(self, consumer: Any) -> None:
        self._consumer = consumer
        self._in_flight_count: int = 0

    async def on_partitions_revoked(self, revoked: list[Any]) -> None:
        log.info(
            "Partitions being revoked: %s — flushing %d in-flight messages",
            revoked,
            self._in_flight_count,
        )
        # Commit current offsets before losing partition ownership
        try:
            await self._consumer.commit()
        except Exception as exc:
            log.error("Commit during revocation failed: %s", exc)

    async def on_partitions_assigned(self, assigned: list[Any]) -> None:
        log.info("Partitions assigned: %s — initialising state", assigned)
        self._in_flight_count = 0
        # Load per-partition cache / seek to specific offset if needed


# --------------------------------------------------------------------------
# 7a. COOPERATIVE STICKY REBALANCING (Kafka 2.4+)
# --------------------------------------------------------------------------

try:
    from aiokafka.coordinator.assignors.sticky.sticky_assignor import (
        StickyPartitionAssignor,
    )
    _STICKY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STICKY_AVAILABLE = False


def build_consumer_cooperative(
    *topics: str,
    bootstrap_servers: str = "localhost:9092",
    group_id: str = "order-processor-coop",
) -> "AIOKafkaConsumer":
    """
    Consumer using cooperative sticky assignor (Kafka 2.4+).

    Old eager rebalance: ALL partitions are revoked from ALL consumers,
    then re-assigned — causing a processing pause ("stop the world").

    Cooperative sticky: only the partitions that actually need to move are
    revoked; other partitions keep processing without interruption.
    Result: dramatically shorter pause during group membership changes.
    """
    kwargs: dict[str, Any] = dict(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=json_deserializer,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    if _STICKY_AVAILABLE:
        kwargs["partition_assignment_strategy"] = [StickyPartitionAssignor]

    return AIOKafkaConsumer(*topics, **kwargs)  # type: ignore[return-value]


# ==========================================================================
# 8. MANUAL PARTITION ASSIGNMENT (bypass consumer group)
# ==========================================================================

try:
    from aiokafka.structs import TopicPartition
    _TP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TP_AVAILABLE = False


async def consume_assigned_partition(
    topic: str,
    partition: int,
    bootstrap_servers: str = "localhost:9092",
    max_messages: int = 50,
) -> None:
    """
    Consume from a specific partition without joining a consumer group.

    Use cases:
      - Deterministic per-shard processing (each microservice handles one partition).
      - Replaying a single partition from a chosen offset for debugging.
      - Avoiding rebalance overhead in stateful stream processors.

    Note: no group_id means no offset tracking by Kafka; you must manage
    offsets externally (e.g., store them in your database).
    """
    if not (_CONSUMER_AVAILABLE and _TP_AVAILABLE):
        log.warning("aiokafka unavailable — skipping manual assignment demo")
        return

    consumer = AIOKafkaConsumer(bootstrap_servers=bootstrap_servers)
    await consumer.start()
    try:
        tp = TopicPartition(topic, partition)
        consumer.assign([tp])
        log.info("Manually assigned to %s partition %d", topic, partition)
        count = 0
        async for msg in consumer:
            log.info(
                "Manual[p%d o%d]: %s",
                msg.partition,
                msg.offset,
                msg.value,
            )
            count += 1
            if count >= max_messages:
                break
    finally:
        await consumer.stop()


# ==========================================================================
# 9. MESSAGE HEADERS — TRACE PROPAGATION & SCHEMA VERSIONING
# ==========================================================================

def build_headers(
    trace_id: str | None = None,
    source_service: str = "backend-service",
    schema_version: str = "v2",
) -> list[tuple[str, bytes]]:
    """
    Construct a standard set of Kafka message headers.

    Headers are key/value pairs carried alongside each message without
    being part of the serialised payload.  Use them for:
      - Distributed trace propagation (trace_id, span_id)
      - Schema version hints so consumers can choose the right deserialiser
      - Routing signals (e.g., priority queues, A/B flags)
      - Source service identification for debugging
    """
    return [
        ("trace_id", (trace_id or str(uuid.uuid4())).encode("utf-8")),
        ("source", source_service.encode("utf-8")),
        ("schema_version", schema_version.encode("utf-8")),
        ("produced_at", datetime.now(timezone.utc).isoformat().encode("utf-8")),
    ]


def extract_trace_id(msg: Any) -> str:
    """Pull the trace_id header from a consumed message for log correlation."""
    headers = _extract_headers(msg)
    return headers.get("trace_id", "unknown")


# ==========================================================================
# 10. ERROR HANDLING — RETRIABLE vs NON-RETRIABLE, DEAD-LETTER QUEUE
# ==========================================================================

class RetriableError(Exception):
    """Transient error — safe to retry with back-off."""


class NonRetriableError(Exception):
    """Permanent error — retrying will not help; send to DLQ."""


async def process_with_retry_and_dlq(
    msg: Any,
    process_fn: Any,
    dlq_producer: "AIOKafkaProducer",
    max_retries: int = 3,
    base_backoff_seconds: float = 1.0,
) -> None:
    """
    Process a message with exponential back-off retry and DLQ fallback.

    Algorithm:
      1. Attempt process_fn up to max_retries times.
      2. On RetriableError sleep 2^attempt * base_backoff_seconds and retry.
      3. If all retries fail, or a NonRetriableError is raised on the first
         attempt, forward the raw message to the dead-letter queue.

    The DLQ payload carries enough context for manual investigation:
    original value, headers, error text, and failure timestamp.
    """
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(max_retries):
        try:
            await process_fn(msg.value)
            return  # Success — no DLQ needed
        except RetriableError as exc:
            last_exc = exc
            backoff = base_backoff_seconds * (2 ** attempt)
            log.warning(
                "Retriable error on attempt %d/%d, back-off %.1fs: %s",
                attempt + 1,
                max_retries,
                backoff,
                exc,
            )
            await asyncio.sleep(backoff)
        except NonRetriableError as exc:
            last_exc = exc
            log.error("Non-retriable error — sending to DLQ immediately: %s", exc)
            break  # No point retrying

    await _send_to_dlq(dlq_producer, msg, str(last_exc))


async def _send_to_dlq(
    dlq_producer: "AIOKafkaProducer",
    original_msg: Any,
    error_text: str,
    dlq_topic_suffix: str = ".dlq",
) -> None:
    """
    Forward a failed message to the dead-letter queue topic.

    Convention: DLQ topic = original topic + '.dlq'
    (e.g., 'orders' → 'orders.dlq').

    The DLQ payload wraps the original value and attaches diagnostic
    metadata so the ops team can inspect, replay, or discard the message.
    """
    dlq_topic = (getattr(original_msg, "topic", None) or "unknown") + dlq_topic_suffix
    dlq_payload = {
        "original_value": original_msg.value if hasattr(original_msg, "value") else None,
        "original_headers": _extract_headers(original_msg) if hasattr(original_msg, "headers") else {},
        "original_topic": getattr(original_msg, "topic", None),
        "original_partition": getattr(original_msg, "partition", None),
        "original_offset": getattr(original_msg, "offset", None),
        "error": error_text,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await dlq_producer.send_and_wait(dlq_topic, value=dlq_payload)
        log.info("Sent failed message to DLQ topic '%s'", dlq_topic)
    except Exception as exc:
        # DLQ send itself failed — log and move on; do not block the consumer
        log.error("DLQ send failed: %s", exc)


# ==========================================================================
# 11. CONFLUENT-KAFKA-PYTHON (SYNCHRONOUS — HIGHER PERFORMANCE)
# ==========================================================================

# pip install confluent-kafka
try:
    from confluent_kafka import Producer as ConfluentProducer
    from confluent_kafka import Consumer as ConfluentConsumer
    _CONFLUENT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CONFLUENT_AVAILABLE = False

CONFLUENT_PRODUCER_CONFIG: dict[str, Any] = {
    "bootstrap.servers": "localhost:9092",
    "acks": "all",
    "compression.type": "lz4",
    "linger.ms": 10,
    "batch.num.messages": 10_000,
    "retries": 10,
    "retry.backoff.ms": 100,
}

CONFLUENT_CONSUMER_CONFIG: dict[str, Any] = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "confluent-consumer-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
    "max.poll.interval.ms": 300_000,
}


def confluent_delivery_report(err: Any, msg: Any) -> None:
    """
    Callback invoked by the confluent producer after each produce() call.

    Unlike aiokafka, confluent-kafka-python uses a callback model.
    Errors here indicate the message was NOT delivered; handle or alert.
    """
    if err is not None:
        log.error(
            "Confluent delivery failed | topic=%s partition=%s: %s",
            msg.topic(),
            msg.partition(),
            err,
        )
    else:
        log.debug(
            "Confluent delivered | topic=%s partition=%d offset=%d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def confluent_produce_batch(topic: str, payloads: list[dict[str, Any]]) -> None:
    """
    Synchronous batch produce using confluent-kafka-python.

    produce() is non-blocking — it enqueues into the internal librdkafka
    buffer.  poll(0) processes delivery callbacks without blocking.
    flush() at the end drains the buffer and blocks until all messages are
    delivered or the timeout expires.

    This pattern achieves ~100K–1M messages/sec with a single producer
    instance thanks to librdkafka's native C implementation.
    """
    if not _CONFLUENT_AVAILABLE:
        log.warning("confluent-kafka not installed — skipping confluent demo")
        return

    producer = ConfluentProducer(CONFLUENT_PRODUCER_CONFIG)  # type: ignore[name-defined]
    for i, payload in enumerate(payloads):
        producer.produce(
            topic=topic,
            key=f"key-{i}".encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
            callback=confluent_delivery_report,
        )
        # Serve delivery callbacks without blocking (pump the event loop)
        producer.poll(0)

    remaining = producer.flush(timeout=30)
    if remaining > 0:
        log.error("%d messages were NOT delivered before timeout", remaining)
    else:
        log.info("All %d confluent messages delivered", len(payloads))


def confluent_consume_loop(topic: str, max_messages: int = 50) -> None:
    """
    Synchronous consume loop using confluent-kafka-python.

    For non-blocking applications wrap this in a thread (concurrent.futures
    or asyncio.run_in_executor) so it does not stall the event loop.
    poll(timeout) blocks up to `timeout` seconds waiting for a message.
    """
    if not _CONFLUENT_AVAILABLE:
        log.warning("confluent-kafka not installed — skipping confluent demo")
        return

    consumer = ConfluentConsumer(CONFLUENT_CONSUMER_CONFIG)  # type: ignore[name-defined]
    consumer.subscribe([topic])
    try:
        received = 0
        while received < max_messages:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue  # no message within timeout window
            if msg.error():
                log.error("Consumer error: %s", msg.error())
                continue
            payload = json.loads(msg.value().decode("utf-8"))
            log.info("Confluent consumer received: %s", payload)
            consumer.commit(asynchronous=False)
            received += 1
    finally:
        consumer.close()


# ==========================================================================
# 12. PERFORMANCE TUNING REFERENCE
# ==========================================================================

# Producer tuning targets
PRODUCER_TUNING = {
    "default_throughput": "~10K messages/sec",
    "tuned_throughput": "~100K messages/sec (batching + lz4)",
    "multi_producer_throughput": "1M+ messages/sec per broker",
    "recommended_settings": {
        "linger_ms": 20,          # accumulate up to 20ms — key batching lever
        "batch_size": 65_536,     # 64 KB batches
        "compression_type": "lz4",
        "max_request_size": 1_048_576,  # 1 MB hard cap on a single request
    },
}

# Consumer tuning targets
CONSUMER_TUNING = {
    "recommended_settings": {
        "fetch_min_bytes": 10_240,   # wait for 10 KB — fewer round-trips
        "fetch_max_wait_ms": 500,    # broker-side wait cap
        "max_poll_records": 500,     # records per getmany() call
    },
}

# Compression trade-off table
COMPRESSION_TRADEOFFS = {
    "none":   {"cpu_cost": "0",        "compression_ratio": "1x"},
    "gzip":   {"cpu_cost": "High",     "compression_ratio": "8x"},
    "snappy": {"cpu_cost": "Low",      "compression_ratio": "4x"},
    "lz4":    {"cpu_cost": "Very low", "compression_ratio": "4x"},  # recommended default
    "zstd":   {"cpu_cost": "Medium",   "compression_ratio": "6x"},
}


def log_tuning_reference() -> None:
    """Print producer/consumer tuning guidance at startup for reference."""
    log.info("=== Kafka Performance Tuning Reference ===")
    log.info("Producer default throughput  : %s", PRODUCER_TUNING["default_throughput"])
    log.info("Producer tuned throughput    : %s", PRODUCER_TUNING["tuned_throughput"])
    log.info("Producer recommended config  : %s", PRODUCER_TUNING["recommended_settings"])
    log.info("Consumer recommended config  : %s", CONSUMER_TUNING["recommended_settings"])
    log.info("Compression options          : %s", list(COMPRESSION_TRADEOFFS.keys()))


# ==========================================================================
# 13. TESTING WITH TESTCONTAINERS (pytest fixture skeleton)
# ==========================================================================

# pip install testcontainers[kafka] pytest pytest-asyncio

TESTCONTAINERS_FIXTURE = '''
# test_kafka_integration.py
#
# Requires: pip install testcontainers[kafka] pytest pytest-asyncio aiokafka
#
# Run with: pytest test_kafka_integration.py -v

import pytest
import pytest_asyncio
from testcontainers.kafka import KafkaContainer

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json


@pytest.fixture(scope="session")
def kafka_bootstrap():
    """Spin up a real Kafka broker in Docker for the entire test session."""
    with KafkaContainer() as k:
        yield k.get_bootstrap_server()


@pytest.mark.asyncio
async def test_produce_then_consume(kafka_bootstrap):
    topic = "test-orders"

    producer = AIOKafkaProducer(
        bootstrap_servers=kafka_bootstrap,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=kafka_bootstrap,
        group_id="test-group",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    await producer.start()
    await consumer.start()
    try:
        sent_value = {"order_id": 1, "amount": 42.0}
        await producer.send_and_wait(topic, value=sent_value)

        msg = await consumer.getone()
        assert msg.value == sent_value, f"Expected {sent_value}, got {msg.value}"
        await consumer.commit()
    finally:
        await producer.stop()
        await consumer.stop()


@pytest.mark.asyncio
async def test_idempotent_producer(kafka_bootstrap):
    """Verify idempotent producer does not raise on normal sends."""
    producer = AIOKafkaProducer(
        bootstrap_servers=kafka_bootstrap,
        enable_idempotence=True,
        acks="all",
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()
    try:
        for i in range(5):
            await producer.send_and_wait("idem-test", value={"i": i})
    finally:
        await producer.stop()
'''


# ==========================================================================
# 14. STANDALONE DEMO — runs without a Kafka broker
# ==========================================================================

def _demo_serialization() -> None:
    """Verify round-trip JSON serialization and header utilities."""
    log.info("--- Serialization round-trip ---")
    payload = {"order_id": 7, "amount": 299.99, "currency": "USD"}
    encoded = json_serializer(payload)
    decoded = json_deserializer(encoded)
    assert decoded == payload, "Round-trip serialization failed"
    log.info("Serialization OK: %s", decoded)

    key_bytes = key_serializer("user-42")
    assert key_bytes == b"user-42"
    assert key_serializer(None) is None
    log.info("Key serializer OK: %s", key_bytes)


def _demo_headers() -> None:
    """Verify header construction."""
    log.info("--- Header construction ---")
    headers = build_headers(trace_id="abc-123", source_service="order-svc")
    header_dict = dict(headers)
    assert header_dict["trace_id"] == b"abc-123"
    assert header_dict["source"] == b"order-svc"
    assert header_dict["schema_version"] == b"v2"
    log.info("Headers OK: %s", {k: v.decode() for k, v in headers})


def _demo_idempotency_store() -> None:
    """Verify the in-memory DB idempotency store deduplicates correctly."""
    log.info("--- Idempotency store (DB pattern) ---")

    store = DatabaseIdempotencyStore()

    async def run() -> None:
        msg_id = "msg-001"
        payload = {"order_id": 1}

        first = await store.process(msg_id, payload)
        second = await store.process(msg_id, payload)   # duplicate
        assert first is True,  "First call should return True"
        assert second is False, "Duplicate should return False"
        log.info("DB idempotency OK: first=%s second=%s", first, second)

    asyncio.run(run())


def _demo_error_classifications() -> None:
    """Verify error class hierarchy."""
    log.info("--- Error class hierarchy ---")
    assert issubclass(RetriableError, Exception)
    assert issubclass(NonRetriableError, Exception)
    assert not issubclass(RetriableError, NonRetriableError)
    log.info("Error classes OK")


def _demo_compression_reference() -> None:
    """Print compression trade-off table."""
    log.info("--- Compression trade-offs ---")
    header = f"{'Type':<10} {'CPU Cost':<15} {'Ratio'}"
    log.info(header)
    log.info("-" * len(header))
    for codec, stats in COMPRESSION_TRADEOFFS.items():
        log.info("%-10s %-15s %s", codec, stats["cpu_cost"], stats["compression_ratio"])


if __name__ == "__main__":
    log.info("=" * 70)
    log.info("Kafka Producers & Consumers — standalone demo (no broker needed)")
    log.info("=" * 70)

    _demo_serialization()
    _demo_headers()
    _demo_idempotency_store()
    _demo_error_classifications()
    _demo_compression_reference()
    log_tuning_reference()

    log.info("=" * 70)
    log.info("All local demos passed.")
    log.info(
        "To run against a real broker, call:\n"
        "  asyncio.run(run_producer_demo('localhost:9092', 'orders', 100))\n"
        "  asyncio.run(run_transactional_producer('localhost:9092'))\n"
        "  confluent_produce_batch('orders', [{'id': i} for i in range(1000)])"
    )
    log.info("=" * 70)
