"""
DAY 55 — Subinterpreters: PEP 684 + PEP 734 — ek process me MULTIPLE Pythons
Architecture Level: Mid → Senior Python Backend (2026 interview HOT topic)

WHY THIS MATTERS:
- Python ka classic dard: GIL ki wajah se threads CPU-bound kaam parallel
  nahi kar sakte. Ab tak ka jawab tha multiprocessing — par uska cost bhaari:
  process spawn slow, har process ki alag RAM, data pickle karke bhejo.
- SUBINTERPRETERS beech ka raasta hai: EK process ke andar MULTIPLE
  independent Python interpreters. Threads jaisa lightweight (same process,
  same address space), processes jaisa isolation (alag globals, alag modules,
  alag sys.path — aur 3.12 se ALAG GIL bhi!).

TIMELINE (interview me story sunao, sirf facts nahi):
    1997   → C-API me Py_NewInterpreter() tha hi (mod_wsgi jaise embedders
             use karte the), par SAB interpreters EK HI GIL share karte the
             → isolation mila, parallelism NAHI.
    PEP 554→ original proposal: subinterpreters ko Python code se accessible
             banao (stdlib module). Saalon discuss hua, evolve hota gaya.
    3.12   → PEP 684: PER-INTERPRETER GIL! Har interpreter ka apna GIL
             → ek process me TRUE multi-core parallelism. Par sirf C-API
             (Py_NewInterpreterFromConfig) + private _xxsubinterpreters module.
    3.13   → private module ka naam _interpreters hua, free-threaded build
             (PEP 703, --disable-gil) bhi experimental aaya — do raaste!
    3.14   → PEP 734: `concurrent.interpreters` OFFICIAL stdlib module +
             `concurrent.futures.InterpreterPoolExecutor`. Ab Python code
             se subinterpreters first-class use kar sakte ho.

KYA SOLVE KARTA HAI (one-liner for interview):
    "True CPU parallelism WITHOUT multiprocessing overhead — threads ki
     lightness + processes ka isolation, ek hi process ke andar."

TRADE-OFF ek line me:
    Isolation ka matlab sharing MUSHKIL — sirf 'shareable' objects
    (str/bytes/int/float/bool/None/tuple-of-shareables/memoryview/Queue)
    directly pass hote hain; baaki sab pickle hoke jaata hai.

NOTE: Ye file HAR Python version pe runnable hai. 3.14+ pe full demos chalte
hain; 3.12/3.13 pe try/except ImportError ke through explanatory prints +
private-API sneak peek milta hai. Ye khud me ek lesson hai: naye features ko
version-gate karna production skill hai.
"""

import sys
import textwrap
import time

PY = sys.version_info  # e.g. (3, 12, 6, ...)


# ============ SECTION 1: STORY — ek process, kitne Python? ============
#
# Mental model: CPython "interpreter" = ek poora Python world —
#   apna __main__, apne imported modules, apna sys.modules, apna GC,
#   aur (3.12+) apna GIL. Process to sirf OS-level ka dabba hai;
#   us dabbe me ab kai independent Python worlds reh sakte hain.

def demo_story():
    print("=" * 60)
    print("SECTION 1: Subinterpreters — ek process me multiple Pythons")
    print("=" * 60)
    print(f"Running on Python {PY.major}.{PY.minor}.{PY.micro}")
    print(textwrap.dedent("""
        Teen concurrency dabbe (boxes) compare karo:

          THREAD          → same interpreter, same globals, same GIL
                            (CPU parallel NAHI, sharing FREE)
          SUBINTERPRETER  → same process, ALAG interpreter, ALAG GIL (3.12+)
                            (CPU parallel HAAN, sharing RESTRICTED)
          PROCESS         → alag process, alag sab kuch
                            (CPU parallel HAAN, sharing EXPENSIVE: pickle+IPC)

        Subinterpreter = "process jaisa isolation, thread jaisa weight".
        Interpreter create karna ~ms-level hai (process spawn se sasta,
        thread se mehenga), aur memory me modules ki apni copies hoti hain
        (thread se zyada RAM, process se kam).
    """))


