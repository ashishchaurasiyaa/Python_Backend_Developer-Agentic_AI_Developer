# 🧩 Microservices

> **15 theory + 8 practical.** Senior interview ka core — "monolith todna hai, kaise?"
> Yahan ka har pattern (saga, outbox, CQRS) system design round me directly kaam aata hai.

---

## 🔴 Interview ke liye pehle yeh 5

| # | Topic | Classic question |
|---|---|---|
| [01](01_microservices_patterns.md) | **Decomposition patterns** | "Monolith ko kaise todoge — boundary kahan?" |
| [04](04_outbox_event_sourcing.md) | **Outbox pattern** | "DB commit hua par event publish fail — kya karoge?" 🔥 |
| [05](05_event_sourcing_cqrs.md) | **Event sourcing + CQRS** | Read/write model alag, replay |
| [10](10_distributed_systems_theory.md) | **Distributed systems theory** | CAP, consensus, partial failure |
| [09](09_domain_driven_design.md) | **DDD** | Bounded context = service boundary |

> **Saga pattern** ka dedicated deep-dive senior track me hai → [59_Saga_Pattern.md](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/59_Saga_Pattern.md)

---

## 📚 Poori list

### Decomposition + design
| # | Topic | Practical |
|---|---|---|
| [01](01_microservices_patterns.md) 🔴 | Decomposition patterns | [`01_...py`](practical/01_microservices_practical.py) |
| [09](09_domain_driven_design.md) 🔴 | Domain-driven design | [`07_ddd_data_management_practical.py`](practical/07_ddd_data_management_practical.py) |
| [11](11_microservices_anti_patterns.md) | Anti-patterns — distributed monolith | [`08_...py`](practical/08_antipatterns_testing_serverless_practical.py) |
| [14](14_cell_based_architecture.md) | Cell-based architecture, blast radius | — |

### Communication
| # | Topic | Practical |
|---|---|---|
| [02](02_api_gateway_service_comm.md) | API gateway + service comm | [`02_...py`](practical/02_api_gateway_service_comm.py) |
| [06](06_service_mesh_istio_linkerd.md) | Service mesh — Istio/Linkerd | [`06_...py`](practical/06_service_mesh_kafka_practical.py) |
| [07](07_kafka_event_streaming.md) | Kafka event streaming | ↑ same |

### Data — sabse mushkil hissa 🔴
| # | Topic | Practical |
|---|---|---|
| [04](04_outbox_event_sourcing.md) 🔴 | **Outbox pattern** — dual-write problem ka jawab | [`04_outbox_idempotency.py`](practical/04_outbox_idempotency.py) |
| [05](05_event_sourcing_cqrs.md) 🔴 | Event sourcing + CQRS | [`05_...py`](practical/05_event_sourcing_cqrs.py) |
| [08](08_distributed_data_management.md) | Distributed data management | [`07_...py`](practical/07_ddd_data_management_practical.py) |
| [10](10_distributed_systems_theory.md) 🔴 | Distributed systems theory | — |

### Operate
| # | Topic | Practical |
|---|---|---|
| [03](03_observability_resilience.md) | Observability + resilience (circuit breaker, bulkhead) | [`03_...py`](practical/03_observability_resilience.py) |
| [12](12_microservices_testing.md) | Testing — contract, integration, **testcontainers** | [`08_...py`](practical/08_antipatterns_testing_serverless_practical.py) |
| [13](13_serverless_microservices.md) | Serverless microservices | ↑ same |
| [15](15_temporal_durable_workflows.md) | Temporal — durable workflows | — |

**Related:** [07_Kafka](../07_Kafka/README.md) · [06_gRPC](../06_gRPC/README.md) · [04_DevOps](../04_DevOps/README.md) · [Architecture Patterns](../../02_Year5%2B_Senior/02_Architecture_Patterns/README.md) · [HLD_Theory](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/)
