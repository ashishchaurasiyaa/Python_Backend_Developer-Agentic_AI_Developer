# 34 — Structured Concurrency (asyncio.TaskGroup / anyio / trio)
## Python Backend Developer Interview Prep | Target: 40 LPA

> **Hinglish Note:** Theory Hindi mein explain ki gayi hai taaki concepts clearly samajh aayein.
> Code, terms, aur technical keywords English mein hi rahenge.

---

## Quick Concepts

**WHAT:**
- **Structured Concurrency** = Har background task ka ek **bounded lifetime** hota hai jo ek lexical scope (block) se tied hai. Scope khatam → saari child tasks bhi khatam (complete ya cancelled).
- **Nursery / TaskGroup** = Woh scope object jiske andar tasks spawn hote hain aur jiske `__aexit__` pe sab join hote hain.
- **asyncio.TaskGroup** = Python 3.11+ ka built-in structured concurrency primitive.
- **trio** = Ek alag (non-asyncio) async library jisne "nursery" concept invent kiya.
- **anyio** = Backend-agnostic layer — same code asyncio YA trio dono pe chalta hai.
- **ExceptionGroup / `except*`** = PEP 654 (3.11) — ek saath aayi multiple exceptions ko represent + handle karna.

**WHY (yeh exist hi kyun karta hai):**
- Unstructured `asyncio.create_task(...)` ek **orphan task** bana deta hai — woh apne creator ko outlive kar sakti hai, koi uska `await` nahi karta, aur uski exception silently swallow ho jaati hai (`Task exception was never retrieved` warning ke saath).
- `asyncio.gather(...)` mein ek task fail hue toh **baaki siblings cancel nahi hote by default** — woh background mein chalte rehte hain (leak).
- Nathaniel J. Smith ka famous post **"Notes on structured concurrency, or: Go statement considered harmful"** (2018) yeh argue karta hai ki "fire-and-forget task spawn" bilkul `goto`/bare `go` jaisa hai — control flow ka black hole. Structured concurrency `goto` ke against `for`/`if`/function-call jaisa discipline laata hai.

**HOW (core invariant):**
- Ek block `async with <task group> as tg:` open karo.
- Andar `tg.create_task(coro())` / `tg.start_soon(fn, *args)` se children spawn karo.
- Block ka `__aexit__` **automatically saari children ka wait** karta hai. Koi bhi task **block ke bahar survive nahi kar sakti.** Agar koi child raise kare → sab siblings cancel, phir error propagate.

---

## 1. The Core Principle — "Black Box" Rule

```
Structured Concurrency ka ek-line rule:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Jab control ek block se bahar nikalta hai,
 us block ke andar spawn hui SAARI tasks complete ho chuki hoti hain."

Matlab function ek BLACK BOX ban jaata hai:
- Andar bhale 1000 tasks spawn kiye ho,
- Bahar se dekho toh ek normal function call jaisa —
  return hua = sab kaam khatam, koi leak nahi.

Yeh bilkul waise hi hai jaise:
  with open("f") as f: ...   # block ke bahar file GUARANTEED closed
  async with tg:        ...   # block ke bahar tasks GUARANTEED done
```

```
UNSTRUCTURED (purana asyncio tarika) — control flow ka leak:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def handler():
    asyncio.create_task(background_work())   # ← spawn aur bhool jao
    return "ok"                              # task ABHI BHI chal raha hai!

Problem:
  - handler() return ho gaya, par background_work() zinda hai (orphan).
  - Agar woh exception phenke → kahin handle nahi hoti.
  - Caller ko nahi pata kitni tasks abhi "owe" hain.
  - Yeh `go background_work()` (Go) jaisa hai = "go statement considered harmful".

STRUCTURED — leak impossible:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def handler():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(background_work())
    return "ok"   # ← yahan pahunchne ka MATLAB: background_work() done hai
```

**Reference:** Nathaniel J. Smith, *"Notes on structured concurrency, or: Go statement considered harmful"* (vorpus.org, 2018) — yeh post trio ki design philosophy hai aur baad mein `asyncio.TaskGroup` (PEP-driven) aur `anyio` dono ko inspire kiya.

