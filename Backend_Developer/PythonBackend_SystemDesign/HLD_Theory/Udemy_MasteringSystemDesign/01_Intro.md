# 01 — Introduction to System Design

## What is system design?

System design is the process of defining the **architecture, components, modules, interfaces, and data flow** of a system to satisfy specified requirements. In an interview context, it usually means *High-Level Design (HLD)* — drawing the box-and-arrow diagram of a large-scale distributed system (e.g., "design Twitter," "design a URL shortener").

It sits **above LLD** (class/object design, design patterns) and **below product design** (UX, business strategy).

## Why it matters

- **Production reality:** Modern apps serve millions of users; bad architecture causes outages and slow product velocity.
- **Hiring signal:** Mid/senior engineering interviews use HLD as the primary differentiator. Coding shows you can *implement*; system design shows you can *decide*.
- **Communication:** Forces you to articulate tradeoffs — the core skill of a senior engineer.

## Functional vs Non-Functional Requirements

| Type | Definition | Examples |
|------|-----------|----------|
| **Functional (FR)** | What the system *does* | "Users can post tweets", "search returns results sorted by relevance" |
| **Non-Functional (NFR)** | *How well* it does it | Latency < 200ms p99, 99.99% availability, 1M QPS, GDPR-compliant |

**Rule of thumb:** clarify FRs first (5 min), then NFRs (3 min). NFRs drive almost every architectural decision (caching, sharding, replication).

### Common NFRs to ask about

- **Scale:** DAU, peak QPS, read/write ratio, storage growth/year
- **Latency:** target p50, p95, p99
- **Availability:** how many 9's? (99.9 → 8.76h downtime/year, 99.99 → 52min, 99.999 → 5min)
- **Consistency:** strong, eventual, causal?
- **Durability:** can we afford to lose data on a node failure?
- **Geographic:** single region, multi-region active-passive, active-active?

## The interview framework (RADIO / 4S)

Most senior engineers use a variant of this 7-step flow:

1. **Requirements** — clarify FR + NFR (5 min). Don't skip; you'll regret it later.
2. **Estimation** — back-of-envelope: QPS, storage, bandwidth (3–5 min).
3. **API design** — list endpoints + request/response shapes (3 min).
4. **Data model** — entities, relationships, choice of SQL vs NoSQL (5 min).
5. **High-level architecture** — draw the boxes: clients, LB, services, DB, cache, queue (10 min).
6. **Deep dive** — interviewer picks 1–2 components; discuss internals, scaling, failure modes (15 min).
7. **Wrap-up** — bottlenecks, future improvements, monitoring (3 min).

## Back-of-envelope estimation cheatsheet

### Powers of 2 / 10

| Power of 10 | Name | Power of 2 (≈) |
|-------------|------|----------------|
| 10³ | thousand (K) | 2¹⁰ = 1,024 |
| 10⁶ | million (M) | 2²⁰ |
| 10⁹ | billion (B) | 2³⁰ |
| 10¹² | trillion (T) | 2⁴⁰ |

### Latency numbers every engineer should know

| Operation | Latency |
|-----------|---------|
| L1 cache reference | 0.5 ns |
| L2 cache reference | 7 ns |
| Main memory reference | 100 ns |
| Compress 1 KB with Zippy | 10 µs |
| Send 1 KB over 1 Gbps network | 10 µs |
| SSD random read | 150 µs |
| Read 1 MB sequentially from memory | 250 µs |
| Round trip within same datacenter | 500 µs |
| Read 1 MB sequentially from SSD | 1 ms |
| Disk seek (HDD) | 10 ms |
| Read 1 MB sequentially from disk | 30 ms |
| Round trip CA → Netherlands → CA | 150 ms |

**Memorize the ratios:** memory ~100× faster than SSD, SSD ~100× faster than HDD seek, intra-DC ~300× faster than cross-continent.

### Estimation workflow

For "design Twitter":

```
DAU                 = 200M
Tweets/user/day     = 2
Total tweets/day    = 400M
Tweets/sec (avg)    = 400M / 86,400 ≈ 4,600 QPS write
Peak QPS (3× avg)   ≈ 14,000 QPS

Read/write ratio    = 100:1 (timelines viewed >> tweets posted)
Read QPS (peak)     ≈ 1.4M QPS

Storage:
  Avg tweet size    = 300 bytes (text) + 10 KB (media, 10% of tweets)
  Daily storage     = 400M × 300B + 40M × 10KB = 120 GB + 400 GB ≈ 520 GB/day
  10-year storage   ≈ 520 GB × 365 × 10 ≈ 1.9 PB
```

## Deliverables of a good HLD

A solid design produces:

- **Box diagram** with: clients, CDN, LB, API gateway, services, DBs, cache, queues, search index
- **API spec** — REST/gRPC endpoints, sample payloads
- **Data schema** — tables/collections with key fields, indexes, partition strategy
- **Capacity plan** — # of servers, storage size, bandwidth
- **Failure modes** — what happens if a DB primary dies, network partition, region outage
- **Bottlenecks** — current limits and how you'd scale past them

## Common interview anti-patterns

1. **Jumping to solutions before clarifying scope.** Spending 25 minutes designing for 100M users when interviewer wanted 10K.
2. **Buzzword bingo.** Saying "Kafka, Redis, Cassandra, Kubernetes" without justifying why.
3. **Ignoring NFRs.** Designing for consistency when interviewer signaled high availability.
4. **No estimation.** Picking a database without knowing if data is 1GB or 1PB.
5. **Single point of failure.** Drawing one DB, one LB, no replication.
6. **Premature optimization.** Sharding from day 1 for 10K QPS.
7. **Silence.** Interviewer can't grade what you don't say. Think aloud.

## Interview Q&A

**Q1: What's the difference between system design and software architecture?**
*A:* They overlap. System design is broader and outcome-driven (will this system meet the SLA?). Software architecture focuses on internal structure (layers, modules, patterns) of a single application. HLD interviews lean toward system design; LLD interviews lean toward software architecture.

**Q2: How do you handle ambiguous requirements in an interview?**
*A:* Make explicit assumptions and state them. "I'll assume 10M DAU, read-heavy workload (100:1), eventual consistency is acceptable for non-critical paths. Should I adjust?" This gives the interviewer a chance to redirect.

**Q3: When would you choose strong consistency over availability?**
*A:* Anything where stale data causes correctness bugs: financial transactions, inventory (don't oversell), unique username assignment, leader election. Choose eventual for: timelines, view counts, recommendations, anything where "good enough soon" is fine.

**Q4: A user reports the app feels slow. How do you investigate?**
*A:* Drill into the request path: client → DNS → CDN → LB → service → DB → cache. Look at p95/p99 latency at each hop. Common culprits: cold cache, slow query (missing index), N+1 query, GC pause, downstream service degradation, network egress to another region.

**Q5: What's the order of magnitude difference between RAM and disk?**
*A:* RAM access ~100 ns, SSD random read ~150 µs (1,500× slower), HDD seek ~10 ms (100,000× slower than RAM). This is why caching exists and why hot data must live in memory.

## Further reading

- "Numbers Every Programmer Should Know" — Jeff Dean
- Donella Meadows, *Thinking in Systems* (mental models)
- Existing notes: `../03_Web_Server.md`, `../04_Latency.md`, `../05_Throughput.md`
