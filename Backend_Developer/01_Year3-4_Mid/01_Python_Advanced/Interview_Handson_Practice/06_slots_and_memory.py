"""
================================================================================
TOPIC: __slots__ & per-instance memory
================================================================================

KYA HOTA HAI:
    By default har Python object apne attributes ko ek per-instance __dict__
    (hash map) me store karta hai. __slots__ ek class-level declaration hai jo
    bolti hai "is class ke instances ke pass sirf YE fixed attributes honge".
    Isse Python __dict__ banana band kar deta hai aur attributes ko ek compact,
    fixed memory layout (C struct jaisa) me rakhta hai.

KYO NEED PADI:
    Per-instance __dict__ mehnga hai — har object ke saath ek alag dict aata hai
    jo attribute values ke alawa hash-table ka overhead bhi carry karta hai.
    Jab tum LAKHON chhote objects bana rahe ho (rows, particles, cache entries,
    SAP HANA se aaye records), to ye dict overhead RAM ko uda deta hai aur GC
    pressure badhata hai. __slots__ wahi dict overhead hata deta hai.

KAISE USE KARTE HAIN:
    Class body me `__slots__ = ("x", "y")` likho — sirf wahi naam allowed honge.
    Modern code me sabse clean tareeka: @dataclass(slots=True). Agar weakref
    chahiye to "__weakref__" slot add karo. Inheritance me HAR ancestor ko
    __slots__ (ya __slots__ = ()) dena padta hai warna __dict__ wapas aa jaata.

KAHAN USE HOTA HAI (scenarios):
    - SAP HANA bi-directional connector: ek sync run me lakhon row-DTOs bante
      hain; slots se memory footprint aur retry-buffer chhota rehta hai.
    - Celery/Redis pipeline: bulk message/event objects jo ek batch me hold hote
      hain — slots se worker RSS kam, kam OOM kills.
    - Multi-tenant Django SaaS: hot in-memory cache / rate-limiter buckets jisme
      per-key chhote value objects hote hain.
    - Payment gateway: idempotency-key ledger entries jo ek window me memory me
      rehte hain.
    - Graph/tree nodes, geometry points, parsing tokens — koi bhi chhota object
      jo crore ki tadaad me banta hai.

INTERVIEW ANSWER (English):
    By default every Python instance stores its attributes in a per-instance
    __dict__, which gives flexibility but costs a separate hash table per object.
    Defining __slots__ tells the interpreter the exact, fixed set of attributes,
    so it allocates them in a compact C-level layout and skips the __dict__
    entirely. The payoff is two-fold: significantly lower memory per instance —
    often 40 to 50 percent — and slightly faster attribute access because lookup
    becomes a fixed descriptor offset instead of a dict probe. The senior nuance
    is that __slots__ only helps if EVERY class in the inheritance chain declares
    it; one slot-less ancestor reintroduces __dict__ and silently kills the
    savings. You also lose dynamic attributes and weakref support unless you add
    a "__weakref__" slot explicitly. So I reach for it for high-cardinality small
    objects — millions of DTOs or cache entries — not for ordinary low-count
    domain classes where the flexibility is worth more than the bytes.

--------------------------------------------------------------------------------
Run:
    python 06_slots_and_memory.py          # saare sections chalao
    python 06_slots_and_memory.py 1 4      # sirf section 1 aur 4 chalao

Sections:
    1. DEMO        — __dict__ ka cost vs __slots__ ka compact layout
    2. DEMO        — tracemalloc memory benchmark (dict vs slots)
    3. DEMO        — faster attribute access (timeit micro-benchmark)
    4. REAL        — SAP HANA sync: lakhon row-DTOs ka memory footprint
    5. BREAK-IT    — inheritance gotcha: ek slot-less parent saari saving kha gaya
    6. BREAK-IT    — weakref TypeError jab __weakref__ slot missing ho
    7. TODO        — tum khud likho: slotted RateLimiterBucket
================================================================================
"""
from __future__ import annotations

