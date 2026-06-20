"""
================================================================================
TOPIC: Monkey Patching (replacing attributes/methods at runtime)
================================================================================

KYA HOTA HAI:
    Monkey patching matlab runtime pe kisi module, class, ya object ke
    attribute/method/function ko CHUPCHAAP replace ya modify kar dena — source
    code chhede bina. Kyunki Python me classes aur modules bhi sirf mutable
    objects hain (attribute namespaces), tum bahar se `obj.method = new_func`
    karke unka behaviour badal sakte ho. Original kahin save karke baad me
    restore bhi kar sakte ho.

KYO NEED PADI:
    Kabhi-kabhi tumhare control me code nahi hota: ek 3rd-party library me bug
    hai aur PyPI fix aane me time lagega — to runtime hotfix (patch) lagana padta
    hai. Testing me bhi asli network/DB call nahi chahiye, to us function ko fake
    se replace karte ho (mocking). Aur feature-toggle / A-B ke liye behaviour
    swap karna padta hai bina deploy ke.

KAISE USE KARTE HAIN:
    Seedha assignment: `module.func = my_func` ya `Cls.method = my_method`.
    Par PROFESSIONAL tarika hai discipline ke saath: original ko save karo,
    patch lagao, kaam ke baad RESTORE karo — ideally try/finally ya context
    manager me. Yahi `unittest.mock.patch` automatically karta hai (enter pe
    patch, exit pe undo). gevent/eventlet to poora `monkey.patch_all()` karke
    stdlib (socket, ssl, threading) ko green-thread aware bana dete hain.

KAHAN USE HOTA HAI (backend scenarios):
    1. Testing: SAP HANA connector ki asli `fetch_rows()` ko fake se patch karke
       retry/idempotency logic test karna — bina HANA chalaye.
    2. Hotfix: ek 3rd-party payment SDK ka buggy `verify_signature` runtime pe
       patch karke prod outage rokna, jab tak upstream fix na aaye.
    3. Feature toggle: Niroskos multi-tenant me ek tenant ke liye pricing
       function ko temporarily naye logic se swap karna.
    4. Celery/Redis: test me `task.delay` ko patch karke task ko inline-eager
       chalana, broker ke bina assert karna.
    5. gevent/eventlet: `monkey.patch_all()` se stdlib socket ko cooperative
       banana taaki blocking I/O bhi green-threads me yield kare.

INTERVIEW ANSWER (English — recite this):
    "Monkey patching is replacing or extending attributes, methods, or functions
    at runtime without editing the original source, which Python allows because
    classes and modules are just mutable namespaces. I reach for it in three
    main situations: dependency-injection-free testing where I swap a real
    network or database call for a fake, emergency hotfixes to a third-party
    library I can't release, and behaviour toggles. The disciplined form of it
    is unittest.mock.patch, which is essentially a context manager that records
    the original, installs the replacement, and guarantees restoration on exit,
    so you never leak a patch into another test. The senior nuance is to always
    patch where the name is looked up, not where it's defined — if module A does
    'from utils import now', you must patch 'A.now', not 'utils.now', otherwise
    A still holds its own reference and your patch silently does nothing. Its
    dangers are real: it's global mutation, it's brittle against upstream
    changes, and an un-restored patch bleeds across tests, so I keep patches
    narrow and always paired with a restore, usually via a context manager.
    Frameworks like gevent take it to the extreme with monkey.patch_all(), which
    rewrites the standard library's blocking I/O to be cooperative."

================================================================================
Run:
    python 13_monkey_patching.py        # saare sections chalao
    python 13_monkey_patching.py 1 5    # sirf section 1 aur 5

Sections:
    1. DEMO  — replace a method/function at runtime (object + class + module attr)
    2. DEMO  — safe patch+restore via try/finally and a custom context manager
    3. REAL  — unittest.mock.patch: fake SAP HANA fetch to test retry logic
    4. REAL  — hotfix a buggy 3rd-party payment SDK method at runtime (+gevent note)
    5. BREAK — patch the WRONG name ('where defined' vs 'where looked up') gotcha
    6. TODO  — tum khud likho: feature-toggle context manager for tenant pricing
================================================================================
"""
from __future__ import annotations

