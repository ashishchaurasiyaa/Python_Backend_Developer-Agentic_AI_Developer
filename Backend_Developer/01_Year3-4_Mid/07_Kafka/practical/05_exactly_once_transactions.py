"""
Kafka Exactly-Once Semantics & Transactions — Production Patterns

Covers all three layers required for true exactly-once delivery:
  Layer 1 — Idempotent Producer      (dedupes retried writes via PID + sequence)
  Layer 2 — Transactional Producer   (atomic multi-topic writes)
  Layer 3 — Read-Process-Write (RPW) (consumer offset committed inside the same txn)

Also demonstrates:
  - read_committed consumer isolation
  - Outbox pattern for DB + Kafka consistency
  - Idempotent consumer alternatives (DB unique constraint, Redis, conditional update)
  - Delivery-guarantee comparison helpers
  - Failure scenario commentary

Dependencies (none required to import this module; external infra optional):
  pip install aiokafka asyncpg aioredis
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# pip install aiokafka
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import OffsetAndMetadata, TopicPartition

# pip install asyncpg
import asyncpg

# pip install aioredis
import aioredis

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


# ==========================================================================
# 1. DELIVERY GUARANTEE CONSTANTS — reference map
# ==========================================================================

DELIVERY_GUARANTEES = {
    "at_most_once": {
        "description": "Fire-and-forget. Possible message loss; no duplicates.",
        "producer_config": {"acks": 0},
        "consumer_config": {"enable_auto_commit": True},
        "use_case": "Logging, metrics, click analytics — loss is acceptable.",
    },
    "at_least_once": {
        "description": "Retries on failure. No loss; possible duplicates.",
        "producer_config": {"acks": "all", "retries": 2_147_483_647},
        "consumer_config": {"enable_auto_commit": False},
        "use_case": "Most event-driven pipelines where consumer is idempotent.",
    },
    "exactly_once_kafka": {
        "description": "Idempotent producer + transactions + RPW. No loss, no duplicates inside Kafka.",
        "producer_config": {
            "enable_idempotence": True,
            "acks": "all",
            "transactional_id": "<unique-per-instance>",
        },
        "consumer_config": {
            "isolation_level": "read_committed",
            "enable_auto_commit": False,
        },
        "use_case": "Payments, inventory deduction, order placement.",
    },
    "effectively_exactly_once": {
        "description": "At-least-once delivery + idempotent consumer. Simpler than full Kafka txns.",
        "producer_config": {"enable_idempotence": True, "acks": "all"},
        "consumer_config": {
            "isolation_level": "read_committed",
            "enable_auto_commit": False,
        },
        "use_case": "Most production services; avoids Kafka transaction overhead.",
    },
}


def describe_guarantees() -> None:
    """Print a comparison of all delivery guarantees."""
    print("\n=== Delivery Guarantee Comparison ===")
    for name, details in DELIVERY_GUARANTEES.items():
        print(f"\n[{name}]")
        print(f"  Description : {details['description']}")
        print(f"  Use case    : {details['use_case']}")
        print(f"  Producer    : {details['producer_config']}")
        print(f"  Consumer    : {details['consumer_config']}")


# ==========================================================================
# 2. LAYER 1 — IDEMPOTENT PRODUCER
#    Producer ID (PID) + per-partition sequence number ensures the broker
#    rejects any message that is a duplicate of a previous write.
# ==========================================================================

def build_idempotent_producer(
    bootstrap_servers: str = "localhost:9092",
) -> AIOKafkaProducer:
    """
    Return an idempotent producer.

    enable_idempotence=True forces:
      - acks="all"     (all in-sync replicas must acknowledge)
      - retries > 0    (must retry on transient errors)
      - max_in_flight  <= 5 per connection

    The broker assigns a unique Producer ID (PID). Every message carries
    (PID, partition, sequence). The broker rejects any re-send with a
    sequence it has already committed — safe retry with no duplicate write.
    """
    return AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        enable_idempotence=True,   # enables PID + sequence deduplication
        acks="all",                # required by idempotent mode
        value_serializer=lambda v: json.dumps(v).encode(),
    )


async def idempotent_producer_demo(bootstrap_servers: str = "localhost:9092") -> None:
    """Send a single message with idempotent guarantees (Layer 1 only)."""
    producer = build_idempotent_producer(bootstrap_servers)
    await producer.start()
    try:
        msg = {"event": "order.created", "order_id": str(uuid.uuid4())}
        await producer.send_and_wait("orders", value=msg)
        log.info("Idempotent send complete: %s", msg)
    finally:
        await producer.stop()


# ==========================================================================
# 3. LAYER 2 — TRANSACTIONAL PRODUCER
#    Multiple sends across topics/partitions treated as a single atomic unit.
#    Either all messages are committed and visible, or none are.
# ==========================================================================

def build_transactional_producer(
    transactional_id: str,
    bootstrap_servers: str = "localhost:9092",
) -> AIOKafkaProducer:
    """
    Return a transactional producer.

    transactional_id must be:
      - Stable across process restarts (the broker uses it to fence stale instances).
      - Unique per logical producer stream (e.g. per partition it consumes).

    Lifecycle:
      await producer.start()
      await producer.init_transactions()   # register with TransactionCoordinator
      async with producer.transaction():   # begin → commit/abort
          await producer.send(...)
    """
    return AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        transactional_id=transactional_id,
        enable_idempotence=True,           # required for transactions
        acks="all",
        value_serializer=lambda v: json.dumps(v).encode(),
    )


async def atomic_multi_topic_write(
    order_id: str,
    bootstrap_servers: str = "localhost:9092",
) -> None:
    """
    Write to 'audit_log' and 'notifications' atomically (Layer 2).

    If the process crashes between the two sends, the partial transaction is
    aborted on the next startup: the broker sees the stale PID and issues an
    abort marker. read_committed consumers skip both messages.
    """
    producer = build_transactional_producer(
        transactional_id="payment-processor-v1",
        bootstrap_servers=bootstrap_servers,
    )
    await producer.start()
    await producer.init_transactions()

    try:
        async with producer.transaction():
            audit_event = {"order_id": order_id, "action": "payment_charged", "ts": time.time()}
            notif_event = {"order_id": order_id, "channel": "email", "template": "receipt"}

            await producer.send("audit_log", value=audit_event)
            await producer.send("notifications", value=notif_event)

            # Both messages are buffered; commit marker sent after this block exits.
            log.info("Transaction committed — audit_log + notifications for order %s", order_id)
    except Exception:
        # async context manager calls abort_transaction automatically on exception.
        log.exception("Transaction aborted for order %s", order_id)
        raise
    finally:
        await producer.stop()


# ==========================================================================
# 4. LAYER 3 — READ-PROCESS-WRITE (RPW)
#    Consumer offset is committed inside the same Kafka transaction as the
#    downstream send. Either both advance or neither does. This is the
#    canonical exactly-once pattern.
# ==========================================================================

async def process_payment(message_value: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate payment processing.

    In production this calls an idempotency-key-aware payment gateway
    (e.g. Stripe with idempotency_key=order_id) so that if the network
    call succeeds but the transaction later aborts and the message is
    re-delivered, the charge is not duplicated at the gateway layer either.
    """
    order_id = message_value.get("order_id", "unknown")
    amount = message_value.get("amount", 0)
    log.info("Processing payment — order=%s amount=%s", order_id, amount)
    await asyncio.sleep(0.01)   # simulate I/O
    return {
        "order_id": order_id,
        "amount": amount,
        "status": "charged",
        "charged_at": time.time(),
    }


