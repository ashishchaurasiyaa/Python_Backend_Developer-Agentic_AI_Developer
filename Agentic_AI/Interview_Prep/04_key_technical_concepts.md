# Key Technical Concepts — Quick Reference Cheat Sheet

## Python Core

```
GENERATORS vs ITERATORS:
  Iterator:  __iter__ + __next__ implement karo
  Generator: yield use karo — auto iterator banata hai
  Generator expression: (x*2 for x in range(10)) — lazy

DECORATORS:
  @functools.wraps — preserve function metadata
  @property       — method ko attribute banao
  @classmethod    — cls first arg, factory methods
  @staticmethod   — no self/cls, utility functions
  @lru_cache      — memoization built-in

CONTEXT MANAGERS:
  __enter__ / __exit__ — with statement
  contextlib.contextmanager — generator-based

METACLASSES:
  type is default metaclass
  class MyMeta(type): ... — customize class creation
  Pydantic, SQLAlchemy use metaclasses internally

DESCRIPTORS:
  __get__ / __set__ / __delete__
  property() is a descriptor
  Django fields are descriptors

GIL:
  One thread runs Python bytecode at a time
  IO-bound: threading is fine (GIL released on IO)
  CPU-bound: use multiprocessing (bypasses GIL)
  Python 3.13: optional no-GIL mode (experimental)
```

---

## Async Python

```
EVENT LOOP:
  Single thread + event loop
  Coroutines: await suspends, returns control to loop
  asyncio.gather() — run coroutines concurrently
  asyncio.Semaphore — limit concurrency

WHEN TO USE WHAT:
  asyncio:         IO-bound, many concurrent connections
  threading:       IO-bound, blocking libraries
  multiprocessing: CPU-bound computation

COMMON MISTAKES:
  ✗ Blocking call inside async function (time.sleep, requests.get)
  ✓ Use asyncio.sleep, httpx/aiohttp instead

TASK vs COROUTINE:
  coro = my_func()           # Coroutine object (not started)
  task = asyncio.create_task(my_func())  # Scheduled immediately
```

---

## FastAPI

```
DEPENDENCY INJECTION:
  Depends() — inject into path operations
  yield in dep — setup/teardown (DB session)
  Depends(Depends()) — chained deps

LIFESPAN:
  @asynccontextmanager + lifespan parameter
  Replaces on_event("startup") / on_event("shutdown")

PYDANTIC INTEGRATION:
  Request body: type hint with BaseModel → auto validation
  Response model: response_model=... → filter output fields
  Field() — validation, description, examples

BACKGROUND TASKS:
  BackgroundTasks.add_task() — fire and forget (simple)
  Celery — for reliable, retryable background jobs

MIDDLEWARE ORDER:
  Middlewares applied in REVERSE order of addition
  Last added = outermost (runs first)
```

---

## Database

```
POSTGRESQL:
  ACID: Atomicity, Consistency, Isolation, Durability
  Isolation levels: Read Uncommitted → Serializable
  
  SELECT FOR UPDATE       — pessimistic lock (row lock)
  Version column + check  — optimistic lock
  
  Index types:
    B-Tree: default, equality + range queries
    GIN:    JSONB, full-text, array containment
    BRIN:   large tables with natural ordering (timestamps)
    HNSW:   vectors (pgvector) — fast approximate search

N+1 PROBLEM:
  Problem: 1 query for list + N queries for each item
  Fix: select_related() (Django) / joinedload (SQLAlchemy)
       OR separate query with IN clause

CONNECTION POOL:
  PgBouncer: connection multiplexer — 100s of app connections → 10s of DB connections
  SQLAlchemy pool_size: connections kept open
  max_overflow: extra connections allowed at peak

TRANSACTIONS:
  BEGIN → work → COMMIT (or ROLLBACK)
  Savepoints: partial rollback within transaction
  Deadlock: two transactions waiting for each other → DB resolves by killing one
```

---

## Redis

```
DATA STRUCTURES:
  String: SET/GET, INCR — counters, simple cache
  Hash:   HSET/HGET — object storage (user profile)
  List:   LPUSH/RPOP — message queue, activity feed
  Set:    SADD/SMEMBERS — unique items, tags
  Sorted Set: ZADD — leaderboard, sliding window rate limit
  Stream: XADD — message streaming (Redis 5+)

PATTERNS:
  Cache-aside:     App checks Redis, miss → load DB → set Redis
  Write-through:   Write to Redis AND DB simultaneously
  Pub/Sub:         Publisher → channel → all subscribers

EXPIRY:
  TTL: EXPIRE key seconds
  Persistent: no TTL set
  volatile-lru: evict keys with TTL first

ATOMIC OPERATIONS:
  MULTI/EXEC: transaction (but no rollback)
  Lua scripts: atomic multi-step operations
  Pipeline: batch commands (reduced round-trips)
```

---

## System Design Concepts

