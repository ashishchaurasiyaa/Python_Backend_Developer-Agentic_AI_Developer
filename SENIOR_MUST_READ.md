# 🎓 SENIOR MUST-READ — 60 files, bas itna

> **Yeh kya hai:** 1,300 files me se wo **60** jo senior Python backend banne ke liye **padhni hi hain**.
> Baaki sab reference hai — tab kholna jab zaroorat pade.
>
> **Yeh kya NAHI hai:**
> - Daily plan nahi → [ROADMAP.md](ROADMAP.md) (aaj kya karna hai)
> - Topic checklist nahi → [COMPULSORY_TOPICS.md](COMPULSORY_TOPICS.md) (kya *aana* chahiye, tick karne ke liye)
> - Topic ka poora scope nahi → [STUDY_PLAN.md](STUDY_PLAN.md)
>
> Yeh **reading list** hai: kaunsi file, kis order me, aur **kyun**.

---

## 📏 "Padh liya" ka matlab

Ek file tab done hai jab tum uska **interview question bina file dekhe, bolke, 2 minute me** jawab de sako.
Sirf padh lena = zero. Isliye har file ke saath wo sawal likha hai jo usse aata hai.

**Total time:** ~55–70 ghante. Roz 1.5 ghante = **~7 hafte**.
Kam time hai? Sirf 🔥 wale padho — 22 files, ~20 ghante.

---

# TIER 1 — Yeh 22 files 🔥 (kam time me sirf yeh)

Inke bina senior interview nahi nikalta. Har ek pe ek sawal **guaranteed** aata hai.

## 🐍 Python internals (4)

| # | File | Jo sawal isse aata hai |
|---|---|---|
| 1 | [Memory model + GIL](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/03_memory_gil.md) 🔥 | "GIL kya hai? Threads se CPU work fast kyun nahi hota?" |
| 2 | [Async concurrency deep dive](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/05_async_concurrency_deep_dive.md) 🔥 | "Event loop kaise kaam karta hai? Blocking call daal do to?" |
| 3 | [Concurrency decision framework](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/26_concurrency_decision_framework.md) 🔥 | "threading vs multiprocessing vs asyncio — kab kya?" |
| 4 | [Race conditions debugging](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/11_race_conditions_debugging.md) 🔥 | "Production me race condition kaise pakda?" ← *tumhari real story chahiye* |

## 🗄️ Database — sabse zyada marks yahan (6)

| # | File | Jo sawal isse aata hai |
|---|---|---|
| 5 | [PostgreSQL internals — MVCC/WAL/VACUUM](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/07_postgresql_internals.md) 🔥 | "UPDATE karne pe andar kya hota hai? VACUUM kyun chahiye?" |
| 6 | [Isolation levels + anomalies](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md) 🔥 | "Dirty / non-repeatable / phantom read — example do" |
| 7 | [Advanced indexing](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/20_advanced_indexing.md) 🔥 | "Index laga hai phir bhi slow — kyun?" |
| 8 | [Optimistic vs pessimistic locking](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/19_optimistic_pessimistic_locking.md) 🔥 | "Do user ek hi seat book kar rahe hain — kya karoge?" |
| 9 | [Connection pooling / pgBouncer](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/11_pgbouncer_connection_pooling.md) 🔥 | "1000 concurrent users, 100 DB connections — kaise?" |
| 10 | [Zero-downtime migrations](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/24_zero_downtime_migrations.md) 🔥 | "Live table pe column rename karna hai — steps?" |

## 🏗️ System design core (5)

| # | File | Jo sawal isse aata hai |
|---|---|---|
| 11 | [CAP theorem](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/08_CAP_Theorem.md) 🔥 | "CP vs AP — apne system me kya chuna aur kyun?" |
| 12 | [Back-of-envelope estimation](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/31_Back_of_Envelope_Estimation.md) 🔥 | *Har* design round ke pehle 5 minute yahi hote hain |
| 13 | [Caching complete](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/13_Caching_Complete.md) 🔥 | "Cache kahan lagaoge, invalidate kaise karoge?" |
| 14 | [Database sharding](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/38_Database_Sharding.md) 🔥 | "Ek table 500GB ka ho gaya — ab?" |
| 15 | [Load balancer](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/12_Load_Balancer.md) 🔥 | L4 vs L7, algorithms, health checks |

