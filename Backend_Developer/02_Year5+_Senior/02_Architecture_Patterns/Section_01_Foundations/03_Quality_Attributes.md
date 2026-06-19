# Lecture 3: Quality Attributes in Software Architecture

> *"Quality attributes shape your system's resilience, growth potential, and long-term success."*

**Section 1 — Foundations of Software Architecture**

---

## 🎯 Is lecture mein kya seekhenge?

- **Quality attributes** kya hote hain aur kyun matter karte hain
- **Non-functional requirements (NFRs)** — features se alag kaise
- **5 main quality attributes** in detail:
  - 📈 Scalability
  - ⚡ Performance
  - ✅ Availability
  - 🔧 Maintainability
  - 🔒 Security
- **CAP Theorem** aur dusre **trade-offs**
- Quality attributes ko **balance kaise karein**

---

## 1. Quality Attributes Kya Hote Hain?

### Definition

> **Quality attributes are non-functional requirements (NFRs) that define system behavior beyond just features.**

Features batate hain ki system **kya karta hai** — login, order, payment.
Quality attributes batate hain ki system **kitne ache se karta hai** — kitna fast, kitna scalable, kitna secure.

### Functional vs Non-Functional

```
┌─────────────────────────────────────┐
│  FUNCTIONAL REQUIREMENTS             │
│  (What the system does)              │
│                                      │
│  ✓ User can login                    │
│  ✓ User can place order              │
│  ✓ Admin can refund                  │
│  ✓ System sends email                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  NON-FUNCTIONAL REQUIREMENTS         │
│  (How well it does it)               │
│                                      │
│  ✓ Login response < 200ms (P95)       │
│  ✓ Handles 100K concurrent users     │
│  ✓ 99.99% uptime                     │
│  ✓ GDPR compliant                    │
│  ✓ Encrypts PII at rest              │
└─────────────────────────────────────┘
```

### Why Quality Attributes Matter

```
System Success / Reliability
    ↑
    │
    ├── Scalability (Can grow?)
    ├── Availability (Stays up?)
    ├── Performance (Fast?)
    ├── Security (Safe?)
    ├── Maintainability (Easy to change?)
    └── Cost Efficiency (Affordable?)
```

> **Features might get the product out of the door, but quality attributes decide if it can handle real-world scale, change, and failures.**

### Real Impact

Production mein:
- ❌ Bad quality → outages, slow responses, security breaches, expensive bugs
- ✅ Good quality → smooth scaling, happy users, easy changes, lower cost

```
🚀 Launch → 📈 Growth → 🔥 Traffic Spike → 💥 Outage → 🛠 Costly Fix
```

Yeh sequence **poor quality attributes** ka classic example hai. **Good architecture** is sequence ko break karta hai.

### The Trade-off Reality

```
⚠️ IMPORTANT:
Quality attributes have TRADE-OFFS.
You CAN'T optimize all simultaneously.
```

- High security → slower performance (encryption overhead)
- High cost efficiency → may limit scalability
- High consistency → may reduce availability (CAP theorem)
- High maintainability → may sacrifice raw performance

**Good architect = one who balances these intentionally.**

---

## 2. Scalability — Can the System Grow?

### Definition

**Scalability** = system ki ability hai increased load handle karne ki **without performance degradation**.

Load increase kya kya ho sakti hai:
- More users
- More data
- More traffic
- More transactions per second

### Two Types of Scaling

