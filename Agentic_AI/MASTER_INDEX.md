# 📚 MASTER INDEX — Agentic AI Complete Learning Directory

> **Tumhari complete navigation map.** Yahaan se start karo — har level, har topic, theory + practical sab listed hai with status.

**Last updated:** 2026-05-25
**Curriculum source:** [AGENTIC_AI_CURRICULUM.md](AGENTIC_AI_CURRICULUM.md) (full topic spec)
**Roadmap:** [00_LEARNING_ROADMAP.md](00_LEARNING_ROADMAP.md) (week-by-week plan)

---

## 🗺️ Status Legend

- ✅ **DONE** — Theory + practical dono complete
- 🟡 **PARTIAL** — Some content there, more needed
- ⬜ **TODO** — Empty / not yet created
- 📦 **EXISTING_REF** — Old content in `_existing_*` folder (reference only, may need consolidation)

---

## 📂 Directory Structure Overview

```
Agentic_AI/
├── MASTER_INDEX.md              ← Tum yahaan ho
├── 00_LEARNING_ROADMAP.md       ✅ Week-by-week plan
├── AGENTIC_AI_CURRICULUM.md     ✅ Full topic spec (110+ docs planned)
│
├── Level1_LLM_Foundations/      🟢 BASIC — Week 1
├── Level2_Prompt_Engineering/   🟢 BASIC — Week 2
├── Level3_LLM_APIs_SDKs/        🟡 INTERMEDIATE — Week 3
├── Level4_Tool_Use_Function_Calling/  🟡 INTERMEDIATE — Week 4
├── Level5_RAG_Vector_Databases/ 🟡 INTERMEDIATE — Week 5-6
├── Level6_Agent_Patterns/       🟠 ADVANCED — Week 7-8
├── Level7_Frameworks/           🟠 ADVANCED — Week 8-10
├── Level8_Production_LLMOps/    🔴 EXPERT — Week 10-12
├── Projects/                    🚀 BUILD — 4 capstone specs
└── Interview_Prep/              🎯 POLISH — Final week
```

**Per-level pattern:**
```
LevelN_Topic/
├── 01_subtopic_a.md             ← Theory (long, detailed Hinglish notes)
├── 01_subtopic_a_practical.py   ← Working code
├── 02_subtopic_b.md
├── 02_subtopic_b_practical.py
└── _existing_ref/               ← Older content (reference)
```

---

## 🟢 LEVEL 1 — LLM FOUNDATIONS (Week 1, ~7 hours) — ✅ COMPLETE

**Goal:** Build intuition for what LLMs are, how they work, the model landscape.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 1.1 | What is an LLM? | [✅ 01_what_is_an_llm.md](Level1_LLM_Foundations/01_what_is_an_llm.md) | (concepts) |
| 1.2 | Tokens & Embeddings | [✅ 02_tokens_embeddings.md](Level1_LLM_Foundations/02_tokens_embeddings.md) | tiktoken playground |
| 1.3 | History of LLMs | [✅ 03_history_of_llms.md](Level1_LLM_Foundations/03_history_of_llms.md) | (reading only) |
| 1.4 | Attention & Transformers | [✅ 04_attention_transformers.md](Level1_LLM_Foundations/04_attention_transformers.md) | (intuition only) |
| 1.5 | Models Landscape | [✅ 05_models_landscape.md](Level1_LLM_Foundations/05_models_landscape.md) | (reference) |
| 1.6 | Dev Environment Setup | [✅ 06_dev_environment_setup.md](Level1_LLM_Foundations/06_dev_environment_setup.md) | (setup guide) |
| 1.7 | First API Calls | [✅ 07_first_api_calls.md](Level1_LLM_Foundations/07_first_api_calls.md) | [✅ practical.py](Level1_LLM_Foundations/07_first_api_calls_practical.py) |
| 🔬 | **Deep Architecture (Internal Working)** | [✅ Deep_Architecture/README.md](Level1_LLM_Foundations/Deep_Architecture/README.md) | [✅ visualize_internals.py](Level1_LLM_Foundations/Deep_Architecture/10_visualize_internals_practical.py) |
| — | 📦 Existing reference | [_existing_ref/](Level1_LLM_Foundations/_existing_ref/) | — |

