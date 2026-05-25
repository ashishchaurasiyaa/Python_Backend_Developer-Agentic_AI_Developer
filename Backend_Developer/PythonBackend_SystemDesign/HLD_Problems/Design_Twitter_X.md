# Design Twitter / X

---

## 1. Requirements

### Functional
- Post tweets (text ≤ 280 chars, optional media)
- Follow / unfollow users
- Home timeline (tweets from followed users, reverse-chronological)
- User timeline (all tweets by a user)
- Like, retweet, quote tweet
- Trending hashtags
- Full-text search

### Non-Functional
- 300M DAU, 500M tweets/day
- Read-heavy: 100:1 read/write ratio
- Timeline load < 200ms (P99)
- 99.99% uptime (< 52 min downtime/year)
- Eventual consistency acceptable for timelines

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Tweet writes | 500M / 86400 | ~5,800 tweets/sec |
| Timeline reads | 500M × 100 | 50B reads/day = ~578K reads/sec |
| Storage (text) | 5800 × 280 bytes | ~1.6 MB/sec = ~50 GB/day |
| Storage (media) | 20% tweets have media, avg 1MB | ~1.1 TB/day |
| Redis memory | 300M users × 800 tweets × 8 bytes | ~1.9 TB for all timelines |

---

## 3. Architecture Diagram

```
                        ┌─────────────┐
  Clients ─────────────▶│  CDN/Edge   │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │ API Gateway │ (auth, rate limit, routing)
                        └──────┬──────┘
              ┌────────────────┼────────────────────┐
              │                │                    │
       ┌──────▼──────┐  ┌──────▼──────┐   ┌────────▼──────┐
       │Tweet Service│  │  Timeline   │   │ Search Service │
       │             │  │  Service    │   │ (Elasticsearch)│
       └──────┬──────┘  └──────┬──────┘   └───────────────┘
              │                │
              │         ┌──────▼──────┐
        Kafka │         │  Redis      │
        topic │         │  (timelines,│
   new_tweets │         │  trending)  │
              │         └─────────────┘
       ┌──────▼──────┐
       │  Fan-out    │ (Kafka consumer)
       │  Service    │
       └──────┬──────┘
              │
    ┌─────────▼──────────┐
    │     Cassandra       │ (tweets, follows, likes)
    │     PostgreSQL      │ (user profiles, settings)
    │     S3 + CDN        │ (media)
    └────────────────────┘
```

---

## 4. Core Components

### Tweet Service — Snowflake ID

```python
import time
import threading
from dataclasses import dataclass

@dataclass
class Tweet:
    tweet_id: int         # Snowflake ID
    author_id: int
    content: str          # max 280 chars
    media_urls: list      # S3 URLs
    created_at: float     # epoch ms
    reply_to_id: int | None = None
    retweet_of_id: int | None = None

class SnowflakeIDGenerator:
    """
    64-bit ID: [41 bits timestamp ms] [10 bits machine_id] [12 bits sequence]
    Guarantees: unique, sortable, monotonically increasing.
    """
    EPOCH = 1_700_000_000_000   # custom epoch (ms)
    MACHINE_BITS = 10
    SEQUENCE_BITS = 12
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1   # 4095
    MAX_MACHINE  = (1 << MACHINE_BITS) - 1    # 1023

    def __init__(self, machine_id: int):
        assert 0 <= machine_id <= self.MAX_MACHINE
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _current_ms(self) -> int:
        return int(time.time() * 1000) - self.EPOCH

    def next_id(self) -> int:
        with self.lock:
            now = self._current_ms()
            if now == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    while now <= self.last_timestamp:
                        now = self._current_ms()
            else:
                self.sequence = 0
            self.last_timestamp = now
            return (now << 22) | (self.machine_id << 12) | self.sequence
```

### Cassandra Schema

