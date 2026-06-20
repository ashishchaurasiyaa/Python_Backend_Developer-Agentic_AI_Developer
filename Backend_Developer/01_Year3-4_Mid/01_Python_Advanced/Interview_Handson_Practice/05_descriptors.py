"""
================================================================================
TOPIC: Descriptors (the machinery behind property, methods, classmethod, ORM fields)
================================================================================

KYA HOTA HAI:
    Descriptor ek class hai jo __get__ / __set__ / __delete__ me se koi bhi
    implement karti hai. Jab ye descriptor kisi DOOSRI class ke CLASS-level
    attribute ke roop me rakhi jaati hai, to us attribute ko access/set/delete
    karne par Python in dunder methods ko call karta hai (instance ke __dict__
    me jaane ke bajaye). Matlab attribute access ko hijack karna.

KYO NEED PADI:
    property() har attribute ke liye getter/setter likhna padta hai — repetitive.
    Agar 10 fields sab "positive integer hone chahiye" wali validation chahti hai
    to property me 10 baar same code likhoge. Descriptor ek baar likho, reuse karo
    har field pe (DRY). ORMs (Django/SQLAlchemy), Pydantic-jaise validators,
    lazy/cached fields — sab descriptors pe khade hain.

KAISE USE KARTE HAIN:
    Ek class banao jisme __set_name__(self, owner, name) ho (taaki wo apna attribute
    naam yaad rakhe) + __get__ aur __set__. Phir use kisi bhi model class me
    class attribute ki tarah assign kar do:  age = Positive(). Bas. Validation/
    storage ab descriptor handle karega, har instance ke liye automatically.

KAHAN USE HOTA HAI (backend scenarios):
    1. Niroskos multi-tenant SaaS me model fields pe reusable validation
       (Positive, NonEmptyStr, TypedField) — bina har field ke liko boilerplate.
    2. SAP HANA connector me lazy connection: pehli baar access pe hi connect ho,
       baad me cache (lazy descriptor), retries ke saath.
    3. Payment amount field — negative/zero amount kabhi set na ho, descriptor
       data-descriptor hone ki wajah se instance __dict__ se override nahi ho sakti.
    4. Config objects: read-only / type-checked settings.
    5. Django ORM ke Field, Python ke property/staticmethod/classmethod — sab
       internally descriptors hi hain (samajhne se debugging aasaan).

INTERVIEW ANSWER (English — recite this):
    "A descriptor is any object that defines __get__, __set__, or __delete__ and
    is stored as a class attribute. When you access that attribute, Python routes
    the access through these methods instead of the instance dict. The crucial
    distinction is data vs non-data descriptors: if a descriptor defines __set__
    or __delete__ it is a data descriptor and it takes precedence over the
    instance __dict__, so it cannot be shadowed by an instance attribute. A
    non-data descriptor — only __get__ — is overridden by an entry in the instance
    dict, and that is exactly why plain functions (which are non-data descriptors)
    can be monkey-patched per instance. __set_name__ lets the descriptor learn the
    attribute name it was assigned to, so I can derive a private storage key
    automatically. property, classmethod, staticmethod and ORM fields are all
    built on this protocol. In production I use descriptors for reusable field
    validation and lazy/cached attributes, and the senior gotcha is to store
    per-instance state in instance.__dict__ keyed by the attribute name — never
    in the descriptor instance itself, because one descriptor object is shared
    across all instances of the class and would otherwise leak state between them."

================================================================================
Run:
    python 05_descriptors.py          # saare sections chalao
    python 05_descriptors.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — minimal descriptor: __get__/__set__/__set_name__ ka flow
    2. DEMO  — data vs non-data precedence (methods kyu shadow ho jaate hain)
    3. REAL  — reusable validation descriptors (Positive / Typed) on a model
    4. REAL  — property scratch se banao + SAP HANA lazy connection descriptor
    5. BREAK — shared-state bug: descriptor me state store karna (galti + fix)
    6. TODO  — tum khud likho: ReadOnly descriptor
================================================================================
"""
from __future__ import annotations