async def exactly_once_processor(
    bootstrap_servers: str = "localhost:9092",
    max_messages: int = 0,   # 0 = run indefinitely
) -> None:
    """
    Exactly-once Read-Process-Write pipeline.

    For each message consumed from 'orders':
      1. Begin Kafka transaction.
      2. Call process_payment (idempotent gateway call).
      3. Write result to 'audit' and 'notifications' topics.
      4. Commit the consumer offset *inside the same transaction*.
      5. Commit (or abort on exception) the transaction.

    Crash scenarios:
      - Before step 5   → transaction aborted, consumer offset NOT advanced,
                          message re-delivered to next consumer instance.
      - After step 5    → transaction committed, offset advanced.
                          No duplicate; exactly-once.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        transactional_id="payment-svc-1",   # stable; fences stale instances
        enable_idempotence=True,
        acks="all",
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=bootstrap_servers,
        group_id="payment-svc",
        isolation_level="read_committed",   # skip messages from aborted transactions
        enable_auto_commit=False,           # we commit offsets via the producer txn
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
    )

    await producer.start()
    await consumer.start()
    await producer.init_transactions()

    processed = 0
    try:
        async for msg in consumer:
            async with producer.transaction():
                # Step 1 — process the business logic
                result = await process_payment(msg.value)

                # Step 2 — write downstream (atomically with offset commit)
                await producer.send("audit", value=result)
                await producer.send("notifications", value=result)

                # Step 3 — commit consumer offset as part of this transaction
                tp = TopicPartition(msg.topic, msg.partition)
                offsets = {tp: OffsetAndMetadata(msg.offset + 1, "")}
                await producer.send_offsets_to_transaction(offsets, "payment-svc")

            # Transaction committed: audit written + notification written + offset advanced.
            log.info(
                "Exactly-once commit — topic=%s partition=%d offset=%d order=%s",
                msg.topic, msg.partition, msg.offset, msg.value.get("order_id"),
            )
            processed += 1
            if max_messages and processed >= max_messages:
                break
    finally:
        await producer.stop()
        await consumer.stop()


# ==========================================================================
# 5. READ-COMMITTED CONSUMER — opt-in isolation
#    Without this, a consumer may read messages from in-flight or aborted
#    transactions ("dirty reads"). Always use read_committed when upstream
#    producers use transactions.
# ==========================================================================

def build_read_committed_consumer(
    topic: str,
    group_id: str,
    bootstrap_servers: str = "localhost:9092",
) -> AIOKafkaConsumer:
    """
    Return a consumer that only delivers messages from committed transactions.

    Trade-off: slight latency increase — the broker withholds messages until
    the transaction commit marker arrives. For non-transactional producers
    this adds no latency (marker is implicit per-message).
    """
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        isolation_level="read_committed",   # default is read_uncommitted
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
    )


# ==========================================================================
# 6. OUTBOX PATTERN — DB + Kafka consistency without Kafka transactions
#
#    Problem: charging a payment gateway and writing a Kafka event are two
#    separate systems. Even inside a Kafka transaction, the gateway call is
#    an external side effect that cannot be rolled back.
#
#    Solution: write the outbox row and the DB state change in a single DB
#    transaction. A separate poller reads the outbox and publishes to Kafka.
#    The poller uses an idempotent producer; at-least-once delivery + an
#    idempotent consumer equals "effectively exactly-once".
# ==========================================================================

OUTBOX_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status      TEXT NOT NULL DEFAULT 'pending',
    amount      NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
    id           BIGSERIAL PRIMARY KEY,
    event_type   TEXT        NOT NULL,
    payload      JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
"""


