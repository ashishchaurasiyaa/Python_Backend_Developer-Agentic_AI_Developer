# `async def` vs `def` — Event Loop vs Threadpool (THE Classic FastAPI Trap)

> **Interview angle:** "FastAPI me `def` aur `async def` endpoint me kya farak hai? Async endpoint slow kyun ho gaya?" — yeh question 10 me se 8 FastAPI interviews me aata hai, aur 10 me se 7 log galat jawab dete hain.

**One-line truth:** `async def` likhne se code fast nahi hota. Galat jagah `async def` likhne se **poori app freeze** ho jaati hai.

---

## 1. Core Model — FastAPI/Starlette ke 2 Execution Paths

FastAPI (actually Starlette) har endpoint ko dekh kar decide karta hai — `inspect.iscoroutinefunction()` se:

1. **`async def` endpoint** → directly **event loop** pe run hota hai (main thread)
2. **`def` (sync) endpoint** → **anyio worker threadpool** me offload hota hai (default limit = **40 threads**)

```
                         ┌─────────────────────────────────────────┐
                         │            Uvicorn Worker                │
                         │         (1 process, 1 event loop)        │
   Request A ──────────► │                                          │
   Request B ──────────► │   ┌──────────────────────────────┐       │
   Request C ──────────► │   │     EVENT LOOP (main thread) │       │
                         │   │                              │       │
                         │   │  async def endpoint?         │       │
                         │   │  ──► coroutine yahi chalega  │       │
                         │   │      await pe SWITCH karega  │       │
                         │   │      (cooperative scheduling)│       │
                         │   └──────────┬───────────────────┘       │
                         │              │ def (sync) endpoint?      │
                         │              ▼                           │
                         │   ┌──────────────────────────────┐       │
                         │   │   anyio THREADPOOL           │       │
                         │   │   [T1][T2][T3]....[T40]      │       │
                         │   │   sync function yahan chalega│       │
                         │   │   block kare toh sirf apna   │       │
                         │   │   thread block hota hai      │       │
                         │   └──────────────────────────────┘       │
                         └─────────────────────────────────────────┘
```

### Dono paths ka flow side-by-side

```
async def path:                          def (sync) path:
─────────────────                        ─────────────────
Request aaya                             Request aaya
  │                                        │
  ▼                                        ▼
Event loop coroutine schedule karta      Starlette: run_in_threadpool(endpoint)
  │                                        │
  ▼                                        ▼
Code chalta hai TILL first `await`       anyio threadpool se 1 thread liya
  │                                        │
  ▼                                        ▼
`await` pe loop DOOSRI request           Thread pe sync code chalta hai
pick kar leta hai (concurrency!)         (block kare toh sirf yeh thread ruka)
  │                                        │
  ▼                                        ▼
I/O complete → coroutine resume          Thread done → result event loop ko wapas
  │                                        │
  ▼                                        ▼
Response                                 Response
```

**Key insight:** Event loop ek hi thread hai. Woh tabhi doosri request pe switch kar sakta hai jab current coroutine **`await` pe pahunchti hai**. `await` nahi aaya = switch nahi hoga = sab ruk gaya.

---

## 2. THE TRAP — `async def` me Blocking Call = Poora Event Loop Frozen

### Disaster code (production me bahut common)

```python
import time
import requests  # sync library!
from fastapi import FastAPI

app = FastAPI()

# ❌ DISASTER: async def + blocking call
@app.get("/disaster")
async def disaster():
    time.sleep(5)               # event loop 5 sec ke liye DEAD
    # ya: requests.get(...)     # same problem — sync HTTP call
    # ya: session.query(...)    # sync SQLAlchemy — same problem
    return {"status": "done"}

# ✅ SAFE: sync def + same blocking call
@app.get("/safe")
def safe():
    time.sleep(5)               # sirf 1 threadpool thread blocked, 39 free
    return {"status": "done"}

# ✅ BEST: async def + async-native sleep
@app.get("/best")
async def best():
    import asyncio
    await asyncio.sleep(5)      # loop free hai, hazaron requests parallel
    return {"status": "done"}
```

### Trap demonstrate karo — khud test karke dekho

