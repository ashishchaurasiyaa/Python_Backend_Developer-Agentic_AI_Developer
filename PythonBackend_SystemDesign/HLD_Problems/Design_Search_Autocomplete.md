# Design Search Autocomplete (Typeahead) — HLD

## Requirements

### Functional
- As user types, show top-5 suggestions in <100ms
- Suggestions are ranked by popularity (search frequency)
- Support prefix matching: "py" → ["python", "python tutorial", "pytest"]
- Update rankings based on recent search trends (near real-time)
- Case-insensitive matching

### Non-Functional
- 10 billion searches/day (like Google)
- Response in <100ms (P99)
- 99.9% availability
- Data freshness: suggestions updated hourly

---

## Back-of-Envelope

```
Daily searches:    10B / day
QPS:               10B / 86,400 = 115,000/sec
With autocomplete: Each character typed = 1 request
  avg query = 5 chars → 115,000 × 5 = 575,000 autocomplete req/sec

Storage:
  Distinct search terms: ~20 billion unique (like Google)
  Per term: query(avg 30 chars) + count(8B) = 38 bytes
  Total: 20B × 38B = 760 GB → fits in memory cluster
```

---

## Architecture

```
                     ┌──────────────────┐
User types "py..."   │   API Gateway /  │
─────────────────►   │  Load Balancer   │
                     └────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │  Autocomplete     │
                     │  Service          │
                     │  (reads Redis)    │
                     └─────────┬─────────┘
                               │ <100ms
                     ┌─────────▼─────────┐
                     │  Redis Cluster    │
                     │  (Trie in Redis   │
                     │   or Sorted Sets) │
                     └─────────┬─────────┘
                               │ hourly sync
                     ┌─────────▼─────────┐
                     │  Data Aggregation │
                     │  Service          │
                     │  (Kafka + Spark)  │
                     └─────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │  Search Log Store │
                     │  (Cassandra/S3)   │
                     └───────────────────┘
```

---

## Data Structure Options

### Option 1 — Trie (Classical)

```python
from collections import defaultdict

class TrieNode:
    def __init__(self):
        self.children  = {}
        self.is_end    = False
        self.frequency = 0
        self.top_k: list[tuple] = []  # (score, query) pre-cached

class Trie:
    def __init__(self, k: int = 5):
        self.root = TrieNode()
        self.k    = k
    
    def insert(self, query: str, frequency: int):
        node = self.root
        for char in query.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end    = True
        node.frequency = frequency
    
    def search_prefix(self, prefix: str) -> list[str]:
        """Return top-k suggestions for prefix."""
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        
        # DFS to collect all completions
        results = []
        self._dfs(node, prefix, results)
        results.sort(key=lambda x: -x[0])
        return [q for _, q in results[:self.k]]
    
    def _dfs(self, node: TrieNode, prefix: str, results: list):
        if node.is_end:
            results.append((node.frequency, prefix))
        for char, child in node.children.items():
            self._dfs(child, prefix + char, results)

# Demo
trie = Trie(k=5)
for query, freq in [
    ("python", 95000), ("python tutorial", 80000),
    ("python flask", 60000), ("pytest", 45000),
    ("pandas", 70000), ("pytorch", 55000),
]:
    trie.insert(query, freq)

print(trie.search_prefix("py"))
# ['python', 'python tutorial', 'python flask', 'pytorch', 'pytest']
```

### Option 2 — Redis Sorted Sets (Production Choice)

```python
import redis
r = redis.Redis()

# For prefix "py":
# Key: "autocomplete:py" → sorted set of completions by score

def update_search_term(query: str, score: float):
    """Add/update a search term with its score."""
    # Add to all prefix keys
    for i in range(1, len(query) + 1):
        prefix = query[:i].lower()
        r.zadd(f"ac:{prefix}", {query: score})
        r.zremrangebyrank(f"ac:{prefix}", 0, -101)  # keep top 100

def get_suggestions(prefix: str, k: int = 5) -> list[str]:
    """Get top-k suggestions for a prefix."""
    results = r.zrevrange(f"ac:{prefix.lower()}", 0, k - 1)
    return [r.decode() for r in results]


# Bulk load top queries
def bulk_load_queries(queries: list[tuple[str, float]]):
    """Load (query, frequency) pairs into Redis."""
    pipe = r.pipeline()
    for query, freq in queries:
        for i in range(1, len(query) + 1):
            prefix = query[:i].lower()
            pipe.zadd(f"ac:{prefix}", {query: freq})
    pipe.execute()

# Demo
queries = [
    ("python tutorial",  95000),
    ("python flask",     80000),
    ("python pandas",    75000),
    ("pytorch",          70000),
    ("pytest fixtures",  45000),
]
bulk_load_queries(queries)
print(get_suggestions("pyt"))   # ['python tutorial', 'python flask', ...]
```

