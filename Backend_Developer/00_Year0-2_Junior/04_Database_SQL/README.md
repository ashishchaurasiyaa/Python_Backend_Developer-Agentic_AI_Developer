# 🗄️ Database / SQL — PostgreSQL Deep Dive

> **32 theory + 23 practical.** Naam "Junior" folder me hai, par content **senior-level** hai —
> PostgreSQL internals, MVCC, partitioning, CDC, zero-downtime migrations. Interview me DB round yahin se nikalta hai.
>
> Theory files is folder ke **root** me hain, code `practical/` me.
> Numbering me 02 aur 05 nahi hain (kabhi bane hi nahi) — koi file missing nahi hai.

---

## 🔴 Interview ke liye pehle yeh 6 (agar time kam hai)

| # | Topic | Kyun |
|---|---|---|
| [07](07_postgresql_internals.md) | **MVCC, WAL, VACUUM** | "Postgres update kaise karta hai" — senior filter question |
| [21](21_isolation_levels_anomalies.md) | **Isolation levels + anomalies** | Dirty/non-repeatable/phantom read — guaranteed poocha jata hai |
| [20](20_advanced_indexing.md) | **Index internals** (B-Tree/GIN/GiST/BRIN) | "Index kab kaam nahi karta" |
| [19](19_optimistic_pessimistic_locking.md) | **Locking** + `SELECT FOR UPDATE` | Race condition scenario ka jawab |
| [13](13_postgresql_performance_tuning.md) | **EXPLAIN ANALYZE + tuning** | Slow query debug karke dikhana padta hai |
| [11](11_pgbouncer_connection_pooling.md) | **pgBouncer / pooling** | "1000 concurrent users, 100 DB connections" |

---

## 📚 Poori list

### Core + Query
| # | Theory | Practical |
|---|---|---|
| 01 | [PostgreSQL advanced](01_postgresql_advanced.md) | [`01_postgresql_practical.py`](practical/01_postgresql_practical.py) |
| 03 | [Soft deletes + SQLAlchemy async](03_soft_deletes_sqlalchemy_async.md) | [`04_sqlalchemy_async_practical.py`](practical/04_sqlalchemy_async_practical.py) |
| 04 | [Window functions + CTE](04_window_functions_cte.md) | — |
| 31 | [Normalization / denormalization](31_normalization_denormalization.md) | — |
| 32 | [Stored procedures + triggers](32_stored_procedures_triggers.md) | — |
| 34 | [Savepoints + nested transactions](34_savepoints_nested_transactions.md) | — |

### Internals + Performance 🔴
| # | Theory | Practical |
|---|---|---|
| 07 | [PostgreSQL internals (MVCC/WAL/VACUUM)](07_postgresql_internals.md) | — |
| 13 | [Performance tuning](13_postgresql_performance_tuning.md) | [`13_...py`](practical/13_postgresql_performance_tuning.py) |
| 19 | [Optimistic vs pessimistic locking](19_optimistic_pessimistic_locking.md) | [`19_...py`](practical/19_optimistic_pessimistic_locking.py) |
| 20 | [Advanced indexing](20_advanced_indexing.md) | [`20_...py`](practical/20_advanced_indexing.py) |
| 21 | [Isolation levels + anomalies](21_isolation_levels_anomalies.md) | [`21_...py`](practical/21_isolation_levels_anomalies.py) |
| 29 | [Storage engines — B-Tree vs LSM](29_storage_engines_btree_vs_lsm.md) | — |

### Scale — HA, partitioning, pooling
| # | Theory | Practical |
|---|---|---|
| 09 | [HA + read replicas](09_postgresql_ha_read_replicas.md) | [`09_...py`](practical/09_postgresql_ha_read_replicas.py) |
| 10 | [Partitioning + sharding](10_postgresql_partitioning_sharding.md) | [`10_...py`](practical/10_postgresql_partitioning_sharding.py) |
| 11 | [pgBouncer connection pooling](11_pgbouncer_connection_pooling.md) | [`11_...py`](practical/11_pgbouncer_connection_pooling.py) |
| 12 | [Backup + disaster recovery](12_backup_disaster_recovery.md) | [`12_...py`](practical/12_backup_disaster_recovery.py) |
| 08 | [CAP theorem + DB selection](08_cap_theorem_db_selection.md) | — |
| 30 | [NewSQL / distributed SQL](30_newsql_distributed_sql.md) | — |

### Migrations 🔴 (production ka asli kaam)
| # | Theory | Practical |
|---|---|---|
| 22 | [Alembic advanced](22_alembic_advanced.md) | [`22_...py`](practical/22_alembic_advanced.py) · [`05_alembic_practical.py`](practical/05_alembic_practical.py) |
| 23 | [Django migrations in production](23_django_migrations_production.md) | [`23_...py`](practical/23_django_migrations_production.py) |
| 24 | [Zero-downtime migrations](24_zero_downtime_migrations.md) | [`24_...py`](practical/24_zero_downtime_migrations.py) |
| 26 | [Expand-contract pattern](26_expand_contract_migrations.md) | [`26_...py`](practical/26_expand_contract_migrations.py) |
| 25 | [CDC with Debezium](25_cdc_debezium_postgresql.md) | [`25_...py`](practical/25_cdc_debezium_postgresql.py) |

### Specialized workloads
| # | Theory | Practical |
|---|---|---|
| 14 | [PostGIS geospatial](14_postgis_geospatial.md) | [`14_...py`](practical/14_postgis_geospatial.py) |
| 15 | [Full-text search](15_postgresql_fulltext_search.md) | [`15_...py`](practical/15_postgresql_fulltext_search.py) |
| 16 | [JSONB queries + indexes](16_jsonb_queries_indexes.md) | [`16_...py`](practical/16_jsonb_queries_indexes.py) |
| 17 | [TimescaleDB time-series](17_timescaledb_timeseries.md) | [`17_...py`](practical/17_timescaledb_timeseries.py) |
| 27 | [ClickHouse OLAP](27_clickhouse_olap.md) | — |
| 33 | [Foreign data wrappers](33_foreign_data_wrappers.md) | — |

### AI / vector workloads
| # | Theory | Practical |
|---|---|---|
| 06 | [pgvector schema design](06_pgvector_schema_design.md) | [`03_pgvector_practical.py`](practical/03_pgvector_practical.py) |
| 18 | [pgvector for AI workloads](18_pgvector_ai_workloads.md) | [`18_...py`](practical/18_pgvector_ai_workloads.py) |
| 28 | [Vector DB comparison](28_vector_databases_comparison.md) | — |

---

## 📝 Notes

- **Theory 27–34 ke practicals nahi hain** — jaan-boojh ke, yeh comparison/concept files hain (ClickHouse, NewSQL, FDW, normalization). Code likhne layak kuch nahi hai.
- [`practical/02_redis_practical.py`](practical/02_redis_practical.py) is folder me **galat jagah** hai (Redis ka asli ghar [`../08_Redis/`](../08_Redis/) hai). Historical reasons se yahan pada hai — Redis padhna ho to wahan jao.
- **SQL query-writing drill karni hai?** → [`03_Interview_AnyYear/02_Interview_Prep/08_sql_interview_questions.md`](../../03_Interview_AnyYear/02_Interview_Prep/08_sql_interview_questions.md) (~46 LeetCode-style problems solutions ke saath).

**Related:** [`05_MySQL/`](../05_MySQL/) · [`09_Caching/`](../09_Caching/) · [`08_Redis/`](../08_Redis/) · [Mid-track MongoDB](../../01_Year3-4_Mid/10_MongoDB/) · [HLD_Theory DB sections](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/)
