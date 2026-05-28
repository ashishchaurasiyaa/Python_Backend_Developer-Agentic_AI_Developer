# 09. Reliability — HA, Fault Tolerance, DR, Backup

## Core Concepts

| Term | Definition |
|---|---|
| **Reliability** | Probability system performs correctly over time |
| **Availability** | % of time system is up (9s notation) |
| **Fault Tolerance** | System keeps running despite failures |
| **High Availability (HA)** | Designed to minimize downtime |
| **Disaster Recovery (DR)** | Ability to recover from major incident |
| **RTO** | Recovery Time Objective — how fast to recover |
| **RPO** | Recovery Point Objective — how much data loss OK |
| **MTBF** | Mean Time Between Failures |
| **MTTR** | Mean Time To Repair |
| **MTTD** | Mean Time To Detect |

---

## The "Nines"

| Availability | Downtime/year | Downtime/month | Downtime/week | Cost level |
|---|---|---|---|---|
| 99% | 3.65 days | 7.3 hr | 1.7 hr | Cheap |
| 99.9% (3 nines) | 8.76 hr | 43.8 min | 10.1 min | Standard |
| 99.95% | 4.38 hr | 21.9 min | 5.04 min | Good |
| 99.99% (4 nines) | 52.6 min | 4.38 min | 1.01 min | Expensive |
| 99.999% (5 nines) | 5.26 min | 26.3 sec | 6 sec | Very expensive |
| 99.9999% (6 nines) | 31.5 sec | 2.6 sec | 0.6 sec | $$$$$ |

**Rule:** Each "9" = 10x harder + ~10x more cost. **Don't promise more than business needs.**

**Typical commitments:**
- Cloud provider SLAs: 99.9% - 99.99%
- SaaS to consumer: 99.9%
- SaaS to enterprise: 99.95%
- Banking, telecom: 99.99%+
- Phone (911): 99.999%

---

## Why Things Fail

```
Hardware (10%):
- Disk failures (~3% annual failure rate)
- Network cable cuts
- Power supply failures
- Memory ECC errors

Software (40%):
- Bugs in production
- Configuration errors
- Resource exhaustion (OOM, disk full)
- Race conditions

Operator error (40%):
- Bad deploys
- Wrong commands
- Misconfiguration

External (10%):
- Cloud provider outages
- DDoS attacks
- BGP routing issues
- Datacenter fires/floods
```

**Implication:** Software + process matter more than hardware.

---

## Single Points of Failure (SPOF)

```
SPOF identification:
─────────────────
1. Draw architecture
2. For each component, ask: "If this dies, does the system stop?"
3. If yes → SPOF → must add redundancy

Common SPOFs:
- Single database instance
- Single load balancer
- Single message broker
- Single DNS provider
- Single cloud region
- Single network path
- Single deployment pipeline
- Single on-call person
```

---

## Redundancy Patterns

### Active-Active

```
Both instances handle traffic simultaneously.

┌─────────────┐        ┌─────────────┐
│   API-1     │◄──50%──┤              │
│   (live)    │        │ Load Balancer│
└─────────────┘        │              │
                       └──────┬───────┘
┌─────────────┐               │ 50%
│   API-2     │◄──────────────┘
│   (live)    │
└─────────────┘

Pros: Better resource utilization; both proven working
Cons: Both must handle full load if one fails
```

### Active-Passive (Standby)

```
Primary handles traffic; secondary ready to take over.

┌─────────────┐        ┌─────────────┐
│   API-1     │◄───────┤              │
│  (active)   │        │ Load Balancer│
└─────────────┘        │              │
                       └──────┬───────┘
┌─────────────┐               │ (idle)
│   API-2     │◄──────────────┘
│ (passive)   │
└─────────────┘

Pros: Simpler; standby tested less
Cons: Wasted capacity; cold start risk
```

### N+1, N+M Redundancy

```
N+1: One spare beyond required capacity
N+M: M spares (more resilient)
2N:  Full duplicate (most expensive)

Example:
Required for traffic: 10 servers
N+1:  11 servers (can lose 1)
N+2:  12 servers (can lose 2)
2N:   20 servers (full duplicate)
```

---

## Failure Modes

### Cascading Failures

```
Service A overloaded → returns errors
   ↓
Service B retries A aggressively
   ↓
A gets even more requests → totally down
   ↓
Service C calls B → blocks on B's slowness
   ↓
Whole system collapses
```