```
┌────────────────────────────────┐    ┌────────────────────────────────┐
│   VERTICAL SCALING (Scale-Up)   │    │  HORIZONTAL SCALING (Scale-Out) │
│                                  │    │                                  │
│  Single machine ko bigger banao  │    │  More machines add karo          │
│                                  │    │                                  │
│       💻                         │    │   💻   💻   💻                   │
│      ↑ Add more RAM, CPU         │    │   💻   💻   💻                   │
│                                  │    │                                  │
│  Pros:                           │    │  Pros:                           │
│  - Simple to do                  │    │  - Practically unlimited         │
│  - No code changes needed        │    │  - Better fault tolerance        │
│                                  │    │                                  │
│  Cons:                           │    │  Cons:                           │
│  - Hardware limits               │    │  - Complex (need load balancer)  │
│  - Expensive at top end          │    │  - Need stateless design         │
│  - SPOF                          │    │  - Network overhead              │
└────────────────────────────────┘    └────────────────────────────────┘
```

### Real-World Scaling Examples

**Vertical scaling example:**
- Database server upgrade: 8 cores, 32 GB RAM → 32 cores, 128 GB RAM
- Single VM upgrade on AWS: t3.medium → m5.4xlarge

**Horizontal scaling example:**
- Load balancer ke peeche multiple application servers
- Database sharding: 1 DB → 100 shards
- Kafka topic partitioning across brokers

### Architecture Patterns for Horizontal Scaling

1. **Load Balancer + App Servers** — traffic distribute karna
2. **Database Sharding** — data ko multiple nodes mein split
3. **Read Replicas** — read traffic offload
4. **CDN** — static content edge servers se serve karna
5. **Auto-scaling** — cloud-based dynamic scaling

### Real Scaling Decision Example

**Scenario:** E-commerce site, Black Friday sale, 100x traffic expected.

```
Option A: Vertical scaling
- Upgrade primary DB to biggest instance type
- Pros: Quick, no code changes
- Cons: Hits ceiling at ~$10K/month; SPOF

Option B: Horizontal scaling
- Add read replicas (3-5)
- Implement caching layer (Redis)
- Auto-scale app servers (5 → 50)
- Pros: Unlimited growth, fault tolerance
- Cons: Cache invalidation, consistency issues
```

Production reality: **Both ka mix** use hota hai.

---

## 3. Types of Scalability

Scalability one-size-fits-all nahi hai. Different load types = different strategies.

### A. Read Scalability

**Problem:** Tons of read requests — API calls, page views, search queries.

```
                  ┌─────────┐
   Users ────────→│  CDN     │ Static content here
                  └────┬─────┘
                       │ Cache miss
                  ┌────▼─────┐
                  │  Cache    │  Redis / Memcached
                  │  (Redis)  │  for frequent data
                  └────┬─────┘
                       │ Cache miss
                  ┌────▼─────┐
                  │  Read     │  Read from replicas
                  │  Replicas │  Not primary!
                  └────┬─────┘
                       │
                  ┌────▼─────┐
                  │  Primary  │  Only on cache + replica miss
                  │  DB       │
                  └──────────┘
```

**Tools:**
- **CDN**: Cloudflare, Akamai, Fastly
- **Cache**: Redis, Memcached, Hazelcast
- **Read replicas**: PostgreSQL streaming replication, MySQL replicas

### B. Write Scalability

**Problem:** Massive write throughput — payments, IoT data, logs.

This is harder than read scaling. Solutions:

**1. Database Partitioning/Sharding:**
```
Single DB                    Sharded DB
─────────                    ──────────
Users table                  Users (Shard 1: user_id 1-1M)
(All 100M rows)         →    Users (Shard 2: user_id 1M-2M)
                              ...
                              Users (Shard 100: user_id 99M-100M)
```

**2. Async Queue for Writes:**
```
Client → API → Kafka topic → Workers → DB
        (fast response)    (process in background)
```

**3. Event Sourcing:**
- Write events to append-only log
- Build read models asynchronously

**Tools:**
- **Kafka, RabbitMQ** for async writes
- **Cassandra, DynamoDB** for write-heavy workloads
- **PostgreSQL Citus** for horizontal sharding

### C. Elastic Scalability

**Cloud-native magic:** Auto-scaling based on real-time demand.

```
Low traffic period:  2 instances running
High traffic spike:  10 instances running (auto-scale up)
Traffic normal:      2 instances running (auto-scale down)
```

