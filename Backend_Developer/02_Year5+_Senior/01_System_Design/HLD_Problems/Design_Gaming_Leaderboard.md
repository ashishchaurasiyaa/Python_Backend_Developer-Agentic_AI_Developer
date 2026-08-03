# Design Real-Time Gaming Leaderboard — HLD

## WHAT

A leaderboard ranks millions of players by score and answers three queries in real time: **top-N players**, **my rank**, and **players around me**. The interesting part: naive SQL (`ORDER BY score`, `COUNT(*) WHERE score > x`) collapses at scale, so the design is really about choosing the right data structure — Redis **sorted sets** — and handling what they can't do.

**Examples:** PUBG/BGMI season ranks, Duolingo leagues, LeetCode contest ranking, Strava segments

---

## Requirements

### Functional
- UpdateScore(player_id, delta) on every match end
- GetTopN(n) — global top 10/100
- GetRank(player_id) — my exact rank
- GetAround(player_id, k) — k players above/below me (relative leaderboard)
- Monthly seasons: leaderboard resets, old ones archived

### Non-Functional
- 25M DAU, 50M score updates/day (~600/sec avg, 10x peak ≈ 6K/sec)
- Rank queries: 5x update volume (every match-end screen shows rank)
- P99 read < 50ms — rank must feel instant
- Rank accuracy: exact (not approximate) for this scale

---

## Back-of-Envelope

```
Players/season:  25M entries
Redis ZSET member: ~8B score + ~16B id + overhead ≈ 100B/player
Memory:          25M × 100B ≈ 2.5 GB → fits in ONE Redis node easily
Updates:         6K/sec peak — ZINCRBY is O(log N) ≈ 25 comparisons → trivial
Reads:           30K/sec peak — ZRANK/ZREVRANGE also O(log N) → one node handles it

Conclusion to state explicitly: a single Redis instance (+replica) is
ENOUGH for 25M players. Don't over-engineer — sharding is the extension,
not the baseline.
```

---

## Architecture

```
 Match Service ──► score event ──► Kafka ──► Leaderboard Service
                                                   │
                                     ┌─────────────┼──────────────┐
                                     ▼             ▼              ▼
                               Redis ZSET     PostgreSQL     Season Archiver
                               (live ranks)   (source of      (old seasons →
                               + replica       truth, audit)    S3/cold table)
                                     ▲
                 GetTopN/GetRank ────┘
                 (API reads hit Redis only)
```

Two stores, two jobs: **Redis ZSET = ranking math**, **Postgres = durable source of truth** (score history, anti-cheat audits, rebuild-Redis-on-loss). Updates go through a queue so a Redis hiccup never drops scores.

---

## Core Concepts

### 1. Redis Sorted Set — the whole game

```python
import redis
r = redis.Redis()
KEY = "lb:season:2026-08"

def update_score(player_id: str, delta: int):
    r.zincrby(KEY, delta, player_id)              # O(log N)

def top_n(n: int = 10):
    return r.zrevrange(KEY, 0, n - 1, withscores=True)   # O(log N + n)

def my_rank(player_id: str) -> int:
    rank = r.zrevrank(KEY, player_id)             # O(log N), 0-based
    return rank + 1 if rank is not None else -1

def around_me(player_id: str, k: int = 5):
    rank = r.zrevrank(KEY, player_id)
    lo, hi = max(rank - k, 0), rank + k
    return r.zrevrange(KEY, lo, hi, withscores=True)
```

Why ZSET wins (the core interview point):

| | SQL `ORDER BY` / `COUNT(*)` | Redis ZSET |
|---|---|---|
| Get rank | O(N) scan or heavy index gymnastics | O(log N) — skip list + hash |
| Top N | O(N log N) sort (or index scan) | O(log N + n) |
| Update | cheap write, but rank reads stay slow | O(log N), rank instantly correct |
| Under the hood | B-tree not built for "position of row" | **skip list** stores rank info in span counts |

### 2. Tie-breaking — same score, who's higher?

