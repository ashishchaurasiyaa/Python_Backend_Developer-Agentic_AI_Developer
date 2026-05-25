"""
============================================================
POSTGRESQL FULL-TEXT SEARCH — Practical
============================================================
SQL templates + Python integration.
"""


# ============================================================
# 1. SCHEMA + INDEXES
# ============================================================
SCHEMA = """
-- Articles with auto-generated search_vector
CREATE TABLE articles (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[] DEFAULT '{}',
    language TEXT DEFAULT 'english',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    search_vector TSVECTOR
);

-- Generated column (Postgres 12+)
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(body, '')), 'B') ||
        setweight(to_tsvector('english', array_to_string(tags, ' ')), 'C')
    ) STORED;

-- GIN index — critical for performance
CREATE INDEX idx_articles_search ON articles USING GIN (search_vector);

-- Trigger-based for older versions or complex logic
CREATE OR REPLACE FUNCTION articles_tsvector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector(NEW.language::regconfig, coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector(NEW.language::regconfig, coalesce(NEW.body, '')), 'B') ||
        setweight(to_tsvector('simple', array_to_string(NEW.tags, ' ')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER articles_tsvector_trigger
    BEFORE INSERT OR UPDATE OF title, body, tags, language
    ON articles
    FOR EACH ROW EXECUTE FUNCTION articles_tsvector_update();
"""


# ============================================================
# 2. CORE QUERIES
# ============================================================
CORE_QUERIES = """
-- Basic AND search
SELECT id, title FROM articles
WHERE search_vector @@ to_tsquery('english', 'python & django');

-- OR search
SELECT id, title FROM articles
WHERE search_vector @@ to_tsquery('english', 'python | ruby | go');

-- NOT
SELECT id, title FROM articles
WHERE search_vector @@ to_tsquery('english', 'python & !rails');

-- Phrase (Postgres 9.6+)
SELECT id, title FROM articles
WHERE search_vector @@ phraseto_tsquery('english', 'machine learning');

-- Prefix
SELECT id, title FROM articles
WHERE search_vector @@ to_tsquery('english', 'pyth:*');

-- Safe with user input (plainto = treats as plain text)
SELECT id, title FROM articles
WHERE search_vector @@ plainto_tsquery('english', 'user input here & special chars!@#$');

-- Web-like search (Postgres 11+)
SELECT id FROM articles
WHERE search_vector @@ websearch_to_tsquery('english', '"machine learning" python -django');
-- Supports quoted phrases, - for NOT, OR keyword
"""


# ============================================================
# 3. RANKING / RELEVANCE
# ============================================================
RANKING_QUERIES = """
-- ts_rank (frequency-based)
SELECT
    id,
    title,
    ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'python & web') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;

-- ts_rank_cd (cover-density — considers word proximity)
SELECT
    id,
    title,
    ts_rank_cd(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'python web framework') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;

-- Custom weights (default: {A=1.0, B=0.4, C=0.2, D=0.1})
SELECT
    id,
    ts_rank('{0.1, 0.3, 0.5, 1.0}'::float4[], search_vector, query) AS rank
FROM articles, to_tsquery('english', 'python') query
WHERE search_vector @@ query
ORDER BY rank DESC;

-- Combine FTS rank + recency boost
SELECT
    id,
    title,
    (ts_rank(search_vector, query) +
     1.0 / (1 + EXTRACT(EPOCH FROM NOW() - created_at) / 86400)) AS combined_score
FROM articles, to_tsquery('english', 'python') query
WHERE search_vector @@ query
ORDER BY combined_score DESC;
"""


# ============================================================
# 4. HIGHLIGHTING
# ============================================================
HIGHLIGHTING = """
-- ts_headline returns snippet with highlights
SELECT
    id,
    title,
    ts_headline(
        'english',
        body,
        query,
        'StartSel=<mark>, StopSel=</mark>, MaxWords=30, MinWords=10, ShortWord=3'
    ) AS snippet
FROM articles, to_tsquery('english', 'python & django') query
WHERE search_vector @@ query
LIMIT 10;

-- Highlight title separately
SELECT
    id,
    ts_headline('english', title, query,
                'StartSel=<b>, StopSel=</b>') AS title_highlighted,
    ts_headline('english', body, query,
                'StartSel=<mark>, StopSel=</mark>, MaxWords=25') AS body_snippet
FROM articles, to_tsquery('english', 'python') query
WHERE search_vector @@ query;
"""


# ============================================================
# 5. PG_TRGM FOR TYPOS / FUZZY
# ============================================================
TRIGRAM_SETUP = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index for fast trigram search
CREATE INDEX idx_articles_title_trgm ON articles USING GIN (title gin_trgm_ops);

-- Similarity search
SELECT
    title,
    similarity(title, 'Pyhton Programming') AS sim
