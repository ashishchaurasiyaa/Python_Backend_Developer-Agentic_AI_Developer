# 11. The System Design Blueprint — A Framework for Any Question

> The most valuable doc in this entire curriculum. **Memorize this framework.** Every interview design question can be answered using this 6-step approach.

---

## Why This Framework Matters

Most candidates fail not because they don't know technology — they fail because they **dive into details too fast**, miss requirements, can't justify decisions, or wander aimlessly.

A **structured approach** signals senior thinking:
- Shows you can manage ambiguity
- Demonstrates trade-off analysis
- Lets interviewer guide you to specific areas
- Buys time to think while sounding deliberate

---

## The 6-Step Blueprint

```
Step 1: Clarify Requirements   (5-7 min)
   ├── Functional requirements
   ├── Non-functional requirements
   └── Constraints & assumptions

Step 2: Estimate Scale          (3-5 min)
   ├── Users, traffic, storage
   ├── Identify bottlenecks
   └── Pick the right scale-out approach

Step 3: High-Level Design       (10-15 min)
   ├── Identify services
   ├── Define APIs
   └── Communication patterns

Step 4: Deep Dive               (15-20 min)
   ├── Data models
   ├── Algorithms
   └── Edge cases (interviewer picks)

Step 5: Address Bottlenecks     (5-10 min)
   ├── Identify weak points
   ├── Apply patterns (cache, queue, shard)
   └── Trade-offs

Step 6: Wrap Up                  (5 min)
   ├── Summary of decisions
   ├── What you'd do differently
   └── Future improvements
```

**Total: ~45-60 minutes** (typical interview length)

---

## Step 1: Clarify Requirements (5-7 minutes)

**Goal**: Define exactly what you're building before designing.

### Functional Requirements

**Ask the interviewer:**
- What are the core features? (List 3-5 max)
- Who are the users? (consumers, sellers, admins)
- What's the most critical flow? (signup → action → outcome)

**Example: "Design Twitter"**
- ✅ Post tweets (text + media)
- ✅ Follow users
- ✅ Home timeline (chronological + algorithmic)
- ❌ DMs? (clarify — often out of scope)
- ❌ Trending? (clarify — could be out of scope)

**Pro tip**: Write each on the whiteboard as you confirm. This anchors the rest of the design.

### Non-Functional Requirements

**The 5 standard NFRs:**

| NFR | Question to ask | Example answer |
|---|---|---|
| **Scale** | How many users? | 100M MAU, 10M DAU |
| **Latency** | What's acceptable? | < 200ms P95 for reads |
| **Availability** | How much downtime OK? | 99.9% (= 43 min/month) |
| **Consistency** | Strong or eventual? | Eventual OK for feed |
| **Durability** | Can we lose data? | Tweets must persist; cache OK to lose |

### Constraints & Assumptions

**Write down explicitly:**
- Read/write ratio (e.g., 100:1 reads:writes)
- Mobile-heavy vs web-heavy
- Geographic distribution (global vs single region)
- Time window for feature (real-time vs daily batch)

**Example explicit statements:**
- "Assuming read-to-write ratio of 100:1"
- "Assuming users are global but mostly US-based"
- "Assuming we're building MVP — no multi-region for now"

### Red Flags to Avoid

❌ "Let me start by drawing the architecture" (without clarifying)
❌ Skipping NFRs (interviewer expects to hear them)
❌ Assuming requirements (always confirm)
❌ Spending > 10 minutes here (interviewer will get impatient)

---

## Step 2: Estimate Scale (3-5 minutes)

**Goal**: Convert vague requirements into concrete numbers that drive design decisions.

### Back-of-Envelope Math

**Standard formula approach:**

