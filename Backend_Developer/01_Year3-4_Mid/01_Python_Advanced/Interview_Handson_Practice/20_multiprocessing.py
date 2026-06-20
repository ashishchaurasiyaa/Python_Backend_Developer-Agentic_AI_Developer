"""
================================================================================
TOPIC: Multiprocessing (Process, Pool.map, Queue/Pipe, Value/Array/shared_memory)
================================================================================

KYA HOTA HAI:
    multiprocessing alag-alag OS PROCESSES spawn karta hai — har process ka apna
    Python interpreter aur apna memory space. Threads ki tarah ye GIL share nahi
    karte, isliye CPU-bound kaam sach me PARALLEL chalta hai (multiple cores pe).
    Trade-off: processes ke beech memory shared nahi, communication explicit hai
    (pickle se args bhejo, Queue/Pipe/shared_memory se data exchange karo).

KYO NEED PADI:
    Python ka GIL ek time pe sirf ek thread ko Python bytecode chalane deta hai.
    Matlab CPU-heavy kaam (hashing, parsing, number crunching) threads se tez
    nahi hota — sab ek hi core pe ghoomta hai. Multiprocessing GIL ko bypass
    karke kaam ko alag processes me daal deta, jo alag cores pe sach me saath
    chalte hain. Tabhi CPU-bound pe real speedup milta.

KAISE USE KARTE HAIN:
    Quick parallel map ke liye: Pool(n).map(fn, iterable) — chunks me bant ke
    cores pe chalata. Long-running workers ke liye: Process(target=..). Data
    exchange: Queue (many-to-many, safe), Pipe (do endpoints, fast). Shared state:
    Value/Array (ctypes, Lock ke saath) ya shared_memory (zero-copy big buffers).
    Hamesha `if __name__ == "__main__":` guard lagao (spawn me re-import hota).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA migration: lakhon GL rows ka heavy transform/validation Pool.map se
       cores pe baant ke, single-process se 4x tez batch processing.
    2. Payment reconciliation: din ke end pe bulk hashing/signature-verify of txns
       — CPU-bound, processes me parallel.
    3. Odoo ERP migration: large CSV/XML parsing + cleaning, har file ek worker.
    4. Niroskos SaaS: per-tenant report generation (CPU-heavy aggregation) ko
       process pool me fan-out, ek tenant doosre ko block na kare.
    5. Celery already processes hi use karta — concept same; ek bade task ke andar
       agar CPU-bound sub-work hai to internal Pool se aur parallelize kar sakte.

INTERVIEW ANSWER (English — recite this):
    "I reach for multiprocessing when the work is CPU-bound, because Python's GIL
    serializes bytecode execution and threads give no real speedup there — only
    separate processes run truly in parallel across cores. For embarrassingly
    parallel work I use a Pool and map the function over the input so it's chunked
    across workers; for long-lived workers I create Process objects and coordinate
    them with a Queue or a Pipe. Since processes have separate memory, anything I
    pass as an argument or return must be picklable, and shared state needs explicit
    primitives — Value or Array with a Lock for small data, or shared_memory for
    large buffers to avoid copy overhead. A critical detail is the start method:
    'fork' on Linux is fast but copies the parent and is unsafe with threads or
    open handles, while 'spawn' (default on macOS and Windows) re-imports the module,
    which is exactly why the if __name__ == '__main__' guard is mandatory — without
    it, spawn re-executes top-level code and you get infinite process spawning. The
    senior nuance is that multiprocessing only pays off when per-task compute clearly
    outweighs the pickling and process-startup cost; for I/O-bound work I'd use
    threads or asyncio instead, since those release the GIL while waiting."

================================================================================
Run:
    python 20_multiprocessing.py          # saare sections chalao
    python 20_multiprocessing.py 2 5      # sirf section 2 aur 5

Sections:
    1. DEMO  — Process basics: spawn 2 processes, har ek apne PID pe kaam kare
    2. REAL  — Pool.map CPU-bound speedup: single-process vs pool (REAL timing)
    3. DEMO  — Queue IPC (worker -> result queue) + Pipe (two-way fast channel)
    4. REAL  — shared state: Value+Lock (sahi) vs shared_memory zero-copy buffer
    5. BREAK — pickling fail (lambda/closure args) + spawn re-import without guard
    6. TODO  — tum khud likho: parallel_sum(numbers, workers) via Pool
================================================================================
"""
from __future__ import annotations

import math
import multiprocessing as mp
import os
import sys
import time
from multiprocessing import shared_memory


# === SECTION 1: DEMO — Process basics (har process apna PID, apna memory) ===
def _worker_say(name: str) -> None:
    """Top-level function (module scope) — ZAROORI hai kyunki spawn ise pickle/
    re-import karke child me dhoondta hai. Nested/lambda yahan kaam nahi karega."""
    print(f"    [child] name={name!r} pid={os.getpid()} parent={os.getppid()}")