### 🔬 Deep Architecture Sub-Series (Internal Working — How a Prompt Travels Through the System)

| # | Topic | Doc |
|---|---|---|
| 0 | Complete Journey (master overview) | [00](Level1_LLM_Foundations/Deep_Architecture/00_complete_journey.md) |
| 1 | Request Flow (Network → Server → GPU) | [01](Level1_LLM_Foundations/Deep_Architecture/01_request_flow.md) |
| 2 | Tokenization (BPE, vocab, multilingual) | [02](Level1_LLM_Foundations/Deep_Architecture/02_tokenization_deep.md) |
| 3 | Embeddings + Position (RoPE) | [03](Level1_LLM_Foundations/Deep_Architecture/03_embeddings_and_position.md) |
| 4 | Attention (Q/K/V math) ⭐ | [04](Level1_LLM_Foundations/Deep_Architecture/04_attention_complete.md) |
| 5 | Transformer Block (FFN, LayerNorm, Residuals) | [05](Level1_LLM_Foundations/Deep_Architecture/05_transformer_block.md) |
| 6 | Layer Stacking + Output Projection | [06](Level1_LLM_Foundations/Deep_Architecture/06_layer_stacking_and_output.md) |
| 7 | Sampling (Temperature, Top-P, Top-K) | [07](Level1_LLM_Foundations/Deep_Architecture/07_sampling_and_generation.md) |
| 8 | Inference Optimizations (KV cache, Flash Attn) | [08](Level1_LLM_Foundations/Deep_Architecture/08_inference_optimizations.md) |
| 9 | Training (Pre-train + RLHF) | [09](Level1_LLM_Foundations/Deep_Architecture/09_training_briefly.md) |
| 10 | **Visualize Internals — Hands-On Code** | [10](Level1_LLM_Foundations/Deep_Architecture/10_visualize_internals_practical.py) |

**Mastery check:** OpenAI + Claude API call. Token counting. Explain hallucination.

---

## 🟢 LEVEL 2 — PROMPT ENGINEERING (Week 2, ~10 hours) — ✅ COMPLETE

**Goal:** Craft prompts that produce reliable, consistent, production-grade outputs.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 2.1 | Anatomy of a Prompt | [✅ 01_anatomy_of_prompt.md](Level2_Prompt_Engineering/01_anatomy_of_prompt.md) | [✅ practical.py](Level2_Prompt_Engineering/01_anatomy_of_prompt_practical.py) |
| 2.2 | Zero-Shot Prompting | [✅ 02_zero_shot.md](Level2_Prompt_Engineering/02_zero_shot.md) | [✅ practical.py](Level2_Prompt_Engineering/02_zero_shot_practical.py) |
| 2.3 | Few-Shot Prompting | [✅ 03_few_shot.md](Level2_Prompt_Engineering/03_few_shot.md) | [✅ practical.py](Level2_Prompt_Engineering/03_few_shot_practical.py) |
| 2.4 | Chain-of-Thought (CoT) | [✅ 04_chain_of_thought.md](Level2_Prompt_Engineering/04_chain_of_thought.md) | [✅ practical.py](Level2_Prompt_Engineering/04_chain_of_thought_practical.py) |
| 2.5 | Advanced Reasoning | [✅ 05_advanced_reasoning.md](Level2_Prompt_Engineering/05_advanced_reasoning.md) | [✅ practical.py](Level2_Prompt_Engineering/05_advanced_reasoning_practical.py) |
| 2.6 | System Prompts Deep | [✅ 06_system_prompts.md](Level2_Prompt_Engineering/06_system_prompts.md) | [✅ practical.py](Level2_Prompt_Engineering/06_system_prompts_practical.py) |
| 2.7 | Structured Outputs | [✅ 07_structured_outputs.md](Level2_Prompt_Engineering/07_structured_outputs.md) | [✅ practical.py](Level2_Prompt_Engineering/07_structured_outputs_practical.py) |
| 2.8 | Prompt Templates | [✅ 08_prompt_templates.md](Level2_Prompt_Engineering/08_prompt_templates.md) | [✅ practical.py](Level2_Prompt_Engineering/08_prompt_templates_practical.py) |
| 2.9 | Prompt Cookbook | [✅ 09_prompt_cookbook.md](Level2_Prompt_Engineering/09_prompt_cookbook.md) | [✅ practical.py](Level2_Prompt_Engineering/09_prompt_cookbook_practical.py) |
| 2.10 | Anti-Patterns | [✅ 10_anti_patterns.md](Level2_Prompt_Engineering/10_anti_patterns.md) | [✅ practical.py](Level2_Prompt_Engineering/10_anti_patterns_practical.py) |

