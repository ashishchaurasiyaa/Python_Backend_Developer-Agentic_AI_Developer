# Polyglot Persistence

## Quick Reference Card
```
Polyglot      → Multiple databases, each for what it's best at
Persistence   → Data storage (persistent = stays after restart)
Key idea      → Don't force all data into one DB type
Trade-off     → Operational complexity vs performance per access pattern
Example       → PostgreSQL (transactions) + Redis (cache) + Elasticsearch (search)
Interview hook → "Youngman: Postgres (data) + Redis (cache/sessions) + Typesense (search) = polyglot"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Polyglot Persistence Kya Hai?

**Analogy: Specialised tools**

Carpenter ke paas ek hi hathoda nahi hota. Unke paas:
- Hammer: nails ke liye
- Screwdriver: screws ke liye
- Drill: holes ke liye
- Saw: cutting ke liye

Har tool apne kaam ke liye best. Screwdriver se nail thokna possible hai — but painful. Polyglot persistence: use the right tool for each job.

```
MONOGLOT (one DB for everything):
  ┌─────────────────────────────────────────────────────┐
  │                   PostgreSQL                         │
  │  User sessions + Cache + Search + Transactions +    │
  │  Logs + Time-series + Full-text + Queues + ...      │
  └─────────────────────────────────────────────────────┘
  Result: PostgreSQL doing many things, none perfectly

POLYGLOT (right tool for each):
  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
  │  PostgreSQL  │  │  Redis   │  │  Typesense   │  │  S3          │
  │  (RDBMS)     │  │(Key-Val) │  │  (Document   │  │  (Object     │
  │  Transactions│  │ Cache    │  │   Search)    │  │   Storage)   │
  │  ACID data   │  │ Sessions │  │  Full-text   │  │  Files       │
  └──────────────┘  └──────────┘  └──────────────┘  └──────────────┘
  Result: Each component performs optimally
```

---

### 1.2 When to Go Polyglot

```
LEGITIMATE REASONS to add a new DB:
  
  1. Performance bottleneck:
     "Our PostgreSQL full-text search is slow at 1M products"
     → Add Elasticsearch/Typesense (built for search)
  
  2. New data model that SQL handles poorly:
     "We need to find 2nd-degree connections between users"
     → Add Neo4j (graph traversal is native)
  
  3. Volume mismatch:
     "We log 1 billion events per day — PostgreSQL can't handle the write rate"
     → Add Cassandra (built for massive append-only writes)
  
  4. Access pattern mismatch:
     "Sessions need sub-1ms reads, PostgreSQL gives 5-10ms"
     → Add Redis (in-memory, <1ms)
  
  5. Cost optimization:
     "Keeping 2 years of clickstream data in PostgreSQL is expensive"
     → Move cold data to S3 (10x cheaper) or Cassandra

BAD REASONS to add a new DB:
  ✗ "It's trendy" (MongoDB without a real need)
  ✗ "Let me try something new" (production is not playground)
  ✗ "RDBMS can't scale" (usually wrong — optimize first!)
  ✗ "NoSQL is faster" (depends on use case — Redis yes, MongoDB maybe)
```

---

### 1.3 Polyglot Architecture Patterns

#### Pattern 1: CQRS with Polyglot

```
CQRS = Command Query Responsibility Segregation
  Commands (writes) → Transactional DB (PostgreSQL)
  Queries (reads) → Optimized read store (Elasticsearch, Redis, denormalized DB)

  ┌────────────────────────────────────────────────────────┐
  │                   Application                           │
  └───────────┬──────────────────────────┬─────────────────┘
              │ Commands                  │ Queries
              ▼                          ▼
  ┌─────────────────────┐     ┌─────────────────────────┐
  │   PostgreSQL         │     │   Read Store            │
  │   (Write model)      │     │   (Elasticsearch /      │
  │   Normalized,        │     │    Redis / Cassandra)   │
  │   ACID              │     │   Denormalized,         │
  └──────────┬──────────┘     │   optimized for queries │
             │                └─────────────────────────┘
             │ Event / Sync                ↑
             └─────────────────────────────┘
               (after write, update read store)

Example in Niroskos:
  Booking created → PostgreSQL (source of truth)
  Post-save signal → Update Typesense search index
  User searches → Typesense (fast, full-text)
  User views booking → PostgreSQL (authoritative data)
```

#### Pattern 2: Purpose-Specific Stores

```
┌─────────────────────────────────────────────────────────────┐
│                     Youngman / Niroskos                      │
├────────────────┬────────────────────────────────────────────┤
│ Data Type      │ Database       │ Why                       │
├────────────────┼────────────────────────────────────────────┤
│ User data      │ PostgreSQL     │ ACID, FK constraints      │
│ Bookings       │ PostgreSQL     │ ACID transactions         │
│ Invoices       │ PostgreSQL     │ Financial integrity       │
│ Sessions       │ Redis          │ Sub-1ms, TTL support      │
│ Cache          │ Redis          │ Sub-1ms, LRU eviction     │
│ Rate limits    │ Redis          │ Atomic counters           │
│ Search index   │ Typesense      │ Full-text, faceted search │
│ Task queue     │ Redis/RabbitMQ │ Fast push/pop             │
│ Files/PDFs     │ S3             │ Unlimited scale, cheap    │
│ Static assets  │ S3 + CloudFront│ CDN delivery              │
└────────────────┴────────────────────────────────────────────┘
```

---

### 1.4 Data Synchronization Challenge

```
PROBLEM: Multiple DBs → Data consistency challenge

