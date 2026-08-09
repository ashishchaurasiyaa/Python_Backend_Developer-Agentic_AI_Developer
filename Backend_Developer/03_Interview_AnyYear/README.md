# 03_Interview_AnyYear

Interview preparation material for backend engineer roles — applicable regardless of experience level. Covers algorithmic problem-solving, verbal and written interview formats, and portfolio projects that demonstrate production-grade engineering.

---

## Directory Overview

```
03_Interview_AnyYear/
├── 01_DSA/               # 28 topic folders, each with theory.py + problems.py
├── 02_Interview_Prep/    # Flashcard & cookbook documents (files numbered 05–12)
└── 03_Projects/          # 10 portfolio project specifications
```

---

## 01_DSA — Data Structures & Algorithms

Each topic lives in its own folder and contains exactly two files:

- `theory.py` — annotated reference implementations, complexity analysis, and pattern notes
- `problems.py` — curated problems with solutions and explanation comments

Additional cross-cutting references at the top level:

- [`00_Coding_Patterns_Index.md`](01_DSA/00_Coding_Patterns_Index.md) — pattern-recognition lens across all 28 topics (33 patterns with canonical LeetCode problems and "when to use" triggers)
- [`TOP_INTERVIEW_QUESTIONS.md`](01_DSA/TOP_INTERVIEW_QUESTIONS.md) — **90 curated problems** (Blind 75 / Grind 75 / Top 150 overlap), organised topic → approach → difficulty
- `2_Month_DSA_5_Problems_Per_Day.docx` — structured 2-month daily practice schedule
- `2_Month_DSA_5_Problems_Per_Day_WITH_LINKS_AND_COMPANY_TAGS.docx` — same schedule with LeetCode links and company frequency tags

### 🔴 `practice/` — write-and-verify harness (this is the actual practice loop)

Reading solutions builds false confidence. [`01_DSA/practice/`](01_DSA/practice/) makes you **write** the code and
tests it against real cases — **35 problems** covering every major pattern (trie, union-find, Dijkstra,
monotonic queue, two-heaps median, k-way merge, cyclic sort included).

```bash
cd 01_DSA/practice
python harness.py --list          # what's available
python harness.py --stats         # your progress
```

See [`practice/README.md`](01_DSA/practice/README.md) for the timed-practice protocol.

### Topic List

| # | Folder | Core Concepts |
|---|--------|---------------|
| 01 | `01_Arrays_Hashing` | Hash maps, frequency counting, prefix sums |
| 02 | `02_Strings` | Sliding window, KMP, Rabin-Karp, anagram detection |
| 03 | `03_Linked_List` | Reversal, cycle detection, merge, fast/slow pointers |
| 04 | `04_Stack_Queue` | Monotonic stack, deque, expression evaluation |
| 05 | `05_Binary_Search` | Classic and search-on-answer variants |
| 06 | `06_Two_Pointers_Sliding_Window` | Fixed and variable windows, sorted-array patterns |
| 07 | `07_Recursion_Backtracking` | Permutations, combinations, pruning strategies |
| 08 | `08_Sorting_Algorithms` | Merge sort, quick sort, counting sort, comparator tricks |
| 09 | `09_Trees` | BST, traversal, LCA, serialization, diameter |
| 10 | `10_Heaps_Priority_Queue` | Min/max heap, top-K, k-way merge |
| 11 | `11_Graphs_BFS_DFS` | BFS/DFS, cycle detection, connected components, topological sort |
| 12 | `12_Dynamic_Programming` | 1-D and 2-D DP, memoization vs. tabulation |
| 13 | `13_Greedy` | Interval scheduling, activity selection, greedy proofs |
| 14 | `14_Trie` | Prefix tree, autocomplete, word search |
| 15 | `15_Advanced_Graphs` | Dijkstra, Bellman-Ford, Floyd-Warshall, Prim, Kruskal |
| 16 | `16_Bit_Manipulation` | XOR tricks, bit masking, power-of-two checks |
| 17 | `17_Intervals` | Merge, insert, sweep line, meeting rooms |
| 18 | `18_Segment_Tree_Fenwick` | Range queries, point updates, BIT (Fenwick tree) |
| 19 | `19_Math_Number_Theory` | GCD/LCM, sieve, modular arithmetic, fast exponentiation |
| 20 | `20_Matrix_Grid` | BFS on grid, spiral traversal, island problems |
| 21 | `21_String_DP` | Edit distance, longest common subsequence, palindrome DP |
| 22 | `22_Monotonic_Queue` | Sliding window maximum, next greater element |
| 23 | `23_Game_Theory_Randomized` | Minimax, Sprague-Grundy, reservoir sampling |
| 24 | `24_Concurrency_Threading` | Python threading primitives, lock patterns, producer-consumer |
| 25 | `25_Sparse_Table_RMQ` | Range minimum query in O(1) after O(n log n) build |
| 26 | `26_Suffix_Structures` | Suffix array, suffix automaton, LCP array |
| 27 | `27_Digit_DP` | Count numbers satisfying digit-level constraints |
| 28 | `28_Bitmask_DP` | Subset enumeration DP, TSP-style problems |

