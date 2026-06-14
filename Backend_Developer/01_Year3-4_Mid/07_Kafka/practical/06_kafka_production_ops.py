"""
Kafka Production Operations — Configuration, Monitoring, and Capacity Planning
==============================================================================

Covers every topic in the 06_kafka_production_ops theory doc:
  - Producer and consumer tuning profiles (throughput / durability / latency).
  - Consumer lag tracking and alerting.
  - Capacity-planning formulae.
  - Common production issue detection helpers.
  - Security configuration reference strings.
  - Schema-compatibility validator.
  - Anti-pattern guard / checklist.
  - KRaft vs ZooKeeper mode comparison.
  - Cloud-managed service decision helper.

This is an *illustrative* module.  The real AIOKafka clients are built but not
connected — no running broker is required.  All helpers that don't need a broker
are runnable standalone via the __main__ demo at the bottom.

pip install aiokafka prometheus-client structlog
"""

import asyncio
import dataclasses
import enum
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import structlog

# ---------------------------------------------------------------------------
# Logging bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = structlog.get_logger()


# ==========================================================================
# 1. CLUSTER SIZING REFERENCE
# ==========================================================================

@dataclasses.dataclass
class BrokerSpec:
    """Recommended per-broker hardware profile for a production Kafka node."""

    cpu_cores: int
    ram_gb: int
    disk_type: str           # "nvme" | "ssd" | "hdd"
    network_gbps: int
    description: str

    def summarise(self) -> str:
        return (
            f"{self.description}: {self.cpu_cores} cores, "
            f"{self.ram_gb}GB RAM, {self.disk_type} disk, "
            f"{self.network_gbps}Gbps NIC"
        )


# Production-tier hardware profiles from the theory doc.
BROKER_PROFILES: Dict[str, BrokerSpec] = {
    "small": BrokerSpec(8, 32, "ssd", 10, "Small / dev cluster"),
    "standard": BrokerSpec(16, 64, "nvme", 10, "Standard production broker"),
    "latency_critical": BrokerSpec(16, 64, "nvme", 25, "Latency-critical / financial"),
    "bulk_archive": BrokerSpec(8, 32, "hdd", 10, "Bulk archive / tiered storage"),
}

CLUSTER_SIZING_GUIDE = {
    "minimum_brokers": 3,          # Required for replication factor 3.
    "typical_mid_scale": (5, 15),
    "large_scale": (50, 200),
    "max_partitions_per_cluster": 10_000,  # Hard limit; beyond this, ops hurt.
}


# ==========================================================================
# 2. TOPIC CONFIGURATION BUILDER
# ==========================================================================

class CleanupPolicy(enum.Enum):
    DELETE = "delete"
    COMPACT = "compact"
    COMPACT_DELETE = "compact,delete"


@dataclasses.dataclass
class TopicConfig:
    """
    Encapsulates all key topic-level Kafka configs.

    Pass the dict returned by ``to_kafka_config()`` directly to
    ``AdminClient.create_topics()``.
    """

    name: str
    num_partitions: int
    replication_factor: int
    retention_hours: int = 168                   # 7 days — Kafka default.
    retention_bytes_per_partition: int = -1      # -1 = unlimited.
    cleanup_policy: CleanupPolicy = CleanupPolicy.DELETE
    compression_type: str = "lz4"
    min_insync_replicas: int = 2

    # Compaction-specific
    delete_retention_ms: int = 86_400_000        # 1 day for tombstones.
    min_cleanable_dirty_ratio: float = 0.1

    def to_kafka_config(self) -> Dict[str, str]:
        """Return the dict of topic configs suitable for the AdminClient."""
        cfg: Dict[str, str] = {
            "cleanup.policy": self.cleanup_policy.value,
            "compression.type": self.compression_type,
            "min.insync.replicas": str(self.min_insync_replicas),
            "log.retention.hours": str(self.retention_hours),
        }
        if self.retention_bytes_per_partition > 0:
            cfg["log.retention.bytes"] = str(self.retention_bytes_per_partition)
        if self.cleanup_policy in (
            CleanupPolicy.COMPACT, CleanupPolicy.COMPACT_DELETE
        ):
            cfg["delete.retention.ms"] = str(self.delete_retention_ms)
            cfg["min.cleanable.dirty.ratio"] = str(self.min_cleanable_dirty_ratio)
        return cfg

    def validate(self) -> List[str]:
        """Return a list of warnings for common mis-configurations."""
        warnings: List[str] = []
        if self.num_partitions < 1:
            warnings.append("num_partitions must be >= 1")
        if self.replication_factor < 3:
            warnings.append(
                f"replication_factor={self.replication_factor} — "
                "production should be 3 for durability"
            )
        if self.min_insync_replicas >= self.replication_factor:
            warnings.append(
                "min.insync.replicas must be < replication_factor "
                "(otherwise a single broker failure makes the topic unavailable)"
            )
        if self.num_partitions > 200:
            warnings.append(
                f"num_partitions={self.num_partitions} is high; "
                "confirm this is intentional (>10K cluster-wide hurts ops)"
            )
        return warnings


