"""
================================================================================
TOPIC: GIL Mechanics (Global Interpreter Lock — CPython ki ek-thread-at-a-time mutex)
================================================================================

KYA HOTA HAI:
    GIL ek process-wide mutex hai CPython me jo guarantee karta hai ki kisi bhi
    ek instant pe SIRF EK thread Python bytecode execute kare. Matlab tumhare paas
    8-core CPU hai aur tum 8 Python threads chala rahe ho — phir bhi pure-Python
    code ek time pe ek hi core pe chalta hai. Threads "concurrent" hain (interleave
    karte hain) par CPU-bound pure Python ke liye truly "parallel" nahi hain.

KYO NEED PADI:
    CPython memory ko reference counting se manage karta hai — har object ka ek
    refcount hota hai jo set/decref hota rehta hai. Agar do threads bina lock ke
    ek hi object ka refcount ek saath touch karein to race condition -> count
    corrupt -> double-free ya memory leak. GIL ek single coarse lock deke is
    refcounting ko thread-safe bana deta hai, bina har object pe fine-grained lock
    lagaye. Iska bonus: single-thread code fast rehta hai aur C extensions likhna
    aasaan hota hai.

KAISE USE KARTE HAIN:
    GIL koi API nahi hai jo tum call karte ho — ye interpreter ke andar baitha hai.
    Tum bas ye samajh ke use karte ho: GIL blocking I/O pe RELEASE hota hai (file,
    socket, DB, network) aur well-behaved C extensions ke andar bhi (numpy, hashlib
    big buffers, zlib). Isliye I/O-bound kaam ke liye threading.Thread theek hai,
    par CPU-bound pure Python ke liye multiprocessing (separate processes = separate
    interpreters = separate GIL) use karte ho.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: N tables ko parallel fetch karna — ye I/O-bound hai
       (DB wait), to ThreadPoolExecutor sahi choice hai, GIL DB-wait pe release
       hota hai.
    2. Niroskos SaaS: ek request me 5 external APIs (payment gateway, email, SMS)
       ko concurrently hit karna — threads se latency kam, kyunki network wait pe
       GIL chhut jaata hai.
    3. Celery worker: CPU-heavy task (PDF render, image resize, report crunch) ko
       threads se speed up karne ki koshish FAIL hogi — process-based concurrency
       (prefork) ya multiprocessing chahiye.
    4. Payment reconciliation: 1L transactions pe pure-Python hashing/diff — threads
       se faayda nahi; multiprocessing.Pool se cores use karo.
    5. Odoo/ETL migration: bulk row transform (pure Python) CPU-bound -> processes;
       par source/target DB reads I/O-bound -> threads.

INTERVIEW ANSWER (English — recite this):
    "The GIL is a process-wide mutex in CPython that allows only one thread to
    execute Python bytecode at any given moment. It exists primarily to protect
    CPython's reference-counting memory management — without it, two threads
    mutating an object's refcount concurrently would corrupt it and cause
    double-frees or leaks, so a single coarse lock is cheaper and simpler than
    fine-grained per-object locking. The key consequence is that threads do not
    give you parallelism for CPU-bound pure-Python code — two CPU-bound threads
    run no faster, sometimes slower, than one because of GIL hand-off and
    context-switch overhead (the convoy effect). However,
    the GIL is released during blocking I/O and inside C extensions like numpy or
    hashlib, so threads are excellent for I/O-bound workloads and for offloading
    heavy C-level computation. For genuine CPU parallelism in pure Python I reach
    for multiprocessing, which spawns separate processes each with its own
    interpreter and GIL, at the cost of IPC and serialization overhead. The forward
    note is Python 3.13's optional free-threaded build (PEP 703), which can disable
    the GIL entirely — it makes pure-Python threads truly parallel but is still
    experimental and can slow down single-threaded code."

================================================================================
Run:
    python 18_gil_mechanics.py          # saare sections chalao
    python 18_gil_mechanics.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — one-thread-at-a-time proof + 3.13 free-threaded build introspection
    2. DEMO  — CPU-bound: threads NOT faster (sometimes slower) vs serial
    3. REAL  — I/O-bound (SAP HANA fetch): threads FASTER because GIL released on wait
    4. REAL  — CPU-bound bypass: multiprocessing uses real cores (payment crunch)
    5. BREAK — "threads = speedup" myth: thread CPU work, see no/negative gain + fix
    6. TODO  — tum khud likho: pick threads vs processes for a given workload
================================================================================
"""
from __future__ import annotations