async def pay_order_with_outbox(
    db: asyncpg.Connection,
    order_id: str,
    amount: float,
) -> None:
    """
    Charge an order atomically: update orders table + insert outbox row
    in a single DB transaction.

    The Kafka publish happens later in outbox_publisher. If the service
    crashes before publishing, the poller picks up the unpublished row on
    restart — no event is lost and no double-charge occurs.
    """
    async with db.transaction():
        await db.execute(
            "UPDATE orders SET status = 'paid' WHERE id = $1",
            order_id,
        )
        await db.execute(
            """
            INSERT INTO outbox (event_type, payload)
            VALUES ('order.paid', $1::jsonb)
            """,
            json.dumps({"order_id": order_id, "amount": amount}),
        )
    log.info("DB transaction committed — order=%s outbox row inserted", order_id)


async def outbox_publisher(
    db: asyncpg.Connection,
    bootstrap_servers: str = "localhost:9092",
    poll_interval: float = 0.5,
    batch_size: int = 100,
) -> None:
    """
    Poll the outbox table and publish unpublished rows to Kafka.

    Uses an idempotent producer (not full Kafka transactions). If the
    process crashes mid-batch, rows remain unpublished and will be
    retried on the next poll cycle. Idempotent consumers handle the
    rare duplicate.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        enable_idempotence=True,
        acks="all",
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await producer.start()

    log.info("Outbox publisher started — polling every %.1fs", poll_interval)
    try:
        while True:
            rows = await db.fetch(
                "SELECT * FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT $1",
                batch_size,
            )
            for row in rows:
                # Publish to topic named after the event type (e.g. "order.paid")
                await producer.send_and_wait(
                    row["event_type"],
                    value=row["payload"],
                )
                await db.execute(
                    "UPDATE outbox SET published_at = now() WHERE id = $1",
                    row["id"],
                )
                log.debug("Published outbox row id=%d type=%s", row["id"], row["event_type"])

            if rows:
                log.info("Outbox batch published — %d events", len(rows))

            await asyncio.sleep(poll_interval)
    finally:
        await producer.stop()


# ==========================================================================
# 7. IDEMPOTENT CONSUMER PATTERNS — cheaper alternative to Kafka transactions
#    At-least-once delivery + idempotent consumer = effectively exactly-once.
# ==========================================================================

# --- 7a. DB unique constraint deduplication ---

async def process_with_db_dedup(
    db: asyncpg.Connection,
    msg_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Insert a processed-message record before doing real work.
    UniqueViolationError means we already handled this message; skip.

    Requires a table:
        CREATE TABLE processed_messages (
            msg_id TEXT PRIMARY KEY,
            processed_at TIMESTAMPTZ DEFAULT now()
        );
    """
    try:
        await db.execute(
            "INSERT INTO processed_messages (msg_id) VALUES ($1)",
            msg_id,
        )
    except asyncpg.UniqueViolationError:
        log.info("Duplicate message skipped — msg_id=%s", msg_id)
        return

    # Safe to process: guaranteed first time for this msg_id.
    log.info("Processing new message — msg_id=%s payload=%s", msg_id, payload)
    # await actual_work(payload)


