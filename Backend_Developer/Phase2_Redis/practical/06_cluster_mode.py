"""
Redis Cluster — Production Patterns
"""

from redis.cluster import RedisCluster, ClusterNode
from redis.cluster import ReadConnection
import redis


# ==========================================================================
# 1. CONNECT TO CLUSTER
# ==========================================================================

startup_nodes = [
    ClusterNode("127.0.0.1", 7000),
    ClusterNode("127.0.0.1", 7001),
    ClusterNode("127.0.0.1", 7002),
]

rc = RedisCluster(
    startup_nodes=startup_nodes,
    decode_responses=True,
    skip_full_coverage_check=False,
    health_check_interval=30,
    socket_timeout=5,
    socket_connect_timeout=5,
)


# Or from URL
# rc = RedisCluster.from_url("redis://127.0.0.1:7000")


# ==========================================================================
# 2. BASIC OPS (same as standalone Redis)
# ==========================================================================

rc.set('user:1000', 'Alice')
print(rc.get('user:1000'))

rc.hset('user:1000:profile', mapping={'name': 'Alice', 'email': 'a@b.com'})
profile = rc.hgetall('user:1000:profile')


# ==========================================================================
# 3. HASH TAGS for multi-key operations
# ==========================================================================

# Same slot — same shard — multi-key ops work
rc.mset({
    '{cart:1}:items': '["item1", "item2"]',
    '{cart:1}:count': '2',
    '{cart:1}:total': '99.99',
})

values = rc.mget(['{cart:1}:items', '{cart:1}:count', '{cart:1}:total'])


# Pipeline (atomic per-shard)
pipe = rc.pipeline()
pipe.set('{user:42}:name', 'Bob')
pipe.incr('{user:42}:login_count')
pipe.expire('{user:42}:name', 3600)
pipe.execute()


# Lua script (single slot only)
script = """
local current = redis.call('GET', KEYS[1])
if current == false then
    redis.call('SET', KEYS[1], ARGV[1])
    return 1
end
return 0
"""
result = rc.eval(script, 1, '{cart:1}:lock', 'owner-1')


# ==========================================================================
# 4. CROSS-SLOT ERROR HANDLING
# ==========================================================================

try:
    # These keys likely on different slots
    rc.mget(['user:1', 'user:2', 'user:3'])
except redis.ClusterCrossSlotError:
    # Fall back to individual gets
    results = []
    for key in ['user:1', 'user:2', 'user:3']:
        results.append(rc.get(key))


# Helper — scatter-gather pattern
def cluster_safe_mget(rc, keys: list[str]) -> dict[str, str]:
    """Multi-get across cluster — groups by slot."""
    from collections import defaultdict

    by_slot = defaultdict(list)
    for key in keys:
        slot = rc.cluster_keyslot(key)
        by_slot[slot].append(key)

    result = {}
    for slot_keys in by_slot.values():
        if len(slot_keys) > 1:
            vals = rc.mget(slot_keys)
        else:
            vals = [rc.get(slot_keys[0])]
        for k, v in zip(slot_keys, vals):
            result[k] = v
    return result


# ==========================================================================
# 5. READ FROM REPLICAS (load distribution)
# ==========================================================================

rc_with_replicas = RedisCluster(
    startup_nodes=startup_nodes,
    decode_responses=True,
    read_from_replicas=True,   # default reads go to replicas
)


# Beware: replica lag — for critical reads use master:
val = rc_with_replicas.get('critical-key', target_nodes=rc.get_primaries())


# ==========================================================================
# 6. SCAN ACROSS CLUSTER
# ==========================================================================

def scan_all_keys(rc, match_pattern: str = '*'):
    """SCAN across all master nodes."""
    for node in rc.get_primaries():
        cursor = 0
        node_client = redis.Redis(host=node.host, port=node.port, decode_responses=True)
        while True:
            cursor, keys = node_client.scan(cursor, match=match_pattern, count=100)
            for k in keys:
                yield k
            if cursor == 0:
                break


# Usage
# for key in scan_all_keys(rc, 'user:*'):
#     print(key)