```sql
-- Tweets by user (user timeline)
CREATE TABLE tweets_by_user (
    user_id     BIGINT,
    tweet_id    BIGINT,        -- Snowflake (time-sortable)
    content     TEXT,
    media_urls  LIST<TEXT>,
    created_at  TIMESTAMP,
    PRIMARY KEY ((user_id), tweet_id)
) WITH CLUSTERING ORDER BY (tweet_id DESC);

-- Tweets by id (lookup)
CREATE TABLE tweets_by_id (
    tweet_id    BIGINT PRIMARY KEY,
    author_id   BIGINT,
    content     TEXT,
    like_count  COUNTER,
    retweet_count COUNTER
);

-- Follow graph
CREATE TABLE following (
    follower_id  BIGINT,
    followee_id  BIGINT,
    created_at   TIMESTAMP,
    PRIMARY KEY ((follower_id), followee_id)
);

CREATE TABLE followers (
    followee_id  BIGINT,
    follower_id  BIGINT,
    created_at   TIMESTAMP,
    PRIMARY KEY ((followee_id), follower_id)
);
```

### Timeline Service — Hybrid Push/Pull

```python
import time
from typing import Optional

CELEBRITY_THRESHOLD = 10_000  # followers

class TimelineService:
    """
    Fan-out on WRITE for regular users (push model).
    Fan-out on READ for celebrities (pull model).
    Avoids write amplification for users with millions of followers.
    """
    def __init__(self, redis_client, cassandra_session):
        self.redis = redis_client
        self.db = cassandra_session
        self.TIMELINE_MAX = 800   # keep only 800 tweets in cache

    async def push_tweet_to_followers(self, tweet_id: int, author_id: int,
                                       follower_ids: list[int]):
        """Fan-out: add tweet to each follower's Redis timeline."""
        score = time.time()   # use timestamp as sort score
        pipe = self.redis.pipeline()
        for fid in follower_ids:
            key = f"timeline:{fid}"
            pipe.zadd(key, {str(tweet_id): score})
            pipe.zremrangebyrank(key, 0, -(self.TIMELINE_MAX + 1))  # trim
        await pipe.execute()

    async def get_home_timeline(self, user_id: int, limit: int = 20,
                                 before_id: Optional[int] = None) -> list[dict]:
        """
        1. Get pushed tweets from Redis (fast path).
        2. Pull celebrity tweets from Cassandra (merge).
        3. Return merged, deduplicated, sorted list.
        """
        # Step 1: Get cached timeline tweets
        key = f"timeline:{user_id}"
        if before_id:
            # cursor-based pagination
            max_score = self._tweet_id_to_score(before_id)
            raw = await self.redis.zrevrangebyscore(
                key, max_score - 0.001, '-inf', start=0, num=limit, withscores=True
            )
        else:
            raw = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)

        cached_ids = [int(tid) for tid, _ in raw]

        # Step 2: Pull celebrity tweets
        celebrity_ids = await self._get_celebrity_followees(user_id)
        celebrity_tweets = []
        for cid in celebrity_ids:
            tweets = await self._get_user_recent_tweets(cid, limit=20)
            celebrity_tweets.extend(tweets)

        # Step 3: Merge and sort by tweet_id (time-sortable)
        all_ids = list(set(cached_ids + [t['tweet_id'] for t in celebrity_tweets]))
        all_ids.sort(reverse=True)
        return await self._fetch_tweets(all_ids[:limit])

    async def _get_celebrity_followees(self, user_id: int) -> list[int]:
        """Get followees who are celebrities (high follower count)."""
        # Cache in Redis: celebrity_following:{user_id}
        cached = await self.redis.smembers(f"celebrity_following:{user_id}")
        return [int(uid) for uid in cached]

    async def _get_user_recent_tweets(self, user_id: int, limit: int) -> list[dict]:
        result = await self.db.execute(
            "SELECT tweet_id, content, created_at FROM tweets_by_user "
            "WHERE user_id = ? LIMIT ?", [user_id, limit]
        )
        return [dict(row) for row in result]

    async def _fetch_tweets(self, tweet_ids: list[int]) -> list[dict]:
        # Batch fetch from Cassandra or Redis cache
        return []  # implementation omitted

    def _tweet_id_to_score(self, tweet_id: int) -> float:
        # Extract timestamp from Snowflake ID
        return ((tweet_id >> 22) + 1_700_000_000_000) / 1000
```

