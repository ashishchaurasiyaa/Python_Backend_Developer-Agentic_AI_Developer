# Redundancy vs Replication — Master-Slave Replication

## Quick Reference Card
```
Redundancy    → Backup component — standby jab tak primary alive hai
Replication   → Live copies — sab simultaneously serve kar rahe hain
Master-Slave  → Master = all writes | Slave = read traffic
WAL           → Write-Ahead Log — PostgreSQL replication mechanism
Failover      → Primary fail → Secondary promotes to primary
Split-brain   → Dono nodes sochein "main primary hoon" — dangerous!
Interview hook → "AWS RDS Multi-AZ = synchronous redundancy | Read replicas = async replication"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Redundancy Kya Hai?

**Analogy: Spare tyre**

Car mein spare tyre hota hai — jab tak main tyre theek hai, spare tyre boot mein rakha hai. Kuch nahi karta. Main tyre puncture ho → spare tyre nikalo, lagao.

```
REDUNDANCY:
  Normal operation:
    Primary Server ← All traffic
    Standby Server ← Idle (doing nothing, just waiting)
  
  Primary fails:
    Primary Server ← DEAD
    Standby Server ← Now active (failover happened)
    
Types:
  Cold Standby: Standby off rehta hai (boot karna padega)
                Failover time: 5-15 minutes
                Cost: Cheapest (not running)
  
  Warm Standby: Standby on hai, data sync ho raha hai, but traffic nahi le raha
                Failover time: 30-60 seconds
                Cost: Medium (server running, no traffic)
  
  Hot Standby:  Standby fully ready, hamesha sync, DNS flip karke immediate switch
                Failover time: < 30 seconds
                Cost: Highest (full capacity running idle)
```

---

### 1.2 Replication Kya Hai?

**Analogy: Netflix regional servers**

Netflix ke Mumbai server pe same movies hain jo London server pe hain. Mumbai ke users Mumbai server se stream karte hain, London ke London se. Dono live hain, dono actively serving hain.

```
REPLICATION:
  All instances serving traffic simultaneously:
  
        ┌─────────────┐
        │  Primary DB  │ ← Writes
        │  (Master)    │
        └──────┬───────┘
               │ Replicate changes continuously
        ┌──────┼──────────────┐
        ▼      ▼              ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │Replica 1 │ │Replica 2 │ │Replica 3 │
  │(Mumbai)  │ │(Delhi)   │ │(Chennai) │
  └──────────┘ └──────────┘ └──────────┘
       ↑              ↑             ↑
  Read traffic   Read traffic  Analytics
```

---

### 1.3 Master-Slave (Primary-Replica) Replication — Deep Dive

**PostgreSQL WAL (Write-Ahead Log) Replication:**

```
STEP 1: All writes go to Primary
  App Server → Primary DB: "INSERT INTO invoices ..."
  Primary writes to WAL (Write-Ahead Log) first
  WAL = sequence of all DB changes in order
  
STEP 2: WAL shipped to replicas
  Primary → Sends WAL segments to Replica 1, Replica 2
  Replica replays WAL → its data becomes identical to primary
  
STEP 3: Reads distributed
  Read traffic → Replica 1 or Replica 2
  Write traffic → Primary only

  ┌────────────────┐
  │   Primary DB   │
  │                │     WAL stream (continuous)
  │  WAL: [1,2,3,4]│ ──────────────────────────► Replica 1
  │                │ ──────────────────────────► Replica 2
  └────────────────┘
       ↑
  All writes only

  WAL = Write-Ahead Log:
    Record 1: INSERT invoices VALUES (...)
    Record 2: UPDATE bookings SET status='confirmed'
    Record 3: DELETE sessions WHERE expired=true
    
  Replica replays same records → exact same data
```

**Sync vs Async WAL replication:**

```
SYNCHRONOUS REPLICATION (safer):
  Primary writes → Waits for at least 1 replica to confirm WAL received
  Only then → Returns success to app server
  
  Pros: Zero data loss (replica always has latest data)
  Cons: Latency increases (wait for network round trip)
  
  PostgreSQL config:
  synchronous_commit = on
  synchronous_standby_names = 'replica1'

ASYNCHRONOUS REPLICATION (faster):
  Primary writes → Immediately returns success to app server
  Background: Ships WAL to replicas
  
  Pros: Low write latency
  Cons: Replication lag — replica might be 0-500ms behind
        If primary crashes, last N milliseconds of data LOST
  
  PostgreSQL config:
  synchronous_commit = off  (or local)
