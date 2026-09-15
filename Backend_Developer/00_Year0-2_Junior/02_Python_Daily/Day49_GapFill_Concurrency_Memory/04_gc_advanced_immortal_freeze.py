"""
DAY 55 — GC Advanced: Immortal Objects (PEP 683), gc.freeze(), Leak Hunting
Architecture Level: Senior Python Backend

WHY THIS MATTERS:
- Tum gunicorn me `preload_app = True` likhte ho aur sochte ho "memory share
  ho gayi, RAM bach gayi" — par bina is file ke concepts ke wo sharing
  CHUPKE SE TOOT jaati hai. Reason: CPython ka refcounting har object ke
  header me WRITE karta hai, aur ek write pura 4KB memory page COPY karwa
  deta hai (Copy-on-Write break).
- Instagram/Meta ne yahi problem production me face ki — unke Django workers
  fork ke baad dheere-dheere saari "shared" memory ko private bana rahe the.
  Unka fix (gc.freeze + baad me PEP 683 immortal objects) ab CPython ka
  part hai. Interview me yeh story sunana = instant senior signal.
- Aur jab production me memory leak aata hai, "RAM badh rahi hai" se aage
  jaane ke liye tumhe gc.get_referrers/tracemalloc ka leak-hunting workflow
  aana chahiye — "KAUN object ko zinda rakh raha hai?" ka jawab.

DEKHO BIG PICTURE:
    Problem 1: fork + CoW memory sharing tut-ti hai
        Kyun?  → refcount writes + GC ke gc_refs writes pages ko dirty karte
        Fix 1  → PEP 683 immortal objects (3.12): None/True/False/small ints
                 ka refcount KABHI change nahi hota → pages clean rehte
        Fix 2  → gc.freeze(): warm-up ke baad sab objects "permanent
                 generation" me daal do → GC unhe scan hi nahi karta

    Problem 2: memory leak — RAM badh rahi, kaun pakde hue hai?
        Step 1 → tracemalloc: KAHAN allocate ho raha hai (file:line)
        Step 2 → gc.get_referrers: KAUN reference pakde hue hai
        Step 3 → gc.set_debug / gc.garbage: uncollectable cycles dekho

NOTE: PEP 683 (immortal objects) Python 3.12+ ka feature hai. File har
version pe chalegi — demos sys.version_info check karke output explain
karte hain. Fork demo sirf Unix (macOS/Linux) pe chalega, guarded hai.
"""

import gc
import os
import sys
import tracemalloc


# ============ SECTION 1: Immortal Objects (PEP 683, Python 3.12+) ============
#
# KYA HAI: Kuch objects ka refcount ek SPECIAL sentinel value pe FREEZE kar
# diya gaya — Py_INCREF/Py_DECREF unpe NO-OP hai (refcount kabhi change nahi
# hota). Ye objects kabhi free nahi honge → "immortal".
#
# KAUN immortal hai (3.12+, implementation detail — set version ke saath
# thoda evolve hota hai):
#   - None, True, False, Ellipsis, NotImplemented
#   - Small ints (-5 se 256) — jo waise bhi cached the
#   - Empty tuple (), empty str/bytes
#   - Compile-time interned strings (identifiers jaise "name", "self")
#     (3.13+ me runtime sys.intern() wale strings mortal-interned ho sakte)
#
# KAISE: refcount field me ek huge sentinel (~2^32 - 1 on 64-bit) rakha
# jaata hai. Py_DECREF check karta hai "immortal hai? → kuch mat karo".
# Isliye sys.getrefcount(None) ek FIXED giant number return karta hai.

