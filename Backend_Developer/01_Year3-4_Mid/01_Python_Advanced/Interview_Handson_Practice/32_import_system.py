"""
================================================================================
TOPIC: Python Import System — Internals, sys.modules, importlib, Circular Imports
================================================================================

KYA HOTA HAI:
    `import foo` likhne pe Python 5 steps karta hai:
    1. sys.modules mein check karo — agar already wahan hai, seedha return karo
    2. Finder dhundo — sys.meta_path mein registered finders iterate karo
    3. Loader mile to module object banao
    4. Module ko sys.modules mein register karo (execute HONE SE PAHLE)
    5. Module code execute karo

    Ye ORDER critical hai — step 4 (register) step 5 (execute) se pahle isliye
    circular imports kuch hadd tak kaam karte hain.

KYO ZAROORI HAI:
    1. Circular import bugs debug karne ke liye — kyon fail hota hai?
    2. Plugin systems — runtime pe modules load karna
    3. Performance — lazy import, 1000 modules ka startup cost
    4. Monkey-patching at module level — sys.modules directly modify karo
    5. Custom importers — DSL files, .env files, remote configs

KAISE KAAM KARTA HAI (architecture):

    import foo
         │
         ▼
    sys.modules['foo']? ──YES──▶ return cached module (O(1))
         │
         NO
         ▼
    sys.meta_path[0], [1], [2], ... (finders)
         │  BuiltinImporter → C extensions (math, sys, io)
         │  FrozenImporter  → frozen modules (__hello__)
         │  PathFinder      → sys.path pe .py / .pyc files
         ▼
    Loader.exec_module(module)  → module code run karo
         │
         ▼
    return module (already in sys.modules)

KAHAN USE HOTA HAI:
    - Django: app registry dynamically imports INSTALLED_APPS strings
    - FastAPI: `importlib.import_module(settings.AUTH_BACKEND)`
    - pytest: `conftest.py` ko import system ke through discover karta hai
    - Celery: task autodiscovery import system ka use karta hai

INTERVIEW ANSWER (English — recite this):
    "When you write `import foo`, Python first checks sys.modules — if the module
    is cached there, it returns immediately (O(1)). Otherwise it walks sys.meta_path
    to find a loader, creates a module object, registers it in sys.modules BEFORE
    executing the module code, then executes the code. The pre-registration is why
    circular imports partially work — the importing module sees an incomplete module
    object but not a NameError. importlib.import_module() is the programmatic API
    for the same flow, useful for plugin architectures."
================================================================================
"""

import sys
import importlib
import importlib.util
import types

# ============================================================================
# SECTION 1 — sys.modules: THE MODULE CACHE
# ============================================================================
print("=" * 65)
print("SECTION 1 — sys.modules: The Module Cache")
print("=" * 65)

# sys.modules is a plain dict: name → module object
print(f"Total modules loaded right now: {len(sys.modules)}")
print(f"Type of sys.modules: {type(sys.modules)}")

# Check if a module is already cached
print(f"\n'os' in sys.modules: {'os' in sys.modules}")
print(f"'json' in sys.modules: {'json' in sys.modules}")

import json
print(f"'json' in sys.modules AFTER import: {'json' in sys.modules}")
print(f"id(json) == id(sys.modules['json']): {id(json) == id(sys.modules['json'])}")

# Second import = cache hit, no re-execution
import os  # Already in sys.modules — instantly returns cached object
import os as os2
print(f"\nos is os2 (same object): {os is os2}")  # True — same cached module


# ============================================================================
# SECTION 2 — importlib.import_module: PROGRAMMATIC IMPORT
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 2 — importlib.import_module() — Plugin Architecture Pattern")
print("=" * 65)

# Django/FastAPI style: load class from string config
module_name = "collections"
mod = importlib.import_module(module_name)
print(f"importlib.import_module('collections'): {mod}")
print(f"mod.OrderedDict: {mod.OrderedDict}")

# Submodule import with package anchor
# importlib.import_module('.abc', 'collections') == from collections import abc
abc_mod = importlib.import_module(".abc", "collections")
print(f"\nSubmodule import: {abc_mod}")
print(f"Has Mapping: {hasattr(abc_mod, 'Mapping')}")

