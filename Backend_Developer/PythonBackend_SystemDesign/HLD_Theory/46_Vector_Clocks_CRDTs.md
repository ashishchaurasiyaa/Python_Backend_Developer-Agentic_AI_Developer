# 46 — Vector Clocks & CRDTs

> How distributed systems reason about "what happened before what" without trusting wall clocks.

---

## Why We Need This

In a single machine, ordering is trivial: timestamps from one clock.

In distributed systems:
- Clocks drift (NTP only synced to ~10ms).
- Network delays mean events arrive out of order.
- Two nodes can produce different "current time".

You can't trust wall clocks for ordering events that happen on different machines.

---

## Lamport Clocks (Recap)

[From earlier file 09]: assign monotonic counter to events.

```
Each process P maintains counter C.
On any event: C += 1.
On send: include C in message.
On receive (with C' from sender):
   C = max(C, C') + 1
```

**Provides:** Total ordering of all events consistent with causality.

**Limitation:** Lamport timestamps tell you if A → B (A happened-before B), but NOT if A and B are concurrent. You can't distinguish "A caused B" from "A and B happened independently".

---

## Vector Clocks

Vector clock = one counter per process.

### Algorithm

```
Each process P_i maintains a vector V_i = [v_1, v_2, ..., v_n].
v_j tracks "what does P_i think P_j's clock is".

On local event:
  V_i[i] += 1

On send message:
  V_i[i] += 1
  attach V_i to message

On receive (from P_k with V_k):
  for j: V_i[j] = max(V_i[j], V_k[j])
  V_i[i] += 1
```

### Reading vector clocks

```
A.vc = [3, 1, 0]
B.vc = [3, 2, 0]
C.vc = [3, 1, 1]
D.vc = [2, 2, 1]

Compare A and B:
  A.vc[i] <= B.vc[i] for all i → A < B → A happened-before B

Compare A and C:
  A[0]=3 <= C[0]=3 ✓
  A[1]=1 <= C[1]=1 ✓
  A[2]=0 <= C[2]=1 ✓
  → A < C → A happened-before C

Compare B and C:
  B[1]=2 > C[1]=1 → B > C in dim 1
  C[2]=1 > B[2]=0 → C > B in dim 2
  → CONCURRENT (neither happened-before the other)
```

### Why this matters

Vector clocks tell you:
- **A → B** (A happened-before B): you can be sure no information from B has affected A.
- **B → A**: vice versa.
- **A || B** (concurrent): could've happened in any order; conflict resolution needed.

---

## Example: Distributed Database with Vector Clocks

Cassandra and DynamoDB (originally) used vector clocks for conflict detection.

```
Initial state:
  Server 1, 2, 3 all have item X = "blue"
  All vector clocks = [0, 0, 0]

Time 1: client writes "red" to Server 1
  Server 1: X = "red", vc = [1, 0, 0]

Time 2: client writes "green" to Server 2 (concurrent with above; before sync)
  Server 2: X = "green", vc = [0, 1, 0]

Time 3: Server 1 and 2 sync
  Server 1 sees X = "green" with vc = [0,1,0]
  Server 1's vc is [1,0,0]
  These are CONCURRENT (neither dominates)
  → CONFLICT! Need conflict resolution.

Possible resolutions:
  1. Last-write-wins by timestamp (lose data).
  2. Application-level merge (e.g., shopping cart union — Dynamo's approach).
  3. Surface to user ("you have conflicting versions").
```

---

## Vector Clock Limitations

### 1. Size grows with cluster
For N nodes, each vc has N entries. Cluster of 1000 nodes = 1000-element vector per piece of data.

### 2. Garbage collection
When can we shrink? When all entries before timestamp X are "known safe" (all nodes have acknowledged).

### 3. Add/remove nodes
Adding a node introduces new dimension. All existing data has implicit 0 there.

---

## Version Vectors

Practical variant of vector clocks: instead of "per event" counters, use "per object" counters per replica.

Used by:
- Riak (Dotted Version Vectors).
- DynamoDB (until 2017, switched to LWW with timestamps).
- Voldemort.

---

## CRDTs — Conflict-Free Replicated Data Types

**Goal:** Achieve eventual consistency *without* coordination, using data types whose operations always commute.

### Two flavors

#### State-based CRDTs (CvRDTs)
- Each replica has full state.
- Periodic gossip: replicas exchange states.
- Merge function combines two states (must be commutative, associative, idempotent).

#### Operation-based CRDTs (CmRDTs)
- Replicas exchange operations (not full state).
- Reliable broadcast required.
- Operations must commute.

---

## CRDT Primitives

### G-Counter (Grow-only Counter)

Counter that only increments.

```python
class GCounter:
    def __init__(self, node_id, n_nodes):
        self.node_id = node_id
        self.state = [0] * n_nodes

    def increment(self, n=1):
        self.state[self.node_id] += n

    def value(self):
        return sum(self.state)

    def merge(self, other):
        self.state = [max(a, b) for a, b in zip(self.state, other.state)]
```

Each node tracks its own contributions. Total = sum.

**Property:** No matter the order of operations or merges, final value is identical.

### PN-Counter (Positive-Negative)

Counter with increment and decrement = two G-counters (P and N).

```python
class PNCounter:
    def __init__(self, node_id, n_nodes):
        self.p = GCounter(node_id, n_nodes)
        self.n = GCounter(node_id, n_nodes)

    def increment(self): self.p.increment()
    def decrement(self): self.n.increment()

    def value(self):
        return self.p.value() - self.n.value()

    def merge(self, other):
        self.p.merge(other.p)
        self.n.merge(other.n)
```

