# Distributed Systems Theory — CAP, PACELC, Raft, Vector Clocks, Distributed Locks

## Quick Concepts

**WHAT:**
- **CAP Theorem** = Choose 2 of 3: Consistency, Availability, Partition tolerance
- **PACELC** = CAP extension: also choose Latency vs Consistency in normal operation
- **Consensus** = Multiple nodes agree on a value (Paxos, Raft)
- **Vector Clocks** = Track causality across nodes
- **CRDT** = Conflict-free Replicated Data Type (eventually consistent without coordination)
- **Distributed Lock** = Mutex across processes (Redlock, ZooKeeper)
- **Leader Election** = Choose one node as coordinator
- **Quorum** = Majority agreement (N/2 + 1)

**WHY senior engineers MUST know:**
- Distributed systems = subtle bugs
- Need to reason about failure modes
- Choose right tool (Redis vs etcd vs ZooKeeper)
- Understand DB guarantees (read your DB docs!)

**HOW failure modes:**

```
Single machine:
- Crash (rare, easy to detect)

Distributed:
- Crash (one node)
- Network partition (split brain)
- Slow network (timeouts)
- Byzantine failure (lying node)
- Clock skew (different times)
- Message reordering
- Message duplication
- All of above SIMULTANEOUSLY
```

---

## Interview Questions & Answers

### Q1: CAP Theorem — exactly kya hai?

**Answer:**

**WHAT:** In presence of network partition (P), system can guarantee:
- **Consistency (C)**: All nodes see same data at same time
- **Availability (A)**: Every request gets a response
- Pick 2: **CP** or **AP** (CA impossible if partition happens)

**WHY "CA" doesn't really exist:**
- Networks DO partition (cables fail, switches die, regions disconnect)
- If partition occurs, must choose: respond stale data (A) or fail (C)
- "CA" only true if you assume no partitions = fantasy

**HOW — Examples by system:**

| System | Choice | Behavior on partition |
|---|---|---|
| **PostgreSQL (single)** | CA-ish | No partition possible (single node) |
| **PostgreSQL with replication** | CP | Master unavailable if can't reach majority |
| **MongoDB (default)** | CP | Refuses writes if no quorum |
| **MongoDB (eventual)** | AP | Accepts writes, conflicts later |
| **Cassandra** | AP | Always accepts writes, eventual consistency |
| **DynamoDB (strong)** | CP | Refuses if no quorum |
| **DynamoDB (eventual)** | AP | Returns potentially stale |
| **Redis (single)** | CA-ish | Single point |
| **Redis Cluster** | CP | Refuses writes if no master |
| **etcd / ZooKeeper / Consul** | CP | Refuses if no quorum (used for coordination) |
| **Kafka** | CP | Producer waits if no quorum (with acks=all) |

**HOW — Practical scenario:**

```
3-node DB cluster: Node A, B, C
Network partition: A isolated from B, C

CP system response:
- Node A: "I can't reach majority — refuse writes"
- Nodes B, C: "We have quorum, accept writes"
- Result: A unavailable, B+C consistent

AP system response:
- Node A: "Accept writes anyway"
- Nodes B, C: "Accept writes anyway"
- Result: Both partitions available, will reconcile when network heals
- May have conflicts (same key updated differently)
```

---

### Q2: PACELC — CAP ka extension?

**Answer:**

**WHAT:** **P**artition: **A**vailability or **C**onsistency. **E**lse: **L**atency or **C**onsistency.

**WHY:**
- CAP only addresses partition case
- BUT: even without partition, you have tradeoffs
- Synchronous replication = consistency + latency
- Asynchronous replication = lower latency + eventual consistency

**HOW — PACELC classification:**

| System | PA/EL or PC/EC etc | Meaning |
|---|---|---|
| **DynamoDB** | PA/EL | Available + low latency (eventual) |
| **Cassandra** | PA/EL | Available + low latency (eventual) |
| **MongoDB** | PA/EC | Available during partition; consistent normally |
| **PostgreSQL (sync replicas)** | PC/EC | Strong consistency always |
| **VoltDB** | PC/EC | Strong consistency always |

**HOW — In code, PACELC matters:**

