"""
DAY 54 — Lazy Imports & Startup Cost: importtime, PEP 562, Cold Start
Architecture Level: Mid → Senior Python Backend (Performance)

WHY THIS MATTERS:
- Heavy modules (pandas, tensorflow, boto3) import hone me 100ms-1s+ le sakte.
  Agar top-level pe import kiya jo har baar process boot pe load hote.
- Serverless (AWS Lambda) cold start = process fresh boot. Har bekaar heavy
  import seedha latency aur $$ me dikhता hai.
- Django/FastAPI worker boot, CLI tool ka first-run lag — sab import cost se
  affected. "Lazy import" yeh selectively defer karne ka tareeka hai.

CORE IDEA:
    Import = code execution (module top-level run hota hai). Jo module har
    code-path me nahi chahiye, usse function/lazy ke andar defer karo — par
    readability cost ke saath. Default: module-level imports (clear). Lazy:
    sirf jab justify ho.
"""

import importlib
import sys
import time


# ============ SECTION 1: Import Cost — measuring ============
#
# Har `import X` pertama baar X.py ka top-level code RUN karta (sys.modules me
# cache hota — doosri baar instant). Heavy libs me ye cost real hai.
#
# TYPICAL ballpark import times (machine pe vary karega):
#   import json      → < 1 ms   (stdlib, light)
#   import requests  → ~50-100 ms
#   import pandas    → ~300-600 ms  (numpy + C ext + bahut submodules)
#   import tensorflow→ ~1-3 s
#
# MEASURE karne ke 2 tareeke:

def demo_measure_import():
    print("=" * 55)
    print("SECTION 1: Import cost measure karna")
    print("=" * 55)

    # (a) time.perf_counter se ek module time karo. NOTE: agar already imported
    #     hai to sys.modules cache se instant — pehle remove karo fresh time ke liye.
    for mod in ("json", "decimal", "fractions"):
        sys.modules.pop(mod, None)        # cache se nikaalo (fresh import)
        t0 = time.perf_counter()
        importlib.import_module(mod)
        dt = (time.perf_counter() - t0) * 1000
        print(f"  import {mod:<12} → {dt:6.2f} ms (first load)")

        t0 = time.perf_counter()
        importlib.import_module(mod)      # ab cached — instant
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"  re-import {mod:<9} → {dt2:6.4f} ms (sys.modules cache hit)")

    # (b) python -X importtime — poora import tree breakdown deta:
    print("\n  CLI tool: python -X importtime -c 'import pandas' 2> imports.log")
    print("    har module ka self/cumulative time stderr pe deta — slowest dhoondo.")
    print("  Alternative: python -X importtime your_app.py 2>&1 | sort -k2 -n -r")


# ============ SECTION 2: Module-level vs Function-level imports ============
#
# DEFAULT: imports file ke top pe (PEP 8). Clear dependencies, ek baar load.
# FUNCTION-LEVEL import justified hota SIRF jab:
#   1. Heavy dependency JO rarely use hoti (ek code path me only)
#   2. CLI subcommands — har subcommand apni deps lazily load kare → fast startup
#   3. Circular import escape — A↔B cycle todne ke liye function ke andar import
#
# COST: readability. Top pe dekh ke pata nahi chalta module kis pe depend karta;
# har call pe import statement chalta (cheap after first, par syntactic noise).

def cli_subcommand_report(fmt):
    """CLI pattern: report command tabhi pandas import kare — baaki commands fast."""
    # Lazy: agar user 'report' kabhi nahi chalata, pandas load hi nahi hoga.
    # import pandas as pd   # <-- yahan, function ke andar (commented; demo me stdlib)
    import csv             # stdlib stand-in for "heavy dep used only here"
    return f"report in {fmt} format (csv module lazily imported = {csv.__name__})"


# Circular import escape demo (concept):
#   module_a.py:  from module_b import helper   # top-level → CIRCULAR if b imports a
#   FIX: a ke function ke andar `from module_b import helper` → import deferred
#        tak jab tak dono module fully loaded na ho. Trade-off hai, design smell bhi.

def demo_module_vs_function():
    print("\n" + "=" * 55)
    print("SECTION 2: Module-level vs function-level imports")
    print("=" * 55)
    print(f"  {cli_subcommand_report('json')}")
    print("  function-level import JUSTIFIED jab:")
    print("    1. heavy dep, rarely-used code path (CLI report → pandas)")
    print("    2. CLI subcommands — startup fast rakhne ke liye per-command lazy")
    print("    3. circular import todne ke liye (last resort, design smell)")
    print("  COST: readability — deps top pe visible nahi; default top-level rakho.")


# ============ SECTION 3: Lazy Import Patterns ============

# (a) importlib.import_module — dynamic import (naam string se)
def load_backend(name):
    """Plugin/driver pattern: backend ka naam config se aata, runtime pe import."""
    # Sirf wahi backend load hoga jo chahiye — baaki import hi nahi honge.
    return importlib.import_module(name)   # e.g. "json", "csv", "myapp.backends.redis"


# (b) PEP 562: module-level __getattr__ — TOP-LEVEL lazy attribute.
#     Jab koi `this_module.heavy` access kare, TAB import ho. Library authors
#     isse public API expose karte bina startup cost ke (e.g. `import mylib;
#     mylib.SomeHeavyThing` heavy thing tabhi load jab actually touch ho).
_HEAVY_CACHE = {}

