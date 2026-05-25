# Agentic AI — Complete Learning Roadmap

> **Welcome.** This is your structured path from "What is an LLM?" to "I can build production-grade autonomous agents."
>
> Estimated time: **12 weeks at 1-2 hrs/day**, or **6 weeks at 4 hrs/day**.

---

## 📚 Who This Is For

You're the right reader if:
- You're a **backend developer** (Python ideally) wanting to add AI to your toolkit.
- You've **heard of ChatGPT / Claude** but never built anything with their APIs.
- You want to understand **agents, RAG, LLMs** from first principles — not just framework wrappers.
- You want to eventually build **production AI systems**, not just demos.

You're NOT the right reader if:
- You want a quick "no-code AI tutorial" (this is engineering-deep).
- You want to train your own model from scratch (this is application-layer, not ML research).
- You want only theory (this is hands-on building focused).

---

## 🎯 What You'll Be Able to Do at the End

By the end of all 8 Levels:

✅ Explain how LLMs work (tokens, embeddings, attention) intuitively
✅ Craft effective prompts using proven patterns
✅ Build apps with OpenAI, Anthropic Claude, and multi-provider routing
✅ Make LLMs call your custom functions (tool use / function calling)
✅ Build RAG systems over your own documents
✅ Design agents that plan, reason, and act autonomously
✅ Use LangChain, LangGraph, CrewAI, DSPy, MCP appropriately
✅ Deploy AI systems to production with observability, eval, cost controls
✅ Build 5+ complete portfolio projects

---

## 🗺️ THE 8 LEVELS

```
┌─────────────────────────────────────────────────────────┐
│  Level 1   LLM Foundations            🟢 BEGINNER       │
│  Level 2   Prompt Engineering          🟢 BEGINNER       │
├─────────────────────────────────────────────────────────┤
│  Level 3   LLM APIs & SDKs            🟡 INTERMEDIATE   │
│  Level 4   Tool Use & Function Calling 🟡 INTERMEDIATE   │
│  Level 5   RAG & Vector Databases      🟡 INTERMEDIATE   │
├─────────────────────────────────────────────────────────┤
│  Level 6   Agent Patterns             🟠 ADVANCED       │
│  Level 7   Frameworks                  🟠 ADVANCED       │
├─────────────────────────────────────────────────────────┤
│  Level 8   Production LLMOps          🔴 EXPERT         │
│  Projects  Build real systems         🚀 BUILD          │
└─────────────────────────────────────────────────────────┘
```

Each level **builds on the previous**. Don't skip ahead — you'll feel lost in Level 6 if you skipped Level 4.

---

## 📅 12-WEEK SCHEDULE (1-2 hrs/day)

### Phase 1 — Foundations (Weeks 1-3)
**Goal:** Make your first AI-powered app.

| Week | Level | Focus | Outcome |
|---|---|---|---|
| 1 | Level 1 | LLM basics, set up env, first API call | "Hello World" with an LLM |
| 2 | Level 2 | Prompt engineering patterns | Personal prompt library |
| 3 | Level 3 | OpenAI, Claude, multi-provider | Multi-LLM chatbot |

### Phase 2 — Building Blocks (Weeks 4-6)
**Goal:** LLMs that can do real work.

| Week | Level | Focus | Outcome |
|---|---|---|---|
| 4 | Level 4 | Tool use, function calling | Agent that books appointments |
| 5 | Level 5 (part 1) | Embeddings, vector DBs | Search engine on your notes |
| 6 | Level 5 (part 2) | Advanced RAG, hybrid search | Document Q&A app |

### Phase 3 — Real Agents (Weeks 7-9)
**Goal:** Autonomous agents that plan and act.

| Week | Level | Focus | Outcome |
|---|---|---|---|
| 7 | Level 6 | Agent patterns (ReAct, planning) | Research agent |
| 8 | Level 7 (part 1) | LangChain + LangGraph | Multi-step workflow agent |
| 9 | Level 7 (part 2) | CrewAI, DSPy, MCP | Multi-agent team |

