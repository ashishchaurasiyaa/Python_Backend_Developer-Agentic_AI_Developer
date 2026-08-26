# 📚 MASTER INDEX — Agentic AI Complete Learning Directory

> **Tumhari complete navigation map.** Yahaan se start karo — har level, har topic, theory + practical sab listed hai with status.

**Last updated:** 2026-08-08 (Azure OpenAI + Azure AI Search, context engineering, voice practical, GRPO/RFT; index reconciled with disk)
**Roz ka kaam + poora topic scope:** [`../STUDY_PLAN.md`](../STUDY_PLAN.md) — single file, Part A (daily sprint) + Part B (full reference)

---

## 📊 Status (2026-08-08)

```
✅ Levels 1-8:        complete (most docs have a _practical.py; ~15 concept-only
                      docs don't — index tables mark those with '—')
✅ Modern Topics:     26 docs (00–24 + coverage analysis)
✅ Classical ML/DL:   12 docs (pre-transformer foundations)
✅ Azure track:       Azure OpenAI + Azure AI Search + Cosmos DB (backend track)
✅ ZERO blocking gaps for Backend+AI senior interviews

Current total: 170 markdown docs (levels + Modern + Projects + Interview Prep)
             + my-agentic-ai-project/ (~435 files: 2 full Udemy courses with runnable labs)
```

> ⚠️ **Content complete hai — labs pending hain.** Padhne se resume verify nahi hota.
> Roz ka kaam [`../STUDY_PLAN.md`](../STUDY_PLAN.md) me hai, log [`../MY_PROGRESS.md`](../MY_PROGRESS.md) me.

---

---

## 🗺️ Status Legend

- ✅ **DONE** — Theory + practical dono complete
- 🟡 **PARTIAL** — Some content there, more needed
- ⬜ **TODO** — Empty / not yet created

---

## 📂 Directory Structure Overview