import contextlib
import sys
import types
from typing import Any, Callable, Iterator
from unittest import mock


# === SECTION 1: DEMO — replace method/function at runtime (object/class/module) ===
def section1() -> None:
    print("\n=== SECTION 1: runtime attribute/method replacement ===")

    class Charger:
        def fee(self, amount: float) -> float:
            return round(amount * 0.02, 2)  # original: 2% gateway fee

    c = Charger()
    print(f"  before patch: Charger().fee(1000) = {c.fee(1000)}  (2%)")

    # ---- CLASS-level patch: ab har instance naya behaviour dekhega ----
    def discounted_fee(self: Charger, amount: float) -> float:
        return round(amount * 0.01, 2)  # promo: 1% fee

    Charger.fee = discounted_fee  # type: ignore[assignment]
    print(f"  after class patch: Charger().fee(1000) = {Charger().fee(1000)}  (1%)")

    # ---- INSTANCE-level patch: sirf ek object pe (note: function vs bound) ----
    # Instance pe plain function set karoge to 'self' auto-bind NAHI hoga,
    # isliye partial/lambda se ya types.MethodType se bind karna padta hai.
    c2 = Charger()
    c2.fee = types.MethodType(lambda self, amount: 0.0, c2)  # type: ignore[method-assign]
    print(f"  instance-only patch: c2.fee(1000) = {c2.fee(1000)}  (waived, sirf c2)")
    print(f"  doosra instance still class behaviour: {Charger().fee(1000)}")

    # ---- MODULE-level attr patch: module bhi ek mutable namespace hai ----
    # 'types' module ka koi attr replace karke dikhate hain (phir wapas).
    saved = types.resolve_bases  # save (restore section 2 me sikhayenge)
    types.resolve_bases = lambda bases: ("patched!",)  # type: ignore[assignment]
    print(f"  module attr patched: types.resolve_bases(()) = {types.resolve_bases(())}")
    types.resolve_bases = saved  # restore right away (clean rakho)
    print("  module attr restored (modules bhi sirf attribute namespaces hain).")


# === SECTION 2: DEMO — safe patch+restore (try/finally + custom context manager) ===
def section2() -> None:
    print("\n=== SECTION 2: safe patch + restore (try/finally / context manager) ===")

    class Clock:
        def now(self) -> str:
            return "REAL-TIME"

    clk = Clock()

    # ---- try/finally: patch lagao, kaam karo, GUARANTEED restore karo ----
    original = Clock.now
    Clock.now = lambda self: "FROZEN-2026-06-18"  # type: ignore[assignment]
    try:
        print(f"  inside try/finally: clk.now() = {clk.now()}  (frozen)")
    finally:
        Clock.now = original  # exception bhi aaye to bhi restore hoga
    print(f"  after finally: clk.now() = {clk.now()}  (restored)")

    # ---- Reusable context manager: yahi pattern mock.patch internally karta hai ----
    @contextlib.contextmanager
    def patched_attr(target: Any, name: str, new_value: Any) -> Iterator[None]:
        sentinel = object()
        old = getattr(target, name, sentinel)
        setattr(target, name, new_value)
        try:
            yield
        finally:
            # agar attr pehle se nahi tha to delete karo, warna purana wapas
            if old is sentinel:
                delattr(target, name)
            else:
                setattr(target, name, old)

    with patched_attr(Clock, "now", lambda self: "CTX-FROZEN"):
        print(f"  inside context manager: clk.now() = {clk.now()}  (frozen)")
    print(f"  after context manager: clk.now() = {clk.now()}  (auto-restored)")
    print("  Lesson: save -> patch -> finally-restore. Yahi disciplined monkeypatch hai.")