FROM articles
WHERE title % 'Pyhton Programming'   -- typo tolerant!
ORDER BY sim DESC
LIMIT 10;

-- Configure threshold
SHOW pg_trgm.similarity_threshold;        -- default 0.3
SET pg_trgm.similarity_threshold = 0.4;   -- stricter match

-- ILIKE becomes fast with trigram index
SELECT * FROM articles
WHERE title ILIKE '%pyth%';
-- Without index: O(N) full scan
-- With trigram GIN: O(log N)
"""


# ============================================================
# 6. AUTOCOMPLETE
# ============================================================
AUTOCOMPLETE = """
-- Option 1: tsvector prefix match
SELECT id, title FROM articles
WHERE search_vector @@ to_tsquery('english', 'pyt:*')
LIMIT 10;

-- Option 2: trigram for partial words
SELECT title
FROM articles
WHERE title ILIKE 'pyt%'
ORDER BY title <-> 'pyt'   -- closest match
LIMIT 10;

-- Option 3: Dedicated suggestions table
CREATE TABLE search_suggestions (
    prefix TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    weight FLOAT DEFAULT 1.0,
    PRIMARY KEY (prefix, suggestion)
);

CREATE INDEX idx_suggestions_prefix ON search_suggestions (prefix text_pattern_ops);

-- Query
SELECT suggestion FROM search_suggestions
WHERE prefix LIKE 'pyt%'
ORDER BY weight DESC
LIMIT 10;
"""


# ============================================================
# 7. PYTHON: SQLALCHEMY
# ============================================================
PYTHON_SQLALCHEMY = '''
from sqlalchemy import Column, BigInteger, String, Text, ARRAY, func, Index, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(Text)
    tags = Column(ARRAY(String), default=list)
    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index("idx_articles_search", "search_vector", postgresql_using="gin"),
    )


# ===== BASIC SEARCH =====
def search(session, query: str, limit: int = 10):
    ts_query = func.plainto_tsquery("english", query)
    return (
        session.query(Article)
        .filter(Article.search_vector.op("@@")(ts_query))
        .order_by(func.ts_rank(Article.search_vector, ts_query).desc())
        .limit(limit)
        .all()
    )


# ===== WITH HIGHLIGHTS =====
def search_with_highlights(session, query: str):
    ts_query = func.plainto_tsquery("english", query)
    return session.query(
        Article.id,
        Article.title,
        func.ts_headline(
            "english", Article.body, ts_query,
            "StartSel=<mark>, StopSel=</mark>, MaxWords=30"
        ).label("snippet"),
        func.ts_rank_cd(Article.search_vector, ts_query).label("rank"),
    ).filter(
        Article.search_vector.op("@@")(ts_query)
    ).order_by(
        func.ts_rank_cd(Article.search_vector, ts_query).desc()
    ).limit(20).all()


# ===== BOOLEAN OPERATORS =====
def boolean_search(session, must: list[str], should: list[str], must_not: list[str]):
    query_parts = []
    if must:
        query_parts.append(" & ".join(must))
    if should:
        query_parts.append("(" + " | ".join(should) + ")")
    if must_not:
        query_parts.extend([f"!{w}" for w in must_not])

    query_str = " & ".join(query_parts)
    ts_query = func.to_tsquery("english", query_str)

    return session.query(Article).filter(
        Article.search_vector.op("@@")(ts_query)
    ).all()


# ===== FUZZY (typo-tolerant) =====
def fuzzy_search(session, query: str, threshold: float = 0.3):
    return session.execute(text("""
        SELECT id, title, similarity(title, :q) AS sim
        FROM articles
        WHERE title % :q
          AND similarity(title, :q) > :threshold
        ORDER BY sim DESC
        LIMIT 10
    """), {"q": query, "threshold": threshold}).all()
'''


# ============================================================
# 8. FASTAPI ENDPOINTS
# ============================================================
FASTAPI_ENDPOINTS = '''
from fastapi import FastAPI, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel

app = FastAPI()


class SearchResult(BaseModel):
    id: int
    title: str
    snippet: str | None
    rank: float


@app.get("/search", response_model=list[SearchResult])
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    sql = text("""
        SELECT
            id, title,
            ts_headline('english', body, query,
                'StartSel=<mark>, StopSel=</mark>, MaxWords=30'
            ) AS snippet,
            ts_rank_cd(search_vector, query) AS rank
        FROM articles, plainto_tsquery('english', :q) query
        WHERE search_vector @@ query
        ORDER BY rank DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"q": q, "limit": limit})
    return [SearchResult(**dict(row)) for row in result.mappings()]


