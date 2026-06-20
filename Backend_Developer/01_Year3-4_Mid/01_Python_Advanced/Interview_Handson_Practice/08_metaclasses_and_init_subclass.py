"""
================================================================================
TOPIC: Metaclasses & __init_subclass__ (class banane ki machinery customize karna)
================================================================================

KYA HOTA HAI:
    Jaise ek normal object kisi class ka instance hota hai, waise hi ek CLASS
    khud ek metaclass ka instance hoti hai. Default metaclass `type` hai. Jab
    Python `class Foo: ...` padhta hai, internally wo `type(name, bases, ns)`
    call karke class OBJECT banata hai. Metaclass = "class banane wali class".
    __init_subclass__ ek lighter hook hai jo har subclass banne par chalta hai
    bina poora metaclass likhe.

KYO NEED PADI:
    Kabhi kabhi chahte hain ki jaise hi koi class DEFINE ho (instance nahi,
    class khud), tabhi kuch ho jaye — e.g. usko ek registry me auto-register
    karna (plugin system), ya enforce karna ki subclass ne kuch fields define
    kiye. Decorator har subclass par dobara lagana padta hai (bhool sakte ho);
    metaclass/__init_subclass__ INHERITED hota hai — ek baar base me likha, sab
    subclasses par automatic.

KAISE USE KARTE HAIN:
    Modern + simple: base class me `def __init_subclass__(cls, **kw)` likho —
    har subclass definition par chalega. Field naam yaad rakhne ke liye
    `__set_name__` (descriptor protocol) use karo. Heavy customization (class
    body kaise bani, namespace badalna) ke liye `class Meta(type)` banao aur
    `__new__`/`__init__` override karke `metaclass=Meta` set karo.

KAHAN USE HOTA HAI (backend scenarios):
    1. Plugin registry — Niroskos SaaS me payment gateways / notification channels:
       har gateway subclass khud-ba-khud ek REGISTRY dict me register ho jaye,
       taaki naam se lookup ho ("razorpay" -> RazorpayGateway).
    2. SAP HANA connector — base class me enforce karo ki har connector subclass
       `endpoint` aur `timeout` define kare warna class definition hi fail (fail
       fast, deploy ke time, runtime pe nahi).
    3. Django Model / SQLAlchemy declarative base — ModelBase ek metaclass hai jo
       fields collect karke _meta banata hai. Samajhne se ORM internals clear.
    4. ABCMeta, Enum — dono metaclasses pe khade hain.
    5. __set_name__ se ORM-style fields apna column naam khud derive karte hain.

INTERVIEW ANSWER (English — recite this):
    "A class in Python is itself an object, and its type is its metaclass —
    `type` by default. Writing `class C(Base): ...` is essentially a call to
    `type(name, bases, namespace)`, so a metaclass is just a class whose
    instances are classes; you hook class creation by subclassing `type` and
    overriding `__new__` or `__init__`. The classic use is a self-populating
    plugin registry: the base's metaclass runs once per subclass and registers
    it, so adding a plugin is just defining a class. However, since Python 3.6 I
    reach for `__init_subclass__` first — it's an ordinary classmethod on the
    base that fires for every subclass and covers most registration and
    validation needs without the conceptual weight of a metaclass, plus it
    composes cleanly because it's a normal method in the MRO. I pair it with
    `__set_name__`, which lets a descriptor learn the attribute name it was bound
    to. The senior nuance is that you genuinely NEED a metaclass only when you
    must control the class object itself before it exists — changing the
    namespace, the bases, `__prepare__`, or how the class is constructed — and
    that metaclasses don't compose: combining two classes with different
    metaclasses raises a 'metaclass conflict'. So the rule is: __init_subclass__
    and decorators for behaviour-on-subclassing, metaclass only as the last resort."

================================================================================
Run:
    python 08_metaclasses_and_init_subclass.py        # saare sections chalao
    python 08_metaclasses_and_init_subclass.py 2 4    # sirf section 2 aur 4

Sections:
    1. DEMO  — type(name, bases, ns) se class banao bina `class` keyword ke
    2. DEMO  — custom metaclass __new__: plugin registry (auto-register)
    3. REAL  — __init_subclass__: modern alternative (gateway registry + validation)
    4. REAL  — __set_name__: ORM-style field apna column naam khud seekhe
    5. BREAK — metaclass conflict: do alag metaclasses mix karoge to crash
    6. TODO  — tum khud likho: __init_subclass__ se required-attrs enforce karo
================================================================================
"""
from __future__ import annotations