```
1. User scale:           100M users
2. DAU ratio:            10% × 100M = 10M DAU
3. Action rate:          DAU × actions/day = 10M × 5 tweets = 50M writes/day
4. Per-second rate:      50M / 86,400s = ~580 writes/sec
5. Peak factor (3-5x):   580 × 5 = ~3000 writes/sec
6. Reads (100:1):        3000 × 100 = ~300K reads/sec

7. Storage per item:     500 bytes/tweet
8. Daily storage:        50M × 500 = 25 GB/day
9. 5-year storage:       25 GB × 365 × 5 = ~45 TB
10. With media:          5x → 225 TB
```

### Common Numbers to Memorize

| Item | Size |
|---|---|
| Tweet/Post text | 500 bytes - 1 KB |
| User profile | 2-5 KB |
| Image (compressed) | 100 KB - 1 MB |
| Video (1 min, compressed) | 50-100 MB |
| HTTP request | 1 KB |
| Vector embedding (1536 dim) | 6 KB |
| 1 year of activity log | 100s of GB |

### Latency Cheat Sheet (Jeff Dean's numbers, updated)

| Operation | Latency |
|---|---|
| L1 cache | 0.5 ns |
| Branch mispredict | 5 ns |
| L2 cache | 7 ns |
| Mutex lock/unlock | 25 ns |
| Main memory access | 100 ns |
| Compress 1KB with Zippy | 3 μs |
| Send 1KB over 1Gbps network | 10 μs |
| Read 1MB from SSD | 50 μs |
| Disk seek | 10 ms |
| Read 1MB from disk | 30 ms |
| Round trip same DC | 0.5 ms |
| Round trip cross-region | 80-150 ms |
| LLM API call | 500ms - 30s |

### Identify Bottlenecks Early

After estimation, predict where things will break:

| If... | Bottleneck likely is... |
|---|---|
| Reads >> writes | Database read throughput → add cache/replicas |
| Writes very high | Single DB → shard or partition |
| Many small files | Disk IOPS → object storage |
| Real-time updates needed | Polling won't scale → WebSocket/SSE |
| Cross-region | Latency → CDN + edge compute |

---

## Step 3: High-Level Design (10-15 minutes)

**Goal**: Draw boxes and arrows showing the major components.

### Standard Components to Consider

```
┌─ Client ─┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Web/iOS  │→│   CDN    │→│    LB    │→│   API    │
│ Android  │  │ (static) │  │          │  │ Gateway  │
└──────────┘  └──────────┘  └──────────┘  └─────┬────┘
                                                │
              ┌─────────────────┬────────────────┼──────────────┬──────────────┐
              │                 │                │              │              │
          ┌───▼────┐       ┌────▼───┐      ┌─────▼────┐    ┌────▼────┐    ┌────▼────┐
          │Service │       │Service │      │ Service  │    │ Search  │    │  Auth   │
          │   A    │       │   B    │      │    C     │    │ Service │    │ Service │
          └───┬────┘       └────┬───┘      └─────┬────┘    └────┬────┘    └────┬────┘
              │                 │                │              │              │
          ┌───▼────────────────┬┴───────────┬────▼────┐    ┌────▼────┐    ┌────▼────┐
          │   PostgreSQL       │   Redis    │  Kafka  │    │ Elastic │    │  Vault  │
          │   (main store)     │ (cache)    │ (events)│    │ Search  │    │(secrets)│
          └────────────────────┴────────────┴─────────┘    └─────────┘    └─────────┘
```

### Decisions to Make Out Loud

**1. Monolith vs Microservices**
- Monolith: < 10 engineers, < 1M users
- Microservices: > 20 engineers, multi-team, scale matters

**2. SQL vs NoSQL vs Mixed**
- SQL (PostgreSQL): transactions, joins, ACID needed
- NoSQL (Cassandra/Dynamo): massive writes, eventual consistency
- Polyglot: mix per service

**3. Communication patterns**
- Sync: REST (user-facing), gRPC (internal)
- Async: Kafka (events), RabbitMQ (tasks)

**4. Real-time delivery**
- Push: WebSocket (chat), SSE (LLM streaming)
- Pull: polling (low-frequency)
- Hybrid: long-polling

### Define Core APIs

**Show 4-6 critical APIs:**

