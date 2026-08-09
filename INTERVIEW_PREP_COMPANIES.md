# 🎯 COMPANY-WISE INTERVIEW PREP

> Per-company **filter layer**: "kaunsa topic kis company ke liye zaroori hai."
> Roz ka kaam [`ROADMAP.md`](ROADMAP.md) me hai · har application [`JOB_TRACKER.md`](JOB_TRACKER.md) me likho.
>
> **Niyam:** interview ho jaye to usi din outcome yahan likho. Dead deadline ko URGENT dikhte rehna sabse bada confusion hai.

---

## 🔴 ABHI LIVE

| | GenAI Developer (Azure) |
|---|---|
| Interview | **2026-08-11** 🔴 (3 din) |
| Stack | **Azure OpenAI + Azure AI Search** + Python backend · Cosmos DB named |
| Prep doc | [`05_genai_developer_azure_role_prep.md`](Agentic_AI/Interview_Prep/05_genai_developer_azure_role_prep.md) — JD→repo gap map + day-wise plan |
| Repo coverage | ✅ [Azure OpenAI](Agentic_AI/Level3_LLM_APIs_SDKs/11_azure_openai.md) · ✅ [Azure AI Search](Agentic_AI/Level5_RAG_Vector_Databases/11_azure_ai_search.md) · ✅ [Cosmos DB](Backend_Developer/01_Year3-4_Mid/10_MongoDB/theory/10_cosmos_db_azure.md) |
| Baaki gap | Cosmos DB **hands-on** nahi hai — honest pivot bolna ("MongoDB deep hai, Cosmos ka Mongo API + RU/partition-key model padha hai") |

**Ab priority yahi hai.** Teen din: Azure OpenAI practical chalao → AI Search hybrid+semantic ranker → Cosmos RU/partition-key + consistency levels.

---

## ✅ CLOSED

| | Infosys | Deloitte |
|---|---|---|
| Role | Python Django Developer | T&T \| Python Developer (Consultant) |
| Job ID | INFSYS-EXTERNAL-248140 | 106165 |
| Window | 1 Jul – 5 Jul 2026 — **closed** | Never scheduled |
| Status | ⬜ **Outcome record karo** (gaya tha ya nahi?) → [JOB_TRACKER](JOB_TRACKER.md) | 💤 Dormant — koi movement nahi |

> Neeche in dono ki topic-priority tables **reference ke liye** rakhi hain — Django/PostgreSQL aur GenAI/RAG ki prep
> kisi bhi similar JD pe dobara kaam aayegi. Dates ignore karo, mapping useful hai.

---

## 📦 (Closed) INFOSYS — Python Django Developer

> Window 5 Jul 2026 ko band ho gaya. Neeche ka topic-map **Django + PostgreSQL** wale kisi bhi JD ke liye reference hai.

**Must-have filter:** Strong Python + Django + PostgreSQL. Baaki (Rust/Angular/React) sirf good-to-have — skip karo, time nahi hai.

### Priority order (jo pehle karna hai)

