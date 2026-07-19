# 🚀 SHIP PLAN — RAG-as-a-Service Backend

> **Yeh mera daily tracker hai.** Roz yahin aa, ek `- [ ]` utha, khatam hote hi `- [x]` kar de.
> Spec (full detail): [../08_FastAPI_OpenAI_RAG_Backend.md](../08_FastAPI_OpenAI_RAG_Backend.md) · Starter: [README.md](README.md)
>
> **Kyun yeh project:** GenAI (RAG/LLM) + backend depth (multi-tenant, auth, scaling) ek hi jagah = mera target role (GenAI Engineer + Backend-with-AI) ka perfect showcase. Yeh "padha→kiya" gap band karta hai — ship karna hai, feature-complete banana nahi.

---

## ⚠️ EK HI NIYAM
> **Day 3 pe DEPLOY karo, Week 4 pe nahi.** Pehle khaali skeleton live URL pe daalo, phir har feature incrementally ship karo. Deployment ka darr end me nahi rehna chahiye. "Continuously deployed" = strong interview signal.

Time budget: ~10–12 hrs/week (evenings + weekend). Realistic ship: **4 weeks**.

---

## 🎯 Scope Discipline — MVP pehle, stretch baad me

**✅ MVP (yeh 100% ship karo):**
- [ ] FastAPI + Postgres + pgvector
- [ ] JWT auth + 2-tenant isolation
- [ ] PDF/MD upload → chunk → embed
- [ ] Hybrid search (pgvector + BM25) + Cohere rerank
- [ ] `/query` + `/query/stream` (SSE) + citations
- [ ] Semantic cache + per-tenant cost counter
- [ ] RAGAS eval (20 Q&A) + p95 latency
- [ ] Dockerfile + live deploy + README + demo video

**❌ DEFER (stretch — sirf jab MVP live ho):**
- ❌ Kafka (Celery/`BackgroundTasks` kaafi) · ❌ Full Stripe billing · ❌ DOCX/HTML/URL scraping · ❌ K8s/Helm/Terraform · ❌ Web UI (Swagger `/docs` kaafi) · ❌ Re-ingestion · ❌ Langfuse/Prometheus dashboards · ❌ Multi-region / 1M-doc scale (bas *bolna* aata ho)

> **Anti-scope-creep rule:** koi bhi ❌ item tab tak mat chhuo jab tak saare ✅ MVP `- [x]` na ho jaayein.

---

## 📅 Week 1 — Skeleton LIVE + Ingestion

- [x] **D1** Starter refactored into `app/` package (config, db, routers, retrieval); `docker-compose.yml` (pgvector+redis) + `init-db.sql` (`CREATE EXTENSION vector`); `Makefile`
- [x] **D1** `pydantic-settings` config (`app/config.py`) + `.env.example`; secrets gitignored. Skeleton **boot-verified** — `/health`, `/health/ready`, `/documents`, `/query`, `/query/stream` all 200/SSE ✅
- [ ] **D2** SQLAlchemy async models: `tenants`, `users`, `documents`, `chunks` (pgvector column) + Alembic migration
- [ ] **D2** JWT auth (`/auth/login`, `get_current_tenant` dependency), `/health`
- [ ] 🎯 **D3 — DEPLOY skeleton** to Fly.io/Render (Postgres+Redis add-on). **Live `/health` = Checkpoint 1**
- [ ] **D4** `/documents/upload` (PDF + MD only), MIME/size validation, raw file store (local disk ya S3)
- [ ] **D5** Token-aware chunking (tiktoken, ~500 tok + overlap)
- [ ] **D6** OpenAI embeddings (batch) → pgvector store, HNSW index
- [ ] ✅ **Demoable:** doc upload → DB me embedded chunks (live URL)

---

## 📅 Week 2 — Retrieval + Query (dil ka core)

- [ ] **D1** Vector search: pgvector cosine top-k
- [ ] **D2** Keyword search: Postgres `tsvector` BM25
- [ ] **D3** RRF merge (vector + keyword) → Cohere rerank top-20 → top-5
- [ ] **D4** `/query`: retrieve → LLM (Claude/OpenAI) → grounded answer **with citations** (chunk → source mapping)
- [ ] **D5** Prompt template: context injection + "answer only from context, cite sources"
- [ ] **D6** `/query/stream`: SSE token-by-token (`async for token in stream.text_stream: yield`)
- [ ] 🎯 ✅ **Demoable — Checkpoint 2:** apne doc pe question → cited streaming answer (live). **Yahaan tak = project already resume-worthy.**

---

## 📅 Week 3 — Production Hardening (backend edge yahin chamakta hai)

- [ ] **D1** Multi-tenant isolation: Postgres Row-Level Security *ya* `tenant_id` filter har query me
- [ ] **D2** 2 test tenants banao + **cross-tenant leak test** (tenant A, tenant B ka doc na dekh paaye)
- [ ] **D3** Semantic cache: query embed → `semantic_cache` table cosine (threshold 0.97) → cached answer
- [ ] **D3** Per-tenant cost counter: `Redis HINCRBYFLOAT usage:tenant:{id}:{date} cost` + pre-call check
- [ ] **D4** Rate limiting (per API key) + API key management
- [ ] **D5** Structured logging (request id, tenant id, latency, tokens, cost) + global error handler
- [ ] **D6** Dockerfile finalize, redeploy, smoke test on live
- [ ] ✅ **Demoable:** 2 tenants isolated, cache-hit latency, cost tracked per tenant

---

## 📅 Week 4 — Eval + Polish + Presentation

- [ ] **D1** RAGAS eval script: 20 Q&A goldset
- [ ] **D2** Metrics README me: `context_precision`, `faithfulness`, `answer_relevancy` (rare + strong AI signal)
- [ ] **D3** Load test (k6/locust), p95 latency note karo (target < 2s)
- [ ] **D4** README: architecture diagram + screenshots + "how to run" + design decisions
- [ ] **D5** 2-min demo video (Loom) + 3 resume bullets (spec §12 template)
- [ ] **D6** Final deploy, GitHub public, LinkedIn post

---

## 🏁 Definition of Done (mera "kiya" proof)

- [ ] Live URL — koi bhi doc upload karke query kar sake
- [ ] Public GitHub repo — clean README + architecture diagram
- [ ] RAGAS numbers + p95 latency README me
- [ ] 2-min demo video (Loom)
- [ ] 3 resume bullets likhe + LinkedIn pe post

---

## 🛠️ Stack (spec se trimmed — ship speed ke liye)

`FastAPI` · `PostgreSQL + pgvector` · `Redis` · `OpenAI/Claude` · `Cohere rerank` · `tiktoken` · `Docker` · deploy: **Fly.io/Render** (AWS EC2+compose bhi chalega, par pehli baar Fly/Render fast).

**Deploy note:** K8s/Terraform abhi NAHI — woh interview me *bolne* ke liye hai, is project me nahi. Ek command deploy (`fly deploy`) > perfect infra.

---

## 🧭 Confusion / atak gaya to

1. **Deploy pehle, feature baad me** — agar ek din bhi live URL toota, use pehle theek karo.
2. **Ek time pe ek `- [ ]`** — MVP list order me.
3. **Stuck > 2 din ek feature pe?** → us feature ko ❌ defer me daal, aage badho. Shipping > completeness.
4. **80% rule:** Week 2 checkpoint (cited streaming answer live) = 80% resume value. Baaki polish hai.

> Related: harden-one-SaaS lab plan ka context repo memory me hai · spec full detail → [../08_FastAPI_OpenAI_RAG_Backend.md](../08_FastAPI_OpenAI_RAG_Backend.md)