# ============ SECTION 2: concurrent.interpreters API (PEP 734, 3.14+) ============
#
# Core API surface (3.14):
#   from concurrent import interpreters
#   interp = interpreters.create()          → naya isolated interpreter
#   interp.exec("code string")              → target ke __main__ me code chalao
#                                             (calling thread BLOCK hota hai)
#   interp.prepare_main(x=1, name="ash")    → shareable objects ko target ke
#                                             __main__ me bind karo (input dena)
#   interp.call(func, *args)                → function ko us interpreter me
#                                             call karo (pickle hoke jaata hai)
#   interp.call_in_thread(func)             → same, par naye thread me (non-blocking)
#   q = interpreters.create_queue()         → cross-interpreter Queue
#   interp.close()                          → interpreter destroy
#
# GOTCHA #1: exec() ka koi return value NAHI hota (exec statement jaisa).
#            Result wapas chahiye? → Queue use karo, ya call() (jo result deta hai).
# GOTCHA #2: exec() me exception aaye toh caller me ExecutionFailed milta hai,
#            jisme .excinfo snapshot hota hai (original traceback object nahi —
#            wo dusre interpreter ka object hai, cross nahi kar sakta).

def demo_interpreters_api():
    print("\n" + "=" * 60)
    print("SECTION 2: concurrent.interpreters API (PEP 734)")
    print("=" * 60)
    try:
        from concurrent import interpreters
    except ImportError:
        print(f"  [SKIP] Python {PY.major}.{PY.minor} pe `concurrent.interpreters` nahi hai.")
        print("  Ye module 3.14+ me aaya (PEP 734). Upgrade karke ye demo full chalega.")
        print("  Niche private-API sneak peek try kar rahe hain (3.12/3.13)...")
        _sneak_peek_private_api()
        return

    # --- create + exec: alag interpreter, alag globals ---
    interp = interpreters.create()
    print(f"Created: {interp!r}")

    # Target interpreter me code string chalao — uske APNE __main__ me.
    # Yahan ka 'x' wahan exist NAHI karta, wahan ka yahan nahi (isolation proof).
    interp.exec("x = 41 + 1; print(f'  [inside subinterpreter] x = {x}')")

    # --- prepare_main: input dena (sirf shareable objects) ---
    interp.prepare_main(name="Ashish", retries=3)  # str/int shareable hain
    interp.exec("print(f'  [inside] got name={name!r}, retries={retries}')")

    # --- result wapas lena: Queue pattern (exec return nahi karta) ---
    q = interpreters.create_queue()
    interp.prepare_main(q=q)                       # Queue khud shareable hai!
    interp.exec("q.put(sum(range(1_000_000)))")    # result Queue me daalo
    print(f"Result via Queue: {q.get()}")

    # --- error handling: ExecutionFailed + excinfo snapshot ---
    try:
        interp.exec("1 / 0")
    except interpreters.ExecutionFailed as e:
        # Original exception object cross nahi karta — sirf snapshot info milti hai
        print(f"ExecutionFailed pakda: {e.excinfo.type.__name__}: {e.excinfo.msg}")

    interp.close()
    print("Interpreter closed. (close() karna achhi hygiene hai — resources free)")


def _sneak_peek_private_api():
    """3.12/3.13 ke liye low-level taste — PRIVATE API, production me mat use karo.

    3.12 → _xxsubinterpreters (PEP 684 ke saath aaya, per-interpreter GIL)
    3.13 → _interpreters (rename hua, PEP 734 ki taraf evolve)
    Signatures release ke beech badle hain, isliye sab broad try/except me hai.
    """
    mod = None
    for name in ("_interpreters", "_xxsubinterpreters"):  # 3.13 first, then 3.12
        try:
            mod = __import__(name)
            break
        except ImportError:
            continue
    if mod is None:
        print("  Private interpreter module bhi nahi mila — demo skip.")
        return
    try:
        iid = mod.create()
        if isinstance(iid, tuple):       # kuch builds (id, whence) tuple dete hain
            iid = iid[0]
        runner = getattr(mod, "run_string", None) or getattr(mod, "exec", None)
        # Flush zaroori: subinterpreter ka stdout alag buffer hai — bina flush
        # ke piped output me uska print PEHLE dikh sakta hai (ordering trap!)
        sys.stdout.flush()
        runner(iid, "print('  [private API] hello from a separate interpreter!')")
        mod.destroy(iid)
        print(f"  Sneak peek OK via `{mod.__name__}` — 3.14 me yahi cheez")
        print("  `concurrent.interpreters` ke through OFFICIALLY milti hai.")
    except Exception as e:               # private API — kabhi bhi toot sakta hai
        print(f"  Private API demo fail hua ({type(e).__name__}: {e}) — expected risk,")
        print("  isliye to PEP 734 ka stable public API banaya gaya!")