```python
# PostgreSQL sync vs async replicas

# Synchronous replication
# - Write returns AFTER replica acknowledges
# - Strong consistency
# - HIGHER latency (wait for replica)
db.execute("UPDATE users SET email = $1 WHERE id = $2", new_email, user_id)
# Waits for replica acknowledgment


# Asynchronous replication
# - Write returns immediately
# - Replica MAY lag (eventual consistency)
# - LOWER latency
db.execute("UPDATE users SET email = $1 WHERE id = $2", new_email, user_id)
# Returns immediately
# Replica updates later (10ms-100ms typical, can be more if replica behind)


# Read from replica might miss recent write
user = db_replica.execute("SELECT email FROM users WHERE id = $1", user_id)
# Could return OLD email!
```

---

### Q3: Raft consensus — kaise kaam karta hai?

**Answer:**

**WHAT:** Algorithm for multiple nodes to agree on shared state.

**WHY:**
- Distributed systems need agreement (who's the leader, what's the value)
- Used by: etcd, Consul, CockroachDB, TiKV
- Replaces complex Paxos (designed to be understandable)

**HOW — 3 components:**

**1. Leader Election**

```
Initially: All nodes = followers
After timeout: A node becomes candidate
Candidate asks other nodes to vote
Wins if majority votes
Becomes leader
Sends heartbeats to followers

If leader fails:
- Heartbeats stop
- Followers time out
- New election

Term: Logical time counter
Each leader = new term
```

**2. Log Replication**

```
Client sends write to leader
Leader appends to its log
Leader sends to followers
Followers append, send ack
When majority ack → leader commits, tells followers commit
Returns success to client
```

**3. Safety**

```
- Only candidate with most up-to-date log can become leader
- Once committed, value cannot be lost
- Linearizable reads (recent + correct)
```

**HOW — Use via etcd:**

```python
# pip install etcd3

import etcd3

# Connect to etcd cluster
client = etcd3.client(host='etcd-leader', port=2379)

# Put (replicated via Raft)
client.put('config/api_url', 'https://api.example.com')

# Get
value, metadata = client.get('config/api_url')
print(value.decode())   # https://api.example.com

# Watch for changes
events_iterator, cancel = client.watch('config/api_url')
for event in events_iterator:
    print(f"Changed: {event.value}")

# Distributed lock
lock = client.lock('my-lock', ttl=30)
if lock.acquire():
    try:
        # Critical section
        do_exclusive_work()
    finally:
        lock.release()
```

---

### Q4: Vector Clocks — causality kaise track karein?

**Answer:**

**WHAT:** Mechanism to determine happens-before relationship in distributed events.

**WHY:**
- Wall clocks are unreliable (clock skew, NTP delays)
- Need to know: did event A happen before event B?
- Used by: DynamoDB, Riak, Cassandra (versioning)

**HOW — Vector clock structure:**

```
3 nodes: A, B, C
Each maintains vector [A_count, B_count, C_count]

Initial:
- Node A: [0, 0, 0]
- Node B: [0, 0, 0]
- Node C: [0, 0, 0]

Node A event 1: Increment own counter
- Node A: [1, 0, 0]

Node B receives message from A:
- Update vector: [max(self, msg)] then increment own
- Node B: [1, 1, 0]

Node A event 2:
- Node A: [2, 0, 0]

Node C event 1 (concurrent with above):
- Node C: [0, 0, 1]


Comparison rules:
- V1 < V2 if V1[i] <= V2[i] for all i AND V1 != V2
- V1 || V2 (concurrent) if neither < the other

Examples:
[1, 0, 0] < [2, 0, 0]   ✅ A happened-before
[2, 0, 0] || [0, 0, 1]  ⚠️ Concurrent (parallel)
```

**HOW — Python implementation:**

```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class VectorClock:
    node_id: str
    clock: Dict[str, int] = field(default_factory=dict)

    def increment(self):
        """Local event — increment own counter."""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1

    def update(self, other_clock: Dict[str, int]):
        """Receive message — merge then increment."""
        # Merge: take max of each component
        for node_id, count in other_clock.items():
            self.clock[node_id] = max(self.clock.get(node_id, 0), count)
        # Increment own
        self.increment()

    def happens_before(self, other: "VectorClock") -> bool:
        """Self happens-before other?"""
        all_le = all(
            self.clock.get(k, 0) <= other.clock.get(k, 0)
            for k in set(self.clock) | set(other.clock)
        )
        not_equal = self.clock != other.clock
        return all_le and not_equal

    def concurrent_with(self, other: "VectorClock") -> bool:
        """Self concurrent with other (neither happens-before)?"""
        return not self.happens_before(other) and not other.happens_before(self)


# Usage
node_a = VectorClock("A")
node_b = VectorClock("B")

# A makes change
node_a.increment()  # A: {A:1}

# A sends message to B
b_clock_at_receive = dict(node_a.clock)
node_b.update(b_clock_at_receive)  # B: {A:1, B:1}

# B makes change
node_b.increment()  # B: {A:1, B:2}

# Was A's first event before B's second?
print(node_a.happens_before(node_b))  # True
```