# ==========================================================================
# 7. CLUSTER INFO + HEALTH
# ==========================================================================

def cluster_health(rc):
    nodes = rc.cluster_nodes()
    # nodes = {'host:port': {'flags': 'master', ...}, ...}

    healthy = sum(1 for n in nodes.values() if 'fail' not in n.get('flags', ''))
    print(f"Healthy nodes: {healthy}/{len(nodes)}")

    info = rc.cluster_info()
    # info = {'cluster_state': 'ok', 'cluster_slots_ok': 16384, ...}
    if info['cluster_state'] != 'ok':
        print(f"ALERT: cluster state = {info['cluster_state']}")
    if info['cluster_slots_assigned'] < 16384:
        print(f"ALERT: only {info['cluster_slots_assigned']}/16384 slots assigned")


# ==========================================================================
# 8. KEY-TO-NODE INSPECTION
# ==========================================================================

def find_owner(rc, key: str):
    """Which node owns this key?"""
    slot = rc.cluster_keyslot(key)
    slots = rc.cluster_slots()

    for slot_range in slots:
        start, end, master = slot_range[0], slot_range[1], slot_range[2]
        if start <= slot <= end:
            return master  # (host, port, node_id)
    return None


# ==========================================================================
# 9. MIGRATION-AWARE CLIENT (handle ASK + MOVED)
# ==========================================================================

# redis-py handles MOVED/ASK transparently — no manual code needed
# Just retry on ClusterError if needed:

import time


def get_with_retry(rc, key, max_retries=3):
    for attempt in range(max_retries):
        try:
            return rc.get(key)
        except redis.ClusterDownError:
            time.sleep(0.5)
            continue
        except redis.ConnectionError:
            time.sleep(1)
            continue
    raise


# ==========================================================================
# 10. CLUSTER SETUP SCRIPT (reference)
# ==========================================================================

CLUSTER_SETUP = """
# 6 redis instances (3 masters + 3 replicas)
for port in 7000 7001 7002 7003 7004 7005; do
    mkdir -p ./redis-$port
    cat > ./redis-$port/redis.conf <<EOF
port $port
cluster-enabled yes
cluster-config-file nodes.conf
cluster-node-timeout 5000
appendonly yes
maxmemory 4gb
maxmemory-policy noeviction
EOF
    redis-server ./redis-$port/redis.conf &
done


# Create cluster
redis-cli --cluster create \\
    127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \\
    127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \\
    --cluster-replicas 1


# Inspect
redis-cli -p 7000 cluster info
redis-cli -p 7000 cluster nodes
redis-cli -p 7000 cluster slots


# Add node
redis-cli --cluster add-node 127.0.0.1:7006 127.0.0.1:7000


# Reshard (interactive)
redis-cli --cluster reshard 127.0.0.1:7000


# Test connectivity
redis-cli -c -p 7000   # -c = follow MOVED/ASK
> SET foo bar
> GET foo
"""


# ==========================================================================
# 11. ADMIN COMMANDS via Python
# ==========================================================================

def reshard_slots(rc, source_node_id: str, dest_node_id: str, num_slots: int):
    """Move slots from source to dest (programmatic resharding)."""
    # Get source's slot range
    source_node = rc.get_node(node_name=source_node_id)
    # ... complex; usually do via redis-cli --cluster reshard


def add_replica_to_master(rc, master_node_id: str, replica_host: str, replica_port: int):
    """Add a replica to a specific master."""
    # cluster replicate master-id
    pass


# ==========================================================================
# 12. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] At least 3 masters + 1 replica each (6 nodes total)
[ ] Each master/replica on different physical host (rack-aware)
[ ] cluster-node-timeout tuned (5s typical, 15s default)
[ ] AOF enabled for durability
[ ] maxmemory + noeviction policy (don't evict during cluster ops)
[ ] Backup strategy (BGSAVE on each master)
[ ] Monitoring: cluster_state, slots_ok, link_state per node
[ ] Connection pooling (one pool per node managed by client)
[ ] Slow log monitoring (CLUSTER SLOWLOG GET)
[ ] Alerts on: failover events, slot mismatch, master-replica lag
"""