# ============ SECTION 3: Sharing limitations — 'shareable' objects ============
#
# Interpreters ke beech objects FREELY pass NAHI hote — har interpreter ka
# apna heap-view, apna refcounting world hai. PEP 734 ne 'shareable' types
# define kiye jo safely cross kar sakte hain:
#
#   str, bytes, int, float, bool, None,
#   tuple (jisme sirf shareable items ho),
#   memoryview (UNDERLYING BUFFER SHARE hota hai — true shared memory!),
#   interpreters.Queue (channel khud)
#
# Baaki sab (dict, list, custom objects, functions) → pickle hoke jaate hain
# (call()/Executor me), yaani COPY milti hai, live shared object NAHI.
#
# memoryview SPECIAL hai: buffer dono taraf SAME physical memory dikhata hai —
# bade numeric data ke liye zero-copy lane (multiprocessing.shared_memory jaisa
# par bina OS-level setup ke).

def demo_shareable_objects():
    print("\n" + "=" * 60)
    print("SECTION 3: Shareable objects — kya cross karta hai, kya nahi")
    print("=" * 60)
    try:
        from concurrent import interpreters
    except ImportError:
        print("  [SKIP] 3.14+ chahiye. Rule yaad rakho:")
        print("    SHAREABLE : str, bytes, int, float, bool, None,")
        print("                tuple(of shareables), memoryview, Queue")
        print("    BAAKI SAB : pickle hoke COPY jaata hai (dict, list, objects)")
        print("    memoryview→ underlying buffer SAME hota hai (zero-copy!)")
        return

    interp = interpreters.create()

    # --- shareable pass: chalega ---
    interp.prepare_main(host="db.prod", port=5432, opts=("retry", 3))
    interp.exec("print(f'  [inside] {host}:{port} opts={opts}')")

    # --- NON-shareable pass: prepare_main fail karega ---
    try:
        interp.prepare_main(config={"debug": True})   # dict shareable NAHI
    except Exception as e:
        print(f"dict bhejne par: {type(e).__name__} — dict not shareable")
        print("  Fix: pickle/json string banao, ya call() use karo (auto-pickle)")

    # --- memoryview: TRUE shared buffer (zero-copy) ---
    buf = bytearray(8)                    # mutable buffer parent me
    interp.prepare_main(view=memoryview(buf))
    interp.exec("view[0] = 255")          # SUBINTERPRETER ne likha...
    print(f"memoryview demo: parent ka buf[0] = {buf[0]}  (<-- 255! same memory)")

    interp.close()


# ============ SECTION 4: InterpreterPoolExecutor + 3-way comparison ============
#
# 3.14 me concurrent.futures ko teesra bhai mila:
#   ThreadPoolExecutor → InterpreterPoolExecutor → ProcessPoolExecutor
# Same .submit()/.map() interface — sirf executor swap karo, code same rahta hai.
# Har worker thread ke andar ek dedicated subinterpreter hota hai; tasks/args
# pickle hoke jaate hain (ProcessPool jaisa), par process spawn ka kharcha nahi.

def cpu_burn(n):
    """CPU-bound task — pool comparison ke liye.

    MODULE-LEVEL hona zaroori hai: InterpreterPool/ProcessPool dono target ko
    PICKLE karke bhejte hain; lambda/nested function pickle nahi hota.
    """
    total = 0
    for i in range(n):
        total += i * i
    return total


