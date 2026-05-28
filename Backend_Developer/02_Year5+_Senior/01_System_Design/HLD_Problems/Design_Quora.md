# Design Quora / Stack Overflow (Q&A Platform)

---

## 1. Requirements

### Functional
- Users post questions with tags.
- Users post answers to questions.
- Upvote / downvote on questions and answers.
- Comment on questions/answers.
- Follow users, topics, questions.
- Personalized feed.
- Search (full-text).
- Reputation system (Stack Overflow style).
- Edit history.
- Question / answer ranking.
- Mark accepted answer.

### Non-Functional
- 200M users, 50M MAU.
- 10M new questions/year, 30M new answers/year.
- 1B page views/month.
- Read p99 < 200ms.
- Write p99 < 500ms.
- 99.95% availability.
- Read-heavy: 100:1 read-to-write ratio.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Active users (DAU) | 5M |
| Pageviews/day | 30M → 350/sec avg, 2K/sec peak |
| New posts/day | ~100K questions + answers |
| Votes/day | 5M |
| Searches/day | 5M |
| Total questions | 50M historical |
| Total answers | 200M historical |
| Avg answer length | 500 bytes; 200M × 500B = 100GB content |

---

## 3. High-Level Architecture

```
                       ┌────────────┐
                       │   CDN       │
                       └─────┬──────┘
                             │
                       ┌─────▼──────┐
                       │ API Gateway │
                       └─────┬──────┘
                             │
   ┌──────────┬──────────┬──┴───────┬──────────┬──────────┐
   │          │          │          │          │          │
┌──▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐
│ Q&A  │ │ Search │ │ Feed   │ │ Vote   │ │ User   │ │ Notif  │
│ Svc  │ │  Svc   │ │  Svc   │ │  Svc   │ │  Svc   │ │  Svc   │
└──┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
   │          │          │          │          │           │
┌──▼─────────▼──────────▼──────────▼──────────▼──────┐    │
│  Postgres (sharded) + Cassandra (timeline) + ES    │    │
│  + Redis (counts, cache) + Kafka                    │    │
└─────────────────────────────────────────────────────┘    │
                                                          ▼
                                                   ┌──────────────┐
                                                   │ Email + Push │
                                                   └──────────────┘
```

---

## 4. Data Model

```sql
CREATE TABLE users (
    id          BIGINT PRIMARY KEY,
    name        TEXT,
    bio         TEXT,
    rep_score   INT DEFAULT 0,
    created_at  TIMESTAMPTZ
);

CREATE TABLE questions (
    id            BIGINT PRIMARY KEY,
    author_id     BIGINT,
    title         TEXT,
    body          TEXT,
    tags          TEXT[],
    view_count    BIGINT DEFAULT 0,
    answer_count  INT DEFAULT 0,
    upvotes       INT DEFAULT 0,
    downvotes     INT DEFAULT 0,
    accepted_answer_id BIGINT NULL,
    created_at    TIMESTAMPTZ,
    edited_at     TIMESTAMPTZ NULL
);
CREATE INDEX ON questions(author_id, created_at DESC);
CREATE INDEX ON questions USING GIN(tags);

CREATE TABLE answers (
    id            BIGINT PRIMARY KEY,
    question_id   BIGINT,
    author_id     BIGINT,
    body          TEXT,
    upvotes       INT DEFAULT 0,
    downvotes     INT DEFAULT 0,
    is_accepted   BOOL DEFAULT FALSE,
    created_at    TIMESTAMPTZ,
    edited_at     TIMESTAMPTZ
);
CREATE INDEX ON answers(question_id);
CREATE INDEX ON answers(author_id, created_at DESC);

CREATE TABLE comments (
    id            BIGINT PRIMARY KEY,
    parent_id     BIGINT,     -- question or answer
    parent_type   SMALLINT,   -- 0=question, 1=answer
    author_id     BIGINT,
    body          TEXT,
    created_at    TIMESTAMPTZ
);
CREATE INDEX ON comments(parent_type, parent_id);

CREATE TABLE votes (
    user_id     BIGINT,
    target_id   BIGINT,
    target_type SMALLINT,    -- 0=question, 1=answer
    direction   SMALLINT,    -- +1 or -1
    voted_at    TIMESTAMPTZ,
    PRIMARY KEY (user_id, target_id, target_type)
);

CREATE TABLE follows (
    follower_id  BIGINT,
    target_id    BIGINT,
    target_type  SMALLINT,    -- 0=user, 1=topic, 2=question
    followed_at  TIMESTAMPTZ,
    PRIMARY KEY (follower_id, target_id, target_type)
);
```