def __getattr__(name):
    """PEP 562 module __getattr__ — sirf MISSING module attr pe call hota.

    Yahan hum 'heavy_namespace' ko lazily resolve karte hain. Pehli access pe
    import hota, phir cache. Production library me ye real heavy submodule hota.
    """
    if name == "heavy_namespace":
        if name not in _HEAVY_CACHE:
            print("    [lazy] heavy_namespace pehli baar resolve ho raha (import now)")
            _HEAVY_CACHE[name] = importlib.import_module("decimal")  # stand-in heavy
        return _HEAVY_CACHE[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def demo_lazy_patterns():
    print("\n" + "=" * 55)
    print("SECTION 3: Lazy import patterns")
    print("=" * 55)

    # (a) dynamic import
    mod = load_backend("json")
    print(f"  importlib.import_module('json') → {mod.__name__} loaded dynamically")

    # (b) PEP 562 module __getattr__ — yeh module ka apna heavy_namespace touch karo
    this_module = sys.modules[__name__]
    print("  Accessing this_module.heavy_namespace (lazy via PEP 562 __getattr__):")
    ns = this_module.heavy_namespace          # __getattr__ fire → lazy import
    print(f"    resolved to: {ns.__name__}")
    ns2 = this_module.heavy_namespace         # cached — no re-import
    print(f"    second access cached (same obj): {ns is ns2}")


# ============ SECTION 4: Backend angle — cold start & boot time ============

def backend_angle():
    print("\n" + "=" * 55)
    print("SECTION 4: Backend angle — cold start / boot time")
    print("=" * 55)
    notes = """
    SERVERLESS / AWS LAMBDA COLD START:
      Cold start = naya container, fresh Python process, saare top-level imports
      execute. boto3/pandas top pe → har cold start me 100ms-1s+ latency + cost.
      FIX: heavy deps ko handler ke andar lazy import karo (sirf jab code path hit ho),
      ya ZIP/layer minimize karo. Warm invocations me sys.modules cache → free.

    DJANGO / FASTAPI WORKER BOOT:
      Gunicorn/uvicorn har worker boot pe pura app module import karta (models,
      serializers, settings, urls). Bhaari third-party (pandas, tensorflow) jo
      sirf ek view me chahiye → us view ke andar lazy import → worker boot fast,
      memory per-worker kam (lazy load = sirf zaroorat pe RAM).

    PEP 690 (LAZY IMPORTS) — REJECTED, par jaan-na zaroori:
      Proposal tha ki Python me opt-in GLOBAL lazy imports ho (import statement
      deferred tak first use). REJECTED kyunki import side-effects (registration,
      monkeypatch) timing badal jaata aur debugging confusing ho jaata. Idea zinda
      hai third-party tools (lazy_loader, sklearn ka lazy module) me. Aaj bhi manual
      lazy pattern (function-level / PEP 562 __getattr__) hi standard hai.

    MEASURE-THEN-OPTIMIZE:
      Pehle `python -X importtime app.py 2>&1 | sort -k2 -nr | head` se slowest
      imports dhoondo. Blindly sab lazy mat karo — readability cost real hai.
      Sirf measured-heavy + rarely-used deps lazy karo.
    """
    print(notes)


# ============ INTERVIEW QUESTIONS ============
"""
Q1: import statement actually karta kya hai? Dusri baar fast kyun?
A : Pehli baar module ka top-level code RUN hota (functions/classes define, side-effects)
    aur object sys.modules me cache hota. Dusri baar import sys.modules se ready object
    deta — re-execute nahi karta, isliye instant. Heavy cost sirf first import pe.

Q2: Function-level import kab justified hai?
A : (1) Heavy dep jo sirf ek rarely-hit code path me chahiye, (2) CLI subcommands — per
    command lazy load → startup fast, (3) circular import todne ke liye. Cost: readability,
    deps top pe visible nahi. Default PEP 8 = top-level imports.

Q3: python -X importtime kya deta hai?
A : Har imported module ka self + cumulative import time (stderr pe). Startup slowness debug
    karne ka best tool — slowest modules identify karke unhe lazy/remove karte ho.
    Usage: python -X importtime app.py 2>&1 | sort -k2 -nr | head.

Q4: PEP 562 module __getattr__ se lazy import kaise hota?
A : Module me top-level def __getattr__(name) likhne se, jab koi MISSING module-level
    attribute access kare, tab ye call hota. Usme tum heavy submodule lazily import karke
    return karte → library users ko clean API milta bina import-time cost ke. Pehli access
    pe load, phir cache.

Q5: Lambda cold start me imports kaise optimize karein?
A : Heavy deps (boto3 client, pandas) ko handler function ke andar lazy import karo taaki
    code path hit hone pe hi load ho; deployment package chhota rakho. Warm invocations
    sys.modules cache use karte → cost sirf cold start pe ek baar.

Q6: PEP 690 kya thi aur kyun reject hui?
A : Global opt-in lazy imports (import deferred until first use) ka proposal. Reject kyunki
    import side-effects (registration, monkeypatching) ka timing badal jaata, errors late
    surface hote, debugging confusing. Idea third-party lazy_loader / module __getattr__ me
    zinda hai. Aaj manual lazy patterns hi recommended.
"""


if __name__ == "__main__":
    demo_measure_import()
    demo_module_vs_function()
    demo_lazy_patterns()
    backend_angle()