import sys
from typing import Any


# === SECTION 1: DEMO — minimal descriptor, __get__/__set__/__set_name__ flow ===
def section1() -> None:
    print("\n=== SECTION 1: minimal descriptor — get/set/set_name flow ===")

    class Logged:
        # __set_name__ owner class definition ke time call hota hai.
        # Yahi se descriptor ko apna attribute naam mil jaata hai.
        def __set_name__(self, owner: type, name: str) -> None:
            self.public_name = name
            self.private_name = f"_{name}"
            print(f"  [__set_name__] owner={owner.__name__} attr='{name}'")

        def __get__(self, obj: Any, objtype: type | None = None) -> Any:
            if obj is None:          # ClassName.attr -> descriptor khud return
                return self
            value = getattr(obj, self.private_name)
            print(f"  [__get__] {self.public_name} -> {value!r}")
            return value

        def __set__(self, obj: Any, value: Any) -> None:
            print(f"  [__set__] {self.public_name} = {value!r}")
            # IMPORTANT: state instance par store, descriptor par NAHI
            setattr(obj, self.private_name, value)

    class User:
        name = Logged()   # <- yahin __set_name__ trigger hota hai

    print("  -- instance banate hain --")
    u = User()
    u.name = "Ashish"     # __set__
    _ = u.name            # __get__
    # ClassName se access -> __get__ me obj=None -> descriptor object milta hai
    print(f"  User.name is the descriptor object? {isinstance(User.name, Logged)}")


# === SECTION 2: DEMO — data vs non-data precedence (why methods get shadowed) ===
def section2() -> None:
    print("\n=== SECTION 2: data vs non-data descriptor precedence ===")

    class NonData:                       # sirf __get__ -> NON-DATA descriptor
        def __get__(self, obj, objtype=None):
            return "from-descriptor (non-data)"

    class Data:                          # __get__ + __set__ -> DATA descriptor
        def __get__(self, obj, objtype=None):
            return obj.__dict__.get("_x", "from-descriptor (data)")
        def __set__(self, obj, value):
            obj.__dict__["_x"] = f"stored-by-data-descriptor({value})"

    class Thing:
        nd = NonData()
        d = Data()

    t = Thing()
    # Lookup order: type's data-descriptor > instance __dict__ > non-data descriptor
    print(f"  non-data, no instance entry : {t.nd}")
    t.__dict__["nd"] = "from-instance-dict"   # instance dict me ghuso
    print(f"  non-data, AFTER instance set: {t.nd}   <- instance jeet gaya (shadowed)")

    t.d = "hello"                              # __set__ chalega
    print(f"  data descriptor read        : {t.d}")
    t.__dict__["d"] = "try-to-shadow"          # instance dict me bhi daal do
    print(f"  data, even WITH dict entry  : {t.d}   <- descriptor jeeta (cannot shadow)")

    print("  Yahi reason hai: ek normal function NON-DATA descriptor hota hai,")
    print("  isliye obj.method = something se per-instance shadow/monkey-patch ho jaata hai.")
    # Practical proof: function is a non-data descriptor
    def fn(self): return "real method"
    class C:
        m = fn
    c = C()
    print(f"  c.m() before patch          : {c.m()}")
    c.m = lambda: "patched-on-instance"        # instance dict shadow (kyunki non-data)
    print(f"  c.m() after instance patch  : {c.m()}   <- shadow worked")


# === SECTION 3: REAL — reusable validation descriptors (Positive / Typed) ===
class Typed:
    """Value ka type enforce karta hai. DATA descriptor (set/get dono)."""
    def __init__(self, expected: type) -> None:
        self.expected = expected

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__[self.name]

    def __set__(self, obj, value) -> None:
        if not isinstance(value, self.expected):
            raise TypeError(
                f"{self.name!r} must be {self.expected.__name__}, got {type(value).__name__}"
            )
        obj.__dict__[self.name] = value


