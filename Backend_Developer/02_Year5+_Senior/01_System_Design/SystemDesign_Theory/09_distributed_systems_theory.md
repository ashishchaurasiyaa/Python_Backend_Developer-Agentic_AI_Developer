# 🌐 Distributed Systems Theory — Foundation Guide

> **Target:** 3-5 YOE | **Goal:** Distributed systems ke core concepts — consensus, time, failures, consistency.

---

## Part 1: WHAT — Distributed System Kya?

### Definition

> **Distributed System** = multiple computers (nodes) jo **coordinate karke** ek single system jaisa behave karte hai.

### Characteristics

1. Multiple nodes
2. Connected by network
3. Coordinate via messages
4. No shared memory
5. No shared clock

### Real-Life Analogy 🍕

Soch ek **pizza delivery chain**:
- Multiple branches (nodes)
- Connected by phone (network)
- Coordinate orders (messages)
- Each branch has own kitchen (memory)
- Each branch has own clock

**Distributed bilkul waisa hi.**

---

## Part 2: WHY — Distributed Systems Kyu Use?

### Reason 1: Scale

Single computer limits.
Multiple = unlimited theoretically.

### Reason 2: Reliability

One fails → others continue.

### Reason 3: Geographic Distribution

Users worldwide → servers nearby.

### Reason 4: Performance

Parallel processing.

### Reason 5: Cost

Commodity hardware vs expensive single machine.

---

## Part 3: 8 FALLACIES OF DISTRIBUTED COMPUTING

### Originally by Peter Deutsch + others

> Common assumptions that turn out wrong:

### Fallacy 1: Network is Reliable

Reality: Networks fail constantly.

### Fallacy 2: Latency is Zero

Reality: Network calls slow.

### Fallacy 3: Bandwidth is Infinite

Reality: Limited bandwidth.

### Fallacy 4: Network is Secure

Reality: Always assume hostile.

### Fallacy 5: Topology Doesn't Change

Reality: Constant changes.

### Fallacy 6: There is One Administrator

Reality: Multiple admins, often.

### Fallacy 7: Transport Cost is Zero

Reality: Bandwidth costs money.

### Fallacy 8: Network is Homogeneous

Reality: Mixed environments.

### Bhai's Take

Every distributed bug = violating one of these.

---

## Part 4: CONSISTENCY MODELS

### Strong Consistency

> **All nodes see same data immediately.**

```
Write: X = 5 to Node 1
Read from Node 2: X = 5 (immediately)
```

Slowest. Safest.

### Eventual Consistency

> **All nodes will agree eventually.**

```
Write: X = 5 to Node 1
Read from Node 2: maybe X = 4 (old)
Wait 1 sec
Read from Node 2: X = 5
```

Fastest. Stale possible.

### Causal Consistency

> **Cause-effect order preserved.**

If A caused B, all see A before B.

### Read-Your-Writes

> **You see your own writes immediately.**

Others may not.

### Monotonic Reads

> **Subsequent reads don't go back in time.**

Once you read X = 5, never see X = 4 later.

---

## Part 5: CAP THEOREM (Recap)

### The Theorem

> Pick 2 of 3:
- Consistency
- Availability
- Partition Tolerance

### In Practice

> Choose CP or AP.
> CA only without partitions (impossible in distributed).

### Detailed: see CAP file in same folder.

---

## Part 6: PACELC THEOREM

### Extension of CAP

> **If Partition (P)**: choose Availability vs Consistency.
> **Else (E)**: choose Latency vs Consistency.

### Why Important

CAP only describes partition behavior.
PACELC includes normal operation.

### Database Examples

| Database | Partition | Normal |
|----------|-----------|--------|
| Cassandra | AP | EL |
| MongoDB | CP | EC |
| DynamoDB | AP | EL |

---

## Part 7: TIME IN DISTRIBUTED SYSTEMS

### Problem

> **No global clock.** Each node has own time.

### Issues

#### Clock Drift

Different nodes, different times.
Could be minutes off.

#### Ordering

"Which event happened first?"
Hard without shared clock.

### Solutions

#### NTP (Network Time Protocol)

> Sync to time servers.

Common. Not perfect (milliseconds off).

#### Logical Clocks

> Order events without real time.

##### Lamport Timestamps

```
Counter per node.
On send, increment, attach.
On receive, max(local, received) + 1.
```

Total ordering, but not causal.

##### Vector Clocks

```
Each node has counter for each node.
[A=5, B=3, C=2]
```

Captures causality.

#### Hybrid Logical Clocks (HLC)

> Combine physical + logical.

Used in: CockroachDB, MongoDB.

---

## Part 8: CONSENSUS

### What is Consensus?

> Multiple nodes **agree on a value** despite failures.

### Why Hard

- Network failures
- Node failures
- Partitions

### Use Cases

- Leader election
- Replicated state machines
- Distributed locks
- Coordination

