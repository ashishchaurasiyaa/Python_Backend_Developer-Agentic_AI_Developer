"""
================================================================================
TOPIC: Concurrency vs Parallelism, Multitasking & Context Switching (concepts)
================================================================================

KYA HOTA HAI:
    Concurrency = bahut saare kaam HANDLE karna (structure: kaam aapas me
    interleave hote hain, ek ruk-ruk ke aage badhte hain). Parallelism = bahut
    saare kaam ek hi waqt me SACHME karna (multiple CPU cores pe literally same
    time pe). Concurrency "dealing with many" hai, parallelism "doing many at
    once" — concurrent code single core pe bhi chal sakta hai, parallel nahi.

KYO NEED PADI:
    Backend me sabse zyada time IO-wait me jaata hai (DB query, HANA socket,
    HTTP gateway, Redis). Agar ek request ke IO-wait me thread/process khali
    baitha rahe to throughput zero. Concurrency se wait ke dauraan doosra kaam
    pick kar lo. CPU-bound kaam (hashing, report crunching) ke liye GIL ki wajah
    se threads se speedup nahi milta — wahan saccha parallelism (processes) chahiye.

KAISE USE KARTE HAIN:
    Cooperative multitasking = asyncio: task khud `await` pe control CHHODTA hai
    (yield point), event loop doosra task uthata hai. Preemptive multitasking =
    OS threads/processes: OS bina puchhe time-slice khatam hone pe ya GIL release
    pe thread switch kar deta hai. Switch ki cost: OS thread switch (kernel,
    register save, cache flush) >> async task switch (just function resume).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: 50 tables parallel-ish fetch — har call IO-bound,
       to asyncio/threads se overlap karo, total wait collapse ho jaata hai.
    2. Niroskos Django SaaS: ek request DB pe wait kare to worker doosri request
       serve kare (gunicorn workers/async) — IO-bound concurrency.
    3. Celery/Redis pipeline: CPU-heavy report generation -> alag process/worker
       (multiprocessing) kyunki GIL threads ko CPU pe block karti hai.
    4. Payment gateway fan-out: 5 providers ko ek saath ping karo, jaldi jawab.
    5. Bulk Odoo migration: thousands of records ka transform (CPU) -> processes,
       fetch (IO) -> threads/async. Decision IO-bound vs CPU-bound pe based.

INTERVIEW ANSWER (English — recite this):
    "Concurrency is about structure — dealing with many tasks by interleaving
    them — while parallelism is about execution — literally doing many things at
    the same instant on multiple cores. Concurrency can exist on a single core;
    parallelism cannot. Python gives us two flavours of multitasking: cooperative,
    where asyncio tasks voluntarily yield control at every await, and preemptive,
    where the OS forcibly switches threads on a timer. The cost difference is
    large: an OS thread context switch crosses into the kernel and saves register
    and cache state, whereas an async task switch is just resuming a coroutine in
    the same thread, so async scales to tens of thousands of in-flight IO
    operations cheaply. My decision rule is simple: IO-bound work goes to asyncio
    or threads so waits overlap — with threads because the GIL is released during
    blocking IO, and with asyncio because the single-threaded event loop suspends
    each coroutine at its await; CPU-bound
    work goes to multiprocessing because the GIL serialises pure-Python bytecode
    and threads give no real speedup. The senior gotcha is that threads do NOT
    speed up CPU-bound Python and a single blocking call inside an async event
    loop stalls every other task — you must offload blocking work to an executor."

================================================================================
Run:
    python 17_concurrency_parallelism_multitasking.py        # saare sections
    python 17_concurrency_parallelism_multitasking.py 1 5    # sirf 1 aur 5

Sections:
    1. DEMO  — concurrency (interleave) vs parallelism (same instant) ka farq
    2. DEMO  — cooperative (asyncio await yield) vs preemptive (OS thread) switch
    3. DEMO  — context switch cost: async task switch sasta, OS thread switch mehnga
    4. REAL  — IO-bound fake task: sequential vs threads vs asyncio (timing)
    5. REAL  — CPU-bound fake task: threads (GIL) vs processes (real parallelism)
    6. BREAK — blocking call event loop me daala -> sab tasks ruk gaye (galti+fix)
    7. TODO  — tum khud likho: pick_executor(kind) decision-table function
================================================================================
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


# === SECTION 1: DEMO — concurrency (interleave) vs parallelism (same instant) ===
def section1() -> None:
    print("\n=== SECTION 1: concurrency (interleave, 1 worker) vs parallelism (>1 core) ===")

    # CONCURRENCY: ek hi worker, kaam tukdo me, beech-beech me switch.
    # Yahan hum manually interleave kar rahe — single thread, par dono "chal rahe".
    def step(task: str, total: int, log: list[str]) -> None:
        for i in range(total):
            log.append(f"{task}:{i}")

    log: list[str] = []
    # round-robin se A aur B ko interleave karo (concurrency = structure)
    a_steps = ["A:0", "A:1", "A:2"]
    b_steps = ["B:0", "B:1", "B:2"]
    for a, b in zip(a_steps, b_steps):
        log.append(a)   # thoda A
        log.append(b)   # thoda B  -> dono "progress" kar rahe ek worker pe
    print(f"  CONCURRENT (1 worker, interleaved): {log}")
    print("    -> dono task aage badh rahe, par kisi 1 instant pe sirf 1 chal raha")

    # PARALLELISM: agar machine pe 2+ cores hain to do kaam SAME instant pe.
    cores = os.cpu_count() or 1
    print(f"  this machine cpu_count() = {cores}  "
          f"(parallelism tabhi possible jab cores > 1)")
    print("    -> concurrency single-core pe bhi hoti; parallelism ke liye cores chahiye")


# === SECTION 2: DEMO — cooperative (asyncio) vs preemptive (OS thread) switch ===
def section2() -> None:
    print("\n=== SECTION 2: cooperative (await yields) vs preemptive (OS forces) ===")

    # COOPERATIVE: task khud `await` pe control chhodta hai. Yield point VISIBLE hai.
    order: list[str] = []

    async def worker(name: str) -> None:
        order.append(f"{name}:start")
        await asyncio.sleep(0)        # <- yield point: yahin control loop ko wapas
        order.append(f"{name}:resume")

    async def cooperative() -> None:
        # dono ek saath schedule; await pe ek doosre ko mauka deta hai
        await asyncio.gather(worker("co-A"), worker("co-B"))

    asyncio.run(cooperative())
    print(f"  COOPERATIVE order: {order}")
    print("    -> dono 'start' pehle (await pe yield), phir 'resume' — switch sirf await pe")

    # PREEMPTIVE: OS kabhi bhi switch kar sakta hai, code me koi yield point nahi.
    # Counter ka final value deterministic, par interleaving OS decide karta hai.
    flips: list[str] = []
    lock = threading.Lock()

    def thread_worker(name: str) -> None:
        for _ in range(2):
            with lock:
                flips.append(name)        # OS in iterations ke beech kabhi bhi switch kar de

    t1 = threading.Thread(target=thread_worker, args=("th-A",))
    t2 = threading.Thread(target=thread_worker, args=("th-B",))
    t1.start(); t2.start(); t1.join(); t2.join()
    print(f"  PREEMPTIVE order : {flips}  (OS-decided, run-to-run vary kar sakta)")
    print("    -> koi explicit yield nahi; OS time-slice/GIL pe khud switch karta hai")


# === SECTION 3: DEMO — context switch cost (async resume vs OS thread switch) ===
def section3() -> None:
    print("\n=== SECTION 3: context switch cost — async task switch vs OS thread switch ===")

    N = 50_000

    # ASYNC switch: ek hi thread me coroutine resume. Kernel me jaana nahi padta.
    async def yielder() -> None:
        for _ in range(N):
            await asyncio.sleep(0)        # pure yield -> loop turant resume karega

    start = time.perf_counter()
    asyncio.run(yielder())
    async_ms = (time.perf_counter() - start) * 1000
    per_async_us = (async_ms * 1000) / N
    print(f"  {N:,} async task switches : {async_ms:7.1f} ms "
          f"(~{per_async_us:.3f} us/switch)")

    # OS thread switch: thread create + start + join = kernel scheduling involved.
    # (Pura thread switch microbenchmark karna tricky, to thread spawn cost se
    #  feel dete hain — har spawn me kernel ko jaana padta hai.)
    M = 200
    start = time.perf_counter()
    for _ in range(M):
        t = threading.Thread(target=lambda: None)
        t.start(); t.join()
    thread_ms = (time.perf_counter() - start) * 1000
    per_thread_us = (thread_ms * 1000) / M
    print(f"  {M:,} OS thread spawn+join: {thread_ms:7.1f} ms "
          f"(~{per_thread_us:.1f} us/thread)")
    print("    -> async switch microseconds ke fraction me; OS thread bahut mehnga")
    print("    -> isiliye 10k+ concurrent IO ke liye asyncio scale karta, threads nahi")


# === SECTION 4: REAL — IO-bound: sequential vs threads vs asyncio (timing) ===
IO_TASKS = 8
IO_WAIT = 0.05   # har "network call" 50ms wait (HANA/HTTP gateway jaisa)


def _fake_io_blocking(idx: int) -> int:
    # blocking IO simulate: thread is wait ke dauraan GIL release karta hai,
    # isiliye threads me ye waits overlap ho jaate hain.
    time.sleep(IO_WAIT)
    return idx * idx


async def _fake_io_async(idx: int) -> int:
    await asyncio.sleep(IO_WAIT)      # non-blocking await -> loop doosra task uthata
    return idx * idx


def section4() -> None:
    print("\n=== SECTION 4: REAL IO-bound (fake HANA/gateway calls) — 3 approaches ===")
    print(f"  {IO_TASKS} tasks, har task ~{IO_WAIT*1000:.0f}ms IO wait")

    # 1) SEQUENTIAL: ek-ek karke -> waits add hote hain (worst).
    start = time.perf_counter()
    seq = [_fake_io_blocking(i) for i in range(IO_TASKS)]
    seq_ms = (time.perf_counter() - start) * 1000
    print(f"  sequential : {seq_ms:7.1f} ms  results={seq}")

    # 2) THREADS: IO ke dauraan GIL release -> waits overlap (IO-bound ka classic fix).
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=IO_TASKS) as ex:
        thr = list(ex.map(_fake_io_blocking, range(IO_TASKS)))
    thr_ms = (time.perf_counter() - start) * 1000
    print(f"  threads    : {thr_ms:7.1f} ms  (waits overlap, GIL IO me release hoti)")

    # 3) ASYNCIO: ek thread, hazaaron tasks tak scale; yahan bhi waits overlap.
    async def run_async() -> list[int]:
        return await asyncio.gather(*(_fake_io_async(i) for i in range(IO_TASKS)))

    start = time.perf_counter()
    aio = asyncio.run(run_async())
    aio_ms = (time.perf_counter() - start) * 1000
    print(f"  asyncio    : {aio_ms:7.1f} ms  results={aio}")
    print("  TAKEAWAY: IO-bound -> threads/asyncio se total wait ~1 task ke barabar")


# === SECTION 5: REAL — CPU-bound: threads (GIL) vs processes (real parallelism) ===
def _cpu_heavy(n: int) -> int:
    # pure-Python CPU kaam (GIL hold karta hai): primes-ish counting.
    total = 0
    for x in range(2, n):
        if all(x % d for d in range(2, int(math.isqrt(x)) + 1)):
            total += 1
    return total


CPU_N = 90_000
CPU_TASKS = 4


def section5() -> None:
    print("\n=== SECTION 5: REAL CPU-bound (fake report crunch) — threads vs processes ===")
    print(f"  {CPU_TASKS} tasks, har task primes upto {CPU_N:,} (pure-Python CPU)")

    # 1) SEQUENTIAL baseline
    start = time.perf_counter()
    seq = [_cpu_heavy(CPU_N) for _ in range(CPU_TASKS)]
    seq_ms = (time.perf_counter() - start) * 1000
    print(f"  sequential : {seq_ms:7.1f} ms  (each result={seq[0]})")

    # 2) THREADS: GIL ki wajah se CPU bytecode serialise -> NO speedup (often slower).
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CPU_TASKS) as ex:
        list(ex.map(_cpu_heavy, [CPU_N] * CPU_TASKS))
    thr_ms = (time.perf_counter() - start) * 1000
    print(f"  threads    : {thr_ms:7.1f} ms  (GIL hold -> ~no speedup, sometimes slower)")

    # 3) PROCESSES: alag interpreter, apni GIL -> saccha parallelism on cores.
    cores = os.cpu_count() or 1
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=min(CPU_TASKS, cores)) as ex:
        list(ex.map(_cpu_heavy, [CPU_N] * CPU_TASKS))
    proc_ms = (time.perf_counter() - start) * 1000
    print(f"  processes  : {proc_ms:7.1f} ms  (real parallelism across {cores} cores)")
    print("  TAKEAWAY: CPU-bound -> processes; threads GIL ki wajah se bekaar")


# === SECTION 6: BREAK IT / GOTCHA — blocking call inside the async event loop ===
def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — blocking call event loop ko freeze kar deta hai ===")

    BLOCK = 0.06

    # ---- GALAT: async function ke andar time.sleep (blocking) ----
    # asyncio single-threaded hai. Jab ek coroutine time.sleep karti hai, wo
    # event loop ka thread block kar deti hai -> baaki tasks bhi ruk jaate.
    async def bad_worker(name: str, log: list[str]) -> None:
        log.append(f"{name}:start")
        time.sleep(BLOCK)                 # <- BLOCKING! loop yahin atak gaya
        log.append(f"{name}:done")

    async def bad_run() -> tuple[list[str], float]:
        log: list[str] = []
        start = time.perf_counter()
        await asyncio.gather(bad_worker("A", log), bad_worker("B", log),
                             bad_worker("C", log))
        return log, (time.perf_counter() - start) * 1000

    log, bad_ms = asyncio.run(bad_run())
    print(f"  WRONG (time.sleep in coroutine): {bad_ms:6.1f} ms  order={log}")
    print(f"    -> ~{3*BLOCK*1000:.0f}ms (SERIAL!). 'start' ke turant baad 'done' —")
    print("       koi overlap nahi. Ek blocking call ne poora loop freeze kar diya.")

    # ---- FIX 1: await asyncio.sleep (cooperative non-blocking) ----
    async def good_worker(name: str, log: list[str]) -> None:
        log.append(f"{name}:start")
        await asyncio.sleep(BLOCK)        # <- non-blocking: loop doosra task uthata
        log.append(f"{name}:done")

    async def good_run() -> tuple[list[str], float]:
        log: list[str] = []
        start = time.perf_counter()
        await asyncio.gather(good_worker("A", log), good_worker("B", log),
                             good_worker("C", log))
        return log, (time.perf_counter() - start) * 1000

    log2, good_ms = asyncio.run(good_run())
    print(f"  FIX1  (await asyncio.sleep) : {good_ms:6.1f} ms  order={log2}")
    print(f"    -> ~{BLOCK*1000:.0f}ms: saare 'start' pehle (overlap), phir 'done'.")

    # ---- FIX 2: agar blocking lib hi use karni hai (legacy HANA driver),
    #            usse executor (thread) me offload karo, loop free rahega.
    async def offloaded_run() -> float:
        loop = asyncio.get_running_loop()
        start = time.perf_counter()
        await asyncio.gather(*(loop.run_in_executor(None, time.sleep, BLOCK)
                               for _ in range(3)))
        return (time.perf_counter() - start) * 1000

    off_ms = asyncio.run(offloaded_run())
    print(f"  FIX2  (run_in_executor)     : {off_ms:6.1f} ms  "
          f"(blocking lib ko thread me bhej do)")
    print("  GOTCHA: async me NEVER blocking call seedha; warna concurrency illusion toot-ti")


# === SECTION 7: TODO — tum khud likho: pick_executor(kind) decision table ===
def pick_executor(kind: str) -> str:
    """
    TODO (tum implement karo):
      Ek decision-table helper banao jo workload ke 'kind' ke hisaab se sahi
      concurrency strategy ka NAAM return kare (string). Ye interview ka core
      mental model hai — IO-bound vs CPU-bound pe sahi tool chunna.

      Expected behaviour (case-insensitive 'kind'):
        "io"        -> "asyncio_or_threads"   # IO ke dauraan GIL release, waits overlap
        "io-bound"  -> "asyncio_or_threads"
        "cpu"       -> "processes"            # GIL ki wajah se threads bekaar
        "cpu-bound" -> "processes"
        "mixed"     -> "processes_with_async_io"  # CPU process me, IO async/threads
        warna       -> raise ValueError(f"unknown workload kind: {kind!r}")

      Hint: kind.strip().lower() karke ek dict/if-else se map karo. Soch:
        - IO-bound (DB/HTTP/HANA/Redis wait) -> overlap chahiye, CPU idle hai
        - CPU-bound (hashing, report crunch, transform) -> alag interpreter chahiye
        - mixed (fetch + crunch) -> dono ko alag-alag handle karo
    """
    raise NotImplementedError("TODO: pick_executor ka decision-table body likho")


def section7() -> None:
    print("\n=== SECTION 7: TODO — pick_executor(kind) decision table (tum likho) ===")

    cases = {
        "io": "asyncio_or_threads",
        "cpu": "processes",
        "mixed": "processes_with_async_io",
    }
    try:
        for kind, expected in cases.items():
            got = pick_executor(kind)
            ok = "OK" if got == expected else "WRONG"
            print(f"  pick_executor({kind!r}) -> {got!r}  (expected {expected!r}) [{ok}]")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")
    else:
        # bonus: unknown kind ValueError dena chahiye
        try:
            pick_executor("quantum")
            print("  ERROR: unknown kind pe ValueError aana chahiye tha!")
        except ValueError as e:
            print(f"  unknown kind correctly rejected: ValueError: {e}")


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