import sys
import timeit
import tracemalloc
import weakref
from dataclasses import dataclass


# === SECTION 1: DEMO — __dict__ ka cost vs __slots__ ka layout ===============
def section_1() -> None:
    print("=" * 70)
    print("SECTION 1: __dict__ ka cost vs __slots__ ka compact layout")
    print("=" * 70)

    class PlainRow:
        # koi __slots__ nahi -> har instance ke saath ek __dict__ aayega
        def __init__(self, id_: int, amount: float) -> None:
            self.id = id_
            self.amount = amount

    class SlottedRow:
        __slots__ = ("id", "amount")  # sirf ye 2 naam allowed

        def __init__(self, id_: int, amount: float) -> None:
            self.id = id_
            self.amount = amount

    plain = PlainRow(1, 99.5)
    slotted = SlottedRow(1, 99.5)

    print(f"PlainRow   has __dict__ ? {hasattr(plain, '__dict__')}")
    print(f"  plain.__dict__         = {plain.__dict__}")
    print(f"SlottedRow has __dict__ ? {hasattr(slotted, '__dict__')}")
    print(f"SlottedRow __slots__     = {SlottedRow.__slots__}")

    # __dict__ ka size dekh lo — yahi per-instance overhead hai jo slots hata deta
    print(f"sizeof(plain.__dict__)   = {sys.getsizeof(plain.__dict__)} bytes "
          f"(ye overhead har plain object ke saath aata hai)")
    print("Takeaway: slotted object me alag dict nahi -> us dict ka overhead bachta hai.")


# === SECTION 2: DEMO — tracemalloc memory benchmark (dict vs slots) ==========
@dataclass
class _DictPoint:
    x: int
    y: int
    z: int


@dataclass(slots=True)
class _SlotPoint:
    x: int
    y: int
    z: int


def _measure_peak_mb(cls: type, n: int) -> float:
    """n instances banao aur peak traced memory (MB) lautao."""
    tracemalloc.start()
    holder = [cls(i, i, i) for i in range(n)]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del holder  # ref tod do taaki agle measurement me leak na ho
    return peak / 1024 / 1024


def section_2() -> None:
    print("=" * 70)
    print("SECTION 2: tracemalloc benchmark — dict vs slots (500k objects)")
    print("=" * 70)

    n = 500_000
    dict_mb = _measure_peak_mb(_DictPoint, n)
    slot_mb = _measure_peak_mb(_SlotPoint, n)

    print(f"  {n:,} x dict-based   -> {dict_mb:6.1f} MB")
    print(f"  {n:,} x slots-based  -> {slot_mb:6.1f} MB")
    saved = (1 - slot_mb / dict_mb) * 100 if dict_mb else 0.0
    print(f"  Memory saved        -> ~{saved:.0f}% (is machine pe abhi measured)")
    print("  Real classes me jitne zyada attrs, utna bada __dict__ overhead,")
    print("  to typically 30-50% saving aati hai high-cardinality objects pe.")


# === SECTION 3: DEMO — faster attribute access ==============================
def section_3() -> None:
    print("=" * 70)
    print("SECTION 3: attribute access speed — slots thoda fast (fixed offset)")
    print("=" * 70)

    class PlainAttr:
        def __init__(self) -> None:
            self.v = 0

    class SlotAttr:
        __slots__ = ("v",)

        def __init__(self) -> None:
            self.v = 0

    # ek statement me kai attribute reads -> signal noise se upar aata hai.
    # aur best-of-5 lete hain taaki GC/scheduler jitter average na bigaade.
    stmt = "o.v; o.v; o.v; o.v; o.v"
    loops = 1_000_000
    repeats = 5
    plain_t = min(timeit.repeat(stmt, setup="o=P()", globals={"P": PlainAttr},
                                number=loops, repeat=repeats))
    slot_t = min(timeit.repeat(stmt, setup="o=S()", globals={"S": SlotAttr},
                               number=loops, repeat=repeats))

    print(f"  dict attr read  : {plain_t:.3f}s (best of {repeats}, {loops:,}x5 reads)")
    print(f"  slot attr read  : {slot_t:.3f}s (best of {repeats}, {loops:,}x5 reads)")
    faster = "slots" if slot_t < plain_t else "dict"
    ratio = plain_t / slot_t if slot_t else 1.0
    print(f"  Faster          : {faster} (~{ratio:.2f}x) "
          f"-- slot = descriptor pe fixed offset, dict = hash probe")
    print("  Note: speedup chhota hai; asli win MEMORY hai, raw speed nahi.")