# ==========================================================================
# 3. PRODUCER TUNING PROFILES
# ==========================================================================

class ProducerProfile(enum.Enum):
    THROUGHPUT = "throughput"
    DURABILITY = "durability"
    LATENCY = "latency"


def build_producer_config(
    bootstrap_servers: str,
    profile: ProducerProfile,
) -> Dict[str, Any]:
    """
    Return an AIOKafkaProducer kwargs dict tuned for the given profile.

    Usage::

        cfg = build_producer_config("broker:9092", ProducerProfile.DURABILITY)
        producer = AIOKafkaProducer(**cfg)
    """
    base: Dict[str, Any] = {"bootstrap_servers": bootstrap_servers}

    if profile == ProducerProfile.THROUGHPUT:
        # Prioritise throughput: batch large, linger, compress.
        # Accepts risk of single-broker message loss (acks=1).
        base.update(
            {
                "acks": 1,
                "compression_type": "lz4",
                "linger_ms": 20,          # Wait up to 20ms to fill a batch.
                "batch_size": 131_072,    # 128 KB batches.
                "max_in_flight_requests_per_connection": 5,
            }
        )

    elif profile == ProducerProfile.DURABILITY:
        # Prioritise zero data loss: idempotent, all-acks, infinite retries.
        # max_in_flight can stay at 5 when idempotence is on.
        base.update(
            {
                "acks": "all",
                "enable_idempotence": True,
                "retries": 2_147_483_647,  # Effectively infinite.
                "max_in_flight_requests_per_connection": 5,
                "compression_type": "lz4",
            }
        )

    elif profile == ProducerProfile.LATENCY:
        # Prioritise end-to-end latency: no batching, no linger, no compression.
        base.update(
            {
                "acks": 1,
                "linger_ms": 0,           # Send immediately.
                "batch_size": 16_384,     # Small batch ceiling.
                "compression_type": "none",
                "max_in_flight_requests_per_connection": 1,
            }
        )

    return base


# ==========================================================================
# 4. CONSUMER TUNING PROFILES
# ==========================================================================

class ConsumerProfile(enum.Enum):
    THROUGHPUT = "throughput"
    RELIABILITY = "reliability"
    LATENCY = "latency"


def build_consumer_config(
    bootstrap_servers: str,
    group_id: str,
    topics: List[str],
    profile: ConsumerProfile,
) -> Dict[str, Any]:
    """
    Return an AIOKafkaConsumer kwargs dict tuned for the given profile.

    Usage::

        cfg = build_consumer_config("broker:9092", "my-group", ["orders"],
                                    ConsumerProfile.RELIABILITY)
        consumer = AIOKafkaConsumer(*cfg.pop("topics"), **cfg)
    """
    base: Dict[str, Any] = {
        "bootstrap_servers": bootstrap_servers,
        "group_id": group_id,
        "topics": topics,
    }

    if profile == ConsumerProfile.THROUGHPUT:
        # Fetch large chunks; trade latency for batch efficiency.
        base.update(
            {
                "fetch_min_bytes": 51_200,         # Wait for 50 KB.
                "fetch_max_wait_ms": 500,
                "max_partition_fetch_bytes": 1_048_576,  # 1 MB per partition.
                "max_poll_records": 1_000,
            }
        )

    elif profile == ConsumerProfile.RELIABILITY:
        # Manual commit; generous poll interval to allow slow processing.
        base.update(
            {
                "enable_auto_commit": False,
                "max_poll_interval_ms": 300_000,   # 5 minutes per batch.
                "session_timeout_ms": 45_000,
                "heartbeat_interval_ms": 3_000,
            }
        )

    elif profile == ConsumerProfile.LATENCY:
        # Fetch single records immediately; minimal wait.
        base.update(
            {
                "fetch_min_bytes": 1,
                "fetch_max_wait_ms": 10,
                "max_poll_records": 1,
            }
        )

    return base


# ==========================================================================
# 5. CONSUMER LAG MONITOR
# ==========================================================================

@dataclasses.dataclass
class PartitionLag:
    topic: str
    partition: int
    consumer_offset: int
    log_end_offset: int

    @property
    def lag(self) -> int:
        return max(0, self.log_end_offset - self.consumer_offset)


