# 02_Python_Daily — Python Mastery Track

This folder contains the full Python curriculum organised across three complementary tracks.
All three cover the same body of knowledge; they differ only in format and study pace.

---

## Folder Structure at a Glance

```
02_Python_Daily/
│
├── Day01_Variables_Basics/           ← daily-drip track (55 folders)
├── Day02_Control_Flow_Loops/
├── Day03_String_Problems/
│   ...
├── Day53_GapFill_Core_Part1/
├── Day53_GapFill_Core_Part2/
├── Day54_GapFill_Advanced/
├── Day55_GapFill_Concurrency_Memory/
│
├── Complete_Theory/                  ← consolidated reference (10 files)
│   ├── 01_Core_Python_Theory.py
│   ├── 02_Functions_Closures_Decorators_Theory.py
│   ├── 03_OOP_Theory.py
│   ├── 04_Async_Concurrency_Theory.py
│   ├── 05_Collections_Functools_Itertools_Theory.py
│   ├── 06_Typing_System_Theory.py
│   ├── 07_Memory_Performance_Theory.py
│   ├── 08_Design_Patterns_Theory.py
│   ├── 09_Modern_Python_Theory.py
│   └── 10_Regex_Testing_Enum_StdLib_Theory.py
│
├── Complete_Practical/               ← consolidated exercises (3 sections)
│   ├── Section_01_Basics/            (6 files — variables → exceptions)
│   ├── Section_02_Intermediate/      (4 files — OOP, async, concurrency)
│   └── Section_03_Advanced/          (3 files — typing, patterns, internals)
│
└── *.html                            ← quick-reference cheat sheets
```

---

## The Three Tracks

### 1. Day-by-Day Track (`Day01` … `Day55`)

Fifty-five topic-scoped folders, each containing 2–6 Python files that build on the
previous day. The progression moves from absolute basics (variables, control flow,
strings) through data structures and algorithms (Days 20–25), the Python standard
library in depth (Days 26–40), and production-grade topics (Days 41–55: FastAPI,
SQLAlchemy, Celery, gRPC, Docker, advanced concurrency, and memory internals).

Use this track when you want a structured, incremental study schedule — one folder
per sitting keeps each session focused and achievable.

**Progression overview:**

| Days    | Theme                                      |
|---------|--------------------------------------------|
| 01–10   | Core language: types, OOP, decorators, async |
| 11–19   | Algorithms, concurrency, advanced OOP      |
| 20–25   | DSA: arrays, linked lists, trees, graphs, DP |
| 26–35   | Standard library deep-dives                |
| 36–43   | Modern Python, testing, regex, CLI         |
| 44–49   | Backend stack: FastAPI, SQLAlchemy, Celery, gRPC, Docker |
| 50–55   | Senior topics: contextvars, concurrency, GC, gap-fills |

---

### 2. Complete Theory (`Complete_Theory/`)

Ten heavily-annotated Python files, each corresponding to a major topic area. Every
file is pure theory: concept explanations, syntax summaries, and illustrative snippets
kept short enough to read in one sitting.

Use this track when you need a fast refresher before an interview, or when you want to
look up how a concept works without running code.

**Mapping to the daily track:**

| Theory file                                      | Equivalent days         |
|--------------------------------------------------|-------------------------|
| 01_Core_Python_Theory.py                         | Day01–Day06             |
| 02_Functions_Closures_Decorators_Theory.py       | Day07, Day10, Day15–16  |
| 03_OOP_Theory.py                                 | Day08–Day09, Day19, Day39 |
| 04_Async_Concurrency_Theory.py                   | Day13–Day14, Day17, Day31 |
| 05_Collections_Functools_Itertools_Theory.py     | Day26–Day28             |
| 06_Typing_System_Theory.py                       | Day29                   |
| 07_Memory_Performance_Theory.py                  | Day35, Day55            |
| 08_Design_Patterns_Theory.py                     | Day18–Day19             |
| 09_Modern_Python_Theory.py                       | Day38                   |
| 10_Regex_Testing_Enum_StdLib_Theory.py           | Day40–Day42             |

---

### 3. Complete Practical (`Complete_Practical/`)

Thirteen end-to-end practice files grouped into three sections (Basics, Intermediate,
Advanced). Each file integrates multiple concepts into realistic, runnable examples —
patterns you would actually write in a backend or Agentic AI codebase.

See `Complete_Practical/README.md` for the detailed contents of every file and a
recommended 11-day study order through this section alone.

Use this track when you want hands-on problem-solving practice, or when you are
preparing for a technical screen and need to write — not just read — idiomatic Python.

---

## Where to Start

| Goal                                        | Start here                                    |
|---------------------------------------------|-----------------------------------------------|
| Build knowledge from zero, one day at a time | `Day01_Variables_Basics/`                     |
| Rapid review of a specific topic             | Matching file in `Complete_Theory/`           |
| Practice writing production-quality code    | `Complete_Practical/Section_01_Basics/`       |
| Interview prep (read + code in 11 days)     | `Complete_Practical/` — see its README        |
| Reference a cheat sheet quickly             | `*.html` files in this folder                 |

There is no single "correct" path. Most learners do best by combining all three:
follow the daily track for structure, consult Complete_Theory when a concept needs
clarification, and use Complete_Practical to confirm that understanding through code.

---

## Topic Coverage

The curriculum covers everything expected of a Python backend developer at the
0–5 year experience range, including topics commonly tested in technical interviews:

- Core language: data types, control flow, functions, closures, comprehensions
- OOP: inheritance, mixins, ABCs, dunder methods, metaclasses, descriptors
- Concurrency: threading, multiprocessing, asyncio (Tasks, gather, TaskGroup, queues)
- Standard library: collections, functools, itertools, typing, pathlib, logging, regex
- Backend stack: FastAPI, SQLAlchemy + Alembic, Celery + Redis, gRPC, Docker
- Algorithms and DSA: two-pointer, sliding window, linked lists, trees, graphs, DP, heaps
- Python internals: GIL, reference counting, GC, `__slots__`, profiling, bytecode
- Modern Python (3.10–3.13): match-case, TypeAlias, Self, PEP 695 generics, sub-interpreters