```bash
# Terminal 1: server chalao
uvicorn main:app

# Terminal 2: /disaster pe 10 concurrent requests
# (httpie/curl loop ya `hey -n 10 -c 10 http://localhost:8000/disaster`)
```

**Result:**

| Endpoint | 10 concurrent requests, total time | Kyun |
|---|---|---|
| `/disaster` | ~**50 sec** (serial!) | Event loop ek hi hai — har `time.sleep(5)` loop freeze karta hai, requests EK-EK karke process hui |
| `/safe` | ~**5 sec** (parallel) | 10 threads ne parallel me sleep kiya, 30 abhi bhi free the |
| `/best` | ~**5 sec** (parallel) | Loop ne 10 coroutines interleave kiye, koi thread bhi nahi laga |

### Production symptoms — yeh trap live me kaise dikhta hai

- **p99 latency spike**: jaise hi koi slow blocking call hit hui, USKE PEECHE ki saari requests bhi slow — even `/ping` jaisi trivial endpoints
- **Health checks timeout**: `/health` bhi `async def` hai toh woh bhi blocked → Kubernetes liveness probe fail → pod restart → cascading failure
- **"Sab kuch ek saath slow ho gaya"** pattern — ek endpoint nahi, POORI app. Yeh signature hai event-loop-block ka. Threadpool exhaustion me degradation gradual hota hai; loop block me cliff hota hai.
- CPU ~0% lekin latency high — kyunki loop I/O pe **block** hai, busy nahi.

**Yeh trap isliye hota hai kyunki** log sochte hain "async likhna = modern = fast". Lekin `async def` ek **contract** hai: "main promise karta hoon ki main block nahi karunga, har slow cheez pe `await` karunga". Contract todo (sync call karo) toh runtime tumhe bachayega nahi — woh bas freeze ho jayega, koi error nahi, koi warning nahi (debug mode me `loop.slow_callback_duration` ke alawa).

---

## 3. Counter-Intuitive Rule — Sync `def` SAFER Hai (Agar Async Libraries Nahi Hain)

Yahi woh baat hai jo interviews me senior ko junior se alag karti hai:

> **"Agar tumhari libraries async-native nahi hain (requests, sync SQLAlchemy, boto3, pymongo), toh `def` endpoint likhna SAFER hai — kyunki FastAPI use threadpool me daal dega aur event loop bacha rahega."**

`async def` likho **sirf tab** jab andar ka **har** slow operation await-able ho.

### Decision Table (yaad kar lo — interview me table bana ke samjhao)

| Combination | Verdict | Kya hota hai |
|---|---|---|
| `async def` + await-able I/O (httpx, asyncpg, aioredis, motor) | ✅ **BEST** | Loop pe hazaron concurrent requests, minimal memory, no thread overhead |
| `def` + blocking libs (requests, sync SQLAlchemy, boto3) | ✅ **OKAY** | Threadpool absorb karta hai, ~40 concurrent blocking ops tak fine |
| `async def` + blocking lib | ❌ **DISASTER** | Event loop frozen, poori app serial ho gayi |
| CPU-bound kaam (kahin bhi — `def` ya `async def`) | ⚠️ **ProcessPool** | GIL ki wajah se threads bhi nahi bachayenge; alag process chahiye |

### CPU-bound kyun alag hai?

`def` endpoint me CPU-heavy kaam (image resize, ML inference, pandas crunching) threadpool me jayega — lekin **GIL** ki wajah se woh thread Python bytecode execute karte waqt baaki threads + event loop ke saath GIL fight karega. Threadpool blocking **I/O** ke liye hai (jahan GIL release hota hai), CPU ke liye nahi. CPU work = `ProcessPoolExecutor` ya Celery.

---

## 4. Escape Hatches — Blocking Code ko Async Context Se Safely Chalana

Kabhi-kabhi `async def` me hi ho aur ek blocking call karni hai (e.g., async endpoint me legacy sync function). 3 tools:

### 4.1 `run_in_threadpool` — Starlette ka apna (recommended in FastAPI)

```python
from starlette.concurrency import run_in_threadpool