### Sharding
- `questions`: by `id` (random distribution).
- `answers`: by `question_id` (co-locate with questions).
- `comments`: by `parent_id`.
- `votes`: by `user_id`.
- `follows`: by `follower_id`.

---

## 5. Vote System

Same problem as Reddit: hot questions get many votes; row-level contention.

### Pattern (covered in Reddit doc): write to log + async aggregate

```python
@app.post("/vote")
async def vote(req: VoteRequest, user_id: int):
    # 1. Persist vote (idempotent via PK)
    await db.execute("""
        INSERT INTO votes (user_id, target_id, target_type, direction, voted_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (user_id, target_id, target_type)
        DO UPDATE SET direction = EXCLUDED.direction, voted_at = now()
    """, user_id, req.target_id, req.target_type, req.direction)

    # 2. Update Redis counter live (fast UI feedback)
    if req.direction == 1:
        await redis.hincrby(f"votes:{req.target_type}:{req.target_id}", "up", 1)
    else:
        await redis.hincrby(f"votes:{req.target_type}:{req.target_id}", "down", 1)

    # 3. Publish for async aggregator
    await kafka.send("votes", req.dict())

    return {"ok": True}
```

Async aggregator flushes counts to DB every 30s.

### Reputation (Stack Overflow style)

```python
REP_RULES = {
    "question_upvote": +5,
    "answer_upvote": +10,
    "answer_accepted": +15,
    "answer_downvote": -2,
    "downvoter": -1,
    "spam_flag": -100,
    "bounty_awarded": "variable",
}
```

When vote happens → publish to `reputation_events` topic → consumer updates `users.rep_score`.

Eventually consistent (acceptable; user sees rep updated within seconds).

---

## 6. Question / Answer Ranking

### Hot / trending
For homepage:
```python
def hot_score(upvotes, downvotes, age_hours):
    score = upvotes - downvotes
    return score / ((age_hours + 2) ** 1.8)
```

Hacker News-style. Older = lower.

### Best answer (sort within question)
1. Accepted answer (if any) at top.
2. Then by `upvotes - downvotes`.
3. Then by created_at (older first if tied).

Or use Wilson score (statistical confidence):
```python
def wilson(ups, downs):
    n = ups + downs
    if n == 0: return 0
    z = 1.96
    p = ups / n
    return (p + z*z/(2*n) - z * math.sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
```

Used for "best answer" sorting.

---

## 7. Feed Generation

User opens home: shows personalized question feed.

### Algorithm
Mix of:
- Questions in topics user follows.
- Questions from users user follows.
- Trending in popular topics.
- Older but high-quality (recency-decayed score).

### Implementation: read-fanout