```
CAP THEOREM:
  Consistency: all nodes see same data simultaneously
  Availability: every request gets a response
  Partition Tolerance: system works despite network failures
  → Can only guarantee 2 of 3
  PostgreSQL: CP (consistency + partition tolerance)
  DynamoDB:   AP (availability + partition tolerance)

SCALING:
  Vertical: bigger server (limited)
  Horizontal: more servers (preferred)
  
  Stateless services: easy to scale horizontally
  Stateful: use external state (Redis, DB)

CACHING LEVELS:
  Browser → CDN → Load Balancer → App Cache (Redis) → DB Cache → DB

MESSAGE QUEUES:
  Celery + Redis/RabbitMQ: task queue (fire-and-forget with reliability)
  Kafka: high-throughput event streaming (event sourcing, analytics)
  Use queue when: decouple producer from consumer, handle bursts

API DESIGN:
  REST: CRUD operations, simple, widely understood
  GraphQL: flexible queries, multiple resources in one call
  gRPC: binary protocol, efficient, internal service-to-service
  WebSocket: bidirectional, real-time (chat, live updates)
  
  Rate Limiting: Token Bucket (burst allowed) vs Sliding Window (smooth)
  Versioning: URL (/v1/users) vs Header (Accept: application/v1+json)
  Idempotency: POST with Idempotency-Key → safe to retry
```

---

## LLM/AI Concepts

```
RAG PIPELINE:
  Chunk → Embed → Store → Retrieve → Rerank → Generate
  
  Chunking: RecursiveCharacter (general), Semantic (quality), Token (exact)
  Embeddings: text-embedding-3-small (fast/cheap), bge-large (local)
  Vector DB: pgvector (postgres), Qdrant (dedicated), Pinecone (managed)
  Reranking: CrossEncoder (local) or Cohere (cloud)

PROMPT ENGINEERING:
  Zero-shot:      No examples, just instruction
  Few-shot:       2-5 examples show pattern
  Chain-of-Thought: "Step by step" → better reasoning
  Structured:     JSON schema in prompt → structured output

LLM METRICS:
  Faithfulness:      Does answer come from context? (anti-hallucination)
  Answer Relevancy:  Does answer address the question?
  Context Precision: Are retrieved docs useful?
  Context Recall:    Is all needed info in retrieved docs?

COST OPTIMIZATION:
  1. Semantic caching  — 60-70% cache hit rate
  2. Model routing     — simple tasks → cheap model
  3. Batch API         — 50% discount for non-urgent
  4. Prompt caching    — repeated context → 90% cheaper (Claude)
  5. Response streaming — better UX for same cost

AGENT PATTERNS:
  ReAct:       Reason → Act → Observe → loop
  Reflection:  Generate → Critique → Improve
  Supervisor:  Manager assigns work to specialist workers
  Planning:    Decompose task → execute sub-tasks → synthesize
```

---

## Interview: What Interviewers Actually Test

```
PYTHON BACKEND ROLE:
  ✓ Async/await understanding (real scenarios)
  ✓ Database query optimization (explain N+1)
  ✓ API design (REST best practices, error handling)
  ✓ Caching strategies (when to cache, invalidation)
  ✓ Testing approach (what to mock, what to integration test)
  ✓ Debugging production issues (logs, metrics, tracing)

AI/ML ENGINEER ROLE:
  ✓ RAG pipeline design
  ✓ Embedding model selection trade-offs
  ✓ Prompt engineering techniques
  ✓ LLM evaluation metrics
  ✓ Cost optimization at scale
  ✓ Agent pattern selection

SENIOR ENGINEER:
  ✓ System design (not just code)
  ✓ Trade-off articulation (pros/cons, not just answer)
  ✓ Past failure + learning
  ✓ Technical leadership (decisions, mentoring)
  ✓ Communication (explain complex things simply)
```

---

## 30-Second Concept Explanations

```
Q: What is a generator?
A: "Function jo yield use karta hai — lazy evaluation karta hai,
    ek time mein ek value produce karta hai. Memory efficient hai
    kyunki puri list memory mein nahi rakhni. Use karo jab: large
    datasets iterate karo, infinite sequences, pipeline processing."

Q: What is the GIL?
A: "Global Interpreter Lock — CPython mein ek mutex jo ensure karta
    hai sirf ek thread ek time mein Python bytecode run kare. Matlab
    CPU-bound multithreading Python mein actual parallel nahi hoti.
    Solution: multiprocessing for CPU work, asyncio for IO work."

Q: What is a context manager?
A: "with statement ke saath kaam karne wala object — __enter__ setup
    karta hai, __exit__ cleanup karta hai even on exception. Classic
    example: database connection, file handling. Guarantee: resource
    hamesha release hogi, chahe exception aaye ya na aaye."

Q: RAG vs Fine-tuning?
A: "RAG is retrieval at runtime — external docs se answer augment karo.
    Fine-tuning is training — model weights update karo with examples.
    RAG use karo jab knowledge dynamic/large hai ya citations chahiye.
    Fine-tune karo jab consistent output FORMAT chahiye ya domain
    vocabulary model ko nahi pata. RAG preferred as default choice."

Q: What is idempotency?
A: "Same request multiple times bhejo — same result milna chahiye,
    no duplicate side effects. POST /payments with Idempotency-Key —
    network retry pe duplicate charge nahi hoga. Implement: store
    request ID in DB, return cached response on duplicate."

Q: Explain ACID.
A: "Atomicity: transaction ya poori complete ho ya poori rollback.
    Consistency: DB always valid state mein rahe (constraints satisfied).
    Isolation: concurrent transactions ek dusre ko affect na karein.
    Durability: committed data crash ke baad bhi survive kare."
```