**How it works:**
- Monitor CPU, memory, queue depth, request rate
- Trigger scale-up when threshold crossed
- Trigger scale-down when load decreases
- Cost optimization: pay only for what you use

**Tools:**
- **AWS Auto Scaling Groups**, **EKS HPA**
- **GCP Managed Instance Groups**, **GKE Autopilot**
- **Azure VMSS**
- **Kubernetes HPA** (Horizontal Pod Autoscaler)

### Putting It Together

```
LOAD BALANCING ──┐
                  ├── Distribute traffic
CACHING STRATEGIES ──┐
                      ├── Speed up reads
DATABASE SHARDING ──┐
                     ├── Scale writes
STATELESS SERVICES ──┐
                      ├── Enable easy scaling
AUTO-SCALING ──┐
                ├── Match capacity to demand
```

Yeh sab **scaling toolbox** hai. **Architecture decide karti hai** kaunsa use karna hai.

---

## 4. Performance — How Fast is the System?

### Definition

**Performance** = system kitne speed se requests process karta hai.

### Two Key Metrics

```
┌──────────────────────────────────────┐
│   LATENCY                             │
│   - Response delay                    │
│   - Time for ONE request              │
│   - Measured in ms                    │
│                                       │
│   Example:                            │
│   API call: 50ms (cached)             │
│   API call: 400ms (uncached)          │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│   THROUGHPUT                          │
│   - Requests/sec                      │
│   - How many in parallel              │
│   - Measured in RPS, TPS              │
│                                       │
│   Example:                            │
│   API: 10K RPS                        │
│   DB writes: 5K TPS                   │
└──────────────────────────────────────┘
```

### Performance Components

Performance sirf API speed nahi hai — pure user journey ki speed:
- Page load time
- Time to first byte (TTFB)
- API response time
- Database query time
- Batch job duration
- Background processing time

### Latency Comparison Example

```
Cached request:    🟢 50ms
Uncached request:  🔴 400ms
```

Cache hit = **8x faster**.

### Architectural Patterns for Performance

**1. Caching**
- Browser cache → CDN cache → App cache → DB cache
- Layer wise optimization

**2. Compression**
- Gzip, Brotli for HTTP responses
- Reduces payload by 60-80%

**3. Indexing**
- Database indexes speed up queries 100x+
- Trade-off: slower writes, more disk space

**4. CDN**
- Static content (images, CSS, JS) edge servers se serve
- Reduces latency for global users

**5. Asynchronous Processing**
- Long tasks → background queue
- Don't block user request

### Percentiles Matter

```
Average latency:  100ms (looks great!)
p95 latency:       500ms
p99 latency:       2000ms ← 1% of users see this!

Without percentiles, you optimize for average and ignore tail.
```

**Always optimize for P99**, not average.

---

## 5. Availability — Is the System Up?

### Definition

**Availability** = system kitna time **up and running** rehta hai.

### Measured in "Nines"

```
99% uptime    = 87.6 hours downtime/year (3.65 days)
99.9% (3 nines) = 8.76 hours/year
99.95%          = 4.38 hours/year
99.99% (4 nines) = 52.6 minutes/year
99.999% (5 nines) = 5.26 minutes/year (very expensive!)
```

Har "9" achieve karna **10x harder + 10x expensive** hota hai. Business need ke hisab se decide karein.

### Common Causes of Downtime

```
Server crashes
   ↓
Database failures
   ↓
Network outages
   ↓
DNS issues
   ↓
Configuration errors
   ↓
Cloud provider outages
   ↓
Software bugs in production
```

### Architectural Patterns for High Availability

**1. Redundancy**
- Multiple replicas of every component
- "Don't put all eggs in one basket"

```
Primary Server ──── Replica 1
                 ├── Replica 2
                 └── Replica 3
```

