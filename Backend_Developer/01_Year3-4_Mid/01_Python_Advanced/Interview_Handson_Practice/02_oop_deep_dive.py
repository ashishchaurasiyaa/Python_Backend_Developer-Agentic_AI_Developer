"""
================================================================================
TOPIC: OOP in Detail (Encapsulation, @property, classmethod/staticmethod,
       Polymorphism / Duck Typing, Composition vs Inheritance)
================================================================================

KYA HOTA HAI:
    OOP matlab data + behaviour ko ek object me bundle karna. Python me iske
    4 pillars practical level pe matter karte hain: encapsulation (state ko
    chhupa ke validate karna), inheritance (reuse via "is-a"), polymorphism
    (same interface, alag behaviour), aur abstraction. Plus Python-specific
    cheezein: name mangling (_/__), @property, classmethod vs staticmethod.

KYO NEED PADI:
    Bina encapsulation ke koi bhi caller object ka internal state direct set
    kar ke usko invalid bana deta hai (e.g. amount = -100). Bina property ke
    validation getter/setter API bante hain jo Pythonic nahi lagte. Deep
    inheritance tree maintain karna nightmare ho jata hai (fragile base class).
    Yeh sab control aur safe extension ke liye chahiye.

KAISE USE KARTE HAIN:
    _name = "private by convention" (linter/docs hint). __name = name mangling
    (subclass collision se bachne ke liye -> _ClassName__name banta hai, fully
    private nahi). @property se attribute jaisa dikhne wala validated getter,
    @x.setter se controlled write. @classmethod alternate constructors ke liye
    (cls.from_xyz). @staticmethod namespaced pure helper. Duck typing: type
    check mat karo, behaviour pe bharosa karo.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector me Money/Amount object jisme negative amount invalid
       ho (property validation) + idempotency key encapsulated ho.
    2. Niroskos multi-tenant SaaS me Tenant object jiska tenant_id read-only
       ho (property, no setter) taaki koi accidentally cross-tenant na kare.
    3. Payment gateway abstraction: Razorpay/Stripe/Paytm sab ek charge()
       interface implement karein -> polymorphism / duck typing.
    4. Celery task config: from_dict() / from_env() alternate constructors
       (classmethod) for retry/backoff settings.
    5. Odoo migration me record adapters jaha composition (has-a logger,
       has-a connection) inheritance se zyada flexible padta hai.

INTERVIEW ANSWER (English):
    Python has no true private members; it leans on convention. A single
    underscore signals "internal, don't touch", while a double underscore
    triggers name mangling, which rewrites the attribute to _ClassName__attr
    to avoid accidental collisions in subclasses, not to enforce privacy.
    For validated access I expose attributes through @property, which keeps a
    clean attribute-style API while running checks in the setter, so a domain
    object like Money can never hold a negative value. I use @classmethod for
    alternate constructors such as from_dict or from_env where I need access to
    cls so subclasses construct correctly, and @staticmethod for stateless
    helpers that just live in the class namespace. Python's polymorphism is
    primarily duck typing: I depend on behaviour, not on isinstance checks,
    which is why payment providers can share a charge() interface without a
    common base class. The senior nuance is composition over inheritance: deep
    inheritance creates fragile base classes where a parent change silently
    breaks children, so I prefer "has-a" composition and reserve inheritance
    for genuine "is-a" relationships and stable, shallow hierarchies.

Run:
    python 02_oop_deep_dive.py          # saare sections
    python 02_oop_deep_dive.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO: Encapsulation + name mangling (_ vs __)
    2. DEMO: @property getter/setter/validation (Money object)
    3. DEMO: classmethod (alt constructors) vs staticmethod
    4. DEMO: Polymorphism / duck typing (payment providers)
    5. REAL BACKEND: composition vs inheritance (SAP HANA connector)
    6. BREAK IT / GOTCHA: mutable default + name-mangling surprise
    7. TODO: tum khud likho (Tenant read-only id + RateLimiter via composition)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field


# === SECTION 1: Encapsulation + name mangling (_ vs __) ===
class BankAccount:
    """_balance = internal convention; __pin = name-mangled."""

    def __init__(self, balance: int, pin: str) -> None:
        self._balance = balance      # "protected" by convention
        self.__pin = pin             # mangled -> _BankAccount__pin

    def check_pin(self, pin: str) -> bool:
        return self.__pin == pin     # inside class, __pin works normally


def section_1() -> None:
    print("=" * 60)
    print("SECTION 1: Encapsulation + name mangling")
    print("=" * 60)
    acc = BankAccount(1000, "4321")

    # _balance: bilkul accessible hai, sirf "mat chhuo" ka signal hai
    print(f"_balance (convention only)   : {acc._balance}  <- accessible!")

    # __pin: direct access fail, kyunki naam mangle ho gaya
    try:
        print(acc.__pin)  # type: ignore[attr-defined]
    except AttributeError as e:
        print(f"acc.__pin direct access      : AttributeError -> {e}")

    # Naam actually yahan hai (privacy nahi, sirf collision-avoidance)
    print(f"mangled name _BankAccount__pin: {acc._BankAccount__pin}")
    print(f"check_pin('4321')            : {acc.check_pin('4321')}")
    print("Takeaway: __ = mangling (collision-safe), NOT real privacy.")


# === SECTION 2: @property getter/setter/validation (Money object) ===
class Money:
    """Domain object jaha negative amount kabhi exist nahi karna chahiye."""

    def __init__(self, amount: float, currency: str = "INR") -> None:
        self._amount = 0.0
        self.amount = amount         # setter chalega -> validation
        self._currency = currency

    @property
    def amount(self) -> float:
        return self._amount

    @amount.setter
    def amount(self, value: float) -> None:
        if value < 0:
            raise ValueError(f"amount cannot be negative: {value}")
        self._amount = round(float(value), 2)

    @property
    def currency(self) -> str:       # getter only -> read-only attribute
        return self._currency

    def __repr__(self) -> str:
        return f"Money({self._amount} {self._currency})"


def section_2() -> None:
    print("=" * 60)
    print("SECTION 2: @property getter/setter/validation")
    print("=" * 60)
    m = Money(100.555)
    print(f"created            : {m}  (rounded in setter)")

    m.amount = 250          # attribute-style write, but validated
    print(f"after m.amount=250 : {m}")

    try:
        m.amount = -5       # invalid -> setter raises
    except ValueError as e:
        print(f"m.amount = -5      : ValueError -> {e}")

    try:
        m.currency = "USD"  # no setter -> read-only
    except AttributeError as e:
        print(f"m.currency = 'USD' : AttributeError -> {e}")
    print("Takeaway: clean attr API + validation; read-only via getter-only.")


# === SECTION 3: classmethod (alt constructors) vs staticmethod ===
class RetryConfig:
    """Celery/SAP retry settings — multiple ways to build, one helper."""

    def __init__(self, max_retries: int, backoff: float) -> None:
        self.max_retries = max_retries
        self.backoff = backoff

    @classmethod
    def from_dict(cls, cfg: dict) -> "RetryConfig":
        # cls use karte hain taaki subclass bhi sahi type return kare
        return cls(cfg["max_retries"], cfg["backoff"])

    @classmethod
    def aggressive(cls) -> "RetryConfig":
        return cls(max_retries=10, backoff=0.1)

    @staticmethod
    def delay_for(attempt: int, backoff: float) -> float:
        # pure function, koi self/cls nahi chahiye -> staticmethod
        return round(backoff * (2 ** attempt), 3)

    def __repr__(self) -> str:
        return f"RetryConfig(max={self.max_retries}, backoff={self.backoff})"


class TenantRetryConfig(RetryConfig):
    """Subclass — cls-based constructor ka fayda yahan dikhta hai."""


def section_3() -> None:
    print("=" * 60)
    print("SECTION 3: classmethod (alt constructors) vs staticmethod")
    print("=" * 60)
    c1 = RetryConfig.from_dict({"max_retries": 3, "backoff": 0.5})
    c2 = RetryConfig.aggressive()
    print(f"from_dict   : {c1}")
    print(f"aggressive  : {c2}")

    # classmethod cls use karta hai -> subclass sahi type deta hai
    sub = TenantRetryConfig.aggressive()
    print(f"subclass via classmethod : {type(sub).__name__} (sahi subtype!)")

    # staticmethod -> stateless helper, instance ki zarurat nahi
    print(f"delay_for(attempt=3, 0.5): {RetryConfig.delay_for(3, 0.5)}s")
    print("Takeaway: classmethod=alt ctor (needs cls); staticmethod=pure util.")


# === SECTION 4: Polymorphism / duck typing (payment providers) ===
class RazorpayProvider:
    def charge(self, amount: int) -> str:
        return f"Razorpay charged Rs.{amount}"


class StripeProvider:
    def charge(self, amount: int) -> str:
        return f"Stripe charged Rs.{amount}"


class BrokenProvider:
    def bill(self, amount: int) -> str:    # galat method naam (charge nahi)
        return f"Broken billed Rs.{amount}"


def run_payment(provider, amount: int) -> str:
    # Duck typing: hum type check NAHI karte; bas charge() pe bharosa
    return provider.charge(amount)


def section_4() -> None:
    print("=" * 60)
    print("SECTION 4: Polymorphism / duck typing")
    print("=" * 60)
    # Koi common base class nahi, fir bhi same interface -> duck typing
    for p in (RazorpayProvider(), StripeProvider()):
        print(f"{type(p).__name__:18s}: {run_payment(p, 500)}")

    # Jo duck nahi quack karta, runtime pe fail (LBYL vs EAFP ka point)
    try:
        run_payment(BrokenProvider(), 500)
    except AttributeError as e:
        print(f"BrokenProvider     : AttributeError -> {e}")
    print("Takeaway: 'if it has charge(), it's a provider' — no inheritance.")


# === SECTION 5: REAL BACKEND — composition vs inheritance (SAP HANA) ===
class _AuditLogger:
    """Reusable behaviour — har connector ko isse INHERIT nahi karna."""

    def __init__(self) -> None:
        self.records: list[str] = []

    def log(self, msg: str) -> None:
        self.records.append(msg)


class _IdempotencyStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def already_done(self, key: str) -> bool:
        if key in self._seen:
            return True
        self._seen.add(key)
        return False


class SapHanaConnector:
    """
    COMPOSITION: connector HAS-A logger aur HAS-A idempotency store.
    Inheritance hota to ye "Connector IS-A Logger" ban jata — galat rishta.
    """

    def __init__(self) -> None:
        self._log = _AuditLogger()           # has-a
        self._idem = _IdempotencyStore()     # has-a

    def push(self, idempotency_key: str, payload: str) -> str:
        if self._idem.already_done(idempotency_key):
            self._log.log(f"SKIP duplicate {idempotency_key}")
            return "skipped (idempotent)"
        self._log.log(f"PUSH {idempotency_key} -> {payload}")
        return "pushed"

    @property
    def audit_trail(self) -> list[str]:
        return list(self._log.records)       # defensive copy, read-only view


def section_5() -> None:
    print("=" * 60)
    print("SECTION 5: REAL BACKEND — composition vs inheritance")
    print("=" * 60)
    conn = SapHanaConnector()
    print(f"first push  : {conn.push('key-1', 'invoice-99')}")
    print(f"retry push  : {conn.push('key-1', 'invoice-99')}  <- idempotent")
    print(f"new push    : {conn.push('key-2', 'invoice-100')}")
    print("audit trail :")
    for line in conn.audit_trail:
        print(f"   - {line}")
    print("Why composition: swap logger/store independently; no fragile base.")


# === SECTION 6: BREAK IT / GOTCHA — mutable default + name mangling ===
def section_6() -> None:
    print("=" * 60)
    print("SECTION 6: BREAK IT / GOTCHA")
    print("=" * 60)

    # ---- GOTCHA A: shared mutable default in __init__ ----
    class BadCart:
        def __init__(self, items: list = []):   # BUG: shared across instances!
            self.items = items

    c1, c2 = BadCart(), BadCart()
    c1.items.append("sap-invoice")
    print("[WRONG] mutable default arg shared across instances:")
    print(f"   c1.items = {c1.items}")
    print(f"   c2.items = {c2.items}  <- leaked! (same list object)")

    class GoodCart:
        def __init__(self, items: list | None = None):
            self.items = items if items is not None else []

    g1, g2 = GoodCart(), GoodCart()
    g1.items.append("sap-invoice")
    print("[FIXED] None sentinel -> fresh list per instance:")
    print(f"   g1.items = {g1.items}")
    print(f"   g2.items = {g2.items}  <- isolated, correct")

    # ---- GOTCHA B: __ name mangling breaks subclass override ----
    class Base:
        def __init__(self) -> None:
            self.__helper()             # mangles to _Base__helper

        def __helper(self) -> None:
            print("   Base.__helper ran (subclass override IGNORED)")

    class Child(Base):
        def __helper(self) -> None:     # mangles to _Child__helper, NOT override
            print("   Child.__helper ran")

    print("[WRONG] expected Child.__helper, but mangling calls Base's:")
    Child()
    print("[FIX] use single _helper (no mangling) if you want overridable hook.")
    print("Takeaway: '[]' default + '__' methods are classic interview traps.")


# === SECTION 7: TODO (tum khud likho) ===
@dataclass
class Tenant:
    """
    TODO-1: Niroskos multi-tenant — tenant_id READ-ONLY hona chahiye.
    Expected behaviour:
      - constructor me tenant_id set ho
      - `t.tenant_id` getter kaam kare
      - `t.tenant_id = "x"` pe AttributeError aaye (no setter)
    Hint: store as self._tenant_id, expose via @property (getter only).
    """
    pass  # tum yahan implement karo


def build_rate_limiter():
    """
    TODO-2: RateLimiter ko COMPOSITION se banao (inheritance se nahi).
    Expected behaviour:
      - allow(key) -> True agar is window me limit cross nahi hui
      - limit cross hone par False
      - internally ek dict/counter HOLD karo (has-a), dict ko SUBCLASS mat karo
    Returns: ek object jiska .allow(key)->bool ho.
    """
    raise NotImplementedError("build_rate_limiter: tum khud likho")


def section_7() -> None:
    print("=" * 60)
    print("SECTION 7: TODO (tum khud likho)")
    print("=" * 60)
    print("TODO-1 Tenant: read-only tenant_id via getter-only @property")
    print("TODO-2 RateLimiter: composition (has-a counter), not dict subclass")
    print("Implement upar ke do functions, fir yahan test print add karo.")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section_1,
        "2": section_2,
        "3": section_3,
        "4": section_4,
        "5": section_5,
        "6": section_6,
        "7": section_7,
    }
    args = sys.argv[1:]
    chosen = args if args else list(sections.keys())
    for key in chosen:
        fn = sections.get(key)
        if fn is None:
            print(f"[skip] unknown section: {key}")
            continue
        fn()
        print()


if __name__ == "__main__":
    main()
