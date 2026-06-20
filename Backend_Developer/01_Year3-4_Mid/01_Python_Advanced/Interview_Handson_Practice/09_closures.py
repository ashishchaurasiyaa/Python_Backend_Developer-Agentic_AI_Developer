"""
================================================================================
TOPIC: Closures (functions that remember their enclosing scope)
================================================================================

KYA HOTA HAI:
    Closure ek inner function hai jo apne enclosing (outer) function ke variables
    ko "yaad" rakhta hai — even after outer function return ho chuka ho. Python
    in captured variables ko "cell" objects me store karta hai, aur unhe
    inner_func.__closure__ tuple ke through dekha ja sakta hai. Closure = function
    code + uske saath bandha hua environment (free variables).

KYO NEED PADI:
    Bina closure ke har baar config/state pass karna padta — ya global variables
    use karne padte (which is messy aur thread-unsafe). Closure ek clean tarika
    hai chhota private state carry karne ka, bina poori class banaye. Decorators,
    callbacks, function factories — sab closures pe khade hain.

KAISE USE KARTE HAIN:
    Outer function ke andar inner function define karo jo outer ke variable ko
    reference kare, phir inner function ko RETURN kar do. Agar inner ko us captured
    variable ko REASSIGN karna ho (sirf read nahi), to `nonlocal x` likho — warna
    Python use naya local maan lega aur enclosing wale ko touch nahi karega.

KAHAN USE HOTA HAI (backend scenarios):
    1. Configurable function factory: SAP HANA retry wrapper jo (max_retries,
       backoff) ko capture kare aur har call pe wahi config use kare.
    2. Decorator state: rate limiter / call-counter / per-tenant cache jo state
       closure me rakhe bina global ya class banaye.
    3. Niroskos multi-tenant: tenant_id ko closure me bind karke "tenant-scoped"
       query/logger function banana.
    4. Celery/Redis: callback functions jo job-context (job_id, retries left)
       capture karte hain.
    5. Payment idempotency: ek "once" guard closure jo seen-keys ka set capture
       kare aur duplicate charge block kare.

INTERVIEW ANSWER (English — recite this):
    "A closure is a nested function that captures and remembers variables from its
    enclosing scope, so it stays bound to that environment even after the outer
    function has returned. Internally Python stores these free variables as cell
    objects, which you can inspect via the function's __closure__ attribute and
    its __code__.co_freevars. By default the inner function can only read these
    variables; to rebind one I use the nonlocal keyword, otherwise Python treats
    the assignment as creating a new local. The classic gotcha is late binding in
    a loop: closures capture the variable, not its value at definition time, so a
    list of lambdas built in 'for i in range(3)' all return 2 because they share
    the same 'i' and read it only when called. The fix is to bind the current
    value eagerly, usually with a default argument 'lambda i=i: i', or by using a
    factory function. In production I lean on closures for configurable function
    factories and for holding small decorator state like counters or rate-limit
    windows, where a full class would be overkill."

================================================================================
Run:
    python 09_closures.py          # saare sections chalao
    python 09_closures.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — closure remembers enclosing scope (counter without globals)
    2. DEMO  — nonlocal: read-only capture vs rebind, + __closure__ cell inspection
    3. REAL  — configurable function factory: SAP HANA retry wrapper (closure config)
    4. REAL  — decorator state: per-tenant call-counter / rate limiter via closure
    5. BREAK — late-binding loop gotcha ([lambda: i] => all 2) + default-arg fix
    6. TODO  — tum khud likho: idempotency 'once' guard closure (payment dedupe)
================================================================================
"""
from __future__ import annotations

import sys
import time
from typing import Any, Callable


# === SECTION 1: DEMO — closure remembers enclosing scope (counter, no globals) ===
def section1() -> None:
    print("\n=== SECTION 1: closure remembers enclosing scope ===")

    def make_counter(start: int) -> Callable[[], int]:
        count = start  # <- free variable, enclosing scope me rehta hai

        def increment() -> int:
            # 'count' ko sirf READ kar rahe (nonlocal abhi nahi chahiye kyunki
            # hum yahan += nahi kar rahe — niche section 2 me wo dikhayenge).
            return count

        # increment 'count' ko yaad rakhega bhale hi make_counter return kar de
        return increment

    c1 = make_counter(10)
    c2 = make_counter(100)
    # Dono apna ALAG environment carry karte hain — state share nahi hota
    print(f"  c1() -> {c1()}   (captured start=10)")
    print(f"  c2() -> {c2()}   (captured start=100)")
    print("  make_counter return ho chuka, phir bhi 'count' zinda hai (closure).")


