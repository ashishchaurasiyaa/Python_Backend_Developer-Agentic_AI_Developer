"""
Operator Overloading vs Method Overriding (aur Python me method overloading kyun NAHI hai)
==========================================================================================

TOPIC: Operator Overloading vs Method Overriding (and why Python has no method overloading)

KYA HOTA HAI:
  - Operator overloading = apni class ko +, ==, <, hash() jaise built-in operators ka
    matlab sikhana via dunder methods (__add__, __eq__, __lt__, __hash__, __repr__).
  - Method overriding = subclass me parent ka SAME naam ka method dobara likhna (inheritance).
  - Method OVERLOADING (same naam, alag signature jaise Java/C++) Python me hota hi nahi —
    same naam ka dusra def bas pehle wale ko overwrite kar deta hai.

KYO NEED PADI:
  - Domain objects (Money, Vector, SemVer, TenantId) ko natural feel dene ke liye —
    total = inv1 + inv2, ya `if version < required:` directly likh paao.
  - Bina dunders ke har jagah obj.add_to(...) / obj.equals(...) likhna padta, ugly aur
    error-prone. Sets/dicts me objects daalne ke liye __eq__ + __hash__ chahiye hi.

KAISE USE KARTE HAIN:
  - Dunder methods define karo. Type mismatch pe `return NotImplemented` (raise nahi) —
    Python phir reflected operand (__radd__) try karta hai, warna clean TypeError deta hai.
  - Overriding ke liye subclass me method dobara likho, parent ko super() se call karo.
  - "Overloading" ka effect chahiye to: default args, *args/**kwargs, ya
    functools.singledispatch (type pe dispatch).

KAHAN USE HOTA HAI (scenarios):
  - SAP HANA connector: RetryPolicy objects ko `==` se dedupe karna, ya Money amounts add karna.
  - Payment idempotency: IdempotencyKey ko set/dict me key banane ke liye __eq__ + __hash__.
  - Multi-tenant Django (Niroskos): TenantId value object jise `==`/hash se compare karein.
  - Celery/Redis pipeline: SemVer-style versions ko `<` se compare karke ordering.
  - singledispatch: ek `serialize(obj)` jo type ke hisaab se alag branch le (str/dict/Decimal).

INTERVIEW ANSWER (English):
  Operator overloading lets a class define what built-in operators mean for its instances
  through dunder methods such as __add__, __eq__, __lt__, __hash__ and __repr__. Method
  overriding is different: it is a subclass redefining a method that exists on its parent,
  resolved at runtime through the MRO. Python deliberately has no method overloading in the
  Java/C++ sense — defining two functions with the same name simply rebinds the name, so the
  last definition wins; we get the same effect with default arguments, *args, or
  functools.singledispatch which dispatches on the first argument's type. Two senior nuances
  separate a strong candidate. First, in operator dunders you should return NotImplemented
  (not raise) for unsupported operand types, so Python can try the reflected method like
  __radd__ before raising a clean TypeError. Second, defining __eq__ on a class silently sets
  __hash__ to None, making instances unhashable and unusable as dict keys or set members; if
  the object is logically immutable you must restore hashability by defining __hash__
  consistently with __eq__ (equal objects must hash equal).

Run:
  python 01_operator_overloading_vs_overriding.py            # saare sections
  python 01_operator_overloading_vs_overriding.py 1 4        # sirf section 1 aur 4

Sections:
  1. DEMO: dunder operator overloading (__add__/__eq__/__hash__/__lt__/__repr__)
  2. DEMO: NotImplemented + reflected __radd__ (sahi vs galat)
  3. DEMO: method overriding via inheritance (super() ke saath)
  4. DEMO: Python me method overloading NAHI — last def jeet jaata hai
  5. DEMO: "overloading" ka asli tareeka — default args + functools.singledispatch
  6. REAL BACKEND: IdempotencyKey / Money value objects (payment + SAP HANA)
  7. BREAK IT / GOTCHA: __eq__ ne __hash__=None kar diya -> unhashable
  8. TODO (tum khud likho): SemVer class with full ordering + hashing
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from functools import singledispatch, total_ordering


# === SECTION 1: dunder operator overloading ===
class Vector:
    """2D vector — dikhata hai __add__, __eq__, __lt__, __hash__, __repr__ ek saath."""

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:  # debugging/log friendly — interviewer ye dekhta hai
        return f"Vector(x={self.x}, y={self.y})"

    def __add__(self, other: object) -> "Vector":
        if not isinstance(other, Vector):
            return NotImplemented  # raise mat karo — Python ko fallback ka chance do
        return Vector(self.x + other.x, self.y + other.y)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)

    def __lt__(self, other: object) -> bool:
        # magnitude (length squared) ke basis pe ordering
        if not isinstance(other, Vector):
            return NotImplemented
        return (self.x**2 + self.y**2) < (other.x**2 + other.y**2)

    def __hash__(self) -> int:
        # __eq__ define kiya to __hash__ bhi consistent dena padta hai
        return hash((self.x, self.y))


def section_1() -> None:
    print("=" * 64)
    print("SECTION 1: dunder operator overloading")
    print("=" * 64)
    a, b = Vector(1, 2), Vector(3, 4)
    print(f"  a + b           -> {a + b}            (via __add__)")
    print(f"  a == Vector(1,2)-> {a == Vector(1, 2)}              (via __eq__)")
    print(f"  a < b           -> {a < b}              (via __lt__)")
    print(f"  hash(a)==hash(.)-> {hash(a) == hash(Vector(1, 2))}              (via __hash__)")
    print(f"  set me dedup    -> {sorted(repr(v) for v in {a, b, Vector(1, 2)})}")
    print("  Takeaway: equal objects same hash -> set/dict me sahi behave karte hain")


# === SECTION 2: NotImplemented + reflected __radd__ ===
class Money:
    """Money jo int ke saath bhi add ho — reflected __radd__ kyun chahiye dikhata hai."""

    def __init__(self, paise: int) -> None:
        self.paise = paise

    def __repr__(self) -> str:
        return f"Money(₹{self.paise / 100:.2f})"

    def __add__(self, other: object) -> "Money":
        if isinstance(other, Money):
            return Money(self.paise + other.paise)
        if isinstance(other, int):  # 50 + money type cases ke liye
            return Money(self.paise + other)
        return NotImplemented

    # sum([...]) 0 se start karta hai -> 0 + Money -> int.__add__ fail -> Money.__radd__
    def __radd__(self, other: object) -> "Money":
        return self.__add__(other)


def section_2() -> None:
    print("=" * 64)
    print("SECTION 2: NotImplemented + reflected __radd__")
    print("=" * 64)
    m1, m2 = Money(10000), Money(5000)
    print(f"  Money + Money         -> {m1 + m2}")

    # GALAT EXPECTATION: bina __radd__ ke sum() crash karta (0 + Money).
    # Yahan __radd__ hai isliye sum() chal jaata hai:
    total = sum([m1, m2, Money(2500)])
    print(f"  sum([...]) (0+Money)  -> {total}   (__radd__ ne 0 ko handle kiya)")

    # NotImplemented ka asli kamaal: unsupported type pe Python CLEAN TypeError deta hai
    try:
        _ = m1 + "abcd"
    except TypeError as e:
        print(f"  Money + str           -> TypeError (NotImplemented ke baad): {e}")
    print("  Takeaway: return NotImplemented, NEVER raise NotImplementedError yahan")


# === SECTION 3: method overriding via inheritance ===
class BaseConnector:
    """SAP HANA-style base — subclass override karega, super() se reuse karega."""

    def connect(self) -> str:
        return "base TCP socket open"

    def fetch(self) -> str:
        return f"[{self.connect()}] generic fetch"


class HanaConnector(BaseConnector):
    def connect(self) -> str:  # OVERRIDE: parent ka same naam method
        base = super().connect()  # parent logic reuse
        return f"{base} + HANA TLS handshake"

    def fetch(self) -> str:  # OVERRIDE with extra retry-flavoured behaviour
        return f"[{self.connect()}] HANA columnar fetch (idempotent)"


def section_3() -> None:
    print("=" * 64)
    print("SECTION 3: method overriding via inheritance")
    print("=" * 64)
    base, hana = BaseConnector(), HanaConnector()
    print(f"  BaseConnector.fetch() -> {base.fetch()}")
    print(f"  HanaConnector.fetch() -> {hana.fetch()}")
    print(f"  MRO                   -> {[c.__name__ for c in HanaConnector.__mro__]}")
    print("  Takeaway: override = runtime dispatch via MRO; super() se parent reuse")


# === SECTION 4: Python me method overloading NAHI ===
class Report:
    """Same naam ke do def -> dusra pehle ko OVERWRITE kar deta hai (overloading nahi)."""

    def generate(self, fmt: str) -> str:  # ye define hua...
        return f"single-arg generate({fmt})"

    def generate(self, fmt: str, rows: int) -> str:  # ...aur ISNE upar wale ko mita diya
        return f"two-arg generate({fmt}, {rows})"


def section_4() -> None:
    print("=" * 64)
    print("SECTION 4: Python me method overloading NAHI hota")
    print("=" * 64)
    r = Report()
    # Sirf doosra (2-arg) wala survive karta hai. 1-arg call crash karega:
    try:
        print(r.generate("pdf"))  # type: ignore[call-arg]
    except TypeError as e:
        print(f"  r.generate('pdf')      -> TypeError: {e}")
    print(f"  r.generate('pdf', 50)  -> {r.generate('pdf', 50)}")
    print("  Takeaway: Java/C++ wali overloading nahi — naam rebind hota hai, last def jeetta")


# === SECTION 5: 'overloading' ka asli tareeka (default args + singledispatch) ===
class Report2:
    def generate(self, fmt: str, rows: int | None = None) -> str:
        # default arg se 'do signatures' ka effect — clean aur Pythonic
        return f"generate({fmt})" if rows is None else f"generate({fmt}, {rows})"


@singledispatch
def serialize(value: object) -> str:
    # fallback branch — koi registered type match na ho to
    return f"<unserializable {type(value).__name__}>"


@serialize.register
def _(value: str) -> str:
    return f'"{value}"'


@serialize.register
def _(value: dict) -> str:
    inner = ", ".join(f"{k}={serialize(v)}" for k, v in value.items())
    return "{" + inner + "}"


@serialize.register
def _(value: Decimal) -> str:
    return f"{value:.2f}"


def section_5() -> None:
    print("=" * 64)
    print("SECTION 5: real 'overloading' — default args + functools.singledispatch")
    print("=" * 64)
    r = Report2()
    print(f"  default-arg 1 arg   -> {r.generate('csv')}")
    print(f"  default-arg 2 args  -> {r.generate('csv', 100)}")
    print(f"  singledispatch str  -> {serialize('hi')}")
    print(f"  singledispatch dict -> {serialize({'amt': Decimal('99.5'), 'cur': 'INR'})}")
    print(f"  singledispatch dflt -> {serialize(3.14)}")
    print("  Takeaway: type pe dispatch chahiye to singledispatch; warna default args")


# === SECTION 6: REAL BACKEND — IdempotencyKey + Money value objects ===
@dataclass(frozen=True)
class IdempotencyKey:
    """
    Payment gateway / SAP HANA retry: frozen=True dataclass automatically
    consistent __eq__ + __hash__ deta hai -> set/dict me safe key.
    Yahi production me 'duplicate request' detect karne ka core hai.
    """
    tenant_id: str
    request_id: str


def section_6() -> None:
    print("=" * 64)
    print("SECTION 6: REAL BACKEND — idempotency dedupe via __eq__/__hash__")
    print("=" * 64)
    seen: set[IdempotencyKey] = set()
    incoming = [
        IdempotencyKey("acme", "req-1"),
        IdempotencyKey("acme", "req-1"),   # retry — duplicate
        IdempotencyKey("globex", "req-1"),  # alag tenant -> alag key (tenant scoping)
    ]
    processed = []
    for key in incoming:
        if key in seen:  # __eq__ + __hash__ ki wajah se O(1) duplicate check
            print(f"  SKIP duplicate -> {key.request_id}/{key.tenant_id}")
            continue
        seen.add(key)
        processed.append(key)
        print(f"  PROCESS        -> {key.request_id}/{key.tenant_id}")
    print(f"  unique processed: {len(processed)} (retry safely deduped)")
    print("  Takeaway: frozen dataclass = free, correct __eq__+__hash__ for idempotency")


# === SECTION 7: BREAK IT / GOTCHA — __eq__ ne __hash__=None kar diya ===
class BrokenTenantId:
    """GALAT: __eq__ likha par __hash__ nahi -> Python __hash__ ko None set kar deta hai."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BrokenTenantId) and self.value == other.value
    # __hash__ define NAHI kiya -> ab ye class UNHASHABLE hai


