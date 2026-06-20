"""
================================================================================
TOPIC: Dataclasses (@dataclass)
================================================================================

KYA HOTA HAI:
    @dataclass ek class decorator hai jo tumhare class ke type-annotated fields
    dekh kar boilerplate khud generate kar deta hai — __init__, __repr__ aur
    __eq__. Tum sirf fields likho (name: type), baaki dunder methods decorator
    likhta hai. Field-level tuning ke liye field() helper milta hai
    (default_factory, compare, repr, init flags etc.).

KYO NEED PADI:
    Plain class me har data-holder ke liye __init__, __repr__, __eq__ haath se
    likhna padta tha — repetitive aur bug-prone (ek attribute add kiya, __eq__
    me add karna bhool gaye). Dataclass ye sab declaratively generate karta hai,
    to DTOs / config / value objects 3 line me ban jaate hain, readable aur
    consistent. Mutable default ka classic trap bhi field(default_factory) se
    properly solve hota hai.

KAISE USE KARTE HAIN:
    `from dataclasses import dataclass, field` -> class ke upar @dataclass lagao
    -> fields ko type annotation ke saath likho. Tuning flags: frozen=True
    (immutable + hashable), slots=True (memory + fast attr), order=True
    (comparison operators), eq=True (default). Mutable default ke liye hamesha
    field(default_factory=list/dict). Validation/derived fields ke liye
    __post_init__ method.

KAHAN USE HOTA HAI (scenarios):
    - SAP HANA connector: incoming row ka DTO + ek frozen RetryPolicy config
      object jo dict keys / cache keys me safely use ho sake.
    - Payment gateway: frozen IdempotencyKey value object — immutable + hashable,
      to seedha set/dict key ban sakta hai duplicate charge rokne ke liye.
    - Multi-tenant Django SaaS: TenantContext jisme tenant_id + features list,
      jahan default_factory se har instance ko apni fresh list milti hai.
    - Celery task payload: order=True wale objects ko priority pe sort karna.
    - Derived/validated config: __post_init__ me amount > 0 check, ya
      total = price * qty compute karna load time pe.

INTERVIEW ANSWER (English):
    A dataclass is a decorator that auto-generates the boilerplate for a
    data-holding class — __init__, __repr__ and __eq__ — directly from the
    type-annotated fields, so I declare data once instead of hand-writing dunder
    methods that drift out of sync. The senior nuances matter most: I never use a
    bare mutable default like a list, because that value is shared across every
    instance; instead I use field(default_factory=list). I reach for frozen=True
    when I want an immutable, hashable value object — for example a payment
    idempotency key that can safely be a dict or set key — and slots=True to cut
    per-instance memory on high-cardinality DTOs. order=True synthesizes the
    comparison operators for sorting, and __post_init__ is where I put validation
    and derived fields. Compared to a namedtuple, a dataclass is mutable by
    default, supports defaults and methods cleanly, and reads better; compared to
    pydantic, a dataclass does NOT coerce or validate types at runtime, so for
    untrusted external input I still prefer pydantic, and keep dataclasses for
    internal, already-trusted data.

--------------------------------------------------------------------------------
Run:
    python 07_dataclasses.py          # saare sections chalao
    python 07_dataclasses.py 1 5      # sirf section 1 aur 5 chalao

Sections:
    1. DEMO        — auto __init__ / __repr__ / __eq__ free me milte hain
    2. DEMO        — frozen=True (immutable + hashable) aur order=True sorting
    3. DEMO        — __post_init__ validation + derived field
    4. REAL        — payment idempotency: frozen+slots key, set me dedupe
    5. BREAK-IT    — mutable default list shared across instances (+ fix)
    6. BREAK-IT    — frozen dataclass attribute assign karne pe FrozenInstanceError
    7. DEMO        — dataclass vs namedtuple vs (pseudo) pydantic ka farak
    8. TODO        — tum khud likho: frozen RetryPolicy SAP HANA config
================================================================================
"""
from __future__ import annotations

import sys
from collections import namedtuple
from dataclasses import (
    FrozenInstanceError,
    asdict,
    dataclass,
    field,
    fields,
)


# === SECTION 1: DEMO — auto __init__ / __repr__ / __eq__ =====================
@dataclass
class HanaRow:
    """SAP HANA se aaya ek row. Notice: koi __init__/__repr__/__eq__ nahi likha."""
    pk: int
    material: str
    qty: int = 0  # default value bhi de sakte ho


