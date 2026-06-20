"""
================================================================================
TOPIC: Lambda Functions (anonymous single-expression functions)
================================================================================

KYA HOTA HAI:
    Lambda ek chhota, anonymous (bina naam ke) function hai jo SIRF ek single
    expression le sakta hai aur uska result implicitly return karta hai. Syntax:
        lambda arg1, arg2: <expression>
    Ye bilkul ek normal `def` jaisa hi function object banata hai — bas inline,
    ek line me, aur uska __name__ '<lambda>' hota hai.

KYO NEED PADI:
    Bahut jagah hume ek chhoti, throwaway function chahiye hoti hai jo bas kahin
    PASS karni hai — jaise sorted() ko batana ki kis cheez pe sort karna hai.
    Uske liye ek poora `def` likhna aur naam dena overkill lagta hai. Lambda us
    callable ko usi line pe define kar deta hai jahan use karna hai, code paas-paas
    rehta hai (locality), naam ka pollution nahi hota.

KAISE USE KARTE HAIN:
    Sabse common: key= argument me — sorted/min/max/heapq/itertools.groupby.
    `sorted(users, key=lambda u: u.created_at)`. Ek aur common jagah: small
    callbacks/adapters (DRF default=, Django ORM ke saath, defaultdict ka factory).
    Rule: agar logic ek saaf single expression hai aur turant consume ho raha hai
    to lambda; warna naam wala `def` likho.

KAHAN USE HOTA HAI (backend scenarios):
    1. Niroskos SaaS me API response sort/group: `sorted(invoices, key=lambda i:
       (i.tenant_id, -i.amount))` — multi-key sorting, tenant ke andar amount desc.
    2. DRF serializer field: `default=lambda: uuid.uuid4().hex` ya choices ke liye
       `sorted(..., key=lambda c: c['label'])`.
    3. SAP HANA retry pipeline me records ko priority pe sort karke process karna,
       ya max(retry_attempts, key=lambda r: r.last_attempt_at).
    4. defaultdict(lambda: {"count": 0, "total": 0}) — payment aggregation buckets.
    5. Celery task results ko latest_first dikhana: max(tasks, key=lambda t: t.eta).

INTERVIEW ANSWER (English — recite this):
    "A lambda is an anonymous function limited to a single expression whose value
    is implicitly returned. Functionally it produces the same kind of callable
    object as a def — the only real differences are that it has no name and cannot
    contain statements, so no assignments, no loops, no try/except, no annotations.
    I reach for lambdas almost exclusively as small, throwaway callables passed
    inline, the classic case being the key= argument to sorted, min, max and
    heapq, where defining a separate function would just add noise. The moment the
    logic needs more than one expression, or I'd want to unit-test or reuse it, or
    a name would document intent, I switch to a named def. Two senior nuances I
    keep in mind: first, a lambda assigned to a variable still shows '<lambda>' in
    tracebacks, which hurts debuggability, so PEP 8 actually discourages naming
    them; second, lambdas close over variables by reference with late binding, so
    building them in a loop captures the loop variable's final value unless I bind
    it explicitly with a default argument — exactly the same gotcha as any closure."

================================================================================
Run:
    python 10_lambda_functions.py          # saare sections chalao
    python 10_lambda_functions.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — lambda is just a function; def-equivalence + cannot hold statements
    2. DEMO  — key= in sorted / min / max (single + multi-key sorting)
    3. REAL  — Niroskos invoice sort + SAP HANA retry priority + payment buckets
    4. WHEN  — lambda vs named def: readability & traceback comparison
    5. BREAK — late-binding closure bug in a loop of lambdas (galti + fix)
    6. TODO  — tum khud likho: top-N payments per tenant using key=
================================================================================
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable


# === SECTION 1: DEMO — lambda is just a function; cannot hold statements ======
def section1() -> None:
    print("\n=== SECTION 1: lambda == anonymous single-expression function ===")

    # lambda aur def — dono SAME tarah ka function object banate hain
    add_lambda = lambda a, b: a + b
    def add_def(a, b):
        return a + b

    print(f"  add_lambda(2, 3)        = {add_lambda(2, 3)}")
    print(f"  add_def(2, 3)           = {add_def(2, 3)}")
    print(f"  type(add_lambda)        = {type(add_lambda).__name__}")
    print(f"  same type as def?       = {type(add_lambda) is type(add_def)}")

    # Ek farq jo turant dikhta hai: lambda ka __name__ '<lambda>' hota hai
    print(f"  add_lambda.__name__     = {add_lambda.__name__!r}  <- anonymous nishaani")
    print(f"  add_def.__name__        = {add_def.__name__!r}")

    # Lambda STATEMENTS nahi rakh sakta — sirf ek expression. Ye demonstrate
    # karne ke liye source ko compile karne ki koshish karte hain:
    bad_src = "lambda x: (y = x + 1)"   # assignment = statement, lambda me illegal
    try:
        eval(compile(bad_src, "<demo>", "eval"))
    except SyntaxError as e:
        print(f"  'lambda x: (y = x+1)'   -> SyntaxError (assignment is a statement)")
    # Conditional EXPRESSION allowed hai (ye statement nahi hai):
    sign = lambda n: "neg" if n < 0 else ("zero" if n == 0 else "pos")
    print(f"  ternary inside lambda ok: sign(-4)={sign(-4)!r} sign(7)={sign(7)!r}")


# === SECTION 2: DEMO — key= in sorted / min / max (single + multi-key) ========
def section2() -> None:
    print("\n=== SECTION 2: key= in sorted / min / max ===")

    words = ["banana", "fig", "cherry", "kiwi", "apple"]

    # key= ko ek callable chahiye jo har element se sort-key nikaale.
    by_len = sorted(words, key=lambda w: len(w))
    print(f"  sorted by length        : {by_len}")

    # min/max bhi key= lete hain — yahan sabse lambi string
    print(f"  longest (max, key=len)  : {max(words, key=lambda w: len(w))!r}")
    print(f"  shortest (min, key=len) : {min(words, key=lambda w: len(w))!r}")

    # MULTI-KEY: tuple return karo. Python tuple ko lexicographically compare karta
    # hai. Yahan: pehle length asc, phir alphabetical asc (tie-breaker).
    by_len_then_alpha = sorted(words, key=lambda w: (len(w), w))
    print(f"  (len, alpha) multi-key  : {by_len_then_alpha}")

    # DESCENDING numeric ke saath ASCENDING string ek hi key me — number ko negate
    # karo (string ko negate nahi kar sakte, isliye yeh trick numeric fields pe).
    scores = [("ashish", 90), ("rahul", 90), ("meena", 75)]
    ranked = sorted(scores, key=lambda t: (-t[1], t[0]))  # score desc, naam asc
    print(f"  score desc, name asc    : {ranked}")


# === SECTION 3: REAL — invoice sort, SAP HANA retry priority, payment buckets =
@dataclass
class Invoice:
    tenant_id: int
    number: str
    amount: float
    created_at: datetime


@dataclass
class RetryRecord:
    record_id: str
    attempts: int
    last_attempt_at: datetime


def section3() -> None:
    print("\n=== SECTION 3: REAL backend usage of lambda key= ===")

    # --- Niroskos multi-tenant: tenant ke andar amount descending dikhao ---
    invoices = [
        Invoice(2, "INV-2001", 1200.0, datetime(2026, 6, 10)),
        Invoice(1, "INV-1001", 500.0,  datetime(2026, 6, 11)),
        Invoice(1, "INV-1002", 999.0,  datetime(2026, 6, 9)),
        Invoice(2, "INV-2002", 300.0,  datetime(2026, 6, 12)),
    ]
    # tenant asc, phir amount desc — exactly jaise API response order chahiye
    ordered = sorted(invoices, key=lambda inv: (inv.tenant_id, -inv.amount))
    print("  Niroskos invoices (tenant asc, amount desc):")
    for inv in ordered:
        print(f"    tenant={inv.tenant_id} {inv.number} amount={inv.amount}")

    # --- SAP HANA retry pipeline: sabse stale failed record pehle process karo ---
    retries = [
        RetryRecord("R-1", 3, datetime(2026, 6, 18, 10, 5)),
        RetryRecord("R-2", 1, datetime(2026, 6, 18, 9, 0)),
        RetryRecord("R-3", 5, datetime(2026, 6, 18, 9, 30)),
    ]
    # Policy: jisne sabse zyada attempts khaye + sabse purana attempt — uska turn.
    next_to_retry = max(retries, key=lambda r: (r.attempts, -r.last_attempt_at.timestamp()))
    print(f"  SAP HANA next retry pick : {next_to_retry.record_id} "
          f"(attempts={next_to_retry.attempts})")

    # --- Payment aggregation: defaultdict(lambda: ...) factory ---
    # lambda yahan zero-arg factory ki tarah — har naye key pe fresh bucket banata hai
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "total": 0.0})
    payments = [("INR", 500.0), ("USD", 40.0), ("INR", 250.0), ("INR", 100.0)]
    for currency, amt in payments:
        buckets[currency]["count"] += 1
        buckets[currency]["total"] += amt
    print("  payment buckets (defaultdict + lambda factory):")
    for cur, agg in sorted(buckets.items()):
        print(f"    {cur}: count={int(agg['count'])} total={agg['total']}")


# === SECTION 4: WHEN — lambda vs named def (readability + traceback) ==========
def section4() -> None:
    print("\n=== SECTION 4: lambda vs named def — kab kya ===")

    # GOOD lambda: inline, throwaway, single expression, turant consume
    data = [{"name": "a", "p": 3}, {"name": "b", "p": 1}, {"name": "c", "p": 2}]
    print(f"  inline key (good lambda) : {[d['name'] for d in sorted(data, key=lambda d: d['p'])]}")

    # Jab logic naam deserve karta hai / reuse / test hona hai -> named def
    def by_priority_then_name(d: dict) -> tuple:
        # ek naam business intent document karta hai; isko alag se test kar sakte ho
        return (d["p"], d["name"])
    print(f"  named def key (reusable) : "
          f"{[d['name'] for d in sorted(data, key=by_priority_then_name)]}")

    # TRACEBACK downside: lambda crash hone par '<lambda>' dikhta hai, line number
    # to milta hai par naam se intent nahi. Hum dono ko explode karke compare karte hain.
    boom_lambda = lambda x: 1 / x
    def boom_named(x):
        return 1 / x

    for label, fn in [("lambda", boom_lambda), ("named def", boom_named)]:
        try:
            fn(0)
        except ZeroDivisionError:
            tb = sys.exc_info()[2]
            # frame jisme actual error hua uska function naam
            frame_name = tb.tb_next.tb_frame.f_code.co_name if tb.tb_next else "?"
            print(f"  {label:9s} crashed in frame named: {frame_name!r}")
    print("  Note: '<lambda>' frame debugging me kam helpful — isliye PEP 8")
    print("        kisi lambda ko variable me assign karne se mana karta hai (named def use karo).")


# === SECTION 5: BREAK IT / GOTCHA — late-binding closure in a loop ============
def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — late-binding closure with loop lambdas ===")

    # ---- GALAT: loop me lambdas banaye jo 'i' ko CAPTURE karte hain ----
    # Expectation (naive): multipliers[0](10)->0, [1](10)->10, [2](10)->20 ...
    bad_multipliers: list[Callable[[int], int]] = []
    for i in range(4):
        bad_multipliers.append(lambda x: x * i)   # BUG: 'i' by reference, late-bound

    # Loop khatam hone ke baad i==3. Sab lambdas ABHI lookup karte hain -> sab 3 use karte.
    wrong = [m(10) for m in bad_multipliers]
    print(f"  WRONG: each lambda used final i (3): {wrong}")
    print(f"         expected [0, 10, 20, 30] but got all using i=3")

    # ---- FIX 1: default argument se loop var ko DEFINITION time pe bind karo ----
    good_multipliers: list[Callable[[int], int]] = []
    for i in range(4):
        good_multipliers.append(lambda x, i=i: x * i)  # i=i snapshot abhi le liya
    fixed = [m(10) for m in good_multipliers]
    print(f"  FIXED (lambda x, i=i): each captured its own i: {fixed}")

    # ---- FIX 2 (alternative): factory function jo fresh scope deta hai ----
    def make_mult(factor: int) -> Callable[[int], int]:
        return lambda x: x * factor   # 'factor' har call me apna alag binding
    fixed2 = [make_mult(i)(10) for i in range(4)]
    print(f"  FIXED (factory closure): {fixed2}")

    print("  Lesson: lambda/closure variable ko REFERENCE se capture karta hai (late binding).")
    print("          Loop me bind chahiye to default-arg (i=i) ya factory use karo.")


# === SECTION 6: TODO — tum khud likho: top-N payments per tenant ==============
@dataclass
class Payment:
    tenant_id: int
    txn_id: str
    amount: float


def top_payments_per_tenant(
    payments: list[Payment], n: int
) -> dict[int, list[Payment]]:
    """
    TODO (tum implement karo):
      Har tenant ke liye unke TOP-N payments (amount DESCENDING) return karo.
      Lambda ka use key= me karna hai — alag se def likhne ki zaroorat nahi.

      Steps (hint):
        1. payments ko tenant_id ke hisaab se group karo (defaultdict(list)).
        2. har tenant ki list ko amount DESCENDING me sort karo:
               sorted(plist, key=lambda p: -p.amount)
           ya  sorted(plist, key=lambda p: p.amount, reverse=True)
        3. har tenant ke liye sirf pehle `n` rakho ([:n]) aur dict me daalo.

      Expected behaviour:
          payments = [
              Payment(1, "T1", 100), Payment(1, "T2", 300), Payment(1, "T3", 50),
              Payment(2, "T4", 999),
          ]
          top_payments_per_tenant(payments, 2)
          ->  {1: [Payment(1,"T2",300), Payment(1,"T1",100)],
               2: [Payment(2,"T4",999)]}
    """
    raise NotImplementedError("TODO: group by tenant, sort by amount desc via key=lambda, slice [:n]")


def section6() -> None:
    print("\n=== SECTION 6: TODO — top-N payments per tenant (tum likho) ===")
    payments = [
        Payment(1, "T1", 100.0),
        Payment(1, "T2", 300.0),
        Payment(1, "T3", 50.0),
        Payment(2, "T4", 999.0),
    ]
    try:
        result = top_payments_per_tenant(payments, 2)
        print("  tumhara result:")
        for tenant_id, plist in sorted(result.items()):
            shown = [(p.txn_id, p.amount) for p in plist]
            print(f"    tenant {tenant_id}: {shown}")
    except NotImplementedError as exc:
        print(f"  [pending] {exc}")


# === MAIN: dispatcher (no args -> sab; args -> sirf wo sections) ==============
SECTIONS = {
    1: section1,
    2: section2,
    3: section3,
    4: section4,
    5: section5,
    6: section6,
}


def main(argv: list[str]) -> None:
    if argv:
        try:
            chosen = [int(a) for a in argv]
        except ValueError:
            print(f"Invalid section numbers: {argv}. Valid: {sorted(SECTIONS)}")
            return
        to_run = [n for n in chosen if n in SECTIONS]
        missing = [n for n in chosen if n not in SECTIONS]
        if missing:
            print(f"Skipping unknown sections: {missing} (valid: {sorted(SECTIONS)})\n")
    else:
        to_run = sorted(SECTIONS)

    for i, n in enumerate(to_run):
        SECTIONS[n]()
        if i != len(to_run) - 1:
            print()


if __name__ == "__main__":
    main(sys.argv[1:])