```
POST   /api/tweets                    # Create tweet
GET    /api/feed?cursor=...            # Home timeline
POST   /api/users/{id}/follow          # Follow user
GET    /api/search?q=...               # Search
```

Be specific about:
- Request shape (body / params)
- Response shape (data + pagination)
- Idempotency (POST with idempotency key)
- Auth (Bearer JWT)

---

## Step 4: Deep Dive (15-20 minutes)

**Goal**: Show technical depth on 2-3 specific areas the interviewer cares about.

### Common deep-dive areas

| Area | What to discuss |
|---|---|
| **Data model** | Table schemas, indexes, relationships, sharding key |
| **Critical algorithm** | Feed ranking, search ranking, matching |
| **Hot path** | The most performance-sensitive flow |
| **Data partitioning** | How you'd shard the data |
| **Cache strategy** | What to cache, TTL, eviction, invalidation |
| **Real-time delivery** | WebSocket, fan-out, pub/sub |
| **Storage layout** | Hot/cold separation, compression |

### Pattern: Data Model Discussion

```sql
-- Always start with the core entity
CREATE TABLE tweets (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL CHECK (length(content) <= 280),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, id)        -- partition by user_id for shard locality
);

-- Indexes for common queries
CREATE INDEX idx_tweets_user_time ON tweets(user_id, created_at DESC);

-- Then derived/related tables
CREATE TABLE follows (
    follower_id BIGINT,
    followed_id BIGINT,
    PRIMARY KEY (follower_id, followed_id)
);

-- Partition strategy
-- For 100M users, partition by hash(user_id) into 256 shards
```

**Always discuss:**
- Why this primary key?
- Why this index?
- How does it shard?
- How does it scale to 10x?

### Pattern: Algorithm Discussion

For "design Twitter feed":

```
Option A: Pull (compute on read)
- User requests feed → query latest tweets from all followed users → merge sort
- Pros: No precompute; works for inactive users
- Cons: Slow for users following 1000s; bursty load

Option B: Push (fan-out on write)
- User tweets → for each follower → write to their feed table
- Pros: Read is O(1); fast
- Cons: Celeb problem (Justin Bieber's 1 tweet = 100M writes)

Option C: Hybrid (this is the answer)
- Push for users with < 10K followers (most people)
- Pull for celebs at read time
- Merge at read time
```

Show that you considered alternatives. Pick one with explicit trade-offs.

### Pattern: Cache Strategy

```
Layer 1: CDN (Cloudflare)
  - Static assets, public timelines
  - TTL: 60 sec

Layer 2: Application cache (Redis)
  - Hot user profiles
  - Recent tweets (last 50 per user)
  - TTL: 5 min, LRU

Layer 3: Database query cache (PostgreSQL)
  - Repeated queries
  - Auto-managed
```

### Edge Cases to Discuss

Interviewer often asks: "What about [edge case]?"

Be ready for:
- **Celebrity user** (1M+ followers)
- **Hot key** (1 viral post)
- **Concurrent writes** (race conditions)
- **Network partition** (CAP trade-off)
- **Bot abuse** (rate limiting, captcha)
- **Cache stampede** (mutex, request coalescing)
- **Backpressure** (slow consumer kills producer)

---

## Step 5: Address Bottlenecks (5-10 minutes)

**Goal**: Show senior thinking by proactively identifying weak spots.

### Standard Bottleneck Patterns

| Bottleneck | Symptom | Solution |
|---|---|---|
| Single DB write throughput | High write latency | Shard / partition / write to log |
| Read amplification | DB CPU pegged | Cache / read replicas |
| Hot key | One row/key getting 90% traffic | Replicate hot keys to multiple shards |
| N+1 queries | App slow despite fast DB | Batch / DataLoader |
| Cross-region latency | Slow for distant users | CDN / edge computing / multi-region |
| Slow downstream | Tail latency p99 spikes | Timeout + circuit breaker |
| Memory leak | Pods OOM over time | Stateless + restart |
| Cache miss storm | DB DDoS on cache restart | Warm cache + request coalescing |
| Synchronous external call | Blocks event loop | Async + queue |

