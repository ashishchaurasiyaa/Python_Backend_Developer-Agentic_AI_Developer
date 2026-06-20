"""
================================================================================
TOPIC: Memory Management, Garbage Collection (GC) & Weak References
================================================================================

KYA HOTA HAI:
    CPython me memory do mechanism se manage hoti hai. Pehla: REFERENCE COUNTING —
    har object ek refcount rakhta hai; jaise hi refcount 0 hota hai, object TURANT
    free ho jaata hai (deterministic). Dusra: GENERATIONAL CYCLIC GC — ye sirf un
    objects ke liye hai jo aapas me REFERENCE CYCLE bana lete hain (a -> b -> a),
    jinhe refcounting akela kabhi 0 nahi kar paata. weakref ek aisi reference hai
    jo refcount badhati NAHI — yaani object ko zinda nahi rakhti.

KYO NEED PADI:
    Pure refcounting ka ek blind spot hai: cycles. Agar do object ek-dusre ko point
    karein, dono ka count kabhi 0 nahi hoga -> memory leak. Isliye CPython ek alag
    cyclic collector chalata hai jo unreachable cycles ko dhoondh ke reclaim karta
    hai. weakref isliye chahiye taaki tum kisi object ko OBSERVE/CACHE kar sako bina
    use artificially zinda rakhe — warna tumhara "cache" ek memory leak ban jaata.

KAISE USE KARTE HAIN:
    Normal kaam me kuch karne ki zaroorat nahi — refcounting + GC automatic chalte
    hain. Tuning/debug ke liye `gc` module: gc.collect() force karo, gc.get_referrers()
    se dekho kaun zinda rakhe hue hai, gc.disable()/freeze() throughput-critical paths
    pe. Cache jo objects ko zinda na rakhe uske liye weakref.WeakValueDictionary, aur
    single observer ke liye weakref.ref(obj, callback).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: ek sync run me lakhon row-DTOs bante aur free hote rehte
       hain; refcounting se wo turant chhutte hain, par retry/idempotency buffers me
       accidental cycle ya stale ref RSS ko phula deta hai.
    2. Niroskos multi-tenant SaaS: per-tenant in-memory cache (compiled query / ORM
       metadata) ko WeakValueDictionary se rakho — tenant object marte hi entry apne
       aap nikal jaaye, leak na ho.
    3. Celery long-running worker: lambda/closure/callback se bane reference cycles
       slowly RSS badhate hain; gc.collect() aur get_referrers() se diagnose karte ho.
    4. Payment idempotency: short-lived in-flight request objects ko weakref se track
       karo taaki finalizer (weakref callback) cleanup/metrics fire kar de bina object
       ko pin kiye.
    5. Parent<->child graph (Odoo ERP tree nodes / order<->lines) jahan dono taraf
       reference hoti hai -> classic cycle; GC hi isse reclaim karta hai.

INTERVIEW ANSWER (English — recite this):
    "CPython manages memory primarily through reference counting: every object tracks
    how many references point to it, and the instant that count drops to zero the
    object is freed deterministically — including running its __del__. The limitation
    is reference cycles: if two objects refer to each other, their counts never reach
    zero even when nothing outside can reach them, so they'd leak. To handle that,
    CPython adds a generational cyclic garbage collector that periodically finds and
    reclaims unreachable cycles, organising objects into three generations on the
    assumption that most objects die young, so younger generations are scanned far
    more often. The senior nuance is that I avoid relying on __del__ inside cycles
    and prefer weak references for caches and observers: a weakref does not increment
    the refcount, so a WeakValueDictionary cache lets entries disappear the moment the
    real object is collected — the cache never keeps anything alive. One more gotcha I
    always flag: small integers from -5 to 256 and many short strings are interned and
    cached, so 'is' may appear to work for value comparison on them — but that is an
    implementation detail, and you must use '==' for value equality and reserve 'is'
    for identity, typically only against None."

--------------------------------------------------------------------------------
Run:
    python 23_memory_gc_and_weakref.py        # saare sections chalao
    python 23_memory_gc_and_weakref.py 1 5    # sirf section 1 aur 5 chalao

Sections:
    1. DEMO     — refcount + immediate free (sys.getrefcount + __del__ deterministic)
    2. DEMO     — reference cycle leak karta hai; gc.collect() use reclaim karta hai
    3. DEMO     — gc.get_referrers(): "kaun zinda rakhe hue hai" diagnose karna
    4. REAL     — Niroskos: WeakValueDictionary cache jo object ko zinda NAHI rakhta
    5. REAL     — payment in-flight tracker: weakref.ref + finalizer callback cleanup
    6. BREAK-IT — small-int/string interning: 'is' chal gaya par '==' hi sahi hai
    7. BREAK-IT — weakref.ref ko inline rakhna object ko galti se pin kar deta hai
    8. TODO     — tum khud likho: weak-cache wala get_or_build()
================================================================================
"""
from __future__ import annotations

