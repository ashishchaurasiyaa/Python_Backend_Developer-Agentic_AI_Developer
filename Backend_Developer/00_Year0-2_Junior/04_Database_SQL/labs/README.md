# Database SQL — Hands-On Labs

> [`../practical/`](../practical/) has reference files. This folder is for **doing**: TODO stubs → fill in → run → PASS/FAIL.

## Setup

```bash
# No pip install needed — all labs use Python's built-in sqlite3
python --version   # 3.8+ required; 3.10+ for window functions in SQLite 3.35+
```

No Docker, no external services. Every lab runs with zero dependencies.

## Labs

| # | Lab | Key Concepts | Run |
|---|-----|--------------|-----|
| 1 | [lab_01_joins_subqueries_cte](lab_01_joins_subqueries_cte.py) | INNER/LEFT/Self JOIN, subquery, EXISTS, CTE, correlated subquery | `python lab_01_*.py` |
| 2 | [lab_02_window_functions](lab_02_window_functions.py) | ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, SUM OVER, PARTITION BY | `python lab_02_*.py` |
| 3 | [lab_03_indexing_query_plan](lab_03_indexing_query_plan.py) | Composite index, partial index, covering index, EXPLAIN QUERY PLAN | `python lab_03_*.py` |
| 4 | [lab_04_transactions_isolation](lab_04_transactions_isolation.py) | ACID, atomicity demo, savepoints, read isolation, lost update | `python lab_04_*.py` |
| 5 | [lab_05_locks_race_conditions](lab_05_locks_race_conditions.py) | Pessimistic lock, optimistic+version, retry, oversell race condition | `python lab_05_*.py` |

## Protocol

```
1. Open the lab file — read module docstring ARCHITECTURE section
2. Fill in each TODO (hints are in the docstring above each function)
3. Run: python lab_0N_*.py
   ✅ → answer SOCH questions aloud → move to next lab
   ❌ → read the FAIL message, fix the TODO, rerun
```

## SQLite vs PostgreSQL

These labs use SQLite (built-in, no install) to teach the concepts. Key differences to know for interviews:

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| SELECT FOR UPDATE | Not supported | Full row-level locking |
| EXPLAIN output | `EXPLAIN QUERY PLAN` — simpler | `EXPLAIN (ANALYZE, BUFFERS)` — detailed cost |
| Isolation levels | DEFERRED/IMMEDIATE/EXCLUSIVE | READ COMMITTED / REPEATABLE READ / SERIALIZABLE |
| Window functions | Supported (SQLite 3.25+) | Full support |
| Partial indexes | Supported | Full support + GIN/GiST |
| SKIP LOCKED | Not supported | Fully supported (queue pattern) |

The SQL concepts — JOIN logic, index column order, transaction atomicity, optimistic locking — are identical across both databases.
