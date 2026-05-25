# Design Instagram / Social Media News Feed — HLD

## Requirements

### Functional
- Users can post photos/videos with captions
- Follow/unfollow other users
- News feed: see posts from followed users (newest first)
- Like and comment on posts
- Search users and hashtags
- Stories (24h disappearing content)

### Non-Functional
- 1 billion users, 500M DAU
- News feed loads in <200ms
- Posts are eventually consistent (slight delay ok)
- 99.9% availability
- 500M photos uploaded/day

---

## Back-of-Envelope

```
Post uploads:    500M/day = 5,800/sec
Feed reads:      500M DAU × 20 feed loads = 10B reads/day = 115,000 reads/sec
Photo storage:   500M × 3MB = 1.5 PB/day
Peak QPS:        feed reads = ~400k/sec (8am-10pm)
```

---

## Architecture Overview

```
Client App
    │
    ▼
API Gateway / Load Balancer
    │
    ├── Post Service         (upload, store photos)
    ├── Feed Service         (generate + serve news feed)
    ├── User Service         (profile, follow/unfollow)
    ├── Like/Comment Service
    ├── Search Service       (Elasticsearch)
    └── Notification Service

Data Layer:
    ├── PostgreSQL           (users, follows, posts metadata)
    ├── Redis Cluster        (feed cache, session, counters)
    ├── Cassandra            (likes, comments — time-series)
    ├── S3 + CloudFront CDN  (photos, videos)
    └── Kafka                (event streaming for fanout)
```

---

## Core Challenge: News Feed Generation

The hardest part of any social media system.

### Approach 1 — Pull Model (Fan-out on Read)

```
When user opens app:
1. Fetch list of users they follow (user_id list)
2. Query recent posts from each followed user
3. Merge, sort by time, return top 20

SELECT p.* FROM posts p
WHERE p.user_id IN (SELECT followee_id FROM follows WHERE follower_id = ?)
ORDER BY p.created_at DESC
LIMIT 20;

Problems:
- User follows 1000 people → 1000 DB queries → slow
- Heavy DB load on every feed load
- Good for: users with few followers
```

### Approach 2 — Push Model (Fan-out on Write)

```
When user posts:
1. Get all their followers
2. For EACH follower → add post_id to their feed cache

Redis per user:
  feed:user_id → sorted set (score=timestamp, member=post_id)

Post arrives: 
  for follower_id in get_followers(poster_id):    # 1M followers?
      redis.zadd(f"feed:{follower_id}", {post_id: timestamp})
      redis.zremrangebyrank(f"feed:{follower_id}", 0, -1001)  # keep 1000

Feed read:
  post_ids = redis.zrevrange(f"feed:{user_id}", 0, 19)  # last 20
  posts = db.bulk_fetch(post_ids)  # batch read

Problems:
- Celebrity with 100M followers → 100M Redis writes on one post!
- Solution: Hybrid model
```

### Approach 3 — HYBRID (Instagram's actual approach)

```
Regular users (< 10k followers): Push model
  → Pre-compute feed on write → fast reads

Celebrities (> 10k followers):   Pull model
  → Not fanned out → fetched lazily on read

Algorithm:
1. User opens feed
2. Load pre-computed feed from Redis (from followed regular users)
3. For each celebrity they follow → pull recent posts (max 5 per celeb)
4. Merge + sort → return

This balances write amplification vs read latency
```

### Feed Service Implementation

```python
import redis
import json
from typing import AsyncIterator

r = redis.Redis()

FEED_SIZE      = 1000    # max posts stored per user
CELEBRITY_THRESHOLD = 10_000  # follower count to classify as celebrity

async def post_created(post_id: str, poster_id: str, timestamp: float):
    """Called when a user creates a post — fanout to followers."""
    
    follower_count = await db.get_follower_count(poster_id)
    
    if follower_count <= CELEBRITY_THRESHOLD:
        # Push model: add to each follower's feed
        followers = await db.get_followers(poster_id, limit=None)
        
        async with r.pipeline() as pipe:
            for follower_id in followers:
                pipe.zadd(f"feed:{follower_id}", {post_id: timestamp})
                pipe.zremrangebyrank(f"feed:{follower_id}", 0, -(FEED_SIZE + 1))
            await pipe.execute()
    else:
        # Celebrity: just mark post exists, don't fanout
        # (will be fetched lazily when followers load their feed)
        await r.zadd(f"posts:{poster_id}", {post_id: timestamp})


async def get_news_feed(user_id: str, page: int = 0, page_size: int = 20) -> list[dict]:
    """Return news feed for user."""
    
    offset = page * page_size
    
    # Get pre-computed feed (from regular users)
    post_ids = await r.zrevrange(f"feed:{user_id}", offset, offset + page_size - 1)
    
    # Get celebrity followees and fetch their recent posts
    celeb_ids = await db.get_celebrity_followees(user_id)
    celeb_posts = []
    for celeb_id in celeb_ids:
        recent = await r.zrevrange(f"posts:{celeb_id}", 0, 4)  # last 5
        celeb_posts.extend(recent)
    
    # Merge all post IDs
    all_post_ids = list(set(post_ids + celeb_posts))
    
    # Batch fetch post details
    posts = await db.bulk_fetch_posts(all_post_ids)
    
    # Sort by timestamp, return page
    return sorted(posts, key=lambda p: p["created_at"], reverse=True)[:page_size]
```

