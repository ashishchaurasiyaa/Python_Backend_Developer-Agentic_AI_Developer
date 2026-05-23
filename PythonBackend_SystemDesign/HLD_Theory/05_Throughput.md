# Throughput — How to Improve Throughput

## Quick Reference Card
```
Throughput  → Requests per second (RPS) ya data per second (Mbps) system process kar sakta hai
Latency     → Ek request ka time (ms) — alag concept
Little's Law→ Throughput = Concurrent Users / Latency
Bottleneck  → Jahan throughput rukta hai — DB, CPU, network
Improve by  → Horizontal scaling, caching, async, connection pooling, batching
Interview hook → "Celery workers badhake SAP sync throughput 3x improve kiya"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai Throughput?

**Analogy: Highway toll booth**

- **Latency** = Ek gaadi ko toll cross karne mein kitna time laga (seconds)
- **Throughput** = Ek ghante mein kitni gaadiyan toll cross kar sakti hain (cars/hour)

Dono alag hain:
- Slow toll booth (high latency) but ek hi lane = low throughput
- Fast toll booth but sirf 1 lane = still low throughput
- Fast booth + 10 lanes = high throughput!

```
System Throughput = min(component throughputs)

If:
  Web Server capacity  = 10,000 RPS
  App Server capacity  = 1,000 RPS   ← BOTTLENECK
  Database capacity    = 5,000 RPS

  Overall throughput   = 1,000 RPS (limited by weakest link)
```

---

### 1.2 Throughput vs Latency Relationship

```
Little's Law (queueing theory):
  Throughput = Concurrency / Latency
  
  Example:
  - 100 concurrent users
  - Each request takes 100ms
  - Throughput = 100 / 0.1 = 1000 RPS

  Latency kam karo → Throughput automatically badhta hai
  Concurrency badhao → Throughput badhta hai

Har ek improvement strategy kisi ek ya dono pe kaam karta hai
```

---

### 1.3 Throughput Kaise Improve Karen?

#### Strategy 1: Horizontal Scaling (More instances)
```
Before:
  1 App Server → 500 RPS max

After:
  Load Balancer
    ├── App Server 1 → 500 RPS
    ├── App Server 2 → 500 RPS
    └── App Server 3 → 500 RPS
  Total: 1500 RPS

Niroskos: Multiple Django instances behind Nginx
Celery: Multiple workers for task processing
```

#### Strategy 2: Caching (Reduce DB load)
```
Without cache:
  Every request → DB query (10ms, 5000 RPS max)
  App bottleneck → 500 RPS

With Redis cache:
  80% requests → Redis (< 1ms, 100,000 RPS capacity)
  20% requests → DB (10ms)
  Effective throughput: much higher

Cache hit rate = % of requests served from cache
Target: 80-95% cache hit rate
```

#### Strategy 3: Async Processing (Don't block the request)
```
Synchronous (blocks throughput):
  Request → Process → SAP Push (3s) → Response
  If 100 concurrent users → 100 threads blocked for 3s
  Throughput = 100/3 = 33 RPS

Asynchronous (free the thread immediately):
  Request → Queue task → Response (10ms)
  Background: Celery worker → SAP Push (3s)
  
  Now 100 concurrent users get response in 10ms
  Throughput = 100/0.01 = 10,000 RPS for the request itself

Youngman: Invoice creation → immediate response
          SAP sync → Celery background task
```

#### Strategy 4: Connection Pooling
```
Without pooling:
  100 RPS × (50ms connection setup + 5ms query) = throughput limited

With pgBouncer / SQLAlchemy pool:
  Pool of 20 connections, reused
  100 RPS × 5ms query only = much higher throughput
  Connection setup overhead eliminated

Django settings:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 60,  # Persistent connections (pseudo-pooling)
    }
}
```

#### Strategy 5: Batching
```
Without batching:
  1000 records → 1000 INSERT queries → 1000 round trips

With batching:
  1000 records → 1 bulk INSERT → 1 round trip

Python/Django:
  Invoice.objects.bulk_create(invoice_list, batch_size=500)
  # 10x faster

Youngman: Bulk SAP sync — batch 100 invoices per API call
instead of 100 separate API calls
```

#### Strategy 6: Read Replicas
```
Write traffic → Primary DB (1 instance)
Read traffic  → Read Replicas (3 instances)

Result:
  Reads (80% traffic) distributed across 3 replicas = 3x read throughput
  Writes (20% traffic) still go to primary

Django:
DATABASE_ROUTERS = ['myapp.routers.PrimaryReplicaRouter']
# Reads → replica, Writes → primary
```

#### Strategy 7: Message Queues
```
Spike traffic (10,000 RPS suddenly):
  Without queue: App server overwhelmed → timeouts → failures
  
  With Kafka/RabbitMQ:
  Spike → Queue (buffer) → Workers process at their own pace
  
  Queue acts as buffer — smooths out traffic spikes
  
Youngman: Celery + RabbitMQ
- Invoicing spike → tasks queued
- Workers process steadily at max capacity
```

---

### 1.4 Identifying the Bottleneck

```
Step 1: Load test (locust, k6, JMeter)
  locust -f locustfile.py --host=https://api.niroskos.com

Step 2: Monitor at each layer
  - CPU %: High → app logic bottleneck
  - DB queries/sec: High → DB bottleneck
  - Memory: High → cache pressure, leaks
  - Network I/O: High → bandwidth bottleneck
  - Queue depth: Growing → consumer bottleneck

