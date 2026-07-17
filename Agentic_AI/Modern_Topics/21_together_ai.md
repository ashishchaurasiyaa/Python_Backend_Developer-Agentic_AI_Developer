# Together AI — Open-Model Inference Provider

**Agentic AI · Modern Topics | Senior AI Engineer**

> Groq/HuggingFace/Ollama covered; Together AI sirf name-drop tha. Yeh file = **hosted open-weight models** (Llama, Qwen, DeepSeek, Mixtral) ek OpenAI-compatible API se.

---

## Quick Concepts

**WHAT:** Together AI ek **inference cloud** hai jo 100+ open-source models (Llama 4, Qwen, DeepSeek, Mixtral, FLUX images) ko serverless OpenAI-compatible API par serve karta hai. Plus fine-tuning + dedicated endpoints.

**WHY on the diagram:** Ollama = local (your machine); Groq = ultra-fast but limited model list; **Together = broadest open-model catalog, hosted, pay-per-token**. Open-weight models ko bina GPU khareede production me use karne ka easiest raasta.

---

## Where it sits

```
   OPEN-MODEL ACCESS OPTIONS
   ┌──────────────────────────────────────────────────────────┐
   │ Ollama      → local, private, free, your GPU/CPU          │
   │ HuggingFace → weights + Inference Endpoints (host yourself)│
   │ Groq        → fastest (LPU), small curated model list     │
   │ Together AI → biggest hosted open catalog, per-token, +FT │
   └──────────────────────────────────────────────────────────┘
                         │ all speak OpenAI-compatible API
                         ▼
                   your agent / RAG code (swap base_url + key)
```

- **OpenAI-compatible:** existing OpenAI SDK code me sirf `base_url` + `api_key` badlo → done
- **Serverless:** pay per token, no infra; **Dedicated endpoints** for steady high throughput
- **Fine-tuning:** LoRA/full FT on open models, then serve the adapter
- **Multimodal:** chat + embeddings + image (FLUX) endpoints

---

## Provider decision

| Need | Pick |
|------|------|
| Private / offline / free | Ollama |
| Absolute lowest latency | Groq |
| Widest hosted open models + FT | Together AI |
| Host your own weights | HuggingFace Endpoints |
| Frontier closed models | OpenAI / Anthropic / Google |

## Interview one-liners
- "Together AI serves open-weight models behind an OpenAI-compatible API — I swap base_url and reuse all my code."
- "Ollama for local, Groq for speed, Together for the widest hosted open catalog plus fine-tuning."
- "Serverless per-token for spiky traffic, dedicated endpoints for steady load."

See runnable example → [21_together_ai_practical.py](21_together_ai_practical.py)
