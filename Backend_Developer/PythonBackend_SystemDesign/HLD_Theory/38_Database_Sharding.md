# 38 — Database Sharding

---

## What & Why

**Sharding** = horizontal partitioning of a database into smaller, independent pieces called **shards**. Each shard holds a subset of the data and runs on its own server.

```
Without Sharding:              With Sharding:
┌──────────────┐               ┌──────┐ ┌──────┐ ┌──────┐
│   One huge   │    →→→        │Shard1│ │Shard2│ │Shard3│
│   database   │               │users │ │users │ │users │
│  (bottleneck)│               │0-33M │ │33-66M│ │66-99M│
└──────────────┘               └──────┘ └──────┘ └──────┘
```

**When to shard?** When vertical scaling (bigger machine) hits limits AND read replicas can't handle write load.

---

## Sharding Strategies

### 1. Range-Based Sharding

```python
def get_shard_range(user_id: int, num_shards: int = 3) -> int:
    """Shard by value range."""
    shard_ranges = [(0, 33_333_333), (33_333_334, 66_666_666), (66_666_667, 99_999_999)]
    for i, (lo, hi) in enumerate(shard_ranges):
        if lo <= user_id <= hi:
            return i
    return num_shards - 1

# Pros: range queries easy (scan one shard)
# Cons: HOT SPOT — if user_ids are sequential, shard 0 gets all new users
```

### 2. Hash-Based Sharding

```python
def get_shard_hash(key: str, num_shards: int = 3) -> int:
    """Distribute by hash of key — uniform distribution."""
    import hashlib
    hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return hash_val % num_shards

# user_id=1001 → hash % 3 = shard 2
# user_id=1002 → hash % 3 = shard 0

# Pros: even distribution, no hot spots
# Cons: range queries span ALL shards (expensive), resharding is painful
```

### 3. Consistent Hashing (Best for Dynamic Resharding)

```python
import bisect
import hashlib

class ConsistentHashRing:
    """
    Virtual nodes on a ring. Adding/removing shards only moves ~1/n of data.
    Without consistent hashing: adding a shard reshuffles ~all data.
    With consistent hashing: reshuffles only ~1/n fraction.
    """
    def __init__(self, nodes: list[str], replicas: int = 150):
        self.replicas = replicas
        self.ring: dict[int, str] = {}
        self.sorted_keys: list[int] = []
        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.replicas):
            virtual_key = self._hash(f"{node}:{i}")
            self.ring[virtual_key] = node
            bisect.insort(self.sorted_keys, virtual_key)

    def remove_node(self, node: str):
        for i in range(self.replicas):
            virtual_key = self._hash(f"{node}:{i}")
            del self.ring[virtual_key]
            self.sorted_keys.remove(virtual_key)

    def get_node(self, key: str) -> str:
        if not self.ring: raise Exception("Ring is empty")
        hash_val = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, hash_val) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]

ring = ConsistentHashRing(["shard1", "shard2", "shard3"])
print("user_1001 →", ring.get_node("user_1001"))
print("user_1002 →", ring.get_node("user_1002"))
ring.add_node("shard4")   # Only ~25% of keys reassigned
print("After adding shard4, user_1001 →", ring.get_node("user_1001"))
```

### 4. Directory-Based Sharding

```python
# Lookup table: key → shard_id
# Flexible but lookup table becomes bottleneck

class DirectoryBasedSharding:
    def __init__(self):
        self.directory: dict[str, int] = {}  # stored in Redis/DB
        self.num_shards = 3

    def get_shard(self, user_id: str) -> int:
        if user_id not in self.directory:
            # Assign shard (e.g., round-robin or least loaded)
            self.directory[user_id] = len(self.directory) % self.num_shards
        return self.directory[user_id]
```

### 5. Geo-Based Sharding

```python
REGION_SHARDS = {
    "us-east": "shard-us-1",
    "us-west": "shard-us-2",
    "eu":      "shard-eu-1",
    "asia":    "shard-asia-1",
}

def get_shard_geo(user_region: str) -> str:
    return REGION_SHARDS.get(user_region, "shard-us-1")

# Pros: data locality (low latency), GDPR compliance (data in region)
# Cons: uneven load if users concentrated in one region
```

---

## Strategy Comparison

| Strategy | Distribution | Range Query | Resharding | Hot Spots |
|----------|-------------|-------------|------------|-----------|
| Range | Uneven | Easy (1 shard) | Hard (move ranges) | ❌ Yes |
| Hash (mod) | Even | Hard (all shards) | Very Hard | ✅ No |
| Consistent Hash | Even | Hard | Easy (~1/n moved) | ✅ No |
| Directory | Custom | Depends | Medium | Custom |
| Geo | By region | Medium | Medium | Regional |

---

## Resharding Problem

```
Problem: You start with 3 shards, now need 4.
Hash-based: user_id % 3 vs user_id % 4 → almost ALL keys move!

Old: user_1001 % 3 = 2  (was on shard2)
New: user_1001 % 4 = 1  (now on shard1)  ← DATA MOVE REQUIRED

Consistent hashing solution:
  Add shard4 to ring → only keys between shard4 and its predecessor move
  Expected: ~25% of keys move (1/n fraction)
```