```

---

### 1.4 Failover — Primary Fail Hone Par Kya Hota Hai

```
SCENARIO: Primary DB crashes
  
  BEFORE FAILOVER:
  ┌──────────────┐   ┌──────────────┐
  │  PRIMARY     │   │  REPLICA     │
  │  (writes)    │   │  (reads)     │
  │  CRASHED ✗   │   │  Running ✓   │
  └──────────────┘   └──────────────┘

  FAILOVER STEPS:
  1. Detect failure (health check fails — 10-30 seconds)
  2. Replica promoted to Primary
     - Can now accept writes
     - WAL streaming stops (no master to receive from)
  3. DNS/connection string updated to point to new primary
  4. Application reconnects
  5. Old primary repaired → comes back as NEW REPLICA

  AFTER FAILOVER:
  ┌──────────────┐   ┌──────────────┐
  │  OLD PRIMARY │   │  NEW PRIMARY │
  │  (now replica│   │  (promoted)  │
  │   after fix) │   │  (writes)    │
  └──────────────┘   └──────────────┘

Tools for PostgreSQL automatic failover:
  Patroni: Leader election via Consul/etcd/ZooKeeper
           Automatic promotion, no human needed
  pgBouncer: Connection pooling + transparent failover
  AWS RDS Multi-AZ: Fully automated (~60 second failover)
```

---

### 1.5 Split-Brain Problem

```
SPLIT-BRAIN:
  Network partition → Primary and Replica both think they're primary!
  
  ┌──────────────┐    ✗ Network ✗    ┌──────────────┐
  │  PRIMARY     │──── partition ────│  REPLICA     │
  │  (writing)   │                   │  (promoted   │
  │              │                   │   itself!)   │
  └──────────────┘                   └──────────────┘
  
  App Server 1 → Writes to "Primary" (left node)
  App Server 2 → Writes to "New Primary" (right node)
  
  Result: Two different sets of data → INCONSISTENT DISASTER!
  
  Solutions:
  1. Quorum (majority voting):
     3 nodes → need 2 to agree on who's primary
     Split: 1 vs 1 → neither can promote (no majority)
     Safe!
  
  2. STONITH (Shoot The Other Node In The Head):
     When promotion happens, forcibly kill old primary
     AWS RDS does this automatically
  
  3. Witness node:
     3rd lightweight node just for tie-breaking
     Can't hold data, only votes in elections
```

---

### 1.6 Read Replica — Practical Use

```python
# Django — Route reads to replica, writes to primary

# database_routers.py
class PrimaryReplicaRouter:
    """
    Routes:
    - Read queries → replica
    - Write queries → primary (default)
    """
    
    def db_for_read(self, model, **hints):
        """Reads go to replica."""
        return 'replica'
    
    def db_for_write(self, model, **hints):
        """Writes go to primary."""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations within same DB."""
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migrations only on primary."""
        return db == 'default'

# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'primary-rds.amazonaws.com',
    },
    'replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'replica-rds.amazonaws.com',
        'TEST': {'MIRROR': 'default'},  # Use primary for tests
    }
}

DATABASE_ROUTERS = ['myapp.routers.PrimaryReplicaRouter']

# Usage — automatic routing:
# Booking.objects.all()           → replica (SELECT)
# Booking.objects.create(...)     → primary (INSERT)
# Booking.objects.select_for_update()  → primary (SELECT FOR UPDATE requires primary)