**Mastery check:** Vague task → reliable JSON output, every single time.

---

## 🟡 LEVEL 3 — LLM APIs & SDKs (Week 3, ~10 hours)

**Goal:** Master the APIs you'll use daily.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 3.1 | OpenAI API Complete | 📦 [_existing_openai](Level3_LLM_APIs_SDKs/_existing_openai/01_openai_api_complete.md) | 📦 [practical](Level3_LLM_APIs_SDKs/_existing_openai/practical/01_openai_practical.py) |
| 3.2 | Anthropic Claude API | 📦 [_existing_claude](Level3_LLM_APIs_SDKs/_existing_claude/01_claude_api_complete.md) | 📦 [practical](Level3_LLM_APIs_SDKs/_existing_claude/practical/01_claude_practical.py) |
| 3.3 | Google Gemini API | 📦 [_existing_ai_apis](Level3_LLM_APIs_SDKs/_existing_ai_apis/01_ai_apis.md) | 📦 [practical](Level3_LLM_APIs_SDKs/_existing_ai_apis/practical/01_ai_apis_practical.py) |
| 3.4 | LiteLLM Multi-Provider | 📦 [_existing_litellm](Level3_LLM_APIs_SDKs/_existing_litellm/01_litellm_complete.md) | 📦 [practical](Level3_LLM_APIs_SDKs/_existing_litellm/practical/01_litellm_practical.py) |
| 3.5 | Streaming Responses | ⬜ 05_streaming.md | ⬜ TODO |
| 3.6 | Async & Parallel | ⬜ 06_async_parallel.md | ⬜ TODO |
| 3.7 | **Error Handling & Retries** | [✅ 07_error_handling_retries.md](Level3_LLM_APIs_SDKs/07_error_handling_retries.md) | (covered in theory) |
| 3.8 | Instructor (Structured) | 📦 [_existing_instructor](Level3_LLM_APIs_SDKs/_existing_instructor/01_instructor_library.md) | 📦 [practical](Level3_LLM_APIs_SDKs/_existing_instructor/practical/01_instructor_practical.py) |
| 3.9 | Sampling Parameters | (covered in Deep_Architecture/07) | — |
| 3.10 | **Cost Tracking & Optimization** | [✅ 10_cost_optimization.md](Level3_LLM_APIs_SDKs/10_cost_optimization.md) | (covered in theory) |

**Mastery check:** Streaming chatbot, OpenAI↔Claude swap, structured JSON via Instructor, token tracking.

---

## 🟡 LEVEL 4 — TOOL USE & FUNCTION CALLING (Week 4, ~8 hours) — ✅ COMPLETE

**Goal:** Let LLMs call your functions to act on the world. **Yahaan se Agentic AI start hota hai.**

