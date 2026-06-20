"""
================================================================================
TOPIC: Abstract Base Classes (ABC) & typing.Protocol
================================================================================

KYA HOTA HAI:
  ABC ek "contract" hota hai — abstractmethod likho, to subclass jab tak woh
  method implement nahi karta, instantiate hi nahi hoga (TypeError milega).
  Protocol structural typing deta hai: "agar duck quack karti hai to duck hai"
  — koi inheritance nahi chahiye, sirf required methods/attrs hone chahiye, aur
  type-checker (mypy) ye static-ally verify karta hai.

KYO NEED PADI:
  Bina ABC ke aap galti se aadha-adhura subclass bana ke prod me ship kar dete
  ho, error tab aata hai jab missing method actually call hota hai (runtime).
  ABC isko class-definition/instantiation time pe hi pakad leta hai.
  Protocol tab kaam aata hai jab aap third-party / pre-existing classes ko
  modify nahi kar sakte (inherit karwana possible nahi) par phir bhi typed
  "ye object charge() karta hai" guarantee chahiye.

KAISE USE KARTE HAIN:
  ABC: class X(ABC) + @abstractmethod. Concrete (shared) methods bhi daal sakte
  ho — woh template/helper ka kaam karte hain.
  register(): bina inherit karwaye kisi class ko "virtual subclass" declare
  karo — isinstance True ho jayega, par abstractmethod enforcement NAHI hoga.
  Protocol: class P(Protocol) bas method signatures; @runtime_checkable lagao
  to isinstance() bhi chalega (warna sirf static check).

KAHAN USE HOTA HAI (backend scenarios):
  - PaymentGateway ABC: charge/refund abstract, charge_with_retry concrete
    (Razorpay/Stripe sab same retry+idempotency logic reuse karein).
  - SAP HANA connector: ek "Transport" Protocol — sync/async/mock client sab
    fit, bina common base class ke (duck-typed, tests me MockClient inject).
  - Niroskos multi-tenant: TenantScoped Protocol — har repo me tenant_id filter
    guarantee, type-checker enforce kare.
  - Celery task base ABC: run() abstract, on_failure/retry concrete.
  - register() se collections.abc me list ko Sequence virtual subclass banate
    hain — wahi pattern legacy DTO classes ke saath.

INTERVIEW ANSWER (English):
  Abstract Base Classes give you nominal contracts: you mark methods with
  @abstractmethod, and Python refuses to instantiate any subclass that has not
  implemented all of them, failing fast at object-creation time instead of deep
  in production. ABCs can also hold concrete shared methods, which is how the
  Template Method pattern works — the base controls the flow, subclasses fill
  the hooks. register() lets you declare an unrelated class a virtual subclass
  so isinstance() passes, but be careful: registration does NOT enforce the
  abstract methods, so it is a typing convenience, not a safety guarantee.
  Protocols, from the typing module, give you structural typing — static duck
  typing — so any object with the right shape satisfies the interface without
  inheriting anything, which is ideal for decoupling from third-party classes.
  The key senior nuance is that Protocols are checked statically by mypy by
  default and only support isinstance() if you add @runtime_checkable — and even
  then runtime checks only verify method NAMES exist, not their signatures or
  argument types, so a runtime_checkable isinstance pass can still call into a
  signature mismatch. Rule of thumb: ABC when you own the hierarchy and want
  shared code, Protocol when you only care about shape and want loose coupling.

Run:
  python 04_abc_and_protocols.py          # saare sections
  python 04_abc_and_protocols.py 2 5      # sirf section 2 aur 5

Sections:
  1. DEMO  — ABC + abstractmethod: incomplete subclass instantiate nahi hota
  2. DEMO  — Concrete method in ABC (Template Method) + abstract property
  3. DEMO  — register() virtual subclass (isinstance True, par enforce NAHI)
  4. DEMO  — typing.Protocol: structural typing, no inheritance needed
  5. REAL  — SAP HANA Transport Protocol + retry helper (mock injectable)
  6. BREAK — runtime_checkable sirf method NAAM check karta hai, signature nahi
  7. TODO  — tum khud likho: TenantScoped Protocol + scoped repo
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


# === SECTION 1: DEMO — ABC + abstractmethod (instantiate fails until implemented) ===
def section_1() -> None:
    print("\n=== SECTION 1: ABC + abstractmethod ===")

    class PaymentGateway(ABC):
        # @abstractmethod => subclass ko ye implement karna HI padega
        @abstractmethod
        def charge(self, amount: int) -> str: ...

    # Galti: charge implement nahi kiya -> ye subclass bhi abstract reh gaya
    class BrokenGateway(PaymentGateway):
        pass

    try:
        BrokenGateway()  # type: ignore[abstract]
    except TypeError as e:
        # Note ye class-DEFINITION pe nahi, INSTANTIATION pe fail hua
        print("BrokenGateway() ->", type(e).__name__, ":", e)

    # Sahi: charge implement kiya -> ab instantiate ho jayega
    class RazorpayGateway(PaymentGateway):
        def charge(self, amount: int) -> str:
            return f"rzp_txn_{amount}"

    print("RazorpayGateway().charge(500) ->", RazorpayGateway().charge(500))
    # __abstractmethods__ batata hai abhi kaun-kaun abstract pending hai
    print("BrokenGateway pending abstracts ->", sorted(BrokenGateway.__abstractmethods__))
    print("RazorpayGateway pending abstracts ->", sorted(RazorpayGateway.__abstractmethods__))


# === SECTION 2: DEMO — Concrete method in ABC (Template Method) + abstract property ===
def section_2() -> None:
    print("\n=== SECTION 2: Concrete method + abstract property in ABC ===")

    class Notifier(ABC):
        @property
        @abstractmethod
        def channel(self) -> str:
            """Subclass batayega kaunsa channel (sms/email)."""
            ...

        @abstractmethod
        def _send(self, to: str, body: str) -> None: ...

        # CONCRETE method: flow yahan control hota hai, subclass sirf hook bharta hai.
        # Sab subclasses ye reuse karte hain — yahi Template Method Pattern hai.
        def notify(self, to: str, body: str) -> str:
            self._send(to, body)
            return f"[{self.channel}] sent to {to}: {body!r}"

    class SmsNotifier(Notifier):
        @property
        def channel(self) -> str:
            return "sms"

        def _send(self, to: str, body: str) -> None:
            pass  # asli SMS API call yahan hoti

    n = SmsNotifier()
    print(n.notify("+9199999", "OTP 123456"))
    print("notify() concrete hai, har subclass me dubara likhne ki zarurat nahi.")


# === SECTION 3: DEMO — register() virtual subclass (isinstance True, par enforce NAHI) ===
def section_3() -> None:
    print("\n=== SECTION 3: ABC.register() virtual subclass ===")

    class Serializable(ABC):
        @abstractmethod
        def to_dict(self) -> dict: ...

    # LegacyDTO purani class hai, hum isko inherit nahi karwa sakte / nahi karna chahte.
    class LegacyDTO:
        def __init__(self, x: int) -> None:
            self.x = x
        # Dhyaan do: to_dict yahan JAAN-BOOJH ke NAHI likha.

    # register se isko "virtual subclass" bana dete hain
    Serializable.register(LegacyDTO)

    dto = LegacyDTO(7)
    print("isinstance(dto, Serializable) ->", isinstance(dto, Serializable))  # True!
    print("issubclass(LegacyDTO, Serializable) ->", issubclass(LegacyDTO, Serializable))

    # GOTCHA: register abstractmethod ENFORCE nahi karta. isinstance True hai par
    # to_dict exist hi nahi karta -> call karoge to AttributeError, runtime me.
    try:
        dto.to_dict()  # type: ignore[attr-defined]
    except AttributeError as e:
        print("dto.to_dict() ->", type(e).__name__, ":", e)
    print("Lesson: register() = typing convenience, NOT a safety guarantee.")


# === SECTION 4: DEMO — typing.Protocol: structural typing, no inheritance ===
def section_4() -> None:
    print("\n=== SECTION 4: Protocol — structural (duck) typing ===")

    class SupportsCharge(Protocol):
        # Sirf shape define kar rahe hain; koi inherit nahi karega.
        def charge(self, amount: int) -> str: ...

    # Ye dono Protocol ko inherit NAHI karte, par shape match karta hai.
    class StripeClient:
        def charge(self, amount: int) -> str:
            return f"ch_{amount}"

    class WalletClient:
        def charge(self, amount: int) -> str:
            return f"wallet_{amount}"

    # Function Protocol pe depend karta hai -> dono accept honge (static duck typing).
    def collect(gw: SupportsCharge, amount: int) -> str:
        return gw.charge(amount)

    print("collect(StripeClient()) ->", collect(StripeClient(), 100))
    print("collect(WalletClient()) ->", collect(WalletClient(), 250))
    print("Dono fit hue bina kisi base class ko inherit kiye — yahi Protocol ka power hai.")


# === SECTION 5: REAL BACKEND SCENARIO — SAP HANA Transport Protocol + retry helper ===
def section_5() -> None:
    print("\n=== SECTION 5: REAL — SAP HANA Transport Protocol + retry ===")

    # Real client ko hum modify nahi kar sakte, isliye Protocol use karte hain.
    # Tests me MockTransport inject karke flaky network simulate kar sakte hain.
    class Transport(Protocol):
        def execute(self, query: str) -> dict: ...

    # idempotency + retry helper — kisi bhi Transport ke saath chalega.
    def run_idempotent(transport: Transport, query: str, key: str, retries: int = 3) -> dict:
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                res = transport.execute(query)
                res["idempotency_key"] = key  # duplicate writes se bachne ke liye
                res["attempt"] = attempt
                return res
            except ConnectionError as e:
                last_err = e
                print(f"  attempt {attempt} failed: {e} -> retrying")
        raise RuntimeError(f"SAP HANA call failed after {retries} tries") from last_err

    # MockTransport: pehle 2 baar fail, 3rd pe success (real HANA flakiness jaisa).
    class MockHanaTransport:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, query: str) -> dict:
            self.calls += 1
            if self.calls < 3:
                raise ConnectionError("HANA socket reset")
            return {"rows": [{"id": 1}], "query": query}

    result = run_idempotent(MockHanaTransport(), "SELECT 1 FROM DUMMY", key="sync-2026-06-18-001")
    print("final result ->", result)
    print("MockTransport ne kahin Transport inherit nahi kiya — sirf shape match kiya.")


# === SECTION 6: BREAK IT / GOTCHA — runtime_checkable sirf NAAM dekhta hai, signature nahi ===
def section_6() -> None:
    print("\n=== SECTION 6: BREAK IT — runtime_checkable only checks method NAMES ===")

    @runtime_checkable
    class Charger(Protocol):
        def charge(self, amount: int, currency: str) -> str: ...

    # GALAT samajh: "isinstance True hai matlab call safe hai." -> ye GALAT hai.
    class WrongSignatureClient:
        # naam to charge hai, par signature alag (currency missing)
        def charge(self) -> str:  # type: ignore[override]
            return "charged-no-args"

    obj = WrongSignatureClient()
    print("isinstance(obj, Charger) ->", isinstance(obj, Charger))  # True (sirf naam matched!)

    # WRONG OUTPUT: bharose ke saath call kiya -> runtime me phat gaya.
    try:
        obj.charge(500, "INR")  # type: ignore[call-arg]
    except TypeError as e:
        print("WRONG: obj.charge(500, 'INR') ->", type(e).__name__, ":", e)

    # FIX: runtime_checkable isinstance pe blindly bharosa mat karo. Sahi class do,
    # aur asli protection ke liye mypy (static check) use karo jo signature verify karta hai.
    class CorrectClient:
        def charge(self, amount: int, currency: str) -> str:
            return f"{currency}-{amount}"

    fixed = CorrectClient()
    print("FIX: isinstance(fixed, Charger) ->", isinstance(fixed, Charger))
    print("FIX: fixed.charge(500, 'INR') ->", fixed.charge(500, "INR"))
    print("Lesson: runtime_checkable = name-only check; signatures sirf mypy pakadta hai.")


# === SECTION 7: TODO (tum khud likho) — TenantScoped Protocol + scoped repo ===
def section_7() -> None:
    print("\n=== SECTION 7: TODO — TenantScoped Protocol (tum likho) ===")

    # GOAL (Niroskos multi-tenant SaaS):
    #   1. @runtime_checkable Protocol 'TenantScoped' banao jisme method ho:
    #        list_for(self, tenant_id: int) -> list[dict]
    #   2. Ek class 'InvoiceRepo' banao jisme _rows ho [{tenant_id, amount}, ...]
    #      aur list_for(tenant_id) sirf usi tenant ke rows return kare.
    #   3. Ek function 'safe_list(repo: TenantScoped, tenant_id: int) -> list[dict]'
    #      jo pehle isinstance(repo, TenantScoped) check kare, fail pe TypeError raise kare,
    #      warna repo.list_for(tenant_id) return kare.
    #   Expected: safe_list(InvoiceRepo([...]), 1) -> sirf tenant 1 ke invoices.

    def safe_list(repo: object, tenant_id: int) -> list[dict]:
        raise NotImplementedError("TODO: TenantScoped Protocol + scoping logic likho")

    try:
        safe_list(object(), 1)
    except NotImplementedError as e:
        print("TODO pending ->", e)


# === MAIN DISPATCHER ===
_SECTIONS = {
    1: section_1,
    2: section_2,
    3: section_3,
    4: section_4,
    5: section_5,
    6: section_6,
    7: section_7,
}


def main(argv: list[str]) -> None:
    args = argv[1:]
    if not args:
        to_run = sorted(_SECTIONS)
    else:
        to_run = []
        for a in args:
            if not a.isdigit() or int(a) not in _SECTIONS:
                print(f"skip invalid section: {a!r} (valid: {sorted(_SECTIONS)})")
                continue
            to_run.append(int(a))
    for num in to_run:
        _SECTIONS[num]()


if __name__ == "__main__":
    main(sys.argv)