# --- 7b. Redis set-if-not-exists deduplication ---

async def process_with_redis_dedup(
    redis: aioredis.Redis,
    msg_id: str,
    payload: Dict[str, Any],
    ttl_seconds: int = 86_400,   # 24-hour dedup window
) -> None:
    """
    Use Redis NX (set if not exists) as a lightweight dedup cache.

    NX guarantees atomicity: only one concurrent processor will get True.
    TTL prevents the key set from growing unbounded.
    """
    acquired = await redis.set(
        f"processed:{msg_id}",
        1,
        nx=True,        # only set if key does not exist
        ex=ttl_seconds,
    )
    if not acquired:
        log.info("Duplicate message skipped (Redis) — msg_id=%s", msg_id)
        return

    log.info("Processing new message (Redis) — msg_id=%s", msg_id)
    # await actual_work(payload)


# --- 7c. Conditional update deduplication ---

async def apply_balance_event(
    db: asyncpg.Connection,
    account_id: str,
    event_id: str,
    amount: float,
) -> bool:
    """
    Apply a balance change only if last_event_id differs from event_id.

    UPDATE returns 0 rows if:
      - account does not exist, OR
      - last_event_id already equals event_id (duplicate).

    Returns True if the update was applied, False if it was a duplicate.
    """
    result = await db.execute(
        """
        UPDATE accounts
        SET    balance       = balance + $1,
               last_event_id = $2
        WHERE  id            = $3
          AND  last_event_id != $2
        """,
        amount, event_id, account_id,
    )
    rows_affected = int(result.split()[-1])   # "UPDATE N"
    if rows_affected == 0:
        log.info("Idempotent no-op — account=%s event=%s already applied", account_id, event_id)
        return False
    log.info("Balance updated — account=%s event=%s amount=%+.2f", account_id, event_id, amount)
    return True


# ==========================================================================
# 8. EFFECTIVELY EXACTLY-ONCE — PRACTICAL RECIPE
#    The recommended starting point for most production services.
#    Simpler than full Kafka transactions; covers the vast majority of cases.
# ==========================================================================

@dataclass
class ProcessedMessageStore:
    """In-memory dedup store — replace with DB or Redis in production."""
    _seen: set = field(default_factory=set)

    def already_processed(self, msg_id: str) -> bool:
        return msg_id in self._seen

    def mark_processed(self, msg_id: str) -> None:
        self._seen.add(msg_id)


