# 🎯 Combined Priority Analysis — Python Backend + Agentic AI

> **Every topic across both curricula, mapped to HIGH / MEDIUM / LOW** for "Python Backend + Agentic AI" senior roles in 2026.

**Total scope:** 679 markdown docs across Backend_Developer + Agentic_AI
**Target role:** Senior Python Backend Engineer with Agentic AI specialization
**Compensation target:** ₹35-60 LPA (India) / $130-200K (international)

---

## 🚦 Priority Definitions

```
🔴 HIGH PRIORITY ─── "Drilled cold. Every senior Backend+AI interview tests this."
   ✓ Comes up in 70%+ of senior interviews
   ✓ Foundational — other concepts build on it
   ✓ Daily production use

🟡 MEDIUM PRIORITY ─ "Strong working knowledge. Common at staff/senior+."
   ✓ Comes up in 30-60% of senior interviews
   ✓ Differentiator in some teams
   ✓ Learn AFTER mastering HIGH

🟢 LOW PRIORITY ─── "Aware of it. Niche or emerging."
   ✓ < 15% of interviews
   ✓ Specialized roles / bleeding edge
   ✓ Optional unless targeting that niche
```

---

## 📊 Combined Coverage Map (Volume)

```
🔴 HIGH       ████████████░░░░░░░░  ~40%   (~272 docs)
🟡 MEDIUM     ████████████░░░░░░░░  ~40%   (~272 docs)
🟢 LOW        ██████░░░░░░░░░░░░░░  ~20%   (~135 docs)

Backend_Developer focus: production reliability
Agentic_AI focus:        AI-specific depth
Combined:                full-stack AI backend engineer
```

---

# 🔴 HIGH PRIORITY — Master Cold (Backend + AI)

> Every senior Backend+AI interview tests these. Drill until automatic.

## H1. Python Core + Async (Foundation)

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| Python core (OOP, decorators, generators) | [Phase1_Python_Daily](Backend_Developer/Phase1_Python_Daily/) | (used throughout) |
| Asyncio fundamentals + advanced | [Day31](Backend_Developer/Phase1_Python_Daily/Day31_Asyncio_Advanced/) | (LLM async calls) |
| Type hints + Pydantic v2 | [Day29, Day47](Backend_Developer/Phase1_Python_Daily/) | (LLM structured output) |
| GIL + threading | [Phase1_Python_Advanced/theory/03](Backend_Developer/Phase1_Python_Advanced/theory/03_memory_gil.md) | — |
| Testing (pytest) | [Day41 + Phase2_Testing](Backend_Developer/Phase2_Testing/) | — |

**Why HIGH:** Without this you can't write async LLM endpoints or production code.

---

## H2. FastAPI + Backend Framework

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| FastAPI routing + DI | [Phase2_FastAPI/01-05](Backend_Developer/Phase2_FastAPI/) | — |
| Async + SQLAlchemy | [Phase2_FastAPI/04, 09](Backend_Developer/Phase2_FastAPI/) | — |
| Auth (JWT + OAuth2) | [Phase2_FastAPI/06, 19](Backend_Developer/Phase2_FastAPI/) | — |
| Streaming (SSE) | [Phase2_FastAPI/26](Backend_Developer/Phase2_FastAPI/26_sse_deep.md) | (LLM token streaming) |
| LLM Integration in FastAPI | [Phase2_FastAPI/31](Backend_Developer/Phase2_FastAPI/31_llm_integration_fastapi.md) | (Level 3 SDK basics) |
| Function calling endpoints | [Phase2_FastAPI/32](Backend_Developer/Phase2_FastAPI/32_function_calling_endpoints.md) | [Level4/](Agentic_AI/Level4_Tool_Use_Function_Calling/) |

**Why HIGH:** FastAPI dominates Python AI backends in 2026.

---

## H3. Databases (Relational + Vector)

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| PostgreSQL deep + pgvector | [Phase2_Database/01-26](Backend_Developer/Phase2_Database/) | [Level5/_existing_vector_dbs](Agentic_AI/Level5_RAG_Vector_Databases/_existing_vector_dbs/) |
| Vector DBs comparison | [Phase2_Database/28](Backend_Developer/Phase2_Database/28_vector_databases_comparison.md) | [Level5/](Agentic_AI/Level5_RAG_Vector_Databases/) |
| Indexing + query optimization | [Phase2_Database/20](Backend_Developer/Phase2_Database/20_advanced_indexing.md) | — |
| Transactions + isolation | [Phase2_Database/19, 21](Backend_Developer/Phase2_Database/) | — |
| Sharding + HA | [Phase2_Database/07, 08](Backend_Developer/Phase2_Database/) | — |
| Migrations (Alembic) | [Phase2_Database/22, 24](Backend_Developer/Phase2_Database/) | — |