```python
async def get_feed(user_id, limit=20):
    # Get follows
    follows = await db.fetch(
        "SELECT target_id, target_type FROM follows WHERE follower_id = $1",
        user_id
    )

    # For each follow type, gather candidates
    candidates = []

    for f in follows:
        if f.target_type == 1:   # topic
            questions = await es.search(
                index="questions",
                body={"query": {"term": {"tags": f.target_id}}, "size": 20}
            )
            candidates.extend(questions)
        elif f.target_type == 0:   # user
            user_q = await db.fetch(
                "SELECT * FROM questions WHERE author_id = $1 ORDER BY created_at DESC LIMIT 5",
                f.target_id
            )
            candidates.extend(user_q)

    # Add trending overall
    trending = await redis.zrevrange("trending:questions", 0, 19, withscores=True)
    candidates.extend(trending)

    # Dedupe + rank + filter already-seen
    seen = await redis.smembers(f"seen:{user_id}")
    candidates = [c for c in candidates if c.id not in seen]

    # Rank by personalization score
    scored = [(c, personalization_score(c, user_id)) for c in candidates]
    return sorted(scored, key=lambda x: -x[1])[:limit]
```

For power users with many follows: heavier query. Cache feed for 5 minutes.

---

## 8. Search

ES indices:
- `questions`: title (heavy weight) + body + tags + author.
- `answers`: body + author + question_id.
- `users`: name + bio.

```json
{
  "query": {
    "multi_match": {
      "query": "python async",
      "fields": ["title^3", "body", "tags^2"]
    }
  },
  "sort": [
    {"_score": "desc"},
    {"upvotes": "desc"}
  ]
}
```

Newer questions ranked slightly higher (recency boost).

Tag filtering:
```json
{"filter": [{"term": {"tags": "python"}}]}
```

---

## 9. Notifications

User gets notified for:
- Answer posted on their question.
- Comment on their question/answer.
- Mention via @username.
- Vote on their content (configurable; not on every vote).
- Acceptance of their answer.

```python
# On answer post
await create_notification(
    user_id=question.author_id,
    type="new_answer",
    target=answer
)
```

In-app notification + optional push/email.

---

## 10. Reputation & Privileges

Stack Overflow's reputation gates privileges:

| Rep | Privilege |
|---|---|
| 1 | Ask, answer |
| 15 | Vote up |
| 50 | Comment |
| 125 | Vote down |
| 1000 | Established user |
| 2000 | Edit any post |
| 10000 | Moderation tools |
| 25000 | Full moderation |

Encourages quality contributions.

---

## 11. Tags

Each question 1-5 tags. Tags themselves are entities:

```sql
CREATE TABLE tags (
    name           TEXT PRIMARY KEY,
    description    TEXT,
    follower_count BIGINT DEFAULT 0,
    question_count BIGINT DEFAULT 0
);
```

Tag pages list questions under that tag, sorted by trending/newest/votes.

ES tag aggregation:
```json
{
  "aggs": {
    "popular_tags": {
      "terms": {"field": "tags", "size": 20}
    }
  }
}
```

---

## 12. Caching

| Layer | TTL |
|---|---|
| CDN: static assets, images | 1 day |
| Question pages (anonymous) | 1 min |
| Question pages (logged-in) | 30 sec |
| User profile | 5 min |
| Hot questions list | 1 min |
| Tag pages | 5 min |
| Search results | 5 min for popular queries |

### Cache invalidation
On vote/edit → invalidate question cache. Use cache tags for bulk invalidation.

---

## 13. Edit History

Every edit creates a new version:
```sql
CREATE TABLE question_revisions (
    id          BIGINT,
    question_id BIGINT,
    revision_no INT,
    title       TEXT,
    body        TEXT,
    edited_by   BIGINT,
    edited_at   TIMESTAMPTZ
);
```

Allows rollback, blame analysis, audit.

---

## 14. Markdown / Rich Text

Posts in Markdown:
```python
import markdown

html = markdown.markdown(post.body, extensions=["fenced_code", "tables"])
# Sanitize HTML to prevent XSS:
import bleach
safe = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
```

Cache rendered HTML alongside raw markdown (re-render on edit).

For code blocks: syntax highlight via Pygments / Highlight.js.

---

## 15. Moderation

### User actions
- Flag post as spam/offensive.
- Suggest edits.
- Mark "off-topic" / "duplicate".

