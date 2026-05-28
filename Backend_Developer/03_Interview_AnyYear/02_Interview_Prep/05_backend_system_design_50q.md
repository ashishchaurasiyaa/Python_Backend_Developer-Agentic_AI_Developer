# 50 Backend System Design Questions — Senior Interview Pack

> Format: **Q** → short answer → deeper explanation → trade-off / follow-up.
> Use this as a flash-card pack 1 week before interviews.

---

## SECTION 1 — API DESIGN (Q1–Q8)

### Q1. REST vs GraphQL vs gRPC — kab kya use karein?

**Short:**
- REST → public APIs, simple CRUD, cacheable.
- GraphQL → BFF / mobile apps with multiple screens needing different data shapes.
- gRPC → internal service-to-service, low latency, strong typing.

**Deep:**
| Criterion | REST | GraphQL | gRPC |
|---|---|---|---|
| Transport | HTTP/1.1 + JSON | HTTP/1.1 + JSON | HTTP/2 + Protobuf |
| Payload size | Medium | Small (client-controlled) | Smallest (binary) |
| Over/under fetching | Yes | No | No |
| Caching | Easy (HTTP cache) | Hard (POST) | Manual |
| Streaming | SSE/WebSocket | Subscriptions | Native bi-directional |
| Browser support | Native | Native | gRPC-Web only |
| Schema | OpenAPI (optional) | Mandatory | Mandatory (.proto) |

**Follow-up:** *"Why not GraphQL everywhere?"* → N+1 query risk, caching complexity, harder rate-limiting per resource.

---

### Q2. Idempotency kaise design karoge for payment API?

**Short:** Client sends `Idempotency-Key` header; server stores `(key → response)` for 24h. Duplicate request → return cached response.

**Deep:**
```python
@app.post("/charge")
async def charge(req: ChargeRequest, idem_key: str = Header(...)):
    cached = await redis.get(f"idem:{idem_key}")
    if cached:
        return json.loads(cached)

    # Lock to prevent concurrent duplicate
    lock = await redis.set(f"lock:{idem_key}", "1", nx=True, ex=30)
    if not lock:
        raise HTTPException(409, "Request in flight")

    try:
        result = await process_charge(req)
        await redis.set(f"idem:{idem_key}", json.dumps(result), ex=86400)
        return result
    finally:
        await redis.delete(f"lock:{idem_key}")
```

**Trade-offs:**
- Store full response, not just success flag (else retries fail differently).
- Hash request body and verify match — same key + different body = 422.
- TTL: 24h enough for retries, longer wastes memory.

---

### Q3. Pagination — offset vs cursor, kab kya?

**Short:**
- Offset (`?page=5&size=20`) → fine for <10K total, simple admin UIs.
- Cursor (`?after=eyJpZCI6MTIzfQ`) → infinite scroll, large datasets, real-time inserts.

**Deep:**
Offset pitfall: `OFFSET 100000 LIMIT 20` scans 100020 rows. Cursor uses indexed `WHERE id > last_id LIMIT 20`.

```python
# Cursor pagination
@app.get("/posts")
async def list_posts(cursor: str | None = None, limit: int = 20):
    last_id = decode_cursor(cursor) if cursor else 0
    posts = await db.fetch(
        "SELECT * FROM posts WHERE id > $1 ORDER BY id LIMIT $2",
        last_id, limit + 1
    )
    next_cursor = encode_cursor(posts[-1].id) if len(posts) > limit else None
    return {"items": posts[:limit], "next_cursor": next_cursor}
```

**Follow-up:** *"What if I sort by created_at DESC?"* → Cursor = `(created_at, id)` tuple to break ties.

---

### Q4. Rate limiting — algorithms aur trade-offs?

| Algo | How it works | Pros | Cons |
|---|---|---|---|
| Token Bucket | Add token/sec, consume per request | Burst allowed, smooth | Token state per user |
| Leaky Bucket | Fixed-rate queue drains | Smooth output | Queue memory |
| Fixed Window | Counter per minute | Simple | Burst at boundary (2x at 59-60s) |
| Sliding Window Log | Store every request timestamp | Accurate | Memory heavy |
| Sliding Window Counter | Weighted avg of current + prev window | Memory cheap, accurate | Complex |

