# PostgreSQL Full-Text Search

> **Interview angle:** "Elasticsearch zaroori hai search ke liye?" — No. Postgres FTS handles ~80% cases.

---

## 1. When Postgres FTS Is Enough

| Scale | Use |
|---|---|
| < 10M docs, basic search | **Postgres FTS** (built-in, free) |
| Complex queries, scoring, faceting | Elasticsearch |
| Massive scale, real-time | Elasticsearch |
| Already have Postgres + search a side feature | Postgres FTS |

**Reality:** Most apps don't need Elasticsearch.

---

## 2. Core Concepts

### `tsvector` — Document representation
Document → tokenized + stemmed + normalized:
```sql
SELECT to_tsvector('english', 'The quick brown fox jumps over the lazy dog');
-- Result: 'brown':3 'dog':9 'fox':4 'jump':5 'lazi':8 'quick':2

-- Stopwords removed: 'the', 'over'
-- Stemmed: jumps → jump, lazy → lazi
-- Positions tracked: brown is word 3
```

### `tsquery` — Search query
```sql
SELECT to_tsquery('english', 'quick & brown');
-- Result: 'quick' & 'brown'

SELECT to_tsquery('english', 'jumping | running');
-- Result: 'jump' | 'run'
```

### Match operator: `@@`
```sql
SELECT
    to_tsvector('english', 'The quick brown fox') @@
    to_tsquery('english', 'fox');
-- Result: true
```

---

## 3. Schema Setup

```sql
CREATE TABLE articles (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[],
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast search
CREATE INDEX idx_articles_search ON articles USING GIN (search_vector);

-- Auto-update search_vector on insert/update
CREATE OR REPLACE FUNCTION articles_search_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.body, '')), 'B') ||
        setweight(to_tsvector('english', array_to_string(NEW.tags, ' ')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER articles_search_trigger
    BEFORE INSERT OR UPDATE OF title, body, tags
    ON articles FOR EACH ROW
    EXECUTE FUNCTION articles_search_update();
```

### Generated column alternative (Postgres 12+)
```sql
ALTER TABLE articles
    ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(body, '')), 'B')
    ) STORED;
```

---

## 4. Basic Queries

```sql
-- AND search
SELECT * FROM articles
WHERE search_vector @@ to_tsquery('english', 'python & django');

-- OR search
SELECT * FROM articles
WHERE search_vector @@ to_tsquery('english', 'python | ruby');

-- NOT search
SELECT * FROM articles
WHERE search_vector @@ to_tsquery('english', 'python & !rails');

-- Phrase search (Postgres 9.6+)
SELECT * FROM articles
WHERE search_vector @@ phraseto_tsquery('english', 'machine learning');

-- Prefix search
SELECT * FROM articles
WHERE search_vector @@ to_tsquery('english', 'python:*');
-- Matches: pythonic, pythonista
```

---

## 5. Ranking (Relevance Scoring)

```sql
-- ts_rank: relevance score
SELECT
    title,
    ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'python & web') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;

-- ts_rank_cd: cover-density ranking (considers proximity)
SELECT
    title,
    ts_rank_cd(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'python web') query
WHERE search_vector @@ query
ORDER BY rank DESC;
```

### Weight system
```sql
-- Title (A) weighs more than body (B)
setweight(to_tsvector('english', title), 'A') ||
setweight(to_tsvector('english', body),  'B')

-- Default weights: {A=1.0, B=0.4, C=0.2, D=0.1}
-- Custom weights:
ts_rank('{0.1, 0.2, 0.4, 1.0}', search_vector, query)
```

---

## 6. Highlighting Results

```sql
SELECT
    title,
    ts_headline(
        'english',
        body,
        query,
        'StartSel=<b>, StopSel=</b>, MaxWords=20, MinWords=5'
    ) AS snippet
FROM articles, to_tsquery('english', 'python & django') query
WHERE search_vector @@ query
LIMIT 10;

-- Output:
-- snippet: "Using <b>Python</b> with <b>Django</b> framework for web..."
```

Options:
- `StartSel`, `StopSel` — highlight tags
- `MaxWords`, `MinWords` — snippet length
- `ShortWord` — skip short stopwords
- `HighlightAll=true` — return whole text

---

## 7. Language Support

```sql
-- Different languages
SELECT to_tsvector('english',  'running');    -- 'run'
SELECT to_tsvector('french',   'cours');      -- 'cour'
SELECT to_tsvector('german',   'läuft');      -- 'läuft'
SELECT to_tsvector('hindi',    'दौड़ना');     -- some stem

-- Use language stored per-row
to_tsvector(article.lang::regconfig, article.body)

-- 'simple' = no stemming, no stopwords (fast)
to_tsvector('simple', 'foo bar')   -- 'bar' 'foo'
```