async def effectively_exactly_once_consumer(
    bootstrap_servers: str = "localhost:9092",
    max_messages: int = 0,
) -> None:
    """
    At-least-once delivery + idempotency check = effectively exactly-once.

    Steps per message:
      1. Check if msg_id was already processed — if yes, commit and skip.
      2. Process business logic.
      3. Mark as processed.
      4. Manually commit offset.

    No Kafka transactions required. 10-30% higher throughput than full EOS.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        enable_idempotence=True,   # safe retries on the send side
        acks="all",
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers=bootstrap_servers,
        group_id="order-processor",
        isolation_level="read_committed",
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
    )

    store = ProcessedMessageStore()
    await producer.start()
    await consumer.start()

    processed = 0
    try:
        async for msg in consumer:
            msg_id = msg.value.get("order_id", str(msg.offset))

            if store.already_processed(msg_id):
                log.info("Skipping already-processed message — msg_id=%s", msg_id)
                await consumer.commit()
                continue

            # Business logic
            log.info("Processing order — msg_id=%s", msg_id)
            await asyncio.sleep(0.005)   # simulate work

            store.mark_processed(msg_id)
            await consumer.commit()

            processed += 1
            if max_messages and processed >= max_messages:
                break
    finally:
        await producer.stop()
        await consumer.stop()


# ==========================================================================
# 9. TRANSACTIONAL PRODUCER INTERNALS — commentary reference
# ==========================================================================

TRANSACTION_INTERNALS = """
Transactional Protocol (broker-side, two-phase commit analogue):

  1. Producer.start() + init_transactions()
       → Producer contacts TransactionCoordinator (a designated broker).
       → Coordinator registers transactional_id, issues Producer ID (PID).

  2. producer.transaction() enters begin_transaction()
       → Coordinator notes transaction open for this PID.

  3. producer.send(topic, partition, value)
       → Message written to partition with PID + sequence + txnId.
       → Broker buffers message; NOT yet visible to read_committed consumers.
       → Coordinator records which partitions are part of this transaction.

  4a. Transaction commit (async context manager exits normally)
       → Producer sends EndTxnRequest(commit=True) to Coordinator.
       → Coordinator writes COMMIT marker to every involved partition.
       → read_committed consumers unblock and see the messages.

  4b. Transaction abort (exception inside context manager, or explicit abort)
       → Coordinator writes ABORT marker to every involved partition.
       → read_committed consumers skip those messages silently.

Fencing stale producers:
  → On restart with same transactional_id, Coordinator increments epoch.
  → Old producer instance receives FencedInstanceError on any operation.
  → Ongoing transaction from old instance is aborted automatically.
