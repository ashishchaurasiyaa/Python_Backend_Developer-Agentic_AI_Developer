"""
================================================================================
TOPIC: Context Managers (__enter__/__exit__, @contextmanager, ExitStack, suppress)
================================================================================

KYA HOTA HAI:
    Context manager ek object hai jo "setup" aur "guaranteed cleanup" ko ek hi
    block me bandhta hai — `with` statement ke saath. Andar se sirf do dunder:
    __enter__ (block start pe chalta, jo return karo wo `as x` me milta) aur
    __exit__ (block khatm/exception pe ZAROOR chalta — cleanup yahin hota). Iska
    matlab: resource khulta hai, kaam hota hai, aur cleanup kabhi miss nahi hota.

KYO NEED PADI:
    Bina iske aapko try/finally har jagah haath se likhna padta — file close,
    db connection release, lock unlock — aur ek exception ya early-return aate hi
    cleanup miss ho jaata (leaked connection, stuck lock, half-committed txn).
    `with` cleanup ko exception-safe + deterministic bana deta hai, ek hi jagah.

KAISE USE KARTE HAIN:
    Class style: __enter__/__exit__ define karo. Generator style: ek function pe
    @contextmanager lagao aur `yield` se pehle setup, `yield` ke baad (try/finally
    me) cleanup likho. Dynamic count of resources ke liye ExitStack. Exception ko
    chupana ho to __exit__ se True return karo (ya contextlib.suppress use karo).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: cursor/transaction ek CM me — block success -> commit,
       exception -> rollback, aur connection HAMESHA close (leak na ho).
    2. Niroskos multi-tenant Django: `with tenant_context(tid):` — schema/RLS set,
       block ke baad reset, taaki cross-tenant data leak na ho.
    3. Celery/Redis pipeline: distributed lock acquire/release as a CM — task crash
       ho bhi jaaye to lock release guaranteed.
    4. Payment gateway: idempotency ke saath atomic charge — DB transaction CM se
       partial state avoid, retry pe duplicate charge se bacho.
    5. Odoo/ETL migration: ExitStack se N source files + 1 target connection ek hi
       block me kholo aur reverse order me automatically band karo.

INTERVIEW ANSWER (English — recite this):
    "A context manager guarantees deterministic, exception-safe cleanup by pairing
    setup in __enter__ with teardown in __exit__, which the with statement calls
    even if the body raises or returns early. __enter__ returns the value bound by
    'as', and __exit__ receives the exception type, value and traceback — returning
    True from __exit__ swallows the exception, which is powerful but dangerous if
    done by accident. For lightweight cases I prefer the @contextmanager generator
    style, putting setup before the yield and cleanup in a finally after it, so the
    cleanup still runs on exceptions. When the number of resources is dynamic I use
    contextlib.ExitStack to register cleanups and unwind them in reverse order, and
    contextlib.suppress for the narrow 'ignore this specific error' case instead of
    a bare except. The pattern I rely on most in production is a transactional
    context manager that commits on success and rolls back on any exception while
    always closing the connection — that is how I keep our SAP HANA writes atomic
    and idempotent. The senior nuance is that __exit__ must be careful what it
    returns: a stray truthy value silently hides real bugs, and for I/O-bound
    resources the right tool is an async context manager with __aenter__/__aexit__
    driven by 'async with'."

================================================================================
Run:
    python 15_context_managers.py          # saare sections chalao
    python 15_context_managers.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — class-based __enter__/__exit__ (cleanup guaranteed on exception)
    2. DEMO  — @contextmanager generator style (try/finally around yield)
    3. REAL  — transactional CM: SAP HANA-style commit/rollback + always close
    4. REAL  — ExitStack for dynamic N resources + contextlib.suppress
    5. REAL  — tenant_context CM (Niroskos) + brief async with (__aenter__/__aexit__)
    6. BREAK — __exit__ returning True swallows ALL exceptions (galti + fix)
    7. TODO  — tum khud likho: @contextmanager distributed_lock(name)
================================================================================
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
from types import TracebackType
from typing import Any, Iterator


# === SECTION 1: DEMO — class-based __enter__/__exit__ (cleanup guaranteed) ===
class ManagedResource:
    """Minimal class CM. __enter__ jo return kare wo `as r` me bind hota.
    __exit__ HAMESHA chalta — normal exit pe bhi, exception pe bhi."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "ManagedResource":
        print(f"    __enter__: opening {self.name!r}")
        return self                       # ye value `with ... as x` me jaati hai

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        # exc_type None = clean exit; warna exception aaya tha block me
        status = "cleanly" if exc_type is None else f"due to {exc_type.__name__}"
        print(f"    __exit__:  closing {self.name!r} ({status})")
        return False                      # False = exception ko mat dabao (re-raise)


