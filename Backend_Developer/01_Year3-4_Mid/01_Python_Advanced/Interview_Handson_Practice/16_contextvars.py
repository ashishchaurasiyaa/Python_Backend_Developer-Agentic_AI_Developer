"""
================================================================================
TOPIC: contextvars (async-safe context-local state)
================================================================================

KYA HOTA HAI:
    contextvars module deta hai ContextVar — ek variable jo "context-local" hota
    hai, yaani uski value current execution context (thread + asyncio task) ke
    saath bandhi hoti hai. set() value rakhta hai, get() padhta hai, aur set()
    ek Token deta hai jise reset() me pass karke purani value wapas la sakte ho.
    Har asyncio Task apna context COPY karke chalta hai — isliye state per-task
    isolate rehta hai, bhale hi saare tasks ek hi thread pe chal rahe hon.

KYO NEED PADI:
    Web backend me har request ke saath kuchh "ambient" data carry karna padta
    hai — request_id, current_user, tenant_id, trace_id — bina inhe har function
    me argument banaye. Pehle log threading.local() use karte the, par asyncio me
    ek hi thread pe kai tasks concurrently chalte hain, to thread-local saare
    tasks me LEAK ho jaata hai (ek request ka user dusre ki request me dikh jaata).
    contextvars exactly is problem ko solve karta hai — per-task isolation.

KAISE USE KARTE HAIN:
    Module level pe `var = ContextVar("name", default=...)` declare karo. Request
    aate hi middleware me `token = var.set(value)`, kaam khatam hone pe
    `var.reset(token)`. Beech me kahin se bhi (deep nested function, logging
    filter) `var.get()` se wahi value mil jaati hai — argument pass kiye bina.
    asyncio me copy_context()/Task automatically context snapshot leta hai.

KAHAN USE HOTA HAI (backend scenarios):
    1. Request-id / correlation-id propagation: middleware request_id set kare,
       structured logger har line me usse attach kare (distributed tracing).
    2. Niroskos multi-tenant Django/ASGI: current tenant_id ko context me rakhna
       taaki ORM queries aur cache keys automatically tenant-scoped ho.
    3. current_user: auth middleware user set kare, audit/permission code get kare
       bina har layer me user object pass kiye.
    4. SAP HANA connector: trace_id ko retry/idempotency logs me carry karna taaki
       ek logical operation ke saare attempts ek hi id se correlate ho.
    5. Celery/async pipelines: per-task job_id/trace_id isolate rakhna jab kai
       coroutines ek event loop par concurrently chal rahe ho.

INTERVIEW ANSWER (English — recite this):
    "contextvars provides context-local state through ContextVar objects, which I
    use to propagate ambient request data like request-id, current-user, and
    trace-id without threading them through every function signature. You set a
    value with set(), which returns a Token, read it anywhere with get(), and
    restore the previous value with reset(token) — typically in a finally block in
    middleware. The key reason it exists is asyncio: with threading.local, many
    coroutines share one thread, so context-local state set by one task leaks into
    another and you get the wrong user or tenant in concurrent requests. ContextVar
    is isolated per task because every asyncio Task runs in a copied context, so
    each request keeps its own value even on a single thread. The senior nuance is
    that copying is shallow and propagation is structured: a child task inherits a
    snapshot of the parent's context at creation time, but a value the child sets
    afterwards does NOT flow back to the parent, and a value the parent changes
    later is not seen by an already-running child. The classic correlation-id
    pattern is a logging.Filter that pulls request_id from a ContextVar so every
    log line is automatically tagged, which is what makes structured logs joinable
    across a distributed system."

================================================================================
Run:
    python 16_contextvars.py          # saare sections chalao
    python 16_contextvars.py 1 5      # sirf section 1 aur 5

Sections:
    1. DEMO  — ContextVar set/get/reset + Token (default, restore old value)
    2. DEMO  — per-task isolation: ek hi thread, do asyncio tasks, alag values
    3. BREAK — threading.local asyncio me LEAK karta hai; contextvars FIX karta hai
    4. REAL  — request_id + structured logging correlation (logging.Filter)
    5. REAL  — multi-tenant + trace_id propagation (SAP HANA retry style)
    6. TODO  — tum khud likho: current_user context manager (set on enter, reset on exit)
================================================================================
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from contextvars import ContextVar, copy_context
from typing import Optional


# === SECTION 1: DEMO — ContextVar set/get/reset + Token ===
def section1() -> None:
    print("\n=== SECTION 1: ContextVar set/get/reset + Token ===")

    # default diya hai, to set se pehle bhi get safe hai (LookupError nahi aayega)
    request_id: ContextVar[str] = ContextVar("request_id", default="-")

    print(f"  before any set, get() -> {request_id.get()!r}  (default fallback)")

    # set() ek Token return karta hai — ye purani value ko yaad rakhta hai
    token = request_id.set("req-123")
    print(f"  after set('req-123'), get() -> {request_id.get()!r}")
    print(f"  token.old_value -> {token.old_value!r}  (jo value pehle thi)")

    # reset(token) se exactly wahi purani value wapas aati hai (LIFO restore)
    request_id.reset(token)
    print(f"  after reset(token), get() -> {request_id.get()!r}  (back to default)")

    # default NA dene par, set se pehle get -> LookupError (ye senior gotcha hai)
    no_default: ContextVar[str] = ContextVar("no_default")
    try:
        no_default.get()
    except LookupError as e:
        print(f"  no-default var get() before set -> LookupError: {type(e).__name__}")
    print("  Lesson: production me hamesha default do, ya get(fallback) use karo.")


# === SECTION 2: DEMO — per-task isolation (ek thread, do asyncio tasks) ===
def section2() -> None:
    print("\n=== SECTION 2: per-task isolation (single thread, asyncio tasks) ===")

    user: ContextVar[str] = ContextVar("user", default="anon")

    async def handle(name: str) -> str:
        # har task apne context me set karta hai
        user.set(name)
        # await pe control dusre task ko jaata hai (interleave) — phir bhi
        # wapas aane par HAMARI value intact rehti hai, dusre ki leak nahi hoti
        await asyncio.sleep(0.01)
        seen = user.get()
        print(f"    task for {name!r}: user.get() -> {seen!r} "
              f"({'OK isolated' if seen == name else 'LEAK!'})")
        return seen

    async def driver() -> None:
        # gather do tasks concurrently — dono ek hi thread, ek hi event loop pe
        tid = threading.get_ident()
        print(f"  both tasks run on the SAME thread id={tid}")
        await asyncio.gather(handle("alice"), handle("bob"))

    asyncio.run(driver())
    print("  Ek hi thread, par har Task apna context copy leke chalta hai -> isolation.")


# === SECTION 3: BREAK IT / GOTCHA — threading.local LEAKS under asyncio ===
def section3() -> None:
    print("\n=== SECTION 3: BREAK IT — threading.local leaks in asyncio ===")

    # ---- GALAT: threading.local ek hi thread ke saare tasks me SHARE ho jaata ----
    tl = threading.local()

    async def bad_handle(name: str) -> str:
        tl.user = name            # think: "request ka user set kiya"
        await asyncio.sleep(0.01)  # yahan dusra task chal padta hai aur tl.user badal deta hai
        return tl.user             # ab galat user mil sakta hai

    async def bad_driver() -> list[str]:
        # dono tasks ek thread pe — tl.user shared hai, isliye LEAK
        return await asyncio.gather(bad_handle("alice"), bad_handle("bob"))

    bad = asyncio.run(bad_driver())
    print("  WRONG (threading.local under asyncio):")
    print(f"    expected ['alice', 'bob'], got {bad}")
    print("    Reason: ek hi thread pe dono tasks chal rahe -> tl.user dono ke "
          "beech share, last writer (bob) jeet gaya.")

    # ---- SAHI: ContextVar har task ka apna copied context use karta hai ----
    user: ContextVar[str] = ContextVar("user", default="anon")

    async def good_handle(name: str) -> str:
        user.set(name)
        await asyncio.sleep(0.01)
        return user.get()

    async def good_driver() -> list[str]:
        return await asyncio.gather(good_handle("alice"), good_handle("bob"))

    good = asyncio.run(good_driver())
    print("  FIX (contextvars.ContextVar):")
    print(f"    expected ['alice', 'bob'], got {good}")
    print("  Lesson: asyncio me thread-local mat use karo for per-request state — "
          "ContextVar lo, kyunki tasks thread share karte hain, context nahi.")


# === SECTION 4: REAL — request_id + structured logging correlation ===
def section4() -> None:
    print("\n=== SECTION 4: request_id -> structured logging correlation id ===")

    # global context var jo har request pe set hoga
    request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

    # logging.Filter jo har LogRecord pe request_id chipka deta hai context se.
    # Yahi production correlation-id ka core idea hai: log call me id pass nahi
    # karni padti, filter ContextVar se khud uthata hai.
    class RequestIdFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.request_id = request_id_var.get()
            return True

    logger = logging.getLogger("section4.demo")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("    [req=%(request_id)s] %(message)s"))
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)

    def charge_payment(amount: int) -> None:
        # deep service-layer function — yahan request_id KAHIN pass nahi hua,
        # phir bhi log line me correctly aayega (ambient via ContextVar).
        logger.info("charging payment amount=%d", amount)

    def handle_request(req_id: str, amount: int) -> None:
        # middleware-style: request aate hi set, finally me reset (clean teardown)
        token = request_id_var.set(req_id)
        try:
            logger.info("request received")
            charge_payment(amount)
        finally:
            request_id_var.reset(token)

    handle_request("req-AAA", 500)
    handle_request("req-BBB", 999)
    logger.info("outside any request")  # ab default '-' dikhega
    print("  Har line apne request ke id se tagged hai — bina id ko thread karke "
          "har function me bhejen. Distributed tracing isi pe khada hai.")


# === SECTION 5: REAL — multi-tenant + trace_id propagation (SAP HANA retry) ===
def section5() -> None:
    print("\n=== SECTION 5: multi-tenant + trace_id propagation (HANA retry) ===")

    tenant_var: ContextVar[str] = ContextVar("tenant")
    trace_var: ContextVar[str] = ContextVar("trace_id", default="-")

    def _log(msg: str) -> None:
        # ambient tenant + trace_id context se uthao — caller pass nahi karta
        print(f"    [tenant={tenant_var.get()} trace={trace_var.get()}] {msg}")

    def hana_query(sql: str, max_retries: int = 2) -> str:
        # SAP HANA connector style: idempotent retry. SAARE attempts ek hi
        # trace_id se correlate honge, taaki logs me ek logical op jud jaaye.
        attempt = 0
        while True:
            attempt += 1
            _log(f"attempt {attempt}: {sql}")
            if attempt <= max_retries and "FLAKY" in sql:
                _log(f"attempt {attempt} failed (HANA reset), retrying...")
                continue
            return f"rows for {tenant_var.get()}"

    def run_request(tenant: str, trace_id: str, sql: str) -> str:
        # middleware boundary: dono context vars set karo, finally me reset
        t1 = tenant_var.set(tenant)
        t2 = trace_var.set(trace_id)
        try:
            _log("request start")
            result = hana_query(sql)
            _log(f"request done -> {result}")
            return result
        finally:
            trace_var.reset(t2)
            tenant_var.reset(t1)

    run_request("acme", "trace-001", "SELECT * FROM FLAKY_TABLE")
    run_request("globex", "trace-002", "SELECT * FROM invoices")
    print("  Notice: tenant aur trace_id automatically har retry/log line me "
          "carry hue — connector code ne unhe explicitly pass nahi kiya.")


# === SECTION 6: TODO — tum khud likho: current_user context manager ===
current_user_var: ContextVar[str] = ContextVar("current_user", default="anonymous")


class use_current_user:  # noqa: N801 (context manager convention me lowercase rakha)
    """
    TODO (tum implement karo):
      Ek context manager banao jo `current_user_var` ko enter pe set kare aur
      exit pe reset kare — exactly middleware/auth boundary jaisa.
      - __init__(self, username): username store kar lo.
      - __enter__: current_user_var.set(self.username) karo, returned Token ko
        self._token me rakho, aur self return karo.
      - __exit__: current_user_var.reset(self._token) karo (purani value restore),
        return None/False (exception suppress mat karo).
      Expected behaviour:
          print(current_user_var.get())        # 'anonymous'
          with use_current_user("ashish"):
              print(current_user_var.get())     # 'ashish'
              with use_current_user("admin"):
                  print(current_user_var.get()) # 'admin'  (nested override)
              print(current_user_var.get())     # 'ashish' (inner reset ho gaya)
          print(current_user_var.get())         # 'anonymous' (bahar reset)
      Hint: set() ka Token sambhal ke rakho — reset(token) se LIFO restore milta hai,
            isliye nesting bilkul saaf chalta hai.
    """

    def __init__(self, username: str) -> None:
        self.username = username

    def __enter__(self) -> "use_current_user":
        raise NotImplementedError(
            "TODO: current_user_var.set(...) karo, token store karo, self return karo"
        )

    def __exit__(self, *exc: object) -> Optional[bool]:
        raise NotImplementedError("TODO: current_user_var.reset(self._token) karo")


def section6() -> None:
    print("\n=== SECTION 6: TODO — current_user context manager (tum likho) ===")
    try:
        before = current_user_var.get()
        with use_current_user("ashish"):
            outer = current_user_var.get()
            with use_current_user("admin"):
                inner = current_user_var.get()
            back_to_outer = current_user_var.get()
        after = current_user_var.get()
        print(f"  before              -> {before!r}  (expected 'anonymous')")
        print(f"  inside ashish       -> {outer!r}  (expected 'ashish')")
        print(f"  inside nested admin -> {inner!r}  (expected 'admin')")
        print(f"  after nested exit   -> {back_to_outer!r}  (expected 'ashish')")
        print(f"  after all exit      -> {after!r}  (expected 'anonymous')")
        if (before, outer, inner, back_to_outer, after) == (
            "anonymous", "ashish", "admin", "ashish", "anonymous",
        ):
            print("  correct! set-on-enter / reset-on-exit with nesting works.")
        else:
            print("  output galat hai — set/reset (Token) logic dobara dekho.")
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
    # copy_context import use ho — yahan ek chhota note ke liye reference rakha;
    # asyncio internally har Task ke liye yahi copy_context() use karta hai.
    _ = copy_context  # (documentation hook; sections asyncio.run se context handle karte hain)
    main()
