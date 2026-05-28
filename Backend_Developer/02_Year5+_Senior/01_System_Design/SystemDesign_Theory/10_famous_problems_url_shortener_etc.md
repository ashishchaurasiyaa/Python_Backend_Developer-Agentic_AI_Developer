# 🎯 Famous System Design Problems — Architecture Walkthrough

> **Target:** 3-5 YOE | **Goal:** URL Shortener, Chat App, News Feed jaisi famous problems ki end-to-end architecture.

---

## Part 1: WHAT — Famous Problems Kya Hai?

### Definition

> **System Design Interview** me commonly asked problems — URL shortener, chat, feed, search, etc.

### Why Important

- Interview standard
- Real-world patterns
- Architecture practice
- Component understanding

### Approach Template

```
1. Requirements clarification
2. Capacity estimation
3. High-level design
4. Deep dive on components
5. Scale considerations
6. Trade-offs
```

---

## Problem 1: URL SHORTENER (TinyURL)

### Requirements

#### Functional
- Long URL → Short URL
- Short URL → Redirect to long
- Custom short URLs (optional)
- Analytics (clicks, locations)

#### Non-Functional
- Low latency (< 100ms)
- High availability (99.99%)
- Read-heavy (100:1 ratio)
- 100M URLs/day

### Capacity Estimation

```
URLs per day: 100M
URLs per second: 1200
Reads per day: 10B (100:1)
Reads per second: 120k

Storage:
  - 500 bytes per URL × 100M × 5 years
  - ~900 TB
```

### Components

#### Short URL Generation

##### Approach 1: Hash
```
Long URL → Hash (MD5/SHA) → Take 7 chars
```

Issues: Collisions possible.

##### Approach 2: Counter
```
Unique ID → Base62 encode
ID 1 → "1"
ID 100 → "1C"
ID 1000000000 → "QcF6r"
```

Sequential, predictable. Hash incrementing counter helps.

##### Approach 3: UUID + Encode
```
UUID → Base62 → First 7 chars
```

Random, collision rare.

### High-Level Architecture

```
USER
 ↓
LOAD BALANCER
 ↓
API SERVERS
 ↓
   ├──→ ID GENERATOR (Zookeeper/Snowflake)
   ├──→ CACHE (Redis) ← popular URLs
   └──→ DATABASE (key: short, value: long)
```

### Database Schema

```
url_mapping:
  short_url (PK)
  long_url
  user_id
  created_at
  expiry_date
  clicks (counter)
```

### Deep Dive: Read Path

```
1. User requests /xyz789
2. Check cache: hit?
   - YES: return long URL
   - NO: continue
3. Database lookup
4. Cache result
5. 302 redirect to long URL
```

### Scale Considerations

#### Caching
> Top 20% URLs get 80% traffic.

LRU cache. 24-hour TTL.

#### Database
> Sharding by short URL hash.

#### Analytics
> Async processing.

Counter updates via Kafka, not synchronously.

### Trade-offs

- Counter vs Hash: simplicity vs predictability
- Cache size: cost vs hit rate
- TTL: storage vs link rot

---

## Problem 2: CHAT APPLICATION (WhatsApp)

### Requirements

#### Functional
- 1-on-1 chat
- Group chat (up to 256)
- Online/offline status
- Message delivery (sent, delivered, read)
- Media (images, videos)

#### Non-Functional
- Low latency (< 100ms)
- Reliable delivery
- 2 billion users
- 50 billion messages/day

### Capacity

```
Messages/day: 50B
Messages/sec: 580k
Storage per message: ~1KB
Storage/day: 50TB
Storage/5yr: ~90PB
```

### Components

#### Connection Management

##### WebSocket
> Persistent connection user-server.

##### XMPP
> Established protocol.

##### Long Polling
> Fallback.

### High-Level Architecture

```
USER
 ↓ (persistent WebSocket)
LOAD BALANCER
 ↓
WEB SERVERS (stateful)
 ↓
   ├──→ MESSAGE STORE (Cassandra)
   ├──→ USER STATUS (Redis)
   ├──→ MEDIA STORAGE (S3)
   └──→ NOTIFICATION SERVICE
```

