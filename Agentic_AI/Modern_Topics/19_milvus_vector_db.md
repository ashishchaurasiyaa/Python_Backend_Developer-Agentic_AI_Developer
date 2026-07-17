# Milvus — Cloud-Native Vector Database

**Agentic AI · Modern Topics | Senior AI Engineer**

> Chroma/pgvector/Qdrant covered ([Level5/03](../Level5_RAG_Vector_Databases/03_vector_databases.md)). Milvus was only a name-drop. Yeh file = purpose-built **billion-scale** vector DB.

---

## Quick Concepts

**WHAT:** Open-source, distributed vector database jo **billions of vectors** handle karne ke liye bana hai. Chroma "embedded/dev", Milvus "distributed/prod-at-scale".

**WHY on the diagram:** jab dataset itna bada ho ki single-node (Chroma/pgvector) fail ho jaaye — Milvus compute aur storage ko alag scale karta hai.

---

## Architecture (disaggregated)

```
        ┌──────────────── Milvus Cluster ────────────────┐
        │                                                 │
  SDK ─►│  Access Layer (proxy, load-balance)             │
        │        │                                        │
        │  Coordinator (root/query/data/index coords)     │
        │        │                                         │
        │  ┌───────────┐  ┌───────────┐  ┌─────────────┐   │
        │  │ Query Node│  │ Data Node │  │ Index Node  │   │  ◄─ scale independently
        │  └───────────┘  └───────────┘  └─────────────┘   │
        │        │                                         │
        │  Object storage (S3/MinIO) + etcd (meta) + MQ    │
        └─────────────────────────────────────────────────┘
```

- **Compute ≠ storage** — query/data/index nodes independently scale (unlike single-process Chroma)
- **Index types:** IVF_FLAT, HNSW, DiskANN, GPU (CAGRA) — tune recall vs speed vs RAM
- **Metrics:** L2, IP, COSINE
- **Deploy tiers:** Milvus Lite (pip, laptop) → Standalone (docker) → Distributed (k8s) → Zilliz Cloud (managed)

---

## Milvus vs the ones you know

| | Chroma | Qdrant | **Milvus** |
|---|--------|--------|-----------|
| Sweet spot | dev / small | mid, great DX | billion-scale prod |
| Scaling | embedded | single+cluster | fully distributed |
| GPU index | no | no | yes (CAGRA) |
| Ops cost | ~zero | low | higher (k8s) |

---

## When to choose
```
Prototyping ..................... Chroma
Great DX, mid-scale ............. Qdrant
Postgres in stack ............... pgvector
Billions of vectors, GPU ANN .... Milvus / Zilliz
```

## Interview one-liners
- "Milvus disaggregates compute and storage, so I scale query nodes and index nodes independently."
- "Start with Milvus Lite locally, same API scales to a distributed k8s cluster or Zilliz Cloud."
- "It supports GPU indexes (CAGRA) and DiskANN for billion-scale recall."

See runnable example → [19_milvus_vector_db_practical.py](19_milvus_vector_db_practical.py)
