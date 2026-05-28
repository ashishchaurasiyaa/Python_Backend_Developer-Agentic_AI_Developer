# Design Search Engine (Google-Scale)

---

## 1. Requirements

### Functional
- Crawl billions of web pages.
- Index pages: keywords, structure, links.
- Serve search queries: return ranked results.
- Support filters (date, site, language).
- Snippets in results.
- Image / video / news vertical search.
- Autocomplete suggestions.
- Spell correction.

### Non-Functional
- 100B+ pages indexed.
- 5B queries/day → ~60K/sec avg, peak 200K/sec.
- Query latency p99 < 500ms.
- Crawl freshness: news within minutes; long-tail within days.
- 99.99% availability.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Total pages | 100B |
| Avg page size | 100KB compressed |
| Storage raw | 100B × 100KB = 10 PB |
| Index size | ~3PB (compressed inverted index) |
| Daily queries | 5B → 60K/sec avg |
| Peak QPS | 200K |
| Crawl rate | 1B pages/day (~12K/sec) |
| Crawl bandwidth | 12K × 100KB = 1.2 GB/sec |

Numbers are estimates; Google is much larger.

---

## 3. Three Main Subsystems

```
   ┌──────────────────────────────┐
   │       1. CRAWLER             │  (fetches web pages)
   └─────────────┬────────────────┘
                 │
                 ▼
   ┌──────────────────────────────┐
   │       2. INDEXER             │  (builds searchable index)
   └─────────────┬────────────────┘
                 │
                 ▼
   ┌──────────────────────────────┐
   │       3. QUERY ENGINE        │  (serves search requests)
   └──────────────────────────────┘
```

---

## 4. Crawler Architecture

```
   Seed URLs
       │
       ▼
   ┌─────────────────┐
   │   URL Frontier  │ ← prioritized queue (PageRank, freshness)
   └────────┬────────┘
            │
   ┌────────▼────────┐    ┌──────────────┐
   │   Fetchers      │ ←→ │ DNS Resolver │
   │   (1000s)       │    └──────────────┘
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │   Page Parser   │ → extracts links, text, metadata
   └────────┬────────┘
            │
   ┌────────▼────────┐
   │   URL Filter    │ → dedupe, respect robots.txt
   └────────┬────────┘
            │
   ┌────────▼────────┐
   │   Storage       │ → S3/HDFS for raw pages
   └─────────────────┘
            │
            ▼
   ┌─────────────────┐
   │   Indexer       │
   └─────────────────┘
```

### URL Frontier
- Priority queue of URLs to crawl.
- Priority = PageRank × freshness factor × type (news > blog).
- Per-domain rate limit (politeness).
- Distributed across many machines.

### Politeness
- Respect `robots.txt`.
- Don't hammer a single domain (e.g., max 1 req/sec per IP).
- Honor `Crawl-Delay` directive.
- Use `If-Modified-Since` to avoid re-crawling unchanged.

### Fetcher
- Async HTTP fetchers (1000s of concurrent connections).
- Handle redirects, retries, timeouts.
- Detect language, encoding.
- Strip boilerplate (nav, footer).

### Deduplication
- URL canonicalization (`http://X` == `https://X` == `http://X/`).
- Content hash (same content from different URLs).
- Bloom filter for "seen this URL".

### Storage
- Raw HTML in S3 / HDFS / Google's GFS.
- Compressed (gzip): 10x reduction.
- Sharded by URL hash.

---

## 5. Indexer

### Inverted Index
For each term: list of document IDs containing it.

```
"python" → [doc_1, doc_5, doc_42, doc_100, ...]
"tutorial" → [doc_5, doc_50, doc_100, ...]
```

Query "python tutorial" → intersect the two lists.

### Index entries (with position)
For phrase / proximity queries:
```
"python" → [(doc_1, [3, 47, 92]), (doc_5, [12, 35]), ...]
```
Positions = where in the document each occurrence is.

### Index per term: posting list
```
posting_list("python"):
  - doc_id, term_freq, positions
  - ...
```

Compressed (delta encoding + variable-byte coding) → 50% size.

### Shard the index
By document range (alphabetical) or by hash. Each shard ~50-100 GB.

For 3 PB index: 30K shards × 100GB = many nodes.

