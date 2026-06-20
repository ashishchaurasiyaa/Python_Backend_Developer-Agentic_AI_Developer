"""
================================================================================
TOPIC: Decorators (function wrappers, functools.wraps, parametrized & class-based)
================================================================================

KYA HOTA HAI:
    Decorator ek callable hai jo ek function (ya class) ko INPUT leta hai aur ek
    naya (usually wrapped) function return karta hai. "@dec" syntax sirf sugar
    hai — andar se ye bas  func = dec(func)  hota hai. Matlab original function
    ko ek aur layer me lapet do bina uska code chhede.

KYO NEED PADI:
    Cross-cutting concerns — retry, timing, caching, auth, logging, rate-limit —
    har function me dohraana padta to code duplicate + bekaar ho jaata. Decorator
    se "ek baar likho, jahan chahe @ laga do" — business logic clean rehti hai aur
    boilerplate ek jagah centralize ho jaata hai (DRY + separation of concerns).

KAISE USE KARTE HAIN:
    def dec(func): def wrapper(*a, **k): ...; return func(*a, **k); return wrapper.
    Wrapper ke upar @functools.wraps(func) lagao (warna naam/docstring kho jaate).
    Parametrized decorator = 3 layers: outer(config) -> middle(func) -> inner(*a).
    State chahiye to class-based decorator (__init__ me func, __call__ me logic).

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: flaky network call pe @retry(times=3, backoff=0.1) —
       transient failure pe exponential backoff ke saath dobara try, idempotent op.
    2. Niroskos multi-tenant Django: @require_role("admin") view pe — auth/permission
       check ek hi jagah, har view me if-else nahi.
    3. Celery/Redis pipeline: @timed se har task ki latency log karo (slow query hunt).
    4. Payment gateway: @cache se idempotency-key -> response memoize, double-charge se bacho.
    5. Rate limiter / circuit breaker: stateful class-based decorator (CountCalls style).

INTERVIEW ANSWER (English — recite this):
    "A decorator is a callable that takes a function and returns a replacement
    function, and the @ syntax is just sugar for func = decorator(func). I use them
    to factor out cross-cutting concerns — retries, timing, caching, auth — so the
    business logic stays clean and the policy lives in one place. The non-negotiable
    detail is functools.wraps on the wrapper: without it the wrapped function loses
    its __name__, __doc__, signature and __wrapped__, which breaks logging,
    introspection and tools like Sphinx and pytest. A parametrized decorator needs
    three layers — the outer factory takes the config, the middle layer takes the
    function, and the inner wrapper takes the call arguments — which is exactly how
    I build a retry-with-backoff decorator for our SAP HANA connector. When the
    decorator needs to keep state, such as a call counter or a rate limiter, I reach
    for a class-based decorator using __init__ and __call__. The senior gotcha is
    stacking order: decorators apply bottom-up at definition time, so the one
    closest to the function wraps first and the topmost runs first at call time."

================================================================================
Run:
    python 11_decorators.py          # saare sections chalao
    python 11_decorators.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — @ sugar = func=dec(func) + functools.wraps kyu mandatory
    2. DEMO  — parametrized 3-layer decorator + stacking order (bottom-up)
    3. REAL  — @retry(times, backoff) on a flaky SAP HANA call (idempotent)
    4. REAL  — @timed (latency log) + @cache (payment idempotency memoize)
    5. REAL  — class-based stateful decorator: CountCalls + @require_role auth
    6. BREAK — wraps bhool gaye: introspection toot-ti hai (galti + fix)
    7. TODO  — tum khud likho: @rate_limit(max_calls, per_seconds)
================================================================================
"""
from __future__ import annotations

import functools
import sys
import time
from typing import Any, Callable


