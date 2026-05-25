# Elasticsearch Relevance Tuning (BM25, Function Score, Hybrid)

## Why It Matters

Default ES search = "OK" results. Tuned ES = relevant results. Senior backend role expectations:
- **Understand BM25** — default scoring, parameter tuning
- **Boost/decay** — domain-specific ranking
- **Hybrid search** — BM25 + vector (RRF) for AI-era search
- **Debug relevance** — explain API
- **Synonyms, analyzers** — recall improvements

Senior interview: "Search results irrelevant — how do you debug + improve?" → explain API, analyzer inspect, function_score tuning.

---

## Core Concepts

### BM25 (Default Similarity)

```
score = Σ IDF(t) * (tf(t,d) * (k1+1)) / (tf(t,d) + k1 * (1 - b + b * |d|/avg_dl))
```

- `IDF(t)` = inverse document frequency (rare terms boosted)
- `tf(t,d)` = term frequency in doc
- `k1` (default 1.2) = term frequency saturation
- `b` (default 0.75) = length normalization

### Tune k1, b

```json
PUT my-index
{
  "settings": {
    "index": {
      "similarity": {
        "custom_bm25": {
          "type": "BM25",
          "k1": 1.5,
          "b": 0.5
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "similarity": "custom_bm25"
      }
    }
  }
}
```

- Increase `k1` (1.5–2.0) for verbose content (term repetition more valued)
- Lower `b` (0.5) if longer docs shouldn't be penalized

### Function Score Query

Boost by field value + decay by time:

```json
{
  "query": {
    "function_score": {
      "query": { "match": { "title": "python" } },
      "functions": [
        {
          "filter": { "term": { "is_promoted": true } },
          "weight": 2.0
        },
        {
          "field_value_factor": {
            "field": "popularity",
            "modifier": "log1p",
            "factor": 0.1
          }
        },
        {
          "gauss": {
            "published_at": {
              "origin": "now",
              "scale": "10d",
              "decay": 0.5
            }
          }
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  }
}
```

**Decay functions:**
- `linear` — decreases linearly
- `exp` — exponential decay (fast falloff)
- `gauss` — gaussian (smooth, peak preserved)

### Boosting Query (Negative Boost)

Demote certain matches without excluding:

```json
{
  "query": {
    "boosting": {
      "positive": { "match": { "title": "python" } },
      "negative": { "term": { "category": "deprecated" } },
      "negative_boost": 0.2
    }
  }
}
```

### Script Score (Custom Math)

```json
{
  "query": {
    "script_score": {
      "query": { "match": { "title": "X" } },
      "script": {
        "source": "_score * doc['views'].value / (1 + doc['age_days'].value)"
      }
    }
  }
}
```

Slower than `function_score` — use sparingly.

### Rescore Phase

First-pass cheap query → rescore top N with expensive query:

```json
{
  "query": { "match": { "title": "python" } },
  "rescore": {
    "window_size": 100,
    "query": {
      "rescore_query": {
        "match_phrase": { "title": "python tutorial" }
      },
      "query_weight": 0.7,
      "rescore_query_weight": 1.5
    }
  }
}
```

Top 100 from match get phrase boost. Saves cost of full phrase match.

### Explain API (Debug Relevance)

```http
GET my-index/_explain/1
{
  "query": { "match": { "title": "python" } }
}
```

Returns breakdown — which terms matched, what BM25 score each contributed. Critical for debugging "why is this doc ranked higher?".

### Analyzers (Recall Improvements)

```json
PUT my-index
{
  "settings": {
    "analysis": {
      "analyzer": {
        "my_english": {
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "porter_stem", "asciifolding"]
        }
      },
      "filter": {
        "my_synonyms": {
          "type": "synonym",
          "synonyms": ["car, auto, automobile", "ml, machine learning"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "my_english"
      }
    }
  }
}
```

### Multi-Field with Different Analyzers

```json
"title": {
  "type": "text",
  "analyzer": "english",
  "fields": {
    "raw": { "type": "keyword" },
    "shingle": { "type": "text", "analyzer": "shingle_analyzer" }
  }
}
```

Query `title` for normal search, `title.shingle` for phrase-aware boost.

### Hybrid Search (BM25 + Vector via RRF)

```json
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": { "match": { "body": "machine learning" } }
          }
        },
        {
          "knn": {
            "field": "body_embedding",
            "query_vector": [...],
            "k": 50,
            "num_candidates": 200
          }
        }
      ],
      "rank_window_size": 100,
      "rank_constant": 60
    }
  }
}
```

RRF (Reciprocal Rank Fusion) combines BM25 + vector rankings without manual tuning. ES 8.8+.

---

## How It Works Internally

### Inverted Index

```
"python" → [doc1:tf=3, doc5:tf=1, doc12:tf=2]
"tutorial" → [doc1:tf=2, doc3:tf=5]
```

Term lookup O(1), scoring via BM25 formula per doc.