def section1() -> None:
    print("\n=== SECTION 1: DEMO — Process basics (separate PID, separate memory) ===")
    print(f"    [parent] pid={os.getpid()}")

    procs = [mp.Process(target=_worker_say, args=(f"w{i}",)) for i in range(2)]
    for p in procs:
        p.start()                         # naya OS process spawn
    for p in procs:
        p.join()                          # parent yahan wait karta (warna zombie/race)
    print("    -> dono child alag PID pe chale; parent ne join se wait kiya")
    print("    NOTE: child ko diye args pickle hote hain — picklable hone chahiye")


# === SECTION 2: REAL — Pool.map CPU-bound speedup (REAL single vs pool timing) ===
def _cpu_heavy(n: int) -> int:
    """Jaan-bujh ke CPU-bound: primes count tak ka kaam. Ye SAP HANA row-transform
    ya payment-hash jaise heavy compute ka stand-in hai (pure CPU, no I/O)."""
    total = 0
    for x in range(2, n):
        if all(x % d for d in range(2, int(math.isqrt(x)) + 1)):
            total += 1
    return total


def section2() -> None:
    print("\n=== SECTION 2: REAL — Pool.map CPU-bound speedup (real timing) ===")
    cores = min(4, os.cpu_count() or 1)
    # Per-chunk kaam itna bhaari rakho ki spawn/pickle startup cost ke baad bhi
    # parallel saaf jeete. Chunks = cores taaki har core ko ek mile.
    workload = [120_000] * cores

    # Single-process baseline (ek hi core, sequentially)
    t0 = time.perf_counter()
    serial = [_cpu_heavy(n) for n in workload]
    serial_ms = (time.perf_counter() - t0) * 1000

    # Pool: kaam ko cores pe baant do, sach me parallel
    t0 = time.perf_counter()
    with mp.Pool(processes=cores) as pool:
        parallel = pool.map(_cpu_heavy, workload)
    pool_ms = (time.perf_counter() - t0) * 1000

    print(f"    workload chunks = {len(workload)}, cores used = {cores}")
    print(f"    single-process : {serial_ms:7.1f} ms  -> {serial}")
    print(f"    Pool.map       : {pool_ms:7.1f} ms  -> {parallel}")
    speedup = serial_ms / pool_ms if pool_ms else 0.0
    print(f"    speedup        : {speedup:.2f}x  (cores aur startup cost pe depend)")
    print("    NOTE: CPU-bound pe hi fayda; chhote tasks me pickle+spawn cost ulta padta")


# === SECTION 3: DEMO — Queue IPC (worker->result) + Pipe (two-way channel) ===
def _square_worker(jobs: "mp.Queue[int]", results: "mp.Queue[tuple[int, int]]") -> None:
    """Queue se kaam utha, result doosri Queue me daal. Queue process-safe hai
    (internally locked) — many producers/consumers ke liye sahi choice."""
    while True:
        n = jobs.get()
        if n is None:                     # sentinel = 'bas, ruk ja' signal
            break
        results.put((n, n * n))


def _pipe_child(conn) -> None:
    """Pipe ka ek endpoint. Pipe = 2 connected ends, Queue se fast lekin sirf
    do parties ke beech. Yahan child parent ko reply bhejta."""
    msg = conn.recv()
    conn.send(f"child got {msg!r}, returning ACK")
    conn.close()


def section3() -> None:
    print("\n=== SECTION 3: DEMO — Queue (many-to-many) + Pipe (two endpoints) ===")

    # --- Queue: ek worker process se results wapas main process me ---
    jobs: "mp.Queue[int]" = mp.Queue()
    results: "mp.Queue[tuple[int, int]]" = mp.Queue()
    for n in (2, 3, 4):
        jobs.put(n)
    jobs.put(None)                        # sentinel taaki worker loop ruke

    w = mp.Process(target=_square_worker, args=(jobs, results))
    w.start()
    w.join()
    collected = []
    while not results.empty():
        collected.append(results.get())
    print(f"    Queue results (worker->main): {sorted(collected)}")

    # --- Pipe: two-way single channel ---
    parent_conn, child_conn = mp.Pipe()
    p = mp.Process(target=_pipe_child, args=(child_conn,))
    p.start()
    parent_conn.send("ping from parent")
    print(f"    Pipe reply: {parent_conn.recv()!r}")
    p.join()
    print("    -> Queue: safe many-to-many; Pipe: fast do-endpoint channel")


# === SECTION 4: REAL — shared state: Value+Lock vs shared_memory zero-copy ===
def _inc_with_lock(counter, lock, times: int) -> None:
    """Shared Value pe increment — Lock ke bina race condition (lost updates).
    Lock ke saath read-modify-write atomic ho jaata."""
    for _ in range(times):
        with lock:                        # critical section: ek time ek hi process
            counter.value += 1


