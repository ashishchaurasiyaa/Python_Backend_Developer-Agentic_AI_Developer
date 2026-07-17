# Cassandra / Astra DB as a Vector Store

**Agentic AI · Modern Topics | Senior AI Engineer**

> Chroma/pgvector already covered ([Level5](../Level5_RAG_Vector_Databases/03_vector_databases.md)). Yeh file = jab **massive scale + multi-region + high write throughput** chahiye.

---

## Quick Concepts

**WHAT:** Apache Cassandra (v5+) aur DataStax Astra DB native **vector search** support karte hain — `VECTOR<FLOAT, n>` column + ANN index.

**WHY on the stack diagram:** jo companies already Cassandra chala rahi hain, woh dedicated vector DB add karne se pehle usi me vectors daal deti hain — operational simplicity + linear scale.

---

## Architecture

```
        ┌──────────── Cassandra Ring (masterless / peer-to-peer) ────────┐
        │   Node A        Node B        Node C        Node D             │
        │     │             │             │             │                │
        │  row: id | text | metadata | VECTOR<FLOAT,768>                 │
        │                          │                                     │
        │                    SAI ANN index (Storage-Attached)           │
        │                    underlying: JVector (DiskANN-style graph)   │
        └────────────────────────────────────────────────────────────────┘
             ▲                                        ▲
     write (any node)                 query: ORDER BY embedding ANN OF ? LIMIT k
```

- **Masterless / peer-to-peer** — no leader, linear horizontal scale, multi-DC replication built-in
- **SAI (Storage-Attached Index)** does vector search; underlying **JVector** graph (DiskANN family)
- **Consistency tunable** per query (ONE / QUORUM / LOCAL_QUORUM)
- **Trade-off vs Chroma/pgvector:** operationally heavy (JVM cluster) — only worth it at real scale or if Cassandra already in stack

---

## CQL syntax

```sql
CREATE TABLE docs (
  id uuid PRIMARY KEY,
  body text,
  embedding VECTOR<FLOAT, 768>
);
CREATE CUSTOM INDEX ON docs(embedding) USING 'StorageAttachedIndex';

-- ANN similarity search
SELECT id, body
FROM docs
ORDER BY embedding ANN OF [0.1, 0.2, ...]
LIMIT 5;
```

---

## When to choose

```
Prototyping / single node ............... Chroma      (covered)
Postgres already in stack ............... pgvector    (covered)
Huge scale, multi-region, high write .... Cassandra / Astra
```

## Interview one-liners
- "Cassandra is masterless — every node accepts writes, so it scales writes linearly across regions."
- "Vector search rides on SAI + JVector; you query with `ORDER BY embedding ANN OF`."
- "I'd pick it over pgvector only when Cassandra is already the system of record or the vector count is huge."

See runnable example → [15_cassandra_vector_store_practical.py](15_cassandra_vector_store_practical.py)
