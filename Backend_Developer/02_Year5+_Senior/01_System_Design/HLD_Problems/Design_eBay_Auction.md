# Design an Auction Platform (eBay)

---

## 1. Understanding the Problem & Defining the Scope

### What is an Auction Platform?

A digital marketplace where:
- **Sellers** list items with auction parameters
- **Buyers** place bids in real-time within a defined auction window
- **Highest bid at closing time wins** the item
- System manages full lifecycle: listing → bidding → closing → payment → fulfillment

**Why it's interesting to design:**
- Real-time responsiveness (sub-second updates)
- Strict timing controls (race-to-close)
- Concurrency handling (multiple bids per second on hot items)
- Fairness (no bot/sniping advantage)
- Payment + fraud handling

---

### Functional Requirements

| # | Capability | Why critical |
|---|---|---|
| 1 | User registration + authentication | Buyers + sellers need accounts |
| 2 | Item listing with parameters | Start/end time, start bid, reserve price, buy-it-now |
| 3 | Real-time bid placement | Sub-second feedback (accepted/rejected/outbid) |
| 4 | Auction lifecycle management | scheduled → active → ended state machine |
| 5 | Real-time updates to all watchers | Everyone sees current bid instantly |
| 6 | Payment processing | Stripe/PayPal integration; track status |
| 7 | Notification system | Outbid, win, payment complete |
| 8 | Search + browse | Find auctions; filter by category, price, time |
| 9 | Bidder history + watchlist | Track auctions user cares about |
| 10 | Seller dashboard | List, manage, see bids |

---

### Non-Functional Requirements

| Requirement | Target |
|---|---|
| **Latency (bid placement)** | < 200ms p95 (accept/reject decision) |
| **Latency (real-time updates)** | < 500ms from bid → watchers see it |
| **Scalability** | 1M concurrent auctions, 100K concurrent watchers per auction |
| **Throughput (peak bid rate)** | 10K bids/sec globally; 100 bids/sec on hot item |
| **Availability** | 99.95% (4.4 hours/year downtime budget) |
| **Consistency** | Strong for bid ordering; eventual for views/notifications |
| **Security** | MFA for sellers, encrypted payments, bot detection |
| **Observability** | Per-bid trace, anomaly detection, fraud alerts |

---

### Constraints & Challenges

**Why these problems are HARD:**

1. **Real-time pressure**
   - Last-second bids ("sniping") happen in milliseconds
   - Need precise timestamp ordering (server clock authoritative)
   - Network latency varies by region

2. **Concurrency conflicts**
   - 50 users bid simultaneously on same item
   - Need ordering + idempotency (no double-charge, no lost bids)
   - Race conditions break trust

3. **Live updates at scale**
   - 100K viewers watching one auction → push to all instantly
   - WebSocket fan-out is non-trivial

4. **Payment reliability**
   - Stripe/PayPal can fail; need retry + reconciliation
   - Fraud detection (stolen cards, account takeover)
   - Escrow / dispute handling

5. **Fairness & trust**
   - Bot prevention (CAPTCHA, behavior analysis)
   - Anti-sniping (extend auction if late bids — eBay does this!)
   - Reserve price enforcement
   - Shill bidding detection (seller bidding on own item)

---

## 2. Estimating Scale & Identifying Bottlenecks

### Scale Estimation

**Assumptions (eBay-scale):**
- 200M users globally
- 100M active auctions at any time
- 5M auctions ending per day (average 1-7 day duration)
- Avg 10 bids per auction → **50M bids/day**
- Peak factor 5x (Sunday evening, holiday sales)

```
Bid rate:
- Avg:  50M / 86400 ≈ 580 bids/sec
- Peak: 580 × 5    ≈ 3,000 bids/sec
- Hot item peak:    100 bids/sec on one item (final 60 sec)

Concurrent users:
- 200M users × 1% online = 2M concurrent
- 10% of online watching auction = 200K WebSocket connections

Storage:
- Auctions: 100M × 5 KB = 500 GB
- Bids (kept 90 days): 50M/day × 90 × 500 bytes = 2.25 TB
- Images (5 per auction × 1MB × 100M) = 500 TB → S3 + CDN
- Search index: 100M auctions × 2KB = 200 GB

Bandwidth:
- WebSocket fan-out: 200K conn × 100 bytes × 10 msg/sec = 200 MB/sec
- Image serving via CDN: handled separately
```

### Bottlenecks Identified

| Bottleneck | Where | Why | Mitigation (preview) |
|---|---|---|---|
| **Hot item contention** | DB row for one auction | 100 bids/sec all updating same row | Per-auction queue + single writer; Redis-based atomic ops |
| **WebSocket fan-out** | Push to 200K watchers | Bandwidth + connection count | Pub/sub fan-out across edge servers |
| **Auction close storms** | Time-based ending | Thousands ending at same time | Stagger closes; sharded timer service |
| **Payment processing** | Stripe API | External, slow, can fail | Async queue + retry + idempotency |
| **Search index lag** | New auctions to index | Real-time indexing expensive | Near-real-time (NRT) with 30s lag acceptable |
| **Fraud detection latency** | Bid evaluation | ML model in critical path | Async post-bid + reactive flag |