---

## 2. `asyncio.TaskGroup` (Python 3.11+)

### Basic Usage

```python
import asyncio

async def worker(n: int) -> int:
    await asyncio.sleep(n * 0.1)
    return n * 10

async def main():
    results = []
    # 3.11+ built-in. Block ke andar saari tasks spawn karo.
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(worker(1))
        t2 = tg.create_task(worker(2))
        t3 = tg.create_task(worker(3))
    # ← Yahan pahunche = teeno tasks GUARANTEED complete (ya group cancelled)
    # __aexit__ ne implicitly sab ka await kiya.
    results = [t1.result(), t2.result(), t3.result()]
    print(results)  # [10, 20, 30]

asyncio.run(main())
```

```
TaskGroup internal lifecycle:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. async with TaskGroup() as tg  → __aenter__ : empty task set banata hai
2. tg.create_task(coro)          → task ko loop pe schedule + set mein track
3. block body normally chalta hai (aur tasks bhi background mein chalti hain)
4. __aexit__:
     a. agar body mein exception nahi → saari pending tasks ka wait
     b. agar KOI task raise kare      → baaki SIBLINGS ko cancel(),
                                         unka cleanup hone do,
                                         phir ExceptionGroup raise
```

### Error Propagation — Siblings Auto-Cancel

```python
import asyncio

async def good():
    await asyncio.sleep(5)
    print("good finished")   # YEH KABHI PRINT NAHI HOGA

async def bad():
    await asyncio.sleep(0.1)
    raise ValueError("boom")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(good())   # 5s wala
            tg.create_task(bad())    # 0.1s mein fail
    except* ValueError as eg:
        # bad() fail hote hi good() ko CANCEL kiya gaya (siblings auto-cancel).
        # Error ek ExceptionGroup ke andar wrap hoke aaya.
        print(f"caught {len(eg.exceptions)} error(s): {eg.exceptions}")

asyncio.run(main())
# Output: caught 1 error(s): (ValueError('boom'),)
# Note: "good finished" kabhi print nahi hua — woh cancel ho gaya tha.
```

```
KEY DIFFERENCE vs gather:
━━━━━━━━━━━━━━━━━━━━━━━━━
TaskGroup mein pehli exception pe:
  - Baaki sab siblings turant cancel hote hain (CancelledError inject).
  - Group unka cleanup hone deta hai.
  - Phir errors ko ExceptionGroup mein bundle karke raise karta hai.
  - Koi orphan task ZINDA NAHI bachti.
```

### PEP 654 — `except*` and ExceptionGroup

```python
import asyncio

async def fail_value():
    raise ValueError("bad value")

async def fail_type():
    raise TypeError("bad type")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fail_value())
            tg.create_task(fail_type())
            # DONO almost ek saath fail kar sakti hain →
            # TaskGroup BOTH ko ek ExceptionGroup mein collect karta hai.
    except* ValueError as eg:
        print("Value errors:", [str(e) for e in eg.exceptions])
    except* TypeError as eg:
        print("Type errors:", [str(e) for e in eg.exceptions])
    # except* ka matlab: "iss type ko ExceptionGroup ke andar se nikaalo",
    # baaki types ko phir bhi propagate hone do.

asyncio.run(main())
```

```
ExceptionGroup mental model (PEP 654, Python 3.11):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Normal `except E` ek single exception pakadta hai.
- Concurrency mein EK SAATH multiple exceptions aa sakti hain →
  ek hi "container" exception chahiye = ExceptionGroup.
- `except*` (star) ExceptionGroup ko "split" karta hai:
    - matching part handle karo,
    - non-matching part automatically re-raise as a smaller group.
- Ek try block mein multiple `except*` clauses chal sakte hain
  (kyunki ek group mein alag-alag types ho sakte hain).
- BaseExceptionGroup = base class; ExceptionGroup = sirf Exception-derived
  ke liye (KeyboardInterrupt/SystemExit jaisi BaseException alag handle hoti).
```

### Contrast: `asyncio.gather` (NOT structured)