**Why HIGH:** Vector DBs are the new SQL for AI apps.

---

## H4. Caching + Queues

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| Redis + patterns | [Phase2_Redis/](Backend_Developer/Phase2_Redis/) | (cache for LLM) |
| Cache patterns | [Phase2_Caching/01-07](Backend_Developer/Phase2_Caching/theory/) | — |
| **Semantic caching for LLMs** | [Phase2_Caching/06](Backend_Developer/Phase2_Caching/theory/06_semantic_caching_llm.md) | (cost optimization) |
| Celery / RabbitMQ / Kafka | [Phase2_*/](Backend_Developer/) | (agent task queues) |
| Temporal durable workflows | [Phase3_Microservices/15](Backend_Developer/Phase3_Microservices/15_temporal_durable_workflows.md) | (agent orchestration) |

**Why HIGH:** Semantic caching saves 50%+ on LLM costs.

---

## H5. RAG (End-to-End)

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| RAG backend architecture | [Phase2_FastAPI/34](Backend_Developer/Phase2_FastAPI/34_rag_backend_architecture.md) | [Level5/_existing_rag](Agentic_AI/Level5_RAG_Vector_Databases/_existing_rag/) |
| **Chunking strategies** | (caching layer) | [Level5/04](Agentic_AI/Level5_RAG_Vector_Databases/04_chunking_strategies.md) |
| **Hybrid search (BM25 + Vector)** | (Elasticsearch + pgvector) | [Level5/06](Agentic_AI/Level5_RAG_Vector_Databases/06_hybrid_search.md) |
| **Reranking** | (production patterns) | [Level5/07](Agentic_AI/Level5_RAG_Vector_Databases/07_reranking.md) |
| **RAGAS evaluation** | (testing layer) | [Level5/09](Agentic_AI/Level5_RAG_Vector_Databases/09_ragas_evaluation.md) |
| Design RAG System HLD | [Design_RAG_System.md](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/Design_RAG_System.md) | — |

**Why HIGH:** RAG is the #1 production AI pattern in 2026.

---

## H6. Agent Patterns + Orchestration

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| **ReAct from scratch** | (orchestration) | [Level6/04](Agentic_AI/Level6_Agent_Patterns/04_react_pattern.md) |
| **Multi-Agent Supervisor** | (microservices coord) | [Level6/07](Agentic_AI/Level6_Agent_Patterns/07_multi_agent_supervisor.md) |
| Plan & Execute | — | [Level6/05](Agentic_AI/Level6_Agent_Patterns/05_plan_and_execute.md) |
| **Agent Evaluation** | (testing) | [Level6/10](Agentic_AI/Level6_Agent_Patterns/10_agent_evaluation.md) |
| Function calling | [Phase2_FastAPI/32](Backend_Developer/Phase2_FastAPI/32_function_calling_endpoints.md) | [Level4/](Agentic_AI/Level4_Tool_Use_Function_Calling/) |
| Temporal for agents | [Phase3_Microservices/15](Backend_Developer/Phase3_Microservices/15_temporal_durable_workflows.md) | [Level7](Agentic_AI/Level7_Frameworks/) |
| Design Agent Orchestration HLD | [Design_Agent_Orchestration.md](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/Design_Agent_Orchestration.md) | — |

**Why HIGH:** Agent design is what separates senior AI engineers.

---

## H7. Production LLMOps + Observability

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| OpenTelemetry tracing | [Phase2_FastAPI/14](Backend_Developer/Phase2_FastAPI/14_opentelemetry_distributed_tracing.md) | (LLM trace integration) |
| **LangSmith / Langfuse Observability** | (infrastructure) | [Level8/08](Agentic_AI/Level8_Production_LLMOps/08_observability.md) |
| **Guardrails & Safety** | [Phase2_FastAPI/33](Backend_Developer/Phase2_FastAPI/33_prompt_injection_security.md) | [Level8/09](Agentic_AI/Level8_Production_LLMOps/09_guardrails.md) |
| **Cost tracking + optimization** | [Phase2_Caching/06](Backend_Developer/Phase2_Caching/theory/06_semantic_caching_llm.md) | [Level3/10](Agentic_AI/Level3_LLM_APIs_SDKs/10_cost_optimization.md) |
| **Error handling & retries (LLM)** | [Phase2_FastAPI/22](Backend_Developer/Phase2_FastAPI/22_hmac_webhooks_idempotency.md) | [Level3/07](Agentic_AI/Level3_LLM_APIs_SDKs/07_error_handling_retries.md) |
| Prometheus + Grafana | [Phase3_DevOps/05](Backend_Developer/Phase3_DevOps/05_prometheus_grafana.md) | — |

