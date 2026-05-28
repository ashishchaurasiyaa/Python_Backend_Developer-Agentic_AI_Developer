# 🚀 0 → 5 Years Study Plan — HIGH Priority Drilling

> **Complete year-by-year roadmap** to go from zero to senior Python backend dev (5-year level) by drilling HIGH priority topics from [PRIORITY_ANALYSIS_5YEAR_2026.md](PRIORITY_ANALYSIS_5YEAR_2026.md).

**Total time:** ~5 years (or compressed to 18-24 months if full-time)
**Daily commitment:** 1-3 hours
**Output by end:** Senior backend engineer ready for ₹25-50 LPA roles

---

## 🎯 The 5-Year Vision

```
Year 0  → Foundation + Python basics
Year 1  → Junior backend dev (first job)
Year 2  → Solid mid-level (own features)
Year 3  → Strong mid-level (architecture input)
Year 4  → Senior candidate (lead small projects)
Year 5  → Senior backend dev (own systems)
```

---

## 📅 YEAR 0 — Foundation (Months 1-3, Pre-Job)

**Goal:** Build the unshakeable foundation. After this, you can write Python AND understand what's under it.

### Month 1 — Linux + Python Basics

**Daily routine (1.5 hrs):**

```
30 min  →  Read theory (02_Python_Daily)
45 min  →  Code along (write every example)
15 min  →  Linux/Bash practice
```

**Topics + Docs:**

| Week | Topic | Docs to Drill |
|---|---|---|
| 1 | Linux + Bash essentials | [00_Year0-2_Junior/01_Foundations/01_linux_bash_essentials.md](00_Year0-2_Junior/01_Foundations/01_linux_bash_essentials.md) |
| 1 | Python variables, types, control flow | [00_Year0-2_Junior/02_Python_Daily/Day1-3](00_Year0-2_Junior/02_Python_Daily) |
| 2 | Strings, lists, tuples, dicts | [Day4-7](00_Year0-2_Junior/02_Python_Daily) |
| 3 | Functions, scope, args | [Day8-10](00_Year0-2_Junior/02_Python_Daily) |
| 4 | File I/O, exceptions | [Day11-15](00_Year0-2_Junior/02_Python_Daily) |

**Practice:**
- Solve 5-10 easy LeetCode problems from `03_Interview_AnyYear/01_DSA/01_Arrays_Hashing/`
- Write 5 small Bash scripts (file rename, log search, backup)

**Milestone:**
- ✅ Can navigate Linux comfortably (ls, grep, find, ps)
- ✅ Can write a 50-line Python script that reads a file, processes it, outputs a result

---

### Month 2 — Python OOP + Git

**Daily routine (1.5 hrs):**

```
30 min  →  OOP theory
60 min  →  Code + practice
```

**Topics + Docs:**

| Week | Topic | Docs |
|---|---|---|
| 1 | Classes, inheritance, polymorphism | [Day11-15](00_Year0-2_Junior/02_Python_Daily) |
| 1 | Git workflows | [00_Year0-2_Junior/01_Foundations/04_git_workflows.md](00_Year0-2_Junior/01_Foundations/04_git_workflows.md) |
| 2 | Decorators + context managers | [Day24-25](00_Year0-2_Junior/02_Python_Daily) |
| 3 | Modules + packages | [Day16-20](00_Year0-2_Junior/02_Python_Daily) |
| 4 | Comprehensions, generators, iterators | [Day21-28](00_Year0-2_Junior/02_Python_Daily) |

**Practice:**
- Build a CLI tool (todo app, file organizer)
- Push it to GitHub with proper commits + README
- Solve 5 DSA problems (strings, linked list)

**Milestone:**
- ✅ Public GitHub repo with weekly commits
- ✅ Can explain inheritance vs composition
- ✅ Can use decorators (@property, @staticmethod, custom)

---

### Month 3 — OS + Networking Basics + Testing

**Topics + Docs:**

| Week | Topic | Docs |
|---|---|---|
| 1 | OS concepts (processes, threads, memory) | [00_Year0-2_Junior/01_Foundations/02_os_concepts.md](00_Year0-2_Junior/01_Foundations/02_os_concepts.md) |
| 2 | Networking fundamentals (TCP/IP, HTTP, DNS) | [00_Year0-2_Junior/01_Foundations/03_networking_fundamentals.md](00_Year0-2_Junior/01_Foundations/03_networking_fundamentals.md) |
| 3 | Type hints + Pydantic basics | [Day29](00_Year0-2_Junior/02_Python_Daily/Day29_Typing_Deep_Dive), [Day47](00_Year0-2_Junior/02_Python_Daily/Day47_Pydantic_v2) |
| 4 | Pytest fundamentals | [Day41_Testing](00_Year0-2_Junior/02_Python_Daily/Day41_Testing) + [00_Year0-2_Junior/10_Testing/theory/01](00_Year0-2_Junior/10_Testing/theory/01_pytest_advanced.md) |