**Production:** Sliding window counter via Redis (`INCR` + `EXPIRE`).

```python
async def rate_limit(user_id: str, limit: int = 100, window: int = 60) -> bool:
    now = int(time.time())
    key_current = f"rl:{user_id}:{now // window}"
    key_prev    = f"rl:{user_id}:{(now // window) - 1}"

    current, prev = await redis.mget(key_current, key_prev)
    current, prev = int(current or 0), int(prev or 0)

    elapsed_in_window = (now % window) / window
    weighted = prev * (1 - elapsed_in_window) + current

    if weighted >= limit:
        return False
    pipe = redis.pipeline()
    pipe.incr(key_current).expire(key_current, window * 2)
    await pipe.execute()
    return True
```

---

### Q5. API versioning strategies?

**Options:**
1. **URL path** — `/v1/users`, `/v2/users`. Most explicit, easy routing. (Stripe, GitHub)
2. **Header** — `Accept: application/vnd.api+json;version=2`. Clean URLs, harder for client devs.
3. **Query param** — `/users?v=2`. Easy testing, ugly URLs.
4. **Subdomain** — `v2.api.example.com`. Separate infrastructure per version.

**Best practice:** URL path for public APIs (clarity > purity). Header for internal where every service is versioned.

**Sunset policy:** Document for 6 months before kill. Add `Sunset:` HTTP header.

---

### Q6. Webhook vs polling vs SSE vs WebSocket — when?

```
Polling:           Client asks "anything new?" every N seconds
Long polling:      Server holds request open until event or timeout
SSE:               Server → Client one-way stream (text/event-stream)
WebSocket:         Bi-directional, binary or text
Webhook:           Server → Client URL push (server-to-server)
```

| Use case | Best fit |
|---|---|
| Order status update to user | SSE |
| Live chat | WebSocket |
| Stripe payment notification to your server | Webhook |
| Mobile app — low battery cost | Polling (with backoff) or push |
| GitHub events to CI | Webhook |

---

### Q7. HATEOAS — worth it?

**Short:** Hypermedia controls in REST responses (`_links: { next, prev, self }`).

**Reality:** Mostly theoretical. Used in PayPal API, NASA APIs. Most teams skip it because client devs ignore the links and hardcode URLs anyway.

**Use it when:** Long-lived public API where URL structure may evolve.

---

### Q8. Bulk operations — design kaise karein?

**Pattern: 207 Multi-Status**
```http
POST /users/bulk
[{"email":"a@x.com"}, {"email":"b@x.com"}, ...]

→ 207 Multi-Status
{
  "results": [
    {"index": 0, "status": 201, "id": "u_1"},
    {"index": 1, "status": 409, "error": "duplicate email"}
  ]
}
```

**Trade-offs:**
- All-or-nothing (transaction) vs partial success.
- Async (return job_id, poll status) for > 1000 items.
- Batch size limits (typically 100-1000).
- Idempotency: same body → same result (hash whole batch).

---

## SECTION 2 — DATABASE (Q9–Q16)

### Q9. ACID vs BASE — concrete examples?

**ACID (Postgres, MySQL):**
- Atomic: transaction all-or-nothing
- Consistent: constraints enforced
- Isolated: concurrent txns don't interfere
- Durable: committed = survives crash

**BASE (DynamoDB, Cassandra):**
- Basically Available: reads/writes always work
- Soft state: data may be stale
- Eventually consistent: converges over time

**When ACID:** Money, inventory, bookings.
**When BASE:** Likes, view counts, recommendations, logs.

---

### Q10. SQL vs NoSQL — decision matrix?

| Need | Pick |
|---|---|
| Joins across 3+ tables | SQL |
| Schema changes daily | NoSQL (Mongo) |
| Counter at scale (likes) | Redis / Cassandra |
| Full-text search | Elasticsearch |
| Graph traversal (friends-of-friends) | Neo4j |
| Time-series (metrics) | TimescaleDB / InfluxDB |
| ACID + complex queries | Postgres |
| 100K writes/sec, eventual OK | Cassandra |
| Document storage (CMS) | MongoDB |

