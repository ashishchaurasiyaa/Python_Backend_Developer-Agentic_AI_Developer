"""
Kafka Streams & Stream Processing — Production Patterns (Python)

Covers:
  - Faust agents, Records, and stateful Tables
  - Tumbling and hopping windowed aggregations
  - Filtering, mapping, and routing transformations
  - Stream-table joins for event enrichment
  - Sessionization, Top-K, and EWMA anomaly detection
  - Exactly-once processing guarantee
  - Event-time vs processing-time semantics and watermarks
  - Bytewax Dataflow-style processing (modern Python alternative)
  - PyFlink outline for heavy-duty distributed pipelines
  - Production considerations: state management, scaling, monitoring

Run command (Faust worker):
    faust -A 03_kafka_streams_processing worker -l info

Dependencies:
    pip install faust-streaming  # maintained Faust fork
    pip install bytewax          # modern Dataflow-style alternative
    pip install apache-flink     # PyFlink (heavy-duty Flink wrapper)

Note: This module is illustrative. A running Kafka broker is required for
Faust/Bytewax agents to consume events; however, all classes and functions
defined here are importable and syntactically complete without a live broker.
"""

import asyncio
import json
import logging
from datetime import timedelta
from functools import wraps
from typing import AsyncIterable, Dict, Optional

# pip install faust-streaming
import faust

log = logging.getLogger(__name__)


# ==========================================================================
# 1. FAUST APP — APPLICATION ENTRY POINT
# ==========================================================================

# processing_guarantee="exactly_once" wraps every consume-process-produce
# cycle in a single Kafka transaction. Cost: ~10-20% lower throughput.
# Use for financial pipelines or anywhere duplicate events are unacceptable.

app = faust.App(
    "order-stream",
    broker="kafka://localhost:9092",
    value_serializer="json",
    # Uncomment for exactly-once semantics (financial / correctness-critical):
    # processing_guarantee="exactly_once",
)


# ==========================================================================
# 2. RECORD SCHEMAS — typed event definitions
# ==========================================================================

class Order(faust.Record, serializer="json"):
    """Represents a single order event flowing through the stream."""

    order_id: str
    user_id: str
    product_id: str
    amount: float
    ts: float  # Unix epoch seconds — used for event-time windowing


class UserProfile(faust.Record, serializer="json"):
    """User profile stored in a compacted lookup topic / Table."""

    user_id: str
    name: str
    tier: str  # e.g. "gold", "silver", "bronze"


class Metric(faust.Record, serializer="json"):
    """Infrastructure metric event (CPU, latency, error rate, etc.)."""

    host: str
    metric_name: str
    value: float
    ts: float


class PageView(faust.Record, serializer="json"):
    """Page-view event for sessionization and Top-K tracking."""

    user_id: str
    product_id: str
    ts: float


# ==========================================================================
# 3. KAFKA TOPICS — declare input/output channels
# ==========================================================================

orders_topic = app.topic("orders", value_type=Order)
high_value_topic = app.topic("high-value-orders", value_type=Order)
enriched_topic = app.topic("enriched-orders")          # dict payloads
alerts_topic = app.topic("metric-alerts")
views_topic = app.topic("page-views", value_type=PageView)
user_updates_topic = app.topic("user-updates", value_type=UserProfile)


# ==========================================================================
# 4. STATEFUL TABLES — backed by RocksDB + Kafka changelog topic
# ==========================================================================

# On worker crash, Faust replays the changelog to rebuild local state.
# No data loss; recovery time grows with state size.

user_totals: faust.TableT[str, float] = app.Table(
    "user-totals",
    default=float,
    partitions=4,
    # Changelog topic: "user-totals-changelog" (auto-created)
)

orders_count: faust.TableT[str, int] = app.Table(
    "orders-count",
    default=int,
    partitions=4,
)

# Lookup table populated by a background agent consuming user updates
users_lookup: faust.TableT[str, Optional[dict]] = app.Table(
    "users-lookup",
    default=lambda: None,
    partitions=4,
)

