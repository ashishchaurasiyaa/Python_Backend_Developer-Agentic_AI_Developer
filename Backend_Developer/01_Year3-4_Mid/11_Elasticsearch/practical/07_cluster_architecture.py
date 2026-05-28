"""
Elasticsearch Cluster Architecture — Production Patterns
"""

from elasticsearch import Elasticsearch
from datetime import datetime


es = Elasticsearch("http://localhost:9200")


# ==========================================================================
# 1. CLUSTER HEALTH CHECK
# ==========================================================================

def cluster_health():
    health = es.cluster.health()
    print(f"Status: {health['status']}")
    print(f"Nodes: {health['number_of_nodes']}")
    print(f"Active primaries: {health['active_primary_shards']}")
    print(f"Active total: {health['active_shards']}")
    print(f"Unassigned: {health['unassigned_shards']}")
    if health['unassigned_shards'] > 0:
        print("ALERT: unassigned shards — run cluster_allocation_explain")
    return health


def cluster_stats():
    stats = es.cluster.stats()
    print(f"Indices: {stats['indices']['count']}")
    print(f"Shards: {stats['indices']['shards']['total']}")
    print(f"Docs: {stats['indices']['docs']['count']:,}")
    print(f"Storage: {stats['indices']['store']['size_in_bytes'] / 1e9:.1f} GB")


# ==========================================================================
# 2. DEBUG UNASSIGNED SHARDS
# ==========================================================================

def diagnose_unassigned():
    """Find out why shards are unassigned."""
    explain = es.cluster.allocation_explain()
    print(f"Index: {explain['index']}")
    print(f"Shard: {explain['shard']}")
    print(f"Primary: {explain['primary']}")
    print(f"Current state: {explain['current_state']}")

    for decider in explain.get('node_allocation_decisions', []):
        print(f"  Node: {decider['node_name']}")
        for d in decider.get('deciders', []):
            if d.get('decision') == 'NO':
                print(f"    {d['decider']}: {d['explanation']}")


# ==========================================================================
# 3. NODE STATS (per-node monitoring)
# ==========================================================================

def node_stats():
    nodes = es.nodes.stats()
    for node_id, node in nodes['nodes'].items():
        name = node['name']
        # JVM
        heap_used_pct = node['jvm']['mem']['heap_used_percent']
        # Disk
        disk_used = node['fs']['total']['total_in_bytes'] - node['fs']['total']['available_in_bytes']
        disk_pct = disk_used / node['fs']['total']['total_in_bytes'] * 100
        # CPU
        cpu_pct = node['os']['cpu']['percent']
        # Open file descriptors
        fd = node['process']['open_file_descriptors']
        max_fd = node['process']['max_file_descriptors']

        print(f"{name}:")
        print(f"  Heap: {heap_used_pct}%")
        print(f"  Disk: {disk_pct:.1f}%")
        print(f"  CPU: {cpu_pct}%")
        print(f"  FDs: {fd}/{max_fd}")

        if heap_used_pct > 85:
            print(f"  ALERT: heap > 85% on {name}")
        if disk_pct > 85:
            print(f"  ALERT: disk > 85% on {name}")


# ==========================================================================
# 4. INDEX WITH SHARD STRATEGY
# ==========================================================================

def create_index_optimized(name: str, shards: int = 3, replicas: int = 1):
    """Create index with calculated shard count."""
    es.indices.create(
        index=name,
        settings={
            "number_of_shards": shards,
            "number_of_replicas": replicas,
            "refresh_interval": "30s",        # batch refreshes (faster indexing)
            "translog.durability": "async",   # batch fsync (faster, slight data risk)
            "index.routing.allocation.total_shards_per_node": 2,
        },
        mappings={
            "properties": {
                # ... your mappings
            },
        },
    )


# ==========================================================================
# 5. HOT-WARM-COLD ILM POLICY
# ==========================================================================