def section_1() -> None:
    print("=" * 70)
    print("SECTION 1: @dataclass auto-generates __init__ / __repr__ / __eq__")
    print("=" * 70)

    r1 = HanaRow(pk=1, material="MAT-0001", qty=5)
    r2 = HanaRow(pk=1, material="MAT-0001", qty=5)
    r3 = HanaRow(pk=2, material="MAT-0002")  # qty default 0

    # __repr__ free me — debugging/logging ke liye readable
    print(f"  __repr__  -> {r1!r}")
    print(f"  default   -> {r3!r}  (qty default 0 lag gaya)")

    # __eq__ free me — FIELD-WISE compare karta hai, identity nahi
    print(f"  r1 == r2 ? {r1 == r2}   (same field values -> True)")
    print(f"  r1 is r2 ? {r1 is r2}   (alag objects -> False)")
    print(f"  r1 == r3 ? {r1 == r3}   (alag values -> False)")

    # introspection: fields() se field metadata milta hai
    names = [f.name for f in fields(HanaRow)]
    print(f"  fields()  -> {names}")
    print("  Takeaway: 3 line ki class, par 3 dunder methods muft mil gaye.")


# === SECTION 2: DEMO — frozen=True (immutable+hashable) + order=True =========
@dataclass(frozen=True, order=True)
class Version:
    """frozen -> immutable + hashable; order -> <, <=, >, >= comparison aate hain.
    Comparison FIELD-ORDER me tuple jaisa hota hai: pehle major, fir minor, fir patch."""
    major: int
    minor: int
    patch: int


def section_2() -> None:
    print("=" * 70)
    print("SECTION 2: frozen=True (immutable + hashable) + order=True (sortable)")
    print("=" * 70)

    versions = [Version(1, 2, 0), Version(1, 0, 5), Version(2, 0, 0), Version(1, 2, 0)]

    # order=True -> seedha sort ho jaata hai (tuple-style field comparison)
    print(f"  sorted -> {sorted(versions)}")
    print(f"  min    -> {min(versions)}   max -> {max(versions)}")

    # frozen=True -> hashable, to set/dict key ban sakta hai (dedupe free)
    unique = set(versions)
    print(f"  set()  -> {unique}  (frozen=hashable, duplicate Version(1,2,0) merge)")
    print(f"  hash(Version(1,2,0)) = {hash(Version(1, 2, 0))}")
    print("  Takeaway: frozen=True deta hai immutable+hashable; order=True deta "
          "hai comparison operators (sorting ke liye).")


# === SECTION 3: DEMO — __post_init__ validation + derived field ==============
@dataclass
class LineItem:
    """__post_init__ tab chalta hai jab __init__ saare fields set kar chuka.
    Yahan validation + derived field (total) compute karte hain."""
    price: float
    qty: int
    # init=False -> ye field constructor argument me nahi aayega, hum compute karenge
    total: float = field(init=False)

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError(f"price negative nahi ho sakta: {self.price}")
        if self.qty <= 0:
            raise ValueError(f"qty positive honi chahiye: {self.qty}")
        self.total = round(self.price * self.qty, 2)  # derived field set


def section_3() -> None:
    print("=" * 70)
    print("SECTION 3: __post_init__ — validation + derived field (total)")
    print("=" * 70)

    item = LineItem(price=99.5, qty=3)
    print(f"  valid     -> {item!r}")
    print(f"  total derived = {item.total}  (price*qty, hum ne pass nahi kiya)")

    # validation actually enforce hoti hai
    try:
        LineItem(price=-1, qty=2)
    except ValueError as exc:
        print(f"  invalid   -> ValueError raised: {exc}")
    print("  Takeaway: __post_init__ = construction-time validation + derived "
          "values. init=False field constructor se hide ho jaata hai.")