**Mitigation:**
- **Circuit breakers** (Hystrix pattern)
- **Bulkheads** (resource isolation)
- **Backpressure** (slow consumers shed load)
- **Retry with jitter** (not synchronized)
- **Timeouts** (don't wait forever)

### Circuit Breaker Pattern

```python
from circuit_breaker import CircuitBreaker

@CircuitBreaker(failure_threshold=5, recovery_timeout=60, expected_exception=APIError)
async def call_payment_service(req):
    return await payment_client.charge(req)

# States:
# CLOSED:   normal, calls go through
# OPEN:     fail-fast, no calls (after 5 failures in window)
# HALF_OPEN: probe with 1 call (after recovery_timeout)
```

**Why this works:**
- Stop hammering broken service
- Service has time to recover
- User gets fast failure response (not timeout)
- Auto-recovery when service back

### Bulkhead Pattern

```python
# Each downstream gets own connection pool — failures don't spread
payment_client = HTTPClient(pool_size=10, timeout=5)
search_client = HTTPClient(pool_size=20, timeout=2)
ml_client = HTTPClient(pool_size=5, timeout=30)

# Payment slow doesn't drain search/ml pool
```

### Timeout + Retry

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def call_with_retry(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

**Anti-pattern:** Infinite retries without backoff → DDoS your own backend.

**Jitter** (avoid synchronized retries):
```python
import random
wait_seconds = base * (2 ** attempt) + random.uniform(0, base)
```

---

## Database Reliability

### Replication

```
Primary (writer)
     │
     ├─── async ──→ Replica 1 (reader)
     ├─── async ──→ Replica 2 (reader)
     └─── async ──→ Replica 3 (different region — DR)
```

**Failure scenarios:**
| Failure | Impact |
|---|---|
| Replica down | None (others serve reads) |
| Primary down | Need failover → brief downtime |
| Replica lag too high | Stale reads |
| Network partition | Split brain risk (if poorly configured) |

### Failover Strategies

**Manual:** SRE decides; safer; slower (10-30 min)
**Automatic:** Software decides; faster (1-5 min); risk of false positive

**Tools:**
- **Patroni** (PostgreSQL HA via etcd/Consul/ZK)
- **AWS RDS Multi-AZ** (managed)
- **Aurora** (built-in, < 1 min failover)
- **Galera** (MySQL multi-master)

### Backup Strategy

**3-2-1 Rule:**
- **3** copies of data
- **2** different media types
- **1** offsite

```
Production DB
     │
     ├─── continuous WAL → S3 (point-in-time recovery)
     ├─── daily snapshot → S3 (with 30-day retention)
     ├─── weekly snapshot → S3 Glacier (1 year)
     └─── cross-region replica → DR site
```

**Test backups regularly:**
- Quarterly: restore to staging, verify integrity
- Annual: full DR drill (failover to backup, run production for an hour)

---

## Disaster Recovery (DR)

### DR Tiers (Industry standard)

| Tier | Strategy | RTO | RPO | Cost |
|---|---|---|---|---|
| 0 | None | Days | Days | None |
| 1 | Backups only | Hours-days | Hours | Low |
| 2 | Backups + standby hardware | Hours | Hours | Medium |
| 3 | Active-passive (warm standby) | 30-60 min | Minutes | Medium-high |
| 4 | Active-active (hot standby) | < 5 min | Seconds | High |
| 5 | Continuous availability | < 1 min | Zero | Very high |

### RTO/RPO Decision

```
Q: How much downtime can business tolerate?
- 24 hours → Tier 1 (backups)
- 4 hours → Tier 2-3
- 1 hour → Tier 3-4
- 5 min → Tier 4
- Zero → Tier 5

Q: How much data loss is acceptable?
- 1 day → Daily backups
- 1 hour → Hourly backups
- 1 minute → Continuous replication
- Zero → Synchronous replication (rare)
```

---

## Health Checks

```python
# Liveness — am I alive?
@app.get("/health/live")
async def liveness():
    return {"status": "ok"}

# Readiness — am I ready for traffic?
@app.get("/health/ready")
async def readiness():
    # Check dependencies
    try:
        await db.execute("SELECT 1")
        await redis.ping()
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)

# Deep health — full functional check (don't expose externally)
@app.get("/health/deep")
async def deep_health():
    checks = {
        "db_primary": await check_db_primary(),
        "db_replica": await check_db_replica(),
        "redis": await check_redis(),
        "kafka": await check_kafka(),
        "stripe": await check_stripe(),
    }
    all_ok = all(checks.values())
    return {"checks": checks, "status": "ok" if all_ok else "degraded"}
```

**K8s probes:**
```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8000 }
  periodSeconds: 10
  failureThreshold: 3        # 30s before kill

readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
  periodSeconds: 5
  failureThreshold: 1        # remove from LB immediately
```

---

## Graceful Degradation

When dependencies fail, what's the minimum viable response?

```python
async def get_dashboard(user_id):
    # Try parallel — but if any fails, degrade
    results = await asyncio.gather(
        get_orders(user_id),
        get_recommendations(user_id),
        get_notifications(user_id),
        return_exceptions=True,
    )

    orders, recs, notifs = results

    return {
        "orders": orders if not isinstance(orders, Exception) else [],
        "recommendations": recs if not isinstance(recs, Exception) else [],
        "notifications": notifs if not isinstance(notifs, Exception) else [],
        "degraded": any(isinstance(r, Exception) for r in results),
    }
```

**Example:**
- Search down → show static "featured products"
- Recommendation engine down → show "popular items"
- Personalization off → show generic homepage
- Payment slow → show "processing, we'll email confirmation"

---

## Chaos Engineering

**Principle:** Inject failures intentionally to find weaknesses before they happen in prod.

```python
# Netflix Chaos Monkey — kills random instances
# Gremlin, Litmus — managed chaos tools

# Simple Python chaos
import random

async def chaotic_call():
    if random.random() < 0.05:                    # 5% fail
        raise ConnectionError("Chaos!")
    if random.random() < 0.10:                    # 10% slow
        await asyncio.sleep(5)
    return await real_call()
```

**Chaos game days (quarterly):**
- Simulate region failure → verify failover
- Kill primary DB → measure RTO
- Network partition → test split-brain handling
- Slow downstream → test circuit breakers
- Full disk → test alerting + cleanup

---

## Monitoring + Alerting for Reliability

```
What to monitor:
─────────────
1. SLI metrics (latency, error rate, throughput)
2. Saturation (CPU, memory, disk, network)
3. Replication lag (DB, cache)
4. Queue depth (Kafka, RabbitMQ, Celery)
5. Connection pool exhaustion
6. Disk space (especially log dir)
7. Certificate expiration
8. DNS resolution time
9. External API success rates

Alert on (not just):
- Errors > 1%
- Latency > SLO
- Queue depth > critical threshold
- Disk > 80% full
- Replication lag > 30s
- Failed health checks > 3 consecutive
- Cert expiring in < 30 days
```

---

## Deployment Reliability

### Strategies

**Blue-Green:**
```
Blue (current production)  ←── 100% traffic
Green (new version)        ←── 0% (deploy + smoke test)
                                ↓
                           Switch DNS/LB
                                ↓
Blue                       ←── 0%
Green (new production)     ←── 100%
```
Pros: instant rollback (switch back)
Cons: 2x infra cost

**Canary:**
```
Old version: 95% traffic
New version: 5% traffic    ← monitor metrics
   ↓ (looks good)
Old version: 80% traffic
New version: 20% traffic
   ↓
... ramp up to 100%
```
Pros: minimize blast radius
Cons: slower; needs traffic splitting

**Rolling:**
```
10 pods, replace one at a time
Pod 1 (old → new)
Pod 2 (still old)
...
```
Pros: standard K8s; easy
Cons: mixed versions briefly

### Rollback Capability

**Mandatory:**
- 1-click rollback (or 1-command)
- Tested regularly
- Database migrations backward-compatible (expand-contract)
- Feature flags for risky changes

```yaml
# K8s rollback
kubectl rollout undo deployment/api -n production
kubectl rollout status deployment/api -n production
```

---

## Network Reliability

| Issue | Mitigation |
|---|---|
| Single ISP outage | Multi-homed (2+ ISPs) |
| Cloud region down | Multi-region |
| BGP route flapping | Health checks + failover |
| DNS provider outage | Multi-DNS (Route53 + Cloudflare) |
| TLS cert expired | Auto-renewal (cert-manager) |
| Network partition | Quorum-based protocols (Raft, Paxos) |

---

## Idempotency for Reliability

```python
# Without idempotency — duplicate processing on retry
async def charge_payment(req):
    return await stripe.PaymentIntent.create(amount=req.amount, ...)

# With idempotency — safe to retry
async def charge_payment(req):
    idempotency_key = req.idempotency_key  # client-generated UUID
    return await stripe.PaymentIntent.create(
        amount=req.amount,
        idempotency_key=idempotency_key,  # Stripe deduplicates
    )

# Database idempotency
async def create_order(req):
    # Use UNIQUE constraint on idempotency_key
    try:
        await db.execute(
            "INSERT INTO orders (idem_key, ...) VALUES (:k, ...)",
            {"k": req.idempotency_key, ...},
        )
    except IntegrityError:
        # Duplicate — return existing
        return await db.fetch_one("SELECT * FROM orders WHERE idem_key = :k", {"k": req.idempotency_key})
```

---

## Interview Q&A

### Q: What's the difference between HA and DR?

**Answer:**
- **HA**: minimize downtime within normal operation (1 server fails → another takes over in seconds)
- **DR**: recover from major disasters (region down, data center fire → failover to backup site in minutes/hours)

HA = small failures, automatic. DR = catastrophic failures, often manual.

### Q: How do you design for 99.99% availability?

**Answer:**
1. **No SPOF** — redundant everything
2. **Multi-AZ** at minimum
3. **Active-passive** or active-active across regions
4. **Automated failover** (< 1 min RTO)
5. **Database replication** (sync within AZ, async cross-region)
6. **CDN** for static (Cloudflare = 99.99%+ availability)
7. **Circuit breakers** on all external calls
8. **Graceful degradation** when dependencies fail
9. **Continuous deployment** with rollback
10. **24/7 on-call** + runbooks

### Q: What's the CAP theorem trade-off in reliability terms?

**Answer:**
- **CP**: prefer consistency over availability (financial systems)
- **AP**: prefer availability over consistency (social media, e-commerce)
- During network partition, must choose

In practice:
- Most systems are AP for reads, CP for writes
- Use strong consistency where it matters (payments)
- Use eventual elsewhere (feeds)

### Q: How do you handle a region outage?

**Answer:**
1. **Detection**: health checks fail; alerts fire
2. **Failover**: traffic redirected to secondary region (DNS/LB)
3. **Promote replica**: secondary DB becomes primary
4. **Validate**: smoke tests in new region
5. **Communicate**: status page + customer comms
6. **Restore**: when primary back, rebuild + reverse if needed
7. **Postmortem**: blameless analysis, action items

Pre-requisites:
- Multi-region architecture
- Tested DR runbook
- Cross-region replication
- Decoupled DNS provider

### Q: What's the difference between MTTR, MTBF, MTTD?

**Answer:**
- **MTBF** (Between Failures): average uptime before failure → reliability metric
- **MTTD** (To Detect): time from failure to detection → monitoring metric
- **MTTR** (To Recover): time from detection to recovery → ops metric

Availability ≈ MTBF / (MTBF + MTTR). Lower MTTR = higher availability.

---

## Cheat Sheet

```
For 99% (downtime OK):
- Single region, multi-AZ
- Daily backups

For 99.9% (standard SaaS):
- Multi-AZ, automated failover
- Hourly backups, PITR
- Circuit breakers, timeouts
- Monitoring + alerts

For 99.99% (tier-1):
- Multi-region active-passive
- Continuous replication
- Auto-failover < 5 min
- Game days quarterly
- 24/7 on-call

For 99.999% (telco):
- Multi-region active-active
- Synchronous replication
- < 1 min failover
- Multiple cloud providers
- Custom routing
```

---

## Related Docs
- [06_Availability.md](../06_Availability.md) — availability deep
- [11_Redundancy_vs_Replication.md](../11_Redundancy_vs_Replication.md)
- [30_SLA_SLO_SLI.md](../30_SLA_SLO_SLI.md) — formal targets
- [34_Circuit_Breaker_Event_Driven.md](../34_Circuit_Breaker_Event_Driven.md)
- [01_Year3-4_Mid/04_DevOps/14_chaos_engineering.md](../../../../01_Year3-4_Mid/04_DevOps/14_chaos_engineering.md)
- [01_Year3-4_Mid/04_DevOps/15_multi_region_deployment.md](../../../../01_Year3-4_Mid/04_DevOps/15_multi_region_deployment.md)
- [01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md](../../../../01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md)