# Plugin pattern — load class by dotted path string
def load_class(dotted_path: str):
    """Load a class from 'module.submodule.ClassName' string."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

OrderedDict = load_class("collections.OrderedDict")
print(f"\nload_class('collections.OrderedDict'): {OrderedDict}")
print(f"Is the class: {OrderedDict({'a': 1})}")


# ============================================================================
# SECTION 3 — sys.meta_path: CUSTOM FINDERS
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 3 — sys.meta_path: Built-in Finders + Custom Finder")
print("=" * 65)

print("sys.meta_path finders:")
for i, finder in enumerate(sys.meta_path):
    print(f"  [{i}] {finder.__class__.__name__}")
# BuiltinImporter, FrozenImporter, PathFinder — in that order

# Custom finder: intercept 'import secret_config' and return a fake module
class SecretConfigFinder:
    """Returns a fake module for 'import secret_config'."""

    def find_module(self, name, path=None):
        if name == "secret_config":
            return self  # I'll load it
        return None  # Not my responsibility

    def load_module(self, name):
        if name in sys.modules:
            return sys.modules[name]
        mod = types.ModuleType(name)
        mod.DB_PASSWORD = "from-vault-not-plaintext"
        mod.API_KEY = "sk-injected-by-custom-finder"
        sys.modules[name] = mod
        return mod

# Register our custom finder FIRST in sys.meta_path
sys.meta_path.insert(0, SecretConfigFinder())

import secret_config  # Our finder intercepts this!
print(f"\nCustom finder: secret_config.DB_PASSWORD = {secret_config.DB_PASSWORD}")
print(f"Custom finder: secret_config.API_KEY      = {secret_config.API_KEY}")

# Clean up — remove our finder
sys.meta_path.pop(0)
del sys.modules["secret_config"]


# ============================================================================
# SECTION 4 — CIRCULAR IMPORTS: WHY THEY HAPPEN
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 4 — Circular Import Behavior")
print("=" * 65)

# Simulate circular import in-memory using types.ModuleType
# Real scenario: a.py imports b.py, b.py imports a.py

# Fake module 'circ_a' (simulates a.py)
circ_a = types.ModuleType("circ_a")
sys.modules["circ_a"] = circ_a  # Pre-register BEFORE adding attributes

# Now if circ_b tried to import circ_a, it would get the INCOMPLETE object
# (no attributes yet — only the bare module is registered)
circ_a.VALUE = 42  # Now attributes added
circ_a.LABEL = "from circ_a"

# circ_b imports circ_a at import time → gets incomplete object
circ_b = types.ModuleType("circ_b")
sys.modules["circ_b"] = circ_b
circ_b.BORROWED = circ_a.VALUE  # Fine — circ_a.VALUE already set
print(f"circ_b.BORROWED = {circ_b.BORROWED}")

# The REAL problem: circ_a imports from circ_b at module TOP LEVEL,
# and circ_b tries to use circ_a.VALUE before it's set (ImportError: cannot
# import name 'VALUE' from partially initialized module 'circ_a')

print("""
Circular import rules:
  BAD:  # a.py top level:  from b import B_CLASS  (B_CLASS may not exist yet)
  OK:   # a.py function:   def f(): from b import B_CLASS  (deferred = safe)
  OK:   # a.py top level:  import b  (then use b.B_CLASS lazily = safe)