**2. Failover Systems**
- Automatic switchover when primary fails
- Database: PostgreSQL Patroni, MySQL Group Replication
- App: Kubernetes pod restart, AWS ELB target health

**3. Heartbeat Checks**
- Periodic health probes
- Detect failure quickly (< 30 sec)

**4. Retries with Timeout**
- Transient failures handle karein
- Exponential backoff
- Circuit breakers prevent retry storms

**5. Multi-Region Deployment**
- US users → US region
- EU users → EU region
- India users → AP-South region

### Availability vs Cost Trade-off

```
Cost ↑
   │       99.999% (5 nines)
   │      /
   │     /
   │    / 99.99% (4 nines)
   │   /
   │  /  99.9% (3 nines)
   │ /
   │/   99% (basic)
   └─────────────────→ Availability
```

**Don't promise more than business needs.**

---

## 6. Maintainability — Can We Evolve the System?

### Definition

**Maintainability** = system ko **change karna kitna easy** hai **bina kuch break kiye**.

### Maintainable System Characteristics

```
✅ Easy to understand
✅ Easy to change
✅ Safe to evolve
```

### Three Pillars of Maintainability

**Pillar 1: Code Structure**
- Clean modules
- Readable naming conventions
- Separation of concerns (SoC)
- SOLID principles

**Pillar 2: Tooling**
- Automated tests (unit, integration, e2e)
- CI/CD pipelines
- Automated deployments
- Static analysis

**Pillar 3: Documentation**
- README files
- API documentation
- Architecture diagrams (C4 model)
- ADRs (Architecture Decision Records)

### Monolith vs Microservices Trade-off

```
❌ MONOLITH (Before)          ✅ MICROSERVICES (After)
─────────────────             ────────────────────
┌────────────────┐            ┌────────────┐
│ M2 │ M3 │      │            │ Auth        │
│  tangled tangled│            │ Service     │
│        ↓        │            └──────┬─────┘
│  Auth+Billing+ │                    ↓
│  UI+DB         │            ┌────────────┐
│  (one big mess)│            │ Billing     │
└────────────────┘            │ Service     │
                              └──────┬─────┘
                                     ↓
                              ┌────────────┐
                              │ UI Module   │
                              └──────┬─────┘
                                     ↓
                              ┌────────────┐
                              │ DB Service  │
                              └────────────┘
```

| Aspect | Monolith | Microservices |
|---|---|---|
| Start | ✅ Simpler | ❌ Complex |
| Long-term | ❌ Becomes tangled | ✅ Better modularity |
| Maintainability over time | ❌ Hard | ✅ Better |
| Operational complexity | ✅ Low | ❌ High |

### Code Smells Indicating Poor Maintainability

```
🚨 Functions > 100 lines
🚨 Classes > 500 lines
🚨 Nested if/else > 5 levels
🚨 Copy-paste code everywhere
🚨 Magic numbers/strings
🚨 No tests
🚨 Tight coupling
🚨 God objects (one class does everything)
```

---

## 7. Security — Is the System Safe?

### Definition

**Security** = system **unauthorized access, misuse, aur breaches** se kitna protected hai.

### Security Layers

```
┌──────────────────────────────────────┐
│ 🔐 Multi-Factor Authentication        │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 🔥 Firewall                          │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 🔒 HTTPS / TLS                       │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 🎫 JWT Authentication                │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ 🔑 App Layer with Role-Based Access  │
└──────────────────────────────────────┘
```

**Defense in depth** — agar ek layer fail bhi ho jaaye, baki layers system ko protect karte hain.

### Core Security Concepts

**1. Authentication vs Authorization**
- **Authentication**: Who are you? (Login)
- **Authorization**: What can you do? (Permissions)

**2. Data Encryption**
- **At rest**: Database encryption, S3 SSE
- **In transit**: HTTPS, TLS 1.3

**3. Secure Coding**
- Input validation (prevent SQL injection, XSS)
- Output encoding
- Parameterized queries

