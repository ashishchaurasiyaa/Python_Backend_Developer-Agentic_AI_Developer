"""
================================================================================
TOPIC: Comprehensions & Functional Tools
================================================================================

KYA HOTA HAI:
    Comprehensions = ek concise expression jo iterable se naya list/set/dict/
    generator banata hai. Functional tools = map/filter/reduce + functools
    (partial, lru_cache, singledispatch, total_ordering) + itertools (chain,
    islice, groupby, accumulate, product, pairwise, batched). Ye sab "data
    transform karo bina manual loop + temp list ke" ka idiomatic Python tareeka
    hai.

KYO NEED PADI:
    Manual `for` loop + `result = []; result.append(...)` boilerplate bahut hai
    aur slow bhi (har append ek attribute lookup). Comprehensions ek hi readable
    line me intent dikhate hain aur C-level pe fast chalte hain. Bade datasets
    (SAP HANA se aaye lakhon rows) ke liye generator comprehension lazy hota hai
    — pura data RAM me load nahi karta, OOM se bachata hai.

KAISE USE KARTE HAIN:
    [x*2 for x in xs], {k: v for k, v in pairs}, {x for x in xs} (dedup),
    (x for x in xs) (lazy). Walrus := se loop me computed value reuse karo.
    map/filter pure function ke liye; reduce running fold ke liye. itertools se
    streaming pipeline; functools se caching/dispatch/ordering.

KAHAN USE HOTA HAI (scenarios):
    - SAP HANA connector: row-stream ko generator pipeline se transform + filter
      karke chunk-by-chunk push — pura table RAM me nahi.
    - Multi-tenant Django SaaS: queryset rows ko {tenant_id: [...]} dict me
      group karna (itertools.groupby), ya tenant-scoped lookup dict banana.
    - Payment reconciliation: itertools.accumulate se running balance, pairwise
      se consecutive txn ka gap detect karna.
    - Celery/Redis: islice + batched se ek bade iterable ko fixed-size batches
      me todna (bulk_create / pipeline.execute).
    - lru_cache se exchange-rate / config lookups cache; singledispatch se
      payload type ke hisaab se serializer pick karna.

INTERVIEW ANSWER (English):
    Comprehensions are Python's idiomatic way to build a list, set, dict, or
    generator from an iterable in a single readable expression, and they run at
    C speed because there's no repeated attribute lookup for append. I reach for
    a list comprehension when I need the whole result materialised, a set or dict
    comprehension for deduplication or keyed lookups, and crucially a generator
    expression when the data is large or streaming — it stays lazy and keeps
    memory flat, which matters when I'm pulling millions of rows from SAP HANA.
    The walrus operator lets me compute a value once inside the comprehension and
    reuse it in both the filter and the output. I prefer comprehensions over
    map/filter when there's a transform plus a condition, but I'll use map with
    an existing named function, and functools.reduce only for genuine folds like
    a running balance. The functools and itertools toolkits cover the rest:
    lru_cache for memoisation, singledispatch for type-based dispatch,
    total_ordering to derive comparisons, and itertools.groupby, accumulate,
    pairwise and batched for streaming aggregations. The senior nuance is that a
    generator is single-use and lazy — exceptions and side effects only fire when
    you consume it — and groupby requires the input to be pre-sorted on the key,
    which is the classic bug.

--------------------------------------------------------------------------------
Run:
    python 12_comprehensions_and_functional_tools.py        # saare sections
    python 12_comprehensions_and_functional_tools.py 1 5    # sirf 1 aur 5

Sections:
    1. DEMO        — list/set/dict/generator comprehension + nested + walrus
    2. DEMO        — map/filter/reduce vs comprehension (kab kaunsa readable)
    3. DEMO        — functools: partial / lru_cache / singledispatch / total_ordering
    4. DEMO        — itertools: chain/islice/groupby/accumulate/product/pairwise/batched
    5. REAL        — SAP HANA row-stream: lazy generator pipeline (memory-flat)
    6. REAL        — payment reconciliation: accumulate (balance) + pairwise (gaps)
    7. BREAK-IT    — generator single-use + lazy-eval gotcha (side effects late)
    8. BREAK-IT    — groupby bina sort -> tukde-tukde groups (classic bug)
    9. TODO        — tum khud likho: tenant-scoped batched generator pipeline
================================================================================
"""
from __future__ import annotations

