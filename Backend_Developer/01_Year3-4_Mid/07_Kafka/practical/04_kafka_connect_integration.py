"""
Kafka Connect & Integration — Production Patterns
==================================================

Kafka Connect is a standalone JVM framework that moves data between Kafka and
external systems (databases, object storage, search engines, data warehouses)
without writing custom producer/consumer code.

Key concepts covered:
  - Source vs Sink connectors
  - Debezium CDC (Change Data Capture) — most important source connector
  - JDBC source / sink connectors
  - Elasticsearch, S3, Snowflake sink connectors
  - Connect REST API management client (Python wrapper)
  - Schema Registry + Avro serialization
  - Single Message Transforms (SMT) configuration
  - Dead Letter Queue (DLQ) for error handling
  - Connector configuration dataclasses (GitOps-ready)
  - Common CDC pipeline patterns (Postgres → Elasticsearch, Kafka → S3)

External infrastructure (Kafka, Postgres, Elasticsearch, Schema Registry) is
not required to import or use most of this module — connectors are configured
and managed via the REST API client.  Where a __main__ demo makes sense without
live infra it is provided; otherwise classes are structured for production import.

pip install requests confluent-kafka confluent-kafka[avro] dataclasses-json
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("kafka_connect")


# =============================================================================
# 1. CONNECTOR CONFIGURATION DATACLASSES (GitOps-ready)
#    Store these as JSON/YAML in git; apply via CI using ConnectClient.
# =============================================================================


@dataclass
class ConnectorConfig:
    """Base class for any Kafka Connect connector configuration."""

    name: str
    config: Dict[str, str]

    def to_api_payload(self) -> Dict[str, Any]:
        """Return the JSON payload expected by the Connect REST API."""
        return {"name": self.name, "config": self.config}

    def to_json(self) -> str:
        return json.dumps(self.to_api_payload(), indent=2)


@dataclass
class DebeziumPostgresSourceConfig(ConnectorConfig):
    """
    Debezium PostgreSQL CDC source connector.

    Reads the Postgres Write-Ahead Log (WAL) and streams every INSERT, UPDATE,
    and DELETE to a Kafka topic named `<server_name>.<schema>.<table>`.

    Why Debezium over JDBC polling:
      - Log-based CDC has negligible DB load (just WAL replication).
      - Captures deletes (JDBC polling cannot see deleted rows).
      - Sub-second latency vs. polling interval.
    """

    def __init__(
        self,
        connector_name: str,
        hostname: str,
        port: str,
        user: str,
        password: str,
        dbname: str,
        server_name: str,
        table_include_list: str,
        plugin_name: str = "pgoutput",
    ) -> None:
        config = {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": hostname,
            "database.port": port,
            "database.user": user,
            "database.password": password,
            "database.dbname": dbname,
            "database.server.name": server_name,
            "table.include.list": table_include_list,
            "plugin.name": plugin_name,
            # Emit the full row "after" image in every event
            "decimal.handling.mode": "double",
            "time.precision.mode": "connect",
        }
        super().__init__(name=connector_name, config=config)


@dataclass
class JdbcSourceConfig(ConnectorConfig):
    """
    Confluent JDBC Source connector — polls a relational DB on an interval.

    Suitable when you cannot enable WAL-level CDC on the database (e.g. managed
    MySQL without binlog access).  Less efficient than Debezium: cannot capture
    deletes, higher DB load, latency = poll interval.

    Modes:
      incrementing — uses a monotonically-increasing column (e.g. auto-increment id).
      timestamp     — uses a timestamp column for detecting new/updated rows.
      bulk          — full-table dump every poll cycle (avoid in production).
    """

    def __init__(
        self,
        connector_name: str,
        connection_url: str,
        topic_prefix: str,
        mode: str = "incrementing",
        incrementing_column: str = "id",
        poll_interval_ms: int = 5_000,
    ) -> None:
        config = {
            "connector.class": "io.confluent.connect.jdbc.JdbcSourceConnector",
            "connection.url": connection_url,
            "mode": mode,
            "incrementing.column.name": incrementing_column,
            "topic.prefix": topic_prefix,
            "poll.interval.ms": str(poll_interval_ms),
            # Include table names in topic names (topic.prefix + table_name)
            "table.whitelist": "",  # empty = all tables; override as needed
        }
        super().__init__(name=connector_name, config=config)


@dataclass
class ElasticsearchSinkConfig(ConnectorConfig):
    """
    Confluent Elasticsearch Sink connector.

    Reads messages from one or more Kafka topics and indexes them into
    Elasticsearch.  Paired with Debezium this gives a fully automated
    Postgres → Elasticsearch search-index pipeline.
    """

    def __init__(
        self,
        connector_name: str,
        topics: str,
        es_url: str,
        index_name: Optional[str] = None,
    ) -> None:
        config = {
            "connector.class": (
                "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector"
            ),
            "topics": topics,
            "connection.url": es_url,
            "type.name": "_doc",
            "key.ignore": "true",
            "schema.ignore": "true",
            # Write-retry on transient errors
            "max.retries": "10",
            "retry.backoff.ms": "3000",
        }
        if index_name:
            config["index"] = index_name
        super().__init__(name=connector_name, config=config)


@dataclass
class S3SinkConfig(ConnectorConfig):
    """
    Confluent S3 Sink connector — streams Kafka topics to S3 for data lake archival.

    Data is flushed to S3 once `flush.size` messages have accumulated or the
    `rotate.interval.ms` wall-clock interval has elapsed, whichever comes first.

    Common format choices: ParquetFormat (analytics), JsonFormat (debugging),
    AvroFormat (compact + schema-aware).
    """

    def __init__(
        self,
        connector_name: str,
        topics: str,
        bucket_name: str,
        region: str = "us-east-1",
        format_class: str = (
            "io.confluent.connect.s3.format.parquet.ParquetFormat"
        ),
        flush_size: int = 10_000,
        rotate_interval_ms: int = 60_000,
    ) -> None:
        config = {
            "connector.class": "io.confluent.connect.s3.S3SinkConnector",
            "topics": topics,
            "s3.bucket.name": bucket_name,
            "s3.region": region,
            "format.class": format_class,
            "partitioner.class": (
                "io.confluent.connect.storage.partitioner.TimeBasedPartitioner"
            ),
            "path.format": "'year'=YYYY/'month'=MM/'day'=dd",
            "locale": "en_US",
            "timezone": "UTC",
            "flush.size": str(flush_size),
            "rotate.interval.ms": str(rotate_interval_ms),
            "storage.class": "io.confluent.connect.s3.storage.S3Storage",
        }
        super().__init__(name=connector_name, config=config)


@dataclass
class JdbcSinkConfig(ConnectorConfig):
    """
    Confluent JDBC Sink connector — writes Kafka messages into a relational DB.

    Useful for DB migration pipelines:
      MySQL (Debezium source) → Kafka → Postgres (JDBC sink).
    """

    def __init__(
        self,
        connector_name: str,
        topics: str,
        connection_url: str,
        connection_user: str,
        connection_password: str,
        insert_mode: str = "upsert",
        pk_mode: str = "record_key",
        pk_fields: str = "id",
        auto_create: bool = True,
        auto_evolve: bool = True,
    ) -> None:
        config = {
            "connector.class": "io.confluent.connect.jdbc.JdbcSinkConnector",
            "topics": topics,
            "connection.url": connection_url,
            "connection.user": connection_user,
            "connection.password": connection_password,
            "insert.mode": insert_mode,
            "pk.mode": pk_mode,
            "pk.fields": pk_fields,
            "auto.create": str(auto_create).lower(),
            "auto.evolve": str(auto_evolve).lower(),
        }
        super().__init__(name=connector_name, config=config)


# =============================================================================
# 2. DEAD LETTER QUEUE (DLQ) MIXIN
#    Apply to any sink connector config dict to enable DLQ routing.
# =============================================================================


def apply_dlq(
    config: Dict[str, str],
    dlq_topic: str,
    tolerance: str = "all",
    include_headers: bool = True,
) -> Dict[str, str]:
    """
    Mutate a connector config dict to route failed messages to a DLQ topic
    instead of halting the connector.

    Args:
        config:          Existing connector config dict (mutated in place).
        dlq_topic:       Kafka topic name for dead-lettered messages.
        tolerance:       "all" — skip all errors; "none" — fail on first error.
        include_headers: Attach error context as Kafka headers on DLQ messages.

    Returns the mutated config dict (for chaining).
    """
    config["errors.tolerance"] = tolerance
    config["errors.deadletterqueue.topic.name"] = dlq_topic
    config["errors.deadletterqueue.context.headers.enable"] = (
        "true" if include_headers else "false"
    )
    config["errors.log.enable"] = "true"
    config["errors.log.include.messages"] = "true"
    return config


# =============================================================================
# 3. SINGLE MESSAGE TRANSFORMS (SMT) HELPERS
#    Chain transforms by adding keys to the connector config dict.
# =============================================================================


def add_smt_extract_key(config: Dict[str, str], field_name: str = "id") -> None:
    """
    SMT: Extract a field from the message value and use it as the Kafka record key.
    Useful when Debezium emits struct keys but downstream needs a simple int/string key.
    """
    _append_transform(config, "extractKey")
    config["transforms.extractKey.type"] = (
        "org.apache.kafka.connect.transforms.ExtractField$Key"
    )
    config["transforms.extractKey.field"] = field_name


def add_smt_unwrap_debezium(config: Dict[str, str]) -> None:
    """
    SMT: Unwrap Debezium envelope — replace the full `{op, before, after, ts_ms}` struct
    with just the `after` value so downstream consumers see a flat row, not a CDC event.
    """
    _append_transform(config, "unwrap")
    config["transforms.unwrap.type"] = (
        "io.debezium.transforms.ExtractNewRecordState"
    )
    config["transforms.unwrap.drop.tombstones"] = "false"
    config["transforms.unwrap.delete.handling.mode"] = "rewrite"


def add_smt_mask_field(
    config: Dict[str, str], fields: List[str]
) -> None:
    """
    SMT: Replace sensitive field values with a fixed placeholder ("****").
    Example use: mask credit card numbers before writing to Elasticsearch.
    """
    _append_transform(config, "mask")
    config["transforms.mask.type"] = (
        "org.apache.kafka.connect.transforms.MaskField$Value"
    )
    config["transforms.mask.fields"] = ",".join(fields)
    config["transforms.mask.replacement"] = "****"


def _append_transform(config: Dict[str, str], name: str) -> None:
    """Append a transform name to the 'transforms' comma-list (create if absent)."""
    existing = config.get("transforms", "")
    names = [t for t in existing.split(",") if t]
    if name not in names:
        names.append(name)
    config["transforms"] = ",".join(names)


# =============================================================================
# 4. CONNECT REST API CLIENT
#    Thin Python wrapper around the Kafka Connect HTTP API.
#    Use this in CI/CD scripts to deploy connector configs from git.
# =============================================================================


class ConnectorStatus(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    UNASSIGNED = "UNASSIGNED"


class ConnectClient:
    """
    HTTP client for the Kafka Connect REST API (port 8083 by default).

    All mutating operations (create, update, pause, resume, restart, delete)
    are idempotent-safe: create uses PUT if the connector already exists.

    Usage (GitOps deploy script):
        client = ConnectClient("http://kafka-connect:8083")
        cfg = DebeziumPostgresSourceConfig(...)
        client.apply(cfg)          # create or update
        client.wait_running(cfg.name)
    """

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # READ operations
    # ------------------------------------------------------------------

    def list_connectors(self) -> List[str]:
        """Return list of connector names currently registered."""
        resp = self._session.get(
            f"{self.base_url}/connectors", timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def get_config(self, name: str) -> Dict[str, Any]:
        """Return the full config of a connector."""
        resp = self._session.get(
            f"{self.base_url}/connectors/{name}", timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def get_status(self, name: str) -> Dict[str, Any]:
        """Return connector + task status."""
        resp = self._session.get(
            f"{self.base_url}/connectors/{name}/status", timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def connector_status(self, name: str) -> ConnectorStatus:
        """Return the connector-level state as a ConnectorStatus enum."""
        data = self.get_status(name)
        state = data.get("connector", {}).get("state", "UNASSIGNED")
        return ConnectorStatus(state)

    # ------------------------------------------------------------------
    # WRITE operations
    # ------------------------------------------------------------------

    def create(self, cfg: ConnectorConfig) -> Dict[str, Any]:
        """Create a new connector.  Raises HTTPError if it already exists."""
        resp = self._session.post(
            f"{self.base_url}/connectors",
            data=cfg.to_json(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        log.info("Created connector: %s", cfg.name)
        return resp.json()

    def update(self, cfg: ConnectorConfig) -> Dict[str, Any]:
        """Update an existing connector config (PUT to /connectors/{name}/config)."""
        resp = self._session.put(
            f"{self.base_url}/connectors/{cfg.name}/config",
            data=json.dumps(cfg.config),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        log.info("Updated connector: %s", cfg.name)
        return resp.json()

    def apply(self, cfg: ConnectorConfig) -> Dict[str, Any]:
        """Create connector if it does not exist, otherwise update it (idempotent)."""
        existing = self.list_connectors()
        if cfg.name in existing:
            return self.update(cfg)
        return self.create(cfg)

    def pause(self, name: str) -> None:
        resp = self._session.put(
            f"{self.base_url}/connectors/{name}/pause", timeout=self.timeout
        )
        resp.raise_for_status()
        log.info("Paused connector: %s", name)

    def resume(self, name: str) -> None:
        resp = self._session.put(
            f"{self.base_url}/connectors/{name}/resume", timeout=self.timeout
        )
        resp.raise_for_status()
        log.info("Resumed connector: %s", name)

    def restart(self, name: str) -> None:
        resp = self._session.post(
            f"{self.base_url}/connectors/{name}/restart", timeout=self.timeout
        )
        resp.raise_for_status()
        log.info("Restarted connector: %s", name)

    def delete(self, name: str) -> None:
        resp = self._session.delete(
            f"{self.base_url}/connectors/{name}", timeout=self.timeout
        )
        resp.raise_for_status()
        log.info("Deleted connector: %s", name)

    # ------------------------------------------------------------------
    # UTILITY
    # ------------------------------------------------------------------

    def wait_running(
        self,
        name: str,
        timeout_seconds: int = 60,
        poll_interval: float = 2.0,
    ) -> None:
        """
        Block until the connector reaches RUNNING state.
        Raises RuntimeError if it does not within `timeout_seconds`.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = self.connector_status(name)
            if status == ConnectorStatus.RUNNING:
                log.info("Connector %s is RUNNING", name)
                return
            if status == ConnectorStatus.FAILED:
                raise RuntimeError(
                    f"Connector {name!r} entered FAILED state. "
                    "Check Connect worker logs for details."
                )
            log.info("Connector %s state=%s — waiting...", name, status)
            time.sleep(poll_interval)
        raise TimeoutError(
            f"Connector {name!r} did not reach RUNNING within {timeout_seconds}s"
        )


