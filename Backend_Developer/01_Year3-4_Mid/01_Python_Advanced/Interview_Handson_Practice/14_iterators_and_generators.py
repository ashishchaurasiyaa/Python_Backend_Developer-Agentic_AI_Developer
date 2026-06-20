"""
================================================================================
TOPIC: Iterators & Generators (iter/next protocol, yield, genexpr, yield from, coroutine)
================================================================================

KYA HOTA HAI:
    ITERABLE wo hai jisme __iter__ ho (for loop chala sakte ho). ITERATOR wo hai
    jisme __next__ ho aur khatam hone pe StopIteration raise kare. Generator ek
    shortcut hai: 'yield' wali function call karte hi ek iterator object milta hai
    jo lazily — ek-ek value, on demand — produce karta hai, poori list memory me
    banaye bina. State function ke andar paused rehti hai.

KYO NEED PADI:
    Bade datasets (10 GB log file, lakhs of DB rows) ko ek saath memory me load
    karna RAM uda dega. Lazy iteration se ek time pe sirf ek item RAM me rehta hai
    — constant memory, streaming style. Plus infinite/unbounded sequences (ID gen,
    paginated API) list me fit hi nahi ho sakte; generator unhe naturally handle
    karta hai. Pipeline bhi ban-na easy: chhote lazy stages chain kar do.

KAISE USE KARTE HAIN:
    Function me 'yield' likho -> generator function. Call karne pe body chalti
    NAHI, ek generator object milta hai; next()/for use karo to body yield tak
    chalti hai aur pause ho jaati hai. genexpr = (x for x in it) -> lazy, list
    comp [..] ki tarah eager nahi. 'yield from sub' delegation karta hai. send()/
    throw()/close() se generator ko coroutine ki tarah bahar se drive karte hain.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA connector: lakhs of rows ko server-side cursor se batch-batch
       stream karo — ek generator jo 1000-row chunks yield kare, RAM constant.
    2. Log MCP / large file processing: GB-size log file ko line-by-line lazily
       parho, filter karo, parse karo — pipeline of generators, file kabhi poori
       memory me nahi aati.
    3. Niroskos multi-tenant SaaS: paginated external API se saare records ko ek
       seamless lazy stream me badlo (page-by-page fetch, yield per record).
    4. Celery/Redis: bade CSV export ko chunk-by-chunk yield karke stream-write,
       worker memory spike na ho.
    5. Idempotent retry/ETL: yield from se sub-generators ko compose karo (validate
       -> transform -> dedupe stages), har stage apni state hold kare.

INTERVIEW ANSWER (English — recite this):
    "An iterable is any object that returns an iterator from __iter__, while the
    iterator is the stateful object with __next__ that yields successive values and
    raises StopIteration when exhausted — that's the protocol for loops, comprehensions
    and unpacking. A generator function, one that uses yield, is just the easiest way
    to build an iterator: calling it returns a generator object without running the
    body, and execution advances lazily one yield at a time, preserving local state
    between resumes. The headline benefit is memory: a generator expression streams
    one item at a time in constant space, whereas the equivalent list comprehension
    materialises everything eagerly, which is the difference between processing a
    multi-gigabyte log file and an OutOfMemory kill. 'yield from' delegates to a
    sub-iterator and transparently forwards values, sends and the return value, which
    makes composing pipeline stages clean. Generators are also coroutines: send()
    pushes a value back in as the result of yield, throw() injects an exception at the
    pause point, and close() raises GeneratorExit for cleanup. The senior gotcha is
    that a generator is single-pass and stateful — once consumed it's empty, re-iterating
    silently yields nothing, so for anything that must be traversed twice you either
    keep the source iterable or materialise deliberately."

================================================================================
Run:
    python 14_iterators_and_generators.py        # saare sections chalao
    python 14_iterators_and_generators.py 1 5    # sirf section 1 aur 5

Sections:
    1. DEMO  — iterable vs iterator: __iter__/__next__/StopIteration by hand
    2. DEMO  — generator function (yield): lazy, paused state, for de-sugared
    3. DEMO  — genexpr vs list comp: MEMORY difference (sys.getsizeof + lazy proof)
    4. DEMO  — yield from: delegation se pipeline stages compose karo
    5. REAL  — lazy CSV/log pipeline (line -> parse -> filter), constant memory
    6. REAL  — generator-as-coroutine: send()/throw()/close() (running averager)
    7. BREAK — generator single-pass hai: dobara iterate = silently empty (galti+fix)
    8. TODO  — tum khud likho: batched(iterable, n) chunker (HANA cursor style)
================================================================================
"""
from __future__ import annotations

