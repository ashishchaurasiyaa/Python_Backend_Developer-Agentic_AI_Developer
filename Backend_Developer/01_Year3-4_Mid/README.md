# Backend Developer — Mid Level (Year 3–4)

This section covers the skills and knowledge expected of a mid-level backend engineer: advanced Python internals, production-grade API design, security, distributed systems, and the professional habits that separate individual contributors from senior engineers.

**Most topics pair theory `.md` files with a `practical/` directory of runnable `.py` exercises** (14_Engineering_Practices is deliberately theory + a written lab — those are judgment skills, not code). Several topics additionally ship **TODO-stub labs with real infrastructure** — that is where the actual learning happens:

| Topic | Hands-on | What you spin up |
|---|---|---|
| [04_DevOps](04_DevOps/labs/) | 4 labs | Docker builds, nginx proxy, Prometheus/PromQL, health gates |
| [06_gRPC](06_gRPC/labs/) | 4 labs | Real `.proto` + generated stubs (unary, streaming, deadlines) |
| [07_Kafka](07_Kafka/labs/) | 6 labs | `docker-compose` Kafka (+ Schema Registry via the `docker-compose.schema-registry.yml` overlay for lab 6) |
| [08_RabbitMQ](08_RabbitMQ/exercises/) | 5 exercises | `docker-compose` + per-exercise `verify.py` self-check |
| [09_Celery](09_Celery/labs/) | 4 labs | `docker-compose` broker + workers |
| [10_MongoDB](10_MongoDB/practical/) · [11_Elasticsearch](11_Elasticsearch/practical/) | compose files | Replica set / ES cluster |
| [14_Engineering_Practices](14_Engineering_Practices/labs/) | 1 written sim | Incident-triage scenario |
| [01_Python_Advanced](01_Python_Advanced/) | 30-file drill set | `Interview_Handson_Practice/00_INDEX.py` menu |

---

## Topic Index

| # | Folder | Description |
|---|--------|-------------|
| 01 | `01_Python_Advanced` | Pydantic v2, ABC/Protocols, memory model, GIL, async concurrency, and advanced type annotations. |
| 02 | `02_API_Design` | REST best practices, versioning, rate limiting, CORS, OpenAPI, HATEOAS, BFF pattern, HTTP/3, and async API patterns. |
| 03 | `03_Security` | JWT/OAuth2/RBAC, OWASP Top 10, CSRF, 2FA, cryptography, secrets management, zero-trust, GDPR/DPDP compliance, WAF, and penetration testing. |
| 04 | `04_DevOps` | Docker, Nginx, GitHub Actions CI/CD, AWS (EC2/S3/RDS), Kubernetes/Helm, Terraform, Prometheus/Grafana, ELK/Loki, GitOps (ArgoCD/Flux), and SRE practices. |
| 05 | `05_Microservices` | Service decomposition patterns, API gateway, event sourcing, CQRS, outbox pattern, service mesh (Istio/Linkerd), DDD, and distributed systems theory. |
| 06 | `06_gRPC` | Protocol Buffers, unary and streaming RPCs, mTLS security, retry/resilience strategies, observability, performance tuning, and gRPC-Web. |
| 07 | `07_Kafka` | Kafka architecture, producers/consumers in Python, Kafka Streams, Kafka Connect, exactly-once semantics, production operations, and broker comparisons (NATS/Pulsar). |
| 08 | `08_RabbitMQ` | AMQP exchanges, dead-letter exchanges, TTL, priority queues, aiopika with FastAPI, quorum queues, federation/shovel, and retry/backoff patterns. |
| 09 | `09_Celery` | Task queues, beat scheduling, advanced patterns (chords/chains), Flower monitoring, Prometheus integration, priority queues, and AWS SQS as a broker. |
| 10 | `10_MongoDB` | CRUD with PyMongo, aggregation pipelines, indexes, Motor async driver with FastAPI, sharding, and multi-document transactions. |
| 11 | `11_Elasticsearch` | Index management, full-text search queries, aggregations, custom analyzers, FastAPI integration, ILM policies, and the ELK stack. |
| 12 | `12_GraphQL` | GraphQL fundamentals, Strawberry + FastAPI, DataLoader (N+1 fix), real-time subscriptions, schema federation, and security hardening. |
| 13 | `13_WebSocket_SSE` | WebSocket fundamentals, Server-Sent Events, scaling with Redis Pub/Sub, and deep-dive FastAPI WebSocket patterns. |
| 14 | `14_Engineering_Practices` | Code review skills, sprint planning/estimation, incident response runbooks, post-mortem writing, Architecture Decision Records (ADRs), and tech-debt management. |
| 15 | [`15_Design_Patterns_SOLID`](15_Design_Patterns_SOLID/README.md) | SOLID principles and 22 of the 23 GoF patterns in Python across creational/structural/behavioural sections (Interpreter is covered in the senior track's [LLD_Theory](../02_Year5%2B_Senior/01_System_Design/LLD_Theory/21_Interpreter_Pattern.md)), plus code smells and interview drills mapping each pattern to real backend use. |

---

## Suggested Learning Order

The order below minimises prerequisite gaps. Topics that share runtime dependencies (Kafka, RabbitMQ, Celery) are grouped so you can spin up infrastructure once.

```
1.  01_Python_Advanced          — solidify the language internals you will use everywhere
2.  02_API_Design               — build correct, production-ready HTTP/GraphQL APIs
3.  03_Security                 — harden those APIs before deploying anything
4.  04_DevOps                   — containerise, deploy, and observe your services
5.  05_Microservices            — decompose monoliths; understand distributed patterns
6.  07_Kafka                    — event streaming backbone for microservices
7.  08_RabbitMQ                 — task/work-queue messaging alternative to Kafka
8.  09_Celery                   — background-task processing on top of broker infrastructure
9.  06_gRPC                     — high-performance inter-service RPC (build on Microservices knowledge)
10. 10_MongoDB                  — document-store data layer for services that need flexible schemas
11. 11_Elasticsearch            — full-text search and observability indexing
12. 12_GraphQL                  — flexible query layer over existing services
13. 13_WebSocket_SSE            — real-time push patterns (builds on API Design + Redis from DevOps)
14. 15_Design_Patterns_SOLID    — SOLID + GoF patterns; makes code-review and LLD rounds much easier
15. 14_Engineering_Practices    — professional practices that apply across all prior topics
```

> **Tip:** Each topic is self-contained. If you are preparing for a specific interview or project, jump directly to the relevant folder. The `practical/` scripts in every topic can be run independently with minimal setup.

---

## Prerequisites

- Solid Python 3.10+ fundamentals (see [`../00_Year0-2_Junior/02_Python_Daily`](../00_Year0-2_Junior/02_Python_Daily/) if needed)
- Familiarity with relational databases and basic SQL
- Understanding of HTTP request/response cycle