---

### Q11. Sharding strategies?

```
Range sharding:    user_id 1-1M → shard1, 1M-2M → shard2
Hash sharding:     hash(user_id) % N → shardN
Geo sharding:      country code → region shard
Directory:         lookup table maps key → shard
```

| Strategy | Pros | Cons |
|---|---|---|
| Range | Range queries fast | Hotspots (recent users) |
| Hash | Even distribution | Range queries hit all shards |
| Geo | Latency, compliance | Skew (US >> Antarctica) |
| Directory | Flexible | Lookup overhead, dir is SPOF |

**Resharding pain:** Hash mod N → all keys move when N changes. Use **consistent hashing** (virtual nodes) → only K/N keys move.

---

### Q12. Master-slave replication — flow + failure?

```
Master    Slave1    Slave2
  │         │         │
  │ writes  │         │
  ├────────►│         │
  │         │ async   │
  ├────────►│────────►│
  │         │         │
  ▼ reads from any
```

**Failure modes:**
- Master dies → promote slave (manual or via Patroni/Orchestrator).
- Replication lag → reads return stale data. Fix: read-after-write to master.
- Split brain → two masters accept writes (use fencing tokens / quorum).

---

### Q13. Strong consistency vs eventual — implementation?

**Strong:**
- Single primary, sync replication, read from primary.
- Cost: latency (wait for replica ack), reduced availability.

**Eventual:**
- Async replication, read from any node.
- Conflict resolution: last-write-wins, vector clocks, CRDTs.

**Read-your-writes:** Stick session to primary for N seconds after write.

---

### Q14. Database indexing — when does it hurt?

**Hurts:**
- Heavy write workload (each insert updates N indexes).
- Indexes larger than RAM → random IO.
- Low-cardinality column (gender → 2 values, index useless).
- Over-indexing (every column → bloated, slow writes).

**Index types:**
- B-tree: range, equality, prefix LIKE.
- Hash: exact equality only.
- GIN: full-text, JSONB, arrays.
- BRIN: huge tables, naturally ordered (time-series).
- Partial: `WHERE status='active'` only.
- Covering: include extra columns to avoid table lookup.

---

### Q15. Connection pooling — config?

```
DB max_connections:  200
App replicas:        10
Pool per replica:    15 (overhead room)
Total connections:   150 (75% of max)
```

**Tools:**
- App-level: SQLAlchemy pool, asyncpg pool.
- External: PgBouncer (transaction-pooling for Postgres → 10K clients on 100 conns).

**Common bug:** Lambda with `min_size=10` → cold start opens 10 conns × 1000 lambdas = 10K conns → DB dies.

---

### Q16. Soft delete vs hard delete?

**Soft (`deleted_at IS NULL`):**
- Pros: undo, audit, compliance.
- Cons: every query needs `WHERE deleted_at IS NULL`, indexes bloat, GDPR conflict.

**Hard (`DELETE`):**
- Pros: clean, fast, GDPR-friendly.
- Cons: gone forever.

**Hybrid:** Soft for 30 days (recovery window), then hard delete via cron.

---

## SECTION 3 — CACHING (Q17–Q22)

### Q17. Cache-aside vs write-through vs write-behind?

```
Cache-aside (lazy):
  read:  cache miss → DB → write to cache → return
  write: write to DB → invalidate cache
  Pros: simple. Cons: first read slow, can serve stale.

Write-through:
  write: write to cache + DB synchronously
  Pros: fresh cache. Cons: slow writes.

Write-behind (write-back):
  write: write to cache → return → async flush to DB
  Pros: fast writes. Cons: data loss on cache crash.

Read-through:
  Cache is in front of DB; cache fetches on miss.
  Pros: transparent. Cons: need cache plugin/loader.
```

---

### Q18. Cache stampede — prevention?

**Problem:** Hot key expires → 10K requests hit DB simultaneously.

**Fixes:**
1. **Lock + double-check**: First request acquires lock, others wait/serve stale.
2. **Probabilistic early refresh**: Refresh when 80% TTL elapsed, randomly.
3. **External cache populator**: Cron warms cache before expiry.