def demo_immortal_objects():
    print("=" * 60)
    print("SECTION 1: Immortal objects — refcount jo kabhi nahi badalta")
    print("=" * 60)

    IMMORTAL_AVAILABLE = sys.version_info >= (3, 12)
    print(f"Python {sys.version.split()[0]} | PEP 683 active: {IMMORTAL_AVAILABLE}")

    # --- sys.getrefcount(None): 3.12+ me huge FIXED sentinel ---
    rc_none = sys.getrefcount(None)
    print(f"\nsys.getrefcount(None) = {rc_none:,}")
    if rc_none > 1_000_000_000:
        print("  → HUGE sentinel (~2^32-1) = IMMORTAL. Ye real count NAHI hai,")
        print("    ye 'refcount frozen' ka marker hai.")
    else:
        print("  → Real count (pre-3.12): har module/function jo None touch")
        print("    karta hai, count badhata hai — isliye hazaaron me hota tha.")

    # --- PROOF: 1 lakh references banao, refcount phir bhi same ---
    before = sys.getrefcount(None)
    hoard = [None] * 100_000          # 1 lakh naye references to None!
    after = sys.getrefcount(None)
    print(f"\n100,000 refs banane ke BAAD bhi:")
    print(f"  before={before:,}  after={after:,}  delta={after - before}")
    if IMMORTAL_AVAILABLE:
        print("  → delta 0: Py_INCREF on immortal = NO-OP (PEP 683)")
    else:
        print("  → delta ~100,000: har reference refcount badhata hai (pre-3.12)")
    del hoard

    # --- Small ints aur normal objects ka comparison ---
    small_int = 100                    # -5..256 → cached + immortal (3.12+)
    big_int = 10**10                   # cache ke bahar → normal mortal object
    my_list = [1, 2, 3]                # user object → hamesha mortal

    print(f"\nsys.getrefcount(100)     = {sys.getrefcount(small_int):,}"
          f"  (small int → immortal on 3.12+)")
    print(f"sys.getrefcount(10**10)  = {sys.getrefcount(big_int)}"
          f"  (bada int → mortal, chhota real count)")
    print(f"sys.getrefcount(my_list) = {sys.getrefcount(my_list)}"
          f"  (apna object → mortal)")

    # Mortal object pe refcount actually MOVE karta hai:
    rc1 = sys.getrefcount(my_list)
    alias = my_list                    # ek aur reference
    rc2 = sys.getrefcount(my_list)
    print(f"my_list: alias banane par refcount {rc1} → {rc2} (mortal = badla)")
    del alias

    # --- (3.14+) sys._is_immortal direct check — version-gated ---
    if hasattr(sys, "_is_immortal"):           # Python 3.14+ only
        print(f"\nsys._is_immortal(None)   = {sys._is_immortal(None)}")
        print(f"sys._is_immortal([1,2])  = {sys._is_immortal([1, 2])}")
    else:
        print("\n(sys._is_immortal 3.14+ me aaya — yahan heuristic: "
              "refcount > 10^9 ≈ immortal)")


# ============ SECTION 2: KYUN immortal? — CoW + Instagram/Meta story ============
#
# fork() ke baad OS parent ki memory COPY nahi karta — dono process SAME
# physical pages share karte hain, "Copy-on-Write" (CoW) mode me. Page tab
# tak shared rehta hai jab tak koi process usme WRITE na kare. Write hote
# hi OS us 4KB page ki PRIVATE COPY bana deta hai.
#
# CPython ka problem: object ko sirf READ karna bhi WRITE hai!
#   x = None; if x is None: ...   ← Py_INCREF(None) chala → None ke
#   ob_refcnt field me write → None wala page DIRTY → copy ban gayi.
#
# INSTAGRAM/META STORY (real production, ~2017-2019 engineering blogs):
#   - Django + uWSGI, preload/fork model: master process me app load karo,
#     phir N workers fork karo → code objects, modules, configs sab CoW-shared.
#   - Observation: workers start me kam RAM lete the, phir REQUEST AANE PAR
#     "shared" memory dhadadhad private hoti gayi — bina naye allocations ke!
#   - Root cause: refcount writes + GC traversal writes har touched object
#     ka page dirty kar rahe the. Sirf code chalane se hi sharing toot rahi thi.
#   - Unka pehla hack: gc.disable() + (apna patched) freeze. Phir unhone
#     CPython me gc.freeze() (3.7) contribute kiya, aur aage chal ke
#     PEP 683 immortal objects (3.12) aaya — ab None/True/small ints ke
#     pages KABHI dirty nahi hote, fork-sharing zinda rehti hai.
#
# MATH KA FEEL: 4KB page me ~50-100 chhote objects baithte hain. EK object
# ka refcount badla → poore page ki copy → uske 99 padosi bhi private ho
# gaye. Isliye thoda sa traffic bhi sharing ko jaldi khatam kar deta tha.