class FixedTenantId:
    """SAHI: __eq__ ke saath consistent __hash__ bhi do (equal -> same hash)."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FixedTenantId) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)  # __eq__ ke saath consistent


def section_7() -> None:
    print("=" * 64)
    print("SECTION 7: BREAK IT — __eq__ defining silently sets __hash__ = None")
    print("=" * 64)
    print(f"  BrokenTenantId.__hash__ is None -> {BrokenTenantId.__hash__ is None}")

    # WRONG OUTPUT: set me daalte hi crash (multi-tenant cache key banate waqt yehi bug)
    try:
        _ = {BrokenTenantId("acme")}
    except TypeError as e:
        print(f"  set(BrokenTenantId)  -> WRONG: TypeError: {e}")

    # FIX + CORRECT OUTPUT
    bucket = {FixedTenantId("acme"), FixedTenantId("acme"), FixedTenantId("globex")}
    print(f"  set(FixedTenantId)   -> CORRECT: {len(bucket)} unique tenants")
    print("  Takeaway: agar object logically immutable hai to __eq__ ke saath __hash__ do")


# === SECTION 8: TODO (tum khud likho) ===
# NOTE: jab implement karo to class ke upar @total_ordering laga dena (functools se import
# already hai). Tab sirf __eq__ + __lt__ likho -> total_ordering baaki >, <=, >= bhar dega.
# Abhi stub me decorator nahi lagaya kyunki total_ordering bina kisi ordering op ke
# class-definition time pe hi ValueError fenkta hai (file chal hi nahi paati).
class SemVer:
    """
    TODO (tum khud implement karo): Semantic version value object.

    Expected behaviour jab complete karoge:
      - __init__(self, version)  -> "major.minor.patch" ko comparable tuple (M, m, p) me parse karo
      - __repr__  -> "SemVer(1.2.3)" jaisa
      - __eq__    -> tuple equality
      - __lt__    -> tuple comparison (1.2.3 < 1.10.0 == True)  [@total_ordering baaki bhar dega]
      - __hash__  -> hash(tuple)  (taaki set/dict me daal sako — section 7 ka sabak)
    Tip: SemVer("1.2.3") < SemVer("1.10.0") -> True hona chahiye (numeric compare, string nahi).

    Use-case: Celery/Redis pipeline me deployed version vs required version compare karna.
    """

    def __init__(self, version: str) -> None:
        raise NotImplementedError("TODO: parse 'major.minor.patch' into a comparable tuple")

    # @total_ordering laga ke (class ke upar) ye implement karo:
    # def __repr__(self) -> str: ...
    # def __eq__(self, other: object) -> bool: ...
    # def __lt__(self, other: object) -> bool: ...
    # def __hash__(self) -> int: ...


def section_8() -> None:
    print("=" * 64)
    print("SECTION 8: TODO — SemVer ko khud implement karo")
    print("=" * 64)
    try:
        _ = SemVer("1.2.3") < SemVer("1.10.0")
        print("  Implemented! 1.2.3 < 1.10.0 ->", _)
    except NotImplementedError as e:
        print(f"  Abhi pending -> {e}")
    print("  Goal: @total_ordering + __eq__ + __lt__ + __hash__ consistent banao")


# === MAIN DISPATCHER ===
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
    args = argv[1:]
    if not args:
        chosen = list(SECTIONS)  # no args -> run ALL
    else:
        try:
            chosen = [int(a) for a in args]
        except ValueError:
            print("Usage: python 01_operator_overloading_vs_overriding.py [section numbers]")
            print(f"Available sections: {list(SECTIONS)}")
            return
    for n in chosen:
        fn = SECTIONS.get(n)
        if fn is None:
            print(f"  [skip] section {n} nahi hai. Valid: {list(SECTIONS)}")
            continue
        fn()
        print()


if __name__ == "__main__":
    main(sys.argv)
