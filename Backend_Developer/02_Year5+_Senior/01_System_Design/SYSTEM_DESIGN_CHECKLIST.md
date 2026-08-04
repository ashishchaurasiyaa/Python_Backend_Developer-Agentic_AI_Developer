# System Design Checklist — LLD + HLD
> Senior Backend Interview Preparation
> Tick off as you complete each topic

---

> **Theory coverage yeh file track karti hai. Bolne ki practice ke liye → [PRACTICE_DRILLS.md](PRACTICE_DRILLS.md)** (timed 45-min drills + self-grading rubric). Padhna aur bol pana alag skill hai.

## How to use this file
- `[ ]` = Not done
- `[x]` = Done
- Priority: **P1** = must know | **P2** = important | **P3** = good to have

---

# PART A — HLD (High Level Design)

## A1. Core Concepts (Theory) — `HLD_Theory/`

### Basics
- [ ] **P1** Monolithic vs Microservices → `01_Monolithic_vs_Microservices.md`
- [ ] **P1** Latency + Throughput → `04_Latency.md` + `05_Throughput.md`
- [ ] **P1** Availability + SLA/SLO/SLI → `06_Availability.md` + `30_SLA_SLO_SLI.md`
- [ ] **P1** Horizontal vs Vertical Scaling → `10_Horizontal_vs_Vertical_Scaling.md`
- [ ] **P1** CAP Theorem → `08_CAP_Theorem.md`
- [ ] **P1** ACID vs BASE → `29_ACID_vs_BASE.md`
- [ ] **P1** Consistency: Strong vs Eventual → `07_Consistency_Strong_vs_Eventual.md`

### Databases
- [ ] **P1** Database Indexing → `20_Database_Indexing.md`
- [ ] **P1** Database Sharding → `38_Database_Sharding.md`
- [ ] **P1** NoSQL Types (Document, KV, Column, Graph) → `17_NoSQL_Types.md`
- [ ] **P1** RDBMS Horizontal Scaling → `16_RDBMS_Horizontal_Scaling.md`
- [ ] **P1** Polyglot Persistence → `18_Polyglot_Persistence.md`
- [ ] **P2** Denormalization → `19_Denormalization.md`

### Caching
- [ ] **P1** Caching Complete (strategies, patterns) → `13_Caching_Complete.md`
- [ ] **P1** Cache Eviction (LRU, LFU, TTL) → `14_Cache_Eviction_Techniques.md`

### Networking & Communication
- [ ] **P1** Load Balancer → `12_Load_Balancer.md`
- [ ] **P1** CDN → `32_CDN.md`
- [ ] **P1** API Gateway → `33_API_Gateway.md`
- [ ] **P1** Forward vs Reverse Proxy → `28_Forward_vs_Reverse_Proxy.md`
- [ ] **P1** Synchronous vs Asynchronous → `21_Synchronous_vs_Asynchronous.md`
- [ ] **P1** Message-Based Communication (Kafka, RabbitMQ) → `22_Message_Based_Communication.md`
- [ ] **P2** Communication Protocols (HTTP, gRPC, WebSocket) → `23_Communication_Protocols.md`
- [ ] **P2** HTTP Versions Deep → `48_HTTP_Versions_Deep.md`
- [ ] **P2** TCP vs UDP → `49_TCP_UDP_Deep.md`
- [ ] **P2** DNS Deep → `50_DNS_Deep.md`

### Distributed Systems
- [ ] **P1** Consistent Hashing → `44_Consistent_Hashing_Theory.md`
- [ ] **P1** Redundancy vs Replication → `11_Redundancy_vs_Replication.md`
- [ ] **P1** Service Discovery + Distributed Locking → `35_Service_Discovery_Distributed_Locking.md`
- [ ] **P1** Circuit Breaker + Event Driven → `34_Circuit_Breaker_Event_Driven.md`
- [ ] **P1** Stateful vs Stateless → `55_Stateful_vs_Stateless_Architecture.md`
- [ ] **P1** Idempotency Tokens → `51_Idempotency_Tokens.md`
- [ ] **P2** Back-of-Envelope Estimation → `31_Back_of_Envelope_Estimation.md`
- [ ] **P2** Bloom Filters → `42_Bloom_Filters.md`
- [ ] **P2** Geohashing → `43_Geohashing.md`
- [ ] **P2** Heartbeat + Failure Detection → `54_Heartbeat_Failure_Detection.md`
- [ ] **P3** Lamport Logical Clocks → `09_Lamport_Logical_Clock.md`
- [ ] **P3** Vector Clocks + CRDTs → `46_Vector_Clocks_CRDTs.md`
- [ ] **P3** Quad / KD Trees → `45_Quad_KD_Trees.md`