### Fan-out Service (Kafka Consumer)

```python
from aiokafka import AIOKafkaConsumer
import json

async def fan_out_worker():
    """
    Consumes new_tweets topic.
    Decides push vs pull based on follower count.
    """
    consumer = AIOKafkaConsumer(
        'new_tweets',
        bootstrap_servers='kafka:9092',
        group_id='fanout-service',
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    async for msg in consumer:
        event = msg.value
        author_id  = event['author_id']
        tweet_id   = event['tweet_id']

        follower_count = await get_follower_count(author_id)

        if follower_count <= CELEBRITY_THRESHOLD:
            # Regular user: push to all followers
            follower_ids = await get_all_follower_ids(author_id)
            # Batch in chunks of 1000 to avoid Redis pipeline overload
            for chunk in chunks(follower_ids, 1000):
                await timeline_service.push_tweet_to_followers(
                    tweet_id, author_id, chunk
                )
        # Celebrity: followers will pull on read (no push needed)
```

### Trending Hashtags

```python
import re
import time

class TrendingService:
    WINDOW = 3600   # 1 hour sliding window
    TOP_N  = 50

    def __init__(self, redis_client):
        self.redis = redis_client

    def extract_hashtags(self, content: str) -> list[str]:
        return re.findall(r'#(\w+)', content.lower())

    async def record_tweet(self, content: str):
        """Called by Tweet Service via Kafka event."""
        now = int(time.time())
        window_start = now - self.WINDOW
        hashtags = self.extract_hashtags(content)
        pipe = self.redis.pipeline()
        for tag in hashtags:
            # Add timestamp event to sorted set for this hashtag
            key = f"tag:{tag}"
            pipe.zadd(key, {now: now})
            pipe.zremrangebyscore(key, 0, window_start)   # expire old events
            count = await self.redis.zcard(key)
            # Update global trending sorted set
            pipe.zadd("trending:global", {tag: count})
        await pipe.execute()

    async def get_trending(self, limit: int = 10) -> list[tuple]:
        """Return top N trending hashtags with counts."""
        return await self.redis.zrevrange(
            "trending:global", 0, limit - 1, withscores=True
        )

    async def refresh_trending(self):
        """Cron job: recompute all hashtag counts from sliding window."""
        # Run every 60 seconds to keep trending accurate
        all_tags = await self.redis.keys("tag:*")
        now = int(time.time())
        window_start = now - self.WINDOW
        pipe = self.redis.pipeline()
        for key in all_tags:
            tag = key.split(b":")[1].decode()
            await self.redis.zremrangebyscore(key, 0, window_start)
            count = await self.redis.zcard(key)
            pipe.zadd("trending:global", {tag: float(count)})
        await pipe.execute()
```

### Search — Elasticsearch

```python
from elasticsearch import AsyncElasticsearch

es = AsyncElasticsearch(["http://elasticsearch:9200"])

TWEET_INDEX = {
    "mappings": {
        "properties": {
            "tweet_id":   {"type": "long"},
            "author_id":  {"type": "long"},
            "content":    {"type": "text", "analyzer": "english"},
            "hashtags":   {"type": "keyword"},
            "created_at": {"type": "date"},
            "like_count": {"type": "integer"}
        }
    }
}

async def index_tweet(tweet: dict):
    await es.index(index="tweets", id=tweet["tweet_id"], body=tweet)

async def search_tweets(query: str, from_: int = 0, size: int = 20) -> list:
    resp = await es.search(index="tweets", body={
        "query": {
            "bool": {
                "must": {"match": {"content": query}},
                "filter": {"range": {"created_at": {"gte": "now-7d"}}}
            }
        },
        "sort": [{"_score": "desc"}, {"created_at": "desc"}],
        "from": from_, "size": size
    })
    return [hit["_source"] for hit in resp["hits"]["hits"]]
```

---

## 5. Deep Dive