def section1() -> None:
    print("\n=== SECTION 1: class __enter__/__exit__ (cleanup runs even on error) ===")

    print("  clean path:")
    with ManagedResource("db_conn") as r:
        print(f"    inside block, using {r.name!r}")

    print("  error path (exception block ke andar uthti hai):")
    try:
        with ManagedResource("file_handle"):
            raise ValueError("kuch galat ho gaya andar")
    except ValueError as e:
        print(f"    caught outside: {type(e).__name__}: {e}")
    print("  -> dono case me __exit__ chala = cleanup kabhi miss nahi hua")


# === SECTION 2: DEMO — @contextmanager generator style (try/finally) ===
@contextlib.contextmanager
def timer(label: str) -> Iterator[dict[str, Any]]:
    """Generator-based CM. yield se PEHLE = setup, yield ke BAAD = cleanup.
    Cleanup ko finally me rakho warna exception pe wo skip ho jaayega."""
    import time

    info: dict[str, Any] = {"label": label}
    start = time.perf_counter()
    print(f"    setup: timer {label!r} start")
    try:
        yield info                        # `as info` me yahi dict jaata hai
    finally:
        # finally => exception aaye ya na aaye, elapsed hamesha measure hoga
        info["elapsed_ms"] = (time.perf_counter() - start) * 1000
        print(f"    cleanup: timer {label!r} -> {info['elapsed_ms']:.2f} ms")


def section2() -> None:
    print("\n=== SECTION 2: @contextmanager generator style (yield + try/finally) ===")

    with timer("clean-block") as t:
        total = sum(range(10_000))
        print(f"    work done, sum={total}")
    print(f"    timer dict after block: {t}")

    print("  ab exception ke saath (finally fir bhi chalega):")
    try:
        with timer("error-block"):
            raise RuntimeError("boom")
    except RuntimeError as e:
        print(f"    caught: {type(e).__name__}: {e}  (lekin cleanup upar chal chuka)")