import sys
from functools import lru_cache, partial, reduce, singledispatch, total_ordering
from itertools import (
    accumulate,
    batched,
    chain,
    groupby,
    islice,
    pairwise,
    product,
)


# === SECTION 1: DEMO — comprehensions (list/set/dict/gen) + nested + walrus ===
def section_1() -> None:
    print("=" * 70)
    print("SECTION 1: list / set / dict / generator comprehension + walrus")
    print("=" * 70)

    nums = [1, 2, 2, 3, 3, 3, 4]

    # list: pura materialise hota hai
    squares = [n * n for n in nums]
    print(f"  list comp (squares)     : {squares}")

    # set: dedup free me mil jaata hai
    unique = {n for n in nums}
    print(f"  set comp (unique)       : {sorted(unique)}")

    # dict: keyed lookup table — yahi tenant/id->row maps banate hain
    by_square = {n: n * n for n in unique}
    print(f"  dict comp (n -> n^2)    : {by_square}")

    # generator: lazy — abhi kuch compute nahi hua, sirf object bana
    gen = (n * n for n in nums)
    print(f"  generator object        : {gen}  (lazy, abhi run nahi hua)")
    print(f"  next(gen) x2            : {next(gen)}, {next(gen)}  (ab compute hua)")

    # nested comprehension: matrix flatten (left-to-right = outer-to-inner loop)
    matrix = [[1, 2, 3], [4, 5, 6]]
    flat = [val for row in matrix for val in row]
    print(f"  nested (flatten matrix) : {flat}")

    # walrus := -> value ek baar compute karo, filter + output dono me reuse
    data = [3, 10, 7, 25, 4]
    # bina walrus: f(x) do baar likhna padta (filter me bhi, output me bhi)
    big = [y for x in data if (y := x * x) > 40]
    print(f"  walrus (x^2 jab >40)    : {big}  (square ek hi baar compute hua)")


# === SECTION 2: DEMO — map/filter/reduce vs comprehension ====================
def section_2() -> None:
    print("=" * 70)
    print("SECTION 2: map / filter / reduce vs comprehension (kab kaunsa)")
    print("=" * 70)

    prices = [100, 250, 50, 400, 175]

    # map + existing named function -> map theek hai (clean, koi lambda nahi)
    rupees = list(map(str, prices))
    print(f"  map(str, prices)        : {rupees}")

    # transform + condition dono -> comprehension zyada readable
    via_mapfilter = list(map(lambda p: p * 1.18, filter(lambda p: p > 100, prices)))
    via_comp = [p * 1.18 for p in prices if p > 100]
    print(f"  map+filter (GST on >100): {[round(x, 2) for x in via_mapfilter]}")
    print(f"  comprehension (same)    : {[round(x, 2) for x in via_comp]}  <- readable")

    # reduce -> genuine fold (running aggregate). Yahan total with 18% GST.
    total_with_gst = reduce(lambda acc, p: acc + p * 1.18, prices, 0.0)
    print(f"  reduce (sum * 1.18)     : {round(total_with_gst, 2)}")
    print(f"  ...but plain sum better : {round(sum(prices) * 1.18, 2)}  "
          f"(reduce sirf jab built-in na ho)")
    print("  Rule: transform+filter -> comprehension; named fn -> map; "
          "real fold -> reduce.")


# === SECTION 3: DEMO — functools toolkit ====================================
@total_ordering
class Money:
    """total_ordering: sirf __eq__ + __lt__ likho, baaki <=,>,>= auto-derive."""

    def __init__(self, paise: int) -> None:
        self.paise = paise

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and self.paise == other.paise

    def __lt__(self, other: "Money") -> bool:
        return self.paise < other.paise

    def __repr__(self) -> str:
        return f"Money(Rs {self.paise / 100:.2f})"


@singledispatch
def serialize(value: object) -> str:
    """Default: type ke hisaab se serializer pick. Naya type? bas register karo."""
    return f"<unhandled {type(value).__name__}>"


@serialize.register
def _(value: int) -> str:
    return f"int:{value}"


@serialize.register
def _(value: list) -> str:
    return "list:[" + ",".join(serialize(v) for v in value) + "]"


@lru_cache(maxsize=128)
def fx_rate(currency: str) -> float:
    """Mehnga lookup (socho external API). lru_cache repeat call cache karta hai."""
    fx_rate.calls += 1  # type: ignore[attr-defined]
    table = {"USD": 83.2, "EUR": 90.1, "GBP": 105.4}
    return table.get(currency, 1.0)