# === SECTION 4: REAL — SAP HANA sync me lakhon row-DTOs ======================
@dataclass(slots=True)
class HanaRowDTO:
    """SAP HANA se aaya ek row. Ek sync run me ye crore ki tadaad me ban sakta hai.
    slots=True -> retry-buffer / staging list ka memory footprint kam, OOM risk kam."""
    pk: int
    material: str
    qty: int
    synced: bool


def section_4() -> None:
    print("=" * 70)
    print("SECTION 4: REAL — SAP HANA connector, 300k row-DTOs staging buffer")
    print("=" * 70)

    n = 300_000
    tracemalloc.start()
    # idempotent sync: rows ko buffer me hold karte hain jab tak ack nahi aata
    staging: list[HanaRowDTO] = [
        HanaRowDTO(pk=i, material=f"MAT-{i % 1000:04d}", qty=i % 50, synced=False)
        for i in range(n)
    ]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # idempotency: dobaara aaye to skip
    seen: set[int] = set()
    unique = sum(1 for r in staging if r.pk not in seen and not seen.add(r.pk))

    print(f"  Staging buffer : {n:,} HanaRowDTO objects")
    print(f"  Peak memory    : {peak / 1024 / 1024:.1f} MB "
          f"(~{peak / n:.0f} bytes/row)")
    print(f"  Unique pks     : {unique:,} (idempotency guard chala)")
    print("  Agar dict-based hota to yahi buffer ~40-50% zyada RAM khaata —")
    print("  jo ek Celery worker pe OOM kill ki seedhi wajah ban sakta hai.")


# === SECTION 5: BREAK-IT — inheritance gotcha (slot-less parent) =============
def section_5() -> None:
    print("=" * 70)
    print("SECTION 5: BREAK-IT — ek slot-less ancestor SAARI saving kha jaata")
    print("=" * 70)

    # ---- GALAT TAREEKA: parent me __slots__ nahi ----
    class BaseEntity:  # bhool gaye __slots__ dena
        def __init__(self) -> None:
            self.created_at = "2026-01-01"

    class TenantRecord(BaseEntity):
        __slots__ = ("tenant_id", "payload")  # lagta hai slotted hai...

        def __init__(self, tenant_id: int) -> None:
            super().__init__()
            self.tenant_id = tenant_id
            self.payload = {}

    bad = TenantRecord(tenant_id=7)
    print("  [WRONG] parent ke paas __slots__ nahi hai:")
    print(f"    TenantRecord has __dict__ ? {hasattr(bad, '__dict__')}  <-- True!")
    bad.random_typo = "oops"  # silently allowed -> saving gayi
    print(f"    bad.random_typo set ho gaya -> {bad.random_typo!r} (memory saving NAHI mili)")
    print(f"    bad.__dict__ = {bad.__dict__}")

    # ---- SAHI TAREEKA: HAR ancestor ko __slots__ (ya () ) do ----
    class BaseEntityFixed:
        __slots__ = ("created_at",)

        def __init__(self) -> None:
            self.created_at = "2026-01-01"

    class TenantRecordFixed(BaseEntityFixed):
        __slots__ = ("tenant_id", "payload")

        def __init__(self, tenant_id: int) -> None:
            super().__init__()
            self.tenant_id = tenant_id
            self.payload = {}

    good = TenantRecordFixed(tenant_id=7)
    print("\n  [FIX] har ancestor ke paas __slots__ hai:")
    print(f"    TenantRecordFixed has __dict__ ? {hasattr(good, '__dict__')}  <-- False!")
    try:
        good.random_typo = "oops"
        print("    typo set ho gaya?! (unexpected)")
    except AttributeError as exc:
        print(f"    good.random_typo BLOCKED -> AttributeError: {exc}")
    print("  Lesson: chain ka ek bhi slot-less class __dict__ wapas le aata hai.")