## 🧩 Distributed systems — yahi senior banata hai (4)

| # | File | Jo sawal isse aata hai |
|---|---|---|
| 16 | [Outbox pattern](Backend_Developer/01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md) 🔥🔥 | "DB commit ho gaya par event publish fail — kya karoge?" ← **sabse discriminating sawal** |
| 17 | [Distributed systems theory](Backend_Developer/01_Year3-4_Mid/05_Microservices/10_distributed_systems_theory.md) 🔥 | Partial failure, consensus, "network reliable nahi hai" |
| 18 | [Saga pattern](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/59_Saga_Pattern.md) 🔥 | "3 service me transaction — 2PC ke bina kaise?" |
| 19 | [Idempotency + testing](Backend_Developer/01_Year3-4_Mid/09_Celery/theory/10_testing_idempotency.md) 🔥 | "Task/API do baar chal gaya to?" |

## 🔐 Security + API (3)

| # | File | Jo sawal isse aata hai |
|---|---|---|
| 20 | [OAuth2 flows deep + OIDC](Backend_Developer/01_Year3-4_Mid/03_Security/04_oauth2_flows_deep.md) 🔥 | "OAuth2 vs OIDC?" · "PKCE kyun?" |
| 21 | [JWT vulnerabilities](Backend_Developer/01_Year3-4_Mid/03_Security/03_jwt_vulnerabilities_2fa_secrets.md) 🔥 | "JWT revoke kaise karoge?" · `alg: none` |
| 22 | [Idempotency + conditional requests](Backend_Developer/01_Year3-4_Mid/02_API_Design/18_conditional_requests_deep.md) 🔥 | "Payment API retry ho gaya — double charge rokoge kaise?" |

> **✋ Yahan ruko.** Yeh 22 padh liye + bolke samjha sakte ho? Tum already zyadatar candidates se aage ho.

---

# TIER 2 — Agle 24 files (senior ka "expected" range)

## Python + code quality (3)
| File | Kyun |
|---|---|
| [Metaclasses + descriptors](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/06_metaclasses_descriptors.md) | "Django `Model` class andar se kaise?" |
| [Modern Python 3.11–3.13](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/18_modern_python_3_11_12_13.md) | Free-threading, TaskGroup — *current* dikhne ke liye |
| [SOLID principles](Backend_Developer/02_Year5%2B_Senior/01_System_Design/LLD_Theory/SOLID_Principles.md) | Code review + LLD round ka base |

## API design (4)
| File | Kyun |
|---|---|
| [Versioning strategies](Backend_Developer/01_Year3-4_Mid/02_API_Design/16_versioning_strategies_deep.md) | "Breaking change kaise ship karoge?" |
| [Rate limiting deep](Backend_Developer/01_Year3-4_Mid/02_API_Design/07_rate_limiting_deep.md) | Token bucket vs sliding window |
| [Webhook design](Backend_Developer/01_Year3-4_Mid/02_API_Design/12_webhook_design_deep.md) | Retry, signature, replay protection |
| [REST vs GraphQL vs gRPC](Backend_Developer/01_Year3-4_Mid/02_API_Design/14_rest_graphql_grpc.md) | Judgment question — kab kya |

## Data + scale (4)
| File | Kyun |
|---|---|
| [Partitioning + sharding](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/10_postgresql_partitioning_sharding.md) | Sharding ka practical side |
| [Performance tuning / EXPLAIN](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/13_postgresql_performance_tuning.md) | "Slow query debug karke dikhao" |
| [Database indexing (HLD view)](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/20_Database_Indexing.md) | Design round me index reasoning |
| [Consistent hashing](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/44_Consistent_Hashing_Theory.md) | Sharding/cache rebalance ka core |