def setup_ilm_policy():
    """Lifecycle: hot 7d → warm 30d → cold 90d → delete."""
    es.ilm.put_lifecycle(
        name="logs_lifecycle",
        policy={
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_size": "50gb",
                            "max_age": "7d",
                        },
                        "set_priority": {"priority": 100},
                    },
                },
                "warm": {
                    "min_age": "7d",
                    "actions": {
                        "allocate": {
                            "include": {"data_tier": "warm"},
                            "number_of_replicas": 0,
                        },
                        "forcemerge": {"max_num_segments": 1},
                        "set_priority": {"priority": 50},
                    },
                },
                "cold": {
                    "min_age": "30d",
                    "actions": {
                        "allocate": {
                            "include": {"data_tier": "cold"},
                        },
                        "set_priority": {"priority": 0},
                    },
                },
                "delete": {
                    "min_age": "90d",
                    "actions": {"delete": {}},
                },
            },
        },
    )


def attach_ilm_to_template():
    """Apply ILM to all logs-* indices via template."""
    es.indices.put_index_template(
        name="logs_template",
        index_patterns=["logs-*"],
        template={
            "settings": {
                "index.lifecycle.name": "logs_lifecycle",
                "index.lifecycle.rollover_alias": "logs-write",
                "number_of_shards": 3,
                "number_of_replicas": 1,
            },
        },
    )


# ==========================================================================
# 6. ROUTING (multi-tenant)
# ==========================================================================

def index_with_routing(index: str, tenant_id: str, doc: dict):
    """All tenant's docs go to same shard."""
    return es.index(
        index=index,
        id=f"{tenant_id}_{doc.get('id')}",
        document=doc,
        routing=tenant_id,
    )


def search_with_routing(index: str, tenant_id: str, query: dict):
    """Search only tenant's shard — much faster."""
    return es.search(
        index=index,
        routing=tenant_id,
        query=query,
    )


# ==========================================================================
# 7. SHARD ALLOCATION AWARENESS (rack/zone)
# ==========================================================================

# Configure on each node via elasticsearch.yml:
"""
node.attr.zone: us-east-1a
cluster.routing.allocation.awareness.attributes: zone

# Forced: don't allocate replica in same zone as primary
cluster.routing.allocation.awareness.force.zone.values: us-east-1a,us-east-1b,us-east-1c
"""


# ==========================================================================
# 8. DISK WATERMARKS
# ==========================================================================

DISK_WATERMARK_CONFIG = """
# elasticsearch.yml or cluster setting

cluster.routing.allocation.disk.watermark.low: "85%"
cluster.routing.allocation.disk.watermark.high: "90%"
cluster.routing.allocation.disk.watermark.flood_stage: "95%"

# At low: don't allocate NEW shards
# At high: move existing shards off
# At flood: index becomes read-only
"""


# Via API
def configure_disk_watermarks():
    es.cluster.put_settings(
        persistent={
            "cluster.routing.allocation.disk.watermark.low": "80%",
            "cluster.routing.allocation.disk.watermark.high": "85%",
            "cluster.routing.allocation.disk.watermark.flood_stage": "90%",
        },
    )


# ==========================================================================
# 9. FORCE MERGE (after data fully written)
# ==========================================================================

def force_merge_index(index: str):
    """Merge segments — speeds up queries. Don't run on active write indices!"""
    # Make read-only first
    es.indices.put_settings(
        index=index,
        settings={"index.blocks.write": True},
    )
    es.indices.forcemerge(index=index, max_num_segments=1)
    # Refresh + open back for writes if needed
    es.indices.refresh(index=index)


# ==========================================================================
# 10. SNAPSHOTS
# ==========================================================================

def setup_s3_repo():
    """One-time setup."""
    es.snapshot.create_repository(
        name="s3_backup",
        body={
            "type": "s3",
            "settings": {
                "bucket": "my-es-backups",
                "region": "us-east-1",
                "base_path": "production-cluster",
                "compress": True,
            },
        },
    )