### Algorithms

#### Paxos

> **Original consensus algorithm.** Complex.

Phases:
1. Prepare (propose number)
2. Promise (acceptors promise)
3. Accept (request commit)
4. Accepted (commit)

#### Raft

> **Simpler than Paxos.** Now more common.

Concepts:
- Leader-based
- Log replication
- Elections

Used by:
- Etcd
- Consul
- CockroachDB

#### ZAB (Zookeeper Atomic Broadcast)

> Used by Zookeeper.

---

## Part 9: REPLICATION

### Why Replicate

- High availability
- Read scaling
- Disaster recovery

### Replication Strategies

#### Single-Leader

```
WRITES → Leader
        ↓
    Replicas
        ↓
READS ← Replicas
```

Simple. Leader bottleneck.

#### Multi-Leader

```
WRITES → Multiple Leaders
        ↕ (sync between)
        Replicas
```

Higher throughput. Conflict resolution needed.

#### Leaderless

```
WRITES → Any Node
        ↕
READS ← Any Node (quorum)
```

Used by: Cassandra, DynamoDB.

### Synchronous vs Asynchronous

#### Sync
- Leader waits for replica ack
- Slow writes
- No data loss

#### Async
- Leader doesn't wait
- Fast writes
- Possible data loss

---

## Part 10: PARTITIONING (Sharding)

### Why Partition

- Data too big for one machine
- Spread load
- Geographic distribution

### Strategies

#### Range-Based

> Each partition holds range of keys.

```
A-G: Partition 1
H-N: Partition 2
O-T: Partition 3
U-Z: Partition 4
```

Hot spots possible.

#### Hash-Based

> Hash key → partition.

```
hash(key) % num_partitions
```

Even distribution. Range queries hard.

#### Consistent Hashing

> Hash to ring.
> Adding/removing partitions = minimal movement.

Used by: Cassandra, DynamoDB.

### See database scaling file for more.

---

## Part 11: FAILURE MODES

### Types

#### Crash Failure

> Node stops working.

Common. Detected by heartbeat.

#### Omission Failure

> Messages lost/dropped.

Network issue.

#### Timing Failure

> Too slow.

Performance issue.

#### Response Failure

> Wrong response.

Logic bug.

#### Byzantine Failure

> Arbitrary, malicious behavior.

Rarely considered (except blockchain).

### Detection

#### Heartbeats

> Periodic "I'm alive" messages.

Miss N → declare dead.

#### Phi Accrual Failure Detector

> Suspicion level vs binary alive/dead.

More nuanced.

---

## Part 12: HANDLING FAILURES

### Strategies

#### Retry

> Try again.

With:
- Exponential backoff
- Jitter
- Max attempts

#### Circuit Breaker

> Stop trying when failing.

States:
- Closed: normal
- Open: failing, don't try
- Half-open: testing if recovered

#### Bulkhead

> Isolate failures.

Resource pools per service.

#### Timeout

> Don't wait forever.

Critical for distributed.

#### Graceful Degradation

> Reduced functionality vs full failure.

"Search not available, but browse works."

---

## Part 13: DISTRIBUTED TRANSACTIONS

### Problem

> Need ACID across multiple services.

Hard in distributed.

### Solutions

#### Two-Phase Commit (2PC)

```
Phase 1: Prepare
  Coordinator: "Can you commit?"
  Participants: "Yes" or "No"

Phase 2: Commit
  If all yes: "Commit"
  If any no: "Abort"
```

#### Issues
- Blocking
- Single point of failure (coordinator)
- Slow

#### Saga Pattern

> Sequence of local transactions.

```
Step 1: Reserve inventory
Step 2: Charge card
Step 3: Confirm order

If failure: compensating actions
```

Eventually consistent.

#### Event-Driven

> Coordinate via events.

Less direct coordination.

---

## Part 14: IDEMPOTENCY

### What

> Operation can be safely repeated.

```
GET /user/123 → idempotent (no change)
POST /user → NOT idempotent (creates new)
PUT /user/123 → idempotent (replace)
DELETE /user/123 → idempotent (already gone)
```

### Why Critical

> Retries common in distributed.

Without idempotency: duplicate operations.

### Implementation

#### Idempotency Keys

```
Client generates UUID per operation.
Server tracks UUIDs.
Duplicate UUID = return previous result.
```

---

## Part 15: SERVICE DISCOVERY

### Problem

> Service A needs to call Service B.
> Service B's location changes (scaling, failure).

### Solutions

#### DNS

> Standard, simple.

Slow updates.

#### Service Registry

> Services register themselves.

Tools:
- Consul
- Etcd
- Zookeeper
- Eureka

#### Service Mesh

> Sidecar handles discovery.

Tools:
- Istio
- Linkerd

---

## Part 16: API GATEWAY

### Role

> Single entry point.