# === SECTION 1: DEMO — @ sugar (func=dec(func)) + functools.wraps mandatory ===
def section1() -> None:
    print("\n=== SECTION 1: @ is just func = dec(func) + why functools.wraps ===")

    def shout(func: Callable[..., str]) -> Callable[..., str]:
        @functools.wraps(func)                 # identity copy: name/doc/signature
        def wrapper(*args: Any, **kwargs: Any) -> str:
            return func(*args, **kwargs).upper() + "!"
        return wrapper

    # @ ke bina, manually — yahi @ syntax andar karta hai
    def greet_plain(name: str) -> str:
        """greet kisi ko (plain)."""
        return f"hello {name}"

    greet_manual = shout(greet_plain)          # <- ye hi @shout hai
    print(f"  manual  shout(greet)('ashish') -> {greet_manual('ashish')!r}")

    # ab @ syntax se — bilkul same cheez
    @shout
    def greet(name: str) -> str:
        """greet kisi ko (decorated)."""
        return f"hi {name}"

    print(f"  @shout  greet('rahul')         -> {greet('rahul')!r}")

    # functools.wraps ka asar: identity preserve
    print(f"  greet.__name__ = {greet.__name__!r}  (wraps ke bina 'wrapper' aata)")
    print(f"  greet.__doc__  = {greet.__doc__!r}")
    # __wrapped__ se original tak pahunch sakte ho (debugging me kaam aata)
    print(f"  greet.__wrapped__ is original?  {greet.__wrapped__ is greet.__wrapped__}")


# === SECTION 2: DEMO — parametrized 3-layer decorator + stacking order ===
def section2() -> None:
    print("\n=== SECTION 2: parametrized (3-layer) decorator + stacking bottom-up ===")

    # 3 layers: outer(config) -> middle(func) -> inner(*args)
    def repeat(times: int) -> Callable[[Callable[..., Any]], Callable[..., list]]:
        def middle(func: Callable[..., Any]) -> Callable[..., list]:
            @functools.wraps(func)
            def inner(*args: Any, **kwargs: Any) -> list:
                return [func(*args, **kwargs) for _ in range(times)]
            return inner
        return middle

    @repeat(times=3)            # repeat(3) pehle chalta -> middle return hota -> @middle
    def ping() -> str:
        return "pong"

    print(f"  @repeat(times=3) ping() -> {ping()}")

    # ---- stacking order: bottom-up wrap, top-down run ----
    order: list[str] = []

    def tag(label: str) -> Callable[[Callable], Callable]:
        def middle(func: Callable) -> Callable:
            order.append(f"WRAP:{label}")          # definition time (bottom-up)
            @functools.wraps(func)
            def inner(*a: Any, **k: Any) -> Any:
                order.append(f"ENTER:{label}")     # call time (top-down)
                result = func(*a, **k)
                order.append(f"EXIT:{label}")
                return result
            return inner
        return middle

    @tag("A")                  # top
    @tag("B")                  # middle
    @tag("C")                  # bottom (function ke sabse paas) -> pehle wrap hota
    def work() -> str:
        order.append("BODY")
        return "done"

    print(f"  wrap order (definition): {[x for x in order if x.startswith('WRAP')]}")
    print("    -> bottom-up: C pehle wrap hua, A last (so A outermost)")
    order.clear()
    order.extend(["WRAP:A", "WRAP:B", "WRAP:C"][::-1])  # reset display baseline
    order.clear()
    work()
    print(f"  call order (runtime)   : {order}")
    print("    -> top-down: A pehle ENTER (outermost), C last; EXIT ulta")


