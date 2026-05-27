# Mastering System Design — Notes Index

Notes companion to the Udemy course *"Mastering System Design: From Basics to Cracking Interviews"*.

These notes are **independently written canonical references** organized to mirror the course outline. As you watch lectures, supplement each file with course-specific examples, instructor wording, or diagrams. The notes here cover what every system design interview expects you to know.

## Sections (matches Udemy course)

| # | File | Topic |
|---|------|-------|
| 01 | [01_Intro.md](./01_Intro.md) | What system design is, requirements, interview framework, estimation |
| 02 | [02_Scalability.md](./02_Scalability.md) | Vertical/horizontal scaling, CAP, PACELC, consistency models |
| 03 | [03_Databases.md](./03_Databases.md) | SQL vs NoSQL, replication, sharding, indexes, transactions |
| 04 | [04_Caching.md](./04_Caching.md) | Cache layers, write/read patterns, eviction, invalidation, Redis |
| 05 | [05_LoadBalancing.md](./05_LoadBalancing.md) | L4/L7, algorithms, health checks, consistent hashing, GSLB |
| 06 | [06_Messaging.md](./06_Messaging.md) | Queues vs streams, Kafka/RabbitMQ, delivery semantics, EDA |
| 07 | [07_Microservices.md](./07_Microservices.md) | Boundaries, gateway, discovery, saga, circuit breaker, tracing |
| 08 | [08_Performance.md](./08_Performance.md) | Latency, throughput, profiling, optimization patterns |
| 09 | [09_Reliability.md](./09_Reliability.md) | HA, fault tolerance, DR, backup, redundancy, "nines" |
| 10 | [10_Security.md](./10_Security.md) | Auth, encryption, OWASP, network security, compliance |
| 11 | **[11_Blueprint.md](./11_Blueprint.md)** | **The 6-step framework — most valuable for interviews** |

## How to use

1. **Watch a lecture → revisit the relevant section here.** Use these notes as the spine; add lecture-specific examples inline.
2. **Each file ends with interview Q&A.** Practice answering aloud before peeking at the answers.
3. **Cross-reference** the existing `HLD_Theory/*.md` files at the parent level — they cover overlapping territory in shorter, more focused chunks.

## Further reading

- *Designing Data-Intensive Applications* — Martin Kleppmann
- *System Design Interview* (Vol 1 & 2) — Alex Xu
- [github.com/donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer)
- Original papers: Dynamo, BigTable, Spanner, Kafka, Chubby, GFS
