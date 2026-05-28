# Design Reddit / Discussion Forum Platform

---

## 1. Requirements

### Functional
- Subreddits (communities) — create, subscribe.
- Posts (text, link, image, video).
- Comments (deeply nested threads).
- Votes (upvote/downvote on posts and comments).
- Feeds: home (subscribed), all, popular, subreddit-specific.
- Ranking: Hot, New, Top, Rising, Controversial.
- Search.
- User karma.
- Moderation (post removal, user ban, rules).
- Notifications (replies, mentions).

### Non-Functional
- 500M MAU, 50M DAU.
- 5B page views/day → ~60K reads/sec avg, peak ~250K/sec.
- 1M new posts/day, 10M comments/day, 100M votes/day.
- Feed gen p99 < 200ms.
- Read-heavy: 100:1 read-to-write ratio.

---

## 2. Scale Estimation

| Metric | Calc | Number |
|---|---|---|
| Reads/sec peak | 250K | |
| Writes/sec peak | (1M posts + 10M comments + 100M votes) / 86400 × 3 | ~4K |
| Posts storage | 1M/day × 5 KB × 10yr | ~18 TB |
| Comments storage | 10M/day × 500 bytes × 10yr | ~18 TB |
| Cache size | Top 10K subreddits × 1MB hot data | ~10 GB (fits Redis) |
| Active subreddits | ~3M, top 10K serve 90% of traffic | |

---

## 3. High-Level Architecture

```
                      ┌──────────────┐
                      │   CDN         │ (Cloudflare)
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │  API Gateway  │
                      └──────┬───────┘
                             │
       ┌─────────┬───────────┼───────────┬──────────┐
       │         │           │           │          │
   ┌───▼──┐ ┌────▼───┐  ┌────▼───┐  ┌────▼───┐ ┌────▼───┐
   │Posts │ │ Vote   │  │ Feed   │  │ Search │ │ User   │
   │Svc   │ │ Svc    │  │ Svc    │  │ Svc    │ │ Svc    │
   └───┬──┘ └────┬───┘  └────┬───┘  └────┬───┘ └────┬───┘
       │         │           │           │          │
       │         │     ┌─────▼──────┐    │          │
       │         │     │ Redis      │    │          │
       │         │     │ (feeds)    │    │          │
       │         │     └────────────┘    │          │
       │         │                       │          │
   ┌───▼─────────▼─────────────────┐    ┌▼─────┐    │
   │   Postgres (sharded)           │    │ ES    │    │
   │   posts, comments, votes       │    │       │    │
   └────────────────────────────────┘    └───────┘    │
                                                      ▼
                                                 ┌─────────┐
                                                 │ Postgres│
                                                 │ users    │
                                                 └─────────┘
```

---

## 4. Data Model

```sql
CREATE TABLE subreddits (
    id           BIGINT PRIMARY KEY,
    name         TEXT UNIQUE,        -- 'programming'
    description  TEXT,
    created_at   TIMESTAMPTZ,
    subscriber_count BIGINT,
    rules        JSONB
);

CREATE TABLE posts (
    id              BIGINT PRIMARY KEY,    -- Snowflake
    subreddit_id    BIGINT,
    author_id       BIGINT,
    title           TEXT,
    content_type    TEXT,          -- text/link/image/video
    content_url     TEXT,
    content_text    TEXT,
    upvotes         BIGINT DEFAULT 0,
    downvotes       BIGINT DEFAULT 0,
    comment_count   INT DEFAULT 0,
    created_at      TIMESTAMPTZ,
    is_removed      BOOL DEFAULT FALSE
);
CREATE INDEX ON posts(subreddit_id, created_at DESC);

CREATE TABLE comments (
    id            BIGINT PRIMARY KEY,
    post_id       BIGINT,
    parent_id     BIGINT NULL,    -- for nesting
    author_id     BIGINT,
    content       TEXT,
    upvotes       BIGINT DEFAULT 0,
    downvotes     BIGINT DEFAULT 0,
    depth         INT,            -- denormalized for sort efficiency
    path          LTREE,          -- '1.5.23.42' for tree queries
    created_at    TIMESTAMPTZ
);
CREATE INDEX ON comments(post_id, path);

CREATE TABLE votes (
    user_id    BIGINT,
    target_id  BIGINT,        -- post or comment
    target_type SMALLINT,     -- 0=post, 1=comment
    direction  SMALLINT,      -- +1, -1
    voted_at   TIMESTAMPTZ,
    PRIMARY KEY (user_id, target_id, target_type)
);

CREATE TABLE subscriptions (
    user_id      BIGINT,
    subreddit_id BIGINT,
    PRIMARY KEY (user_id, subreddit_id)
);
```

