# Availability — Replication vs Redundancy, 9s of Availability

## Quick Reference Card
```
Availability  → % time system is operational: (uptime / total time) × 100
9s of avail   → 99.9% = 8.76 hrs/year downtime | 99.99% = 52 min/year
Redundancy    → Backup component — standby, activates on failure
Replication   → Live copies of data/service — all active simultaneously
SPOF          → Single Point of Failure — ek fail = sab fail
MTTR/MTBF     → Mean Time To Recover / Mean Time Between Failures
Interview hook → "AWS RDS Multi-AZ = synchronous replication, automatic failover"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai Availability?

**Analogy: Bijli supply**

- **Availability** = Kitne % time bijli aati hai
- 99% availability = 3.65 din/year bijli nahi
- 99.99% = 52 minutes/year bijli nahi

Website ke liye:
- `availability = uptime / (uptime + downtime)`
- Agar site 1 ghante se zyada down hai → SLA breach

---

### 1.2 Nines of Availability (Memorize)

```
Availability    Downtime/Year    Downtime/Month   Downtime/Day
─────────────────────────────────────────────────────────────
90%   (1 nine)  36.5 days        72 hours         2.4 hours
99%   (2 nines) 3.65 days        7.2 hours        14.4 min
99.9% (3 nines) 8.76 hours       43.8 min         1.44 min
99.99%(4 nines) 52.6 minutes     4.4 min          8.6 sec
99.999%(5 nines)5.26 minutes     26 sec           0.86 sec
─────────────────────────────────────────────────────────────

Common SLAs:
- Startups: 99.9% (3 nines) — acceptable
- E-commerce: 99.99% (4 nines) — important
- Banking/Payments: 99.999% (5 nines) — critical
- YES Platform target: 99.9% (stated in resume)
```

---

### 1.3 Single Point of Failure (SPOF)

```
SPOF Example:
  Users → App Server → ← SINGLE DB ← PROBLEM!
                              |
                         DB crashes
                              ↓
                    ENTIRE SITE DOWN

How to identify SPOF:
  Draw your architecture
  Find any component where if it fails → nothing works
  That's your SPOF

Common SPOFs:
  - Single database (no replica)
  - Single app server (no load balancer)
  - Single region (no DR)
  - Single DNS provider
  - Single payment gateway
```

---

### 1.4 Redundancy vs Replication — Key Difference

### Redundancy
```
REDUNDANCY = Backup component — idle jab tak primary alive hai

                    Active Primary
                         │
                    ─────┤ Normal operation
                         │
              Primary FAILS
                         │
                    Standby Backup ← activates now!
                         │
                    Takes over

Types:
  Cold Standby: Backup powered off, manual start (cheap, slow failover)
  Warm Standby: Backup running but not serving traffic (faster failover)
  Hot Standby:  Backup running and ready to take over immediately

Example:
  AWS RDS: Primary + Standby in different AZ
  Normal: Standby does nothing
  Primary AZ fails: Standby promoted to primary (~1 min failover)
```

### Replication
```
REPLICATION = Multiple LIVE copies, all serving traffic

        ┌─────────────────────────────────┐
        │           Primary DB            │
        │  (accepts reads + writes)       │
        └──────────────────┬──────────────┘
                           │ Replicate (async/sync)
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      Replica 1        Replica 2       Replica 3
   (read traffic)  (read traffic)  (read traffic)

Purpose:
  - Scale READ throughput (80% traffic is reads)
  - Geographic distribution (replica in Mumbai for Indian users)
  - Backup/DR (replica in different region)
```

---

### 1.5 Replication Types — Sync vs Async

```
SYNCHRONOUS REPLICATION:
  Primary → Write → Wait for replica ACK → Respond to client

  Pros: Zero data loss (replica always in sync)
  Cons: Latency increases (wait for replica write)
  Use: Banking, payments, critical data

  ┌────────┐   Write   ┌──────────┐  ACK   ┌────────┐
  │ Client │ ────────> │ Primary  │ ──────> │Replica │
  │        │           │   DB     │         │   DB   │
  │        │ <──────── │          │ <────── │        │
  └────────┘  Response └──────────┘ Confirm └────────┘
  
  (Client waits until replica confirms write)

