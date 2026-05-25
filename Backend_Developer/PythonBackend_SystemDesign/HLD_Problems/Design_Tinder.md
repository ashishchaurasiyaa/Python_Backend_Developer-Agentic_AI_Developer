# Design Tinder / Dating App

---

## 1. Requirements

### Functional
- Profile creation (photos, bio, age, gender, preferences).
- Recommendation feed (cards to swipe).
- Swipe left (no), right (yes), super-like.
- Mutual match → unlock chat.
- 1:1 chat after match.
- Filter by distance, age range, gender.
- Boost / premium features (visibility, see who likes you).
- Photo verification.

### Non-Functional
- 100M users globally, 50M MAU.
- 1.5B swipes/day → ~17K swipes/sec, peak ~50K/sec.
- Feed gen p99 < 300ms.
- Match detection real-time (< 1s).
- Geo queries: find users within 50km.

---

## 2. Scale Estimation

| Metric | Calc | Number |
|---|---|---|
| Swipes/sec avg | 1.5B / 86400 | 17K |
| Swipes/sec peak | 17K × 3 | 50K |
| Active feed gens/sec | 5M peak users × 1 feed / 5 min | ~17K |
| Photo storage | 100M users × 6 photos × 200KB | ~120 TB |
| Daily new matches | 1.5B swipes × 4% right rate × 2% reciprocity | ~1.2M / day |
| Active chats | 1.2M new matches × 30% chat | ~360K new chats/day |

---

## 3. High-Level Architecture

```
                          ┌──────────────┐
                          │   API Gateway │
                          └──────┬───────┘
                                 │
       ┌─────────────┬───────────┼──────────────┬──────────────┐
       │             │           │              │              │
  ┌────▼────┐  ┌─────▼────┐  ┌───▼────┐  ┌──────▼─────┐  ┌─────▼─────┐
  │ Profile │  │ Feed/Reco│  │ Swipe  │  │  Match     │  │  Chat     │
  │ Service │  │ Service  │  │ Service│  │  Service   │  │  Service  │
  └────┬────┘  └────┬─────┘  └───┬────┘  └─────┬──────┘  └─────┬─────┘
       │            │            │              │               │
  ┌────▼──┐    ┌────▼─────┐   ┌──▼────┐    ┌────▼───┐      ┌────▼───┐
  │ Postgr│    │ Redis +  │   │Cassand│    │Postgres│      │Cassandra│
  │  +    │    │ ES (Geo) │   │ ra    │    │  +     │      │  + S3   │
  │  S3   │    │          │   │       │    │ Cache  │      │         │
  └───────┘    └──────────┘   └───────┘    └────────┘      └─────────┘
                                                    │
                                          ┌─────────▼──────────┐
                                          │ Push (FCM/APNs)    │
                                          └────────────────────┘
```

---

## 4. Profile Service

Stores user profiles. Standard CRUD.

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY,
    name          TEXT,
    age           INT,
    gender        TEXT,
    bio           TEXT,
    job_title     TEXT,
    school        TEXT,
    interests     TEXT[],
    photos        TEXT[],         -- S3 URLs
    location_lat  DOUBLE PRECISION,
    location_lon  DOUBLE PRECISION,
    location_h3   TEXT,           -- H3 hexagon ID
    created_at    TIMESTAMPTZ
);

CREATE TABLE user_prefs (
    user_id        UUID PRIMARY KEY REFERENCES users(id),
    interested_in  TEXT[],     -- ['male', 'female', 'non-binary']
    age_min        INT,
    age_max        INT,
    max_distance_km INT
);
```

Profile cached in Redis (~1KB × 100M = 100GB → use multiple Redis clusters).

---

## 5. Geo Recommendation (Hardest Part)

Need: for user U at (lat, lon), find candidates within 50km matching prefs, NOT already swiped, ranked by ELO + freshness.

### Option A: PostGIS
```sql
SELECT *
FROM users
WHERE ST_DWithin(
    location::geography,
    ST_MakePoint($lon, $lat)::geography,
    50000   -- 50km
)
  AND age BETWEEN $min AND $max
  AND gender = ANY($interested_in)
  AND id NOT IN (SELECT target_id FROM swipes WHERE user_id = $uid)