### Index building (Pipeline)
```
Raw page → Parse → Tokenize → Stop-word filter → Stem → Position record →
Shuffle by term → Append to posting list → Compress → Write shard
```

Batch process via MapReduce / Spark.

### Incremental updates
- Fresh pages → immediately add to "live index" (smaller, in-memory).
- Periodic merge of live index into main index.
- Two-level index keeps query consistent.

---

## 6. Query Engine

### Query parsing
```
"how to learn python tutorial"
↓
- Tokenize: [how, to, learn, python, tutorial]
- Remove stop words: [learn, python, tutorial]
- Stem: [learn, python, tutori]
- Spell correct?
- Extract phrases: "learn python"
```

### Query routing
1. Send query to all shards in parallel.
2. Each shard returns top-N results.
3. Aggregator merges; takes overall top-K.

```python
async def query(q, k=10):
    parsed = parse(q)
    tasks = [
        shard.search(parsed, top_n=k * 2)
        for shard in shards
    ]
    results = await asyncio.gather(*tasks)
    merged = heapq.nlargest(k, chain(*results), key=lambda r: r.score)
    return merged
```

For 30K shards: aggregate in tree (root → 10 mid → each fans out to 3K shards).

### Ranking

Scoring formula combines:
- **TF-IDF / BM25**: term frequency × inverse document frequency.
- **PageRank**: importance of page from link graph.
- **Click-through rate**: which result users clicked historically.
- **Freshness**: newer = higher (for news queries).
- **Personalization**: user history.
- **Anchor text**: text in links pointing to this page.
- **Page quality signals**: HTTPS, mobile-friendly, load speed.

```
score = BM25(query, doc)
      × pagerank(doc)
      × click_signal(query, doc)
      × freshness(doc)
      + boost(personalization)
```

### Snippet generation
- Find best matching sentence from doc.
- Highlight query terms.
- Cached pre-computed for popular queries.

---

## 7. PageRank (Simplified)

Algorithm: iteratively compute each page's rank based on incoming links.

```python
PR(A) = (1 - d) + d × sum(PR(T) / C(T) for T in inbound_links_to(A))

# d = damping factor (~0.85)
# C(T) = number of outbound links from T
```

Iterated to convergence. Originally re-computed monthly; modern variants are continuous.

Computed offline via MapReduce on link graph.

### Modern Google
Hundreds of ranking signals; PageRank is one of many. Deep learning models combine.

---

## 8. Caching

### Query cache (most impactful)
Common queries serve from cache:
```
cache_key = (normalized_query, locale, personalization_class)
```

TTL: minutes for news, hours for stable queries.

Cache hit ratio: 30-50%.

### Result cache (per page rank)
Posting lists for hot terms cached in memory.

### Doc cache
Frequently retrieved documents cached.

---

## 9. Autocomplete

User types "how to learn p" → suggestions.

### Implementation
- Trie / radix tree of popular queries.
- Each node stores top-N completions by frequency.

```python
class TrieNode:
    children: dict[str, TrieNode]
    top_suggestions: list[(str, int)]   # (query, count)

trie = Trie()
trie.insert("how to learn python", count=100K)
trie.insert("how to learn programming", count=50K)

# Lookup
node = trie.search_prefix("how to learn")
return node.top_suggestions[:10]
```

For new query phrases: log + aggregate; periodically refresh trie.

---

## 10. Spell Correction

Detect misspellings; suggest "did you mean...?"

### Approaches
- Edit distance to common queries.
- Phonetic matching (Soundex).
- Statistical (n-gram language model).

### Bloom filter for valid words
Quickly reject typos.

### Suggestion ranking
By query frequency (more common = more likely intended).

---

## 11. Vertical Search

Specialized indices:
- Images.
- Videos.
- News (fresh, 24-hour cycle).
- Maps.
- Shopping.
- Academic papers.

Each runs its own crawler + indexer + serving stack.

Top-level query dispatched to verticals; results merged.

---

## 12. Indexes Worth Knowing

### Sharded Inverted Index
Per-term posting lists distributed across machines.

### Latitude-Longitude index (for Maps)
Quadtree / S2 cells.

### Vector index (for semantic search)
HNSW / FAISS for sentence embeddings.

Modern Google combines lexical (BM25) + semantic (vector) retrieval.

---

## 13. Distributed Architecture

