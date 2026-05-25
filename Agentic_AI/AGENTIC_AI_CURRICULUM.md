# Agentic AI — Complete Curriculum (Basic → Advanced)

> **The complete topic list across all 8 levels.** Use this as the table of contents for your learning journey. Each topic listed here will become a dedicated .md doc.

---

## 📊 At a Glance

```
Level 1 — LLM Foundations          🟢 BASIC           7 docs / Week 1
Level 2 — Prompt Engineering       🟢 BASIC          10 docs / Week 2
Level 3 — LLM APIs & SDKs          🟡 INTERMEDIATE   10 docs / Week 3
Level 4 — Tool Use & Function Call 🟡 INTERMEDIATE    8 docs / Week 4
Level 5 — RAG & Vector Databases   🟡 INTERMEDIATE   15 docs / Week 5-6
Level 6 — Agent Patterns           🟠 ADVANCED       12 docs / Week 7-8
Level 7 — Frameworks               🟠 ADVANCED       25 docs / Week 8-10
Level 8 — Production LLMOps        🔴 EXPERT         18 docs / Week 10-12
Projects                            🚀 BUILD          8 project specs
─────────────────────────────────────────────────────────────────────
TOTAL: ~110 detailed learning docs + 8 project specs
```

---

## 🟢 LEVEL 1 — LLM FOUNDATIONS (Basic)

> **Goal:** Build intuition for what LLMs are, how they work, and the landscape.
> **Time:** Week 1 — ~7 hours total.
> **Prerequisite:** Python basics, comfortable with APIs.

### Topics

#### 1.1 What is an LLM?
- Definition (next-token predictor)
- The "world's most well-read autocomplete" analogy
- What "large" means (parameters)
- Pre-training vs post-training (RLHF)
- What an LLM is NOT (not conscious, not always factual)
- Hallucination problem

#### 1.2 History of LLMs (5-min skim)
- Pre-2017: RNN/LSTM era
- 2017: Transformer paper ("Attention is All You Need")
- 2018-2020: BERT, GPT-1, GPT-2, GPT-3
- 2022: ChatGPT launches → mainstream
- 2023-2024: GPT-4, Claude, Gemini, Llama
- 2024-2025: o1/o3 reasoning, Claude 3.5, Gemini 2.0

#### 1.3 Tokens & Tokenization
- What's a token (not word, not char)
- Tokenizer = text → token IDs
- Byte-pair encoding (BPE), tiktoken
- Token-to-cost relationship
- Foreign language tokenization (Hindi 2-3x more tokens)
- Token-counting in code

#### 1.4 Embeddings (Introduction)
- Text → vector of numbers
- Similar meanings → similar vectors
- Cosine similarity
- Use cases (search, recommendation, RAG preview)
- Embedding models landscape

#### 1.5 Attention & Transformers (Simplified)
- "Attention" intuition (LLM "looks at" relevant tokens)
- Self-attention vs cross-attention
- Transformer architecture (high-level)
- Why this scaled to GPT-4 level
- No math — just intuition

#### 1.6 Models Landscape
- OpenAI (GPT-4o, GPT-4o-mini, o1, o3)
- Anthropic (Claude 3.5 Sonnet, Opus, Haiku)
- Google (Gemini 1.5/2.0 Pro, Flash)
- Meta (Llama 3.1, 3.2)
- Mistral, DeepSeek, Qwen, Cohere
- Open-source vs closed-source trade-offs
- Specialized models (Codestral, Voyage embeddings)
- Multi-modal (vision, audio)
- Pricing comparison

#### 1.7 Dev Environment Setup
- Python 3.10+ + uv/pip
- API keys (OpenAI, Anthropic)
- VS Code / Cursor / PyCharm
- Environment variables (.env)
- First "Hello World" call
- Tokenizer playground

**Mastery Check:** Make a successful API call to OpenAI AND Claude. Explain what tokens are and why they cost money.

---

## 🟢 LEVEL 2 — PROMPT ENGINEERING (Basic)

> **Goal:** Craft prompts that produce reliable, consistent outputs.
> **Time:** Week 2 — ~10 hours total.

### Topics

#### 2.1 Anatomy of a Prompt
- System message, user message, assistant message
- Multi-turn conversation structure
- Role-based prompting
- Examples in code

#### 2.2 Zero-Shot Prompting
- Just ask
- When it works, when it fails
- Common pitfalls

