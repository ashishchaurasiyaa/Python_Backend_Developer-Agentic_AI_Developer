"""
================================================================================
TOPIC: Exceptions (Advanced) — hierarchy, raise-from, else/finally, ExceptionGroup,
       except*, add_note(), EAFP vs LBYL, dont-bare-except
================================================================================

KYA HOTA HAI:
    Advanced exception handling matlab error ko sirf `try/except` se pakadna nahi,
    balki: apni typed exception hierarchy banana (har layer ka ek base), error
    chaining (`raise ... from`) se root cause preserve karna, aur Python 3.11 ke
    ExceptionGroup + `except*` se ek saath multiple concurrent failures handle
    karna. add_note() se exception pe runtime context (tenant_id, request_id)
    chipka sakte ho bina message badle.

KYO NEED PADI:
    Production debugging me sabse bada dard: "kya fail hua aur KYO". Generic
    `except Exception` sab kuch ek jaisa bana deta — caller decide nahi kar paata
    retry kare ya fail. Chaining ke bina jab tum low-level error ko domain error
    me wrap karte ho to original traceback gum ho jaata. Aur TaskGroup me 5 tasks
    me se 3 fail ho to ek hi exception dikhe purane model me — baaki kho jaate.

KAISE USE KARTE HAIN:
    Per-layer base exception (DB layer ka DBError, payment layer ka PaymentError).
    Wrap karte waqt `raise DomainError(...) from low_level_err` — __cause__ set,
    "The above exception was the direct cause" dikhta. `from None` se chain hide.
    try/except/else/finally: else = no-exception path, finally = always-cleanup.
    Concurrency me asyncio.TaskGroup raises ExceptionGroup -> `except*` se filter.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: low-level socket/driver error ko RetryableSyncError me
       wrap (raise ... from) — retry loop decide karta hai transient hai ya nahi,
       aur original cause traceback me preserve rehta for postmortem.
    2. Niroskos multi-tenant Django: exception pe add_note(f"tenant={tid}") taaki
       Sentry me kis tenant ka request tha turant dikhe.
    3. Payment gateway: idempotency — DuplicateChargeError (non-retryable) vs
       GatewayTimeoutError (retryable) alag types, taaki double-charge na ho.
    4. Celery/asyncio fan-out: 10 tenant syncs parallel; TaskGroup Ex.Group raise
       karta, `except*` se retryable vs fatal failures ko alag-alag aggregate.
    5. Odoo ETL: row-level validation errors ko ExceptionGroup me collect karke
       ek hi baar report — har row pe crash nahi.

INTERVIEW ANSWER (English — recite this):
    "For non-trivial systems I design a small typed exception hierarchy with one
    base exception per layer, so callers can catch a layer's base or a specific
    subclass and decide whether to retry, fail, or surface the error. When I wrap a
    low-level error in a domain error I always use 'raise DomainError(...) from
    original' so __cause__ is set explicitly and the full root cause stays in the
    traceback; 'raise ... from None' is reserved for when the internal cause is
    noise I deliberately want to hide. I lean on else and finally precisely: else
    holds the success-only path so it doesn't accidentally catch errors from itself,
    and finally guarantees cleanup. On Python 3.11+ I rely on ExceptionGroup and
    except* for concurrent code — an asyncio.TaskGroup collects every child failure
    into one ExceptionGroup, and except* lets me handle retryable and fatal errors
    separately while re-raising the rest. I attach runtime context with
    add_note(tenant_id, request_id) instead of mangling the message. My default
    stance is EAFP over LBYL because LBYL has a check-then-act race, and the one
    rule I never break is no bare 'except:' — it swallows KeyboardInterrupt and
    SystemExit and hides the very bug you need to see."

================================================================================
Run:
    python 25_exceptions_advanced.py        # saare sections chalao
    python 25_exceptions_advanced.py 1 6    # sirf section 1 aur 6

Sections:
    1. DEMO  — custom exception hierarchy (one base per layer) + isinstance catch
    2. DEMO  — raise..from (__cause__) vs implicit __context__ vs from None
    3. DEMO  — try/except/ELSE/FINALLY semantics (kaun kab chalta)
    4. REAL  — SAP HANA retry: wrap low-level err, retryable vs fatal types
    5. REAL  — asyncio TaskGroup -> ExceptionGroup + except* (concurrent fan-out)
    6. REAL  — add_note() tenant/request context (Niroskos) + EAFP vs LBYL
    7. BREAK — bare except / except Exception swallows SystemExit + loses cause
    8. TODO  — tum khud likho: charge_payment() with idempotency + raise-from
================================================================================
"""
from __future__ import annotations