# === SECTION 6: BREAK-IT — weakref ke liye __weakref__ slot chahiye ==========
def section_6() -> None:
    print("=" * 70)
    print("SECTION 6: BREAK-IT — slots ke saath weakref TypeError")
    print("=" * 70)

    # ---- GALAT: slotted class weakref support kho deti hai by default ----
    class CacheEntry:
        __slots__ = ("key", "value")

        def __init__(self, key: str, value: int) -> None:
            self.key = key
            self.value = value

    print("  [WRONG] plain slotted class pe weakref:")
    try:
        weakref.ref(CacheEntry("k", 1))  # boom
        print("    weakref ban gaya?! (unexpected)")
    except TypeError as exc:
        print(f"    TypeError -> {exc}")
        print("    (WeakValueDictionary based cache yahi pe silently toot jaata)")

    # ---- SAHI: explicitly __weakref__ slot add karo ----
    class CacheEntryFixed:
        __slots__ = ("key", "value", "__weakref__")

        def __init__(self, key: str, value: int) -> None:
            self.key = key
            self.value = value

    print("\n  [FIX] __weakref__ slot add karke:")
    entry = CacheEntryFixed("k", 1)
    ref = weakref.ref(entry)
    print(f"    weakref ban gaya -> {ref}  alive? {ref() is entry}")
    print("  Lesson: agar object WeakValueDictionary/weakref me jaayega to "
          "'__weakref__' slot zaroori hai.")


# === SECTION 7: TODO — tum khud likho =======================================
def section_7() -> None:
    print("=" * 70)
    print("SECTION 7: TODO — slotted RateLimiterBucket khud implement karo")
    print("=" * 70)
    print("  Expected behaviour:")
    print("    - class RateLimiterBucket: __slots__ ke saath ('tokens', 'last_ts').")
    print("    - __init__(self, tokens: int, last_ts: float) attributes set kare.")
    print("    - method allow(self, now: float, refill: float) -> bool:")
    print("        * elapsed = now - last_ts; tokens += elapsed * refill (cap 'capacity'? simple rakho)")
    print("        * agar tokens >= 1: tokens -= 1; last_ts = now; return True")
    print("        * warna return False")
    print("    - NOTE: koi extra attribute (jaise self.name) set karne pe")
    print("      AttributeError aana chahiye — wahi slots ka proof hai.")
    print("    - Bonus: multi-tenant Django SaaS me per-tenant lakhon buckets ban")
    print("      sakte hain, isliye slots se memory bachti hai.")

    def rate_limiter_bucket_solution() -> object:
        # TODO: yahan apna RateLimiterBucket class bana ke ek instance return karo.
        raise NotImplementedError("Tum likho: slotted RateLimiterBucket + allow()")

    try:
        bucket = rate_limiter_bucket_solution()
        print(f"  Tumhara bucket: {bucket!r}")
    except NotImplementedError as exc:
        print(f"  [pending] {exc}")


# === MAIN: dispatcher (no args -> sab; args -> sirf wo sections) =============
SECTIONS = {
    1: section_1,
    2: section_2,
    3: section_3,
    4: section_4,
    5: section_5,
    6: section_6,
    7: section_7,
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