### Phase 4 — Production (Weeks 10-12)
**Goal:** Ship AI to real users.

| Week | Level | Focus | Outcome |
|---|---|---|---|
| 10 | Level 8 (part 1) | Observability, evaluation | LangSmith dashboard |
| 11 | Level 8 (part 2) | Cost optimization, caching, safety | Production-grade pipeline |
| 12 | Projects | Complete one full project | Portfolio piece |

---

## 🛠️ TOOLS YOU'LL NEED

### Required (free or trial)
- **Python 3.10+** (already have if you're a backend dev).
- **OpenAI API key** — free $5 trial credit; sign up at platform.openai.com.
- **Anthropic API key** — free credit; sign up at console.anthropic.com.
- **VS Code / Cursor / PyCharm** — your editor.
- **Git** — version control.

### Recommended (you'll add as you go)
- **Docker** — for running vector DBs locally (Level 5).
- **Postgres** — for `pgvector` (Level 5).
- **LangSmith account** (free) — for observability (Level 8).
- **HuggingFace account** (free) — for embeddings models.

### Cost expectation
- OpenAI/Anthropic free tiers → enough for Levels 1-5.
- For full Level 8 + projects → budget **$20-50** total over the journey. Use cheap models (`gpt-4o-mini`, `claude-3-haiku`).

---

## ✅ PRE-REQUISITES

Before starting:
- **Python**: comfortable with functions, classes, async (`asyncio`).
- **HTTP / REST APIs**: how to make API calls.
- **JSON**: read and write.
- **Command line**: install packages with `pip` / `uv`.
- **Git**: basic commits and clones.
- **Optional**: SQL basics (Level 5 helpful).

If any of these are weak, brush up first — they're foundational for AI work too.

---

## 📖 LEARNING PHILOSOPHY

### 1. Build before you read
Every level has a "build a small thing" exercise. **Don't skip.** Reading without building = no real learning.

### 2. Understand the fundamentals first
Frameworks (LangChain, LangGraph) make AI easier. But if you start with them, you don't understand what they're hiding. We do **raw API first**, then frameworks.

### 3. Cost-aware from day 1
Track your API spend. Use cheap models for learning (`gpt-4o-mini`). Save the expensive ones for production.

### 4. Real problems > toy demos
Each project addresses a real use case. Generic "chatbot tutorials" are a trap — they don't teach you anything you can't get from copy-paste blogs.

### 5. Trust the order
Level 5 RAG is hard because Level 4 tool use is built into Level 6 agents. You can't shortcut.

---

## 📊 LEVEL DETAILS

### Level 1 — LLM Foundations 🟢
**Weeks: 1**
**Folder:** `Level1_LLM_Foundations/`

**What you'll learn:**
- What an LLM actually is (intuitive, non-mathy explanation).
- Tokens and tokenization (why "strawberry has 3 R's" was hard for ChatGPT).
- Embeddings (vectors that capture meaning).
- Attention mechanism (why "the cat sat on the mat" → it knows "it" refers to "cat").
- The current landscape (GPT-4, Claude, Gemini, Llama, etc.).
- Setting up your development environment.
- Making your first API call.

**Files (planned):**
1. `01_what_is_an_llm.md` — High-level intuition.
2. `02_tokens_embeddings.md` — Why tokens matter for cost and quality.
3. `03_attention_transformers_simple.md` — How LLMs "pay attention".
4. `04_models_landscape.md` — Which model for which job.
5. `05_setting_up_dev_env.md` — Python env, keys, packages.
6. `06_your_first_llm_call.md` — Hello World with OpenAI / Claude.

**Mastery check:** You can call an LLM API, get a response, and explain what each line does.

---

### Level 2 — Prompt Engineering 🟢
**Weeks: 2**
**Folder:** `Level2_Prompt_Engineering/`

**What you'll learn:**
- Anatomy of a prompt (system, user, assistant messages).
- Few-shot prompting (examples in the prompt).
- Chain-of-thought (forcing the LLM to "think step by step").
- System prompts and personas.
- Structured outputs (Pydantic, JSON mode).
- Reusable prompt patterns.
- Anti-patterns to avoid.

**Files:**
1. `01_anatomy_of_a_prompt.md`
2. `02_few_shot_chain_of_thought.md`
3. `03_system_prompts.md`
4. `04_structured_outputs_pydantic.md`
5. `05_prompt_patterns_library.md`
6. `06_anti_patterns.md`

**Mastery check:** Given a vague task ("summarize this article"), you can write a prompt that produces consistent, structured output.

---

### Level 3 — LLM APIs & SDKs 🟡
**Weeks: 3**
**Folder:** `Level3_LLM_APIs_SDKs/`

**What you'll learn:**
- OpenAI API (chat, embeddings, audio, vision).
- Anthropic Claude API (similar but different).
- LiteLLM (use multiple providers with one API).
- Instructor (Pydantic + LLMs = type-safe responses).
- Streaming responses (real-time chat UX).
- Cost optimization (caching, picking right model).

**Files:**
1. `01_openai_api_complete.md`
2. `02_anthropic_claude_complete.md`
3. `03_litellm_multi_provider.md`
4. `04_instructor_structured.md`
5. `05_streaming_responses.md`
6. `06_cost_optimization_basics.md`

**Mastery check:** Build a chatbot that streams responses, switches providers, and returns structured JSON.

---

### Level 4 — Tool Use & Function Calling 🟡
**Weeks: 4**
**Folder:** `Level4_Tool_Use_Function_Calling/`

**What you'll learn:**
- "Tool use" — letting an LLM call Python functions you wrote.
- OpenAI function calling spec.
- Anthropic Claude tool use spec.
- Building tool libraries (web search, calculator, DB query, etc.).
- Parallel tool calls (multiple tools in one turn).
- Error handling and retry logic.

**Files:**
1. `01_tool_use_fundamentals.md`
2. `02_function_calling_openai.md`
3. `03_tool_use_claude.md`
4. `04_building_tool_libraries.md`
5. `05_parallel_tool_use.md`
6. `06_error_handling_retries.md`

**Mastery check:** Build an agent that, given "What's the weather in Mumbai and convert that temp to Fahrenheit?", calls 2 tools and gives the right answer.

---

### Level 5 — RAG & Vector Databases 🟡
**Weeks: 5-6**
**Folder:** `Level5_RAG_Vector_Databases/`

**What you'll learn:**
- What RAG (Retrieval Augmented Generation) is and why it matters.
- Embeddings deep dive (why they capture meaning).
- Chunking strategies (how to split documents).
- Vector databases compared (Pinecone, Weaviate, Qdrant, pgvector).
- Hybrid search (vector + keyword).
- Reranking for better results.
- Evaluating RAG quality.
- Advanced RAG patterns (HyDE, multi-query, parent-child).

**Files:**
1. `01_what_is_rag.md`
2. `02_embeddings_deep_dive.md`
3. `03_chunking_strategies.md`
4. `04_vector_databases_compared.md`
5. `05_hybrid_search.md`
6. `06_reranking.md`
7. `07_rag_evaluation.md`
8. `08_advanced_rag_patterns.md`

**Mastery check:** Build a Q&A bot over a PDF (or your code repo) that answers questions accurately, citing sources.

---

### Level 6 — Agent Patterns 🟠
**Weeks: 7-8**
**Folder:** `Level6_Agent_Patterns/`

**What you'll learn:**
- What an "agent" really is.
- ReAct pattern (Reason + Act loop).
- Plan-and-Execute (planner + executor split).
- Agent memory (short-term, long-term, episodic, semantic).
- Multi-step reasoning.
- Self-reflection and critique (agent reviews its own work).
- Safety and guardrails.

**Files:**
1. `01_what_is_an_agent.md`
2. `02_react_pattern.md`
3. `03_plan_and_execute.md`
4. `04_agent_memory_systems.md`
5. `05_multi_step_reasoning.md`
6. `06_self_reflection_critique.md`
7. `07_safety_guardrails.md`

**Mastery check:** Build a research agent that, given "research the top 5 Python web frameworks and rank them," autonomously plans, searches, summarizes, and ranks — without you intervening.

---

### Level 7 — Frameworks 🟠
**Weeks: 8-10**
**Folder:** `Level7_Frameworks/`

**Sub-folders:**
- `LangChain/` (5 docs) — the OG framework.
- `LangGraph/` (5 docs) — graph-based agents (the modern preferred approach).
- `CrewAI/` (4 docs) — multi-agent crews.
- `DSPy/` (4 docs) — declarative pipelines.
- `MCP/` (3 docs) — Model Context Protocol (standardized tool interface).
- `Frameworks_Compared.md` — decision matrix.

**What you'll learn:**
- When to use which framework.
- How to debug framework-built agents.
- How to migrate between frameworks.
- Production gotchas.

**Mastery check:** Build the same agent in 2 different frameworks. Compare. Pick winner with reasons.

---

### Level 8 — Production LLMOps 🔴
**Weeks: 10-12**
**Folder:** `Level8_Production_LLMOps/`

**What you'll learn:**
- Observability with LangSmith / LangFuse / Helicone.
- Evaluation: offline (test sets) and online (user feedback).
- Cost optimization at scale (model routing, caching).
- Caching strategies (Redis, semantic cache).
- Safety: prompt injection, jailbreaks, output filtering.
- Deployment and inference (latency targets).
- Fine-tuning: when and how (and when NOT to).
- GraphRAG (knowledge graph + RAG hybrid).

**Files:**
1. `01_observability_langsmith_langfuse.md`
2. `02_evaluation_offline_online.md`
3. `03_cost_optimization_advanced.md`
4. `04_caching_strategies.md`
5. `05_safety_guardrails_production.md`
6. `06_deployment_inference.md`
7. `07_finetuning_when_how.md`
8. `08_graphrag_advanced.md`

**Mastery check:** Deploy an AI agent with proper observability, evaluation suite, cost monitoring, and safety guardrails.

---

### Projects 🚀
**Weeks: 12+**
**Folder:** `Projects/`

**5 projects to choose from:**
1. **Personal AI Assistant** (LangChain + tools) — Multi-tool assistant for calendar, email, web.
2. **RAG Document Q&A** — Upload PDFs, ask questions, get cited answers.
3. **Multi-Agent Code Review** (CrewAI) — Multiple agents review your PRs.
4. **AI Agent with MCP** — Production-grade agent using MCP tools.
5. **Production RAG SaaS** — End-to-end RAG product with multi-tenancy.

**Goal:** Build ONE complete project as portfolio piece.

---

## 📖 HOW EACH LEVEL DOC IS STRUCTURED

Each `.md` file follows a consistent format:

```
1. What & Why                 — Conceptual intro
2. Mental Model               — Diagram or analogy
3. The Code Pattern           — Skeleton (you fill in)
4. Real Example               — Working scenario
5. Common Gotchas             — Pitfalls
6. Mastery Check              — How to verify you understood
7. Going Deeper               — Links + further reading
8. Connect to Next Level      — How this feeds into next topic
```

---

## 💡 STUDY TIPS

### Morning routine
- Read 1 doc (30 min).
- Build the example yourself (30 min).
- Write 3 sentences in your own words: "Today I learned..."

### Weekly review
- Sunday evening: re-skim the week's docs.
- Note 3 things still confusing.
- Address them next Monday.

### Repo practice
- Create a `learning-agentic-ai/` git repo.
- One subfolder per level with your code.
- Commit daily — even small progress.
- 12 weeks of commits = strong GitHub presence.

### When stuck
1. Re-read previous level.
2. Try the simplest version first.
3. Read official docs (linked at end of each level doc).
4. Search "[topic] tutorial" on official YouTube channels (3Blue1Brown for math, Anthropic / OpenAI for APIs).

---

## 🔄 EXISTING REFERENCE MATERIAL

Each Level folder has `_existing_*` subfolders containing your **previous** AI notes that I moved here as reference. They're SHALLOW (1-2 docs each) — use them as supplementary, but the new numbered docs (`01_*.md`, `02_*.md`...) are the actual curriculum.

```
Level1_LLM_Foundations/
├── 01_what_is_an_llm.md          ← NEW (read this)
├── 02_tokens_embeddings.md       ← NEW
├── ...
└── _existing_ref/                ← OLD reference notes (skim, don't depend on)
```

---

## 🚀 NEXT STEPS

After this roadmap:

1. **Today**: Set up your dev environment (`Level1_LLM_Foundations/05_setting_up_dev_env.md` when ready).
2. **Tomorrow**: Read `Level1_LLM_Foundations/01_what_is_an_llm.md` — start the journey.
3. **End of Week 1**: You should have made your first LLM API call.
4. **End of Week 4**: Your first agent (LLM + tool use).
5. **End of Week 12**: Production-grade AI system deployed.

---

## 📈 PROGRESS TRACKING

Track your own progress here (or in a separate `MY_PROGRESS.md`):

```
[ ] Level 1 — LLM Foundations              (6 docs)
[ ] Level 2 — Prompt Engineering           (6 docs)
[ ] Level 3 — LLM APIs & SDKs              (6 docs)
[ ] Level 4 — Tool Use & Function Calling  (6 docs)
[ ] Level 5 — RAG & Vector Databases       (8 docs)
[ ] Level 6 — Agent Patterns               (7 docs)
[ ] Level 7 — Frameworks                   (21 docs across 5 frameworks)
[ ] Level 8 — Production LLMOps            (8 docs)
[ ] Project — Pick one and build           (1 project)
```

Total: **~70 learning docs + 1 project = portfolio + skills + interviews**.

---

## ❓ FAQ

**Q: Do I need to know Machine Learning / Deep Learning first?**
A: No. This is **application-layer AI**. We use LLMs as a black box (mostly). Deep ML is helpful but not required.

**Q: Will I be able to "train my own ChatGPT"?**
A: No. That requires $100M+ in GPU compute. You'll **use** pre-trained models, fine-tune them for specific tasks (Level 8), and build agents on top.

**Q: How much will the APIs cost me?**
A: $20-50 over 12 weeks if you use cheap models (`gpt-4o-mini`, `claude-3-haiku`). Free tiers cover Levels 1-5.

**Q: Should I learn LangChain first or learn the raw API?**
A: **Raw API first.** Then frameworks. Otherwise you don't understand what frameworks abstract away. This roadmap forces that order.

**Q: Which framework should I bet on long-term?**
A: **LangGraph** for production agents (modern, graph-based). LangChain for quick prototypes. CrewAI for explicit multi-agent. DSPy for "compile" prompts. MCP for standardized tools.

**Q: What about open-source models (Llama, Mistral)?**
A: Same patterns apply. You'll use them in Level 8 (deployment + fine-tuning).

**Q: How do I know I've actually learned, not just read?**
A: **Build the mastery check** at the end of each level. If you can't build it, you didn't learn it.

---

## 🎯 FINAL WORD

The AI field moves fast. New models, frameworks, papers every week. **Don't try to keep up with everything.** Master the fundamentals here, and you'll be able to evaluate any new tool/framework in 30 minutes (vs needing to learn it from scratch).

**Agent engineering = the new full-stack development.** Backend dev + LLM + agents = the most in-demand profile of 2025-2027.

You're starting at the right time.

Let's go. → Start with `Level1_LLM_Foundations/01_what_is_an_llm.md`.