Available: `english`, `french`, `german`, `spanish`, `russian`, `chinese` (with pg_jieba)...

---

## 8. Trigram Search (for fuzzy/typo)

`pg_trgm` extension — handles typos, partial matches.

```sql
CREATE EXTENSION pg_trgm;

-- Similarity search
SELECT name, similarity(name, 'Pyhton') AS sim
FROM products
WHERE name % 'Pyhton'   -- typo!
ORDER BY sim DESC;
-- Returns: Python (similarity ~0.5)

-- Index for fast trigram search
CREATE INDEX idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);

-- Now ILIKE is fast!
SELECT * FROM products WHERE name ILIKE '%pyth%';
```

### Combining: FTS + trigram fallback
```sql
WITH fts_results AS (
    SELECT id, ts_rank(search_vector, query) AS score
    FROM products, to_tsquery('english', 'python') query
    WHERE search_vector @@ query
),
fuzzy_results AS (
    SELECT id, similarity(name, 'python') AS score
    FROM products
    WHERE name % 'python'
    AND id NOT IN (SELECT id FROM fts_results)
)
SELECT * FROM fts_results
UNION ALL
SELECT * FROM fuzzy_results
ORDER BY score DESC;
```

---

## 9. Autocomplete (search-as-you-type)

### Option A: Prefix matching
```sql
-- Match anything starting with "pyt"
SELECT title FROM articles
WHERE search_vector @@ to_tsquery('english', 'pyt:*')
LIMIT 10;
```

### Option B: Trigram index (better for partials)
```sql
SELECT name FROM products
WHERE name ILIKE 'pyt%'
ORDER BY name <-> 'pyt'   -- distance operator
LIMIT 10;
```

### Option C: Separate autocomplete table
```sql
-- Pre-computed prefixes
CREATE TABLE autocomplete (
    prefix TEXT PRIMARY KEY,
    suggestions TEXT[]
);

-- Lookup
SELECT suggestions FROM autocomplete WHERE prefix = 'pyt';
```

---

## 10. Faceted Search

```sql
-- Get facets along with results
WITH search_results AS (
    SELECT * FROM articles
    WHERE search_vector @@ to_tsquery('english', 'python')
)
SELECT
    'category' AS facet, category AS value, COUNT(*) AS count
FROM search_results
GROUP BY category
UNION ALL
SELECT
    'tag', unnest(tags), COUNT(*)
FROM search_results
GROUP BY unnest(tags)
ORDER BY facet, count DESC;
```

---

## 11. Multi-Table Search

```sql
-- Search across multiple tables
SELECT 'article' AS type, id, title FROM articles
WHERE search_vector @@ to_tsquery('python')

UNION ALL

SELECT 'product', id, name FROM products
WHERE search_vector @@ to_tsquery('python')

UNION ALL

SELECT 'user', id, username FROM users
WHERE search_vector @@ to_tsquery('python')

ORDER BY type, id;
```

Better: Create unified search index:
```sql
CREATE MATERIALIZED VIEW search_index AS
    SELECT 'article' AS source, id, title AS subject, search_vector FROM articles
    UNION ALL
    SELECT 'product', id, name, search_vector FROM products;

CREATE INDEX ON search_index USING GIN (search_vector);
REFRESH MATERIALIZED VIEW CONCURRENTLY search_index;
```

---

## 12. Python: SQLAlchemy Integration

```python
from sqlalchemy import Column, BigInteger, String, Text, func, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(Text)
    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index("idx_articles_search", search_vector, postgresql_using="gin"),
    )


# Search
def search(session, query: str, limit: int = 10):
    ts_query = func.to_tsquery("english", " & ".join(query.split()))
    return (
        session.query(
            Article,
            func.ts_rank(Article.search_vector, ts_query).label("rank"),
        )
        .filter(Article.search_vector.op("@@")(ts_query))
        .order_by(func.ts_rank(Article.search_vector, ts_query).desc())
        .limit(limit)
        .all()
    )


# With highlighting
def search_with_highlight(session, query: str):
    ts_query = func.plainto_tsquery("english", query)
    return session.query(
        Article.id,
        Article.title,
        func.ts_headline(
            "english", Article.body, ts_query,
            "StartSel=<b>, StopSel=</b>, MaxWords=30"
        ).label("snippet"),
        func.ts_rank(Article.search_vector, ts_query).label("rank"),
    ).filter(
        Article.search_vector.op("@@")(ts_query)
    ).order_by(
        func.ts_rank(Article.search_vector, ts_query).desc()
    ).all()
```

