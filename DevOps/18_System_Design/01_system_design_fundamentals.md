# System Design — DevOps-Lens Fundamentals
**DevOps Track · Phase 18: System Design**

> Full HLD/LLD problem-solving depth lives in `Backend_Developer/02_Year5+_Senior/01_System_Design/` (66 HLD_Theory files, 34 HLD_Problems walkthroughs, 21 LLD_Problems) — this file gives the DevOps-relevant vocabulary and patterns only. Read this if you're building/operating systems, not designing them from scratch in an interview.

## Quick Concepts

- **Monolith** = one deployable unit containing all application logic
- **Microservices** = independently deployable services, each owning its own data
- **API Gateway** = single entry point that routes, authenticates, and rate-limits requests to backend services
- **Service Discovery** = mechanism by which a service finds the network location of another service
- **Load Balancing** = distributing traffic across multiple instances of a service
- **High Availability (HA)** = system stays up despite component failure (measured in "nines")
- **Fault Tolerance** = system keeps functioning correctly even when parts fail
- **CAP Theorem** = a distributed system can only guarantee 2 of {Consistency, Availability, Partition Tolerance} during a network partition
- **Distributed System** = multiple machines that must coordinate to look like one system to the caller
- **Event-Driven Architecture** = services communicate via events (async, decoupled) instead of direct calls
- **Horizontal Scaling** = add more machines
- **Vertical Scaling** = add more resources (CPU/RAM) to an existing machine

---

## Why This Matters for a DevOps Engineer

```
A backend engineer designs the system.
A DevOps engineer keeps that design ALIVE in production:

   - You provision the infrastructure the architecture assumes
     (load balancers, service mesh, message queues, discovery)
   - You are paged when the CAP tradeoff the team picked bites them
     (a network partition, a split-brain, a stale read)
   - You size instances based on horizontal vs vertical scaling decisions
   - You build the health checks that make "fault tolerance" real,
     not just a slide in an architecture doc

You don't need to invent the Twitter feed algorithm.
You DO need to know why the on-call runbook says
"check for a network partition between AZs" and what that means.
```

---

## Monolith vs Microservices — DevOps Tradeoffs

| Dimension | Monolith | Microservices |
|---|---|---|
| Deployment | One artifact, one pipeline | N artifacts, N pipelines (or one templated pipeline) |
| Scaling | Scale the whole app even if 1 module is hot | Scale only the hot service |
| Infra complexity | Low — one process, one DB | High — service mesh, discovery, distributed tracing, more moving parts to monitor |
| Failure blast radius | One bug can crash everything | Isolated — one service crashing doesn't take down others (if designed right) |
| CI/CD | Simple: build → test → deploy | Needs per-service pipelines + versioned contracts (API compat) |
| Observability | Simple: one set of logs/metrics | Needs distributed tracing to follow a request across services (see Phase 19) |
| On-call cognitive load | Low — one system to understand | High — need service maps, dependency graphs |
| Local dev | Easy — clone, run, done | Hard — need to run N services or mocks (docker-compose, Tilt, Skaffold) |
| Team size sweet spot | Small teams, early-stage products | Multiple teams owning separate services independently |

**DevOps reality check:** most companies that "need microservices" actually need a well-modularized monolith first. Microservices multiply your infrastructure and observability burden — you inherit network calls, partial failures, and distributed debugging in exchange for independent deployability. Don't reach for K8s + service mesh + 12 repos before the team and traffic justify it.

---

## API Gateway

**What it does (from an ops standpoint):**

```
Client → API Gateway → [Auth, Rate Limiting, Routing, TLS termination] → Backend services
```

- **Single ingress point** — one place to enforce auth, rate limits, request/response transforms, and observability (you instrument ONE layer instead of every service)
- **Routing** — path-based (`/orders/*` → orders-service) or header-based
- **Aggregation** — sometimes fans out to multiple services and composes one response (BFF pattern)
- **Common implementations you'll actually operate:** Kong, AWS API Gateway, Nginx/Envoy as a gateway, Kubernetes Ingress + Ingress Controller (see `DevOps/01_Year3-4_Mid/04_DevOps/21_ingress_controller.md`), Istio Gateway (service mesh)