import sys
from typing import Any


# === SECTION 1: DEMO — type(name, bases, ns) as a class factory ===
def section1() -> None:
    print("\n=== SECTION 1: type(name, bases, ns) — class is just an object ===")

    # `class` keyword sirf syntactic sugar hai. Ye dono BILKUL same class banate hain.
    def greet(self) -> str:
        return f"hi, I am {self.name}"

    # type(name, bases, namespace) -> ek nayi class OBJECT return karta hai
    Dynamic = type(
        "Dynamic",                       # class ka naam
        (object,),                       # bases (tuple)
        {"species": "human", "greet": greet},  # namespace (class body == ye dict)
    )

    d = Dynamic()
    d.name = "Ashish"
    print(f"  type(...) se bani class : {Dynamic!r}")
    print(f"  instance call            : {d.greet()}  | species={d.species}")

    # Proof: har class khud `type` ki instance hai (uska metaclass `type` hai)
    class Normal:
        pass
    print(f"  type(Normal)             : {type(Normal).__name__}  (yahi uska metaclass hai)")
    print(f"  type(Dynamic)            : {type(Dynamic).__name__}")
    print(f"  Normal is instance of type? {isinstance(Normal, type)}")
    print("  Lesson: 'class Foo:' == type('Foo', bases, body_dict) ka call.")


# === SECTION 2: DEMO — custom metaclass __new__ (plugin registry) ===
class _PluginMeta(type):
    """Metaclass: har is-metaclass-wali class banne par __new__ chalta hai.
    Hum yahan har concrete plugin ko REGISTRY me daal dete hain."""
    registry: dict[str, type] = {}

    def __new__(mcls, name: str, bases: tuple, ns: dict, **kw: Any) -> type:
        # pehle asli class object banao (type ko delegate karo)
        cls = super().__new__(mcls, name, bases, ns)
        # base 'Plugin' khud register na ho — sirf uske subclasses.
        # Trick: jab `class Plugin(metaclass=...)` likhte hain (koi explicit base
        # nahi), to Python `bases` me EMPTY tuple () bhejta hai -> falsy.
        # Subclasses ke liye bases = (Plugin,) hoga -> truthy. Isliye `if bases:`
        # base ko cleanly skip kar deta hai.
        if bases:
            key = ns.get("key", name.lower())
            _PluginMeta.registry[key] = cls
            print(f"  [metaclass __new__] registered plugin {key!r} -> {name}")
        return cls


def section2() -> None:
    print("\n=== SECTION 2: custom metaclass __new__ — plugin registry ===")
    _PluginMeta.registry.clear()

    class Plugin(metaclass=_PluginMeta):
        """base class — ye REGISTER nahi hoga kyunki iska `bases` empty () hai
        (koi explicit base nahi diya). Sirf neeche wale concrete plugins register
        honge."""

    class RazorpayGateway(Plugin):
        key = "razorpay"

    class StripeGateway(Plugin):
        key = "stripe"

    print(f"  registry keys: {sorted(_PluginMeta.registry)}")
    # naam se lookup -> factory pattern, bina if/elif chain ke
    chosen = _PluginMeta.registry["stripe"]
    print(f"  lookup 'stripe' -> {chosen.__name__}")
    print("  Faayda: naya gateway add karna = bas ek subclass define karna.")
    print("          Koi central if/elif ya manual register() call ki zaroorat nahi.")