#### 2.3 Few-Shot Prompting
- Including examples in prompt
- How many shots? (typically 3-8)
- Selecting good examples
- Dynamic example selection

#### 2.4 Chain-of-Thought (CoT)
- "Let's think step by step"
- Why it dramatically improves reasoning
- Zero-shot CoT vs few-shot CoT
- When CoT doesn't help

#### 2.5 Advanced Reasoning Patterns
- Self-Consistency (multiple samples, vote)
- Tree of Thoughts (ToT)
- Self-Critique (LLM reviews its own answer)
- Reasoning models (o1, o3) — when prompting changes

#### 2.6 System Prompts Deep
- Persona setting
- Constraints and rules
- Output format specification
- Anti-injection prompts
- Length and tone control

#### 2.7 Structured Outputs
- JSON mode
- Function calling for structure
- Pydantic + Instructor library
- Schema enforcement
- Error handling for malformed JSON

#### 2.8 Prompt Templates & Variables
- Jinja2 in prompts
- LangChain ChatPromptTemplate
- Reusable templates
- Versioning prompts

#### 2.9 Prompt Patterns Library (Cookbook)
- Summarization patterns
- Extraction patterns
- Classification patterns
- Translation patterns
- Creative writing patterns
- Code generation patterns
- Q&A patterns
- Critique patterns
- Refusal patterns

#### 2.10 Anti-Patterns & Pitfalls
- Hallucination triggers
- Conflicting instructions
- Token waste
- Overly long system prompts
- Prompt injection vulnerabilities (basic awareness)
- "Please be honest" doesn't work the way you think

**Mastery Check:** Given a vague task ("extract key info from this email"), write a prompt that returns consistent, structured JSON every time.

---

## 🟡 LEVEL 3 — LLM APIs & SDKs (Intermediate)

> **Goal:** Master the APIs you'll use daily.
> **Time:** Week 3 — ~10 hours total.

### Topics

#### 3.1 OpenAI API Complete
- Chat Completions endpoint
- Embeddings endpoint
- Audio (Whisper, TTS)
- Vision (image input)
- Assistants API (overview)
- Batch API (50% discount)
- Files API