import io
import sys
from typing import Any, Iterator, Iterable


# === SECTION 1: DEMO — iterable vs iterator (__iter__/__next__/StopIteration) ===
class Countdown:
    """Iterable: __iter__ har baar ek FRESH iterator deta hai. Yahi reusable
    banata hai (list jaisa). Iterator alag class — usme __next__ + state hota."""
    def __init__(self, start: int) -> None:
        self.start = start

    def __iter__(self) -> "CountdownIterator":
        return CountdownIterator(self.start)


class CountdownIterator:
    """Iterator: stateful, __next__ aur khatam pe StopIteration. __iter__ apne
    aap ko return karta (taaki iterator bhi iterable ho — for loop expect karta)."""
    def __init__(self, current: int) -> None:
        self.current = current

    def __iter__(self) -> "CountdownIterator":
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration            # for loop yahi catch karke ruk jaata
        self.current -= 1
        return self.current + 1


def section1() -> None:
    print("\n=== SECTION 1: iterable vs iterator (__iter__/__next__/StopIteration) ===")

    cd = Countdown(3)
    it = iter(cd)                          # iter(obj) -> obj.__iter__()
    print(f"  iter(Countdown) -> {type(it).__name__}")
    print(f"  next() one by one: {next(it)}, {next(it)}, {next(it)}")
    try:
        next(it)                           # exhausted
    except StopIteration:
        print("  next() again -> StopIteration (iterator khatam)")

    # for loop = de-sugared: iter() banao, next() tab tak jab StopIteration na aaye
    print(f"  for loop over SAME iterable (fresh iterator): {[x for x in cd]}")
    # GOTCHA preview: iterator ek baar consume ho gaya to khaali
    print(f"  but reusing exhausted iterator 'it': {[x for x in it]}  (empty!)")


# === SECTION 2: DEMO — generator function (yield): lazy + paused state ===
def gen_countdown(start: int) -> Iterator[int]:
    """Poori CountdownIterator class ka kaam 3 line me. yield = pause + value bahar.
    Call karte hi body NAHI chalti — generator object milta hai."""
    print(f"      [gen] body START (start={start})")
    n = start
    while n > 0:
        yield n                            # yahan pause; agle next() pe resume
        n -= 1
    print("      [gen] body END (StopIteration auto)")


def section2() -> None:
    print("\n=== SECTION 2: generator function (yield) — lazy, paused state ===")

    g = gen_countdown(3)                   # body abhi tak chala hi nahi
    print(f"  called gen_countdown(3) -> {type(g).__name__} (body not run yet)")
    print(f"  next(g) -> {next(g)}   (ab body 'START' print karega, fir pause)")
    print(f"  next(g) -> {next(g)}   (yield se yield, beech ka state yaad)")
    print(f"  next(g) -> {next(g)}")
    try:
        next(g)
    except StopIteration:
        print("  next(g) -> StopIteration (loop khatam, body END)")
    # equivalence: class-based aur generator dono same protocol follow karte hain
    print(f"  full for-loop on fresh gen: {list(gen_countdown(4))}")


# === SECTION 3: DEMO — genexpr vs list comp: MEMORY difference ===
def section3() -> None:
    print("\n=== SECTION 3: genexpr vs list comp — MEMORY (lazy vs eager) ===")

    n = 1_000_000
    list_comp = [x * x for x in range(n)]          # EAGER: 1M ints abhi RAM me
    gen_expr = (x * x for x in range(n))           # LAZY: ek tiny generator object

    print(f"  list comp [x*x for x in range({n:_})]")
    print(f"    sys.getsizeof = {sys.getsizeof(list_comp):>10,} bytes (poora materialised)")
    print(f"  gen expr  (x*x for x in range({n:_}))")
    print(f"    sys.getsizeof = {sys.getsizeof(gen_expr):>10,} bytes (kuch sau bytes, lazy!)")
    print("    -> isi liye GB-size stream pe genexpr/generator, list NAHI (OOM bachta).")

    # lazy proof: sum() genexpr ko ek-ek consume karega, beech me poori list nahi banti
    total = sum(x * x for x in range(5))           # parentheses drop ho sakta as sole arg
    print(f"  sum(x*x for x in range(5)) = {total}  (streamed, never a full list)")

    # genexpr bhi single-pass: dobara use -> khaali
    squares = (x * x for x in range(3))
    print(f"  first pass : {list(squares)}")
    print(f"  second pass: {list(squares)}   (exhausted -> empty)")