```python
import asyncio

async def good():
    await asyncio.sleep(5)
    print("good still running...")   # gather mein YEH chal sakta hai!
    return "good"

async def bad():
    await asyncio.sleep(0.1)
    raise ValueError("boom")

async def with_gather():
    # gather DEFAULT behaviour: pehli exception turant propagate hoti hai,
    # PAR baaki tasks ko cancel NAHI karta — woh background mein chalte rehte!
    try:
        await asyncio.gather(good(), bad())
    except ValueError as e:
        print(f"gather raised: {e}")
        # good() abhi bhi event loop pe ZINDA hai → leak / surprise behaviour.

async def with_gather_return_exceptions():
    # return_exceptions=True: koi exception raise NAHI hoti —
    # har result ki jagah exception OBJECT list mein aa jaata hai.
    results = await asyncio.gather(good(), bad(), return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            print("got exception object:", repr(r))
        else:
            print("got value:", r)
    # Khatra: agar aap results check karna bhool gaye → errors silently gum.
```

```
gather vs TaskGroup — cheat sheet:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                          gather (default)   gather(return_exceptions=True)   TaskGroup
First error pe siblings?  NOT cancelled       NOT cancelled                    AUTO-cancelled
Error kaise milti hai?    raise (first only)  list mein object banke           ExceptionGroup
Multiple errors?          baaki gum/leak      sab list mein                    sab group mein
Orphan leak possible?     HAAN                 HAAN                             NAHI
Recommended (3.11+)?      legacy/simple        jab har result chahiye          DEFAULT choice
```

---

## 3. `trio` — The Original Nursery

```bash
# pip install trio
```

`trio` ek **alag event loop** hai (asyncio nahi). Isne hi "nursery" word coin kiya. Iska har design decision structured concurrency + correct cancellation ke around hai.

### Nursery Basics

```python
import trio

async def child(name: str, seconds: float):
    print(f"{name} start")
    await trio.sleep(seconds)
    print(f"{name} done")

async def parent():
    # open_nursery() ek async context manager hai.
    async with trio.open_nursery() as nursery:
        nursery.start_soon(child, "A", 1)   # fn + args (coroutine call NAHI)
        nursery.start_soon(child, "B", 2)
        print("children spawned, ab block khatam hone se pehle wait hoga")
    # ← nursery block ka exit DONO children ka wait karta hai.
    print("saari children done")

trio.run(parent)   # asyncio.run() nahi — trio ka apna runner
```

```
trio API note:
━━━━━━━━━━━━━━
- start_soon(fn, *args)  → fn(*args) ko spawn karta hai.
  IMPORTANT: aap `child("A", 1)` call karke nahi dete; aap fn aur args
  ALAG dete ho (taaki trio control kare kab call ho). kwargs ke liye
  functools.partial use karo.
- nursery.start(fn)      → task spawn karke uske "ready" signal ka wait
                            karta hai (neeche dekho).
```

### `nursery.start()` — Tasks That Signal Readiness

```python
import trio

async def server(task_status=trio.TASK_STATUS_IGNORED):
    listener = await bind_socket()           # setup (e.g. port bind)
    # "Main ready hoon" — yahin se parent ka start() return hoga,
    # aur is task ko parent nursery mein move kar diya jaata hai.
    task_status.started(listener.port)
    await serve_forever(listener)

async def main():
    async with trio.open_nursery() as nursery:
        # start() tab tak BLOCK karta hai jab tak server task_status.started()
        # call na kare → guaranteed: server bind ho chuka hai before we proceed.
        port = await nursery.start(server)
        print(f"server ready on port {port}")
        await send_request(port)   # ab safe — server up hai
```

```
start_soon vs start:
━━━━━━━━━━━━━━━━━━━━
start_soon(fn): fire karo, turant return — readiness ka koi guarantee nahi.
start(fn):      spawn karo PAR task_status.started() tak wait karo.
                Use case: server/listener jise "main up hoon" signal dena ho
                taaki race condition na ho (request bhejne se pehle bind done).
```

### Cancellation — Cancel Scopes, Timeouts, Checkpoints

