# System Design — Hands-On Lab
**DevOps Track · Phase 18 Practical**

## Prerequisites

These labs are written design exercises, not shell commands — that's expected for this phase (per the lesson file itself: "Read this if you're building/operating systems, not designing them from scratch in an interview"). What you need:

- A blank document/notebook (physical or `.md` file) to actually write your answers before checking the solution — the value here is in producing your own structured answer under a bit of time pressure, not reading someone else's
- Optional but recommended: a whiteboard tool (Excalidraw, tldraw, or literal paper) to sketch the architecture diagrams called for in each lab — system design is spatial reasoning as much as prose
- No infra required for Labs 1-3. Lab 4 optionally uses the Docker setups from Phases 15-17 (Postgres, Redis) if you want to make the CAP-theorem lab concrete instead of purely theoretical
- Give yourself a real time box per lab (45-60 min for Labs 1-2, 60-90 min for Lab 3) — system design interviews are timed, and writing under a clock is part of what you're practicing

---

## Lab 1: Basic — Design a Rate Limiter for an API Gateway

**Objective:** Apply the API Gateway and load-balancing concepts from the lesson to a concrete, scoped design problem.

**Task:** Write a structured answer (aim for 300-500 words + a simple diagram) covering:
1. Where does the rate limiter sit in the request path relative to the API Gateway described in the lesson (`Client → API Gateway → [Auth, Rate Limiting, Routing, TLS termination] → Backend services`)? Why there and not inside each individual backend service?
2. Name and briefly describe TWO rate-limiting algorithms (e.g. token bucket, sliding window) and state which one you'd pick for a public API with bursty-but-fair traffic, and why.
3. Where does the rate limiter's STATE (request counts) live if you're running 3 replicas of the API Gateway behind a load balancer? Why can't each replica just keep counts in local memory?
4. What HTTP status code and response headers should a rate-limited client receive, and why does that matter for well-behaved API consumers?
5. One sentence: what happens to your rate limiter's correctness during a network partition between gateway replicas and the shared state store — which side of CAP are you implicitly choosing?

<details>
<summary>Solution / walkthrough</summary>

**1. Placement:** The rate limiter sits inside the API Gateway layer, before requests are routed to backend services — exactly per `Client → API Gateway → [Auth, Rate Limiting, Routing, TLS termination] → Backend services`. Putting it here (not in each service) means you instrument ONE layer instead of every service, which is precisely the gateway's stated value in the lesson ("single ingress point... one place to enforce auth, rate limits"). If each backend service enforced its own limits, a client could still exhaust shared downstream resources (DB connections, a third-party API's own rate limit) before any individual service's local counter tripped, and you'd have to keep N services' rate-limit logic consistent instead of one.

**2. Algorithms:**
- **Token bucket**: a bucket holds up to N tokens, refilled at a fixed rate; each request consumes a token, requests are rejected when the bucket is empty. Allows bursts up to the bucket size while enforcing a long-run average rate.
- **Sliding window log/counter**: tracks request timestamps (or counts per sub-window) over a rolling time period, rejecting once the count in the window exceeds the limit. More precise than a fixed window (no edge-of-window burst-doubling bug) but more expensive to track exactly.

For a public API with "bursty-but-fair" traffic, **token bucket** is the better fit — it explicitly allows short bursts (a client catching up after being idle) while still bounding the sustained rate, which matches real client behavior (a mobile app syncing after being backgrounded) better than a strict sliding window that would reject the burst outright.

**3. Shared state:** with 3 gateway replicas behind a load balancer, a client's requests can land on any replica. If each replica counted locally, a client could get 3x the intended limit by spreading requests across replicas (or by the LB's own algorithm distributing them). The counts must live in a shared, fast store — Redis is the standard choice (`INCR` with a TTL per window, or a Lua script implementing token bucket atomically) precisely because it's fast enough not to add meaningful latency and because `INCR` is atomic, avoiding race conditions between replicas incrementing the same counter concurrently.

**4. Response contract:** `429 Too Many Requests`, with `Retry-After` (seconds until the client should retry) and ideally `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset` headers. This matters because well-behaved API clients use these headers to back off correctly instead of hammering the API in a tight retry loop — a rate limiter with no `Retry-After` header just trades "the API is overloaded" for "the API is now ALSO fielding a retry storm."

