# 🎯 CAP Theorem — System Design Foundation

> **Target:** 3-5 YOE | **Goal:** Distributed systems ka foundational theorem — Consistency, Availability, Partition tolerance.

---

## Part 1: WHAT — CAP Theorem Kya Hai?

### Definition

> **CAP Theorem** kehta hai: **distributed system me sirf 2 properties same time pe possible hai** out of 3:
- **C**onsistency
- **A**vailability  
- **P**artition Tolerance

### Origin

> **Eric Brewer** ne 2000 me propose kiya. **Seth Gilbert + Nancy Lynch** ne 2002 me formally proved kiya.

### Real-Life Analogy 📞

Soch tu **3 dosto se call karta hai** ek saath:
- Ek bole "haan" (consistency)
- Ek bole "hamesha available" (availability)  
- Ek bole "network down ho to bhi kaam ho" (partition tolerance)

**Sab nahi mil sakte ek saath. 2 select karne padenge.**

---

## Part 2: WHY — CAP Important Kyu?

### Reason 1: Foundation of Distributed Systems

Without CAP, every distributed system design wrong.

### Reason 2: Trade-off Awareness

Every database, every system makes CAP trade-off.
Senior engineer samajhta hai trade-off.

### Reason 3: Right Tool Selection

- MongoDB? PostgreSQL? Cassandra?
- Each has different CAP profile

### Reason 4: Interview Must-Know

Senior interview: "Explain CAP theorem." **Mandatory.**

---

## Part 3: 3 PROPERTIES EXPLAINED

### C — Consistency

> **Sab nodes same data dikhayein at any moment.**

#### Strong Consistency Example

```
Write to Node 1: User name = "Bhai"
Read from Node 2: User name = "Bhai"
(Immediately, after write)
```

#### Real Example

Bank account balance.
Always shows latest.

### A — Availability

> **Every request gets a response** (success/failure), without error.

#### Example

```
1000 servers, 999 down
Last server can still respond:
"Yes, here's data" or "Yes, your write succeeded"
```

#### Real Example

Twitter timeline.
Even if some servers down, you still see posts.

### P — Partition Tolerance

> **Network partitions ke baad bhi system kaam karta hai.**

#### Network Partition Kya Hai?

```
Datacenter US ←-X-→ Datacenter EU
Network down between them.

Each side can't talk to other.
```

#### System Choice

- Keep working (give up consistency or availability)
- Stop working (give up partition tolerance)

#### Real Example

Cross-region database.
Network failures common.
Must handle.

---

## Part 4: HOW — Why 3 Not Possible Together

### The Proof Intuition

```
NORMAL OPERATION:
Node A ←→ Node B
Both can communicate. CA possible.

NETWORK PARTITION:
Node A ✗ Node B (can't reach)

User writes to A: "Update X to 5"
What does A do?

Option 1: Wait for B (Consistency)
   → A becomes UNAVAILABLE
   → CP system

Option 2: Accept write (Availability)
   → A and B inconsistent
   → AP system

CANNOT have both during partition!
```

### Real-World Reality

> **Partitions WILL happen.** Network is unreliable.

So real choice:
- CP (Consistency over Availability)
- AP (Availability over Consistency)
- CA (rarely chosen — only works in non-distributed)

---

## Part 5: CP SYSTEMS (Consistency + Partition Tolerance)

### Behavior During Partition

> **Becomes unavailable** rather than serve stale data.

### Examples

#### Databases
- MongoDB (default settings)
- HBase
- Redis Cluster
- Etcd
- Zookeeper

### Use Cases

#### Banking
> Cannot show wrong balance.
> Better to be down than incorrect.

#### Inventory
> Cannot oversell.
> Stop selling than wrong count.

#### Identity / Authentication
> User must be authenticated correctly.

### Trade-off

- **Reliable data** ✓
- **Sometimes unavailable** ✗

### When to Choose

- Money involved
- Critical business logic
- User can wait

---

## Part 6: AP SYSTEMS (Availability + Partition Tolerance)

### Behavior During Partition

> **Stays available** but may serve stale data temporarily.

### Examples

#### Databases
- Cassandra
- CouchDB
- DynamoDB
- Riak

### Use Cases

#### Social Media
> Twitter shows old tweets, fine.
> Site down = bad.

#### Shopping Cart
> Always allow adding to cart.
> Sync later.

#### Like Counts
> "5,234 likes" vs "5,235 likes" — doesn't matter.

#### Logging / Analytics
> Stale by seconds is fine.

### Trade-off

- **Always responding** ✓
- **Maybe stale data** ✗

### When to Choose

- User experience priority
- Eventual consistency OK
- Scale critical

---

## Part 7: CA SYSTEMS (Consistency + Availability)

### Reality Check

> **Cannot exist in distributed systems with partitions.**

### When Exists