# === SECTION 3: REAL — transactional CM (SAP HANA commit/rollback + close) ===
class FakeConnection:
    """SAP HANA / Postgres connection ka chhota stand-in. Real me ye driver
    object hota. Yahan sirf commit/rollback/close ka behaviour demo karte hain."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.log: list[str] = []
        self.closed = False

    def execute(self, sql: str) -> None:
        self.log.append(sql)
        print(f"      [{self.name}] exec: {sql}")

    def commit(self) -> None:
        print(f"      [{self.name}] COMMIT ({len(self.log)} stmts)")

    def rollback(self) -> None:
        print(f"      [{self.name}] ROLLBACK (undoing {len(self.log)} stmts)")

    def close(self) -> None:
        self.closed = True
        print(f"      [{self.name}] connection CLOSED")


@contextlib.contextmanager
def transaction(conn: FakeConnection) -> Iterator[FakeConnection]:
    """Atomic write CM — ye exact pattern Ashish ke SAP HANA connector me hai:
        - block bina exception -> COMMIT
        - koi bhi exception -> ROLLBACK, fir exception re-raise
        - dono case me connection CLOSE (leak na ho)
    Idempotent writes + retries ke liye ye atomicity foundation hai."""
    try:
        yield conn
    except Exception:
        conn.rollback()                   # partial state mat chhodo
        raise                             # error ko upar bhejo (chupao mat)
    else:
        conn.commit()                     # sirf clean path pe commit
    finally:
        conn.close()                      # GUARANTEED cleanup (try/except dono ke baad)


def section3() -> None:
    print("\n=== SECTION 3: REAL — transactional CM (SAP HANA commit/rollback/close) ===")

    print("  happy path (commit hona chahiye):")
    conn_ok = FakeConnection("HANA-1")
    with transaction(conn_ok) as c:
        c.execute("INSERT INTO gl_entries VALUES (...)")
        c.execute("UPDATE sync_state SET cursor='X'")
    print(f"    closed? {conn_ok.closed}")

    print("  failure path (rollback + close, error bubble up):")
    conn_bad = FakeConnection("HANA-2")
    try:
        with transaction(conn_bad) as c:
            c.execute("INSERT INTO gl_entries VALUES (...)")
            raise ConnectionError("HANA socket reset mid-write")
    except ConnectionError as e:
        print(f"    caught outside: {type(e).__name__}: {e}")
    print(f"    closed? {conn_bad.closed}  (rollback ke baad bhi close hua)")


# === SECTION 4: REAL — ExitStack (dynamic N resources) + contextlib.suppress ===
def section4() -> None:
    print("\n=== SECTION 4: REAL — ExitStack (dynamic count) + suppress ===")

    # ETL migration: kitni source files aayengi runtime pe pata nahi. Sabhi ko
    # ek hi `with` me kholo; ExitStack reverse order me sabko close karega.
    sources = ["customers.csv", "orders.csv", "invoices.csv"]

    print("  ExitStack se N connections ek block me:")
    with contextlib.ExitStack() as stack:
        conns = [
            stack.enter_context(transaction(FakeConnection(f"src:{name}")))
            for name in sources
        ]
        print(f"    opened {len(conns)} connections dynamically")
        for c in conns:
            c.execute("SELECT count(*)")
    print("  -> block khatm: ExitStack ne sabko REVERSE order me commit+close kiya")

    # contextlib.suppress: ek specific expected error ko narrowly ignore karo,
    # bare except ke bajaye. Jaise: optional cache delete jo na mile to chalega.
    print("  contextlib.suppress (sirf KeyError ignore, baaki nahi):")
    cache = {"user:1": "ashish"}
    with contextlib.suppress(KeyError):
        del cache["user:999"]             # missing key -> KeyError -> chup-chaap ignore
    print(f"    cache intact, no crash: {cache}")
    print("    NOTE: suppress ko tang scope me rakho — wide kiya to real bug chhup jaayega")


# === SECTION 5: REAL — tenant_context (Niroskos) + brief async with ===
_CURRENT_TENANT: dict[str, str | None] = {"id": None}


@contextlib.contextmanager
def tenant_context(tenant_id: str) -> Iterator[str]:
    """Niroskos multi-tenant SaaS: block ke andar ye tenant 'active' hai
    (schema / RLS / connection routing iske hisaab se). Block ke baad PURANA
    tenant restore — warna ek request ka tenant agle me leak kar jaaye (data leak)."""
    previous = _CURRENT_TENANT["id"]
    _CURRENT_TENANT["id"] = tenant_id
    print(f"    enter tenant_context: active={tenant_id!r} (prev={previous!r})")
    try:
        yield tenant_id
    finally:
        _CURRENT_TENANT["id"] = previous   # nested-safe restore
        print(f"    exit  tenant_context: restored active={previous!r}")


class AsyncResource:
    """Async CM — I/O-bound resource (aiohttp session, async DB pool) ke liye.
    `async with` __aenter__/__aexit__ ko await karta hai, sync wale ko nahi."""

    async def __aenter__(self) -> "AsyncResource":
        await asyncio.sleep(0)            # pretend await (connect)
        print("      __aenter__: async resource acquired")
        return self

    async def __aexit__(self, *exc: object) -> bool:
        await asyncio.sleep(0)            # pretend await (graceful close)
        print("      __aexit__:  async resource released")
        return False


async def _async_demo() -> None:
    async with AsyncResource():
        print("      inside async block (doing I/O)")


def section5() -> None:
    print("\n=== SECTION 5: REAL — tenant_context (Niroskos) + brief async with ===")

    print("  nested tenant scoping (restore order matters):")
    with tenant_context("acme"):
        print(f"    work-1 sees tenant: {_CURRENT_TENANT['id']!r}")
        with tenant_context("globex"):
            print(f"    work-2 sees tenant: {_CURRENT_TENANT['id']!r}")
        print(f"    back to: {_CURRENT_TENANT['id']!r}  (globex se acme restore)")
    print(f"  outside all: {_CURRENT_TENANT['id']!r}  (None — clean)")

    print("  async with (I/O-bound resource — __aenter__/__aexit__ awaited):")
    asyncio.run(_async_demo())


# === SECTION 6: BREAK IT / GOTCHA — __exit__ returning True swallows everything ===
class SilentExit:
    """GALAT: __exit__ se hamesha True return — har exception chup-chaap nigal
    jaayega. Ye sabse khatarnak CM bug hai: bug dikhta hi nahi, data corrupt
    hota rehta hai aur koi alert nahi aata."""

    def __enter__(self) -> "SilentExit":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return True                       # <- BUG: sab kuch suppress


class CorrectExit:
    """SAHI: by default False (ya None) return karo taaki exception propagate ho.
    Sirf tab True karo jab tum EK specific exception ko jaan-bujh ke handle kar
    rahe ho — aur tab bhi exc_type ko check karke decide karo."""

    def __enter__(self) -> "CorrectExit":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # sirf KeyError ko handle/suppress karo, baaki ko jaane do
        if exc_type is KeyError:
            print("      handled KeyError intentionally")
            return True
        return False


def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — __exit__ returning True swallows ALL errors ===")

    print("  WRONG (__exit__ always True):")
    with SilentExit():
        raise ValueError("real bug: balance went negative!")
    print("    ...code yahan tak pahunch gaya, ValueError GAYAB ho gaya (silent)")
    print("    -> production me ye sabse bura: corruption hota hai, exception kabhi")
    print("       surface nahi karti, alert/log kuch nahi — debugging nightmare.")

    print("  FIXED (return False by default, sirf chosen error suppress):")
    try:
        with CorrectExit():
            raise ValueError("ye propagate honi chahiye")
    except ValueError as e:
        print(f"    correctly propagated: {type(e).__name__}: {e}")

    with CorrectExit():
        raise KeyError("ye wala intentionally handle hota hai")
    print("    KeyError handle hua, baaki sab ab bhi raise hote hain")


# === SECTION 7: TODO — tum khud likho: @contextmanager distributed_lock(name) ===
_LOCKS_HELD: set[str] = set()


@contextlib.contextmanager
def distributed_lock(name: str) -> Iterator[str]:
    """
    TODO (tum implement karo):
      Ek @contextmanager banao jo Celery/Redis-style distributed lock model kare,
      module-level set `_LOCKS_HELD` ko fake Redis maan ke.
        - setup (yield se pehle):
            * agar name already _LOCKS_HELD me hai -> raise RuntimeError(
                  f"lock {name!r} already held")  (double-acquire block)
            * warna _LOCKS_HELD.add(name) aur print karo "acquired {name}"
        - yield name
        - cleanup (finally me — ZAROORI):
            * _LOCKS_HELD.discard(name) aur print "released {name}"
      finally hi use karna: taaki task crash/exception pe bhi lock RELEASE ho
      (warna stuck lock -> next worker hamesha block).
    Expected behaviour:
        with distributed_lock("invoice:42"):
            ...                       # andar "invoice:42" held
        # block ke baad released, dobara acquire ho sakta
      Aur agar same lock NESTED le (already held) -> RuntimeError aana chahiye.
    """
    raise NotImplementedError("TODO: distributed_lock ka body likho (try/finally)")


def section7() -> None:
    print("\n=== SECTION 7: TODO — @contextmanager distributed_lock(name) (tum likho) ===")

    try:
        with distributed_lock("invoice:42"):
            print(f"    inside lock, held = {_LOCKS_HELD}")
        print(f"    after block, held = {_LOCKS_HELD}  (release hona chahiye)")

        # nested same-name acquire -> RuntimeError expected
        with distributed_lock("invoice:42"):
            with distributed_lock("invoice:42"):
                pass
        print("    ERROR: double-acquire block hona chahiye tha!")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")
    except RuntimeError as e:
        print(f"  correct! double-acquire blocked: RuntimeError: {e}")
        print(f"  held after error = {_LOCKS_HELD} (finally ne cleanup kiya?)")


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
