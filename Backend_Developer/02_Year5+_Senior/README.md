# Backend Developer — Year 5+ Senior

This section targets engineers operating at the senior / principal level. The material assumes solid mid-level fluency and focuses on the three pillars that distinguish senior contributors: **System Design** (HLD + LLD), **Architecture Patterns**, and **Engineering Leadership**.

---

## Directory Overview

```
02_Year5+_Senior/
├── 01_System_Design/
│   ├── HLD_Theory/          # 58 topic notes — core theory for every HLD interview and design review
│   ├── HLD_Code/            # Runnable Django/Python implementations of key HLD concepts
│   ├── HLD_Problems/        # 40+ end-to-end system design walkthroughs (famous products + infrastructure)
│   ├── LLD_Theory/          # 27 notes covering GoF patterns, SOLID, OOP, concurrency, CQRS and more
│   ├── LLD_Problems/        # 21 structured class-design problems with model answers
│   └── Design_Patterns_Code/# 16 runnable Django projects, one per design pattern
├── 02_Architecture_Patterns/# 10 progressive sections from foundations to cloud-native
└── 03_Senior_Leadership/    # 10 files on hiring, strategy, FinOps, DORA metrics, mentorship
```

---

## 01\_System\_Design

### HLD\_Theory (58 topics)

Comprehensive theory notes numbered `01` through `58`. Topics progress from architectural foundations through distributed systems internals:

| Range | Theme |
|-------|-------|
| 01 – 10 | Architecture styles, web servers, latency, throughput, availability, consistency, CAP theorem, Lamport clocks, scaling |
| 11 – 20 | Redundancy, load balancers, caching, cache eviction, file storage, RDBMS scaling, NoSQL types, polyglot persistence, denormalization, database indexing |
| 21 – 30 | Sync vs async, message-based communication, protocols, authentication (Basic / Token / OAuth), proxies, ACID vs BASE, SLA/SLO/SLI |
| 31 – 40 | Back-of-envelope estimation, CDN, API Gateway, circuit breaker, service discovery, RBAC, observability, sharding, zero-downtime deployment, webhooks |
| 41 – 50 | Data pipelines, Bloom filters, geohashing, consistent hashing, Quad/KD trees, vector clocks + CRDTs, multi-tenancy, HTTP versions, TCP/UDP deep dive, DNS |
| 51 – 58 | Idempotency tokens, serialization, big-data / distributed processing, heartbeat & failure detection, stateful vs stateless, serverless, read-heavy vs write-heavy, data compression & deduplication |

### HLD\_Code (5 implementations)

Working Python/Django code for concepts that benefit from concrete implementation:

| Folder | Pattern |
|--------|---------|
| `01_cqrs_event_sourcing` | CQRS with event sourcing |
| `02_saga_orchestration` | Distributed saga / orchestration |
| `03_circuit_breaker` | Circuit breaker pattern |
| `04_rate_limiter` | Token-bucket / sliding-window rate limiter |
| `05_consistent_hashing` | Consistent hashing ring |

### HLD\_Problems (40 problems)

End-to-end design documents for real-world and interview-canonical systems. Grouped loosely below for orientation:

**Classic interview targets**
`URL_Shortener`, `Pastebin`, `Rate_Limiter`, `Notification_System`, `Payment_System`, `File_Storage_System`, `Task_Queue_Job_Scheduler`, `Ride_Booking_System`

**Consumer products**
`Design_YouTube`, `Design_Netflix`, `Design_Spotify`, `Design_Twitter_X`, `Design_Instagram_NewsFeed`, `Design_WhatsApp_Chat`, `Design_Slack`, `Design_Tinder`, `Design_Reddit`, `Design_Quora`

**Marketplaces and e-commerce**
`Design_Amazon_Ecommerce`, `Design_Airbnb`, `Design_eBay_Auction`, `Design_BookMyShow`, `Design_Uber_Maps`

**Search and data**
`Design_Search_Engine`, `Design_Search_Autocomplete`, `Design_Google_Maps`, `Design_Google_Docs`, `Design_Dropbox`, `Design_Web_Crawler`, `Design_Real_Time_Analytics`, `Design_Distributed_Cache`, `Design_Distributed_Logging`

