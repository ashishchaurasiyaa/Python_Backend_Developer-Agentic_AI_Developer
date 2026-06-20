"""
================================================================================
TOPIC: Thread Pools & Process Pools (concurrent.futures)
================================================================================

KYA HOTA HAI:
    concurrent.futures ek high-level interface deta hai parallel kaam chalane ke
    liye. Do executors hote hain: ThreadPoolExecutor (threads ka pool) aur
    ProcessPoolExecutor (alag OS processes ka pool). Dono ka API EXACTLY same
    hai — submit(), map(), shutdown() — sirf "worker" ki nature alag hai. submit()
    ek Future object return karta hai jo abhi-ya-baad-me-aane-wale result ka
    placeholder hota hai.

KYO NEED PADI:
    Sequentially N kaam karna slow hai. Threads IO-wait (network/disk/DB) ke
    dauran GIL release kar dete hain, to IO-bound kaam (HTTP calls, SAP HANA
    queries) thread pool me overlap ho jaate hain. Par pure CPU-bound kaam (hashing,
    parsing, number crunching) me GIL ek hi thread ko CPU dene deta hai — wahan
    threads se speedup NAHI milta, processes chahiye (har process ka apna GIL).
    raw threading/multiprocessing me lifecycle, result-collection aur exception
    handling khud manage karna padta tha; futures ye sab clean kar deta hai.

KAISE USE KARTE HAIN:
    `with ThreadPoolExecutor(max_workers=N) as ex:` banao. Phir ya to
    `fut = ex.submit(fn, *args)` karke Future lo aur `fut.result()` se nateeja,
    ya `ex.map(fn, iterable)` se ordered results stream karo. Jab results jaise-jaise
    ready ho waise process karne ho to `as_completed(futures)` use karo. Context
    manager exit pe pool clean shutdown ho jaata hai (saare kaam khatam hone tak wait).

KAHAN USE HOTA HAI (backend scenarios):
    1. Fan-out: ek request me 10 downstream HTTP/microservice calls parallel maarna
       (ThreadPool, IO-bound) instead of serial — p95 latency gir jaati hai.
    2. SAP HANA connector: kai independent idempotent queries ek saath fire karna,
       as_completed se jo pehle aaye usko aage bhejna, fail hue ko retry queue me.
    3. Niroskos multi-tenant: per-tenant report generation parallel chalana.
    4. CPU-bound batch: invoice PDFs ka hashing / image resize / heavy parsing —
       ProcessPoolExecutor se saare cores use, GIL bypass.
    5. Celery alternative for in-process bounded parallelism jab full broker overkill ho.

INTERVIEW ANSWER (English — recite this):
    "concurrent.futures gives me two interchangeable executors with an identical
    API: ThreadPoolExecutor and ProcessPoolExecutor. I choose threads for IO-bound
    work — HTTP fan-out, database calls, file IO — because the GIL is released
    during the wait, so the calls overlap. I choose processes for CPU-bound work
    like hashing or parsing, because each process has its own GIL and can actually
    use multiple cores. submit() returns a Future, a handle to a result that may
    not exist yet; I use as_completed() when I want to react to results in finish
    order and handle each one's exception independently, and map() when I want
    results back in input order. Tuning max_workers matters: for IO I oversubscribe
    well past the core count since workers mostly wait, but for CPU I keep it near
    os.cpu_count() to avoid context-switch thrash. The senior gotcha is that an
    exception inside a task is stored on its Future, not raised at submit time — it
    only surfaces when you call result(), so a fire-and-forget pool silently swallows
    failures. And for processes, every argument and return value must be picklable
    and the worker function must be top-level/importable, otherwise it blows up at
    dispatch — closures and lambdas don't survive the process boundary."

================================================================================
Run:
    python 21_thread_and_process_pools.py        # saare sections chalao
    python 21_thread_and_process_pools.py 1 4    # sirf section 1 aur 4

Sections:
    1. DEMO  — ThreadPool submit + result(); Future kya hota hai (running/done)
    2. DEMO  — as_completed (finish order) vs map (input order) — fark dikhao
    3. DEMO  — Thread (IO) vs Process (CPU): same API, alag kaam ke liye
    4. REAL  — fan-out N HTTP-like calls parallel; as_completed se result/exception
    5. BREAK — exception Future me chhup jaati hai; result() pe phootti hai (FIX)
    6. BREAK — ProcessPool picklability: lambda/closure fail, top-level fn works
    7. TODO  — tum khud likho: bounded-retry fan-out (fail hue calls dobara try)
================================================================================
"""
from __future__ import annotations