```python
import trio

async def slow():
    await trio.sleep(100)

async def main():
    # move_on_after: timeout pe block ko GRACEFULLY chhod do (no exception).
    with trio.move_on_after(2) as cancel_scope:
        await slow()
    if cancel_scope.cancelled_caught:
        print("2s mein complete nahi hua, move on kar gaye")

    # fail_after: timeout pe trio.TooSlowError RAISE karo.
    try:
        with trio.fail_after(2):
            await slow()
    except trio.TooSlowError:
        print("deadline miss — exception raised")

    # Manual CancelScope — apni marzi se cancel() trigger karo.
    with trio.CancelScope() as scope:
        scope.cancel()           # is scope ke andar ka next checkpoint cancel
        await trio.sleep(1)      # yahan Cancelled inject ho jaayega
```

```
trio CHECKPOINT concept (yeh trio ki superpower hai):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Har `await trio.<something>()` ek "checkpoint" hai.
- Cancellation + task-switching SIRF checkpoints pe ho sakta hai.
- Guarantee: har trio async fn kam se kam ek checkpoint hit karta hai,
  isliye cancellation kabhi "atak" nahi sakti (no checkpoint-less loops).
- Fayda: deterministic — aap exactly jaante ho kahan cancel ho sakta hai.

Cancellation cooperative hai:
- trio andar ek `Cancelled` exception inject karta hai NEXT checkpoint pe.
- Aapka cleanup (finally / __aexit__) chalta hai.
- `Cancelled` ko aap khud catch karke swallow MAT karo (let it propagate).
```

### Shielding — Protect Critical Cleanup

```python
import trio

async def critical_cleanup():
    # Maan lo yeh DB flush / audit write hai — cancel par bhi poora chahiye.
    await trio.sleep(1)

async def worker():
    try:
        await trio.sleep(100)
    finally:
        # Parent ne cancel kar diya, par cleanup ko cancellation se bachao:
        with trio.CancelScope(shield=True):
            await critical_cleanup()   # yeh outer cancel se shielded hai
```

```
shield=True ka matlab:
━━━━━━━━━━━━━━━━━━━━━━
- Bahar se aane wali cancellation iss scope ke andar PROPAGATE nahi hoti.
- Critical cleanup / payment-commit jaise kaam ke liye.
- WARNING: shield ke andar khud ka timeout rakho, warna agar woh hang kare
  toh cancellation usse kabhi nahi rok paayegi (cancel-proof hang).
```

---

## 4. `anyio` (v4) — Backend-Agnostic Layer

```bash
# pip install anyio trio    # trio optional; default backend asyncio hai
```

`anyio` ek **compatibility layer** hai jo trio-style structured concurrency API deta hai PAR andar se **asyncio YA trio** — dono backends pe chal sakta hai. Aapko ek hi API seekhni padti hai.

```
2026 reality — anyio kahan chhupa baitha hai:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Starlette / FastAPI  → anyio pe based (threadpool, task groups).
- httpx                → anyio use karta hai async internals ke liye.
- AnyIO khud asyncio par DEFAULT chalta hai; aap chaaho toh trio backend.
Matlab: aap FastAPI likhte ho toh already anyio ki structured concurrency
ke upar baithe ho — bas seedha use kar sakte ho.
```

### Task Groups (anyio)

```python
import anyio

async def worker(n: int):
    await anyio.sleep(n * 0.1)
    print(f"worker {n} done")

async def main():
    # anyio.create_task_group() — trio nursery jaisa, par backend-agnostic.
    async with anyio.create_task_group() as tg:
        tg.start_soon(worker, 1)        # fn + args (trio style)
        tg.start_soon(worker, 2)
        # tg.start(fn) bhi available hai (readiness signalling ke liye)
    # ← block exit = saari tasks done (ya group cancelled + ExceptionGroup)
    print("all done")

# DONO backends pe chalega:
anyio.run(main)                          # default: asyncio
# anyio.run(main, backend="trio")        # ya phir trio pe
```