# === SECTION 2: DEMO — nonlocal (read vs rebind) + __closure__ cell inspection ===
def section2() -> None:
    print("\n=== SECTION 2: nonlocal + __closure__ cell inspection ===")

    # ---- Bina nonlocal: rebind karne ki koshish -> UnboundLocalError ----
    def broken_counter() -> Callable[[], int]:
        count = 0

        def step() -> int:
            # count += 1  ko Python dekhte hi 'count' ko LOCAL maan leta hai,
            # par abhi tak assign nahi hua -> read karne pe UnboundLocalError.
            count += 1  # type: ignore[misc]
            return count

        return step

    try:
        broken_counter()()
    except UnboundLocalError as e:
        print(f"  bina nonlocal, rebind -> UnboundLocalError: {e}")

    # ---- nonlocal ke saath: ab rebind allowed hai, real stateful counter ----
    def good_counter() -> Callable[[], int]:
        count = 0

        def step() -> int:
            nonlocal count  # <- enclosing 'count' ko hi modify karo, naya local nahi
            count += 1
            return count

        return step

    cnt = good_counter()
    print(f"  nonlocal counter: {cnt()}, {cnt()}, {cnt()}  (state persist karta hai)")

    # ---- __closure__ cell inspection: dikhao Python kaise capture karta hai ----
    print(f"  step.__code__.co_freevars = {cnt.__code__.co_freevars}")
    cells = cnt.__closure__ or ()
    print(f"  step.__closure__ has {len(cells)} cell(s)")
    for name, cell in zip(cnt.__code__.co_freevars, cells):
        # cell.cell_contents = us free variable ki CURRENT value
        print(f"    cell for {name!r} -> cell_contents = {cell.cell_contents}")
    print("  Note: ek normal (non-closure) function ka __closure__ None hota hai.")
    print(f"  section2.__closure__ is None? {section2.__closure__ is None}")


# === SECTION 3: REAL — configurable function factory (SAP HANA retry wrapper) ===
def section3() -> None:
    print("\n=== SECTION 3: configurable retry factory (SAP HANA style) ===")

    def make_retrier(
        max_retries: int, backoff: float
    ) -> Callable[[Callable[[], Any]], Any]:
        """Config (max_retries, backoff) ko closure me CAPTURE karte hain.
        Returned 'run' function har baar wahi config use karega — bina globals,
        bina class. Yahi 'configurable function factory' pattern hai."""

        def run(operation: Callable[[], Any]) -> Any:
            attempt = 0
            while True:
                attempt += 1
                try:
                    return operation()
                except RuntimeError as e:
                    if attempt > max_retries:  # captured config
                        print(f"    giving up after {attempt} attempts")
                        raise
                    # backoff capped chhota rakha (test fast rahe)
                    delay = min(backoff * attempt, 0.05)
                    print(f"    attempt {attempt} failed ({e}); retry in {delay:.3f}s")
                    time.sleep(delay)

        return run

    # Do alag-alag policy, dono apni config closure me rakhte hain
    hana_retry = make_retrier(max_retries=3, backoff=0.01)
    strict_retry = make_retrier(max_retries=1, backoff=0.01)

    # Ek flaky SAP HANA call simulate karo: pehli 2 baar fail, phir success
    state = {"calls": 0}

    def flaky_hana_call() -> str:
        state["calls"] += 1
        if state["calls"] < 3:
            raise RuntimeError("HANA connection reset")
        return "HANA rows fetched OK"

    print("  hana_retry (max_retries=3):")
    print(f"    result -> {hana_retry(flaky_hana_call)}")

    # strict_retry sirf 1 retry deta hai -> ye fail karega
    state["calls"] = 0
    print("  strict_retry (max_retries=1) on same flaky call:")
    try:
        strict_retry(flaky_hana_call)
    except RuntimeError as e:
        print(f"    surfaced error: {type(e).__name__}: {e}")
    print("  Same factory, do alag closures, do alag policies — zero globals.")