---

## 13. FastAPI Endpoint

```python
@app.get("/search")
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Sanitize query — escape special chars
    sanitized = " & ".join(q.split())

    sql = text("""
        SELECT
            id,
            title,
            ts_headline('english', body, query,
                'StartSel=<mark>, StopSel=</mark>, MaxWords=30'
            ) AS snippet,
            ts_rank_cd(search_vector, query) AS rank
        FROM articles, to_tsquery('english', :query) query
        WHERE search_vector @@ query
        ORDER BY rank DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {"query": sanitized, "limit": limit})
    return [dict(row) for row in result.mappings()]
```

---

## 14. Postgres FTS vs Elasticsearch

| Feature | Postgres FTS | Elasticsearch |
|---|---|---|
| Built-in | ✅ | Separate service |
| Setup complexity | Low | Medium-High |
| Scale | ~50M docs | Billions |
| Real-time | Sync (transactional) | Near-real-time |
| Languages | ~30 built-in | All |
| Fuzzy search | Via pg_trgm | Native |
| Aggregations | SQL GROUP BY | Native faceting |
| Relevance scoring | Decent | Industry-best |
| Distributed | Manual sharding | Native |
| Cost | Free with Postgres | Separate ops + $$ |

**Migrate to ES when:**
- > 50M searchable docs
- Multi-field complex queries
- Faceted search at scale
- Search-heavy workload (>20% queries)

---

## 15. Performance Tips

### 1. GIN > GiST for FTS
GIN faster for searches (read-heavy). GiST faster for updates.

### 2. Maintenance
```sql
VACUUM ANALYZE articles;   -- update stats
REINDEX INDEX idx_articles_search;   -- if degraded
```

### 3. Pre-compute search vector
Don't use `to_tsvector('english', body) @@ query` in WHERE — full table scan.

### 4. Limit early
```sql
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10
```

### 5. Use parallel query for large tables
```sql
SET max_parallel_workers_per_gather = 4;
```

---

## 16. Common Pitfalls

### Pitfall 1: No GIN index
```sql
-- Sequential scan on 1M rows = slow
WHERE to_tsvector('english', body) @@ to_tsquery('python')
```
Always pre-compute search_vector + index.

### Pitfall 2: Wrong language
```sql
-- ❌ Wrong tokenization
to_tsvector('english', 'französisch text')

-- ✅ Match language
to_tsvector('german', 'französisch text')
```

### Pitfall 3: Special chars not escaped
```python
# ❌ User can inject query syntax
ts_query = f"to_tsquery('english', '{user_input}')"

# ✅ Use parametrized + plainto_tsquery
plainto_tsquery('english', user_input)   -- treats input as plain text
```

### Pitfall 4: Stale generated column
If generated column based on related table, won't auto-update. Use trigger.

### Pitfall 5: tsquery syntax confusion
```sql
to_tsquery('python and django')  -- 'and' is a word, not operator!
to_tsquery('python & django')    -- correct
```

---

## 17. Interview Questions

**Q1: Postgres FTS vs Elasticsearch?**
FTS = built-in, simple, ~50M docs. ES = scale, complex queries, real ops. Default: FTS.

**Q2: tsvector kya hai?**
Document tokenized + stemmed + indexed positions. Stored in column for indexing.

**Q3: tsquery operators?**
`&` AND, `|` OR, `!` NOT, `<->` followed-by, `:*` prefix.

**Q4: Ranking — ts_rank vs ts_rank_cd?**
ts_rank: word frequency-based. ts_rank_cd: also considers word proximity (better).

**Q5: Typo handling?**
pg_trgm extension. Similarity operator `%` + GIN trigram index.

**Q6: Autocomplete?**
Prefix matching (`pyt:*`) or trigram index for "starts with".

**Q7: Multi-language?**
Per-row language column + cast to regconfig. Different tokenizers per language.

---

## 18. Best Practices

1. **Pre-compute tsvector** (generated column or trigger)
2. **GIN index** for FTS (faster queries)
3. **Weighted fields** (title = A, body = B)
4. **`plainto_tsquery`** for user input (safer)
5. **`ts_rank_cd`** for relevance (considers proximity)
6. **`ts_headline`** for highlights
7. **`pg_trgm`** for typo tolerance
8. **Maintenance** — REINDEX + VACUUM periodically
9. **Migrate to ES** at 50M+ docs or complex queries
10. **Stopword + synonym** dictionaries for tuned results

---

## Related
- [[01_postgresql_advanced]]
- [[16_jsonb_queries_indexes]]
- [[../../01_Year3-4_Mid/11_Elasticsearch/]]
- [[14_postgis_geospatial]]
