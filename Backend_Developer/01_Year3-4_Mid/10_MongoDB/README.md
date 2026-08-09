# 🍃 MongoDB

> **10 theory + 9 practical.** Document DB ka pattern-sense — "kab MongoDB, kab Postgres" ka jawab.
> Cosmos DB (Azure) bhi yahin hai, kyunki uska Mongo API wire-compatible hai.

---

## 🔴 Pehle yeh 4

| # | Topic | Classic question |
|---|---|---|
| [08](theory/08_data_modeling_patterns.md) | **Data modeling** | "Embed karoge ya reference?" 🔥 sabse important |
| [02](theory/02_aggregation_indexes.md) | **Aggregation + indexes** | Pipeline stages, compound index order |
| [04](theory/04_sharding_aggregation_advanced.md) | **Sharding + shard keys** | "Galat shard key chuna to kya hoga?" |
| [05](theory/05_transactions_deep.md) | **Transactions** | "Mongo me ACID hai?" — replica set requirement |

---

## 📚 Poori list

| # | Theory | Practical |
|---|---|---|
| [01](theory/01_basics_installation_crud.md) | Basics, CRUD, PyMongo | [`01_pymongo_basics.py`](practical/01_pymongo_basics.py) |
| [02](theory/02_aggregation_indexes.md) 🔴 | Aggregation pipelines + indexes | [`02_aggregation_pipeline.py`](practical/02_aggregation_pipeline.py) |
| [03](theory/03_advanced_motor_fastapi.md) | Motor async + FastAPI | [`03_motor_async_fastapi.py`](practical/03_motor_async_fastapi.py) |
| [04](theory/04_sharding_aggregation_advanced.md) 🔴 | Sharding + advanced aggregation | [`04_...py`](practical/04_sharding_aggregation_advanced.py) |
| [05](theory/05_transactions_deep.md) 🔴 | Multi-document transactions | [`05_transactions_deep.py`](practical/05_transactions_deep.py) |
| [06](theory/06_replication_read_preferences.md) | Replication + read preferences | [`06_...py`](practical/06_replication_read_preferences.py) |
| [07](theory/07_change_streams.md) | Change streams (CDC) | [`07_change_streams.py`](practical/07_change_streams.py) |
| [08](theory/08_data_modeling_patterns.md) 🔴 | Data modeling patterns | [`08_...py`](practical/08_data_modeling_patterns.py) |
| [09](theory/09_gridfs.md) | GridFS (large files) | — |
| [10](theory/10_cosmos_db_azure.md) | **Cosmos DB (Azure)** — RU/s, partition keys, 5 consistency levels, Mongo-API gotchas | [`09_cosmos_db_emulator.py`](practical/09_cosmos_db_emulator.py) |

---

## 🐳 Local setup

`practical/docker-compose.yml` ek **replica set** (`--replSet rs0`) khada karta hai — single node, par replica set mode me.
Kyun? Transactions aur change streams standalone mongod pe **kaam hi nahi karte**. File ke comments me poora explanation hai.

```bash
cd practical && docker compose up -d
```

---

## ⚔️ MongoDB vs PostgreSQL — interview ka jawab

| Chuno | Kab |
|---|---|
| **MongoDB** | Schema evolve ho raha hai, documents self-contained hain, horizontal scale chahiye, nested/varied data |
| **PostgreSQL** | Relations + joins chahiye, strong transactional guarantees, reporting/analytics queries — *aur JSONB dono de deta hai* |

**Honest line:** *"2026 me Postgres ka JSONB bahut sa MongoDB use-case cover kar leta hai. MongoDB tab chunta hoon jab scale-out aur document model dono chahiye."*

**Related:** [11_Elasticsearch](../11_Elasticsearch/README.md) · [04_Database_SQL](../../00_Year0-2_Junior/04_Database_SQL/README.md) · [Azure prep](../../../Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md)
