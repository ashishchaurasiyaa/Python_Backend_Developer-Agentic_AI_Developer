"""
Advanced Indexing — Production Patterns
"""

# ==========================================================================
# 1. COVERING INDEX (INCLUDE)
# ==========================================================================

COVERING_INDEX_SQL = """
-- Without — index lookup + heap fetch
CREATE INDEX idx_users_email ON users (email);
EXPLAIN ANALYZE SELECT name, email FROM users WHERE email = 'a@b.com';
-- Index Scan + Heap Fetches

-- With — fully covered
CREATE INDEX idx_users_email_covering ON users (email) INCLUDE (name);
EXPLAIN ANALYZE SELECT name, email FROM users WHERE email = 'a@b.com';
-- Index Only Scan (no heap access if VM up to date)

-- Real-world: API endpoint that lists users by email with names
"""


# ==========================================================================
# 2. PARTIAL INDEX
# ==========================================================================

PARTIAL_INDEX_SQL = """
-- Job queue: 99% of rows are 'completed', only 1% 'pending'
CREATE INDEX idx_jobs_pending
    ON jobs (priority DESC, created_at)
    WHERE status = 'pending';

-- Query benefits:
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY priority DESC, created_at
LIMIT 1;
-- Only scans 1% subset


-- Soft delete: most rows not deleted
CREATE INDEX idx_users_active_email ON users (email) WHERE deleted_at IS NULL;


-- Unique constraint with soft delete (allows email reuse after delete)
CREATE UNIQUE INDEX idx_users_email_unique
    ON users (email)
    WHERE deleted_at IS NULL;


-- Active users only
CREATE INDEX idx_users_active_lastlogin ON users (last_login_at) WHERE is_active = true;
"""


# ==========================================================================
# 3. EXPRESSION INDEX (Functional)
# ==========================================================================

EXPRESSION_INDEX_SQL = """
-- Case-insensitive email lookup
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
SELECT * FROM users WHERE LOWER(email) = 'a@b.com';   -- uses index


-- Date extraction
CREATE INDEX idx_orders_year ON orders (EXTRACT(YEAR FROM created_at));
SELECT * FROM orders WHERE EXTRACT(YEAR FROM created_at) = 2026;


-- JSONB key lookup
CREATE INDEX idx_orders_status ON orders ((metadata->>'status'));
SELECT * FROM orders WHERE metadata->>'status' = 'paid';


-- Compound expression
CREATE INDEX idx_users_fullname ON users (LOWER(first_name || ' ' || last_name));
"""


# ==========================================================================
# 4. MULTI-COLUMN INDEX — ORDER MATTERS
# ==========================================================================

MULTICOLUMN_ORDER_SQL = """
CREATE INDEX idx_orders_user_status_date ON orders (user_id, status, created_at);

-- USES INDEX:
SELECT * FROM orders WHERE user_id = 5;
SELECT * FROM orders WHERE user_id = 5 AND status = 'paid';
SELECT * FROM orders WHERE user_id = 5 AND status = 'paid' AND created_at > '...';

-- DOES NOT USE INDEX:
SELECT * FROM orders WHERE status = 'paid';            -- skips leading column
SELECT * FROM orders WHERE created_at > '...';          -- skips both
SELECT * FROM orders WHERE user_id = 5 AND created_at > '...';  -- skips middle


-- Rule: most-selective column first, equality before range
-- (user_id high selectivity, status low — but most common WHERE includes user_id)
"""


# ==========================================================================
# 5. INDEX TYPES (B-tree, GIN, GiST, BRIN)
# ==========================================================================

INDEX_TYPES_SQL = """
-- B-tree (default) — equality, range, sort
CREATE INDEX idx_users_id ON users (id);
CREATE INDEX idx_orders_created ON orders (created_at DESC);

-- GIN — array, JSONB, full-text
CREATE INDEX idx_articles_tags ON articles USING GIN (tags);
-- SELECT * FROM articles WHERE tags @> ARRAY['python'];

CREATE INDEX idx_orders_metadata ON orders USING GIN (metadata jsonb_path_ops);
-- SELECT * FROM orders WHERE metadata @> '{"status": "paid"}';

CREATE INDEX idx_articles_search ON articles
    USING GIN (to_tsvector('english', title || ' ' || body));
-- SELECT * FROM articles WHERE to_tsvector('english', title || ' ' || body) @@ plainto_tsquery('search');


-- GiST — geometric, range types, full-text
CREATE INDEX idx_places_location ON places USING GiST (location);
-- ORDER BY location <-> ST_MakePoint(0, 0) LIMIT 10;


-- BRIN — huge tables with natural ordering (logs)
CREATE INDEX idx_logs_time ON logs USING BRIN (created_at);
-- 1000x smaller than B-tree, slower lookup, but fits in RAM


-- Hash — equality only, rarely needed in modern Postgres
CREATE INDEX idx_users_name_hash ON users USING HASH (name);
"""