- Single-node systems
- Tightly coupled (one rack, one DC)
- Ignoring partitions (risky)

### Examples

- Traditional RDBMS (single server)
- Distributed monolith (sort of)

### Why Rare

In real distributed:
- Partitions WILL happen
- Must choose CP or AP

---

## Part 8: EVENTUAL CONSISTENCY

### What It Is

> **AP system** — temporarily inconsistent, but **eventually all nodes converge** to same state.

### Mental Model

```
Time 0: All nodes have "X = 5"
Time 1: Write "X = 7" to Node A
Time 2: Node A = 7, Node B = 5 (inconsistent)
Time 3: Replication catches up
Time 4: Node A = 7, Node B = 7 (consistent)
```

### Used In

- Cassandra
- DynamoDB
- DNS
- Email systems

### When OK

- User can tolerate slight delay
- Read-heavy workloads
- Globally distributed

---

## Part 9: PACELC THEOREM (Extension)

### Beyond CAP

> **PACELC** = if partition (P), trade off A vs C. Else (E), trade off Latency (L) vs Consistency (C).

```
During Partition:
  Availability ← → Consistency

Normal Operation:
  Latency ← → Consistency
```

### Why Important

CAP only describes partition behavior.
PACELC includes normal operation.

### Examples

| Database | Partition | Normal |
|----------|-----------|--------|
| Cassandra | AP | EL (fast over consistent) |
| MongoDB | CP | EC (consistent over fast) |
| DynamoDB | AP | EL |

---

## Part 10: CONSISTENCY MODELS

### Strong Consistency

> **Same data everywhere immediately.**

```
Write → All replicas updated
Read → Always latest
```

Slowest, safest.

### Linearizable

> **Strong consistency + real-time ordering.**

Most strict. Performance hit.

### Sequential Consistency

> **Order preserved, not real-time.**

All clients see same order.

### Eventual Consistency

> **Convergence over time.**

Fastest, weakest.

### Causal Consistency

> **Cause-effect preserved.**

If A caused B, all see A before B.
Other order unspecified.

---

## Part 11: AVAILABILITY LEVELS

### 99% (Two Nines)

```
Downtime allowed:
- Per day: 14.4 minutes
- Per year: 87.6 hours
```

Acceptable for: prototypes, internal tools

### 99.9% (Three Nines)

```
Downtime:
- Per day: 1.44 minutes
- Per year: 8.76 hours
```

Standard for: most SaaS apps

### 99.99% (Four Nines)

```
Downtime:
- Per day: 8.6 seconds
- Per year: 52.6 minutes
```

For: critical business apps

### 99.999% (Five Nines)

```
Downtime:
- Per day: 0.86 seconds
- Per year: 5.26 minutes
```

For: telecom, finance critical

### Cost vs Availability

Each extra 9 = ~10x cost.
Don't over-engineer.

---

## Part 12: PARTITION SCENARIOS

### Network Partition Types

#### 1. Complete Partition

```
DC East ─X─ DC West
No communication.
```

#### 2. Asymmetric

```
DC East → DC West (works)
DC East ← DC West (broken)
```

#### 3. Intermittent

```
On for 5 sec, off for 5 sec, on for 5 sec...
```

#### 4. Slow

```
Communication works but very slow.
(Almost a partition.)
```

---

## Part 13: REAL-WORLD CHOICES

### MongoDB

Default: CP
- Single primary writes
- Secondaries read replicas
- Sometimes unavailable during election

### Cassandra

AP
- Multiple masters
- Eventual consistency
- Always writes succeed

### PostgreSQL (Single-Master)

CA (in single region)
- Not partition tolerant
- Single point of failure

### PostgreSQL (Multi-Master)

CP or AP
- Configured per setup

### Redis Cluster

AP-leaning (not strongly consistent)
- Async replication shards ke beech → failover pe acked writes lost ho sakte hain
- Har shard independently available; cross-slot ops limited

---

## Part 14: DESIGNING FOR CAP

### Step 1: Identify Requirements

#### Consistency Need
> How critical is latest data?

#### Availability Need
> How critical is always responding?

### Step 2: Pick CP or AP

#### CP If
- Financial transactions
- Inventory
- Critical state

#### AP If
- Social feeds
- Comments
- Analytics
- Status updates

### Step 3: Choose Tools

#### CP Tools
- PostgreSQL with replication
- MongoDB
- HBase
- Redis Cluster

#### AP Tools
- Cassandra
- DynamoDB
- CouchDB
- Riak

### Step 4: Design Application

#### Handle Inconsistency
- Conflict resolution
- Last-write-wins
- Vector clocks
- CRDTs

#### Handle Unavailability
- Retries
- Cached responses
- Graceful degradation
- Fallbacks

---

## Part 15: COMMON MISCONCEPTIONS