# =============================================================================
# 5. SCHEMA REGISTRY + AVRO SERIALIZATION
#    pip install confluent-kafka[avro]
# =============================================================================

# NOTE: Schema Registry and Avro imports are guarded so this module remains
# importable even when confluent-kafka is not installed (CI lint checks, etc.).

ORDER_AVRO_SCHEMA = json.dumps(
    {
        "type": "record",
        "name": "Order",
        "namespace": "com.shop.events",
        "fields": [
            {"name": "id", "type": "long"},
            {"name": "customer_id", "type": "long"},
            {"name": "amount", "type": "double"},
            {"name": "status", "type": "string"},
            {"name": "created_at_ms", "type": "long"},
        ],
    }
)

CUSTOMER_AVRO_SCHEMA = json.dumps(
    {
        "type": "record",
        "name": "Customer",
        "namespace": "com.shop.events",
        "fields": [
            {"name": "id", "type": "long"},
            {"name": "email", "type": "string"},
            # Schema evolution: add optional field with default — BACKWARD compatible.
            {"name": "tier", "type": ["null", "string"], "default": None},
        ],
    }
)


def build_avro_producer(
    bootstrap_servers: str,
    schema_registry_url: str,
    schema_str: str,
    topic: str,
):
    """
    Return a configured Confluent Kafka producer that serializes messages with
    Avro, embedding the schema ID in every message (magic byte + 4-byte schema ID).

    The Schema Registry enforces compatibility rules on schema updates:
      BACKWARD  — new schema can read data written with the old schema.
      FORWARD   — old schema can read data written with the new schema.
      FULL      — both directions.

    Example:
        producer = build_avro_producer(
            "kafka:9092",
            "http://schema-registry:8081",
            ORDER_AVRO_SCHEMA,
            "orders",
        )
        producer.produce(topic, key=str(order.id), value=order_dict)
        producer.flush()
    """
    # pip install confluent-kafka[avro]
    from confluent_kafka import Producer
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroSerializer
    from confluent_kafka.serialization import (
        MessageField,
        SerializationContext,
        StringSerializer,
    )

    sr_client = SchemaRegistryClient({"url": schema_registry_url})
    avro_serializer = AvroSerializer(
        sr_client,
        schema_str,
        # to_dict: convert your domain object / dict to the Avro-compatible dict
        lambda obj, ctx: obj if isinstance(obj, dict) else vars(obj),
    )
    string_serializer = StringSerializer("utf_8")

    raw_producer = Producer({"bootstrap.servers": bootstrap_servers})

    class AvroProducer:
        """Thin wrapper that handles Avro serialization automatically."""

        def produce(
            self,
            value: dict,
            key: Optional[str] = None,
            on_delivery=None,
        ) -> None:
            raw_producer.produce(
                topic=topic,
                key=string_serializer(key) if key else None,
                value=avro_serializer(
                    value, SerializationContext(topic, MessageField.VALUE)
                ),
                on_delivery=on_delivery,
            )

        def flush(self) -> None:
            raw_producer.flush()

    return AvroProducer()