# === SECTION 4: REAL — payment idempotency key (frozen + slots) ==============
@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Payment gateway value object. frozen -> immutable + hashable (set/dict key
    ban sakta hai), slots -> per-instance memory kam (lakhon keys ho sakti hain)."""
    merchant_id: int
    order_ref: str
    amount_cents: int


def _charge(seen: set[IdempotencyKey], key: IdempotencyKey) -> str:
    """Idempotent charge: agar key pehle dekhi -> skip (double charge rokna)."""
    if key in seen:  # frozen=hashable hone ki wajah se set membership chalti hai
        return "SKIPPED (duplicate request, no double charge)"
    seen.add(key)
    return "CHARGED"


def section_4() -> None:
    print("=" * 70)
    print("SECTION 4: REAL — payment idempotency, frozen+slots key set me dedupe")
    print("=" * 70)

    seen: set[IdempotencyKey] = set()
    # Network retry ki wajah se same charge request 3 baar aa gayi
    k = IdempotencyKey(merchant_id=42, order_ref="ORD-9001", amount_cents=14999)
    requests = [k, k, IdempotencyKey(42, "ORD-9002", 500), k]

    for i, key in enumerate(requests, 1):
        result = _charge(seen, key)
        print(f"  req#{i} {key.order_ref} ({key.amount_cents}c) -> {result}")

    print(f"  Distinct charges committed: {len(seen)} (3 mein se 2 unique)")
    # frozen=True ka proof: koi bhi attribute set/overwrite block ho jaata hai.
    # NOTE: frozen+slots combo me generated __setattr__ TypeError bhi de sakta
    # hai (sirf FrozenInstanceError maan ke mat chalna — wahi senior gotcha hai).
    try:
        k.note = "tampered"  # type: ignore[attr-defined]
    except (FrozenInstanceError, AttributeError, TypeError) as exc:
        print(f"  Extra/overwrite attribute blocked -> {type(exc).__name__}: {exc}")
    print("  Takeaway: frozen value object = natural dict/set key for "
          "idempotency; slots se memory bhi bachti hai.")


# === SECTION 5: BREAK-IT — mutable default shared across instances ===========
def section_5() -> None:
    print("=" * 70)
    print("SECTION 5: BREAK-IT — mutable default list SAARI instances me shared")
    print("=" * 70)

    # ---- GALAT: bare mutable default. Sirf @dataclass me ye ERROR deta hai
    # newer Python pe, par concept samajhne ke liye plain class se dikhate hain
    # ki actual problem kya hoti hai. ----
    class TenantBad:
        def __init__(self, tenant_id: int, features: list[str] = []) -> None:
            # DEFAULT [] ek hi baar banti hai (function def time pe) aur SAARE
            # callers ke beech SHARE hoti hai — yahi asli trap hai.
            self.tenant_id = tenant_id
            self.features = features

    a = TenantBad(1)
    b = TenantBad(2)
    a.features.append("billing")  # sirf 'a' ko chahiye tha...
    print("  [WRONG] bare mutable default (shared object):")
    print(f"    a.features -> {a.features}")
    print(f"    b.features -> {b.features}   <-- LEAK! b me bhi aa gaya")
    print(f"    a.features is b.features ? {a.features is b.features}  (ek hi object)")

    # @dataclass actually is galti ko CATCH karta hai compile/def time pe:
    print("\n  Note: @dataclass me bare 'features: list = []' likhoge to Python")
    print("  ValueError dega ('mutable default ... not allowed'). Isiliye:")

    # ---- SAHI: field(default_factory=list) -> har instance ko fresh list ----
    @dataclass
    class TenantGood:
        tenant_id: int
        features: list[str] = field(default_factory=list)  # fresh list per instance

    g1 = TenantGood(1)
    g2 = TenantGood(2)
    g1.features.append("billing")
    print("  [FIX] field(default_factory=list):")
    print(f"    g1.features -> {g1.features}")
    print(f"    g2.features -> {g2.features}   <-- isolated, leak nahi")
    print(f"    g1.features is g2.features ? {g1.features is g2.features}  (alag objects)")
    print("  Lesson: mutable default (list/dict/set) ke liye HAMESHA "
          "field(default_factory=...).")


# === SECTION 6: BREAK-IT — frozen instance pe assignment FrozenInstanceError =
def section_6() -> None:
    print("=" * 70)
    print("SECTION 6: BREAK-IT — frozen dataclass mutate karne pe error")
    print("=" * 70)

    @dataclass(frozen=True)
    class RetryConfig:
        max_attempts: int
        backoff_s: float

    cfg = RetryConfig(max_attempts=3, backoff_s=0.5)
    print(f"  config -> {cfg!r}")

    # ---- GALAT: log frozen object ko 'thoda sa' update karna chahte hain ----
    print("  [WRONG] seedha attribute assign karna:")
    try:
        cfg.max_attempts = 5  # type: ignore[misc]
        print("    assign ho gaya?! (unexpected)")
    except FrozenInstanceError as exc:
        print(f"    FrozenInstanceError -> {exc}")

    # ---- SAHI: naya object banao (dataclasses.replace) — frozen ka intended flow
    from dataclasses import replace
    cfg2 = replace(cfg, max_attempts=5)
    print("  [FIX] dataclasses.replace() se naya immutable object:")
    print(f"    original -> {cfg!r}")
    print(f"    replaced -> {cfg2!r}")
    print("  Lesson: frozen object ko mutate mat karo; replace() se naya "
          "instance banao (functional update).")


# === SECTION 7: DEMO — dataclass vs namedtuple vs pydantic ===================
PointNT = namedtuple("PointNT", ["x", "y"])


@dataclass
class PointDC:
    x: int
    y: int


def _fake_pydantic_coerce(x: object, y: object) -> tuple[int, int]:
    """Pydantic INSTALL nahi karna allowed (stdlib only), isliye pydantic ka
    KEY farak — runtime type coercion/validation — manually simulate karte hain.
    Pydantic '3' (str) ko int 3 me coerce kar deta; dataclass NAHI karta."""
    return int(x), int(y)


def section_7() -> None:
    print("=" * 70)
    print("SECTION 7: dataclass vs namedtuple vs pydantic — kab kaun?")
    print("=" * 70)

    dc = PointDC(1, 2)
    nt = PointNT(1, 2)

    print("  namedtuple:")
    print(f"    {nt!r}  -> immutable, tuple hai, index/unpack ho sakta")
    print(f"    nt[0]={nt[0]}, unpack: x,y = nt -> {tuple(nt)}")
    print("    par: by default mutable nahi, methods/defaults add karna awkward.")

    print("  dataclass:")
    print(f"    {dc!r}  -> mutable by default, methods/defaults easy, readable")
    dc.x = 99
    print(f"    dc.x = 99 -> {dc!r}  (mutable)")
    print(f"    asdict()  -> {asdict(dc)}")

    print("  pydantic (concept, install nahi kiya):")
    print('    BaseModel("3", "4") ko -> int 3, int 4 COERCE + validate karta.')
    coerced = _fake_pydantic_coerce("3", "4")
    print(f"    simulated coercion of ('3','4') -> {coerced}")
    # dataclass me wahi string seedha rakh leta hai — NO validation:
    sneaky = PointDC("3", "4")  # type: ignore[arg-type]
    print(f"    dataclass PointDC('3','4') -> {sneaky!r}  <-- str hi rahe, NO coercion!")
    print(f"    type(sneaky.x) = {type(sneaky.x).__name__}  (int nahi, str!)")
    print("  Rule of thumb: namedtuple = lightweight immutable record/unpack;")
    print("  dataclass = internal trusted data + behaviour; pydantic = untrusted")
    print("  external input (API body, config file) jahan validation/coercion chahiye.")


# === SECTION 8: TODO — tum khud likho =======================================
def section_8() -> None:
    print("=" * 70)
    print("SECTION 8: TODO — frozen RetryPolicy (SAP HANA connector config)")
    print("=" * 70)
    print("  Expected behaviour:")
    print("    - @dataclass(frozen=True, slots=True) wali class RetryPolicy.")
    print("    - fields: max_attempts:int, base_backoff_s:float,")
    print("      retry_on:tuple[str,...] = field(default_factory=...)  <- mutable")
    print("      default ke liye factory use karo (bare tuple bhi chalega par list/")
    print("      set ho to factory MUST).")
    print("    - __post_init__: max_attempts >= 1 verify karo, warna ValueError.")
    print("    - method backoff_for(self, attempt:int) -> float jo")
    print("      base_backoff_s * (2 ** (attempt-1)) lautaye (exponential backoff).")
    print("    - frozen hone ki wajah se ye dict/cache key ban sake (hashable).")

    def retry_policy_solution() -> object:
        # TODO: yahan frozen+slots RetryPolicy class bana ke ek instance return karo,
        # aur backoff_for(3) print karke check karo. (max_attempts=0 pe ValueError aana chahiye.)
        raise NotImplementedError("Tum likho: frozen+slots RetryPolicy + backoff_for()")

    try:
        policy = retry_policy_solution()
        print(f"  Tumhara policy: {policy!r}")
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