### G-Set (Grow-only Set)

Add-only set. Union for merge.

### 2P-Set (Two-Phase Set)
Set with add and remove.
- `added` set + `removed` set (tombstones).
- Once removed, can't re-add (limitation).

### OR-Set (Observed-Remove Set)
Set with add and remove, where re-add works.
- Each add tagged with unique ID.
- Remove specific IDs.

```python
class ORSet:
    def __init__(self):
        self.elements = {}      # element → set of unique IDs
        self.tombstones = set() # removed IDs

    def add(self, element):
        uid = uuid.uuid4().hex
        self.elements.setdefault(element, set()).add(uid)

    def remove(self, element):
        if element in self.elements:
            for uid in self.elements[element]:
                self.tombstones.add(uid)
            del self.elements[element]

    def contains(self, element):
        ids = self.elements.get(element, set())
        return len(ids - self.tombstones) > 0

    def merge(self, other):
        for e, ids in other.elements.items():
            self.elements.setdefault(e, set()).update(ids)
        self.tombstones.update(other.tombstones)
```

### LWW-Register (Last-Write-Wins)
- Stores value + timestamp.
- Merge: pick value with latest timestamp.
- Simple but loses data on concurrent writes.

### MV-Register (Multi-Value)
- Stores all concurrent values.
- Application resolves conflicts.

---

## CRDT Text Editing (Real-time Collab)

For collaborative editors (Google Docs, Figma, CodeSandbox):

### Logoot
- Each character has a unique position identifier.
- Insert between two characters → new identifier "between" them.
- Concurrent inserts at same position → both kept (deterministic order via tie-break).

### RGA (Replicated Growable Array)
- Each character linked to previous one.
- Deletes mark tombstone.
- Causal order preserved via vector clock.

### Yjs (modern, used by many production editors)
- Optimized RGA-like algorithm.
- Compact memory, fast.

```javascript
// Yjs example
const ydoc = new Y.Doc();
const ytext = ydoc.getText('content');

ytext.insert(0, 'Hello');
// Sync with another peer...
ytext.insert(5, ', World');
// Concurrent inserts merge automatically.
```

---

## CRDT Sets in Production

### Riak (Basho)
- Built CRDTs into the database.
- Counters, Sets, Maps as native types.

### Redis
- Modules: RedisJSON (CRDT-like), Redis Streams (append-only).
- Not pure CRDT but eventually consistent ops.

### Apache Cassandra
- Counters use CRDT semantics (PN-Counter-like).

### Microsoft Cosmos DB
- Multi-master mode with CRDT-based conflict resolution.

---

## Trade-offs of CRDTs

### Pros
- **No coordination** — replicas can update independently.
- **Always available** — even during network partition.
- **Eventually consistent** — merges always converge.
- **Mathematically guaranteed correctness**.

### Cons
- **Limited operations** — only those that commute/are idempotent.
- **Storage overhead** — version metadata, tombstones.
- **Tombstone GC** — when to remove deleted markers safely.
- **Complex implementation** — harder than centralized.

---

## When to Use CRDTs

**Yes:**
- Collaborative apps (docs, design, whiteboards).
- Offline-first apps (mobile that syncs).
- Multi-region active-active DBs.
- Counters / metrics that need to be incremented from many places.
- Shopping carts in distributed e-commerce.

**No:**
- Banking / financial txn (need strict ordering, ACID).
- Inventory (over-counting bad).
- When you can afford a single leader.

---

## Real-World Example: Shopping Cart (Dynamo Paper)

Original Dynamo paper has the canonical shopping cart example:

```
User adds item A to cart on phone (offline).
User adds item B on laptop (offline).
Both come back online.
Server A has [A], Server B has [B].
Merge: cart = {A, B}.   ← union, never lose items.

Better than LWW which would lose one item!
```

This is why Amazon (and Dynamo derivatives) use a set CRDT for carts.

---

## Implementation Tip — Use a Library

Don't implement CRDTs from scratch. Use:
- **Yjs** (JS) — top quality, used by major editors.
- **Automerge** (JS/Rust/Go) — full document CRDT.
- **akka-cluster-distributed-data** (Scala).
- **Apache Riak DT** (Erlang).

---

## CRDT vs OT (Operational Transformation)

| | CRDT | OT |
|---|---|---|
| Coordination | None needed | Central server arbitrates |
| Offline editing | Native support | Hard |
| Algorithm complexity | High (per type) | Medium |
| Used by | Yjs, Automerge, Figma | Google Docs |
| Latency | Excellent | Good with low-latency server |

Modern preference: CRDT. Google Docs is moving toward CRDT internally.

---

## TL;DR

| Concept | What it does |
|---|---|
| Lamport clock | Total order respecting causality |
| Vector clock | Detect concurrent vs causal events |
| Version vector | Per-object vector for replica conflict detection |
| G-Counter | Increment-only distributed counter |
| PN-Counter | Increment + decrement |
| OR-Set | Add/remove set with re-add |
| LWW-Register | Last-write-wins value |
| Y.js / Automerge | Production CRDT libraries |

**Senior signal:** Knowing when to use LWW (simple, lossy) vs CRDT (complex, lossless), and being able to explain why concurrent writes don't break CRDTs.