**4. Rate Limiting**
- Prevent brute force attacks
- Prevent DDoS
- Per-IP, per-user, per-endpoint

**5. Zero Trust Architecture**
- "Never trust, always verify"
- Every request authenticated
- No implicit trust between services

**6. Least Privilege Principle**
- Users/services get minimum needed access
- No "admin everywhere"

### Common Security Threats (OWASP Top 10)

1. Broken Access Control
2. Cryptographic Failures
3. Injection (SQL, NoSQL, OS command)
4. Insecure Design
5. Security Misconfiguration
6. Vulnerable Components
7. Authentication Failures
8. Software/Data Integrity Failures
9. Logging/Monitoring Failures
10. Server-Side Request Forgery (SSRF)

### Security Trade-offs

```
🔒 More security:
+ Better protection
- Slower performance (encryption overhead)
- More complex code
- Worse user experience (more auth steps)
```

**Right balance** business requirements pe depend karta hai.

---

## 8. Trade-offs Between Quality Attributes

### CAP Theorem — The Famous Trade-off

In distributed systems, you can have at most **TWO** of these three:

```
            ▲ Consistency
            │
       CP   │   CA
   (MongoDB,│ (RDBMS like
    Hbase)  │  Oracle, MySQL)
            │
            ├─────── "Pick Two" ──────→ Availability
            │
            │   AP
            │ (Cassandra,
            │  RIAK, CouchDB)
            │
            ▼ Partition Tolerance
```

| System Type | Trades off |
|---|---|
| **CP** (Consistency + Partition Tolerance) | Availability — some data may be unavailable during partition |
| **CA** (Consistency + Availability) | Partition Tolerance — works fine until network partition, then stops |
| **AP** (Availability + Partition Tolerance) | Consistency — clients may read inconsistent data |

**In practice:** Network partitions DO happen. So real choice is **CP vs AP**.

### Other Common Trade-offs

**1. Performance vs Security**
- Encryption adds latency (10-50ms overhead)
- Auth checks slow down requests
- HTTPS handshake takes time

**2. Maintainability vs Performance**
- Clean abstracted code = slower than optimized low-level code
- Object-oriented overhead vs procedural speed
- Generic solutions vs specialized fast paths

**3. Cost vs Scalability**
- Auto-scaling costs more than fixed capacity
- Multi-region deployment expensive but scalable
- Premium DB tiers more expensive but more capacity

**4. Consistency vs Availability**
- Strong consistency = potential downtime during partition
- Eventual consistency = always up but stale reads

**5. Simplicity vs Flexibility**
- Microservices flexible but operationally complex
- Monolith simple but harder to scale

### Trade-off Decision Framework

```
1. List all relevant quality attributes
2. Rank them by business priority
3. For each pair, identify trade-off
4. Make explicit decision
5. Document rationale
6. Revisit when context changes
```

---

## 9. Balancing Quality Attributes

### No One-Size-Fits-All

> **The right balance depends entirely on your use case, business goals, and user expectations.**

### Use-Case-Driven Prioritization

**Healthcare System:**
```
Priority: Security > Reliability > Performance > Cost
- HIPAA compliance critical
- Data privacy paramount
- Encryption everywhere
- Audit logs comprehensive
- 99.99% uptime expected
```

**Gaming Platform:**
```
Priority: Performance > Scalability > Availability > Security
- Sub-100ms latency expected
- Real-time multiplayer needs low latency
- Some security trade-offs acceptable
- Auto-scaling for events
```

**Financial Trading:**
```
Priority: Consistency > Performance > Security > Availability
- Cannot lose transactions
- Sub-millisecond latency for trades
- Strict regulatory compliance
- Brief downtime acceptable (better than inconsistency)
```

**Social Media:**
```
Priority: Availability > Scalability > Performance > Consistency
- Always online required
- Massive scale (billions of users)
- Eventual consistency OK
- Some security trade-offs for UX
```