# ==========================================================================
# 6. CONCURRENT INDEX CREATION
# ==========================================================================

CONCURRENT_INDEX_SQL = """
-- Production-safe (no AccessExclusiveLock)
CREATE INDEX CONCURRENTLY idx_users_email_new ON users (email);

-- Slower but doesn't block writes
-- If fails, leftover INVALID index:
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
DROP INDEX CONCURRENTLY idx_users_email_new;

-- Reindex without lock (Postgres 12+)
REINDEX INDEX CONCURRENTLY idx_users_email;
REINDEX TABLE CONCURRENTLY users;
"""


# ==========================================================================
# 7. DJANGO MODEL INDEXES
# ==========================================================================

"""
from django.db import models


class Order(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            # Multi-column
            models.Index(fields=['user', 'status', '-created_at'], name='order_user_status_idx'),

            # Partial (Django 2.0+)
            models.Index(
                fields=['priority', 'created_at'],
                name='order_pending_idx',
                condition=models.Q(status='pending'),
            ),

            # Covering (Django 4.0+)
            models.Index(
                fields=['user'],
                include=['status', 'amount'],
                name='order_user_covering',
            ),

            # Expression (Django 3.2+)
            models.Index(
                Lower('email'),
                name='order_email_lower_idx',
            ),

            # GIN for JSONB (PostgreSQL only)
            GinIndex(fields=['metadata'], name='order_metadata_gin'),
        ]
"""


# ==========================================================================
# 8. SQLALCHEMY INDEXES
# ==========================================================================

"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSONB


Base = declarative_base()


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    status = Column(String(20), nullable=False)
    amount = Column(Integer)
    created_at = Column(DateTime)
    metadata = Column(JSONB)

    __table_args__ = (
        Index('idx_user_status_created', 'user_id', 'status', 'created_at'),
        Index(
            'idx_pending_jobs',
            'created_at',
            postgresql_where='status = \\'pending\\'',
        ),
        Index(
            'idx_email_lower',
            func.lower(email),
        ),
        Index(
            'idx_metadata_gin',
            'metadata',
            postgresql_using='gin',
        ),
    )
"""


# ==========================================================================
# 9. INDEX HEALTH MONITORING QUERIES
# ==========================================================================

INDEX_HEALTH_QUERIES = """
-- Index size + usage
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS times_used,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;


-- UNUSED indexes (candidate for drop)
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
  AND indexrelname NOT LIKE '%_unique%'
ORDER BY pg_relation_size(indexrelid) DESC;


-- Invalid indexes (failed creation)
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;


-- Index bloat (rough estimate via pgstattuple extension)
CREATE EXTENSION IF NOT EXISTS pgstattuple;
SELECT * FROM pgstatindex('idx_orders_user_status_created');


-- Tables without indexes on FK columns (perf issue)
SELECT
    c.conrelid::regclass AS table_name,
    a.attname AS column_name,
    c.conname AS fk_name
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid AND a.attnum = ANY(i.indkey)
  );
"""


# ==========================================================================
# 10. EXPLAIN INTERPRETATION
# ==========================================================================

EXPLAIN_EXAMPLES = """
-- Always use ANALYZE for real timings
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM orders WHERE user_id = 5 AND status = 'paid';

-- Read top to bottom:
-- Index Scan (good) vs Seq Scan (potentially bad on large tables)
-- Rows: estimated vs actual — large discrepancy = stats stale
-- Loops > 1 = nested operation
-- Buffers: shared hit (cached) vs shared read (disk)

-- Use auto_explain in prod for slow queries
LOAD 'auto_explain';
SET auto_explain.log_min_duration = '500ms';
SET auto_explain.log_analyze = on;
SET auto_explain.log_buffers = on;
"""


# ==========================================================================
# 11. PERFORMANCE PATTERNS
# ==========================================================================

PATTERNS = """
Pattern 1: Sort + Limit with index
    CREATE INDEX idx_articles_views ON articles (view_count DESC);
    SELECT * FROM articles ORDER BY view_count DESC LIMIT 10;
    -- O(log n) — index already sorted

Pattern 2: Keyset pagination (no OFFSET)
    -- Bad (slow on large tables)
    SELECT * FROM articles ORDER BY id LIMIT 20 OFFSET 100000;
    -- Database must scan 100020 rows

    -- Good (cursor-based)
    SELECT * FROM articles
    WHERE id > :last_seen_id
    ORDER BY id
    LIMIT 20;

Pattern 3: Composite index for ORDER BY + WHERE
    CREATE INDEX idx_orders_user_date ON orders (user_id, created_at DESC);
    SELECT * FROM orders WHERE user_id = 5 ORDER BY created_at DESC LIMIT 10;
    -- Uses index for both filter AND sort

Pattern 4: Don't index everything
    Each INSERT updates all indexes. 20 indexes = 20x write amplification.
    Add only based on slow query log.
"""