### Sharding
- `posts` → shard by `subreddit_id` (queries always include subreddit).
- `comments` → shard by `post_id`.
- `votes` → shard by `user_id` (user's vote history queries) OR `target_id` (recompute aggregates). Reddit uses both: dual-write or read-replicate.

---

## 5. Voting System

Naive: every vote → `UPDATE posts SET upvotes = upvotes + 1 WHERE id = ?`.
Problem: row-level lock contention on hot posts (front-page post gets 1000 votes/sec).

### Solution: write to log + async aggregation

```python
@app.post("/vote")
async def vote(req: VoteRequest, user_id: int):
    # 1. Persist user's vote (idempotent via PK)
    await db.execute("""
        INSERT INTO votes (user_id, target_id, target_type, direction, voted_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (user_id, target_id, target_type)
        DO UPDATE SET direction = EXCLUDED.direction, voted_at = now()
    """, user_id, req.target_id, req.target_type, req.direction)

    # 2. Publish to Kafka
    await kafka.produce("votes", {
        "target_id": req.target_id,
        "direction": req.direction,
        "user_id": user_id
    })

    return {"ok": True}
```

### Aggregator (consumer)

```python
# Coalesce votes per target every 5 seconds → single UPDATE
async def vote_aggregator():
    buffer = defaultdict(lambda: {"up": 0, "down": 0})
    async for batch in kafka.consume("votes", batch_size=1000):
        for msg in batch:
            if msg.direction == 1:
                buffer[msg.target_id]["up"] += 1
            else:
                buffer[msg.target_id]["down"] += 1

        for target_id, counts in buffer.items():
            await db.execute(
                "UPDATE posts SET upvotes = upvotes + %s, downvotes = downvotes + %s WHERE id = %s",
                counts["up"], counts["down"], target_id
            )
        buffer.clear()
```

**Trade-off:** Vote counts lag by ~5 seconds. Acceptable.

### Faked numbers (Reddit's "fuzzing")
Reddit deliberately fuzzes vote counts to prevent bot detection of vote manipulation. Real reddit counts are stored internally; displayed counts are slightly randomized.

---

## 6. Ranking Algorithms

### Hot Ranking (front-page algorithm)

```python
import math
from datetime import datetime

EPOCH = datetime(2005, 12, 8).timestamp()

def hot_score(ups, downs, created_at) -> float:
    score = ups - downs
    order = math.log10(max(abs(score), 1))
    sign = 1 if score > 0 else (-1 if score < 0 else 0)
    seconds = created_at.timestamp() - EPOCH
    return sign * order + seconds / 45000  # ~12.5h time decay
```

Older posts decay; high-score posts age slower. Pre-compute periodically for top subreddits.

### Best Comments (Wilson lower bound)

```python
def wilson_score(ups, downs):
    n = ups + downs
    if n == 0: return 0
    z = 1.96  # 95% confidence
    p = ups / n
    return (p + z*z/(2*n) - z * math.sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
```

Better than (ups-downs) because it accounts for sample size. A comment with 10 ups / 0 downs > 1000 ups / 500 downs.

### Controversial

```python
def controversial(ups, downs):
    if ups <= 0 or downs <= 0: return 0
    magnitude = ups + downs
    balance = downs / ups if ups > downs else ups / downs
    return magnitude ** balance
```

Posts with similar ups+downs score higher.

---

## 7. Feed Generation

### Subreddit feed (single subreddit, sorted by Hot)

```sql
SELECT id, title, upvotes, downvotes, created_at,
    hot_score(upvotes, downvotes, created_at) AS hot
FROM posts
WHERE subreddit_id = ?
  AND created_at > now() - interval '30 days'
ORDER BY hot DESC
LIMIT 25;
```

For top subreddits: precompute and cache the sorted list every minute in Redis.

```python
# Periodic job
async def refresh_subreddit_feed(subreddit_id):
    posts = await db.fetch("SELECT id, ... FROM posts WHERE subreddit_id = $1 ORDER BY hot DESC LIMIT 1000", subreddit_id)
    pipe = redis.pipeline()
    pipe.delete(f"feed:sub:{subreddit_id}")
    pipe.zadd(f"feed:sub:{subreddit_id}", {p.id: p.hot for p in posts})
    pipe.expire(f"feed:sub:{subreddit_id}", 600)
    await pipe.execute()
```

### Home feed (user's subscribed subreddits)
**Approach 1: Read-time aggregation (Twitter-style fanout-on-read)**
- Fetch from each subscribed subreddit's cached top-N.
- Merge, sort, take top 25.

```python
async def home_feed(user_id: int):
    subs = await get_subscriptions(user_id)  # cached
    posts_per_sub = []
    for sub_id in subs:
        ids = await redis.zrevrange(f"feed:sub:{sub_id}", 0, 19, withscores=True)
        posts_per_sub.extend(ids)

    posts_per_sub.sort(key=lambda x: -x[1])
    top_25_ids = [pid for pid, _ in posts_per_sub[:25]]
    return await fetch_posts_bulk(top_25_ids)
```

Latency: O(N subs × cache call). Most users have < 100 subscriptions → fast.

**Approach 2: Write-fanout (only for power users with millions of subscribers)**
Not needed — Reddit only fans out for subreddits, not user-to-user.

---

## 8. Comments — Deeply Nested

### Storage with materialized path

```sql
-- A reply to comment 5 inside post 1, where comment 5's path = '1.3.5'
INSERT INTO comments (..., path) VALUES (..., '1.3.5.42'::ltree);

-- Fetch full tree
SELECT * FROM comments
WHERE path <@ '1'::ltree
ORDER BY path, created_at;
```

PostgreSQL `ltree` extension does this natively + indexes well.

### Display strategy
- Top-level: paginated 25 at a time.
- Children: progressive disclosure ("load more").
- Deep threads (>10): collapse, show "continue reading".

### Comment count denormalization
Maintained via Kafka event on insert:
```python
INSERT comment → kafka → consumer: UPDATE posts SET comment_count = comment_count + 1
```

---

## 9. Search

Elasticsearch indices:
- `posts`: title + content, filtered by subreddit, sorted by relevance + recency.
- `comments`: less common but supported.
- `users`: name search.

```python
GET /posts/_search
{
  "query": {
    "bool": {
      "must": [{"multi_match": {"query": "python tips", "fields": ["title^3", "content"]}}],
      "filter": [{"term": {"subreddit_name": "programming"}}]
    }
  },
  "sort": [{"_score": "desc"}, {"created_at": "desc"}]
}
```

---

## 10. Caching Strategy

| Cache | TTL | Notes |
|---|---|---|
| Subreddit metadata | 1h | Rarely changes |
| Post details (top 10K hot) | 1m | Edge-cacheable |
| Subreddit feed (sorted) | 1m | Regen by cron |
| User subscription list | 5m | Invalidate on subscribe |
| Comment trees (top posts) | 30s | Hot posts only |
| Vote counts | Live (Redis counter) | Flushed to DB every 5s |

### Pre-warming
Front-page posts: aggressively cached at CDN. Stale-while-revalidate.

### Cache stampede
Hot post expires → 1000 requests hit DB.
Fix: lock-on-miss (single regen), serve stale during regen.

---

## 11. Anti-Vote Manipulation

### Signals
- New accounts voting → low weight.
- Cross-account voting patterns from same IP.
- Time correlation (votes coming in burst).
- Vote-only accounts (no posts/comments).

### Counter-measures
- **Shadow ban**: user thinks votes work, but they're ignored.
- **Vote weight**: based on account age + karma.
- **Ratelimit per IP** at gateway.

```python
class VoteWeight:
    def calculate(self, user):
        if user.is_shadow_banned: return 0
        if user.account_age_days < 7: return 0.1
        if user.karma < 100: return 0.5
        return 1.0
```

---

## 12. Moderation

### Auto-moderation
- Spam filter (ML model).
- Rule-based: regex on titles, URL blocklists.
- AutoMod: per-subreddit YAML config.

### Manual moderation
- Mod queue: reported items.
- Actions: remove post, ban user, lock thread, distinguish comment.

### Audit log
Every mod action logged immutable:
```sql
CREATE TABLE mod_actions (
    id BIGSERIAL, mod_id BIGINT, target_id BIGINT, action TEXT,
    reason TEXT, created_at TIMESTAMPTZ
);
```

---

## 13. Notifications

User gets notifications for:
- Replies to their comments/posts.
- @mentions.
- DMs (separate system).
- Mod actions on their content.

```python
# On comment insert
async def on_new_comment(comment):
    parent = comment.parent  # post or comment
    if parent.author_id != comment.author_id:  # not self-reply
        await create_notification(
            user_id=parent.author_id,
            type="reply",
            target=comment
        )

    # @mentions
    for mentioned_user in extract_mentions(comment.content):
        await create_notification(user_id=mentioned_user.id, type="mention", target=comment)
```

---

## 14. Edge Cases

### Reddit hug of death (sudden traffic spike on a single post)
- CDN caches the post page.
- Comments lazily loaded.
- Vote counter at Redis level (fast).

### Comment ordering stability
Reddit shows comments by "best" by default. If two replies arrive simultaneously, tie-break by created_at (Snowflake ID order).

### Account deletion
- Soft-delete: replace username with `[deleted]`, content preserved.
- Hard delete on user request: content removed, edit log preserved for audit.

### Brigading
Mass-vote attacks from external sites.
- Detect via referrer + IP cluster.
- Block votes from cohort temporarily.
- Mods alerted.

---

## 15. APIs

```
POST /subreddits/{name}/posts          # create post
GET  /subreddits/{name}/posts?sort=hot&t=day&limit=25
GET  /posts/{id}                       # detail
POST /posts/{id}/comments              # create comment
GET  /posts/{id}/comments?sort=best&depth=10
POST /vote   { target_id, direction }
GET  /r/all
GET  /r/popular
GET  /home   (subscribed feed)
GET  /search?q=...&type=post

WS:  /events?subreddits=...            # live new posts
```

---

## 16. Trade-offs

| Decision | Trade-off |
|---|---|
| Async vote aggregation | Lag 5s; eliminates contention |
| LTREE for comments | Fast subtree queries; needs ltree extension |
| Read-fanout home feed | Slower for power users; no write amplification |
| Cache-heavy reads | Cold reads slow; covers 99% of cases |
| Fuzzed vote counts | Counter manipulation harder; user confusion |

---

## 17. Follow-up Questions

- **"What if a subreddit goes viral?"** → Sharding by subreddit_id may create hotspot; split into sub-shards by post_id range.
- **"How would you A/B test feed algorithms?"** → User cohorts get different `hot_score()` weights. Track engagement metrics.
- **"How to prevent karma farming?"** → Bot detection ML, vote weight by account quality, repost detection.
- **"Real-time updates on a post page?"** → WebSocket for live vote count, new comment notifications.
- **"Awards / Reddit Gold?"** → Separate payment service, awards stored alongside post, displayed on render.
- **"Subreddit private/restricted/quarantined?"** → Access check at API layer: query user's subscription + subreddit's privacy settings.