**DevOps angle:** the API gateway is a single point of failure if you don't run it HA (min 2 replicas, behind a load balancer itself). It's also your best chokepoint for global rate limiting, WAF rules, and centralized auth token validation — put observability (request ID injection, latency histograms) here so every downstream trace starts consistently.

---

## Service Discovery

**Problem it solves:** in a dynamic environment (containers restart, autoscaling adds/removes instances, IPs change), how does Service A find a healthy instance of Service B right now?

### Client-Side Discovery

```
Service A → queries Service Registry directly → picks an instance → calls it
```

- Client owns the load-balancing decision
- Needs a client library that knows how to query the registry (e.g., Netflix Eureka + Ribbon)
- Less network hops, more client complexity

### Server-Side Discovery

```
Service A → calls a Load Balancer / Proxy → LB queries registry → forwards to instance
```

- Client just calls a stable endpoint; LB/proxy does the lookup
- Simpler clients, but LB is now a hop + potential bottleneck
- This is what Kubernetes does by default

### Real Implementations

| Tool | Pattern | Where you'll see it |
|---|---|---|
| **Consul** | Server-side + client-side, health checks, KV store, multi-datacenter | VM-based infra, HashiCorp stack (pairs with Terraform/Vault) |
| **Eureka** | Client-side discovery | Netflix/Spring Cloud microservices |
| **Kubernetes DNS (CoreDNS)** | Server-side — `service-name.namespace.svc.cluster.local` resolves to a stable virtual IP (ClusterIP) that `kube-proxy` load-balances across healthy pods | Any K8s cluster — this is the default and what you'll operate 90% of the time |
| **etcd** | Underlying key-value store K8s itself uses for cluster/service state | Under the hood of K8s discovery |

