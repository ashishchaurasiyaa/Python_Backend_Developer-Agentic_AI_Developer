# ✅ COMPULSORY TOPICS CHECKLIST — Python Backend + Agentic AI (Product Companies)

> **Purpose:** The single "what MUST I know" surface for the 3-month switch. Not a daily plan (that's [DAILY_PLAN_90_DAYS.md](DAILY_PLAN_90_DAYS.md)) — this is the *coverage map*. If a topic here is 🔴 and you can't explain it out loud in English in 2 minutes, it's a hole to close before you interview.
>
> **Created 2026-07-15.** Priority tiers:
> - 🔴 **COMPULSORY** — every product-company interview touches this. No exceptions. Must be able to *speak* it, not just recognize it.
> - 🟡 **SHOULD-KNOW** — commonly asked; JD-dependent but expect ~70% of roles to probe it.
> - ⚪ **JD-SPECIFIC** — learn only if the job description names it. Don't spend general prep time here.
>
> Tick `- [ ]` → `- [x]` as each sub-topic reaches "can explain out loud". A topic isn't done when you've *read* it — it's done when you can *say* it.

---

## 🔴 TIER 1 — COMPULSORY (the non-negotiable core)

### 1. Python Core + Advanced → [01_Python_Advanced](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced) · [Interview_Handson_Practice](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/Interview_Handson_Practice)
- [ ] OOP (classes, inheritance, MRO/super, dunder methods, `@property`)
- [ ] Abstract base classes vs Protocols; duck typing
- [ ] Decorators (function + class), closures, `functools`
- [ ] Generators, iterators, `yield`, lazy evaluation
- [ ] Context managers (`with`, `__enter__/__exit__`, `contextlib`)
- [ ] Comprehensions, `itertools`, `functools`
- [ ] **Concurrency:** threading vs multiprocessing vs asyncio — when to use which
- [ ] **The GIL** — what it is, time-based switch (~5ms), why threads don't speed up CPU work
- [ ] `async`/`await`, event loop, `asyncio.gather`, async generators
- [ ] Data model: `dataclasses`, `__slots__`, descriptors
- [ ] Type hints + `mypy`/`ruff` (say you use them — cheap credibility win)
- [ ] Exceptions (custom, chaining, `else/finally`), memory/GC/refcounting basics

### 2. DSA — Data Structures & Algorithms → [01_DSA](Backend_Developer/03_Interview_AnyYear/01_DSA) · [00_Coding_Patterns_Index](Backend_Developer/03_Interview_AnyYear/01_DSA/00_Coding_Patterns_Index.md)
> ⚠️ **Your weakest gate and the one most likely to fail you. Daily, from now.** Target ~150 problems.
- [ ] Arrays & Hashing, Strings, Two Pointers, Sliding Window
- [ ] Stack/Queue, Linked List, Binary Search
- [ ] Recursion & Backtracking, Sorting
- [ ] Trees (BST, traversals), Heaps / Priority Queue
- [ ] Graphs (BFS/DFS, topological sort, Dijkstra)
- [ ] Dynamic Programming (1D, 2D, string DP), Greedy, Intervals
- [ ] Bit Manipulation, Trie
- [ ] Big-O analysis — state time/space for every solution out loud
- ⚪ Advanced (only if targeting FAANG-tier): Segment Tree/Fenwick, Suffix structures, Digit DP, Bitmask DP

### 3. Web Framework — go DEEP on ONE (both listed; pick primary)
**FastAPI** → [06_FastAPI](Backend_Developer/00_Year0-2_Junior/06_FastAPI)
- [ ] Pydantic models (v2), request/response validation
- [ ] Dependency injection (`Depends`), sub-dependencies
- [ ] Async endpoints, background tasks, lifespan events
- [ ] Path/query/body params, status codes, error handling
- [ ] Middleware, CORS, auth (OAuth2/JWT), rate limiting

**Django + DRF** → [07_Django_DRF](Backend_Developer/00_Year0-2_Junior/07_Django_DRF) · [00_django_basics_definition](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/00_django_basics_definition.md)
- [ ] **What Django is** — MVT pattern, plain-English pitch (the gap that started your plan)
- [ ] ORM: models, migrations, querysets, `select_related`/`prefetch_related` (N+1 fix)
- [ ] Middleware, signals, settings, apps structure
- [ ] **DRF:** serializers, ViewSets, routers, generics
- [ ] DRF auth (Token/JWT/Session), permissions, throttling, pagination

### 4. REST API Design → [02_API_Design](Backend_Developer/01_Year3-4_Mid/02_API_Design)
- [ ] HTTP verbs, idempotency, status codes (know 2xx/4xx/5xx cold)
- [ ] Resource naming, statelessness, REST vs RPC
- [ ] **Versioning** (URL/header), **pagination** (offset/cursor)
- [ ] Error format — **RFC 7807** (problem+json)
- [ ] Auth: JWT vs session vs API keys, OAuth2 flow
- [ ] Rate limiting, idempotency keys, HATEOAS (recognize)
- [ ] Request validation, content negotiation

### 5. Databases & SQL → [04_Database_SQL](Backend_Developer/00_Year0-2_Junior/04_Database_SQL) · [05_MySQL](Backend_Developer/00_Year0-2_Junior/05_MySQL)
- [ ] SQL: joins, GROUP BY, subqueries, window functions, CTEs
- [ ] Indexing — B-tree, when indexes help/hurt, composite/covering
- [ ] **Transactions & ACID**, isolation levels + anomalies (dirty/non-repeatable/phantom)
- [ ] Locking, deadlocks, `SELECT ... FOR UPDATE`
- [ ] **MVCC**, WAL, VACUUM (PostgreSQL internals)
- [ ] Normalization (1NF/2NF/3NF) vs denormalization
- [ ] **N+1 problem**, query optimization, `EXPLAIN ANALYZE`
- [ ] Connection pooling, migrations (Alembic/Django migrations)
- [ ] SQL vs NoSQL trade-offs; when to shard/partition/replicate

### 6. Caching & Redis → [08_Redis](Backend_Developer/00_Year0-2_Junior/08_Redis) · [09_Caching](Backend_Developer/00_Year0-2_Junior/09_Caching)
- [ ] Redis data structures (string, hash, list, set, sorted set)
- [ ] Caching patterns: cache-aside, write-through, write-behind
- [ ] TTL, eviction policies (LRU/LFU), cache invalidation
- [ ] Cache stampede/thundering herd; distributed lock (Redlock idea)
- [ ] Redis pub/sub, use as broker/session store

### 7. Testing → [10_Testing](Backend_Developer/00_Year0-2_Junior/10_Testing)
- [ ] pytest, fixtures, parametrize, mocking (`unittest.mock`/`monkeypatch`)
- [ ] Unit vs integration vs e2e; test pyramid
- [ ] Coverage, TDD basics, testing async code
- [ ] **Have a real test suite in your proof-project** (true capability gap per audit)

### 8. System Design → [01_System_Design](Backend_Developer/02_Year5+_Senior/01_System_Design)
- [ ] **HLD:** load balancing, caching, DB replication/sharding, CAP theorem
- [ ] Message queues, consistency models, CDN, rate limiting at scale
- [ ] Capacity estimation (think in RPS/QPS, storage, bandwidth)
- [ ] **LLD:** SOLID, design patterns, class design (LRU cache, rate limiter, etc.)
- [ ] Walk a design out loud in English (this is where English + SD combine)

### 9. Git & Fundamentals
- [ ] Git branching, merge vs rebase, PR workflow, resolving conflicts
- [ ] HTTP/HTTPS, TLS basics, DNS, how a request travels
- [ ] Linux basics (processes, ports, logs, permissions)

---

## 🔴 TIER 1 (AI) — COMPULSORY for the "Agentic AI" half

### 10. LLM APIs & SDKs → [Level3_LLM_APIs_SDKs](Agentic_AI/Level3_LLM_APIs_SDKs)
- [ ] Chat completions, messages API, system/user/assistant roles
- [ ] Streaming, temperature/top_p, token limits, cost/token
- [ ] Structured outputs / JSON mode, retries & error handling

### 11. Prompt Engineering → [Level2_Prompt_Engineering](Agentic_AI/Level2_Prompt_Engineering)
- [ ] Zero/few-shot, chain-of-thought, role prompting
- [ ] Prompt templates, output formatting, guardrails against injection

### 12. Tool Use / Function Calling → [Level4_Tool_Use_Function_Calling](Agentic_AI/Level4_Tool_Use_Function_Calling)
- [ ] Tool/function schemas, the call→execute→return loop
- [ ] Parallel tool calls, error handling, tool result formatting

### 13. RAG & Vector DBs → [Level5_RAG_Vector_Databases](Agentic_AI/Level5_RAG_Vector_Databases)
- [ ] Embeddings, chunking strategies, vector DBs (pgvector/Pinecone/Chroma)
- [ ] Retrieval, semantic vs keyword, **hybrid search**, reranking
- [ ] RAG pipeline end-to-end; when RAG vs fine-tune

### 14. Agent Patterns → [Level6_Agent_Patterns](Agentic_AI/Level6_Agent_Patterns)
- [ ] ReAct, plan-and-execute, reflection
- [ ] Multi-agent (supervisor/swarm), memory (episodic/semantic)
- [ ] Agent evaluation basics

---

## 🟡 TIER 2 — SHOULD-KNOW (expect ~70% of roles to probe)

| Topic | Folder | Must be able to say |
|---|---|---|
| Security | [03_Security](Backend_Developer/01_Year3-4_Mid/03_Security) | OWASP Top 10, JWT/OAuth, SQLi/XSS/CSRF, secrets mgmt, HTTPS |
| DevOps | [04_DevOps](Backend_Developer/01_Year3-4_Mid/04_DevOps) | Docker, docker-compose, CI/CD (GitHub Actions), K8s basics, env config |
| Observability | [04_DevOps](Backend_Developer/01_Year3-4_Mid/04_DevOps) | Structured logging, metrics (Prometheus), tracing (OTel), correlation IDs, Grafana/Sentry |
| Microservices | [05_Microservices](Backend_Developer/01_Year3-4_Mid/05_Microservices) | Service boundaries, sync vs async comms, saga, circuit breaker, distributed systems (Raft idea) |
| Async tasks | [09_Celery](Backend_Developer/01_Year3-4_Mid/09_Celery) | Celery workers, task queues, retries, idempotency, scheduling |
| Messaging | [07_Kafka](Backend_Developer/01_Year3-4_Mid/07_Kafka) · [08_RabbitMQ](Backend_Developer/01_Year3-4_Mid/08_RabbitMQ) | Pub/sub, partitions/ordering, at-least-once vs exactly-once, consumer lag |
| Design Patterns & SOLID | [15_Design_Patterns_SOLID](Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID) | SOLID, factory/strategy/observer/singleton/adapter, when to use |
| GraphQL | [12_GraphQL](Backend_Developer/01_Year3-4_Mid/12_GraphQL) | Schema, resolvers, N+1/DataLoader, REST vs GraphQL |
| WebSocket/SSE | [13_WebSocket_SSE](Backend_Developer/01_Year3-4_Mid/13_WebSocket_SSE) | When to use, WS vs SSE vs polling, scaling stateful conns |
| Agentic Frameworks | [Level7_Frameworks](Agentic_AI/Level7_Frameworks) | LangGraph, MCP, PydanticAI — build a graph/agent, explain it |
| Production LLMOps | [Level8_Production_LLMOps](Agentic_AI/Level8_Production_LLMOps) | Guardrails, evals, cost optimization, observability, caching |
| Engineering Practices | [14_Engineering_Practices](Backend_Developer/01_Year3-4_Mid/14_Engineering_Practices) | Code review, incident response, post-mortems, RFC/ADR |

---

## ⚪ TIER 3 — JD-SPECIFIC (learn ONLY if the job description names it)

| Topic | Folder |
|---|---|
| gRPC | [06_gRPC](Backend_Developer/01_Year3-4_Mid/06_gRPC) |
| MongoDB | [10_MongoDB](Backend_Developer/01_Year3-4_Mid/10_MongoDB) |
| Elasticsearch | [11_Elasticsearch](Backend_Developer/01_Year3-4_Mid/11_Elasticsearch) |
| MySQL specifics (Galera/NDB) | [05_MySQL](Backend_Developer/00_Year0-2_Junior/05_MySQL) |
| Classical ML/DL foundations | [Level1_LLM_Foundations](Agentic_AI/Level1_LLM_Foundations)/Classical_ML_DL_Foundations |
| Modern AI (voice, computer-use, multimodal, Responses/Live API) | [Modern_Topics](Agentic_AI/Modern_Topics) |
| Architecture patterns (CQRS, event sourcing, sidecar) | [02_Architecture_Patterns](Backend_Developer/02_Year5+_Senior/02_Architecture_Patterns) |
| Senior leadership (RFC/ADR, mentoring) | [03_Senior_Leadership](Backend_Developer/02_Year5+_Senior/03_Senior_Leadership) |

---

## 🎤 The hidden compulsory topic: English + Storytelling
Not a folder — the delivery layer. For **every** 🔴 topic above, you must be able to explain it **out loud in clear English** and tie it to a **STAR story** from real work or your proof-project. Practice via [english_speaking/03_Advanced/06_interview_english.md](english_speaking/03_Advanced/06_interview_english.md) and weekly mocks.

---

## How to use this file
1. **Weekly:** scan the 🔴 list. Any sub-topic you can't say out loud → schedule it in [DAILY_PLAN_90_DAYS.md](DAILY_PLAN_90_DAYS.md).
2. **Before each interview:** read the target JD, promote any ⚪ items it names to 🔴 for that week, skim the matching folder.
3. **"Done" test:** you can explain it in 2 min, in English, with an example — not "I read the file".

> Related: [STUDY_PLAN.md](STUDY_PLAN.md) (daily entry) · [DAILY_PLAN_90_DAYS.md](DAILY_PLAN_90_DAYS.md) (12-week schedule + Job-Hunt Track) · [MASTER_INDEX.md](Agentic_AI/MASTER_INDEX.md) (Agentic full index)
