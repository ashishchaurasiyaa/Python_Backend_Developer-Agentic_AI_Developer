# GenAI Developer Interview Prep — Azure/OpenAI role, Interview: Tue 2026-08-11

Target role: GenAI Developer, 4+ yrs, BE/BTech. JD emphasis: Azure OpenAI + OpenAI/Gemini/Claude,
LangChain/LlamaIndex/Semantic Kernel, RAG + vector DBs, prompt engineering, MLOps/CI-CD for AI,
responsible AI/governance. Certs listed as *preferred*, not mandatory — don't panic about AI-900/AI-102,
you won't get them in 5 days and nobody expects you to for a live req closing this fast.

**Bottom line: this JD is 80% things already in this repo.** Same pattern as your backend job search —
presentation, not capability. Two real gaps below, everything else is recall + framing practice.

---

## 1. JD → Repo coverage map

| JD ask | Where you already have it | Status |
|---|---|---|
| OpenAI API | [`Level3_LLM_APIs_SDKs/01_openai_api_complete.md`](../Level3_LLM_APIs_SDKs/01_openai_api_complete.md) | ✅ strong |
| Claude / Gemini | [`02_claude_api_complete.md`](../Level3_LLM_APIs_SDKs/02_claude_api_complete.md), `03_ai_apis.md`, `04_litellm_complete.md` (multi-provider abstraction) | ✅ strong |
| **Azure OpenAI specifically** | ✅ **Ab covered** — [Level3/11_azure_openai.md](../Level3_LLM_APIs_SDKs/11_azure_openai.md) + [practical](../Level3_LLM_APIs_SDKs/11_azure_openai_practical.py) (deployments vs models, Entra ID, quota/TPM, PTU, content filters) | 🟢 padho + practical chalao (§4 cheat sheet = quick recall) |
| Prompt engineering | `Level2_Prompt_Engineering/` (full folder) | ✅ strong |
| RAG architecture | `Level5_RAG_Vector_Databases/01_rag_complete.md`, `02_rag_advanced.md`, `08_query_transformation.md`, `10_contextual_retrieval.md` | ✅ strong |
| Vector DBs: Pinecone/Chroma/Weaviate/FAISS/Azure AI Search | Deep on **pgvector + Qdrant** (`03_vector_databases.md`) + ✅ **Azure AI Search ab covered** — [Level5/11_azure_ai_search.md](../Level5_RAG_Vector_Databases/11_azure_ai_search.md) + [practical](../Level5_RAG_Vector_Databases/11_azure_ai_search_practical.py) (hybrid RRF, semantic ranker, integrated vectorization) | 🟢 Azure AI Search padho; baaki pe concept-transfer framing (§5 Q6) |
| Chunking / embeddings / hybrid search / reranking | `04_chunking_strategies.md`, `05_embedding_models.md`, `06_hybrid_search.md`, `07_reranking.md` | ✅ strong |
| RAG evaluation | `09_ragas_evaluation.md` | ✅ strong |
| LangChain | `Level7_Frameworks/01_langchain_complete.md` | ✅ strong |
| LlamaIndex | `07_llamaindex.md` | ✅ covered |
| **Semantic Kernel** | `09_semantic_kernel.md` (295 lines, no practical run yet) | 🟡 read but never executed — run it once |
| Agent patterns / LangGraph / CrewAI | `Level6_Agent_Patterns/`, `02_langgraph_complete.md`, `05_crewai_complete.md` | ✅ strong |
| MCP | `04_mcp_complete.md` | ✅ strong (rare for most candidates — mention it) |
| MLOps / CI-CD for AI / model lifecycle | `Level8_Production_LLMOps/01_production_ai.md`, `02_llmops_production.md`, `03_ai_testing.md` | ✅ strong |
| Observability / monitoring | `08_observability.md` + real OTel/Prometheus/Grafana labs in `my-agentic-ai-project/Udemy_EdDonner_ProductionTrack/Week4` | ✅ strong, has real lab |
| Guardrails / responsible AI / governance | `09_guardrails.md` | ✅ covered |
| Cost optimization | `10_cost_optimization.md` (Level3), `10_cost_optimization_advanced.md` (Level8) | ✅ strong |
| REST APIs / microservices / cloud-native | Backend_Developer repo (your actual production experience) | ✅ real experience |
| ML/NLP fundamentals | `Level1_LLM_Foundations/Classical_ML_DL_Foundations/11_*`, `12_*` | ✅ covered |
| Cloud: Azure/AWS/GCP | `my-agentic-ai-project/Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/` (real Azure/GCP/AWS deploy labs) | ✅ real lab, not just theory |
| SQL Server / PostgreSQL / **Cosmos DB** | Postgres = real (production). Cosmos DB = ✅ **theory ab covered** — [10_cosmos_db_azure.md](../../Backend_Developer/01_Year3-4_Mid/10_MongoDB/theory/10_cosmos_db_azure.md) (RU/s, partition keys, 5 consistency levels, Mongo-API gotchas) — **hands-on nahi** | 🟡 **honest pivot bolo, claim mat karo** — see §4 |
| Git / DevOps / Agile | Daily practice | ✅ real |