**Practice:**
- Write tests for your CLI tool
- Add type hints everywhere
- Solve 10 DSA problems (sliding window, two pointers from [03_Interview_AnyYear/01_DSA/06](03_Interview_AnyYear/01_DSA/06_Two_Pointers_Sliding_Window))

**Year 0 Milestone:**
- ✅ Solid Python fluency (no looking up syntax)
- ✅ Comfort with Linux/Git/networking basics
- ✅ One CLI project on GitHub with tests + docs
- ✅ Solved 30+ easy DSA problems

---

## 📅 YEAR 1 — Junior Backend (Build First Web Apps)

**Goal:** Ship your first APIs. Get hireable.

### Months 4-6 — FastAPI + SQL Fundamentals

**Daily routine (2 hrs):**

```
1 hr   →  FastAPI theory + code
30 min →  SQL + Postgres practice
30 min →  DSA (rotate categories)
```

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 4 | FastAPI basics (routing, params, Pydantic) | [00_Year0-2_Junior/06_FastAPI/01-05](00_Year0-2_Junior/06_FastAPI) |
| 4 | SQL fundamentals | [03_Interview_AnyYear/02_Interview_Prep/04_sql_interview_questions.md](03_Interview_AnyYear/02_Interview_Prep/04_sql_interview_questions.md) |
| 5 | FastAPI auth (JWT + OAuth2) | [00_Year0-2_Junior/06_FastAPI/06](00_Year0-2_Junior/06_FastAPI/06_security_jwt.md), [00_Year0-2_Junior/06_FastAPI/19](00_Year0-2_Junior/06_FastAPI/19_oauth2_full_flows.md) |
| 5 | Postgres basics + indexing | [00_Year0-2_Junior/04_Database_SQL/01-04](00_Year0-2_Junior/04_Database_SQL) |
| 6 | SQLAlchemy async | [00_Year0-2_Junior/06_FastAPI/04](00_Year0-2_Junior/06_FastAPI/04_testing_sqlalchemy.md), [00_Year0-2_Junior/06_FastAPI/09](00_Year0-2_Junior/06_FastAPI/09_sqlalchemy_advanced.md) |
| 6 | Pytest for FastAPI | [00_Year0-2_Junior/10_Testing/theory/08](00_Year0-2_Junior/10_Testing/theory/08_fastapi_testing_patterns.md) |

**Project (Months 4-6):**
- Build a **multi-user blog API** with FastAPI + Postgres
- Features: JWT auth, CRUD posts, comments, tags
- Tests: pytest coverage > 70%
- Deploy: Railway / Render (free tier)

**Milestone:**
- ✅ Deployed blog API publicly
- ✅ Can write Pydantic models, FastAPI routes, SQLAlchemy queries
- ✅ Comfortable with `JOIN`, `GROUP BY`, indexes

---

### Months 7-9 — Redis, Docker, REST Best Practices

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 7 | REST + HTTP deep | [01_Year3-4_Mid/02_API_Design/01-03](01_Year3-4_Mid/02_API_Design), [HLD_Theory/48](02_Year5+_Senior/01_System_Design/HLD_Theory/48_HTTP_Versions_Deep.md) |
| 7 | Redis basics + caching patterns | [00_Year0-2_Junior/08_Redis/01-03](00_Year0-2_Junior/08_Redis/theory), [00_Year0-2_Junior/09_Caching/01](00_Year0-2_Junior/09_Caching/theory/01_caching_patterns.md) |
| 8 | Docker | [01_Year3-4_Mid/04_DevOps/01](01_Year3-4_Mid/04_DevOps/01_docker.md), [Day49](00_Year0-2_Junior/02_Python_Daily/Day49_Docker) |
| 8 | Middleware + CORS | [00_Year0-2_Junior/06_FastAPI/03](00_Year0-2_Junior/06_FastAPI/03_middleware_websockets.md), [01_Year3-4_Mid/03_Security/07](01_Year3-4_Mid/03_Security/07_cors_csp_security_headers.md) |
| 9 | Error handling + RFC 7807 | [00_Year0-2_Junior/06_FastAPI/05](00_Year0-2_Junior/06_FastAPI/05_exception_handling.md), [00_Year0-2_Junior/06_FastAPI/20](00_Year0-2_Junior/06_FastAPI/20_owasp_api_top10.md) |
| 9 | Idempotency + rate limiting | [00_Year0-2_Junior/06_FastAPI/22](00_Year0-2_Junior/06_FastAPI/22_hmac_webhooks_idempotency.md), [01_Year3-4_Mid/02_API_Design/06](01_Year3-4_Mid/02_API_Design/06_rate_limiting_deep.md) |

**Project (Months 7-9):**
- **URL shortener** with Redis cache + Docker
- Reproduce [Projects/03](03_Interview_AnyYear/03_Projects/03_FastAPI_URL_Shortener_Scale.md)
- Add: analytics, custom slugs, expiration
- Deploy with Docker Compose