### Auto-moderation
- Spam filter ML.
- Auto-close low-quality questions.
- Auto-merge duplicates.

### Manual moderation
- Moderators review flag queue.
- Vote-to-close (5 close votes from high-rep users → closed).

### Audit log
All mod actions logged immutably.

---

## 16. Real-Time Updates

For active question pages: live answer count, vote count.

WebSocket subscription per question:
```python
@app.websocket("/ws/question/{q_id}")
async def question_ws(ws, q_id):
    await ws.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"question:{q_id}:events")
    async for msg in pubsub.listen():
        await ws.send_json(json.loads(msg["data"]))
```

Events:
- New answer.
- New comment.
- Vote count change.

For pages with low traffic: skip WS, use polling.

---

## 17. Search Quality

Beyond keyword matching:

### Semantic search
- Compute embeddings of questions (Sentence-BERT).
- Index in vector DB (Pinecone, FAISS).
- Query embedding → nearest neighbors.

```python
embedding = encoder.encode(query)
similar = vector_db.search(embedding, k=10)
```

Useful for finding "similar questions" even with different wording.

### Hybrid (lexical + semantic)
- BM25 score from ES + cosine similarity from vectors.
- Combine: `final_score = α × BM25 + (1-α) × cosine`.

---

## 18. Spam & Quality Control

### At submission
- Rate limit posting (1 post / 90 sec for new users).
- Detect duplicates (vector similarity > 0.9).
- ML spam classifier.

### Karma / rep gates
- New users need 50+ rep to post links.
- Forced edit-only for first N posts.

### Flagging
- Community flags accumulate.
- ML model recommends actions to mods.

---

## 19. APIs

```
POST  /questions                     (create)
GET   /questions/{id}                (read)
POST  /questions/{id}/answers        (post answer)
POST  /comments
POST  /vote   { target_id, direction }
GET   /search?q=...&tags=...
GET   /feed                          (personalized)
GET   /tags/{name}/questions
POST  /questions/{id}/accept-answer  { answer_id }
GET   /users/{id}                    (profile)
POST  /follow                        (user/topic/question)
WS    /ws/question/{id}              (real-time updates)
```

---

## 20. Hot Issues

### Same person asking same question
Vector similarity detection on submit → suggest existing similar questions.

### Closed/duplicate handling
Mark as duplicate; link to original. Future views redirect or show side-by-side.

### Karma farming
ML detects: rapid posting, vote rings, scripted behavior. Shadow ban.

### Sock puppet accounts
Same IP, similar behavior → flag for review.

### Wikipedia-edit-war
Two users repeatedly editing each other's edits → temporary post lock.

---

## 21. Trade-offs

| Decision | Trade-off |
|---|---|
| Read-fanout feed | Compute per request; scales linearly |
| Write-fanout feed | Pre-compute; storage explosion |
| Async vote aggregation | UI feels live (Redis); DB eventually consistent |
| ES for search | Fast, lag |
| Vector search | Semantic quality, infra cost |
| Per-question cache | High hit rate; invalidation complexity |

Read-fanout is the right call (most users have few follows).

---

## 22. Follow-up Questions

- **"Differences between Quora and Stack Overflow?"** → Quora: more conversational, broad topics. SO: technical, accepted-answer focused, reputation-driven.
- **"How would you train the spam classifier?"** → Manual labeling + auto-label from flag history + adversarial training. Re-train weekly.
- **"How does 'questions you might know the answer to' work?"** → Tag overlap between user's answered questions and unanswered questions. ML model on user expertise topics.
- **"How to handle non-English content?"** → Per-language ES analyzers, language detection on submit, separate UI per language.
- **"Real-time view count for popular questions?"** → Redis INCR + flush to DB; show approximate count.
- **"How would you A/B test feed algorithm?"** → User bucketing; track engagement (CTR, time spent, follow-ups).
- **"Bounties (SO-style)?"** → Rep transferred from question author to best-answer author; queue with auto-expire.