import math
import os
import sys
import time
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)


# === SECTION 1: DEMO — ThreadPool submit + result(); Future lifecycle ===
def _io_task(name: str, delay: float) -> str:
    # IO-bound ko simulate karta hai (sleep = network/DB wait); GIL release hota hai
    time.sleep(delay)
    return f"{name}-done"


def section1() -> None:
    print("\n=== SECTION 1: ThreadPool submit() + Future + result() ===")
    with ThreadPoolExecutor(max_workers=3) as ex:
        # submit() turant lautata hai — kaam background me chalu, hume Future milta hai
        fut = ex.submit(_io_task, "job", 0.05)
        # submit ke turant baad: kaam abhi chalu hai, result ready nahi
        print(f"  submit() ke turant baad -> done()={fut.done()}  (abhi chal raha)")
        # result() BLOCK karta hai jab tak nateeja na aaye, phir value deta hai
        value = fut.result()
        print(f"  result() ke baad        -> done()={fut.done()}  value={value!r}")
        print("  Lesson: submit() non-blocking hai; Future = 'baad me milega' ka handle, "
              "result() us par wait karta hai.")


# === SECTION 2: DEMO — as_completed (finish order) vs map (input order) ===
def section2() -> None:
    print("\n=== SECTION 2: as_completed (finish order) vs map (input order) ===")
    # delays ulte order me: pehla sabse slow, aakhri sabse fast
    jobs = [("A", 0.15), ("B", 0.10), ("C", 0.05)]

    print("  as_completed -> jo pehle KHATAM ho wahi pehle aayega:")
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(_io_task, n, d) for n, d in jobs]
        for fut in as_completed(futures):
            print(f"    arrived: {fut.result()!r}")
    print("    notice: C, B, A order me aaye (fast pehle) — submit order se alag.")

    print("  map -> hamesha INPUT order me, chahe kaun pehle khatam ho:")
    with ThreadPoolExecutor(max_workers=3) as ex:
        for name, result in zip(
            (n for n, _ in jobs),
            ex.map(_io_task, (n for n, _ in jobs), (d for _, d in jobs)),
        ):
            print(f"    mapped : {result!r}")
    print("    notice: A, B, C order me — map results ko input order me deta hai.")
    print("  Lesson: latency-sensitive streaming -> as_completed; deterministic "
          "aligned output -> map.")


# === SECTION 3: DEMO — Thread (IO) vs Process (CPU): same API ===
def _cpu_task(n: int) -> int:
    # CPU-bound: koi IO nahi, pure computation (GIL yahan threads ko block karta)
    total = 0
    for i in range(2, n):
        total += int(math.sqrt(i))
    return total


def section3() -> None:
    print("\n=== SECTION 3: Thread (IO) vs Process (CPU) — same API, alag kaam ===")
    n = 400_000
    workloads = [n, n, n, n]

    # ThreadPool: CPU-bound kaam me GIL ki wajah se sequential jaisa, speedup ~nahi
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:
        thread_results = list(ex.map(_cpu_task, workloads))
    t_thread = time.perf_counter() - t0

    # ProcessPool: har process apna GIL -> sach me parallel cores use
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=4) as ex:
        proc_results = list(ex.map(_cpu_task, workloads))
    t_proc = time.perf_counter() - t0

    print(f"  results match: {thread_results == proc_results}")
    print(f"  ThreadPool (CPU-bound): {t_thread:.3f}s  <- GIL ki wajah se overlap nahi")
    print(f"  ProcessPool(CPU-bound): {t_proc:.3f}s  <- multiple cores actually use")
    print("  Lesson: API bilkul same (.map), par CPU-bound ke liye Process chahiye; "
          "IO-bound (sleep/network) ke liye Thread sasta aur kaafi hai.")