fx_rate.calls = 0  # type: ignore[attr-defined]


def section_3() -> None:
    print("=" * 70)
    print("SECTION 3: functools — partial / lru_cache / singledispatch / total_ordering")
    print("=" * 70)

    # partial: ek function ke kuch args pehle se bind karke naya callable
    def retry_call(attempts: int, fn_name: str) -> str:
        return f"calling {fn_name} (max {attempts} retries)"

    hana_call = partial(retry_call, 3)  # SAP HANA ke liye attempts=3 fix
    print(f"  partial (attempts=3)    : {hana_call('SAP_HANA_UPSERT')}")

    # total_ordering: ek hi __lt__ se pura ordering mil gaya
    a, b = Money(15000), Money(9900)
    print(f"  total_ordering          : {a} > {b} ? {a > b}  (>=,<= bhi mile)")
    print(f"  sorted([b, a])          : {sorted([b, a])}")

    # singledispatch: type-based dispatch (if/elif chain ka clean alternative)
    print(f"  singledispatch int      : {serialize(42)}")
    print(f"  singledispatch list     : {serialize([1, 2, [3, 4]])}")
    print(f"  singledispatch unknown  : {serialize({'k': 1})}")

    # lru_cache: dusri baar same arg -> function body run hi nahi hota
    fx_rate.calls = 0  # type: ignore[attr-defined]
    [fx_rate("USD") for _ in range(5)]
    fx_rate("EUR")
    print(f"  lru_cache (5x USD,1xEUR): actual computes = "
          f"{fx_rate.calls}  (5 nahi, sirf 2)")  # type: ignore[attr-defined]
    print(f"  cache_info              : {fx_rate.cache_info()}")


# === SECTION 4: DEMO — itertools toolkit =====================================
def section_4() -> None:
    print("=" * 70)
    print("SECTION 4: itertools — chain/islice/groupby/accumulate/product/"
          "pairwise/batched")
    print("=" * 70)

    # chain: kai iterables ko ek stream ki tarah jodo (bina list concat ke)
    page1, page2 = [1, 2, 3], [4, 5, 6]
    print(f"  chain (paged results)   : {list(chain(page1, page2))}")

    # islice: lazy slice — generator pe bhi chalti hai (list banaye bina)
    first3 = list(islice(chain(page1, page2), 3))
    print(f"  islice (first 3)        : {first3}")

    # groupby: CONSECUTIVE keys group kare -> input sorted hona zaroori (sec 8)
    txns = [("acme", 100), ("acme", 50), ("globex", 75), ("globex", 25)]
    grouped = {k: [amt for _, amt in g] for k, g in groupby(txns, key=lambda t: t[0])}
    print(f"  groupby (by tenant)     : {grouped}")

    # accumulate: running aggregate (default sum) — running balance ke liye
    deposits = [100, -30, 200, -50]
    print(f"  accumulate (balance)    : {list(accumulate(deposits))}")

    # product: cartesian product (nested loop ka flat version)
    combos = list(product(["card", "upi"], ["INR", "USD"]))
    print(f"  product (method x cur)  : {combos}")

    # pairwise: consecutive (a,b) pairs — gaps/deltas detect karne ke liye
    timestamps = [10, 12, 19, 20]
    deltas = [b - a for a, b in pairwise(timestamps)]
    print(f"  pairwise (deltas)       : {deltas}")

    # batched (3.12+): iterable ko fixed-size tuples me todo (bulk insert ke liye)
    ids = range(1, 8)
    print(f"  batched (size 3)        : {[list(b) for b in batched(ids, 3)]}")


# === SECTION 5: REAL — SAP HANA row-stream lazy generator pipeline ===========
def _hana_rows(n: int):
    """Socho ye SAP HANA cursor hai — ek-ek row yield karta hai, pura table
    RAM me nahi laata. Yahan simulate kar rahe hain."""
    for i in range(n):
        yield {"pk": i, "material": f"MAT-{i % 4}", "qty": i % 10, "active": i % 3 != 0}