**Why HIGH:** Production AI = observability + guardrails. Asked in every senior interview.

---

## H8. Security (LLM + Backend)

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| OWASP API Top 10 | [Phase3_Security/02](Backend_Developer/Phase3_Security/02_owasp_brute_force_csrf.md), [Phase2_FastAPI/20](Backend_Developer/Phase2_FastAPI/20_owasp_api_top10.md) | — |
| **Prompt injection security** | [Phase2_FastAPI/33](Backend_Developer/Phase2_FastAPI/33_prompt_injection_security.md) | [Level8/09](Agentic_AI/Level8_Production_LLMOps/09_guardrails.md) |
| OAuth2 deep flows | [Phase3_Security/04](Backend_Developer/Phase3_Security/04_oauth2_flows_deep.md) | — |
| Zero-trust + mTLS | [Phase3_Security/10](Backend_Developer/Phase3_Security/10_zero_trust_microservices.md) | — |
| Secrets management | [Phase3_Security/08](Backend_Developer/Phase3_Security/08_secrets_management_advanced.md) | (API key rotation) |
| Passkeys / WebAuthn | [Phase3_Security/18](Backend_Developer/Phase3_Security/18_passkeys_webauthn.md) | — |

**Why HIGH:** LLM apps are new attack surface. Senior interviewers love this.

---

## H9. DevOps + Deployment

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| Docker + Compose | [Phase3_DevOps/01](Backend_Developer/Phase3_DevOps/01_docker.md) | — |
| Kubernetes + Helm | [Phase3_DevOps/06](Backend_Developer/Phase3_DevOps/06_kubernetes_helm.md) | (LLM deployment) |
| CI/CD (GitHub Actions) | [Phase3_DevOps/03](Backend_Developer/Phase3_DevOps/03_github_actions_cicd.md) | — |
| SRE practices SLI/SLO | [Phase3_DevOps/16](Backend_Developer/Phase3_DevOps/16_sre_practices_sli_slo.md) | — |
| Feature flags | [Phase3_DevOps/18](Backend_Developer/Phase3_DevOps/18_feature_flags_experimentation.md) | (LLM A/B testing) |
| Terraform | [Phase3_DevOps/07](Backend_Developer/Phase3_DevOps/07_terraform.md) | — |

**Why HIGH:** Senior = ships to production.

---

## H10. System Design (HLD Core + AI-Era)

| Problem | Backend_Developer | Why HIGH |
|---|---|---|
| URL Shortener | [HLD_Problems/](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/) | Universal warm-up |
| Rate Limiter | HLD_Problems | 60%+ of interviews |
| Notification Service | HLD_Problems | Common |
| Distributed Cache | HLD_Problems | Senior level |
| Twitter / News Feed | HLD_Problems | FAANG favorite |
| **ChatGPT-style backend** | [Design_ChatGPT_Backend.md](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/Design_ChatGPT_Backend.md) | 2026 hot Q |
| **RAG System** | [Design_RAG_System.md](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/Design_RAG_System.md) | 2026 hot Q |
| **Agent Orchestration** | [Design_Agent_Orchestration.md](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/Design_Agent_Orchestration.md) | 2026 hot Q |
| Real-time Chat | HLD_Problems | Common |
| Payment System | HLD_Problems | Senior |
| WebSocket scaling | [Phase2_FastAPI/15](Backend_Developer/Phase2_FastAPI/15_websocket_scaling.md) | Real-time AI |

**Why HIGH:** System design IS the differentiator at senior level.

---

## H11. LLM Foundations + Prompt Engineering

