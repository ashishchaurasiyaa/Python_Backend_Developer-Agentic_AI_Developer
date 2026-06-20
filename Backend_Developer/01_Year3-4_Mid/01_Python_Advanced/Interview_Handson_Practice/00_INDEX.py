"""
INTERVIEW HANDS-ON PRACTICE LAB  —  Advanced Python (Senior Backend)
====================================================================
Ye lab THEORY nahi hai — ye PRACTICE hai. Har file khud chala, output dekh,
BREAK-IT section me galti feel kar, phir TODO khud likh.

Har file ka structure:
    Header docstring -> KYA / KYO / KAISE / KAHAN (Hinglish) + INTERVIEW ANSWER (English)
    SECTION 1..N     -> DEMO + REAL BACKEND SCENARIO + BREAK-IT/GOTCHA + TODO

Kaise chalao:
    python 11_decorators.py            # poori file (saare sections)
    python 11_decorators.py 1 4        # sirf section 1 aur 4
    python 00_INDEX.py                 # ye menu

Practice ka tareeka (har topic pe):
    1. file chala -> output padh
    2. BREAK-IT section samajh (yahi interview gotcha hai)
    3. INTERVIEW ANSWER zor se bol ke rehearse kar
    4. TODO function khud implement kar -> dobara chala
"""
from __future__ import annotations
import sys

# (number, filename-slug, one-line "kya seekhoge")
TOPICS = [
    ("OOP & DATA MODEL", [
        ("01", "operator_overloading_vs_overriding", "Dunder operators vs method overriding; why Python me method overloading nahi hota"),
        ("02", "oop_deep_dive",                      "Encapsulation, @property, classmethod/staticmethod, composition vs inheritance"),
        ("03", "mro_super_mixins",                   "C3 MRO, cooperative super(), mixins; diamond problem ek hi baar resolve"),
        ("04", "abc_and_protocols",                  "ABC + abstractmethod vs typing.Protocol (structural/duck typing)"),
        ("05", "descriptors",                        "property ke peeche ki machinery: __get__/__set__/__set_name__, data vs non-data"),
        ("06", "slots_and_memory",                   "__slots__ se per-instance memory bachana + gotchas"),
        ("07", "dataclasses",                        "auto init/repr/eq, frozen/slots/order, default_factory trap, vs namedtuple/pydantic"),
        ("08", "metaclasses_and_init_subclass",      "type() class factory, custom metaclass, __init_subclass__ (simpler alt)"),
    ]),
    ("FUNCTIONS", [
        ("09", "closures",                           "Enclosing scope yaad rakhna, nonlocal, late-binding loop gotcha + fix"),
        ("10", "lambda_functions",                   "Kab lambda kab def, key= use, gotchas"),
        ("11", "decorators",                         "wraps, parametrized retry (SAP HANA), class-based with state, stacking order"),
        ("12", "comprehensions_and_functional_tools","comprehensions + walrus + map/filter/reduce + functools + itertools"),
        ("13", "monkey_patching",                    "Runtime me method replace; testing/mock; kab safe kab dangerous"),
    ]),
    ("ITERATION & RESOURCE MGMT", [
        ("14", "iterators_and_generators",           "iterable vs iterator, yield, lazy genexpr, yield from, generator-coroutine"),
        ("15", "context_managers",                   "__enter__/__exit__, @contextmanager, ExitStack, DB transaction CM"),
        ("16", "contextvars",                        "async-safe context-local state (request-id); thread-local kyun toot-ta hai"),
    ]),
    ("CONCURRENCY & PARALLELISM", [
        ("17", "concurrency_parallelism_multitasking","Concurrency vs parallelism, cooperative vs preemptive, context switching"),
        ("18", "gil_mechanics",                      "GIL kya/kyun, IO-bound vs CPU-bound, threads kab help karte hain"),
        ("19", "multithreading_and_sync_primitives", "Race condition demo+fix, Lock/RLock/Semaphore/Event/Condition/Queue"),
        ("20", "multiprocessing",                    "Process/Pool CPU speedup, IPC, pickling, spawn + __main__ guard"),
        ("21", "thread_and_process_pools",           "concurrent.futures: ThreadPool (IO) vs ProcessPool (CPU), as_completed/map"),
        ("22", "asyncio_coroutines_and_async_iter",  "event loop, gather/TaskGroup, blocking trap + to_thread, async gen/with"),
    ]),
    ("MEMORY & SERIALIZATION", [
        ("23", "memory_gc_and_weakref",              "refcount + cyclic GC, reference cycle reclaim, weakref, interning/identity"),
        ("24", "pickling_serialization",             "'cannot pickle lock/conn' crash + __getstate__/__setstate__ fix; security"),
    ]),
    ("BONUS — HIGH INTERVIEW VALUE", [
        ("25", "exceptions_advanced",                "custom hierarchy, raise from, else/finally, ExceptionGroup/except*"),
        ("26", "pattern_matching",                   "match/case destructuring (webhook/event JSON, command dispatch)"),
        ("27", "type_hints_and_runtime_introspection","hints likhna + get_type_hints/get_args/Annotated (FastAPI/Pydantic ka core)"),
    ]),
    ("STDLIB FOR SERVICES (security + ops — interview me bahut aate hain)", [
        ("28", "logging_production",                 "dictConfig, propagation duplicate-log bug, JSON logs, QueueHandler, correlation-id"),
        ("29", "datetime_zoneinfo",                  "UTC discipline: now(utc) vs naive utcnow() footgun, ZoneInfo, naive-vs-aware TypeError"),
        ("30", "hashlib_hmac_secrets",               "password hashing (scrypt+salt), HMAC webhook verify (Exotel-style), secrets vs random"),
    ]),
]

SUGGESTED_ORDER = "09 14 11 15 18 19 22 05 03 23 30 28  ->  phir baaki apni marzi se"


def main() -> None:
    total = sum(len(items) for _, items in TOPICS)
    print("=" * 74)
    print("  INTERVIEW HANDS-ON PRACTICE LAB — Advanced Python (Senior Backend)")
    print(f"  {total} runnable topics | har file: DEMO + BACKEND + BREAK-IT + TODO")
    print("=" * 74)
    for bucket, items in TOPICS:
        print(f"\n  ── {bucket} " + "─" * (66 - len(bucket)))
        for num, slug, desc in items:
            print(f"   {num}  {slug}")
            print(f"       └─ {desc}")
    print("\n" + "=" * 74)
    print("  RUN kaise kare:")
    print("     python 11_decorators.py          # poori file")
    print("     python 11_decorators.py 1 4      # sirf section 1 & 4")
    print(f"\n  Pehle ye order suggest karta hoon (high-value first):")
    print(f"     {SUGGESTED_ORDER}")
    print("\n  Tip: BREAK-IT section sabse zaroori hai — wahi interview gotcha hai.")
    print("=" * 74)


if __name__ == "__main__":
    main()
