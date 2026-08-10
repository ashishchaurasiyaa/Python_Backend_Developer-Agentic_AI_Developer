# PostgreSQL — Start Here (Not MySQL)

## Why PostgreSQL, Not MySQL?

| Reason | PostgreSQL | MySQL |
|--------|-----------|-------|
| Market standard 2026 | 90% of startups + product companies | Legacy — LAMP stack era |
| JSON support | JSONB — fast, indexed | JSON — slow, no indexing |
| Advanced indexes | BTree, GIN, BRIN, Hash, SP-GiST | BTree only |
| Full-text search | Built-in, powerful | Basic only |
| Vector support (AI) | pgvector extension — native | Not supported |
| Window functions | Full SQL:2016 support | Partial support |
| ACID compliance | Full | InnoDB only |
| Concurrency (MVCC) | True MVCC | Lock-heavy |
| Replication | Logical + streaming | Master-slave only |
| Companies using it | Uber, Instagram, GitHub, Notion, Supabase | WordPress, Drupal, old apps |

**In Indian market:** Zepto, CRED, Razorpay, Groww, Meesho all use PostgreSQL.

---

## Install PostgreSQL (Mac)

```bash
# Install
brew install postgresql@16

# Start service
brew services start postgresql@16

# Connect
psql postgres

# Create a database
CREATE DATABASE myproject;

# Create a user
CREATE USER myuser WITH PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE myproject TO myuser;
```

---

## Install PostgreSQL (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Switch to postgres user
sudo -i -u postgres
psql

# Create db and user
CREATE DATABASE myproject;
CREATE USER myuser WITH PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE myproject TO myuser;
```

---

## Connect From Python (psycopg2 + SQLAlchemy)

```python
# Install
pip install psycopg2-binary sqlalchemy asyncpg

# Sync connection (SQLAlchemy)
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://myuser:mypassword@localhost:5432/myproject"
engine = create_engine(DATABASE_URL)

# Async connection (FastAPI standard)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

ASYNC_DATABASE_URL = "postgresql+asyncpg://myuser:mypassword@localhost:5432/myproject"
async_engine = create_async_engine(ASYNC_DATABASE_URL)
```

---

## PostgreSQL vs MySQL — Quick Syntax Differences

```sql
-- PostgreSQL uses SERIAL or GENERATED ALWAYS AS IDENTITY
CREATE TABLE users (
    id SERIAL PRIMARY KEY,          -- auto-increment
    name VARCHAR(100) NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()   -- timezone-aware (use this always)
);

-- MySQL equivalent (for reference)
-- id INT AUTO_INCREMENT PRIMARY KEY
-- created_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

```sql
-- PostgreSQL JSONB (indexed JSON — very powerful)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    metadata JSONB                  -- use JSONB not JSON
);

-- Query inside JSONB
SELECT * FROM products WHERE metadata->>'category' = 'electronics';
SELECT * FROM products WHERE metadata @> '{"in_stock": true}';

-- Create index on JSONB field
CREATE INDEX idx_products_category ON products USING GIN (metadata);
```

---

## Order to Study PostgreSQL Files in This Folder

Study these files in this exact order:

### Fresher Level (start here)
```
01_postgresql_advanced.md        ← core PostgreSQL — tables, queries, constraints
31_normalization_denormalization.md  ← schema design basics
32_stored_procedures_triggers.md     ← server-side logic
```

### Junior Level
```
04_window_functions_cte.md       ← ROW_NUMBER, RANK, LEAD, LAG, WITH clause
21_isolation_levels_anomalies.md ← dirty read, phantom read, serializable
19_optimistic_pessimistic_locking.md ← concurrency control
20_advanced_indexing.md          ← BTree, GIN, BRIN, partial indexes
22_alembic_advanced.md           ← migrations with SQLAlchemy
```

### Mid Level
```
07_postgresql_internals.md       ← MVCC, VACUUM, WAL, query planner
13_postgresql_performance_tuning.md ← EXPLAIN ANALYZE, slow query log
11_pgbouncer_connection_pooling.md  ← connection pooling (mandatory for production)
10_postgresql_partitioning_sharding.md ← horizontal scaling
09_postgresql_ha_read_replicas.md    ← high availability setup
```

### Senior Level
```
25_cdc_debezium_postgresql.md    ← Change Data Capture
24_zero_downtime_migrations.md   ← deploy without downtime
26_expand_contract_migrations.md ← safe schema changes in production
12_backup_disaster_recovery.md   ← pg_dump, WAL archiving, PITR
29_storage_engines_btree_vs_lsm.md ← internals deep dive
30_newsql_distributed_sql.md     ← CockroachDB, TiDB, Spanner
```

### AI / Vector Workloads (Agentic AI track)
```
06_pgvector_schema_design.md     ← store embeddings in PostgreSQL
18_pgvector_ai_workloads.md      ← similarity search for RAG
28_vector_databases_comparison.md ← pgvector vs Pinecone vs Qdrant vs Weaviate
08_cap_theorem_db_selection.md   ← when to use which database
```

### Specialised
```
14_postgis_geospatial.md         ← location-based apps
15_postgresql_fulltext_search.md ← built-in search (alternative to Elasticsearch)
16_jsonb_queries_indexes.md      ← JSONB deep dive
17_timescaledb_timeseries.md     ← time series data
27_clickhouse_olap.md            ← analytics workloads
```

---

## Common Mistakes to Avoid

```python
# WRONG — VARCHAR with arbitrary limit (use TEXT in PostgreSQL)
name = Column(VARCHAR(255))   # pointless in PostgreSQL

# RIGHT — TEXT has same performance, no artificial limit
name = Column(Text, nullable=False)

# WRONG — use naive datetime
created_at = Column(DateTime)

# RIGHT — always timezone-aware
created_at = Column(DateTime(timezone=True), server_default=func.now())

# WRONG — N+1 query problem
users = session.query(User).all()
for user in users:
    print(user.orders)    # executes 1 query per user!

# RIGHT — eager load
users = session.query(User).options(joinedload(User.orders)).all()
```

---

## Quick Reference — Most Used Commands

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('myproject'));

-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('users'));

-- Running queries
SELECT pid, query, state, now() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Kill a query
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = 12345;

-- Explain a query
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';

-- Check indexes on a table
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users';

-- Check locks
SELECT * FROM pg_locks WHERE NOT granted;
```

---

## Environment Variable Setup (Python)

```bash
# .env file
DATABASE_URL=postgresql+asyncpg://myuser:mypassword@localhost:5432/myproject
```

```python
# settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str

    class Config:
        env_file = ".env"

settings = Settings()
```