**Status update (2026-08-08):** teeno content gaps ab repo me bhar diye gaye hain — Azure OpenAI, Azure AI Search, Cosmos DB.
Ab yeh **padhne + chalane** ka kaam hai, likhne ka nahi.

**Tuesday se pehle 3 cheezein (priority order):**
1. **Azure OpenAI practical chalao** (30 min) — [`11_azure_openai_practical.py`](../Level3_LLM_APIs_SDKs/11_azure_openai_practical.py). Client syntax haath se likho.
2. **Azure AI Search practical chalao** (45 min) — [`11_azure_ai_search_practical.py`](../Level5_RAG_Vector_Databases/11_azure_ai_search_practical.py). Bina key ke bhi chalta hai (mock mode) — hybrid RRF score aur semantic reranking apni aankh se dekho.
3. **Cosmos DB ka honest pivot rehearse karo** (20 min) — RU/s + partition key + consistency levels bol ke samjha do; "used in production" mat bolo.

Semantic Kernel ka koi runnable practical repo me **nahi** hai — sirf theory doc hai ([Level7/09_semantic_kernel.md](../Level7_Frameworks/09_semantic_kernel.md)). Agar SK JD me strongly aata hai to 20 min me uska Kernel + plugin + planner mental model padh lo, aur interview me honest raho: "padha hai, production me use nahi kiya." Baaki sab rehearsal hai, learning nahi.

---

## 2. 5-Day Plan (today Thu Aug 6 → Tue Aug 11 morning)

Budget: ~2 hrs/weekday evening, ~3-4 hrs each weekend day. This is recall + articulation practice, not new study — don't over-read, prioritize saying answers out loud.