import gc
import sys
import weakref


# === SECTION 1: DEMO — reference counting + immediate (deterministic) free =====
def section_1() -> None:
    print("=" * 70)
    print("SECTION 1: refcount + IMMEDIATE free (refcounting deterministic hai)")
    print("=" * 70)

    class Conn:
        # __del__ tab chalta hai jab refcount 0 ho jaata hai (cycle na ho to TURANT).
        def __init__(self, name: str) -> None:
            self.name = name

        def __del__(self) -> None:
            print(f"    [__del__] {self.name} freed (refcount 0 ho gaya)")

    c = Conn("hana-conn")
    # sys.getrefcount() khud ek temporary ref banata hai (argument pass hone se),
    # isliye reported count me +1 hamesha hota hai — yeh classic gotcha hai.
    print(f"  refcount after 1 binding   = {sys.getrefcount(c)}  (note: getrefcount +1 dikhata)")

    alias = c  # ek aur reference -> count badh gaya
    print(f"  refcount after alias = c   = {sys.getrefcount(c)}")

    del alias  # ek ref hata di -> count ghata, par object zinda (c abhi point karta)
    print(f"  refcount after del alias   = {sys.getrefcount(c)}  (abhi zinda hai)")

    print("  ab 'del c' karte hain -> aakhri ref gayi -> __del__ TURANT chalega:")
    del c  # aakhri reference gayi -> refcount 0 -> object yahin, isi line pe free
    print("  ^ dekho __del__ GC ka wait nahi karta — refcounting deterministic hai.")


# === SECTION 2: DEMO — reference cycle leak; gc.collect() reclaim karta hai =====
_FREED_LOG: list[str] = []  # kaun-kaun __del__ chala, track karne ke liye