def section4() -> None:
    print("\n=== SECTION 4: REAL — Value+Lock (shared counter) + shared_memory ===")

    # --- Value + Lock: chhota shared state (e.g. processed-rows counter) ---
    counter = mp.Value("i", 0)            # 'i' = C int, processes ke beech shared
    lock = mp.Lock()
    procs = [mp.Process(target=_inc_with_lock, args=(counter, lock, 1000))
             for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    print(f"    Value+Lock counter = {counter.value} (expected 4000, Lock ne race roka)")

    # --- shared_memory: bade buffer ko COPY kiye bina share (zero-copy) ---
    # Big array (e.g. millions of HANA rows) ko pickle/copy karna mehnga hai;
    # shared_memory me ek hi physical block sab processes map kar lete hain.
    shm = shared_memory.SharedMemory(create=True, size=10)
    try:
        shm.buf[:5] = b"HELLO"
        attached = shared_memory.SharedMemory(name=shm.name)  # same block, alag handle
        try:
            print(f"    shared_memory name={shm.name!r} read={bytes(attached.buf[:5])!r}")
            print("    -> wahi physical bytes, koi copy nahi (zero-copy big-buffer share)")
        finally:
            attached.close()
    finally:
        shm.close()
        shm.unlink()                      # ZAROORI: warna OS me leaked segment reh jaata
    print("    NOTE: shared_memory ko hamesha close()+unlink() karo (resource leak)")


# === SECTION 5: BREAK IT / GOTCHA — pickling fail + spawn guard ===
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — args must be PICKLABLE + __main__ guard ===")

    # --- GALTI: lambda/closure ko Pool me bhejna -> PicklingError ---
    print("  WRONG: lambda ko Pool.map me bhejna (lambda picklable nahi):")
    try:
        with mp.Pool(processes=2) as pool:
            pool.map(lambda x: x * x, [1, 2, 3])   # <- pickle nahi ho sakta
        print("    (agar yahan pahunche to is platform ne allow kiya — rare)")
    except Exception as e:
        print(f"    -> failed as expected: {type(e).__name__}: {str(e)[:60]}...")

    # --- FIX: top-level function use karo (module scope -> picklable by name) ---
    print("  FIXED: top-level function (_double) use karo:")
    with mp.Pool(processes=2) as pool:
        ok = pool.map(_double, [1, 2, 3])
    print(f"    -> works: {ok}  (function name se pickle hota, body nahi)")

    # --- spawn vs fork + guard ka kyun ---
    print(f"  start method on this OS: {mp.get_start_method()!r}")
    print("    spawn (mac/Windows default): child module ko RE-IMPORT karta — agar")
    print("    top-level pe Process().start() bina guard ke likha, to re-import pe")
    print("    wo dobara chalega -> INFINITE process spawn / RuntimeError.")
    print("    fork (Linux default): parent ki copy, fast, par threads/handles ke")
    print("    saath unsafe (locks half-held copy ho sakte -> deadlock).")
    print("    Isliye: process-spawning code HAMESHA `if __name__=='__main__':` ke andar.")


def _double(x: int) -> int:
    """FIX target: module-level function — pickle by qualified name, isliye spawn me
    child ise import karke dhoondh leta. Lambda/closure ke paas qualified name nahi."""
    return x * 2


# === SECTION 6: TODO — tum khud likho: parallel_sum(numbers, workers) ===
def _chunk_sum(chunk: list[int]) -> int:
    """Helper jo TODO me kaam aayega — ek chunk ka sum. (Module-level isliye taaki
    Pool ise pickle kar sake.)"""
    return sum(chunk)


def parallel_sum(numbers: list[int], workers: int = 2) -> int:
    """
    TODO (tum implement karo):
      `numbers` list ko `workers` (roughly) barabar chunks me todo, fir Pool ka
      use karke har chunk ka sum PARALLEL nikaalo, aur saare partial sums ko jod ke
      final total return karo.
      Steps:
        1. numbers ko `workers` chunks me slice karo (e.g. chunk size =
           ceil(len/workers)). Khaali chunks skip kar dena.
        2. `with mp.Pool(processes=workers) as pool:` ke andar
           pool.map(_chunk_sum, chunks) call karo -> partial sums milenge.
        3. sum(partials) return karo.
      Yaad rakho:
        - _chunk_sum module-level hi rehne do (picklable requirement).
        - empty list aaye to 0 return ho jaaye (Pool ko khaali iterable mat do bekaar).
    Expected:
        parallel_sum([1,2,3,4,5], workers=2) == 15
        parallel_sum([], workers=3) == 0
    """
    raise NotImplementedError("TODO: parallel_sum ka body likho (chunk + Pool.map + sum)")


def section6() -> None:
    print("\n=== SECTION 6: TODO — parallel_sum(numbers, workers) (tum likho) ===")
    try:
        got = parallel_sum([1, 2, 3, 4, 5], workers=2)
        expected = 15
        ok = "PASS" if got == expected else "FAIL"
        print(f"    parallel_sum([1..5], 2) = {got} (expected {expected}) [{ok}]")
        empty = parallel_sum([], workers=3)
        print(f"    parallel_sum([], 3)     = {empty} (expected 0)")
    except NotImplementedError as e:
        print(f"  abhi unimplemented (TODO complete karo): {e}")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
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
    # spawn-safe: saara process-spawning sirf is guard ke andar se hota hai.
    main()