```
anyio ↔ asyncio.TaskGroup ↔ trio — naam ka mapping:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
spawn task:        asyncio: tg.create_task(coro())
                   trio:    nursery.start_soon(fn, *args)
                   anyio:   tg.start_soon(fn, *args)
group object:      asyncio: asyncio.TaskGroup()
                   trio:    trio.open_nursery()
                   anyio:   anyio.create_task_group()
errors bundle as:  teeno → ExceptionGroup (anyio v4 + asyncio 3.11 native;
                   trio bhi ab ExceptionGroup use karta hai modern versions mein)
```

### Cancellation + Timeouts (anyio)

```python
import anyio

async def slow():
    await anyio.sleep(100)

async def main():
    # move_on_after: graceful, no exception (trio jaisa).
    with anyio.move_on_after(2) as scope:
        await slow()
    if scope.cancelled_caught:
        print("anyio: moved on after 2s")

    # fail_after: deadline miss → TimeoutError raise.
    try:
        with anyio.fail_after(2):
            await slow()
    except TimeoutError:
        print("anyio: deadline exceeded")

    # Explicit cancel scope + shielding bhi support karta hai:
    with anyio.CancelScope(shield=True):
        await slow()   # bahar ke cancel se shielded
```

### Running Blocking Code — `anyio.to_thread.run_sync`

```python
import anyio
import time

def blocking_db_call(query: str) -> str:
    time.sleep(0.5)              # sync/blocking — event loop ko block karega
    return f"rows for {query}"

async def main():
    # Blocking sync function ko ek worker THREAD mein bhej do —
    # event loop free rehta hai. (asyncio.to_thread ka backend-agnostic version.)
    result = await anyio.to_thread.run_sync(blocking_db_call, "SELECT 1")
    print(result)

    # Ulta direction bhi hai: thread ke andar se async chalana —
    # anyio.from_thread.run(...)  (worker thread se loop pe coroutine bhejo)

anyio.run(main)
```

```
anyio.to_thread.run_sync — kaise kaam karta hai:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Ek thread limiter (capacity-limited) ke through worker thread leta hai.
- Sync fn ko us thread mein chalata hai, result ko await-able banata hai.
- FastAPI internally yahi use karta hai jab aap `def` (non-async) route
  ya sync dependency likhte ho → use threadpool pe bhej deta hai.
- cancellable=True pass karke aap waiting ko cancellable bana sakte ho
  (par underlying thread tab bhi chalta rehta hai — sirf wait chhodi jaati hai).
```

---

## 5. Cancellation Model — Unified Mental Model

```
COOPERATIVE cancellation (teeno systems mein):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- "Cancel" ka matlab thread ko maar dena NAHI hai.
- Ek special exception (asyncio: CancelledError, trio/anyio: Cancelled)
  next suspension point (await / checkpoint) pe INJECT hoti hai.
- Aapka finally / __aexit__ cleanup chalta hai.
- RULE: cancellation exception ko catch karke SWALLOW mat karo —
  cleanup karo aur re-raise hone do (warna task "cancel" nahi maani jaati).

CANCEL SCOPES (trio/anyio) vs asyncio:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- trio/anyio: cancellation ek SCOPE-level concept hai (with-block).
  Timeout = ek cancel scope jo deadline pe khud .cancel() kar deta hai.
  Scopes nest hote hain; har scope independently cancel ho sakti hai.
- asyncio: cancellation TASK-level hai (task.cancel()). 3.11 mein
  asyncio.timeout()/asyncio.TaskGroup ne scope-jaisa behaviour add kiya.

SHIELDING:
━━━━━━━━━━
- CancelScope(shield=True) (trio/anyio) → bahar ka cancel andar nahi ghusta.
- asyncio mein equivalent = asyncio.shield(coro) (per-awaitable).
- Sirf truly-critical cleanup ke liye; hamesha andar apna timeout rakho.

TIMEOUTS — naam mapping:
━━━━━━━━━━━━━━━━━━━━━━━━
graceful (no raise):   trio.move_on_after / anyio.move_on_after
hard (raises):         trio.fail_after(→TooSlowError) /
                       anyio.fail_after(→TimeoutError) /
                       asyncio.timeout(→TimeoutError) [3.11+] /
                       asyncio.wait_for(coro, t)(→TimeoutError)
```