**DSA:** Solve 30 problems in Year 1 (mix Arrays, Strings, Linked List, Trees BFS/DFS)

**Year 1 Milestone (Job-Ready Junior):**
- ✅ 2 deployed projects on GitHub
- ✅ Can build a CRUD API with auth in 1 day
- ✅ Comfortable with Docker basics
- ✅ Resume + first job applications
- 🎯 **Target: Junior backend role**

---

## 📅 YEAR 2 — Solid Mid-Level

**Goal:** Stop being "the junior who needs hand-holding." Own features end-to-end.

### Months 10-15 — Advanced Database + Async

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 10 | Postgres advanced (joins, CTEs, window fns) | [00_Year0-2_Junior/04_Database_SQL/03](00_Year0-2_Junior/04_Database_SQL/03_window_functions_cte.md), [00_Year0-2_Junior/04_Database_SQL/05](00_Year0-2_Junior/04_Database_SQL/05_postgresql_internals.md) |
| 10 | N+1 queries + query optimization | [00_Year0-2_Junior/07_Django_DRF/15](00_Year0-2_Junior/07_Django_DRF/15_n_plus_1_detection.md), [00_Year0-2_Junior/06_FastAPI/09](00_Year0-2_Junior/06_FastAPI/09_sqlalchemy_advanced.md) |
| 11 | Database transactions + isolation | [00_Year0-2_Junior/04_Database_SQL/19](00_Year0-2_Junior/04_Database_SQL/19_optimistic_pessimistic_locking.md), [00_Year0-2_Junior/04_Database_SQL/21](00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md) |
| 11 | Asyncio fundamentals | [Day31](00_Year0-2_Junior/02_Python_Daily/Day31_Asyncio_Advanced), [01_Year3-4_Mid/01_Python_Advanced/theory/05](01_Year3-4_Mid/01_Python_Advanced/theory/05_async_concurrency_deep_dive.md) |
| 12 | Pydantic v2 deep + dataclasses | [Day33](00_Year0-2_Junior/02_Python_Daily/Day33_Dataclasses_Advanced), [Day47](00_Year0-2_Junior/02_Python_Daily/Day47_Pydantic_v2) |
| 12 | Connection pooling (PgBouncer) | [00_Year0-2_Junior/04_Database_SQL/09](00_Year0-2_Junior/04_Database_SQL/09_pgbouncer_connection_pooling.md) |
| 13 | Migrations (Alembic) | [00_Year0-2_Junior/04_Database_SQL/22](00_Year0-2_Junior/04_Database_SQL/22_alembic_advanced.md), [00_Year0-2_Junior/04_Database_SQL/24](00_Year0-2_Junior/04_Database_SQL/24_zero_downtime_migrations.md) |
| 13 | Background tasks (Celery basics) | [01_Year3-4_Mid/09_Celery/theory/01](01_Year3-4_Mid/09_Celery/theory/01_celery_basics.md) |
| 14 | Logging + structured logging | [00_Year0-2_Junior/06_FastAPI/25](00_Year0-2_Junior/06_FastAPI/25_structured_logging.md), [Day30](00_Year0-2_Junior/02_Python_Daily/Day30_Logging_Pathlib_Dotenv) |
| 14 | Health checks + readiness | [00_Year0-2_Junior/06_FastAPI/24](00_Year0-2_Junior/06_FastAPI/24_health_checks_k8s.md) |
| 15 | OWASP Top 10 | [01_Year3-4_Mid/03_Security/02](01_Year3-4_Mid/03_Security/02_owasp_brute_force_csrf.md), [00_Year0-2_Junior/06_FastAPI/20](00_Year0-2_Junior/06_FastAPI/20_owasp_api_top10.md) |
| 15 | Secrets management | [01_Year3-4_Mid/03_Security/08](01_Year3-4_Mid/03_Security/08_secrets_management_advanced.md) |

**Project (Months 10-15):**
- **Multi-tenant SaaS** (clone of [Projects/01](03_Interview_AnyYear/03_Projects/01_FastAPI_Multi_Tenant_SaaS.md))
- Features: per-tenant data isolation, RBAC, async background jobs
- Add observability: structured logs, Prometheus metrics

**DSA:** Solve 60 problems (Trees, Graphs BFS/DFS, Recursion, basic DP from [03_Interview_AnyYear/01_DSA/11-12](03_Interview_AnyYear/01_DSA))

**Year 2 Milestone:**
- ✅ Can write complex SQL with optimizations
- ✅ Understands async deeply
- ✅ Knows database internals (MVCC, indexes, isolation)
- ✅ Production-ready code (logging, health, secrets, errors)
- 🎯 **Target: Confident mid-level**

---

## 📅 YEAR 3 — Strong Mid-Level

**Goal:** Be the engineer everyone asks "how should we design X?"