**HOW — Conflict resolution with vector clocks:**

```python
# DynamoDB-style write
class VersionedDocument:
    def __init__(self, value, vector_clock):
        self.value = value
        self.vc = vector_clock

    @classmethod
    def merge_conflicting(cls, versions: List["VersionedDocument"]):
        """When concurrent writes, return all versions."""
        # Filter out dominated versions
        winners = []
        for v in versions:
            is_dominated = any(
                v.vc.happens_before(other.vc) for other in versions if other != v
            )
            if not is_dominated:
                winners.append(v)

        if len(winners) == 1:
            return winners[0]
        else:
            # Conflict — return all for app to resolve
            raise ConflictError(winners)
```

---

### Q5: CRDT — conflict-free replicated data?

**Answer:**

**WHAT:** Data types that automatically resolve conflicts without coordination.

**WHY:**
- Multi-master replication without conflicts
- Eventually consistent without conflict resolution code
- Used by: Redis CRDTs (Redis Enterprise), Riak, real-time collaborative tools

**HOW — CRDT types:**

**1. G-Counter (Grow-only Counter)**

```python
class GCounter:
    """
    INTERVIEW: Counter that only goes up.
    Each node has own counter, total = sum.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.counters: Dict[str, int] = {}

    def increment(self, value: int = 1):
        self.counters[self.node_id] = self.counters.get(self.node_id, 0) + value

    def value(self) -> int:
        return sum(self.counters.values())

    def merge(self, other: "GCounter"):
        # Take max of each node's counter
        for node, count in other.counters.items():
            self.counters[node] = max(self.counters.get(node, 0), count)


# Usage: distributed view counter
node_a = GCounter("A")
node_b = GCounter("B")

# Independent updates
node_a.increment()    # A: {A:1}
node_a.increment()    # A: {A:2}
node_b.increment()    # B: {B:1}

# Eventually merge
node_a.merge(node_b)  # A: {A:2, B:1}, value=3
node_b.merge(node_a)  # B: {A:2, B:1}, value=3

# Both converge to same value
```

**2. PN-Counter (Increment + Decrement)**

```python
class PNCounter:
    """Counter that can go up or down."""
    def __init__(self, node_id):
        self.increments = GCounter(node_id)
        self.decrements = GCounter(node_id)

    def increment(self): self.increments.increment()
    def decrement(self): self.decrements.increment()
    def value(self): return self.increments.value() - self.decrements.value()

    def merge(self, other):
        self.increments.merge(other.increments)
        self.decrements.merge(other.decrements)
```

**3. G-Set (Grow-only Set)**

```python
class GSet:
    """Set that only adds (no remove)."""
    def __init__(self):
        self.items = set()

    def add(self, item): self.items.add(item)
    def contains(self, item): return item in self.items
    def merge(self, other): self.items |= other.items   # Union
```

**4. OR-Set (Observed-Remove Set)**

```python
class ORSet:
    """
    Set with add + remove (CRDT-friendly).
    Each add gets unique tag, remove targets specific tag.
    """
    def __init__(self):
        self.added = {}    # item → set of tags
        self.removed = {}  # item → set of tags

    def add(self, item):
        tag = uuid.uuid4()
        self.added.setdefault(item, set()).add(tag)

    def remove(self, item):
        # Move all current tags to removed
        for tag in self.added.get(item, set()):
            self.removed.setdefault(item, set()).add(tag)

    def contains(self, item):
        active_tags = self.added.get(item, set()) - self.removed.get(item, set())
        return bool(active_tags)

    def merge(self, other):
        # Union of added and removed (tag-based)
        for item, tags in other.added.items():
            self.added.setdefault(item, set()).update(tags)
        for item, tags in other.removed.items():
            self.removed.setdefault(item, set()).update(tags)
```

---

### Q6: Distributed Locks — Redlock vs ZooKeeper vs etcd?

**Answer:**