import os
import sys
import sysconfig
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


# === SECTION 1: DEMO — one-thread-at-a-time proof + free-threaded build check ===
def section1() -> None:
    print("\n=== SECTION 1: GIL exists — one thread runs Python bytecode at a time ===")

    # Kya ye build GIL-disabled (3.13+ free-threaded / "nogil") hai?
    # sys._is_gil_enabled() sirf 3.13+ pe hai; isliye getattr se safe check.
    gil_check = getattr(sys, "_is_gil_enabled", None)
    if gil_check is not None:
        print(f"  Python {sys.version.split()[0]} — sys._is_gil_enabled() = {gil_check()}")
    else:
        print(f"  Python {sys.version.split()[0]} — sys._is_gil_enabled() not present")
        print("  (matlab normal GIL build hai; ye API 3.13+ free-threaded me aayi.)")

    # Free-threaded build ka config flag (3.13+). 1 = nogil build available.
    free_threaded = sysconfig.get_config_var("Py_GIL_DISABLED")
    print(f"  sysconfig Py_GIL_DISABLED = {free_threaded!r}  (1 => free-threaded build)")

    # Proof of seriality: do threads ek SHARED list me append karte hain.
    # GIL ke kaaran in pure-Python ops ke beech race se data corrupt nahi hota —
    # ek hi thread ek time pe bytecode chala raha hota hai.
    import threading

    shared: list[int] = []

    def worker(tag: int) -> None:
        for _ in range(50_000):
            shared.append(tag)  # pure-Python op; GIL ki wajah se atomic-ish dikhta

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start(); t2.start(); t1.join(); t2.join()

    # Agar truly parallel bina lock hote to list internal state corrupt ho sakta;
    # yahan total count exact hai kyunki GIL ne bytecode-level serialization diya.
    print(f"  2 threads ne shared list me append kiya -> len = {len(shared):,}")
    print("  Exactly 100,000 (50k x 2) — koi append lost/corrupt nahi (GIL serialized).")


# === SECTION 2: DEMO — CPU-bound: threads NOT faster than serial ===
def _cpu_burn(n: int) -> int:
    # Pure-Python tight loop = CPU-bound. NUMPY/C extension nahi, isliye GIL
    # poore loop ke dauraan HELD rehta hai -> dusra thread wait karta hai.
    total = 0
    for i in range(n):
        total += i * i
    return total


def section2() -> None:
    print("\n=== SECTION 2: CPU-bound — threads do NOT beat serial (GIL held) ===")
    n = 2_000_000

    # Serial: do baar kaam, ek ke baad ek
    t0 = time.perf_counter()
    _cpu_burn(n); _cpu_burn(n)
    serial = time.perf_counter() - t0

    # Threaded: do threads, "lagta hai" parallel — par GIL ek time pe ek hi
    # thread ko bytecode chalane deta hai, to wall-time ghatega nahi.
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(_cpu_burn, [n, n]))
    threaded = time.perf_counter() - t0

    print(f"  serial   (1 thread, 2 tasks): {serial:.3f}s")
    print(f"  threaded (2 threads, 2 tasks): {threaded:.3f}s")
    speedup = serial / threaded if threaded else float("inf")
    print(f"  speedup = {speedup:.2f}x  (~1x ya kam expected — NO real parallelism)")
    print("  CPU-bound pure Python pe threads se faayda nahi: GIL serialize karta hai.")