@app.get("/report")
async def report():
    # generate_pdf ek sync, blocking function hai
    pdf = await run_in_threadpool(generate_pdf, user_id=42)
    # ⬆ yahi threadpool use hota hai jo `def` endpoints use karte hain
    return {"size": len(pdf)}
```

**Kyun yeh:** FastAPI internally yahi use karta hai `def` endpoints/dependencies ke liye — same anyio limiter share hota hai, toh capacity planning predictable rehti hai.

### 4.2 `asyncio.to_thread` — stdlib (Python 3.9+)

```python
import asyncio

@app.get("/legacy")
async def legacy():
    result = await asyncio.to_thread(legacy_sync_function, arg1, arg2)
    return {"result": result}
```

Functionally similar — asyncio ke default executor ke through jaata hai (Starlette ke anyio limiter se ALAG pool, dhyan rakhna capacity math karte waqt). kwargs directly pass kar sakte ho, `functools.partial` ki zaroorat nahi.

### 4.3 `loop.run_in_executor` + `ProcessPoolExecutor` — CPU-bound ke liye

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

process_pool = ProcessPoolExecutor(max_workers=4)  # app startup pe banao

def crunch_numbers(n: int) -> int:
    # Pure CPU work — GIL pakad ke baithega, isliye ALAG PROCESS me bhejo
    return sum(i * i for i in range(n))

@app.get("/crunch")
async def crunch():
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(process_pool, crunch_numbers, 10_000_000)
    return {"result": result}
```

**Trap within trap:** `run_in_executor(None, ...)` = default **Thread**PoolExecutor — CPU work ke liye useless (GIL). CPU ke liye explicitly `ProcessPoolExecutor` pass karo. Aur process pool me bheja hua function + args **picklable** hone chahiye.

### Kab kya use karo

| Tool | Use case |
|---|---|
| `run_in_threadpool` | FastAPI ke andar blocking I/O — Starlette ke shared limiter me accounted |
| `asyncio.to_thread` | Generic asyncio code, kwargs chahiye, FastAPI-independent |
| `run_in_executor` + ProcessPool | CPU-bound work jisko request ke andar hi complete hona hai |
| Celery / task queue | CPU/long work jisko request se BAHAR le jaa sakte ho (best for >1-2 sec) |

---

## 5. Threadpool Exhaustion — 40 Threads ki Limit Aur Latency Cliff

### Problem

anyio ka default thread limiter = **40 threads** (per process). Har `def` endpoint, har sync dependency, har `run_in_threadpool` call — sab isi pool se thread leta hai.

```
Scenario: /slow-report ek def endpoint hai jo 10 sec leta hai (slow DB query)

Traffic: 5 req/sec is endpoint pe
  → steady state me 5 × 10 = 50 threads chahiye
  → lekin pool me sirf 40 hain
  → 41st request QUEUE me wait karegi jab tak koi thread free na ho
  → ab /fast-def-endpoint bhi queue me phas gaya (same pool!)
  → latency cliff: p50 = 5ms tha, ab p50 = seconds me
```

**Symptom difference (interview me bolo):**
- Event loop block = **sab kuch turant freeze** (async endpoints bhi)
- Threadpool exhaustion = **sirf sync (`def`) endpoints queue hote hain**, async endpoints chalte rehte hain. Gradual degradation as pool fills.

### Limiter tune karna

```python
from contextlib import asynccontextmanager
import anyio.to_thread
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Default 40 → 100 threads
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 100
    yield

app = FastAPI(lifespan=lifespan)
```

(Internally yeh ek `RunVar` me stored `CapacityLimiter` hai — `total_tokens` runtime pe mutate kar sakte ho.)

### Kab tune karo (aur kab NAHI)

| Situation | Action |
|---|---|
| Bahut saare `def` endpoints, moderate-slow blocking I/O, RAM available | Limiter badhao (60–100) — threads sasti hain (~8MB stack virtual, actual kam) |
| Threads DB connections hold karte hain | ⚠️ Pehle DB pool dekho! 100 threads × DB conn > `max_connections` = DB pe DoS |
| Blocking calls 5–10+ sec ki hain | Limiter band-aid hai — root cause fix karo (async driver, ya Celery me bhejo) |
| CPU-bound work threadpool me ja raha | Limiter badhana ULTA padega — GIL contention badhegi. ProcessPool/Celery. |