### Message Flow

```
User A sends to User B:

1. A → WebSocket → Server (A connected)
2. Server stores message in Cassandra
3. Server checks: B online?
   - YES: send via B's WebSocket
   - NO: send via FCM/APNS push
4. Acknowledgment back to A
```

### Database

#### Cassandra Schema

```
messages:
  user_id (partition)
  message_id (clustering)
  from
  text
  timestamp
  status (sent/delivered/read)
```

Partition by user_id = all user's messages co-located.

### Group Chat

```
group_messages:
  group_id (partition)
  message_id (clustering)
  ...

For each message:
1. Store once in group_messages
2. Fan-out: push to each online member
3. Mobile notification for offline
```

### Read Receipts

```
Status: sent → delivered → read

Sent: when sender sends
Delivered: when receiver's device receives
Read: when receiver opens
```

### Scale Considerations

#### Sharding
> By user_id.

#### Caching
> Recent messages, user status.

#### Media
> S3, CDN for delivery.

---

## Problem 3: NEWS FEED (Twitter/Facebook)

### Requirements

#### Functional
- Post content
- Follow users
- See feed of followed users
- Like, comment

#### Non-Functional
- Read-heavy
- Low latency feed loading
- 500M users
- 100M posts/day

### Capacity

```
Posts/day: 100M
Posts/sec: 1200
Reads/day: 50B (followers)
Reads/sec: 600k
```

### Two Approaches

#### Approach 1: Pull (Read-time)

> Build feed when user requests.

```
User opens app
↓
Query: all posts from followed users
↓
Sort by time
↓
Return top 100
```

Pros: Simple, always current
Cons: Slow for users with many follows

#### Approach 2: Push (Write-time / Fan-out)

> Pre-compute feed on post.

```
User posts
↓
Find all followers
↓
Add post to each follower's feed
↓
When follower opens app: feed ready
```

Pros: Fast reads
Cons: Slow writes, "celebrity problem"

#### Hybrid (Real-World)

> Push for normal users, pull for celebrities.

```
Normal user posts:
  Fan-out to followers' feeds

Celebrity (>1M followers) posts:
  Don't fan-out (too expensive)
  Pull on follower's feed request
```

### Architecture

```
USER
 ↓
LOAD BALANCER
 ↓
API SERVERS
 ↓
   ├──→ POST SERVICE
   ├──→ FEED SERVICE
   ├──→ USER GRAPH
   └──→ NOTIFICATION
```

### Database

```
posts:
  post_id, user_id, content, created_at

user_follows:
  follower_id, followed_id

feeds:
  user_id, post_ids (sorted by time)
```

### Feed Storage

#### Redis
> Sorted set per user.

```
user:123:feed = [post_1, post_2, post_3, ...]
```

Fast retrieval.

### Scale Considerations

#### Sharding
> Posts by user_id.
> Feeds by user_id.

#### Caching
> Recent posts, popular content.

#### CDN
> Media delivery.

---

## Problem 4: VIDEO STREAMING (YouTube)

### Requirements

#### Functional
- Upload video
- Watch video
- Search
- Recommendations

#### Non-Functional
- 2B users
- 1B hours watched/day
- Multiple resolutions
- Global delivery

### Architecture

```
UPLOADER
 ↓
UPLOAD SERVICE
 ↓
TRANSCODING (multiple resolutions)
 ↓
STORAGE (S3)
 ↓
CDN (Cloudflare/Akamai)
 ↓
VIEWERS
```

### Transcoding

Original 4K → multiple:
- 240p, 360p, 480p, 720p, 1080p, 4K

Per device/bandwidth.

### Storage

#### Hot
> Recently uploaded, popular.

#### Warm
> Older but watched.

#### Cold
> Rarely watched. Cheap storage.

Auto-tiering.

### Delivery

#### CDN
> Global edge caching.

#### Adaptive Bitrate
> Quality adjusts to bandwidth.

#### HLS / DASH
> Streaming protocols.

### Metadata DB