---

## 02_Interview_Prep — Flashcards & Cookbooks

> **Note on numbering:** Files in this section are numbered starting at **05**. Files 01–04 existed in an earlier layout and were consolidated or removed during a curriculum restructuring; the gap is intentional and does not indicate missing content.

| File | Title | What It Covers |
|------|-------|----------------|
| `05_backend_system_design_50q.md` | 50 Backend System Design Questions | Q&A format with short answer, deep explanation, and trade-offs. Covers CAP theorem, database selection, caching, message queues, rate limiting, and more. |
| `06_backend_coding_round_patterns.md` | Backend Coding Round Patterns | Implementation recipes for common 45-minute backend coding rounds — API design under constraints, DB schema, and algorithmic patterns asked specifically in backend roles. |
| `07_python_tricky_questions.md` | Python Tricky Interview Questions | Senior-level gotchas: mutable defaults, GIL implications, `__slots__`, descriptors, metaclasses — each with a code snippet, predicted output, and production relevance. |
| `08_sql_interview_questions.md` | SQL Interview Questions | Window functions, CTEs, query optimization, indexing strategies, and real-world schema questions from senior backend interviews. |
| `09_debugging_scenarios.md` | Backend Debugging Scenarios | Production triage playbook using STAR format — memory leaks, N+1 queries, race conditions, slow endpoints, and on-call incident walkthroughs. |
| `10_behavioral_backend.md` | Behavioral Interview — STAR Templates | Pre-written STAR stories covering conflict, ownership, technical leadership, failure recovery, and cross-functional collaboration. |
| `11_resume_walkthrough_prep.md` | Resume Walkthrough Prep | Frameworks for narrating past projects to sound senior — impact quantification, technical depth cues, and how to handle gaps or pivots. |
| `12_negotiation_offer.md` | Offer Negotiation Guide | Salary anchoring, competing-offer leverage, counter-offer scripts, and how to handle stock vs. cash trade-offs for backend engineer roles. |
| [`INFOSYS_QUICK_REVISION.md`](02_Interview_Prep/INFOSYS_QUICK_REVISION.md) | Service-company rapid revision | Condensed Python/Django/SQL revision sheet built for a short-notice service-company screen. Useful for any quick refresher round. |

> **GenAI / LLM interview questions** (RAG design, agent orchestration, eval) live in the agentic track:
> [`Agentic_AI/Interview_Prep/`](../../Agentic_AI/Interview_Prep/).
> **System design drills** (timed, with rubric) live in [`02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md`](../02_Year5%2B_Senior/01_System_Design/PRACTICE_DRILLS.md).

---

## 03_Projects — Portfolio Project Specifications