"""


# ==========================================================================
# 10. FAILURE SCENARIO REFERENCE TABLE
# ==========================================================================

FAILURE_SCENARIOS: List[Dict[str, str]] = [
    {
        "scenario": "Producer crashes mid-transaction",
        "recovery": (
            "On restart with same transactional_id, Coordinator fences the "
            "old PID epoch and aborts the stale transaction. New instance "
            "calls init_transactions() and starts fresh."
        ),
    },
    {
        "scenario": "Network partition during commit",
        "recovery": (
            "Coordinator either commits or aborts based on quorum (ISR). "
            "Producer client retries; idempotent sequence numbers prevent "
            "duplicate messages even if the commit request is resent."
        ),
    },
    {
        "scenario": "Consumer crashes mid-process (before transaction commits)",
        "recovery": (
            "Offset was never committed (it is part of the aborted transaction). "
            "Next consumer instance reads the same message from its last "
            "committed offset. No data loss, no duplicate downstream write."
        ),
    },
    {
        "scenario": "Broker crashes during active transaction",
        "recovery": (
            "Kafka replication ensures transactional state survives broker failure. "
            "Replicas take over; in-flight transaction is either committed (if "
            "commit marker was replicated) or aborted."
        ),
    },
    {
        "scenario": "External side effect (payment gateway) succeeds but Kafka txn aborts",
        "recovery": (
            "Exactly-once guarantee does NOT extend outside Kafka. Use idempotency "
            "keys (e.g. Stripe idempotency_key=order_id) or the Outbox pattern to "
            "avoid double-charging at the external system."
        ),
    },
]


def print_failure_scenarios() -> None:
    """Print all failure scenarios and their recovery mechanisms."""
    print("\n=== Failure Scenarios & Recovery ===")
    for i, item in enumerate(FAILURE_SCENARIOS, 1):
        print(f"\n[{i}] {item['scenario']}")
        print(f"    {item['recovery']}")


# ==========================================================================
# 11. STREAM PROCESSING — EXACTLY-ONCE WITH FAUST / FLINK (config snippets)
# ==========================================================================

STREAM_PROCESSING_CONFIGS = {
    "faust": {
        "snippet": "app = faust.App('my-app', processing_guarantee='exactly_once')",
        "note": (
            "Faust wraps Kafka transactions internally. Every table changelog "
            "and output topic write is part of a single transaction per "
            "processing loop iteration."
        ),
    },
    "flink": {
        "snippet": (
            "env.get_checkpoint_config()"
            ".set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)"
        ),
        "note": (
            "Flink uses two-phase commit with Kafka transactions. Checkpoints "
            "align with Kafka transaction boundaries. Default checkpoint interval "
            "is the effective transaction batch window."
        ),
    },
}


# ==========================================================================
# 12. COST SUMMARY — WHEN TO USE EACH GUARANTEE
# ==========================================================================

COST_TABLE = """
Guarantee                | Throughput impact | Extra latency | Complexity | Use when
-------------------------|-------------------|---------------|------------|-------------------------------------
At-most-once             |  0%               | 0ms           | Low        | Logs, metrics, click streams
At-least-once            | ~0%               | +1-2ms        | Low        | Most event pipelines
Exactly-once (Kafka txn) | -10 to -30%       | +5-50ms       | High       | Payments, inventory, order placement
Effectively exactly-once | ~0%               | +1-2ms        | Medium     | Most production services (recommended)
"""

WHEN_NOT_TO_USE_EOS = [
    "Logging and analytics — message loss is tolerable.",
    "Hot-path low-latency services — 5-50ms per message is unacceptable.",
    "External systems already idempotent (Stripe idempotency keys, S3 put-if-absent).",
    "Counters reconciled periodically — occasional duplicates wash out.",
]

WHEN_MUST_USE_EOS = [
    "Money movement — payments, transfers, refunds.",
    "Inventory deduction — overselling is a business risk.",
    "Order placement — duplicate orders have financial and legal cost.",
    "Audit trails where completeness and uniqueness are compliance requirements.",
]


# ==========================================================================
# 13. DEMO ENTRYPOINT (runs without external infra — structural demonstration)
# ==========================================================================

async def _demo_structural() -> None:
    """
    Demonstrate module structure without requiring a live Kafka broker.

    Prints configuration objects, the transaction internals commentary,
    failure scenarios, and the cost comparison. All production functions
    above are importable and can be wired to a real broker by supplying
    bootstrap_servers="<host>:9092".
    """
    print("=" * 70)
    print(" Kafka Exactly-Once Semantics & Transactions — Module Demo")
    print("=" * 70)

    # 1. Delivery guarantee comparison
    describe_guarantees()

    # 2. Idempotent producer config
    print("\n=== Layer 1 — Idempotent Producer Config ===")
    idempotent = build_idempotent_producer.__doc__
    print(idempotent.strip())

    # 3. Transactional producer config
    print("\n=== Layer 2 — Transactional Producer Config ===")
    transactional = build_transactional_producer.__doc__
    print(transactional.strip())

    # 4. Idempotent consumer demo (in-memory store)
    print("\n=== Idempotent Consumer — in-memory dedup demo ===")
    store = ProcessedMessageStore()
    test_ids = ["order-001", "order-002", "order-001"]   # order-001 is a duplicate
    for oid in test_ids:
        if store.already_processed(oid):
            print(f"  SKIP duplicate: {oid}")
        else:
            print(f"  PROCESS new   : {oid}")
            store.mark_processed(oid)

    # 5. Transaction internals
    print("\n=== Layer 3 — Transaction Internals (Commentary) ===")
    print(TRANSACTION_INTERNALS)

    # 6. Failure scenarios
    print_failure_scenarios()

    # 7. Cost comparison
    print("\n=== Cost Comparison ===")
    print(COST_TABLE)

    print("\n=== When NOT to use Exactly-Once ===")
    for item in WHEN_NOT_TO_USE_EOS:
        print(f"  - {item}")

    print("\n=== When You MUST use Exactly-Once ===")
    for item in WHEN_MUST_USE_EOS:
        print(f"  - {item}")

    # 8. Stream processing configs
    print("\n=== Stream Processing EOS Configs ===")
    for name, cfg in STREAM_PROCESSING_CONFIGS.items():
        print(f"\n  [{name}]")
        print(f"    Config : {cfg['snippet']}")
        print(f"    Note   : {cfg['note']}")

    print("\n=== Production Usage ===")
    print(
        "  To run against a real Kafka broker:\n"
        "    asyncio.run(exactly_once_processor(bootstrap_servers='localhost:9092'))\n"
        "    asyncio.run(effectively_exactly_once_consumer(bootstrap_servers='localhost:9092'))\n"
        "  Outbox pattern requires a running PostgreSQL instance and asyncpg connection.\n"
        "  Redis dedup requires a running Redis instance and aioredis connection."
    )


if __name__ == "__main__":
    asyncio.run(_demo_structural())