```python
async def get_with_lock(key: str, loader):
    val = await redis.get(key)
    if val: return val

    lock = await redis.set(f"lock:{key}", "1", nx=True, ex=30)
    if lock:
        try:
            val = await loader()
            await redis.set(key, val, ex=3600)
            return val
        finally:
            await redis.delete(f"lock:{key}")
    else:
        await asyncio.sleep(0.1)
        return await redis.get(key)  # other process should have set it
```

---

### Q19. Cache invalidation — top 3 strategies?

1. **TTL** — simple, accepts staleness. Most common.
2. **Write-invalidate** — on DB write, `DEL` cache. Risk: race condition (read between DEL and update).
3. **Versioned key** — `user:123:v5`. Bump version on write, old cache GCs naturally.

**The hard one:** *"How do you invalidate cache when DB is updated by another service?"*
→ Pub/sub on DB CDC (Debezium → Kafka → cache invalidator).

---

### Q20. Redis vs Memcached?

| Feature | Redis | Memcached |
|---|---|---|
| Data structures | strings, lists, sets, sorted sets, streams, geo | strings only |
| Persistence | RDB + AOF | None |
| Replication | Yes (master-slave, cluster) | No |
| Eviction | 8 policies | LRU only |
| Pub/sub | Yes | No |
| Lua scripting | Yes | No |
| Multi-thread | Single (mostly) | Multi-thread |

**Use Redis** for 95% cases. Memcached only if pure key-value, max throughput, no persistence needed.

---

### Q21. Multi-level cache — design?

```
Browser cache  →  CDN  →  App-local (in-memory)  →  Redis  →  DB
   5min            1h           30s                  5min
```

Each layer absorbs traffic. App-local (LRU dict / `cachetools`) saves Redis round-trip for hot keys.

**Cache stack invariant:** TTL increases as you go deeper from user (browser short, CDN long).

---

### Q22. Cache key design — best practices?

```
✓ Good:  user:123:profile:v2
✓ Good:  product:abc:detail
✗ Bad:   123 (no namespace)
✗ Bad:   user.123.profile (some Redis tools mis-parse dots)
```

**Rules:**
- Colon-separated namespaces.
- Include version → easy schema evolution.
- Lowercase, kebab or snake.
- Avoid spaces, control chars.
- Max length 250 bytes (Memcached limit, Redis allows more but be sane).

---

## SECTION 4 — SCALING & DISTRIBUTED (Q23–Q30)

### Q23. Vertical vs horizontal scaling?

**Vertical:** Bigger box (more CPU/RAM). Pros: simple, no code change. Cons: hardware ceiling, single point of failure.

**Horizontal:** More boxes. Pros: ~linear scale, fault tolerance. Cons: stateless app required, distributed systems complexity (consistency, coordination).

**Rule of thumb:** Vertical until you can't, then horizontal.

---

### Q24. Load balancer — L4 vs L7?

| Layer | What it sees | Use |
|---|---|---|
| L4 (TCP) | IP, port | High throughput, raw TCP |
| L7 (HTTP) | URL, headers, cookies | Routing by path, sticky sessions, TLS termination |

**Algorithms:**
- Round-robin
- Least connections
- IP hash (sticky)
- Weighted (heterogeneous backends)

**Health checks:** Active (LB probes) vs passive (count failures from real traffic).

---

### Q25. CAP theorem — practical interpretation?

In a network partition (P), choose:
- **CP (consistency)**: Refuse requests, no split-brain. Examples: Zookeeper, etcd, MongoDB (default).
- **AP (availability)**: Accept writes on both sides, reconcile later. Examples: Cassandra, DynamoDB, CouchDB.

**Real world:** Networks usually don't partition. Latency-vs-consistency (PACELC) matters more day-to-day.

---

### Q26. Distributed lock — Redlock vs Zookeeper?

**Redlock (Redis):**
```python
async def acquire(key: str, ttl: int = 30):
    token = uuid.uuid4().hex
    ok = await redis.set(f"lock:{key}", token, nx=True, ex=ttl)
    return token if ok else None

async def release(key: str, token: str):
    lua = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """
    await redis.eval(lua, 1, f"lock:{key}", token)
```