### Visualization

```
            Balanced System Goals
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
  Scalability  Availability  Performance
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
    Security  Maintainability  Cost
```

Aap **tune** karte ho — har dial alag use case mein alag setting pe hota hai.

### The Architect's Job

```
Architecture Mixing Board

Scalability    [▓▓▓▓▓▓▓▓░░] 80%
Availability   [▓▓▓▓▓▓▓░░░] 70%
Performance    [▓▓▓▓▓▓▓▓░░] 80%
Security       [▓▓▓▓▓▓▓▓▓▓] 100%
Maintainability[▓▓▓▓▓░░░░░] 50%
Cost-Efficiency[▓▓▓░░░░░░░] 30%
```

- Healthcare: Security maxed out, Cost-Efficiency low
- Game: Performance maxed out, Maintainability medium

**You can't max all dials.** You **tune** based on what matters most.

---

## 10. Summary & Key Takeaways

### What You Should Remember

| Quality Attribute | Key Question | Key Tools |
|---|---|---|
| **Scalability** | Can system grow? | Sharding, replicas, auto-scaling |
| **Performance** | How fast? | Caching, CDN, compression, async |
| **Availability** | Stays up? | Redundancy, failover, retries |
| **Maintainability** | Easy to change? | Tests, docs, modular code |
| **Security** | Safe? | Auth, encryption, validation |

### Key Principles

1. **Quality attributes shape resilience, growth, longevity**
2. **Each attribute needs active design consideration** — afterthought se nahi hota
3. **Trade-offs are inevitable** — understand your priorities
4. **No one-size-fits-all** — depends on use case
5. **You can't maximize everything** — tune based on context

### Architect's Mindset

```
Don't say: "Let's make it scalable and secure and fast"
Say:        "Given that we're building healthcare software,
            security is top priority. We'll trade some
            performance for HIPAA compliance. Scalability
            is moderate — we expect 100K users not 100M."
```

**Specific. Intentional. Trade-off aware.**

---

## 11. Interview Questions

### Q1: "What are non-functional requirements?"

**Answer:**
"Non-functional requirements (NFRs) define **how well** a system performs, as opposed to functional requirements which define **what** the system does.

Examples:
- **Functional**: User can log in
- **Non-functional**: Login responds in < 200ms at p95, supports 100K concurrent users, 99.9% uptime, OWASP-compliant

NFRs include scalability, performance, availability, security, maintainability, and cost efficiency. They're critical because they shape architecture decisions. Features come and go, but NFRs are baked into the system structure."

### Q2: "Explain the CAP theorem with an example."

**Answer:**
"CAP theorem states that in a distributed system, you can guarantee at most two of three properties:
- **Consistency**: All nodes see the same data at the same time
- **Availability**: Every request receives a response
- **Partition tolerance**: System continues working despite network failures

Since network partitions DO happen in real systems, the practical choice is between **CP** (Consistency + Partition tolerance) or **AP** (Availability + Partition tolerance).

**Example:**
- **Banking system**: CP — better to refuse a transaction than process inconsistent data (could lead to overdraft)
- **Social media feed**: AP — better to show slightly stale posts than show 'service unavailable'

In practice, modern databases like Cassandra are configurable — you can tune per-operation consistency."

### Q3: "How would you scale a database?"

**Answer:**
"Multiple strategies depending on the load type:

**For reads:**
1. **Read replicas** — write to primary, read from replicas
2. **Caching layer** — Redis/Memcached in front
3. **CDN** for static data
4. **Materialized views** — pre-computed aggregates

**For writes:**
1. **Vertical scaling** first — bigger machine
2. **Partitioning** — split data within one DB
3. **Sharding** — split data across multiple DBs
4. **Async writes** — queue writes, batch insert
5. **Different DB** — Cassandra for write-heavy workloads