# === SECTION 3: REAL — unittest.mock.patch to test SAP HANA retry logic ===
def section3() -> None:
    print("\n=== SECTION 3: REAL — mock.patch fakes SAP HANA fetch (test retry) ===")

    class HanaConnector:
        def fetch_rows(self, query: str) -> list[dict[str, Any]]:
            # Asli me: SAP HANA pe network call (test me hum nahi chalana chahte)
            raise RuntimeError("real HANA call — should be patched in tests!")

        def fetch_with_retry(self, query: str, max_retries: int = 3) -> list[dict[str, Any]]:
            attempt = 0
            while True:
                attempt += 1
                try:
                    return self.fetch_rows(query)
                except ConnectionError as e:
                    if attempt > max_retries:
                        raise
                    print(f"    attempt {attempt} failed ({e}); retrying...")

    conn = HanaConnector()

    # ---- mock.patch.object: fetch_rows ko fake se replace, sirf 'with' block me ----
    # side_effect list: pehle 2 call pe ConnectionError, teesri pe success rows.
    fake = mock.Mock(side_effect=[
        ConnectionError("HANA reset"),
        ConnectionError("HANA reset"),
        [{"id": 1, "amt": 500}],
    ])
    with mock.patch.object(HanaConnector, "fetch_rows", fake):
        rows = conn.fetch_with_retry("SELECT * FROM invoices")
        print(f"  retry succeeded after fakes -> rows = {rows}")
        print(f"  fetch_rows called {fake.call_count} times (2 fail + 1 ok)")
        # assert-style check jaise test me karte
        fake.assert_called_with("SELECT * FROM invoices")

    # ---- patch block ke BAAR me original wapas: real method bahal ----
    print("  outside 'with': original fetch_rows restored ->", end=" ")
    try:
        conn.fetch_rows("x")
    except RuntimeError as e:
        print(f"raises real error again ({e})")
    print("  mock.patch = disciplined monkeypatch: auto patch on enter, undo on exit.")


# === SECTION 4: REAL — runtime hotfix a buggy 3rd-party payment SDK (+gevent note) ===
def section4() -> None:
    print("\n=== SECTION 4: REAL — hotfix a buggy 3rd-party payment SDK method ===")

    # Maan lo ye ek 3rd-party SDK hai jo tumhare control me nahi (vendored).
    class VendorPaymentSDK:
        def verify_signature(self, payload: str, sig: str) -> bool:
            # BUG: vendor galti se hamesha True return kar raha (security hole!)
            return True

    sdk = VendorPaymentSDK()
    print(f"  buggy SDK: verify_signature('p','WRONG') = {sdk.verify_signature('p', 'WRONG')}  (always True — bad!)")

    # ---- Runtime hotfix: jab tak upstream fix na aaye, sahi logic patch karo ----
    def safe_verify(self: VendorPaymentSDK, payload: str, sig: str) -> bool:
        # asli HMAC nahi, demo: sig ko payload+'secret' ke against match karo
        expected = f"{payload}-secret"
        return sig == expected

    _original_verify = VendorPaymentSDK.verify_signature  # save for audit/rollback
    VendorPaymentSDK.verify_signature = safe_verify  # type: ignore[assignment]
    try:
        print(f"  after hotfix: verify('p','WRONG')        = {sdk.verify_signature('p', 'WRONG')}  (now False)")
        print(f"  after hotfix: verify('p','p-secret')     = {sdk.verify_signature('p', 'p-secret')}  (valid)")
    finally:
        VendorPaymentSDK.verify_signature = _original_verify  # documented rollback
    print("  Patch documented + reversible. Upstream fix aate hi remove kar do.")

    # ---- gevent/eventlet mention (yahan import nahi, sirf concept) ----
    print("  NOTE (gevent/eventlet): ye libs `monkey.patch_all()` se stdlib ke")
    print("    socket/ssl/threading/time.sleep ko COOPERATIVE versions se replace")
    print("    kar deti hain — taaki blocking I/O bhi green-threads me yield kare.")
    print("    Isliye gevent ka patch_all() program ke SABSE PEHLE call hona chahiye.")


# === SECTION 5: BREAK IT / GOTCHA — patch 'where defined' vs 'where looked up' ===
# Module-level helpers taaki 'from X import name' wala lookup realistically dikhe.
def _send_email(to: str) -> str:
    return f"REAL email sent to {to}"


