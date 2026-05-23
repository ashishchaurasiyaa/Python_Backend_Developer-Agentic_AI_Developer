# Consistency — Strong vs Eventual Consistency

## Quick Reference Card
```
Consistency   → Sabhi nodes ek hi time pe same data dikhate hain
Strong        → Read always returns latest write — banking, payments
Eventual      → Lagbhag sab nodes sync ho jaayenge — DNS, social feeds
Linearizable  → Strongest form — reads see all previous writes globally
Causal        → Related operations same order mein dikhate hain
Read-your-writes → Apna likha hua khud padh sako
Interview hook → "Niroskos: Payment = strong consistency | Search cache = eventual"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai Consistency?

**Analogy: Whatsapp group**

Tum group mein message bhejte ho "Party cancelled":
- **Strong consistency**: Sabhi members ka WhatsApp immediately "Party cancelled" dikhata hai
- **Eventual consistency**: Kuch members ko pehle dikha, kuch ko 2 seconds baad, kuch ko 10 seconds baad — but eventually sab ko dikha

Distributed system mein:
- Data multiple servers pe store hota hai (replicas)
- Write ek server pe hota hai
- Consistency define karta hai: **baaki servers kab updated dikhate hain?**

---

### 1.2 Consistency Levels — Spectrum

```
STRICT / LINEARIZABLE ←────────────────────────→ EVENTUAL
     (Strongest)                                  (Weakest)

Linearizable → Single-copy semantics globally
    │
Strong Consistency
    │         → After write, any read sees it
Sequential Consistency
    │         → All nodes see operations in same order
Causal Consistency
    │         → Causally related ops in same order
Read-Your-Writes
    │         → You always read your own writes
Monotonic Reads
    │         → Don't see older data after seeing newer
Eventual Consistency
              → Given no more writes, all nodes converge
```

---

### 1.3 Strong Consistency — Deep Dive

```
STRONG CONSISTENCY:
─────────────────
After a write completes, any subsequent read (from ANY node)
returns the latest written value.

Timeline:
  t=0: DB1=100, DB2=100 (both synchronized)
  t=1: User A: WRITE balance=50 → Primary DB
  t=2: User B: READ balance → from Replica
       Returns: 50 ✓ (not 100, not stale)

How achieved:
  - Synchronous replication (wait for all replicas to confirm)
  - OR: Route all reads to primary only (no stale reads)
  - Quorum reads: Read from majority of nodes