### Like System (Redis + Async DB Sync)
```python
async def like_tweet(user_id: int, tweet_id: int) -> int:
    key = f"likes:{tweet_id}"
    added = await redis.sadd(key, user_id)   # SADD returns 1 if new like
    if added:
        count = await redis.scard(key)
        # Async: publish to Kafka → consumer updates Cassandra
        await kafka.send('tweet_likes', {'tweet_id': tweet_id, 'user_id': user_id})
        return count
    return await redis.scard(key)   # already liked
```

### Retweet
- Creates new tweet with `retweet_of_id` pointing to original
- Original tweet's `retweet_count` incremented
- Retweeter's followers see the retweet in their timeline

### Notification (Kafka → WebSocket)
```
Kafka topic: notifications
  → consumer group: notification-service
  → fan-out to user via WebSocket or APNs/FCM
```

---

## 6. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| Celebrity posts tweet (write storm) | Pull-based for celebrities — no fan-out write amplification |
| Cache stampede on popular tweet | Probabilistic early expiration (PER algorithm) |
| Cassandra node failure | Replication factor 3, consistency level QUORUM |
| Kafka consumer lag | Monitor lag, scale consumers horizontally per partition |
| Redis OOM | LRU eviction on timeline keys, maxmemory-policy allkeys-lru |
| Timeline out of sync | Accept eventual consistency; periodic rebuild job |

---

## 7. Interview Questions

**Q1: Why Cassandra for tweets instead of PostgreSQL?**
> Cassandra excels at write-heavy workloads with time-series data. Tweets are append-only (rarely updated), and we read by user_id + time range — a natural partition key. Cassandra's wide-row model handles 500M writes/day without sharding complexity. PostgreSQL would require complex horizontal sharding.

**Q2: Why hybrid push/pull instead of pure push or pure pull?**
> Pure push: 1 celebrity with 50M followers → 50M Redis writes per tweet. Unacceptable. Pure pull: read timeline = query 1000 followed users × N tweets = 1000 DB queries. Too slow. Hybrid: regular users (< 10k followers) use push (fast reads), celebrities use pull (avoid write amplification).

**Q3: How does the Snowflake ID help with pagination?**
> Snowflake IDs embed a timestamp in the top 41 bits, making them time-sortable. "Load more tweets before this ID" = compare tweet_id values directly without storing cursor timestamps separately. ID comparison = time comparison.

**Q4: How to handle the thundering herd when a celebrity logs in?**
> Pre-warm the celebrity's pull query on login. Background job periodically rebuilds the celebrity's recent tweets cache. Rate limit how often we recompute the merged timeline.

**Q5: How is trending hashtag count kept accurate with the sliding window?**
> Each hashtag has a Redis sorted set where members = event timestamps and scores = timestamps. Removing events older than 1 hour via ZREMRANGEBYSCORE. Count = ZCARD. Global trending sorted set updated with each new event.

**Q6: What is the fan-out problem and how does Twitter solve it?**
> Fan-out = distributing one tweet to all followers' timelines. Twitter uses Flock (graph store) for the follow graph and Flock + Finagle to parallelize fan-out. Cutoff at ~10k followers; above that, pull-based.

**Q7: How to scale the search service for 500M tweets/day?**
> Elasticsearch cluster with index sharding by time (rolling daily indices). Hot indices on SSD, cold on HDD. Kafka consumer indexes tweets in near-real-time. Separate read/write nodes. Cache frequent queries in Redis.

**Q8: How to prevent duplicate tweets on retry?**
> Client generates idempotency key (UUID) per tweet attempt. Server checks Redis: `SET idempotency:{key} tweet_id NX EX 86400`. If key exists, return existing tweet. Prevents double-posting on network retry.

**Q9: How does the "who to follow" recommendation work?**
> Graph-based: find users followed by people you follow (2nd-degree connections). Use Hadoop/Spark offline batch job on the follow graph. Serve recommendations from a precomputed Redis sorted set. Refresh every few hours.

**Q10: Why use Redis Sorted Set for timelines instead of a List?**
> Sorted set allows: O(log n) insertion, O(1) range by score (timestamp), deduplication (same tweet_id can't appear twice), and easy merging of celebrity pull results by score. A list would require O(n) search for deduplication and can't efficiently insert in sorted order.