### Auth & Security
- [ ] **P1** Authentication vs Authorization → `24_Authentication_vs_Authorization.md`
- [ ] **P1** Token-Based Auth (JWT) → `26_Token_Based_Authentication.md`
- [ ] **P1** OAuth → `27_OAuth_Authentication.md`
- [ ] **P2** RBAC Design → `36_RBAC_Design.md`
- [ ] **P2** Basic Authentication → `25_Basic_Authentication.md`

### Operations
- [ ] **P1** Monitoring + Observability → `37_Monitoring_Observability.md`
- [ ] **P1** Zero Downtime Deployment → `39_Zero_Downtime_Deployment.md`
- [ ] **P2** Read Heavy vs Write Heavy → `57_Read_Heavy_vs_Write_Heavy.md`
- [ ] **P2** Data Pipelines + Streaming → `41_Data_Pipelines_Streaming.md`
- [ ] **P2** Webhooks Design → `40_Webhooks_Design.md`
- [ ] **P3** Serverless vs Traditional → `56_Serverless_vs_Traditional.md`
- [ ] **P3** Multi Tenancy Patterns → `47_Multi_Tenancy_Patterns.md`
- [ ] **P3** Big Data + Distributed Processing → `53_Big_Data_Distributed_Processing.md`
- [ ] **P3** Serialization Deep → `52_Serialization_Deep.md`
- [ ] **P3** Data Compression vs Deduplication → `58_Data_Compression_vs_Deduplication.md`

---

## A2. HLD Problems — `HLD_Problems/`
**Format to follow:** Requirements → Capacity Estimation → API Design → DB Schema → Architecture Diagram → Deep Dives

### Tier 1 — Must Solve (asked everywhere)
- [ ] **P1** URL Shortener → `URL_Shortener.md`
- [ ] **P1** WhatsApp / Chat System → `Design_WhatsApp_Chat.md`
- [ ] **P1** Instagram News Feed → `Design_Instagram_NewsFeed.md`
- [ ] **P1** YouTube / Netflix → `Design_YouTube.md` + `Design_Netflix.md`
- [ ] **P1** Uber / Maps → `Design_Uber_Maps.md` + `Design_Google_Maps.md`
- [ ] **P1** Twitter / X → `Design_Twitter_X.md`
- [ ] **P1** Search Autocomplete / Typeahead → `Design_Search_Autocomplete.md`
- [ ] **P1** Distributed Cache → `Design_Distributed_Cache.md`
- [ ] **P1** Rate Limiter (as HLD) → *(covered in LLD too)*
- [ ] **P1** Notification System → *(covered in LLD too)*

### Tier 2 — Important
- [ ] **P2** BookMyShow / Ticket Booking → `Design_BookMyShow.md`
- [ ] **P2** Dropbox / Google Drive → `Design_Dropbox.md`
- [ ] **P2** Google Docs (collaborative) → `Design_Google_Docs.md`
- [ ] **P2** Slack → `Design_Slack.md`
- [ ] **P2** Amazon E-commerce → `Design_Amazon_Ecommerce.md`
- [ ] **P2** Stock Exchange → `Design_Stock_Exchange.md`
- [ ] **P2** eBay Auction → `Design_eBay_Auction.md`
- [ ] **P2** Tinder → `Design_Tinder.md`
- [ ] **P2** Pastebin → `Design_Pastebin.md`
- [ ] **P2** Web Crawler → `Design_Web_Crawler.md`
- [ ] **P2** Spotify → `Design_Spotify.md`
- [ ] **P2** Distributed Logging → `Design_Distributed_Logging.md`
- [ ] **P2** Real Time Analytics → `Design_Real_Time_Analytics.md`