```
                  Query
                    │
              ┌─────▼────────┐
              │ Front-end    │  ← receives, parses, caches
              └──────┬───────┘
                     │
              ┌──────▼───────┐
              │ Aggregator   │  ← fans out to shards
              └──┬───┬───┬───┘
                 │   │   │
              ┌──▼┐┌──▼┐┌──▼┐ ...
              │S1 ││S2 ││S3 │   ← shards (each holds part of index)
              └───┘└───┘└───┘
```

Result aggregation in tree to keep latency O(log shards).

---

## 14. Indexing Pipeline (Daily / Realtime)

```
Crawled pages →
  Parse pipeline (extract text, links, metadata) →
  De-duplicate →
  Compute embeddings (for semantic search) →
  Build posting lists →
  PageRank update (batch) →
  Atomic swap of new index version
```

Live index for fresh pages serves alongside main index. Periodically merged.

---

## 15. Storage

### Raw HTML
- Bigtable / HDFS / Cassandra-like store.
- Sharded by URL hash.

### Inverted Index
- Custom optimized format.
- Replicated for redundancy + read scaling.

### Link Graph
- Graph DB or custom.
- ~1 trillion edges.

### Logs
- Query logs (anonymized) → analytics + training.

---

## 16. Anti-Spam

Adversarial environment: SEO spammers try to game rankings.

### Techniques
- **Link farm detection**: clusters of low-quality sites linking to each other.
- **Keyword stuffing detection**: term frequency too high.
- **Cloaking**: site shows different content to crawler vs user.
- **Manual reviews**: flagged sites reviewed by spam team.
- **ML models**: classify "spammy" pages.

PageRank + quality signals naturally devalue spam, but constant arms race.

---

## 17. Personalization

- User location.
- Search history.
- Click patterns.
- Language preference.
- Device type.

Re-ranks results per-user. Some queries highly personalized (e.g., "restaurants near me"), others not (e.g., "Wikipedia").

---

## 18. Result Page

```
[Query: "python tutorial"]

1. Top 10 organic results
2. Sponsored ads (top + side)
3. Knowledge panel ("Python is a programming language...")
4. People also ask (related questions)
5. Videos
6. News
7. Pagination
```

Personalized + featured snippets above results.

---

## 19. Operational Concerns

### Index rotation
Build new index version offline; atomic swap. Old version available for rollback.

### Crawl freshness
Sites monitored at different rates:
- News: minutes.
- Popular sites: hours.
- Long-tail: weeks.

### Bandwidth
1.2 GB/sec crawl → CDN + multiple data centers + peering with ISPs.

### Cost
- Google's index estimated 1-2 EB raw data.
- Tens of thousands of servers worldwide.
- Annual energy cost: hundreds of millions.

---

## 20. Trade-offs

| Decision | Trade-off |
|---|---|
| Shard by term | Easier, but term distribution uneven (Zipf law) |
| Shard by doc | Even, but every query hits every shard |
| In-memory hot index | Fast, expensive RAM |
| BM25 + ML ranking | Strong relevance, complex |
| Full crawl periodically | Fresh, expensive bandwidth |
| Selective re-crawl | Cheaper, slower freshness |

Modern systems: shard by document; index serves entirely from memory.

---

## 21. Follow-up Questions

- **"How does Google handle 'right to be forgotten' (GDPR)?"** → Removal team reviews requests; removes from index; respects via robots.txt directives.
- **"How would you handle a viral story spreading?"** → News index updates faster; query routing temporarily allocates more resources.
- **"How does the crawler avoid spider traps?"** → URL hash dedup, depth limits, per-domain limits, anomaly detection.
- **"What about JavaScript-rendered pages?"** → Headless Chrome (Puppeteer) used for some. Most pages crawled with rendering.
- **"How to add semantic search (vector embeddings)?"** → Index sentence embeddings → ANN search alongside BM25; combine scores.
- **"How does autocomplete update with trending queries?"** → Real-time query log → streaming aggregation → push to trie.
- **"How do you ensure data center failure doesn't kill search?"** → Multi-region replicated indices; DNS/Anycast routes around failures.
- **"Differences from Bing / DuckDuckGo?"** → Different ranking signals, freshness strategies, personalization levels. DuckDuckGo licenses Bing data + adds privacy.