### Months 16-21 — Distributed Systems + Messaging

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 16 | CAP theorem + consistency | [HLD_Theory/08](02_Year5+_Senior/01_System_Design/HLD_Theory/08_CAP_Theorem.md), [HLD_Theory/07](02_Year5+_Senior/01_System_Design/HLD_Theory/07_Consistency_Strong_vs_Eventual.md) |
| 16 | Microservices vs Monolith | [01_Year3-4_Mid/05_Microservices/01](01_Year3-4_Mid/05_Microservices/01_microservices_patterns.md) |
| 17 | Replication + sharding | [00_Year0-2_Junior/04_Database_SQL/07](00_Year0-2_Junior/04_Database_SQL/07_postgresql_ha_read_replicas.md), [00_Year0-2_Junior/04_Database_SQL/08](00_Year0-2_Junior/04_Database_SQL/08_partitioning_sharding.md) |
| 17 | Load balancing | [HLD_Theory/12](02_Year5+_Senior/01_System_Design/HLD_Theory/12_Load_Balancer.md), [01_Year3-4_Mid/04_DevOps/02](01_Year3-4_Mid/04_DevOps/02_nginx.md) |
| 18 | Celery deep + workflows | [01_Year3-4_Mid/09_Celery/theory/02-09](01_Year3-4_Mid/09_Celery/theory) |
| 18 | RabbitMQ | [01_Year3-4_Mid/08_RabbitMQ/theory](01_Year3-4_Mid/08_RabbitMQ/theory) (all 7 docs) |
| 19 | Kafka fundamentals | [01_Year3-4_Mid/07_Kafka](01_Year3-4_Mid/07_Kafka) (all 6 docs) |
| 19 | Saga pattern + Outbox | [01_Year3-4_Mid/05_Microservices/04](01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md), [01_Year3-4_Mid/05_Microservices/05](01_Year3-4_Mid/05_Microservices/05_event_sourcing_cqrs.md) |
| 20 | API Gateway + BFF | [01_Year3-4_Mid/02_API_Design/14](01_Year3-4_Mid/02_API_Design/14_bff_pattern.md) |
| 20 | WebSocket scaling | [00_Year0-2_Junior/06_FastAPI/15](00_Year0-2_Junior/06_FastAPI/15_websocket_scaling.md), [01_Year3-4_Mid/13_WebSocket_SSE/03](01_Year3-4_Mid/13_WebSocket_SSE/03_scaling_redis_pubsub.md) |
| 21 | OAuth2 deep flows | [01_Year3-4_Mid/03_Security/04](01_Year3-4_Mid/03_Security/04_oauth2_flows_deep.md) |
| 21 | Zero-trust + mTLS | [01_Year3-4_Mid/03_Security/10](01_Year3-4_Mid/03_Security/10_zero_trust_microservices.md) |

**Project (Months 16-21):**
- **Real-time chat app** with WebSocket + Redis pub/sub + Kafka events
- Clone [Projects/04](03_Interview_AnyYear/03_Projects/04_FastAPI_WhatsApp_Lite_Chat.md)
- Features: 1-to-1 + group chat, presence, history, delivery receipts
- Stretch: notification service via Kafka

**DSA:** Solve 80 problems (Trees, Graphs advanced, DP intermediate, Heaps from [03_Interview_AnyYear/01_DSA/10-12](03_Interview_AnyYear/01_DSA))

**System Design Practice:**
- Weekly: 1 HLD problem from [HLD_Problems/](02_Year5+_Senior/01_System_Design/HLD_Problems)
- Whiteboard before reading the solution
- Start with: URL Shortener, Rate Limiter, Distributed Cache, Notification Service

**Year 3 Milestone:**
- ✅ Can design medium-scale systems on whiteboard
- ✅ Understands distributed systems trade-offs
- ✅ Comfortable with Celery, Kafka, RabbitMQ patterns
- ✅ Can pass mid-level interviews
- 🎯 **Target: Strong mid-level, ready for senior interviews**

---

## 📅 YEAR 4 — Senior Candidate

**Goal:** Architect-level thinking. Lead small projects. Own a domain.

