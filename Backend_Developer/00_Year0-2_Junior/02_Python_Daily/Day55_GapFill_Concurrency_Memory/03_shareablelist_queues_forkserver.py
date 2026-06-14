"""
DAY 55 — ShareableList, SharedMemoryManager, SimpleQueue, Queue.shutdown, forkserver
Architecture Level: Mid → Senior Python Backend

PREREQUISITE: Day54/01_multiprocessing_shared_state.py PEHLE padho — wahan
SharedMemory raw buffer, Value/Array, Manager, aur close()/unlink() lifecycle
cover hai. Ye file uska AGLA STEP hai — wahi cheezein REPEAT nahi karenge.

WHY THIS MATTERS:
- Day54 me dekha: SharedMemory = raw bytes. Par real code me tumhe "list of
  mixed values" share karni hoti hai — uske liye ShareableList hai (raw buffer
  ke upar list-like API, ZERO pickle per access).
- Day54 me dekha: close()/unlink() bhoolna = resource leak warning. Production
  me ye manual lifecycle PAIN hai — SharedMemoryManager context manager se
  crash/exception pe bhi auto-cleanup milta hai.
- queue.Queue sab use karte hain, par queue.SimpleQueue kab aur kyun — ye
  CPython internals ka classic interview question hai (reentrancy!).
- Worker shutdown ka "put None sentinel" hack 20 saal purana tha — Python 3.13
  ne Queue.shutdown() + queue.ShutDown diya. Naye interviews me poocha jaata hai.
- Start methods (fork/spawn/forkserver): Python 3.14 ne Linux ka DEFAULT
  fork → forkserver kar diya. "Tumhara code 3.14 pe kyun toot gaya?" — iska
  jawab is file me hai.

BIG PICTURE MAP:
    SharedMemory (Day54)      → raw bytes buffer (tum layout manage karo)
    ShareableList (aaj)       → buffer ke upar fixed-size list API
    SharedMemoryManager (aaj) → in dono ka LIFECYCLE automate (with-block)
    queue.SimpleQueue (aaj)   → thread queue, minimal + reentrant-safe
    Queue.shutdown 3.13 (aaj) → graceful worker stop, sentinel hack ka the end
    forkserver (aaj)          → fork ki speed + spawn ki thread-safety

NOTE: Saare process targets MODULE-LEVEL hain aur demos __main__ guard me —
spawn/forkserver child me module re-import + target pickle hota hai (Day54 Q6).
Version-gated features (3.13 Queue.shutdown) sys.version_info se guard kiye
hain taaki file 3.9 se 3.14 tak har jagah runnable rahe.
"""

import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.managers import SharedMemoryManager
import queue
import sys
import threading
import time


# ============ SECTION 1: ShareableList — list-like API on shared memory ============
#
# shared_memory.ShareableList = SharedMemory buffer ke UPAR ek list jaisa wrapper.
# Day54 me raw bytes the (buf[i] = 42) — yahan sl[0] = "hello" jaisa kaam karta hai.
#
# RULES (sab fixed-size philosophy se aate hain):
#   - Allowed types SIRF: int (64-bit), float, bool, str, bytes, None
#     (nested list/dict/custom object → ValueError. Wo chahiye toh Manager lo.)
#   - LENGTH FIXED at creation — no append/insert/remove/pop. Sirf indexing,
#     count(), index(). Ye "list" naam ka trap hai — actually fixed slots hain.
#   - Har str/bytes SLOT ka storage creation ke time uski initial value se
#     allocate hota hai → baad me LAMBI string set karoge toh ValueError.
#
# Access = direct shared-memory read/write. NO pickle, NO IPC round-trip.
# Isi liye ye Manager.list() se ordersof-magnitude faster hai (benchmark neeche).

def shareablelist_child(shm_name):
    """Child: naam se attach karo, in-place edit karo — same physical memory."""
    sl = shared_memory.ShareableList(name=shm_name)   # attach by name (no copy)
    sl[0] = sl[0] * 2          # int slot — parent ko turant dikhega
    sl[2] = "child-edit"       # 10 chars — initial slot ("parent-str") me fit
    sl.shm.close()             # apna view band (unlink NAHI — creator karega, Day54 rule)