Step 3: Profiling
  import cProfile
  cProfile.run('create_invoice(data)')
  # Find slow functions

Step 4: Fix the bottleneck, re-test
  # Never optimize what isn't the bottleneck!
```

---

### 1.5 Ashish ke projects mein

**Youngman — SAP sync throughput:**
```
Before:
  - Invoice creation triggered immediate SAP push
  - SAP API: 200-500ms per call
  - At peak: 50 invoices/minute = 25 seconds of waiting
  - Throughput bottleneck: SAP API rate

After (Celery async):
  - Invoice creation: instant response (10ms)
  - SAP push: Celery task, 3 workers in parallel
  - 3 workers × 2 RPS each = 6 SAP pushes/second = 360/minute
  - Throughput: 7x improvement
```

**Youngman — Bulk operations:**
```python
# Before: Individual creates (slow)
for invoice_data in monthly_invoices:
    Invoice.objects.create(**invoice_data)  # N DB queries

# After: Bulk create (fast)
Invoice.objects.bulk_create(
    [Invoice(**data) for data in monthly_invoices],
    batch_size=200
)  # Ceil(N/200) DB queries

# For 1000 invoices: 1000 → 5 queries (200x fewer roundtrips)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Throughput** is the number of operations a system can process per unit of time — measured as requests per second (RPS), transactions per second (TPS), or bytes per second. It represents the productive capacity of a system. Throughput is limited by the weakest component in the system (the bottleneck), not the strongest.

---

### 2.2 Throughput vs Latency vs Bandwidth

| Metric | Definition | Unit | Optimize by |
|--------|-----------|------|-------------|
| Latency | Time for single request | ms | Caching, indexing, CDN |
| Throughput | Operations per second | RPS, TPS | Scaling, async, batching |
| Bandwidth | Data transfer rate | Mbps, Gbps | CDN, compression, streaming |

**Key insight:** Improving latency often improves throughput (Little's Law). But they can be in tension — batching improves throughput but can increase individual latency.

---

### 2.3 Amdahl's Law — Scaling Limits

```
Amdahl's Law: Speedup = 1 / (S + (1-S)/N)

Where:
  S = fraction of code that cannot be parallelized (sequential)
  N = number of processors/workers

Example:
  S = 0.2 (20% sequential — e.g., DB writes, locks)
  N = 10 workers
  Speedup = 1 / (0.2 + 0.8/10) = 1 / 0.28 = 3.57x (not 10x!)

Implication: If 20% of your system is sequential,
max speedup = 5x regardless of how many workers you add.
This is why eliminating locks and bottlenecks matters.
```

---

### 2.4 Throughput Optimization Priority

```
1. Identify bottleneck first (profile, monitor)
2. Cache hot data (Redis) — biggest ROI usually
3. Async for I/O-bound work (Celery, queues)
4. Batch DB operations (bulk_create, bulk_update)
5. Index DB queries (composite indexes)
6. Connection pooling (pgBouncer)
7. Horizontal scaling (more instances)
8. Read replicas (split read/write)
9. Sharding (extreme scale — rarely needed)
```

---

### 2.5 Real Project Answer

> "In Youngman's invoicing system, the throughput bottleneck was synchronous SAP HANA API calls. Each API call took 200-500ms, and our invoice creation was blocking on this call. By moving SAP sync to Celery background tasks with 3 dedicated workers, invoice creation response time dropped to ~20ms and SAP sync throughput increased from ~2/second to ~6/second. Additionally, for monthly bulk invoice generation affecting 500+ customers, switching from individual ORM creates to bulk_create with batch_size=200 reduced DB time from ~25 seconds to ~2 seconds."

---

### 2.6 Common Follow-up Q&A

**Q1: How do you measure throughput in production?**
> "Application metrics via Prometheus/Datadog — request_count counter per endpoint. Rate function gives RPS: rate(http_requests_total[5m]). For DB throughput, pg_stat_activity and pg_stat_statements. For Celery, monitor queue depth and task completion rate. Load testing pre-production with Locust or k6 to establish baseline and identify breaking point (max RPS before errors start)."

**Q2: What's the difference between throughput and scalability?**
> "Throughput is current capacity — how many RPS right now. Scalability is the ability to increase throughput by adding resources. A system can have high throughput but poor scalability (monolithic DB — adding more RAM eventually hits limits). Good scalability means throughput grows linearly (or near-linearly) with added resources — horizontal scaling."

**Q3: Can high throughput and low latency conflict?**
> "Yes. Batching is the classic trade-off: instead of processing each request immediately (low latency), you buffer requests and process in batches (higher throughput, but each request waits for the batch to fill). Kafka's linger.ms setting is this trade-off — wait 5ms to batch more messages, improving throughput at cost of 5ms added latency. The right balance depends on SLA requirements."

---

## Interview Cheat Sheet

```
Throughput = RPS/TPS the system can handle
Bottleneck = weakest link limits total throughput
Little's Law: Throughput = Concurrency / Latency

Improvement strategies:
1. Cache (Redis) → DB load reduce karo
2. Async (Celery) → Don't block threads
3. Batching → N queries → 1 query
4. Horizontal scaling → More instances
5. Connection pooling → TCP overhead hatao
6. Read replicas → Read load distribute karo
7. Message queue → Traffic spikes buffer karo

Amdahl's Law: Sequential code limits max speedup
20% sequential → max 5x speedup regardless of workers

My project:
- SAP sync async → invoice throughput 7x
- bulk_create → monthly generation 12x faster
- 3 Celery workers → parallel SAP pushes
```