### Months 22-30 — Kubernetes + Architecture + Advanced DSA

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 22 | Kubernetes + Helm | [01_Year3-4_Mid/04_DevOps/06](01_Year3-4_Mid/04_DevOps/06_kubernetes_helm.md) |
| 22 | Production deployment | [01_Year3-4_Mid/04_DevOps/09-11](01_Year3-4_Mid/04_DevOps) |
| 23 | Observability (Prometheus + Grafana) | [01_Year3-4_Mid/04_DevOps/05](01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md) |
| 23 | Distributed tracing (OpenTelemetry) | [00_Year0-2_Junior/06_FastAPI/14](00_Year0-2_Junior/06_FastAPI/14_opentelemetry_distributed_tracing.md) |
| 24 | Clean architecture + DDD | [00_Year0-2_Junior/06_FastAPI/12](00_Year0-2_Junior/06_FastAPI/12_clean_architecture_ddd.md), [01_Year3-4_Mid/05_Microservices/09](01_Year3-4_Mid/05_Microservices/09_domain_driven_design.md) |
| 24 | Software architecture course | [02_Year5+_Senior/02_Architecture_Patterns/Section_01-04](02_Year5+_Senior/02_Architecture_Patterns) |
| 25 | Service mesh + resilience patterns | [01_Year3-4_Mid/05_Microservices/06](01_Year3-4_Mid/05_Microservices/06_service_mesh_istio_linkerd.md), [01_Year3-4_Mid/04_DevOps/14](01_Year3-4_Mid/04_DevOps/14_chaos_engineering.md) |
| 25 | Terraform + GitOps | [01_Year3-4_Mid/04_DevOps/07](01_Year3-4_Mid/04_DevOps/07_terraform.md), [01_Year3-4_Mid/04_DevOps/13](01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md) |
| 26 | Advanced testing | [00_Year0-2_Junior/10_Testing/theory/04-06](00_Year0-2_Junior/10_Testing/theory) + [00_Year0-2_Junior/10_Testing/contract_testing_pact.md](00_Year0-2_Junior/10_Testing/contract_testing_pact.md) |
| 26 | SRE practices (SLI/SLO) | [01_Year3-4_Mid/04_DevOps/16](01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md) |
| 27 | gRPC | [01_Year3-4_Mid/06_gRPC/01-05](01_Year3-4_Mid/06_gRPC) |
| 27 | GraphQL deep | [01_Year3-4_Mid/12_GraphQL](01_Year3-4_Mid/12_GraphQL) (all 7) |
| 28 | LLD + Design Patterns | [LLD_Theory](02_Year5+_Senior/01_System_Design/LLD_Theory) (all 28 docs) |
| 28 | LLD problems practice | [LLD_Problems](02_Year5+_Senior/01_System_Design/LLD_Problems) (start: Parking Lot, ATM, LRU Cache) |
| 29 | Advanced DSA (DP, Graphs, Tries) | [03_Interview_AnyYear/01_DSA/12](03_Interview_AnyYear/01_DSA/12_Dynamic_Programming), [15](03_Interview_AnyYear/01_DSA/15_Advanced_Graphs), [14](03_Interview_AnyYear/01_DSA/14_Trie) |
| 29 | HLD deep practice | 2 HLD problems/week from [HLD_Problems](02_Year5+_Senior/01_System_Design/HLD_Problems) |
| 30 | Architecture decision-making | [02_Year5+_Senior/02_Architecture_Patterns/Section_09](02_Year5+_Senior/02_Architecture_Patterns/Section_09_Architectural_Decision_Making) |
| 30 | Anti-patterns | [01_Year3-4_Mid/05_Microservices/11](01_Year3-4_Mid/05_Microservices/11_microservices_anti_patterns.md) |

**Project (Months 22-30):**
- **Production-grade banking API** (clone of [Projects/05](03_Interview_AnyYear/03_Projects/05_Django_Banking_Fintech.md))
- Features: ACID transactions, audit log, multi-currency, fraud detection
- Architecture: Hexagonal/Clean, full observability
- Deploy on K8s with Helm + Terraform

**DSA:** Total 200+ problems across all 28 categories

**Mock Interviews:**
- Bi-weekly: HLD mock with peer
- Weekly: 1 coding mock recorded
- Monthly: behavioral practice

**Year 4 Milestone:**
- ✅ Can design any classic system from scratch
- ✅ Comfortable with K8s + Terraform + observability
- ✅ Understands architecture trade-offs
- ✅ 200+ DSA solved across categories
- 🎯 **Target: Pass senior interviews at small-mid companies**

---

## 📅 YEAR 5 — Senior Backend Dev

**Goal:** Senior. Production-grade ownership. AI/LLM fluency. Specialization.

### Months 31-36 — AI/LLM + Specialization + Polish

**Topics + Docs:**

