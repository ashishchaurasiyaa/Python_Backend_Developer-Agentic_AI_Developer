# 44 — Consistent Hashing — Theory Deep Dive

---

## The Problem It Solves

You have N servers and want to map keys → servers.

### Naive: modular hashing
```
server = hash(key) % N
```

Works fine while N is fixed.

**Disaster when N changes:**
- Add a node: N goes from 4 → 5. Now `hash(key) % 5 ≠ hash(key) % 4` for ~80% of keys.
- Most keys remap to a different server.
- Cache invalidation storm.
- Massive data movement.

**Numbers:** For N=4 → N=5, ~80% of keys move. For N=100 → N=101, ~99% of keys move. Catastrophic.

---

## Core Idea of Consistent Hashing

Map both **servers AND keys** onto the same circular hash space (the "ring"). A key goes to the next server clockwise.

```
Hash range: 0 to 2^32 - 1, arranged as a ring.

      0/2^32
        │
   S1 ──┤── S2
   │    │    │
   │  RING   │
   │    │    │
   S4 ──┤── S3
        │

Key K:  hash(K) = some point on ring
        → assigned to first server clockwise from that point
```

### When you add/remove a server
**Only K/N keys move** (where K = total keys, N = servers).

Add S5 between S2 and S3:
- Keys that were going to S3 (those between S2 and S5) now go to S5.
- Other ~80% of keys unaffected.

---

## Why This Works

```
Add server:
  - Inserted at some point on ring.
  - "Steals" keys from one neighbor.
  - Movement: K/N keys.

Remove server:
  - Its keys redistribute to next clockwise server.
  - Movement: K/N keys.

Compare with mod-hashing: ~K keys move.
Consistent hashing: only K/N keys move.
For 1B keys, 100 servers: 10M moved vs 990M moved. 99x improvement.
```

---

## Implementation

```python
import hashlib
import bisect

class ConsistentHashRing:
    def __init__(self, nodes=None, replicas=100):
        self.replicas = replicas      # virtual nodes per physical
        self.ring = {}                # hash → physical_node
        self.sorted_hashes = []
        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str) -> None:
        for i in range(self.replicas):
            h = self._hash(f"{node}#{i}")
            self.ring[h] = node
            bisect.insort(self.sorted_hashes, h)

    def remove_node(self, node: str) -> None:
        for i in range(self.replicas):
            h = self._hash(f"{node}#{i}")
            self.ring.pop(h, None)
            idx = bisect.bisect_left(self.sorted_hashes, h)
            if idx < len(self.sorted_hashes) and self.sorted_hashes[idx] == h:
                self.sorted_hashes.pop(idx)

    def get_node(self, key: str) -> str | None:
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_hashes, h) % len(self.sorted_hashes)
        return self.ring[self.sorted_hashes[idx]]
```

Time complexity: `get_node` is O(log V) where V = total virtual nodes.

---

## The Virtual Nodes Trick (vnodes)

**Problem with naive consistent hashing:** With few servers, keys distribute unevenly (one server gets 40% of keys, another 5%).

**Solution:** Each physical server takes K positions on the ring (= K virtual nodes).

```
Naive (1 position per server):
  4 servers → 4 arcs on ring
  Arc sizes very uneven → uneven load

With 100 vnodes per server:
  400 positions on ring
  Each server's 100 arcs average out → very even distribution
```

### How many vnodes?

| Vnodes per server | Load distribution stddev |
|---|---|
| 1 | ~30% |
| 10 | ~10% |
| 100 | ~3% |
| 1000 | ~1% |

Industry: 100-500 vnodes per physical node.

### Trade-off
- More vnodes → smoother distribution, slower lookups (binary search on more sorted hashes).
- 100-200 is the sweet spot.

---

## Variants & Improvements

### Jump Consistent Hash (Google)

Don't need a ring at all. Pure math.

```python
def jump_consistent_hash(key: int, num_buckets: int) -> int:
    """
    Google's jump consistent hash.
    Maps key to bucket [0, num_buckets) with same properties.
    """
    b, j = -1, 0
    while j < num_buckets:
        b = j
        key = key * 2862933555777941757 + 1
        j = int((b + 1) * (2**31 / ((key >> 33) + 1)))
    return b
```

**Pros:**
- No ring data structure.
- O(log n) time.
- No memory overhead.

**Cons:**
- Buckets identified by index 0..N-1.
- Can't remove arbitrary bucket (only the last).
- Used internally at Google for shard mapping.

### Rendezvous Hashing (HRW — Highest Random Weight)

For each key, compute `hash(key, server)` for every server. Pick the server with highest hash.

```python
def rendezvous_hash(key, servers):
    return max(servers, key=lambda s: hash(f"{key}:{s}"))
```

**Pros:**
- No ring needed.
- Adding/removing servers: only K/N keys move (same as consistent hashing).
- Simpler implementation.