# === SECTION 4: REAL — fan-out N HTTP-like calls; as_completed result/exception ===
def _fake_http_get(url: str) -> dict[str, object]:
    # Real HTTP call ki jagah simulate: thoda latency, aur ek endpoint fail karta hai.
    # (No real network — sleeps chhote rakhe hain.)
    latency = {"/users": 0.04, "/orders": 0.06, "/billing": 0.03, "/audit": 0.05}
    time.sleep(latency.get(url, 0.02))
    if url == "/billing":
        raise TimeoutError("billing upstream 504")
    return {"url": url, "status": 200}


def section4() -> None:
    print("\n=== SECTION 4: REAL — fan-out N HTTP-like calls (parallel) ===")
    urls = ["/users", "/orders", "/billing", "/audit"]

    # Serial me yeh sum-of-latencies leta; thread pool me max-of-latencies (overlap).
    # max_workers IO-bound hai isliye N ke barabar/zyada rakhna theek hai (workers wait karte).
    ok: list[dict[str, object]] = []
    failed: list[tuple[str, str]] = []

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(urls)) as ex:
        # Future -> url ka mapping rakho taaki failure me pata chale KAUN si call giri
        fut_to_url = {ex.submit(_fake_http_get, u): u for u in urls}
        for fut in as_completed(fut_to_url):
            url = fut_to_url[fut]
            try:
                # har call ka exception independent — ek ka gir-na baaki ko nahi rokta
                resp = fut.result()
                ok.append(resp)
                print(f"    OK   {url:<9} -> {resp['status']}")
            except Exception as e:  # noqa: BLE001 (demo: har failure capture karni hai)
                failed.append((url, f"{type(e).__name__}: {e}"))
                print(f"    FAIL {url:<9} -> {type(e).__name__}: {e}")
    elapsed = time.perf_counter() - t0

    print(f"  done in {elapsed:.3f}s (overlapping, NOT sum of all latencies)")
    print(f"  succeeded={len(ok)}  failed={len(failed)}  (failed -> retry queue me daalo)")
    print("  Lesson: ek request me 4 downstream calls parallel; as_completed se jaise "
          "result aaye process karo, fail hue ko alag bucket me — yeh real fan-out pattern hai.")


# === SECTION 5: BREAK IT — exception Future me chhup jaati hai ===
def _risky(n: int) -> int:
    if n == 0:
        raise ValueError("cannot process zero")
    return 100 // n


def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — exception Future me silently store hoti hai ===")

    # ---- GALAT: submit kiya, result() kabhi call nahi kiya -> failure CHUP-CHAP gayab ----
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(_risky, n) for n in (5, 0, 2)]
        # fire-and-forget: hum result() nahi padhte, bas "ho gaya" maan lete hain
    # n=0 wali task andar exception phenkti hai, par humne kabhi result() nahi kiya
    crashed = any(f.exception() is not None for f in futures)
    print("  WRONG (fire-and-forget, result() kabhi nahi padha):")
    print(f"    pool clean exit ho gaya, koi error nahi dikha — par crash hua tha? {crashed}")
    print("    Reason: task ki exception us Future ke andar store hoti hai, submit pe "
          "raise NAHI hoti. result() na padho to failure dab jaata hai (data loss/silent bug).")

    # ---- SAHI: har Future ka result()/exception() padho, failure handle karo ----
    print("  FIX (har result() padho, exception ko handle/log karo):")
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_to_n = {ex.submit(_risky, n): n for n in (5, 0, 2)}
        for fut in as_completed(fut_to_n):
            n = fut_to_n[fut]
            try:
                print(f"    n={n} -> {fut.result()}")
            except Exception as e:  # noqa: BLE001
                print(f"    n={n} -> handled {type(e).__name__}: {e}")
    print("  Lesson: pool exceptions ko swallow karta hai — hamesha result()/exception() "
          "padho, warna failures silently kho jaayenge.")


# === SECTION 6: BREAK IT — ProcessPool picklability caveat ===
def squared_top_level(x: int) -> int:
    # Top-level (module-level) function — picklable hai, process boundary cross kar sakta hai.
    return x * x