---

## 6. Decision Table — Kab Kya Use Karein

| Situation | Best Choice | Reason |
|-----------|-------------|--------|
| Naya asyncio project, 3.11+ | **`asyncio.TaskGroup`** | Built-in, zero deps, native ExceptionGroup |
| Library jo dono asyncio + trio support kare | **`anyio`** | Ek codebase, dono backends |
| FastAPI / Starlette / httpx ke andar | **`anyio`** | Woh already anyio pe hain — same primitives |
| Max correctness, learning structured concurrency | **`trio`** | Sabse strict + clean cancellation model |
| Stuck on Python 3.8–3.10 (no TaskGroup) | **`anyio`** | Backport-style structured concurrency deta hai |
| Need scope-based timeouts everywhere | **`anyio` / `trio`** | `move_on_after` / `fail_after` cancel scopes |
| Pure asyncio app, sirf timeout chahiye | `asyncio.timeout()` (3.11+) | Lightweight, no extra primitive |
| Existing big asyncio codebase, `gather` chalu hai | TaskGroup mein migrate karo | Leaks + error-swallow se bachne ke liye |

```
Quick decision tree:
━━━━━━━━━━━━━━━━━━━━
Library likh rahe ho jo backend-neutral ho?
   └─ HAAN → anyio
   └─ NAHI ↓
Sirf asyncio + Python 3.11+?
   └─ HAAN → asyncio.TaskGroup (+ asyncio.timeout)
   └─ NAHI ↓
Strict-est cancellation / learning / greenfield?
   └─ trio
Python < 3.11 par structured concurrency chahiye?
   └─ anyio (asyncio backend)
```

---

## 7. Interview Q&As

### Q1: Structured concurrency kya hai, aur "go statement considered harmful" se kya lena-dena?

**Answer:**

> Structured concurrency ka core idea: har spawned task ka lifetime ek lexical scope se bandha hota hai — scope ke bahar koi task survive nahi karti. Nathaniel J. Smith ne *"Go statement considered harmful"* mein argue kiya ki `asyncio.create_task` / Go ka `go` keyword bilkul `goto` jaisa hai: control flow ek black hole mein chala jaata hai, error propagation tut-ti hai, aur cleanup unreliable ho jaata hai.
>
> Solution = "nursery"/TaskGroup: ek block jiske andar tasks spawn hote hain aur jiske exit pe sab join + error-propagate hote hain. Yeh `for`/`while`/function-call jaisa discipline laata hai — function ek "black box" ban jaata hai (return hua = saara internal concurrency settle ho gaya).

### Q2: `asyncio.TaskGroup` aur `asyncio.gather` mein fundamental difference?

**Answer:**

```python
# gather (default): pehli exception raise hoti hai PAR siblings cancel NAHI,
# woh background mein chalte rehte hain → leak + surprise.
await asyncio.gather(good(), bad())

# gather(return_exceptions=True): kuch raise nahi hota, har exception
# result list mein OBJECT ban ke aata hai — check na karo toh silently gum.

# TaskGroup: pehli exception pe baaki SIBLINGS auto-cancel, cleanup hone do,
# phir saari errors ek ExceptionGroup mein bundle karke raise.
async with asyncio.TaskGroup() as tg:
    tg.create_task(good())
    tg.create_task(bad())   # ← good() yahin cancel ho jaayega
```

> Ek line mein: gather **leak/swallow-prone** hai; TaskGroup **leak-proof + all-or-nothing** hai aur multiple errors ke liye ExceptionGroup deta hai.

### Q3: `ExceptionGroup` aur `except*` kya hai? Normal `except` se kyun nahi chal jaata?

**Answer:**

> Concurrency mein ek saath **multiple** exceptions raise ho sakti hain (5 tasks, 3 fail). Normal `except E` sirf ek exception pakad sakta hai. PEP 654 (Python 3.11) ne `ExceptionGroup` (ek container) aur `except*` (group ko split karke handle karne wala syntax) introduce kiya.

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fail_value())   # ValueError
        tg.create_task(fail_type())    # TypeError