---

## Search Frequency Aggregation Pipeline

```python
# Kafka consumer: aggregate search logs hourly
# Raw event: {"query": "python tutorial", "timestamp": "...", "user_id": "..."}

from collections import Counter
import asyncio

class SearchAggregator:
    def __init__(self):
        self.window_counts: Counter = Counter()
    
    async def process_event(self, event: dict):
        query = event["query"].lower().strip()
        if len(query) >= 2:  # minimum 2 chars
            self.window_counts[query] += 1
    
    async def flush_to_redis(self):
        """Called every 60 minutes — update Redis with new counts."""
        top_queries = self.window_counts.most_common(1_000_000)
        
        # Decay old scores: new_score = 0.7 * old_score + 0.3 * new_count
        pipe = r.pipeline()
        for query, new_count in top_queries:
            old_score = float(r.zscore("global_queries", query) or 0)
            new_score = 0.7 * old_score + 0.3 * new_count
            
            # Update all prefix keys
            for i in range(1, len(query) + 1):
                prefix = query[:i]
                pipe.zadd(f"ac:{prefix}", {query: new_score})
        
        pipe.execute()
        self.window_counts.clear()
        print(f"Flushed {len(top_queries)} queries to Redis")
```

---

## API Design

```python
from fastapi import FastAPI, Query
app = FastAPI()

@app.get("/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(5, ge=1, le=10),
) -> dict:
    """Return search suggestions for prefix q."""
    suggestions = get_suggestions(q.strip(), k=limit)
    return {
        "query":    q,
        "results":  suggestions,
        "count":    len(suggestions),
    }
```

---

## Trie vs Redis Sorted Sets

| | Trie | Redis Sorted Sets |
|---|---|---|
| Memory | Efficient for sparse data | Simpler, O(prefix_length × alphabet) |
| Speed | O(prefix) traversal | O(log N) per prefix key |
| Distribution | Hard to shard | Redis Cluster shards by key |
| Updates | Complex tree rebalance | Simple ZADD |
| Production fit | Custom impl needed | Ready to use |

**Production recommendation:** Redis Sorted Sets for simplicity + Redis Cluster for scale.

---

## Optimizations

```
1. Client-side cache:
   Cache results per prefix in browser (last 30 sec)
   "pyth" result cached → don't hit server for same prefix

2. CDN cache:
   Autocomplete responses for common prefixes (top 10k)
   Cache-Control: max-age=60

3. Trie optimization:
   Pre-compute top-k at each node → O(1) lookup
   (instead of DFS every time)

4. Language/locale:
   Separate tries/sorted sets per language
   "de" prefix → German completions
```

---

## Interview Talking Points

1. **How do you handle the "space" character?**  
   Include space in trie/prefix. "python tu" → "python tutorial". Store queries with spaces normally.

2. **How do you handle trending queries?**  
   Recency-weighted scoring: score = Σ(count_in_window × time_decay). Recent searches weighted more. Update hourly with exponential decay.

3. **How do you scale to 575k req/sec autocomplete?**  
   - Redis Cluster (shard by prefix key)
   - CDN caches top-N prefixes (most "py" lookups hit CDN)
   - Horizontal scaling of autocomplete API servers

4. **What is the memory usage for storing all prefixes?**  
   For query "python" (6 chars): stores in ac:p, ac:py, ac:pyt, ac:pyth, ac:pytho, ac:python = 6 keys. Each key stores up to 100 completions × ~30 bytes = 3KB per prefix. Top 10M distinct prefixes × 3KB = 30GB → Redis Cluster.