ZSET orders equal scores lexically by member — usually wrong (you want "reached it first" to win). Standard trick: pack score + inverted timestamp into the float:

```python
MAX_TS = 10**10
def composite(score: int, ts: int) -> float:
    return score * MAX_TS + (MAX_TS - ts)   # earlier ts → larger composite → higher rank
```

Caveat worth saying: ZSET scores are IEEE 754 doubles — 53 bits of integer precision. If score×10^10 overflows that, keep the real score in the top bits and accept coarser timestamps, or do tie-breaks app-side.

### 3. Seasons, resets, archiving

```
Season key per month: lb:season:2026-08
Reset = just start writing to lb:season:2026-09  (old key untouched)
Archive job: ZSCAN old key → bulk insert final ranks into Postgres → EXPIRE old key
```

No "big reset" operation, no downtime, old seasons queryable forever from SQL.

### 4. Extension: what if 25M → 2B players (or 1M writes/sec)?

Now shard — **by score range**, not by player hash:

```
Shard 1: scores 0–999        Shard 2: 1000–1999       Shard 3: 2000+

GetRank(player):  find player's shard by score →
                  rank = ZREVRANK within shard + Σ ZCARD of all higher shards
Top-10:           only ask the top shard
Rebalance:        ranges drift as scores inflate → periodic re-split job
```

Hash-sharding is the trap answer: rank would need querying **every** shard and merging. Score-range sharding keeps rank = local rank + counts of higher shards (ZCARD is O(1)).

For **billions** with approximate ranks being acceptable: keep exact ZSET for top ~1M only, bucket the long tail into score histograms → rank ≈ sum of higher buckets (cheap, off by <1 bucket).

---

## Bottlenecks & Scaling

| Problem | Fix |
|---|---|
| Redis node dies | Replica + AOF; rebuild from Postgres via replay if both lost |
| Hot key (single ZSET, all traffic) | Read replicas for GetTopN (cache 1s), writes stay on primary |
| Top-10 hammered by every client | Cache the top-10 payload (1s TTL) — it barely changes; the "celebrity read" of this problem |
| Cheaters posting fake scores | Server-authoritative scoring only (never trust client), anomaly detection on score deltas, audit trail in Postgres |
| Cross-region latency | Regional leaderboards natively; global = async merge job (global rank tolerates staleness) |

---

## Interview Q&A

**Q: Why not just `SELECT COUNT(*) FROM scores WHERE score > my_score` for rank?**
A: That's an O(N) scan per rank query (index helps but it's still a range count — Postgres walks the index counting entries). At 30K rank-reads/sec over 25M rows the DB dies. A skip-list-backed sorted set maintains rank positional info structurally, making rank O(log N) — this is a data-structure-selection problem, not a tuning problem.

**Q: How does Redis get ZRANK in O(log N)?**
A: ZSET = hash (member → score lookup, O(1)) + skip list ordered by score. Each skip-list node stores the **span** (how many nodes a forward pointer jumps over); summing spans while descending gives the rank without walking every node.

**Q: Redis dies — did we lose the leaderboard?**
A: No — Redis here is a derived view, not the source of truth. Scores flow through Kafka into Postgres; recovery = replay/rebuild the ZSET from Postgres. Interviewers specifically probe whether you put your only copy of the data in Redis.

**Q: Design changes for a Duolingo-style league (groups of 30) vs global?**
A: Thousands of tiny independent ZSETs (one per league) instead of one giant one — trivially shardable by league id, no rank-merge problem at all. Recognizing when the problem decomposes into many small leaderboards is a big signal.

---

## Related
- Redis data structures + caching patterns → [13_Caching_Complete](../HLD_Theory/13_Caching_Complete.md)
- Approximate rank at extreme scale → [67_Probabilistic_Data_Structures](../HLD_Theory/67_Probabilistic_Data_Structures.md)
- LRU/LFU + Redis internals → [`08_Redis/`](../../../00_Year0-2_Junior/08_Redis/)
- Real-time analytics pipeline (same ingest shape) → [Design_Real_Time_Analytics](Design_Real_Time_Analytics.md)