**For both:**
- **Connection pooling** — PgBouncer
- **Query optimization** — indexes, EXPLAIN ANALYZE
- **Denormalization** — trade space for speed

I'd start with the easiest (caching, replicas) and only add complexity (sharding) when needed."

### Q4: "How do you balance security with performance?"

**Answer:**
"Several techniques:

1. **TLS termination** at edge — handle expensive TLS handshakes at CDN/LB, internal traffic in private network
2. **Cache auth decisions** — validate JWT once per request, not per check
3. **Connection reuse** — long-lived connections reduce TLS handshake overhead
4. **Asymmetric crypto only when needed** — use symmetric encryption (AES) for bulk data
5. **Hardware acceleration** — AES-NI instructions, dedicated HSMs
6. **Rate limiting at edge** — block bad actors before they hit app
7. **Smart caching** — cache public data aggressively, private data carefully

Trade-off: I'd never compromise critical security (e.g., never disable TLS, never store passwords in plaintext), but I'd cache authentication results, batch security operations, and use efficient algorithms."

### Q5: "How do you ensure 99.99% availability?"

**Answer:**
"99.99% means about 52 minutes downtime per year. To achieve this:

1. **Multi-AZ deployment** — at least 2 availability zones
2. **Active-passive or active-active** failover
3. **Automated failover** — Patroni for PostgreSQL, K8s for app
4. **Health checks** at multiple levels
5. **Graceful degradation** — degraded mode if dependencies fail
6. **Circuit breakers** — prevent cascading failures
7. **Comprehensive monitoring** — detect issues fast (MTTD < 1 min)
8. **Runbooks + automation** — fast recovery (MTTR < 5 min)
9. **Load testing** — verify capacity for peak loads
10. **Chaos engineering** — test failure scenarios
11. **No single points of failure** — every component redundant

Higher tiers (99.999%) need multi-region active-active, which is significantly more expensive."

---

## 12. Key Slide References (from PDF)

- 📄 **Slide 23**: What are Quality Attributes?
- 📄 **Slide 24**: Why Quality Attributes Matter
- 📄 **Slide 25**: Scalability — Can the System Grow?
- 📄 **Slide 26**: Types of Scalability
- 📄 **Slide 27**: Performance — How Fast is the System?
- 📄 **Slide 28**: Availability — Is the System Up?
- 📄 **Slide 29**: Maintainability — Can We Evolve the System?
- 📄 **Slide 30**: Security — Is the System Safe?
- 📄 **Slide 31**: Trade-offs Between Quality Attributes (CAP Theorem)
- 📄 **Slide 32**: Balancing Quality Attributes

---

## 13. What's Next?

**Lecture 4: Roles & Responsibilities of a Software Architect** — Architect ka kaam exactly kya hota hai? Decisions kaise lete hain? Tech lead se kya difference hai?

➡️ **[Lecture 4: Roles & Responsibilities of a Software Architect](04_Roles_Responsibilities_Software_Architect.md)**

---

## 🎓 Related Backend_Developer Curriculum

- [02_Year5+_Senior/01_System_Design/HLD_Theory/04_Latency.md](../../01_System_Design/HLD_Theory/04_Latency.md)
- [02_Year5+_Senior/01_System_Design/HLD_Theory/05_Throughput.md](../../01_System_Design/HLD_Theory/05_Throughput.md)
- [02_Year5+_Senior/01_System_Design/HLD_Theory/06_Availability.md](../../01_System_Design/HLD_Theory/06_Availability.md)
- [02_Year5+_Senior/01_System_Design/HLD_Theory/08_CAP_Theorem.md](../../01_System_Design/HLD_Theory/08_CAP_Theorem.md)
- [02_Year5+_Senior/01_System_Design/HLD_Theory/10_Horizontal_vs_Vertical_Scaling.md](../../01_System_Design/HLD_Theory/10_Horizontal_vs_Vertical_Scaling.md)
