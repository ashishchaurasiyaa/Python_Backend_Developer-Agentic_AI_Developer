# Design Distributed Cache — HLD

## WHAT

A distributed cache is a **shared, in-memory key-value store** that multiple application servers can read/write concurrently. Reduces DB load by storing frequently accessed data in RAM.

**Examples:** Redis Cluster, Memcached, Apache Ignite, AWS ElastiCache

---

## Requirements

### Functional
- Get(key) → value (in <1ms)
- Set(key, value, TTL)
- Delete(key)
- Support for expiration (TTL-based eviction)
- Horizontal scalability (add nodes)

### Non-Functional
- 1 million requests/sec
- <1ms P99 latency
- 99.99% availability
- 10 TB total cache capacity
- Consistency: eventual (ok for cache use cases)

---

## Back-of-Envelope

```
Requests:   1M req/sec
Memory:     10 TB → need multiple nodes
            Typical server RAM: 256 GB
            Nodes needed: 10 TB / 256 GB ≈ 40 nodes

Per request: avg value size = 10 KB
Throughput:  1M × 10 KB = 10 GB/sec network → needs 10GbE NICs
```

---

## Architecture

```
                   ┌──────────────────────────┐
Application Servers│                          │
  ┌──────────┐     │   Consistent Hashing     │
  │ App-1    │────►│      Ring                │
  │          │     │                          │
  │ App-2    │────►│  ┌─────┐ ┌─────┐ ┌─────┐│
  │          │     │  │Cache│ │Cache│ │Cache││
  │ App-3    │────►│  │Node1│ │Node2│ │Node3││
  └──────────┘     │  │     │ │     │ │     ││
                   │  │ +   │ │ +   │ │ +   ││
                   │  │Repli│ │Repli│ │Repli││
                   │  │ca-1 │ │ca-2 │ │ca-3 ││
                   │  └─────┘ └─────┘ └─────┘│
                   └──────────────────────────┘
```

---

## Core Concepts

### 1. Consistent Hashing — Data Distribution

```python
import hashlib
import bisect
from typing import Optional

class ConsistentHashRing:
    """
    Consistent hashing ring — minimises redistribution when nodes added/removed.
    
    WITHOUT consistent hashing:
      5 nodes: key hashes to node = hash(key) % 5
      Add 6th node: ALL keys redistribute (hash % 6 changes for everything)
    
    WITH consistent hashing:
      Add 6th node: only ~1/6 of keys move
    """
    
    def __init__(self, virtual_nodes: int = 100):
        self.virtual_nodes = virtual_nodes
        self.ring: dict[int, str] = {}
        self.sorted_keys: list[int] = []
    
    def _hash(self, key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)
    
    def add_node(self, node: str):
        """Add a cache node with multiple virtual positions on the ring."""
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:vn{i}"
            h = self._hash(virtual_key)
            self.ring[h] = node
            bisect.insort(self.sorted_keys, h)
    
    def remove_node(self, node: str):
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:vn{i}"
            h = self._hash(virtual_key)
            del self.ring[h]
            self.sorted_keys.remove(h)
    
    def get_node(self, key: str) -> str:
        """Find which cache node is responsible for this key."""
        if not self.ring:
            raise Exception("No nodes in ring")
        h = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]


# Demo
ring = ConsistentHashRing(virtual_nodes=100)
ring.add_node("cache-node-1")
ring.add_node("cache-node-2")
ring.add_node("cache-node-3")

keys = ["user:123", "product:456", "session:789", "rate:alice"]
for key in keys:
    print(f"  {key!r:25} → {ring.get_node(key)}")

# Add 4th node — only ~25% of keys should move
ring.add_node("cache-node-4")
print("\nAfter adding node-4:")
for key in keys:
    print(f"  {key!r:25} → {ring.get_node(key)}")
```

### 2. Cache Client (Reads from Correct Node)

```python
import redis
from typing import Any, Optional

class DistributedCacheClient:
    """Client that routes requests to correct shard using consistent hashing."""
    
    def __init__(self, nodes: list[str]):
        self.ring = ConsistentHashRing()
        self.clients: dict[str, redis.Redis] = {}
        
        for node in nodes:
            self.ring.add_node(node)
            host, port = node.split(":")
            self.clients[node] = redis.Redis(host=host, port=int(port))
    
    def _get_client(self, key: str) -> redis.Redis:
        node = self.ring.get_node(key)
        return self.clients[node]
    
    def get(self, key: str) -> Optional[Any]:
        client = self._get_client(key)
        value  = client.get(key)
        return value.decode() if value else None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        client = self._get_client(key)
        return client.setex(key, ttl, str(value))
    
    def delete(self, key: str) -> int:
        client = self._get_client(key)
        return client.delete(key)
    
    def add_node(self, node: str):
        """Dynamically add a new cache node (only ~1/N keys move)."""
        self.ring.add_node(node)
        host, port = node.split(":")
        self.clients[node] = redis.Redis(host=host, port=int(port))
```

### 3. Eviction Policies

