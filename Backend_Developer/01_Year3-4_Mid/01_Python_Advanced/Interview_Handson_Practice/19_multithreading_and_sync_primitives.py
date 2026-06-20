"""
================================================================================
TOPIC: Multithreading & Synchronization Primitives
================================================================================

KYA HOTA HAI:
    threading module se hum ek hi process ke andar multiple threads bana sakte
    hain (Thread.start() / join()). Threads memory SHARE karte hain — same
    variables, same objects. Isi sharing ki wajah se "race condition" aati hai
    jab do threads ek hi cheez ko bina coordination ke read-modify-write karein.
    Sync primitives (Lock, RLock, Semaphore, Event, Condition, Queue) hi wo tools
    hain jinse hum is shared access ko safe aur ordered banate hain.

KYO NEED PADI:
    Bina lock ke `counter += 1` ek ATOMIC operation nahi hai — wo internally
    load -> add -> store hai, aur beech me thread switch ho sakta hai, isliye
    updates "lost" ho jaate hain aur total galat aata hai. CPython me GIL hai par
    GIL time-based switch interval (~5ms, sys.getswitchinterval()) pe release hota
    hai aur hand-off agle bytecode boundary pe land karta hai — yaani thread beech-e-`+=`
    suspend ho sakta hai. To ye galtfehmi mat rakho ki GIL tumhe race conditions se bacha lega. Need padi: shared state ko corrupt
    hone se rokne ke liye aur threads ke beech safe hand-off / signalling ke liye.

KAISE USE KARTE HAIN:
    Thread(target=fn, args=...).start() banata hai, join() wait karta hai khatam
    hone ka. Critical section ko `with lock:` me wrap karo (RAII-style release).
    RLock tab jab same thread ko nested acquire chahiye. Semaphore se bounded
    resource (connection pool / concurrency cap). Event se ek simple "go" signal,
    Condition se producer/consumer wait/notify. Best practice: shared data direct
    chhuo mat — queue.Queue se hand-off karo, jo internally already thread-safe hai.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: bounded connection pool — sirf N concurrent HANA calls
       allow karo (Semaphore), warna server overwhelm/throttle ho jaata hai.
    2. Celery/Redis pipeline jaisa local producer-consumer: worker threads queue
       se jobs uthayein (queue.Queue) — safe hand-off, koi manual lock nahi.
    3. Payment gateway idempotency: ek hi idempotency-key pe do retry threads ek
       saath na charge kar dein — Lock se critical section guard karo.
    4. Niroskos multi-tenant: shared in-memory cache/metrics counter ko concurrent
       request threads se safely update karna (Lock / atomic increment).
    5. Background flush thread + main thread: Event se "shutdown/start" signal,
       daemon thread se fire-and-forget background work jo process ke saath mar jaaye.
    6. Rate limiter / quota: Condition se threads tab tak wait karwana jab tak
       token/slot available na ho.

INTERVIEW ANSWER (English — recite this):
    "Python threads share process memory, so any read-modify-write on shared state
    is a race condition unless it is protected. The classic example is a shared
    counter where many threads do counter += 1: that statement is not atomic, it is
    a load, add, and store, and a thread can be switched out in the middle, so
    increments get lost and the final total is wrong. The fix is a threading.Lock
    around the critical section, ideally with a with-statement so it is always
    released. A common senior misconception is that the GIL makes this safe — it
    does not, because the interpreter releases the GIL on a time-based switch
    interval (~5ms) and the hand-off lands at a bytecode boundary, so a thread can
    be suspended mid-increment and you still need explicit locks. I pick the primitive by intent: Lock for mutual
    exclusion, RLock when the same thread must re-acquire it (recursive or nested
    calls), Semaphore to cap concurrency such as a bounded connection pool, Event
    for a one-shot broadcast signal, and Condition for wait/notify producer-consumer
    coordination. In practice my default for moving work between threads is
    queue.Queue, because it is already internally synchronized and lets me avoid
    hand-rolled locking entirely. I also mark background helper threads as daemon so
    they do not block process exit, and remember the real gotcha: for CPU-bound work
    threads do not give parallelism because of the GIL, so there I reach for
    multiprocessing or a C-extension instead."

================================================================================
Run:
    python 19_multithreading_and_sync_primitives.py        # saare sections
    python 19_multithreading_and_sync_primitives.py 2 3    # sirf section 2 aur 3

Sections:
    1. DEMO  — Thread start()/join() basics + daemon thread (process ke saath marta)
    2. BREAK — shared-counter race condition (no lock => galat total) + Lock FIX
    3. DEMO  — RLock: same thread nested acquire (Lock yahan deadlock kar deta)
    4. REAL  — Semaphore: SAP HANA bounded connection pool (max N concurrent)
    5. REAL  — Event: background flush thread ko start/stop signal dena
    6. REAL  — Condition: producer/consumer wait/notify (bounded buffer)
    7. REAL  — queue.Queue: preferred safe hand-off (worker pool, no manual lock)
    8. TODO  — tum khud likho: payment idempotency guard (Lock + per-key dedupe)
================================================================================
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Optional


# === SECTION 1: DEMO — Thread start()/join() + daemon thread ===
def section1() -> None:
    print("\n=== SECTION 1: Thread start()/join() + daemon thread ===")

    results: list[str] = []

    def worker(name: str) -> None:
        # thoda "kaam" — chhota sleep, taaki interleaving dikhe
        time.sleep(0.05)
        results.append(f"{name} done on thread={threading.current_thread().name}")

    # start() naya OS thread launch karta hai; target function wahan chalta hai
    t1 = threading.Thread(target=worker, args=("job-A",), name="W-A")
    t2 = threading.Thread(target=worker, args=("job-B",), name="W-B")
    t1.start()
    t2.start()

    # join() => main thread wait karta hai jab tak ye threads khatam na ho jaayein.
    # Bina join ke main aage badh jaata aur results adhoora dikhta.
    t1.join()
    t2.join()
    print(f"  both finished, results = {results}")

    # ---- daemon thread: background helper jo process exit ko BLOCK nahi karta ----
    def heartbeat() -> None:
        # asli code me ye loop hota; yahan ek hi tick, demo ke liye
        time.sleep(0.02)

    d = threading.Thread(target=heartbeat, name="heartbeat", daemon=True)
    d.start()
    print(f"  daemon thread started: is_daemon={d.daemon} "
          f"(process exit pe ye apne aap mar jaayega, koi join zaroori nahi)")
    print("  Lesson: non-daemon threads ka join() zaroori; daemon background "
          "helpers ke liye theek (interpreter unhe abruptly maar deta hai).")


# === SECTION 2: BREAK IT / GOTCHA — shared-counter race condition + Lock fix ===
def section2() -> None:
    print("\n=== SECTION 2: BREAK IT — shared-counter race (no lock) + Lock fix ===")

    n_threads = 8
    per_thread = 1_000
    expected = n_threads * per_thread

    # ---- GALAT: bina lock ke counter += 1 ----
    # counter += 1 = load, add, store. Beech me thread switch -> updates lost.
    # Real machine pe choti loop me CPython aksar += ko ek hi switch-interval me
    # nipta deta, isliye race kabhi-kabhi chhup jaata. Race ko RELIABLY dikhane
    # ke liye yahan hum read-modify-write ko jaan-boojhke "stretch" karte hain:
    # local me padho -> thread ko yield karwao -> wapas likho. Yehi non-atomic
    # read-modify-write ka asli structure hai, bas window bada kar diya.
    class UnsafeCounter:
        def __init__(self) -> None:
            self.value = 0

        def incr(self) -> None:
            tmp = self.value         # load
            time.sleep(0)            # force scheduler ko yahin switch karne ka mauka
            self.value = tmp + 1     # store (tmp purana ho chuka -> update lost)

    unsafe = UnsafeCounter()

    def bump_unsafe() -> None:
        for _ in range(per_thread):
            unsafe.incr()

    threads = [threading.Thread(target=bump_unsafe) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("  WRONG (no lock):")
    print(f"    expected = {expected}, got = {unsafe.value}")
    print(f"    lost updates = {expected - unsafe.value} "
          f"({'race hua!' if unsafe.value != expected else 'is run me bach gaya — par bharosa mat karo'})")
    print("    Reason: += atomic nahi; GIL bhi bachata nahi (switch-interval pe GIL release, beech-e-operation).")

    # ---- SAHI: Lock se critical section guard ----
    class SafeCounter:
        def __init__(self) -> None:
            self.value = 0
            self._lock = threading.Lock()

        def incr(self) -> None:
            with self._lock:        # acquire on enter, release on exit (exception-safe)
                self.value += 1

    safe = SafeCounter()

    def bump_safe() -> None:
        for _ in range(per_thread):
            safe.incr()

    threads = [threading.Thread(target=bump_safe) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("  FIX (threading.Lock):")
    print(f"    expected = {expected}, got = {safe.value} "
          f"({'OK' if safe.value == expected else 'still wrong?!'})")
    print("  Lesson: shared mutable state ka har read-modify-write Lock me wrap karo.")


# === SECTION 3: DEMO — RLock (same thread nested acquire) ===
def section3() -> None:
    print("\n=== SECTION 3: RLock — same thread nested acquire ===")

    # Scenario: ek method public hai jo lock leta hai, aur internally ek aur
    # locked method ko call karta hai (same thread). Plain Lock yahan DEADLOCK
    # kar deta — kyunki Lock non-reentrant hai, same thread dobara acquire pe
    # khud ka hi wait karega. RLock owner-thread ko re-acquire allow karta hai.
    rlock = threading.RLock()
    log: list[str] = []

    def inner() -> None:
        with rlock:                  # same thread, nested acquire — RLock OK
            log.append("inner: lock dobara mila (reentrant)")

    def outer() -> None:
        with rlock:
            log.append("outer: lock liya")
            inner()                  # plain Lock hota to yahin atak jaata
            log.append("outer: inner ke baad bhi lock paas hai")

    t = threading.Thread(target=outer)
    t.start()
    t.join()
    for line in log:
        print(f"    {line}")

    # proof ki plain Lock non-reentrant hai (same thread dobara acquire = block):
    plain = threading.Lock()
    plain.acquire()
    got_again = plain.acquire(blocking=False)  # False milega — apne aap ko block karega
    plain.release()
    print(f"  plain Lock re-acquire (same thread, non-blocking) -> {got_again} "
          f"(False = non-reentrant; RLock yahan True deta)")
    print("  Lesson: agar ek locked method dusre locked method ko call kare "
          "(recursion/composition), to RLock lo — warna self-deadlock.")


# === SECTION 4: REAL — Semaphore as SAP HANA bounded connection pool ===
def section4() -> None:
    print("\n=== SECTION 4: REAL — Semaphore: SAP HANA bounded connection pool ===")

    MAX_CONNS = 2            # HANA pe sirf 2 concurrent calls allow (throttle protection)
    pool = threading.BoundedSemaphore(MAX_CONNS)

    # in-flight count track karne ke liye chhota lock (sirf demo metric ke liye)
    metric_lock = threading.Lock()
    state = {"in_flight": 0, "peak": 0}

    def hana_call(req_id: int) -> None:
        # acquire => agar 2 already chal rahe to yahan WAIT karega slot free hone tak
        with pool:
            with metric_lock:
                state["in_flight"] += 1
                state["peak"] = max(state["peak"], state["in_flight"])
                now = state["in_flight"]
            print(f"    req-{req_id}: HANA query running (in_flight={now}/{MAX_CONNS})")
            time.sleep(0.05)         # query latency simulate
            with metric_lock:
                state["in_flight"] -= 1

    threads = [threading.Thread(target=hana_call, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"  peak concurrent HANA calls = {state['peak']} "
          f"(cap {MAX_CONNS} kabhi cross nahi hua => Semaphore ne throttle kiya)")
    print("  Lesson: BoundedSemaphore = N-permit pool. release() extra ho to "
          "BoundedSemaphore turant error deta (plain Semaphore chup-chaap leak hone deta).")


# === SECTION 5: REAL — Event: background flush thread start/stop signal ===
def section5() -> None:
    print("\n=== SECTION 5: REAL — Event: background flush thread signalling ===")

    flush_now = threading.Event()    # "data flush kar do" signal
    stop = threading.Event()         # "shutdown" signal
    flushed: list[str] = []

    def background_flusher() -> None:
        # background daemon-style worker jo signal ka wait karta hai (busy-loop nahi)
        while not stop.is_set():
            # wait(timeout) => True agar event set hua, False agar timeout.
            # CPU spin nahi karta — block hota hai jab tak signal ya timeout.
            if flush_now.wait(timeout=0.2):
                flushed.append("buffer flushed to DB")
                flush_now.clear()    # signal consume kiya, agle ke liye reset
        flushed.append("flusher stopped cleanly")

    t = threading.Thread(target=background_flusher, name="flusher")
    t.start()

    # main thread se do baar flush trigger karo
    flush_now.set()
    time.sleep(0.05)
    flush_now.set()
    time.sleep(0.05)
    stop.set()                       # ab clean shutdown bolo
    t.join()

    print(f"    events recorded: {flushed}")
    print("  Lesson: Event = ek-baar broadcast flag (set/clear/wait/is_set). "
          "Polling/sleep-loop ki jagah wait() use karo — efficient aur responsive.")


# === SECTION 6: REAL — Condition: producer/consumer (bounded buffer) ===
def section6() -> None:
    print("\n=== SECTION 6: REAL — Condition: producer/consumer wait/notify ===")

    cond = threading.Condition()
    buffer: list[int] = []
    MAX_SIZE = 3
    produced_total = 5
    consumed: list[int] = []

    def producer() -> None:
        for item in range(1, produced_total + 1):
            with cond:
                # buffer full ho to wait — wait() lock chhod deta hai aur notify pe wapas leta
                while len(buffer) >= MAX_SIZE:
                    cond.wait()
                buffer.append(item)
                print(f"    produced {item}, buffer={buffer}")
                cond.notify()        # consumer ko jagao (kuchh available hai)

    def consumer() -> None:
        while len(consumed) < produced_total:
            with cond:
                while not buffer:
                    cond.wait()      # empty -> wait, lock release ho jaata hai
                item = buffer.pop(0)
                consumed.append(item)
                print(f"    consumed {item}, buffer={buffer}")
                cond.notify()        # producer ko jagao (jagah ban gayi)

    p = threading.Thread(target=producer, name="producer")
    c = threading.Thread(target=consumer, name="consumer")
    p.start()
    c.start()
    p.join()
    c.join()

    print(f"  consumed order = {consumed} (expected 1..{produced_total})")
    print("  Lesson: wait() HAMESHA `while condition:` loop me, agar ke andar nahi — "
          "spurious wakeups aur multiple waiters ke liye predicate dobara check zaroori.")


# === SECTION 7: REAL — queue.Queue: preferred safe hand-off (worker pool) ===
def section7() -> None:
    print("\n=== SECTION 7: REAL — queue.Queue: safe hand-off (worker pool) ===")

    # Yeh hai preferred pattern: shared list + manual Lock + Condition mat likho,
    # queue.Queue already internally synchronized hai. Celery/Redis ka local analog.
    jobs: queue.Queue[Optional[int]] = queue.Queue()
    results_q: queue.Queue[str] = queue.Queue()
    N_WORKERS = 3

    def worker() -> None:
        while True:
            job = jobs.get()         # blocking get — koi manual lock nahi
            try:
                if job is None:      # sentinel => "shutdown" (poison pill)
                    return
                results_q.put(f"job-{job} processed by {threading.current_thread().name}")
            finally:
                jobs.task_done()     # har get ka ek task_done — join() isi par depend karta

    workers = [
        threading.Thread(target=worker, name=f"worker-{i}", daemon=True)
        for i in range(N_WORKERS)
    ]
    for w in workers:
        w.start()

    for job_id in range(1, 7):
        jobs.put(job_id)

    jobs.join()                      # saare enqueued jobs ke task_done ka wait

    # workers ko cleanly band karo: har worker ke liye ek sentinel
    for _ in range(N_WORKERS):
        jobs.put(None)
    for w in workers:
        w.join()

    out = []
    while not results_q.empty():
        out.append(results_q.get())
    print(f"  processed {len(out)} jobs across {N_WORKERS} workers:")
    for line in sorted(out):
        print(f"    {line}")
    print("  Lesson: thread hand-off ka DEFAULT queue.Queue hai — get/put/task_done/"
          "join thread-safe hai, manual Lock/Condition ka jhanjhat khatam.")


# === SECTION 8: TODO — tum khud likho: payment idempotency guard ===
class IdempotentCharger:
    """
    TODO (tum implement karo):
      Payment gateway scenario: do retry threads ek SAATH same idempotency_key pe
      charge karne aayein, to gateway ko sirf EK BAAR hit hona chahiye; doosre ko
      cached result milna chahiye (double-charge se bacho).

      State diya gaya hai:
        self._lock   : threading.Lock  (critical section guard karne ke liye)
        self._done   : dict[str, str]  (idempotency_key -> result, dedupe cache)
        self.gateway_hits : int        (kitni baar "real" gateway call hua — verify ke liye)

      charge(self, key, amount) ko aise likho:
        1. `with self._lock:` ke andar pehle self._done me dekho —
           agar key already hai, to cached result return karo (gateway hit MAT karo).
        2. Agar nahi hai: gateway hit simulate karo (self.gateway_hits += 1),
           result string banao (e.g. f"charged {amount} for {key}"),
           self._done[key] me store karo, aur wahi return karo.
        NOTE: pura check-then-act EK hi lock ke andar hona chahiye, warna do threads
              dono "key not found" dekh lenge aur DONO charge kar denge (race).

      Expected behaviour (section8 isse test karega):
        - 5 threads same key 'ord-1' pe concurrently charge karein
        - self.gateway_hits == 1   (sirf ek real charge hua)
        - sabhi threads ko same result string mile
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._done: dict[str, str] = {}
        self.gateway_hits = 0

    def charge(self, key: str, amount: int) -> str:
        raise NotImplementedError(
            "TODO: with self._lock ke andar check-then-act karo "
            "(cache hit => return cached; warna gateway_hits += 1, store, return)"
        )


def section8() -> None:
    print("\n=== SECTION 8: TODO — payment idempotency guard (tum likho) ===")
    charger = IdempotentCharger()
    outputs: list[str] = []
    out_lock = threading.Lock()

    def attempt() -> None:
        try:
            res = charger.charge("ord-1", 1000)
        except NotImplementedError as e:
            res = f"<unimplemented: {e}>"
        with out_lock:
            outputs.append(res)

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if any(o.startswith("<unimplemented") for o in outputs):
        print("  abhi tak unimplemented (TODO complete karo).")
        return

    unique_results = set(outputs)
    print(f"  gateway_hits = {charger.gateway_hits}  (expected 1)")
    print(f"  distinct results = {len(unique_results)}  (expected 1)")
    if charger.gateway_hits == 1 and len(unique_results) == 1:
        print("  correct! idempotency guard ne double-charge roka (single gateway hit).")
    else:
        print("  output galat — check-then-act ek hi Lock ke andar hai? (race ho raha)")


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
        "8": section8,
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
