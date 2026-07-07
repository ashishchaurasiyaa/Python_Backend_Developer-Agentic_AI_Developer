# PostgreSQL Foreign Data Wrappers (FDW)

## Why It Matters

Most backend systems eventually hit "I need to query data that lives in a
different database" — a legacy MySQL system, a partner's Postgres instance,
even a CSV file. FDW is Postgres's built-in answer: query external data
sources using normal SQL, no ETL pipeline required for simple cases.

Senior interview: "Marketing team's data lives in a separate Postgres
instance. You need to JOIN it with your orders table for a one-off report.
Options?" → `postgres_fdw` for a quick federated query, vs building a full
ETL/replication pipeline if it becomes a recurring need.

---

## Core Concept

```
Your Postgres DB                    Remote Postgres DB
┌─────────────────┐                 ┌──────────────────┐
│  orders table    │                 │  campaigns table  │
│                  │   FDW           │                   │
│  foreign table:  │ ──────────────► │  (actual data     │
│  campaigns       │  (queries       │   lives here)     │
│  (looks local,   │   pushed over   │                   │
│   isn't)         │   the wire)     │                   │
└─────────────────┘                 └──────────────────┘
```

A foreign table looks like a normal table to your queries — Postgres pushes
the query (or parts of it) to the remote server and pulls back only the
result rows.

---

## Setup — `postgres_fdw` (Postgres-to-Postgres)

```sql
-- 1. Enable the extension
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- 2. Define the remote server connection
CREATE SERVER campaigns_server
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'marketing-db.internal', port '5432', dbname 'marketing');

-- 3. Map local role to remote credentials
CREATE USER MAPPING FOR CURRENT_USER
    SERVER campaigns_server
    OPTIONS (user 'readonly_user', password 'secret');

-- 4. Import the remote schema (or declare tables manually)
IMPORT FOREIGN SCHEMA public
    LIMIT TO (campaigns)
    FROM SERVER campaigns_server
    INTO public;

-- 5. Query it like a normal table
SELECT o.id, o.total, c.campaign_name
FROM orders o
JOIN campaigns c ON o.campaign_id = c.id
WHERE c.campaign_name = 'summer_sale';
```

### Other common wrappers

| FDW | Connects to |
|---|---|
| `postgres_fdw` | Another PostgreSQL instance |
| `mysql_fdw` | MySQL/MariaDB |
| `file_fdw` | Flat files (CSV) as if they were tables |
| `multicorn` | Python framework to write a custom FDW for anything (REST API, MongoDB, etc.) |

---

## Query Pushdown (the performance detail worth knowing)

```sql
-- Without pushdown: pulls the ENTIRE remote table over the network,
-- then filters locally — slow for large remote tables.

-- With pushdown (postgres_fdw supports this): the WHERE clause is sent
-- to the remote server, only matching rows cross the network.
EXPLAIN VERBOSE
SELECT * FROM campaigns WHERE campaign_name = 'summer_sale';
-- Look for "Remote SQL" in the plan — confirms the filter ran remotely
```

`postgres_fdw` pushes down `WHERE`, `JOIN`, `ORDER BY`, and aggregate
functions where possible (Postgres 10+) — this is why it's the recommended
FDW over older/simpler wrappers that pull everything and filter locally.

---

## When to use FDW vs alternatives

| Need | Use |
|---|---|
| One-off report, occasional cross-DB query | **FDW** — quick, no infra to stand up |
| Frequent cross-DB queries, need it fast | **Replication/CDC** into your own DB — FDW still round-trips over network per query |
| Data integration across many systems | **ETL pipeline / data warehouse** — FDW isn't built for heavy transform logic |
| Cross-DB transactions | FDW does NOT give you distributed transactions — writes through FDW are best-effort, not ACID across the two databases |

---

## Interview Q&A

**Q: Is querying through FDW as fast as a local JOIN?**
A: No — it's fundamentally a network round-trip per remote fetch, even with
pushdown. Fine for occasional/reporting queries; wrong choice for a hot path
serving user-facing requests.

**Q: Can you write to a foreign table through FDW?**
A: Yes (`postgres_fdw` supports `INSERT`/`UPDATE`/`DELETE` on foreign tables
since Postgres 9.3+), but there's no two-phase commit — a local+remote write
in one transaction isn't atomic across both databases.

**Q: FDW vs Debezium/CDC — when would you pick FDW instead?**
A: FDW for ad-hoc/infrequent federated queries with no pipeline to maintain.
CDC ([25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md)) when you
need continuous, low-latency sync of changes into your own database for
frequent local queries.

---

Related: [25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md),
[34_savepoints_nested_transactions.md](34_savepoints_nested_transactions.md).
