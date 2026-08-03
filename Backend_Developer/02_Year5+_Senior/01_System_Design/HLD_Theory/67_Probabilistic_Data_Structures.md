# 67 — Probabilistic Data Structures (HyperLogLog, Count-Min Sketch, T-Digest)

---

## What & Why

Family of structures that answer big-data questions in **tiny, fixed memory** by accepting a small, *bounded* error. [Bloom filters](42_Bloom_Filters.md) (doc 42) answer "is X in the set?" — this doc covers the other three interview regulars:

| Structure | Question it answers | Exact-version cost | Sketch cost |
|---|---|---|---|
| **HyperLogLog** | "How many DISTINCT items?" (count-distinct) | O(N) memory (a set) | **~12 KB** for billions, ±0.8% |
| **Count-Min Sketch** | "How many times did X occur?" (frequency / heavy hitters) | O(unique keys) hashmap | few KB, overcounts only |
| **T-Digest** | "What is the p99?" (quantiles over streams) | store every value | ~KB, tight tail accuracy |

The moment an interviewer says *"billions of events, limited memory, approximate is fine"* — the answer is one of these.

---

## HyperLogLog — count distinct

**Intuition:** hash every item; rare patterns imply many distinct items. If the luckiest hash you ever saw has ~20 leading zero bits, you've probably seen ~2²⁰ distinct values. One max is noisy → keep 2^b buckets (first b bits pick the bucket), each remembering *its* max leading-zero run, then take a corrected harmonic mean.

```
add(x):    h = hash(x)
           bucket   = first b bits of h          (e.g. b=14 → 16384 buckets)
           rest     = remaining bits
           M[bucket] = max(M[bucket], leading_zeros(rest) + 1)

estimate:  α · m² / Σ 2^(-M[i])     (harmonic mean + bias correction)

Memory:    16384 buckets × ~6 bits ≈ 12 KB  →  error ≈ 1.04/√m ≈ 0.8%
```

Key properties:
- **Mergeable:** union two HLLs = bucket-wise max → count distinct across shards/days by merging sketches, no raw data movement. This is why analytics pipelines love it.
- **Cannot delete** items; only add and merge.

```python
import redis
r = redis.Redis()
r.pfadd("uv:2026-08-03", "user_1", "user_2")   # PFADD — Redis built-in HLL
r.pfcount("uv:2026-08-03")                     # ≈ distinct count
r.pfmerge("uv:week", "uv:mon", "uv:tue")       # union across days
```

**Classic uses:** daily/monthly unique visitors, distinct IPs per minute (DDoS detection), `COUNT(DISTINCT)` in BigQuery/Presto/Druid (`approx_distinct`).

---

## Count-Min Sketch — frequency of each item

**Intuition:** a Bloom filter that counts. `d` rows × `w` counters; each item hashes to one counter per row and increments it. Collisions only ever **inflate** counts — so read back the **minimum** across rows, the estimate least damaged by collisions.

```
Grid: d rows (one hash each) × w counters

add(x):      for each row i: counter[i][h_i(x) % w] += 1
estimate(x): min over rows of counter[i][h_i(x) % w]

Guarantee: never undercounts; overcounts by ≤ εN with probability 1-δ
           (w = e/ε, d = ln(1/δ) — e.g. 2000×5 ints ≈ 40 KB for 0.1% of N)
```

```python
import mmh3, math

class CountMinSketch:
    def __init__(self, width: int = 2000, depth: int = 5):
        self.w, self.d = width, depth
        self.grid = [[0] * width for _ in range(depth)]

    def add(self, item: str, count: int = 1):
        for i in range(self.d):
            self.grid[i][mmh3.hash(item, seed=i) % self.w] += count

    def estimate(self, item: str) -> int:
        return min(self.grid[i][mmh3.hash(item, seed=i) % self.w]
                   for i in range(self.d))
```

**Heavy hitters / top-k pattern (the interview combo):** stream events → CMS for frequencies + a small min-heap of the current top-k. New event: bump CMS, compare estimate against heap-min, swap in if bigger. Memory stays KBs for "top 10 trending hashtags", "top talkers by IP", "most-played songs this hour".

**Rate limiting connection:** CMS can approximate per-key request counts when tracking millions of keys exactly is too expensive — coarse first-pass filter before an exact limiter.

---

## T-Digest — percentiles over streams

Averages lie; SLOs are defined on **p95/p99** ([30_SLA_SLO_SLI](30_SLA_SLO_SLI.md)). Exact percentiles need every sample. T-digest keeps a few hundred **centroids** (mean, count), deliberately sized *smaller near the tails* — so p50 is good and p99/p999 are excellent, in ~KB.

Two properties interviewers care about:
- **Mergeable:** each app server keeps a local digest, ships it every 10s, aggregator merges → true global p99 (you *cannot* average per-server p99s — that's a classic wrong answer).
- Powers `histogram_quantile`-style backends: Prometheus native histograms, Elasticsearch percentiles agg, Datadog distributions all use t-digest or a cousin (HDRHistogram).

---

## Choosing the right sketch (cheat table)

| Question in the problem | Reach for |
|---|---|
| "Have we seen this before?" (membership) | Bloom filter (doc 42) |
| "How many uniques?" | HyperLogLog |
| "How often did X appear?" / "top-k trending" | Count-Min Sketch (+ heap) |
| "What's the p99 latency?" | T-digest / HDRHistogram |
| Need exact answers / deletes / small N | Just use a set/hashmap — don't sketch what fits in memory |

Shared superpowers: **fixed tiny memory, one-pass streaming, mergeable across shards**. Shared cost: approximate, and most can't delete.

---

## Interview Q&A

**Q: Count unique daily visitors across 1B events with 100 MB of RAM total?**
A: HyperLogLog — ~12 KB per day for <1% error. Per-shard HLLs merge losslessly (bucket-wise max), so distributed counting = merge sketches, and weekly/monthly uniques = merge daily sketches. An exact set would need tens of GB.

**Q: Why does Count-Min Sketch take the MINIMUM across rows?**
A: Collisions only add, never subtract — every counter is (true count + collision noise) ≥ true count. Each row is an independent overestimate, so the minimum is the tightest bound available. That's also why CMS never undercounts.

**Q: Why can't you average per-server p99s to get global p99?**
A: Percentiles aren't linear — a server with 10 req/s and one with 10K req/s contribute equally to the average but not to reality; the tail may live entirely on one box. Correct approach: merge mergeable digests (t-digest/HDRHistogram) or aggregate raw histogram buckets, then compute the quantile once, globally.

**Q: Twitter trending hashtags — exact hashmap or CMS?**
A: CMS + min-heap. Hashtag cardinality is unbounded (millions of uniques/hour), and trending only needs the top ~50 with roughly-right counts — a hashmap grows without limit, CMS stays at a few hundred KB per time window and windows can be merged/expired cheaply.

---

## Related
- [42_Bloom_Filters](42_Bloom_Filters.md) — the membership member of this family
- [30_SLA_SLO_SLI](30_SLA_SLO_SLI.md) — why p99, not average
- [41_Data_Pipelines_Streaming](41_Data_Pipelines_Streaming.md) — where sketches live in the pipeline
- [Design_Gaming_Leaderboard](../HLD_Problems/Design_Gaming_Leaderboard.md) — approximate ranks at extreme scale
- [Design_Real_Time_Analytics](../HLD_Problems/Design_Real_Time_Analytics.md) — uniques/top-k in a real design