ASYNCHRONOUS REPLICATION:
  Primary → Write → Respond to client → Replicate later

  Pros: Low latency (don't wait for replica)
  Cons: Potential data loss if primary crashes before replica sync
  Use: Read-heavy apps, analytics, search

  ┌────────┐   Write   ┌──────────┐
  │ Client │ ────────> │ Primary  │ 
  │        │ <──────── │   DB     │ ──async──> Replica
  └────────┘  Response └──────────┘            (later)
```

---

### 1.6 Master-Slave (Primary-Replica) Replication

```
MASTER-SLAVE SETUP:
───────────────────
Master (Primary):
  - All WRITES go here
  - Replicates changes to slaves
  
Slaves (Replicas):
  - READS go here (distribute load)
  - Cannot accept writes

┌───────────┐
│  Master   │ ← All writes
│    DB     │
└─────┬─────┘
      │  Replication stream (WAL logs in PostgreSQL)
      ├──────────────────────┐
      ▼                      ▼
┌───────────┐         ┌───────────┐
│  Slave 1  │         │  Slave 2  │
│  (Read)   │         │  (Read)   │
└───────────┘         └───────────┘
  ↑                         ↑
  API reads                 Analytics queries

Failover: Slave ka promoted to master agar master fail kare
  (Manual or automatic with Patroni/PgBouncer)
```

---

### 1.7 High Availability Patterns

#### Pattern 1: Active-Active
```
Both instances serve traffic simultaneously
Load balancer distributes between them
If one fails → other handles full load

Best for: Stateless services (app servers)
Challenge: Data consistency (both writing to DB?)
```

#### Pattern 2: Active-Passive (Failover)
```
One active, one standby
On failure: passive becomes active
Downtime: ~30-60 seconds for detection + failover

AWS RDS Multi-AZ: Active-Passive
Normal: Primary serves traffic
AZ failure: Standby promoted, DNS updated
```

#### Pattern 3: Circuit Breaker
```
If downstream service keeps failing:
  - Don't keep retrying (makes things worse)
  - "Open" the circuit — fast fail
  - Try again after 60 seconds
  - If succeeds → "Close" circuit

Prevents cascade failures
Protects upstream from downstream failures
```

---

### 1.8 Availability Formula for Distributed Systems

```
Systems in Series (all must work):
  Overall availability = A1 × A2 × A3

  Example:
  App Server: 99.9% × DB: 99.9% × Cache: 99.9%
  = 0.999 × 0.999 × 0.999 = 99.7% ← worse than each component!

Systems in Parallel (any one works):
  Overall = 1 - (1-A1) × (1-A2)

  Example:
  Two servers each 99.9%
  = 1 - (0.001 × 0.001) = 1 - 0.000001 = 99.9999%

Lesson: Parallel = dramatically better availability
         More components in series = lower availability
```

---

### 1.9 Ashish ke projects mein

**AWS setup:**
```
Youngman / Niroskos:
  EC2 App Server → AWS RDS PostgreSQL (Multi-AZ enabled)
  
  Multi-AZ = Synchronous replication to standby in different AZ
  Normal: Primary in AZ-1 serves traffic
  AZ-1 fails: Automatic failover to standby in AZ-2 (~1 min)
  
  Result: 99.95% availability (AWS SLA for RDS Multi-AZ)

Redis:
  ElastiCache Redis Cluster → automatic failover
  
S3: 
  AWS S3 = 99.999999999% (11 nines) data durability
  Multiple AZ replication by default
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Availability** is the proportion of time a system is operational and accessible, expressed as a percentage. It is calculated as `uptime / (uptime + downtime)`. High availability architectures eliminate single points of failure through redundancy (standby backups) and replication (live copies), ensuring the system continues operating despite component failures.

---

### 2.2 Redundancy vs Replication

| Dimension | Redundancy | Replication |
|-----------|-----------|-------------|
| State | Backup is idle (hot/warm/cold) | All copies active |
| Purpose | Fault tolerance | Scale + fault tolerance |
| Failover time | Seconds to minutes | Immediate (load balancer) |
| Data sync | Sync or async | Sync or async |
| Cost | Wasted capacity (passive) | Productive (all serve traffic) |
| Example | AWS RDS Multi-AZ standby | Read replicas |

---

### 2.3 MTTR and MTBF

```
MTBF (Mean Time Between Failures):
  Average time between failures
  Higher MTBF = more reliable
  MTBF = Total uptime / Number of failures

MTTR (Mean Time To Recovery):
  Average time to restore after failure
  Lower MTTR = better (faster recovery)
  MTTR = Total downtime / Number of failures

Availability = MTBF / (MTBF + MTTR)

To improve availability:
  - Increase MTBF: Better hardware, redundancy, fewer deployments
  - Decrease MTTR: Automation, runbooks, monitoring, on-call
```

---

### 2.4 Availability Trade-offs with Consistency (CAP)

```
In distributed systems, during a network partition:
  Choose Availability OR Consistency

CP systems (Consistent + Partition tolerant):
  - Return error rather than stale data
  - Banking, payment systems
  - Example: HBase, Zookeeper

AP systems (Available + Partition tolerant):
  - Return possibly stale data rather than error
  - Better user experience but stale reads possible
  - Example: Cassandra, DynamoDB (default)
  - Niroskos package search: AP acceptable (stale package info ok)
  - Payment processing: CP required (stale balance not ok)
```

---

### 2.5 Real Project Answer

> "At Youngman and Niroskos, we use AWS RDS PostgreSQL with Multi-AZ enabled — this provides synchronous replication to a standby instance in a separate Availability Zone. For reads, we use the primary since our read volume doesn't require replicas yet. The standby's purpose is pure high availability — automatic failover in ~1 minute if the primary AZ has issues. For the app layer, we run multiple EC2 instances behind an Application Load Balancer, eliminating the app server as a SPOF. This architecture gives us approximately 99.95% availability, aligning with the 99.9% target we maintained for the YES Platform."

---

### 2.6 Common Follow-up Q&A

**Q1: How do you achieve 99.99% availability?**
> "Four nines requires eliminating every SPOF and reducing MTTR to under 5 minutes. Architecture: multi-region active-active deployment, database with synchronous replication + automatic failover, load balancers in multiple AZs, CDN for static content, health checks with auto-scaling. Operationally: automated deployments (blue-green/canary), comprehensive monitoring with alerting, runbooks for common failures, 24/7 on-call rotation."

**Q2: What's the difference between fault tolerance and high availability?**
> "High availability means minimizing downtime — the system may briefly fail but recovers quickly (MTTR is low). Fault tolerance means the system continues operating WITHOUT any perceivable interruption despite component failures — zero downtime. Fault tolerance is harder and more expensive. Example: AWS EC2 instance behind a load balancer is high availability (fails, LB detects, redirects traffic — brief interruption). Active-active multi-region with no single DB is closer to fault tolerance."

**Q3: How do you handle split-brain in Master-Slave replication?**
> "Split-brain: both master and slave think they're primary (network partition). Solved by: (1) Quorum-based election — need majority (e.g., 2 of 3 nodes) to become primary. (2) STONITH (Shoot The Other Node In The Head) — forcibly kill the old primary. (3) Witness/arbitrator node that breaks ties. Tools: Patroni for PostgreSQL HA, AWS RDS handles this automatically."

---

## Comparison: Redundancy vs Replication vs Backup

| Feature | Redundancy | Replication | Backup |
|---------|-----------|-------------|--------|
| Purpose | Failover | Scale + HA | Disaster recovery |
| Data age | Real-time (sync) | Real-time | Point in time (daily) |
| Recovery time | Minutes | Seconds | Hours |
| Serves traffic | Passive (standby) | Active (all copies) | Never directly |
| Cost | Moderate | High | Low |

---

## Interview Cheat Sheet

```
Availability = uptime / (uptime + downtime) × 100%

9s of availability:
99%    = 3.65 days/year downtime
99.9%  = 8.76 hours/year
99.99% = 52 minutes/year

Redundancy = Backup (idle standby, activates on failure)
Replication = Live copies (all serving traffic)

Master-Slave:
  Master = all writes, replicates to slaves
  Slaves = read traffic, can promote on master failure
  Sync replication = zero data loss, higher latency
  Async replication = lower latency, possible data loss

SPOF = Single Point of Failure — eliminate with:
  - Multiple app instances behind LB
  - DB replication + failover
  - Multi-AZ deployment

Availability formula:
  Series: A1 × A2 × ... (gets worse)
  Parallel: 1 - (1-A1)(1-A2)... (gets better)

My setup: AWS RDS Multi-AZ (sync replication, auto-failover)
          Multiple EC2 + ALB (app layer HA)
```