Example:
  PostgreSQL: Package updated (price changed)
  Typesense: Still has old price in search index!
  
  User searches → sees old price
  User views package → sees new price
  → INCONSISTENT!

SOLUTIONS:

1. Synchronous dual-write (simple, risky):
   def update_package(pk, data):
       package = Package.objects.get(id=pk)
       package.price = data['price']
       package.save()                              # PostgreSQL
       typesense_client.update_document(pk, data)  # Typesense
   
   RISK: If Typesense fails → PostgreSQL saved but Typesense stale!
         If PostgreSQL fails after Typesense → inconsistent!

2. Event-driven sync (better):
   PostgreSQL write → Django Signal → Celery task → Typesense update
   
   @receiver(post_save, sender=Package)
   def sync_to_search_index(sender, instance, **kwargs):
       update_typesense.delay(instance.id)  # Async task
   
   RISK: Celery task fails → Typesense not updated
   FIX: Celery retry + periodic full re-index job

3. Change Data Capture (CDC — production grade):
   PostgreSQL WAL → Debezium → Kafka → Typesense consumer
   
   PostgreSQL change → WAL record → Kafka event → Consumer updates Typesense
   
   Benefits: Reliable, exactly-once semantics, replayable
   Complexity: More infrastructure (Debezium, Kafka)
   
   Used by: Large-scale systems (Shopify, LinkedIn)

4. Periodic full sync (simple safety net):
   # Management command — runs nightly
   def sync_all_packages():
       for package in Package.objects.all():
           typesense_client.upsert_document(...)
   
   Handles: Missed events, crashed tasks, any inconsistency
   Lag: At most 24 hours stale
   Use: As ADDITIONAL safety net, not primary sync
```

---

### 1.5 Operational Complexity — The Cost of Polyglot

```
Each additional database:
  + Monitoring: Another dashboard, another alert
  + Backup: Another backup strategy
  + Security: Another access control config
  + Dev knowledge: Team must know N databases
  + Version management: Upgrades for each
  + Failure modes: More failure modes to handle
  + Cost: License + infra cost per DB

START-UP: 1 DB (PostgreSQL) — simple, fast
  ↓ growth
MID-SIZE: Add Redis — 2 DBs — manageable
  ↓ growth
SCALE: Add Typesense/Elastic — 3 DBs — getting complex
  ↓ growth
LARGE: Add Cassandra, Kafka — 4+ DBs — needs dedicated platform team

Rule of thumb:
  Add a new DB type ONLY when:
  The performance/capability gain > operational overhead
  The team has expertise to maintain it
  Single DB optimization has been exhausted

"Don't add a new database until it's painful enough to need one"
```

---

### 1.6 Ashish ke projects — Polyglot in action

```python
# Youngman: 3 databases working together

# 1. PostgreSQL — Source of Truth
class Invoice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20)
    pdf_s3_key = models.CharField(max_length=500)  # Pointer to S3

# 2. Redis — Cache + Sessions
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://elasticache:6379',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# 3. S3 — File Storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# 4. Typesense — Search (Niroskos)
typesense_client = typesense.Client({
    'nodes': [{'host': 'typesense', 'port': 8108}],
    'api_key': settings.TYPESENSE_API_KEY,
})

# HOW THEY INTERACT:
def create_invoice(data):
    # 1. PostgreSQL — create invoice record
    invoice = Invoice.objects.create(**data)
    
    # 2. S3 — generate and store PDF
    pdf_key = generate_and_upload_pdf(invoice)
    invoice.pdf_s3_key = pdf_key
    invoice.save()
    
    # 3. Redis — cache invoice for fast retrieval
    cache.set(f'invoice:{invoice.id}', InvoiceSerializer(invoice).data, 300)
    
    # 4. Celery (via Redis broker) — async SAP push
    push_to_sap.delay(invoice.id)
    
    return invoice

def get_invoice(invoice_id):
    # Try Redis cache first
    cached = cache.get(f'invoice:{invoice_id}')
    if cached:
        return cached
    
    # Miss → PostgreSQL
    invoice = Invoice.objects.get(id=invoice_id)
    data = InvoiceSerializer(invoice).data
    cache.set(f'invoice:{invoice_id}', data, 300)
    return data

