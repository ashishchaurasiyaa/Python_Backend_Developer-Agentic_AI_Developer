# Redis Labs — Runnable Exercises

> `../practical/` me production-quality **reference modules** hain (padhne ke liye). Yeh folder **chalane** ke liye hai: real Redis, TODO stubs jo tum bharoge, aur har lab ka apna verification step.

## Setup (ek baar)

```bash
cd Backend_Developer/00_Year0-2_Junior/08_Redis/labs
docker compose up -d                    # single redis:7-alpine instance
docker compose ps                       # redis healthy hona chahiye (~5s)
pip install "redis[hiredis]>=5.0"

# UI (optional): http://localhost:8081
```

Cleanup: `docker compose down -v`

## Labs

| # | Lab | Kya sikhata hai | Verify kaise |
|---|---|---|---|
| 1 | [01_cache_aside](01_cache_aside.py) | Cache-aside get-or-set, TTL populate | 2nd call cache se aaye, `db_fetch()` sirf 1 baar chale |
| 2 | [02_cache_stampede_lock](02_cache_stampede_lock.py) | `SET NX PX` lock se stampede protection | 20 concurrent threads, phir bhi `db_fetch()` sirf 1 baar chale |
| 3 | [03_watch_atomic_transfer](03_watch_atomic_transfer.py) | WATCH/MULTI/EXEC optimistic locking + retry | Forced `WatchError` ke baad bhi transfer sum conserved rahe |
| 4 | [04_sliding_window_rate_limiter](04_sliding_window_rate_limiter.py) | ZADD/ZREMRANGEBYSCORE/ZCARD sliding-window-log | Burst me exactly N allowed, window slide ke baad naya request allowed |
| 5 | [05_redlock_quorum](05_redlock_quorum.py) | Majority-acquire quorum logic (local simulation) | 2/5 nodes down → still acquires; 3/5 down → correctly fails |

Har file me **TODO** blocks hain — pehle khud bharo, phir `python 0N_....py` chalao. Har lab apna verification khud print karta hai (✅/❌).

Yeh labs `../../09_Caching/theory/` (cache-aside, stampede protection, Redlock) me documented concepts ko bhi hands-on exercise karte hain — us theory ko yahan duplicate nahi kiya gaya, sirf reference hai.

## Protocol

```
1. Lab file kholo, docstring me OBJECTIVE + TASK padho
2. TODO bharo (reference: ../practical/ aur ../theory/)
3. Chalao → ✅ mile to agla lab; ❌ mile to output padho, fix karo
4. Lab ke end me "SOCH" section hota hai — usme diye sawaalon ka
   jawab bolke do. Interview me yahi poocha jaata hai, code nahi.
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionError: Error 61 connecting to localhost:6379` | `docker compose ps` — redis healthy hai? Ya local `redis-server` chala lo |
| Lab 2 me `db_fetch()` 1 se zyada baar chal raha | TODO 1 check karo — `SET NX PX` lock sahi se acquire nahi ho raha |
| Lab 3 me sum conserve nahi ho raha | TODO 3 check karo — `WatchError` pe `continue` ki jagah loop return kar raha hoga |
| Lab 4 me burst ke baad bhi sab allowed | TODO 1 check karo — purani entries `ZREMRANGEBYSCORE` se hat nahi rahi |
| Purana data interfere kar raha | `docker compose down -v` (volume delete) ya lab ke `main()` me `_cleanup`/`delete` calls dekho |

---

**Related:** [theory files](../theory/) · [reference modules](../practical/) · [Caching theory](../../09_Caching/theory/) · [Kafka labs](../../../01_Year3-4_Mid/07_Kafka/labs/)