def demo_shareablelist():
    print("=" * 60)
    print("SECTION 1: ShareableList — list API, shared memory speed")
    print("=" * 60)

    ctx = mp.get_context('spawn')   # explicit context — global default touch nahi karte

    # Mixed types allowed: int, float, bool, str, bytes, None
    sl = shared_memory.ShareableList([100, 3.14, "parent-str", b"raw", True, None])
    try:
        print(f"Created: {list(sl)}  (block name: {sl.shm.name})")

        p = ctx.Process(target=shareablelist_child, args=(sl.shm.name,))
        p.start(); p.join()
        print(f"After child edit: {list(sl)}   <-- sl[0] doubled, sl[2] replaced")

        # TRAP 1: fixed length — append nahi hai
        print(f"len fixed at {len(sl)}; append/insert/pop EXIST hi nahi karte")

        # TRAP 2: str slot ka storage initial value jitna — lambi string => ValueError
        try:
            sl[2] = "ye string bahut hi zyada lambi hai original slot ke liye"
        except ValueError as e:
            print(f"Longer str in slot -> ValueError: {e}")
    finally:
        sl.shm.close()      # view band
        sl.shm.unlink()     # physical block free — Day54 wala resource leak rule

    # --- ShareableList vs Manager.list — performance note (live measure) ---
    # ShareableList read = direct memory. Manager.list read = pickle + socket
    # round-trip to manager server process (Day54 Section 2). Farak DEKHO:
    N_OPS = 3000
    sl2 = shared_memory.ShareableList(list(range(50)))
    try:
        t0 = time.perf_counter()
        for i in range(N_OPS):
            _ = sl2[i % 50]
        t_sl = time.perf_counter() - t0
    finally:
        sl2.shm.close(); sl2.shm.unlink()

    with mp.Manager() as mgr:
        ml = mgr.list(range(50))
        t0 = time.perf_counter()
        for i in range(N_OPS):
            _ = ml[i % 50]
        t_ml = time.perf_counter() - t0

    print(f"\n{N_OPS} reads -> ShareableList: {t_sl*1000:7.1f} ms | "
          f"Manager.list: {t_ml*1000:7.1f} ms  (~{t_ml/max(t_sl, 1e-9):.0f}x slower)")
    print("RULE: fixed-size mixed scalars hot path me -> ShareableList.")
    print("      append/nested objects chahiye -> Manager.list (slow but flexible).")


# ============ SECTION 2: SharedMemoryManager — lifecycle ka with-block ============
#
# Day54 ka PAIN yaad karo: har SharedMemory pe close() HAR process me + unlink()
# EXACTLY EK BAAR creator me. Exception aa gayi beech me? finally bhool gaye?
# → leaked block + resource_tracker warning + /dev/shm me kachra (Linux).
#
# SharedMemoryManager (multiprocessing.managers) ye solve karta hai:
#   - Ek tracking server process start hota hai (Manager family ka member)
#   - smm.SharedMemory(size=N) / smm.ShareableList([...]) usse allocate karo
#   - with-block exit (normal YA exception) → SAB blocks auto close+unlink
# Trade-off: ek extra server process chalta hai. One-off scripts me manual
# theek hai; long-running app jahan blocks dynamically bante hain → SMM lo.

def smm_child(sl_name):
    sl = shared_memory.ShareableList(name=sl_name)
    sl[1] = 999
    sl.shm.close()


def demo_shared_memory_manager():
    print("\n" + "=" * 60)
    print("SECTION 2: SharedMemoryManager — auto cleanup lifecycle")
    print("=" * 60)

    ctx = mp.get_context('spawn')
    leaked_name = None

    with SharedMemoryManager() as smm:          # __enter__ -> server start
        shm = smm.SharedMemory(size=32)         # manager-tracked raw block
        sl = smm.ShareableList([1, 2, 3])       # manager-tracked ShareableList
        leaked_name = sl.shm.name

        shm.buf[0] = 42
        p = ctx.Process(target=smm_child, args=(sl.shm.name,))
        p.start(); p.join()
        print(f"Inside with: shm.buf[0]={shm.buf[0]}, sl={list(sl)}")
        # NOTE: koi close()/unlink() likhna hi nahi pada!
    # __exit__ -> HAR tracked block ka close + unlink ho chuka, server band.

    # PROOF: block sach me delete hua — attach try karo, FileNotFoundError aayega
    try:
        shared_memory.ShareableList(name=leaked_name)
    except FileNotFoundError:
        print(f"After with: block '{leaked_name}' attach -> FileNotFoundError")
        print("            (auto-unlinked — no leak, no resource_tracker warning)")

    print("\nManual (Day54)            vs  SharedMemoryManager (aaj):")
    print("  try/finally + close+unlink     with-block, zero boilerplate")
    print("  exception me leak ka risk      exception pe bhi guaranteed cleanup")
    print("  no extra process               +1 tracking server process")


