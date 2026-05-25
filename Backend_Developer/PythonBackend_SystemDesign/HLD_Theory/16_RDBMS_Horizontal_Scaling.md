# RDBMS Horizontal Scaling — Why Hard? Sharding, Read Replicas

## Quick Reference Card
```
RDBMS scale up   → Vertical scaling — bigger machine (simpler, try first)
Read replicas    → Horizontal reads — 80% traffic goes here
Sharding         → Split data across multiple DBs by shard key
Consistent hash  → Even distribution + minimal resharding on node add/remove
Cross-shard join → IMPOSSIBLE in SQL — application-level merge needed
Interview hook   → "PostgreSQL vertical scaling first; read replicas for reports; sharding = last resort"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 RDBMS Horizontal Scaling Kyun Mushkil Hai?

**Analogy: Library ke books**

Library mein books hain. Ek librarian (DB) sab kuch jaanta hai — "Mathematics ki kitaab shelf C5 pe hai, Fiction shelf A3 pe hai." Koi bhi book kahin bhi link ho sakti hai. Ek librarian ke paas poori library ki knowledge hai.

Ab socho — 2 alag librarians (2 DB servers), aur books dono ke beech split kar diye:
- Librarian 1: Mathematics, Science books
- Librarian 2: Fiction, History books

User aata hai: "Mujhe ek fiction book chahiye jo science ke chapter mein bhi mention hai"
→ Librarian 1 aur Librarian 2 dono se consult karna padega → COMPLEX!

```
WHY HORIZONTAL SCALING IS HARD FOR RDBMS:

1. ACID Transactions:
   UPDATE bank_account SET balance = balance - 100 WHERE user=A
   UPDATE bank_account SET balance = balance + 100 WHERE user=B
   
   Agar A aur B alag shards pe hain:
   → Distributed transaction needed (2-Phase Commit — slow, complex)
   → If one shard fails mid-transaction → rollback kaise? (2PC failures)

2. JOINs across shards:
   SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.id
   
   Agar orders shard1 pe hain aur users shard2 pe:
   → Database JOIN impossible → Application-level merge (slow, complex)

3. Foreign Key Constraints:
   orders.user_id → users.id (FK)
   Agar alag shards pe hain → FK enforcement impossible

4. Schema changes:
   ALTER TABLE across all shards → coordinate, test, rollback complex

5. Hot spots:
   Agar shard key poorly chosen → ek shard pe zyada load
   (e.g., Shard by alphabetical — users starting with 'S' are most → S shard overloaded)
```

---

### 1.2 Scaling Journey — Order of Operations

```
STEP 1: Vertical Scaling (Try This First!)
  Upgrade DB server: t3.medium → r5.xlarge
  Cost: $$
  Complexity: Zero (just resize)
  Covers: 90% of companies
  
STEP 2: Connection Pooling
  pgBouncer: Reuse DB connections
  Django CONN_MAX_AGE: Persistent connections
  Reduces: Connection establishment overhead
  
STEP 3: Query Optimization
  EXPLAIN ANALYZE slow queries
  Add missing indexes
  Fix N+1 queries (prefetch_related, select_related)
  Often: 10-100x speedup from proper indexing!
  
STEP 4: Read Replicas
  Writes → Primary
  Reads → Replica(s)
  70-80% traffic is reads → significant improvement
  
STEP 5: Caching Layer
  Redis in front of DB
  Cache expensive queries (package listings, reports)
  Hit rate 80%+ → DB sees 80% less read traffic
  
STEP 6: Vertical Scaling Again
  r5.xlarge → r5.4xlarge → r5.16xlarge
  Millions of queries/day still manageable on big single instance
  
STEP 7: Sharding (Last Resort!)
  Only when all above exhausted
  Pinterest: 500 million users before sharding
  Shopify: Shards after massive growth
  Most companies NEVER need sharding
```

---

### 1.3 Read Replicas — Horizontal Read Scaling

```
READ REPLICA SETUP:
  
  ALL WRITES → Primary DB
                  │
                  │ WAL streaming (async replication)
                  ├──────────────────────┐
                  ▼                      ▼
           Replica 1               Replica 2
           (READS)                 (READS + Reporting)

WHAT TO ROUTE WHERE:
  → Primary:
    INSERT, UPDATE, DELETE (all writes)
    SELECT FOR UPDATE (requires lock → must be primary)
    Financial calculations (need latest data)
    Booking creation (consistency critical)
  
  → Replica:
    Dashboard queries (slight staleness ok)
    Reports and analytics
    Product listings, package search
    User profiles (read-heavy, rarely written)
    Admin reports