def demo_pools():
    print("\n" + "=" * 60)
    print("SECTION 4: InterpreterPoolExecutor — teesra executor (3.14)")
    print("=" * 60)

    N, TASKS = 2_000_000, 4
    try:
        from concurrent.futures import InterpreterPoolExecutor, ThreadPoolExecutor

        # ThreadPool: GIL ki wajah se CPU-bound tasks SERIALIZE ho jaate hain
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=TASKS) as ex:
            list(ex.map(cpu_burn, [N] * TASKS))
        thread_time = time.perf_counter() - t0

        # InterpreterPool: har worker ka APNA GIL → multi-core parallel
        t0 = time.perf_counter()
        with InterpreterPoolExecutor(max_workers=TASKS) as ex:
            list(ex.map(cpu_burn, [N] * TASKS))
        interp_time = time.perf_counter() - t0

        print(f"CPU-bound x{TASKS} tasks:")
        print(f"  ThreadPool      : {thread_time:.2f}s  (GIL → effectively serial)")
        print(f"  InterpreterPool : {interp_time:.2f}s  (per-interpreter GIL → parallel)")
    except ImportError:
        print(f"  [SKIP] InterpreterPoolExecutor 3.14+ me hai (abhi {PY.major}.{PY.minor}).")
        print("  Code pattern bilkul ThreadPoolExecutor jaisa hai — sirf naam swap.")

    # 3-WAY COMPARISON TABLE — ye table interview me likh ke dikhao!
    print("""
    ┌────────────────┬──────────────────┬─────────────────────┬──────────────────┐
    │                │ ThreadPool       │ InterpreterPool     │ ProcessPool      │
    │                │ Executor         │ Executor (3.14)     │ Executor         │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ GIL            │ EK shared GIL    │ Har worker ka APNA  │ Har process ka   │
    │                │ (CPU serial)     │ GIL (CPU parallel)  │ apna (parallel)  │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ Memory         │ Sabse kam        │ Beech ka (modules   │ Sabse zyada      │
    │                │ (sab shared)     │ ki apni copies)     │ (poora dup)      │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ Startup cost   │ ~negligible      │ ~ms per interp      │ ~10-100ms+ per   │
    │                │                  │ (no process spawn)  │ process (spawn)  │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ Data sharing   │ Free (same heap, │ Shareable types +   │ Sab pickle + IPC │
    │                │ locks chahiye)   │ pickle; memoryview  │ (pipe/queue)     │
    │                │                  │ = zero-copy buffer  │                  │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ Crash blast    │ Poora process    │ Poora process       │ Sirf wo worker   │
    │ radius         │ girta hai        │ girta hai (same     │ marta hai        │
    │                │                  │ process!)           │ (best isolation) │
    ├────────────────┼──────────────────┼─────────────────────┼──────────────────┤
    │ Use case       │ I/O-bound        │ CPU-bound, pure-    │ CPU-bound, C-ext │
    │                │ (network, disk)  │ Python, low-overhead│ heavy, ya crash- │
    │                │                  │ parallelism         │ isolation chahiye│
    └────────────────┴──────────────────┴─────────────────────┴──────────────────┘

    THUMB RULE:
      I/O wait hai?                → ThreadPool (ya asyncio)
      CPU-bound + pure Python?     → InterpreterPool (3.14+) — naya default candidate
      CPU-bound + numpy/C-ext?     → ProcessPool (ext compatibility pakki hai)
      Worker crash afford nahi?    → ProcessPool (alag process = alag blast radius)
    """)


# ============ SECTION 5: Free-threading (no-GIL) vs Subinterpreters ============
#
# 2026 ka HOT interview sawaal: "CPython me GIL ka future kya hai?"
# Jawab: DO parallel tracks chal rahe hain — dono jaano:
#
#   PEP 703 FREE-THREADING: GIL ko HATAO hi. 3.13 me experimental build
#   (--disable-gil se compile, binary `python3.13t`), 3.14 me officially
#   supported (PEP 779) — par ab bhi ALAG build hai, default nahi.
#
#   PEP 684/734 SUBINTERPRETERS: GIL rakho, par har interpreter ko APNA do.
#   Default build me hi kaam karta hai, koi special binary nahi.