# ============ SECTION 3: queue.SimpleQueue — minimal & reentrant-safe ============
#
# DHYAN: ye THREAD wala `queue` module hai, multiprocessing.Queue nahi!
# (mp.SimpleQueue alag cheez hai — pipe-based process queue. Naam ka trap.)
#
# queue.Queue (pure Python) = lock + Condition variables + unfinished-task
# counter (task_done()/join() ke liye). Har put/get pe ye sab overhead.
#
# queue.SimpleQueue (3.7+, C me implemented) = sirf put/get/empty/qsize.
#   - NO maxsize (always unbounded), NO task_done/join, NO full()
#   - put() REENTRANT hai — yahi killer feature hai:
#       queue.Queue.put ek lock leta hai. Agar usi moment GC chala aur kisi
#       object ke __del__ / weakref callback ne USI queue pe put kiya
#       (classic: logging QueueHandler) → same thread, lock already held
#       → DEADLOCK. SimpleQueue.put lock-free C code hai → safe.
#   - KAB USE: __del__/GC/signal-handler context se put ho sakta hai (logging
#     handlers!), ya bas fire-and-forget pipeline jahan task_done nahi chahiye.
#   - KAB NahI: backpressure chahiye (maxsize) ya join() se completion track
#     karna hai → queue.Queue hi lo.

class NoisyOnDelete:
    """__del__ me queue pe put karta hai — SimpleQueue ke saath safe."""
    def __init__(self, log_q):
        self._log_q = log_q

    def __del__(self):
        # GC ke beech chal sakta hai — queue.Queue hota toh lock-deadlock ka
        # khatra; SimpleQueue.put reentrant hai, bindaas.
        self._log_q.put("NoisyOnDelete.__del__ logged safely")


def demo_simplequeue():
    print("\n" + "=" * 60)
    print("SECTION 3: queue.SimpleQueue — kab Queue, kab SimpleQueue")
    print("=" * 60)

    sq = queue.SimpleQueue()

    # Reentrancy demo: __del__ ke andar se put
    obj = NoisyOnDelete(sq)
    del obj                       # __del__ fire -> put from finalizer context
    print(f"From __del__: {sq.get()}")

    # Thread pipeline — same API as Queue for put/get
    def producer():
        for i in range(3):
            sq.put(f"item-{i}")

    t = threading.Thread(target=producer)
    t.start(); t.join()
    while not sq.empty():
        print(f"  consumed: {sq.get()}")

    print("\nqueue.Queue                    vs  queue.SimpleQueue")
    print("  maxsize/full() (backpressure)     unbounded only")
    print("  task_done()/join()                nahi hai (no tracking overhead)")
    print("  pure-Python locks                 C impl, put() reentrant")
    print("  general worker pools              logging/finalizer-safe, hot paths")


# ============ SECTION 4: Queue.shutdown() + queue.ShutDown (3.13) ============
#
# 20 saal ka PURANA pattern: workers ko rokne ke liye HAR worker ke liye ek
# None "sentinel" put karo; worker None dekhe toh break. Problems:
#   - N workers = exactly N sentinels (count galat → worker hang ya early exit)
#   - None khud valid data ho toh? Custom sentinel object banao... boilerplate
#   - Producers ko alag se batana padta hai ki ab put mat karo
#
# Python 3.13: q.shutdown(immediate=False) + queue.ShutDown exception.
#   - shutdown() ke baad: put() turant ShutDown raise karta hai (sab producers
#     ek saath band), get() bache hue items deta rehta hai, queue khali hote
#     hi ShutDown raise → worker loop cleanly break.
#   - shutdown(immediate=True): pending items DISCARD, get() turant ShutDown.
#   - asyncio.Queue ko bhi 3.13 me yahi shutdown() mila — same pattern.