```python
from collections import OrderedDict
from typing import Optional

class LRUCache:
    """LRU — Least Recently Used (most common for caches)."""
    
    def __init__(self, capacity: int):
        self.cap   = capacity
        self.cache = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)    # mark as recently used
        return self.cache[key]
    
    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)  # evict LRU (first item)


"""
Other eviction policies:
  LFU (Least Frequently Used)  — evict least accessed overall
  FIFO                          — evict oldest inserted
  TTL-based                     — evict expired keys (Redis default)
  Random                        — simple, fast
  
Redis default: allkeys-lru (when maxmemory set)
"""
```

### 4. Cache Write Strategies

```python
"""
Write-Through:
  Write to cache AND DB simultaneously.
  Pros: Cache always fresh
  Cons: Write latency = DB latency
  Use when: Read-heavy, consistency important

Write-Back (Write-Behind):
  Write to cache only → async flush to DB later.
  Pros: Very fast writes
  Cons: Data loss risk if cache node dies before flush
  Use when: Write-heavy, can tolerate brief inconsistency

Write-Around:
  Write directly to DB, skip cache.
  Pros: Cache not polluted with write-once data
  Cons: First read = cache miss, hits DB
  Use when: Data written once, rarely read again
"""

class WriteStrategies:
    def write_through(self, key: str, value: Any, ttl: int):
        """Write to both cache and DB atomically."""
        self.cache.set(key, value, ttl)      # update cache
        self.db.write(key, value)            # update DB
        # Both must succeed — if DB fails, also delete from cache
    
    async def write_back(self, key: str, value: Any, ttl: int):
        """Write to cache, async flush to DB."""
        self.cache.set(key, value, ttl)
        self.dirty_keys.add(key)             # mark for async flush
        # Background worker flushes dirty_keys every 5 seconds
    
    def write_around(self, key: str, value: Any):
        """Skip cache, write directly to DB."""
        self.db.write(key, value)
        # Cache will populate on next read (cache-aside)
```

### 5. Cache Aside Pattern (Most Common in Production)

```python
import json

async def get_user(user_id: str) -> dict:
    """Cache-aside: check cache → on miss → load from DB → store in cache."""
    
    cache_key = f"user:{user_id}"
    
    # 1. Check cache
    cached = cache_client.get(cache_key)
    if cached:
        return json.loads(cached)          # cache HIT
    
    # 2. Cache MISS — load from DB
    user = await db.fetch_user(user_id)
    if not user:
        return None
    
    # 3. Store in cache with TTL
    cache_client.set(cache_key, json.dumps(user), ttl=3600)
    
    return user                            # return fresh data
```

---

## Replication & High Availability

```
Redis Sentinel (single-region HA):
  1 Master → 2 Replicas
  Sentinel monitors master health
  On master failure → promotes replica → updates clients

Redis Cluster (sharding + HA):
  16,384 hash slots distributed across nodes
  Each master has 1-2 replicas
  Automatically reshards on node add/remove

Example: 6 nodes (3 masters, 3 replicas):
  Node-1 (M): slots 0-5460     + Node-2 (R): replica of Node-1
  Node-3 (M): slots 5461-10922 + Node-4 (R): replica of Node-3
  Node-5 (M): slots 10923-16383+ Node-6 (R): replica of Node-5
```

---

## Hot Key Problem

```python
"""
Hot key: one key accessed by millions of requests/sec
Example: celebrity user profile, viral product

Problem: All requests hit same cache node → overloaded

Solutions:
1. Local in-memory cache (each app server caches hot key locally)
2. Key sharding: split hot key into N shards
   "user:celeb_123" → "user:celeb_123:shard_0" to "user:celeb_123:shard_7"
   Read from random shard (all have same data)
"""

import random

class HotKeyHandler:
    def __init__(self, num_shards: int = 8):
        self.num_shards = num_shards
    
    def write_hot_key(self, key: str, value: Any, ttl: int):
        """Write to all shards."""
        for i in range(self.num_shards):
            cache_client.set(f"{key}:shard_{i}", value, ttl)
    
    def read_hot_key(self, key: str) -> Any:
        """Read from random shard — distributes load."""
        shard = random.randint(0, self.num_shards - 1)
        return cache_client.get(f"{key}:shard_{shard}")
```

---

## Interview Q&A

**Q: What is consistent hashing and why is it used in distributed caches?**
A: Consistent hashing maps both keys and nodes to positions on a virtual ring. A key is owned by the nearest clockwise node. When nodes are added/removed, only ~1/N of keys need to be remapped (vs 100% with naive modulo hashing).

**Q: What is a cache stampede (thundering herd)?**
A: When a popular cache key expires, many requests hit the DB simultaneously. Solutions: (1) Cache locking: only 1 request refreshes, others wait (2) Stale-while-revalidate: serve stale data while refreshing in background (3) Jitter on TTL: add random seconds to TTL so not all expire at once.

**Q: When would you choose Memcached over Redis?**
A: Memcached: simpler, pure cache, slightly faster for simple string values, multi-threaded. Redis: data structures (sorted sets, lists, hashes), persistence, pub-sub, Lua scripting, Cluster mode. In 2025, Redis is almost always preferred.

**Q: How do you handle cache invalidation?**
A: (1) TTL: simplest, may serve stale (2) Event-driven: publish invalidation event when data changes (3) Write-through: update cache on every write. "Cache invalidation is one of the two hard problems in CS."