## Caching (3)
| File | Kyun |
|---|---|
| [Caching patterns](Backend_Developer/00_Year0-2_Junior/09_Caching/theory/01_caching_patterns.md) | Cache-aside vs write-through — kab kya |
| [Cache stampede](Backend_Developer/00_Year0-2_Junior/09_Caching/theory/03_cache_stampede_cold_start.md) | "Cache expire hote hi DB gir gaya" |
| [Redlock / distributed locks](Backend_Developer/00_Year0-2_Junior/08_Redis/theory/19_redlock_distributed_locks.md) | "Do server ek hi kaam na karein" |

## Events + messaging (4)
| File | Kyun |
|---|---|
| [Kafka ordering guarantees](Backend_Developer/01_Year3-4_Mid/07_Kafka/08_ordering_guarantees.md) | "Events order me kaise rahenge?" |
| [Exactly-once semantics](Backend_Developer/01_Year3-4_Mid/07_Kafka/05_exactly_once_transactions.md) | "Exactly-once sach me hota hai?" |
| [Event sourcing + CQRS](Backend_Developer/01_Year3-4_Mid/05_Microservices/05_event_sourcing_cqrs.md) | Read/write model alag |
| [Dead letter queue](Backend_Developer/02_Year5%2B_Senior/01_System_Design/HLD_Theory/65_Dead_Letter_Queue.md) | "Message fail hota rahe to kahan jayega?" |

## Architecture (3)
| File | Kyun |
|---|---|
| [Domain-driven design](Backend_Developer/01_Year3-4_Mid/05_Microservices/09_domain_driven_design.md) | "Service boundary kahan khinchoge?" |
| [Microservices anti-patterns](Backend_Developer/01_Year3-4_Mid/05_Microservices/11_microservices_anti_patterns.md) | Distributed monolith — *kya nahi karna* |
| [Observability + resilience](Backend_Developer/01_Year3-4_Mid/05_Microservices/03_observability_resilience.md) | Circuit breaker, bulkhead, retry budget |

## Production ops (3)
| File | Kyun |
|---|---|
| [OpenTelemetry + tracing](Backend_Developer/01_Year3-4_Mid/04_DevOps/19_opentelemetry_distributed_tracing.md) | "10 service me request slow — kahan?" |
| [SRE — SLI/SLO/error budget](Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md) | "Availability target kaise decide karte ho?" |
| [Incident response runbooks](Backend_Developer/01_Year3-4_Mid/14_Engineering_Practices/03_incident_response_runbooks.md) | "Ek production incident batao jo tumne own kiya" |

---

# TIER 3 — Senior/Staff differentiator (14 files)

Yeh wo hain jo tumhe *"achha engineer"* se *"senior engineer"* banate hain. Zyadatar log yeh nahi padhte.

## Concurrency + correctness (2)
[Thread safety (real war stories)](Backend_Developer/02_Year5%2B_Senior/01_System_Design/LLD_Theory/Concurrency_Thread_Safety.md) · [DI + Repository + State Machine](Backend_Developer/02_Year5%2B_Senior/01_System_Design/LLD_Theory/11_Dependency_Injection_Repository_StateMachine.md)

## Security depth (2)
[Session management](Backend_Developer/01_Year3-4_Mid/03_Security/09_session_management.md) · [Secrets management](Backend_Developer/01_Year3-4_Mid/03_Security/08_secrets_management_advanced.md)

## Infra jo tumhare resume pe honi chahiye (2)
[Kubernetes + Helm](Backend_Developer/01_Year3-4_Mid/04_DevOps/06_kubernetes_helm.md) · [Prometheus + Grafana](Backend_Developer/01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md)
> ⚠️ Yeh do sirf padhne se kaam nahi chalega — [ROADMAP](ROADMAP.md) Week 1-2 ke labs karo, warna resume pe likhna jhooth hai.