| # | Topic | Theory | Practical |
|---|---|---|---|
| 4.1 | What is Tool Use? | [✅ 01_what_is_tool_use.md](Level4_Tool_Use_Function_Calling/01_what_is_tool_use.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/01_what_is_tool_use_practical.py) |
| 4.2 | OpenAI Function Calling | [✅ 02_openai_function_calling.md](Level4_Tool_Use_Function_Calling/02_openai_function_calling.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/02_openai_function_calling_practical.py) |
| 4.3 | Claude Tool Use | [✅ 03_claude_tool_use.md](Level4_Tool_Use_Function_Calling/03_claude_tool_use.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/03_claude_tool_use_practical.py) |
| 4.4 | Writing Tool Descriptions ⭐ | [✅ 04_tool_descriptions.md](Level4_Tool_Use_Function_Calling/04_tool_descriptions.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/04_tool_descriptions_practical.py) |
| 4.5 | Building Tool Libraries | [✅ 05_tool_libraries.md](Level4_Tool_Use_Function_Calling/05_tool_libraries.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/05_tool_libraries_practical.py) |
| 4.6 | Parallel Tool Calls | [✅ 06_parallel_tool_calls.md](Level4_Tool_Use_Function_Calling/06_parallel_tool_calls.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/06_parallel_tool_calls_practical.py) |
| 4.7 | Tool Use Loop | [✅ 07_tool_use_loop.md](Level4_Tool_Use_Function_Calling/07_tool_use_loop.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/07_tool_use_loop_practical.py) |
| 4.8 | Error Handling in Tools | [✅ 08_tool_error_handling.md](Level4_Tool_Use_Function_Calling/08_tool_error_handling.md) | [✅ practical.py](Level4_Tool_Use_Function_Calling/08_tool_error_handling_practical.py) |
| — | Web Search Tools | 📦 [_existing_web_search](Level4_Tool_Use_Function_Calling/_existing_web_search/01_web_search_tools.md) | 📦 [practical](Level4_Tool_Use_Function_Calling/_existing_web_search/practical/01_web_search_tools_practical.py) |

**Mastery check:** Build a ReAct agent from scratch (no framework). Tool fails gracefully, retries, recovers.

---

## 🟡 LEVEL 5 — RAG & VECTOR DATABASES (Week 5-6, ~15 hours)

**Goal:** Make LLMs answer from YOUR data, not just training data.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 5.1 | RAG Complete | 📦 [_existing_rag](Level5_RAG_Vector_Databases/_existing_rag/01_rag_complete.md) | 📦 [practical](Level5_RAG_Vector_Databases/_existing_rag/practical/01_rag_practical.py) |
| 5.2 | RAG Advanced | 📦 [_existing_rag](Level5_RAG_Vector_Databases/_existing_rag/02_rag_advanced.md) | 📦 [practical](Level5_RAG_Vector_Databases/_existing_rag/practical/02_rag_advanced.py) |
| 5.3 | Vector Databases | 📦 [_existing_vector_dbs](Level5_RAG_Vector_Databases/_existing_vector_dbs/01_vector_databases.md) | 📦 [practical](Level5_RAG_Vector_Databases/_existing_vector_dbs/practical/01_vector_db_practical.py) |
| 5.4 | **Chunking Strategies** ⭐ | [✅ 04_chunking_strategies.md](Level5_RAG_Vector_Databases/04_chunking_strategies.md) | (theory + examples) |
| 5.5 | Embedding Models | ⬜ 05_embedding_models.md | — |
| 5.6 | **Hybrid Search (BM25 + Vector)** ⭐ | [✅ 06_hybrid_search.md](Level5_RAG_Vector_Databases/06_hybrid_search.md) | (theory + code) |
| 5.7 | **Reranking** ⭐ | [✅ 07_reranking.md](Level5_RAG_Vector_Databases/07_reranking.md) | (theory + code) |
| 5.8 | Query Transformation (HyDE) | ⬜ 08_query_transformation.md | — |
| 5.9 | **RAGAS Evaluation** ⭐ | [✅ 09_ragas_evaluation.md](Level5_RAG_Vector_Databases/09_ragas_evaluation.md) | (theory + code) |