# === SECTION 3: REAL — @retry(times, backoff) on a flaky SAP HANA call ===
def retry(times: int = 3, backoff: float = 0.05,
          exceptions: tuple[type[BaseException], ...] = (Exception,)
          ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Parametrized 3-layer retry with exponential backoff.
    SAP HANA jaisi transient network failure pe dobara try karta hai. Operation
    IDEMPOTENT honi chahiye (warna retry se duplicate side-effect)."""
    def middle(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def inner(*args: Any, **kwargs: Any) -> Any:
            delay = backoff
            last_exc: BaseException | None = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    print(f"    [retry] attempt {attempt}/{times} failed: {exc} "
                          f"-> sleeping {delay:.3f}s" if attempt < times
                          else f"    [retry] attempt {attempt}/{times} failed: {exc} (giving up)")
                    if attempt < times:
                        time.sleep(delay)
                        delay *= 2                  # exponential backoff
            assert last_exc is not None
            raise last_exc
        return inner
    return middle


def section3() -> None:
    print("\n=== SECTION 3: REAL — @retry on flaky SAP HANA call (idempotent) ===")

    state = {"calls": 0}

    @retry(times=3, backoff=0.05)
    def fetch_from_hana(table: str) -> dict[str, Any]:
        state["calls"] += 1
        # pehli 2 baar fail (transient), 3rd baar success — real flaky connector
        if state["calls"] < 3:
            raise ConnectionError(f"HANA socket reset (call #{state['calls']})")
        return {"table": table, "rows": 42, "served_on_attempt": state["calls"]}

    print("  calling fetch_from_hana('GL_ACCOUNTS'):")
    result = fetch_from_hana("GL_ACCOUNTS")
    print(f"  SUCCESS: {result}")

    # ab ek aisa case jo hamesha fail kare -> retries khatm -> exception bubble up
    @retry(times=2, backoff=0.02, exceptions=(ConnectionError,))
    def always_down() -> None:
        raise ConnectionError("HANA host unreachable")

    print("  calling always_down() (will exhaust retries):")
    try:
        always_down()
    except ConnectionError as e:
        print(f"  bubbled up after retries: {type(e).__name__}: {e}")


# === SECTION 4: REAL — @timed (latency) + @cache (payment idempotency memoize) ===
def timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """Latency log decorator — Celery task / slow query hunting me kaam aata."""
    @functools.wraps(func)
    def inner(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"    [timed] {func.__name__} took {elapsed_ms:.2f} ms")
    return inner


def cache(func: Callable[..., Any]) -> Callable[..., Any]:
    """Simple memoize keyed by args. Payment idempotency-key -> response,
    taaki same key pe dobara charge na ho (double-charge se bacho)."""
    store: dict[tuple, Any] = {}

    @functools.wraps(func)
    def inner(*args: Any, **kwargs: Any) -> Any:
        key = (args, tuple(sorted(kwargs.items())))
        if key in store:
            print(f"    [cache] HIT for {args} -> returning stored response")
            return store[key]
        print(f"    [cache] MISS for {args} -> computing")
        store[key] = func(*args, **kwargs)
        return store[key]
    inner.cache_clear = store.clear  # type: ignore[attr-defined]
    return inner


def section4() -> None:
    print("\n=== SECTION 4: REAL — @timed latency + @cache payment idempotency ===")

    charge_calls = {"n": 0}

    @timed
    @cache
    def charge_payment(idempotency_key: str, amount: int) -> dict[str, Any]:
        # @timed @cache stacked: @cache function ke paas (pehle wrap), @timed bahar.
        charge_calls["n"] += 1
        time.sleep(0.02)                      # pretend gateway round-trip
        return {"key": idempotency_key, "amount": amount, "charged": True,
                "gateway_hits": charge_calls["n"]}

    print("  first charge (idem-key 'pay_001'):")
    r1 = charge_payment("pay_001", 500)
    print(f"    -> {r1}")
    print("  RETRY same idem-key 'pay_001' (must NOT hit gateway again):")
    r2 = charge_payment("pay_001", 500)
    print(f"    -> {r2}")
    print(f"  actual gateway hits = {charge_calls['n']}  (1 expected, cache saved us)")


# === SECTION 5: REAL — class-based stateful decorator (CountCalls) + @require_role ===
class CountCalls:
    """Class-based decorator with STATE. __init__ me func pakdo, __call__ me
    har call count karo. Function-based me state nonlocal/closure se hota,
    class-based zyada readable jab state grow kare (metrics, circuit breaker)."""
    def __init__(self, func: Callable[..., Any]) -> None:
        functools.update_wrapper(self, func)   # wraps ka class-version (name/doc copy)
        self.func = func
        self.count = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.count += 1
        print(f"    [CountCalls] {self.func.__name__} call #{self.count}")
        return self.func(*args, **kwargs)


def require_role(role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Parametrized auth decorator — Niroskos multi-tenant Django view guard.
    Pehla arg ko 'user' (dict with 'role') maan ke check karta hai."""
    def middle(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def inner(user: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            if user.get("role") != role:
                raise PermissionError(
                    f"{func.__name__}: requires role={role!r}, "
                    f"user has {user.get('role')!r}")
            return func(user, *args, **kwargs)
        return inner
    return middle


def section5() -> None:
    print("\n=== SECTION 5: REAL — class-based CountCalls (state) + @require_role auth ===")

    @CountCalls
    def sync_tenant(tenant_id: str) -> str:
        return f"synced:{tenant_id}"

    sync_tenant("acme")
    sync_tenant("globex")
    sync_tenant("acme")
    print(f"  total invocations tracked on decorator object = {sync_tenant.count}")
    print(f"  name preserved via update_wrapper? __name__={sync_tenant.__name__!r}")

    @require_role("admin")
    def delete_tenant(user: dict[str, Any], tenant_id: str) -> str:
        return f"deleted:{tenant_id}"

    admin = {"id": 1, "role": "admin"}
    member = {"id": 2, "role": "member"}
    print(f"  admin  deletes -> {delete_tenant(admin, 'acme')}")
    try:
        delete_tenant(member, "acme")
    except PermissionError as e:
        print(f"  member blocked -> PermissionError: {e}")


# === SECTION 6: BREAK IT / GOTCHA — functools.wraps bhool jaana ===
def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — forgetting functools.wraps breaks introspection ===")

    # ---- GALAT: wraps nahi lagaya ----
    def bad_log(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """main wrapper hoon, asli function nahi."""
            return func(*args, **kwargs)
        return wrapper

    @bad_log
    def create_invoice(tenant: str) -> str:
        """Niroskos ke liye invoice banata hai."""
        return f"invoice:{tenant}"

    print("  WRONG (no functools.wraps):")
    print(f"    __name__ = {create_invoice.__name__!r}   <- expected 'create_invoice'")
    print(f"    __doc__  = {create_invoice.__doc__!r}")
    print(f"    has __wrapped__? {hasattr(create_invoice, '__wrapped__')}")
    print("    -> logging 'wrapper' dikhayega, Sphinx/pytest galat naam pakdenge,")
    print("       aur ek dispatch table jo func.__name__ pe key kare wo tut jaayega.")

    # ---- SAHI: wraps laga diya ----
    def good_log(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        return wrapper

    @good_log
    def create_invoice2(tenant: str) -> str:
        """Niroskos ke liye invoice banata hai."""
        return f"invoice:{tenant}"

    print("  FIXED (with functools.wraps):")
    print(f"    __name__ = {create_invoice2.__name__!r}")
    print(f"    __doc__  = {create_invoice2.__doc__!r}")
    print(f"    has __wrapped__? {hasattr(create_invoice2, '__wrapped__')}  "
          f"(original tak pahunch + sneaky double-decoration detect)")


# === SECTION 7: TODO — tum khud likho: @rate_limit(max_calls, per_seconds) ===
def rate_limit(max_calls: int, per_seconds: float
               ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    TODO (tum implement karo):
      Ek PARAMETRIZED (3-layer) decorator banao jo ek function ko per_seconds ke
      sliding window me max max_calls tak hi chalne de.
        - outer: rate_limit(max_calls, per_seconds) -> middle return kare
        - middle: func le -> inner return kare (functools.wraps zaroor lagao)
        - inner: ek list me call ke timestamps (time.monotonic()) rakho;
                 purane (window ke bahar) timestamps hata do;
                 agar len(timestamps) >= max_calls  -> raise RuntimeError(
                     f"{func.__name__}: rate limit {max_calls}/{per_seconds}s exceeded")
                 warna ab ka timestamp append karo aur func(*args, **kwargs) return karo.
      Expected behaviour (max_calls=2, per_seconds=60):
          @rate_limit(2, 60)
          def hit(): return "ok"
          hit(); hit()      -> dono "ok"
          hit()             -> RuntimeError (3rd call blocked, window me 2 ho chuke)
      Hint: timestamps ko closure variable (middle me list) me rakho — har
      decorated function ki apni alag list honi chahiye (CountCalls jaisa state).
    """
    raise NotImplementedError("TODO: rate_limit ka 3-layer body likho")


def section7() -> None:
    print("\n=== SECTION 7: TODO — @rate_limit(max_calls, per_seconds) (tum likho) ===")

    try:
        @rate_limit(2, 60)
        def hit() -> str:
            return "ok"

        print(f"  call 1 -> {hit()}")
        print(f"  call 2 -> {hit()}")
        print(f"  call 3 -> {hit()}   (ye RuntimeError hona chahiye)")
        print("  ERROR: 3rd call block hona chahiye tha!")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")
    except RuntimeError as e:
        print(f"  correct! rate limited: RuntimeError: {e}")


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