except* ValueError as eg:
    ...   # sirf ValueError-wala sub-group
except* TypeError as eg:
    ...   # sirf TypeError-wala sub-group
# except* matching part nikaal leta hai, non-matching part chhota group
# ban ke aage propagate ho jaata hai. eg.exceptions ek tuple hai.
```

### Q4: `trio.open_nursery()` mein `start_soon` aur `start` ka fark?

**Answer:**

> - `nursery.start_soon(fn, *args)`: task ko spawn karke turant return — readiness ka koi guarantee nahi.
> - `nursery.start(fn)`: task spawn karta hai PAR tab tak block karta hai jab tak woh task `task_status.started(value)` na call kare. Phir woh task parent nursery mein move ho jaati hai aur `start()` woh `value` return karta hai.
>
> Use case: server jise "main bind ho gaya, port X pe ready hoon" signal dena ho — taaki client request bhejne se pehle race condition na ho. Note: dono mein aap `fn` aur `args` ALAG dete ho (coroutine call nahi), kwargs ke liye `functools.partial`.

### Q5: trio mein "checkpoint" kya hai, aur cancellation kaise inject hoti hai?

**Answer:**

> Checkpoint = woh point jahan task suspend ho sakti hai aur cancellation/scheduling ho sakti hai — har `await trio.something()` ek checkpoint hai. trio guarantee karta hai ki har async operation kam-se-kam ek checkpoint hit kare, isliye koi "checkpoint-less" busy loop cancellation ko atka nahi sakta.
>
> Cancellation **cooperative** hai: trio next checkpoint pe `Cancelled` exception inject karta hai. Aapka `finally`/`__aexit__` cleanup chalta hai. `Cancelled` ko swallow mat karo — propagate hone do, warna cancel-scope confuse ho jaayega.

### Q6: `anyio` ki zaroorat kya hai jab `asyncio.TaskGroup` already hai?

**Answer:**

> Teen reasons:
> 1. **Backend-agnostic:** anyio code asyncio AUR trio dono pe chalta hai — library authors ke liye ideal (user jo bhi loop chalaye).
> 2. **Pre-3.11 support:** Python 3.8–3.10 mein TaskGroup nahi hai; anyio wahan structured concurrency deta hai.
> 3. **Ecosystem:** Starlette/FastAPI/httpx andar se anyio use karte hain. Inke saath kaam karte waqt anyio ke task groups + `to_thread.run_sync` seedhe available hote hain.
>
> Agar aap pure-asyncio app likh rahe ho aur 3.11+ ho, toh `asyncio.TaskGroup` enough hai — anyio tab over-engineering ho sakta hai.

### Q7: Blocking sync code ko structured async mein kaise chalaoge?

**Answer:**

```python
# anyio (backend-agnostic):
result = await anyio.to_thread.run_sync(blocking_fn, arg)

# trio:
result = await trio.to_thread.run_sync(blocking_fn, arg)

