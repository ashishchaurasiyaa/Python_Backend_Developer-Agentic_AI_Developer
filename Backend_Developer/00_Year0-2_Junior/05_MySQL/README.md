# 🐬 MySQL

> **10 theory + 7 practical.** Bahut se India JDs me MySQL likha hota hai (PostgreSQL nahi) —
> concepts 80% same hain, par **InnoDB internals aur replication** ke jawab alag hote hain.
>
> PostgreSQL ka gehra version [`../04_Database_SQL/`](../04_Database_SQL/) me hai. Yahan MySQL-specific delta hai.

---

## 🔴 Pehle yeh 3

| # | Topic | Kyun |
|---|---|---|
| [06](theory/06_innodb_internals.md) | **InnoDB internals** — clustered index, buffer pool, redo/undo | MySQL ka sabse bada differentiator question |
| [02](theory/02_joins_indexes_transactions.md) | **Joins, indexes, transactions** | Base filter |
| [07](theory/07_replication_deep.md) | **Replication** — binlog, GTID, lag | "Read replica lag ho to kya karoge?" |

---

## 📚 Poori list

| # | Theory | Practical | Kya |
|---|---|---|---|
| 01 | [Basics, installation, CRUD](theory/01_basics_installation_crud.md) | [`01_basics_crud.py`](practical/01_basics_crud.py) | Setup, data types, CRUD |
| 02 | [Joins, indexes, transactions](theory/02_joins_indexes_transactions.md) | [`02_joins_indexes_transactions.py`](practical/02_joins_indexes_transactions.py) | Join types, index design, ACID |
| 03 | [Advanced optimization](theory/03_advanced_optimization.md) | [`03_advanced_optimization.py`](practical/03_advanced_optimization.py) | EXPLAIN, query rewriting, slow log |
| 04 | [SQLAlchemy + FastAPI](theory/04_sqlalchemy_fastapi.md) | [`04_sqlalchemy_fastapi.py`](practical/04_sqlalchemy_fastapi.py) | ORM wiring, session management |
| 05 | [ProxySQL + performance_schema](theory/05_proxysql_performance_schema.md) | [`05_proxysql_performance_schema.py`](practical/05_proxysql_performance_schema.py) | Pooling, routing, live diagnostics |
| 06 | [InnoDB internals](theory/06_innodb_internals.md) | [`06_innodb_internals.py`](practical/06_innodb_internals.py) | Clustered index, buffer pool, MVCC, locks |
| 07 | [Replication deep](theory/07_replication_deep.md) | [`07_replication_deep.py`](practical/07_replication_deep.py) | Binlog formats, GTID, semi-sync, lag |
| 08 | [Window functions + CTE + partitioning](theory/08_window_functions_cte_partitioning.md) | — | MySQL 8 features |
| 09 | [Galera / NDB clustering](theory/09_galera_ndb_clustering.md) | — | Multi-master, kab use karein |
| 10 | [Charset + collation](theory/10_charset_collation.md) | — | utf8 vs utf8mb4 — emoji/Hindi data ka classic bug |

> **08–10 ke practicals nahi hain** — ye concept/config files hain (SQL syntax + cluster decisions), Python code likhne layak nahi.

---

## ⚔️ MySQL vs PostgreSQL — interview me kya bolna hai

| Cheez | MySQL (InnoDB) | PostgreSQL |
|---|---|---|
| Primary index | **Clustered** — table hi index hai, PK order me data | Heap + separate index, PK bhi secondary jaisa |
| MVCC | Undo log me purani version | Table me hi dead tuples → **VACUUM** chahiye |
| Replication | Binlog (statement/row/mixed), GTID | WAL streaming, logical replication |
| JSON | JSON type, generated columns pe index | **JSONB** + GIN — clearly stronger |
| Extensions | Kam | pgvector/PostGIS/TimescaleDB — bada plus |

**Related:** [`../04_Database_SQL/`](../04_Database_SQL/) (PostgreSQL deep) · [SQL interview questions](../../03_Interview_AnyYear/02_Interview_Prep/08_sql_interview_questions.md) · [DevOps databases](../../../DevOps/15_Databases/)