---

## Photo Upload Flow

```
1. Client → POST /upload → Media Service
2. Media Service:
   a. Generate unique post_id
   b. Upload original to S3
   c. Queue for thumbnail generation (Kafka → Image Workers)
   d. Return post_id + CDN URL to client

3. Image Workers:
   a. Generate thumbnails (480px, 240px, 80px)
   b. Store all variants to S3
   c. Update post record: thumbnail_urls = {...}

4. Client polls or gets WebSocket notification when thumbnails ready

CDN URLs:
  cdn.instagram.com/posts/post-123/480px.jpg
  cdn.instagram.com/posts/post-123/240px.jpg
```

---

## Like Count — Avoiding DB Bottleneck

```python
# Bad: UPDATE posts SET likes = likes + 1 WHERE id = ?
# Problem: 1M concurrent users liking → DB write bottleneck

# Good: Redis counter + async sync to DB
async def like_post(user_id: str, post_id: str):
    # Check if already liked (prevent double-like)
    already_liked = await r.sismember(f"likes:{post_id}", user_id)
    if already_liked:
        return {"liked": False, "message": "Already liked"}
    
    # Atomic add + increment
    await r.sadd(f"likes:{post_id}", user_id)
    count = await r.incr(f"like_count:{post_id}")
    
    # Async sync to DB (every 60 seconds via Celery task)
    return {"liked": True, "count": count}

# Celery task: sync Redis counters to DB every minute
@celery.task
def sync_like_counts():
    for key in r.scan_iter("like_count:*"):
        post_id = key.split(":")[1]
        count   = int(r.get(key))
        db.execute("UPDATE posts SET likes = %s WHERE id = %s", (count, post_id))
```

---

## Database Schema

```sql
-- Users
CREATE TABLE users (
    id          UUID PRIMARY KEY,
    username    VARCHAR(30) UNIQUE,
    bio         TEXT,
    avatar_url  TEXT,
    follower_count  INT DEFAULT 0,
    following_count INT DEFAULT 0
);

-- Posts
CREATE TABLE posts (
    id           UUID PRIMARY KEY,
    user_id      UUID REFERENCES users(id),
    caption      TEXT,
    media_urls   JSONB,       -- ["url1", "url2"] for carousel
    hashtags     TEXT[],
    likes_count  INT DEFAULT 0,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_posts_user_time ON posts(user_id, created_at DESC);

-- Follows (graph)
CREATE TABLE follows (
    follower_id  UUID REFERENCES users(id),
    followee_id  UUID REFERENCES users(id),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (follower_id, followee_id)
);
CREATE INDEX idx_follows_followee ON follows(followee_id);  -- get all followers
```

---

## Scaling Challenges

| Bottleneck | Solution |
|---|---|
| Feed for 500M DAU | Redis pre-computed feed (sorted sets) |
| Celebrity fanout | Hybrid: push for regular, pull for celebrities |
| 1.5 PB/day photos | S3 + CloudFront CDN + lazy-load thumbnails |
| Like counter race | Redis INCR (atomic) + async DB sync |
| Follow graph queries | Denormalize follower_count in users table |
| Search by hashtag | Elasticsearch, index hashtags |

---

## Interview Talking Points

1. **Why not use a single SQL query for news feed?**  
   At 500M DAU × 1000 follows = 500B rows to join. DB cannot handle this real-time.

2. **How do you handle the "celebrity problem"?**  
   Hybrid: pre-compute feed for regular users (push). Fetch celebrity posts at read time (pull). Merge in Feed Service.

3. **How do Stories differ from Posts?**  
   Stories have 24h TTL → stored in Redis with auto-expiry. Not in main feed — separate Stories feed. Cheaper storage (deleted after 24h).

4. **How do you recommend content (Explore page)?**  
   ML-based: collaborative filtering (users with similar likes), content-based (hashtag similarity). Separate recommendation service, pre-computed offline, served from Redis.