**WHAT:** Mutex across multiple processes/nodes.

**WHY:**
- Prevent concurrent operations
- Leader election
- Coordinating tasks

**HOW — Redis (Redlock):**

```python
# pip install redis

import redis
import uuid
import time

class RedisLock:
    """
    Single-Redis lock (NOT Redlock — Redlock uses 5 Redis nodes).
    """
    def __init__(self, redis_client: redis.Redis, key: str, ttl_ms: int = 30000):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.ttl_ms = ttl_ms
        self.token = str(uuid.uuid4())   # ⭐ Unique to this acquisition

    def acquire(self) -> bool:
        # SET with NX (only if not exists) + PX (TTL)
        result = self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
        return result is True

    def release(self):
        # ⭐ Lua script: check token THEN delete (atomic)
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        self.redis.eval(lua_script, 1, self.key, self.token)


# Usage
redis_client = redis.Redis(host='redis', port=6379)
lock = RedisLock(redis_client, "user-123-process")

if lock.acquire():
    try:
        # Critical section
        process_user(user_id=123)
    finally:
        lock.release()
else:
    print("Could not acquire lock")
```

**HOW — Proper Redlock (multi-Redis):**

```python
# pip install redlock-py

from redlock import Redlock

dlm = Redlock([
    {"host": "redis-1", "port": 6379, "db": 0},
    {"host": "redis-2", "port": 6379, "db": 0},
    {"host": "redis-3", "port": 6379, "db": 0},
    {"host": "redis-4", "port": 6379, "db": 0},
    {"host": "redis-5", "port": 6379, "db": 0},
])

# Acquire across N/2+1 Redis instances
my_lock = dlm.lock("my_resource", 1000)   # 1000ms TTL
if my_lock:
    try:
        # Critical section
        do_work()
    finally:
        dlm.unlock(my_lock)
```

**HOW — etcd lock (strongest guarantee):**

```python
import etcd3

client = etcd3.client(host='etcd', port=2379)

# Lock with auto-release on session loss
lock = client.lock('my-resource', ttl=30)
if lock.acquire(timeout=10):
    try:
        do_work()
    finally:
        lock.release()
```

**Comparison:**

| Lock System | Consistency | Performance | Use Case |
|---|---|---|---|
| **Redis (single)** | ⚠️ Weak (failover loss) | Very fast | Low-stakes coordination |
| **Redlock (5 Redis)** | Better but debated | Fast | Most use cases |
| **ZooKeeper** | Strong (Zab consensus) | Slower | Critical coordination |
| **etcd** | Strong (Raft) | Slower | Kubernetes ecosystem |

**⚠️ Important caveat (Redlock criticism by Martin Kleppmann):**
- Even Redlock isn't truly safe for correctness-critical use
- Use fencing tokens for true safety
- Use ZooKeeper/etcd for distributed locks needing strong guarantees

---

### Q7: Leader Election — Bully algorithm vs Raft?

**Answer:**

**WHAT:** Choose one node as coordinator.

**WHY:**
- Distributed databases (write replicas)
- Job schedulers (single instance)
- Cache invalidation coordinator

**HOW — Bully Algorithm:**

```
Nodes have unique IDs (e.g., 1, 2, 3, 4, 5)
Highest ID = leader

If leader fails:
1. Any node detecting failure starts election
2. Sends ELECTION message to all higher-ID nodes
3. If no response → declares self leader, broadcasts VICTORY
4. If response → waits for higher node to take over

Pros: Simple
Cons: O(N²) messages
```

**HOW — Raft Leader Election (better):**

```
All nodes start as followers
Each has random election timeout (150-300ms)

If follower times out without heartbeat:
1. Becomes candidate
2. Increments term
3. Votes for self
4. Sends RequestVote to all peers
5. If majority votes → becomes leader
6. Sends heartbeats to maintain leadership

Pros: O(N) messages, fault-tolerant
Cons: More complex
```

**HOW — Use via Kubernetes (leader election lease):**

```python
# pip install kubernetes

from kubernetes import client, config
from kubernetes.leaderelection import leaderelection
from kubernetes.leaderelection.resourcelock.configmaplock import ConfigMapLock
from kubernetes.leaderelection import electionconfig

config.load_incluster_config()

def on_started_leading():
    print("Became leader — running scheduled jobs")

def on_stopped_leading():
    print("Lost leadership")

config = electionconfig.Config(
    ConfigMapLock(
        "my-leader-lock",
        "default",       # namespace
        candidate_id="pod-id-here",
    ),
    lease_duration=15,
    renew_deadline=10,
    retry_period=2,
    onstarted_leading=on_started_leading,
    onstopped_leading=on_stopped_leading
)

# Blocks forever, runs callback when leader
leaderelection.LeaderElection(config).run()
```