**Mastery check:** RAG over 1000 docs with hybrid search, reranking, RAGAS metrics > 0.85.

---

## 🟠 LEVEL 6 — AGENT PATTERNS (Week 7-8, ~12 hours)

**Goal:** Master the design patterns that power production agents.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 6.1 | Agent Patterns Overview | 📦 [_existing_patterns](Level6_Agent_Patterns/_existing_patterns/01_agent_patterns.md) | 📦 [practical](Level6_Agent_Patterns/_existing_patterns/practical/01_agent_patterns_practical.py) |
| 6.2 | Tool Use Advanced | 📦 [_existing_patterns](Level6_Agent_Patterns/_existing_patterns/02_tool_use_advanced.md) | 📦 [practical](Level6_Agent_Patterns/_existing_patterns/practical/02_tool_use_advanced.py) |
| 6.3 | Agent Memory | 📦 [_existing_memory](Level6_Agent_Patterns/_existing_memory/01_agent_memory.md) | 📦 [practical](Level6_Agent_Patterns/_existing_memory/practical/01_agent_memory_practical.py) |
| 6.4 | **ReAct Pattern (from scratch)** ⭐ | [✅ 04_react_pattern.md](Level6_Agent_Patterns/04_react_pattern.md) | [✅ practical](Level6_Agent_Patterns/04_react_pattern_practical.py) |
| 6.5 | **Plan & Execute** | [✅ 05_plan_and_execute.md](Level6_Agent_Patterns/05_plan_and_execute.md) | (theory + code) |
| 6.6 | Reflection Pattern | ⬜ 06_reflection.md | — |
| 6.7 | **Multi-Agent (Supervisor)** ⭐ | [✅ 07_multi_agent_supervisor.md](Level6_Agent_Patterns/07_multi_agent_supervisor.md) | [✅ practical](Level6_Agent_Patterns/07_multi_agent_supervisor_practical.py) |
| 6.8 | Routing & Classification | ⬜ 08_routing.md | — |
| 6.9 | Human-in-the-Loop | ⬜ 09_human_in_loop.md | — |
| 6.10 | **Agent Evaluation** ⭐ | [✅ 10_agent_evaluation.md](Level6_Agent_Patterns/10_agent_evaluation.md) | (theory + code) |

---

## 🟠 LEVEL 7 — FRAMEWORKS (Week 8-10, ~25 hours)

**Goal:** Production-grade frameworks. LangGraph + MCP are non-negotiable.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 7.1 | LangChain Complete | 📦 [_existing_LangChain](Level7_Frameworks/_existing_LangChain/01_langchain_complete.md) | 📦 [practical](Level7_Frameworks/_existing_LangChain/practical/01_langchain_practical.py) |
| 7.2 | LangGraph Complete ⭐ | 📦 [_existing_LangGraph](Level7_Frameworks/_existing_LangGraph/01_langgraph_complete.md) | 📦 [practical](Level7_Frameworks/_existing_LangGraph/practical/01_langgraph_practical.py) |
| 7.3 | LangGraph Advanced | 📦 [_existing_LangGraph](Level7_Frameworks/_existing_LangGraph/02_langgraph_advanced.md) | 📦 [practical](Level7_Frameworks/_existing_LangGraph/practical/02_langgraph_advanced.py) |
| 7.4 | MCP (Model Context Protocol) ⭐ | 📦 [_existing_MCP](Level7_Frameworks/_existing_MCP/01_mcp_complete.md) | 📦 [practical](Level7_Frameworks/_existing_MCP/practical/01_mcp_practical.py) |
| 7.5 | CrewAI | 📦 [_existing_CrewAI](Level7_Frameworks/_existing_CrewAI/01_crewai_complete.md) | 📦 [practical](Level7_Frameworks/_existing_CrewAI/practical/01_crewai_practical.py) |
| 7.6 | DSPy | 📦 [_existing_DSPy](Level7_Frameworks/_existing_DSPy/01_dspy_complete.md) | 📦 [practical](Level7_Frameworks/_existing_DSPy/practical/01_dspy_practical.py) |
| 7.7 | LlamaIndex | ⬜ 07_llamaindex.md | ⬜ 07_llamaindex_practical.py |
| 7.8 | Pydantic AI | ⬜ 08_pydantic_ai.md | ⬜ 08_pydantic_ai_practical.py |