# Ye function module-level _send_email ko GLOBAL lookup se call karta hai.
def notify_via_global(user: str) -> str:
    return _send_email(user)


# Ye function ne ek LOCAL alias bana liya (jaise 'from helpers import send as _local').
_local_alias = _send_email


def notify_via_alias(user: str) -> str:
    return _local_alias(user)  # apne alias ko dekhega, original namespace ko nahi


def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — patch the WRONG name (lookup vs definition) ===")

    fake = lambda to: f"FAKE captured for {to}"

    # ---- WORKS: notify_via_global module-global _send_email ko har call pe dekhta hai ----
    with mock.patch(f"{__name__}._send_email", fake):
        out = notify_via_global("alice")
    print(f"  patch module-global, call via global lookup -> {out}")
    print("    ^ WORKS: function har call pe module namespace se naam dhundhta hai.")

    # ---- GALAT: notify_via_alias ne apna alias bana liya — module attr patch use NAHI dikhega ----
    with mock.patch(f"{__name__}._send_email", fake):
        out_bad = notify_via_alias("bob")
    print(f"  patch module-global, call via LOCAL alias  -> {out_bad}")
    print("    ^ BROKEN: '_local_alias' apna reference rakhta hai; module attr badla,")
    print("      par alias purana hi point karta raha — patch silently no-op ho gaya.")

    # ---- FIX: us NAME ko patch karo jahan code use karta hai (yahan: _local_alias) ----
    with mock.patch(f"{__name__}._local_alias", fake):
        out_fixed = notify_via_alias("bob")
    print(f"  FIX: patch the alias name actually used    -> {out_fixed}")
    print("  RULE: patch where the name is LOOKED UP, not where it's DEFINED.")
    print("  (i.e. 'from mod import f' => patch 'caller.f', NOT 'mod.f')")


# === SECTION 6: TODO — tum khud likho: feature-toggle context manager (tenant pricing) ===
class PricingEngine:
    """Niroskos-style pricing. Default flat rate; toggle se temporarily swap karna hai."""

    def rate(self, tenant_id: str, base: float) -> float:
        return round(base * 1.0, 2)  # default: no markup


@contextlib.contextmanager
def feature_toggle_pricing(new_rate_fn: Callable[[PricingEngine, str, float], float]) -> Iterator[None]:
    """
    TODO (tum implement karo):
      Ek context manager banao jo PricingEngine.rate ko TEMPORARILY `new_rate_fn`
      se replace kare (feature toggle / A-B), aur block ke baad GUARANTEED restore
      kare — chahe exception aaye.
      Steps:
        1. PricingEngine.rate ka original reference save karo.
        2. PricingEngine.rate = new_rate_fn  (class-level patch).
        3. try: yield  / finally: original wapas set karo.
      Expected behaviour:
          eng = PricingEngine()
          eng.rate("acme", 100)                      -> 100.0   (default)
          with feature_toggle_pricing(lambda self, t, b: round(b*1.2, 2)):
              eng.rate("acme", 100)                  -> 120.0   (20% markup ON)
          eng.rate("acme", 100)                      -> 100.0   (auto-restored)
      Hint: bilkul section 2 ke try/finally patch+restore jaisa — bas class method pe.
    """
    raise NotImplementedError("TODO: feature_toggle_pricing context manager implement karo (patch+restore)")


def section6() -> None:
    print("\n=== SECTION 6: TODO — feature-toggle pricing context manager (tum likho) ===")
    eng = PricingEngine()
    try:
        before = eng.rate("acme", 100)
        with feature_toggle_pricing(lambda self, t, b: round(b * 1.2, 2)):
            during = eng.rate("acme", 100)
        after = eng.rate("acme", 100)
        print(f"  before toggle -> {before}  (expected 100.0)")
        print(f"  during toggle -> {during}  (expected 120.0, +20%)")
        print(f"  after  toggle -> {after}  (expected 100.0, restored)")
        if (before, during, after) == (100.0, 120.0, 100.0):
            print("  correct! feature toggle patches + auto-restores cleanly.")
        else:
            print("  output galat hai — patch/restore logic dobara dekho.")
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
