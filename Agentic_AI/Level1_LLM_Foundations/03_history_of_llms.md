# Level 1 — Doc 3: History of LLMs (Quick Skim)

> **Goal:** 5-min read to understand how we got here. Helps in interviews + papers.

---

## Timeline at a Glance

```
1950s-2000s: Symbolic AI, rule-based, chatbots (ELIZA)
2010-2017:   RNN, LSTM era (sequence models)
2017:        Transformer paper "Attention Is All You Need"  ← Game changer
2018:        BERT (Google), GPT-1 (OpenAI)
2019-2020:   GPT-2, GPT-3 (175B params)
2022 (Nov):  ChatGPT launches → AI mainstream
2023:        GPT-4, Claude, Gemini, Llama race begins
2024:        Multi-modal (vision, audio), agents, tool use
2025-2026:   Reasoning models (o1, o3), MCP, AI agents production
```

---

## 1. Pre-Transformer (Before 2017)

### Rule-based (1960s-2000s)
- ELIZA (1966): pattern matching
- No "learning", just rules
- Limited domain

### Statistical NLP (2000s)
- N-gram models
- Hidden Markov Models
- Word2Vec (2013): word embeddings

### RNN/LSTM (2010s)
- Sequential processing
- Could handle context (somewhat)
- **Problem:** Slow, couldn't parallelize, forgot long context
- Used in early Google Translate

---

## 2. The Transformer Revolution (2017)

**"Attention Is All You Need"** — paper from Google researchers.

Key innovation: **Self-Attention** mechanism
- Each token can "look at" all other tokens
- Massively parallelizable (vs RNN's sequential)
- Captures long-range dependencies

This **changed everything**. Every modern LLM is a Transformer.

---

## 3. The Pretraining Era (2018-2020)

### BERT (Google, 2018)
- Bidirectional encoding
- Pretrained on Wikipedia + BookCorpus
- Excellent at understanding tasks (classification, NER)
- 110M and 340M parameters

### GPT-1, GPT-2 (OpenAI)
- Generative, autoregressive
- GPT-1: 117M params (2018)
- GPT-2: 1.5B params (2019)
- "Too dangerous to release fully" (initially)

### GPT-3 (OpenAI, 2020)
- **175 billion** parameters — huge leap
- Few-shot learning emerged
- Could do many tasks without fine-tuning
- ~$10M+ to train

**Insight:** Scale matters more than architecture changes.

---

## 4. The ChatGPT Moment (Nov 2022)

OpenAI released ChatGPT (GPT-3.5):
- Free, easy to use
- 100M users in 2 months (fastest in history)
- AI went mainstream overnight

**What was new?**
- Conversational interface
- RLHF (Reinforcement Learning from Human Feedback)
- Better at following instructions

---

## 5. The Race Begins (2023)

| Model | Company | Notable |
|---|---|---|
| GPT-4 | OpenAI | 1.7T params (estimated), multi-modal |
| Claude 1/2 | Anthropic | Long context (100k tokens) |
| Bard / PaLM 2 | Google | Multi-modal |
| Llama 1/2 | Meta | Open-source, 7B-65B |
| Mistral | Mistral AI | Smaller, efficient |

---

## 6. Multi-Modal & Agents (2024)

- **Vision:** GPT-4V, Claude 3 — process images
- **Audio:** Whisper (transcription), TTS models
- **Function calling:** LLMs can use tools
- **Long context:** 200k (Claude), 1M (Gemini 1.5), 2M (Gemini 2.0)
- **Open source:** Llama 3.1 405B rivals GPT-4

---

## 7. Reasoning Models (2024-2025)

OpenAI's **o1 / o3** series:
- "Reasoning" before answering
- Internal CoT
- 10x more expensive but smarter on math/code

Anthropic's **Extended Thinking** (Claude 3.7+):
- Similar concept
- `budget_tokens` for internal reasoning

This is the **current frontier**.

---

## 8. Agentic AI Era (2024-2026)

- **MCP** (Model Context Protocol) by Anthropic — standard for tools
- **Computer Use** (Claude) — control desktop apps
- **AI Agents** in production: customer support, coding, research
- **LangGraph, CrewAI, AutoGen** — agent frameworks
- **AI coding tools** (Cursor, Claude Code, GitHub Copilot)

---

## 9. Where We Are (2026)

- Models: GPT-4o, Claude 4.x, Gemini 2.x, Llama 3.x+
- Cost: ~10x cheaper than 2023 for same quality
- Capability: PhD-level reasoning on hard problems
- Agentic: AI completes hours-long tasks autonomously
- Embodied AI: robotics integration starting

---

## 10. Where We're Going

- **Smaller models** matching big ones (efficiency)
- **Better agents** (longer horizons, more reliable)
- **Multimodal** (video, 3D, sensor data)
- **Specialized** (coding-specific, science-specific models)
- **On-device** (Apple Intelligence, etc.)
- **Embodied** (robots powered by LLMs)

---

## 11. Why History Matters for You

Understanding history helps you:
1. **Read papers** — context for older terms (BERT, GPT-3)
2. **Interviews** — show breadth
3. **Predict trends** — see what's plateauing vs accelerating
4. **Cost decisions** — know which model generation has best price/performance

---

## 12. Key Takeaways

✅ Transformer (2017) = foundational architecture
✅ ChatGPT (2022) = AI mainstream
✅ 2023-26: Race + multi-modal + agents
✅ Current frontier: reasoning models + agentic AI
✅ Pattern: scale × better training data × algorithmic improvements

**Next:** [04_attention_transformers.md](04_attention_transformers.md) — Attention mechanism (no math, just intuition)