```
Agentic_AI/
├── MASTER_INDEX.md              ← Tum yahaan ho
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
└── 02_subtopic_b_practical.py
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
| 1.8 | **World Models & Theory of Mind** ⭐ *(NEW)* | [✅ 08_world_models_theory_of_mind.md](Level1_LLM_Foundations/08_world_models_theory_of_mind.md) | — |
| 🔬 | **Deep Architecture (Internal Working)** | [✅ Deep_Architecture/README.md](Level1_LLM_Foundations/Deep_Architecture/README.md) | [✅ visualize_internals.py](Level1_LLM_Foundations/Deep_Architecture/10_visualize_internals_practical.py) |
| 🧠 | **Classical ML/DL Foundations (Before Transformers)** | [✅ Classical_ML_DL_Foundations/README.md](Level1_LLM_Foundations/Classical_ML_DL_Foundations/README.md) | [✅ 4 numpy-from-scratch practicals](Level1_LLM_Foundations/Classical_ML_DL_Foundations/04_gradient_descent_backprop_practical.py) |

### 🧠 Classical ML/DL Foundations Sub-Series (Perceptron → MLP → CNN → RNN → Bridge to Transformer)

| # | Topic | Doc | Practical |
|---|---|---|---|
| 1 | Linear & Logistic Regression | [01](Level1_LLM_Foundations/Classical_ML_DL_Foundations/01_ml_foundations_regression.md) | [✅ practical.py](Level1_LLM_Foundations/Classical_ML_DL_Foundations/01_ml_foundations_regression_practical.py) |
| 2 | Perceptron & MLP (XOR problem) | [02](Level1_LLM_Foundations/Classical_ML_DL_Foundations/02_perceptron_mlp.md) | (concepts) |
| 3 | Loss & Activation Functions | [03](Level1_LLM_Foundations/Classical_ML_DL_Foundations/03_loss_activation_functions.md) | (concepts) |
| 4 | Gradient Descent & Backpropagation ⭐ | [04](Level1_LLM_Foundations/Classical_ML_DL_Foundations/04_gradient_descent_backprop.md) | [✅ solves XOR from scratch](Level1_LLM_Foundations/Classical_ML_DL_Foundations/04_gradient_descent_backprop_practical.py) |
| 5 | Deep Neural Networks (overfitting, dropout, batch norm, residuals) | [05](Level1_LLM_Foundations/Classical_ML_DL_Foundations/05_deep_neural_networks_intro.md) | (concepts) |
| 6 | CNNs for Computer Vision | [06](Level1_LLM_Foundations/Classical_ML_DL_Foundations/06_cnn_computer_vision.md) | [✅ edge detection from scratch](Level1_LLM_Foundations/Classical_ML_DL_Foundations/06_cnn_computer_vision_practical.py) |
| 7 | RNNs & LSTMs for Sequential Data | [07](Level1_LLM_Foundations/Classical_ML_DL_Foundations/07_rnn_lstm_sequential.md) | [✅ measures gradient decay](Level1_LLM_Foundations/Classical_ML_DL_Foundations/07_rnn_lstm_sequential_practical.py) |
| 8 | RNN Limits & Rise of Transformers ⭐ | [08](Level1_LLM_Foundations/Classical_ML_DL_Foundations/08_rnn_limits_transformer_rise.md) | (bridges to Deep_Architecture) |
| 9 | Transfer Learning (→ LoRA/QLoRA) | [09](Level1_LLM_Foundations/Classical_ML_DL_Foundations/09_transfer_learning.md) | (concepts) |
| 10 | GANs & Diffusion Models (DALL-E/Stable Diffusion/Midjourney) | [10](Level1_LLM_Foundations/Classical_ML_DL_Foundations/10_gans_diffusion_image_gen.md) | (concepts) |
| 11 | Classical ML Algorithms (trees, SVM, ensembles) | [11](Level1_LLM_Foundations/Classical_ML_DL_Foundations/11_classical_ml_algorithms.md) | [✅ practical.py](Level1_LLM_Foundations/Classical_ML_DL_Foundations/11_classical_ml_algorithms_practical.py) |
| 12 | Classical NLP Pipeline (tokenize → TF-IDF → word2vec) | [12](Level1_LLM_Foundations/Classical_ML_DL_Foundations/12_classical_nlp_pipeline.md) | [✅ practical.py](Level1_LLM_Foundations/Classical_ML_DL_Foundations/12_classical_nlp_pipeline_practical.py) |

**Mastery check:** Explain backprop via chain rule. Why transformers replaced RNNs (2 specific reasons). Why LoRA works (transfer-learning theory).

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
| 3.1 | OpenAI API Complete | ✅ [01_openai_api_complete.md](Level3_LLM_APIs_SDKs/01_openai_api_complete.md) | ✅ [practical](Level3_LLM_APIs_SDKs/01_openai_api_complete_practical.py) |
| 3.2 | Anthropic Claude API | ✅ [02_claude_api_complete.md](Level3_LLM_APIs_SDKs/02_claude_api_complete.md) | ✅ [practical](Level3_LLM_APIs_SDKs/02_claude_api_complete_practical.py) |
| 3.3 | Google Gemini API | ✅ [03_ai_apis.md](Level3_LLM_APIs_SDKs/03_ai_apis.md) | ✅ [practical](Level3_LLM_APIs_SDKs/03_ai_apis_practical.py) |
| 3.4 | LiteLLM Multi-Provider | ✅ [04_litellm_complete.md](Level3_LLM_APIs_SDKs/04_litellm_complete.md) | ✅ [practical](Level3_LLM_APIs_SDKs/04_litellm_complete_practical.py) |
| 3.5 | Streaming Responses | [✅ 05_streaming_responses.md](Level3_LLM_APIs_SDKs/05_streaming_responses.md) | [✅ practical](Level3_LLM_APIs_SDKs/05_streaming_responses_practical.py) |
| 3.6 | Async & Parallel | [✅ 06_async_parallel.md](Level3_LLM_APIs_SDKs/06_async_parallel.md) | [✅ practical](Level3_LLM_APIs_SDKs/06_async_parallel_practical.py) |
| 3.7 | **Error Handling & Retries** | [✅ 07_error_handling_retries.md](Level3_LLM_APIs_SDKs/07_error_handling_retries.md) | [✅ practical](Level3_LLM_APIs_SDKs/07_error_handling_retries_practical.py) |
| 3.8 | Instructor (Structured) | ✅ [08_instructor_library.md](Level3_LLM_APIs_SDKs/08_instructor_library.md) | ✅ [practical](Level3_LLM_APIs_SDKs/08_instructor_library_practical.py) |
| 3.9 | Sampling Parameters | [✅ 09_sampling_parameters.md](Level3_LLM_APIs_SDKs/09_sampling_parameters.md) | [✅ practical](Level3_LLM_APIs_SDKs/09_sampling_parameters_practical.py) |
| 3.10 | **Cost Tracking & Optimization** | [✅ 10_cost_optimization.md](Level3_LLM_APIs_SDKs/10_cost_optimization.md) | [✅ practical](Level3_LLM_APIs_SDKs/10_cost_optimization_practical.py) |
| 3.11 | **Azure OpenAI** 🔴 *(NEW)* — deployments, Entra ID, quota/TPM, PTU, content filters | [✅ 11_azure_openai.md](Level3_LLM_APIs_SDKs/11_azure_openai.md) | [✅ practical](Level3_LLM_APIs_SDKs/11_azure_openai_practical.py) |

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
| — | Web Search Tools | ✅ [09_web_search_tools.md](Level4_Tool_Use_Function_Calling/09_web_search_tools.md) | ✅ [practical](Level4_Tool_Use_Function_Calling/09_web_search_tools_practical.py) |

**Mastery check:** Build a ReAct agent from scratch (no framework). Tool fails gracefully, retries, recovers.

---

## 🟡 LEVEL 5 — RAG & VECTOR DATABASES (Week 5-6, ~15 hours)

**Goal:** Make LLMs answer from YOUR data, not just training data.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 5.1 | RAG Complete | ✅ [01_rag_complete.md](Level5_RAG_Vector_Databases/01_rag_complete.md) | ✅ [practical](Level5_RAG_Vector_Databases/01_rag_complete_practical.py) |
| 5.2 | RAG Advanced | ✅ [02_rag_advanced.md](Level5_RAG_Vector_Databases/02_rag_advanced.md) | ✅ [practical](Level5_RAG_Vector_Databases/02_rag_advanced_practical.py) |
| 5.3 | Vector Databases | ✅ [03_vector_databases.md](Level5_RAG_Vector_Databases/03_vector_databases.md) | ✅ [practical](Level5_RAG_Vector_Databases/03_vector_databases_practical.py) |
| 5.4 | **Chunking Strategies** ⭐ | [✅ 04_chunking_strategies.md](Level5_RAG_Vector_Databases/04_chunking_strategies.md) | [✅ practical](Level5_RAG_Vector_Databases/04_chunking_strategies_practical.py) |
| 5.5 | Embedding Models | [✅ 05_embedding_models.md](Level5_RAG_Vector_Databases/05_embedding_models.md) | [✅ practical](Level5_RAG_Vector_Databases/05_embedding_models_practical.py) |
| 5.6 | **Hybrid Search (BM25 + Vector)** ⭐ | [✅ 06_hybrid_search.md](Level5_RAG_Vector_Databases/06_hybrid_search.md) | [✅ practical](Level5_RAG_Vector_Databases/06_hybrid_search_practical.py) |
| 5.7 | **Reranking** ⭐ | [✅ 07_reranking.md](Level5_RAG_Vector_Databases/07_reranking.md) | [✅ practical](Level5_RAG_Vector_Databases/07_reranking_practical.py) |
| 5.8 | Query Transformation (HyDE) | [✅ 08_query_transformation.md](Level5_RAG_Vector_Databases/08_query_transformation.md) | [✅ practical](Level5_RAG_Vector_Databases/08_query_transformation_practical.py) |
| 5.9 | **RAGAS Evaluation** ⭐ | [✅ 09_ragas_evaluation.md](Level5_RAG_Vector_Databases/09_ragas_evaluation.md) | [✅ practical](Level5_RAG_Vector_Databases/09_ragas_evaluation_practical.py) |
| 5.10 | **Contextual Retrieval (Anthropic)** ⭐ | [✅ 10_contextual_retrieval.md](Level5_RAG_Vector_Databases/10_contextual_retrieval.md) | — |
| 5.11 | **Azure AI Search** 🔴 *(NEW)* — vector + hybrid RRF + semantic ranker, integrated vectorization | [✅ 11_azure_ai_search.md](Level5_RAG_Vector_Databases/11_azure_ai_search.md) | [✅ practical](Level5_RAG_Vector_Databases/11_azure_ai_search_practical.py) |

**Mastery check:** RAG over 1000 docs with hybrid search, reranking, RAGAS metrics > 0.85.

---

## 🟠 LEVEL 6 — AGENT PATTERNS (Week 7-8, ~12 hours)

**Goal:** Master the design patterns that power production agents.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 6.1 | Agent Patterns Overview | ✅ [01_agent_patterns.md](Level6_Agent_Patterns/01_agent_patterns.md) | ✅ [practical](Level6_Agent_Patterns/01_agent_patterns_practical.py) |
| 6.2 | Tool Use Advanced | ✅ [02_tool_use_advanced.md](Level6_Agent_Patterns/02_tool_use_advanced.md) | ✅ [practical](Level6_Agent_Patterns/02_tool_use_advanced_practical.py) |
| 6.3 | Agent Memory | ✅ [03_agent_memory.md](Level6_Agent_Patterns/03_agent_memory.md) | ✅ [practical](Level6_Agent_Patterns/03_agent_memory_practical.py) |
| 6.4 | **ReAct Pattern (from scratch)** ⭐ | [✅ 04_react_pattern.md](Level6_Agent_Patterns/04_react_pattern.md) | [✅ practical](Level6_Agent_Patterns/04_react_pattern_practical.py) |
| 6.5 | **Plan & Execute** | [✅ 05_plan_and_execute.md](Level6_Agent_Patterns/05_plan_and_execute.md) | [✅ practical](Level6_Agent_Patterns/05_plan_and_execute_practical.py) |
| 6.6 | Reflection Pattern | [✅ 06_reflection_pattern.md](Level6_Agent_Patterns/06_reflection_pattern.md) | [✅ practical](Level6_Agent_Patterns/06_reflection_pattern_practical.py) |
| 6.7 | **Multi-Agent (Supervisor)** ⭐ | [✅ 07_multi_agent_supervisor.md](Level6_Agent_Patterns/07_multi_agent_supervisor.md) | [✅ practical](Level6_Agent_Patterns/07_multi_agent_supervisor_practical.py) |
| 6.8 | Routing & Classification | [✅ 08_routing.md](Level6_Agent_Patterns/08_routing.md) | [✅ practical](Level6_Agent_Patterns/08_routing_practical.py) |
| 6.9 | Human-in-the-Loop | [✅ 09_human_in_loop.md](Level6_Agent_Patterns/09_human_in_loop.md) | [✅ practical](Level6_Agent_Patterns/09_human_in_loop_practical.py) |
| 6.10 | **Agent Evaluation** ⭐ | [✅ 10_agent_evaluation.md](Level6_Agent_Patterns/10_agent_evaluation.md) | [✅ practical](Level6_Agent_Patterns/10_agent_evaluation_practical.py) |
| 6.11 | **Swarm Agents** (decentralized handoff) | [✅ 11_swarm_agents.md](Level6_Agent_Patterns/11_swarm_agents.md) | — |
| 6.12 | **Agent Harness Engineering** ⭐ | [✅ 12_agent_harness_engineering.md](Level6_Agent_Patterns/12_agent_harness_engineering.md) | — |
| 6.13 | **Context Engineering** ⭐ *(NEW)* — context budgets, compaction, sub-agent isolation | [✅ 13_context_engineering.md](Level6_Agent_Patterns/13_context_engineering.md) | — |

---

## 🟠 LEVEL 7 — FRAMEWORKS (Week 8-10, ~25 hours)

**Goal:** Production-grade frameworks. LangGraph + MCP are non-negotiable.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 7.1 | LangChain Complete | ✅ [01_langchain_complete.md](Level7_Frameworks/01_langchain_complete.md) | ✅ [practical](Level7_Frameworks/01_langchain_complete_practical.py) |
| 7.2 | LangGraph Complete ⭐ | ✅ [02_langgraph_complete.md](Level7_Frameworks/02_langgraph_complete.md) | ✅ [practical](Level7_Frameworks/02_langgraph_complete_practical.py) |
| 7.3 | LangGraph Advanced | ✅ [03_langgraph_advanced.md](Level7_Frameworks/03_langgraph_advanced.md) | ✅ [practical](Level7_Frameworks/03_langgraph_advanced_practical.py) |
| 7.4 | MCP (Model Context Protocol) ⭐ | ✅ [04_mcp_complete.md](Level7_Frameworks/04_mcp_complete.md) | ✅ [practical](Level7_Frameworks/04_mcp_complete_practical.py) |
| 7.5 | CrewAI | ✅ [05_crewai_complete.md](Level7_Frameworks/05_crewai_complete.md) | ✅ [practical](Level7_Frameworks/05_crewai_complete_practical.py) |
| 7.6 | DSPy | ✅ [06_dspy_complete.md](Level7_Frameworks/06_dspy_complete.md) | ✅ [practical](Level7_Frameworks/06_dspy_complete_practical.py) |
| 7.7 | LlamaIndex | [✅ 07_llamaindex.md](Level7_Frameworks/07_llamaindex.md) | [✅ practical](Level7_Frameworks/07_llamaindex_practical.py) |
| 7.8 | Pydantic AI | [✅ 08_pydantic_ai.md](Level7_Frameworks/08_pydantic_ai.md) | [✅ practical](Level7_Frameworks/08_pydantic_ai_practical.py) |
| 7.9 | Semantic Kernel (Azure/.NET shops) | [✅ 09_semantic_kernel.md](Level7_Frameworks/09_semantic_kernel.md) | — |
| 7.10 | **A2A Protocol (Agent2Agent interop)** ⭐ *(NEW)* | [✅ 10_a2a_protocol.md](Level7_Frameworks/10_a2a_protocol.md) | — |
| 7.11 | Haystack (deepset) *(NEW)* | [✅ 11_haystack.md](Level7_Frameworks/11_haystack.md) | — |

⭐ = Must-master

---

## 🔴 LEVEL 8 — PRODUCTION LLMOps (Week 10-12, ~18 hours)

**Goal:** Senior-level — what separates demos from production.

| # | Topic | Theory | Practical |
|---|---|---|---|
| 8.1 | Production AI Systems | ✅ [01_production_ai.md](Level8_Production_LLMOps/01_production_ai.md) | ✅ [practical](Level8_Production_LLMOps/01_production_ai_practical.py) |
| 8.2 | LLMOps Production | ✅ [02_llmops_production.md](Level8_Production_LLMOps/02_llmops_production.md) | ✅ [practical](Level8_Production_LLMOps/02_llmops_production_practical.py) |
| 8.3 | AI Testing | ✅ [03_ai_testing.md](Level8_Production_LLMOps/03_ai_testing.md) | ✅ [practical](Level8_Production_LLMOps/03_ai_testing_practical.py) |
| 8.4 | Enterprise AI Platforms | ✅ [04_enterprise_ai_platforms.md](Level8_Production_LLMOps/04_enterprise_ai_platforms.md) | ✅ [practical](Level8_Production_LLMOps/04_enterprise_ai_platforms_practical.py) |
| 8.5 | GraphRAG | ✅ [05_graphrag.md](Level8_Production_LLMOps/05_graphrag.md) | ✅ [practical](Level8_Production_LLMOps/05_graphrag_practical.py) |
| 8.6 | LLM Fine-tuning | ✅ [06_llm_finetuning.md](Level8_Production_LLMOps/06_llm_finetuning.md) | ✅ [practical](Level8_Production_LLMOps/06_llm_finetuning_practical.py) |
| 8.7 | Specialized AI (OCR, Speech) | ✅ [07_specialized_ai.md](Level8_Production_LLMOps/07_specialized_ai.md) | ✅ [practical](Level8_Production_LLMOps/07_specialized_ai_practical.py) |
| 8.8 | **Observability (LangSmith/Langfuse)** ⭐ | [✅ 08_observability.md](Level8_Production_LLMOps/08_observability.md) | [✅ practical](Level8_Production_LLMOps/08_observability_practical.py) |
| 8.9 | **Guardrails & Safety** ⭐ | [✅ 09_guardrails.md](Level8_Production_LLMOps/09_guardrails.md) | [✅ practical](Level8_Production_LLMOps/09_guardrails_practical.py) |
| 8.10 | **Cost Optimization (Advanced)** | [✅ 10_cost_optimization_advanced.md](Level8_Production_LLMOps/10_cost_optimization_advanced.md) | [✅ practical](Level8_Production_LLMOps/10_cost_optimization_advanced_practical.py) |
| 8.11 | Databricks/Spark/Snowflake (enterprise data plane) | [✅ 11_databricks_spark_snowflake.md](Level8_Production_LLMOps/11_databricks_spark_snowflake.md) | — |

---

## 🚀 PROJECTS (Capstone — Build & Deploy)

Portfolio building. **Yahi hain interview ka real weapon.**

| # | Project | Spec | Status |
|---|---|---|---|
| 1 | Personal AI Assistant + MCP | [📄](Projects/01_project1_personal_ai_assistant.md) | ⬜ Build |
| 2 | RAG Document Q&A System | [📄](Projects/02_project2_rag_document_qa.md) | ⬜ Build |
| 3 | Multi-Agent Code Review | [📄](Projects/03_project3_multiagent_code_review.md) | ⬜ Build |
| 4 | Production AI SaaS | [📄](Projects/04_project4_production_ai_saas.md) | ⬜ Build |
| 5 | Wedding Transformation Agent | [📁](Projects/project5_wedding_transformation_agent/) | 🔨 In progress |

> **Starter code:** projects 1–4 ke starter scaffolds `Projects/` me hain (project 3 sabse zyada bana hua hai —
> LangGraph nodes/state/graph + MCP server). Spec padh ke shuru mat karo — starter kholo.

---

## 🌟 MODERN TOPICS (2025-26)

Cutting-edge topics beyond original PDF roadmap.

| # | Topic | Doc |
|---|---|---|
| 0 | **AI Tools Landscape** — kaunsa tool kis kaam ka | [✅ 00_ai_tools_landscape.md](Modern_Topics/00_ai_tools_landscape.md) |
| 1 | **Voice Agents** (Whisper, Realtime API, ElevenLabs) — + [runnable pipeline practical](Modern_Topics/01_voice_agents_practical.py) *(NEW)* | [✅ 01_voice_agents.md](Modern_Topics/01_voice_agents.md) |
| 2 | **Computer Use** (Claude Desktop Control) | [✅ 02_computer_use.md](Modern_Topics/02_computer_use.md) |
| 3 | **Local Serving** (Ollama, vLLM) | [✅ 03_local_serving.md](Modern_Topics/03_local_serving.md) |
| 4 | **Memory Frameworks** (Mem0, Zep) | [✅ 04_memory_frameworks.md](Modern_Topics/04_memory_frameworks.md) |
| 5 | **Multi-modal Agents** (Vision + Audio + Text) | [✅ 05_multimodal_agents.md](Modern_Topics/05_multimodal_agents.md) |
| 6 | **Playwright / Browser Automation** | [✅ 06_playwright_browser_automation.md](Modern_Topics/06_playwright_browser_automation.md) |
| 7 | **AI Coding Tools** (Claude Code, Copilot, Cursor) | [✅ 07_ai_coding_tools.md](Modern_Topics/07_ai_coding_tools.md) |
| 8 | **MCP Advanced Server Dev** (transports, auth, hardening) | [✅ 08_mcp_advanced_server_dev.md](Modern_Topics/08_mcp_advanced_server_dev.md) |
| 9 | **AI Security Threats** (OWASP LLM Top 10, prompt injection) | [✅ 09_ai_security_threats.md](Modern_Topics/09_ai_security_threats.md) |
| 10 | **AI Ethics & Responsible AI** (bias, fairness, governance, EU AI Act) | [✅ 10_ai_ethics_responsible_ai.md](Modern_Topics/10_ai_ethics_responsible_ai.md) |
| 11 | **Coding Agent Harness Deep Dive** (diff-editing, verification loops, sandboxing) *(NEW)* | [✅ 11_coding_agent_harness_deep_dive.md](Modern_Topics/11_coding_agent_harness_deep_dive.md) |
| 12 | **OpenAI Responses API** (2025 agentic API: stateful, hosted tools, agent loop) *(NEW)* | [✅ 12_openai_responses_api.md](Modern_Topics/12_openai_responses_api.md) |
| 13 | **Gemini Live API** (real-time bidirectional multimodal, barge-in, voice+vision) *(NEW)* | [✅ 13_gemini_live_api.md](Modern_Topics/13_gemini_live_api.md) |
| 14 | **Data Extraction** (Crawl4AI, FireCrawl, ScrapeGraphAI, Docling, LlamaParse, MegaParser, ExtractThinker) — architecture + practical *(NEW)* | [✅ 14_data_extraction.md](Modern_Topics/14_data_extraction.md) · [🐍 practical](Modern_Topics/14_data_extraction_practical.py) |
| 15 | **Cassandra / Astra vector store** (masterless ring, SAI + JVector ANN, CQL) *(NEW)* | [✅ 15_cassandra_vector_store.md](Modern_Topics/15_cassandra_vector_store.md) · [🐍 practical](Modern_Topics/15_cassandra_vector_store_practical.py) |
| 16 | **Txtai** (all-in-one embeddings DB + pipelines + workflows) *(NEW)* | [✅ 16_txtai.md](Modern_Topics/16_txtai.md) · [🐍 practical](Modern_Topics/16_txtai_practical.py) |
| 17 | **Giskard** (LLM/RAG red-teaming, scan, RAGET, CI gate) *(NEW)* | [✅ 17_giskard_evaluation.md](Modern_Topics/17_giskard_evaluation.md) · [🐍 practical](Modern_Topics/17_giskard_evaluation_practical.py) |
| 18 | **Model training internals** (RLHF/PPO/DPO, Distillation, Validation Loss) — concept level *(NEW)* | [✅ 18_model_training_internals.md](Modern_Topics/18_model_training_internals.md) |
| 19 | **Milvus** (cloud-native, billion-scale, disaggregated, GPU ANN) *(NEW)* | [✅ 19_milvus_vector_db.md](Modern_Topics/19_milvus_vector_db.md) · [🐍 practical](Modern_Topics/19_milvus_vector_db_practical.py) |
| 20 | **OpenSearch vectors** (k-NN + BM25 hybrid, HNSW/Faiss) *(NEW)* | [✅ 20_opensearch_vector.md](Modern_Topics/20_opensearch_vector.md) · [🐍 practical](Modern_Topics/20_opensearch_vector_practical.py) |
| 21 | **Together AI** (hosted open-weight models, OpenAI-compatible, FT) *(NEW)* | [✅ 21_together_ai.md](Modern_Topics/21_together_ai.md) · [🐍 practical](Modern_Topics/21_together_ai_practical.py) |
| 22 | **TruLens** (LLM observability, RAG Triad, feedback functions) *(NEW)* | [✅ 22_trulens_evaluation.md](Modern_Topics/22_trulens_evaluation.md) · [🐍 practical](Modern_Topics/22_trulens_evaluation_practical.py) |
| 23 | **Claude Agent SDK + Agent Skills** (Claude Code as a library: built-in tools, hooks, subagents; SKILL.md progressive disclosure) *(NEW)* | [✅ 23_claude_agent_sdk_skills.md](Modern_Topics/23_claude_agent_sdk_skills.md) |
| 24 | **OpenAI AgentKit** (Agent Builder, ChatKit, Connector Registry, trace-grading Evals; vs Agents SDK) *(NEW)* | [✅ 24_openai_agentkit.md](Modern_Topics/24_openai_agentkit.md) |
| 25 | 🔴 **Azure AI Foundry + Prompt Flow** (hierarchy, deployment types, DAG + variants, azure-ai-evaluation, OTel tracing, Agent Service, Content Safety) *(NEW)* | [✅ 25_azure_ai_foundry_promptflow.md](Modern_Topics/25_azure_ai_foundry_promptflow.md) |
| 26 | 🔴 **Azure AI Services (AI-900/AI-102 scope)** (Document Intelligence layout→Markdown, AI Language PII/CLU, Speech, Vision, Responsible AI 6) *(NEW)* | [✅ 26_azure_ai_services_ai102.md](Modern_Topics/26_azure_ai_services_ai102.md) |
| — | **📊 Complete Coverage Analysis** (all 43 tools + 12 terms mapped) | [✅ COVERAGE_ANALYSIS.md](Modern_Topics/COVERAGE_ANALYSIS.md) |

---

## 🎯 INTERVIEW PREP

Final-week polish.

| # | Topic | File |
|---|---|---|
| 1 | System Design for AI | [📄](Interview_Prep/01_system_design_ai_questions.md) |
| 2 | Coding Patterns | [📄](Interview_Prep/02_coding_patterns.md) |
| 3 | Behavioral Questions | [📄](Interview_Prep/03_behavioral_questions.md) |
| 4 | Key Technical Concepts | [📄](Interview_Prep/04_key_technical_concepts.md) |
| 5 | 🔴 **GenAI Developer (Azure role) prep** — JD→repo gap map + day-wise plan | [📄](Interview_Prep/05_genai_developer_azure_role_prep.md) |
| 6 | 🔴 **PwC Senior Associate GenAI prep — interview Tue 18 Aug 2026** *(NEW)* — gap audit, 6-day plan, consulting behavioral, honest-answer scripts, one-page recall card | [📄](Interview_Prep/06_pwc_genai_senior_associate_prep.md) |

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

---

## 🎓 `my-agentic-ai-project/` — course notes + runnable labs (~435 files)

> **Yeh index me pehle tha hi nahi** — sabse bada practical hissa yahi hai. Levels 1–8 *theory* hain;
> yahan **per-lecture notes + chalne wale labs** hain (OpenAI Agents SDK, CrewAI, LangGraph, AutoGen, MCP, deployment).

| Folder | Kya hai | Kab kholo |
|---|---|---|
| [`Udemy_EdDonner_Course/`](my-agentic-ai-project/Udemy_EdDonner_Course/) | ~131 lectures — per-lecture Hinglish notes + labs (OpenAI Agents SDK, CrewAI, LangGraph, AutoGen, MCP) | Framework hands-on chahiye |
| [`Udemy_EdDonner_ProductionTrack/`](my-agentic-ai-project/Udemy_EdDonner_ProductionTrack/) | ~124 lectures — multi-agent, observability, AgentCore, cloud deploy | Production/LLMOps ka practical |
| [`KrishNaik_AgenticAI_NewTopics/`](my-agentic-ai-project/KrishNaik_AgenticAI_NewTopics/) | N01 LangChain v1 · N02 Vectorless RAG · N03 Deep Agents · N04 LLM Gateways | 2026 ke naye topics |
| [`generativeai/`](my-agentic-ai-project/generativeai/) | uv-managed workspace — labs yahan chalte hain | Code likhte waqt |
| [`COMPLETE_SEQUENCE.md`](my-agentic-ai-project/COMPLETE_SEQUENCE.md) · [`4_DAY_PRACTICE_PLAN.md`](my-agentic-ai-project/4_DAY_PRACTICE_PLAN.md) · [`NOTES.md`](my-agentic-ai-project/NOTES.md) | Course ka apna sequence + practice plan | Yahan se shuru karo |

```bash
cd my-agentic-ai-project && uv sync    # labs chalane ke liye
```

---

**Last note:** Ye index living document hai. Jaise files create hote jayenge, status update karte raho.