| Rank | Topic | Kahan practice karo | Kyun |
|---|---|---|---|
| 1 🔴 | **Django ORM deep dive** | [`01_orm_deep_dive.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/01_orm_deep_dive.md) + [`33_queryset_internals.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/33_queryset_internals.md) + [`09_advanced_orm_subquery.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/09_advanced_orm_subquery.md) | ORM = Django interview ka #1 filter |
| 2 🔴 | **N+1 queries + select_related/prefetch_related** | [`15_n_plus_one_detection.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/15_n_plus_one_detection.md) | Almost guaranteed question |
| 3 🔴 | **PostgreSQL fundamentals** — indexing, transactions, isolation levels | [`01_postgresql_advanced.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/01_postgresql_advanced.md), [`20_advanced_indexing.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/20_advanced_indexing.md), [`21_isolation_levels_anomalies.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md) | "Must have" line mein explicitly likha hai |
| 4 🔴 | **Django migrations (incl. zero-downtime)** | [`25_zero_downtime_migrations.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/25_zero_downtime_migrations.md), [`23_django_migrations_production.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/23_django_migrations_production.md) | Production Django ka core skill |
| 5 🔴 | **DRF — serializers, viewsets, permissions** | [`02_viewsets_serializers_auth.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/02_viewsets_serializers_auth.md), [`22_object_level_permissions.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/22_object_level_permissions.md) | REST API layer |
| 6 🔴 | **Transactions + F-expressions + atomic updates** | [`34_transactions_deep.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/34_transactions_deep.md), [`36_f_expressions_atomic_updates.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/36_f_expressions_atomic_updates.md) | Race conditions = common scenario Q |
| 7 🟡 | **Middleware + signals** | [`03_django_channels_middleware.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/03_django_channels_middleware.md), [`41_django_middleware_signals_testing_gaps.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/41_django_middleware_signals_testing_gaps.md) | Django internals question |
| 8 🟡 | **Security hardening** | [`16_security_hardening.md`](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/16_security_hardening.md) | Consultant role — client-facing trust |
| 9 🟡 | **General Python + DSA warm-up** | [`03_Interview_AnyYear/02_Interview_Prep`](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep) — [`07_python_tricky_questions.md`](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/07_python_tricky_questions.md), [`08_sql_interview_questions.md`](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/08_sql_interview_questions.md) | AI interview generic filter round |
| 10 ⚪ | Rust / Angular / React | — skip | Good-to-have, deadline mein waste mat karo |

### AI-interview specific tips (Glider.ai, recorded)
- Laptop/desktop + Chrome + wired mic — pehle se test kar lena (link diya gaya hai email mein)
- Har answer **structured bolo**: pehle concept ek line mein, phir example, phir gotcha/edge-case
- Django ORM ya PostgreSQL question aaye toh apna real experience (SAP HANA / Niroskos) se tie karo agar relevant ho
- 60 min hai — pacing rakho, ek hi topic pe atka mat raho

**Target: 3-5 Jul ke beech ye poori list ek baar revise karo, phir interview window mein kabhi bhi de do.**

---

## 📦 (Dormant) DELOITTE — T&T Python Developer / AI Solutions

> Kabhi schedule nahi hui. Neeche ka topic-map **GenAI/RAG-heavy** JD ke liye reference hai.

**Must-have filter:** Python backend (FastAPI/Flask/Django) + OOP/SOLID/design patterns + NumPy/Pandas/SQL + **GenAI exposure** (RAG, embeddings, vector DBs, LLM workflows).

### Priority order

| Rank | Topic | Kahan practice karo | Kyun |
|---|---|---|---|
| 1 🔴 | **RAG pipelines + embeddings + vector DBs** | [`Level5_RAG_Vector_Databases`](Agentic_AI/Level5_RAG_Vector_Databases/) + [`06_pgvector_schema_design.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/06_pgvector_schema_design.md), [`18_pgvector_ai_workloads.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/18_pgvector_ai_workloads.md), [`28_vector_databases_comparison.md`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/28_vector_databases_comparison.md) | JD ka differentiator ask, explicitly likha hai |
| 2 🔴 | **LLM integration workflows / API serving for models** | [`Level3_LLM_APIs_SDKs`](Agentic_AI/Level3_LLM_APIs_SDKs/), [`08_FastAPI_OpenAI_RAG_Backend_starter`](Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter) | "APIs for AI/ML model serving" — responsibility #4 |
| 3 🔴 | **FastAPI backend + REST APIs + microservices** | [`Day44_FastAPI`](Backend_Developer/00_Year0-2_Junior/02_Python_Daily/Day44_FastAPI), [`02_API_Design`](Backend_Developer/01_Year3-4_Mid/02_API_Design), [`05_Microservices`](Backend_Developer/01_Year3-4_Mid/05_Microservices) | Core responsibility #1 |
| 4 🔴 | **OOP + SOLID + design patterns** | [`15_Design_Patterns_SOLID`](Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID/) (Section 10 = Interview Drills) | Explicitly required qualification |
| 5 🔴 | **NumPy / Pandas / SQL for data processing** | [`04_Database_SQL`](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/) practical folder | Required qualification, ETL work |
| 6 🟡 | **ETL / data pipelines** | check `04_Database_SQL/practical` + `Level5_RAG` chunking/loading scripts | Responsibility #5 |
| 7 🟡 | **Agent patterns (multi-agent, tool use)** | [`Level6_Agent_Patterns`](Agentic_AI/Level6_Agent_Patterns/), [`Level4_Tool_Use_Function_Calling`](Agentic_AI/Level4_Tool_Use_Function_Calling/) | GenAI depth signal, not core ask but strengthens fit |
| 8 🟡 | **Docker + Git + CI/CD** | [`04_DevOps`](Backend_Developer/01_Year3-4_Mid/04_DevOps/) | Required qualification |
| 9 🟡 | **Observability (structured logging, monitoring, tracing)** | Udemy_EdDonner_ProductionTrack Week folders (`Agentic_AI/my-agentic-ai-project/`) | Preferred, matches responsibility #10 |
| 10 ⚪ | AWS/Azure cloud AI services (SageMaker/Bedrock/Azure OpenAI) | — read up conceptually, hands-on not critical | Preferred qualification only |
| 11 ⚪ | LangChain / FAISS / ChromaDB familiarity | [`project2_rag_document_qa_starter`](Agentic_AI/Projects/project2_rag_document_qa_starter), [`project3_multiagent_code_review_starter`](Agentic_AI/Projects/project3_multiagent_code_review_starter) | Preferred, already have starters — polish one |
| 12 ⚪ | Rust | — skip unless time left | "Strong plus" only, not required |

### Prep angle
- Deloitte GenAI-heavy hai — **1-page project story** ready rakho: RAG document Q&A ya multi-agent code review starter (dono already scaffolded in `Agentic_AI/Projects/`) — "maine ye banaya, ye architecture, ye trade-off" bolke explain karne layak.
- System-design angle: agar system design round aaye, "Design a RAG system for enterprise" type question expect karo — [`JULY_SPRINT.md`](JULY_SPRINT.md) Week 3 mein already covered hai.

---

## 🗓️ THIS WEEK — dono ko kaise fit karein (2 - 5 Jul)

| Day | Priority Slot | Kya |
|---|---|---|
| Thu 2 Jul (aaj) | Infosys 🔴 | Django ORM + N+1 + PostgreSQL indexing/isolation — rank 1-3 |
| Fri 3 Jul | Infosys 🔴 | Migrations + DRF serializers/permissions — rank 4-5 |
| Sat 4 Jul | Infosys 🔴 → Deloitte 🟡 | Transactions + middleware/signals (morning) → RAG/vector DB refresh (evening) |
| Sun 5 Jul | Infosys 🔴 FINAL + interview de do | Security + Python tricky Qs revise → AI interview complete karo before 11:50 PM |
| Mon 6 Jul onwards | Deloitte 🟡 | Rank 1-9 ko JULY_SPRINT ke Week 2 (RAG/System Design) ke saath merge karke chalao |

---

> **Yaad rakh:** Infosys deadline-bound hai, pehle wahi. Deloitte ke liye jaldi nahi — sprint ke saath organically chalta rahega. Content dono jagah already repos mein hai, bas targeted revision chahiye.