# =============================================================================
# 6. CDC EVENT MODEL
#    Represents the Debezium envelope that arrives on a CDC topic.
# =============================================================================


@dataclass
class DebeziumEvent:
    """
    Typed representation of a Debezium change event.

    Every row-level change on a captured table produces a message with this
    structure on the topic `<server_name>.<schema>.<table>`.
    """

    op: str                   # "c" = create/INSERT, "u" = UPDATE, "d" = DELETE, "r" = READ (snapshot)
    before: Optional[Dict[str, Any]]   # Row state before change (None for inserts)
    after: Optional[Dict[str, Any]]    # Row state after change (None for deletes)
    ts_ms: int                # Transaction commit timestamp in milliseconds

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DebeziumEvent":
        return cls(
            op=data["op"],
            before=data.get("before"),
            after=data.get("after"),
            ts_ms=data.get("ts_ms", 0),
        )

    @property
    def operation_label(self) -> str:
        return {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "SNAPSHOT"}.get(
            self.op, "UNKNOWN"
        )

    def changed_fields(self) -> Dict[str, tuple]:
        """
        For UPDATE events, return a dict of {field: (old_value, new_value)}
        for fields that actually changed.
        """
        if self.op != "u" or not self.before or not self.after:
            return {}
        return {
            k: (self.before.get(k), self.after.get(k))
            for k in self.after
            if self.before.get(k) != self.after.get(k)
        }