**Caveats:** Clock drift, network delays → not safe under adversarial conditions. For correctness-critical, use Zookeeper / etcd (consensus-backed).

---

### Q27. Saga vs 2PC for distributed transactions?

**2PC:**
1. Prepare → all participants vote.
2. Commit/abort → all execute.
- Blocking, coordinator SPOF. Used in XA (Java EE).

**Saga:**
- Sequence of local txns + compensating txns.
- Choreography (event-driven) or orchestration (central coordinator).
- Eventually consistent.

**Example saga:** Order → Payment → Inventory → Ship.
If inventory fails: refund payment + cancel order.

---

### Q28. Eventually consistent — how to handle in UI?

**Patterns:**
1. **Optimistic UI**: Show update immediately, rollback on error.
2. **Read-your-writes**: Route reads to primary for N seconds after write.
3. **Versioned reads**: Return version with each write; client polls until that version reaches replica.
4. **Pull-on-demand**: User refresh triggers consistency check.

---

### Q29. Service discovery — client-side vs server-side?

**Client-side (Netflix Eureka, Consul):**
- Client queries registry, gets instance list, picks one.
- Pros: less hops, smarter routing.
- Cons: client library per language.

**Server-side (Kubernetes Service, AWS ELB):**
- Client → LB → instance.
- Pros: language-agnostic, simpler client.
- Cons: extra hop, LB SPOF.

K8s default is server-side via `kube-dns` + `Service` ClusterIP.

---

### Q30. Circuit breaker — states + config?

```
CLOSED ──(failures > threshold)──► OPEN
  ▲                                  │
  │                                  │ (after timeout)
  │                                  ▼
HALF-OPEN ◄──(probe request)── HALF-OPEN
  │
  └─ (success) → CLOSED
  └─ (fail) → OPEN
```

**Config:**
- `failure_threshold`: 50% errors in last 20 requests.
- `timeout`: 30s before probing.
- `half_open_max_calls`: 5 probes allowed.

**Use:** Wrap every external call (DB, downstream service, third-party).

---

## SECTION 5 — ASYNC & MESSAGING (Q31–Q36)

### Q31. Celery vs RQ vs Dramatiq vs Arq?

| Framework | Broker | Use |
|---|---|---|
| Celery | Redis/RabbitMQ/SQS | Mature, feature-rich, heavy |
| RQ | Redis only | Simple Python jobs |
| Dramatiq | Redis/RabbitMQ | Faster than Celery, less features |
| Arq | Redis | Async-native (asyncio) |

**Pick Celery** for legacy / chains / large team. **Arq** for new async-first projects.

---

### Q32. At-least-once vs exactly-once delivery?

**At-most-once:** Fire and forget. Loss possible.
**At-least-once:** Retry on failure. Duplicates possible. **Default for production.**
**Exactly-once:** Idempotency or transactional outbox + dedup on consumer.

**Real exactly-once doesn't exist** in distributed systems without coordinator. Achieve via at-least-once + idempotent consumers.

---

### Q33. Dead-letter queue — design?

```
Main Queue ──► Worker ──(N retries fail)──► DLQ
                                              │
                                              ├─ Alert
                                              ├─ Manual inspection
                                              └─ Replay tool
```

**Config:**
- Max retries: 3-5.
- Backoff: exponential (1s, 5s, 25s).
- DLQ retention: 14 days.
- Alarms on DLQ size > 0.

---

### Q34. Kafka vs RabbitMQ vs SQS?

| Need | Pick |
|---|---|
| Event streaming, replay, high throughput | Kafka |
| Complex routing (topic exchange) | RabbitMQ |
| Managed, simple, AWS native | SQS |
| Real-time analytics | Kafka |
| Task queue (Celery) | RabbitMQ or SQS |
| Pub/sub at billions msgs/day | Kafka |

---

### Q35. Outbox pattern — implementation?

**Problem:** Update DB + publish event. If only DB succeeds, event lost. If only event, DB inconsistent.

**Solution:**
```sql
BEGIN;
  UPDATE orders SET status='paid' WHERE id=123;
  INSERT INTO outbox (event_type, payload)
    VALUES ('order.paid', '{"order_id":123}');
COMMIT;
```