```
videos:
  video_id, uploader_id, title, description
  views, likes, dislikes
  created_at

view_history:
  user_id, video_id, watched_at
```

### Search

> Elasticsearch.

Indexed:
- Title
- Description
- Tags
- Comments

### Recommendations

> ML pipeline.

Inputs:
- Watch history
- Demographics
- Trending
- Similar users

Output: ranked list per user.

---

## Problem 5: RIDE-SHARING (Uber)

### Requirements

#### Functional
- Request ride
- Match with driver
- Track real-time
- Payment

#### Non-Functional
- Low latency
- Real-time updates
- High availability

### Architecture

```
RIDER APP                    DRIVER APP
   │                             │
   ↓                             ↓
RIDER SERVICE              DRIVER SERVICE
   │                             │
   └──────→ MATCHING SERVICE ←──┘
                  ↓
            ROUTING SERVICE
                  ↓
            PAYMENT SERVICE
```

### Matching

#### Geo-Spatial Index

> Quadtree or GeoHash.

```
City divided into grid.
Drivers in same grid as rider.
Find closest available.
```

### Real-Time Tracking

> WebSocket updates.

Driver location every 5 seconds.
Update rider's map.

### Database

#### PostgreSQL
> Rides, users, payments.

#### Redis
> Driver locations.

#### Cassandra
> Trip events stream.

### Surge Pricing

> Based on demand/supply ratio.

Real-time calculation.

---

## Problem 6: PAYMENT SYSTEM

### Requirements

#### Functional
- Charge card
- Refund
- Subscription
- Multi-currency

#### Non-Functional
- ACID transactions
- Idempotency
- Audit trail
- High security

### Architecture

```
USER
 ↓
API GATEWAY
 ↓
PAYMENT SERVICE
 ↓
   ├──→ FRAUD DETECTION
   ├──→ PAYMENT PROCESSOR (Stripe, etc.)
   ├──→ DATABASE (ACID)
   └──→ EVENT BUS (async work)
```

### Idempotency Critical

```
Client generates UUID.
Server tracks UUIDs.
Same UUID = same response (no re-charge).
```

### Database (ACID Required)

```
transactions:
  transaction_id (PK)
  user_id
  amount
  currency
  status (pending/success/failed)
  created_at
  external_ref (Stripe ID)
```

### Audit Trail

```
transaction_events:
  event_id
  transaction_id
  event_type
  metadata
  timestamp
```

Append-only.
Never modified.

### Reconciliation

Daily:
- Compare internal vs Stripe data
- Detect discrepancies
- Alert on mismatches

---

## Problem 7: SEARCH AUTOCOMPLETE

### Requirements

- As user types, suggest queries
- Sub-100ms latency
- Trending awareness
- Personalization

### Architecture

```
USER TYPES
 ↓
TRIE (in-memory)
 ↓
RANKED SUGGESTIONS
```

### Trie Data Structure

```
        root
         │
    ┌────┼────┐
    a    b    c
    │    │    │
    p    o    a
    │    │    │
    p    o    r
    │    │
    l    k
    │
    e

"apple", "book", "car" stored
"app" → returns "apple" (and children)
```

### Updates

#### Offline
> Batch update trie daily.

#### Real-Time
> Stream of search queries → update trie.

### Personalization

> User-specific cache for their history.

### Scale

#### Multiple Tries
> Sharded by first character.

#### Caching
> Common prefixes.

---

## Problem 8: RATE LIMITER

### Requirements

- Limit requests per user/IP
- Distributed (multiple servers)
- Configurable limits

### Algorithms

#### Token Bucket

```
Bucket: 100 tokens
Refill: 10 tokens/sec

Each request: consume 1 token
No tokens: reject (429)
```

#### Leaky Bucket

```
Queue with fixed rate processing
Overflow: drop
```

#### Fixed Window

```
1-min window: 1000 requests max
At 60 sec: reset counter
```

Issue: spike at window boundary.

#### Sliding Window

```
Track requests in last 60 sec.
More accurate.
```

### Implementation

#### Redis-Based

```
Key: "user:123:requests"
Value: counter
TTL: 60 seconds
```

Atomic INCR.

### Distributed