def demo_free_threading_vs_subinterpreters():
    print("\n" + "=" * 60)
    print("SECTION 5: Free-threaded (no-GIL) vs Subinterpreters")
    print("=" * 60)

    # Runtime pe detect karo: kya hum free-threaded build pe hain?
    is_gil_enabled = getattr(sys, "_is_gil_enabled", None)   # 3.13+ hi hota hai
    if is_gil_enabled is None:
        print(f"  Is build ({PY.major}.{PY.minor}) me sys._is_gil_enabled() nahi —")
        print("  matlab pre-3.13, GIL pakka ON hai.")
    else:
        print(f"  sys._is_gil_enabled() = {is_gil_enabled()}  "
              f"({'normal GIL build' if is_gil_enabled() else 'FREE-THREADED build!'})")

    print("""
    ┌──────────────────┬────────────────────────────┬────────────────────────────┐
    │                  │ Free-threading (PEP 703)   │ Subinterpreters (684/734)  │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ Idea             │ GIL hatao, threads ko      │ GIL rakho, har interpreter │
    │                  │ truly parallel karo        │ ko apna GIL do             │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ Build            │ ALAG binary (3.13t/3.14t)  │ DEFAULT build me hi        │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ Sharing model    │ Sab kuch shared (threads   │ Isolated by default;       │
    │                  │ jaisa) → races possible,   │ explicit channels (Queue,  │
    │                  │ locks tumhari zimmedari    │ memoryview) → races kam    │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ Single-thread    │ Thoda slow (~5-10% range,  │ Zero — normal build,       │
    │ cost             │ versions ke saath ghat     │ normal speed               │
    │                  │ raha hai)                  │                            │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ C-extension      │ Ext ko thread-safety audit │ Ext ko multi-phase init    │
    │ burden           │ + nogil wheels chahiye     │ (PEP 489/630) support      │
    │                  │                            │ chahiye (numpy lagged)     │
    ├──────────────────┼────────────────────────────┼────────────────────────────┤
    │ Programming feel │ Java/C++ threads jaisa     │ Erlang/actor-model jaisa   │
    │                  │ (shared everything)        │ (message passing)          │
    └──────────────────┴────────────────────────────┴────────────────────────────┘

    INTERVIEW LINE: "Ye competitors kam, complements zyada hain. Free-threading
    shared-memory parallelism deta hai (existing threaded code speedup),
    subinterpreters isolated share-nothing parallelism dete hain (safer
    architecture). Long-term dono CPython me coexist karenge — free-threading
    eventually default ban sakta hai, subinterpreters actor-style design ke
    liye rahenge."
    """)


# ============ SECTION 6: Honest current-state assessment (mid-2026) ============

def production_assessment():
    print("\n" + "=" * 60)
    print("SECTION 6: Production me kab use karein? (honest take)")
    print("=" * 60)
    print(textwrap.dedent("""
        MATURE / SAFE AAJ:
          - threading (I/O), asyncio, multiprocessing, ProcessPoolExecutor
            → battle-tested, har library compatible.

        SUBINTERPRETERS (3.14 stdlib) — promising, par dhyaan se:
          - Pure-Python CPU-bound workloads → kaam karta hai, fast hai.
          - BIG CATCH: C extensions. Jo extension multi-phase init + isolated
            module state support nahi karta, wo subinterpreter me import par
            ImportError dega. numpy/pandas jaise heavyweights ka support
            dheere-dheere aa raha hai — APNI dependency list pehle TEST karo.
          - Ecosystem patterns (pools, frameworks, docs) abhi young hain.

        FREE-THREADED BUILD:
          - 3.14 me 'officially supported' (PEP 779), par alag binary hai;
            har wheel ke nogil variant chahiye. Greenfield experiments ke
            liye theek, conservative prod ke liye abhi early.

        PRACTICAL DECISION (2026):
          1. Prod default       → multiprocessing/ProcessPool (boring = good)
          2. 3.14 + pure Python → InterpreterPoolExecutor try karo; benchmark
                                  karke ProcessPool se compare karo
          3. Naya parallel-heavy design → subinterpreter/actor model ko
                                  architecture me ab se hi consider karo —
                                  yahi direction hai jisme CPython ja raha hai
    """))


