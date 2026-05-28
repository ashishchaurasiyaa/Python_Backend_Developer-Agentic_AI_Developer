# Redis Cluster Mode

## Why It Matters

Single-instance Redis = vertical scale limit (memory, CPU). Cluster = horizontal scale:
- **Sharding** → data split across N nodes
- **HA per shard** → each shard has master + replicas
- **Auto-failover** → replica promoted on master crash
- **No single point of failure**

Senior interview: "Redis can't fit dataset in one node — solution?" → Cluster mode.

---

## Core Concepts

### Hash Slots

Cluster has 16384 hash slots. Each key → slot via:
```
slot = CRC16(key) mod 16384
```

Slots distributed across master nodes:
```
Master 1: slots 0–5460
Master 2: slots 5461–10922
Master 3: slots 10923–16383
```

### Setup (Minimal — 3 Masters + 3 Replicas)

```bash
# 6 instances on ports 7000-7005
redis-server --port 7000 --cluster-enabled yes --cluster-config-file nodes-7000.conf --appendonly yes
# ... repeat for 7001-7005

# Create cluster
redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
                           127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
                           --cluster-replicas 1
```

### Python Client (redis-py Cluster)

```python
from redis.cluster import RedisCluster, ClusterNode


startup_nodes = [
    ClusterNode("127.0.0.1", 7000),
    ClusterNode("127.0.0.1", 7001),
    ClusterNode("127.0.0.1", 7002),
]
rc = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)


rc.set("user:1000", "Alice")
print(rc.get("user:1000"))
```

Client maintains slot mapping → routes commands directly. Updates on `MOVED` redirect.

### MOVED vs ASK Redirects

```
Client sends: GET user:5
Slot for "user:5" = 12345

Master at slot 12345 = Node B
If client asks Node A → returns MOVED 12345 nodeB:7001
Client retries on B + updates local map
```

`ASK` redirect = used during slot migration (temporary). Client retries on new node but doesn't update map permanently.

### Multi-Key Operations + Hash Tags

```python
# WRONG — keys may be on different shards
rc.mset({'user:1:profile': 'X', 'user:1:settings': 'Y'})  # CROSSSLOT error


# RIGHT — hash tag forces same slot
rc.mset({'{user:1}:profile': 'X', '{user:1}:settings': 'Y'})
# Slot computed from text between { and }
```

`{user:1}:profile` and `{user:1}:settings` both hash to same slot → same shard → atomic ops work.

### Pipeline + Transactions

```python
# Cluster pipeline — keys must be on same slot (use hash tags)
pipe = rc.pipeline()
pipe.set('{cart:1}:items', '...')
pipe.incr('{cart:1}:count')
pipe.execute()


# Cross-slot in cluster mode = ERROR
# Use multiple pipelines (one per shard)
```

### Resharding (Add/Remove Nodes)

```bash
# Add new master
redis-cli --cluster add-node 127.0.0.1:7006 127.0.0.1:7000

# Rebalance — move slots to new node
redis-cli --cluster reshard 127.0.0.1:7000
# Specify how many slots, source nodes


# Remove node (drain slots first)
redis-cli --cluster reshard ... # move all slots off
redis-cli --cluster del-node 127.0.0.1:7000 <node-id>
```

### Failover

```
Master crashes → replicas vote → highest priority replica promoted
Old master rejoins → becomes replica
```

Tunable via `cluster-replica-validity-factor`. `cluster-node-timeout` controls detection speed.

### Cross-Shard Operations

Cluster doesn't support multi-key ops across shards (transactions, MGET, etc.). Workarounds:
- Use hash tags to force same-shard
- Application-level scatter-gather (read from each shard, combine)
- Avoid multi-key patterns

### Cluster vs Sentinel

| | Cluster | Sentinel |
|---|---|---|
| Sharding | Yes | No (single master) |
| HA | Yes | Yes |
| Setup complexity | High | Low |
| Use case | Big data | Small data + HA |

For most apps: single instance + Sentinel. For > 100GB data: Cluster.

---

## How It Works Internally

### Gossip Protocol

Nodes exchange state via cluster bus (port = data port + 10000). Each node knows full topology. Updates propagate in O(log N).

### CLUSTER NODES Output

```
abc123... 127.0.0.1:7000@17000 myself,master - 0 0 0 connected 0-5460
def456... 127.0.0.1:7001@17001 master - 0 ... connected 5461-10922
...
```

### Slot Migration Protocol