| Month | Focus | Docs |
|---|---|---|
| 31 | LLM integration in FastAPI | [00_Year0-2_Junior/06_FastAPI/31-32](00_Year0-2_Junior/06_FastAPI) |
| 31 | Prompt injection security | [00_Year0-2_Junior/06_FastAPI/33](00_Year0-2_Junior/06_FastAPI/33_prompt_injection_security.md) |
| 32 | RAG backend architecture | [00_Year0-2_Junior/06_FastAPI/34](00_Year0-2_Junior/06_FastAPI/34_rag_backend_architecture.md) |
| 32 | Vector DBs comparison | [00_Year0-2_Junior/04_Database_SQL/28](00_Year0-2_Junior/04_Database_SQL/28_vector_databases_comparison.md) |
| 33 | MCP server | [00_Year0-2_Junior/06_FastAPI/35](00_Year0-2_Junior/06_FastAPI/35_mcp_server_implementation.md) |
| 33 | Semantic caching | [00_Year0-2_Junior/09_Caching/theory/06](00_Year0-2_Junior/09_Caching/theory/06_semantic_caching_llm.md) |
| 34 | Modern HLD (ChatGPT/RAG/Agent) | [HLD_Problems/Design_ChatGPT_Backend](02_Year5+_Senior/01_System_Design/HLD_Problems/Design_ChatGPT_Backend.md), [Design_RAG_System](02_Year5+_Senior/01_System_Design/HLD_Problems/Design_RAG_System.md), [Design_Agent_Orchestration](02_Year5+_Senior/01_System_Design/HLD_Problems/Design_Agent_Orchestration.md) |
| 34 | Temporal durable workflows | [01_Year3-4_Mid/05_Microservices/15](01_Year3-4_Mid/05_Microservices/15_temporal_durable_workflows.md) |
| 35 | ClickHouse for analytics | [00_Year0-2_Junior/04_Database_SQL/27](00_Year0-2_Junior/04_Database_SQL/27_clickhouse_olap.md) |
| 35 | Feature flags | [01_Year3-4_Mid/04_DevOps/18](01_Year3-4_Mid/04_DevOps/18_feature_flags_experimentation.md) |
| 36 | Passkeys / WebAuthn | [01_Year3-4_Mid/03_Security/18](01_Year3-4_Mid/03_Security/18_passkeys_webauthn.md) |
| 36 | India DPDP / Compliance | [01_Year3-4_Mid/03_Security/17](01_Year3-4_Mid/03_Security/17_india_dpdp_compliance.md) |

**Project (Months 31-36):**
- **AI-powered backend** (clone [Projects/08](03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend.md) or [Projects/09](03_Interview_AnyYear/03_Projects/09_Realtime_AI_Chat_App.md))
- Full production deploy: K8s + observability + feature flags
- Add MCP server interface for LLM tool use

**Interview Prep:**
- Daily: 2-3 DSA problems
- Weekly: 2 HLD mocks
- Bi-weekly: 1 LLD mock
- Monthly: full mock interview (coding + system + behavioral)
- Practice: [03_Interview_AnyYear/02_Interview_Prep](03_Interview_AnyYear/02_Interview_Prep) (all 8 docs)

**Behavioral + Negotiation:**
- Drill: [03_Interview_AnyYear/02_Interview_Prep/10](03_Interview_AnyYear/02_Interview_Prep/10_behavioral_backend.md)
- Prepare: [03_Interview_AnyYear/02_Interview_Prep/11](03_Interview_AnyYear/02_Interview_Prep/11_resume_walkthrough_prep.md)
- Negotiate: [03_Interview_AnyYear/02_Interview_Prep/12](03_Interview_AnyYear/02_Interview_Prep/12_negotiation_offer.md)

**Year 5 Milestone:**
- ✅ Can integrate LLMs into production backend
- ✅ Senior interview-ready (₹25-50 LPA roles)
- ✅ 3 deployed projects on GitHub
- ✅ Active open-source contributions
- 🎯 **Target: Senior offer at ₹30+ LPA**

---

## 📅 Daily / Weekly Routine (Template)

### Daily (1-3 hours)

```
Weekday Morning (30 min) — before work
   ✓ Quick read of 1 doc section
   ✓ Or 1 DSA problem (warm-up)

Lunch (30 min)
   ✓ Review yesterday's notes
   ✓ Practice 1 SQL query / 1 LeetCode

Evening (1-2 hours)
   ✓ Deep study session
   ✓ Code along with theory
   ✓ Work on current project

Before sleep (15 min)
   ✓ Read interview Q&A from [03_Interview_AnyYear/02_Interview_Prep](03_Interview_AnyYear/02_Interview_Prep)
   ✓ Reflection: what I learned today
```

### Weekly

```
Mon-Fri  →  Daily routine above
Saturday →  3-4 hour project work session
            + 1 HLD whiteboard practice
Sunday   →  Mock interview (recorded)
            + review week's notes
            + plan next week
```

### Monthly

```
Week 1  →  New topic introduction
Week 2-3 →  Deep practice + project work
Week 4  →  Review, mock interview, update resume
```

---

## 🎯 DSA Daily Drill (HIGH Categories)

Rotate through the 13 HIGH-priority categories from [PRIORITY_ANALYSIS H9](PRIORITY_ANALYSIS_5YEAR_2026.md):