Ten end-to-end backend projects with full tech-stack definitions, architecture notes, and implementation guidance. Designed to be resume-worthy and demonstrable in interviews.

| # | File | Project | Primary Stack |
|---|------|---------|---------------|
| 1 | `01_FastAPI_Multi_Tenant_SaaS.md` | Multi-Tenant SaaS API Platform | FastAPI, Postgres, Redis, Celery, Stripe, Docker, AWS |
| 2 | `02_FastAPI_RealTime_Whiteboard.md` | Real-Time Collaborative Whiteboard | FastAPI, WebSocket, Y.js (CRDT), Redis, Postgres, S3, Cloudflare |
| 3 | `03_FastAPI_URL_Shortener_Scale.md` | URL Shortener at Scale (Bitly-clone) | FastAPI, Postgres, Redis, Kafka, ClickHouse, Cloudflare |
| 4 | `04_FastAPI_WhatsApp_Lite_Chat.md` | WhatsApp-lite Chat Backend | FastAPI, WebSocket, Cassandra, Redis, Kafka, FCM/APNs |
| 5 | `05_Django_Banking_Fintech.md` | Banking / Fintech Backend | Django 5, DRF, Postgres, Redis, Celery, Kafka, WeasyPrint |
| 6 | `06_Django_HR_Payroll.md` | HR & Payroll Management System | Django 5, DRF, Postgres, Redis, Celery, WeasyPrint |
| 7 | `07_Django_Food_Delivery.md` | Food Delivery Backend (Swiggy/Zomato-lite) | Django 5, DRF, Channels, Postgres, Redis (geo), H3, Kafka |
| 8 | `08_FastAPI_OpenAI_RAG_Backend.md` | FastAPI + OpenAI RAG Backend | FastAPI, Postgres + pgvector, OpenAI/Claude, Redis, Celery, Cohere Rerank |
| 9 | `09_Realtime_AI_Chat_App.md` | Real-Time AI Chat App (ChatGPT-style) | FastAPI, WebSocket/SSE, Postgres, Redis, Anthropic, OpenAI, Stripe |
| 10 | `10_MCP_Server_FastAPI.md` | MCP Server for FastAPI (AI Tool Platform) | FastAPI, Python MCP SDK, Starlette, Postgres, OAuth 2.1, Cloudflare |

### 🏗️ Starter scaffolds — don't start from an empty folder

Every spec has a matching **`<same-name>_starter/`** directory (e.g. `01_FastAPI_Multi_Tenant_SaaS.md`
→ [`01_FastAPI_Multi_Tenant_SaaS_starter/`](03_Projects/01_FastAPI_Multi_Tenant_SaaS_starter/)) with a
README, entry point, and dependency file so you can begin immediately.

[`08_FastAPI_OpenAI_RAG_Backend_starter/`](03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/) is the most
developed (config, db, routers, retrieval packages) — the best one to harden first if you want a single
strong portfolio project.

> **Pick ONE and go deep.** Ten half-built projects are worth less in an interview than one that is
> tested, observable, and deployed. [DAILY_PLAN_90_DAYS.md](../../DAILY_PLAN_90_DAYS.md) recommends
> hardening project 01 as the proof-project.

---

## Suggested Study Order

1. **Warm-up (2 weeks):** Topics 01–08 in `01_DSA` — foundational patterns that appear in almost every screen.
2. **Core algorithms (4 weeks):** Topics 09–20 — trees, graphs, DP, and greedy make up the bulk of medium/hard interview problems.
3. **Advanced patterns (2 weeks):** Topics 21–28 — competitive-programming-level material; valuable for senior or FAANG-track interviews.
4. **Parallel track:** Work through `02_Interview_Prep` files 05–12 during the same period as DSA study to build system design and behavioral fluency simultaneously.
5. **Project build (ongoing):** Select one project from `03_Projects` that matches your target role (startup vs. enterprise, AI vs. pure backend) and build it end-to-end to anchor interview stories.