# === SECTION 4: REAL — decorator state via closure (per-tenant counter / limiter) ===
def section4() -> None:
    print("\n=== SECTION 4: decorator state in a closure (rate limiter) ===")

    def rate_limited(max_calls: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator jo per-tenant call count closure me rakhta hai.
        State (seen calls) na global hai na class — bas closure ke andar dict."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            calls_by_tenant: dict[str, int] = {}  # <- captured state, per-function

            def wrapper(tenant_id: str, *args: Any, **kwargs: Any) -> Any:
                n = calls_by_tenant.get(tenant_id, 0) + 1
                calls_by_tenant[tenant_id] = n
                if n > max_calls:
                    raise RuntimeError(
                        f"rate limit exceeded for tenant {tenant_id!r} "
                        f"({n} > {max_calls})"
                    )
                return func(tenant_id, *args, **kwargs)

            # state ko bahar se inspect karne ke liye expose (debugging me kaam aata)
            wrapper._calls_by_tenant = calls_by_tenant  # type: ignore[attr-defined]
            return wrapper

        return decorator

    @rate_limited(max_calls=2)
    def fetch_invoices(tenant_id: str) -> str:
        return f"invoices for {tenant_id}"

    print("  Niroskos-style per-tenant rate limiting (max_calls=2):")
    for i in range(1, 4):
        try:
            out = fetch_invoices("acme")
            print(f"    call {i} (acme): {out}")
        except RuntimeError as e:
            print(f"    call {i} (acme): BLOCKED -> {e}")
    # Doosra tenant apna alag counter rakhta hai (state isolated in same closure dict)
    print(f"    call 1 (globex): {fetch_invoices('globex')}")
    print(f"  captured state -> {fetch_invoices._calls_by_tenant}")  # type: ignore[attr-defined]
    print("  State closure me jeevit hai calls ke beech — koi global/class nahi.")


# === SECTION 5: BREAK IT / GOTCHA — late-binding loop ([lambda: i] => all 2) ===
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — late-binding loop closure gotcha ===")

    # ---- GALAT: closures 'i' ko VALUE se nahi, VARIABLE se capture karte hain ----
    bad_funcs: list[Callable[[], int]] = []
    for i in range(3):
        bad_funcs.append(lambda: i)  # BUG: sab same 'i' share karte hain

    # Loop ke baad i == 2. Har lambda CALL hone par hi 'i' read karta hai,
    # isliye sab 2 return karte hain — definition ke time ka 0/1/2 nahi.
    print("  WRONG (late binding):")
    print(f"    [f() for f in bad_funcs] = {[f() for f in bad_funcs]}   <- expected [0, 1, 2]")
    print("    Reason: lambda ne value 0/1/2 capture nahi ki — wahi shared 'i' capture kiya,")
    print("    aur call ke waqt i ki final value (2) padhi.")

    # ---- FIX 1: default argument se CURRENT value ko eagerly bind karo ----
    fixed_default: list[Callable[[], int]] = []
    for i in range(3):
        fixed_default.append(lambda i=i: i)  # default arg = define-time pe evaluate

    print("  FIX 1 (default arg 'lambda i=i: i' binds value now):")
    print(f"    {[f() for f in fixed_default]}   <- correct [0, 1, 2]")

    # ---- FIX 2: factory function — har iteration ka apna naya scope/cell ----
    def make(n: int) -> Callable[[], int]:
        return lambda: n  # 'n' har call me alag, kyunki naya enclosing frame

    fixed_factory = [make(i) for i in range(3)]
    print("  FIX 2 (factory gives each closure its own cell):")
    print(f"    {[f() for f in fixed_factory]}   <- correct [0, 1, 2]")
    print("  Lesson: closures bind to the VARIABLE, not the value — eager-bind karo.")


# === SECTION 6: TODO — tum khud likho: idempotency 'once' guard closure ===
def make_once_guard() -> Callable[[str], bool]:
    """
    TODO (tum implement karo):
      Ek closure-based 'once guard' banao jo payment idempotency ke liye kaam aaye.
      - Outer function ek empty set `seen` rakhe (captured state).
      - Inner function `seen_before(key: str) -> bool` return karo jo:
            * agar key PEHLE aa chuki hai  -> True return kare (duplicate / skip)
            * agar key NAYI hai            -> use seen me add kare aur False return kare
      - 'seen' ko closure me hi rakho (na global, na argument) — state persist ho.
      Expected behaviour:
          guard = make_once_guard()
          guard("txn-1")  -> False   (pehli baar, process karo)
          guard("txn-1")  -> True    (duplicate, charge skip karo)
          guard("txn-2")  -> False
      Hint: set ko sirf read+mutate kar rahe (add) — reassign nahi — to nonlocal
            ki zaroorat NAHI; sirf set.add() se kaam chal jaayega.
    """
    raise NotImplementedError("TODO: closure-based once-guard implement karo (seen set capture karo)")


def section6() -> None:
    print("\n=== SECTION 6: TODO — idempotency 'once' guard closure (tum likho) ===")
    try:
        guard = make_once_guard()
        r1 = guard("txn-1")
        r2 = guard("txn-1")
        r3 = guard("txn-2")
        print(f"  guard('txn-1') first  -> {r1}  (expected False)")
        print(f"  guard('txn-1') again  -> {r2}  (expected True  = duplicate)")
        print(f"  guard('txn-2')        -> {r3}  (expected False)")
        if (r1, r2, r3) == (False, True, False):
            print("  correct! duplicate payment dedupe via closure state works.")
        else:
            print("  output galat hai — logic dobara dekho.")
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