```
Day 1 — Arrays + Hashing       [03_Interview_AnyYear/01_DSA/01](03_Interview_AnyYear/01_DSA/01_Arrays_Hashing)
Day 2 — Strings                [03_Interview_AnyYear/01_DSA/02](03_Interview_AnyYear/01_DSA/02_Strings)
Day 3 — Linked List            [03_Interview_AnyYear/01_DSA/03](03_Interview_AnyYear/01_DSA/03_Linked_List)
Day 4 — Stack + Queue          [03_Interview_AnyYear/01_DSA/04](03_Interview_AnyYear/01_DSA/04_Stack_Queue)
Day 5 — Binary Search          [03_Interview_AnyYear/01_DSA/05](03_Interview_AnyYear/01_DSA/05_Binary_Search)
Day 6 — Two Pointers/Sliding   [03_Interview_AnyYear/01_DSA/06](03_Interview_AnyYear/01_DSA/06_Two_Pointers_Sliding_Window)
Day 7 — Recursion/Backtracking [03_Interview_AnyYear/01_DSA/07](03_Interview_AnyYear/01_DSA/07_Recursion_Backtracking)
Day 8 — Sorting                [03_Interview_AnyYear/01_DSA/08](03_Interview_AnyYear/01_DSA/08_Sorting_Algorithms)
Day 9 — Trees                  [03_Interview_AnyYear/01_DSA/09](03_Interview_AnyYear/01_DSA/09_Trees)
Day 10 — Heaps                 [03_Interview_AnyYear/01_DSA/10](03_Interview_AnyYear/01_DSA/10_Heaps_Priority_Queue)
Day 11 — Graphs BFS/DFS        [03_Interview_AnyYear/01_DSA/11](03_Interview_AnyYear/01_DSA/11_Graphs_BFS_DFS)
Day 12 — Dynamic Programming   [03_Interview_AnyYear/01_DSA/12](03_Interview_AnyYear/01_DSA/12_Dynamic_Programming)
Day 13 — Greedy                [03_Interview_AnyYear/01_DSA/13](03_Interview_AnyYear/01_DSA/13_Greedy)
Day 14 — REST / repeat weak areas
```

**Volume targets:**
```
Year 1:   30 problems   (easy)
Year 2:   60 problems   (easy + medium)
Year 3:   80 problems   (medium)
Year 4:  120 problems   (medium + hard)
Year 5:  150+ problems  (all difficulty)

By Year 5 total: 400+ DSA problems solved
```

---

## 📚 HIGH-Priority Topic Coverage Map

### Year 1 Foundation Topics (Master First)

```
✓ Linux + Bash               [00_Year0-2_Junior/01_Foundations/01]
✓ Python core (52 days)      [00_Year0-2_Junior/02_Python_Daily]
✓ OS concepts                [00_Year0-2_Junior/01_Foundations/02]
✓ Networking basics          [00_Year0-2_Junior/01_Foundations/03]
✓ Git workflows              [00_Year0-2_Junior/01_Foundations/04]
✓ FastAPI fundamentals       [00_Year0-2_Junior/06_FastAPI/01-10]
✓ SQL + Postgres basics      [00_Year0-2_Junior/04_Database_SQL/01-04]
✓ Redis + caching            [00_Year0-2_Junior/08_Redis, 00_Year0-2_Junior/09_Caching]
✓ Docker basics              [01_Year3-4_Mid/04_DevOps/01]
✓ Pytest                     [00_Year0-2_Junior/10_Testing/theory/01]
✓ JWT + OAuth2               [00_Year0-2_Junior/06_FastAPI/06, 19]
✓ REST best practices        [01_Year3-4_Mid/02_API_Design/01-03]
```

### Year 2-3 Mid-Level (Solidify)

```
✓ Postgres advanced          [00_Year0-2_Junior/04_Database_SQL/05-20]
✓ N+1 + query optimization   [multiple]
✓ Asyncio deep               [Day31, 01_Year3-4_Mid/01_Python_Advanced]
✓ Pydantic v2                [Day47]
✓ Celery + queues            [01_Year3-4_Mid/09_Celery]
✓ Distributed systems        [01_Year3-4_Mid/05_Microservices/01-10]
✓ Replication + sharding     [00_Year0-2_Junior/04_Database_SQL/07-08]
✓ Kafka + RabbitMQ           [01_Year3-4_Mid/07_Kafka, 01_Year3-4_Mid/08_RabbitMQ]
✓ WebSocket scaling          [00_Year0-2_Junior/06_FastAPI/15]
✓ OWASP + Zero-trust         [01_Year3-4_Mid/03_Security/02, 10]
✓ Saga + Outbox              [01_Year3-4_Mid/05_Microservices/04-05]
```

### Year 4-5 Senior (Specialize)

```
✓ Kubernetes + Helm          [01_Year3-4_Mid/04_DevOps/06]
✓ Terraform + GitOps         [01_Year3-4_Mid/04_DevOps/07, 13]
✓ Observability + SRE        [01_Year3-4_Mid/04_DevOps/05, 16]
✓ Clean architecture + DDD   [01_Year3-4_Mid/05_Microservices/09]
✓ HLD (40 problems)          [02_Year5+_Senior/01_System_Design/HLD_Problems]
✓ LLD (21 problems)          [02_Year5+_Senior/01_System_Design/LLD_Problems]
✓ Software Architecture      [02_Year5+_Senior/02_Architecture_Patterns]
✓ AI/LLM integration         [00_Year0-2_Junior/06_FastAPI/31-37]
✓ Vector DBs + RAG           [00_Year0-2_Junior/04_Database_SQL/28, 00_Year0-2_Junior/06_FastAPI/34]
✓ Temporal workflows         [01_Year3-4_Mid/05_Microservices/15]
✓ Feature flags              [01_Year3-4_Mid/04_DevOps/18]
✓ Passkeys + DPDP            [01_Year3-4_Mid/03_Security/17, 18]
✓ Negotiation                [03_Interview_AnyYear/02_Interview_Prep/12]
```