| Topic | Agentic_AI |
|---|---|
| Transformer architecture | [Level1/Deep_Architecture/](Agentic_AI/Level1_LLM_Foundations/Deep_Architecture/) |
| Attention mechanism | [Level1](Agentic_AI/Level1_LLM_Foundations/) |
| Tokenization | [Level1](Agentic_AI/Level1_LLM_Foundations/) |
| Context window | [Level1](Agentic_AI/Level1_LLM_Foundations/) |
| Sampling (temp, top-p) | [Level1](Agentic_AI/Level1_LLM_Foundations/) |
| Prompt engineering patterns | [Level2/](Agentic_AI/Level2_Prompt_Engineering/) (10 docs) |
| Chain-of-thought | [Level2](Agentic_AI/Level2_Prompt_Engineering/) |
| Few-shot, zero-shot | [Level2](Agentic_AI/Level2_Prompt_Engineering/) |

**Why HIGH:** First questions in every AI interview.

---

## H12. LLM APIs + SDKs (Production)

| Topic | Backend_Developer | Agentic_AI |
|---|---|---|
| OpenAI SDK patterns | [Phase2_FastAPI/31](Backend_Developer/Phase2_FastAPI/31_llm_integration_fastapi.md) | [Level3/_existing_openai](Agentic_AI/Level3_LLM_APIs_SDKs/_existing_openai/) |
| Anthropic Claude SDK | [Phase2_FastAPI/31](Backend_Developer/Phase2_FastAPI/31_llm_integration_fastapi.md) | [Level3/_existing_claude](Agentic_AI/Level3_LLM_APIs_SDKs/_existing_claude/) |
| LiteLLM (multi-provider) | — | [Level3/_existing_litellm](Agentic_AI/Level3_LLM_APIs_SDKs/_existing_litellm/) |
| Instructor (structured output) | — | [Level3/_existing_instructor](Agentic_AI/Level3_LLM_APIs_SDKs/_existing_instructor/) |
| Error handling + retries | [Phase2_FastAPI/22](Backend_Developer/Phase2_FastAPI/22_hmac_webhooks_idempotency.md) | [Level3/07](Agentic_AI/Level3_LLM_APIs_SDKs/07_error_handling_retries.md) |

**Why HIGH:** Daily work for AI backend.

---

## H13. DSA Core (Interview Patterns)

[Phase8_DSA/](Backend_Developer/Phase8_DSA/) — 13 HIGH categories:

```
✓ 01_Arrays_Hashing          ✓ 08_Sorting_Algorithms
✓ 02_Strings                  ✓ 09_Trees
✓ 03_Linked_List              ✓ 10_Heaps_Priority_Queue
✓ 04_Stack_Queue              ✓ 11_Graphs_BFS_DFS
✓ 05_Binary_Search            ✓ 12_Dynamic_Programming
✓ 06_Two_Pointers_Sliding     ✓ 13_Greedy
✓ 07_Recursion_Backtracking
```

**Why HIGH:** 90% of coding interviews stay in these 13 categories.

---

## H14. Interview Prep

| Topic | Coverage |
|---|---|
| Backend system design 50Q | [Phase8_Interview_Prep/01](Backend_Developer/Phase8_Interview_Prep/01_backend_system_design_50q.md) |
| Coding round patterns | [Phase8_Interview_Prep/02](Backend_Developer/Phase8_Interview_Prep/02_backend_coding_round_patterns.md) |
| Python tricky | [Phase8_Interview_Prep/07](Backend_Developer/Phase8_Interview_Prep/07_python_tricky_questions.md) |
| SQL Q&A | [Phase8_Interview_Prep/04](Backend_Developer/Phase8_Interview_Prep/04_sql_interview_questions.md) |
| Behavioral | [Phase8_Interview_Prep/10](Backend_Developer/Phase8_Interview_Prep/10_behavioral_backend.md) |
| Negotiation | [Phase8_Interview_Prep/12](Backend_Developer/Phase8_Interview_Prep/12_negotiation_offer.md) |
| AI system design | [Agentic_AI/Interview_Prep/01](Agentic_AI/Interview_Prep/01_system_design_ai_questions.md) |
| AI coding patterns | [Agentic_AI/Interview_Prep/02](Agentic_AI/Interview_Prep/02_coding_patterns.md) |
| AI behavioral | [Agentic_AI/Interview_Prep/03](Agentic_AI/Interview_Prep/03_behavioral_questions.md) |
| AI technical concepts | [Agentic_AI/Interview_Prep/04](Agentic_AI/Interview_Prep/04_key_technical_concepts.md) |

**Why HIGH:** Prep is the actual job-getting work.

---

# 🟡 MEDIUM PRIORITY — Strong Working Knowledge

## M1. Advanced Backend