A separate poller reads `outbox` table → publishes to Kafka → marks rows processed.

**Or:** Debezium reads Postgres WAL → publishes to Kafka. No poller needed.

---

### Q36. Backpressure — how to handle?

When consumer slower than producer:
- **Buffer (queue):** Absorb spikes. Bounded → drops at limit.
- **Drop:** Random sample drop.
- **Reject:** 429 / 503 to client.
- **Slow down producer:** Token-based credit (HTTP/2 flow control).
- **Scale consumers:** Auto-scale on queue depth.

Kafka has natural backpressure (consumer lag visible). RabbitMQ uses `prefetch` + bounded queues.

---

## SECTION 6 — SECURITY (Q37–Q42)

### Q37. JWT vs session — when?

**Session (server-side):**
- Token = opaque ID, server looks up in Redis.
- Pros: revocation easy, small token.
- Cons: requires session store.

**JWT (stateless):**
- Token = signed payload (claims).
- Pros: no DB lookup, microservices-friendly.
- Cons: can't revoke instantly, larger token, secret rotation hard.

**Production:** JWT short-lived (15min) + refresh token in DB. Refresh token revocable.

---

### Q38. OAuth2 flows — which when?

| Flow | Use case |
|---|---|
| Authorization Code (+ PKCE) | Web app, mobile, SPA |
| Client Credentials | Server-to-server |
| Device Code | TV, IoT |
| Implicit | **DEPRECATED** (security holes) |
| Resource Owner Password | **Avoid** (only for legacy migration) |

PKCE = Proof Key for Code Exchange. Prevents auth code interception on mobile.

---

### Q39. SQL injection — prevention?

```python
# ✗ Vulnerable
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# ✓ Parameterized
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# ✓ ORM (preferred)
session.query(User).filter(User.id == user_id).first()
```

**Defense in depth:**
- Use ORM / prepared statements.
- Least-privilege DB user.
- WAF as backup.
- Validate input format (e.g., uuid).

---

### Q40. CORS — why it exists, how to configure?

**Why:** Browser same-origin policy → JS on `evil.com` can't read `bank.com` cookies.

CORS = controlled exception. `bank.com` says "yes, `myapp.com` can call me".

```python
# FastAPI
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],   # specific, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)
```

**Trap:** `allow_origins=["*"]` + `allow_credentials=True` → browser rejects.

---

### Q41. Secrets management — at scale?

**❌ Don't:** `.env` committed, hardcoded in code, plaintext in DB.

**✓ Do:**
- AWS Secrets Manager / GCP Secret Manager / HashiCorp Vault.
- K8s External Secrets Operator → syncs Vault → K8s Secret → env var.
- Rotation policy (90-day for static, automatic for managed).
- Encryption at rest (KMS) + in transit (TLS).

**Bonus:** Sealed Secrets for GitOps (encrypted before commit).

---

### Q42. CSRF — still relevant in 2026?

**Yes, if:** You use cookie auth.

**Defense:**
- `SameSite=Lax` or `Strict` cookies.
- CSRF tokens (double-submit cookie pattern).
- Custom header (`X-Requested-With`) — browsers forbid setting it cross-origin.