class Positive(Typed):
    """Typed + > 0 ka rule. Reuse via inheritance (DRY)."""
    def __init__(self) -> None:
        super().__init__(int)

    def __set__(self, obj, value) -> None:
        super().__set__(obj, value)              # pehle type check
        if value <= 0:
            raise ValueError(f"{self.name!r} must be positive, got {value}")
        obj.__dict__[self.name] = value


def section3() -> None:
    print("\n=== SECTION 3: reusable validation descriptors on a model ===")

    class Payment:
        # ek hi descriptor logic, multiple fields pe — Niroskos/payment domain
        amount = Positive()
        retries = Positive()
        currency = Typed(str)

        def __init__(self, amount: int, currency: str, retries: int) -> None:
            self.amount = amount
            self.currency = currency
            self.retries = retries

    p = Payment(amount=500, currency="INR", retries=3)
    print(f"  valid payment: amount={p.amount} {p.currency} retries={p.retries}")

    for bad in [
        ("amount", lambda: Payment(amount=-10, currency="INR", retries=3)),
        ("currency", lambda: Payment(amount=10, currency=999, retries=3)),  # type: ignore[arg-type]
        ("retries", lambda: Payment(amount=10, currency="INR", retries=0)),
    ]:
        field, builder = bad
        try:
            builder()
        except (TypeError, ValueError) as e:
            print(f"  blocked bad {field:9s}: {type(e).__name__}: {e}")