# === SECTION 4: DEMO — yield from delegation (pipeline stages compose) ===
def stream_pages(pages: list[list[int]]) -> Iterator[int]:
    """Niroskos paginated API style — har page ek list, sabko ek flat lazy
    stream me delegate kar do. 'yield from page' = page ke har item ko yield."""
    for page in pages:
        yield from page                    # delegation: manual 'for x in page: yield x' ka short


def even_only(source: Iterable[int]) -> Iterator[int]:
    """Pipeline stage: sirf even pass kare. Source bhi lazy, ye bhi lazy."""
    for item in source:
        if item % 2 == 0:
            yield item


def section4() -> None:
    print("\n=== SECTION 4: yield from — delegation + composing lazy stages ===")

    pages = [[1, 2, 3], [4, 5], [6, 7, 8, 9]]      # 3 paginated API responses
    flat = stream_pages(pages)
    print(f"  flatten pages via 'yield from': {list(flat)}")

    # compose: stream_pages -> even_only, dono generators, fully lazy chain
    pipeline = even_only(stream_pages(pages))
    print(f"  pipeline even_only(stream_pages(..)) -> {list(pipeline)}")
    print("    -> har stage ek generator; data ek item-at-a-time flow karta (no big list).")


# === SECTION 5: REAL — lazy CSV/log pipeline (constant memory) ===
def read_lines(fp: io.StringIO) -> Iterator[str]:
    """Stage 1: file/stream se line-by-line lazily parho. Real life me ye open(path)
    hota — GB file bhi constant memory, kyunki ek time ek line. (Yahan StringIO se simulate.)"""
    for raw in fp:                         # file object khud ek lazy iterator hai
        yield raw.rstrip("\n")


