"""
================================================================================
TOPIC: Asyncio — Coroutines, Event Loop, async generators & async context managers
================================================================================

KYA HOTA HAI:
    asyncio single-thread pe COOPERATIVE concurrency deta hai. 'async def' ek
    coroutine banata hai; 'await' pe control event loop ko wapas milta hai taaki
    woh doosre ready kaam chala sake. Loop ek scheduler hai jo I/O ke wait pe
    coroutines ko switch karta hai — threads/locks ke bina, ek hi thread me.

KYO NEED PADI:
    Backend ka 90% time I/O wait me jaata hai — DB call, HTTP API, Redis, disk.
    Threads se ye scale karta hai par GIL + context-switch + lock overhead aata.
    asyncio ek thread me hazaaron concurrent I/O waits hold kar leta — payment
    gateway ko 50 parallel call, SAP HANA ke 100 idempotent retries, sab cheap.

KAISE USE KARTE HAIN:
    Entry point pe asyncio.run(main()) — ek hi baar, loop khud banata/band karta.
    Concurrency ke liye gather() / create_task() / 3.11 ka TaskGroup. await sirf
    awaitables pe (coroutine, Task, Future). async for => async generator, async
    with => async context manager (contextlib.asynccontextmanager / aclosing).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: N tenants ke liye parallel idempotent fetch+upsert,
       per-call retry, ek bhi fail ho to TaskGroup baaki cancel kar de (atomic-ish).
    2. Payment gateway: 50 charge-status checks concurrently, Semaphore se provider
       ka rate-limit (max 5 in-flight) respect karte hue.
    3. Niroskos multi-tenant SaaS: paginated external API ko async generator se
       stream karo (async for page), connection aclosing se guaranteed close.
    4. Celery/Redis pipeline ke async worker: asyncio.Queue se producer/consumer
       fan-out (ek producer rows daale, N consumers process karein).
    5. Odoo/ETL migration: bulk read async, par CPU-heavy / blocking driver call
       ko asyncio.to_thread me bhej do warna poora loop freeze ho jaata.

INTERVIEW ANSWER (English — recite this):
    "Asyncio gives single-threaded cooperative concurrency: an 'async def' defines a
    coroutine, and every 'await' is a suspension point where the coroutine yields
    control back to the event loop so it can run other ready tasks. It shines for
    I/O-bound workloads — database, HTTP, Redis — where threads would waste memory
    and fight the GIL; one thread can hold thousands of in-flight waits. asyncio.run
    is the single entry point that owns the loop's lifecycle. For concurrency I reach
    for gather when I want results from independent tasks, create_task for fire-and-
    track, and from 3.11 a TaskGroup for structured concurrency — it awaits all
    children, and if one fails it cancels the siblings and raises an ExceptionGroup,
    which is exactly the all-or-nothing semantics you want for a multi-step write.
    The cardinal rule is never call blocking code inside a coroutine: a time.sleep or
    a synchronous DB driver doesn't yield, so it freezes the whole loop and every
    other task stalls — the fix is asyncio.to_thread (or a run_in_executor) to push
    that blocking call onto a thread. For streaming I use async generators with
    async-for and wrap them in aclosing so the underlying cursor or connection is
    always closed even on early break, and I bound concurrency with a Semaphore and
    coordinate producers and consumers with asyncio.Queue."

================================================================================
Run:
    python 22_asyncio_coroutines_and_async_iter.py        # saare sections chalao
    python 22_asyncio_coroutines_and_async_iter.py 2 5    # sirf section 2 aur 5

Sections:
    1. DEMO  — coroutine vs call: async def returns coroutine; await/asyncio.run
    2. DEMO  — gather vs create_task vs TaskGroup (3.11 structured + ExceptionGroup)
    3. REAL  — SAP HANA parallel idempotent fetch with TaskGroup (one fail = cancel all)
    4. REAL  — payment gateway: Semaphore rate-limit + asyncio.Queue producer/consumer
    5. DEMO  — async generator (__aiter__/__anext__) + async with + aclosing cleanup
    6. BREAK — CARDINAL rule: time.sleep blocks the loop; asyncio.to_thread fix
    7. TODO  — tum khud likho: bounded gather_with_limit(coros, limit) via Semaphore
================================================================================
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from typing import Any, AsyncIterator, Awaitable, Callable


# === SECTION 1: DEMO — coroutine object vs call; await; asyncio.run ===
async def greet(name: str, delay: float) -> str:
    """async def => coroutine function. await asyncio.sleep yahan loop ko control
    deta (non-blocking wait). time.sleep MAT use karna — section 6 dekho."""
    await asyncio.sleep(delay)               # suspension point: loop free ho jaata
    return f"hello {name}"


async def _s1() -> None:
    coro = greet("ashish", 0.01)             # call karte hi body NAHI chalti...
    print(f"  greet(...) returned -> {type(coro).__name__} (coroutine, not result!)")
    result = await coro                      # await pe hi body run + value milta
    print(f"  await coro -> {result!r}")
    print("  -> async def ek coroutine deta; bina await/run ke kuch nahi hota.")


def section1() -> None:
    print("\n=== SECTION 1: coroutine vs call — async def / await / asyncio.run ===")
    # asyncio.run: loop banao -> coro chalao -> loop band karo. Ek hi entry point.
    asyncio.run(_s1())


# === SECTION 2: DEMO — gather vs create_task vs TaskGroup (3.11) ===
async def work(label: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{label}-done"


async def boom(delay: float) -> str:
    await asyncio.sleep(delay)
    raise ValueError("downstream service exploded")


async def _s2() -> None:
    # --- gather: independent tasks, results ek list me ORDER me (input order) ---
    t0 = time.perf_counter()
    results = await asyncio.gather(work("a", 0.05), work("b", 0.05), work("c", 0.05))
    took = time.perf_counter() - t0
    print(f"  gather -> {results}  (3x0.05s but ran CONCURRENT in ~{took:.2f}s)")

    # --- create_task: abhi schedule karo, baad me await/track karo ---
    task = asyncio.create_task(work("bg", 0.02))   # turant loop pe chalna start
    print(f"  create_task -> {type(task).__name__} scheduled; doing other stuff...")
    print(f"  later await task -> {await task!r}")

    # --- TaskGroup (3.11): structured concurrency. with-block exit pe SAB await ---
    async with asyncio.TaskGroup() as tg:
        r1 = tg.create_task(work("x", 0.02))
        r2 = tg.create_task(work("y", 0.03))
    print(f"  TaskGroup (all awaited at block exit) -> {r1.result()}, {r2.result()}")

    # --- TaskGroup failure: ek child fail -> baaki CANCEL -> ExceptionGroup raise ---
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(work("slow", 0.30))   # ye cancel ho jaayega
            tg.create_task(boom(0.02))           # ye pehle fail karega
    except* ValueError as eg:                    # 3.11 except* => ExceptionGroup unpack
        print(f"  TaskGroup one-fails-all: caught ExceptionGroup with {len(eg.exceptions)} err")
        print(f"    -> sibling auto-cancelled; ye gather ke return_exceptions se zyada safe.")


def section2() -> None:
    print("\n=== SECTION 2: gather vs create_task vs TaskGroup (3.11 + ExceptionGroup) ===")
    asyncio.run(_s2())


# === SECTION 3: REAL — SAP HANA parallel idempotent fetch (TaskGroup all-or-nothing) ===
async def hana_upsert(tenant: str, fail: bool = False) -> dict[str, Any]:
    """Ek tenant ke liye idempotent fetch+upsert simulate. Real me ye async DB
    driver call hota. fail=True wala downstream error simulate karta."""
    await asyncio.sleep(0.02)                # I/O wait (network/DB round trip)
    if fail:
        raise ConnectionError(f"HANA refused for {tenant}")
    return {"tenant": tenant, "rows_upserted": len(tenant) * 10, "idempotent": True}


async def _s3(fail_globex: bool) -> None:
    tenants = ["acme", "globex", "initech"]
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = {
                t: tg.create_task(hana_upsert(t, fail=(fail_globex and t == "globex")))
                for t in tenants
            }
        # yahan pahunche matlab SAB success — atomic-ish batch
        for t, task in tasks.items():
            print(f"    OK {t}: {task.result()}")
        print("  all tenants upserted (no partial-commit risk).")
    except* ConnectionError as eg:
        print(f"  batch FAILED: {[str(e) for e in eg.exceptions]}")
        print("  -> TaskGroup ne baaki tenants cancel kiye; retry whole batch (idempotent so safe).")


def section3() -> None:
    print("\n=== SECTION 3: REAL — SAP HANA parallel idempotent fetch (TaskGroup) ===")
    print("  -- happy path (all tenants succeed) --")
    asyncio.run(_s3(fail_globex=False))
    print("  -- failure path (globex refuses; siblings cancelled) --")
    asyncio.run(_s3(fail_globex=True))


# === SECTION 4: REAL — payment gateway: Semaphore rate-limit + asyncio.Queue ===
async def charge_status(charge_id: int, gate: asyncio.Semaphore) -> str:
    """Provider sirf N concurrent calls allow karta -> Semaphore se gate.
    'async with gate' ek permit leta, block exit pe wapas chhod deta."""
    async with gate:                         # max-in-flight enforce
        await asyncio.sleep(0.02)            # provider round-trip
        return f"charge#{charge_id}=settled"


async def _s4() -> None:
    # --- Semaphore: 6 charges, par ek time max 2 in-flight (provider rate-limit) ---
    gate = asyncio.Semaphore(2)
    out = await asyncio.gather(*(charge_status(i, gate) for i in range(1, 7)))
    print(f"  Semaphore(2) over 6 charges -> {out}")
    print("    -> kabhi 2 se zyada concurrent provider call nahi gaye (429 bachao).")

    # --- asyncio.Queue: 1 producer rows daale, 2 consumers process karein (Celery-style) ---
    q: asyncio.Queue[int | None] = asyncio.Queue(maxsize=4)
    processed: list[str] = []

    async def producer() -> None:
        for txn in range(1, 6):
            await q.put(txn)                 # queue full ho to yahan backpressure
        await q.put(None)                    # sentinel: ek consumer ko stop signal
        await q.put(None)                    # doosre consumer ke liye bhi

    async def consumer(name: str) -> None:
        while True:
            txn = await q.get()
            try:
                if txn is None:              # poison pill -> ruk jao
                    return
                await asyncio.sleep(0.01)
                processed.append(f"{name}:txn{txn}")
            finally:
                q.task_done()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer())
        tg.create_task(consumer("c1"))
        tg.create_task(consumer("c2"))
    print(f"  Queue producer/2-consumers fan-out -> {sorted(processed)}")


def section4() -> None:
    print("\n=== SECTION 4: REAL — payment gateway Semaphore + asyncio.Queue ===")
    asyncio.run(_s4())


# === SECTION 5: DEMO — async generator + async with + aclosing cleanup ===
class PagedApi:
    """Manual async iterator: __aiter__/__anext__. Niroskos paginated API jaisa —
    har __anext__ pe ek page lazily fetch karta (network), khatam pe StopAsyncIteration."""
    def __init__(self, total_pages: int) -> None:
        self._page = 0
        self._total = total_pages

    def __aiter__(self) -> "PagedApi":
        return self

    async def __anext__(self) -> list[int]:
        if self._page >= self._total:
            raise StopAsyncIteration         # async for yahan ruk jaata
        await asyncio.sleep(0.005)           # page fetch I/O
        self._page += 1
        return [self._page * 10 + i for i in range(3)]


@contextlib.asynccontextmanager
async def db_session(name: str) -> AsyncIterator[str]:
    """async context manager (decorator style). __aenter__ = yield se pehle setup,
    __aexit__ = finally me teardown — error aaye tab bhi connection close guaranteed."""
    print(f"      [session] OPEN {name} (await connect)")
    await asyncio.sleep(0.005)
    try:
        yield f"conn::{name}"
    finally:
        await asyncio.sleep(0.005)
        print(f"      [session] CLOSE {name} (finally — always runs)")


async def tenant_records(tenant: str) -> AsyncIterator[dict[str, int]]:
    """async generator: 'async for ... yield'. Page stream ko flat record stream
    me badalta, fully lazy. close hone pe finally cleanup chal sake — aclosing dekho."""
    api = PagedApi(total_pages=3)
    try:
        async for page in api:               # async for => __aiter__/__anext__
            for rid in page:
                yield {"tenant_id": len(tenant), "record": rid}
    finally:
        print("      [stream] async-gen cleanup (cursor/connection close)")


async def _s5() -> None:
    # async with: setup/teardown bhi awaitable. Body me await kar sakte ho.
    async with db_session("niroskos-acme") as conn:
        print(f"  inside async with, using {conn}")

    # async for on manual async iterator
    print("  async for over PagedApi pages:")
    async for page in PagedApi(total_pages=2):
        print(f"    page -> {page}")

    # aclosing: async generator ka GUARANTEED aclose() even on early break.
    # Bina aclosing, agar bich me break karo to finally turant chalega iski guarantee
    # nahi (GC timing pe depend) — aclosing deterministic cleanup deta.
    print("  async-gen with aclosing (early break still cleans up):")
    async with contextlib.aclosing(tenant_records("acme")) as stream:
        async for rec in stream:
            print(f"    rec -> {rec}")
            if rec["record"] >= 11:          # jaan-boojh ke jaldi break
                print("    early break!")
                break
    # block exit pe stream.aclose() -> generator ka finally pakka chala (upar print)


def section5() -> None:
    print("\n=== SECTION 5: async generator (__aiter__/__anext__) + async with + aclosing ===")
    asyncio.run(_s5())


# === SECTION 6: BREAK IT / GOTCHA — CARDINAL rule: never block the event loop ===
async def blocking_task(label: str) -> str:
    """GALAT: coroutine ke andar time.sleep — ye loop ko THREAD-level block karta,
    koi await/yield nahi, isliye event loop ruk jaata aur baaki sab task freeze."""
    time.sleep(0.10)                         # <-- CARDINAL SIN: blocking call
    return f"{label}-blocking"


async def nonblocking_task(label: str) -> str:
    """SAHI: blocking call ko to_thread me bhej do -> alag thread chale, loop free
    rahe. Async-friendly call ho to await asyncio.sleep, warna asyncio.to_thread."""
    await asyncio.to_thread(time.sleep, 0.10)   # blocking ko worker thread pe offload
    return f"{label}-offloaded"


async def heartbeat(tag: str, n: int) -> None:
    """Background ticker — agar loop healthy hai to ye bich-bich me tick karega.
    Agar koi blocking_task loop ko jakad le, ye ek saath end me bilkul late tickega."""
    for i in range(n):
        await asyncio.sleep(0.02)
        print(f"      [{tag}] tick {i}")


async def _s6() -> None:
    # ---- WRONG: time.sleep poora loop freeze; heartbeat tick nahi paayega time pe ----
    print("  WRONG (time.sleep inside coroutine — loop FROZEN):")
    t0 = time.perf_counter()
    await asyncio.gather(
        blocking_task("job"),
        heartbeat("frozen", 3),              # ticks ko block ke baad hi mauka milega
    )
    print(f"    took {time.perf_counter() - t0:.2f}s — ticks blocking ke khatam hone ke "
          f"baad hue (concurrency mar gayi).")

    # ---- FIXED: to_thread se blocking offload; heartbeat saath-saath tick karta ----
    print("  FIXED (asyncio.to_thread — loop free, true concurrency):")
    t1 = time.perf_counter()
    res, _ = await asyncio.gather(
        nonblocking_task("job"),
        heartbeat("healthy", 3),             # ab block ke DAURAN interleave karega
    )
    print(f"    {res} in {time.perf_counter() - t1:.2f}s — ticks block ke DAURAN aaye "
          f"(loop responsive raha).")
    print("    -> Rule: coroutine ke andar sync DB driver / time.sleep / heavy CPU = NA. "
          "to_thread / run_in_executor use karo.")


def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — never block the loop (time.sleep) -> to_thread fix ===")
    asyncio.run(_s6())


# === SECTION 7: TODO — tum khud likho: bounded gather via Semaphore ===
async def gather_with_limit(
    coro_factories: list[Callable[[], Awaitable[Any]]],
    limit: int,
) -> list[Any]:
    """
    TODO (tum implement karo):
      Ek bounded concurrent runner banao. Diye gaye coroutine-FACTORIES (zero-arg
      callables jo coroutine return karein) ko chalao, par ek time pe max `limit`
      hi in-flight ho — exactly payment-gateway / SAP-HANA rate-limit pattern.
      Results INPUT ORDER me return karo (asyncio.gather order preserve karta).
        - asyncio.Semaphore(limit) banao;
        - har factory ke liye ek wrapper coroutine jo 'async with sem:' ke andar
          factory() ko await kare;
        - in wrappers ko asyncio.gather(*wrappers) se chalao aur result lautao.
      Expected behaviour:
          factories = [lambda: work(f"t{i}", 0.02) for i in range(5)]
          out = await gather_with_limit(factories, limit=2)
          # out == ['t0-done','t1-done','t2-done','t3-done','t4-done'] (order intact)
          # aur kabhi 2 se zyada concurrent nahi chale.
      Hint: factory isliye, kyunki coroutine ek hi baar await ho sakta — list of
      already-created coroutines reuse/order pe gotcha de sakta. limit<=0 pe
      ValueError raise karna acchi practice.
    """
    raise NotImplementedError("TODO: gather_with_limit() ka Semaphore-bounded body likho")


async def _s7() -> None:
    factories: list[Callable[[], Awaitable[Any]]] = [
        (lambda i=i: work(f"t{i}", 0.02)) for i in range(5)
    ]
    try:
        out = await gather_with_limit(factories, limit=2)
        print(f"  gather_with_limit(.., limit=2) -> {out}")
        if out == [f"t{i}-done" for i in range(5)]:
            print("  correct! bounded concurrency with order preserved.")
        else:
            print("  output expected ['t0-done'..'t4-done'] tha — dobara dekho.")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")


def section7() -> None:
    print("\n=== SECTION 7: TODO — bounded gather_with_limit via Semaphore (tum likho) ===")
    asyncio.run(_s7())


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
        "7": section7,
    }
    args = sys.argv[1:]
    to_run = args if args else list(sections.keys())
    for key in to_run:
        fn = sections.get(key)
        if fn is None:
            print(f"[skip] unknown section: {key!r} (valid: {', '.join(sections)})")
            continue
        fn()


if __name__ == "__main__":
    main()