sessions: faust.TableT[str, float] = app.Table(
    "user-sessions",
    default=float,
    partitions=4,
)

top_products: faust.TableT[str, int] = app.Table(
    "top-products",
    default=int,
    partitions=4,
)

ewma_table: faust.TableT[str, float] = app.Table(
    "ewma-baselines",
    default=float,
    partitions=4,
)


# ==========================================================================
# 5. WINDOWED TABLES — tumbling and hopping aggregations
# ==========================================================================

# Tumbling window: non-overlapping, fixed-size blocks of time.
# Each event falls into exactly one window.
# expires= sets how long past windows are retained in state.
orders_5min_tumbling = app.Table(
    "orders-5min",
    default=float,
    partitions=4,
).tumbling(timedelta(minutes=5), expires=timedelta(hours=1))

# Hopping window: overlapping windows, each event counted in multiple.
# size=1 hour, step=5 min → 12 overlapping windows per event.
orders_1hr_hopping = app.Table(
    "orders-1hr-hopping",
    default=float,
    partitions=4,
).hopping(
    size=timedelta(hours=1),
    step=timedelta(minutes=5),
    expires=timedelta(hours=2),
)

# Late-event tolerance (watermark): wait 10 min after window close before
# finalising the window, absorbing out-of-order events.
orders_5min_watermarked = app.Table(
    "orders-5min-wm",
    default=float,
    partitions=4,
).tumbling(
    timedelta(minutes=5),
    expires=timedelta(minutes=10),  # late tolerance / watermark
)


# ==========================================================================
# 6. SIMPLE PROCESSOR — baseline agent
# ==========================================================================

@app.agent(orders_topic)
async def process_orders(orders: AsyncIterable[Order]) -> None:
    """Log every incoming order. Offset management handled by Faust."""
    async for order in orders:
        log.info(
            "Received order order_id=%s user_id=%s amount=%.2f",
            order.order_id,
            order.user_id,
            order.amount,
        )


# ==========================================================================
# 7. REAL-TIME AGGREGATION — running totals per user
# ==========================================================================

@app.agent(orders_topic)
async def aggregate_user_totals(orders: AsyncIterable[Order]) -> None:
    """Maintain a running total of order amounts per user in real time.

    group_by() repartitions the stream by user_id so that all events for
    a given user land on the same partition and the same worker's local state.
    This is mandatory for consistent stateful aggregations.
    """
    async for order in orders.group_by(Order.user_id):
        user_totals[order.user_id] += order.amount
        orders_count[order.user_id] += 1

        log.debug(
            "Aggregated user_id=%s running_total=%.2f count=%d",
            order.user_id,
            user_totals[order.user_id],
            orders_count[order.user_id],
        )


# ==========================================================================
# 8. WINDOWED AGGREGATION — tumbling 5-minute windows
# ==========================================================================

@app.agent(orders_topic)
async def windowed_5min_totals(orders: AsyncIterable[Order]) -> None:
    """Accumulate order amounts in non-overlapping 5-minute tumbling windows.

    Event time is used by default (Kafka message timestamp). For accuracy
    with out-of-order events, use the watermarked table variant.

    Access the current window value:
        current_total = orders_5min_tumbling[user_id].current()
    """
    async for order in orders.group_by(Order.user_id):
        orders_5min_tumbling[order.user_id] += order.amount
        orders_5min_watermarked[order.user_id] += order.amount


# ==========================================================================
# 9. FILTERING & ROUTING — high-value order detection
# ==========================================================================

@app.agent(orders_topic)
async def route_high_value_orders(orders: AsyncIterable[Order]) -> None:
    """Forward orders above $1,000 to a dedicated topic.

    Pattern: read from one input topic, apply a predicate, write matching
    events to a downstream topic. Downstream consumers can specialise further
    (fraud review, VIP workflow, etc.).
    """
    async for order in orders:
        if order.amount > 1_000.0:
            log.info("High-value order detected order_id=%s amount=%.2f", order.order_id, order.amount)
            await high_value_topic.send(value=order)


