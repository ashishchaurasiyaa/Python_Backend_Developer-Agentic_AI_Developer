# HLD Code — Working Implementations

Self-contained Python implementations of five core distributed-systems patterns.
Each file runs with the standard library only (Python 3.10+) and produces annotated
console output that maps directly to the theory notes.

---

## Subdirectory Overview

### 01_cqrs_event_sourcing — `cqrs.py`

Implements CQRS (Command Query Responsibility Segregation) combined with Event
Sourcing using a bank-account domain. Commands emit immutable events into an
append-only `EventStore`; three independent projections (`BalanceProjection`,
`StatementProjection`, `TopAccountsProjection`) rebuild separate read models from
the same event stream. Includes optimistic concurrency, snapshot optimisation, and
a time-travel demo.

Theory cross-link:
- [`../LLD_Theory/Event_Sourcing_CQRS.md`](../LLD_Theory/Event_Sourcing_CQRS.md)

**Run:**
```bash
python 01_cqrs_event_sourcing/cqrs.py
```

---

### 02_saga_orchestration — `saga.py`

Implements both flavours of the Saga pattern for distributed transactions across an
e-commerce order flow (inventory → payment → shipping → email). The
`SagaOrchestrator` drives a sequential step-list and executes compensating
transactions in reverse on failure; the choreography variant wires the same services
through an in-process `EventBus` with no central coordinator. Demonstrates happy
paths and cascade rollback.

Theory cross-link:
- [`../HLD_Theory/51_Idempotency_Tokens.md`](../HLD_Theory/51_Idempotency_Tokens.md)
  (idempotent compensations)
- [`../HLD_Theory/22_Message_Based_Communication.md`](../HLD_Theory/22_Message_Based_Communication.md)
  (choreography messaging model)

**Run:**
```bash
python 02_saga_orchestration/saga.py
```

---

### 03_circuit_breaker — `circuit_breaker.py`

Implements the three-state circuit breaker (`CLOSED → OPEN → HALF_OPEN`) with a
thread-safe rolling-window failure counter, configurable failure-rate threshold, and
automatic half-open probing after a cooldown timeout. Provides a decorator API,
exponential-backoff retry integration (that skips retries when the circuit is open),
and a `CircuitBreakerRegistry` for per-endpoint isolation.

Theory cross-link:
- [`../HLD_Theory/34_Circuit_Breaker_Event_Driven.md`](../HLD_Theory/34_Circuit_Breaker_Event_Driven.md)

**Run:**
```bash
python 03_circuit_breaker/circuit_breaker.py
```

---

### 04_rate_limiter — `rate_limiter.py`

Implements five rate-limiting algorithms side by side: Token Bucket, Leaky Bucket,
Fixed Window Counter, Sliding Window Log, and Sliding Window Counter (Cloudflare
style). Also includes a simulated Redis-backed distributed limiter and an async
`AsyncTokenBucket` for use with `asyncio`. A FastAPI middleware template shows
production wiring.

Theory cross-link:
- [`../HLD_Theory/05_Throughput.md`](../HLD_Theory/05_Throughput.md)
- [`../HLD_Theory/33_API_Gateway.md`](../HLD_Theory/33_API_Gateway.md)
  (API Gateway rate-limiting context)

**Run:**
```bash
python 04_rate_limiter/rate_limiter.py
```

---

### 05_consistent_hashing — `consistent_hashing.py`

Implements both a `BasicConsistentHash` (one ring position per node) and a
production-grade `ConsistentHashRing` with configurable virtual nodes (vnodes) and
replication factor. Benchmarks demonstrate key-remap counts when adding or removing
a node compared with naive modulo hashing, and a `DistributedCache` wrapper shows
replica-aware get/set with graceful node-failure handling.

Theory cross-link:
- [`../HLD_Theory/44_Consistent_Hashing_Theory.md`](../HLD_Theory/44_Consistent_Hashing_Theory.md)

**Run:**
```bash
python 05_consistent_hashing/consistent_hashing.py
```

---

## Prerequisites

No third-party packages are required. All files use only the Python standard library.

```bash
python --version   # 3.10 or later recommended
```

---

## Directory Structure

```
HLD_Code/
├── README.md                          # this file
├── 01_cqrs_event_sourcing/
│   └── cqrs.py
├── 02_saga_orchestration/
│   └── saga.py
├── 03_circuit_breaker/
│   └── circuit_breaker.py
├── 04_rate_limiter/
│   └── rate_limiter.py
└── 05_consistent_hashing/
    └── consistent_hashing.py
```

Related theory is in the sibling directories:
- `../HLD_Theory/` — distributed systems theory notes (58 files)
- `../LLD_Theory/` — design patterns and LLD notes