```
✓ Microservices patterns           [Phase3_Microservices/]
✓ Saga + Outbox                    [Phase3_Microservices/04, 05]
✓ Service Mesh (Istio)             [Phase3_Microservices/06]
✓ DDD                              [Phase3_Microservices/09]
✓ gRPC                             [Phase3_gRPC/]
✓ GraphQL                          [Phase2_GraphQL/]
✓ Event sourcing + CQRS            [Phase3_Microservices/05]
✓ Multi-region                     [Phase3_DevOps/15]
✓ Chaos engineering                [Phase3_DevOps/14]
✓ Software Architecture course     [Software_Architecture_Patterns/]
```

## M2. AI Frameworks (Beyond Basics)

```
✓ LangChain deep                   [Agentic_AI/Level7/_existing_LangChain]
✓ LangGraph                        [Agentic_AI/Level7/_existing_LangGraph]
✓ CrewAI                           [Agentic_AI/Level7/_existing_CrewAI]
✓ DSPy                             [Agentic_AI/Level7/_existing_DSPy]
✓ MCP                              [Agentic_AI/Level7/_existing_MCP]
✓ Web search tools                 [Agentic_AI/Level4/_existing_web_search]
```

## M3. Modern AI Topics

```
✓ Voice agents                     [Agentic_AI/Modern_Topics/01]
                                   [Backend/Phase2_FastAPI/37]
✓ Computer use / browser           [Agentic_AI/Modern_Topics/02]
✓ Local LLM serving                [Agentic_AI/Modern_Topics/03]
                                   [Backend/Phase2_FastAPI/36]
✓ Memory frameworks (Mem0, Zep)    [Agentic_AI/Modern_Topics/04]
✓ Multimodal agents                [Agentic_AI/Modern_Topics/05]
```

## M4. Advanced Testing

```
✓ Contract testing (Pact)          [Backend/Phase2_Testing/]
✓ Property-based (Hypothesis)      [Backend/Phase2_Testing/]
✓ Load testing (Locust/k6)         [Backend/Phase2_Testing/]
✓ Mutation testing                 [Backend/Phase2_Testing/]
✓ RAGAS for AI                     [Agentic_AI/Level5/09]
```

## M5. Advanced AI Topics (Filled but MEDIUM)

```
✓ Plan & Execute                   [Agentic_AI/Level6/05]
✓ Agent Evaluation                 [Agentic_AI/Level6/10]
✓ Hybrid Search                    [Agentic_AI/Level5/06]
✓ Reranking                        [Agentic_AI/Level5/07]
✓ Chunking                         [Agentic_AI/Level5/04]
✓ RAGAS                            [Agentic_AI/Level5/09]
```

## M6. Advanced HLD Problems

[Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/](Backend_Developer/PythonBackend_SystemDesign/HLD_Problems/) — pick 10-15 to drill:

```
✓ Uber / Ride sharing              ✓ Multi-Tenant SaaS
✓ Netflix / Video streaming         ✓ API Gateway design
✓ Instagram / Photo feed            ✓ Dropbox / File storage
✓ Slack / Real-time chat            ✓ Google Docs / Collaborative
✓ Tinder / Matching                 ✓ BookMyShow
✓ Airbnb                            ✓ Web crawler
✓ Google Maps                       ✓ Distributed logging
```

## M7. DSA Advanced

[Phase8_DSA/](Backend_Developer/Phase8_DSA/) — 9 MEDIUM categories:

```
✓ 14_Trie                          ✓ 19_Math_Number_Theory
✓ 15_Advanced_Graphs               ✓ 20_Matrix_Grid
✓ 16_Bit_Manipulation              ✓ 21_String_DP
✓ 17_Intervals                     ✓ 22_Monotonic_Queue
✓ 18_Segment_Tree_Fenwick          ✓ 24_Concurrency_Threading
```

---

# 🟢 LOW PRIORITY — Aware Of

## L1. Niche Backend

```
✗ Phase0_Foundations (already known with 4.3 yrs exp)
✗ Phase1_Python_Daily Day 1-30 (basics)
✗ Suffix structures / advanced DSA  [Phase8_DSA/26-28]
✗ HIPAA / SOC 2                     (US-specific compliance)
✗ WebAssembly backend                (bleeding edge)
✗ Distributed consensus deep         (Raft/Paxos algorithms)
```

## L2. Niche AI