# === SECTION 3: REAL — __init_subclass__ (the simpler modern alternative) ===
GATEWAY_REGISTRY: dict[str, type] = {}


class PaymentGateway:
    """Base. __init_subclass__ ek normal classmethod hai jo HAR subclass
    define hone par chalti hai — metaclass likhe bina same registry + validation.
    Ye Niroskos jaise SaaS me gateways plug karne ka clean tareeka hai."""

    # subclass `class X(PaymentGateway, key="razorpay")` ke kwargs yahan aate hain
    def __init_subclass__(cls, *, key: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)        # cooperative — MRO me aage bhejo
        resolved = key or cls.__name__.lower()
        # validation: subclass ne charge() override kiya ya nahi (fail fast)
        if "charge" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must implement charge()")
        GATEWAY_REGISTRY[resolved] = cls
        print(f"  [__init_subclass__] registered {resolved!r} -> {cls.__name__}")

    def charge(self, amount: int) -> str:
        raise NotImplementedError


def section3() -> None:
    print("\n=== SECTION 3: __init_subclass__ — modern registry + validation ===")
    GATEWAY_REGISTRY.clear()

    class Razorpay(PaymentGateway, key="razorpay"):
        def charge(self, amount: int) -> str:
            return f"razorpay charged ₹{amount} (idempotent)"

    class Paytm(PaymentGateway, key="paytm"):
        def charge(self, amount: int) -> str:
            return f"paytm charged ₹{amount}"

    print(f"  registry keys: {sorted(GATEWAY_REGISTRY)}")
    gw = GATEWAY_REGISTRY["razorpay"]()
    print(f"  resolve+charge: {gw.charge(500)}")

    # validation demo — charge() bhoolne par class DEFINITION hi fail ho jayegi
    print("  ab ek galat subclass (no charge()) define karte hain:")
    try:
        class BrokenGateway(PaymentGateway, key="broken"):
            pass  # charge() implement nahi kiya
    except TypeError as e:
        print(f"  blocked at class-definition time: TypeError: {e}")
    print("  Faayda: error DEPLOY/import time pe milega, na ki production runtime pe.")
    print("  Aur metaclass ke comparison me: ye sirf ek classmethod hai — simple.")


# === SECTION 4: REAL — __set_name__ (descriptor learns its own column name) ===
class Column:
    """ORM-style field. __set_name__ class-definition ke time chalta hai aur
    descriptor ko bata deta hai ki use kis attribute naam par bind kiya gaya —
    isi se wo apna DB column naam derive kar leta hai (Django/SQLAlchemy aise hi)."""

    def __init__(self, col_type: str) -> None:
        self.col_type = col_type
        self.name = "<unbound>"

    def __set_name__(self, owner: type, name: str) -> None:
        # owner = wo class, name = attribute ka naam jise assign hua
        self.name = name
        print(f"  [__set_name__] bound field -> column {name!r} ({self.col_type})")

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return obj.__dict__.get(self.name)

    def __set__(self, obj: Any, value: Any) -> None:
        obj.__dict__[self.name] = value


def section4() -> None:
    print("\n=== SECTION 4: __set_name__ — field apna column naam khud seekhe ===")

    class TenantModel:
        # dhyan do: kahin bhi "id"/"name" string repeat nahi kiya —
        # __set_name__ ne attribute naam khud pakad liya (DRY).
        id = Column("INTEGER")
        tenant_name = Column("VARCHAR")

    print(f"  derived column names: id={TenantModel.id.name!r}, "
          f"tenant_name={TenantModel.tenant_name.name!r}")
    row = TenantModel()
    row.id = 42
    row.tenant_name = "acme-corp"
    print(f"  stored row: id={row.id}, tenant_name={row.tenant_name!r}")
    print("  Lesson: __set_name__ ke bina har field ko apna naam manually dena padta:")
    print("          id = Column('INTEGER', name='id')  <- repetitive + error-prone.")