**No CSRF risk if:** Bearer token in `Authorization` header (since attackers can't set cross-origin headers).

---

## SECTION 7 — OBSERVABILITY (Q43–Q46)

### Q43. Logs, metrics, traces — three pillars?

| Pillar | Question answered | Tool |
|---|---|---|
| Logs | What happened? | Loki, ELK, CloudWatch |
| Metrics | How many / how fast? | Prometheus, Datadog |
| Traces | Where did it spend time? | Jaeger, Tempo |

**Best practice:** Same `trace_id` across all three → click metric anomaly → see traces → see logs.

---

### Q44. Logging — structured vs unstructured?

```python
# Unstructured (don't)
logger.info(f"user {user_id} logged in from {ip}")

# Structured (do)
logger.info("user_login", user_id=user_id, ip=ip)
# → {"event":"user_login","user_id":123,"ip":"1.2.3.4","ts":"..."}
```

**Why:** Searchable, aggregatable. `count by user_id` → trivial.

Use `structlog` in Python. Always log JSON to stdout, let log shipper handle the rest.

---

### Q45. SLA / SLO / SLI?

- **SLI** (indicator): Actual measurement (request success rate).
- **SLO** (objective): Internal target (99.9% success).
- **SLA** (agreement): Customer-facing contract (99.5% or refund).

**SLA < SLO** by a margin (buffer for surprises).

**Error budget:** (1 - SLO) × period. 99.9% × 30 days = 43min/month allowed errors. Burn it → freeze releases.

---

### Q46. Distributed tracing — sampling?

**Why sample:** 1M req/sec × 1KB span = 1GB/sec → unaffordable.

**Strategies:**
- **Head-based:** Decide at request start (random N%).
- **Tail-based:** Buffer all spans, decide at end (e.g., always keep errors, 1% of success).
- **Adaptive:** Sample more during low traffic, less during peaks.

Production: Tail-based, keep 100% errors + slow + 1% normal.

---

## SECTION 8 — DEPLOYMENT & RELIABILITY (Q47–Q50)

### Q47. Blue-green vs canary vs rolling?

```
Rolling:    Replace pods one by one. Simple. Bad if v2 broken (50% serve broken).
Blue-green: v1 + v2 both up, switch LB. Easy rollback. Double infrastructure cost during.
Canary:     1% → 5% → 25% → 100%. Real traffic gradual. Needs metrics gate.
```

**Hybrid:** Most teams = rolling for minor releases + canary for risky ones.

---

### Q48. Zero-downtime DB migration?

**Expand-Contract:**
1. **Expand:** Add new column (nullable). Deploy app reading both old + new.
2. **Migrate:** Backfill new column from old.
3. **Cut over:** Deploy app writing only new.
4. **Contract:** Drop old column.

**Never:** Rename column + deploy at once. Old pods reading old name → 500.

---

### Q49. Health checks — liveness vs readiness?

| Check | Question | Failure action |
|---|---|---|
| Liveness | Am I alive? (deadlock-free) | Kill + restart pod |
| Readiness | Can I serve traffic? (deps up) | Remove from LB, don't kill |
| Startup | Did I finish booting? | Wait, don't kill |

**Common mistake:** Liveness checks DB. DB down → all pods restart → cascading failure. **Liveness should only check process-internal state.**

---

### Q50. RTO vs RPO — DR planning?

- **RTO** (Recovery Time Objective): How long until service back up. (e.g., 1 hour)
- **RPO** (Recovery Point Objective): How much data loss acceptable. (e.g., 5 minutes)

**Backup strategy maps to RPO:**
- RPO 0: synchronous replication (cost: latency).
- RPO 5min: async replication.
- RPO 1h: hourly snapshots.
- RPO 24h: daily backups.

**Test DR drills quarterly.** Untested backups = no backups.

---

## RAPID FIRE BONUS (Q51+)

| Q | Quick A |
|---|---|
| Why is HTTP/3 better? | UDP-based (QUIC), no head-of-line blocking, connection migration. |
| What is CDN edge compute? | Run code at CDN POPs (Cloudflare Workers, Lambda@Edge). |
| Read replica lag — how to detect? | Monitor `pg_stat_replication.replay_lag` / `SHOW SLAVE STATUS`. |
| What is a fencing token? | Monotonic counter to detect stale lock holder after pause. |
| Bulkhead pattern? | Isolate resources per service so one failure doesn't drain shared pool. |
| Hot partition? | Single shard/key getting disproportionate traffic. Salt the key. |
| Why use UUID v7 over v4? | v7 is time-ordered → better B-tree insert performance. |
| Snowflake ID? | 64-bit: timestamp + worker_id + sequence. Time-ordered, distributed. |
| Why prefer ULID over UUID? | Same time-ordering as UUID v7, shorter, URL-safe. |

---

## How to use this pack

1. **Week before interview:** Read all 50 Q.
2. **Day before:** Pick weak areas, deep-dive.
3. **During interview:** When asked design question, mentally locate which section it falls in → recall the trade-off matrix.

**Pro tip:** Interviewers love "it depends, here are the trade-offs" answers more than dogmatic "always use X" answers. **Sound like a senior, not a junior.**