def section_5() -> None:
    print("=" * 70)
    print("SECTION 5: REAL — SAP HANA stream, lazy generator pipeline (memory-flat)")
    print("=" * 70)

    # PIPELINE: har stage generator -> kuch bhi materialise nahi hota jab tak
    # consume na karo. 10 lakh rows aaye to bhi RAM flat rehti hai.
    src = _hana_rows(1_000_000)                                  # stage 1: source
    active = (r for r in src if r["active"])                     # stage 2: filter
    shaped = ({"pk": r["pk"], "qty": r["qty"]} for r in active)  # stage 3: transform
    nonzero = (r for r in shaped if r["qty"] > 0)                # stage 4: filter

    # ab batched se chunk-by-chunk "push" karte hain (Celery/bulk_create style)
    pushed_rows = 0
    batches = 0
    for batch in batched(nonzero, 500):
        # yahan real life me: pipeline.execute() / bulk_create(batch)
        pushed_rows += len(batch)
        batches += 1
        if batches >= 3:  # demo ke liye sirf 3 batches dekhte hain
            break

    print(f"  Pipeline stages         : source -> filter(active) -> transform "
          f"-> filter(qty>0) -> batched(500)")
    print(f"  Batches processed (demo): {batches}  (har batch = {pushed_rows // batches} rows)")
    print(f"  Rows pushed so far      : {pushed_rows}")
    print("  Poora 10-lakh-row table kabhi list me load nahi hua — "
          "ye generator pipeline ka asli faayda.")


# === SECTION 6: REAL — payment reconciliation (accumulate + pairwise) ========
def section_6() -> None:
    print("=" * 70)
    print("SECTION 6: REAL — payment reconciliation: running balance + gaps")
    print("=" * 70)

    # (ts_seconds, signed_amount) — credit positive, debit negative
    ledger = [
        (1000, +5000),
        (1010, -1200),
        (1015, -800),
        (1300, +2000),  # bada time gap (jump 1015 -> 1300)
        (1305, -500),
    ]

    # running balance via accumulate (fold without manual loop)
    amounts = [amt for _, amt in ledger]
    balances = list(accumulate(amounts))
    print("  Running balance (accumulate):")
    for (ts, amt), bal in zip(ledger, balances):
        print(f"    t={ts:<5} {amt:+6d} -> balance {bal}")

    # pairwise se consecutive txn ka time-gap nikaalo -> anomaly detect
    times = [ts for ts, _ in ledger]
    gaps = [(t2, t2 - t1) for t1, t2 in pairwise(times)]
    suspicious = [t for t, g in gaps if g > 100]  # walrus-free, simple
    print(f"  Time gaps (pairwise)    : {[g for _, g in gaps]}")
    print(f"  Suspicious (gap>100s)   : at t={suspicious}  "
          f"(reconciliation flag laga sakte ho)")


# === SECTION 7: BREAK-IT — generator single-use + lazy side-effects ==========
def section_7() -> None:
    print("=" * 70)
    print("SECTION 7: BREAK-IT — generator EK BAAR consume hota + lazy hota hai")
    print("=" * 70)

    # ---- GALAT #1: ek hi generator ko do baar use karna ----
    gen = (x * 2 for x in [1, 2, 3])
    first = list(gen)   # poora consume ho gaya
    second = list(gen)  # ab khaali!
    print("  [WRONG] same generator twice:")
    print(f"    first  pass : {first}")
    print(f"    second pass : {second}   <-- khaali! generator exhaust ho gaya")

    # ---- FIX: list me materialise karo (multi-pass chahiye to), ya naya banao ----
    data = [1, 2, 3]
    reusable = [x * 2 for x in data]  # list -> jitni baar chaho use karo
    print("  [FIX] list comprehension (re-iterable):")
    print(f"    first  pass : {reusable}")
    print(f"    second pass : {reusable}   <-- ab dono baar mila")

    # ---- GALAT #2: lazy eval -> side-effect/exception turant nahi chalta ----
    def risky(x: int) -> int:
        if x == 0:
            raise ValueError("x=0 not allowed")
        return 100 // x

    print("\n  [WRONG] lazy eval — exception abhi nahi aayega:")
    lazy = (risky(x) for x in [5, 0, 2])   # yahan koi error NAHI
    print("    generator bana — abhi tak koi ValueError nahi (lazy!)")
    try:
        list(lazy)  # ab consume karte hi blast
    except ValueError as exc:
        print(f"    consume karte hi -> ValueError: {exc}")
    print("  Lesson: generator lazy + single-use hai. Validation/early-fail "
          "chahiye to comprehension (eager) use karo ya turant consume karo.")