def demo_cow_story():
    print("\n" + "=" * 60)
    print("SECTION 2: CoW + fork — refcount writes sharing kyun todte")
    print("=" * 60)

    diagram = """
    fork() ke turant baad (ideal CoW):
        Master:  [page A][page B][page C]   ← physical memory
        Worker1: [  same  shared  pages  ]  ← 0 extra RAM
        Worker2: [  same  shared  pages  ]  ← 0 extra RAM

    Request process karte hi (pre-3.12, bina freeze):
        Worker1: `if x is None` → Py_INCREF(None) → None ke page pe WRITE
                 → OS: "write detected!" → page ki PRIVATE COPY
        Worker1: [copy A][page B][copy C]   ← RAM badhna shuru
        4KB page = ~50-100 objects → 1 refcount write = 100 objects private!

    3.12+ (immortal) ya gc.freeze() ke saath:
        None/True/small ints ka refcount kabhi nahi likha jaata,
        frozen objects ko GC touch nahi karta → pages CLEAN → shared rehte.
    """
    print(diagram)

    # --- Mini fork demo (sirf Unix; Windows pe fork nahi hota) ---
    if hasattr(os, "fork"):
        rc_parent = sys.getrefcount(None)
        pid = os.fork()
        if pid == 0:
            # CHILD: parent ki memory CoW-shared mili
            rc_child = sys.getrefcount(None)
            # Immortal hai toh dono me SAME sentinel — koi page dirty nahi hua
            # flush=True ZAROORI: os._exit() buffers flush NAHI karta —
            # bina flush ke child ka print gayab ho jaata hai (classic trap)
            print(f"  [child ] getrefcount(None) = {rc_child:,}", flush=True)
            os._exit(0)               # child me sys.exit nahi — _exit (no cleanup)
        else:
            os.waitpid(pid, 0)
            print(f"  [parent] getrefcount(None) = {rc_parent:,}")
            print("  → 3.12+: dono me same frozen sentinel; None ka page kabhi")
            print("    dirty nahi hota, fork ke baad bhi shared rehta hai.")
    else:
        print("  (os.fork is OS pe nahi — Windows; concept same rehta hai)")


# ============ SECTION 3: gc.freeze() — gunicorn preload pattern ============
#
# Immortality sirf CHEND built-in singletons ko milti hai. Tumhare apne
# warm-up objects (Django apps registry, compiled regexes, config dicts)
# ka kya? Unke liye: gc.freeze() (Python 3.7+, Instagram contribution).
#
# gc.freeze() → abhi-zinda SAARE tracked objects ko "permanent generation"
# me move kar deta hai. Permanent generation ko GC KABHI scan nahi karta →
# unke gc headers pe write nahi hota → CoW pages clean.
#
# THE PATTERN (gunicorn-style preload server):
#   1. gc.disable()      # warm-up ke dauran GC chalne mat do (warna wo
#                        #   gc_refs likhega + objects shuffle karega)
#   2. app load / warm-up  (saare modules import, caches build)
#   3. gc.collect()      # ek baar saaf karo — warm-up ka garbage nikal do
#   4. gc.freeze()       # jo bacha wo permanent — GC ke liye invisible
#   5. fork workers      # gunicorn: preload_app=True, post_fork hook me:
#   6. (workers me) gc.enable()  # naya per-request garbage to collect hona hi hai
#
# GUNICORN CONNECTION: `preload_app = True` master me app load karta hai,
# phir fork. gunicorn config me:
#     def post_fork(server, worker): gc.enable()
#     # aur master me app load ke baad: gc.disable(); gc.collect(); gc.freeze()
# (Instagram ne exactly yahi pipeline run ki — "fork-before-freeze" nahi,
#  "FREEZE-BEFORE-FORK" — freeze hamesha fork se PEHLE master me hota hai.)