def parse_log(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """Stage 2: 'LEVEL|tenant|message' ko dict me parse karo. Lazy: ek line aayi,
    ek dict bahar gaya."""
    for line in lines:
        if not line:
            continue
        level, tenant, message = line.split("|", 2)
        yield {"level": level, "tenant": tenant, "message": message}


def filter_errors(records: Iterable[dict[str, str]], tenant: str) -> Iterator[dict[str, str]]:
    """Stage 3: tenant-scoped ERROR records — multi-tenant log MCP ka core kaam."""
    for rec in records:
        if rec["level"] == "ERROR" and rec["tenant"] == tenant:
            yield rec


def section5() -> None:
    print("\n=== SECTION 5: REAL — lazy CSV/log pipeline (line->parse->filter) ===")

    # bade log file ka simulate — real me open('/var/log/app.log') hota
    log_blob = (
        "INFO|acme|user logged in\n"
        "ERROR|acme|payment gateway timeout\n"
        "WARN|globex|cache miss spike\n"
        "ERROR|globex|db connection reset\n"
        "ERROR|acme|idempotency key clash\n"
        "INFO|acme|sync completed\n"
    )
    fp = io.StringIO(log_blob)

    # 3-stage lazy pipeline: kuch bhi materialise nahi hota jab tak consume na karo
    errors_for_acme = filter_errors(parse_log(read_lines(fp)), tenant="acme")
    print("  pipeline built (nothing read yet). Now streaming acme ERRORs:")
    count = 0
    for rec in errors_for_acme:            # yahi pe data line-by-line flow karta
        count += 1
        print(f"    [{count}] {rec['tenant']}: {rec['message']}")
    print(f"  total acme errors = {count}  (file ek time ek line, RAM constant)")


# === SECTION 6: REAL — generator-as-coroutine: send()/throw()/close() ===
def running_average() -> Iterator[float | None]:
    """Coroutine: bahar se .send(value) se number bhejo, ye ab tak ka average
    wapas yield karta hai. State (total, count) generator ke andar paused rehti.
    Use-case: streaming metric (rolling latency avg) bina external accumulator ke."""
    total = 0.0
    count = 0
    average: float | None = None
    try:
        while True:
            value = yield average          # yield bahar bhejta, send() andar deta
            total += value
            count += 1
            average = total / count
    except GeneratorExit:                  # close() yahan aata — cleanup spot
        print(f"      [coroutine] closing, final avg over {count} values = {average}")


def section6() -> None:
    print("\n=== SECTION 6: REAL — generator-as-coroutine: send/throw/close ===")

    avg = running_average()
    next(avg)                              # "prime" — pehle yield tak chalao (zaroori!)
    print(f"  send(10) -> avg {avg.send(10)}")
    print(f"  send(20) -> avg {avg.send(20)}")
    print(f"  send(30) -> avg {avg.send(30)}")

    # throw(): pause point pe exception inject karo — generator handle/propagate kare
    try:
        avg.throw(ValueError("bad metric sample"))
    except ValueError as e:
        print(f"  throw(ValueError) -> propagated out (uncaught inside): {e}")

    # close() ek fresh coroutine pe -> GeneratorExit -> cleanup branch chalta
    avg2 = running_average()
    next(avg2)
    avg2.send(5)
    avg2.send(15)
    avg2.close()
    print("  close() ne cleanup (GeneratorExit) branch chala diya (upar print).")


# === SECTION 7: BREAK IT / GOTCHA — generator single-pass (silently empty) ===
def section7() -> None:
    print("\n=== SECTION 7: BREAK IT — generator single-pass: 2nd iterate = empty ===")

    def hana_rows() -> Iterator[dict[str, Any]]:
        for i in range(1, 4):
            yield {"id": i, "amount": i * 100}

    # ---- GALAT: ek hi generator object ko do baar use karna ----
    rows = hana_rows()                     # ek generator object
    total = sum(r["amount"] for r in rows)            # pehla pass — generator drain
    audit = [r["id"] for r in rows]                   # doosra pass — ALREADY EMPTY
    print("  WRONG: ek hi generator object dobara iterate kiya")
    print(f"    total amount  = {total}")
    print(f"    audit ids     = {audit}   <- BUG: khaali! (silently, no error)")
    print("    -> sabse khatarnaak: koi exception nahi, bas chupke se empty result.")

    # ---- SAHI option A: jitni baar chahiye, FRESH generator banao ----
    total2 = sum(r["amount"] for r in hana_rows())
    audit2 = [r["id"] for r in hana_rows()]
    print("  FIXED A (call factory again -> fresh generator each pass):")
    print(f"    total = {total2}, audit ids = {audit2}")

    # ---- SAHI option B: agar SACH me 2 baar chahiye, ek baar materialise karo ----
    materialised = list(hana_rows())       # ab list — reusable, but memory cost soch ke
    total3 = sum(r["amount"] for r in materialised)
    audit3 = [r["id"] for r in materialised]
    print("  FIXED B (materialise to list once, reuse — only if it FITS in RAM):")
    print(f"    total = {total3}, audit ids = {audit3}")


# === SECTION 8: TODO — tum khud likho: batched(iterable, n) chunker ===
def batched(iterable: Iterable[Any], n: int) -> Iterator[list[Any]]:
    """
    TODO (tum implement karo):
      Ek LAZY generator banao jo kisi bhi iterable ko n-size ke chunks (list) me
      yield kare — SAP HANA cursor / Celery batch-write style. Aakhri chunk chhota
      ho sakta hai. Poora input kabhi memory me load NAHI hona chahiye (lazy).
        - iter(iterable) lo, ek 'batch' list banate jao;
        - jab len(batch) == n ho -> 'yield batch' aur batch reset karo;
        - input khatam hone pe agar batch me kuch bacha ho to wo bhi yield karo.
      Expected behaviour:
          list(batched([1,2,3,4,5], 2))  -> [[1, 2], [3, 4], [5]]
          list(batched(range(6), 3))     -> [[0, 1, 2], [3, 4, 5]]
          list(batched([], 3))           -> []
      Hint: n <= 0 pe ValueError raise karna acchi practice hai. Python 3.12 me
      itertools.batched built-in hai — par yahan khud likh ke protocol samjho.
    """
    raise NotImplementedError("TODO: batched() ka lazy chunking body likho")


def section8() -> None:
    print("\n=== SECTION 8: TODO — batched(iterable, n) lazy chunker (tum likho) ===")

    try:
        out = list(batched([1, 2, 3, 4, 5], 2))
        print(f"  batched([1,2,3,4,5], 2) -> {out}")
        if out == [[1, 2], [3, 4], [5]]:
            print("  correct! lazy chunking kaam kar raha hai.")
        else:
            print("  hmm, output expected [[1, 2], [3, 4], [5]] tha — dobara dekho.")
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