def demo_sentinel_pattern_old():
    """PURANA pattern — har Python version pe chalta hai (baseline)."""
    print("\n--- OLD (pre-3.13): sentinel-None pattern ---")
    q, results = queue.Queue(), []
    SENTINEL = None
    N_WORKERS = 2

    def worker(wid):
        while True:
            item = q.get()
            if item is SENTINEL:      # poison pill mila -> exit
                break
            results.append(f"w{wid}:{item}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N_WORKERS)]
    for t in threads: t.start()
    for i in range(4):
        q.put(i)
    for _ in range(N_WORKERS):        # TRAP: workers jitne, sentinels utne — exact!
        q.put(SENTINEL)
    for t in threads: t.join()
    print(f"processed: {sorted(results)}  (had to put {N_WORKERS} sentinels manually)")


def demo_queue_shutdown_313():
    """NAYA pattern — version-gated, 3.13+ pe hi chalega."""
    print("\n--- NEW (3.13+): Queue.shutdown() + queue.ShutDown ---")
    if sys.version_info < (3, 13):
        print(f"(Skipped — Python 3.13+ chahiye, ye {sys.version_info.major}."
              f"{sys.version_info.minor} hai. Pattern neeche comments me.)")
        # 3.13+ code (reference):
        #   def worker():
        #       while True:
        #           try:
        #               item = q.get()          # khali + shutdown -> ShutDown raise
        #           except queue.ShutDown:
        #               break                    # clean exit — NO sentinel counting
        #           process(item)
        #   q.shutdown()                         # ek call, SAB workers drain-then-exit
        return

    q, results = queue.Queue(), []

    def worker(wid):
        while True:
            try:
                item = q.get()
            except queue.ShutDown:    # 3.13 ka naya exception
                break
            results.append(f"w{wid}:{item}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads: t.start()
    for i in range(4):
        q.put(i)

    q.shutdown()                      # EK call — sentinel counting ki zaroorat khatam
    for t in threads: t.join()
    print(f"processed: {sorted(results)}  (drained then ShutDown — graceful)")

    try:
        q.put("late")                 # producer side bhi turant band
    except queue.ShutDown:
        print("put() after shutdown -> queue.ShutDown (producers auto-blocked)")


# ============ SECTION 5: fork vs spawn vs forkserver — DEEP ============
#
# Child process BANTA kaise hai? Teen tarike, aur ye choice correctness decide
# karti hai (sirf speed nahi):
#
#   fork      : os.fork() — parent ka POORA memory copy-on-write me milta hai.
#               Re-import nahi, pickle nahi → SABSE FAST start.
#   spawn     : fresh Python interpreter launch hota hai, module re-import,
#               target+args PICKLE hoke jaate hain → SABSE SLOW par sabse safe.
#   forkserver: START me ek single-threaded "server" process ban jaata hai;
#               har naya child us SERVER se fork hota hai (parent se nahi!).
#               → fork ki speed (after warmup) + threads wali safety.
#
# FORK + THREADS = DEADLOCK DANGER (interview favourite):
#   fork() sirf CALLING thread ko child me copy karta hai — baaki threads
#   GAYAB. Par unke HOLD kiye hue locks "locked" state me COPY ho jaate hain!
#   Child me wo lock kabhi release nahi hoga (holder thread hai hi nahi)
#   → child us lock pe acquire karte hi HANG. Classic victims: logging ka
#   internal lock, malloc arena locks, requests/grpc ke background threads.
#
#   # DANGER pattern (mat chalao — hang karega kabhi-kabhi, yahi worst hai):
#   #   threading.Thread(target=lambda: logging.info("spam"), ...).start()
#   #   mp.get_context('fork').Process(target=f).start()
#   #   # child me logging ka lock locked-forever mil sakta hai -> deadlock
#
# TIMELINE (versions — interview-relevant!):
#   3.8  : macOS default fork -> spawn (Apple frameworks fork-unsafe nikle)
#   3.12 : multi-threaded process me fork karne pe DeprecationWarning
#   3.14 : Linux (POSIX, non-macOS) DEFAULT fork -> forkserver! Code jo fork ke
#          "inherited globals" pe depend karta tha (lazy programmers ka global
#          config/connection) 3.14 pe TOOT-ta hai — explicitly pass karo args me.

def noop():
    pass


def demo_start_methods():
    print("\n" + "=" * 60)
    print("SECTION 5: fork vs spawn vs forkserver")
    print("=" * 60)

    print(f"Platform: {sys.platform} | Python {sys.version_info.major}."
          f"{sys.version_info.minor}")
    print(f"Available methods : {mp.get_all_start_methods()}")
    print(f"Current default   : {mp.get_start_method()}")
    # set_start_method('forkserver') GLOBAL + sirf EK BAAR allowed (warna
    # RuntimeError). Library code me KABHI nahi — wahan get_context() lo:
    # ctx = mp.get_context('forkserver') -> local choice, global ko nahi chhedta.

    print(f"\nChild start cost (noop child, warmed up, avg of 3):")
    for method in ('fork', 'spawn', 'forkserver'):
        if method not in mp.get_all_start_methods():
            print(f"  {method:10s}: not available on this platform")
            continue
        try:
            ctx = mp.get_context(method)        # global default untouched
            p = ctx.Process(target=noop)        # warmup — forkserver ka server
            p.start(); p.join()                 # pehli baar me hi spin-up hota hai
            t0 = time.perf_counter()
            for _ in range(3):
                p = ctx.Process(target=noop)
                p.start(); p.join()
            avg_ms = (time.perf_counter() - t0) / 3 * 1000
            print(f"  {method:10s}: {avg_ms:7.1f} ms per child")
        except Exception as e:                  # fork macOS pe flaky ho sakta hai
            print(f"  {method:10s}: failed ({type(e).__name__}: {e})")

    table = """
    ┌──────────────────┬──────────────────┬──────────────────┬─────────────────────┐
    │                  │ fork             │ spawn            │ forkserver          │
    ├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
    │ Speed            │ fastest (CoW)    │ slowest (fresh   │ fast after warmup   │
    │                  │                  │ interp+reimport) │ (fork from server)  │
    ├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
    │ Safe w/ threads? │ NO — inherited   │ YES — clean      │ YES — server is     │
    │                  │ locks deadlock   │ slate            │ single-threaded     │
    ├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
    │ Inherited state  │ EVERYTHING       │ nothing — target │ sirf server ka      │
    │                  │ (globals, fds,   │ +args pickled,   │ state (preload via  │
    │                  │ locks — sab)     │ module reimport  │ set_forkserver_     │
    │                  │                  │                  │ preload())          │
    ├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
    │ Platforms        │ Unix only        │ all              │ Unix only           │
    ├──────────────────┼──────────────────┼──────────────────┼─────────────────────┤
    │ Default kahan    │ Linux <=3.13     │ macOS 3.8+,      │ Linux 3.14+  <-- !! │
    │                  │                  │ Windows always   │                     │
    └──────────────────┴──────────────────┴──────────────────┴─────────────────────┘

    THUMB RULE:
      Cross-platform / threads anywhere in app -> spawn (boring = correct)
      Linux, many short-lived workers, threads -> forkserver (3.14 yahi degi)
      fork sirf tab jab 100% sure: single-threaded parent + Unix-only + speed god
    """
    print(table)


# ============ INTERVIEW QUESTIONS ============
"""
Q1: ShareableList aur Manager.list() me kya farak — kab kya?
A : ShareableList shared-memory buffer pe direct read/write hai (no pickle, no
    IPC) par FIXED length + sirf int/float/bool/str/bytes/None. Manager.list
    har operation pe manager-server se pickle+socket round-trip karta hai —
    10-100x slow, PAR append/nested objects sab chalta hai. Hot path + fixed
    scalars -> ShareableList; flexibility chahiye -> Manager.

Q2: ShareableList me sl[2] = "lambi string" ValueError kyun de raha hai?
A : Har str/bytes slot ka storage CREATION ke time initial value ke size se
    fix hota hai. Naya value usi allocated space me fit hona chahiye. Fixed
    layout hi reason hai ki access zero-copy/fast hai. Bade-variable strings
    chahiye toh slot ko pehle se pad karo ya Manager use karo.

Q3: SharedMemoryManager kya problem solve karta hai jo plain SharedMemory me hai?
A : Manual lifecycle: har process me close() + creator me exactly-once unlink(),
    aur exception path me leak (resource_tracker warning, /dev/shm me orphan
    blocks). SMM ek tracking server process chalata hai; with-block exit pe
    (exception ho ya na ho) saare allocated blocks auto close+unlink ho jaate hain.

Q4: queue.SimpleQueue kab prefer karoge queue.Queue pe?
A : Jab put() finalizer/GC/signal context se ho sakta hai — e.g. logging
    QueueHandler, __del__ se logging. queue.Queue.put pure-Python lock leta
    hai; agar GC usi thread me __del__ chala de jo phir same queue pe put kare
    -> self-deadlock. SimpleQueue C-implemented hai, put() reentrant. Trade-off:
    no maxsize (no backpressure), no task_done/join.

Q5: queue.SimpleQueue aur multiprocessing.SimpleQueue same hain?
A : NAHI — naam ka trap. queue.SimpleQueue threads ke liye (in-process, C impl,
    reentrant). multiprocessing.SimpleQueue processes ke liye pipe-based queue
    hai jo data PICKLE karta hai. Import dekh ke hi batao kaunsa hai.

Q6: Python 3.13 ke Queue.shutdown() ne sentinel-None pattern kaise replace kiya?
A : Pehle har worker ke liye exactly ek None put karna padta tha (count galat =
    hang/early-exit, aur None valid data ho toh custom sentinel banao). Ab
    q.shutdown() ke baad put() turant queue.ShutDown raise karta hai, get()
    pending items drain karne deta hai aur khali hote hi ShutDown raise — worker
    `except queue.ShutDown: break` se cleanly nikalta hai. immediate=True pending
    items discard karke turant rokta hai. asyncio.Queue me bhi 3.13 me same aaya.

Q7: fork + threads deadlock kaise hota hai? Exact mechanism batao.
A : fork() child me sirf CALLING thread copy karta hai, par poora memory image —
    including DUSRE threads ke held locks — locked state me aata hai. Child me
    holder thread exist hi nahi karta, toh wo lock kabhi release nahi hoga.
    Child jab us lock ko acquire kare (commonly logging ka module lock ya malloc
    internals) -> permanent hang. Isliye 3.12 me multi-threaded fork pe
    DeprecationWarning aayi.

Q8: forkserver fork se safer kaise jab dono fork() hi karte hain?
A : forkserver me ek DEDICATED single-threaded server process pehle ban jaata
    hai; har child PARENT se nahi, us SERVER se fork hota hai. Server me koi
    extra thread/lock hai hi nahi -> locked-lock inherit karne ka scenario
    impossible. Parent chahe 50 threads chalaye, children clean rehte hain.
    Cost: pehli Process pe server spin-up + parent ka state inherit NAHI hota
    (spawn jaisa pickle-args discipline chahiye).

Q9: Python 3.14 pe Linux me multiprocessing code achanak kyun toot sakta hai?
A : 3.14 ne Linux default start method fork -> forkserver kar diya. Jo code
    fork ke "child ko globals/connections free me mil jaate hain" behaviour pe
    depend karta tha (global config, lazily-initialized clients), wo forkserver
    child me missing milega (server se fork hua, parent se nahi). Fix: saara
    needed state target ke args me explicitly pass karo, ya (sochkar)
    mp.set_start_method('fork') / get_context('fork') se old behaviour pin karo.
"""


if __name__ == '__main__':
    # Global set_start_method() yahan NAHI kiya — har demo apna get_context()
    # leta hai (library-safe pattern, Section 5 me explained).
    demo_shareablelist()
    demo_shared_memory_manager()
    demo_simplequeue()
    print("\n" + "=" * 60)
    print("SECTION 4: graceful worker shutdown — old vs new (3.13)")
    print("=" * 60)
    demo_sentinel_pattern_old()
    demo_queue_shutdown_313()
    demo_start_methods()