class ConsumerLagMonitor:
    """
    Polls AdminClient / consumer group describe endpoints and returns per-
    partition lag.  In production, these metrics feed Prometheus and alert
    when lag exceeds a threshold.

    Example PromQL alert rule (configured in Prometheus / Alertmanager):
        kafka_consumergroup_lag > 10000
    """

    LAG_ALERT_THRESHOLD = 10_000   # Alert when lag exceeds this value.

    def __init__(self, lag_threshold: int = LAG_ALERT_THRESHOLD) -> None:
        self.lag_threshold = lag_threshold
        self._history: List[Tuple[float, List[PartitionLag]]] = []

    def record_snapshot(self, snapshot: List[PartitionLag]) -> None:
        """Store a timestamped lag snapshot."""
        self._history.append((time.monotonic(), snapshot))
        # Keep only the last 60 snapshots to bound memory.
        if len(self._history) > 60:
            self._history.pop(0)

    def check_alerts(self, snapshot: List[PartitionLag]) -> List[str]:
        """Return a list of alert strings for any partition breaching the threshold."""
        alerts: List[str] = []
        for pl in snapshot:
            if pl.lag > self.lag_threshold:
                alerts.append(
                    f"ALERT: {pl.topic}[{pl.partition}] lag={pl.lag:,} "
                    f"exceeds threshold {self.lag_threshold:,}. "
                    "Scale consumers, optimise processing, or reduce produce rate."
                )
        return alerts

    def growing_lag_partitions(self) -> List[str]:
        """
        Compare the two most recent snapshots.  Return a list of partition
        descriptions where lag is monotonically increasing — early warning
        that consumers are falling behind.
        """
        if len(self._history) < 2:
            return []
        _, older = self._history[-2]
        _, newer = self._history[-1]

        older_map = {(p.topic, p.partition): p.lag for p in older}
        growing = []
        for p in newer:
            key = (p.topic, p.partition)
            if key in older_map and p.lag > older_map[key]:
                growing.append(
                    f"{p.topic}[{p.partition}]: "
                    f"{older_map[key]:,} → {p.lag:,} (growing)"
                )
        return growing


# ==========================================================================
# 6. CAPACITY PLANNING CALCULATOR
# ==========================================================================

