"""
PostgreSQL Advanced — Practical Examples
═══════════════════════════════════════════════════════════════
Run: python 01_postgresql_practical.py
Install: pip install asyncpg sqlalchemy[asyncio] psycopg2-binary

Topics:
  - Window functions (ROW_NUMBER, RANK, LAG, running totals)
  - CTEs (simple, chained, recursive)
  - Full-text search (tsvector, GIN index, pg_trgm)
  - Table partitioning setup
  - EXPLAIN ANALYZE in Python
  - Index management

INTERVIEW QUICK REFERENCE at bottom of file.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
import random

DATABASE_URL = "postgresql://postgres:password@localhost:5432/demo_db"


# ═══════════════════════════════════════════════════════════
# SECTION 1: Setup — Create Tables
# ═══════════════════════════════════════════════════════════

SETUP_SQL = """
-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector (if installed)

-- Users table
CREATE TABLE IF NOT EXISTS demo_users (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100),
    department VARCHAR(50),
    salary     DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Posts table with FTS support
CREATE TABLE IF NOT EXISTS demo_posts (
    id            SERIAL PRIMARY KEY,
    title         VARCHAR(300),
    content       TEXT,
    author_id     INT REFERENCES demo_users(id),
    views         INT DEFAULT 0,
    likes         INT DEFAULT 0,
    status        VARCHAR(20) DEFAULT 'published',
    published_at  TIMESTAMPTZ DEFAULT NOW(),
    search_vector TSVECTOR
);

-- FTS index
CREATE INDEX IF NOT EXISTS idx_posts_search ON demo_posts USING gin(search_vector);

-- Trigger to auto-update search_vector
CREATE OR REPLACE FUNCTION update_post_search()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS posts_search_update ON demo_posts;
CREATE TRIGGER posts_search_update
    BEFORE INSERT OR UPDATE ON demo_posts
    FOR EACH ROW EXECUTE FUNCTION update_post_search();

-- Monthly revenue table (for window function demos)
CREATE TABLE IF NOT EXISTS monthly_revenue (
    id         SERIAL PRIMARY KEY,
    month      DATE UNIQUE,
    revenue    DECIMAL(12,2),
    orders     INT
);

-- Category tree (for recursive CTE)
CREATE TABLE IF NOT EXISTS categories (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(100),
    parent_id INT REFERENCES categories(id)
);
"""

SEED_SQL = """
-- Users
INSERT INTO demo_users (name, department, salary) VALUES
    ('Alice Johnson',  'Engineering', 120000),
    ('Bob Smith',      'Engineering', 95000),
    ('Charlie Brown',  'Engineering', 110000),
    ('Diana Prince',   'Marketing',   85000),
    ('Evan Rogers',    'Marketing',   90000),
    ('Fiona Green',    'HR',          75000),
    ('George Wilson',  'HR',          78000),
    ('Hannah Davis',   'Engineering', 130000)
ON CONFLICT DO NOTHING;

-- Posts
INSERT INTO demo_posts (title, content, author_id, views, likes) VALUES
    ('Django ORM Deep Dive',      'Learn select_related prefetch_related N+1 optimization',     1, 5000, 200),
    ('FastAPI Complete Guide',    'Build production APIs with FastAPI dependency injection',      1, 8000, 350),
    ('PostgreSQL Indexing',       'Understand B-tree GIN GIST indexes and EXPLAIN ANALYZE',      2, 3000, 120),
    ('Redis Caching Patterns',    'Cache aside pattern Pub Sub Sorted Sets rate limiting',        2, 4500, 180),
    ('Python Async Programming',  'asyncio coroutines tasks event loop ThreadPoolExecutor',       3, 6000, 250),
    ('Docker and Kubernetes',     'Containerize your Python application deploy to production',    3, 7500, 300),
    ('System Design Basics',      'CAP theorem consistency availability partition tolerance',     4, 9000, 400),
    ('LangChain and LangGraph',   'Build AI agents with LangChain LangGraph RAG pipeline',       4, 12000, 500)