# asyncio:
result = await asyncio.to_thread(blocking_fn, arg)
```

> Teeno blocking sync fn ko ek worker thread mein bhejte hain taaki event loop free rahe. FastAPI internally `anyio.to_thread.run_sync` use karta hai jab aap `def` (non-async) route ya sync dependency likhte ho. Cancellation note: aap wait ko cancel kar sakte ho, par underlying OS thread tab bhi chalta rehta hai (threads forcibly kill nahi hote).

### Q8: Cancellation ke time `CancelledError`/`Cancelled` ko catch karke swallow karna kyun galat hai?

**Answer:**

> Agar aap cancellation exception ko catch karke `raise` nahi karte:
> - asyncio: task `cancelled()` state mein nahi jaati; `TaskGroup`/`gather` ko lagta hai task abhi bhi "alive" hai → cleanup logic tut jaata hai.
> - trio/anyio: cancel scope kabhi "satisfied" nahi hota → potentially infinite hang (cancel-proof loop).
>
> Sahi pattern: cleanup karo `finally`/`except` mein, phir `raise` karo. Critical cleanup ko cancellation se bachana ho toh `CancelScope(shield=True)` (trio/anyio) ya `asyncio.shield()` use karo — par andar apna timeout zaroor rakho.

### Q9: `move_on_after` aur `fail_after` mein difference?

**Answer:**

> - `move_on_after(t)`: deadline miss hone par block ko **gracefully** chhod deta hai — koi exception nahi. Aap `scope.cancelled_caught` check karke jaante ho timeout hua. "Best effort, warna chhod do" semantics.
> - `fail_after(t)`: deadline miss par **exception raise** karta hai (`trio.TooSlowError`, anyio mein `TimeoutError`). "Yeh hona hi chahiye warna fail" semantics.
>
> asyncio equivalents: `asyncio.timeout(t)` (3.11+, raises `TimeoutError`) aur `asyncio.wait_for(coro, t)`. asyncio mein graceful "no-raise" version directly nahi hai — aap `asyncio.timeout` ko `try/except TimeoutError` se wrap karte ho.

### Q10: Ek purane `create_task`-based codebase ko structured concurrency mein migrate kaise karenge?

**Answer:**

> 1. "Fire-and-forget" `asyncio.create_task(...)` calls dhundo jinka koi owner/`await` nahi — yeh leaks hain.
> 2. Inhe enclosing `async with asyncio.TaskGroup() as tg:` block mein move karo, `tg.create_task(...)` use karo.
> 3. `gather(..., return_exceptions=True)` jahan errors silently list mein ja rahe the — TaskGroup + `except*` se replace karo.
> 4. Genuinely long-lived background services (jinka lifetime app ke barabar hai) ke liye app-level lifespan scope rakho (e.g. FastAPI `lifespan` / ek top-level task group) — taaki woh bhi kisi scope ke andar hi rahein, truly orphan nahi.
> 5. Long sync calls ko `asyncio.to_thread` / `anyio.to_thread.run_sync` mein daalo.

---

## Summary — Key Takeaways

```
1. Structured concurrency: har task ka lifetime ek block se tied — koi orphan nahi.
2. asyncio.TaskGroup (3.11+): built-in; first error pe siblings auto-cancel + ExceptionGroup.
3. gather: leak-prone (siblings cancel nahi) + return_exceptions errors swallow kar sakta hai.
4. PEP 654: ExceptionGroup (container) + except* (split & handle) for concurrent errors.
5. trio: alag event loop, nursery + checkpoints + cancel scopes — strict-est correctness.
6. anyio (v4): backend-agnostic (asyncio/trio); FastAPI/Starlette/httpx isi pe based.
7. start_soon = fire; start = spawn + wait-for-ready (readiness signalling).
8. Cancellation cooperative: exception at next checkpoint; cleanup karo, re-raise karo.
9. Timeouts: move_on_after (graceful) vs fail_after (raises); asyncio.timeout (3.11+).
10. Blocking code: anyio/trio/asyncio sab ka to_thread → worker thread, loop free.
```

---

## Related Topics
- `05_async_concurrency_deep_dive.md` — asyncio fundamentals, gather/create_task/wait, cancellation basics
- `16_async_advanced_patterns.md` — queues, backpressure, executors, cancellation patterns
- `18_modern_python_3_11_12_13.md` — ExceptionGroup, `except*`, `asyncio.TaskGroup`, no-GIL
- `26_concurrency_decision_framework.md` — threading vs multiprocessing vs asyncio decision-making
- `13_uvloop_deep_dive.md` — faster asyncio event loop (drop-in replacement)
- `11_race_conditions_debugging.md` — concurrency bug debugging
- `17_http_clients_complete.md` — httpx (anyio-based) async HTTP client

## External References
- Nathaniel J. Smith — "Notes on structured concurrency, or: Go statement considered harmful": https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
- trio docs: https://trio.readthedocs.io
- anyio docs: https://anyio.readthedocs.io
- PEP 654 (Exception Groups and `except*`): https://peps.python.org/pep-0654/
- `asyncio.TaskGroup` docs: https://docs.python.org/3/library/asyncio-task.html#task-groups

---

*File created for 40 LPA Python Backend Developer Interview Prep*
*Series: Python Advanced (Year 3-4) | Topic 34*
