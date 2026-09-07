# 01_System_Design — HLD + LLD

## Start here

| File | What it's for |
|---|---|
| [`SYSTEM_DESIGN_CHECKLIST.md`](SYSTEM_DESIGN_CHECKLIST.md) | The framework to run in your head during any design interview — requirements → estimation → API → data model → scaling → bottlenecks. |
| [`PRACTICE_DRILLS.md`](PRACTICE_DRILLS.md) | 🔴 Timed, self-graded drills — the "bolke design karna" loop. Reading `HLD_Problems/` builds recognition; this builds the ability to perform under a clock. |
| [`00_Pattern_Topic_Index.md`](00_Pattern_Topic_Index.md) | Pattern-wise / concept-wise reverse index — same lens as DSA's `Coding_Patterns_Index.md`: which LLD design pattern and which HLD concept shows up in which problem. |

## The six folders

| Folder | Count | What it is |
|---|---|---|
| [`HLD_Theory/`](HLD_Theory/) | 67 notes | Core theory — CAP, consistency, caching, sharding, indexing, protocols, auth, observability, consensus, probabilistic structures. Numbered 01→67, roughly foundations-first. |
| [`HLD_Problems/`](HLD_Problems/) | 37 designs | Full walkthroughs (requirements → estimation → architecture → deep dive → failure modes → interview Qs) for real systems — Twitter, WhatsApp, Netflix, Uber, RAG, ChatGPT backend, and more. See its own [README](HLD_Problems/README.md) for the category breakdown and suggested order. |
| [`HLD_Code/`](HLD_Code/) | 5 implementations | Runnable Python for CQRS/event sourcing, saga orchestration, circuit breaker, rate limiter, consistent hashing. Thin relative to the theory — bloom filter, outbox pattern, idempotency store, vector clocks/CRDT, and leader election are covered in theory but have no runnable version yet. |
| [`LLD_Theory/`](LLD_Theory/) | 28 notes | All 23 GoF patterns, plus OOP fundamentals, SOLID, UML, DB design, concurrency/thread safety, event sourcing + CQRS. |
| [`LLD_Problems/`](LLD_Problems/) | 20 problems | Class-design / machine-coding problems, levelled 1–3 (LRU Cache and Parking Lot first). See its own [README](LLD_Problems/README.md) for the day-by-day interview plan. No runnable practice harness yet — unlike DSA's `practice/`, these are prose + inline code blocks, not stub-and-test files. |
| [`Design_Patterns_Code/`](Design_Patterns_Code/) | 16 projects | 10 runnable Django mini-projects (patterns 01–14) + 6 standalone scripts (15–20), built against a shared B2B ERP scenario. See its own [README](Design_Patterns_Code/README.md) for setup and port assignments. |

## Suggested order

1. **HLD foundations** — `HLD_Theory` 01→31, then 32→67.
2. **LLD foundations** — `LLD_Theory/OOP_Fundamentals.md` + `SOLID_Principles.md`, then the 21 numbered GoF notes in order.
3. **Hands-on code** — run `Design_Patterns_Code/` locally; trace `HLD_Code/` end to end.
4. **Problem practice** — `LLD_Problems/` (attempt before reading the model answer), then `HLD_Problems/` starting with the classic warm-ups.

Full detail and a week-by-week reading sequence: [`../README.md`](../README.md).