ON CONFLICT DO NOTHING;

-- Monthly revenue
INSERT INTO monthly_revenue (month, revenue, orders) VALUES
    ('2024-01-01', 125000.00, 450),
    ('2024-02-01', 118000.00, 420),
    ('2024-03-01', 135000.00, 480),
    ('2024-04-01', 142000.00, 510),
    ('2024-05-01', 138000.00, 495),
    ('2024-06-01', 155000.00, 560),
    ('2024-07-01', 162000.00, 580),
    ('2024-08-01', 158000.00, 565)
ON CONFLICT DO NOTHING;

-- Category tree
INSERT INTO categories (id, name, parent_id) VALUES
    (1, 'Technology', NULL),
    (2, 'Programming', 1),
    (3, 'Databases', 1),
    (4, 'Python',  2),
    (5, 'JavaScript', 2),
    (6, 'PostgreSQL', 3),
    (7, 'Redis', 3),
    (8, 'Django', 4),
    (9, 'FastAPI', 4)
ON CONFLICT DO NOTHING;
"""


# ═══════════════════════════════════════════════════════════
# SECTION 2: Window Functions
# ═══════════════════════════════════════════════════════════

async def demo_window_functions(conn):
    print("\n" + "═"*60)
    print("WINDOW FUNCTIONS")
    print("═"*60)

    # ─── ROW_NUMBER + RANK ───
    print("\n--- ROW_NUMBER vs RANK (salary ranking per dept) ---")
    rows = await conn.fetch("""
        SELECT
            name,
            department,
            salary,
            ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS row_num,
            RANK()       OVER (PARTITION BY department ORDER BY salary DESC) AS rank,
            DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dense_rank
        FROM demo_users
        ORDER BY department, salary DESC
    """)
    for r in rows:
        print(f"  {r['name']:20} | {r['department']:12} | ${r['salary']:>10,.0f} "
              f"| row#{r['row_num']} rank#{r['rank']} dense#{r['dense_rank']}")

    # ─── Top N per group ───
    print("\n--- Top 2 earners per department ---")
    rows = await conn.fetch("""
        SELECT name, department, salary FROM (
            SELECT name, department, salary,
                   ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rn
            FROM demo_users
        ) ranked
        WHERE rn <= 2
        ORDER BY department, salary DESC
    """)
    for r in rows:
        print(f"  {r['name']:20} | {r['department']:12} | ${r['salary']:>10,.0f}")

    # ─── LAG + Running total ───
    print("\n--- Month-over-Month + Running Total ---")
    rows = await conn.fetch("""
        SELECT
            TO_CHAR(month, 'YYYY-MM')         AS month,
            revenue,
            LAG(revenue) OVER (ORDER BY month) AS prev_month,
            ROUND(
                (revenue - LAG(revenue) OVER (ORDER BY month))
                / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) * 100, 1
            ) AS mom_pct_change,
            SUM(revenue) OVER (ORDER BY month ROWS UNBOUNDED PRECEDING) AS running_total
        FROM monthly_revenue
        ORDER BY month
    """)
    for r in rows:
        change = f"{r['mom_pct_change']:+.1f}%" if r['mom_pct_change'] else "N/A"
        print(f"  {r['month']} | Revenue: ${r['revenue']:>10,.0f} "
              f"| MoM: {change:>8} | Running: ${r['running_total']:>12,.0f}")

    # ─── Moving average (7-row window) ───
    print("\n--- 3-Month Moving Average ---")
    rows = await conn.fetch("""
        SELECT
            TO_CHAR(month, 'YYYY-MM') AS month,
            revenue,
            ROUND(
                AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2
            ) AS moving_avg_3m
        FROM monthly_revenue
        ORDER BY month
    """)
    for r in rows:
        print(f"  {r['month']} | Revenue: ${r['revenue']:>10,.0f} | 3M Avg: ${r['moving_avg_3m']:>10,.2f}")


# ═══════════════════════════════════════════════════════════
# SECTION 3: CTEs
# ═══════════════════════════════════════════════════════════

async def demo_cte(conn):
    print("\n" + "═"*60)
    print("CTEs — Common Table Expressions")
    print("═"*60)

    # ─── Chained CTEs ───
    print("\n--- Chained CTE: dept stats + top performers ---")
    rows = await conn.fetch("""
        WITH
        dept_stats AS (
            SELECT department,
                   COUNT(*)      AS headcount,
                   AVG(salary)   AS avg_salary,
                   MAX(salary)   AS max_salary
            FROM demo_users
            GROUP BY department
        ),
        top_earners AS (
            SELECT name, department, salary,
                   ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rn
            FROM demo_users
        )
        SELECT
            ds.department,
            ds.headcount,
            ROUND(ds.avg_salary, 0)  AS avg_salary,
            te.name                  AS top_earner,
            te.salary                AS top_salary
        FROM dept_stats ds
        JOIN top_earners te ON te.department = ds.department AND te.rn = 1
        ORDER BY ds.avg_salary DESC
    """)
    for r in rows:
        print(f"  {r['department']:12} | {r['headcount']} people "
              f"| Avg: ${r['avg_salary']:>8,.0f} | Top: {r['top_earner']} (${r['top_salary']:,.0f})")

    # ─── Recursive CTE: Category tree ───
    print("\n--- Recursive CTE: Category Hierarchy ---")
    rows = await conn.fetch("""
        WITH RECURSIVE cat_tree AS (
            SELECT id, name, parent_id, 0 AS depth, name AS path
            FROM categories
            WHERE parent_id IS NULL

            UNION ALL

            SELECT c.id, c.name, c.parent_id,
                   ct.depth + 1,
                   (ct.path || ' > ' || c.name)
            FROM categories c
            JOIN cat_tree ct ON ct.id = c.parent_id
        )
        SELECT depth, name, path FROM cat_tree ORDER BY path
    """)
    for r in rows:
        indent = "  " * r['depth']
        print(f"  {indent}{'└─' if r['depth'] > 0 else '►'} {r['name']:20} | {r['path']}")


# ═══════════════════════════════════════════════════════════
# SECTION 4: Full-Text Search
# ═══════════════════════════════════════════════════════════

async def demo_fts(conn):
    print("\n" + "═"*60)
    print("FULL-TEXT SEARCH")
    print("═"*60)

    # ─── FTS with ranking ───
    print("\n--- FTS: search 'django orm' with ranking ---")
    rows = await conn.fetch("""
        SELECT
            p.title,
            ts_rank(p.search_vector, query) AS rank,
            ts_headline('english', p.content, query,
                'MaxWords=10, MinWords=5') AS snippet
        FROM demo_posts p,
             to_tsquery('english', 'django | orm | select_related') AS query
        WHERE p.search_vector @@ query
        ORDER BY rank DESC
    """)
    if rows:
        for r in rows:
            print(f"  [{r['rank']:.4f}] {r['title']}")
            print(f"         ↳ {r['snippet'][:100]}...")
    else:
        print("  (No results — check if seed data was inserted)")

    # ─── plainto_tsquery — user-friendly input ───
    print("\n--- plainto_tsquery (natural language input) ---")
    rows = await conn.fetch("""
        SELECT title,
               ts_rank(search_vector, plainto_tsquery('english', 'python async programming')) AS rank
        FROM demo_posts
        WHERE search_vector @@ plainto_tsquery('english', 'python async programming')
        ORDER BY rank DESC
    """)
    for r in rows:
        print(f"  [{r['rank']:.4f}] {r['title']}")

    # ─── pg_trgm — fuzzy/similarity search ───
    print("\n--- pg_trgm: fuzzy search 'Dajngo' (typo) ---")
    rows = await conn.fetch("""
        SELECT title, similarity(title, 'Dajngo ORM') AS sim
        FROM demo_posts
        WHERE title % 'Dajngo ORM'
        ORDER BY sim DESC
    """)
    if rows:
        for r in rows:
            print(f"  [{r['sim']:.3f}] {r['title']}")
    else:
        print("  (No fuzzy matches — pg_trgm may need index or lower threshold)")


# ═══════════════════════════════════════════════════════════
# SECTION 5: EXPLAIN ANALYZE in Python
# ═══════════════════════════════════════════════════════════

async def demo_explain(conn):
    print("\n" + "═"*60)
    print("EXPLAIN ANALYZE")
    print("═"*60)

    query = "SELECT * FROM demo_posts WHERE status = 'published' ORDER BY views DESC LIMIT 10"

    rows = await conn.fetch(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {query}")
    print(f"\nQuery: {query}\n")
    for r in rows:
        print(f"  {r[0]}")


# ═══════════════════════════════════════════════════════════
# SECTION 6: Index Management
# ═══════════════════════════════════════════════════════════

async def demo_indexes(conn):
    print("\n" + "═"*60)
    print("INDEX MANAGEMENT")
    print("═"*60)

    # Create useful indexes
    index_sql = [
        # Composite index for common query pattern
        ("idx_posts_status_views",
         "CREATE INDEX IF NOT EXISTS idx_posts_status_views "
         "ON demo_posts (status, views DESC)"),
        # Partial index — only published posts
        ("idx_posts_published_only",
         "CREATE INDEX IF NOT EXISTS idx_posts_published_only "
         "ON demo_posts (published_at DESC) WHERE status = 'published'"),
        # Covering index — avoid table access
        ("idx_posts_covering",
         "CREATE INDEX IF NOT EXISTS idx_posts_covering "
         "ON demo_posts (status, published_at DESC) "
         "INCLUDE (id, title, author_id)"),
        # Trigram index for LIKE queries
        ("idx_posts_title_trgm",
         "CREATE INDEX IF NOT EXISTS idx_posts_title_trgm "
         "ON demo_posts USING gin(title gin_trgm_ops)"),
    ]

    for name, sql in index_sql:
        await conn.execute(sql)
        print(f"  ✓ Created index: {name}")

    # Show index usage stats
    print("\n--- Index sizes ---")
    rows = await conn.fetch("""
        SELECT
            indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) AS size
        FROM pg_stat_user_indexes
        WHERE relname IN ('demo_posts', 'demo_users')
        ORDER BY pg_relation_size(indexrelid) DESC
    """)
    for r in rows:
        print(f"  {r['indexname']:40} | {r['size']}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    print("Connecting to PostgreSQL...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Update DATABASE_URL at top of file")
        return

    print("✓ Connected")

    # Setup
    await conn.execute(SETUP_SQL)
    await conn.execute(SEED_SQL)
    print("✓ Tables created and seeded")

    # Demos
    await demo_window_functions(conn)
    await demo_cte(conn)
    await demo_fts(conn)
    await demo_explain(conn)
    await demo_indexes(conn)

    await conn.close()
    print("\n✓ Done!")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: Window function syntax?
A: func() OVER (PARTITION BY col ORDER BY col ROWS BETWEEN ...)

Q: ROW_NUMBER vs RANK vs DENSE_RANK?
A: ROW_NUMBER: 1,2,3,4 (always unique)
   RANK:       1,1,3,4 (gap after ties)
   DENSE_RANK: 1,1,2,3 (no gap after ties)

Q: CTE vs Subquery?
A: CTE: multiple places use karna ho, readability, recursive queries
   Subquery: one-off, simple inline queries

Q: Recursive CTE use case?
A: Category tree, org chart, file system, social follows

Q: FTS operators?
A: @@ = match, to_tsvector() = index document,
   to_tsquery('a & b') = exact words,
   plainto_tsquery('a b') = user input (AND by default)
   ts_rank() = relevance score
   ts_headline() = snippet with highlights

Q: pg_trgm vs tsvector?
A: tsvector: word stemming, stop words, relevance ranking — full-text
   pg_trgm:  character-level, fuzzy match, typo tolerance, LIKE with index

Q: Create index on large table without lock?
A: CREATE INDEX CONCURRENTLY idx_name ON table (column)
"""

if __name__ == "__main__":
    asyncio.run(main())