import asyncio
import sys


# === SECTION 1: DEMO — custom exception hierarchy (one base per layer) ===
class AppError(Exception):
    """Root of poori app ki exceptions. Har cheez isse niche aati — top-level
    handler `except AppError` se sab domain errors pakad sakta, baaki (programming
    bugs jaise TypeError) ko jaane deta."""


class DBError(AppError):
    """Data-access layer ka base. Connection/query/txn sab iske neeche."""


class ConnectionLostError(DBError):
    """Transient — retry kar sakte ho."""


class IntegrityViolationError(DBError):
    """Permanent — duplicate key / constraint. Retry bekaar, fail fast karo."""


def section1() -> None:
    print("\n=== SECTION 1: DEMO — exception hierarchy (one base per layer) ===")

    errors = [ConnectionLostError("socket reset"), IntegrityViolationError("dup pk")]
    for err in errors:
        # caller base se catch karke decide karta retry ya fail
        if isinstance(err, ConnectionLostError):
            decision = "RETRY (transient)"
        elif isinstance(err, IntegrityViolationError):
            decision = "FAIL FAST (permanent)"
        else:
            decision = "?"
        # dono DBError hain aur dono AppError bhi — layered catching ka fayda
        print(f"    {type(err).__name__:24} is DBError={isinstance(err, DBError)} "
              f"is AppError={isinstance(err, AppError)} -> {decision}")
    print("  -> ek base per layer = caller granularity choose karta (specific ya broad)")


# === SECTION 2: DEMO — raise..from (__cause__) vs __context__ vs from None ===
def _explicit_cause() -> None:
    try:
        int("not-a-number")
    except ValueError as e:
        # EXPLICIT chaining: __cause__ set hota, traceback me
        # "The above exception was the direct CAUSE of..." dikhta
        raise DBError("parsing GL row failed") from e


def _implicit_context() -> None:
    try:
        int("not-a-number")
    except ValueError:
        # bina `from`: __context__ implicitly set hota (during handling...).
        # __cause__ None rehta. Aksar accidental nesting yahin se aati.
        raise DBError("parsing GL row failed")


def _suppressed_cause() -> None:
    try:
        int("not-a-number")
    except ValueError:
        # from None: chain ko jaan-bujh ke hide karo (internal noise nahi chahiye)
        raise DBError("invalid GL row") from None


def section2() -> None:
    print("\n=== SECTION 2: DEMO — raise..from vs implicit context vs from None ===")

    for label, fn in [("explicit (from e)", _explicit_cause),
                      ("implicit (no from)", _implicit_context),
                      ("suppressed (from None)", _suppressed_cause)]:
        try:
            fn()
        except DBError as e:
            cause = type(e.__cause__).__name__ if e.__cause__ else None
            context = type(e.__context__).__name__ if e.__context__ else None
            suppressed = e.__suppress_context__
            print(f"    {label:24} __cause__={cause}  __context__={context}  "
                  f"__suppress_context__={suppressed}")
    print("  -> explicit: __cause__ set (best for postmortem).")
    print("  -> implicit: sirf __context__ (traceback me dono dikhte, accidental).")
    print("  -> from None: context suppressed (clean message, root cause hidden).")


# === SECTION 3: DEMO — try/except/ELSE/FINALLY semantics ===
def _run(divisor: int) -> str:
    log: list[str] = []
    try:
        result = 10 // divisor
        log.append("try-ok")
    except ZeroDivisionError:
        log.append("except")
        return ",".join(log)            # finally STILL runs even on return
    else:
        # else SIRF tab jab try me koi exception nahi aaya. Yahan wo code rakho
        # jo success ke baad chale, par jise tum galti se catch nahi karna chahte.
        log.append(f"else(result={result})")
    finally:
        # finally HAMESHA — success, exception, ya return — cleanup ka ghar
        log.append("finally")
    return ",".join(log)


def section3() -> None:
    print("\n=== SECTION 3: DEMO — try/except/ELSE/FINALLY order ===")
    print(f"    no error (div=2): {_run(2)}")
    print(f"    error   (div=0): {_run(0)}")
    print("  -> else: success-only path (try ka exception isme nahi aata).")
    print("  -> finally: return/raise ke baad bhi chalta = guaranteed cleanup.")


# === SECTION 4: REAL — SAP HANA retry: wrap low-level err, retryable vs fatal ===
class SyncError(AppError):
    """Connector layer ka base."""


class RetryableSyncError(SyncError):
    """Transient — retry loop isko retry karega."""


class FatalSyncError(SyncError):
    """Permanent — turant fail, retry waste."""