---

### Q8: Quorum systems — N, W, R config?

**Answer:**

**WHAT:** Read/write to subset of replicas, with quorum overlap for consistency.

**HOW — Formula:**
```
N = total replicas
W = write quorum (replicas that must ack write)
R = read quorum (replicas to query for read)

Strong consistency requires: W + R > N
```

**HOW — Examples:**

```
N=3, W=2, R=2: W+R=4 > 3 ✅ Strong consistency
  - Write to majority (2 of 3)
  - Read from majority (2 of 3)
  - Overlap guarantees at least 1 replica has latest

N=3, W=1, R=1: W+R=2 ≤ 3 ❌ May read stale
  - Fastest, but eventual consistency

N=3, W=3, R=1: W+R=4 > 3 ✅ Read from 1 (fast reads)
  - But writes need ALL replicas (slow)
  - Any node failure = no writes

N=3, W=1, R=3: W+R=4 > 3 ✅ Write to 1 (fast writes)
  - Reads need all replicas
  - Any node failure = no reads
```

**HOW — Cassandra example:**

```python
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel

cluster = Cluster(['cassandra-1', 'cassandra-2', 'cassandra-3'])
session = cluster.connect('myapp')

# Strong consistency (W + R > N)
session.default_consistency_level = ConsistencyLevel.QUORUM
# QUORUM = N/2 + 1, so N=3 → 2 replicas

# Eventual consistency
session.default_consistency_level = ConsistencyLevel.ONE

# Per-query override
from cassandra.query import SimpleStatement

query = SimpleStatement(
    "SELECT * FROM users WHERE id = ?",
    consistency_level=ConsistencyLevel.LOCAL_QUORUM
)
result = session.execute(query, (user_id,))
```

**Cassandra consistency levels:**

| Level | Description | Use Case |
|---|---|---|
| `ONE` | 1 replica | Fast, may be stale |
| `QUORUM` | N/2 + 1 | Strong, slower |
| `ALL` | All replicas | Strictest, slowest |
| `LOCAL_QUORUM` | Quorum in local DC | Multi-DC, low latency |
| `EACH_QUORUM` | Quorum in each DC | Multi-DC, strong |

---

## Distributed Systems Decision Guide

```markdown
### CAP/PACELC Choice
- [ ] Strong consistency needed? → CP (PostgreSQL replicated, MongoDB strict, DynamoDB strong)
- [ ] High availability needed? → AP (Cassandra, DynamoDB eventual)
- [ ] Both impossible — choose based on business

### Consensus
- [ ] Need agreement (config, leader)? → etcd, ZooKeeper, Consul
- [ ] Building DB? → Use Raft, Paxos
- [ ] Don't roll your own (use proven impls)

### Conflict Resolution
- [ ] Simple counter? → CRDT (G-Counter)
- [ ] Set operations? → OR-Set
- [ ] Need to track causality? → Vector clocks
- [ ] Document store? → Last-write-wins (with timestamps)

### Distributed Locks
- [ ] Best-effort coordination? → Redis with TTL
- [ ] Correctness-critical? → ZooKeeper / etcd
- [ ] K8s ecosystem? → etcd / Lease objects

### Quorum
- [ ] Strong consistency? → W + R > N (typically W=R=quorum)
- [ ] Multi-DC? → LOCAL_QUORUM
- [ ] Read-heavy? → W=N, R=1 (slow writes)
- [ ] Write-heavy? → W=1, R=N (slow reads)
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Trusting wall clocks | Clock skew bugs | Vector clocks / logical clocks |
| Rolling own consensus | Subtle bugs | Use etcd / ZooKeeper |
| Redlock for correctness | Not truly safe (debate) | Use fencing tokens |
| Eventual consistency surprise | User confusion | UX shows "syncing" |
| Picking AP without need | Consistency loss | Default to strong unless need |
| No quorum config | Default may be wrong | Explicit W + R + N |
| Ignoring network partitions | Split brain | Design for partition |
| Assuming exactly-once | Hard to achieve | Idempotency keys |