# === SECTION 3: REAL — I/O-bound (SAP HANA fetch): threads FASTER ===
def _fake_hana_fetch(table: str) -> str:
    # Real DB/network call ki tarah: thread yahan BLOCK hota hai (wait).
    # time.sleep() / socket / DB driver blocking I/O pe Python GIL RELEASE
    # kar deta hai -> doosra thread is dauraan apna kaam kar leta hai.
    time.sleep(0.10)  # ~100ms "DB round-trip" simulate (chhota rakha test fast)
    return f"{table}:rows_fetched"


def section3() -> None:
    print("\n=== SECTION 3: I/O-bound (SAP HANA fetch) — threads ARE faster ===")
    tables = ["customers", "invoices", "payments", "ledger"]

    # Serial: har table ka 100ms wait, ek-ek karke -> ~400ms
    t0 = time.perf_counter()
    serial_results = [_fake_hana_fetch(tbl) for tbl in tables]
    serial = time.perf_counter() - t0

    # Threaded: sab waits OVERLAP ho jaate hain kyunki sleep/I/O pe GIL release
    # hota hai -> total ~100ms (sabse lambe single wait ke aas-paas).
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(tables)) as ex:
        threaded_results = list(ex.map(_fake_hana_fetch, tables))
    threaded = time.perf_counter() - t0

    print(f"  serial   ({len(tables)} tables one-by-one): {serial:.3f}s")
    print(f"  threaded ({len(tables)} tables concurrent): {threaded:.3f}s")
    speedup = serial / threaded if threaded else float("inf")
    print(f"  speedup = {speedup:.2f}x  (~{len(tables)}x ke kareeb — GIL waits pe release hua)")
    print(f"  sample -> {threaded_results[0]}")
    print("  I/O-bound (DB/network/file) pe threading PERFECT hai — yahi SAP connector pattern.")


# === SECTION 4: REAL — CPU-bound bypass: multiprocessing uses real cores ===
def _payment_crunch(chunk: int) -> int:
    # CPU-bound pure-Python kaam (jaise reconciliation hashing/diff).
    total = 0
    for i in range(chunk):
        total += (i ^ (i << 1)) % 7
    return total


def section4() -> None:
    print("\n=== SECTION 4: CPU-bound bypass — multiprocessing = real parallelism ===")
    chunk = 1_500_000
    tasks = [chunk, chunk]
    cores = os.cpu_count() or 1
    print(f"  detected cores = {cores}")

    # Serial baseline
    t0 = time.perf_counter()
    [_payment_crunch(c) for c in tasks]
    serial = time.perf_counter() - t0

    # Processes: har process ka APNA interpreter + APNA GIL -> sach me parallel.
    # Cost: process spawn + pickle/IPC overhead (chhote kaam pe ulta mehenga).
    t0 = time.perf_counter()
    try:
        with ProcessPoolExecutor(max_workers=2) as ex:
            list(ex.map(_payment_crunch, tasks))
        proc = time.perf_counter() - t0
        print(f"  serial      (2 tasks):              {serial:.3f}s")
        print(f"  multiprocess(2 procs, 2 GILs):      {proc:.3f}s")
        speedup = serial / proc if proc else float("inf")
        if cores >= 2:
            print(f"  speedup = {speedup:.2f}x  (>1x on multi-core — GIL bypassed by processes)")
        else:
            print(f"  speedup = {speedup:.2f}x  (single-core box, isliye gain kam)")
    except Exception as e:  # noqa: BLE001 — sandbox me spawn restrict ho sakta hai
        print(f"  multiprocessing yahan unavailable ({type(e).__name__}: {e})")
        print(f"  (concept: serial tha {serial:.3f}s; processes alag GIL pe parallel chalte.)")
    print("  CPU-bound parallelism chahiye -> processes, NOT threads (GIL ko bypass karo).")