> Each server checks Redis.
> Counter shared.

---

## Problem 9: NOTIFICATION SYSTEM

### Requirements

- Email
- SMS
- Push
- Multiple providers
- Retry logic

### Architecture

```
APP
 ↓
NOTIFICATION SERVICE
 ↓
QUEUE (Kafka)
 ↓
   ├──→ Email Worker → SendGrid
   ├──→ SMS Worker → Twilio
   └──→ Push Worker → FCM/APNS
```

### Templates

```
template:
  template_id
  channels (email, sms, push)
  subject (email)
  body
  variables
```

### Preferences

```
user_preferences:
  user_id
  channel
  enabled
  frequency_limit
```

### Retry

```
Failed → retry queue
  Backoff: 1s, 5s, 30s, 5min, 1hr
  Max attempts: 5
  Final fail → dead letter queue
```

---

## Problem 10: DISTRIBUTED CACHE

### Requirements

- Sub-ms latency
- Highly available
- Scalable

### Architecture

```
CLIENT
 ↓
SHARDING (consistent hashing)
 ↓
   ├──→ Node 1 (data X)
   ├──→ Node 2 (data Y)
   └──→ Node 3 (data Z)
```

### Consistent Hashing

> Adding/removing nodes = minimal data movement.

### Replication

> Each shard replicated 2-3 times.

### Memcached vs Redis

#### Memcached
- Simple
- Multi-threaded
- LRU only

#### Redis
- Rich data types
- Single-threaded
- Multiple eviction policies
- Persistence

---

## Part 2: COMMON PATTERNS ACROSS PROBLEMS

### Pattern 1: Caching Layer

Almost every problem.

### Pattern 2: Async Processing

Background jobs via queues.

### Pattern 3: Sharding

Horizontal scaling.

### Pattern 4: Replication

High availability.

### Pattern 5: Event-Driven

Loose coupling.

### Pattern 6: CDN

Static content delivery.

### Pattern 7: Geo-Distribution

Multi-region for global.

---

## Part 3: INTERVIEW APPROACH

### Step 1: Clarify Requirements (5 min)

- Functional
- Non-functional
- Scale assumptions

### Step 2: Capacity Estimation (5 min)

- Users, requests
- Storage
- Bandwidth

### Step 3: API Design (5 min)

- Key endpoints
- Request/response

### Step 4: High-Level Design (10 min)

- Major components
- Data flow

### Step 5: Database Design (5 min)

- Schema
- SQL or NoSQL?

### Step 6: Deep Dive (15 min)

- Focus on 1-2 components
- Trade-offs

### Step 7: Scale (10 min)

- Bottlenecks
- Solutions

### Step 8: Q&A (5 min)

---

## Part 4: COMMON MISTAKES

### Mistake 1: Jumping to Code

❌ Start designing immediately.
✅ Clarify requirements first.

### Mistake 2: Over-Engineering

❌ Microservices for everything.
✅ Match complexity to scale.

### Mistake 3: Ignoring Trade-offs

❌ "X is best."
✅ "X has these trade-offs..."

### Mistake 4: One Approach Only

❌ Only one solution mentioned.
✅ Discuss alternatives.

### Mistake 5: No Estimates

❌ "Will scale."
✅ "Handles 1M req/sec because..."

---

## Part 5: PREPARATION

### Practice Resources

- "System Design Interview" by Alex Xu
- High Scalability blog
- Engineering blogs (Netflix, Uber)
- LeetCode system design
- ByteByteGo videos

### Mock Interviews

- Pramp
- Interviewing.io
- Practice with peers

### Read Real Architectures

Famous companies share:
- Netflix (microservices, chaos)
- Uber (geo-spatial)
- Twitter (timelines)
- Discord (real-time)

---

## 🎯 Bhai's Final Words

> **Famous problems = templates for any system. Master 5-10 problems deeply, you can design anything.**

3 Mantras:
1. **Clarify first** (don't assume)
2. **Estimate always** (numbers matter)
3. **Discuss trade-offs** (no perfect solution)

After mastering these problems, FAANG system design interviews become achievable. 🚀