### Sharding + Scoring

Score computed per shard, then top-K aggregated at coordinator. Statistics (IDF) per shard differ slightly → potential ranking inconsistency. Use `dfs_query_then_fetch` search type for accurate scoring across shards.

### Cache

Filter clauses cached in bitset (filter cache). Match queries not cached. Use `bool: filter` for non-scoring conditions.

---

## Common Pitfalls

### 1. Using match for Exact Match

```json
{ "match": { "id": "user_1" } }  // tokenizes → potential mismatch
```

For exact, use `term`:

```json
{ "term": { "id.keyword": "user_1" } }
```

### 2. Stopwords Wrongly Filtered

Default English analyzer removes "the", "is", etc. "to be or not to be" → all stopwords → 0 match.

Use custom analyzer without stopword filter for short queries.

### 3. Token Mismatch (Analyzer Differences)

Index-time analyzer differs from query-time → no match. Always test:

```http
GET my-index/_analyze
{
  "analyzer": "my_english",
  "text": "Running"
}
```

### 4. boost in Mapping vs Query

```json
// Mapping boost (deprecated, doesn't work as expected)
"title": { "type": "text", "boost": 2.0 }
```

Use query-time boost instead.

### 5. Synonyms at Wrong Time

```json
// Index-time synonyms: expand to all in stored term vector → bigger index
// Query-time synonyms: expanded on query → flexible but recompute each time
```

Use query-time for evolving synonyms; index-time for static.

### 6. Length Normalization Penalizes Long Docs

Default `b=0.75` heavily penalizes length. For knowledge bases with long articles, lower `b`.

---

## Interview Q&A

**Q1:** BM25 vs TF-IDF?
**A:** BM25 = improved TF-IDF. Better term frequency saturation (k1) — repeating term 100 times not 100x as valuable. Length normalization (b) — long docs not falsely favored. Default in ES since 5.0. Better recall + precision than classic TF-IDF.

**Q2:** Relevance debug kaise karoge?
**A:** `_explain` API on specific doc + query → score breakdown per term. `_analyze` API for analyzer output. Profile API (`"profile": true` in search) for query plan + timing. Compare with known good results — what scoring changes needed?

**Q3:** Function score query use kab?
**A:** Domain-specific ranking: recency boost (gauss decay on date), popularity boost (field_value_factor on views), promoted items boost. Apply on top of BM25. Use `boost_mode: multiply` to scale, `replace` to override.

**Q4:** Synonyms — index-time vs query-time?
**A:** Index-time: synonyms expanded when storing → bigger index, faster query, can't update without reindex. Query-time: expanded at search → smaller index, slightly slower, can update synonyms dynamically. Production: query-time for evolving lists, both for production-tested static lists.

**Q5:** Hybrid search BM25 + Vector kaise combine karoge?
**A:** RRF (Reciprocal Rank Fusion) — combines rankings without score normalization issues. `score_rrf(d) = Σ 1 / (rank_in_retriever_i + k)`. ES 8.8+ has built-in RRF retriever. Or weighted sum: `final = α * bm25_score + (1-α) * cosine_similarity` (requires score normalization).

**Q6:** Rescore phase kab use?
**A:** Expensive scoring on subset of results. First pass: cheap match query, returns top N (e.g., 1000). Rescore: phrase match or function score on those N. Saves compute vs scoring entire index with expensive query. Common: first pass term match, rescore with phrase relevance.

**Q7:** Boost-by-recency implementation?
**A:** `function_score` with `gauss` decay on date field. `origin: "now", scale: "30d"` → docs from now scored 1.0, decreasing by 30 days. `decay: 0.5` controls dropoff. Combine with `boost_mode: multiply` so old relevant content still surfaces.

**Q8:** Analyzer chain example?
**A:** `Standard tokenizer` (split on whitespace) → `lowercase` → `asciifolding` (é → e) → `synonym filter` → `stop` (remove "the", "a") → `porter_stem` (running → run). Match index + search analyzer for predictable results.

---

## Real-World Use Cases

### 1. E-commerce Product Search

```json
{
  "query": {
    "function_score": {
      "query": { "multi_match": { "query": "wireless headphones", "fields": ["title^3", "description"] }},
      "functions": [
        { "field_value_factor": { "field": "popularity", "modifier": "log1p" }},
        { "gauss": { "released_at": { "origin": "now", "scale": "180d", "decay": 0.7 }}}
      ],
      "boost_mode": "multiply"
    }
  }
}
```

### 2. Knowledge Base RAG (Hybrid)

BM25 + vector embedding via RRF — best of keyword + semantic.

### 3. Personalized Ranking

```json
"functions": [
  { "filter": { "term": { "category": user_preferred_category }}, "weight": 2.0 }
]
```

---

## References

- [ES Relevance Tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/scoring-theory.html)
- [Function Score](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html)
- [RRF Retriever](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
- Doug Turnbull's "Relevant Search" book