def take_snapshot(name: str):
    es.snapshot.create(
        repository="s3_backup",
        snapshot=name,
        indices="*",
        ignore_unavailable=True,
        include_global_state=True,
        wait_for_completion=False,
    )


def setup_slm_policy():
    """Snapshot Lifecycle Management — daily snapshots, retain 30 days."""
    es.slm.put_lifecycle(
        policy_id="daily-snapshots",
        body={
            "name": "<daily-snap-{now/d}>",
            "schedule": "0 0 2 * * ?",  # 2 AM daily
            "repository": "s3_backup",
            "config": {
                "indices": ["*"],
                "ignore_unavailable": True,
                "include_global_state": True,
            },
            "retention": {
                "expire_after": "30d",
                "min_count": 5,
                "max_count": 50,
            },
        },
    )


# ==========================================================================
# 11. CROSS-CLUSTER REPLICATION (DR)
# ==========================================================================

CCR_SETUP = """
# On follower cluster, configure remote
PUT _cluster/settings
{
    "persistent": {
        "cluster": {
            "remote": {
                "primary-cluster": {
                    "seeds": ["primary-host:9300"]
                }
            }
        }
    }
}


# Start following
PUT my-follower-index/_ccr/follow
{
    "remote_cluster": "primary-cluster",
    "leader_index": "my-leader-index"
}


# Auto-follow patterns
PUT _ccr/auto_follow/my-pattern
{
    "remote_cluster": "primary-cluster",
    "leader_index_patterns": ["logs-*"],
    "follow_index_pattern": "{{leader_index}}"
}
"""


# ==========================================================================
# 12. RECOVERY MONITORING
# ==========================================================================

def check_recovery():
    """Monitor shard recovery progress."""
    recovery = es.cat.recovery(active_only=True, format='json')
    for r in recovery:
        print(f"Index: {r['index']}, shard: {r['shard']}, stage: {r['stage']}, progress: {r['files_percent']}%")


# ==========================================================================
# 13. JVM SETTINGS (config file)
# ==========================================================================

JVM_OPTIONS = """
# jvm.options

# Heap size — 50% of RAM, max 32GB
-Xms16g
-Xmx16g

# G1GC for better latency on large heaps (ES 8+ default)
-XX:+UseG1GC
-XX:G1HeapRegionSize=32m
-XX:G1ReservePercent=25
-XX:InitiatingHeapOccupancyPercent=30

# Lock memory
bootstrap.memory_lock: true

# Network
network.host: 0.0.0.0
http.port: 9200
transport.port: 9300

# Cluster
cluster.name: prod-cluster
node.name: ${HOSTNAME}
discovery.seed_hosts: ["master-1", "master-2", "master-3"]
cluster.initial_master_nodes: ["master-1", "master-2", "master-3"]


# /etc/security/limits.conf
elasticsearch  -  nofile  65535
elasticsearch  -  memlock unlimited
elasticsearch  -  nproc   4096


# /etc/sysctl.conf
vm.max_map_count = 262144
vm.swappiness = 1
"""


# ==========================================================================
# 14. PROD MONITORING METRICS
# ==========================================================================

CRITICAL_METRICS = """
Cluster:
- elasticsearch_cluster_health_status (green/yellow/red)
- elasticsearch_cluster_unassigned_shards
- elasticsearch_cluster_pending_tasks

Per node:
- elasticsearch_jvm_memory_used_bytes / elasticsearch_jvm_memory_max_bytes
- elasticsearch_fs_total_available_bytes  (disk space)
- elasticsearch_process_open_file_descriptors / max
- elasticsearch_thread_pool_*_active (search, write, indexing pools)
- elasticsearch_indices_search_query_time_seconds (P95 latency)

Per index:
- search rate, latency
- indexing rate, latency
- refresh time
- merge time
- segment count
"""