### Tier 3 — Good to Know
- [ ] **P3** Airbnb → `Design_Airbnb.md`
- [ ] **P3** Reddit / Quora → `Design_Reddit.md` + `Design_Quora.md`
- [ ] **P3** Search Engine → `Design_Search_Engine.md`
- [ ] **P3** Ad Server → `Design_AdServer.md`
- [ ] **P3** RAG System / ChatGPT Backend → `Design_RAG_System.md` + `Design_ChatGPT_Backend.md`
- [ ] **P3** Online Code Editor → `Design_Online_Code_Editor.md`
- [ ] **P3** Multi-Tenant SaaS → `Design_Multi_Tenant_SaaS.md`
- [ ] **P3** API Gateway (design) → `Design_API_Gateway.md`
- [ ] **P3** Agent Orchestration → `Design_Agent_Orchestration.md`

---

# PART B — LLD (Low Level Design)

## B1. OOP & SOLID Foundation — `LLD_Theory/`
- [ ] **P1** OOP Fundamentals (4 pillars) → `OOP_Fundamentals.md`
- [ ] **P1** SOLID Principles → `SOLID_Principles.md`
- [ ] **P1** UML Class Diagrams → `10_UML_Class_Diagrams.md`
- [ ] **P1** Database Design (normalization, ER) → `Database_Design.md`
- [ ] **P2** Dependency Injection + Repository + State Machine → `11_Dependency_Injection_Repository_StateMachine.md`
- [ ] **P2** Event Sourcing + CQRS → `Event_Sourcing_CQRS.md`
- [ ] **P2** Concurrency + Thread Safety → `Concurrency_Thread_Safety.md`

## B2. Design Patterns — `LLD_Theory/` + `Design_Patterns_Code/`
**Interview tip:** Know when to use, not just how to implement.

### Creational
- [ ] **P1** Singleton → `01_Singleton_Pattern.md`
- [ ] **P1** Factory → `02_Factory_Pattern.md`
- [ ] **P1** Builder → `04_Builder_Pattern.md`
- [ ] **P2** Abstract Factory → `03_Abstract_Factory_Pattern.md`
- [ ] **P3** Prototype → `12_Prototype_Pattern.md`

### Structural
- [ ] **P1** Adapter → `06_Adapter_Pattern.md`
- [ ] **P1** Decorator → `05_Decorator_Pattern.md`
- [ ] **P1** Facade → `13_Facade_Pattern.md`
- [ ] **P2** Proxy → `Command_Composite_Proxy_Flyweight_Patterns.md`
- [ ] **P2** Composite → `Command_Composite_Proxy_Flyweight_Patterns.md`
- [ ] **P3** Bridge → `20_Bridge_Pattern.md`
- [ ] **P3** Flyweight → `Command_Composite_Proxy_Flyweight_Patterns.md`

### Behavioral
- [ ] **P1** Strategy → `07_Strategy_Pattern.md`
- [ ] **P1** Observer → `08_Observer_Pattern.md`
- [ ] **P1** Command → `Command_Composite_Proxy_Flyweight_Patterns.md`
- [ ] **P2** Iterator → `14_Iterator_Pattern.md`
- [ ] **P2** State → `18_State_Pattern.md`
- [ ] **P2** Template Method → `09_Template_Method_Pattern.md`
- [ ] **P2** Chain of Responsibility → `17_Chain_of_Responsibility_Pattern.md`
- [ ] **P3** Mediator → `15_Mediator_Pattern.md`
- [ ] **P3** Visitor → `16_Visitor_Pattern.md`
- [ ] **P3** Memento → `19_Memento_Pattern.md`
- [ ] **P3** Interpreter → `21_Interpreter_Pattern.md`

## B3. LLD Problems — `LLD_Problems/`
**Format to follow:** Requirements → Class Diagram → Core Classes → Code Skeleton → Edge Cases

