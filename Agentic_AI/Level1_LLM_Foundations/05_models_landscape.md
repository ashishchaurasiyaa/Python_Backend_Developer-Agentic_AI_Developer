# Level 1 — Doc 5: LLM Models Landscape (2026)

> **Goal:** Current landscape — kaunse providers, kaunse models, kab use kare. Pricing comparison.

---

## 1. Major Providers

| Provider | Flagship Models | Strength |
|---|---|---|
| **OpenAI** | GPT-4o, GPT-4o-mini, o1, o3 | Largest ecosystem, reasoning models |
| **Anthropic** | Claude 3.5/4 Sonnet, Opus, Haiku | Safety, long context, prompt caching |
| **Google** | Gemini 2.0 Pro, Flash | Long context (2M), multi-modal |
| **Meta** | Llama 3.1/3.2/3.3 | Open-source, deploy yourself |
| **Mistral** | Mistral Large, Codestral | European, open + commercial |
| **DeepSeek** | DeepSeek V3, R1 | Cheap, capable reasoning |
| **Cohere** | Command R+ | Enterprise, RAG-optimized |

---

## 2. OpenAI Models (Detailed)

| Model | Use | Cost (input/output per 1M) | Context |
|---|---|---|---|
| **GPT-4o** | General flagship | $2.50 / $10 | 128K |
| **GPT-4o-mini** | Cheap, fast | $0.15 / $0.60 | 128K |
| **o1** | Hard reasoning | $15 / $60 | 200K |
| **o1-mini** | Reasoning, cheaper | $3 / $12 | 128K |
| **o3** | Latest reasoning | TBD (premium) | 200K |
| **text-embedding-3-small** | Embeddings | $0.02 | 8K |
| **whisper-1** | Speech-to-text | $0.006/min | — |
| **dall-e-3** | Image generation | $0.04-$0.12/image | — |

**Recommendation:**
- Default: **GPT-4o-mini** (cheap, fast, capable)
- Hard tasks: GPT-4o
- Math/code reasoning: o1-mini
- Embeddings: text-embedding-3-small

---

## 3. Anthropic Claude Models

| Model | Use | Cost (input/output per 1M) | Context |
|---|---|---|---|
| **Claude 3.5 Sonnet** | Best balance | $3 / $15 | 200K |
| **Claude 3.5 Haiku** | Fast, cheap | $0.25 / $1.25 | 200K |
| **Claude 3 Opus** | Most capable (legacy) | $15 / $75 | 200K |
| **Claude 3.7 Sonnet** (with extended thinking) | Reasoning | $3 / $15 + thinking | 200K |

**Killer features:**
- **Prompt caching** — 90% discount on cached tokens
- **Computer Use** — control desktop apps
- **Extended thinking** — built-in reasoning

**Recommendation:**
- Default: **Claude 3.5 Sonnet** (Sonnet beats Opus in most things)
- Cheap volume: Claude 3.5 Haiku
- Hard reasoning: Claude 3.7 with thinking enabled

---

## 4. Google Gemini Models

| Model | Use | Cost | Context |
|---|---|---|---|
| **Gemini 2.0 Pro** | Flagship | $1.25 / $5 | 2M |
| **Gemini 2.0 Flash** | Fast | $0.075 / $0.30 | 1M |
| **Gemini 2.0 Flash Thinking** | Reasoning | $0.075 / $0.30 | 1M |

**Killer feature:**
- **2M context window** — fit entire codebases
- Free tier (very generous)
- Native multi-modal (text + image + audio + video)

**Recommendation:**
- Long documents/code: Gemini 2.0 Pro
- Cost-sensitive: Gemini Flash
- Free experimentation: Gemini

---

## 5. Open-Source Models (Self-Host)

| Model | Size | Use |
|---|---|---|
| **Llama 3.1 405B** | 405B | Best open model |
| **Llama 3.1 70B** | 70B | Practical for most |
| **Llama 3.2 (11B, 90B)** | Multi-modal | Vision-enabled |
| **Mistral 7B / Mixtral** | 7B-50B | European, efficient |
| **Qwen 2.5** | 0.5B-72B | Strong multilingual |
| **DeepSeek V3** | 671B (MoE) | Cheap to run, strong reasoning |

**Why open-source:**
- Self-host (no API costs at scale)
- Privacy (data stays internal)
- Fine-tunable
- No vendor lock-in

**Drawback:**
- Need GPU infrastructure
- Slower than managed APIs
- Less capable (usually) than frontier closed models

**Where to run:**
- **Ollama** (local desktop)
- **vLLM** (production server)
- **Together AI, Groq, Replicate** (hosted open models)

---

## 6. Specialized Models

### Coding
- **Codestral** (Mistral) — code-specific
- **CodeLlama** (Meta) — Llama variant
- **Qwen2.5-Coder** — strong coding

### Embeddings
- **OpenAI text-embedding-3** (small/large)
- **Voyage AI** (state-of-the-art)
- **Sentence Transformers** (open source)
- **BGE** (open, multilingual)

### Translation
- **NLLB** (Meta, 200 languages)