def get_invoice_pdf_url(invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    # S3 pre-signed URL
    return generate_presigned_url(invoice.pdf_s3_key)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Polyglot Persistence**: Using multiple specialized database technologies within a single application, where each database is chosen for its optimal fit to a specific data access pattern, data model, or performance requirement. Coined by Martin Fowler. Trade-off: superior per-domain performance vs increased operational complexity.

---

### 2.2 Polyglot Stack for Common Architectures

```
E-COMMERCE:
  PostgreSQL/MySQL  → Orders, users, inventory (ACID required)
  Redis            → Cart sessions, price cache, flash sale counters
  Elasticsearch    → Product search, recommendations
  MongoDB          → Product catalog (flexible attributes per category)
  S3               → Product images, user-generated content
  Cassandra        → Clickstream, recommendation signals

BOOKING SYSTEM (Niroskos-like):
  PostgreSQL       → Bookings, payments, user accounts (ACID)
  Redis            → Sessions, search result cache, rate limiting
  Typesense        → Package search with faceting
  S3               → Tour images, booking documents, certificates
  Redis Streams    → Real-time booking event streaming (optional)

SOCIAL MEDIA:
  PostgreSQL/MySQL → User accounts, posts (source of truth)
  Redis            → Timeline cache, count cache (likes, followers)
  Cassandra        → Activity feed (high-write time-series)
  Neo4j            → Social graph (friendship recommendations)
  S3 + CDN         → Photos, videos
  Elasticsearch    → Post search
```

---

### 2.3 Data Sync Strategies

| Strategy | Consistency | Complexity | Best For |
|----------|-------------|------------|----------|
| Synchronous dual-write | Strong | Low | Small scale, simple |
| Event-driven (signals/Celery) | Eventual | Medium | Most web apps |
| CDC (Debezium + Kafka) | Near-real-time | High | Large scale |
| Periodic full sync | Eventual (batchy) | Low | Safety net |

---

### 2.4 Real Project Answer

> "Youngman and Niroskos both use polyglot persistence, though not excessively. The core transactional data — bookings, invoices, users, payments — lives in PostgreSQL where ACID guarantees are essential. Redis handles two concerns: caching (package listings, SAP tokens) at sub-millisecond speed, and session storage with TTL support. For Niroskos, Typesense powers package search because it handles full-text search with faceting and typo tolerance far better than PostgreSQL's tsvector. File storage is on S3 — unlimited scale and 99.999999999% durability with no operational overhead. Each database does one thing excellently. The sync challenge between PostgreSQL and Typesense is handled via Django post_save signals triggering Celery tasks, with a nightly management command as a safety net."

---

### 2.5 Common Follow-up Q&A

**Q1: How do you maintain consistency across multiple databases?**
> "Perfect consistency across databases is usually not achievable without distributed transactions, which are expensive. The practical approach is eventual consistency with clear boundaries: PostgreSQL is the system of record (source of truth). Other databases are derived views — they eventually sync to PostgreSQL's state. Key patterns: (1) Event-driven sync — Django signals trigger async tasks to update secondary stores. (2) Idempotent updates — if a sync task runs twice, the result is the same. (3) Periodic reconciliation — nightly job that checks primary vs secondary stores and fixes discrepancies. (4) Staleness tolerance — design features to accept slightly stale data from secondary stores."

**Q2: What is the danger of polyglot persistence?**
> "The main danger is operational complexity — each database adds monitoring, backup, security, and expertise requirements. A team of 3 engineers managing 5 different databases is stretched thin. Also, partial failures become more likely: if Typesense is down, does the search API return 503 or fall back to slower PostgreSQL full-text search? These failure mode decisions multiply with each database. The risk mitigation: start with one database, add others only when the pain is clear, ensure the team has expertise for each addition, and have runbooks for failure scenarios of each database."

**Q3: How does CQRS relate to polyglot persistence?**
> "CQRS (Command Query Responsibility Segregation) naturally enables polyglot persistence. Commands (writes) go to a normalized, ACID-compliant database optimized for integrity. Queries (reads) go to denormalized read models optimized for specific access patterns. The read model can be in any database — Redis for hot data, Elasticsearch for search, a denormalized PostgreSQL table for reporting. The write database is the source of truth; the read databases are projections updated via events. This separation means each database only does what it's best at, and you can optimize reads and writes independently."

---

## Interview Cheat Sheet

```
Polyglot Persistence = Right database for each access pattern

Common stack:
  RDBMS (PostgreSQL): Transactions, ACID, JOINs, financial data
  Key-Value (Redis): Cache, sessions, rate limiting, queues
  Document (MongoDB/Typesense): Search, catalog, flexible schema
  Object (S3): Files, media, backups
  Graph (Neo4j): Relationships, recommendations (if needed)
  Column-Family (Cassandra): Time-series, logs (if needed)

Add new DB only when:
  Performance requirement can't be met by current DBs
  Data model fundamentally different
  Team has operational expertise for it

Sync strategies (PostgreSQL → secondary):
  1. Django Signal → Celery async task (most common)
  2. CDC (Debezium → Kafka → consumer) [large scale]
  3. Periodic full sync (safety net)

Cost of polyglot:
  + Performance per domain
  + Specialized capabilities
  - Operational complexity
  - Multiple failure modes
  - Team expertise needed for each

My stack:
  PostgreSQL: All transactional data (source of truth)
  Redis: Cache + sessions (ElastiCache)
  Typesense: Package search
  S3 + CloudFront: Files + static assets
  RabbitMQ/Redis: Celery task broker

Design principle: Start monoglot, go polyglot as pain demands
```