# Manual override when needed:
Invoice.objects.using('default').get(id=invoice_id)  # Force primary read
```

---

### 1.7 Ashish ke projects mein

```
Youngman:
  AWS RDS PostgreSQL with Multi-AZ:
  - Primary: us-east-1a (AZ-1)
  - Standby: us-east-1b (AZ-2)
  - Replication: Synchronous (zero data loss)
  - Failover: Automatic (~60 seconds)
  - This is REDUNDANCY — standby is idle normally
  
  Why not read replicas yet?
  Current traffic doesn't justify it
  Single primary handles read+write load fine
  When read traffic grows → add read replica separately

  Niroskos:
  Same RDS Multi-AZ setup
  Future plan: Add read replica for reporting queries
  (Monthly financial reports → heavy SELECT → shouldn't hit primary)
  
  Celery — Replication concept:
  RabbitMQ message queue:
    Publisher sends task to queue
    Multiple workers consume from queue
    Workers ARE replicas of processing capacity
    Worker 1 fails → Worker 2 and 3 still processing
    This is horizontal redundancy + replication concept
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Redundancy**: Duplication of a critical component with a standby that activates on failure. The standby is passive — it maintains state synchronization but does not serve traffic until failover. Eliminates single points of failure, provides fault tolerance.

> **Replication**: Maintaining multiple live copies of data/service, all actively serving traffic simultaneously. Provides both fault tolerance AND throughput scaling. Types: synchronous (zero data loss, higher latency) and asynchronous (lower latency, potential data loss).

> **Master-Slave Replication**: A write-to-one, replicate-to-many topology. The master accepts all writes; slaves receive replicated changes via WAL (PostgreSQL) or binlog (MySQL) and serve read traffic.

---

### 2.2 Redundancy vs Replication

| Dimension | Redundancy | Replication |
|-----------|-----------|-------------|
| Standby state | Passive (idle) | Active (serving traffic) |
| Primary purpose | Fault tolerance | Throughput + fault tolerance |
| Failover time | Seconds to minutes | Immediate (LB redirects) |
| Wasted capacity | Yes (standby idle) | No (all copies serve load) |
| Data sync | Real-time (sync or async) | Real-time |
| AWS example | RDS Multi-AZ standby | RDS Read Replicas |
| Use case | Database HA | Read scaling + HA |

---

### 2.3 Replication Lag and Its Impact

```
REPLICATION LAG:
  Time difference between primary write and replica reflecting it
  
  Typical values:
  - Same datacenter, async: 0-100ms
  - Cross-region, async: 10-500ms
  - Sync replication: 0ms (blocked until replica confirms)
  
  Problems caused by lag:
  1. Read-your-writes violation:
     User updates profile → reads from replica → sees old data
     
  2. Monotonic reads violation:
     User sees newer data from Replica1, then older from Replica2
  
  3. Stale data in reporting:
     Report shows yesterday's data (lag too high)
  
  Monitoring: pg_stat_replication view shows lag in bytes and time
```

---

### 2.4 Multi-Master Replication

```
MULTI-MASTER (active-active):
  Both nodes accept writes simultaneously
  More complex — write conflicts possible
  
  ┌──────────────┐ ←────→ ┌──────────────┐
  │   Master 1   │ (sync) │   Master 2   │
  │  (writes)    │        │  (writes)    │
  └──────────────┘        └──────────────┘
  
  Conflict resolution needed:
  - Last-Write-Wins (timestamp-based) — can lose writes
  - Operational Transformation (Google Docs approach)
  - CRDTs (Conflict-Free Replicated Data Types)
  
  Use cases:
  - Global apps (write locally, sync globally)
  - AWS Aurora Global Database: 1 primary region, 5 secondary (read-only)
    On failure: secondary promoted to primary (multi-master not default)
  
  Generally avoided — master-slave much simpler and usually sufficient
```

---

### 2.5 Real Project Answer

> "In our production setup at Youngman, we use AWS RDS PostgreSQL with Multi-AZ enabled — this is synchronous redundancy. The standby in a separate Availability Zone receives every write synchronously before the primary acknowledges it to the application. Failover is automated — if the primary AZ has issues, RDS promotes the standby and updates the DNS endpoint within ~60 seconds. We haven't added read replicas yet because our current read load doesn't justify it, but our database router class is already written to support it — reads would route to the replica, writes to primary. For critical queries like payment allocation, we'd force primary reads regardless, using `select_for_update()` which inherently requires the primary."

---

### 2.6 Common Follow-up Q&A

**Q1: What is the difference between RDS Multi-AZ and Read Replicas?**
> "Multi-AZ is for high availability — synchronous replication to a standby in a different AZ. The standby is passive and not accessible for reads. Its purpose is automatic failover. Read Replicas are for read scaling — asynchronous replication to one or more replicas that actively serve read traffic. You can also promote a read replica to standalone for disaster recovery. Multi-AZ = redundancy. Read Replicas = replication for throughput. You can use both simultaneously."

**Q2: How does PostgreSQL streaming replication work?**
> "PostgreSQL generates a Write-Ahead Log (WAL) for every change — it's an ordered journal of all database modifications. In streaming replication, the primary continuously ships WAL records to replicas over a persistent TCP connection. The replica replays these records in order, keeping its data in sync. In synchronous mode, the primary waits for the standby to confirm WAL receipt before returning success to the client. In async mode, it returns immediately and ships WAL in the background. The lag between primary and replica is measured by `pg_stat_replication.write_lag`."

**Q3: How do you handle the connection string after failover?**
> "AWS RDS provides a single endpoint that always points to the current primary. After failover, RDS updates the DNS record to point to the promoted standby. Existing connections are dropped (TCP reset), and the application reconnects using the same endpoint. With connection pooling (pgBouncer) or Django's persistent connections, reconnection is automatic. The key is that applications use the RDS endpoint DNS name, not a hardcoded IP — DNS TTL is low (5-30 seconds), so failover is transparent after reconnection."

---

## Interview Cheat Sheet

```
Redundancy = Passive standby (activates on failure)
  Cold: off → 5-15 min failover
  Warm: on, not serving → 30-60 sec
  Hot:  on, ready → < 30 sec
  AWS: RDS Multi-AZ = hot standby, sync replication

Replication = All copies active (serve traffic)
  Master-Slave: Master=writes, Slaves=reads
  WAL (PostgreSQL) / binlog (MySQL) = replication mechanism
  Sync = zero data loss, higher latency
  Async = lower latency, possible few-ms data loss

Failover:
  Detect → Promote replica → Update DNS → App reconnects
  Tools: Patroni (PostgreSQL), AWS RDS (automated)

Split-brain prevention:
  Quorum (majority vote), STONITH, witness node

Read Replica in Django:
  db_for_read() → 'replica'
  db_for_write() → 'default' (primary)
  select_for_update() always hits primary

My setup:
  RDS Multi-AZ: sync redundancy, 60-sec auto-failover
  Read replicas: not yet — will add for reporting queries
```