```
1. Source node marks slot MIGRATING
2. Target node marks slot IMPORTING
3. Keys moved one-by-one (MIGRATE command)
4. Clients hit source → ASK redirect to target during migration
5. After all keys moved → SETSLOT NODE permanently
```

---

## Common Pitfalls

### 1. Cross-Slot Operations

```python
rc.mget(['key1', 'key2', 'key3'])  # may fail if different slots
```

Use hash tags OR multiple gets.

### 2. Transactions / Lua Across Shards

```python
# WATCH/MULTI/EXEC, Lua EVAL — all single-shard only
```

Design data layout so related keys share slot.

### 3. SCAN Per Node

```python
# SCAN scans one node at a time
for node in rc.get_nodes():
    for key in node.scan_iter():
        ...
```

Not a single SCAN across cluster.

### 4. PubSub Limited

Cluster pub/sub broadcasts to all nodes (inefficient). Use sharded pub/sub (Redis 7+ `SSUBSCRIBE`).

### 5. CLUSTER KEYSLOT Asymmetric

Different language clients may hash differently. Always use `CLUSTER KEYSLOT key` to verify.

### 6. Replica Reads Not Default

By default, all reads go to master. To use replicas:

```python
rc = RedisCluster(read_from_replicas=True)
```

Risk: replica lag → stale reads.

### 7. Configuration Differences

`MOVED` errors flood logs if cluster topology unstable. `CLUSTERDOWN` if too few nodes online (< (slots/16384) coverage).

---

## Interview Q&A

**Q1:** Redis Cluster aur Sentinel mein difference?
**A:** Cluster: sharding + HA, 16384 hash slots distributed across nodes, scales horizontally. Sentinel: single master with replicas, monitor + auto-failover, no sharding. Cluster for big data (>100GB), Sentinel for HA on smaller datasets.

**Q2:** Multi-key operations Cluster mein kaise?
**A:** Hash tags — `{user:1}:profile` and `{user:1}:settings` both hash to same slot via text between `{}`. Forces same shard → MGET, transactions, Lua work. Without hash tag = CROSSSLOT error.

**Q3:** Resharding live cluster pe kaise hoti hai?
**A:** Slot migration: source marks slot MIGRATING, target IMPORTING, keys MIGRATE one-by-one. During migration, clients hit source get ASK redirect to target (temporary). After all keys moved, SETSLOT NODE finalizes. Zero downtime if done carefully.

**Q4:** MOVED vs ASK redirect?
**A:** MOVED: permanent — slot now owned by other node. Client updates local slot map. ASK: temporary — slot in migration, this specific key has moved. Client retries on new node WITHOUT updating map. Subsequent requests still hit original.

**Q5:** Failover trigger conditions?
**A:** Quorum-based: `cluster-node-timeout` (default 15s) → majority of masters mark master as failing → election among replicas → highest priority + most up-to-date wins → becomes new master. Tunable for faster failover (lower timeout) vs network blip tolerance.

**Q6:** Cluster scale-out steps?
**A:** (1) Provision new node. (2) `cluster meet` to introduce. (3) `cluster reshard` to move slots from existing nodes. (4) Optional: add replicas for new master. (5) Update client startup_nodes config. (6) Monitor for stable cluster state.

**Q7:** Stale reads from replicas — how to handle?
**A:** Configure `read_from_replicas=True` per query. For critical reads, use master only. Or replication lag monitoring: if lag > threshold, route reads back to master temporarily. WAIT command can ensure replication before read.

**Q8:** Cluster size — sweet spot?
**A:** 3-10 master nodes typical. Beyond 20+ masters, slot rebalancing slow, gossip overhead grows. Each master: 4-16 GB RAM, 1-2 replicas. For massive scale, multiple smaller clusters with app-level routing.

---

## Real-World Use Cases

### 1. Session Store (Big Scale)

Millions of sessions → Cluster shards by session_id. Each shard handles fraction. Failover automatic.

### 2. Cache Layer (Sharded)

Hot keys distributed across shards. Hash tag for related cached items.

### 3. Rate Limiting Counters

```python
# Per-user counter — sharded automatically
rc.incr(f'rl:user:{user_id}')
```

---

## References

- [Redis Cluster spec](https://redis.io/docs/management/scaling/)
- [Cluster Tutorial](https://redis.io/docs/management/scaling/#redis-cluster-101)
- redis-py-cluster docs
- "Redis in Action" — Cluster chapter