# =============================================================================
# 7. CDC CONSUMER — PURE KAFKA (no Connect required on the consumer side)
#    This is what a downstream service reads after Debezium writes CDC events.
# =============================================================================


def build_cdc_consumer(
    bootstrap_servers: str,
    group_id: str,
    topic: str,
):
    """
    Return a plain Confluent Kafka consumer subscribed to a Debezium CDC topic.

    The consumer processes DebeziumEvent objects; each handler receives the
    typed event and can fan out to Elasticsearch, Redis, a data warehouse, etc.

    Example usage:
        consumer = build_cdc_consumer("kafka:9092", "search-indexer", "shop_db.public.orders")
        for event in consumer:
            if event.op in ("c", "u"):
                es_client.index(index="orders", id=event.after["id"], body=event.after)
            elif event.op == "d":
                es_client.delete(index="orders", id=event.before["id"])
    """
    # pip install confluent-kafka
    from confluent_kafka import Consumer, KafkaError

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])

    class CDCConsumerIterator:
        def __iter__(self):
            return self

        def __next__(self) -> DebeziumEvent:
            while True:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise StopIteration
                data = json.loads(msg.value().decode("utf-8"))
                consumer.commit(asynchronous=False)
                return DebeziumEvent.from_dict(data)

        def close(self) -> None:
            consumer.close()

    return CDCConsumerIterator()