### Tier 1 — Asked in almost every LLD round
- [ ] **P1** Parking Lot → `Parking_Lot_System.md`
- [ ] **P1** LRU Cache → `LRU_Cache.md`
- [ ] **P1** Rate Limiter → `Rate_Limiter.md`
- [ ] **P1** Notification System → `Notification_System.md`
- [ ] **P1** Booking System → `Booking_System.md`
- [ ] **P1** Payment System → `Payment_System.md`
- [ ] **P1** Task Queue / Job Scheduler → `Task_Queue_Job_Scheduler.md`

### Tier 2 — Common
- [ ] **P2** Elevator System → `Elevator_System.md`
- [ ] **P2** Ride Booking (Ola/Uber LLD) → `Ride_Booking_System.md`
- [ ] **P2** Food Delivery System → `Food_Delivery_System.md`
- [ ] **P2** Splitwise → `Splitwise.md`
- [ ] **P2** Login System → `Login_System.md`
- [ ] **P2** ATM System → `ATM_System.md`
- [ ] **P2** Vending Machine → `Vending_Machine.md`
- [ ] **P2** Online Shopping Cart → `Online_Shopping_Cart.md`
- [ ] **P2** Stock Trading System → `Stock_Trading_System.md`
- [ ] **P2** Library Management System → `Library_Management_System.md`

### Tier 3 — Good to Know
- [ ] **P3** Tic Tac Toe / Chess → `Tic_Tac_Toe_Chess.md`
- [ ] **P3** Zoom Video Call → `Zoom_Video_Call.md`
- [ ] **P3** File Storage System → `File_Storage_System.md`

---

# PART C — Advanced Topics (Now Added)

## C1. Distributed Transactions
- [ ] **P2** Saga Pattern (choreography + orchestration) → `HLD_Theory/59_Saga_Pattern.md`
- [ ] **P2** Two-Phase Commit (2PC) + WAL → `HLD_Theory/60_Two_Phase_Commit.md`

## C2. Database Internals
- [ ] **P2** Read Replicas + Write-Ahead Log → `HLD_Theory/61_Read_Replicas_WAL.md`

## C3. Distributed Consensus
- [ ] **P3** Raft + Paxos → `HLD_Theory/62_Raft_Paxos_Consensus.md`

## C4. API Design
- [ ] **P2** GraphQL vs REST vs gRPC → `HLD_Theory/63_GraphQL_vs_REST_vs_gRPC.md`

## C5. Product Engineering
- [ ] **P2** Feature Flags + A/B Testing Design → `HLD_Theory/64_Feature_Flags_AB_Testing.md`

## C6. Messaging Patterns
- [ ] **P2** Dead Letter Queue (DLQ) + Retry Strategy → `HLD_Theory/65_Dead_Letter_Queue.md`

---

# Progress Tracker

| Section | Total | Done | % |
|---------|-------|------|---|
| HLD Theory (P1 only) | 30 | 0 | 0% |
| HLD Problems (Tier 1) | 10 | 0 | 0% |
| HLD Problems (Tier 2) | 13 | 0 | 0% |
| LLD Foundation | 7 | 0 | 0% |
| Design Patterns (P1+P2) | 16 | 0 | 0% |
| LLD Problems (Tier 1) | 7 | 0 | 0% |
| LLD Problems (Tier 2) | 10 | 0 | 0% |

---

## Recommended Study Order

```
Week 1-2  →  HLD Theory P1 (Basics + DB + Caching + Networking)
Week 3    →  HLD Tier 1 Problems (URL Shortener, Chat, Feed, YouTube)
Week 4    →  LLD Foundation + P1 Design Patterns
Week 5    →  LLD Tier 1 Problems (Parking Lot, LRU, Rate Limiter, Payment)
Week 6    →  HLD Tier 2 Problems
Week 7    →  LLD Tier 2 Problems + remaining patterns
Week 8    →  Mock interviews + revision of weak areas
```

---

> **Enough for senior interviews at:** Amazon, Flipkart, Swiggy, Zomato, PhonePe, Razorpay, Uber, Google (L4-L5)
> **Rule:** HLD = think at scale. LLD = think in code + patterns.