class Node:
    """Ek node jo intentionally cycle banayega (parent <-> child)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.partner: Node | None = None

    def __del__(self) -> None:
        _FREED_LOG.append(self.name)


def section_2() -> None:
    print("=" * 70)
    print("SECTION 2: reference CYCLE -> refcounting akela free nahi kar paata")
    print("=" * 70)

    _FREED_LOG.clear()
    gc.collect()  # saaf slate

    # Cycle banao: a -> b -> a. Dono ka refcount kabhi 0 nahi hoga sirf del se.
    a = Node("A")
    b = Node("B")
    a.partner = b
    b.partner = a

    # GC ko temporarily off karke dikhayenge ki sirf 'del' se ye free NAHI hote.
    gc.disable()
    del a
    del b
    print(f"  del a, del b ke baad bhi freed? {_FREED_LOG or 'KOI nahi (cycle leak!)'}")
    print("  refcounting fail: a aur b ek-dusre ko hold kiye hue hain (count != 0).")

    # Ab cyclic garbage collector ko bolo — ye unreachable cycle dhoondh ke reclaim karega.
    collected = gc.collect()
    gc.enable()
    print(f"  gc.collect() ne objects reclaim kiye: {collected}")
    print(f"  ab freed log = {sorted(_FREED_LOG)}  <-- GC ne cycle tod ke free kiya")
    print("  Lesson: cycles ke liye generational cyclic GC chahiye; refcounting kaafi nahi.")


# === SECTION 3: DEMO — gc.get_referrers(): kaun object ko zinda rakhe hue hai ===
def section_3() -> None:
    print("=" * 70)
    print("SECTION 3: gc.get_referrers() — 'leak kaun kar raha hai' diagnose karo")
    print("=" * 70)

    # Real worker me RSS slowly badhe to: kis container ne object pakda hua hai?
    target = {"row": "MAT-0001"}  # maan lo ye ek DTO hai jo free nahi ho raha

    cache_list = [target]            # ek list hold kar rahi hai
    cache_map = {"k": target}        # ek dict bhi hold kar raha hai

    referrers = gc.get_referrers(target)
    # apne local frame/temp refs filter kar do; sirf hamare 2 containers dikhane hain.
    interesting = [r for r in referrers if r is cache_list or r is cache_map]
    print(f"  target ko {len(interesting)} known containers hold kar rahe hain:")
    for r in interesting:
        kind = "list" if isinstance(r, list) else "dict"
        print(f"    - ek {kind} -> {r}")

    # Ek container se ref hatao -> ab sirf doosra hold karta hai.
    cache_list.clear()
    still = [r for r in gc.get_referrers(target) if r is cache_map]
    print(f"  cache_list.clear() ke baad ab sirf dict hold karta hai: {bool(still)}")
    print("  Lesson: prod leak hunt me get_referrers() batata hai object ka 'maalik' kaun.")


# === SECTION 4: REAL — Niroskos cache jo object ko zinda NAHI rakhta ===========
class TenantConfig:
    """Per-tenant compiled config (mehnga banta hai -> cache karna chahte ho)."""

    __slots__ = ("tenant_id", "__weakref__")  # weakref ke liye __weakref__ slot zaroori

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def __repr__(self) -> str:
        return f"TenantConfig({self.tenant_id!r})"


def section_4() -> None:
    print("=" * 70)
    print("SECTION 4: REAL — WeakValueDictionary cache (object ko pin NAHI karta)")
    print("=" * 70)

    # WeakValueDictionary: values weakly held. Jaise hi asli object kahin aur se
    # reachable nahi raha, entry apne aap gayab -> cache LEAK nahi karta.
    cache: weakref.WeakValueDictionary[str, TenantConfig] = weakref.WeakValueDictionary()

    cfg = TenantConfig("acme")     # strong ref: cfg
    cache["acme"] = cfg            # cache me weakly daala
    print(f"  cache me daala. cache.get('acme') = {cache.get('acme')}")
    print(f"  live entries = {len(cache)} (kyunki 'cfg' strong ref zinda rakhe hai)")

    # Ab strong ref hata do -> object collectible -> cache se entry GAYAB
    del cfg
    gc.collect()  # CPython refcounting yahan turant marta, collect() bas pakka karne ko
    print(f"  del cfg ke baad cache.get('acme') = {cache.get('acme')}  <-- None!")
    print(f"  live entries = {len(cache)} (entry apne aap nikal gayi)")
    print("  Lesson: agar normal dict use karte to 'acme' hamesha zinda rehta = LEAK.")
    print("  Niroskos: per-tenant cache weakly rakho -> tenant marte hi memory free.")


# === SECTION 5: REAL — payment in-flight tracker: weakref.ref + finalizer ======
def section_5() -> None:
    print("=" * 70)
    print("SECTION 5: REAL — weakref.ref + callback (in-flight payment cleanup)")
    print("=" * 70)

    class PaymentRequest:
        def __init__(self, idem_key: str) -> None:
            self.idem_key = idem_key

    cleanup_log: list[str] = []

    def on_finalize(_dead_ref: weakref.ref) -> None:
        # Ye callback object COLLECT hone ke baad chalta hai — metrics/cleanup ke liye.
        cleanup_log.append("finalizer-fired")

    req = PaymentRequest("idem-9f3a")
    # weakref.ref refcount NAHI badhati -> object ko zinda nahi rakhti.
    wref = weakref.ref(req, on_finalize)

    print(f"  weakref alive? {wref() is req}  -> {wref()!r}")
    print(f"  idem_key via weakref = {wref().idem_key}")

    # Request complete -> strong ref drop -> object collectible -> callback fire
    del req
    gc.collect()
    print(f"  del req ke baad wref() = {wref()}  <-- None (object chala gaya)")
    print(f"  cleanup_log = {cleanup_log}  (finalizer ne cleanup/metrics trigger kiya)")
    print("  Lesson: in-flight requests ko weakref se track karo -> tracker khud kabhi")
    print("  request ko zinda nahi rakhta, aur free hote hi cleanup auto-fire hota hai.")


# === SECTION 6: BREAK-IT — small-int / string interning aur 'is' ka jaal =======
def section_6() -> None:
    print("=" * 70)
    print("SECTION 6: BREAK-IT — interning: 'is' chal gaya, par '==' hi SAHI hai")
    print("=" * 70)

    # ---- GALAT mental model: "is value equality ke liye theek hai" ----
    # Small ints -5..256 CPython me pre-cached (interned) hote hain -> same object.
    a = 256
    b = 256
    print("  [WRONG-looking-right] small int 256:")
    print(f"    a is b = {a is b}   (True — kyunki 256 interned/cached hai)")

    # Range ke bahar (257): NOTE — same function ke do literals ko CPython ek hi
    # constant me fold kar sakta hai, isliye literal-vs-literal 'is' yahan dhokha
    # de sakta hai. Asli truth dekhne ke liye value ko RUNTIME pe banao taaki wo
    # cached small-int pool me na ho -> tab 'is' reliably FAIL hota hai.
    x = 257
    y = int("257")      # runtime pe banaya -> alag object (constant-fold nahi hua)
    print("  [BREAK] value 257 (range ke bahar), runtime-built:")
    print(f"    x is y = {x is y}   (False — 257 cached/interned nahi hai)")
    print(f"    x == y = {x == y}   (hamesha True — yeh sahi check hai)")

    # Computed value pe bhi same baat: value barabar, identity alag.
    p = 1000
    q = int("999") + 1  # runtime pe banaa -> alag object
    print(f"  computed: p is q = {p is q}  but p == q = {p == q}  (value to barabar hai)")

    # Strings: kuch intern hote hain (identifier-jaise), kuch nahi.
    s1 = "hana"
    s2 = "hana"
    print(f"  interned-ish string: 'hana' is 'hana' = {s1 is s2}  (often True)")
    literal = "hana"  # variable use karte hain taaki SyntaxWarning na aaye
    runtime_str = "ha" + ("na" if a else "xx")  # runtime concat -> naya object
    print(f"  runtime-built string is 'hana' = {runtime_str is literal}  "
          f"but == = {runtime_str == literal}")

    print("  FIX / Rule: VALUE equality ke liye HAMESHA '==' use karo. 'is' sirf")
    print("  IDENTITY ke liye (typically 'x is None'). 'is' on ints/strings ka")
    print("  'kaam karna' interning ka implementation detail hai — usपe bharosa mat karo.")


# === SECTION 7: BREAK-IT — weakref galti se object ko pin kar dena =============
def section_7() -> None:
    print("=" * 70)
    print("SECTION 7: BREAK-IT — weak cache me galti se STRONG ref reh jaana")
    print("=" * 70)

    class Session:
        def __init__(self, sid: str) -> None:
            self.sid = sid

    # ---- GALAT: 'weak cache' kehte ho par object ko ek local/list me bhi rakh lete ho.
    weak_cache: weakref.WeakValueDictionary[str, Session] = weakref.WeakValueDictionary()
    s = Session("s-1")
    weak_cache["s-1"] = s
    accidental_keepalive = [s]  # <-- yahi bug: ek strong ref chhup ke baith gaya

    del s
    gc.collect()
    print("  [WRONG] weak_cache hai par ek list ne strong ref pakad rakha hai:")
    print(f"    weak_cache.get('s-1') = {weak_cache.get('s-1')}  <-- abhi bhi zinda (LEAK)")
    print(f"    kyunki accidental_keepalive list hold kar rahi hai: {accidental_keepalive}")

    # ---- FIX: koi chhupa strong ref mat rakho; sirf weak cache me jaane do ----
    accidental_keepalive.clear()  # asli galti hata di
    gc.collect()
    print("  [FIX] strong ref (list) hata di:")
    print(f"    weak_cache.get('s-1') = {weak_cache.get('s-1')}  <-- ab None (free ho gaya)")
    print("  Lesson: WeakValueDictionary tabhi kaam karta jab object pe koi DUSRA")
    print("  strong ref na bacha ho — ek bhi list/closure/local use pin kar deta hai.")


# === SECTION 8: TODO — tum khud likho: weak-cache wala get_or_build() ==========
def section_8() -> None:
    print("=" * 70)
    print("SECTION 8: TODO — get_or_build() with WeakValueDictionary (tum likho)")
    print("=" * 70)
    print("  Expected behaviour:")
    print("    - ek class Registry banao jiske paas WeakValueDictionary cache ho.")
    print("    - method get_or_build(self, key, factory):")
    print("        * agar key cache me hai aur object abhi zinda hai -> wahi return karo")
    print("          (factory dobara MAT chalao).")
    print("        * warna factory() call karke object banao, cache me weakly daalo,")
    print("          aur return karo.")
    print("    - HINT: WeakValueDictionary me value tabhi rahegi jab caller usko")
    print("      strong reference me pakde rakhe; warna apne aap nikal jaayegi.")
    print("    - GOTCHA: factory ka return ek aisi class hona chahiye jisme weakref")
    print("      support ho (slots use karo to '__weakref__' slot dena padega).")

    class Registry:
        def __init__(self) -> None:
            self._cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

        def get_or_build(self, key: str, factory):  # type: ignore[no-untyped-def]
            # TODO: cache check karo; hit -> wahi object; miss -> factory() build + cache.
            raise NotImplementedError("Tum likho: weak-cache backed get_or_build()")

    try:
        reg = Registry()
        calls = {"n": 0}

        class Built:
            __slots__ = ("key", "__weakref__")

            def __init__(self, key: str) -> None:
                self.key = key

        def factory() -> Built:
            calls["n"] += 1
            return Built("acme")

        obj1 = reg.get_or_build("acme", factory)  # build (calls=1)
        obj2 = reg.get_or_build("acme", factory)  # cache hit (calls still 1)
        ok = obj1 is obj2 and calls["n"] == 1
        print(f"  obj1 is obj2 = {obj1 is obj2}, factory calls = {calls['n']}  "
              f"-> {'OK' if ok else 'check logic'}")
    except NotImplementedError as exc:
        print(f"  [pending] {exc}")


# === MAIN: dispatcher (no args -> sab; args -> sirf wo sections) ===============
SECTIONS = {
    1: section_1,
    2: section_2,
    3: section_3,
    4: section_4,
    5: section_5,
    6: section_6,
    7: section_7,
    8: section_8,
}


def main(argv: list[str]) -> None:
    if argv:
        try:
            chosen = [int(a) for a in argv]
        except ValueError:
            print(f"Invalid section numbers: {argv}. Valid: {sorted(SECTIONS)}")
            return
        to_run = [n for n in chosen if n in SECTIONS]
        missing = [n for n in chosen if n not in SECTIONS]
        if missing:
            print(f"Skipping unknown sections: {missing} "
                  f"(valid: {sorted(SECTIONS)})\n")
    else:
        to_run = sorted(SECTIONS)

    for i, n in enumerate(to_run):
        SECTIONS[n]()
        if i != len(to_run) - 1:
            print()


if __name__ == "__main__":
    main(sys.argv[1:])
