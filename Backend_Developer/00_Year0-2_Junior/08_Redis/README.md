# 🔴 Redis — Basics to Advanced

> **19 theory + 18 practical + 5 runnable labs.** Redis har backend interview me aata hai —
> caching se shuru hota hai, distributed locks pe khatam hota hai.
>
> **Padhne ka tarika:** theory kholo → uska `practical/` file chalao → phir `labs/` me khud likho.

---

## 🔴 Interview ke liye pehle yeh 5

| # | Topic | Classic question |
|---|---|---|
| [14](theory/14_caching_patterns.md) | **Caching patterns** | "Cache-aside vs write-through — kaunsa kab?" |
| [15](theory/15_rate_limiting.md) | **Rate limiting** | "Sliding window rate limiter Redis me kaise?" |
| [13](theory/13_transactions_watch.md) | **Transactions + WATCH** | "Redis me atomic transfer kaise karoge?" |
| [19](theory/19_redlock_distributed_locks.md) | **Redlock / distributed locks** | "Do server ek hi order process na karein — kaise?" |
| [09](theory/09_persistence_memory.md) | **Persistence (RDB/AOF) + eviction** | "Redis restart pe data jayega?" |

---

## 📚 Poori list

### Core
| # | Theory | Practical |
|---|---|---|
| 01 | [Basics, installation, CLI](theory/01_basics_installation_cli.md) | [`01_basics_cli_keys.py`](practical/01_basics_cli_keys.py) |
| 16 | [Core data structures](theory/16_core_data_structures.md) | *(theory-only — jaan-boojh ke)* |
| 02 | [Pipeline + connection pool](theory/02_pipeline_connection_pool.md) | [`02_pipeline_pool_session.py`](practical/02_pipeline_pool_session.py) |
| 11 | [Bitmaps + BITFIELD](theory/11_bitmaps_bitfield.md) | [`11_bitmaps_bitfield.py`](practical/11_bitmaps_bitfield.py) |
| 03 | [Geo, HyperLogLog, JSON](theory/03_geo_hyperloglog_json.md) | [`03_geo_hyperloglog_json.py`](practical/03_geo_hyperloglog_json.py) |

### Patterns 🔴 (interview ka core)
| # | Theory | Practical | Lab |
|---|---|---|---|
| 14 | [Caching patterns](theory/14_caching_patterns.md) | [`14_caching_patterns.py`](practical/14_caching_patterns.py) | [Lab 1](labs/01_cache_aside.py) · [Lab 2](labs/02_cache_stampede_lock.py) |
| 15 | [Rate limiting](theory/15_rate_limiting.md) | [`15_rate_limiting.py`](practical/15_rate_limiting.py) | [Lab 4](labs/04_sliding_window_rate_limiter.py) |
| 13 | [Transactions + WATCH](theory/13_transactions_watch.md) | [`13_transactions_watch.py`](practical/13_transactions_watch.py) | [Lab 3](labs/03_watch_atomic_transfer.py) |
| 19 | [Redlock distributed locks](theory/19_redlock_distributed_locks.md) | [`19_redlock_distributed_locks.py`](practical/19_redlock_distributed_locks.py) | [Lab 5](labs/05_redlock_quorum.py) |
| 08 | [Lua scripting](theory/08_lua_scripting.md) | [`08_lua_scripting.py`](practical/08_lua_scripting.py) | — |

### Messaging
| # | Theory | Practical |
|---|---|---|
| 10 | [Pub/Sub fundamentals](theory/10_pubsub_fundamentals.md) | [`10_pubsub_fundamentals.py`](practical/10_pubsub_fundamentals.py) |
| 05 | [Streams + consumer groups](theory/05_streams_consumer_groups.md) | [`05_streams_consumer_groups.py`](practical/05_streams_consumer_groups.py) |

### Production — HA, scale, security
| # | Theory | Practical |
|---|---|---|
| 09 | [Persistence + memory](theory/09_persistence_memory.md) | [`09_persistence_memory.py`](practical/09_persistence_memory.py) |
| 17 | [Replication fundamentals](theory/17_replication_fundamentals.md) | [`17_replication_fundamentals.py`](practical/17_replication_fundamentals.py) |
| 07 | [Sentinel HA](theory/07_sentinel_ha.md) | [`07_sentinel_ha.py`](practical/07_sentinel_ha.py) |
| 06 | [Cluster mode](theory/06_cluster_mode.md) | [`06_cluster_mode.py`](practical/06_cluster_mode.py) |
| 18 | [ACL + security](theory/18_acl_security.md) | [`18_acl_security.py`](practical/18_acl_security.py) |
| 12 | [Monitoring + keyspace notifications](theory/12_monitoring_keyspace_clientside.md) | [`12_monitoring_keyspace_clientside.py`](practical/12_monitoring_keyspace_clientside.py) |

### AI / search
| # | Theory | Practical |
|---|---|---|
| 04 | [Vector search + FastAPI](theory/04_vector_search_fastapi.md) | [`04_vector_search_semantic_cache.py`](practical/04_vector_search_semantic_cache.py) |

---

## 🧪 Labs — yahan haath chalega

[`labs/`](labs/) me 5 TODO-stub exercises hain + [`docker-compose.yml`](labs/docker-compose.yml) (Redis khada karne ke liye).
Theory padhna easy hai, **labs karna asli kaam hai** — [labs/README.md](labs/README.md) padho.

```bash
cd labs && docker compose up -d && python 01_cache_aside.py
```

---

## 📦 `*.json` exercise files (folder root me)

`Strings_Exercises.json`, `Hashes_Exercises.json`, `Lists_Exercises.json`, `Sets_Exercises.json`, `SortedSets_Exercises.json`, `Basic_Strings_-_Completed.json`

Ye **Redis Insight / Redis notebook** ke export hain — Redis Insight me import karke command-by-command practice kar sakte ho.
Sirf data-structure drilling ke liye hain; concepts upar wali theory files me hain.

**Related:** [`09_Caching/`](../09_Caching/) (caching theory ka gehra version) · [`04_Database_SQL/`](../04_Database_SQL/) · [Mid-track Celery](../../01_Year3-4_Mid/09_Celery/) · [DevOps caching](../../../DevOps/17_Caching/)