def demo_gc_freeze():
    print("\n" + "=" * 60)
    print("SECTION 3: gc.freeze() — permanent generation, preload pattern")
    print("=" * 60)

    # Warm-up simulate karo: kuch "app startup" objects banao
    gc.disable()                       # STEP 1: warm-up me GC band
    app_cache = {f"route_{i}": [i, i * 2] for i in range(1000)}  # warm-up data
    gc.collect()                       # STEP 2: warm-up garbage flush

    print(f"freeze se pehle: gc.get_freeze_count() = {gc.get_freeze_count()}")
    gc.freeze()                        # STEP 3: sab kuch permanent generation me
    print(f"freeze ke baad : gc.get_freeze_count() = {gc.get_freeze_count():,}")
    print("  → ye saare objects ab GC scan se BAHAR hain (gc headers pe")
    print("    koi write nahi → CoW pages clean → fork sharing preserved)")

    # STEP 4 (real server): yahin pe fork hota — workers clean pages share karte
    print("\n(real server me YAHAN fork hota: gunicorn preload_app=True)")

    # Worker side: naye objects normal GC me aate hain, frozen wale nahi
    gc.enable()                        # workers me GC wapas on
    new_garbage = [[] for _ in range(10)]   # naya allocation → young gen me
    del new_garbage

    gc.unfreeze()                      # demo cleanup: permanent gen wapas oldest gen me
    print(f"unfreeze ke baad: gc.get_freeze_count() = {gc.get_freeze_count()}")
    del app_cache

    print("\nTHE RECIPE (yaad karo, interview me bolo):")
    print("  gc.disable() → warm up → gc.collect() → gc.freeze() → FORK")
    print("  → workers me gc.enable()  | gunicorn: preload_app + post_fork hook")


# ============ SECTION 4: GC debugging toolkit — set_debug, thresholds, callbacks ============
#
# gc.collect() ka RETURN VALUE = kitne unreachable objects mile (collected +
# uncollectable). Leak investigation me pehla cheap signal.
#
# gc.set_debug(flags):
#   gc.DEBUG_STATS         → har collection pe stats stderr pe print
#   gc.DEBUG_COLLECTABLE   → har collectable object print
#   gc.DEBUG_UNCOLLECTABLE → uncollectable (gc.garbage me jaane wale) print
#   gc.DEBUG_SAVEALL       → collectable objects ko FREE mat karo,
#                            gc.garbage list me daal do → post-mortem!
#   gc.DEBUG_LEAK = DEBUG_COLLECTABLE | DEBUG_UNCOLLECTABLE | DEBUG_SAVEALL
#
# Thresholds: gc.get_threshold() → e.g. (700, 10, 10)
#   gen0: (allocations - deallocations) > 700 → young collection
#   gen1/gen2: kitni baar chhoti generation chali, uska counter
#   (3.13+/3.14 me GC internals incremental hue — values alag dikh sakti,
#    isliye hard-code mat karo, READ karke tune karo.)
#   Tuning: batch jobs jo crores objects banate hain → threshold badhao ya
#   loop ke dauran gc.disable() → end pe ek manual gc.collect().

class Node:
    """Cycle banane ke liye — self-referencing linked node."""
    def __init__(self, name):
        self.name = name
        self.ref = None
    def __repr__(self):
        return f"Node({self.name})"