# =============================================================================
# 8. COMMON PIPELINE FACTORY FUNCTIONS
#    Ready-made connector sets for the five most common integration patterns.
# =============================================================================


def postgres_to_elasticsearch_pipeline(
    pg_hostname: str,
    pg_port: str,
    pg_user: str,
    pg_password: str,
    pg_dbname: str,
    pg_server_name: str,
    table_list: str,
    es_url: str,
) -> List[ConnectorConfig]:
    """
    Pattern 1: Postgres → Kafka (Debezium CDC) → Elasticsearch (search index).

    Topology:
      App writes to Postgres
        → Debezium reads WAL
          → Kafka topic: <pg_server_name>.public.<table>
            → Elasticsearch sink indexes every row

    Returns a list of two ConnectorConfig objects to apply via ConnectClient.
    """
    source_cfg = DebeziumPostgresSourceConfig(
        connector_name=f"{pg_server_name}-pg-source",
        hostname=pg_hostname,
        port=pg_port,
        user=pg_user,
        password=pg_password,
        dbname=pg_dbname,
        server_name=pg_server_name,
        table_include_list=table_list,
    )

    # Build topic list from table list: schema.table → server.schema.table
    tables = [t.strip() for t in table_list.split(",")]
    es_topics = ",".join(f"{pg_server_name}.{t}" for t in tables)

    sink_cfg = ElasticsearchSinkConfig(
        connector_name=f"{pg_server_name}-es-sink",
        topics=es_topics,
        es_url=es_url,
    )
    # Unwrap Debezium envelope so ES receives flat row documents
    add_smt_unwrap_debezium(sink_cfg.config)

    # Route malformed messages to DLQ rather than halting the pipeline
    apply_dlq(sink_cfg.config, dlq_topic=f"dlq-{pg_server_name}-es")

    return [source_cfg, sink_cfg]