## Testing (2)
[pytest advanced](Backend_Developer/00_Year0-2_Junior/10_Testing/theory/01_pytest_advanced.md) · [Testcontainers](Backend_Developer/00_Year0-2_Junior/10_Testing/theory/09_testcontainers_python.md)

## Leadership — staff track (3)
[RFC + ADR writing](Backend_Developer/02_Year5%2B_Senior/03_Senior_Leadership/11_rfc_adr_writing.md) · [Tech strategy docs](Backend_Developer/02_Year5%2B_Senior/03_Senior_Leadership/05_tech_strategy_documentation.md) · [DORA metrics](Backend_Developer/02_Year5%2B_Senior/03_Senior_Leadership/07_dora_metrics_productivity.md)

## Interview-specific (3)
[Debugging scenarios](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/09_debugging_scenarios.md) · [Resume walkthrough prep](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/11_resume_walkthrough_prep.md) · [Code review skills](Backend_Developer/01_Year3-4_Mid/14_Engineering_Practices/01_code_review_skills.md)

---

# 🤖 AI/GenAI role bhi target kar rahe ho? (+3)

Sirf tab jab JD me AI ho. Yeh 3 kaafi hain interview ke liye:

| File | Kyun |
|---|---|
| [RAG advanced](Agentic_AI/Level5_RAG_Vector_Databases/02_rag_advanced.md) | RAG design round ka poora core (2356 lines — sabse bada) |
| [Agent harness engineering](Agentic_AI/Level6_Agent_Patterns/12_agent_harness_engineering.md) | "Agent production me kaise chalega" |
| [LLMOps production](Agentic_AI/Level8_Production_LLMOps/02_llmops_production.md) | Eval, cost, guardrails, monitoring |

---

# 🧮 Padhna kaafi nahi — yeh 2 cheezein ROZ

| Kya | Kahan | Kyun |
|---|---|---|
| **DSA — 1 problem** | [`practice/harness.py`](Backend_Developer/03_Interview_AnyYear/01_DSA/practice/) (35 problems) · [patterns index](Backend_Developer/03_Interview_AnyYear/01_DSA/00_Coding_Patterns_Index.md) | Coding round **pehla filter** hai. Upar ki saari knowledge bekaar agar yahin kat gaye. |
| **System design — 1 drill, BOLKE** | [PRACTICE_DRILLS.md](Backend_Developer/02_Year5%2B_Senior/01_System_Design/PRACTICE_DRILLS.md) (12 drills, rubric ke saath) | Senior round **bolne** ka test hai, padhne ka nahi. |

---

# ❌ Jo mat padho (abhi)

Time bachane ke liye yeh saaf likh raha hoon:

- **Poora 1,300-file repo** — 95% reference hai. Zaroorat pe kholo.
- **Segment Tree, Suffix Automaton, Digit DP** — FAANG-tier ke liye. India product companies me nahi aata.
- **gRPC / GraphQL / Elasticsearch** — sirf tab jab **JD me naam ho**. Warna skip.
- **Har design pattern** — Strategy, Observer, State, Factory, Repository, DI. Baaki tab jab milein.
- **Junior basics** — tum 4 saal ke ho. Bas weak spot pe jao.

---

## Roz ka rasta

1. Aaj ka kaam → [ROADMAP.md](ROADMAP.md)
2. Raat ko 3 line → [MY_PROGRESS.md](MY_PROGRESS.md)
3. Interview aane pe → [INTERVIEW_PREP_COMPANIES.md](INTERVIEW_PREP_COMPANIES.md) + [JOB_TRACKER.md](JOB_TRACKER.md)
4. Yeh file → jab poochna ho *"senior ke liye kya padhna hi hai"*

> **Yaad rakho:** yeh list padh lene se senior nahi banoge. Yeh list padh ke **bol paane** se banoge.
> Har file ke saath uska sawal likha hai — file band karke wo sawal apne aap se pooch lo. Atko to file dobara kholo.