---

## 🚀 Compressed Timeline (Full-Time, 18-24 Months)

If you can study 6-8 hours/day:

```
Month 1-2     →  Year 0 (Foundations + Python)
Month 3-5     →  Year 1 (FastAPI + SQL + projects)
Month 6-9     →  Year 2 (Async + DB + production)
Month 10-13   →  Year 3 (Distributed + messaging + system design)
Month 14-17   →  Year 4 (K8s + architecture + DSA)
Month 18-20   →  Year 5 (AI/LLM + senior interviews)
Month 21-24   →  Active interviewing + landing senior role
```

→ **Compressed path: 5 years of growth in 2 years.**

---

## 📊 Milestone Checklist

### Year 1 — Junior
- [ ] 2+ deployed projects on GitHub
- [ ] First backend job offer
- [ ] 30+ DSA problems solved
- [ ] Comfortable with FastAPI + Postgres + Docker + Git

### Year 2 — Mid-Level
- [ ] Production code with logging, tests, error handling
- [ ] Understand DB internals + async
- [ ] 60+ DSA solved
- [ ] Promoted or job-changed to mid-level

### Year 3 — Strong Mid
- [ ] Design medium systems on whiteboard
- [ ] Worked with Celery + Kafka in production
- [ ] 80+ DSA + 5 HLD problems whiteboarded
- [ ] Pass mid-level senior interviews

### Year 4 — Senior Candidate
- [ ] K8s + Terraform fluency
- [ ] Architecture decision-making skills
- [ ] 200+ DSA + 20+ HLD + 10+ LLD
- [ ] Pass senior interviews at small/mid companies
- [ ] Lead a small project

### Year 5 — Senior
- [ ] AI/LLM integration in production
- [ ] 3+ deployed AI-era projects
- [ ] 400+ DSA + 30+ HLD + 15+ LLD
- [ ] Senior offer at ₹30+ LPA / FAANG-tier
- [ ] Mentoring junior devs
- [ ] Tech blog / open-source contributions

---

## 💡 Senior Mantras

```
1. CONSISTENCY beats intensity. 1 hour daily > 10 hours Sunday.

2. BUILD don't just read. Every doc → run the code.

3. SHIP projects. Public GitHub > private LeetCode count.

4. WRITE about what you learn. Blog posts solidify understanding.

5. TEACH others. Mentoring a junior teaches you 10x.

6. MOCK INTERVIEWS, EARLY. Don't wait until you're "ready."

7. RE-PRIORITIZE quarterly based on interview feedback.

8. NETWORK matters. Tech Twitter / LinkedIn / meetups.

9. PHYSICAL HEALTH = mental performance.
   Sleep, exercise, sunlight. Non-negotiable.

10. BURN-OUT KILLS PROGRESS. Take 1 day/week off.
```

---

## 🎯 What to Drop (Common Mistakes)

```
✗ Studying LOW-priority topics before HIGH
   → Suffix automaton when you can't solve mediums

✗ Reading too many books, building nothing
   → 0 projects = 0 job offers

✗ Memorizing pattern code instead of understanding
   → Stuck on variations

✗ Avoiding system design until "ready"
   → System design IS the differentiator

✗ Procrastinating on mocks
   → Fear of failure delays growth

✗ Comparing yourself to others
   → Their year 3 ≠ your year 3

✗ Not deploying projects
   → "I built it" ≠ "It runs in production"
```

---

## 📎 Companion Files

- [PRIORITY_ANALYSIS_5YEAR_2026.md](PRIORITY_ANALYSIS_5YEAR_2026.md) — HIGH/MEDIUM/LOW priority guide
- [COMPLETE_ANALYSIS_5YEAR_2026.md](COMPLETE_ANALYSIS_5YEAR_2026.md) — coverage verification
- [GAP_ANALYSIS.md](GAP_ANALYSIS.md) — zero-gap confirmation
- This file — actionable 0-to-5-year plan

---

## 🏆 Final Pledge

```
I commit to:

   ✓ 1 hour minimum daily (even on bad days)
   ✓ 1 project shipped per quarter
   ✓ 1 mock interview per week (from Year 2)
   ✓ Update this plan quarterly based on progress
   ✓ Celebrate small wins
   ✓ Ask for help when stuck (>30 min on bug)
   ✓ Sleep 7+ hours / exercise 3x week
   ✓ Document everything I learn

By Year 5:
   ₹30+ LPA senior backend role.
   Production systems I designed.
   Junior devs I mentored.
   The career I built deliberately.
```

---

*Start date: ____________   |   Target Year 5 date: ____________*
*Updated quarterly. Last review: ____________*