def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — ProcessPool picklability (lambda/closure fail) ===")

    # ---- GALAT: lambda ProcessPool me pickle nahi ho sakta -> error at dispatch ----
    print("  WRONG (lambda ko ProcessPoolExecutor.map me bhejna):")
    try:
        with ProcessPoolExecutor(max_workers=2) as ex:
            # lambda picklable nahi -> result lene par hi error surface hoga
            list(ex.map(lambda x: x * x, [1, 2, 3]))
        print("    (unexpected: error nahi aaya)")
    except Exception as e:  # noqa: BLE001
        print(f"    -> {type(e).__name__}: {e}")
        print("    Reason: process worker ko function PICKLE karke bhejna padta hai; "
              "lambda/closure/nested fn picklable nahi hote.")

    # ---- SAHI: top-level importable function bhejo (pickle ho jaata hai) ----
    print("  FIX (top-level function squared_top_level use karo):")
    with ProcessPoolExecutor(max_workers=2) as ex:
        out = list(ex.map(squared_top_level, [1, 2, 3]))
    print(f"    result -> {out}")
    print("  Lesson: ProcessPool me fn aur saare args/returns PICKLABLE + importable hone "
          "chahiye. Yehi caveat Threads me nahi hai (same memory) — isliye threads me "
          "lambda/closure chal jaata hai par process me nahi.")


# === SECTION 7: TODO — tum khud likho: bounded-retry fan-out ===
def _flaky_call(url: str, _attempt_state: dict[str, int]) -> dict[str, object]:
    # Helper: pehli baar fail karta hai, dusri baar pass — retry practice ke liye.
    _attempt_state[url] = _attempt_state.get(url, 0) + 1
    time.sleep(0.02)
    if _attempt_state[url] < 2 and url == "/payments":
        raise ConnectionError("transient reset")
    return {"url": url, "status": 200, "attempts": _attempt_state[url]}


def fan_out_with_retry(urls: list[str], max_retries: int = 2) -> dict[str, object]:
    """
    TODO (tum implement karo):
      Ek thread pool fan-out likho jo failed calls ko bounded retry kare.
      Behaviour:
        - ek ThreadPoolExecutor banao (max_workers = len(urls), IO-bound).
        - har url ke liye _flaky_call(url, state) submit karo (state ek shared dict
          rakho jo attempt count track kare — already upar diya hai pattern).
        - as_completed se results collect karo; jo Future exception() de usko
          "pending retry" list me daalo.
        - jab tak pending non-empty hai AUR retry budget bacha hai, pending ko
          dobara submit karo (same pool me) aur loop repeat karo.
        - return: {"ok": [...successful resp dicts...], "failed": [...urls jo
          max_retries ke baad bhi gire...]}.
      Expected (roughly): "/payments" pehli baar girta hai par retry pe pass ho jaata,
      to aakhir me ok me aana chahiye, failed khaali.
      Hint: Future->url mapping har round me rebuild karo; result() try/except me padho.
    """
    raise NotImplementedError(
        "TODO: thread pool fan-out + bounded retry implement karo (ok/failed return karo)"
    )


def section7() -> None:
    print("\n=== SECTION 7: TODO — bounded-retry fan-out (tum likho) ===")
    urls = ["/users", "/payments", "/orders"]
    try:
        result = fan_out_with_retry(urls, max_retries=2)
        ok_urls = sorted(r["url"] for r in result["ok"])  # type: ignore[union-attr]
        print(f"  ok     -> {ok_urls}")
        print(f"  failed -> {result['failed']}")
        if ok_urls == ["/orders", "/payments", "/users"] and not result["failed"]:
            print("  correct! transient /payments retry pe recover ho gaya.")
        else:
            print("  output expected se alag — retry loop / pending logic dobara dekho.")
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
    # ProcessPoolExecutor child processes parent module ko import karte hain (spawn/fork);
    # isliye worker functions top-level hone chahiye aur heavy code is guard ke neeche ho.
    _ = os.cpu_count  # (reference: max_workers tuning yahin se aata hai — IO>cores, CPU~=cores)
    main()