def kafka_to_s3_datalake_pipeline(
    topics: str,
    bucket_name: str,
    region: str = "us-east-1",
    flush_size: int = 10_000,
) -> S3SinkConfig:
    """
    Pattern 2: Kafka topics → S3 data lake (Parquet, time-partitioned).

    Microservices publish domain events → Kafka.  The S3 sink archives them to
    s3://<bucket>/topics/<topic>/year=YYYY/month=MM/day=dd/*.parquet.
    Suitable for feeding Athena, Spark, or Snowflake external tables.
    """
    return S3SinkConfig(
        connector_name="s3-datalake-sink",
        topics=topics,
        bucket_name=bucket_name,
        region=region,
        flush_size=flush_size,
    )


def mysql_to_postgres_migration_pipeline(
    mysql_url: str,
    pg_url: str,
    pg_user: str,
    pg_password: str,
    topics: str,
    topic_prefix: str = "migration_",
) -> List[ConnectorConfig]:
    """
    Pattern 4: MySQL → Postgres live DB migration via Kafka.

    Uses JDBC source (polling) against MySQL and JDBC sink against Postgres.
    For production migrations prefer Debezium MySQL source for full CDC fidelity.
    """
    source_cfg = JdbcSourceConfig(
        connector_name="mysql-migration-source",
        connection_url=mysql_url,
        topic_prefix=topic_prefix,
        mode="incrementing",
        incrementing_column="id",
    )
    sink_cfg = JdbcSinkConfig(
        connector_name="pg-migration-sink",
        topics=topics,
        connection_url=pg_url,
        connection_user=pg_user,
        connection_password=pg_password,
        insert_mode="upsert",
        pk_mode="record_key",
        pk_fields="id",
        auto_create=True,
        auto_evolve=True,
    )
    return [source_cfg, sink_cfg]


# =============================================================================
# 9. GITOPS DEPLOY HELPER
#    Idempotent: applies all connectors in a pipeline, waits for RUNNING state.
# =============================================================================