#### 3.2 Anthropic Claude API Complete
- Messages API
- System parameter (vs OpenAI's system message)
- Vision with Claude
- Prompt caching (90% cost savings)
- Computer use API (Claude controls computer)
- Differences from OpenAI

#### 3.3 Google Gemini API
- Gemini 1.5/2.0
- Long context (2M tokens)
- Native multi-modal
- Free tier benefits

#### 3.4 LiteLLM (Multi-Provider)
- One API, 100+ models
- Failover and fallback
- Cost tracking
- Streaming
- Rate limit handling

#### 3.5 Streaming Responses
- Why streaming (UX)
- Server-Sent Events (SSE)
- Async iteration
- Handling partial JSON
- Streaming with tool calls

#### 3.6 Async & Parallel Calls
- asyncio with LLM SDKs
- Concurrent requests
- Semaphore for rate limits
- Batching multiple prompts

#### 3.7 Error Handling & Retries
- Rate limit (429)
- Timeout
- Token limit exceeded
- Model unavailable
- Tenacity library for retries
- Exponential backoff

#### 3.8 Instructor Library (Structured Output)
- Pydantic + LLM = type-safe
- Validation retries
- Streaming structured output
- Async support
- Why this beats raw JSON mode

#### 3.9 Sampling Parameters
- Temperature (0-2)
- Top-p (nucleus sampling)
- Top-k
- Frequency penalty, presence penalty
- Stop sequences
- Seed (reproducibility)
- Logprobs

#### 3.10 Cost Tracking & Optimization
- Token counting (input + output)
- Per-request logging
- Choosing right model per task
- Prompt caching (Anthropic)
- Batching (OpenAI Batch API)

**Mastery Check:** Build a streaming chatbot that switches between OpenAI and Claude based on user choice, returns structured JSON via Instructor, and tracks token usage.

---

## 🟡 LEVEL 4 — TOOL USE & FUNCTION CALLING (Intermediate)

> **Goal:** Let LLMs call your functions to act on the world.
> **Time:** Week 4 — ~8 hours total.

### Topics

#### 4.1 What is Tool Use?
- Concept: LLM picks a function to call
- Tool use loop: LLM → choose tool → execute → return result → LLM continues
- "Function calling" (OpenAI) vs "Tool use" (Anthropic) — same idea

#### 4.2 OpenAI Function Calling
- Defining functions with JSON Schema
- Tool descriptions (clarity matters!)
- Tool choice (auto, required, specific)
- Parallel function calls
- Strict mode (guaranteed schema)

#### 4.3 Anthropic Claude Tool Use
- Tool definitions
- Forced tool use
- Stop reasons
- Computer Use (control desktop)
- Differences from OpenAI

#### 4.4 Writing Great Tool Descriptions
- The single most important skill
- What the tool does + when to use it + parameters
- Examples in description
- Avoiding ambiguity
- Tool naming conventions

#### 4.5 Building Tool Libraries
- Web search (Tavily, SerpAPI, Brave, You.com)
- Calculator
- Code execution (sandboxed via E2B, Daytona)
- File system tools (read, write, list)
- HTTP/API tools
- Database query tools
- Calendar tools
- Email tools

#### 4.6 Multi-Step Tool Use
- LLM calls tool → gets result → calls another tool
- Building the execution loop
- Maximum iterations safety
- Tool result formatting

#### 4.7 Parallel Tool Calls
- LLM calls multiple tools at once
- Implementation pattern
- When parallel makes sense vs sequential
- Result aggregation

#### 4.8 Tool Error Handling & Patterns
- Tool returns error → LLM retries or asks user
- Tool unavailable
- Tool returns ambiguous data
- Tool timeout
- Validating tool args before execution

**Mastery Check:** Build an agent with 5 tools (weather, calculator, search, code execution, email-send) that correctly handles a multi-step request like "Find the temperature in Mumbai and Tokyo, calculate the difference, and email me the result."

---

## 🟡 LEVEL 5 — RAG & VECTOR DATABASES (Intermediate)

> **Goal:** Build Q&A systems over your own documents.
> **Time:** Week 5-6 — ~15 hours total.

### Topics

#### 5.1 What is RAG?
- Retrieval-Augmented Generation
- Why: LLMs don't know your private docs
- The RAG loop (query → retrieve → augment → generate)
- RAG vs Fine-tuning vs Long context
- When to use which

#### 5.2 Embeddings Deep Dive
- How embeddings encode semantics
- Embedding model selection
- OpenAI text-embedding-3 (small, large)
- Cohere embed-multilingual-v3
- Voyage AI voyage-3
- Open-source: BGE, MiniLM, mxbai
- Domain-specific embeddings (medical, legal, code)
- Cost & latency comparison

#### 5.3 Chunking Strategies
- Why chunking matters
- Fixed-size chunking
- Sentence-based chunking
- Paragraph-based chunking
- Recursive character chunking
- Semantic chunking (Greg Kamradt's approach)
- Late chunking (Jina)
- Parent-child / hierarchical chunking
- Window-based with overlap
- Code-specific chunking (Tree-sitter)

#### 5.4 Document Parsing
- PDF parsing (PyMuPDF, Unstructured, LlamaParse)
- DOCX parsing
- HTML / web scraping
- Markdown
- Code repositories
- Tables and figures
- OCR for scanned docs

#### 5.5 Vector Databases Compared
- Pinecone (managed, easy)
- Weaviate (full-featured, hybrid built-in)
- Qdrant (Rust, fast, open-source)
- Milvus (large-scale, complex)
- Chroma (dev-friendly, in-process)
- pgvector (Postgres extension — your existing stack)
- LanceDB (embedded, growing)
- FAISS (Facebook's lib, in-memory)
- Decision matrix

#### 5.6 Indexing Algorithms
- Flat index (exact, slow)
- IVF (Inverted File)
- HNSW (Hierarchical Navigable Small World)
- LSH (Locality-Sensitive Hashing)
- Quantization (PQ, SQ)
- Trade-offs (recall vs speed vs memory)

#### 5.7 Hybrid Search
- Combining vector + keyword (BM25)
- Reciprocal Rank Fusion (RRF)
- Weighted scoring
- When each search type wins

#### 5.8 Reranking
- Cross-encoder rerankers
- Cohere Rerank API
- BGE Reranker (open-source)
- When to add reranking
- Performance vs latency trade-off

#### 5.9 Query Transformation
- Query expansion (synonyms)
- Multi-query (generate variations)
- HyDE (Hypothetical Document Embeddings)
- Step-back prompting
- Sub-question decomposition

#### 5.10 Advanced Retrieval
- Self-Query Retriever
- Parent-Document Retriever
- Multi-vector retriever (one doc, multiple embeddings)
- Contextual retrieval (Anthropic's approach)
- Hierarchical retrieval

#### 5.11 RAG Evaluation
- Retrieval metrics (Recall@K, MRR, NDCG)
- Generation metrics (faithfulness, relevance)
- RAGAS framework
- TruLens
- Building eval test sets

#### 5.12 RAG Anti-Patterns
- Chunking too small / too large
- Bad chunking on code
- Single vector for huge documents
- No reranking on dense corpora
- Ignoring metadata
- Not citing sources

#### 5.13 GraphRAG (Intro)
- Knowledge graph + RAG
- When traditional RAG fails (multi-hop)
- Microsoft GraphRAG
- LightRAG
- Neo4j + LLM
- Deep dive in Level 8

#### 5.14 Multi-Modal RAG
- Image embeddings (CLIP, SigLIP)
- Search images by text
- PDF with tables and images
- Cross-modal retrieval

#### 5.15 Production RAG Architecture
- Indexing pipeline (offline)
- Query pipeline (online)
- Caching at each layer
- Re-indexing on doc updates
- Multi-tenancy
- Cost optimization

**Mastery Check:** Build a Q&A system over your company's documentation that answers questions accurately, cites sources, and works in <2 seconds.

---

## 🟠 LEVEL 6 — AGENT PATTERNS (Advanced)

> **Goal:** Build autonomous agents that plan, reason, and act.
> **Time:** Week 7-8 — ~12 hours total.

### Topics

#### 6.1 What is an Agent?
- Agent = LLM + Tools + Memory + Loop
- Agent vs Chatbot vs RAG
- Levels of agency (chat → tool use → autonomous → continuous)
- Common misconceptions

#### 6.2 ReAct Pattern
- Reason + Act + Observe loop
- Thought-Action-Observation format
- Why it works
- ReAct in raw API code (no framework)
- Pros and cons

#### 6.3 Plan-and-Execute Pattern
- Separate planner LLM from executor LLM
- Plan → execute steps → re-plan if needed
- When P&E beats ReAct
- Failure modes

#### 6.4 Self-Reflection & Critique
- Reflexion paper
- Generator-Critic pattern
- Self-improvement loop
- When self-critique helps / hurts
- Trade-off: cost vs quality

#### 6.5 Tree of Thoughts (Agent Style)
- Explore multiple paths
- Backtrack on failure
- BFS / DFS over thoughts
- When ToT beats CoT

#### 6.6 Voyager-Style Skill Discovery
- Agent builds its own library of skills
- Long-running agents
- Skill versioning
- Compounding capability

#### 6.7 Agent Memory Systems
- Short-term (conversation buffer)
- Long-term (vector store)
- Episodic (specific events)
- Semantic (general knowledge)
- Procedural (how to do things)
- Memory writing policies
- Memory retrieval policies

#### 6.8 Memory Implementations
- ConversationBufferMemory
- ConversationSummaryMemory
- Vector-based memory (Pinecone, Qdrant)
- MemGPT / Letta
- Mem0 framework
- Knowledge graph memory

#### 6.9 Multi-Step Reasoning
- Decomposition strategies
- HuggingGPT pattern
- Plan-and-Solve
- LLM-as-orchestrator

#### 6.10 Autonomous Loops
- When to stop?
- Max iterations
- Budget limits (tokens, time, cost)
- Confidence thresholds
- Human escalation triggers

#### 6.11 Safety & Guardrails
- Prompt injection defense
- Tool authorization
- Output validation
- Confidence calibration
- Refusal patterns
- PII redaction

#### 6.12 Human-in-the-Loop
- Approval gates
- Confidence-based pausing
- Override mechanisms
- Auditable agent logs

**Mastery Check:** Build a research agent that, given "Find the top 5 Python web frameworks in 2025 and rank them by community size, GitHub stars, and ease of learning," runs autonomously and produces a cited ranked list.

---

## 🟠 LEVEL 7 — FRAMEWORKS (Advanced)

> **Goal:** Master the production-grade agent frameworks.
> **Time:** Week 8-10 — ~25 docs across 6 frameworks.

### 7A. LangChain (5 docs)

#### 7A.1 LangChain Overview & LCEL
- LangChain Expression Language
- Runnables and chaining (`|` operator)
- Why LCEL > old chains

#### 7A.2 Models, Prompts, Output Parsers
- ChatModel abstraction
- PromptTemplate, ChatPromptTemplate
- Output parsers (Pydantic, JSON, list)

#### 7A.3 Document Loaders, Splitters, Embeddings
- 100+ loaders (PDF, web, GitHub, Notion...)
- Text splitters compared
- Embedding integrations

#### 7A.4 Vectorstores & Retrievers
- All vector DB integrations
- Self-query, parent-document retrievers
- Custom retrievers

#### 7A.5 LangChain Agents (Legacy)
- Old AgentExecutor (now superseded by LangGraph)
- When to still use LangChain agents
- Migration path to LangGraph

### 7B. LangGraph (6 docs) — MODERN STANDARD

#### 7B.1 Why LangGraph
- Graph-based vs chain-based
- Cyclic workflows
- State machines for agents

#### 7B.2 Nodes, Edges, State
- Defining state
- Node functions
- Conditional edges
- Entry/end points

#### 7B.3 Checkpoints & Persistence
- Saving state to DB
- Resuming from checkpoint
- Time-travel debugging

#### 7B.4 Human-in-the-Loop
- Interrupt before/after
- Approval workflows
- State editing

#### 7B.5 Multi-Agent in LangGraph
- Supervisor pattern
- Hierarchical teams
- Subgraphs

#### 7B.6 Production LangGraph
- Streaming
- LangGraph Studio
- Deployment (LangGraph Platform, self-hosted)

### 7C. CrewAI (4 docs)

#### 7C.1 CrewAI Basics
- Agents, Tasks, Crew
- Roles and goals
- Simple example

#### 7C.2 Processes & Workflows
- Sequential process
- Hierarchical process
- Custom process

#### 7C.3 Memory & Tools in CrewAI
- Memory types
- Custom tools
- Tool delegation

#### 7C.4 Production CrewAI
- Deployment patterns
- Monitoring
- When to pick CrewAI

### 7D. DSPy (4 docs)

#### 7D.1 What is DSPy
- Declarative prompts
- Compile prompts via optimization
- Why it's different

#### 7D.2 Signatures & Modules
- InputField, OutputField
- Predict, ChainOfThought, ReAct modules
- Composition

#### 7D.3 Optimizers (Compilers)
- BootstrapFewShot
- MIPRO
- Training data preparation
- Why this is the future of prompt engineering

#### 7D.4 DSPy Production Patterns
- DSPy + custom LMs
- Assertions
- Deployment

### 7E. Model Context Protocol (MCP) (3 docs)

#### 7E.1 What is MCP
- Anthropic's standard for tool/resource sharing
- Client/server architecture
- Why it matters (universal tool interface)

#### 7E.2 Building MCP Servers
- Tools, Resources, Prompts
- Python SDK
- TypeScript SDK
- Example: filesystem server, GitHub server

#### 7E.3 MCP in Production
- Claude Desktop integration
- Cursor + MCP
- Custom clients
- Security considerations

### 7F. Pydantic AI (1 doc)

#### 7F.1 Pydantic AI Overview
- Type-safe agents
- Dependency injection
- When to pick this

### 7G. Microsoft AutoGen (1 doc)

#### 7G.1 AutoGen Overview
- GroupChat between agents
- Code execution agents
- When to use

### 7H. Frameworks Compared (1 doc)

- Decision matrix
- Performance benchmarks
- Maturity comparison
- Migration paths

**Mastery Check:** Build the same multi-agent system in LangGraph AND CrewAI. Explain which is better for your use case and why.

---

## 🔴 LEVEL 8 — PRODUCTION LLMOps (Expert)

> **Goal:** Ship AI agents to real users.
> **Time:** Week 10-12 — ~18 docs.

### Topics

#### 8.1 LLMOps Overview
- What's different from MLOps
- Lifecycle (prompt dev → eval → deploy → monitor → iterate)
- Tooling landscape

#### 8.2 Observability — LangSmith
- Tracing LLM calls
- Hierarchical traces
- Dataset management
- Eval runs

#### 8.3 Observability — LangFuse (Open-Source)
- Self-hosted alternative to LangSmith
- LangFuse vs LangSmith
- Integration with LangChain / OpenAI

#### 8.4 Observability — Helicone, Arize, Weights & Biases Weave
- Comparison of platforms
- Picking for your needs

#### 8.5 Evaluation Strategies
- Offline eval (test sets, golden answers)
- Online eval (A/B tests, user feedback)
- LLM-as-judge
- Custom evaluators
- Trade-offs

#### 8.6 RAG-Specific Evaluation
- RAGAS framework
- Faithfulness, Answer Relevancy, Context Recall, Context Precision
- TruLens
- Synthetic test set generation

#### 8.7 Cost Optimization
- Model routing (cheap for easy, expensive for hard)
- Token budgeting per request
- Prompt compression
- Output length limits
- Distillation (small model trained on big model outputs)

#### 8.8 Caching Strategies
- Exact match cache
- Semantic cache (GPTCache)
- Anthropic prompt caching (~90% savings)
- OpenAI prompt caching (~50% savings)
- Multi-tier caching

#### 8.9 Safety — Prompt Injection
- Direct vs indirect injection
- Attack patterns (jailbreaks, "ignore previous instructions")
- Defenses (input sanitization, output validation)
- LLM guards (Guardrails AI, NeMo Guardrails)
- Defensive prompting

#### 8.10 Safety — Output Filtering
- Toxicity detection (OpenAI moderation, Llama Guard)
- PII redaction (Presidio)
- Hallucination detection
- Output schema enforcement

#### 8.11 Deployment — Inference Servers
- vLLM (open-source, fast)
- TGI (Text Generation Inference)
- SGLang (structured outputs)
- Triton Inference Server
- NVIDIA TensorRT-LLM

#### 8.12 Latency Optimization
- Streaming
- Speculative decoding
- KV-cache
- Quantization (INT8, INT4, GPTQ, AWQ)
- Continuous batching

#### 8.13 Fine-Tuning — When & How
- When to fine-tune (vs RAG, vs prompt eng)
- SFT (Supervised Fine-Tuning)
- DPO (Direct Preference Optimization)
- ORPO, KTO (newer methods)
- LoRA / QLoRA / DoRA
- Datasets preparation
- Evaluation post-tune

#### 8.14 Fine-Tuning Platforms
- OpenAI Fine-Tuning API
- Anthropic Fine-Tuning (limited)
- Together AI, Replicate
- Self-hosted (Axolotl, Unsloth)
- HuggingFace TRL

#### 8.15 GraphRAG Deep Dive
- Microsoft GraphRAG architecture
- Knowledge graph construction from text
- Community detection
- Local vs global queries
- Neo4j + LLM
- LightRAG

#### 8.16 Multi-Modal Production
- Voice agents (Whisper STT + TTS pipeline)
- Real-time voice (OpenAI Realtime API)
- Vision agents (GPT-4o, Claude vision in prod)
- Image generation (DALL-E, Stable Diffusion)
- Video understanding (Gemini)

#### 8.17 Compliance & Security
- GDPR considerations (data retention, right to delete)
- SOC 2 for AI products
- EU AI Act overview
- Healthcare (HIPAA) + AI
- Audit logging
- Data residency

#### 8.18 Red Teaming AI
- Adversarial testing
- Jailbreak attempts
- Bias testing
- Garak (open-source AI red team)
- Bug bounty programs for AI

**Mastery Check:** Deploy an AI agent to production with observability, evaluation suite, cost monitoring, safety guardrails, and a clear scaling story.

---

## 🚀 PROJECTS — Build Real Systems

> **Pick at least ONE to build as portfolio.**

### Project 1: Personal AI Assistant
- Stack: FastAPI + LangGraph + OpenAI + Postgres
- Features: Calendar, email, web search, conversation memory
- Time: 2-3 weeks

### Project 2: RAG Document Q&A Platform
- Stack: FastAPI + LangChain + pgvector + OpenAI
- Features: Multi-doc upload, accurate citations, sub-2s responses
- Time: 2-3 weeks

### Project 3: Multi-Agent Code Review Bot
- Stack: CrewAI + GitHub API + Claude
- Features: Multiple specialist agents review your PRs
- Time: 2 weeks

### Project 4: AI Agent with MCP
- Stack: MCP server + LangGraph + custom tools
- Features: Production-grade with MCP-standard tools
- Time: 2-3 weeks

### Project 5: Production RAG SaaS
- Stack: FastAPI + LangGraph + Qdrant + Postgres + Stripe
- Features: Multi-tenant, billing, eval dashboard
- Time: 4-6 weeks

### Project 6: Voice-First Agent
- Stack: OpenAI Realtime API + LangGraph + tools
- Features: Phone-call quality conversation, tool calls
- Time: 3 weeks

### Project 7: Coding Agent (Cursor-lite)
- Stack: Claude + filesystem tools + git tools
- Features: Multi-file refactoring, test generation
- Time: 4 weeks

### Project 8: Multi-Modal Document Processor
- Stack: GPT-4o + Anthropic vision + S3
- Features: PDFs with images/tables/charts → structured data
- Time: 3 weeks

---

## 📊 FINAL SUMMARY TABLE

| Level | Topic Area | Topics | Docs | Difficulty | Week |
|---|---|---|---|---|---|
| 1 | LLM Foundations | 7 | 7 | 🟢 Basic | 1 |
| 2 | Prompt Engineering | 10 | 10 | 🟢 Basic | 2 |
| 3 | LLM APIs & SDKs | 10 | 10 | 🟡 Intermediate | 3 |
| 4 | Tool Use & Function Calling | 8 | 8 | 🟡 Intermediate | 4 |
| 5 | RAG & Vector Databases | 15 | 15 | 🟡 Intermediate | 5-6 |
| 6 | Agent Patterns | 12 | 12 | 🟠 Advanced | 7-8 |
| 7 | Frameworks | 25 | 25 | 🟠 Advanced | 8-10 |
| 8 | Production LLMOps | 18 | 18 | 🔴 Expert | 10-12 |
| Projects | Build | 8 | 8 specs | 🚀 Build | 12+ |
| **TOTAL** | | **113** | **~113 docs** | | **12 wks** |

---

## 🎯 DIFFICULTY DISTRIBUTION

```
🟢 BASIC          ~17 docs  (Level 1-2)   → start here
🟡 INTERMEDIATE   ~33 docs  (Level 3-5)
🟠 ADVANCED       ~37 docs  (Level 6-7)
🔴 EXPERT         ~18 docs  (Level 8)
🚀 PROJECTS        ~8 specs  (build phase)
```

---

## 📚 ALREADY WRITTEN (Reference)

From the previous start of Level 1:
- ✅ `Level1_LLM_Foundations/01_what_is_an_llm.md` (~400 lines)
- ✅ `Level1_LLM_Foundations/02_tokens_embeddings.md` (~600 lines)
- ⏳ Level 1 remaining: 5 docs
- ⏳ Level 2-8 + Projects: ~106 docs

---

## 🎯 NEXT STEPS

You now have the **complete map** of the journey. Choose:

| Option | Action |
|---|---|
| **A** | Continue Level 1 (5 remaining docs) |
| **B** | Skip ahead to a specific topic of interest |
| **C** | Restructure the curriculum (any changes?) |
| **D** | Start a different level entirely |
| **E** | Just provide outlines + key concepts for each topic (faster, less depth) |

---

## 📝 NOTES ON CURRICULUM DESIGN CHOICES

### Why this order?
- **Level 1-2** before APIs because you need to understand LLMs before calling them.
- **Level 3** raw APIs before **Level 7** frameworks because frameworks abstract things you need to know.
- **Level 4** tool use before **Level 5** RAG because RAG uses tool-like patterns.
- **Level 5** RAG before **Level 6** agents because agents often use RAG.
- **Level 6** patterns before **Level 7** frameworks because frameworks implement patterns.
- **Level 8** production at end because all prior must work first.

### What's NOT covered?
- **Deep ML / Training models from scratch** — outside scope. We use pre-trained models.
- **Mathematical theory** — not needed for application engineering.
- **Specific cloud provider deep dives** (Bedrock, Vertex AI) — covered briefly; pick one for your work.
- **Image/Audio generation training** — Stable Diffusion, etc. are referenced but not core.

### Bias toward
- Production over research.
- Application engineering over pure ML.
- Open standards (MCP) over vendor lock-in.
- 2024-2025 best practices over older tutorials.

---

**This is your map. Now: where do you want to start digging deep?**