# ==========================================================================
# 10. STREAM-TABLE JOIN — enrichment with user profile data
# ==========================================================================

@app.agent(user_updates_topic)
async def populate_users_lookup(profiles: AsyncIterable[UserProfile]) -> None:
    """Materialise user profiles into a local Table for O(1) enrichment.

    The changelog topic keeps this Table durable across restarts.
    """
    async for profile in profiles:
        users_lookup[profile.user_id] = {
            "name": profile.name,
            "tier": profile.tier,
        }
        log.debug("Upserted user profile user_id=%s", profile.user_id)


@app.agent(orders_topic)
async def enrich_orders(orders: AsyncIterable[Order]) -> None:
    """Join each order event with the users_lookup Table to add user context.

    Stream-table join: the Table acts as a continuously updated side-input.
    Produces enriched events to a downstream topic for analytics consumers.
    """
    async for order in orders:
        profile = users_lookup[order.user_id]
        if profile is None:
            log.warning("No profile found for user_id=%s — skipping enrichment", order.user_id)
            continue

        enriched_payload = {
            **order.asdict(),
            "user_name": profile["name"],
            "user_tier": profile["tier"],
        }
        await enriched_topic.send(value=enriched_payload)


# ==========================================================================
# 11. SESSIONIZATION — group events by inactivity gap
# ==========================================================================

SESSION_TIMEOUT = timedelta(minutes=30)


@app.agent(views_topic)
async def sessionize_views(events: AsyncIterable[PageView]) -> None:
    """Detect user session boundaries based on a 30-minute inactivity gap.

    A new session begins when the gap between the current event and the
    last recorded event exceeds SESSION_TIMEOUT. This is a common pattern
    in web analytics for computing session count and depth.
    """
    async for event in events.group_by(PageView.user_id):
        last_seen = sessions[event.user_id]
        gap = event.ts - last_seen if last_seen else None

        if gap is None or gap > SESSION_TIMEOUT.total_seconds():
            log.info(
                "New session detected user_id=%s gap_secs=%s",
                event.user_id,
                f"{gap:.0f}" if gap else "first event",
            )

        sessions[event.user_id] = event.ts


# ==========================================================================
# 12. TOP-K — maintain top 10 most-viewed products
# ==========================================================================

TOP_K = 10


@app.agent(views_topic)
async def track_top_products(views: AsyncIterable[PageView]) -> None:
    """Count views per product and log the current Top-K periodically.

    In production: emit the sorted Top-K to a dedicated output topic on a
    timer or after each N events, replacing the log statement below.
    """
    async for view in views:
        top_products[view.product_id] += 1

    # Periodic emit of Top-K (illustrative — runs after agent loop closes)
    sorted_products = sorted(top_products.items(), key=lambda kv: kv[1], reverse=True)
    top_k = sorted_products[:TOP_K]
    log.info("Current Top-%d products: %s", TOP_K, top_k)


# ==========================================================================
# 13. ANOMALY DETECTION — EWMA spike alerting
# ==========================================================================

metrics_topic = app.topic("metrics", value_type=Metric)

EWMA_ALPHA = 0.1       # smoothing factor (0 = no update, 1 = replace)
SPIKE_SIGMA = 3.0      # flag if value deviates more than 3× baseline