def deploy_pipeline(
    connect_url: str,
    connectors: List[ConnectorConfig],
    wait_timeout: int = 120,
) -> None:
    """
    Apply a list of connector configs to a Connect cluster in order.

    Intended for use in CI/CD pipelines where connector JSON lives in git:
        connectors = postgres_to_elasticsearch_pipeline(...)
        deploy_pipeline("http://kafka-connect:8083", connectors)
    """
    client = ConnectClient(connect_url)
    for cfg in connectors:
        log.info(
            "Deploying connector %s to %s ...", cfg.name, connect_url
        )
        client.apply(cfg)
        client.wait_running(cfg.name, timeout_seconds=wait_timeout)
    log.info("All %d connector(s) deployed successfully.", len(connectors))


# =============================================================================
# 10. MONITORING HELPERS — poll connector health from Python
# =============================================================================


def check_all_connectors(connect_url: str) -> Dict[str, ConnectorStatus]:
    """
    Return a dict of {connector_name: ConnectorStatus} for every connector in
    the cluster.  Use from a health-check endpoint or monitoring script.

    Example:
        statuses = check_all_connectors("http://kafka-connect:8083")
        failed = [n for n, s in statuses.items() if s == ConnectorStatus.FAILED]
        if failed:
            alert(f"Failed connectors: {failed}")
    """
    client = ConnectClient(connect_url)
    names = client.list_connectors()
    return {name: client.connector_status(name) for name in names}


def get_task_errors(connect_url: str, connector_name: str) -> List[Dict[str, Any]]:
    """
    Return a list of task-level error details for a connector.
    Useful for diagnosing FAILED tasks without reading raw Connect logs.
    """
    client = ConnectClient(connect_url)
    status = client.get_status(connector_name)
    tasks = status.get("tasks", [])
    failed_tasks = [t for t in tasks if t.get("state") == "FAILED"]
    return [
        {
            "task_id": t["id"],
            "trace": t.get("trace", ""),
        }
        for t in failed_tasks
    ]


# =============================================================================
# 11. STRIMZI KUBERNETES MANIFEST TEMPLATES
#    Generate KafkaConnect + KafkaConnector CRD YAML for K8s-native deployments.
# =============================================================================

STRIMZI_KAFKA_CONNECT_TEMPLATE = """
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnect
metadata:
  name: {name}
  annotations:
    # Allow KafkaConnector CRDs to manage connectors declaratively
    strimzi.io/use-connector-resources: "true"
spec:
  replicas: {replicas}
  bootstrapServers: {bootstrap_servers}
  config:
    config.storage.replication.factor: 3
    offset.storage.replication.factor: 3
    status.storage.replication.factor: 3
    config.storage.topic: "{name}-configs"
    offset.storage.topic: "{name}-offsets"
    status.storage.topic: "{name}-status"
  build:
    output:
      type: docker
      image: {image}
    plugins:
      - name: debezium-postgres
        artifacts:
          - type: tgz
            url: https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/{debezium_version}/debezium-connector-postgres-{debezium_version}-plugin.tar.gz
"""

STRIMZI_KAFKA_CONNECTOR_TEMPLATE = """
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: {connector_name}
  labels:
    strimzi.io/cluster: {connect_cluster}
spec:
  class: {connector_class}
  tasksMax: {tasks_max}
  config:
{config_yaml}
"""


def render_strimzi_connect(
    name: str = "my-connect",
    replicas: int = 3,
    bootstrap_servers: str = "kafka-bootstrap:9093",
    image: str = "myregistry/kafka-connect:latest",
    debezium_version: str = "2.4.0.Final",
) -> str:
    """Render a KafkaConnect CRD manifest for Strimzi."""
    return STRIMZI_KAFKA_CONNECT_TEMPLATE.format(
        name=name,
        replicas=replicas,
        bootstrap_servers=bootstrap_servers,
        image=image,
        debezium_version=debezium_version,
    ).strip()


