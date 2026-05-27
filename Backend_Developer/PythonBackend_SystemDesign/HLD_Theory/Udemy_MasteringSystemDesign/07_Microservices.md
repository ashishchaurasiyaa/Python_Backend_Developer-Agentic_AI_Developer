# 07 — Microservices

## Definition

A **microservice architecture** structures an application as a collection of small, autonomous, independently deployable services that communicate over a network. Each owns:

- A bounded **business capability** (e.g., "payments", "search", "notifications")
- Its **own data store**
- An **independent deployment pipeline**
- Often a **small team** (Amazon's "two-pizza team")

Contrast with **monolith** — one codebase, one deploy, one shared DB.

## Monolith vs Microservices

| | **Monolith** | **Microservices** |
|---|--------------|-------------------|
| Codebase | One repo, one app | Many repos / services |
| Deploy | All-or-nothing | Independent per service |
| Tech stack | Uniform | Polyglot (Python, Go, Java, ...) |
| Scaling | Whole app scales together | Scale hot services independently |
| Team coordination | High (shared code) | Low (well-defined contracts) |
| Local dev | Simple — run one thing | Complex — Docker Compose / mocks |
| Operational complexity | Low — one log, one metric | High — N services, distributed tracing |
| Failure mode | One bug crashes everything | Bulkhead — isolate failures |
| Network calls | In-process function call | RPC / HTTP / gRPC across network |
| Transactions | DB transactions | Saga / eventual consistency |
| Testing | Easy unit + integration | Hard — contract tests, chaos eng |

**Default advice:** start with a well-modularized monolith. Extract microservices when team grows beyond ~30 engineers or specific services have wildly different scale/tech needs. Premature microservices = distributed monolith (worst of both worlds).

## When microservices help vs hurt

**Helps when:**
- Multiple teams need independent deploy cadence
- Services have very different scaling profiles (search 100×, payments 1×)
- Different tech needs (ML model in Python, low-latency in Go, etc.)
- Domain has clear bounded contexts
- You have observability + DevOps maturity

**Hurts when:**
- Small team, simple domain
- No DevOps platform (each service needs CI/CD, monitoring, logging)
- Shared data model that's hard to split
- Network unreliability becomes the bottleneck
- Distributed transactions are the norm

## Service boundaries (Domain-Driven Design)

Use **DDD** to find boundaries:

- **Bounded context:** a clear domain area (e.g., "ordering" vs "billing") with its own ubiquitous language and model.
- **Aggregate:** a cluster of objects treated as a unit (e.g., Order + OrderItems).
- **Service per bounded context**, not per entity.

**Bad boundary signs:**
- Two services constantly call each other (chatty)
- A "user-service" that everyone depends on for everything
- Services share a DB (you have a distributed monolith)
- One feature requires changes in 5 services (boundaries don't match feature flow)

## Inter-service communication

### Synchronous

| Protocol | Use case | Notes |
|----------|----------|-------|
| **REST/HTTP** | Public APIs, simple use, browser-friendly | Verbose; JSON ubiquitous |
| **gRPC** | Internal RPC, performance-sensitive | Protobuf, HTTP/2, streaming, codegen |
| **GraphQL** | Aggregating APIs, flexible client queries | Powerful but complex |

### Asynchronous

| Pattern | Use case |
|---------|----------|
| Event bus (Kafka, RabbitMQ) | Decoupled fan-out, audit log |
| Pub-sub (SNS, Pub/Sub) | Notifications |
| Background queues (SQS, Celery) | Long-running work |

**Rule:** prefer async for non-user-facing flows. Sync for fast critical-path lookups.

## API Gateway

A single entrypoint that fronts all microservices.

**Responsibilities:**
- Routing (path/host → service)
- Authentication (validate JWT, OAuth)
- Rate limiting
- Request/response transformation
- API versioning
- Caching
- Aggregation (fan-out to multiple services and combine)
- Observability (logs, metrics, traces)

**Examples:** Kong, Tyk, AWS API Gateway, Apigee, Envoy, Nginx Plus, Zuul.

**BFF (Backend-for-Frontend):** dedicated gateway per client (web, iOS, Android) tailoring responses. Avoids overfetching.

## Service discovery

How does service A find service B's network address?

### Client-side discovery
- Service registers itself with a registry on startup
- Client queries registry → gets list of instances → load-balances itself
- Examples: Netflix Eureka + Ribbon, Consul

### Server-side discovery
- Client calls a stable address (LB/gateway)
- LB does the lookup
- Examples: Kubernetes Services, AWS ALB target groups

### DNS-based
- Service name resolves to instance(s) via DNS
- Examples: Kubernetes DNS, Consul DNS
- Simple but DNS caching can delay updates

**Modern default:** Kubernetes Service (cluster IP + kube-proxy) abstracts discovery + LB.

## Resilience patterns

### Timeouts

Every external call must have a timeout. Default `requests.get(url)` blocks forever. Set: `timeout=(connect_5s, read_30s)`.

Pattern: caller's timeout > callee's max latency.

### Retries

Retry transient failures with **exponential backoff + jitter**. Don't retry: 4xx errors (client bug), non-idempotent ops without idempotency keys.

### Circuit Breaker

After N consecutive failures, "open" the circuit — reject calls immediately for a cool-down period, then "half-open" to test recovery.

States: Closed (normal) → Open (fast-fail) → Half-Open (testing).

Libraries: Hystrix (deprecated but conceptually canonical), Resilience4j, Polly, Envoy outlier detection.

### Bulkhead

Isolate failure domains. Separate thread pool / connection pool per downstream so one slow dep can't exhaust resources used by others.

### Rate limiting

Protect callees from being overwhelmed.

- **Token bucket** — N tokens; each request consumes one; refilled at rate R
- **Leaky bucket** — fixed rate output regardless of burst
- **Fixed window** — count requests per window (can have edge effects)
- **Sliding window** — smoother variant

Implementations: Redis-based counter (`INCR + EXPIRE`), Envoy/Istio rate limit filters, AWS WAF.

### Fallback / Graceful degradation

When a downstream fails, return a sensible default (cached data, empty list, "service unavailable" page) rather than 500.

## Distributed transactions

You can't have true ACID transactions across service boundaries.

Options:

1. **Saga (orchestration or choreography)** — see Messaging notes.
2. **Two-phase commit** — possible but blocking and brittle; avoid.
3. **Outbox pattern** — atomically commit business state + event to publish.
4. **Event sourcing** — store events as source of truth, project state.
5. **Eventual consistency + idempotent compensations.**

## Observability — three pillars

1. **Logs** — what happened, with context. Structured (JSON), centralized (ELK, Loki, Datadog).
2. **Metrics** — counters/gauges/histograms aggregated. Prometheus + Grafana, Datadog.
3. **Traces** — request path across services. OpenTelemetry, Jaeger, Zipkin, AWS X-Ray.

**Correlation ID:** every request gets a unique ID propagated via header (`X-Request-ID`, `traceparent`). Stamp on every log line and span. Without it, debugging across services is impossible.

**SLI / SLO / SLA:**
- SLI = Service Level Indicator (the measured metric, e.g., p99 latency)
- SLO = Service Level Objective (target, e.g., p99 < 200ms over 30d)
- SLA = Service Level Agreement (external promise + consequences)

## Deployment patterns

| Pattern | How | Use |
|---------|-----|-----|
| **Rolling** | Replace pods N at a time | Default in K8s |
| **Blue/Green** | Two full envs; switch LB | Fast rollback |
| **Canary** | 1% → 5% → 50% → 100% | Safest, but slowest |
| **Shadow / dark launch** | Mirror prod traffic to new version, ignore response | Validate before user impact |
| **Feature flag** | Code deployed but gated by config | Decouple deploy from release |

## Containerization

- **Docker** — package code + deps into immutable images
- **Kubernetes** — orchestrate containers across machines: scheduling, rolling deploys, autoscaling, service discovery, secrets

**Critical K8s primitives:** Deployment, Service, Ingress, ConfigMap, Secret, Pod, HorizontalPodAutoscaler, NetworkPolicy.

## Microservices anti-patterns

1. **Distributed monolith** — services so coupled you must deploy in lockstep.
2. **Shared DB** — kills service independence.
3. **Chatty interfaces** — N+1 calls per operation; latency explodes.
4. **Synchronous chains** — A → B → C → D; one slow link kills the whole flow.
5. **No contracts** — schemas drift; consumers break silently.
6. **Mocking everything in tests** — you've tested mocks, not the system. Use contract tests (Pact).
7. **No observability** — you're flying blind across N services.
8. **Stateful services** without explicit replication / consensus.
9. **Different teams, different stacks, no platform** — every team reinvents CI/CD, monitoring.

## When to extract a service (Strangler Fig pattern)

Take a monolith and extract piece by piece:

1. Identify a bounded context to extract
2. Build new service alongside monolith
3. Route a small % of traffic to new service via gateway
4. Migrate data (dual-write, then read from new, then stop writing to old)
5. Repeat for next module

Pattern from Martin Fowler — named after a tree that strangles its host gradually.

## Interview Q&A

**Q1: When would you NOT use microservices?**
*A:* Small team (<15 engineers), early product (still finding PMF), simple domain, no DevOps platform. Microservices are a force multiplier when team coordination is the bottleneck; they're an anchor when you're trying to ship fast with few people.

**Q2: How do you handle a transaction across order + payment + inventory services?**
*A:* Saga. Orchestration version: an Order Saga service drives the steps — reserve inventory → charge payment → confirm order. Each step has a compensation (release inventory, refund). State machine ensures progress. All steps idempotent. Events emitted for observability. Avoid 2PC.

**Q3: One downstream service is slow. Symptoms in the calling service?**
*A:* Threads/connections piling up waiting on it. If no timeout, calling service eventually OOMs or runs out of conns. With timeouts, you get cascading timeouts. Fix: set aggressive timeouts, add circuit breaker (fast-fail when downstream broken), bulkhead the call so it doesn't starve other operations.

**Q4: How do you debug a slow user request that traverses 8 services?**
*A:* Distributed tracing with a propagated trace ID. Jaeger / X-Ray visualizes the waterfall: which service spent the time, what DB call was slow, etc. Without tracing, you'd grep logs across 8 services trying to correlate by request ID. With tracing, the bottleneck is one click away.

**Q5: How do you do schema evolution without breaking consumers?**
*A:* (1) Use a schema registry (Avro/Protobuf) with compat rules. (2) Always add fields as optional with defaults — never remove or rename. (3) Version your APIs (`/v1/`, `/v2/`). (4) Deploy producer changes first if adding fields; consumer changes first if removing (deprecation cycle). (5) Contract tests in CI catch breakage.

**Q6: API Gateway vs Service Mesh — what's the difference?**
*A:* **API Gateway** is north-south (client ↔ services) — auth, rate limit, request shaping for external traffic. **Service Mesh** is east-west (service ↔ service) — mTLS, retries, circuit breaking, traffic splitting between internal services. Different concerns; large systems use both.

**Q7: How do you size your microservices?**
*A:* Not by lines of code. By **bounded context** (DDD) and **team ownership**. A service should be owned by one team, deployable independently, with a clear business purpose. If it's so small that it has no autonomy ("nano-service"), it's too small. If multiple teams must coordinate every change, it's too big.

## Further reading

- *Building Microservices* — Sam Newman
- *Domain-Driven Design* — Eric Evans
- *Release It!* — Michael Nygard (patterns: bulkhead, circuit breaker, etc.)
- Existing notes: `../01_Monolithic_vs_Microservices.md`, `../02_REST_SOA_Microservices_Tier_Architecture.md`
- Martin Fowler's articles on microservices (martinfowler.com/microservices/)