# === SECTION 5: BREAK IT / GOTCHA — metaclass conflict ===
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — metaclass conflict (kyu metaclass last resort) ===")

    class MetaA(type):
        pass

    class MetaB(type):
        pass

    class A(metaclass=MetaA):
        pass

    class B(metaclass=MetaB):
        pass

    # ---- GALAT: do classes jinke metaclasses unrelated hain, ko mix karna ----
    print("  Trying: class C(A, B)  -- A ka metaclass MetaA, B ka MetaB ...")
    try:
        # type() se runtime pe banao taaki Python crash na ho, exception pakad sakein
        type("C", (A, B), {})
    except TypeError as e:
        print(f"  WRONG (crash): TypeError: {e}")
        print("  Reason: derived class ka metaclass saare base-metaclasses ka subclass")
        print("          hona chahiye. MetaA aur MetaB me koi relation nahi -> conflict.")

    # ---- SAHI: ek combined metaclass banao jo MetaA aur MetaB DONO se inherit kare ----
    # Ab derived metaclass MetaAB dono base-metaclasses ka subclass hai -> conflict gaya.
    class MetaAB(MetaA, MetaB):
        pass

    Fixed = MetaAB("Fixed", (A, B), {})
    print(f"  FIX: combined metaclass MetaAB(MetaA, MetaB) -> {Fixed.__name__} bana, "
          f"metaclass={type(Fixed).__name__}")
    print("  Asli lesson: metaclasses COMPOSE nahi karte. Isliye library code me")
    print("  metaclass dena risky hai — user ki dusri metaclass se clash kar sakta.")
    print("  Jahan ho sake __init_subclass__ / decorator use karo (wo MRO me compose hote).")


# === SECTION 6: TODO — tum khud likho: __init_subclass__ se required attrs enforce ===
class StrictConnector:
    """
    TODO (tum implement karo):
      __init_subclass__ likho jo enforce kare ki HAR subclass ne ye class-attrs
      define kiye hon:  'endpoint' (str) aur 'timeout' (int/float).
      Agar koi missing ho ya galat type ka ho to class-definition par hi
      TypeError raise karo, message:
          f"{cls.__name__} must define '{attr}' as {expected_type}"

      Expected behaviour:
          class GoodConn(StrictConnector):
              endpoint = "https://hana.internal/api"
              timeout  = 30
          # -> theek se ban jaye, koi error nahi

          class BadConn(StrictConnector):
              endpoint = "..."        # timeout missing
          # -> TypeError: BadConn must define 'timeout' as ...

      Hint:
        - super().__init_subclass__(**kwargs) zaroor call karna (cooperative).
        - cls par getattr(cls, 'endpoint', None) se value lo.
        - SAP HANA connector me yahi pattern config-completeness deploy time pe
          guarantee karta hai (runtime crash se bachata hai).
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        raise NotImplementedError(
            "TODO: endpoint(str) aur timeout(int/float) ki presence + type check karo"
        )


def section6() -> None:
    print("\n=== SECTION 6: TODO — __init_subclass__ required-attrs enforce (tum likho) ===")
    try:
        class GoodConn(StrictConnector):
            endpoint = "https://hana.internal/api"
            timeout = 30

        print(f"  GoodConn defined OK: endpoint={GoodConn.endpoint!r}, "
              f"timeout={GoodConn.timeout}")

        try:
            class BadConn(StrictConnector):
                endpoint = "https://x"  # timeout missing -> hona chahiye TypeError
            print("  ERROR: BadConn ko fail hona chahiye tha (timeout missing).")
        except TypeError as e:
            print(f"  correct! missing attr blocked: TypeError: {e}")

    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")


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