class _FlakyHanaDriver:
    """SAP HANA driver ka stand-in. Pehle 2 call transient socket error, fir ok."""

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self) -> str:
        self.calls += 1
        if self.calls < 3:
            raise OSError(f"socket reset (attempt {self.calls})")  # low-level
        return "GL rows OK"


def _fetch_with_wrapping(driver: _FlakyHanaDriver) -> str:
    """Low-level driver error ko domain error me wrap karte hain — raise..from se
    original OSError __cause__ me preserve, taaki retry decision domain-type pe ho
    par root cause postmortem ke liye na khoye."""
    try:
        return driver.fetch()
    except OSError as e:
        # socket-level = transient -> retryable. Original cause chain me rakho.
        raise RetryableSyncError("HANA fetch failed (transient)") from e


def section4() -> None:
    print("\n=== SECTION 4: REAL — SAP HANA retry (wrap + retryable vs fatal) ===")
    driver = _FlakyHanaDriver()
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            data = _fetch_with_wrapping(driver)
        except RetryableSyncError as e:
            root = type(e.__cause__).__name__
            print(f"    attempt {attempt}: RETRYABLE ({e}) [cause={root}] -> retry")
            continue
        except FatalSyncError as e:
            print(f"    attempt {attempt}: FATAL ({e}) -> give up")
            break
        else:
            print(f"    attempt {attempt}: SUCCESS -> {data}")
            break
    print("  -> retry loop sirf RetryableSyncError pe retry karta; cause preserved.")


# === SECTION 5: REAL — asyncio TaskGroup -> ExceptionGroup + except* ===
async def _tenant_sync(tenant: str) -> str:
    """Ek tenant ka sync. Kuch transient fail, kuch fatal, kuch ok."""
    await asyncio.sleep(0)
    if tenant == "acme":
        raise RetryableSyncError(f"{tenant}: HANA timeout")
    if tenant == "globex":
        raise FatalSyncError(f"{tenant}: schema missing")
    return f"{tenant}: synced"


async def _fan_out() -> None:
    """3.11 TaskGroup: agar koi child fail kare to baaki bhi chalte, fir SAARI
    failures ek ExceptionGroup me aati hain. except* se TYPE ke hisaab se split."""
    try:
        async with asyncio.TaskGroup() as tg:
            for tenant in ["acme", "globex", "initech"]:
                tg.create_task(_tenant_sync(tenant))
    # except* har matching subgroup ko handle karta — multiple except* chal sakte
    except* RetryableSyncError as eg:
        msgs = [str(e) for e in eg.exceptions]
        print(f"    RETRYABLE group ({len(msgs)}): {msgs} -> requeue")
    except* FatalSyncError as eg:
        msgs = [str(e) for e in eg.exceptions]
        print(f"    FATAL group ({len(msgs)}): {msgs} -> alert + skip")


def section5() -> None:
    print("\n=== SECTION 5: REAL — TaskGroup ExceptionGroup + except* (fan-out) ===")
    asyncio.run(_fan_out())
    print("  -> except* concurrent failures ko TYPE-wise split karta; baaki re-raise.")

    # Manually bhi bana sakte (jab khud aggregate karna ho):
    eg = ExceptionGroup("row validation", [ValueError("row3 bad"), KeyError("row7")])
    print(f"    manual ExceptionGroup carries {len(eg.exceptions)} sub-errors")


# === SECTION 6: REAL — add_note() context (Niroskos) + EAFP vs LBYL ===
def _process_tenant_request(tenant_id: str, payload: dict[str, int]) -> int:
    """add_note(): exception pe runtime context chipkao (message mat badlo).
    Sentry/logs me 'kis tenant ka' turant dikhta — yahi senior debugging trick."""
    try:
        return payload["amount"]
    except KeyError as e:
        e.add_note(f"tenant_id={tenant_id}")
        e.add_note("hint: payload missing 'amount' — check API contract")
        raise


def _eafp(d: dict[str, int], key: str) -> str:
    # EAFP: pehle try karo, fail ho to handle. No check-then-act race.
    try:
        return f"value={d[key]}"
    except KeyError:
        return "missing"


def _lbyl(d: dict[str, int], key: str) -> str:
    # LBYL: pehle check. Concurrency me key check ke baad delete ho sakta (TOCTOU).
    if key in d:
        return f"value={d[key]}"
    return "missing"