### Scaling Patterns Cheat Sheet

**For reads:**
- Read replicas (write to primary, read from replicas)
- Cache (Redis, Memcached)
- CDN (geographically distributed)
- Materialized views (precomputed)

**For writes:**
- Sharding (horizontal partitioning)
- Write-behind cache (Redis → DB async)
- Event sourcing (append-only log)
- Queue + worker (smooth bursts)

**For both:**
- Multi-region (active-active)
- Microservices (independent scaling)
- Async everything possible

---

## Step 6: Wrap Up (5 minutes)

**Goal**: Demonstrate self-awareness and big-picture thinking.

### Summary

Recap in 30 seconds:
- "We designed a system supporting 100M users at 3K writes/sec"
- "Key decisions: microservices, sharded PostgreSQL, hybrid feed (push + pull), Redis cache"
- "We addressed celeb problem with read-time merging, hot keys with replication"

### What You'd Do Differently

Show you can self-critique:
- "I'd validate the read/write ratio with actual production data"
- "I'd run a load test to confirm the cache hit rate assumption"
- "I'd consider a different sharding key if access patterns showed user-id hotspots"

### Future Improvements

Open-ended growth:
- Multi-region for global users (data residency too)
- ML-based ranking instead of chronological
- Real-time analytics pipeline
- A/B testing framework
- More granular monitoring

---

## Common Mistakes & How to Avoid Them

### ❌ Mistake 1: Going Deep Too Early

```
Interviewer: "Design Twitter"
Bad candidate: "Let me draw the database schema first..."
Good candidate: "Before I draw anything, let me clarify the scope..."
```

### ❌ Mistake 2: Not Doing Math

```
Bad: "We'll have a lot of users so we need to scale"
Good: "100M users × 5 tweets/day = 500M writes/day = 5800 writes/sec average,
       peak ~20K writes/sec. Single PostgreSQL won't handle that, so we shard."
```

### ❌ Mistake 3: Naming Tech Without Justifying

```
Bad: "We'll use Cassandra"
Good: "For 50M tweets/day with eventual consistency OK, Cassandra fits because:
       - Massive write throughput
       - Tunable consistency
       - But: we lose joins, which we don't need for the feed table"
```

### ❌ Mistake 4: Ignoring Failure Modes

```
Bad: Designs only the happy path
Good: "If the cache fails, we fall back to DB with rate limiting to prevent stampede.
       If the DB master fails, replica is promoted in < 1 min using Patroni."
```

### ❌ Mistake 5: No Trade-offs

Every decision has trade-offs. Mention at least one:
- "Cassandra gives write throughput at cost of joins and strong consistency"
- "Cache reduces DB load at cost of stale reads and invalidation complexity"
- "Microservices enable team autonomy at cost of operational overhead"

---

## Time Budget — Hour-Long Interview

```
0-5 min   :  Step 1 — Clarify requirements
5-10 min  :  Step 2 — Estimate scale
10-25 min :  Step 3 — High-level design
25-40 min :  Step 4 — Deep dive (interviewer-led)
40-50 min :  Step 5 — Address bottlenecks
50-55 min :  Step 6 — Wrap up
55-60 min :  Questions from candidate
```

