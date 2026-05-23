# CAP Theorem

## Quick Reference Card
```
CAP         → Consistency + Availability + Partition Tolerance — pick 2
Reality     → Partition ALWAYS possible → real choice is C vs A during partition
CP systems  → Consistency + Partition Tolerance — bank, payment (accurate > available)
AP systems  → Availability + Partition Tolerance — social media, DNS (available > accurate)
CA systems  → Only possible in single-node / same datacenter (no partition tolerance)
Interview hook → "CAP theorem ke basis pe design karte hain — payment = CP, search = AP"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai CAP Theorem?

**2000 mein Eric Brewer ne prove kiya:** Distributed system mein teen guarantees simultaneously dena impossible hai — sirf do mili sakti hain.

**C — Consistency (Samai Data)**
> Har read latest write return karta hai. Koi bhi node same time pe same data dikhata hai.

**A — Availability (Hamesha Jawab)**
> Har request ka response milega — chahe "error" ho lekin "no response" nahi hoga.

**P — Partition Tolerance (Network Fail Ho Toh Bhi)**
> Network partition (two servers communicate nahi kar sakte) ke bawajood system kaam karta rahega.

---

### 1.2 Analogy — Bank ke 2 Branches

```
Branch A (Mumbai) ←── Network Cut ──→ Branch B (Delhi)

Customer X: Branch A pe ₹10,000 withdraw karta hai

Now at same time:
Customer Y: Branch B pe check karta hai balance

PROBLEM:
  Branch B abhi nahi jaanta ki Branch A ne ₹10,000 diya
  Communication cut hai