---

## 3. High-Level Design: Services, APIs & Communication

### Service Decomposition (Why microservices here?)

**Why split into services:**
- Different scaling needs (bid service = high QPS; search = read-heavy)
- Different deployment cadence (bid service stable; UI changes daily)
- Failure isolation (image upload outage shouldn't kill bidding)
- Team autonomy (separate teams own different domains)

```
┌─────────────────────────────────────────────────────┐
│  Clients (Web, iOS, Android)                         │
└────────────────┬────────────────────────────────────┘
                 │ HTTPS / WSS
        ┌────────▼────────┐
        │  CDN / WAF      │ Cloudflare
        │  - DDoS         │
        │  - bot detect   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  API Gateway    │ rate limit, auth, routing
        │  (Kong/Envoy)   │
        └────────┬────────┘
   ┌─────────────┼─────────────┬─────────────┬────────────┐
   │             │             │             │            │
┌──▼──────┐ ┌────▼─────┐ ┌─────▼──────┐ ┌────▼────┐ ┌─────▼─────┐
│ User    │ │ Listing  │ │ BID        │ │ Search  │ │ Payment   │
│ Service │ │ Service  │ │ Service    │ │ Service │ │ Service   │
│         │ │          │ │ (hot!)     │ │         │ │           │
└──┬──────┘ └────┬─────┘ └─────┬──────┘ └────┬────┘ └─────┬─────┘
   │             │             │              │           │
   │             │      ┌──────▼──────┐       │           │
   │             │      │ Bid Engine  │       │           │
   │             │      │ (per-item   │       │           │
   │             │      │  workers)   │       │           │
   │             │      └──────┬──────┘       │           │
   │             │             │              │           │
   │  ┌──────────┼─────────────┼──────────────┼───────────┘
   │  │          │             │              │
┌──▼──▼──┐  ┌────▼─────┐  ┌────▼──────┐ ┌─────▼─────┐
│ Users  │  │ Auctions │  │ Bids      │ │ Search    │
│ DB     │  │ DB       │  │ DB        │ │ Index     │
│ (PG)   │  │ (PG)     │  │ (Cassandra│ │ (ES/Solr) │
└────────┘  └──────────┘  │  /Postgres│ └───────────┘
                          │  partitions)
                          └───────────┘

┌─────────────────────────────────────────────────────────┐
│  Async / Real-Time Layer                                │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────────┐  ┌────────────┐          │
│  │ Kafka   │  │ Redis       │  │ Timer       │          │
│  │ - bid   │  │ - hot bids  │  │ Service     │          │
│  │  stream │  │ - sessions  │  │ - auction   │          │
│  │ - events│  │ - pub/sub   │  │   ends      │          │
│  └─────────┘  └─────────────┘  └────────────┘          │
│                                                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │ Notification │ │ Fraud         │ │ WebSocket Hub    │ │
│  │ Service      │ │ Detection ML  │ │ - fan-out         │ │
│  │ (Email/SMS/  │ │               │ │ - presence        │ │
│  │  Push)       │ │               │ │                   │ │
│  └─────────────┘ └──────────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────┘

External:
- Stripe / PayPal (payments)
- SendGrid (email)
- Twilio (SMS)
- S3 + CloudFront (images)
- DataDog (observability)
```

---

### Core APIs (REST + WebSocket)

```python
# ─── REST API ───

# User
POST   /api/users/register
POST   /api/users/login
GET    /api/users/me

# Listing (Seller)
POST   /api/auctions                    # create new auction
PUT    /api/auctions/{id}               # edit before active
DELETE /api/auctions/{id}               # cancel (only before bids)
GET    /api/auctions/seller/{user_id}   # seller's auctions

# Browse / Search (Buyer)
GET    /api/auctions?category=&query=&sort=ending_soon&page=
GET    /api/auctions/{id}               # auction detail + current bid

# Bidding
POST   /api/auctions/{id}/bids          # place bid
GET    /api/auctions/{id}/bids          # bid history (paginated)
POST   /api/auctions/{id}/buy-now       # instant purchase
GET    /api/users/me/active-bids        # bids I'm currently winning/losing
GET    /api/users/me/watchlist          # auctions I'm watching
POST   /api/users/me/watchlist/{id}     # add to watchlist

# Post-auction
GET    /api/auctions/{id}/result        # who won, final price
POST   /api/auctions/{id}/payment       # initiate payment
GET    /api/auctions/{id}/shipping      # tracking info


# ─── WebSocket ───
# wss://ws.auction.com/v1/connect
# Subscribe pattern:
# → { "action": "subscribe", "channel": "auction:42" }
# → { "action": "subscribe", "channel": "user:me" }

# Server pushes:
# { "type": "new_bid", "auction_id": 42, "bid": {...}, "current_price": 250 }
# { "type": "outbid", "auction_id": 42, "you_were": 200, "now_winning": "user_99" }
# { "type": "auction_ending", "auction_id": 42, "seconds_left": 30 }
# { "type": "auction_ended", "auction_id": 42, "winner": "user_99", "final": 250 }
```

---

### Communication Patterns

| Interaction | Pattern | Why |
|---|---|---|
| User browses auctions | REST + Cache (CDN) | Cacheable, read-heavy |
| User places bid | REST (sync confirm) + Kafka (async process) | Need immediate feedback + reliable processing |
| Bid → all watchers | WebSocket pub/sub | Real-time, fan-out |
| Auction close trigger | Timer service → Kafka | Deterministic scheduled events |
| Payment | Async (Kafka → Stripe webhook) | External slow API |
| Search indexing | CDC from Auction DB → Elasticsearch | Eventual consistency OK |
| Notifications | Kafka event → notification service | Fire-and-forget |
| Fraud detection | Async on every bid | Don't block bid; flag if needed |

---

## 4. Making Tech & Infra Decisions

### Decision Matrix (How, What, Why)

#### Decision 1: Database for Bids — Cassandra vs PostgreSQL

**The problem:** 3000 bids/sec global, 100/sec on hot items, need historical lookups.

| Option | Pros | Cons |
|---|---|---|
| PostgreSQL (single instance) | Strong consistency, transactions | Won't scale to 10K writes/sec |
| **PostgreSQL (partitioned by auction_id)** | Strong consistency per auction; fits | Operations complex at extreme scale |
| Cassandra | Massive write throughput | Eventual consistency; complex ordering |
| ScyllaDB | C++ Cassandra, faster | Smaller ecosystem |

**Decision: PostgreSQL with partitioning by auction_id hash.**
**Why:**
- Bid ordering MUST be strongly consistent (fairness!)
- Auction is bounded — single auction has finite bids
- Partition by `auction_id` → each partition is small, manageable
- Avoid Cassandra's "last-write-wins" pitfalls

**Schema:**
```sql
CREATE TABLE bids (
    id BIGSERIAL,
    auction_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    bid_time TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),  -- microsecond precision
    sequence_num BIGINT NOT NULL,                              -- monotonic per auction
    status TEXT NOT NULL,                                       -- 'placed', 'outbid', 'winning', 'rejected'
    PRIMARY KEY (auction_id, id)
) PARTITION BY HASH (auction_id);

-- 256 partitions
CREATE TABLE bids_0  PARTITION OF bids FOR VALUES WITH (modulus 256, remainder 0);
-- ... bids_1, ..., bids_255

CREATE UNIQUE INDEX ON bids (auction_id, sequence_num);
CREATE INDEX ON bids (auction_id, amount DESC, bid_time);
CREATE INDEX ON bids (user_id, bid_time DESC) WHERE status IN ('winning', 'outbid');
```

---

#### Decision 2: Hot-item bid serialization — How to handle 100/sec on one row?

**The problem:** If 100 users bid simultaneously on iPhone-15-auction, we need:
- Strict ordering
- No lost bids
- < 200ms latency

**Options:**

| Approach | Pros | Cons |
|---|---|---|
| Optimistic locking (SELECT FOR UPDATE) | Simple | Lock contention; serializes; high latency |
| Distributed lock (Redis Redlock) | Fast | Lock acquisition overhead |
| **Per-auction Kafka partition + single consumer** | Natural serialization; no locks | Slight async lag (acceptable) |
| Lua script in Redis (atomic check-and-set) | Fastest | Limited logic; need DB write after |

**Decision: Hybrid — Redis Lua atomic check, then Kafka for durability.**

**Why:**
- Redis Lua = atomic; "check current highest, accept if higher" in 1 op
- Kafka = durable record of bid order
- Per-auction Kafka partition = ordered processing for DB write
- Result: 1-5ms decision, fully consistent ordering

**Flow:**
```
1. Bid arrives → API
2. Redis Lua: check current high + accept/reject in 1 atomic op
3. If accepted → publish to Kafka partition (key=auction_id)
4. Return success to user (~5ms total)
5. Async: Kafka consumer writes to PG (durable)
6. Async: WebSocket fan-out new bid to watchers
7. Async: Fraud check
```

```lua
-- Redis Lua script (atomic)
-- KEYS[1] = "auction:42:high_bid"
-- ARGV[1] = bid_amount, ARGV[2] = user_id, ARGV[3] = bid_id, ARGV[4] = min_increment

local current = tonumber(redis.call('HGET', KEYS[1], 'amount') or 0)
local new_amount = tonumber(ARGV[1])
local min_increment = tonumber(ARGV[4])

if new_amount < current + min_increment then
    return {0, "below_minimum", current}  -- rejected
end

-- Accept: update atomically
redis.call('HSET', KEYS[1],
    'amount', new_amount,
    'user_id', ARGV[2],
    'bid_id', ARGV[3],
    'timestamp', redis.call('TIME')[1])

-- Track previous winner for "outbid" notification
local prev_user = redis.call('HGET', KEYS[1], 'prev_user_id') or ''
redis.call('HSET', KEYS[1], 'prev_user_id', ARGV[2])

return {1, "accepted", new_amount, prev_user}
```

```python
# Python wrapper
import redis.asyncio as aioredis
import json
import uuid

LUA_BID = """... (above script) ..."""

class BidService:
    def __init__(self):
        self.redis = aioredis.from_url("redis://redis-cluster")
        self.lua_sha = None

    async def setup(self):
        self.lua_sha = await self.redis.script_load(LUA_BID)

    async def place_bid(self, auction_id: int, user_id: int, amount: float) -> dict:
        # 1. Get auction config (cached)
        auction = await self.get_auction_cached(auction_id)
        if not auction or auction["status"] != "active":
            raise HTTPException(400, "Auction not active")

        # 2. Atomic Redis check
        bid_id = str(uuid.uuid4())
        result = await self.redis.evalsha(
            self.lua_sha, 1,
            f"auction:{auction_id}:high_bid",
            amount, user_id, bid_id, auction["min_increment"],
        )

        accepted, reason, current, prev_user = result
        if not accepted:
            raise HTTPException(400, f"Bid rejected: {reason}. Current high: {current}")

        # 3. Publish to Kafka (durable; async DB write follows)
        await kafka_producer.send(
            "bids",
            key=str(auction_id).encode(),  # ensures ordering per auction
            value=json.dumps({
                "bid_id": bid_id,
                "auction_id": auction_id,
                "user_id": user_id,
                "amount": float(amount),
                "timestamp": time.time_ns(),
            }).encode(),
        )

        # 4. Publish to WebSocket (real-time fan-out)
        await self.redis.publish(
            f"ws:auction:{auction_id}",
            json.dumps({
                "type": "new_bid",
                "amount": float(amount),
                "user_id": user_id,
            }),
        )

        # 5. Outbid notification for previous winner
        if prev_user and prev_user != str(user_id):
            await self.redis.publish(
                f"ws:user:{prev_user}",
                json.dumps({
                    "type": "outbid",
                    "auction_id": auction_id,
                    "now_winning_amount": float(amount),
                }),
            )

        return {"bid_id": bid_id, "accepted": True, "current_high": float(amount)}
```

---

#### Decision 3: Real-time updates — WebSocket vs SSE vs polling

**Options:**

| Approach | Pros | Cons |
|---|---|---|
| Polling (every 2s) | Simple | Wasteful, laggy |
| Long polling | Simpler than WS | Connection overhead |
| Server-Sent Events (SSE) | Auto-reconnect, HTTP-friendly | One-way only |
| **WebSocket** | Bidirectional, low overhead | More complex to scale |

**Decision: WebSocket** with Redis pub/sub for cross-pod fan-out.

**Why:**
- 200K concurrent watchers per hot item
- Need < 500ms push latency
- Server scales horizontally via pub/sub

**Architecture:**
```python
# WebSocket Hub (each pod handles ~50K connections)
class WebSocketHub:
    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}  # channel → ws
        self.redis = aioredis.from_url("redis://redis-cluster")

    async def connect(self, ws: WebSocket, user_id: str):
        await ws.accept()
        self.user_to_ws[user_id] = ws
        # Subscribe user to their personal channel
        asyncio.create_task(self._listen(f"ws:user:{user_id}", ws))

    async def subscribe(self, ws: WebSocket, channel: str):
        """User subscribes to an auction's updates."""
        self.connections.setdefault(channel, set()).add(ws)
        # Listen to Redis pub/sub if not already
        if channel not in self.subscribed:
            asyncio.create_task(self._listen(channel, None))
            self.subscribed.add(channel)

    async def _listen(self, channel: str, specific_ws: WebSocket | None):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue
            data = msg["data"]
            if specific_ws:
                # Direct to one user
                try:
                    await specific_ws.send_text(data)
                except Exception:
                    break
            else:
                # Fan-out to all subscribers on this pod
                dead = set()
                for ws in self.connections.get(channel, set()):
                    try:
                        await ws.send_text(data)
                    except Exception:
                        dead.add(ws)
                self.connections[channel] -= dead

hub = WebSocketHub()

@app.websocket("/ws/connect")
async def ws_endpoint(ws: WebSocket):
    user_id = await authenticate_ws(ws)
    await hub.connect(ws, user_id)

    try:
        while True:
            msg = await ws.receive_json()
            if msg["action"] == "subscribe":
                channel = msg["channel"]  # e.g., "auction:42"
                if await can_subscribe(user_id, channel):
                    await hub.subscribe(ws, f"ws:{channel}")
    except WebSocketDisconnect:
        pass
```

**Scaling:** 10 pods × 50K conn each = 500K total connections. Redis pub/sub handles cross-pod fan-out.

---

#### Decision 4: Auction closing — How to trigger ending at exact second?

**The problem:** 1000s of auctions ending at top of every minute. Each must fire at exact time, atomic, idempotent.

**Options:**

| Approach | Pros | Cons |
|---|---|---|
| Cron job every minute | Simple | Coarse; not millisecond-precise |
| Per-auction Celery `eta` task | Distributed | Task storms; Celery has clock skew |
| **Dedicated Timer Service (Redis sorted set)** | Precise; horizontally scalable | Custom service to build |
| Temporal / DBOS workflows | Durable | Heavyweight for simple timers |

**Decision: Custom Timer Service using Redis sorted set + multiple workers.**

**Why:**
- Auctions have specific `end_time`
- Need precise (< 1s accuracy) triggering
- Must handle restart (durable)

```python
import time
import asyncio
import redis.asyncio as aioredis

class TimerService:
    """Schedules auctions for closing."""

    KEY = "auctions:scheduled"

    def __init__(self):
        self.redis = aioredis.from_url("redis://timer-redis")

    async def schedule_close(self, auction_id: int, end_time_unix: float):
        """Add auction to closing queue. Score = end_time."""
        await self.redis.zadd(self.KEY, {str(auction_id): end_time_unix})

    async def cancel(self, auction_id: int):
        await self.redis.zrem(self.KEY, str(auction_id))

# Worker loop (run N replicas for redundancy)
async def timer_worker():
    redis = aioredis.from_url("redis://timer-redis")

    while True:
        now = time.time()
        # Get all auctions whose end_time has passed
        # ZPOPMIN-style: atomically pop min element if < now
        # Use Lua for atomicity
        script = """
        local items = redis.call('ZRANGEBYSCORE', KEYS[1], 0, ARGV[1], 'LIMIT', 0, 100)
        if #items > 0 then
            redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
        end
        return items
        """
        due_auctions = await redis.eval(script, 1, "auctions:scheduled", now)

        if due_auctions:
            for auction_id in due_auctions:
                # Publish close event
                await kafka_producer.send(
                    "auction.close",
                    key=auction_id,
                    value=json.dumps({"auction_id": int(auction_id), "triggered_at": now}).encode(),
                )

        # Sleep briefly (10ms) for precision
        await asyncio.sleep(0.01)

# Run multiple worker pods (idempotent via ZREM)
```

**Anti-sniping (eBay-style "going, going, gone"):**
```python
# In bid handler
ANTI_SNIPE_EXTEND_SECONDS = 30
ANTI_SNIPE_WINDOW = 60  # last 60 sec

async def maybe_extend_auction(auction_id: int):
    """If bid placed in last 60 sec, extend auction by 30 sec."""
    auction = await db.fetch_one("SELECT end_time FROM auctions WHERE id = :id", {"id": auction_id})
    now = time.time()
    end_time = auction.end_time.timestamp()

    if end_time - now <= ANTI_SNIPE_WINDOW:
        # Extend
        new_end = end_time + ANTI_SNIPE_EXTEND_SECONDS
        await db.execute(
            "UPDATE auctions SET end_time = to_timestamp(:t) WHERE id = :id",
            {"t": new_end, "id": auction_id},
        )
        # Update timer service
        await timer_service.schedule_close(auction_id, new_end)
        # Notify watchers
        await redis.publish(
            f"ws:auction:{auction_id}",
            json.dumps({"type": "extended", "new_end_time": new_end, "extended_by_seconds": ANTI_SNIPE_EXTEND_SECONDS}),
        )
```

---

#### Decision 5: Payment — Synchronous or async?

**Decision: Async with idempotency keys.**

**Why:**
- Stripe/PayPal can take 5-30 seconds; can fail; can retry
- Winner shouldn't wait blocking
- Failure handling needs DLQ + retry

```python
@app.post("/api/auctions/{auction_id}/payment")
async def initiate_payment(auction_id: int, user: User):
    # Verify user is the winner
    auction = await get_auction(auction_id)
    if auction.winner_id != user.id:
        raise HTTPException(403, "Not the winner")

    # Idempotency key
    idem_key = f"payment:{auction_id}:{user.id}"
    existing = await redis.get(idem_key)
    if existing:
        return json.loads(existing)

    # Queue payment processing
    payment_id = uuid.uuid4()
    await kafka_producer.send(
        "payments.process",
        key=str(payment_id).encode(),
        value=json.dumps({
            "payment_id": str(payment_id),
            "auction_id": auction_id,
            "user_id": user.id,
            "amount": float(auction.winning_bid),
            "idempotency_key": idem_key,
        }).encode(),
    )

    result = {"payment_id": str(payment_id), "status": "processing"}
    await redis.setex(idem_key, 86400, json.dumps(result))
    return result

# Payment worker (Celery task with retry)
@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def process_payment(self, payment_data: dict):
    try:
        # Stripe with idempotency
        intent = stripe.PaymentIntent.create(
            amount=int(payment_data["amount"] * 100),
            currency="usd",
            customer=get_stripe_customer_id(payment_data["user_id"]),
            idempotency_key=payment_data["idempotency_key"],
            metadata={"auction_id": payment_data["auction_id"]},
        )

        # Persist
        db.execute(
            "INSERT INTO payments (id, auction_id, user_id, stripe_intent_id, amount, status) VALUES (...)",
            payment_data,
        )

        # Notify user
        notify(payment_data["user_id"], "payment_processing", intent.id)

    except stripe.error.CardError:
        # Don't retry — user needs to fix card
        notify(payment_data["user_id"], "payment_failed", "card_error")

    except stripe.error.APIConnectionError as e:
        # Retry with backoff
        raise self.retry(exc=e)
```

---

#### Decision 6: Fraud detection — Inline or async?

**Decision: Async post-bid, with quick pre-checks inline.**

**Why:**
- ML model takes 50-200ms — too slow for critical path
- Pre-checks (velocity, account age) are cheap → inline
- ML fraud score → async; if flagged, retroactively reject

```python
# Inline pre-checks (< 5ms)
async def quick_fraud_check(user_id: int, amount: float) -> bool:
    # Check 1: Account age
    user = await get_user_cached(user_id)
    if (datetime.utcnow() - user.created_at).total_seconds() < 24 * 3600:
        if amount > 100:
            return False  # New account, large bid suspicious

    # Check 2: Bid velocity (Redis counter)
    velocity = await redis.incr(f"bid_velocity:{user_id}:{int(time.time()) // 60}")
    if velocity == 1:
        await redis.expire(f"bid_velocity:{user_id}:{int(time.time()) // 60}", 60)
    if velocity > 30:  # > 30 bids/minute
        return False

    # Check 3: Shill bidding (seller != bidder)
    auction = await get_auction_cached(auction_id)
    if auction.seller_id == user_id:
        return False

    return True

# Async deep check (Kafka consumer)
async def fraud_ml_worker():
    consumer = AIOKafkaConsumer("bids", bootstrap_servers="kafka:9092")
    async for msg in consumer:
        bid = json.loads(msg.value)
        features = await extract_features(bid)
        score = await fraud_model.predict(features)

        if score > 0.85:  # likely fraud
            await db.execute(
                "UPDATE bids SET status = 'fraud_flagged' WHERE id = :id",
                {"id": bid["bid_id"]},
            )
            await alert_security(bid)
            # If was winning, recompute new winner
            await recompute_winner(bid["auction_id"])
```

---

### Other Tech Decisions

| Need | Choice | Why |
|---|---|---|
| Search | Elasticsearch | Full-text + filters + facets |
| Image storage | S3 + CloudFront CDN | Cheap; global edge |
| Email | SendGrid | Mature, deliverability |
| SMS | Twilio | Global reach |
| ML serving | SageMaker / TGI | Managed, GPU-available |
| Cache | Redis Cluster | Hot bids, sessions, pub/sub |
| Queue | Kafka | High throughput, ordered partitions |
| Distributed tracing | OpenTelemetry + Tempo | Bid path traceability |
| Metrics | Prometheus + Grafana | Standard |
| Multi-region | AWS — us-east-1, eu-west-1, ap-south-1 | Latency + data residency |

---

## 5. The Final Design — Auction Platform

### Complete Data Model

```sql
-- Users
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    name TEXT,
    is_seller BOOLEAN DEFAULT FALSE,
    seller_rating NUMERIC(3, 2),
    kyc_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    stripe_customer_id TEXT
);

-- Auctions
CREATE TABLE auctions (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    category_id INT,
    images JSONB,                          -- ["s3://...", ...]
    start_bid NUMERIC(12, 2) NOT NULL,
    reserve_price NUMERIC(12, 2),          -- min for winning
    buy_now_price NUMERIC(12, 2),          -- instant purchase
    min_increment NUMERIC(12, 2) DEFAULT 1.00,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    extended_count INT DEFAULT 0,          -- anti-snipe counter
    status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled, active, ended, cancelled
    current_high_bid NUMERIC(12, 2),
    current_high_bidder_id BIGINT,
    winner_id BIGINT,
    winning_bid NUMERIC(12, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_auctions_status_end ON auctions(status, end_time) WHERE status = 'active';
CREATE INDEX idx_auctions_seller ON auctions(seller_id, created_at DESC);

-- Bids (partitioned by hash of auction_id)
CREATE TABLE bids (
    id BIGSERIAL,
    auction_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    bid_time TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    sequence_num BIGINT NOT NULL,
    status TEXT NOT NULL,                   -- placed, winning, outbid, fraud_flagged, retracted
    ip_address INET,
    user_agent TEXT,
    PRIMARY KEY (auction_id, id)
) PARTITION BY HASH (auction_id);
-- + 256 partitions

-- Payments
CREATE TABLE payments (
    id UUID PRIMARY KEY,
    auction_id BIGINT REFERENCES auctions(id),
    user_id BIGINT REFERENCES users(id),
    amount NUMERIC(12, 2),
    currency TEXT DEFAULT 'USD',
    stripe_intent_id TEXT,
    status TEXT,                             -- pending, processing, succeeded, failed, refunded
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    failure_reason TEXT
);

-- Watchlist
CREATE TABLE watchlist (
    user_id BIGINT REFERENCES users(id),
    auction_id BIGINT REFERENCES auctions(id),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, auction_id)
);

-- Notifications (Kafka-sourced, but stored for in-app history)
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    type TEXT,                               -- outbid, won, payment, shipment
    payload JSONB,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fraud signals (audit)
CREATE TABLE fraud_signals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    bid_id BIGINT,
    auction_id BIGINT,
    signal_type TEXT,                        -- shill_bid, velocity, ml_score
    score NUMERIC(3, 2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### End-to-End Bid Flow (the critical path)

```
┌──────────┐
│ Client   │
└─────┬────┘
      │ POST /api/auctions/42/bids  {amount: 250}
      ▼
┌──────────────────┐
│ API Gateway      │  rate limit (10 bids/sec/user)
└─────┬────────────┘
      ▼
┌──────────────────┐
│ Bid Service       │
│ ┌──────────────┐ │  1. Inline fraud check (5ms)
│ │ Pre-checks    │ │  2. Redis Lua atomic accept (5ms)
│ └──────────────┘ │  3. Anti-snipe check (extend if late)
│ ┌──────────────┐ │  4. Publish to Kafka (durable)
│ │ Redis Lua     │ │  5. Publish to WebSocket Redis pub/sub
│ │ atomic check  │ │  6. Return success
│ └──────────────┘ │
│  Total: ~15ms    │
└─────┬────────────┘
      ├──→ Kafka topic "bids" (key=auction_id) ───→ ┐
      ├──→ Redis pub/sub "ws:auction:42" ──→ WS Hub │
      └──→ HTTP 200 to client (~15ms)               │
                                                    │
                ┌───────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Kafka Consumer │
        │ (Bid Writer)   │ partition for auction_id 42
        └───────┬────────┘
                │
                ├──→ INSERT INTO bids (PG)
                ├──→ UPDATE auctions SET current_high_bid (PG)
                ├──→ Send notification to prev winner ("outbid")
                ├──→ ML fraud score (async)
                └──→ Update search index (CDC → ES)


Same time, WebSocket fan-out:
       ┌──────────────┐
       │ WS Hub        │
       │ (pod 1)       │ ──→ pushes to 50K subscribers
       └──────────────┘
       ┌──────────────┐
       │ WS Hub        │
       │ (pod 2)       │ ──→ pushes to 50K subscribers
       └──────────────┘
            ...
```

---

### Auction Close Flow

```
Timer Service (Redis sorted set)
       │
       │ Every 10ms: ZRANGEBYSCORE 0..now
       │
       ▼
   Auction 42 due → publish to Kafka "auction.close"
       │
       ▼
┌──────────────────┐
│ Auction Closer   │
│ Worker            │
└────┬─────────────┘
     │
     ├─→ Read current_high_bid from Redis
     ├─→ Check reserve_price met → set winner OR "reserve_not_met"
     ├─→ UPDATE auctions SET status='ended', winner_id, winning_bid
     ├─→ Publish to Kafka "auction.ended"
     │
     ▼
  Multiple consumers:
  ├─→ Notification Service → email/SMS winner + seller
  ├─→ Payment Service → initiate Stripe payment intent
  ├─→ Search Indexer → remove from active listings
  └─→ Analytics → record final price
```

---

### Multi-Region Deployment

```
us-east-1 (primary):
- API, Bid Service, DB primary
- Stripe US

eu-west-1:
- API replicas, DB replica
- Stripe EU
- Data residency for EU users (GDPR)

ap-south-1 (Mumbai):
- API replicas, DB replica
- Stripe India
- Data residency for Indian users (DPDP Act)

Cross-region:
- Read replicas for browse
- Writes (bids) go to primary
- Latency for bidding: route via nearest edge → cross-region to primary (~50-100ms acceptable)
```

---

### Observability & Monitoring

```python
# Critical metrics
bid_placement_latency_ms = Histogram("bid_placement_latency_ms", buckets=[1,5,10,25,50,100,250,500])
bid_outcome = Counter("bids_total", "Outcome", ["status"])  # accepted/rejected/fraud
auction_extensions = Counter("auction_extensions_total")
ws_active_connections = Gauge("ws_active_connections", ["pod"])
ws_messages_sent = Counter("ws_messages_sent_total", ["channel_type"])
payment_failures = Counter("payment_failures_total", ["reason"])
fraud_detected = Counter("fraud_detected_total", ["signal_type"])

# Trace spans
@trace.span("place_bid")
async def place_bid(...):
    with trace.span("redis_atomic_check"): ...
    with trace.span("kafka_publish"): ...
    with trace.span("ws_pubsub"): ...
```

**Alerts:**
- Bid latency p95 > 100ms for 5 min → page
- Bid rejection rate > 5% → ticket
- WS disconnect rate spike → page
- Payment failure rate > 2% → page
- Auction close lag > 5s → page

---

### Anti-Patterns to Avoid

| Anti-pattern | Why bad |
|---|---|
| SELECT FOR UPDATE on auction row | Serializes; 10ms+ per bid |
| Single DB instance for bids | Won't handle 3K/sec |
| Synchronous payment in bid handler | Blocks; user waits |
| Polling for real-time updates | Wasteful; laggy |
| Trust client timestamp for bid order | Cheaters can game it |
| No idempotency on bid POST | Double-submit creates duplicates |
| Inline ML fraud check | Adds 200ms; degrades UX |
| Single timer worker | SPOF for auction close |
| No anti-snipe | "Bid in last 50ms" wins unfairly |

---

### Trade-offs Summary

| Decision | Trade-off |
|---|---|
| Redis Lua for atomic bid check | Fast but more code; Lua debugging hard |
| Kafka for durability | Adds ~5ms latency, but durable |
| Eventual consistency for views | Watchers may see 500ms-old data; acceptable |
| Per-auction partition | Hot auction = 1 partition; can't parallelize within |
| Anti-snipe extension | Unpopular with snipers, but fairer |
| Async payment | Better UX, more failure modes to handle |

---

## Interview Talking Points

**"How do you ensure bid ordering is fair?"**
1. Server timestamp (`clock_timestamp()`) authoritative
2. Redis Lua atomic check = single point of ordering
3. Kafka partition (key=auction_id) preserves order downstream
4. Sequence number assigned per auction (monotonic)

**"What if Redis crashes during a bid?"**
- Redis Sentinel/Cluster for HA
- Last-known high bid replicated
- If lost: replay from Kafka (durable source of truth)
- Brief window of unavailability (< 5s); reject new bids during

**"How do you scale to 1M concurrent watchers on one auction?"**
- WebSocket pods scale horizontally
- Redis pub/sub for cross-pod fan-out
- Eventually: dedicated edge servers (Cloudflare WebSockets, Pusher)
- For mega-popular auctions: pre-compute "next 10 bids you might see" client-side

**"How do you prevent sniping?"**
- Anti-snipe extension (extend auction if bid in last 60 sec)
- Proxy bidding (user sets max; system auto-bids minimum needed) — eBay does this!
- Rate limit per user (10 bids/sec)

**"What if winning bidder doesn't pay?"**
- 48-hour payment window
- If unpaid: forfeit deposit; second-highest bidder offered item
- Account flagged; multiple offenses → ban
- Fraud signal feeds ML model

**"Multi-region — where does a bid go?"**
- Bid writes always to primary region (consistency)
- Cross-region latency ~50-100ms acceptable
- Reads served from local replica

---

## Stretch / Advanced Features

- **Proxy bidding** (auto-bid up to user's max) — eBay-style
- **Reserve price hiding** (don't show until met)
- **Bulk auctions** (multiple identical items, Dutch auction)
- **Live video auctions** (Sotheby's style)
- **Cryptocurrency payments**
- **Escrow** for high-value items
- **Insurance** for buyers/sellers
- **Shipping label generation** (UPS/USPS APIs)
- **Tax calculation** by jurisdiction
- **Multi-currency** with FX

---

## Related Designs
- [Design_Stock_Exchange.md](Design_Stock_Exchange.md) — similar order matching mechanics
- [Design_AdServer.md](Design_AdServer.md) — real-time bidding for ads (RTB)
- [Design_Amazon_Ecommerce.md](Design_Amazon_Ecommerce.md) — e-commerce primitives
- [Payment_System.md](Payment_System.md) — Stripe-like payment flows
- [Notification_System.md](Notification_System.md) — multi-channel notifications
- [Rate_Limiter.md](Rate_Limiter.md) — bid rate limiting

## Related Implementation Docs
- [00_Year0-2_Junior/06_FastAPI/15_websocket_scaling_patterns.md](../../../00_Year0-2_Junior/06_FastAPI/15_websocket_scaling_patterns.md) — WebSocket scaling
- [00_Year0-2_Junior/09_Caching/theory/02_redlock_distributed_locks.md](../../../00_Year0-2_Junior/09_Caching/theory/02_redlock_distributed_locks.md) — distributed locks
- [01_Year3-4_Mid/07_Kafka/](../../../01_Year3-4_Mid/07_Kafka) — Kafka patterns
- [01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md](../../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md) — event sourcing
- [01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md](../../../01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md) — SLO design

---

## Summary — Why This Design Works

| Requirement | Solution |
|---|---|
| Sub-second bid latency | Redis Lua atomic check (~15ms total) |
| Strict bid ordering | Server timestamp + Kafka partition key |
| 100 bids/sec per auction | Single-writer per partition + async DB writes |
| 200K real-time watchers | WebSocket pods + Redis pub/sub fan-out |
| Auction close precision | Dedicated timer service (Redis sorted set) |
| Anti-sniping fairness | Auto-extend if late bid + proxy bidding |
| Payment reliability | Async + idempotency + retry + DLQ |
| Fraud prevention | Inline pre-checks + async ML scoring |
| High availability | Multi-region, Kafka durability, Redis Sentinel |
| Observability | Per-bid trace, metrics, alerts |

**Core insight:** Separate the **hot path** (Redis atomic check) from **durable path** (Kafka → PG) from **fan-out path** (Redis pub/sub → WebSocket). Each scales independently.
