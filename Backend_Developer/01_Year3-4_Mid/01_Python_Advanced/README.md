# 🐍 Python Advanced

> **34 theory + 16 practical + 30-file hands-on drill set.** Yeh mid-track ka sabse bada module hai (~47k lines).
> "Python aata hai" aur "Python **internals** aate hain" ka farq yahin banta hai — senior interview isi pe judge karta hai.

---

## 🔴 Interview ke liye pehle yeh 6

| # | Topic | Classic question |
|---|---|---|
| [03](theory/03_memory_gil.md) | **Memory model + GIL** | "GIL kya hai, kab problem hai, kab nahi?" |
| [05](theory/05_async_concurrency_deep_dive.md) | **Async concurrency deep** | "asyncio vs threading vs multiprocessing — kab kya?" |
| [26](theory/26_concurrency_decision_framework.md) | **Concurrency decision framework** | Upar wale ka structured jawab |
| [06](theory/06_metaclasses_descriptors.md) | **Metaclasses + descriptors** | "Django ORM `Model` class kaise kaam karta hai?" |
| [11](theory/11_race_conditions_debugging.md) · [12](theory/12_deadlock_debugging.md) | **Race conditions + deadlocks** | "Production me race condition kaise debug kiya?" |
| [18](theory/18_modern_python_3_11_12_13.md) | **Modern Python 3.11–3.13** | Free-threading, exception groups, `TaskGroup` — current dikhne ke liye |

---

## 📚 Poori list

### Core language internals
| # | Topic | # | Topic |
|---|---|---|---|
| [01](theory/01_pydantic_v2.md) | Pydantic v2 | [02](theory/02_abc_protocols.md) | ABC + Protocols |
| [03](theory/03_memory_gil.md) 🔴 | Memory model + GIL | [04](theory/04_type_annotations.md) | Type annotations |
| [06](theory/06_metaclasses_descriptors.md) 🔴 | Metaclasses + descriptors | [09](theory/09_slots_deep_dive.md) | `__slots__` |
| [10](theory/10_weakref_deep_dive.md) | weakref | [23](theory/23_python_internals_bytecode.md) | Internals + bytecode |
| [19](theory/19_type_hints_advanced.md) | Type hints advanced | [08](theory/08_cpython_vs_pypy.md) | CPython vs PyPy |

### Concurrency 🔴
| # | Topic | # | Topic |
|---|---|---|---|
| [05](theory/05_async_concurrency_deep_dive.md) 🔴 | Async deep dive | [16](theory/16_async_advanced_patterns.md) | Async advanced patterns |
| [11](theory/11_race_conditions_debugging.md) 🔴 | Race conditions | [12](theory/12_deadlock_debugging.md) 🔴 | Deadlocks |
| [13](theory/13_uvloop_deep_dive.md) | uvloop | [34](theory/34_structured_concurrency_anyio_trio.md) | Structured concurrency (anyio/trio) |
| [26](theory/26_concurrency_decision_framework.md) 🔴 | Decision framework | | |

### Performance + debugging
| # | Topic | # | Topic |
|---|---|---|---|
| [07](theory/07_performance_profiling.md) | Profiling | [14](theory/14_pyspy_scalene_profiling.md) | py-spy + scalene |
| [27](theory/27_performance_optimization.md) | Optimization | [24](theory/24_debugging_production.md) | Production debugging |
| [22](theory/22_serialization_comparison.md) | Serialization comparison | [17](theory/17_http_clients_complete.md) | HTTP clients |

### Production practices
| # | Topic | # | Topic |
|---|---|---|---|
| [15](theory/15_mypy_ruff_production.md) | mypy + ruff at scale | [20](theory/20_logging_production_deep.md) | Logging deep |
| [21](theory/21_stdlib_networking_security.md) | stdlib networking/security | [25](theory/25_python_antipatterns.md) | Anti-patterns |
| [28](theory/28_packaging_distribution.md) | Packaging | [29](theory/29_cli_frameworks.md) | CLI frameworks |
| [31](theory/31_documentation_sphinx.md) | Sphinx docs | [32](theory/32_project_structure_12factor.md) | Project structure / 12-factor |
| [30](theory/30_library_comparisons.md) | Library comparisons | [33](theory/33_pyo3_rust_extensions.md) | PyO3 / Rust extensions |
| [18](theory/18_modern_python_3_11_12_13.md) 🔴 | Modern Python 3.11–3.13 | | |

---

## 🧪 Hands-on — [`Interview_Handson_Practice/`](Interview_Handson_Practice/)

30 files ka drill set with a menu runner. **Yahi asli practice hai** — theory padhne se GIL samajh nahi aata, code chala ke aata hai.

```bash
cd Interview_Handson_Practice && python 00_INDEX.py
```

Runnable code: [`practical/`](practical/) (16 files)

**Related:** [15_Design_Patterns_SOLID](../15_Design_Patterns_SOLID/README.md) · [Junior Python Daily](../../00_Year0-2_Junior/02_Python_Daily/) · [Testing](../../00_Year0-2_Junior/10_Testing/README.md)