def demo_gc_debugging():
    print("\n" + "=" * 60)
    print("SECTION 4: gc debugging — collect(), DEBUG flags, thresholds")
    print("=" * 60)

    # --- gc.collect() return value: cycle banao, gino ---
    a, b = Node("a"), Node("b")
    a.ref, b.ref = b, a                # reference CYCLE: a→b→a
    del a, b                           # naam gaye, par cycle zinda (refcount>0)
    found = gc.collect()
    print(f"gc.collect() return = {found}  "
          f"(unreachable objects mile — humara a↔b cycle + internals)")

    # --- DEBUG_SAVEALL: garbage free hone ke bajaye gc.garbage me aata hai ---
    gc.set_debug(gc.DEBUG_SAVEALL)     # ab collectable objects SAVE honge
    c, d = Node("c"), Node("d")
    c.ref, d.ref = d, c
    del c, d
    gc.collect()
    cycle_nodes = [o for o in gc.garbage if isinstance(o, Node)]
    print(f"DEBUG_SAVEALL ke baad gc.garbage me Nodes: {cycle_nodes}")
    print("  → production post-mortem: 'kaunse objects cycle me mar rahe the?'")
    gc.set_debug(0)                    # debug OFF — warna sab kuch save hota rahega
    gc.garbage.clear()                 # MANUAL clear zaroori — warna khud leak!
    gc.collect()

    # gc.DEBUG_STATS note: enable karo toh har collection pe stderr me
    # "gc: collecting generation 1... objects in each generation..." aata hai.
    # Noisy hai isliye yahan run nahi kiya — staging me 5 min ke liye on karo.
    print("(gc.DEBUG_STATS → har collection ki stats stderr pe; staging me use karo)")

    # --- Thresholds: read + tune ---
    print(f"\ngc.get_threshold() = {gc.get_threshold()}")
    print(f"gc.get_count()     = {gc.get_count()}  (har gen me abhi kitne pending)")
    old = gc.get_threshold()
    gc.set_threshold(50_000, old[1], old[2])   # batch-job tuning: gen0 rare chale
    print(f"set_threshold(50000,...) ke baad: {gc.get_threshold()}")
    gc.set_threshold(*old)             # demo cleanup — default wapas
    print("  Tuning rule: object-heavy batch loop → threshold↑ ya gc.disable()")
    print("  + end me manual gc.collect(). Web request path me usually default theek.")

    # --- gc.callbacks: har collection ka hook (timing/monitoring) ---
    events = []
    def on_gc(phase, info):
        # phase: "start"/"stop"; info: {generation, collected, uncollectable}
        events.append((phase, dict(info)))
    gc.callbacks.append(on_gc)
    gc.collect()
    gc.callbacks.remove(on_gc)         # hamesha REMOVE karo — warna global leak
    print(f"\ngc.callbacks demo: {events[-1][0]} → {events[-1][1]}")
    print("  → production me: GC pause time metric (statsd/prometheus) yahi se nikalti")


# ============ SECTION 5: Leak hunting — get_referrers + tracemalloc workflow ============
#
# PRODUCTION STORY SHAPE (yahi workflow interview me sunao):
#   Symptom : worker RSS har ghante 50MB badh rahi, restart pe theek.
#   Step 1  : tracemalloc.start() deploy karo → 2 snapshots lo →
#             compare_to('lineno') → "KAHAN se allocations aa rahe" (file:line)
#   Step 2  : culprit type mila (e.g. dict) → gc.get_objects() se instances
#             gino → count monotonically badh raha = confirmed leak
#   Step 3  : ek leaked instance pakdo → gc.get_referrers(obj) →
#             "KAUN ise zinda rakhe hue hai?" → wahi tumhara bug hai
#             (typically: module-level cache/list/dict jisme append hota
#              hai par eviction kabhi nahi)
#   Tool    : objgraph (pip install objgraph) — yahi kaam graphviz PNG ke
#             saath karta hai: objgraph.show_backrefs(obj) → visual chain.

_GLOBAL_CACHE = []                     # "bhoola hua" module-level cache — classic leak