```
✗ Embedding fine-tuning              (researcher domain)
✗ Pre-training internals             (unless ML role)
✗ LlamaIndex                         (LangChain enough)
✗ Pydantic AI                        (new + uncommon)
✗ AutoGen / OpenAI Swarm             (LangGraph wins)
✗ Streaming UI patterns              (frontend, not backend)
✗ Synthetic data generation          (specialized)
```

## L3. Niche Patterns

```
✗ UI Architecture (MVC/MVP/MVVM)     [Architecture/Section_08]
✗ Software Architecture Section 9-10
✗ Game backend / matchmaking
✗ Web3 / Crypto backend
```

---

# 🎯 Recommended Drill Order (60-Day Plan)

For 4.3-year experienced targeting Backend+AI senior in 2 months:

## Week 1-2: Self-Audit + AI Gap Fill

```
Day 1-2:   Self-assessment, mark HIGH/MEDIUM/LOW by personal rust level
Day 3-4:   Resume + Portfolio polish
Day 5-7:   AI HIGH gaps: LLM integration + Function calling + RAG basics
Day 8-10:  AI HIGH gaps: Agent patterns + MCP + Observability
```

## Week 3-4: DSA + AI Skills

```
Day 11-17:  DSA 13 HIGH categories rotation + AI Level1-3 review
Day 18-25:  DSA harder problems + AI Level4-6 review
```

## Week 5-6: System Design Intensive (BOTH STACKS)

```
Day 26-32:  Classic HLD (URL Shortener, Twitter, Uber, Chat, etc.)
Day 33-40:  AI HLD (ChatGPT, RAG, Agent) + LLD problems
```

## Week 7-8: Mock + Behavioral + Apply

```
Day 41-50:  9+ mocks (Backend, AI, hybrid)
Day 51-60:  Active interviews + negotiations
```

→ See [COMBINED_STUDY_PLAN_2_MONTHS.md](COMBINED_STUDY_PLAN_2_MONTHS.md) for daily breakdown.

---

# 🎯 What to Tell Hiring Managers

```
"I'm not just a backend engineer who can call OpenAI.
I'm not just an AI engineer who can't deploy.

I'm the integration: production AI backends.
I build RAG systems that scale, agent orchestrators
that survive crashes, LLM endpoints with observability
and guardrails — all on stacks I've shipped to prod
for 4+ years (FastAPI, PostgreSQL, Kubernetes).

The Backend AND the AI side — both production-grade."
```

---

# 📊 Final Cheat Sheet

```
🔴 HIGH (drill cold — 80% of interview focus):
   ✓ Python async + Pydantic
   ✓ FastAPI + LLM integration
   ✓ PostgreSQL + pgvector + Vector DBs
   ✓ Redis + semantic caching
   ✓ RAG end-to-end (chunk, hybrid, rerank, RAGAS)
   ✓ Agent patterns (ReAct, multi-agent)
   ✓ Production LLMOps (observability, guardrails, cost)
   ✓ Security (OWASP + prompt injection)
   ✓ K8s + SRE
   ✓ HLD (15 classic + 3 AI-era)
   ✓ DSA (13 core categories)
   ✓ Interview prep (system design, coding, behavioral)

🟡 MEDIUM (depth bonus — 15% of interview):
   ✓ Microservices + Saga + DDD
   ✓ LangGraph + CrewAI + MCP
   ✓ Voice + Computer Use + Multimodal
   ✓ Advanced testing
   ✓ Advanced HLD (Uber, Netflix, etc.)
   ✓ DSA advanced (Trie, Graphs, DP)

🟢 LOW (skip unless specifically targeted):
   ✗ Phase 0 Foundations (you know it)
   ✗ Python basics
   ✗ Niche DSA
   ✗ Niche AI (fine-tuning, etc.)
   ✗ HIPAA, SOC 2, Web3
```

---

## 📎 Companion Files

- [BACKEND_AI_BRIDGE.md](BACKEND_AI_BRIDGE.md) — how Backend and AI connect
- [COMBINED_GAP_ANALYSIS.md](COMBINED_GAP_ANALYSIS.md) — zero-gap verification
- [COMBINED_STUDY_PLAN_2_MONTHS.md](COMBINED_STUDY_PLAN_2_MONTHS.md) — 60-day prep
- [Backend_Developer/PRIORITY_ANALYSIS_5YEAR_2026.md](Backend_Developer/PRIORITY_ANALYSIS_5YEAR_2026.md) — backend-only deep
- [Agentic_AI/](Agentic_AI/) — AI curriculum

---

*Updated: 2026-05-27. Re-prioritize quarterly based on interview signals.*
