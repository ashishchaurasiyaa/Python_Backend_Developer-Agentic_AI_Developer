# 02 — Scalability

## Definition

**Scalability** is a system's ability to handle increasing load *without proportional cost or complexity increases*. A scalable system stays performant when traffic, data, or feature complexity grows.

Three things scale independently:
1. **Traffic** — more requests per second
2. **Data** — more bytes stored / queried
3. **Operational complexity** — more services, more developers, more deploys

A "scalable architecture" must address all three.

## Vertical vs Horizontal Scaling

| | Vertical (Scale Up) | Horizontal (Scale Out) |
|---|---------------------|------------------------|
| **What** | Bigger machine (more CPU, RAM) | More machines |
| **Limit** | Hardware ceiling | Effectively unlimited |
| **Failure** | SPOF | Tolerant if stateless |
| **Cost** | Super-linear (high-end HW expensive) | Linear (commodity HW) |
| **Complexity** | Trivial — no code change | Hard — needs load balancing, distributed state, consensus |
| **Downtime** | Reboot required | Rolling deploy possible |
| **When to use** | DB primary, small services with low load | Stateless web tier, microservices |

**Modern default:** scale horizontally for stateless tiers (web/API); use vertical scaling sparingly for stateful systems (master DB) and shift to horizontal-scaled stateful (sharding, replicas) when forced.

## The AKF Scale Cube

A model of three independent scaling axes:

- **X-axis (horizontal duplication):** clone the service behind a load balancer. Easy, but each clone hits the same DB.
- **Y-axis (functional decomposition):** split by feature — auth service, payment service, search service. This is *microservices*.
- **Z-axis (data partitioning / sharding):** split by data — users A–M on shard 1, N–Z on shard 2. This is *sharding*.

A mature system uses all three: many copies of each microservice (X), each owning a domain (Y), with data sharded across many DBs (Z).

## Stateless vs Stateful

- **Stateless** services hold no per-request memory between calls. Any instance can serve any request. Trivial to horizontally scale — just add more.
- **Stateful** services hold session state, cache, or own data. Scaling requires sticky sessions, replication, or partitioning.

**Rule:** push state to the edges (cache, DB, queue). Keep compute stateless. The web tier should be a "cattle, not pets" farm.

### Where state legitimately lives

- **Client side:** auth tokens, UI state
- **Distributed cache:** session data (Redis), so any backend can read it
- **Database:** the canonical truth
- **Message queue:** in-flight work
- **Search index:** queryable derived data

## CAP Theorem

In any distributed data store, you can only guarantee **two of three** in the presence of a network partition:

- **C (Consistency)** — every read returns the most recent write or an error
- **A (Availability)** — every request gets a non-error response (not necessarily the latest)
- **P (Partition tolerance)** — the system continues despite network drops between nodes

Because partitions are inevitable in a distributed system (P is non-negotiable), the *real* choice is **CP vs AP**.

| Choice | Behavior under partition | Examples |
|--------|--------------------------|----------|
| **CP** | Refuse some requests to preserve consistency | HBase, MongoDB (default), ZooKeeper, etcd, Spanner |
| **AP** | Serve possibly-stale data, reconcile later | DynamoDB, Cassandra, Riak, Couchbase |

**Common misconception:** CAP doesn't mean "always pick 2." Outside of partitions, you usually get all three. CAP is only invoked *during* a partition.

## PACELC — the better model

Daniel Abadi's refinement: even *without* a partition, every distributed system trades **L**atency vs **C**onsistency.

```
If Partition: choose Availability OR Consistency
Else: choose Latency OR Consistency
```

| System | P → | E → |
|--------|-----|-----|
| Spanner | C | C (synchronous global commit) |
| Cassandra | A | L (tunable consistency, fast reads) |
| MongoDB | C | C (default), L (with readPreference) |
| DynamoDB | A | L (eventual consistency by default) |

## Consistency Models (from strongest to weakest)

1. **Linearizable / Strong** — operations appear instantaneous in a global order. Real time semantics. Example: Spanner, ZooKeeper.
2. **Sequential** — all clients see the same order, but not necessarily real-time.
3. **Causal** — operations causally related (one happens-before another) are seen in order; concurrent operations may be seen in different orders.
4. **Read-your-writes** — a client always sees its own writes (but other clients may not yet).
5. **Monotonic reads** — once you see a value, you won't see an older one.
6. **Eventual** — given enough time and no new writes, all replicas converge.