**Infrastructure components**
`Design_API_Gateway`, `Design_AdServer`, `Design_Stock_Exchange`, `Design_Online_Code_Editor`

**AI / modern systems**
`Design_ChatGPT_Backend`, `Design_RAG_System`, `Design_Agent_Orchestration`, `Design_Multi_Tenant_SaaS`

### LLD\_Theory (27 notes)

| Note | Topic |
|------|-------|
| 01 – 09 | Singleton, Factory, Abstract Factory, Builder, Decorator, Adapter, Strategy, Observer, Template Method |
| 10 – 21 | UML class diagrams, Dependency Injection / Repository / State Machine, Prototype, Facade, Iterator, Mediator, Visitor, Chain of Responsibility, State, Memento, Bridge, Interpreter |
| Standalone | Command / Composite / Proxy / Flyweight, Concurrency & thread safety, Database design, Event Sourcing + CQRS, OOP fundamentals, SOLID principles, Resume-based LLD interview prep |

### LLD\_Problems (21 problems)

Structured class-design problems covering: `ATM_System`, `Booking_System`, `Elevator_System`, `File_Storage_System`, `Food_Delivery_System`, `LRU_Cache`, `Library_Management_System`, `Login_System`, `Notification_System`, `Online_Shopping_Cart`, `Parking_Lot_System`, `Payment_System`, `Rate_Limiter`, `Ride_Booking_System`, `Splitwise`, `Stock_Trading_System`, `Task_Queue_Job_Scheduler`, `Tic_Tac_Toe_Chess`, `URL_Shortener`, `Vending_Machine`, `Zoom_Video_Call`

### Design\_Patterns\_Code (16 Django projects)

Each folder is a self-contained Django project demonstrating the pattern in an enterprise/ERP context (SAP integrations, order events, document routing, etc.):

`01_singleton`, `02_factory`, `03_abstract_factory`, `04_observer`, `06_builder`, `09_template_method`, `11_command`, `12_repository`, `13_service_layer`, `14_dependency_injection`, `15_prototype`, `16_facade`, `17_iterator`, `18_mediator`, `19_visitor`, `20_chain_of_responsibility`

---

## 02\_Architecture\_Patterns

Ten sections that build from first principles to cloud-native decision-making. Each section contains theory notes plus practical hands-on exercises:

| Section | Theme |
|---------|-------|
| `Section_01_Foundations` | What is software architecture; architecture vs design vs code; quality attributes; roles; ADR and C4 documentation |
| `Section_02_Layered_Modular` | Layered architecture, modular monoliths, clean/hexagonal/onion architectures |
| `Section_03_Distributed_Systems` | Microservices, service mesh, distributed data management |
| `Section_04_Communication_Integration` | Synchronous (REST/gRPC), asynchronous (messaging, event streaming), API versioning |
| `Section_05_Security_Governance` | Zero-trust, OWASP, compliance, governance models |
| `Section_06_Event_Driven_Reactive` | Event-driven architecture, reactive systems, CQRS at the architecture level |
| `Section_07_Cloud_Native_Scalable` | Containers, Kubernetes, serverless, auto-scaling strategies |
| `Section_08_UI_Architecture_Patterns` | BFF (Backend For Frontend), micro-frontends, API contracts |
| `Section_09_Architectural_Decision_Making` | Trade-off analysis, ADR process, evaluating architectural fitness |
| `Section_10_Conclusion_Next_Steps` | Synthesis and career path for the architect role |

---

## 03\_Senior\_Leadership

Soft and strategic skills that separate senior engineers from principal / staff engineers:

| File | Topic |
|------|-------|
| `01_hiring_interviewing_skills.md` | Building a hiring bar; structured interviews; levelling candidates |
| `02_engineering_leadership.md` | Technical leadership without direct authority; influencing outcomes |
| `03_cost_optimization_finops.md` | Cloud cost governance, FinOps practices, rightsizing |
| `04_vendor_evaluation_framework.md` | Build vs buy decisions; vendor scoring; contract negotiation |
| `05_tech_strategy_documentation.md` | Writing tech strategies, roadmaps, and RFC / proposal documents |
| `06_cross_team_collaboration.md` | Working across engineering, product, and business stakeholders |
| `07_dora_metrics_productivity.md` | DORA metrics, deployment frequency, lead time, change failure rate |
| `08_pep_703_nogil_deep.md` | Python 3.13 free-threaded mode; implications for backend services |
| `09_ai_llm_integration_backend.md` | Integrating LLMs and AI pipelines into production backend systems |
| `10_mentorship_coaching.md` | Structured mentorship, growth frameworks, giving effective feedback |

---

## Recommended Reading Sequence

The sequence below is optimised for interview preparation and practical depth. Follow it in order; skip sections you already own.

### Phase 1 — HLD Foundations (weeks 1–2)

1. `HLD_Theory` files `01` through `31` — cover every first-principles topic that appears in HLD interviews.
2. `HLD_Theory` files `32` through `58` — advanced distributed systems topics; read in order.

### Phase 2 — LLD Foundations (week 3)

3. `LLD_Theory/OOP_Fundamentals.md` and `LLD_Theory/SOLID_Principles.md` — prerequisite for pattern study.
4. `LLD_Theory` files `01` through `21` — work through each GoF pattern in sequence.
5. `LLD_Theory/Command_Composite_Proxy_Flyweight_Patterns.md`, `LLD_Theory/Concurrency_Thread_Safety.md`, `LLD_Theory/Database_Design.md`, `LLD_Theory/Event_Sourcing_CQRS.md`.

### Phase 3 — Hands-on Code (week 4)

6. `Design_Patterns_Code/` — run each Django project locally, read the source, modify one component to reinforce the pattern.
7. `HLD_Code/` — study each implementation; trace the request path end-to-end.

### Phase 4 — Problem Practice (weeks 5–6)

8. `LLD_Problems/` — attempt each problem independently before reading the model answer. Start with `LRU_Cache`, `Parking_Lot_System`, `URL_Shortener`, then work through the full list.
9. `HLD_Problems/` — work the classic interview targets first (`URL_Shortener`, `Rate_Limiter`, `Notification_System`, `Payment_System`), then consumer products, then infrastructure and AI systems.

### Phase 5 — Architecture Depth (week 7)

10. `02_Architecture_Patterns/` — read sections 1 through 10 in order, completing the practical exercises in each section before moving to the next.

### Phase 6 — Leadership and Strategy (week 8)

11. `03_Senior_Leadership/` — read files 01 through 10. Prioritise `01`, `02`, `05`, and `07` if time is limited.

---

## Quick Reference

| Goal | Go to |
|------|-------|
| Understand CAP / consistency trade-offs | `HLD_Theory/08_CAP_Theorem.md`, `HLD_Theory/07_Consistency_Strong_vs_Eventual.md` |
| Prepare for a Netflix / YouTube HLD question | `HLD_Problems/Design_Netflix.md`, `HLD_Problems/Design_YouTube.md` |
| Learn Singleton pattern with real code | `LLD_Theory/01_Singleton_Pattern.md` + `Design_Patterns_Code/01_singleton/` |
| Understand CQRS end to end | `LLD_Theory/Event_Sourcing_CQRS.md` + `HLD_Code/01_cqrs_event_sourcing/` |
| Write an ADR for a design decision | `02_Architecture_Patterns/Section_01_Foundations/05_Documenting_Architecture_ADR_C4.md` |
| Prepare for senior engineering leadership discussion | `03_Senior_Leadership/02_engineering_leadership.md`, `03_Senior_Leadership/05_tech_strategy_documentation.md` |
| Understand cloud cost governance | `03_Senior_Leadership/03_cost_optimization_finops.md` |
| Integrate AI into a backend system | `03_Senior_Leadership/09_ai_llm_integration_backend.md` + `HLD_Problems/Design_ChatGPT_Backend.md` |

---

*This section is part of the [Backend Developer Curriculum](../README.md).*