**Rule of thumb:** limiter tuning tab justified jab blocking calls **short aur I/O-bound** hain aur concurrency 40 se zyada chahiye. Warna architecture fix karo, number nahi.

---

## 6. Real Stack Decisions — Production Me Kya Choose Karoge

### 6.1 Sync SQLAlchemy vs Async SQLAlchemy 2.0

```python
# Pattern A: sync SQLAlchemy + def endpoints (battle-tested, simple)
from sqlalchemy.orm import Session

@app.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):  # def! threadpool me
    return db.query(User).filter(User.id == user_id).first()

# Pattern B: async SQLAlchemy 2.0 + asyncpg (high concurrency)
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

| Aspect | Sync SQLAlchemy (`def`) | Async SQLAlchemy 2.0 (asyncpg) |
|---|---|---|
| Concurrency ceiling | ~threadpool size (40 default) | Hazaron (loop-bound) |
| Ecosystem maturity | 15+ saal, har pattern documented | Mature now, lekin lazy-load traps |
| Lazy loading | Kaam karta hai (n+1 alag issue hai) | ❌ `MissingGreenlet` error — explicit `selectinload` chahiye |
| Debugging | Straightforward stack traces | Async stack traces + greenlet magic |
| Moderate scale (<500 RPS, fast queries) | ✅ Bilkul fine | Overkill ho sakta hai |
| High concurrency / slow queries / many waits | Threadpool bottleneck | ✅ Shines here |

**Honest take (interview gold):** "Sync SQLAlchemy in `def` endpoints is FINE at moderate scale — threadpool handle karta hai. Async tab migrate karo jab measure kar ke threadpool saturation dikhe, ya concurrency requirement 40-ish simultaneous DB waits cross kare."

**Migration considerations** (sync → async SQLAlchemy):
1. Driver: `psycopg2` → `asyncpg` (URL: `postgresql+asyncpg://`)
2. Saari `db.query(...)` → `await db.execute(select(...))` — 2.0 style
3. Lazy relationships explicit eager-loading me convert karo (`selectinload`) warna `MissingGreenlet`
4. `Session` → `AsyncSession`, dependency bhi async generator
5. Alembic sync hi reh sakta hai (migrations offline chalti hain)
6. **Sabse bada cost:** TEST SUITE — fixtures, factories sab async banane padenge

### 6.2 `requests` vs `httpx.AsyncClient`

```python
# ❌ async def me requests = loop block
@app.get("/proxy")
async def proxy():
    r = requests.get("https://api.example.com/data")   # DISASTER
    return r.json()

# ✅ httpx.AsyncClient — app-level shared client (connection pooling)
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http.aclose()

@app.get("/proxy")
async def proxy(request: Request):
    r = await request.app.state.http.get("https://api.example.com/data")
    return r.json()
```

**Note:** Har request pe naya `AsyncClient` banana bhi mistake hai — TCP/TLS handshake har baar. Lifespan me ek shared client banao.

### 6.3 Celery dispatch from async — yeh THEEK hai

```python
@app.post("/orders")
async def create_order(payload: OrderIn):
    order = await save_order(payload)
    process_order.delay(order.id)   # ✅ fine in async def
    return {"id": order.id}
```

**Kyun fine:** `.delay()` sirf ek **quick network publish** hai broker (Redis/RabbitMQ) ko — microseconds-to-low-milliseconds. Yeh "blocking" technically hai lekin itna chhota ki practically harmless. Paranoid ho toh `run_in_threadpool(process_order.delay, order.id)` — lekin broker healthy hai toh zaroorat nahi. Broker DOWN hone pe `.delay()` retry/timeout me atak sakta hai — isliye broker connection timeouts chhote rakho.

---

## 7. Benchmarking Honesty — Async ≠ Automatically Fast

### Async kya deta hai aur kya NAHI deta