# === SECTION 8: BREAK-IT — groupby bina sort (classic bug) ===================
def section_8() -> None:
    print("=" * 70)
    print("SECTION 8: BREAK-IT — itertools.groupby bina pehle SORT kiye")
    print("=" * 70)

    # multi-tenant rows, par tenant ke hisaab se SORTED nahi (DB se aise hi aaye)
    rows = [
        {"tenant": "acme", "amt": 100},
        {"tenant": "globex", "amt": 50},
        {"tenant": "acme", "amt": 70},   # acme dobaara, par beech me globex aa gaya
        {"tenant": "globex", "amt": 20},
    ]
    # ---- GALAT: bina sort ke groupby -> tenant tukdo me toot jaata ----
    wrong = {}
    for tenant, grp in groupby(rows, key=lambda r: r["tenant"]):
        # NOTE: same tenant ke alag-alag tukde overwrite kar denge -> data loss
        wrong[tenant] = [r["amt"] for r in grp]
    print("  [WRONG] groupby on UNSORTED rows:")
    print(f"    result : {wrong}")
    print("    acme ke 70 wala row gayab! (do alag 'acme' groups bane, last jeeta)")

    # ---- FIX: pehle usi key pe sort karo, phir groupby ----
    rows_sorted = sorted(rows, key=lambda r: r["tenant"])
    right = {
        tenant: [r["amt"] for r in grp]
        for tenant, grp in groupby(rows_sorted, key=lambda r: r["tenant"])
    }
    print("  [FIX] sort first, then groupby:")
    print(f"    result : {right}   <-- acme = [100, 70] poora aaya")
    print("  Lesson: groupby sirf CONSECUTIVE equal keys jodti hai (SQL GROUP BY "
          "nahi). Input ko key pe sort karna mandatory hai.")


# === SECTION 9: TODO — tum khud likho =======================================
def section_9() -> None:
    print("=" * 70)
    print("SECTION 9: TODO — tenant-scoped batched generator pipeline khud likho")
    print("=" * 70)
    print("  Expected behaviour:")
    print("    def tenant_batches(rows, tenant_id, size):")
    print("      - rows: iterable of dicts {'tenant': str, 'pk': int, 'qty': int}")
    print("      - Step 1: GENERATOR expression se sirf tenant_id wale rows filter karo")
    print("                (list mat banao — lazy raho, memory flat).")
    print("      - Step 2: us filtered stream se qty>0 wale ka 'pk' nikaalo (gen).")
    print("      - Step 3: itertools.batched se 'size' ke fixed chunks me yield karo.")
    print("      - Return: ek generator jo list-of-pks (har batch) yield kare.")
    print("    Example: 6 matching pks, size=2 -> [[..,..],[..,..],[..,..]]")
    print("    NOTE: pura kaam tab tak na ho jab tak consume na karo (lazy proof).")

    def tenant_batches(rows, tenant_id: str, size: int):
        # TODO: yahan generator pipeline + batched implement karo.
        raise NotImplementedError("Tum likho: filter(gen) -> map pk(gen) -> batched")

    sample = [
        {"tenant": "acme", "pk": 1, "qty": 5},
        {"tenant": "globex", "pk": 2, "qty": 3},
        {"tenant": "acme", "pk": 3, "qty": 0},  # qty 0 -> skip hona chahiye
        {"tenant": "acme", "pk": 4, "qty": 9},
    ]
    try:
        result = [list(b) for b in tenant_batches(sample, "acme", 2)]
        print(f"  Tumhara output: {result}")
    except NotImplementedError as exc:
        print(f"  [pending] {exc}")


# === MAIN: dispatcher (no args -> sab; args -> sirf wo sections) =============
SECTIONS = {
    1: section_1,
    2: section_2,
    3: section_3,
    4: section_4,
    5: section_5,
    6: section_6,
    7: section_7,
    8: section_8,
    9: section_9,
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
            print(f"Skipping unknown sections: {missing} "
                  f"(valid: {sorted(SECTIONS)})\n")
    else:
        to_run = sorted(SECTIONS)

    for i, n in enumerate(to_run):
        SECTIONS[n]()
        if i != len(to_run) - 1:
            print()


if __name__ == "__main__":
    main(sys.argv[1:])