**Cons:**
- O(N) per lookup (must hash with each server).
- For small N (< 100 servers), often faster than ring.

**Used by:** Memcached client libraries (libketama).

### Anchor Hash

Recent (2019) algorithm. Constant-time, distributed-friendly.
Used in modern systems like ScyllaDB.

---

## Replication on the Ring

For data systems like Cassandra/DynamoDB, you want each key on multiple servers (replication).

### Strategy
- Hash key → position on ring.
- Assign to next N servers clockwise (N = replication factor).
- Cassandra: typically RF=3.

```python
def get_replicas(self, key: str, n: int = 3) -> list[str]:
    h = self._hash(key)
    idx = bisect.bisect(self.sorted_hashes, h) % len(self.sorted_hashes)
    nodes = []
    seen = set()
    i = idx
    while len(nodes) < n:
        node = self.ring[self.sorted_hashes[i]]
        if node not in seen:
            nodes.append(node)
            seen.add(node)
        i = (i + 1) % len(self.sorted_hashes)
    return nodes
```

The `seen` set prevents picking same physical node twice (because vnodes are scattered).

---

## Real-World Use Cases

### Distributed Cache (Memcached, Redis Cluster)
- Distribute keys across cache nodes.
- Adding capacity → minimal rebuild.

### Cassandra / ScyllaDB
- Partition key hash → token range → replica nodes.
- 256 tokens per node by default.

### DynamoDB
- Internal partitioning uses consistent hashing.

### Akamai CDN
- One of the original use cases (Karger et al. 1997).
- URL → edge server.

### Discord (originally with Redis)
- Distributed chat shards via consistent hashing.

### Riak, CouchDB
- All Dynamo-style key-value stores use consistent hashing.

### Service Mesh (Envoy)
- Load balancing modes include consistent hashing for "sticky sessions" via hash on header/cookie.

---

## Handling Hotspots

Even with vnodes, you can get hotspots from skewed key access:
- One viral post in a social network.
- Celebrity user in a chat system.

### Solutions

**1. Salt the key:**
```python
# Spread "celeb_user_123" across multiple shards
shard = consistent_hash(f"celeb_user_123:{random.randint(0,9)}")
```
Read from any shard (replicas).

**2. Adaptive vnode allocation:**
Track per-vnode QPS; rebalance vnodes off hot servers.

**3. Caching layer above ring:**
Hot keys in app-local LRU.

---

## Common Interview Question

> *"What's the difference between consistent hashing and mod-hashing?"*

**Crisp answer:**

> Mod-hashing maps `hash(key) % N` to nodes. When N changes, almost every key remaps. Catastrophic for distributed caches.
>
> Consistent hashing puts both keys and nodes on a circular hash space. Each key goes to the next clockwise node. Adding/removing a node only moves `K/N` keys.
>
> Virtual nodes (100-200 per physical node) smooth distribution to ~1-3% variance.

---

## Production Concerns

### Node failure handling
- Detect via health check.
- Removed from ring.
- Keys redistribute (K/N moved).
- Use replication so removed node's data is still accessible from replicas.

### Adding new nodes (capacity)
- Insert into ring.
- New node serves new requests immediately.
- Old node's data for shifted keys: rebalanced via background sync.

### Rebalancing
- Don't move all data immediately (would saturate network).
- Stream new ownership over hours/days.
- Old node still serves reads until handoff complete.

### Topology awareness
- Place vnodes from different physical nodes in different racks/AZs.
- Cassandra has rack/datacenter awareness for replica placement.

---

## Picking the Right Algorithm

| Use case | Algorithm |
|---|---|
| Distributed cache | Consistent hashing with vnodes |
| Sharded DB | Consistent hashing or jump hash |
| Load balancer (sticky) | Consistent hashing on session ID |
| Highly dynamic cluster | Rendezvous (HRW) |
| Google-scale (millions of buckets) | Jump consistent hash |

---

## Visual Intuition

```
Adding a server to a 4-node ring:

Before:
  ┌─ S1 ─┐
 K1 → S1 (hash falls in S1's arc)
 K2 → S2
 K3 → S3
 K4 → S4

After adding S5 between S2 and S3:
 K1 → S1 (unchanged)
 K2 → S2 (unchanged)
 K3 → S5 (was S3; moved!)  ← only keys in this arc move
 K4 → S4 (unchanged)

Result: ~1/5 of keys moved (small fraction).
```

---

## TL;DR

- **Mod hashing** = catastrophic on resize.
- **Consistent hashing** = K/N keys move on resize.
- **Vnodes** = essential for even distribution.
- **Jump hash** / **rendezvous** = ring-less alternatives.
- **Replication** = pick next N nodes clockwise.

**Show this in interviews:** draw the ring, show vnodes, walk through what happens on node add. Senior signal.