@app.agent(metrics_topic)
async def detect_anomalies(stream: AsyncIterable[Metric]) -> None:
    """Detect metric spikes using an Exponentially Weighted Moving Average.

    For each host+metric pair the baseline EWMA is updated continuously.
    When a new reading deviates from the baseline by more than SPIKE_SIGMA
    times the baseline value, an alert is emitted to the alerts topic.

    EWMA update rule:
        new_ewma = ALPHA * new_value + (1 - ALPHA) * old_ewma
    """
    async for m in stream.group_by(Metric.host):
        key = f"{m.host}:{m.metric_name}"
        baseline = ewma_table[key]

        # Prime the baseline with the first observation
        if baseline == 0.0:
            ewma_table[key] = m.value
            continue

        new_ewma = EWMA_ALPHA * m.value + (1 - EWMA_ALPHA) * baseline
        ewma_table[key] = new_ewma

        deviation = abs(m.value - baseline)
        threshold = SPIKE_SIGMA * baseline

        if deviation > threshold:
            alert_payload = {
                "host": m.host,
                "metric": m.metric_name,
                "value": m.value,
                "baseline": baseline,
                "deviation": deviation,
            }
            log.warning("Anomaly detected: %s", alert_payload)
            await alerts_topic.send(value=alert_payload)


# ==========================================================================
# 14. EXACTLY-ONCE PROCESSING — configuration note
# ==========================================================================

# To enable exactly-once semantics, initialise the app with:
#
#   app = faust.App(
#       "order-stream",
#       broker="kafka://localhost:9092",
#       value_serializer="json",
#       processing_guarantee="exactly_once",
#   )
#
# Every consume → process → produce cycle becomes an atomic Kafka transaction.
# Kafka broker version >= 2.5 required. Throughput cost: ~10-20%.
# Use for: financial pipelines, billing, inventory deductions.
# Avoid for: high-throughput analytics where at-least-once is acceptable.

EXACTLY_ONCE_NOTE = """
processing_guarantee options:
  "at_least_once"  — default; consumer commits after processing, possible
                     duplicates on crash (idempotent consumers required).
  "exactly_once"   — atomic transaction; each event processed exactly once
                     end-to-end (consume + process + produce).
"""


# ==========================================================================
# 15. EVENT TIME vs PROCESSING TIME — helper utility
# ==========================================================================

def event_age_seconds(event_ts: float) -> float:
    """Return how many seconds ago an event occurred (event-time lag).

    For accurate windowed aggregations use event_ts from the payload rather
    than wall-clock time. Large lag (>window size) may indicate a backlogged
    consumer or slow producer; surface this via monitoring.
    """
    import time
    return time.time() - event_ts


def log_time_semantics_summary() -> None:
    """Log a reminder about time semantics relevant to windowing decisions."""
    log.info(
        "Time semantics: use event_ts in payload (event time) for accurate "
        "windowing. Processing time (wall clock) causes drift with backlog. "
        "Watermark = grace period after window close for late arrivals."
    )


# ==========================================================================
# 16. BYTEWAX — Dataflow-style alternative (modern Python streams)
# ==========================================================================

# pip install bytewax
# Bytewax uses a stateless functional Dataflow API. No agents or Tables;
# operators transform streams as pure functions. Suitable for modern Python
# microservices that prefer explicit data-flow over magic.
#
# NOTE: code is defined inside a string block for documentation purposes.
# Bytewax workers are launched separately via `python -m bytewax.run`.

BYTEWAX_EXAMPLE = r"""
import json
import bytewax.operators as op
from bytewax.connectors.kafka import KafkaSource, KafkaSink
from bytewax.dataflow import Dataflow

flow = Dataflow("order-processor")

# --- Input ---
stream = op.input(
    "kafka-in",
    flow,
    KafkaSource(brokers=["localhost:9092"], topics=["orders"]),
)

# --- Deserialise ---
def parse_order(raw):
    return json.loads(raw.value)

parsed = op.map("parse", stream, parse_order)

# --- Filter: high-value only ---
high_value = op.filter(
    "hi-val",
    parsed,
    lambda order: order["amount"] > 1_000,
)

# --- Transform: tag tier ---
def tag_vip(order):
    order["tag"] = "vip"
    return order

tagged = op.map("tag-vip", high_value, tag_vip)

# --- Output ---
op.output(
    "kafka-out",
    tagged,
    KafkaSink(brokers=["localhost:9092"], topic="high-value-orders"),
)

# Run:
# python -m bytewax.run 03_kafka_streams_processing:flow
"""