**Stronger consistency costs latency and availability.** Pick the weakest model that satisfies correctness.

## Latency vs Throughput

- **Latency** — time per request (e.g., 50ms p99)
- **Throughput** — requests per second the system handles (e.g., 10K QPS)

These are *related but distinct*. Adding parallelism can raise throughput without lowering latency. Lowering latency (better algorithm, caching) usually raises throughput too.

**Little's Law:** `L = λW` where L = concurrent requests in system, λ = arrival rate (QPS), W = average latency. Useful for capacity planning.

> Example: target 1000 QPS, each request takes 50ms → need to handle 50 concurrent requests. With 1 server doing 100 concurrent, you have 2× headroom.

## Bottleneck Patterns and Fixes

| Bottleneck | Symptom | Fix |
|------------|---------|-----|
| CPU-bound service | High CPU, slow response | Horizontal scale, optimize hot path, async I/O |
| Memory pressure | OOM kills, GC pauses | Vertical scale, off-heap cache, leak audit |
| DB connection pool exhaustion | Connection timeouts | Connection pooling (pgbouncer), shorter txns, read replicas |
| Slow query | One query at 5s, rest at 5ms | Index, denormalize, materialized view, query rewrite |
| N+1 query | DB CPU pegged | Batch, JOIN, eager loading |
| Single hot key | One shard overloaded | Add randomization, split key, write-through cache |
| Network egress | Throttled by cloud provider | Compression, regional caches, CDN, reduce payload |

## Capacity Planning Worksheet

```
1. Estimate peak QPS (3-5× average for spiky workloads)
2. Estimate per-request CPU/mem/IO cost from benchmarks
3. Pick a target utilization (60-70% to leave headroom)
4. Required capacity = Peak QPS × cost / target_util
5. Apply replication factor (×2-3 for HA)
6. Add 20-30% buffer for traffic surprises
```

## Availability Math

Series components multiply: `A_total = A_1 × A_2 × ... × A_n`

> LB (99.99%) → API (99.95%) → DB (99.99%) → total = 99.93% ≈ 6h downtime/yr

Redundant (parallel) components reduce failure: `1 - (1-A)^n`

> Two DBs at 99.9% each → 99.9999% combined (assuming independent failures — rarely truly independent in practice)

## Interview Q&A

**Q1: Your service is at 80% CPU with 2× headroom. Traffic is forecast to 4× in 6 months. What do you do?**
*A:* First, profile — confirm where CPU goes. If genuine compute, plan horizontal scale (4× pods/instances). Verify the downstream DB and cache can handle 4× too (often the actual bottleneck). Load test before peak. Add autoscaling for spikes.

**Q2: When does vertical scaling beat horizontal?**
*A:* Single-writer stateful workloads where consensus overhead dominates (DB primary, in-memory store). Also low-traffic services where managing N pods is more overhead than running one bigger one. Most modern systems still scale the stateful tier vertically until forced to shard.

**Q3: Pick a DB for a global social network. Justify CAP choice.**
*A:* AP system (Cassandra/DynamoDB) for the timeline and feed — users prefer slightly stale content over an error. CP system (Spanner or sharded Postgres) for billing/payments. Different services, different tradeoffs.

**Q4: What does "stateless" actually mean for a service that has an in-memory cache?**
*A:* Stateless w.r.t. user requests — any instance can serve any request without coordinating with other instances. Local cache is fine as a performance optimization (you tolerate cache miss). It becomes problematic if correctness depends on the cache (e.g., dedupe within a window). Then you need a shared cache (Redis).

**Q5: Explain "eventual consistency" to a non-technical PM.**
*A:* When you post a photo, your friend in Australia may not see it for 200ms. The system promises everyone *eventually* sees the same thing, but not at the exact same instant. It's how we get 10× the speed and reliability — by accepting tiny windows of disagreement.

**Q6: What's the difference between consistency in CAP vs ACID?**
*A:* Completely different. ACID consistency means "transactions preserve invariants" (e.g., debits = credits). CAP consistency means "all nodes see the same data at the same time" (linearizability). A NoSQL store can be ACID-consistent but CAP-eventual.

## Further reading

- Existing notes: `../06_Availability.md`, `../07_Consistency_Strong_vs_Eventual.md`, `../08_CAP_Theorem.md`, `../10_Horizontal_vs_Vertical_Scaling.md`
- *DDIA* — Ch 5 (Replication), Ch 9 (Consistency & Consensus)
- "PACELC" — Daniel Abadi