@dataclasses.dataclass
class CapacityPlan:
    """
    Storage and throughput capacity plan based on workload parameters.

    All storage figures in bytes.
    """

    avg_message_size_bytes: int
    messages_per_second: int
    retention_days: int
    replication_factor: int = 3

    @property
    def storage_per_day_bytes(self) -> int:
        return self.avg_message_size_bytes * self.messages_per_second * 86_400

    @property
    def total_storage_bytes(self) -> int:
        return (
            self.storage_per_day_bytes
            * self.retention_days
            * self.replication_factor
        )

    @property
    def total_storage_tb(self) -> float:
        return self.total_storage_bytes / 1e12

    @property
    def ingress_bytes_per_sec(self) -> int:
        """Raw ingress rate (before replication)."""
        return self.avg_message_size_bytes * self.messages_per_second

    @property
    def total_throughput_bytes_per_sec(self) -> int:
        """Actual disk write rate including replication."""
        return self.ingress_bytes_per_sec * self.replication_factor

    def recommended_broker_count(
        self, broker_throughput_bytes_per_sec: int = 1_000_000_000
    ) -> int:
        """
        Minimum brokers needed given a per-broker throughput ceiling.
        Default: 1 GB/s per broker on tuned NVMe hardware.
        """
        return max(
            CLUSTER_SIZING_GUIDE["minimum_brokers"],
            -(-self.total_throughput_bytes_per_sec // broker_throughput_bytes_per_sec),
        )

    def recommended_partitions(
        self, target_throughput_per_partition_bytes: int = 1_048_576
    ) -> int:
        """
        Estimate partitions needed to handle ingress at ~1 MB/s per partition
        (rule of thumb from the theory doc).
        """
        return max(
            1,
            -(-self.ingress_bytes_per_sec // target_throughput_per_partition_bytes),
        )

    def describe(self) -> str:
        lines = [
            "=== Capacity Plan ===",
            f"  Message size      : {self.avg_message_size_bytes:,} bytes",
            f"  Throughput        : {self.messages_per_second:,} msg/s",
            f"  Retention         : {self.retention_days} days",
            f"  Replication factor: {self.replication_factor}",
            f"  Storage / day     : {self.storage_per_day_bytes / 1e9:.2f} GB",
            f"  Total storage     : {self.total_storage_tb:.2f} TB",
            f"  Ingress rate      : {self.ingress_bytes_per_sec / 1e6:.1f} MB/s",
            f"  Total disk write  : {self.total_throughput_bytes_per_sec / 1e6:.1f} MB/s",
            f"  Min brokers       : {self.recommended_broker_count()}",
            f"  Min partitions    : {self.recommended_partitions()}",
        ]
        return "\n".join(lines)


# ==========================================================================
# 7. COMMON PRODUCTION ISSUES — DIAGNOSTIC HELPERS
# ==========================================================================

class ProductionIssue(enum.Enum):
    UNDER_REPLICATED_PARTITIONS = "under_replicated_partitions"
    GROWING_CONSUMER_LAG = "growing_consumer_lag"
    REBALANCE_STORM = "rebalance_storm"
    DISK_FULL = "disk_full"
    HOT_PARTITION = "hot_partition"
    PRODUCER_QUEUE_FULL = "producer_queue_full"
    COORDINATOR_FAILURE = "coordinator_failure"


PRODUCTION_ISSUE_PLAYBOOK: Dict[ProductionIssue, Dict[str, str]] = {
    ProductionIssue.UNDER_REPLICATED_PARTITIONS: {
        "symptom": "ISR count < replication factor; durability at risk.",
        "causes": "Broker overload, JVM GC pauses, network partition.",
        "fix": (
            "Investigate the lagging broker (GC logs, CPU, disk IO). "
            "Throttle replication if needed. Reassign partitions if persistent."
        ),
    },
    ProductionIssue.GROWING_CONSUMER_LAG: {
        "symptom": "Lag grows over time; consumer cannot keep up with producer.",
        "causes": "Slow processing logic, too few consumer instances, GC pauses.",
        "fix": (
            "Add consumer instances up to the partition count. "
            "Optimise processing (batch writes, async I/O). "
            "Consider reducing producer rate or increasing partitions."
        ),
    },
    ProductionIssue.REBALANCE_STORM: {
        "symptom": "Consumer group rebalances repeatedly; no net progress.",
        "causes": (
            "max.poll.interval.ms too low; processing takes longer than the interval."
        ),
        "fix": (
            "Increase max.poll.interval.ms. "
            "Reduce max.poll.records so each batch finishes faster. "
            "Move long-running I/O to an async worker thread."
        ),
    },
    ProductionIssue.DISK_FULL: {
        "symptom": "Broker disk fills; new segments cannot be written.",
        "causes": "Retention misconfigured; log compaction cleaner not running.",
        "fix": (
            "Check log.retention.hours / log.retention.bytes. "
            "Verify log.cleaner.enable=true and the cleaner thread is healthy."
        ),
    },
    ProductionIssue.HOT_PARTITION: {
        "symptom": "One partition receives a disproportionate share of traffic.",
        "causes": "Poor key distribution (e.g., all messages share the same key).",
        "fix": (
            "Salt keys (append random suffix). "
            "Re-design the partitioning key for better cardinality."
        ),
    },
    ProductionIssue.PRODUCER_QUEUE_FULL: {
        "symptom": "BufferExhaustedException; producer's send buffer is full.",
        "causes": "Produce rate exceeds broker accept rate; slow network.",
        "fix": (
            "Increase buffer.memory (default 32MB). "
            "Apply back-pressure in the sending loop. "
            "Scale brokers or reduce produce concurrency."
        ),
    },
    ProductionIssue.COORDINATOR_FAILURE: {
        "symptom": "Offset commits fail; consumers cannot commit.",
        "causes": (
            "The broker hosting the __consumer_offsets partition is down."
        ),
        "fix": (
            "Distribute __consumer_offsets replicas across multiple brokers. "
            "Ensure offsets.topic.replication.factor=3."
        ),
    },
}


def print_playbook(issue: ProductionIssue) -> None:
    entry = PRODUCTION_ISSUE_PLAYBOOK[issue]
    print(f"\n=== {issue.value.upper()} ===")
    for key, value in entry.items():
        print(f"  {key.capitalize():10}: {value}")


# ==========================================================================
# 8. SECURITY CONFIGURATION REFERENCE
# ==========================================================================

# These are configuration fragments used in broker server.properties / client
# configs.  Stored as strings for reference; copy into your actual config files.

SECURITY_TLS_BROKER = """
# Broker server.properties — TLS encryption
listeners=SSL://:9093
security.inter.broker.protocol=SSL
ssl.keystore.location=/path/to/kafka.server.keystore.jks
ssl.keystore.password=<keystore-password>
ssl.truststore.location=/path/to/kafka.server.truststore.jks
ssl.truststore.password=<truststore-password>
ssl.client.auth=required      # Enforces mTLS for clients
"""

SECURITY_SASL_SCRAM_CLIENT = """
# Producer / consumer client config — SASL/SCRAM-SHA-512
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \\
    username="alice" \\
    password="<password>";
"""

SECURITY_ACL_COMMANDS = """
# Grant alice Read + Write on topic 'orders'
kafka-acls.sh --bootstrap-server localhost:9092 \\
  --add --allow-principal User:alice \\
  --operation Read --operation Write \\
  --topic orders

# Grant alice's consumer group Read
kafka-acls.sh --bootstrap-server localhost:9092 \\
  --add --allow-principal User:alice \\
  --operation Read \\
  --group orders-consumer-group

# List ACLs for a topic
kafka-acls.sh --bootstrap-server localhost:9092 \\
  --list --topic orders
"""


class SASLMechanism(enum.Enum):
    PLAIN = "SASL/PLAIN"          # Simple; must run over TLS.
    SCRAM = "SASL/SCRAM-SHA-512"  # Stronger; default for managed services.
    OAUTHBEARER = "SASL/OAUTHBEARER"  # OAuth2 tokens.
    MTLS = "mTLS"                 # Client certificate authentication.


SASL_MECHANISM_GUIDE: Dict[SASLMechanism, str] = {
    SASLMechanism.PLAIN: "Username/password — simple but requires TLS to avoid plaintext creds.",
    SASLMechanism.SCRAM: "Salted challenge/response — stronger than PLAIN; managed Kafka default.",
    SASLMechanism.OAUTHBEARER: "OAuth2 token-based; integrates with identity providers (Okta, Keycloak).",
    SASLMechanism.MTLS: "Mutual TLS — no passwords; certificate identity; highest assurance.",
}


# ==========================================================================
# 9. SCHEMA EVOLUTION VALIDATOR
# ==========================================================================

class SchemaCompatibility(enum.Enum):
    BACKWARD = "BACKWARD"    # New schema reads old data  — consumers upgrade first.
    FORWARD = "FORWARD"      # Old schema reads new data  — producers upgrade first.
    FULL = "FULL"            # Both directions — safest; upgrade in any order.
    NONE = "NONE"            # No enforcement — dangerous in production.


@dataclasses.dataclass
class SchemaChange:
    """Describes a single field-level change in an Avro / Protobuf schema."""

    change_type: str          # "add_field" | "remove_field" | "rename_field" | "change_type"
    field_name: str
    has_default: bool = False
    old_type: Optional[str] = None
    new_type: Optional[str] = None

    # Promotable type pairs per Avro spec.
    _PROMOTABLE = {("int", "long"), ("float", "double"), ("int", "float")}

    def is_safe(self, mode: SchemaCompatibility) -> Tuple[bool, str]:
        """
        Return (is_safe, reason).  Checks against Schema Registry compatibility rules.
        """
        if self.change_type == "add_field":
            if mode in (SchemaCompatibility.BACKWARD, SchemaCompatibility.FULL):
                if not self.has_default:
                    return (
                        False,
                        f"Adding '{self.field_name}' without a default breaks "
                        "BACKWARD compatibility — old data has no value for this field.",
                    )
            return True, "Adding a field with a default is safe."

        if self.change_type == "remove_field":
            if mode in (SchemaCompatibility.FORWARD, SchemaCompatibility.FULL):
                if not self.has_default:
                    return (
                        False,
                        f"Removing '{self.field_name}' without a default breaks "
                        "FORWARD compatibility — old producers still send this field.",
                    )
            return True, "Removing an optional field with a default is safe."

        if self.change_type == "rename_field":
            return (
                False,
                f"Renaming '{self.field_name}' is NOT compatible in any mode. "
                "Add the new field and deprecate the old one instead.",
            )

        if self.change_type == "change_type":
            pair = (self.old_type, self.new_type)
            if pair in self._PROMOTABLE:
                return True, f"Type promotion {self.old_type} → {self.new_type} is safe."
            return (
                False,
                f"Type change {self.old_type} → {self.new_type} is NOT compatible. "
                "Add a new field with the new type and migrate consumers.",
            )

        return False, f"Unknown change_type: '{self.change_type}'"


def validate_schema_changes(
    changes: List[SchemaChange],
    mode: SchemaCompatibility,
) -> None:
    """Print a safety report for a list of schema changes."""
    print(f"\n=== Schema Compatibility Check ({mode.value}) ===")
    all_safe = True
    for change in changes:
        safe, reason = change.is_safe(mode)
        status = "SAFE  " if safe else "UNSAFE"
        print(f"  [{status}] {change.change_type}({change.field_name}): {reason}")
        if not safe:
            all_safe = False
    print(f"\n  Overall: {'PASS' if all_safe else 'FAIL — schema migration blocked'}")


# ==========================================================================
# 10. ANTI-PATTERN CHECKLIST
# ==========================================================================

@dataclasses.dataclass
class AntiPatternCheck:
    name: str
    description: str
    recommendation: str


ANTI_PATTERNS: List[AntiPatternCheck] = [
    AntiPatternCheck(
        "Single partition per topic",
        "One partition = no parallelism; all consumers serialize.",
        "Plan partitions upfront. Target >= consumers in the largest group.",
    ),
    AntiPatternCheck(
        "Shared group ID across unrelated services",
        "Two services with the same group share the partition workload accidentally.",
        "Use unique group IDs per logical consumer application.",
    ),
    AntiPatternCheck(
        "acks=0",
        "Fire-and-forget; data loss guaranteed on any broker failure.",
        "Use acks=all + enable_idempotence=True in production.",
    ),
    AntiPatternCheck(
        "Auto-commit in critical path",
        "If the process crashes between fetch and processing, messages are lost.",
        "Disable auto-commit; commit manually after successful processing.",
    ),
    AntiPatternCheck(
        "Long synchronous work inside the consumer loop",
        "Exceeding max.poll.interval.ms triggers a rebalance; progress is lost.",
        "Offload long I/O to an async worker or reduce batch size.",
    ),
    AntiPatternCheck(
        "Storing messages > 1 MB",
        "Huge messages stress broker memory, consumer fetch buffers, and GC.",
        "Store payload in S3/object store; publish only the reference URL.",
    ),
    AntiPatternCheck(
        "No retention policy",
        "Disk fills; broker crashes; entire cluster at risk.",
        "Always set log.retention.hours or log.retention.bytes.",
    ),
    AntiPatternCheck(
        "Schema-less topics",
        "Breaking changes are silent; consumers crash without warning.",
        "Use Confluent Schema Registry (or Apicurio) with BACKWARD compatibility.",
    ),
]


def print_anti_pattern_checklist() -> None:
    print("\n=== Kafka Production Anti-Pattern Checklist ===")
    for i, ap in enumerate(ANTI_PATTERNS, 1):
        print(f"\n  {i}. {ap.name}")
        print(f"     Problem: {ap.description}")
        print(f"     Fix    : {ap.recommendation}")


# ==========================================================================
# 11. KRAFT vs ZOOKEEPER MODE COMPARISON
# ==========================================================================

KRAFT_VS_ZOOKEEPER = {
    "KRaft (Kafka 3.3+)": {
        "description": "Built-in Raft-based metadata store; no external dependency.",
        "pros": [
            "Simpler deployment — single binary, single config.",
            "Faster controller failover (seconds vs minutes).",
            "Supports millions of partitions (ZK bottleneck removed).",
            "Recommended for all new deployments.",
        ],
        "cons": [
            "Migration from ZooKeeper requires a staged upgrade.",
            "Some admin tools still assume ZooKeeper path format.",
        ],
    },
    "ZooKeeper (legacy)": {
        "description": "External consensus service required alongside Kafka.",
        "pros": [
            "Battle-tested; supported in Kafka < 3.3.",
            "Familiar to older operations teams.",
        ],
        "cons": [
            "Separate cluster to maintain (3-5 ZK nodes).",
            "Slow controller failover on leader election.",
            "Partition count limited by ZK write throughput.",
            "Deprecated; will be removed in a future Kafka major release.",
        ],
    },
}


def print_kraft_comparison() -> None:
    print("\n=== KRaft vs ZooKeeper ===")
    for mode, info in KRAFT_VS_ZOOKEEPER.items():
        print(f"\n  {mode}:")
        print(f"    {info['description']}")
        print("    Pros:")
        for p in info["pros"]:
            print(f"      + {p}")
        print("    Cons:")
        for c in info["cons"]:
            print(f"      - {c}")


# ==========================================================================
# 12. CLOUD-MANAGED KAFKA DECISION HELPER
# ==========================================================================

@dataclasses.dataclass
class CloudKafkaOption:
    name: str
    pros: List[str]
    cons: List[str]
    best_for: str


CLOUD_KAFKA_OPTIONS: List[CloudKafkaOption] = [
    CloudKafkaOption(
        "AWS MSK",
        pros=["Native AWS integration", "IAM authentication", "Managed ZK/KRaft"],
        cons=["Limited customisation", "No tiered storage until recently"],
        best_for="AWS-native shops; tight IAM integration required.",
    ),
    CloudKafkaOption(
        "Confluent Cloud",
        pros=["Full-featured", "Multi-cloud", "Schema Registry included", "KSQL"],
        cons=["Most expensive at scale", "Vendor lock-in risk"],
        best_for="Teams wanting a managed ecosystem with Schema Registry and KSQL.",
    ),
    CloudKafkaOption(
        "Aiven for Kafka",
        pros=["Multi-cloud", "Mid-priced", "Good observability"],
        cons=["Smaller player; less ecosystem depth"],
        best_for="Teams wanting multi-cloud flexibility at a reasonable price.",
    ),
    CloudKafkaOption(
        "WarpStream",
        pros=["S3-backed storage; very cheap", "Kafka-compatible API"],
        cons=["Higher latency (S3 round-trips)", "Newer; less proven"],
        best_for="High-volume batch workloads where latency > 50ms is acceptable.",
    ),
    CloudKafkaOption(
        "Redpanda Cloud",
        pros=["Kafka-compatible; written in C++ (lower latency)", "No JVM GC pauses"],
        cons=["Different internals; some edge cases differ from Apache Kafka"],
        best_for="Latency-sensitive workloads; teams that want Kafka API without JVM.",
    ),
    CloudKafkaOption(
        "Self-managed",
        pros=["Lowest cost at scale", "Full configuration control"],
        cons=["High ops burden", "Requires Kafka expertise in-house"],
        best_for="Large teams (> 100 brokers) with dedicated platform engineering.",
    ),
]


def recommend_cloud_kafka(
    team_size: str = "small",
    primary_cloud: str = "aws",
    latency_sensitive: bool = False,
    budget_priority: bool = False,
) -> str:
    """
    Simple rule-based recommendation.  In practice, run a formal RFP / PoC.
    """
    if budget_priority:
        return "WarpStream (S3-backed, cheapest) — validate latency requirements first."
    if latency_sensitive:
        return "Redpanda Cloud — no JVM GC pauses, lowest tail latency."
    if primary_cloud == "aws" and team_size in ("small", "medium"):
        return "AWS MSK — best native integration; IAM auth reduces credential sprawl."
    if team_size == "large":
        return "Self-managed on bare metal / EC2 — cost-efficient at scale with a platform team."
    return "Confluent Cloud — broadest ecosystem; easiest onboarding."


# ==========================================================================
# 13. PROMETHEUS METRIC NAMES REFERENCE
# ==========================================================================

# Production monitoring requires these JMX-exported / Prometheus metric names.
# Plug into Grafana using the pre-built Kafka dashboard or build custom panels.

PROMETHEUS_METRICS = {
    "cluster": {
        "kafka_controller_activecontrollercount": "Must equal 1 at all times.",
        "kafka_server_replicamanager_underreplicatedpartitions": "Must be 0.",
        "kafka_controller_offlinepartitionscount": "Must be 0.",
        "kafka_controller_isrshrinks_total": "Alerts when ISR contracts.",
    },
    "broker": {
        "kafka_server_brokertopicmetrics_messagesin_total": "Message ingestion rate.",
        "kafka_server_brokertopicmetrics_bytesin_total": "Byte ingestion rate.",
        "kafka_network_requestmetrics_requestqueuetimems": "Request handler queue depth.",
        "kafka_server_kafkarequesthandlerpool_requesthandleravgidlepercent": "CPU pressure proxy.",
        "jvm_gc_collection_seconds_sum": "JVM GC pause time — spikes = ISR risk.",
    },
    "consumer": {
        "kafka_consumergroup_lag": "Per-partition lag. Alert when > threshold.",
        "kafka_consumergroup_lag_sum": "Total lag across all partitions in group.",
        "kafka_consumergroup_members": "Number of active consumer instances.",
    },
}

ALERT_RULES_PROMQL = """
# Paste into a Prometheus rules file
groups:
  - name: kafka_production
    rules:
      - alert: KafkaUnderReplicatedPartitions
        expr: kafka_server_replicamanager_underreplicatedpartitions > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Under-replicated partitions detected"

      - alert: KafkaConsumerLagHigh
        expr: kafka_consumergroup_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Consumer group {{ $labels.consumergroup }} lag > 10000"

      - alert: KafkaOfflinePartitions
        expr: kafka_controller_offlinepartitionscount > 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Offline partitions detected — data is unavailable"
"""


# ==========================================================================
# 14. ROLLING RESTART / LIFECYCLE OPERATIONS GUIDE
# ==========================================================================

LIFECYCLE_GUIDE = {
    "add_broker": [
        "Bring up the new broker with the same cluster.id and correct advertised listeners.",
        "Generate a partition reassignment plan: kafka-reassign-partitions.sh --generate",
        "Execute the plan: kafka-reassign-partitions.sh --execute --reassignment-json-file plan.json",
        "Verify completion: kafka-reassign-partitions.sh --verify",
    ],
    "remove_broker": [
        "Move ALL partitions off the target broker via reassignment plan.",
        "Verify no leader replicas remain on the broker.",
        "Shut down the broker gracefully.",
    ],
    "rolling_restart": [
        "Restart brokers ONE AT A TIME.",
        "After each restart, wait for ISR to fully recover (kafka-topics.sh --describe).",
        "Run kafka-preferred-replica-election.sh after the last restart to rebalance leaders.",
    ],
    "version_upgrade": [
        "Upgrade brokers one at a time (rolling restart procedure above).",
        "Keep inter.broker.protocol.version at the OLD version until all brokers are upgraded.",
        "Then bump inter.broker.protocol.version and log.message.format.version.",
    ],
}


def print_lifecycle_guide(operation: str) -> None:
    steps = LIFECYCLE_GUIDE.get(operation)
    if not steps:
        print(f"Unknown operation: {operation}. Options: {list(LIFECYCLE_GUIDE)}")
        return
    print(f"\n=== Lifecycle: {operation.replace('_', ' ').title()} ===")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")


# ==========================================================================
# 15. ASYNC PRODUCER / CONSUMER FACTORY (AIOKafka wrappers)
# ==========================================================================

async def create_producer(
    bootstrap_servers: str,
    profile: ProducerProfile = ProducerProfile.DURABILITY,
):
    """
    Build and start an AIOKafkaProducer with the selected tuning profile.

    Returns the started producer; caller must call ``await producer.stop()``
    when done (or use as an async context manager via aiokafka 0.8+).

    pip install aiokafka
    """
    # Import deferred so the module loads even without aiokafka installed.
    from aiokafka import AIOKafkaProducer  # noqa: PLC0415

    cfg = build_producer_config(bootstrap_servers, profile)
    # Remove non-AIOKafka kwarg before construction.
    cfg.pop("bootstrap_servers")
    producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers, **cfg)
    await producer.start()
    log.info("producer_started", profile=profile.value, brokers=bootstrap_servers)
    return producer


async def create_consumer(
    bootstrap_servers: str,
    group_id: str,
    topics: List[str],
    profile: ConsumerProfile = ConsumerProfile.RELIABILITY,
):
    """
    Build and start an AIOKafkaConsumer with the selected tuning profile.

    pip install aiokafka
    """
    from aiokafka import AIOKafkaConsumer  # noqa: PLC0415

    cfg = build_consumer_config(bootstrap_servers, group_id, topics, profile)
    topic_list = cfg.pop("topics")
    cfg.pop("bootstrap_servers")
    consumer = AIOKafkaConsumer(
        *topic_list,
        bootstrap_servers=bootstrap_servers,
        **cfg,
    )
    await consumer.start()
    log.info(
        "consumer_started",
        group=group_id,
        topics=topics,
        profile=profile.value,
    )
    return consumer


# ==========================================================================
# 16. MAIN — STANDALONE DEMO (no broker required)
# ==========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  Kafka Production Operations — Illustrative Module Demo")
    print("=" * 70)

    # --- Capacity planning ---
    plan = CapacityPlan(
        avg_message_size_bytes=1_024,   # 1 KB
        messages_per_second=10_000,
        retention_days=7,
        replication_factor=3,
    )
    print("\n" + plan.describe())

    # --- Topic config with validation ---
    topic = TopicConfig(
        name="orders",
        num_partitions=24,
        replication_factor=3,
        retention_hours=168,
        cleanup_policy=CleanupPolicy.DELETE,
    )
    warnings = topic.validate()
    print(f"\n=== Topic '{topic.name}' Kafka Config ===")
    for k, v in topic.to_kafka_config().items():
        print(f"  {k} = {v}")
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    else:
        print("  Validation: PASS")

    # --- Producer / consumer config preview ---
    print("\n=== Producer Configs ===")
    for prof in ProducerProfile:
        cfg = build_producer_config("broker:9092", prof)
        print(f"  {prof.value}: {cfg}")

    print("\n=== Consumer Configs ===")
    for prof in ConsumerProfile:
        cfg = build_consumer_config("broker:9092", "my-group", ["orders"], prof)
        print(f"  {prof.value}: {cfg}")

    # --- Consumer lag alerting ---
    monitor = ConsumerLagMonitor(lag_threshold=10_000)
    snapshot_1 = [
        PartitionLag("orders", 0, consumer_offset=5_000, log_end_offset=5_500),
        PartitionLag("orders", 1, consumer_offset=3_000, log_end_offset=16_000),
    ]
    snapshot_2 = [
        PartitionLag("orders", 0, consumer_offset=5_100, log_end_offset=5_800),
        PartitionLag("orders", 1, consumer_offset=3_200, log_end_offset=18_000),
    ]
    monitor.record_snapshot(snapshot_1)
    monitor.record_snapshot(snapshot_2)

    print("\n=== Consumer Lag Report ===")
    for pl in snapshot_2:
        print(f"  {pl.topic}[{pl.partition}] lag={pl.lag:,}")
    alerts = monitor.check_alerts(snapshot_2)
    for alert in alerts:
        print(f"  {alert}")
    growing = monitor.growing_lag_partitions()
    for g in growing:
        print(f"  GROWING: {g}")

    # --- Schema compatibility ---
    changes = [
        SchemaChange("add_field", "customer_tier", has_default=True),
        SchemaChange("add_field", "internal_ref", has_default=False),
        SchemaChange("rename_field", "user_id"),
        SchemaChange("change_type", "amount", old_type="int", new_type="long"),
    ]
    validate_schema_changes(changes, SchemaCompatibility.BACKWARD)

    # --- Anti-pattern checklist ---
    print_anti_pattern_checklist()

    # --- Production issue playbooks ---
    for issue in [
        ProductionIssue.UNDER_REPLICATED_PARTITIONS,
        ProductionIssue.REBALANCE_STORM,
    ]:
        print_playbook(issue)

    # --- KRaft comparison ---
    print_kraft_comparison()

    # --- Cloud recommendation ---
    print("\n=== Cloud Kafka Recommendation ===")
    recommendation = recommend_cloud_kafka(
        team_size="medium", primary_cloud="aws", latency_sensitive=False
    )
    print(f"  Recommendation: {recommendation}")

    # --- Lifecycle guide ---
    print_lifecycle_guide("rolling_restart")

    print("\n" + "=" * 70)
    print("  All demos complete.  No broker connection was required.")
    print("=" * 70)