# === SECTION 4: REAL — property from scratch + SAP HANA lazy-connection descriptor ===
class my_property:
    """property ka apna chhota implementation — dikhata hai property bhi
    bas ek data descriptor hai (__get__ + __set__ + __delete__)."""
    def __init__(self, fget=None, fset=None) -> None:
        self.fget = fget
        self.fset = fset

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError(f"unreadable attribute {self.name!r}")
        return self.fget(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError(f"can't set attribute {self.name!r}")
        self.fset(obj, value)

    def setter(self, fset):                       # @x.setter chain support
        return type(self)(self.fget, fset)


class lazy_attr:
    """Lazy / cached attribute as a NON-DATA descriptor.
    Pehli access pe compute karta hai, phir result ko instance __dict__ me
    likh deta hai — wahi naam. Agli baar non-data hone ki wajah se instance
    __dict__ ki value jeet jaati hai => compute dobara nahi hota. (functools.cached_property
    bilkul aise hi kaam karta hai.)"""
    def __init__(self, func) -> None:
        self.func = func

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        value = self.func(obj)
        obj.__dict__[self.name] = value           # cache; next time dict wins
        return value


def section4() -> None:
    print("\n=== SECTION 4: scratch property + SAP HANA lazy connection ===")

    class Account:
        def __init__(self, balance: int) -> None:
            self._balance = balance

        @my_property
        def balance(self):                        # getter
            return self._balance

        @balance.setter
        def balance(self, value):                 # setter with validation
            if value < 0:
                raise ValueError("balance cannot be negative")
            self._balance = value

    a = Account(100)
    print(f"  my_property get: balance={a.balance}")
    a.balance = 250
    print(f"  my_property set: balance={a.balance}")
    try:
        a.balance = -5
    except ValueError as e:
        print(f"  my_property setter validation: ValueError: {e}")

    # SAP HANA style lazy connection — connect sirf pehli access pe (idempotent cache)
    connect_calls = {"n": 0}

    class HanaClient:
        @lazy_attr
        def connection(self):
            connect_calls["n"] += 1
            print(f"    [connect] establishing SAP HANA session (call #{connect_calls['n']})")
            return f"HANA-SESSION-{id(self) % 1000}"

    client = HanaClient()
    print("  first access (should connect):")
    c1 = client.connection
    print("  second access (should be cached, NO new connect):")
    c2 = client.connection
    print(f"  same session reused? {c1 == c2} | total connect() calls = {connect_calls['n']}")


# === SECTION 5: BREAK IT / GOTCHA — descriptor me state store karna (shared bug) ===
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — state on descriptor leaks across instances ===")

    # ---- GALAT version: value ko descriptor instance par store kiya ----
    class BadField:
        def __set_name__(self, owner, name):
            self.name = name
        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return self.value                      # BUG: ek hi 'self' sabke liye
        def __set__(self, obj, value):
            self.value = value                     # BUG: shared storage!

    class BadUser:
        name = BadField()

    a, b = BadUser(), BadUser()
    a.name = "Ashish"
    b.name = "Rahul"
    print("  WRONG output (descriptor stores state on itself):")
    print(f"    a.name = {a.name!r}   <- expected 'Ashish'")
    print(f"    b.name = {b.name!r}   <- expected 'Rahul'")
    print("    Dono same! Kyunki ek hi descriptor object class-level pe shared hai.")

    # ---- SAHI version: per-instance state instance.__dict__ me ----
    class GoodField:
        def __set_name__(self, owner, name):
            self.name = name
        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return obj.__dict__.get(self.name)     # FIX: instance ke dict me
        def __set__(self, obj, value):
            obj.__dict__[self.name] = value         # FIX: per-instance storage

    class GoodUser:
        name = GoodField()

    x, y = GoodUser(), GoodUser()
    x.name = "Ashish"
    y.name = "Rahul"
    print("  FIXED output (state keyed by attr name in instance __dict__):")
    print(f"    x.name = {x.name!r}")
    print(f"    y.name = {y.name!r}")
    print("  Lesson: descriptor object class pe ek hi hota hai — per-instance")
    print("          state hamesha obj.__dict__[self.name] me rakho.")


# === SECTION 6: TODO — tum khud likho: ReadOnly descriptor ===
class ReadOnly:
    """
    TODO (tum implement karo):
      Ek DATA descriptor banao jo:
        - __init__(self, value) me ek fixed value le aur store kare (descriptor ke
          shared-state ka issue yahan nahi — value sabke liye SAME read-only constant hai).
        - __get__ pe wahi value return kare.
        - __set__ pe hamesha AttributeError raise kare:
              f"{self.name!r} is read-only"
        - __set_name__ se attribute ka naam yaad rakhe (error message me use ho).
      Expected behaviour:
          class Cfg:
              VERSION = ReadOnly("1.2.0")
          Cfg().VERSION            -> "1.2.0"
          Cfg().VERSION = "9.9.9"  -> AttributeError: 'VERSION' is read-only
      Note: __set__ define karna ise DATA descriptor banata hai, isliye instance
      __dict__ se ise shadow karke override nahi kiya ja sakta — yahi read-only ki guarantee hai.
    """
    def __init__(self, value: Any) -> None:
        self.value = value

    def __set_name__(self, owner: type, name: str) -> None:
        raise NotImplementedError("TODO: attribute ka naam self.name me store karo")

    def __get__(self, obj, objtype=None):
        raise NotImplementedError("TODO: fixed value return karo (obj is None -> self)")

    def __set__(self, obj, value):
        raise NotImplementedError("TODO: AttributeError raise karo (read-only)")


def section6() -> None:
    print("\n=== SECTION 6: TODO — ReadOnly descriptor (tum likho) ===")

    try:
        # NOTE: __set_name__ class-definition ke time chalta hai, isliye agar wo
        # raise kare to Python use RuntimeError me wrap kar deta hai. Tab tak ye
        # try-block run ko crash hone se bachata hai (taaki run clean rahe).
        class Cfg:
            VERSION = ReadOnly("1.2.0")

        c = Cfg()
        print(f"  Cfg().VERSION = {c.VERSION!r}")
        c.VERSION = "9.9.9"
        print("  ERROR: read-only hona chahiye tha, set ho gaya!")
    except (NotImplementedError, RuntimeError) as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")
    except AttributeError as e:
        print(f"  correct! read-only enforced: AttributeError: {e}")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
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