LIMIT 100;
```
Works for moderate scale. Index: `GiST` on location.

### Option B: H3 Hexagons (Uber's library) — scales better
- Each user assigned H3 cell (level 7 ≈ 5km).
- To find candidates within 50km, get 50km / 5km = 10-cell radius hexagons.
- Look up users in those hex cells from Redis.

```python
import h3
def cells_around(lat, lon, radius_km=50):
    center = h3.geo_to_h3(lat, lon, 7)
    return h3.k_ring(center, k=radius_km // 5)

def get_candidates(user):
    cells = cells_around(user.lat, user.lon, user.max_dist)
    candidate_ids = set()
    for cell in cells:
        ids = redis.smembers(f"geo:{cell}:{user.target_gender}")
        candidate_ids.update(ids)
    return candidate_ids
```

Redis sets are fast. Storage: ~100M users in geo sets ≈ 5GB.

### Option C: Elasticsearch geo_distance
Easy, but slower at scale; good for moderate.

---

## 6. Feed Generation (Recommendation)

```
1. Get candidate pool (geo + filters) → ~5000 candidates typically
2. Filter out already-swiped (Bloom filter check)
3. Filter out blocked / reported users
4. Rank by score:
   score = ELO * weight_elo
         + freshness * weight_new (newer profile = higher)
         + activity * weight_active (recently online)
         - distance * weight_dist
         + premium_boost
5. Return top 100 — client pre-fetches batches of 25
```

### Caching the feed
- Computed once, stored in Redis sorted set per user.
- Refreshed when user runs out or every 30 min.
- TTL 1 hour → forces periodic refresh.

```python
# After generating
await redis.zadd(f"feed:{user_id}", {uid: score for uid, score in ranked})
await redis.expire(f"feed:{user_id}", 3600)

# Client fetches
candidates = await redis.zrevrange(f"feed:{user_id}", 0, 24, withscores=True)
```

---

## 7. Already-Swiped Filter

Naive: query `swipes` table for each candidate. 5000 candidates × 1 query = 5000 queries → no.

### Bloom filter per user
- 100K swipes per user max → 100K * 10 bits = 125KB.
- Stored in Redis as binary.
- Check: O(1).

```python
from pybloom_live import ScalableBloomFilter
async def is_swiped(user_id, target_id) -> bool:
    bf_data = await redis.get(f"swiped_bf:{user_id}")
    if not bf_data: return False
    bf = pickle.loads(bf_data)
    return target_id in bf
```

On swipe → update bloom and persist swipe.

**Trade-off:** False positives possible (~1%) — user occasionally won't see candidates they didn't actually swipe. Acceptable.

---

## 8. Swipe Service

```python
@app.post("/swipe")
async def swipe(req: SwipeRequest):
    # Persist swipe
    await cassandra.execute(
        "INSERT INTO swipes (user_id, target_id, direction, created_at) "
        "VALUES (%s, %s, %s, now())",
        req.user_id, req.target_id, req.direction
    )

    # Update bloom filter
    await update_bloom(req.user_id, req.target_id)

    if req.direction == "right" or req.direction == "super":
        # Check reciprocal
        reciprocal = await cassandra.fetch_one(
            "SELECT direction FROM swipes "
            "WHERE user_id = %s AND target_id = %s",
            req.target_id, req.user_id
        )
        if reciprocal and reciprocal.direction in ("right", "super"):
            await create_match(req.user_id, req.target_id)
            return {"match": True, "match_id": match.id}

    return {"match": False}
```

### Swipe table (Cassandra)
```sql
CREATE TABLE swipes (
    user_id     UUID,
    target_id   UUID,
    direction   TEXT,    -- right, left, super
    created_at  TIMESTAMP,
    PRIMARY KEY (user_id, target_id)
);
```

Partition key = user_id. Allows efficient "did A swipe B?" via point query.

---

## 9. Match Detection

When mutual right-swipe detected:
```python
async def create_match(uid1, uid2):
    match_id = uuid.uuid4()
    a, b = sorted([uid1, uid2])  # canonical order
    await postgres.execute(
        "INSERT INTO matches (id, user_a, user_b, created_at) "
        "VALUES (%s, %s, %s, now())",
        match_id, a, b
    )
    await kafka.produce("matches", {"match_id": match_id, "user_a": a, "user_b": b})
    # Push notification to both users
```

### Matches table (Postgres)
```sql
CREATE TABLE matches (
    id        UUID PRIMARY KEY,
    user_a    UUID,
    user_b    UUID,
    created_at TIMESTAMPTZ,
    last_msg_at TIMESTAMPTZ,
    UNIQUE (user_a, user_b)   -- canonical order
);
CREATE INDEX ON matches(user_a, last_msg_at DESC);
CREATE INDEX ON matches(user_b, last_msg_at DESC);
```

---

## 10. ELO Rating

Tinder reportedly uses ELO-like (called "desirability score" internally).
- User starts at 1500.
- When A swipes right on B: A's ELO impacts B's gain.
  - If B is high-ELO and A is low-ELO → small gain.
  - If B is low-ELO and A is high-ELO → big gain.
- Symmetric for left swipes.

```python
def update_elo(swiper_elo, target_elo, swipe_right) -> tuple[float, float]:
    K = 32
    expected_target = 1 / (1 + 10 ** ((swiper_elo - target_elo) / 400))
    actual = 1 if swipe_right else 0
    new_target = target_elo + K * (actual - expected_target)
    return new_target
```

Update asynchronously via Kafka consumer.

---

## 11. Chat After Match

Same as a simplified Slack/WhatsApp:
- WebSocket for real-time.
- Messages stored in Cassandra partitioned by `match_id`.
- Push notification when offline.

```sql
CREATE TABLE messages_by_match (
    match_id  UUID,
    msg_id    BIGINT,
    sender_id UUID,
    content   TEXT,
    sent_at   TIMESTAMP,
    PRIMARY KEY (match_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);
```

---

## 12. Photos & CDN

- Upload via presigned S3 URLs.
- Pre-process: resize to 4 sizes (thumbnail, small, medium, large).
- Served via CloudFront / Cloudflare.
- Moderation: ML model scans for nudity, fake faces, deepfakes.

```
Photo upload pipeline:
1. Client uploads to S3 (presigned URL)
2. S3 trigger → Lambda
3. Lambda: resize to multiple sizes + content moderation
4. If passes moderation, update profile photo URLs
5. If flagged, send to manual review queue
```

---

## 13. Premium Features

### Boost
User's profile shown ~10x more for 30 min.
- Implementation: multiply `score` by 10 in feed generation for boosted users.
- Stored in Redis with TTL: `boosted:{user_id} → 1` with `EX 1800`.

### See Who Likes You
Reverse query: who right-swiped on me?
```sql
SELECT user_id FROM swipes
WHERE target_id = $me AND direction = 'right'
  AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = $me)
ORDER BY created_at DESC;
```

Needs `(target_id)` index.

### Super Like
- 1-5 per day depending on tier.
- Notifies recipient immediately ("X super liked you").
- 3x weight in their feed.

---

## 14. Edge Cases

### Spammer / bot detection
- Right-swipe rate > 95% (humans typically 5-40%).
- High swipe velocity (> 1/sec sustained).
- Photo similarity (reused images).
- Account: flag → shadow ban → review.

### Distance updates
- User travels → location changes.
- Update H3 cell → re-index in Redis geo sets.
- Old cell `SREM`, new cell `SADD`.

### Privacy / Block
- Block list per user → exclude from feed.
- Report → mod queue → ban if confirmed.
- Show user only to opposite-gender preference, etc.

### Right-to-be-forgotten
- Delete from all DBs (users, swipes, matches, messages).
- Photos S3 delete.
- 30-day grace then permanent.

---

## 15. Trade-offs

| Decision | Trade-off |
|---|---|
| H3 over PostGIS | Faster reads, slightly less accurate (hex boundary) |
| Bloom filter for swiped | False positives → some candidates skipped |
| Cassandra for swipes | Write-heavy, no need for joins |
| Reciprocal check in swipe path | Synchronous match detection vs async with delay |
| ELO async update | User sees ELO delta with 5-10s lag |
| Premium boost via score mult | Simple but coarse — could be more nuanced |

---

## 16. Follow-up questions

- **"How would you A/B test the ranking algorithm?"** → Cohort users into buckets, expose to different scoring weights, measure: matches per day, messages exchanged, retention.
- **"How to prevent fake profiles?"** → Photo verification (selfie with required pose), SMS verification, ML-based duplicate detection.
- **"What if user shows up in multiple cities frequently?"** → Travel mode: pick city, profile boosted there, geo cells updated.
- **"How to scale globally?"** → Region-pinned data (GDPR), CDN-edge swipe API, multi-region replication for chat.
- **"How to detect catfishing?"** → Photo verification, social signals (Instagram link, mutual friends).