⭐ = Must-master

---

## 🔴 LEVEL 8 — PRODUCTION LLMOps (Week 10-12, ~18 hours)

**Goal:** Senior-level — what separates demos from production.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 8.1 | Production AI Systems | 📦 [_existing_production](Level8_Production_LLMOps/_existing_production/01_production_ai.md) | 📦 [practical](Level8_Production_LLMOps/_existing_production/practical/01_production_ai_practical.py) |
| 8.2 | LLMOps Production | 📦 [_existing_production](Level8_Production_LLMOps/_existing_production/02_llmops_production.md) | 📦 [practical](Level8_Production_LLMOps/_existing_production/practical/02_llmops_production.py) |
| 8.3 | AI Testing | 📦 [_existing_testing](Level8_Production_LLMOps/_existing_testing/01_ai_testing.md) | 📦 [practical](Level8_Production_LLMOps/_existing_testing/practical/01_ai_testing_practical.py) |
| 8.4 | Enterprise AI Platforms | 📦 [_existing_enterprise](Level8_Production_LLMOps/_existing_enterprise/01_enterprise_ai_platforms.md) | 📦 [practical](Level8_Production_LLMOps/_existing_enterprise/practical/01_enterprise_ai_practical.py) |
| 8.5 | GraphRAG | 📦 [_existing_graphrag](Level8_Production_LLMOps/_existing_graphrag/01_graphrag.md) | 📦 [practical](Level8_Production_LLMOps/_existing_graphrag/practical/01_graphrag_practical.py) |
| 8.6 | LLM Fine-tuning | 📦 [_existing_finetuning](Level8_Production_LLMOps/_existing_finetuning/01_llm_finetuning.md) | 📦 [practical](Level8_Production_LLMOps/_existing_finetuning/practical/01_finetuning_practical.py) |
| 8.7 | Specialized AI (OCR, Speech) | 📦 [_existing_specialized](Level8_Production_LLMOps/_existing_specialized/01_specialized_ai.md) | 📦 [practical](Level8_Production_LLMOps/_existing_specialized/practical/01_specialized_ai_practical.py) |
| 8.8 | **Observability (LangSmith/Langfuse)** ⭐ | [✅ 08_observability.md](Level8_Production_LLMOps/08_observability.md) | (theory + code) |
| 8.9 | **Guardrails & Safety** ⭐ | [✅ 09_guardrails.md](Level8_Production_LLMOps/09_guardrails.md) | (theory + code) |
| 8.10 | Cost Optimization (covered in Level 3.10) | (see Level3/10_cost_optimization.md) | — |

---

## 🚀 PROJECTS (Capstone — Build & Deploy)

Portfolio building. **Yahi hain interview ka real weapon.**

| # | Project | Spec | Status |
|---|---|---|---|
| 1 | Personal AI Assistant + MCP | [📄](Projects/01_project1_personal_ai_assistant.md) | ⬜ Build |
| 2 | RAG Document Q&A System | [📄](Projects/02_project2_rag_document_qa.md) | ⬜ Build |
| 3 | Multi-Agent Code Review | [📄](Projects/03_project3_multiagent_code_review.md) | ⬜ Build |
| 4 | Production AI SaaS | [📄](Projects/04_project4_production_ai_saas.md) | ⬜ Build |