- ✅ **Throughput under I/O wait**: 1000 requests jo har ek 200ms DB/API wait karti hain — async loop sab interleave kar lega; sync me 40 threads ki ceiling
- ❌ **Single request latency**: ek request jo 50ms DB query karti hai — async me bhi 50ms hi lagega. Async waiting ko parallel karta hai, **wait khatam nahi karta**
- ❌ **CPU-bound speed**: JSON serialize, ORM object creation, computation — yeh sab loop PE hi chalta hai async me. CPU-heavy async endpoint sync se SLOW bhi ho sakta hai (event loop overhead + ek hi thread)

### Workers × Threadpool Math

```
Capacity for BLOCKING work (def endpoints):
  uvicorn workers × anyio threads = concurrent blocking requests

  4 workers × 40 threads  = 160 concurrent blocking ops
  Per-op time 100ms       → ~1600 RPS ceiling for def endpoints
  Per-op time 2s          → ~80 RPS ceiling ← yahan log chaukte hain

Capacity for ASYNC work (proper async def):
  workers × (loop concurrency)  — loop concurrency practically
  memory/FD/downstream limits se bound hoti hai, threads se nahi.
  1 worker easily 1000s of concurrent waits handle karta hai.
```

**Aur ek hidden coupling:** DB pool. 4 workers × 40 threads = 160 potential DB connections agar har thread DB use kare. Postgres default `max_connections=100`. Math karo BEFORE limiter badhane ke.

**Benchmark karte waqt:** load tool se **concurrency vary** karo (10, 50, 100, 500). Sync stack 40-concurrency tak async jaisa hi dikhega — cliff uske baad aati hai. Sirf `ab -c 10` chala ke "dono same hai" conclude karna classic galti hai.

---

## 8. Common Mistakes Checklist

- [ ] ❌ `async def` endpoint me `requests`, `time.sleep`, sync SQLAlchemy, `boto3`, `pymongo` — **loop block**
- [ ] ❌ `def` aur `async def` ko "style choice" samajhna — yeh execution model choice hai
- [ ] ❌ Sync **dependency** (`def` wala Depends) ko bhool jaana — woh bhi threadpool consume karta hai
- [ ] ❌ CPU-bound work `run_in_threadpool` me daalna — GIL, ProcessPool use karo
- [ ] ❌ Har request pe naya `httpx.AsyncClient` — lifespan me shared client banao
- [ ] ❌ Threadpool limiter 500 kar dena bina DB `max_connections` check kiye
- [ ] ❌ `run_in_executor(None, cpu_func)` — default executor THREAD pool hai, CPU ke liye process pool pass karo
- [ ] ❌ Middleware/background task me blocking call (`BackgroundTasks` me sync func threadpool me jaata hai — fine; lekin async background func me blocking call = wahi loop trap)
- [ ] ❌ Benchmark sirf low concurrency pe karke "async se farak nahi padta" bolna
- [ ] ✅ Doubt ho toh: blocking libs ke saath `def` likho — FastAPI tumhe bacha lega

### Debugging tip — loop block pakadne ke liye

```python
# Dev me asyncio debug mode: slow callbacks (>100ms loop hog) log hote hain
import asyncio
loop = asyncio.get_event_loop()
loop.set_debug(True)
loop.slow_callback_duration = 0.1   # 100ms se zyada loop hog = warning log

# Ya: PYTHONASYNCIODEBUG=1 uvicorn main:app
```

---

## 9. Interview Q&A

**Q1: FastAPI me `def` aur `async def` endpoint me kya farak hai?**
`async def` event loop (main thread) pe directly chalta hai — concurrency `await` points pe cooperative switching se aati hai. `def` ko Starlette anyio threadpool (default 40 threads) me offload karta hai — concurrency threads se aati hai. Dono concurrent hain, mechanism alag hai. Critical difference: `async def` me blocking call POORA loop rok deta hai; `def` me sirf ek thread.

**Q2: Mera async endpoint slow kyun ho gaya — aur saath me baaki endpoints bhi?**
Almost certainly kisi `async def` me blocking call hai (sync DB driver, `requests`, `time.sleep`, heavy CPU). Event loop single thread hai — ek blocking call ke dauraan KOI doosri request process nahi hoti, isliye unrelated endpoints (health checks tak) bhi hang dikhte hain. Diagnose: `loop.set_debug(True)` + `slow_callback_duration`, ya py-spy dump se dekho loop thread kahan atka hai. Fix: async library use karo ya call ko `run_in_threadpool` me bhejo.