**If running short on time:**
- Skim Step 2 (just state numbers, don't derive)
- Truncate Step 4 (let interviewer guide)
- Skip Step 6 details

---

## Interview Q&A — Framework Application

### Q: "I have 30 minutes, what do I focus on?"

**A:** Quick version:
- 3 min: Requirements
- 2 min: Scale
- 10 min: HLD diagram
- 10 min: Deep dive on ONE area (interviewer picks)
- 5 min: Bottlenecks + wrap

### Q: "What if the interviewer doesn't ask clarifying questions?"

**A:** YOU ask them. "Before I dive in, I have a few clarifying questions. Is X in scope? What's the user volume? Are we global day 1 or starting in one region?"

### Q: "How do I handle topics I don't know?"

**A:** Be honest + reason from first principles:
- "I haven't used Kafka in production, but here's what I know: it's a distributed log..."
- "I'd reach for X because of these properties, though there might be better options I'm unaware of"

Interviewer values honesty over fake expertise.

### Q: "What if I draw something wrong?"

**A:** Correct it openly: "On reflection, that approach has [issue]. Let me adjust..."
Showing you can self-correct is a senior signal.

### Q: "How important is the diagram quality?"

**A:** Functional > pretty. Clear boxes and labeled arrows beat polished diagrams. Use:
- Boxes for services / databases
- Arrows for data flow (label them!)
- Different shapes for storage (cylinder), cache (small box), queue (rectangle)

---

## Practice Routine (30 days)

**Week 1**: Practice the framework with simple problems
- URL shortener
- Pastebin
- Rate limiter

**Week 2**: Real-world products
- Twitter timeline
- WhatsApp chat
- Uber matching

**Week 3**: Complex distributed
- Google Drive
- Netflix streaming
- Stock exchange

**Week 4**: Modern (2026 relevant)
- ChatGPT backend
- RAG system
- Agent orchestration

For each problem:
1. Time yourself (60 min)
2. Write down each step
3. Compare against canonical answer
4. Identify what you missed → improve

---

## Memorization Anchors

Memorize these 6 words. Each is a step.

> **"Clarify, Estimate, Design, Deep-dive, Optimize, Wrap"**

Or in Hindi-friendly mnemonic:

> **"Samjho, Ginto, Banao, Khodo, Sudharo, Samaapt"**

---

## Templates to Write on Whiteboard at Start

```
=== Functional Requirements ===
1. _____________
2. _____________
3. _____________

=== Non-Functional Requirements ===
Scale: ___
Latency: ___
Availability: ___
Consistency: ___

=== Estimation ===
Users: ___M
Writes/sec: ___
Reads/sec: ___
Storage: ___ TB

=== Components ===
[draw architecture]

=== APIs ===
POST /...
GET  /...

=== Deep Dives ===
1. Data model
2. ___
3. ___

=== Bottlenecks ===
- ___ → solution
- ___ → solution
```

Having this template ready in your head = automatic structure.

---

## What Senior Candidates Do Differently

1. **State assumptions explicitly** — don't make interviewer guess
2. **Quantify decisions** — "this saves 60% latency", not "this is faster"
3. **Mention alternatives** — "I chose X over Y because..."
4. **Anticipate questions** — "If you ask about Z, here's how..."
5. **Time-box themselves** — "Spending 5 more min on this then moving on"
6. **Self-critique** — "One weakness in this design is..."
7. **Ask clarifying questions throughout** — not just at start
8. **Use familiar names** — "Like Netflix's Eureka for service discovery"

---

## Final Mantras

- **You're not graded on correctness.** You're graded on how you think.
- **There's no single right answer.** There are trade-offs.
- **Talk through your reasoning.** Silence = nothing to grade.
- **Use the framework as a safety net.** When lost, return to the 6 steps.

---

## Related Reading
- **Designing Data-Intensive Applications** — Martin Kleppmann (must-read)
- **System Design Interview Vol 1 & 2** — Alex Xu
- **The Architecture of Open Source Applications** — free online
- **github.com/donnemartin/system-design-primer**
- Original papers: Dynamo, BigTable, Spanner, Kafka, GFS

## Related Curriculum Docs
- [31_Back_of_Envelope_Estimation.md](../31_Back_of_Envelope_Estimation.md) — Step 2 deep
- [01_Monolithic_vs_Microservices.md](../01_Monolithic_vs_Microservices.md) — Step 3 decisions
- [08_CAP_Theorem.md](../08_CAP_Theorem.md) — Step 4 trade-offs
- [12_Load_Balancer.md](../12_Load_Balancer.md) — Step 3 components
- All [HLD_Problems/](../../HLD_Problems) — practice