def render_strimzi_connector(
    connector_name: str,
    connect_cluster: str,
    connector_class: str,
    config: Dict[str, str],
    tasks_max: int = 1,
) -> str:
    """Render a KafkaConnector CRD manifest for Strimzi."""
    config_lines = "\n".join(
        f"    {k}: {json.dumps(v)}" for k, v in config.items()
    )
    return STRIMZI_KAFKA_CONNECTOR_TEMPLATE.format(
        connector_name=connector_name,
        connect_cluster=connect_cluster,
        connector_class=connector_class,
        tasks_max=tasks_max,
        config_yaml=config_lines,
    ).strip()


# =============================================================================
# 12. __main__ DEMO
#    Runs without any external infrastructure.
#    Shows connector config serialization, SMT application, and DLQ config.
# =============================================================================

if __name__ == "__main__":
    import pprint

    print("=" * 70)
    print("DEMO: Kafka Connect configuration builder (no live infra needed)")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Pattern 1: Postgres → Elasticsearch pipeline
    # -------------------------------------------------------------------------
    print("\n[1] Postgres → Elasticsearch (CDC pipeline configs)")
    print("-" * 50)
    pg_es_connectors = postgres_to_elasticsearch_pipeline(
        pg_hostname="postgres",
        pg_port="5432",
        pg_user="debezium",
        pg_password="s3cr3t",
        pg_dbname="shop",
        pg_server_name="shop_db",
        table_list="public.orders,public.customers",
        es_url="http://elasticsearch:9200",
    )
    for cfg in pg_es_connectors:
        print(f"\nConnector: {cfg.name}")
        pprint.pprint(cfg.config)

    # -------------------------------------------------------------------------
    # Pattern 2: Kafka → S3 data lake
    # -------------------------------------------------------------------------
    print("\n[2] S3 Sink — data lake archival config")
    print("-" * 50)
    s3_cfg = kafka_to_s3_datalake_pipeline(
        topics="orders,customers,payments",
        bucket_name="data-lake-prod",
        region="eu-west-1",
        flush_size=5_000,
    )
    print(s3_cfg.to_json())

    # -------------------------------------------------------------------------
    # SMT: mask a sensitive field before indexing to Elasticsearch
    # -------------------------------------------------------------------------
    print("\n[3] SMT: mask credit_card_number field")
    print("-" * 50)
    es_cfg = ElasticsearchSinkConfig(
        connector_name="orders-es-sink",
        topics="shop_db.public.orders",
        es_url="http://elasticsearch:9200",
    )
    add_smt_unwrap_debezium(es_cfg.config)
    add_smt_mask_field(es_cfg.config, fields=["credit_card_number", "cvv"])
    apply_dlq(es_cfg.config, dlq_topic="dlq-orders-es")
    print(es_cfg.to_json())

    # -------------------------------------------------------------------------
    # DebeziumEvent model
    # -------------------------------------------------------------------------
    print("\n[4] DebeziumEvent parsing")
    print("-" * 50)
    raw_event = {
        "op": "u",
        "before": {"id": 1, "amount": 100.0, "status": "pending"},
        "after": {"id": 1, "amount": 150.0, "status": "paid"},
        "ts_ms": 1700000000000,
    }
    evt = DebeziumEvent.from_dict(raw_event)
    print(f"Operation : {evt.operation_label}")
    print(f"Changed   : {evt.changed_fields()}")

    # -------------------------------------------------------------------------
    # Strimzi CRD generation
    # -------------------------------------------------------------------------
    print("\n[5] Strimzi KafkaConnect CRD manifest")
    print("-" * 50)
    print(
        render_strimzi_connect(
            name="shop-connect",
            replicas=3,
            bootstrap_servers="kafka-bootstrap:9093",
            image="myregistry/kafka-connect:2.4",
        )
    )

    print("\n[6] Strimzi KafkaConnector CRD manifest (Debezium PG)")
    print("-" * 50)
    debezium_cfg = DebeziumPostgresSourceConfig(
        connector_name="shop-pg-source",
        hostname="postgres",
        port="5432",
        user="debezium",
        password="s3cr3t",
        dbname="shop",
        server_name="shop_db",
        table_include_list="public.orders,public.customers",
    )
    print(
        render_strimzi_connector(
            connector_name="shop-pg-source",
            connect_cluster="shop-connect",
            connector_class="io.debezium.connector.postgresql.PostgresConnector",
            config=debezium_cfg.config,
        )
    )

    print("\nDemo complete.")