**DevOps angle:** in Kubernetes you rarely hand-roll discovery — a `Service` object + CoreDNS + kube-proxy IS your service discovery. Your job is making sure readiness probes are correct (an unready pod must NOT receive traffic — see Phase 20's zero-downtime checklist) because discovery is only as good as the health signal feeding it.

---

## Load Balancing (Recap Tie-In)

Deep coverage already exists in `Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/12_Load_Balancer.md`. DevOps-relevant recap:

- **L4 (transport layer)** — balances on IP/port (TCP/UDP), fast, no content awareness. AWS NLB, `kube-proxy` in IPVS mode.
- **L7 (application layer)** — balances on HTTP data (path, headers, cookies), can do routing/retries/circuit breaking. AWS ALB, Nginx, Envoy, K8s Ingress.
- **Algorithms you'll actually configure:** round robin (default, simple), least connections (better for long-lived/uneven requests), weighted (canary traffic splits — see Phase 20), IP hash (session affinity/sticky sessions).
- **Health checks are the load balancer's eyes** — if your `/healthz` endpoint lies (returns 200 while the DB pool is exhausted), the LB keeps sending traffic to a dying instance. This is the single most common cause of "why is prod slow but all pods look healthy in kubectl."

---

## High Availability & Fault Tolerance

**High Availability (HA)** = minimizing downtime, usually expressed in "nines":

| Availability | Downtime/year | Downtime/month |
|---|---|---|
| 99% (two nines) | 3.65 days | 7.3 hours |
| 99.9% (three nines) | 8.76 hours | 43.8 minutes |
| 99.95% | 4.38 hours | 21.9 minutes |
| 99.99% (four nines) | 52.6 minutes | 4.38 minutes |
| 99.999% (five nines) | 5.26 minutes | 26 seconds |

Every additional nine is exponentially more expensive — multi-AZ, multi-region, automated failover, chaos-tested runbooks. (Full SLI/SLO/SLA math: `Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md`.)

**How you actually buy HA (infra decisions):**
- No single instance of anything — min 2 replicas of every stateless service
- Spread replicas across Availability Zones (AZ failure shouldn't take down the service)
- Database: primary + read replica(s), automated failover (RDS Multi-AZ, Patroni for Postgres)
- Stateless app servers behind a load balancer — any instance can die, LB routes around it
- Health checks + auto-restart (Kubernetes liveness probes, systemd `Restart=always`)

**Fault Tolerance** = the system produces correct results even when a component fails, not just "stays up":

- **Retries with backoff** — transient failures (network blip) shouldn't become user-facing errors
- **Circuit breakers** — stop hammering a failing downstream service; fail fast instead of cascading (Hystrix pattern, Istio's `outlierDetection`)
- **Bulkheads** — isolate resource pools (a slow payment API shouldn't exhaust the thread pool that serves the homepage)
- **Graceful degradation** — serve a cached/stale response instead of a 500 when a dependency is down
- **Idempotency** — retries must be safe to repeat (idempotency keys on POST /payments)

---

## CAP Theorem — With a Concrete Partition Scenario

**The theorem:** in the presence of a **network Partition (P)**, a distributed system must choose between **Consistency (C)** and **Availability (A)**. You cannot have all three simultaneously during a partition. (Deep treatment: `HLD_Theory/08_CAP_Theorem.md`.)

**Concrete scenario — a Postgres primary + read replica split across two AZs:**

```
Normal operation:
   [Primary DB — AZ-a] --replication--> [Replica DB — AZ-b]
   Writes go to Primary, reads can go to either.

Network partition happens: AZ-a and AZ-b can no longer talk to each other.

   Option 1 — Choose Consistency (CP):
      Replica in AZ-b REFUSES to serve reads/writes because it can't
      confirm it has the latest data from Primary.
      → App in AZ-b returns errors. System is NOT available there.
      → But no client ever sees stale data.

   Option 2 — Choose Availability (AP):
      Replica in AZ-b KEEPS serving reads using its last-known data.
      → App in AZ-b stays up, but may return data that's seconds/minutes stale.
      → A user could see an order status that already changed on the Primary.
```

- Real Postgres/MySQL primary-replica setups are typically **AP-leaning for reads** (replicas serve stale reads during a partition unless you explicitly configure synchronous replication, which then becomes CP but slower and can block writes).
- **etcd, ZooKeeper, Consul (KV store)** are **CP** — they'd rather reject a write than risk split-brain, because they're used for leader election / config where correctness matters more than uptime.
- **DynamoDB, Cassandra** are tunable, typically deployed **AP** — they stay available and reconcile later (eventual consistency, vector clocks / last-write-wins).

**DevOps angle:** when you provision multi-AZ or multi-region infra, you are explicitly making a CAP choice for the team, whether anyone says it out loud or not. "Multi-AZ RDS with synchronous replication" is a CP choice (failover waits for sync ack). "Multi-region active-active with async replication" is an AP choice. Know which one you built, because that's what the incident postmortem will ask about.

---

## Distributed Systems Basics

- **No shared clock** — you can't trust "which event happened first" across machines without logical clocks (Lamport clocks — see `HLD_Theory/09_Lamport_Logical_Clock.md`) or synchronized time (NTP, and even then there's drift)
- **Partial failure is the default** — in a single process, either the whole thing works or crashes. In a distributed system, some nodes can be up while others are down, and you can't always tell the difference between "slow" and "dead" (this is why heartbeats + timeouts exist — see `HLD_Theory/54_Heartbeat_Failure_Detection.md`)
- **Consensus is hard** — getting N nodes to agree on one value despite failures needs protocols like Raft or Paxos (etcd uses Raft; this is what makes Kubernetes' control plane consistent)
- **Idempotency and retries** are the practical coping mechanism for "did that request actually succeed, or did the response just get lost?"

---

## Event-Driven Architecture

```
Producer → Event (message) → Broker (Kafka/RabbitMQ/SQS) → Consumer(s)
```

- Producers don't call consumers directly — they publish an event and move on (decoupling)
- Consumers process at their own pace (buffers spikes — the broker absorbs bursts your DB couldn't)
- Enables **fan-out** (one event, many consumers: send-email, update-analytics, notify-webhook all triggered by one `order.created` event)
- Tradeoff: you gain decoupling and resilience to spikes, but lose synchronous request/response simplicity — debugging "why didn't X happen" now means tracing through a broker, not just reading a stack trace

**DevOps angle:** you operate the broker (Kafka cluster sizing/partitions, RabbitMQ queue depth alerts, SQS DLQ monitoring). A silently growing queue depth or consumer lag is one of the most common "everything looks fine in APM but the business is breaking" incidents — this is why queue depth and consumer lag are first-class metrics, not an afterthought (see Phase 19, and `Backend_Developer/.../HLD_Theory/65_Dead_Letter_Queue.md` for DLQ handling).

---

## Scalability

**Scalability** = the system's ability to handle growth (more users, more data, more traffic) by adding resources, ideally without a redesign.

### Horizontal vs Vertical Scaling

| | Horizontal Scaling (scale out) | Vertical Scaling (scale up) |
|---|---|---|
| **What you do** | Add more machines/instances | Add more CPU/RAM to existing machine |
| **Ceiling** | Effectively unlimited (add more nodes) | Hard ceiling — biggest instance type available |
| **Downtime to apply** | None — add instances behind LB, drain old ones | Usually requires a restart/reboot |
| **Cost curve** | Roughly linear | Often superlinear near the top (biggest instances cost disproportionately more) |
| **Complexity added** | Needs load balancing, service discovery, stateless design, session handling | None — same architecture, just bigger box |
| **State handling** | Requires externalizing state (sessions in Redis, not in-process memory) | State can stay local — simplest for stateful apps (single-node DB, legacy monoliths) |
| **Real example: when chosen** | A stateless FastAPI/Django app behind an ALB during a traffic spike — add pods via HPA (Horizontal Pod Autoscaler) | A single Postgres primary that's CPU/IO bound — bump from `db.r6g.xlarge` to `db.r6g.4xlarge` before you're ready to shard |
| **Typical trigger in practice** | Web/API tier, workers, anything stateless | Databases (until you're forced into read replicas/sharding), legacy single-instance systems, or a quick fix before a proper horizontal redesign |

**Real-world pattern:** scale the stateless web/app tier horizontally (this is what Kubernetes HPA and AWS Auto Scaling Groups are built for) and scale the database vertically for as long as possible, because horizontally scaling a relational database (sharding, read replicas, connection pooling with PgBouncer) is a much bigger architectural project than adding pods.

**DevOps angle:** this is a decision you'll make constantly when tuning autoscalers. `HorizontalPodAutoscaler` on CPU/memory or custom metrics (queue depth, request latency) scales pod count. Vertical scaling in K8s exists too (`VerticalPodAutoscaler`, or just bumping `resources.requests/limits` and rolling), but it requires a pod restart — never do it as a live incident response the way you'd add a horizontal replica.

---

## Senior Tip

```
In an interview, don't just define CAP theorem — pick a real system you've
touched (a Postgres replica, a Redis cluster, an SQS queue) and say which
side of CAP it lands on and WHY that was the right tradeoff for that use case.

Definitions are junior. Tradeoff judgment is senior.
```

## Interview Angle

**Q: "Your service needs to scale from 1,000 to 100,000 requests/sec. Walk me through what changes."**

A strong DevOps answer touches: horizontal scaling of stateless app tier (HPA/ASG) → externalize session state (Redis) → introduce a load balancer / API gateway if not present → identify the database as the likely bottleneck (read replicas, connection pooling, caching layer) → add async processing for anything that doesn't need a synchronous response (event-driven architecture, queue) → add observability (Phase 19) to know WHERE the next bottleneck will appear before it pages you at 100k rps.

---

## Related

- [`Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/`](../../Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/) — full depth on every topic above
- [`../19_Observability/01_metrics_logs_traces_opentelemetry.md`](../19_Observability/01_metrics_logs_traces_opentelemetry.md) — how you actually see these systems behave
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — how you deploy changes to these systems safely