#### Functions
- Routing
- Authentication
- Rate limiting
- Logging
- Transformation

#### Tools
- Kong
- AWS API Gateway
- Nginx
- Envoy

---

## Part 17: EVENT-DRIVEN ARCHITECTURE

### Concept

> Services communicate via events.

```
Order Created → Event Bus → Multiple Subscribers
```

### Benefits

- Loose coupling
- Scalability
- Resilience

### Patterns

#### Event Sourcing
> Store events, not state.

#### CQRS
> Different paths for read/write.

#### Saga
> Distributed transactions.

---

## Part 18: GLOBAL DISTRIBUTION

### Multi-Region

```
USERS:
  US users → US datacenter
  EU users → EU datacenter
  Asia users → Asia datacenter
```

### Cross-Region Replication

- Sync vs async
- Consistency models
- Conflict resolution

### Geo-DNS

> DNS returns nearest IP.

### Anycast

> Same IP, multiple locations.

### CDN

> Edge servers for static content.

---

## Part 19: FAMOUS DISTRIBUTED SYSTEMS

### Google Spanner

> Globally distributed SQL.

- TrueTime API (atomic clocks)
- ACID across regions
- 5 9s availability

### Amazon DynamoDB

> NoSQL distributed.

- AP system
- Auto-scaling
- Multi-region

### Apache Kafka

> Distributed event streaming.

- Partitioned topics
- Replication
- High throughput

### Cassandra

> Distributed NoSQL.

- AP system
- Eventually consistent
- Linear scaling

---

## Part 20: COMMON PROBLEMS

### Split-Brain

> Two leaders due to partition.

#### Solution
- Quorum-based
- Fencing tokens

### Cascading Failures

> One service fails, takes others down.

#### Solution
- Circuit breakers
- Bulkheads
- Timeouts

### Hot Partitions

> Uneven load.

#### Solution
- Better partitioning
- Caching hot keys
- Rate limiting

### Clock Drift

> Different node times.

#### Solution
- NTP
- Logical clocks
- Tolerate clock skew

---

## Part 21: TESTING DISTRIBUTED SYSTEMS

### Chaos Engineering

> **Intentionally break things.**

Netflix Chaos Monkey:
- Kills random servers
- Tests resilience
- Reveals weaknesses

### Jepsen Testing

> Tests consistency under partitions.

Used by major distributed databases.

### Load Testing

> Simulate scale.

Tools: Locust, k6.

---

## Part 22: MEASURING DISTRIBUTED SYSTEMS

### Latency

- p50, p95, p99
- Tail latencies matter

### Availability

- 99.9%, 99.99%, 99.999%
- Each 9 = 10x harder

### Throughput

- Operations per second
- Sustained vs peak

### Consistency

- Read-your-writes
- Stale reads percentage
- Eventual consistency window

---

## Part 23: DESIGN PRINCIPLES

### 1. Embrace Failure

Failures will happen. Design for them.

### 2. Idempotent Operations

Retries safe.

### 3. Asynchronous When Possible

Don't block.

### 4. Eventual Consistency Default

Strong consistency expensive.

### 5. Statelessness

Easier to scale.

### 6. Cell-Based Architecture

Isolated failure domains.

### 7. Backpressure

Don't overwhelm downstream.

### 8. Monitoring First

Observability not optional.

---

## Part 24: REAL-WORLD CASE STUDIES

### Amazon Dynamo Paper

> Influential paper from Amazon.

Concepts:
- Consistent hashing
- Vector clocks
- Eventually consistent
- Sloppy quorum

Influenced: DynamoDB, Cassandra, Riak.

### Google's Bigtable

> Distributed wide-column.

Influenced: HBase, Cassandra.

### Google Spanner

> Globally distributed SQL.

TrueTime: atomic clocks for ordering.

---

## Part 25: Q&A

### Q: When need distributed?
**A**: When single machine insufficient (scale, reliability, geography).

### Q: Distributed systems hard?
**A**: Yes. Multiple components, partial failures, no global state.

### Q: Eventual consistency OK?
**A**: For most user-facing features, yes. For money, no.

### Q: How to test distributed?
**A**: Chaos engineering, Jepsen, load tests.

### Q: Best distributed DB?
**A**: Depends. Spanner for SQL global. DynamoDB for NoSQL. Cassandra for self-hosted.

### Q: Latency vs Consistency?
**A**: Real trade-off. Choose per use case.

### Q: Senior interview level?
**A**: Must know CAP, consensus basics, common patterns.

---

## 🎯 Bhai's Final Words

> **Distributed systems = engineering's hardest problem. Master these concepts → master systems at scale. Senior interviews focus heavily here.**

3 Mantras:
1. **Network unreliable** (always)
2. **Failures common** (design for)
3. **Eventual consistency OK** (often)

After understanding distributed systems deeply, FAANG interviews become tractable. 🚀