""")

del sys.modules["circ_a"], sys.modules["circ_b"]


# ============================================================================
# SECTION 5 — __all__: WHAT GETS EXPORTED
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 5 — __all__ and 'from module import *'")
print("=" * 65)

# Fake module with __all__
controlled_mod = types.ModuleType("controlled_mod")
controlled_mod.PUBLIC_API = "use this"
controlled_mod.INTERNAL = "_dont_use_this"
controlled_mod._private = "definitely not"
controlled_mod.__all__ = ["PUBLIC_API"]  # Only this exported by 'import *'

sys.modules["controlled_mod"] = controlled_mod

# from controlled_mod import *  → only PUBLIC_API
# Normally: exec("from controlled_mod import *") would work
# Demonstrate __all__ inspection:
print(f"controlled_mod.__all__ = {controlled_mod.__all__}")
print(f"All attributes: {[a for a in dir(controlled_mod) if not a.startswith('__')]}")
print(f"Public API (via __all__): {controlled_mod.__all__}")

del sys.modules["controlled_mod"]


# ============================================================================
# SECTION 6 — LAZY IMPORT PATTERN (startup optimization)
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 6 — Lazy Import for Startup Performance")
print("=" * 65)

import time

# Eager import at module top level — always pays the cost
start = time.perf_counter()
import hashlib  # Already cached, fast here — but imagine heavy module
t_eager = time.perf_counter() - start
print(f"Eager import (already cached): {t_eager*1000:.3f}ms")

# Pattern 1: Import inside function — deferred until first call
def get_hashlib():
    import hashlib  # Only pays cost on first call
    return hashlib

# Pattern 2: _module = None + lazy init
_pandas = None
def get_pandas():
    global _pandas
    if _pandas is None:
        _pandas = importlib.import_module("pandas") if "pandas" in sys.modules else None
        if _pandas is None:
            print("  pandas not available — using fallback")
    return _pandas

result = get_pandas()  # None — pandas not installed in this env, graceful fallback
print(f"Lazy pandas: {result}")

# Pattern 3: importlib.util.find_spec — check without importing
spec = importlib.util.find_spec("json")
print(f"\nimportlib.util.find_spec('json'): {spec is not None} (found: {spec})")
spec_missing = importlib.util.find_spec("nonexistent_package_xyz")
print(f"find_spec('nonexistent_package_xyz'): {spec_missing}")  # None — not installed


# ============================================================================
# SECTION 7 — sys.path: WHERE PYTHON LOOKS
# ============================================================================
print("\n" + "=" * 65)
print("SECTION 7 — sys.path and __file__")
print("=" * 65)

print("sys.path (first 5 entries):")
for p in sys.path[:5]:
    print(f"  {p!r}")

# sys.path is just a list — you can append to it dynamically
# (Useful in scripts, NOT in libraries)
print(f"\nTotal sys.path entries: {len(sys.path)}")
print(f"Current file: {__file__ if '__file__' in dir() else 'interactive'}")
print(f"Module name: {__name__}")


# ============================================================================
# BREAK-IT — Common Import Mistakes
# ============================================================================
print("\n" + "=" * 65)
print("BREAK-IT — Common Import Mistakes")
print("=" * 65)

# BUG 1: Circular import with top-level 'from' import
print("""Bug 1 — Circular import:
  # a.py:  from b import Foo   ← fails if b.py imports a at top level
  Fix: import b  (module import, not name import) OR move import inside function
""")

# BUG 2: Modifying sys.modules directly (monkey-patch)
import json as real_json
original = sys.modules["json"]
fake_json = types.ModuleType("json")
fake_json.dumps = lambda x, **kw: f"FAKED:{x}"
sys.modules["json"] = fake_json

import json  # Gets the fake one!
print(f"Bug 2 — sys.modules monkey-patch: json.dumps({{}}) = {json.dumps({})}")

sys.modules["json"] = original  # Restore
import json
print(f"  Restored: json.dumps({{}}) = {json.dumps({})}")

# BUG 3: __init__.py not present — package not recognized (Python <3.3)
# Python 3.3+ allows namespace packages (no __init__.py needed)
# but explicit __init__.py is still best practice
print("""
Bug 3 — Missing __init__.py in Python <3.3:
  mypackage/
    mymodule.py   (no __init__.py)
  → from mypackage import mymodule  ← ImportError in Python <3.3
  Fix: touch mypackage/__init__.py
""")

# BUG 4: Import at wrong scope causes unexpected re-imports
print("""Bug 4 — Relative vs absolute import confusion:
  Inside a package, 'import utils' can mean different things.
  Use explicit relative: from . import utils
  Or explicit absolute: from mypackage import utils
""")


# ============================================================================
# TODO — Django-style app registry
# ============================================================================
"""
Django INSTALLED_APPS mein strings hoti hain:
  INSTALLED_APPS = ['django.contrib.auth', 'myapp.apps.MyAppConfig']

Implement ek AppRegistry class jo:
  1. `register(dotted_path: str)` — importlib se module load karo
  2. `get_app(name: str)` — registered module return karo
  3. `list_apps()` — sab registered app names return karo

Verify:
  - registry.register('collections') → load karo
  - registry.get_app('collections').OrderedDict → accessible hona chahiye
  - registry.register('collections') twice → second call sys.modules se aaye (no re-load)
  - registry.register('nonexistent_xyz') → graceful error with meaningful message
"""

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("RUN: python 32_import_system.py")
    print("Sab sections automatically run hote hain above.")
    print("TODO: Implement Django-style AppRegistry at the bottom.")
    print("=" * 65)
