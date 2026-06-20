"""
================================================================================
TOPIC: MRO, super() & Mixins
================================================================================

KYA HOTA HAI:
    MRO (Method Resolution Order) = wo fixed order jisme Python multiple
    inheritance me method/attribute dhundta hai. Python C3 linearization
    algorithm use karta hai is order ko banane ke liye. `super()` us MRO ke
    "agle" class ko call karta hai — strictly parent ko nahi. Har class ka
    `__mro__` tuple pre-computed hota hai class creation time pe.

KYO NEED PADI:
    Multiple inheritance me agar do base classes ka common ancestor hai
    (diamond problem), to naive approach me base ka __init__ ya method 2 baar
    chal jata hai. C3 + cooperative super() guarantee deta hai ki har class
    exactly EK baar chale, ek deterministic order me. Iske bina mixins,
    Django CBVs, DRF ke saare layered behaviours toot jaate.

KAISE USE KARTE HAIN:
    Har class ka __init__/method `super().__init__(**kwargs)` cooperatively
    call karta hai aur bache hue kwargs aage forward karta hai. Mixins ko
    inheritance list me LEFT side rakhte hain (override priority), concrete
    base ko RIGHT side. `ClassName.__mro__` ya `.mro()` se order verify karo.

KAHAN USE HOTA HAI (scenarios):
    1. Django/DRF Class-Based Views: LoginRequiredMixin + PermissionMixin +
       generic View — sab cooperative dispatch chain me chalte hain.
    2. Niroskos multi-tenant SaaS: TenantScopedMixin jo har queryset ko
       tenant_id se filter karta hai, kisi bhi model-service pe mix kar do.
    3. SAP HANA connector: RetryMixin + TimingMixin ko ek SAPClient pe lagana
       bina core call logic ko chhede.
    4. JsonMixin / TimestampMixin: DTOs ko serialization + created_at/updated_at
       audit behaviour dena without duplicating code across 50 models.
    5. Logging/metrics mixins jo har payment-gateway call ko wrap karte hain.

INTERVIEW ANSWER (English):
    The Method Resolution Order is the deterministic sequence Python uses to
    look up attributes and methods across a class hierarchy. Python builds it
    using the C3 linearization algorithm, which guarantees three properties:
    a class always precedes its parents, the left-to-right order of bases is
    preserved, and every class appears exactly once. The crucial nuance is
    that super() does NOT mean "call my parent" — it means "call the next
    class in the MRO of the actual instance", which may be a sibling, not an
    ancestor. This is why super() correctly resolves the diamond problem: the
    shared base runs only once even though two children both call super().
    For this to work, every cooperative method must accept and forward
    **kwargs and call super(). I lean on this with mixins — small, focused
    classes like a JsonMixin or a TenantScopedMixin placed to the left of the
    concrete base, so behaviour composes predictably. The common production
    bug is hardcoding BaseClass.__init__(self) instead of super().__init__(),
    which breaks cooperative chaining the moment a mixin is inserted.

Run:
    python 03_mro_super_mixins.py            # saare sections chalao
    python 03_mro_super_mixins.py 1 3        # sirf section 1 aur 3

Sections:
    1. DEMO: __mro__ aur C3 linearization (order kaise banta hai)
    2. DEMO: super() is NOT just "parent" (sibling ko call karta hai)
    3. DEMO: Diamond problem — cooperative super() + **kwargs (base once only)
    4. REAL BACKEND: JsonMixin + TimestampMixin + TenantScopedMixin compose
    5. BREAK IT / GOTCHA: hardcoded Base.__init__ vs cooperative super()
    6. TODO (tum khud likho): RetryMixin for SAP HANA call
================================================================================
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


# === SECTION 1: __mro__ and C3 linearization ===============================
def section_1_mro_basics() -> None:
    """Dikhaata hai ki C3 ek single deterministic order banata hai."""
    print("\n=== SECTION 1: __mro__ & C3 linearization ===")

    class A:
        pass

    class B(A):
        pass

    class C(A):
        pass

    class D(B, C):  # diamond: D -> B, C -> A
        pass

    # C3 rule: D, fir B, fir C, fir common ancestor A, fir object.
    # Note: A (shared base) sirf EK baar aata hai, B aur C ke BAAD.
    print("D ki MRO:")
    for klass in D.__mro__:
        print("   ->", klass.__name__)

    # .mro() method aur __mro__ attribute same cheez deti hain
    assert D.__mro__ == tuple(D.mro())
    # C3 guarantee: child hamesha parent se pehle, A object se pehle
    names = [k.__name__ for k in D.__mro__]
    assert names == ["D", "B", "C", "A", "object"], names
    print("Verified: C3 order = D, B, C, A, object (A appears ONCE, after B & C)")


# === SECTION 2: super() is NOT just "parent" ================================
def section_2_super_is_not_parent() -> None:
    """super() MRO ke agle class ko call karta hai — sibling bhi ho sakta hai."""
    print("\n=== SECTION 2: super() is NOT just the parent ===")

    class Base:
        def who(self) -> list[str]:
            return ["Base"]

    class Left(Base):
        def who(self) -> list[str]:
            # 'super()' yahan Base nahi, MRO ke agle class ko call karega.
            return ["Left"] + super().who()

    class Right(Base):
        def who(self) -> list[str]:
            return ["Right"] + super().who()

    class Child(Left, Right):
        def who(self) -> list[str]:
            return ["Child"] + super().who()

    c = Child()
    chain = c.who()
    print("Child().who() chain:", " -> ".join(chain))
    # KEY INSIGHT: Left.who() ne super().who() kiya. Left ka 'parent' Base hai,
    # PAR MRO me Left ke baad Right aata hai. To super() ne Right.who() call kiya,
    # apne literal parent Base ko NAHI. Yahi senior-level gotcha hai.
    print("MRO of Child:", " -> ".join(k.__name__ for k in Child.__mro__))
    assert chain == ["Child", "Left", "Right", "Base"], chain
    print("Proof: inside Left, super() -> Right (a SIBLING), not Base.")


# === SECTION 3: Diamond problem solved with cooperative super() + kwargs =====
def section_3_diamond_cooperative() -> None:
    """Cooperative super() + **kwargs se shared base ka __init__ EK hi baar."""
    print("\n=== SECTION 3: Diamond problem, base __init__ runs ONCE ===")

    init_log: list[str] = []

    class Base:
        def __init__(self, **kwargs) -> None:
            init_log.append("Base")
            # MRO ke top par (object) pohonchne tak forward karte raho.
            super().__init__(**kwargs)

    class Engine(Base):
        def __init__(self, *, power: int = 0, **kwargs) -> None:
            init_log.append(f"Engine(power={power})")
            self.power = power
            super().__init__(**kwargs)  # baaki kwargs aage bhejo

    class Wheels(Base):
        def __init__(self, *, count: int = 4, **kwargs) -> None:
            init_log.append(f"Wheels(count={count})")
            self.count = count
            super().__init__(**kwargs)

    class Car(Engine, Wheels):
        def __init__(self, *, brand: str, **kwargs) -> None:
            init_log.append(f"Car(brand={brand})")
            self.brand = brand
            super().__init__(**kwargs)

    car = Car(brand="Tata", power=120, count=4)
    print("Init order:", " -> ".join(init_log))
    print("MRO:", " -> ".join(k.__name__ for k in Car.__mro__))
    # Base sirf EK baar, kwargs har class ne apna nikaal ke baaki forward kiya.
    assert init_log.count("Base") == 1, "Base must init exactly once!"
    assert (car.brand, car.power, car.count) == ("Tata", 120, 4)
    print(f"Result: brand={car.brand}, power={car.power}, count={car.count}")
    print("Base.__init__ ran exactly ONCE despite diamond. **kwargs routed cleanly.")


# === SECTION 4: REAL BACKEND — JsonMixin + TimestampMixin + TenantScopedMixin =
def section_4_real_backend_mixins() -> None:
    """His domain: DTO ko serialization + audit timestamps + tenant scoping."""
    print("\n=== SECTION 4: REAL BACKEND mixins (Niroskos-style DTO) ===")

    class JsonMixin:
        """Kisi bhi object ko JSON me serialize karne ka reusable behaviour."""
        def to_json(self) -> str:
            payload = {
                k: v for k, v in self.__dict__.items()
                if not k.startswith("_")
            }
            return json.dumps(payload, default=str, sort_keys=True)

    class TimestampMixin:
        """Audit: created_at set karta hai, fir chain ko aage badhata hai."""
        def __init__(self, **kwargs) -> None:
            self.created_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
            super().__init__(**kwargs)  # cooperative — next in MRO

    class TenantScopedMixin:
        """Multi-tenant SaaS: har record ko tenant_id se bind karta hai."""
        def __init__(self, *, tenant_id: str, **kwargs) -> None:
            self.tenant_id = tenant_id
            super().__init__(**kwargs)

    class InvoiceDTO(JsonMixin, TimestampMixin, TenantScopedMixin):
        # Mixins LEFT side (priority), concrete fields niche.
        def __init__(self, *, number: str, amount: float, **kwargs) -> None:
            self.number = number
            self.amount = amount
            super().__init__(**kwargs)  # TimestampMixin -> TenantScopedMixin -> object

    inv = InvoiceDTO(number="INV-001", amount=4999.0, tenant_id="acme")
    print("MRO:", " -> ".join(k.__name__ for k in InvoiceDTO.__mro__))
    print("tenant_id :", inv.tenant_id)
    print("created_at:", inv.created_at.isoformat())
    print("to_json() :", inv.to_json())
    # JsonMixin me __init__ nahi hai, par cooperative chain phir bhi
    # TimestampMixin -> TenantScopedMixin tak pohonchti hai. Yahi composition.
    assert inv.tenant_id == "acme" and inv.amount == 4999.0
    print("All three mixins composed via one super() chain. Zero duplicated code.")


# === SECTION 5: BREAK IT / GOTCHA — hardcoded Base.__init__ kills the chain ===
def section_5_break_it() -> None:
    """Common bug: super() ki jagah Base ko hardcode karna -> mixin skip."""
    print("\n=== SECTION 5: BREAK IT — hardcoded parent vs cooperative super() ===")

    log_broken: list[str] = []
    log_fixed: list[str] = []

    # ----- WRONG version: har class apne literal parent ko call karti hai -----
    class BaseW:
        def __init__(self) -> None:
            log_broken.append("BaseW")

    class AuditW(BaseW):
        def __init__(self) -> None:
            log_broken.append("AuditW")
            BaseW.__init__(self)  # <-- GALTI: hardcoded, MRO bypass

    class TenantW(BaseW):
        def __init__(self) -> None:
            log_broken.append("TenantW")
            BaseW.__init__(self)  # <-- GALTI: hardcoded

    class ServiceW(AuditW, TenantW):
        def __init__(self) -> None:
            log_broken.append("ServiceW")
            AuditW.__init__(self)  # <-- sirf AuditW ko bulaaya

    ServiceW()
    print("WRONG  init order:", " -> ".join(log_broken))
    # TenantW NEVER chala (skip ho gaya), aur BaseW DO baar chal sakta tha.
    # Yani tenant scoping kabhi apply hi nahi hui -> multi-tenant data leak bug.
    assert "TenantW" not in log_broken
    print("  BUG: TenantW.__init__ NEVER ran -> tenant scoping silently skipped!")

    # ----- RIGHT version: cooperative super() + **kwargs -----
    class BaseR:
        def __init__(self, **kwargs) -> None:
            log_fixed.append("BaseR")
            super().__init__(**kwargs)

    class AuditR(BaseR):
        def __init__(self, **kwargs) -> None:
            log_fixed.append("AuditR")
            super().__init__(**kwargs)

    class TenantR(BaseR):
        def __init__(self, **kwargs) -> None:
            log_fixed.append("TenantR")
            super().__init__(**kwargs)

    class ServiceR(AuditR, TenantR):
        def __init__(self, **kwargs) -> None:
            log_fixed.append("ServiceR")
            super().__init__(**kwargs)

    ServiceR()
    print("FIXED  init order:", " -> ".join(log_fixed))
    # Ab har class EK baar, MRO order me. TenantR bhi chala.
    assert log_fixed == ["ServiceR", "AuditR", "TenantR", "BaseR"], log_fixed
    assert log_fixed.count("BaseR") == 1
    print("  FIX: super() walks the MRO -> every mixin runs exactly once.")


# === SECTION 6: TODO (tum khud likho) =======================================
def section_6_todo() -> None:
    """
    TODO: Ek RetryMixin likho jo SAP HANA call ko cooperatively wrap kare.

    Expected behaviour:
      - class RetryMixin: ek method `execute(self, **kwargs)` ho jo
        max 3 attempts tak super().execute(**kwargs) ko call kare.
      - Agar super().execute() RuntimeError raise kare, to retry (attempt++)
        warna result return kar do.
      - Saari retries fail -> last exception ko re-raise karo.
      - class SAPClient: ka apna execute(**kwargs) ho jo (demo ke liye)
        pehle 2 baar RuntimeError de aur 3rd baar {"ok": True} return kare.
      - class IdempotentSAPClient(RetryMixin, SAPClient): banake test karo ki
        teesri attempt pe success aaye aur RetryMixin SAPClient ke result ko
        cooperatively (super() se) le.

    Hint: RetryMixin ko inheritance list me LEFT rakho taaki uska execute()
    pehle chale aur andar super().execute() se SAPClient tak pohonche.
    """
    print("\n=== SECTION 6: TODO — RetryMixin for SAP HANA (tum implement karo) ===")

    class RetryMixin:
        def execute(self, **kwargs):
            raise NotImplementedError("TODO: cooperative retry-around-super() likho")

    class SAPClient:
        def execute(self, **kwargs):
            raise NotImplementedError("TODO: 2 fail then success wala demo likho")

    print("TODO function ready — implement RetryMixin.execute + SAPClient.execute.")
    print("Goal: IdempotentSAPClient(RetryMixin, SAPClient) succeeds on 3rd try.")


# === MAIN DISPATCHER ========================================================
SECTIONS = {
    1: section_1_mro_basics,
    2: section_2_super_is_not_parent,
    3: section_3_diamond_cooperative,
    4: section_4_real_backend_mixins,
    5: section_5_break_it,
    6: section_6_todo,
}


def main(argv: list[str]) -> None:
    if argv:
        try:
            wanted = [int(a) for a in argv]
        except ValueError:
            print(f"Usage: python {sys.argv[0]} [section numbers]")
            print(f"Valid sections: {sorted(SECTIONS)}")
            return
    else:
        wanted = sorted(SECTIONS)

    for num in wanted:
        fn = SECTIONS.get(num)
        if fn is None:
            print(f"[skip] No section {num}. Valid: {sorted(SECTIONS)}")
            continue
        fn()


if __name__ == "__main__":
    main(sys.argv[1:])