REPLICATION LAG:
  Typical: 0-100ms (same region, async)
  Impact: User writes → 50ms → might not see own write on replica
  Fix: Route user's own reads to primary for 1-2 seconds after their write
       (Read-your-writes consistency pattern)

Django implementation:
  # See 11_Redundancy_vs_Replication.md for full router code
  # Quick version:
  DATABASE_ROUTERS = ['app.routers.PrimaryReplicaRouter']
  
  class PrimaryReplicaRouter:
      def db_for_read(self, model, **hints):
          return 'replica'
      def db_for_write(self, model, **hints):
          return 'default'
```

---

### 1.4 Sharding — Horizontal Write Scaling

**Sharding = Data ko multiple databases mein split karo**

```
SHARD BY USER_ID (Horizontal sharding):

  User ID 1-1M   → Shard 1 (DB Server 1)
  User ID 1M-2M  → Shard 2 (DB Server 2)
  User ID 2M-3M  → Shard 3 (DB Server 3)
  
  Application code:
  def get_shard(user_id):
      shard_num = user_id % 3  # Modulo hash
      return SHARDS[shard_num]
  
  User ID 4567 → 4567 % 3 = 1 → Shard 1
  User ID 5001 → 5001 % 3 = 2 → Shard 2
  User ID 6000 → 6000 % 3 = 0 → Shard 0

Problem with modulo: If you add a 4th shard
  User ID 4567 → 4567 % 4 = 3 → NOW Shard 3! (changed!)
  ALL data needs resharding → massive migration!
```

---

### 1.5 Consistent Hashing — Resharding Problem Solution

```
CONSISTENT HASHING:
  Imagine a ring (0 to 2^32)
  
  Servers placed on ring:
  Server A: hash("serverA") = position 50
  Server B: hash("serverB") = position 150  
  Server C: hash("serverC") = position 250
  
  Key → hash → position on ring → closest server clockwise
  
  Key "user:4567" → hash = 75 → Server B (position 150, next clockwise)
  Key "user:5001" → hash = 170 → Server C (position 250, next clockwise)
  Key "user:6000" → hash = 275 → Server A (position 50, wraps around)
  
  ADD Server D at position 200:
  
  Before: Keys 150-250 → Server C
  After:  Keys 150-200 → Server D, Keys 200-250 → Server C
  
  Only keys in range 150-200 need to move from C → D
  ~25% data moves (not 100% like with modulo!)
  
  For k keys and n nodes:
  Adding 1 node: Only k/n keys need to move (not all!)

VIRTUAL NODES (vnodes):
  Problem: Servers might cluster on ring → uneven distribution
  Solution: Each server gets 100-200 virtual positions on ring
  Server A: positions 50, 120, 310, 450 (multiple points)
  
  Result: More even distribution
  Also: When a server fails, its load spreads to MULTIPLE servers (not one)

  This is how Cassandra and DynamoDB distribute data.
```

---

### 1.6 Shard Key Selection

```
GOOD SHARD KEYS:

1. User ID:
   Most queries involve a specific user → stays on single shard
   Good distribution (uniform IDs)
   User's data colocated → joins work within shard
   ✓ Best for multi-tenant apps (Niroskos: per-customer data)

2. Geography:
   India users → India shard
   Kenya users → Kenya shard  
   Legal compliance (data residency requirements)
   ✓ Good for global apps with regional requirements

3. Tenant ID (for SaaS):
   Company A → Shard 1
   Company B → Shard 2
   Company's data fully on one shard → clean isolation
   ✓ Easy to scale large companies to dedicated shard

BAD SHARD KEYS:

1. Timestamp (monotonically increasing):
   All new data → last shard
   Hot spot! Last shard = write bottleneck
   ✗ Never use timestamp as primary shard key

2. Status (active/inactive):
   active → Shard 1 (overloaded!)
   inactive → Shard 2 (underutilized)
   ✗ Low cardinality = terrible distribution

3. Sequential ID from single sequence:
   ID 1 → Shard 1, ID 2 → Shard 2, ID 3 → Shard 3 (round robin)
   No colocation → cross-shard queries for everything
   ✗ Very bad — every query needs multiple shards