### Speech
- **Whisper** (OpenAI, transcription)
- **ElevenLabs** (text-to-speech)
- **Cartesia** (low-latency TTS)

### Image
- **DALL-E 3** (OpenAI)
- **Stable Diffusion** (open)
- **Midjourney** (best quality, no API)
- **Flux** (open, high quality)

---

## 7. Multi-Modal Capabilities

| Input Type | Supporting Models |
|---|---|
| Text | All |
| Image input (vision) | GPT-4o, Claude 3.5, Gemini, Llama 3.2 |
| Audio input | Gemini, GPT-4o (with audio API), Whisper |
| Video input | Gemini 2.0, Claude (frames) |
| Audio output | GPT-4o (real-time audio), ElevenLabs |
| Image generation | DALL-E, Stable Diffusion, Flux |

---

## 8. Model Selection Decision Tree

```
Task:
├── General chat
│   ├── Cheap: GPT-4o-mini, Claude Haiku, Gemini Flash
│   └── Best: Claude 3.5 Sonnet (default), GPT-4o
│
├── Hard reasoning (math, code, science)
│   ├── Cheap: o1-mini, DeepSeek R1
│   └── Best: o1, o3, Claude 3.7 thinking
│
├── Long documents (>100K tokens)
│   ├── 200K: Claude 3.5, GPT-4o, o1
│   └── 2M: Gemini 2.0 Pro
│
├── Coding
│   ├── Default: Claude 3.5 Sonnet (best at code)
│   ├── Cheap: GPT-4o-mini
│   └── Specialized: Codestral, Qwen2.5-Coder
│
├── RAG / Q&A
│   ├── Embeddings: OpenAI text-embedding-3, Voyage
│   └── Generation: GPT-4o-mini, Claude Haiku
│
├── Multi-modal (vision)
│   ├── GPT-4o, Claude 3.5
│   └── Free: Gemini
│
├── Privacy / On-premise
│   └── Llama 3.1, Qwen, Mistral (self-host)
│
└── Real-time / low latency
    └── Groq (fastest hosted), Claude Haiku, Gemini Flash
```

---

## 9. Cost Comparison (Per 1M Tokens)

```
Cheapest:
- Gemini Flash:   $0.075 / $0.30
- GPT-4o-mini:    $0.15  / $0.60
- DeepSeek V3:    $0.27  / $1.10
- Claude Haiku:   $0.25  / $1.25

Mid-tier:
- Gemini Pro:     $1.25  / $5
- GPT-4o:         $2.50  / $10
- Claude Sonnet:  $3     / $15

Premium:
- o1-mini:        $3     / $12
- Claude Opus:    $15    / $75
- o1:             $15    / $60
- o3:             ~$30+  / $120+
```

**Pro tip:** Most tasks work with cheap models. Reserve expensive ones for hard problems.

---

## 10. Closed vs Open Source — Trade-offs

| Aspect | Closed (GPT/Claude) | Open (Llama/Mistral) |
|---|---|---|
| Capability | Frontier | 80-90% of frontier |
| Cost | API only | Pay for GPU |
| Speed | Hosted, fast | Depends on hosting |
| Privacy | Send to vendor | Keep internal |
| Reliability | Managed | DIY |
| Customization | Limited | Full fine-tuning |
| Compliance | Vendor's controls | Yours |

**Recommendation for startups:** Closed APIs initially, switch to open at scale if cost-sensitive.

---

## 11. Routing Strategy (Production)

Use **multiple models** in same app:

```python
def route_model(query_type, complexity):
    if query_type == "classification":
        return "gpt-4o-mini"  # Cheap, fast
    elif query_type == "code_generation":
        return "claude-3-5-sonnet"  # Best at code
    elif complexity == "hard_math":
        return "o1-mini"  # Reasoning
    elif query_type == "extraction":
        return "gpt-4o-mini"  # Good at structured outputs
    elif query_type == "embeddings":
        return "text-embedding-3-small"
    return "claude-3-5-sonnet"  # Default
```

**LiteLLM** library makes this easy — covered in Level 3.

---

## 12. Trends to Watch

1. **Cost falling 10x/year** — what costs $1 today, $0.10 next year
2. **Open-source catching up** — Llama 3.1 405B ≈ GPT-4 (2023)
3. **Reasoning models** — new paradigm, ~10x cost but qualitatively better
4. **Long context** — moving to 10M+ tokens
5. **Multi-modal native** — vision/audio not separate APIs
6. **Edge deployment** — running on phones (Apple Intelligence, Gemini Nano)

---

## 13. Key Takeaways

✅ Big 3: OpenAI, Anthropic, Google. Plus open-source (Llama, Mistral).
✅ Default models: GPT-4o-mini / Claude 3.5 Sonnet / Gemini Flash
✅ Hard reasoning: o1, o3, Claude 3.7 thinking
✅ Long context: Gemini 2.0 (2M tokens)
✅ Cost varies 100x+ between models — choose based on task
✅ Closed = best quality, open = privacy + cost at scale
✅ Production: route different tasks to different models

**Next:** [06_dev_environment_setup.md](06_dev_environment_setup.md) — Setup your dev env