### Misconception 1: "Pick CA"

Reality: Real distributed systems must pick CP or AP.
"CA" doesn't apply to distributed.

### Misconception 2: "Always Strong Consistency"

Reality: Many use cases work fine with eventual.

### Misconception 3: "AP Means Inconsistent"

Reality: Means eventually consistent.

### Misconception 4: "P is Optional"

Reality: In distributed, P is non-negotiable.

### Misconception 5: "Modern DBs Solved CAP"

Reality: Trade-offs still exist. They're just hidden better.

---

## Part 16: BEYOND CAP

### Beyond Trade-offs

Modern systems give choices:
- Per-request consistency level
- Read your writes
- Bounded staleness

### Example: DynamoDB

```
Eventually Consistent: cheap, fast (default)
Strongly Consistent: 2x cost, slower
```

User picks per query.

### Multi-Region

```
Same DB, multiple regions.
Each region can be CP or AP locally.
Cross-region eventually consistent.
```

---

## Part 17: APPLICATION-LEVEL HANDLING

### Strategies for AP Systems

#### Read Repair
> Detect inconsistency on read, fix it.

#### Hinted Handoff
> Save writes for offline nodes, replay later.

#### Anti-Entropy
> Periodically compare nodes, fix differences.

### Strategies for CP Systems

#### Failover
> Promote replica when primary fails.

#### Circuit Breaker
> Stop trying when DB unavailable.

#### Graceful Degradation
> Read-only mode.

---

## Part 18: CAP IN MICROSERVICES

### Each Service Independent

```
User Service: CP (auth critical)
Cart Service: AP (always allow)
Notification Service: AP (eventually deliver)
Payment Service: CP (must be correct)
```

### Cross-Service

Different services, different choices.
Sagas for coordination.

---

## Part 19: TESTING CAP BEHAVIORS

### Tools

#### Chaos Engineering
> Intentionally break network.

- Netflix Chaos Monkey
- Jepsen testing
- AWS Fault Injection

### What to Test

- Network partition behavior
- Failover speed
- Data consistency after recovery
- Application graceful degradation

---

## Part 20: CAP DECISION FRAMEWORK

### Decision Tree

```
Is this a distributed system?
├─ No → CA is possible
└─ Yes → Must choose P

  During partition, what's worse?
  ├─ Wrong data → Pick CP
  └─ No data → Pick AP

  Can users tolerate eventual consistency?
  ├─ Yes → AP friendlier
  └─ No → CP needed
```

### Bhai's Rule

Default: **AP for user-facing, CP for money.**

Adjust based on specifics.

---

## Part 21: PRACTICAL EXAMPLES

### Example 1: E-Commerce Cart

#### Choice: AP
- Always allow adding (UX critical)
- Resolve conflicts at checkout
- Eventual consistency OK

### Example 2: Stock Trading

#### Choice: CP
- Cannot show wrong prices
- Cannot oversell
- Must be down rather than incorrect

### Example 3: Social Feed

#### Choice: AP
- Always show feed
- New posts may take time
- Network issues common

### Example 4: Bank Account

#### Choice: CP
- Must be accurate
- ACID transactions
- Down better than wrong

### Example 5: Game Leaderboard

#### Choice: AP
- Slightly stale OK
- Always responsive
- Eventually consistent

---

## Part 22: COMMON INTERVIEW QUESTIONS

### Q: Explain CAP theorem.
**A**: Distributed system pick 2 of 3: Consistency, Availability, Partition Tolerance.

### Q: Difference CP vs AP?
**A**: CP sacrifices availability for consistency during partition. AP sacrifices consistency for availability.

### Q: Can we have all 3?
**A**: Not in real distributed. Only single-node or no partitions (theoretical).

### Q: Why CA system bad?
**A**: Cannot handle partitions, which will happen. Single point of failure.

### Q: Cassandra vs MongoDB?
**A**: Cassandra AP (always available, eventual consistency). MongoDB CP (consistent, sometimes unavailable).

### Q: How to handle eventual consistency in app?
**A**: Conflict resolution, retries, idempotent operations, user expectations.

### Q: When AP appropriate?
**A**: User-facing reads, social features, non-critical writes.

### Q: When CP appropriate?
**A**: Money, inventory, critical state.

### Q: PACELC vs CAP?
**A**: PACELC adds normal operation trade-off (Latency vs Consistency).

---

## 🎯 Bhai's Final Words

> **CAP theorem distributed systems ki ABCD hai. Senior engineer ko byheart hona chahiye. Database choice se microservices design tak — sab CAP pe based hai.**

3 Mantras:
1. **P is non-negotiable** (in distributed)
2. **AP for UX, CP for correctness**
3. **Eventual consistency is OK** (often)

After understanding CAP deeply, you'll design systems consciously. Better choices, fewer surprises. 🚀