# === SECTION 5: BREAK IT / GOTCHA — "threads make CPU work faster" myth ===
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — 'add threads => faster' myth on CPU work ===")
    n = 1_500_000

    # ---- GALAT mental model: "4 threads = 4x speed" ----
    # Junior log report-generation jaise CPU kaam ko threads me daal dete hain
    # aur expect karte hain 4x. GIL ki wajah se ulta thread-switching overhead
    # add hota hai -> often same ya SLOWER than serial.
    t0 = time.perf_counter()
    _cpu_burn(n); _cpu_burn(n); _cpu_burn(n); _cpu_burn(n)
    serial = time.perf_counter() - t0

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(_cpu_burn, [n, n, n, n]))
    threaded = time.perf_counter() - t0

    print("  WRONG assumption: '4 threads CPU kaam ko ~4x fast karenge'")
    print(f"    serial   (4 tasks): {serial:.3f}s")
    print(f"    4 threads          : {threaded:.3f}s")
    ratio = serial / threaded if threaded else float("inf")
    verdict = "SLOWER" if ratio < 0.98 else ("~SAME" if ratio < 1.3 else "faster?!")
    print(f"    result -> {ratio:.2f}x  => {verdict}  (NO 4x; GIL + switch overhead)")

    # ---- FIX: same CPU kaam ko PROCESSES me daalo -> real cores use ----
    cores = os.cpu_count() or 1
    try:
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=min(4, cores)) as ex:
            list(ex.map(_cpu_burn, [n, n, n, n]))
        proc = time.perf_counter() - t0
        pratio = serial / proc if proc else float("inf")
        print("  FIX: same kaam ProcessPoolExecutor me (har process apna GIL):")
        print(f"    {min(4, cores)} processes: {proc:.3f}s  => {pratio:.2f}x vs serial")
    except Exception as e:  # noqa: BLE001
        print(f"  FIX (processes) yahan run nahi ho paya: {type(e).__name__}: {e}")
    print("  Lesson: CPU-bound => processes; threads sirf I/O-bound pe madad karte hain.")


# === SECTION 6: TODO — tum khud likho: choose threads vs processes ===
def choose_executor(workload: str) -> str:
    """
    TODO (tum implement karo):
      Ek helper banao jo workload type dekh ke sahi concurrency tool suggest kare.
      Input `workload` in me se ek hoga (lowercase):
          "db_fetch"        -> SAP HANA se rows laana (network/DB wait)  -> I/O-bound
          "api_calls"       -> payment gateway + email + SMS hit karna    -> I/O-bound
          "file_read"       -> bade files read karna                      -> I/O-bound
          "pdf_render"      -> pure-Python report/PDF crunch              -> CPU-bound
          "hash_reconcile"  -> 1L txns pe pure-Python hashing/diff        -> CPU-bound

      Return EXACTLY in se ek string:
          "threads"   -> agar workload I/O-bound hai (GIL wait pe release hota)
          "processes" -> agar workload CPU-bound pure Python hai (GIL bypass chahiye)

      Expected behaviour:
          choose_executor("db_fetch")       -> "threads"
          choose_executor("pdf_render")     -> "processes"
          choose_executor("hash_reconcile") -> "processes"
      Hint: ek set me I/O-bound names rakho; us set me hai to "threads", warna
            "processes". Unknown input pe ValueError raise kar sakte ho.
    """
    raise NotImplementedError("TODO: I/O-bound => 'threads', CPU-bound => 'processes' return karo")


def section6() -> None:
    print("\n=== SECTION 6: TODO — threads vs processes chooser (tum likho) ===")
    cases = {
        "db_fetch": "threads",
        "api_calls": "threads",
        "file_read": "threads",
        "pdf_render": "processes",
        "hash_reconcile": "processes",
    }
    try:
        all_ok = True
        for workload, expected in cases.items():
            got = choose_executor(workload)
            ok = got == expected
            all_ok = all_ok and ok
            mark = "OK" if ok else "WRONG"
            print(f"  choose_executor({workload!r}) -> {got!r}  (expected {expected!r}) [{mark}]")
        print("  correct! workload classification sahi hai." if all_ok
              else "  kuch cases galat — I/O vs CPU classification dobara dekho.")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")


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
    main()