Cost:
  - Higher latency (wait for all replicas)
  - Lower availability (if replica unreachable → can't proceed)

Use cases:
  - Payment processing (balance must be accurate)
  - Seat booking (no double booking)
  - Account login (password must be current)
  - Inventory management (no overselling)
```

**Niroskos payment:**
```python
# MUST be strongly consistent
# Wrong balance = wrong charge / failed refund

def process_payment(booking_id, amount):
    with transaction.atomic():
        # Lock the account row (SELECT FOR UPDATE)
        account = Account.objects.select_for_update().get(id=account_id)
        
        if account.balance < amount:
            raise InsufficientFundsError()
        
        account.balance -= amount
        account.save()
        
        # All in one transaction — atomic, isolated
        PaymentRecord.objects.create(booking_id=booking_id, amount=amount)
    
    # PostgreSQL default: READ COMMITTED
    # Our payment code: SERIALIZABLE (strongest isolation)
```

---

### 1.4 Eventual Consistency — Deep Dive

```
EVENTUAL CONSISTENCY:
────────────────────
If no new writes happen, eventually all nodes will converge
to the same value. But temporarily, different nodes may
show different values.

Timeline:
  t=0:  DB1=100 (primary), DB2=100, DB3=100
  t=1:  User A: WRITE DB1 → balance=50
  t=2:  DB1=50, DB2=100 (stale!), DB3=100 (stale!)
  t=3:  Replication lag...
  t=5:  DB1=50, DB2=50, DB3=50 ← eventually consistent!

During t=2 to t=5: User B reads DB2 → sees 100 (stale!)

Acceptable when:
  - Stale data is okay for a short time
  - Performance > perfect accuracy

Use cases:
  - DNS propagation (takes hours)
  - Social media feed (friend's post appearing)
  - Search index (new product in search)
  - Shopping cart (add to cart, view later)
  - View counts, like counts

Not acceptable for:
  - Money transfer
  - Ticket booking (limited inventory)
  - Medical records
```

**Niroskos search (eventual is ok):**
```python
# Package search via Typesense
# New package added → signal triggers Typesense index update
# For 5-10 seconds → search might not show new package
# User won't even notice — acceptable!

@receiver(post_save, sender=Package)
def update_search_index(sender, instance, **kwargs):
    # Async task — eventual consistency acceptable
    update_typesense_index.delay(instance.id)
    # If this task runs 5 seconds later → 5 second eventual consistency window
```

---

### 1.5 Read-Your-Writes Consistency

```
Common problem:
  User posts a tweet
  Server writes to primary DB
  User refreshes feed
  Read goes to replica (replication lag = 100ms)
  User doesn't see their own tweet!
  
  "Why didn't my post appear??" — bad UX

Solution: Read-Your-Writes guarantee
  After a user writes, subsequent reads for THAT USER
  go to primary until replica catches up.

  Implementation:
  - Session-based: Store write timestamp in session
    If now - last_write < replication_lag → read from primary
    Otherwise → read from replica
  
  - User-specific sticky reads: User X's reads always
    hit the same replica that received their write

Django implementation:
from django.db import connections

def get_queryset_for_user(user, operation):
    if user.has_recent_write():
        # Route to primary
        return Booking.objects.using('default')
    else:
        # Route to replica (read-heavy operations)
        return Booking.objects.using('replica')
```

---

### 1.6 Monotonic Reads

```
Problem without Monotonic Reads:
  t=1: User reads from Replica1 → sees message at 3pm
  t=2: User reads from Replica2 → sees message at 2pm (older!)
  
  "The message I just saw disappeared!" — confusing

Monotonic Read guarantee:
  Once you read a value, subsequent reads never return older values.
  
  Implementation:
  - Sticky routing: Same user always hits same replica
  - Version vector: Track what version user last saw,
    only serve from replicas that have that version
```

---

### 1.7 Causal Consistency

```
Problem:
  Alice: "I got promoted!" (post A)
  Bob: "Congratulations!" (post B, in reply to A)
  
  Without causal consistency:
  Carol sees: "Congratulations!" (B)
  Then: "I got promoted!" (A)
  ← Reads in wrong causal order!

Causal Consistency:
  If A causally precedes B (B is a reply to A),
  then any node that shows B must also show A first.

  Implementation: Vector clocks / version vectors
  Each message tagged with causal dependencies
```

---

### 1.8 Ashish ke projects mein

```
STRONG CONSISTENCY needed:
  ✓ Payment allocation (balance, ledger)
  ✓ Booking creation (no double booking)
  ✓ Invoice creation + SAP push
  
  Implementation: PostgreSQL transactions, select_for_update()

EVENTUAL CONSISTENCY acceptable:
  ✓ Typesense search index (5-10 sec delay ok)
  ✓ Redis cache for package listings
  ✓ SAP customer sync (slight delay ok)
  ✓ Notification delivery (slight delay ok)
  
  Implementation: Celery async tasks, Django signals
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Strong Consistency**: After a write completes, all subsequent reads from any node return that written value. Provides single-copy semantics — equivalent to a single server. Achieved via synchronous replication or routing reads to primary only.

> **Eventual Consistency**: A liveness guarantee — given sufficient time without new writes, all replicas will converge to the same value. Allows temporary divergence between replicas in exchange for lower latency and higher availability.

---

### 2.2 Consistency Models Comparison

| Model | Guarantee | Latency | Availability | Use Case |
|-------|-----------|---------|--------------|----------|
| Linearizable | Real-time ordering globally | Highest | Lowest | Financial txns |
| Strong | All reads see latest write | High | Low-Medium | Payments, bookings |
| Causal | Related ops ordered | Medium | Medium | Social media |
| Read-your-writes | Own writes visible | Low-Medium | High | User profiles |
| Monotonic reads | Never see older data | Low | High | Feeds |
| Eventual | Converges eventually | Lowest | Highest | DNS, caches, likes |

---

### 2.3 Consistency vs Isolation (Don't confuse!)

```
CONSISTENCY (distributed) → Same data across multiple servers/replicas
  "All replicas agree on the value"
  CAP theorem's C

ISOLATION (transactions) → Concurrent transactions don't interfere
  "One transaction doesn't see another's partial effects"
  ACID's I — levels: READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE

These are different:
  Consistency = replication agreement
  Isolation = transaction concurrency control
  
  Strong consistency + Serializable isolation = maximum guarantees
  Both needed for payment processing
```

---

### 2.4 Implementing Eventual Consistency Safely

```python
# Anti-entropy: periodic reconciliation job
# Even if async replication fails, a scheduled job finds and fixes differences

class DataReconciler:
    """
    Compare primary and replica, fix discrepancies
    Used as a safety net for eventually consistent systems
    """
    
    def reconcile(self, table: str):
        primary_checksum = self.compute_checksum(table, 'primary')
        replica_checksum = self.compute_checksum(table, 'replica')
        
        if primary_checksum != replica_checksum:
            rows = self.find_divergent_rows(table)
            self.sync_rows(rows, source='primary', target='replica')
            self.alert_ops(f"Divergence detected in {table}")
```

---

### 2.5 Real Project Answer

> "In Niroskos, we use different consistency levels for different parts of the system based on business requirements. Payments and booking creation use strong consistency via PostgreSQL transactions with select_for_update — a double booking would be a critical business failure. However, our Typesense search index uses eventual consistency — a new package appearing in search results 5-10 seconds after creation is perfectly acceptable. The search index is updated via Celery background task triggered by a Django post_save signal. This gives us the best of both worlds: correctness where it matters, performance where it doesn't."

---

### 2.6 Common Follow-up Q&A

**Q1: How do you decide between strong and eventual consistency?**
> "Ask: What is the cost of reading stale data? For payments — cost is high (wrong balance, overdraft). For social feed — cost is low (slightly late post). Formula: if stale data leads to incorrect financial, legal, or safety decisions → strong. If stale data is merely a momentary UX imperfection → eventual. Also consider read/write frequency — high-read systems benefit more from eventual consistency (can distribute reads to replicas)."

**Q2: Can eventual consistency lead to data loss?**
> "Not exactly data loss, but it can lead to write conflicts. Example: two users update the same record simultaneously on different replicas. Conflict resolution strategies: (1) Last-Write-Wins (timestamp) — simple but can lose a write. (2) Multi-Version Concurrency Control — keep all versions, resolve conflicts explicitly. (3) CRDTs (Conflict-Free Replicated Data Types) — data structures that merge automatically (counters, sets). Amazon Dynamo uses Last-Write-Wins as default."

**Q3: What is read repair in Cassandra?**
> "Read repair is a mechanism to fix stale data lazily. When a read goes to multiple nodes (quorum), if they return different values, the coordinator identifies the most recent version and updates the stale nodes. No separate reconciliation job needed — reads themselves heal the data. This is how Cassandra maintains eventual consistency with good convergence properties."

---

## Interview Cheat Sheet

```
Strong Consistency:
  - Any read after write returns new value
  - HOW: Sync replication OR read from primary only
  - COST: Higher latency, lower availability
  - USE: Payments, bookings, login

Eventual Consistency:
  - All replicas converge over time (seconds/minutes)
  - HOW: Async replication + conflict resolution
  - BENEFIT: Lower latency, higher availability
  - USE: DNS, search index, social feeds, view counts

Other models:
  Read-your-writes: Own writes always visible to you
  Monotonic reads: Never see older data than you've seen
  Causal: Cause seen before effect

My project:
  Strong: PostgreSQL transactions, select_for_update (payments/bookings)
  Eventual: Typesense index, Redis cache (search/listings)

Key insight: Choose per-feature, not system-wide
```