CHOICE:
  Option 1 (CP): Branch B "Sorry, network down — can't process"
                 → Consistent (won't show wrong data)
                 → NOT Available (request rejected)
  
  Option 2 (AP): Branch B ₹10,000 dikhata hai (stale data)
                 → Available (gives some answer)
                 → NOT Consistent (wrong balance!)
```

---

### 1.3 Why "Pick 2" is Misleading

```
Real situation:
  Network partitions WILL happen in distributed systems
  (Hardware fails, cables cut, routing issues)
  
  So P (Partition Tolerance) is NOT optional
  You MUST handle partitions or your system is unreliable
  
  Real choice: When partition happens, do you sacrifice C or A?

BETTER way to think:
  "During a network partition, prefer Consistency or Availability?"
  
  CP: During partition → return error (sacrifice availability)
  AP: During partition → return possibly stale data (sacrifice consistency)
```

---

### 1.4 CP Systems

```
CP = Consistent + Partition Tolerant
   = During partition: return error / wait
   = Sacrifice availability for correctness

When network partition:
  ┌──────────┐   X   ┌──────────┐
  │  Node 1  │───────│  Node 2  │
  │ (primary)│       │ (replica)│
  └──────────┘       └──────────┘
  
  CP system:
  - Node 2 can't reach Node 1
  - Node 2 STOPS accepting writes (might create inconsistency)
  - Returns: "Service unavailable" or waits for partition to heal
  - Correctness guaranteed!

Examples:
  - HBase, Zookeeper, Redis (in cluster mode)
  - Traditional RDBMS (PostgreSQL with sync replication)
  - Niroskos payment processing

Use when: Data correctness > temporary unavailability
  ✓ Banking transactions
  ✓ Booking systems (no double sell)
  ✓ Inventory management
  ✓ Authentication/login
```

---

### 1.5 AP Systems

```
AP = Available + Partition Tolerant
   = During partition: return possibly stale data
   = Sacrifice consistency for availability

When network partition:
  ┌──────────┐   X   ┌──────────┐
  │  Node 1  │───────│  Node 2  │
  │ (primary)│       │ (replica)│
  └──────────┘       └──────────┘
  
  AP system:
  - Node 2 can't reach Node 1
  - Node 2 STILL accepts reads (returns possibly stale data)
  - Returns: value from its own copy (may be outdated)
  - Always available, possibly inconsistent!

Examples:
  - Cassandra, DynamoDB (default), CouchDB
  - DNS (returns cached IPs even if origin unreachable)
  - Amazon shopping cart

Use when: Temporary inconsistency acceptable
  ✓ Social media feeds
  ✓ Product search/listing
  ✓ View counts, likes
  ✓ Shopping cart
  ✓ User preferences/settings
```

---

### 1.6 CA Systems (Not really distributed)

```
CA = Consistent + Available (no partition tolerance)
   = Assumes network never partitions
   = Only possible within single datacenter OR single server

Examples:
  - Single PostgreSQL server
  - Traditional RDBMS on one machine
  - LDAP directory

Reality: In distributed systems, partitions WILL happen
         CA is not a practical choice for distributed setups
         
CA is misleading — most "CA databases" are just single-node
or assume perfect network (not realistic for production)
```

---

### 1.7 PACELC Theorem — CAP ka Extension

```
CAP problem: Only talks about partition scenario

PACELC adds:
  Even without partition:
  - Latency vs Consistency trade-off exists!

PACELC:
  During Partition: choose A or C (like CAP)
  Else (normal): choose L (Latency) or C (Consistency)

  PA/EL: Available during partition + Low latency normally
         (Cassandra, DynamoDB default)
  
  PC/EC: Consistent during partition + Consistent normally
         (Spanner, VoltDB)
  
  PA/EC: Available during partition + Consistent normally
         (MySQL Cluster, DynamoDB strong reads)

More realistic than CAP for system design decisions!
```

---

### 1.8 Database CAP Classification

```
CP Databases:
  ┌────────────────────────────────────────────┐
  │ HBase, Zookeeper, Redis Cluster            │
  │ MongoDB (default: strong consistency mode) │
  │ Etcd                                       │
  └────────────────────────────────────────────┘

AP Databases:
  ┌────────────────────────────────────────────┐
  │ Cassandra, DynamoDB (default), CouchDB     │
  │ Riak                                       │
  └────────────────────────────────────────────┘

CA (Single-node / non-distributed):
  ┌────────────────────────────────────────────┐
  │ PostgreSQL (single node)                   │
  │ MySQL (single node)                        │
  └────────────────────────────────────────────┘

Note: PostgreSQL with Patroni HA → CP
      PostgreSQL read replicas → AP for reads
```

---

### 1.9 Ashish ke projects mein

```python
# Niroskos — CAP decisions documented in code comments

# PAYMENT: CP — consistency over availability
class PaymentService:
    def allocate_payment(self, booking_id, amount):
        """
        CAP Choice: CP
        During network issue → fail with error (don't risk double allocation)
        """
        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update(
                    nowait=True  # Raise exception if can't lock (don't wait)
                ).get(id=booking_id)
                
                if booking.is_fully_paid:
                    raise AlreadyPaidError()
                
                # Allocate...
                
        except OperationalError:
            # DB lock unavailable → return error (CP behavior)
            raise ServiceUnavailableError("Payment service busy, retry")

# SEARCH: AP — availability over consistency
class PackageSearchService:
    def search(self, query):
        """
        CAP Choice: AP
        If Typesense unreachable → fall back to cached results (stale is ok)
        """
        try:
            return typesense_client.collections['packages'].documents.search(...)
        except Exception:
            # Typesense down → return cached results (AP behavior)
            cached = redis.get(f'search_fallback:{hash(query)}')
            return json.loads(cached) if cached else []
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **CAP Theorem** (Brewer's Theorem, 2000): A distributed data store can provide at most two of three guarantees simultaneously: **Consistency** (every read receives the most recent write), **Availability** (every request receives a non-error response), and **Partition Tolerance** (the system continues operating despite network partitions). Since network partitions are inevitable in distributed systems, the practical choice is between Consistency and Availability during partition events.

---

### 2.2 CAP Triangle

```
         Consistency
              C
             /|\
            / | \
           /  |  \
          / CA|   \
         /    |    \
        /_____|_____\
       A      P      P
    Availability  Partition
                  Tolerance
    
    CP: Sacrifice Availability during partition
    AP: Sacrifice Consistency during partition
    CA: Sacrifice Partition Tolerance (impractical for distributed)
```

---

### 2.3 How to Choose CP vs AP

| Question | Choose CP | Choose AP |
|----------|-----------|-----------|
| What happens if stale data read? | Financial loss / data corruption | Minor UX glitch |
| User expects perfect accuracy? | Yes (bank balance) | No (social feed) |
| Can we retry on error? | Yes | Retry not great for UX |
| Data correctable later? | Hard (transactions) | Yes (reconciliation) |
| Regulatory requirement? | Yes (finance, medical) | No |

---

### 2.4 Modern Databases: Tunable Consistency

```python
# Many modern databases allow per-operation consistency tuning

# DynamoDB:
response = table.get_item(
    Key={'id': booking_id},
    ConsistentRead=True   # Strong consistency (CP behavior)
    # ConsistentRead=False → Eventually consistent (AP, cheaper)
)

# Cassandra:
# Per-query consistency level
session.execute(query, consistency_level=ConsistencyLevel.QUORUM)  # Strong
session.execute(query, consistency_level=ConsistencyLevel.ONE)     # Weak

# MongoDB:
db.collection.find({}, read_concern={'level': 'majority'})  # CP-like
db.collection.find({}, read_concern={'level': 'local'})     # AP-like
```

---

### 2.5 Real Project Answer

> "In Niroskos, we make explicit CAP choices per feature. Payments and booking creation use CP: PostgreSQL with transactions and select_for_update — during any failure, we return an error rather than risk duplicate payments or double bookings. This is the right choice because stale payment data has real financial consequences. However, our package search via Typesense uses AP: if Typesense is temporarily unavailable, we fall back to cached results, accepting that search results might be slightly stale. This keeps the browse experience smooth even during search service issues. The business impact of a temporarily stale search result is negligible compared to a search page returning 503."

---

### 2.6 Common Follow-up Q&A

**Q1: Does the CAP theorem mean NoSQL > SQL?**
> "No, that's a common misconception. CAP applies to distributed systems — when you distribute data across multiple nodes. A single PostgreSQL server doesn't face the CAP trade-off. The choice of SQL vs NoSQL should be driven by data model, query patterns, and scale requirements. PostgreSQL with read replicas gives you AP for reads and CP for writes. Cassandra gives you AP for both. The right tool depends on your use case."

**Q2: Can a system be both CP and AP?**
> "Not simultaneously for the same operation during a partition. However, many systems allow you to choose per-operation. DynamoDB supports both consistent reads (CP) and eventually consistent reads (AP) — you choose per query. This tunable consistency is more practical than system-wide classification. Modern distributed databases like Google Spanner use TrueTime to provide strong consistency globally, but at higher cost."

**Q3: What is quorum in the context of CAP?**
> "Quorum is (N/2)+1 nodes in a cluster — the majority. For writes to succeed, a quorum must confirm. For reads to be consistent, a quorum must respond. Example: 3-node cluster, quorum=2. Write to 2 nodes → consistent write. Read from 2 nodes → at least one has latest data. This is how Cassandra and DynamoDB achieve tunable consistency. Higher quorum = more consistency, lower availability. Lower quorum = more availability, weaker consistency."

---

## Interview Cheat Sheet

```
CAP = Consistency + Availability + Partition Tolerance
→ Pick 2 (but P is mandatory → real choice: C vs A during partition)

CP (Consistent + Partition Tolerant):
  During partition → return error (sacrifice availability)
  Examples: HBase, Zookeeper, Redis Cluster
  Use: Banking, payments, bookings

AP (Available + Partition Tolerant):
  During partition → return stale data (sacrifice consistency)
  Examples: Cassandra, DynamoDB default, DNS
  Use: Social feeds, search, view counts

PACELC: Even without partition → Latency vs Consistency trade-off

My project:
  CP: Payments (PostgreSQL txn + select_for_update) → error on conflict
  AP: Search (Typesense → Redis fallback) → stale results ok

Key line for interview:
"CAP theorem means during network issues, we must choose
 between serving wrong data (AP) or no data (CP).
 We choose per business feature based on cost of staleness."
```