# ============ INTERVIEW QUESTIONS ============
"""
Q1: Subinterpreter kya hai aur multiprocessing se kaise alag hai?
A : Ek hi OS process ke andar multiple independent Python interpreters — har
    ek ka apna __main__, sys.modules, GC, aur (3.12+) apna GIL. Multiprocessing
    se alag: process spawn nahi karna padta (startup ~ms vs ~10-100ms), memory
    footprint kam, aur memoryview ke through zero-copy buffer sharing possible.
    Par isolation same process me hai — ek interpreter segfault kare toh poora
    process girta hai (process isolation ye bachata hai).

Q2: PEP 684 aur PEP 734 me kya farak hai?
A : PEP 684 (3.12) = PER-INTERPRETER GIL — engine-level change jisne true
    parallelism enable kiya, par sirf C-API/private module se accessible tha.
    PEP 734 (3.14) = `concurrent.interpreters` stdlib module +
    InterpreterPoolExecutor — Python developers ke liye PUBLIC API.
    Short: 684 ne engine banaya, 734 ne steering wheel diya.

Q3: Interpreters ke beech kaunse objects pass ho sakte hain?
A : Directly sirf 'shareable' types: str, bytes, int, float, bool, None,
    tuple (of shareables), memoryview, aur interpreters.Queue. memoryview
    special hai — underlying buffer dono taraf SAME memory hota hai (zero-copy).
    Dict/list/custom objects directly nahi jaate; call()/Executor unhe pickle
    karke COPY bhejte hain — live shared object kabhi nahi milta.

Q4: exec() se return value kaise laoge? Wo None kyun deta hai?
A : interp.exec() statement-exec jaisa hai — return value hai hi nahi. Result
    wapas lene ke 2 patterns: (1) interpreters.create_queue() banao, Queue ko
    prepare_main se bind karo, subinterpreter q.put(result) kare, parent
    q.get() kare; (2) interp.call(func, args) use karo jo result (pickled)
    return karta hai.

Q5: ThreadPool vs InterpreterPool vs ProcessPool — kab kya?
A : I/O-bound → ThreadPool (GIL I/O wait me release hota hai). CPU-bound +
    pure Python → InterpreterPool (3.14+): per-interpreter GIL se parallel,
    process-spawn cost nahi. CPU-bound + C-extension heavy ya crash isolation
    chahiye → ProcessPool (har extension compatible, worker crash process tak
    limited). Teeno ka .submit()/.map() interface same hai — swap is cheap.

Q6: Free-threading (no-GIL) aur subinterpreters — dono kyun bana rahe hain CPython wale?
A : Do alag parallelism philosophies. Free-threading (PEP 703): GIL hatao,
    shared-memory threads — existing threaded code ko speedup, par races/locks
    tumhari problem aur alag build chahiye. Subinterpreters (684/734):
    share-nothing isolation + message passing (actor model) — safer design,
    default build me kaam karta hai, par sharing restricted. Complementary
    hain: shared-state speedup chahiye → free-threading; isolated workers ka
    clean architecture chahiye → subinterpreters.

Q7: Production me aaj subinterpreters use karoge?
A : Conditional yes. 3.14 + pure-Python CPU-bound workload → haan, benchmark
    ke saath. Numpy/pandas jaise C-extensions pe heavy ho → pehle test karo;
    jo extension multi-phase init (PEP 489) support nahi karta wo subinterpreter
    me ImportError dega. Conservative default abhi bhi ProcessPool hai —
    boring but battle-tested. Direction clear hai, ecosystem catch-up me hai.

Q8: Subinterpreter me uncaught exception ka kya hota hai?
A : Caller ko interpreters.ExecutionFailed milta hai, jisme .excinfo snapshot
    hota hai (type name, message, formatted traceback). ORIGINAL exception
    object cross NAHI karta — wo dusre interpreter ka object hai, aur objects
    interpreters ke beech freely travel nahi kar sakte. Ye design hi isolation
    ka proof hai.
"""


if __name__ == '__main__':
    demo_story()
    demo_interpreters_api()
    demo_shareable_objects()
    demo_pools()
    demo_free_threading_vs_subinterpreters()
    production_assessment()