---

## Cross-Shard Challenges

### 1. Cross-Shard Queries

```python
# "Find all users in city='Mumbai'" — city is not the shard key
# Must query ALL shards → scatter-gather

async def scatter_gather_query(query: str, shards: list) -> list:
    """Query all shards in parallel, gather results."""
    import asyncio
    tasks = [query_shard(shard, query) for shard in shards]
    results = await asyncio.gather(*tasks)
    # Merge and sort
    all_rows = [row for result in results for row in result]
    return sorted(all_rows, key=lambda x: x['id'])

# Solution: Denormalize city into user's shard key
# OR: maintain secondary index (city → [user_ids]) in separate shard/ES
```

### 2. Cross-Shard Transactions

```python
# Moving user from shard1 to shard2 (e.g., after resharding)
# Need 2-phase commit or SAGA pattern

async def move_user(user_id: str, from_shard: str, to_shard: str):
    # Phase 1: Prepare
    user_data = await from_shard.read(user_id)
    await to_shard.write(user_id, user_data)
    
    # Phase 2: Commit (mark old as deleted)
    await from_shard.delete(user_id)
    # Risk: failure between write and delete → duplicate!
    # Use tombstone + idempotency key to handle
```

### 3. Hot Shard / Hotspot Problem

```python
# Celebrity problem: 1 user has 50M followers → all queries hit same shard

class HotKeyHandler:
    """Spread hot key across multiple shards."""
    HOT_REPLICAS = 10

    async def get_hot_key(self, key: str) -> dict:
        # Route to random replica of the hot shard
        replica = random.randint(0, self.HOT_REPLICAS - 1)
        shard_key = f"{key}:replica:{replica}"
        return await self.cache.get(shard_key)

    async def write_hot_key(self, key: str, value: dict):
        # Write to all replicas
        for i in range(self.HOT_REPLICAS):
            shard_key = f"{key}:replica:{i}"
            await self.cache.set(shard_key, value)
```

---

## Shard Key Selection — Best Practices

```
✅ Good shard keys:
   - High cardinality (many distinct values)
   - Evenly distributed
   - Frequently used in queries (avoid scatter-gather)
   - Immutable (don't change after insert)
   
❌ Bad shard keys:
   - Monotonically increasing (timestamp, auto-increment ID) → hot shard
   - Low cardinality (status: active/inactive) → too few shards
   - Frequently changing (user_location) → requires data moves
   
Common choices:
   - user_id (hash) → routes user's data to one shard
   - tenant_id → multi-tenant: one tenant = one shard
   - Geographic region → geo-sharding
```

---

## Interview Q&A

**Q1: What is the difference between partitioning and sharding?**
> Partitioning = splitting data within a single database instance (horizontal = row split, vertical = column split). Sharding = distributing partitions across multiple database instances (machines). Sharding is essentially horizontal partitioning across machines.

**Q2: When should you NOT shard?**
> When you can solve the problem with: (1) vertical scaling (bigger machine), (2) caching (Redis for reads), (3) read replicas (for read-heavy workload). Sharding adds significant operational complexity — cross-shard joins, transactions, resharding. Apply only when necessary.

**Q3: Why is auto-increment ID a bad shard key?**
> Auto-increment is sequential. All new writes go to the shard handling the highest ID range (range sharding) or always hash to the same shard (if not randomized). This creates a "hot shard" that handles all writes while others are idle.

**Q4: How does consistent hashing minimize data movement during resharding?**
> In a hash ring, each node owns keys between itself and its predecessor. Adding a new node only takes keys from its immediate predecessor (1/n of total keys). Without consistent hashing, changing n (number of shards) means almost all keys change their target shard (k % n vs k % (n+1)).

**Q5: How to handle a cross-shard JOIN?**
> Options: (1) Application-level join: query both shards, merge in code. (2) Denormalization: embed joined data to avoid cross-shard queries. (3) Global secondary index: store city→[user_ids] mapping separately. (4) Co-location: ensure related data is on same shard (shard by user_id, store all user's orders on same shard).

**Q6: What is a hotspot and how to fix it?**
> Hotspot = one shard gets disproportionate traffic (reads or writes). Fix: (1) Better shard key (use hash of ID instead of ID itself). (2) Add salt/randomness to shard key. (3) For read hotspots: replicate hot data across multiple shards. (4) For celebrity problem: pull-based read (don't write to all followers' shards).

**Q7: How do you handle transactions across shards?**
> Options: (1) Avoid by design: keep related data on same shard (most common). (2) 2-Phase Commit (2PC): coordinator asks all shards to prepare, then commit. Blocks on failure. (3) SAGA: sequence of local transactions with compensating transactions on failure. (4) Eventual consistency: accept temporary inconsistency.

**Q8: What is the role of a shard manager / router?**
> Shard manager (e.g., MongoDB mongos, Vitess vtgate) routes queries to correct shard(s). Maintains shard map (key range → shard). Handles scatter-gather for cross-shard queries. Application connects to router, not directly to shards. Hides sharding complexity from application code.