IDEAL SHARD KEY:
  High cardinality (many unique values)
  Even distribution
  Query locality (queries mostly touch one shard)
  Stable (value doesn't change after write)
```

---

### 1.7 Cross-Shard Problems

```
CROSS-SHARD JOIN (problem):
  Normal SQL:
  SELECT b.*, u.email FROM bookings b
  JOIN users u ON b.user_id = u.id
  WHERE b.created_at > '2024-01-01'
  
  With sharding (users on Shard A, B, C based on user_id):
  Bookings for recent period could span ALL shards
  Can't do SQL JOIN across shards
  
  Solution: Application-level merge
  
  # Fetch from all shards, merge in memory
  all_bookings = []
  for shard in [shard_a, shard_b, shard_c]:
      bookings = shard.query("SELECT * FROM bookings WHERE created_at > ...")
      all_bookings.extend(bookings)
  
  user_ids = [b.user_id for b in all_bookings]
  # Group by shard
  users = {}
  for shard in [shard_a, shard_b, shard_c]:
      for user in shard.query(f"SELECT * FROM users WHERE id IN ({user_ids_for_shard})"):
          users[user.id] = user
  
  # Merge
  results = [(b, users[b.user_id]) for b in all_bookings]
  
  PROBLEMS with this:
  - Application becomes complex
  - N queries instead of 1
  - Pagination hard across shards
  - Aggregates (COUNT, SUM) need per-shard then merge

AGGREGATION ACROSS SHARDS:
  SELECT COUNT(*) FROM bookings WHERE status='active'
  
  → Query each shard separately
  → SUM the counts
  → Works! But N database queries

REPORTING DATABASE:
  Common pattern for cross-shard reporting:
  All shards → ETL pipeline → Single analytical DB (no sharding)
  Report queries → analytical DB
  Operational queries → shards
  
  Delay: 1-5 minutes (ETL lag acceptable for reports)
```

---

### 1.8 Ashish ke projects mein

```
Youngman:
  Current: Single PostgreSQL RDS instance (db.t3.medium)
  
  Scaling path taken:
  1. Query optimization: Added indexes → 5x speedup on invoice queries
  2. select_related / prefetch_related → Fixed N+1 queries
  3. bulk_create for monthly invoice batch → 12x faster bulk generation
  4. CONN_MAX_AGE = 60 → Persistent connections (no reconnect overhead)
  5. Vertical scaling: t2.micro → t3.medium
  
  NOT needed yet: Read replicas, sharding
  When to add read replica: Monthly report generation consuming DB resources
  
  If sharding ever needed (not yet):
  Shard key: company_id (multi-tenant — each company's data colocated)

Niroskos:
  Booking data: user_id as natural shard key (if ever needed)
  But current scale: Single PostgreSQL handles fine
  
  Key realization: Most companies at startup/mid scale don't need sharding.
  Instagram ran on 1 PostgreSQL for first 2 years (400M photos).
  Shopify: Sharded MySQL only after reaching billions in GMV.
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Horizontal Scaling of RDBMS**: Distributing relational database load across multiple servers. The fundamental challenge is that RDBMS features (ACID transactions, foreign keys, JOINs) assume a single shared data store. Solutions: read replicas (scale reads), sharding (scale writes), caching (reduce DB load).

> **Sharding**: Partitioning data horizontally across multiple database instances based on a shard key. Each shard holds a subset of rows; the application routes queries to the appropriate shard. Enables horizontal write scaling but introduces cross-shard query complexity.

> **Consistent Hashing**: A hashing scheme where adding/removing nodes only redistributes a fraction (k/n) of keys, rather than all keys as with modulo hashing. Used in distributed caches and sharded databases for minimal resharding impact.

---

### 2.2 Scaling Strategies Comparison

| Strategy | What It Scales | Complexity | When to Use |
|----------|---------------|------------|-------------|
| Vertical scaling | Read + Write | None | Always try first |
| Query optimization | Read + Write | Low | Always — huge ROI |
| Connection pooling | Read + Write | Low | ~100+ RPS |
| Caching (Redis) | Reads | Low-Medium | Hot data exists |
| Read replicas | Reads only | Medium | Read:Write > 4:1 |
| Sharding | Reads + Writes | Very High | Extreme scale only |
| NewSQL (Spanner, CockroachDB) | Reads + Writes | Medium | Need SQL + global |

---

### 2.3 Consistent Hashing Details

```
Properties:
  - N servers: each handles ~1/N of load
  - Add 1 server: Only 1/N keys reshuffled
  - Remove 1 server: Only 1/N keys redistributed

  vs. Modulo hashing:
  - Add 1 server: ALL keys potentially reshuffled
  
  Formula: When n nodes → n+1:
  Keys reshuffled = K / (n+1)  [only 1/(n+1) fraction]
  
  vs. Modulo: All K keys may need to move

  Virtual nodes (vnodes):
  - Each physical node gets V virtual positions on ring
  - Better load distribution
  - Smaller key ranges per physical node
  - Cassandra default: 256 vnodes per node
```

---

### 2.4 Real Project Answer

> "In Youngman's PostgreSQL setup, our scaling story is about doing the simpler things first. We identified N+1 queries using Django's query inspector and fixed them with `select_related` and `prefetch_related`. We added composite indexes on our most queried combinations — the invoice list query went from 500ms to 20ms just from indexing. We upgraded the instance from t2.micro to t3.medium as user count grew. These steps alone handled our scale needs without any architectural changes. If read replicas become necessary — likely when monthly report generation starts impacting operational queries — we've already written the database router that would route report queries to a replica. We explicitly avoid premature sharding because the cross-shard JOIN problem would make our booking queries that join across 4-5 tables extremely complex."

---

### 2.5 Common Follow-up Q&A

**Q1: How do distributed transactions work in sharded databases?**
> "Distributed transactions use Two-Phase Commit (2PC): Phase 1 (Prepare) — coordinator asks all shards 'Can you commit?' Each shard writes to its WAL and votes yes/no. Phase 2 (Commit/Abort) — if all voted yes, coordinator sends commit. If any voted no, all abort. Problem: If coordinator crashes between phases → shards might be in inconsistent states. This is why distributed transactions are rare in production — the failure modes are complex. Common alternative: Saga pattern — break transaction into local transactions with compensating transactions for rollback. E.g., booking: reserve seat → charge payment → confirm booking. If payment fails: reverse seat reservation (compensating)."

**Q2: What is the difference between vertical and horizontal partitioning?**
> "Horizontal partitioning = sharding = splitting rows. Same table schema, different rows go to different shards based on shard key. Vertical partitioning = splitting columns. Put frequently accessed columns in one table/DB (hot data), rarely accessed in another (cold data). Example: `user` table split into `user_core` (id, name, email — queried always) and `user_profile` (bio, preferences — queried rarely). Vertical partitioning reduces row size, improves cache efficiency for hot queries. Horizontal is for scale; vertical is for access pattern optimization."

**Q3: When would you use NewSQL instead of sharding?**
> "NewSQL databases (Google Spanner, CockroachDB, TiDB) provide horizontal scalability with full SQL support and ACID guarantees. They use distributed consensus (Paxos/Raft) and distributed transactions natively. If you need: full SQL with JOINs, ACID transactions, and horizontal write scaling — NewSQL is compelling versus manual sharding. Trade-offs: higher latency (consensus overhead), less mature ecosystem, higher operational cost. For Youngman's scale, standard PostgreSQL with careful optimization handles everything. At Shopify-scale write volumes with global distribution, Spanner becomes attractive."

---

## Interview Cheat Sheet

```
Why RDBMS horizontal scaling is hard:
  1. ACID transactions (distributed txn = 2PC = slow + complex)
  2. JOINs across shards = impossible in SQL
  3. Foreign key constraints can't cross shards
  4. Hot spots from poor shard key

Scaling order (always follow!):
  1. Query optimization (indexes, N+1 fixes)
  2. Connection pooling (pgBouncer, CONN_MAX_AGE)
  3. Vertical scaling (upgrade instance)
  4. Caching (Redis in front of DB)
  5. Read replicas (horizontal reads)
  6. Sharding (last resort — extreme scale only)

Read Replicas:
  Primary → writes, Replicas → reads
  80% traffic = reads → big win
  Replication lag: 0-100ms (async)
  Router: db_for_read() → 'replica'

Sharding:
  Shard key: user_id, tenant_id, geography
  Consistent hashing: k/n keys reshuffled on node add
  Virtual nodes: better distribution
  
  BAD keys: timestamp (hot spot), low cardinality (skewed load)

Cross-shard problems:
  JOINs → application-level merge
  Aggregates → per-shard then sum
  Reports → separate analytics DB (ETL)

My project:
  PostgreSQL single instance
  Optimizations: indexes, prefetch_related, bulk_create
  Scaled: t2.micro → t3.medium (vertical)
  Read replica: planned for reporting queries
  Sharding: not needed at current scale
```
