# Lecture 1 — Practical Hands-On: Choosing the Right Architecture

> **Theory file:** [01_Choosing_Architecture_Pattern.md](01_Choosing_Architecture_Pattern.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Decision worksheet** template (Markdown)
2. ✅ **ADR (Architecture Decision Record)** example
3. ✅ **Architecture spike** script — quick prototype-and-throw-away
4. ✅ **Ride-hailing case study** worked end-to-end
5. ✅ **Constraint capture template**

By end: aap apne project ke liye **structured decision document** likh sakte ho.

---

## 1. Decision Worksheet Template

### `decision_worksheet.md`

```markdown
# Architecture Decision Worksheet — <Project Name>

> Owner: ____________   Date: ____________

## 1. Business Goals
- [ ] Time-to-market priority
- [ ] High availability (99.9%+)
- [ ] Real-time responsiveness
- [ ] Global reach
- [ ] Compliance / audit
- [ ] Cost efficiency

> Top 3 ranked:
> 1. _______________________
> 2. _______________________
> 3. _______________________

## 2. Technical Goals
- [ ] Independent team deploys
- [ ] Polyglot tech stack
- [ ] Horizontal scaling
- [ ] Strong consistency
- [ ] Eventual consistency OK

## 3. Constraints
| Constraint            | Value / Limit                  |
|-----------------------|--------------------------------|
| Team size             | __________                     |
| Team experience       | __________                     |
| Expected QPS at year 1| __________                     |
| Expected QPS at year 3| __________                     |
| Latency SLO (p99)     | __________ ms                  |
| Budget (infra)        | __________ /month              |
| Regulatory            | __________                     |

## 4. Candidate Architectures
- [ ] Monolith
- [ ] Modular monolith
- [ ] Microservices
- [ ] Event-driven (hybrid)
- [ ] Serverless
- [ ] Layered (N-tier)

## 5. Trade-off Evaluation
| Pattern             | Pros (3)            | Cons (3)            | Risk      |
|---------------------|---------------------|---------------------|-----------|
| Monolith            |                     |                     | Low/Med/Hi|
| Microservices       |                     |                     |           |
| Hybrid              |                     |                     |           |

## 6. Recommendation
> Chosen: ___________
> Why (3 sentences):
> _______________________________________________________________

## 7. Validation Plan
- [ ] Spike 1: __________
- [ ] Spike 2: __________
- [ ] Load test prototype

## 8. Re-evaluation Triggers
> Revisit this decision when:
> - Team grows beyond ____
> - QPS exceeds ____
> - New compliance requirement
```

---

## 2. ADR Example — Ride-Hailing Hybrid

### `adr/0001-hybrid-microservices-event-driven.md`

```markdown
# ADR-0001: Hybrid Microservices + Event-Driven for RideX

**Status**: Accepted
**Date**: 2026-05-26
**Decider**: Architecture Council

## Context

We're building RideX, a ride-hailing platform. Key requirements:

- Real-time driver location updates (≤ 2s latency)
- 99.95% availability across India regions
- Independent teams for Trips, Pricing, Payments, Notifications
- Expected scale: 100k concurrent users in year 1, 1M in year 3
- 6 backend engineers (year 1), scaling to 30 (year 3)

## Decision

Adopt a **hybrid architecture**:

1. **Microservices** for domain ownership:
   - Trip Service
   - Rider Service
   - Driver Service
   - Pricing Service
   - Notification Service
   - Payment Service
2. **Event-driven** communication (Kafka) for cross-domain flows:
   - `TripRequested` → matched by Driver Service
   - `TripStarted` → Pricing + Analytics
   - `TripCompleted` → Payment + Notification + Analytics
3. **REST + gRPC** for synchronous read-paths.

## Consequences

### Positive
- Each domain team owns its service end-to-end.
- New consumers (e.g., fraud detection) can subscribe to existing events without touching producers.
- Independent scaling — Driver Service handles 10x the load of Payment Service.
- Resilience: a Payment outage doesn't block trip dispatch.

### Negative
- DevOps complexity: need K8s, Kafka cluster ops, distributed tracing.
- Eventual consistency between services — UI must handle.
- Higher initial cost vs a monolith.

### Mitigations
- Invest in observability from day 1 (OpenTelemetry, Grafana, Loki).
- Use Saga pattern for cross-service workflows (see ADR-0007).
- Start with 4 services, not 12 — split further only when contention proven.

## Validation
- Spike: deploy 3 services + Kafka + sample event flow → confirm end-to-end latency
- Load test: 10k events/sec → measure consumer lag

## Re-evaluation Triggers
- Operational toil exceeds 30% of engineering time → consider consolidating services
- A service becomes a clear bottleneck → split further
```

---

## 3. Architecture Spike Script (Python)

Sometimes you need a **throwaway prototype** to validate latency or feasibility before committing.

### `spike_event_flow.py`

```python
"""
Spike: validate that ordered events from Trip Service can be consumed
by Pricing + Notification under 500ms end-to-end.

Run: docker compose up kafka  → then python spike_event_flow.py
"""

import asyncio
import json
import time

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer


BROKER = "localhost:9092"
TOPIC = "trip-events"


async def trip_service():
    producer = AIOKafkaProducer(bootstrap_servers=BROKER)
    await producer.start()
    try:
        for i in range(100):
            event = {
                "type": "TripRequested",
                "trip_id": f"trip-{i}",
                "ts": time.time(),
            }
            await producer.send_and_wait(TOPIC, json.dumps(event).encode())
            await asyncio.sleep(0.01)
    finally:
        await producer.stop()


async def pricing_service(name: str):
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        group_id=name,
    )
    await consumer.start()
    latencies = []
    try:
        async for msg in consumer:
            event = json.loads(msg.value)
            latency = (time.time() - event["ts"]) * 1000
            latencies.append(latency)
            if len(latencies) >= 100:
                break
    finally:
        await consumer.stop()
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"[{name}] avg={sum(latencies)/len(latencies):.1f}ms  p95={p95:.1f}ms")


async def main():
    await asyncio.gather(
        trip_service(),
        pricing_service("pricing"),
        pricing_service("notification"),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

### What This Validates

```
✓ End-to-end event latency
✓ Multiple independent consumers don't interfere
✓ Kafka can handle target throughput
```

---

## 4. Constraint Capture Template

### `constraints.yaml`

```yaml
project: ridex
version: 0.1
captured_at: 2026-05-26

scale:
  users_year_1: 100_000
  users_year_3: 1_000_000
  peak_qps: 5_000
  p99_latency_ms: 200

team:
  size_now: 6
  size_planned: 30
  experience: [microservices, kubernetes, kafka]
  bus_factor: 3

regulatory:
  - PCI-DSS (payment data)
  - Data residency: india-only

operational:
  available_devops_engineers: 1
  on-call_rotation: 4 people
  budget_monthly_usd: 20000

domain:
  bounded_contexts:
    - rider
    - driver
    - trip
    - pricing
    - payment
    - notification
  shared_data:
    - user_profile  # read-mostly
```

---

## 5. ✅ Hands-On Checklist

```
□ Filled in decision_worksheet.md for your project
□ Wrote at least one ADR for a current architecture call
□ Ran the Kafka spike (or imagined equivalent) to validate latency
□ Captured constraints.yaml
□ Identified re-evaluation triggers
```

---

## 🔗 Next

- Next: [02_Tradeoff_Analysis.md](02_Tradeoff_Analysis.md)