---

## 🌟 MODERN TOPICS (2025-26)

Cutting-edge topics beyond original PDF roadmap.

| # | Topic | Doc |
|---|---|---|
| 1 | **Voice Agents** (Whisper, Realtime API, ElevenLabs) | [✅ 01_voice_agents.md](Modern_Topics/01_voice_agents.md) |
| 2 | **Computer Use** (Claude Desktop Control) | [✅ 02_computer_use.md](Modern_Topics/02_computer_use.md) |
| 3 | **Local Serving** (Ollama, vLLM) | [✅ 03_local_serving.md](Modern_Topics/03_local_serving.md) |
| 4 | **Memory Frameworks** (Mem0, Zep) | [✅ 04_memory_frameworks.md](Modern_Topics/04_memory_frameworks.md) |
| 5 | **Multi-modal Agents** (Vision + Audio + Text) | [✅ 05_multimodal_agents.md](Modern_Topics/05_multimodal_agents.md) |

---

## 🎯 INTERVIEW PREP

Final-week polish.

| # | Topic | File |
|---|---|---|
| 1 | System Design for AI | [📄](Interview_Prep/01_system_design_ai_questions.md) |
| 2 | Coding Patterns | [📄](Interview_Prep/02_coding_patterns.md) |
| 3 | Behavioral Questions | [📄](Interview_Prep/03_behavioral_questions.md) |
| 4 | Key Technical Concepts | [📄](Interview_Prep/04_key_technical_concepts.md) |

---

## 📖 How to Use This Directory

### Daily learning flow:
1. **Open MASTER_INDEX.md** (this file) — find today's topic
2. **Read theory file** (e.g., `Level2_Prompt_Engineering/01_anatomy_of_prompt.md`)
3. **Run practical file** (`01_anatomy_of_prompt_practical.py`) — modify, experiment
4. **Update status** in this index when done (⬜ → ✅)
5. **Make notes** in your own scratch file or git commit

### Setup once:
```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
python -m venv .venv
source .venv/bin/activate
pip install openai anthropic litellm instructor pydantic tiktoken \
            langchain langgraph langchain-openai langchain-anthropic \
            chromadb pgvector psycopg2-binary tavily-python \
            ragas datasets sentence-transformers rank-bm25
```

### Env vars (.env file at root):
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
LANGCHAIN_API_KEY=ls__...    # for LangSmith
LANGCHAIN_TRACING_V2=true
```

---

## 🏆 Priority Order (If Short on Time)

If you have only 5 weeks (not 10-12):

1. **Week 1:** L1 + L2 (foundations, prompts)
2. **Week 2:** L3 + L4 (APIs, tool use)
3. **Week 3:** L5 (RAG end-to-end)
4. **Week 4:** L7.2 LangGraph + L7.4 MCP only (skip rest)
5. **Week 5:** L8 production basics + 1 project + interview prep

---

## 📝 Naming Conventions

- **Theory file:** `NN_topic_name.md` (e.g., `01_anatomy_of_prompt.md`)
- **Practical file:** `NN_topic_name_practical.py`
- **NN** = 2-digit number for ordering within a level
- **All lowercase** with underscores, no spaces

---

## 🔗 External Resources (Quick Links)

| Topic | Resource |
|---|---|
| Anthropic agent guide | [building-effective-agents](https://www.anthropic.com/research/building-effective-agents) |
| LangGraph docs | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph) |
| MCP spec | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| Claude API | [docs.anthropic.com](https://docs.anthropic.com) |
| OpenAI API | [platform.openai.com/docs](https://platform.openai.com/docs) |
| RAGAS | [docs.ragas.io](https://docs.ragas.io) |
| Eugene Yan's blog | [eugeneyan.com](https://eugeneyan.com) (production LLM systems) |

---

**Last note:** Ye index living document hai. Jaise files create hote jayenge, status update karte raho.