class LeakedConnection:
    """Pretend DB connection jo kahin stuck reh gaya."""
    def __init__(self, conn_id):
        self.conn_id = conn_id
    def __repr__(self):
        return f"LeakedConnection(id={self.conn_id})"


def handle_request(conn_id):
    conn = LeakedConnection(conn_id)
    _GLOBAL_CACHE.append(conn)         # BUG: cache me daala, kabhi nikala nahi
    return f"handled {conn_id}"


def demo_leak_hunt():
    print("\n" + "=" * 60)
    print("SECTION 5: Leak hunting — tracemalloc + get_referrers combo")
    print("=" * 60)

    # --- STEP 1: tracemalloc — KAHAN allocate ho raha hai ---
    tracemalloc.start()
    snap1 = tracemalloc.take_snapshot()
    for i in range(500):
        handle_request(i)              # leak simulate: 500 "requests"
    snap2 = tracemalloc.take_snapshot()

    top = snap2.compare_to(snap1, "lineno")[:3]
    print("tracemalloc top-3 growth (file:line → kitna naya RAM):")
    for stat in top:
        print(f"  {stat}")
    tracemalloc.stop()
    print("  → file:line mil gaya. Ab pata KAHAN banta hai, par ZINDA kyun hai?")

    # --- STEP 2: gc.get_objects() — kitne instances zinda? ---
    live = [o for o in gc.get_objects() if isinstance(o, LeakedConnection)]
    print(f"\ngc.get_objects() scan: {len(live)} LeakedConnection zinda")
    print("  (isi count ko 2 baar measure karo — badh raha = leak confirmed)")

    # --- STEP 3: gc.get_referrers — KAUN pakde hue hai? ---
    victim = live[0]
    referrers = gc.get_referrers(victim)
    print(f"\ngc.get_referrers({victim}) ne pakda:")
    for r in referrers:
        if r is live:                  # humari apni scan-list ko skip karo
            continue
        desc = type(r).__name__
        if r is _GLOBAL_CACHE:
            desc += "  ← YE RAHA CULPRIT: module-level _GLOBAL_CACHE!"
        print(f"  referrer: {desc} (len={len(r) if hasattr(r, '__len__') else '?'})")
    # NOTE: get_referrers me tumhara current frame/locals bhi aa sakta hai —
    # `r is suspect_container` se identity-check karke confirm karo.

    # --- Bonus: get_referents — ULTA direction (obj kis-kis ko point karta) ---
    outgoing = gc.get_referents(victim)
    print(f"\ngc.get_referents(victim) → {outgoing}")
    print("  (referrers = kaun MUJHE pakde hai; referents = MAIN kise pakde hoon)")
    print("  objgraph library yahi sab + graphviz diagram deta hai: ")
    print("  objgraph.show_backrefs(victim, filename='leak.png')")

    _GLOBAL_CACHE.clear()              # demo cleanup — the actual "fix"
    print("\nFIX shapes: bounded cache (lru_cache/maxsize), WeakValueDictionary,")
    print("  ya explicit eviction. 'Append-only module-level list' = leak magnet.")