**Thu Aug 6 (tonight, ~1 hr)**
- Skim this file once fully so you know the map.
- Read `Level7_Frameworks/09_semantic_kernel.md` end to end (no practical exists — just read + note 3 talking points: what it is, how it differs from LangChain, when you'd pick it in an MS-shop).
- Do §4 Azure OpenAI cheat sheet below — run it once against a real key if you have one, otherwise just read the diff cold.

**Fri Aug 7 (~2 hrs) — RAG deep dive**
- Re-run `Level5_RAG_Vector_Databases/01_rag_complete_practical.py` and `02_rag_advanced_practical.py`.
- Rehearse out loud: "walk me through how you'd design a RAG system for [enterprise knowledge repo]" — use `02_rag_advanced.md` + `10_contextual_retrieval.md` as your answer skeleton.
- Read `09_ragas_evaluation.md` — RAG *evaluation* is a favorite interviewer follow-up ("how do you know your RAG isn't hallucinating").

**Sat Aug 8 (~3 hrs) — Frameworks + vector DB honesty pass**
- LangChain vs LangGraph vs LlamaIndex vs Semantic Kernel vs CrewAI: write yourself a 1-line differentiator for each (you'll get "which would you pick and why" style questions).
- Vector DB honesty pass: prep the pgvector/Qdrant-deep, others-conceptual answer (§5 Q6) so it sounds confident, not evasive.
- Run `Level4_Tool_Use_Function_Calling/02_openai_function_calling_practical.py` — tool/function calling is core to "AI workflow" questions.

**Sun Aug 9 (~3-4 hrs) — Production/MLOps + system design**
- `Level8_Production_LLMOps`: 01, 02, 03, 08 (observability), 09 (guardrails), 10 (cost).
- `Interview_Prep/01_system_design_ai_questions.md` — do at least 2 questions as full whiteboard-style answers (RAG system, multi-tenant AI SaaS).
- Skim `Interview_Prep/04_key_technical_concepts.md`.

**Mon Aug 10 (~2 hrs) — Behavioral + mock + resume**
- `Interview_Prep/03_behavioral_questions.md` — pick 4 STAR stories, practice saying them out loud (not reading).
- Mock interview: ask me to run one live in chat (technical + behavioral mix, timed).
- 20 min: check your resume/LinkedIn against §1 table — anything you list as a skill, make sure you can defend it if probed.

**Tue Aug 11 (morning)**
- No new material. Re-read this file's §1 table once, re-say your 4 STAR stories out loud, sleep-adjacent light review only. Confidence > cramming at this point.

---

## 3. Likely interview questions (JD-specific)

**Q1. "How would you design a RAG pipeline for an enterprise knowledge base?"**
Answer skeleton: ingestion (chunking strategy — `04_chunking_strategies.md`) → embedding model choice
(`05_embedding_models.md`) → vector store (pgvector for cost/simplicity vs Pinecone/Azure AI Search for
managed scale — name the tradeoff) → hybrid search (dense + BM25, `06_hybrid_search.md`) → reranking
(`07_reranking.md`) → generation with citations → evaluation via RAGAS (`09_ragas_evaluation.md`).
Always mention **evaluation and guardrails** — juniors forget this, seniors lead with it.

**Q2. "Azure OpenAI vs OpenAI directly — what changes in your code?"**
See §4. Key point to say: endpoint/deployment-name based routing instead of model name, API version pinning,
Azure AD/managed-identity auth option instead of just API keys, data residency/compliance being the actual
business reason enterprises pick Azure OpenAI over vanilla OpenAI.

**Q3. "LangChain vs LlamaIndex vs Semantic Kernel — when would you pick which?"**
- LangChain: general-purpose orchestration, huge integration ecosystem, agent patterns.
- LlamaIndex: RAG-first, strongest at data connectors + indexing strategies.
- Semantic Kernel: Microsoft-native (C#/.NET shops, Azure-first orgs) — natural fit if the client stack is
  already MS/Azure, which is *literally this JD*. Say this explicitly — it signals you read the room.

**Q4. "How do you improve a RAG system that's hallucinating / giving irrelevant answers?"**
Diagnose first: retrieval problem or generation problem? Check retrieved chunks relevance (retrieval
metrics from RAGAS) before touching the prompt. Then: better chunking, reranking, query transformation
(`08_query_transformation.md`), grounding instructions in the system prompt, guardrails to refuse when
retrieval confidence is low rather than let the model guess.

**Q5. "How do you evaluate and monitor an LLM application in production?"**
RAGAS/eval harness pre-deploy, then production: latency, cost/token, groundedness sampling, user feedback
loop, drift detection, OTel tracing per-request (you have a *real* lab for this — Week4 observability —
cite it, don't just cite the doc).

**Q6. "You've listed pgvector/Qdrant but not Pinecone/Weaviate — are you familiar with those?"**
Honest framing (don't dodge): "I've built production-depth with pgvector and Qdrant — schema design,
distance metrics, filtered + hybrid search. Pinecone/Weaviate/Azure AI Search follow the same conceptual
model — client init, index/collection creation, upsert, similarity query with metadata filters — so the
ramp is syntax, not concepts. I'd be productive in days, not weeks." This is *true* and sounds senior,
not evasive.

**Q7. "Walk me through prompt engineering techniques you use to improve accuracy."**
Few-shot, chain-of-thought, structured output (JSON mode / `Level3_LLM_APIs_SDKs/08_instructor_library.md`),
system prompt role framing, self-consistency, and — important for an enterprise JD — **prompt injection
defense** (mention `09_guardrails.md`).

**Q8. "How would you fine-tune vs RAG vs prompt-engineer — how do you decide?"**
Prompt engineering first (cheapest, fastest iteration) → RAG when you need up-to-date/proprietary knowledge
the model wasn't trained on → fine-tuning only for style/format consistency or domain jargon at scale, and
only after the first two are exhausted (cost/complexity tradeoff — this is the answer that signals
seniority, most candidates jump straight to "fine-tune it").

**Q9. "How do you handle responsible AI / governance in an enterprise GenAI app?"**
PII redaction before sending to the LLM, content filtering (Azure has built-in content safety), audit
logging of prompts/responses, human-in-the-loop for high-stakes outputs, rate limiting/cost guardrails per
tenant. Tie to `09_guardrails.md`.

**Q10. "Describe a CI/CD pipeline for an AI application — what's different from normal software CI/CD?"**
Same base (lint/test/build/deploy) plus: prompt regression testing (does a prompt change break eval
scores?), eval-gate before merge (RAGAS score threshold), model/prompt versioning, canary rollout for
prompt changes since they're behaviorally risky like any other code change. `03_ai_testing.md` +
`02_llmops_production.md` are your source material.

---

## 4. Azure OpenAI cheat sheet (the actual gap)

Conceptually it's the same OpenAI SDK, different client + auth:

```python
# Vanilla OpenAI
from openai import OpenAI
client = OpenAI(api_key="...")
resp = client.chat.completions.create(model="gpt-4o", messages=[...])

# Azure OpenAI — same .chat.completions.create() call, different setup:
from openai import AzureOpenAI
client = AzureOpenAI(
    api_key="...",                              # or azure_ad_token_provider for managed identity
    azure_endpoint="https://<resource>.openai.azure.com/",
    api_version="2024-08-01-preview",            # Azure requires explicit API version pinning
)
resp = client.chat.completions.create(
    model="<deployment-name>",                   # NOT the model name — your Azure *deployment* name
    messages=[...],
)
```

Talking points to say out loud in the interview (you don't need to have run this in prod to say these —
they're true and demonstrate you understand *why* enterprises choose Azure OpenAI, not just *that* they do):
- Deployment-name routing (you deploy a model instance in Azure, then call it by your own deployment name).
- `api_version` is mandatory and matters (breaking changes are versioned).
- Auth can be Azure AD / managed identity, not just static API keys — matters for enterprise security review.
- Data stays in your Azure tenant/region — the actual compliance reason vs calling OpenAI directly.
- Content filtering is built-in at the Azure resource level (ties to Q9 above).

**Cosmos DB (true gap, be honest if asked):** "I've worked deeply with PostgreSQL in production; I haven't
used Cosmos DB hands-on, but I understand it's Azure's multi-model NoSQL (SQL/Mongo/Cassandra/Gremlin APIs)
with global distribution and tunable consistency — I'd expect the ramp to be fast given my Postgres and
MongoDB background." Don't claim hands-on. This exact honesty pattern is what worked in your resume audit.

---

## 5. Night-before checklist (Mon Aug 10 night)
- [ ] 4 STAR stories rehearsed out loud, not just read
- [ ] Can explain the Azure OpenAI client diff without looking at §4
- [ ] Can say the pgvector/Qdrant-honesty line (Q6) fluently, no hesitation
- [ ] Resume/LinkedIn checked against §1 table — nothing claimed you can't defend
- [ ] Know 2-3 questions to ask *them* (team size, which vector DB/framework they've standardized on, how they evaluate RAG in prod)
- [ ] Sleep > extra revision after 10 PM