# ==========================================================================
# 17. PYFLINK — heavy-duty distributed stream processing outline
# ==========================================================================

# pip install apache-flink
# PyFlink wraps Apache Flink's DataStream API. Use for enterprise workloads
# requiring complex joins, checkpointing, and massive horizontal scale.
# Learning curve is significantly steeper than Faust or Bytewax.

PYFLINK_EXAMPLE = r"""
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import (
    KafkaSource, KafkaOffsetsInitializer, KafkaSink,
)
from pyflink.common import WatermarkStrategy
from pyflink.datastream.window import TumblingEventTimeWindows
from pyflink.common.time import Time

env = StreamExecutionEnvironment.get_execution_environment()
env.set_parallelism(4)

# Source: Kafka topic with bounded-out-of-orderness watermark strategy
source = KafkaSource.builder() \
    .set_bootstrap_servers("localhost:9092") \
    .set_topics("orders") \
    .set_starting_offsets(KafkaOffsetsInitializer.latest()) \
    .build()

ds = env.from_source(
    source,
    WatermarkStrategy.for_bounded_out_of_orderness(Duration.ofMinutes(1)),
    "kafka-orders",
)

# Key by user_id, tumbling 5-minute event-time window, sum amounts
result = ds \
    .key_by(lambda order: order["user_id"]) \
    .window(TumblingEventTimeWindows.of(Time.minutes(5))) \
    .reduce(lambda a, b: {**a, "amount": a["amount"] + b["amount"]})

# Sink: Kafka output topic
result.sink_to(
    KafkaSink.builder()
        .set_bootstrap_servers("localhost:9092")
        .set_record_serializer(...)
        .build()
)

env.execute("flink-order-aggregation")

# Features: checkpointing, savepoints, exactly-once, complex joins,
# broadcast state, side outputs, async I/O enrichment.
"""


# ==========================================================================
# 18. PRODUCTION CONSIDERATIONS
# ==========================================================================

PRODUCTION_NOTES = """
STATE MANAGEMENT
  - Each Faust Table grows with cardinality. Set TTL / expiry on windows.
  - Use compacted changelog topics to avoid unbounded log growth.
  - Shard state across workers via group_by() on a high-cardinality key.

SCALING
  - Add worker processes: `faust -A app worker -l info --web-port 6067`
  - Faust auto-rebalances partitions across workers (like a consumer group).
  - Match worker count to topic partition count for maximum parallelism.

MONITORING
  - Consumer group lag: `kafka-consumer-groups --describe --group order-stream`
  - Faust web monitor (built-in): http://localhost:6066
  - Prometheus metrics via faust-prometheus plugin.
  - Alert on: lag > N seconds, processing rate drop, state store disk usage.

RESTART & RECOVERY
  - Faust replays the changelog topic on restart to rebuild local RocksDB state.
  - Large state → slow recovery. Tune `standby_replicas` for hot standby.
  - For Bytewax/PyFlink: use checkpointing to external store (S3, GCS).

EXACTLY-ONCE COST
  - ~10-20% throughput reduction due to Kafka transaction overhead.
  - Only enable for correctness-critical paths (billing, inventory).
  - For analytics, at-least-once + idempotent sinks is usually acceptable.

TOOLS COMPARISON
  Tool       | Scale           | Style         | Best for
  -----------|-----------------|---------------|------------------------
  Faust      | Microservice    | Agents/Tables | Mid-complexity Python
  Bytewax    | Distributed     | Dataflow ops  | Modern Pythonic apps
  PyFlink    | Enterprise      | DataStream    | Complex heavy pipelines
"""


# ==========================================================================
# 19. FAUST WORKER ENTRY POINT
# ==========================================================================

# Run the Faust worker:
#   faust -A 03_kafka_streams_processing worker -l info
#
# The `app.main()` call below allows running as a plain Python script:
#   python 03_kafka_streams_processing.py worker -l info

if __name__ == "__main__":
    app.main()