# ============ INTERVIEW QUESTIONS ============
"""
Q1: PEP 683 immortal objects kya hain aur kaunse objects immortal hain?
A : 3.12+ me kuch objects ka refcount ek sentinel (~2^32-1) pe permanently
    fix kar diya gaya — INCREF/DECREF unpe no-op. None, True, False,
    Ellipsis, small ints (-5..256), empty tuple/str, compile-time interned
    strings. Ye objects kabhi deallocate nahi hote (waise bhi interpreter ke
    saath hi marte the), isliye "immortal".

Q2: Immortal objects laaye hi kyun gaye? Speed ke liye?
A : Nahi — primary reason Copy-on-Write memory sharing hai. fork() ke baad
    parent/child pages share karte hain jab tak write na ho. CPython me
    object READ karna bhi refcount WRITE karta hai → page dirty → OS private
    copy banata hai → sharing tut-ti hai. Immortal objects ka refcount kabhi
    nahi likha jaata → unke pages clean → fork workers RAM share karte
    rehte. Instagram/Meta ne yeh problem report ki aur fix contribute kiya.

Q3: sys.getrefcount(None) 4,294,967,295 kyun return karta hai 3.12 pe?
A : Wo real count nahi — immortality ka sentinel (UINT32_MAX on 64-bit) hai.
    Pre-3.12 me yahi call hazaaron me real count deta tha aur har naya
    reference use badhata tha. 3.12+ me lakhon references banao, value same
    rehti hai — refcount field pe write hota hi nahi.

Q4: gc.freeze() kya karta hai aur gunicorn preload ke saath kaise use hota?
A : Saare currently-tracked objects ko "permanent generation" me move karta
    hai jise GC kabhi scan nahi karta → GC unke headers pe write nahi karta
    → CoW pages clean. Pattern (freeze-BEFORE-fork): master me gc.disable()
    → app warm-up → gc.collect() → gc.freeze() → fork workers (gunicorn
    preload_app=True) → workers ke post_fork hook me gc.enable(). Instagram
    ne yahi pattern CPython 3.7 me contribute kiya.

Q5: gc.disable() warm-up ke dauran kyun, sirf freeze kaafi nahi?
A : Warm-up ke beech agar GC chal gaya toh wo har tracked object ke gc head
    me gc_refs likhta hai (pages dirty) aur generations shuffle karta hai.
    disable() se warm-up ke dauran ye writes nahi hote; phir ek deliberate
    collect() se garbage saaf, phir freeze() se survivors permanent. Order
    matters: disable → warm → collect → freeze → fork.

Q6: Production me memory leak aaya — tumhara debugging workflow kya hoga?
A : (1) tracemalloc.start() + 2 snapshots + compare_to('lineno') → kaunsi
    file:line se RAM badh rahi. (2) gc.get_objects() me suspect type ke
    instances count karo, time ke saath badh raha = confirmed. (3) Ek
    instance pe gc.get_referrers() → kaun container use pakde hai (typically
    koi module-level cache/list jisme eviction nahi). objgraph se backref
    chain ka PNG bana sakte ho. Fix: bounded cache / weakref / eviction.

Q7: gc.collect() ka return value kya hota hai? gc.garbage kab bharta hai?
A : Return = is collection me mile unreachable objects ki count (collected +
    uncollectable) — cheap leak signal. gc.garbage me uncollectable objects
    aate hain; 3.4+ (PEP 442) ke baad __del__ wale cycles bhi collect ho
    jaate hain isliye normally khaali rehta hai. gc.set_debug(DEBUG_SAVEALL)
    se saare collectable objects free hone ke bajaye gc.garbage me save
    hote hain — post-mortem analysis ke liye (baad me clear karna mat bhoolo).

Q8: gc.get_threshold() kya deta hai aur kab tune karoge?
A : Default jaise (700, 10, 10): gen0 collection tab jab allocations minus
    deallocations 700 cross kare; 10 young runs → gen1 run, 10 gen1 → gen2.
    Tuning: object-heavy batch loops me threshold badhao ya gc.disable() +
    end pe manual collect (GC pauses hatao); long-running server me default
    usually theek. 3.13/3.14 me GC incremental hua hai — values version pe
    depend karti hain, hard-code mat karo.

Q9: gc.get_referrers() use karte waqt kya trap hai?
A : Result me TUMHARA APNA frame/locals/temporary list bhi aa jaata hai
    (tumne reference banaya scan karne ke liye!). Isliiye identity check
    (`r is suspected_cache`) ya type-filter karke hi conclude karo. Aur ye
    sirf GC-tracked containers deta hai — C-level ya atomic containers ke
    references miss ho sakte hain. Production me isko ek debug session me
    use karo, hot path me nahi (poora heap walk karta hai, slow).
"""


if __name__ == '__main__':
    demo_immortal_objects()
    demo_cow_story()
    demo_gc_freeze()
    demo_gc_debugging()
    demo_leak_hunt()