@app.get("/autocomplete")
async def autocomplete(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    sql = text("""
        SELECT DISTINCT title
        FROM articles
        WHERE title ILIKE :prefix
        ORDER BY title <-> :prefix
        LIMIT 10
    """)
    result = await db.execute(sql, {"prefix": f"{q}%"})
    return [r[0] for r in result.fetchall()]


@app.get("/search/fuzzy")
async def fuzzy_search(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    """Typo-tolerant search using pg_trgm."""
    sql = text("""
        SELECT id, title, similarity(title, :q) AS score
        FROM articles
        WHERE title % :q
        ORDER BY score DESC
        LIMIT 10
    """)
    result = await db.execute(sql, {"q": q})
    return [dict(row) for row in result.mappings()]


@app.get("/search/advanced")
async def advanced_search(
    q: str | None = None,
    must: list[str] = Query(default=[]),
    must_not: list[str] = Query(default=[]),
    category: str | None = None,
    tag: list[str] = Query(default=[]),
    sort: str = Query("relevance", regex="^(relevance|date|popularity)$"),
    db: AsyncSession = Depends(get_db),
):
    """Multi-faceted search."""
    parts = []
    params = {}

    if q:
        parts.append("search_vector @@ plainto_tsquery('english', :q)")
        params["q"] = q
    if must:
        for i, term in enumerate(must):
            parts.append(f"search_vector @@ to_tsquery('english', :must_{i})")
            params[f"must_{i}"] = term
    if must_not:
        for i, term in enumerate(must_not):
            parts.append(f"NOT (search_vector @@ to_tsquery('english', :not_{i}))")
            params[f"not_{i}"] = term
    if category:
        parts.append("category = :cat")
        params["cat"] = category
    if tag:
        parts.append("tags && :tags")
        params["tags"] = tag

    where = " AND ".join(parts) if parts else "TRUE"

    order_by = {
        "relevance": "ts_rank_cd(search_vector, plainto_tsquery('english', :q)) DESC" if q else "created_at DESC",
        "date": "created_at DESC",
        "popularity": "view_count DESC",
    }[sort]

    sql = text(f"""
        SELECT id, title, snippet, category, tags, created_at
        FROM articles
        WHERE {where}
        ORDER BY {order_by}
        LIMIT 50
    """)
    result = await db.execute(sql, params)
    return [dict(row) for row in result.mappings()]
'''


# ============================================================
# 9. CONFIGURATION TUNING
# ============================================================
TUNING = """
-- Custom dictionary (synonyms)
CREATE TEXT SEARCH DICTIONARY english_synonym (
    TEMPLATE = synonym,
    SYNONYMS = my_synonyms
);

-- my_synonyms.syn file:
--   js javascript
--   ml machine learning
--   ai artificial intelligence

-- Use custom config
CREATE TEXT SEARCH CONFIGURATION my_english (COPY = english);
ALTER TEXT SEARCH CONFIGURATION my_english
    ALTER MAPPING FOR asciiword
    WITH english_synonym, english_stem;

-- Now searching "js" finds "javascript" too
SELECT to_tsvector('my_english', 'I love JS programming');
-- 'javascript' 'love' 'program'

-- Check config
SHOW default_text_search_config;
"""


# ============================================================
# 10. MAINTENANCE
# ============================================================
MAINTENANCE = """
-- Vacuum + analyze (update stats)
VACUUM ANALYZE articles;

-- Reindex if degraded (after lots of updates)
REINDEX INDEX CONCURRENTLY idx_articles_search;

-- Check index health
SELECT
    schemaname, tablename, indexname,
    pg_size_pretty(pg_relation_size(indexrelid)),
    idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE indexname LIKE '%search%';

-- Check tsvector content
SELECT id, search_vector
FROM articles
WHERE id = 1;
-- Output: 'python':3 'web':5 ...

-- Test tokenization
SELECT to_tsvector('english', 'The quick brown fox jumps');
-- 'brown':3 'fox':4 'jump':5 'quick':2
-- Note: stopwords 'the' removed, 'jumps' stemmed to 'jump'
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("POSTGRESQL FULL-TEXT SEARCH — Practical")
    print("=" * 60)

    print("\n--- SCHEMA ---")
    print(SCHEMA)
    print("\n--- CORE QUERIES ---")
    print(CORE_QUERIES)
    print("\n--- RANKING ---")
    print(RANKING_QUERIES)
    print("\n--- HIGHLIGHTING ---")
    print(HIGHLIGHTING)
    print("\n--- TRIGRAM (typo handling) ---")
    print(TRIGRAM_SETUP)
    print("\n--- AUTOCOMPLETE ---")
    print(AUTOCOMPLETE)
    print("\n--- PYTHON SQLALCHEMY ---")
    print(PYTHON_SQLALCHEMY)
    print("\n--- FASTAPI ENDPOINTS ---")
    print(FASTAPI_ENDPOINTS)
    print("\n--- CONFIG TUNING ---")
    print(TUNING)
    print("\n--- MAINTENANCE ---")
    print(MAINTENANCE)