**Q3: Kab sync `def` choose karoge over `async def`?**
Jab endpoint ke andar ki libraries blocking hain — sync SQLAlchemy, `requests`, boto3, pymongo. Tab `def` SAFER hai kyunki FastAPI threadpool me chalayega aur loop protected rahega. `async def` tabhi jab har I/O await-able ho. Mixed case me: `async def` + blocking parts ko `run_in_threadpool` se wrap karo.

**Q4: `async def` me `time.sleep(5)` vs `def` me `time.sleep(5)` — 10 concurrent requests pe kya hoga?**
`async def`: ~50 sec total — loop freeze hota hai har sleep me, requests serial process hoti hain. `def`: ~5 sec — 10 threads parallel sleep karte hain. Yahi ek-line demo trap ko prove karta hai.

**Q5: Threadpool ka size kya hai aur kaise badhate ho? Kab badhana chahiye?**
anyio default = 40 tokens. `anyio.to_thread.current_default_thread_limiter().total_tokens = N` lifespan me. Badhao jab: `def` endpoints pe short blocking I/O hai aur concurrency 40+ chahiye, aur RAM + DB pool allow karte hain. MAT badhao jab: calls long hain (Celery me bhejo) ya CPU-bound hain (GIL — ProcessPool).

**Q6: `run_in_threadpool` vs `asyncio.to_thread` vs `run_in_executor`?**
`run_in_threadpool` (starlette) — FastAPI ke shared anyio limiter me chalta hai, framework ke andar prefer karo. `asyncio.to_thread` — stdlib, asyncio ke default executor me (alag pool), kwargs support. `loop.run_in_executor` — low-level, custom executor pass kar sakte ho; CPU work ke liye `ProcessPoolExecutor` ke saath yahi use hota hai.

**Q7: CPU-bound work (image processing) FastAPI endpoint me kaise handle karoge?**
Threadpool nahi (GIL — Python bytecode me threads serialize ho jaate hain). Options: (1) `loop.run_in_executor(process_pool, fn)` agar request ke andar hi result chahiye, (2) Celery/RQ/arq me offload + job-id return karo (best for >1-2 sec), (3) chhota CPU work hai toh sync `def` bhi chalega at low scale, lekin measure karo.

**Q8: Sync SQLAlchemy FastAPI me use karna galat hai kya?**
Nahi — `def` endpoints me bilkul valid pattern hai at moderate scale. Threadpool blocking queries absorb karta hai. Async SQLAlchemy 2.0 + asyncpg tab justify hota hai jab concurrent DB waits threadpool ceiling cross karein. Migration cost real hai: lazy-loading `MissingGreenlet` deta hai (explicit `selectinload` chahiye), test suite async banana padta hai. "Measure first, migrate second."

**Q9: Async endpoint se Celery task dispatch karna safe hai? `delay()` toh sync hai.**
Haan, practically safe — `.delay()` broker ko ek quick publish hai (sub-millisecond to few ms healthy broker pe). Loop itne chhote block tolerate karta hai. Caveat: broker down/slow ho toh yeh call atak sakti hai — broker connection timeout tight rakho, ya hyper-critical paths pe `run_in_threadpool` wrap karo.

**Q10: Async banane se app fast ho jayegi?**
Nahi necessarily — async **throughput under I/O wait** badhata hai, individual request latency nahi (50ms ki query async me bhi 50ms hai). CPU-bound work me async kuch nahi deta, ulta single-thread loop pe sab serialize hota hai. Capacity math: blocking path = workers × 40 threads; async path = workers × (practically unbounded waits). Aur benchmark high concurrency pe karo — 40 se neeche sync/async same dikhte hain, cliff baad me aati hai.

---

## Related
- [[13_asgi_internals_uvicorn_tuning]] — event loop, uvicorn workers, uvloop
- [[04_testing_sqlalchemy]] — sync SQLAlchemy session-per-request pattern
- [[09_sqlalchemy_advanced]] — async SQLAlchemy 2.0 patterns
- [[30_performance_profiling]] — py-spy se loop block diagnose karna