**5. CAP tradeoff:** if the gateway can't reach the shared Redis state store during a partition, you must choose: fail closed (reject all requests — strict correctness on the limit, but you've taken yourself down, an availability sacrifice) or fail open (allow all requests through unlimited — availability preserved, but the rate limit's correctness guarantee is gone for the duration of the partition). Most production rate limiters fail open with a fallback local/degraded limit, explicitly choosing availability over strict correctness for this specific mechanism, because an over-permissive rate limiter for a few seconds is a much smaller blast radius than an outage.
</details>

---

## Lab 2: Intermediate — Design the Failover Story for a Multi-AZ Service

**Objective:** Apply the HA/Fault Tolerance and CAP concepts to a concrete deployment topology, matching the "Postgres primary + read replica split across two AZs" scenario in the lesson.

**Task:** You're operating an order-processing service. Requirement: "must survive a full AZ outage with no data loss and under 2 minutes of downtime." Write a structured answer covering:
1. Sketch (describe in words or draw) the topology across 2 AZs: app tier, load balancer, database. Where does each component live, and how many replicas of each?
2. Given the RPO/RTO implied by "no data loss, under 2 minutes downtime" — what does this force you to choose for database replication mode (sync vs async), and what's the latency cost you're accepting?
3. Walk through, step by step, what happens automatically vs what needs a human when AZ-a (holding the primary DB) goes dark. Use the concepts from the lesson: health checks, service discovery, load balancer behavior.
4. Identify the single biggest remaining single point of failure in your design, and propose a fix (even if it adds cost/complexity) — explicitly state the tradeoff you're now making.
5. State which side of CAP this whole design lands on during a partition, and defend it in 2 sentences using the lesson's own framing.

<details>
<summary>Solution / walkthrough</summary>

**1. Topology:**
```
                        [ Route53 / DNS health-checked failover ]
                                       │
                        [ Load Balancer — spans both AZs ]
                        /                                 \
        AZ-a                                              AZ-b
   [App pods x2]  <──same target group──>            [App pods x2]
        │                                                    │
   [Postgres PRIMARY]  ──synchronous replication──>  [Postgres REPLICA]
```
App tier: minimum 2 replicas per AZ (4 total), stateless, registered with the LB in both AZs. Database: 1 primary in AZ-a, 1 synchronous standby in AZ-b. The LB itself must be a managed multi-AZ LB (ALB/NLB) — never a single-instance LB, or it becomes the SPOF the whole design was built to avoid.

**2. Replication mode:** "No data loss" means RPO = 0, which forces **synchronous replication** (`synchronous_commit = remote_apply` per the Databases lesson) — async replication risks losing the last few seconds of writes exactly like the lesson describes for the primary-crash scenario. The cost: every write now waits for the AZ-b standby to apply the WAL before the primary confirms to the client — meaningfully higher write latency (cross-AZ round trip, typically single-digit ms extra, but real) than async. This is the explicit CP choice the lesson calls out: "Multi-AZ RDS with synchronous replication is a CP choice (failover waits for sync ack)."

**3. Failover sequence:**
- **Automatic:** the LB's health checks stop receiving 200s from AZ-a app pods (or the DB connection check inside the readiness probe starts failing) — traffic is automatically routed to AZ-b app pods within the LB's health-check interval (seconds). This part needs no human.
- **Needs orchestration (often automated by RDS Multi-AZ / Patroni, but worth knowing what it's doing):** the AZ-b standby must be promoted to primary. With a managed service (RDS Multi-AZ) this is automatic, typically 60-120 seconds. With self-managed Postgres, this needs an automated failover tool (Patroni + a consensus store like etcd/Consul) — doing this manually (a human running `pg_promote()`) blows the 2-minute RTO budget almost immediately once you factor in paging/detection time.
- **After promotion:** app pods in AZ-b need to reconnect to the newly-promoted primary — this is where a stable DNS name/service-discovery layer that gets updated on promotion (not a hardcoded IP) matters, tying back to the lesson's Service Discovery section.

**4. Remaining SPOF:** the promoted AZ-b database is now a single instance with NO standby of its own until a new replica is provisioned — if AZ-b also fails before a new standby exists, you're back to a full outage. Fix: provision a third replica in a third AZ (3-AZ topology) so you always have a standby even immediately after one failover — tradeoff: full 3x infrastructure cost for the database tier instead of 2x, for a failure mode (two AZs failing close together) that's rare but not impossible, and the cost has to be justified against the actual RTO/RPO the business is paying for (per the lesson: "the business requirement should drive the spend, not the other way around").

**5. CAP verdict:** this design is explicitly **CP** — during a network partition between AZ-a and AZ-b, writes on the primary will block waiting for synchronous replication ack rather than risk confirming a write that could be lost, exactly the "Choose Consistency (CP)" branch in the lesson's concrete partition scenario. We accepted higher write latency and a system that can stall (not silently lose data) during a partition, because the stated requirement was zero data loss — an AP choice (keep serving writes, risk losing the last few seconds on failover) would have violated the explicit "no data loss" requirement.
</details>

---

## Lab 3: Advanced — Design a URL Shortener (Full Written Answer)

**Objective:** The classic system-design interview problem, answered with DevOps-lens rigor — covering CAP tradeoffs and horizontal scaling explicitly, not just "here's an API and a DB schema."

**Task:** Write a structured design doc (aim for 600-900 words, this is the capstone exercise for the phase) covering ALL of the following sections. Time-box yourself to 60-90 minutes, written as if you were handing this to a team about to build it.

1. **Requirements** — functional (shorten a URL, redirect a short URL to original) and non-functional (scale numbers: assume 100M new URLs/month, 10:1 read:write ratio, must handle a viral link getting 50K redirects/minute).
2. **API design** — the two core endpoints, request/response shapes.
3. **ID generation strategy** — compare at least two approaches (e.g. base62 encoding of an auto-increment ID vs a distributed ID generator like Snowflake vs hash-and-check) and justify your pick given the scale in (1).
4. **Data model + storage choice** — what does a row/document look like, and which database type (SQL vs NoSQL) fits better here and why, tying back to the Databases phase.
5. **Caching layer** — where would you put a cache (tying back to Phase 17) given the 10:1 read-heavy ratio and the "viral link" spike scenario, and which caching pattern from the lesson applies.
6. **Horizontal scaling plan** — what's stateless and scales horizontally trivially, and what's the hard part to scale (tie back to the Horizontal vs Vertical Scaling table in the lesson).
7. **CAP tradeoff** — explicitly state which side of CAP your data store choice lands on and why that's acceptable for THIS use case (compare to the lesson's etcd/DynamoDB examples).
8. **Failure mode walkthrough** — what happens to the system if the cache layer goes down entirely for 5 minutes during the viral-link spike? Does it degrade gracefully or fall over?

<details>
<summary>Solution / walkthrough</summary>

**1. Requirements**
Functional: `POST /shorten {long_url}` → returns a short code; `GET /{short_code}` → 301/302 redirect to the original URL. Non-functional: 100M writes/month ≈ 40 writes/sec average (bursty, plan for 5-10x peak); 10:1 read:write means ~400 reads/sec average; a viral link at 50K redirects/minute ≈ 833 reads/sec for THAT SINGLE KEY — this last number is the one that drives the caching design, not the aggregate average.

**2. API design**
```
POST /shorten
  body: { "long_url": "https://example.com/very/long/path" }
  response: { "short_code": "aZ3xQ1", "short_url": "https://short.ly/aZ3xQ1" }

GET /{short_code}
  response: 301 Location: <original long_url>
```
301 (permanent redirect) vs 302: 301 lets browsers cache the redirect client-side, reducing load on the service for repeat visits to the same short link — a deliberate choice given the read-heavy profile, at the cost of losing per-click analytics unless you track clicks another way (e.g., a beacon or async log before the redirect fires).

**3. ID generation**
- *Auto-increment + base62 encode*: simplest, guarantees uniqueness, but a single auto-increment counter is a write bottleneck/SPOF at 40+ writes/sec sustained across multiple app instances unless centralized (defeats horizontal scaling of the write path).
- *Hash-and-check*: hash the long URL (e.g. MD5, take first 6-8 chars, base62), check for collision, retry with a salt if collided. No central counter needed, but adds a DB read-before-write on every shorten call, and collision handling adds tail latency.
- *Distributed ID generator (Snowflake-style)*: each app instance/worker gets a unique machine ID and generates IDs locally (timestamp + machine ID + sequence) with no coordination needed per request, then base62-encodes the ID. **Chosen approach**: at 40 writes/sec average with expected bursts, avoiding any centralized coordination on the write path is worth the added deployment complexity (machine ID assignment) — this is exactly the horizontal-scaling-of-a-stateless-tier pattern the lesson emphasizes, applied to ID generation instead of just the web tier.

**4. Data model + storage**
Row: `{short_code (PK), long_url, created_at, expires_at (nullable), click_count}`. Access pattern is pure key-value lookup by `short_code` — no relational joins, no complex queries. This favors a **NoSQL key-value/wide-column store** (DynamoDB, Cassandra) over a relational DB: horizontal scaling of a key-value workload is a solved, well-supported path in these systems, whereas the lesson's own note applies directly — "horizontally scaling a relational database (sharding, read replicas) is a much bigger architectural project than adding pods." A relational DB (Postgres) would still WORK at this scale with a single well-indexed table and read replicas, and is a defensible alternative if the team already runs Postgres and doesn't want a second storage technology — but purpose-built KV storage is the more scalable default for a lookup-by-key-only workload at this write volume.

**5. Caching layer**
Cache-aside (Phase 17) in front of the datastore, keyed by `short_code`, is the natural fit: `GET /{short_code}` checks Redis first, falls back to the DB on miss, populates cache with a TTL. Given the 10:1 read:write ratio, this cache absorbs the vast majority of read traffic. For the viral-link spike specifically (833 reads/sec for ONE key), a bare cache-aside with TTL is exactly the stampede setup from Phase 17's Lab 3 — every time that hot key's TTL expires, hundreds of concurrent requests would miss simultaneously. Mitigation: apply the lock/single-flight pattern for cache repopulation, AND set a much longer TTL (or no TTL at all, with explicit invalidation only on `expires_at` changes) for entries once they're identified as hot, since a short-URL's target rarely changes after creation — unlike the user-profile example in Phase 17, staleness risk here is close to zero, so an aggressive, long-lived cache is safe and arguably makes more sense than in the caching lesson's default web-app examples.

**6. Horizontal scaling plan**
Stateless and trivially horizontal: the API/app tier (add pods behind a load balancer, per Phase 18's Horizontal vs Vertical table) and the ID-generation approach chosen above (no shared counter to bottleneck on). The Redis cache layer scales via Redis Cluster (Phase 15/17) if a single node's throughput or memory becomes the bottleneck. The hard part is the underlying datastore at very large scale — a KV store like DynamoDB/Cassandra is chosen specifically because it has a well-trodden horizontal sharding story (partition key = `short_code` hash), avoiding the "vertical-scale-until-forced-into-sharding" trap the lesson describes for relational databases.

**7. CAP tradeoff**
This system should be **AP-leaning**: a short URL that redirects to a few-seconds-stale version of `click_count`, or even (in a rare edge case) briefly returns a 404 for a just-created link that hasn't fully propagated, is a far smaller problem than the redirect service itself becoming unavailable during a partition. This mirrors the lesson's DynamoDB/Cassandra framing directly ("tunable, typically deployed AP — they stay available and reconcile later"), and is the opposite choice from the order-database CP example in Lab 2 of this file — the deciding factor is that a stale or eventually-consistent read here has near-zero business cost, unlike an order or payment record.

**8. Failure mode — cache down for 5 minutes during a viral spike**
Every request for the hot key now misses cache and hits the datastore directly — 833 reads/sec for one partition key against DynamoDB/Cassandra. A key-value store handles a single hot partition far better than a relational DB would (still bounded by that partition's own throughput limits — this is itself a known KV-store failure mode, a "hot partition," directly analogous to the MongoDB hot-shard problem from Phase 15). Without any mitigation, this degrades badly — elevated latency, possible throttling/throughput exceptions from the datastore, and if the app doesn't handle datastore errors gracefully, 5xx errors to end users on the viral link specifically (the worst possible link to have failing). Graceful degradation options: an in-app-process fallback cache (even a small local LRU cache per app instance, accepting slightly more staleness) as a second line of defense when Redis is unreachable, and circuit-breaking to serve a generic "please try again" page instead of hammering a struggling datastore — directly the Fault Tolerance concepts (bulkheads, circuit breakers, graceful degradation) from this same lesson file, applied to this specific failure.
</details>

---

## Lab 4 (optional): Debugging Scenario — "The Read Replica Is Lying"

**Objective:** A short, focused troubleshooting exercise connecting the CAP/replication theory to a real symptom — good preparation for a live debugging round in an interview.

**Task:** You're paged: "Users in our EU region are seeing their own just-placed orders show as 'not found' for a few seconds after checkout, then the order appears." The architecture: a single primary DB in `us-east-1`, with an async read replica in `eu-west-1` that the EU app tier reads from for GET requests (writes always go to the US primary). Write a short diagnosis (150-250 words) covering:
1. What's actually happening here, in CAP terms?
2. Is this a bug, or an inherent consequence of the architecture as designed?
3. Propose two different fixes with different tradeoffs — one that keeps the async replica (cheaper, some UX cost) and one that changes the architecture (more expensive, fixes it fully).

<details>
<summary>Solution / walkthrough</summary>

**1. What's happening:** this is textbook replication lag exposed as a user-facing bug. The write (order creation) commits on the `us-east-1` primary and returns success to the client immediately (async replication, per the Databases lesson — the primary doesn't wait for the replica). The very next request (checkout confirmation page) reads from the `eu-west-1` replica, which hasn't yet received/applied that specific write. This is exactly the AP behavior described in the System Design lesson's CAP scenario — the replica is "AP-leaning for reads," serving its last-known (stale) data rather than blocking or erroring.

**2. Bug or inherent consequence:** inherent consequence of the architecture, not a bug in the traditional sense — nothing is broken, the system is behaving exactly as async replication is defined to behave. It only LOOKS like a bug because the read-your-own-writes expectation was never explicitly designed for.

**3. Two fixes:**
- **Cheap, keeps async replica:** read-your-own-writes routing — immediately after a write, route that specific user's subsequent reads to the PRIMARY (not the replica) for a short window (e.g., session-flag or a few seconds via a "recently wrote" cache marker), then fall back to the replica once enough time has passed for lag to almost certainly have caught up. Keeps the cheap async replica and cross-region read latency benefit for everyone else, at the cost of some added routing logic and slightly higher primary load for a small subset of reads.
- **Expensive, architectural:** switch to synchronous or semi-synchronous replication for the EU replica (or a synchronous quorum write), guaranteeing the replica has the write before the primary confirms it — this is a CP choice, and it adds real write latency (cross-region round trip, likely 50-100ms+ US-EU) to EVERY write, for every user, to fix a UX issue that specifically only affects the read-immediately-after-write path. Worth it only if read-your-own-writes consistency is a hard product requirement everywhere, not just checkout.
</details>

---

## Self-Check Checklist

- [ ] Can you explain, unprompted, why most companies that think they need microservices actually need a well-modularized monolith first?
- [ ] Can you draw (even roughly) the difference between client-side and server-side service discovery, and name a real tool for each?
- [ ] Can you state which side of CAP etcd/ZooKeeper/Consul land on, and why that's the right choice for what they're used for?
- [ ] Given a real system you've touched (not a textbook example), can you say which side of CAP it lands on and defend why, the way the lesson's Senior Tip demands?
- [ ] Can you explain the difference between horizontal and vertical scaling well enough to say which one Kubernetes' HPA does and which one requires a pod restart?
- [ ] Can you walk through, end to end, "scale from 1,000 to 100,000 req/sec" the way the lesson's Interview Angle question expects (app tier → session state → LB/gateway → DB → async processing → observability)?
- [ ] Can you design a URL shortener from a blank page in under 60 minutes, covering ID generation, storage choice, caching, and CAP, without re-reading this lab?
- [ ] Can you explain why a load balancer's health check lying (`/healthz` returns 200 while the DB pool is exhausted) is the single most common cause of "prod is slow but kubectl says everything's healthy"?
- [ ] Can you explain read-your-own-writes consistency problems and propose a fix without being told the term first?
- [ ] Can you explain, in your own words, why "multi-region active-active with async replication" and "Multi-AZ RDS with synchronous replication" represent two different, deliberate CAP choices?
