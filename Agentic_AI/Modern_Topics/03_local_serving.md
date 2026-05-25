# Modern Topics — Doc 3: Local LLM Serving (Ollama, vLLM)

> **Goal:** Apne machine pe LLM chalao. Privacy, no API costs, custom models.

---

## 1. Why Local?

| Reason | Detail |
|---|---|
| **Privacy** | Data never leaves your machine |
| **Cost** | No per-token charges (just electricity) |
| **Customization** | Fine-tune freely |
| **Offline** | Works without internet |
| **Latency** | Faster for nearby use |
| **Compliance** | Some industries require it |

---

## 2. Ollama (Easiest)

**Best for:** Local desktop, prototyping.

### Install
```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from ollama.com
```

### Run a model
```bash
ollama pull llama3.1:8b   # Download 4.7GB
ollama run llama3.1:8b    # Chat in terminal
```

### Python API (OpenAI-compatible)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Required but unused
)

response = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Available models
- `llama3.1:8b`, `llama3.1:70b`, `llama3.1:405b`
- `mistral:7b`, `mixtral:8x7b`
- `qwen2.5:7b`, `qwen2.5:72b`
- `gemma2:9b`, `gemma2:27b`
- `phi3.5`, `codellama`, `deepseek-coder`
- Many more

---

## 3. Hardware Requirements

| Model | RAM | GPU | Quality |
|---|---|---|---|
| 3B (Phi-3.5) | 4GB | optional | Good for simple |
| 7-8B (Llama, Mistral) | 8GB | 8GB+ helpful | General use |
| 13B | 16GB | 16GB+ | Better quality |
| 30-70B | 32GB+ | 24GB+ GPU | Strong |
| 405B | 256GB | Multiple GPUs | Frontier |

For your MacBook (M-series):
- 16GB RAM → can run 8B models well
- 32GB+ → 13B comfortable, 70B with quantization

---

## 4. Quantization (Smaller = Faster)

Models come in different precisions:
- **Q8** = 8-bit (good quality, slower)
- **Q4** = 4-bit (smaller, slight quality loss) ← default
- **Q2** = 2-bit (tiny, more loss)

Ollama uses Q4 by default.

```bash
ollama pull llama3.1:8b-q8  # Higher quality
ollama pull llama3.1:8b-q2  # Smaller, faster
```

---

## 5. vLLM (Production)

**Best for:** Multi-user production serving.

### Install + serve
```bash
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct \
    --port 8000
```

### Why vLLM > Ollama for production
- **Continuous batching** (multiple users share GPU efficiently)
- **PagedAttention** (memory efficient)
- **Tensor parallelism** (multi-GPU)
- **Flash Attention** built-in
- **High throughput** (1000s req/sec)

### Client
```python
from openai import OpenAI
client = OpenAI(base_url="http://your-server:8000/v1", api_key="...")
# Use like OpenAI
```

---

## 6. Other Serving Frameworks

### TGI (Text Generation Inference) — Hugging Face
```bash
docker run --gpus all -p 8080:80 ghcr.io/huggingface/text-generation-inference:latest --model-id meta-llama/Llama-3.1-8B-Instruct
```

### TensorRT-LLM — NVIDIA
Fastest but more complex setup. Best for production scale.

### Ray Serve + DeepSpeed
For massive scale, distributed serving.

---

## 7. LiteLLM with Local Models

Use SAME code for local + cloud:

```python
from litellm import completion

# OpenAI
completion(model="gpt-4o-mini", messages=[...])

# Local Ollama (just change model name)
completion(model="ollama/llama3.1:8b", messages=[...])

# Local vLLM
completion(
    model="openai/meta-llama/Llama-3.1-8B-Instruct",
    api_base="http://localhost:8000/v1",
    messages=[...]
)
```

---

## 8. Fine-tuning for Local Models

### LoRA (Low-Rank Adaptation)
Tiny adapter layers — only ~1% of params trained.

```python
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B")

# Add LoRA adapters
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    bias="none"
)
model = get_peft_model(model, lora_config)

# Train on your data
# ...

# Save: only adapters (~50MB)
model.save_pretrained("./my_lora_adapter")
```

### Unsloth (Fast Fine-tuning)
2x faster than HuggingFace for fine-tuning:
```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/llama-3-8b-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
)
```

---

## 9. When to Use Local vs API

### Use Local when:
✅ Privacy critical (medical, financial)
✅ High volume (1B+ tokens/day) — break-even
✅ Custom fine-tuning needed
✅ Offline / on-device needed
✅ Cost-sensitive at scale

### Use API when:
✅ Building prototypes
✅ Lower volume
✅ Want frontier capability
✅ Limited compute resources

**Break-even calculation:**
```
API: $0.15/1M tokens × 1B/month = $150/month for gpt-4o-mini
Local: GPU rental $1000/month, but unlimited tokens

If using 5B+ tokens/month → local cheaper
```

---

## 10. Performance Comparison (Rough)

For Llama 3.1 8B:
- **Ollama on M3 Mac:** 30-50 tokens/sec
- **vLLM on H100:** 1000+ tokens/sec aggregate (with batching)
- **OpenAI gpt-4o-mini:** 100-150 tokens/sec (for you, server batches others)

---

## 11. Production Local Stack

```
Load Balancer (nginx)
       ↓
vLLM Server 1 (H100)
vLLM Server 2 (H100)
vLLM Server 3 (H100)
       ↓
Each: Llama 3.1 70B with LoRA adapters per tenant
```

Tools:
- **Kubernetes** for orchestration
- **Prometheus** for metrics
- **Grafana** for dashboards
- **NATS/Kafka** for queueing

---

## 12. Key Takeaways

✅ Ollama = easy local desktop (5-min setup)
✅ vLLM = production-grade serving
✅ OpenAI-compatible APIs (drop-in)
✅ Quantization (Q4) standard for size
✅ LoRA = cheap fine-tuning
✅ Break-even with API at ~5B tokens/month
✅ Use local for: privacy, scale, customization

**Next:** [04_memory_frameworks.md](04_memory_frameworks.md) — Mem0, Zep for persistent agent memory
