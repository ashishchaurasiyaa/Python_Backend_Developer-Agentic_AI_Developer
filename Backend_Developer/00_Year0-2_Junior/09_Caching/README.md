# ⚡ Caching

> **9 theory + 9 practical (perfect 1:1).** Caching sabse zyada poocha jane wala scaling topic hai —
> aur sabse zyada galat samjha jane wala. "Cache laga do" jawab nahi hai; **invalidation** asli sawal hai.

---

## 🔴 Pehle yeh 3

| # | Topic | Classic question |
|---|---|---|
| [01](theory/01_caching_patterns.md) | **Caching patterns** | "Cache-aside vs read-through vs write-behind?" |
| [03](theory/03_cache_stampede_cold_start.md) | **Stampede + cold start** | "Cache expire hote hi 10k requests DB pe — kya karoge?" |
| [02](theory/02_redlock_distributed_locks.md) | **Redlock / distributed locks** | "Multi-server pe ek hi kaam do baar na ho" |

---

## 📚 Poori list

| # | Theory | Practical | Kya |
|---|---|---|---|
| 01 | [Caching patterns](theory/01_caching_patterns.md) | [`01_caching_patterns.py`](practical/01_caching_patterns.py) | Cache-aside, read/write-through, write-behind, TTL strategy |
| 02 | [Redlock distributed locks](theory/02_redlock_distributed_locks.md) | [`02_redlock_distributed_locks.py`](practical/02_redlock_distributed_locks.py) | Quorum, fencing tokens, clock drift |
| 03 | [Cache stampede + cold start](theory/03_cache_stampede_cold_start.md) | [`03_cache_stampede_cold_start.py`](practical/03_cache_stampede_cold_start.py) | Thundering herd, lock/early-expiry, jitter |
| 04 | [Memory + eviction policies](theory/04_memory_eviction_policies.md) | [`04_memory_eviction_policies.py`](practical/04_memory_eviction_policies.py) | LRU/LFU/TTL, maxmemory-policy |
| 05 | [Redis Big-O complexity](theory/05_redis_bigO_complexity.md) | [`05_redis_bigO_complexity.py`](practical/05_redis_bigO_complexity.py) | Kaunsa command O(N) hai — prod me kya na chalao |
| 06 | [Semantic caching for LLMs](theory/06_semantic_caching_llm.md) | [`06_semantic_caching_llm.py`](practical/06_semantic_caching_llm.py) | Embedding-similarity cache, LLM cost bachao |
| 07 | [Multi-level caching](theory/07_multi_level_caching.md) | [`07_multi_level_caching.py`](practical/07_multi_level_caching.py) | L1 in-process + L2 Redis + CDN, coherence |
| 08 | [Cache warming strategies](theory/08_cache_warming_strategies.md) | [`08_cache_warming_strategies.py`](practical/08_cache_warming_strategies.py) | Preload, deploy ke baad cold cache |
| 09 | [Negative caching](theory/09_negative_caching.md) | [`09_negative_caching.py`](practical/09_negative_caching.py) | "Not found" cache karo, penetration attack rok do |

---

> **Redis commands + labs** chahiye to [`../08_Redis/`](../08_Redis/) jao — wahan runnable labs hain.
> Yeh folder **patterns aur decisions** ke liye hai (kya cache karein, kab invalidate karein), Redis API ke liye nahi.

**Related:** [`08_Redis/`](../08_Redis/) · [DevOps caching](../../../DevOps/17_Caching/) · [HLD_Theory caching](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/) · [Agentic semantic caching](../../../Agentic_AI/Level5_RAG_Vector_Databases/)