def section6() -> None:
    print("\n=== SECTION 6: REAL — add_note() tenant context + EAFP vs LBYL ===")
    try:
        _process_tenant_request("tenant-42", {})
    except KeyError as e:
        notes = getattr(e, "__notes__", [])
        print(f"    caught KeyError({e}) with notes: {notes}")

    d = {"x": 1}
    print(f"    EAFP hit/miss: {_eafp(d, 'x')} / {_eafp(d, 'y')}")
    print(f"    LBYL hit/miss: {_lbyl(d, 'x')} / {_lbyl(d, 'y')}")
    print("  -> add_note keeps message clean; notes carry tenant/request context.")
    print("  -> prefer EAFP: pythonic + avoids check-then-act TOCTOU races.")


# === SECTION 7: BREAK IT / GOTCHA — bare except swallows everything + loses cause ===
def _bad_handler() -> str:
    """GALAT: bare `except:` (ya `except BaseException`) sab kuch pakad leta —
    KeyboardInterrupt, SystemExit, MemoryError tak. Ctrl-C kaam karna band kar
    deta, aur tum exception ko `from` ke bina re-wrap karke cause bhi kho dete."""
    try:
        raise SystemExit(2)             # operator ne shutdown maanga (ya ctrl-C)
    except:                             # noqa: E722 — DELIBERATE bad example
        return "swallowed (process ko shutdown hone se rok diya!)"


def _good_handler() -> str:
    """SAHI: narrow type catch karo. BaseException-derived (SystemExit/
    KeyboardInterrupt) ko jaane do; sirf Exception ya specific type pakdo."""
    try:
        raise SystemExit(2)
    except Exception:                   # SystemExit Exception ka subclass NAHI
        return "handled"                # is tak pahunchega hi nahi -> SystemExit upar
    # finally yahan dikhane ke liye nahi; SystemExit propagate hogi


def section7() -> None:
    print("\n=== SECTION 7: BREAK IT — bare except swallows SystemExit/ctrl-C ===")
    print("  WRONG (bare except:):")
    print(f"    {_bad_handler()}")
    print("    -> SystemExit/KeyboardInterrupt nigal gaye: graceful shutdown TOOT")
    print("       gaya, Ctrl-C kaam nahi karega, aur real bug bhi chup jaate hain.")

    print("  FIXED (except Exception — BaseException-derived ko chhodo):")
    try:
        _good_handler()
    except SystemExit as e:
        print(f"    SystemExit correctly propagated: code={e.code}")
    print("    -> NEVER bare except. Catch Exception or a specific type; let")
    print("       SystemExit/KeyboardInterrupt bubble up. And re-wrap with 'from'.")


# === SECTION 8: TODO — tum khud likho: charge_payment() idempotency + raise-from ===
class PaymentError(AppError):
    """Payment layer ka base."""


class DuplicateChargeError(PaymentError):
    """Idempotency hit — same key dobara. NON-retryable."""


class GatewayTimeoutError(PaymentError):
    """Gateway timeout — RETRYABLE."""


_SEEN_KEYS: set[str] = set()


def charge_payment(idempotency_key: str, amount: int, gateway_raises: Exception | None = None) -> str:
    """
    TODO (tum implement karo):
      Payment charge with idempotency + proper exception chaining.
        1. Agar idempotency_key already _SEEN_KEYS me hai:
               raise DuplicateChargeError(f"already charged: {idempotency_key}")
           (double-charge se bachne ke liye — NON-retryable).
        2. Warna key ko _SEEN_KEYS me add karo.
        3. Agar gateway_raises (ek low-level error jaise TimeoutError) diya gaya hai:
               usse `raise GatewayTimeoutError(...) from gateway_raises` karo
               taaki original cause __cause__ me preserve rahe (retryable).
        4. Warna success string return karo: f"charged {amount} (key={idempotency_key})"
    Expected behaviour:
        charge_payment("k1", 500)              -> "charged 500 (key=k1)"
        charge_payment("k1", 500)              -> raises DuplicateChargeError
        charge_payment("k2", 700, TimeoutError("gw down"))
                                               -> raises GatewayTimeoutError,
                                                  e.__cause__ is the TimeoutError
    """
    raise NotImplementedError("TODO: charge_payment ka body likho (idempotency + raise-from)")


def section8() -> None:
    print("\n=== SECTION 8: TODO — charge_payment() idempotency + raise-from (tum likho) ===")
    try:
        print(f"    first  : {charge_payment('k1', 500)}")
        try:
            charge_payment("k1", 500)
            print("    ERROR: duplicate block hona chahiye tha!")
        except DuplicateChargeError as e:
            print(f"    correct! duplicate blocked: {e}")
        try:
            charge_payment("k2", 700, TimeoutError("gateway down"))
        except GatewayTimeoutError as e:
            print(f"    correct! retryable: {e} [cause={type(e.__cause__).__name__}]")
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
        "7": section7,
        "8": section8,
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
