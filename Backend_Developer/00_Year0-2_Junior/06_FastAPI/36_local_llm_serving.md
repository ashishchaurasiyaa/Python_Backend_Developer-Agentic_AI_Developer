# FastAPI — Local LLM Serving (vLLM, Ollama, llama.cpp, TGI)
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Local LLM** = self-hosted model (Llama, Qwen, Mistral) — privacy + cost control
- **vLLM** = production-grade Python inference server (PagedAttention, continuous batching)
- **Ollama** = developer-friendly local LLM runtime (one-command setup)
- **llama.cpp** = C++ CPU-first inference (also GGUF format)
- **TGI** = Text Generation Inference (Hugging Face's server)
- **GGUF** = quantized model format for llama.cpp
- **Quantization** = compress model (FP16 → INT8 → INT4) for less memory
- **Continuous batching** = serve multiple requests in one GPU batch (3-10x throughput)
- **PagedAttention** = KV-cache memory management (vLLM's innovation)
- **Tensor parallelism** = split model across GPUs

---

## Why Self-Host?

| Reason | Trade-off |
|---|---|
| **Privacy** — data never leaves your network | Need GPU infra |
| **Cost** — at scale cheaper than API | High upfront cost |
| **Latency** — no network roundtrip | Need ops expertise |
| **Customization** — fine-tune, custom tokenizers | Maintenance burden |
| **Compliance** — DPDP, HIPAA, on-prem | Less mature than API |
| **No rate limits** | You ARE the rate limit |

---

## Decision Matrix

| Need | Pick |
|---|---|
| Dev / experimentation | **Ollama** |
| Production at scale | **vLLM** |
| CPU-only inference | **llama.cpp** |
| Hugging Face ecosystem | **TGI** |
| Apple Silicon | **MLX** or Ollama |
| Edge / embedded | **llama.cpp** (GGUF) |
| Multi-model serving | **vLLM + LiteLLM proxy** |

---

## Interview Questions & Answers

### Q1: Ollama — fastest local LLM setup?

**Answer:** One command setup, OpenAI-compatible API.

```bash
# Install (macOS / Linux)
brew install ollama
# or curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.3:70b           # 40GB, needs 48GB+ RAM
ollama pull qwen2.5:7b              # 4.5GB, runs on 8GB RAM
ollama pull mistral:7b
ollama pull deepseek-r1:7b          # reasoning model

# Run server (auto-starts as systemd / launchctl)
ollama serve  # listens on :11434

# Test
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Why is the sky blue?",
  "stream": false
}'
```

**FastAPI integration:**
```python
from openai import AsyncOpenAI

# Ollama exposes OpenAI-compatible endpoint
client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # any string
)

@app.post("/chat/local")
async def chat_local(req: ChatRequest):
    response = await client.chat.completions.create(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": req.message}],
        max_tokens=512,
    )
    return {"text": response.choices[0].message.content}
```

**Pros:** Trivial setup, model management, OpenAI compat
**Cons:** Single-process; doesn't scale beyond 10 concurrent users

---

### Q2: vLLM — production-grade serving?

**Answer:** Highest throughput open-source inference server.

```bash
# Install
pip install vllm

# Serve OpenAI-compatible API
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.95 \
  --max-model-len 8192 \
  --port 8000 \
  --enable-prefix-caching \
  --quantization awq        # 4-bit quantization for less GPU memory
```

**Multi-GPU example (4× A100 80GB):**
```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --tensor-parallel-size 4 \                  # split across 4 GPUs
  --pipeline-parallel-size 1 \
  --max-num-seqs 256 \                        # batch up to 256 concurrent
  --max-num-batched-tokens 16384 \
  --enable-chunked-prefill \                  # better for long inputs
  --enable-prefix-caching                     # share KV cache for system prompts
```

**Programmatic Python API:**
```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3.3-70B-Instruct",
    tensor_parallel_size=4,
    quantization="awq",
    gpu_memory_utilization=0.95,
    enable_prefix_caching=True,
)

sampling = SamplingParams(temperature=0.7, max_tokens=512, top_p=0.95)

# Batch inference — 100 prompts in parallel
prompts = [f"Question {i}: ..." for i in range(100)]
outputs = llm.generate(prompts, sampling)

# vLLM batches automatically for max throughput
for output in outputs:
    print(output.outputs[0].text)
```

**Async client:**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(base_url="http://vllm:8000/v1", api_key="EMPTY")

async def call_vllm(messages: list[dict]) -> str:
    response = await client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=messages,
        max_tokens=1024,
        temperature=0.7,
    )
    return response.choices[0].message.content
```

**vLLM throughput (typical):**
- A100 80GB × 1, Llama 70B AWQ: ~50 tokens/sec/user × 32 concurrent = 1600 tok/sec total
- H100 × 4, Llama 70B FP16: ~80 tok/sec/user × 128 concurrent = 10K tok/sec

---

### Q3: llama.cpp + CPU inference?

**Answer:** CPU-only or GPU-offload; runs on Raspberry Pi to 64-core servers.

```bash
# Build (one-time)
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
make LLAMA_METAL=1                   # Apple GPU
# OR
make LLAMA_CUDA=1                    # NVIDIA GPU
# OR
make                                  # CPU only

# Download GGUF model (quantized)
wget https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf

# Run server
./llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf \
  --host 0.0.0.0 --port 8080 \
  -c 4096 \                          # context window
  -ngl 32 \                          # GPU layers (0 = CPU only)
  --n-batch 512
```

**GGUF quantization levels:**
| Format | Size | Quality | Use |
|---|---|---|---|
| Q2_K | smallest | poor | Embedded only |
| Q4_K_M | 1/4 | good (recommended) | Most use cases |
| Q5_K_M | smaller than Q8 | very good | Quality-critical |
| Q8_0 | half | near-perfect | Best CPU quality |
| F16 | full | perfect | If RAM allows |

**Python binding:**
```python
from llama_cpp import Llama

llm = Llama(
    model_path="./qwen2.5-7b-q4_k_m.gguf",
    n_ctx=4096,
    n_threads=8,
    n_gpu_layers=32,  # offload to GPU
)

output = llm(
    "Q: What is the capital of India? A:",
    max_tokens=100,
    stop=["Q:", "\n"],
)
print(output["choices"][0]["text"])
```

---

### Q4: GPU sizing — kitne GPUs chahiye?

**Answer:** Calculate based on model size + concurrent users.

**Memory math:**
```
Model memory ≈ Params × bytes/param
- FP16: 2 bytes/param   → 70B model = 140 GB
- INT8: 1 byte/param    → 70B = 70 GB
- INT4: 0.5 bytes/param → 70B = 35 GB

KV cache per request ≈ 2 × layers × heads × dim × seq_len × 2 bytes
- Llama 70B, 8K context: ~4 GB per concurrent request
```

**Sizing examples:**

| Model | Quant | Min GPU | Concurrent (rough) |
|---|---|---|---|
| Qwen 7B | FP16 | 1× T4 (16 GB) | 4 |
| Qwen 7B | INT4 | 1× T4 (16 GB) | 16 |
| Llama 70B | FP16 | 2× A100 80GB | 8 |
| Llama 70B | AWQ INT4 | 1× A100 80GB | 16 |
| Llama 405B | FP8 | 8× H100 | 32 |
| Mixtral 8x22B | FP16 | 4× A100 | 16 |

**Cost (approximate, 2026):**
- A100 80GB on AWS: ~$32/hour ($23K/mo per GPU)
- H100 on AWS: ~$95/hour ($69K/mo per GPU)
- Self-hosted (3-year amort): 40-60% cheaper than cloud GPU

---

### Q5: Multi-model serving with LiteLLM proxy?

**Answer:** Single endpoint, multiple backends.

```bash
pip install litellm[proxy]
```

```yaml
# litellm_config.yaml
model_list:
  # Local models
  - model_name: local-llama-70b
    litellm_params:
      model: openai/meta-llama/Llama-3.3-70B-Instruct
      api_base: http://vllm-prod:8000/v1
      api_key: EMPTY

  - model_name: local-qwen-7b
    litellm_params:
      model: openai/qwen2.5:7b
      api_base: http://ollama:11434/v1
      api_key: EMPTY

  # External fallback
  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-7
      api_key: os.environ/ANTHROPIC_API_KEY

router_settings:
  routing_strategy: simple-shuffle    # or "latency-based", "least-busy"
  fallbacks:
    - local-llama-70b: ["claude-opus"]  # fallback to Claude if local down

general_settings:
  master_key: sk-1234
  database_url: postgresql://litellm:pass@db/litellm
```

```bash
litellm --config litellm_config.yaml --port 4000
```

**Use from FastAPI:**
```python
client = AsyncOpenAI(
    base_url="http://litellm:4000/v1",
    api_key="sk-1234",
)

# Route based on tier
async def chat(req: ChatRequest, user: User):
    model = "local-qwen-7b" if user.tier == "free" else "local-llama-70b"
    return await client.chat.completions.create(model=model, messages=req.messages)
```

---

### Q6: Kubernetes deployment for vLLM?

**Answer:** GPU node pool + Horizontal Pod Autoscaler on queue depth.

```yaml
# vllm-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-llama-70b
spec:
  replicas: 2
  selector:
    matchLabels: { app: vllm-llama }
  template:
    metadata:
      labels: { app: vllm-llama }
    spec:
      nodeSelector:
        nvidia.com/gpu.product: NVIDIA-A100-SXM4-80GB
      tolerations:
      - key: nvidia.com/gpu
        operator: Equal
        value: "true"
        effect: NoSchedule
      containers:
      - name: vllm
        image: vllm/vllm-openai:v0.6.0
        command:
        - python
        - -m
        - vllm.entrypoints.openai.api_server
        - --model=meta-llama/Llama-3.3-70B-Instruct
        - --tensor-parallel-size=2
        - --quantization=awq
        - --max-num-seqs=128
        - --enable-prefix-caching
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: 2
            memory: 200Gi
          requests:
            nvidia.com/gpu: 2
            memory: 180Gi
        volumeMounts:
        - name: model-cache
          mountPath: /root/.cache/huggingface
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-creds
              key: token
        readinessProbe:
          httpGet: { path: /health, port: 8000 }
          initialDelaySeconds: 300    # model load takes 5 min
        livenessProbe:
          httpGet: { path: /health, port: 8000 }
          periodSeconds: 30
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: hf-cache-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: vllm-service
spec:
  selector: { app: vllm-llama }
  ports:
  - port: 8000
    targetPort: 8000

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vllm-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-llama-70b
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Pods
    pods:
      metric:
        name: vllm_running_requests
      target:
        type: AverageValue
        averageValue: "100"
```

**Custom metric for HPA:**
```python
# Expose Prometheus metric from vLLM-side proxy
from prometheus_client import Gauge
running_requests = Gauge("vllm_running_requests", "Current running requests")
```

---

### Q7: Quantization — kya choose karein?

**Answer:** Trade-off between size and quality.

```python
# Loading quantized models with vLLM
llm = LLM(
    model="TheBloke/Llama-2-70B-AWQ",
    quantization="awq",        # AWQ — best quality at 4-bit
    dtype="auto",
)

# Other quantization methods:
# - GPTQ: older, similar to AWQ
# - SqueezeLLM: experimental, best quality
# - bitsandbytes: development convenience (slower)
# - SmoothQuant: INT8 for activations
# - FP8: H100/H200 hardware-accelerated
```

**Comparison (Llama-70B, MMLU benchmark):**

| Quantization | Size | MMLU | vs FP16 | Speed |
|---|---|---|---|---|
| FP16 | 140 GB | 80.0 | baseline | 1.0x |
| FP8 | 70 GB | 79.8 | -0.2% | 1.5x |
| AWQ INT4 | 35 GB | 78.5 | -1.5% | 2.0x |
| GPTQ INT4 | 35 GB | 78.2 | -1.8% | 1.9x |
| GGUF Q4_K_M | 40 GB | 78.8 | -1.2% | varies |
| GGUF Q2_K | 25 GB | 73.0 | -7% (bad) | 2.5x |

**Recommendation:** AWQ INT4 for production (best quality/size).

---

### Q8: Monitoring + observability for local LLM?

**Answer:** Track GPU + request metrics.

```python
from prometheus_client import Counter, Histogram, Gauge
import GPUtil
import asyncio

# GPU metrics
gpu_memory_used = Gauge("gpu_memory_used_bytes", "GPU memory used", ["gpu_id"])
gpu_utilization = Gauge("gpu_utilization_percent", "GPU utilization", ["gpu_id"])
gpu_temp = Gauge("gpu_temp_celsius", "GPU temperature", ["gpu_id"])

# Request metrics
llm_requests_total = Counter("local_llm_requests_total", "Total requests", ["model", "status"])
llm_ttft_seconds = Histogram("local_llm_ttft_seconds", "Time to first token", ["model"])
llm_tokens_generated = Counter("local_llm_tokens_total", "Output tokens", ["model"])
llm_active_requests = Gauge("local_llm_active_requests", "Currently processing")

async def gpu_metrics_collector():
    """Run as background task."""
    while True:
        for gpu in GPUtil.getGPUs():
            gpu_memory_used.labels(gpu_id=gpu.id).set(gpu.memoryUsed * 1024 * 1024)
            gpu_utilization.labels(gpu_id=gpu.id).set(gpu.load * 100)
            gpu_temp.labels(gpu_id=gpu.id).set(gpu.temperature)
        await asyncio.sleep(15)

# In FastAPI proxy in front of vLLM
@app.post("/chat")
async def chat_with_metrics(req: ChatRequest):
    llm_active_requests.inc()
    start = time.time()
    first_token_time = None
    output_tokens = 0

    try:
        async for chunk in stream_from_vllm(req):
            if first_token_time is None:
                first_token_time = time.time() - start
                llm_ttft_seconds.labels(model=req.model).observe(first_token_time)
            output_tokens += 1
            yield chunk

        llm_requests_total.labels(model=req.model, status="success").inc()
        llm_tokens_generated.labels(model=req.model).inc(output_tokens)
    except Exception:
        llm_requests_total.labels(model=req.model, status="error").inc()
        raise
    finally:
        llm_active_requests.dec()
```

**Alerts:**
- GPU memory > 95% for 5 min → page (OOM imminent)
- GPU utilization < 20% for 10 min → ticket (overprovisioned)
- TTFT P95 > 3s → ticket
- Error rate > 1% → page

---

## Cost Comparison (10M tokens/day)

| Backend | Setup | Monthly cost |
|---|---|---|
| Claude Opus API | None | $22,500 |
| Claude Sonnet API | None | $4,500 |
| Self-hosted Llama 70B (1× A100) | Cloud | $23,000 + ops |
| Self-hosted Llama 70B (4× A100 owned) | CapEx ~$80K | $4,000 (power+ops) |
| Self-hosted Llama 7B Quantized | 1× T4 | $400 + ops |

**Break-even:** Self-hosting wins **only when** you process > 1B tokens/month consistently.

---

## When NOT to Self-Host

- < 100K tokens/day → API cheaper
- Spiky traffic → API auto-scales
- No GPU ops capability → API safer
- Need frontier models (GPT-4, Claude Opus) → no open equivalent
- Compliance allows API providers (BAA, DPA available)

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Model load takes 5+ min on pod start | Generous `readinessProbe` initial delay |
| OOM under burst load | Set `max-num-seqs` conservatively |
| KV cache fragmentation | Use PagedAttention (vLLM does this) |
| Long context = high memory | Cap `max-model-len`; chunk long inputs |
| Stale model after fine-tune | Versioned model deployment |
| Quantization breaks tool use | Test thoroughly post-quant |
| Cold start latency | Keep min replicas ≥ 2 |
| GPU hardware failure | Multi-AZ; auto-failover |
| Tokenizer mismatch with API | Use exact same tokenizer (verify) |

---

## Senior-level Checklist

- [ ] Right tool picked (Ollama dev, vLLM prod, llama.cpp CPU)
- [ ] Quantization chosen (AWQ INT4 typical)
- [ ] Tensor parallelism configured (multi-GPU)
- [ ] PagedAttention + continuous batching enabled
- [ ] Prefix caching for repeated system prompts
- [ ] HPA on `vllm_running_requests` metric
- [ ] GPU metrics in Prometheus + Grafana
- [ ] TTFT + throughput SLOs defined
- [ ] LiteLLM proxy for multi-model + fallback
- [ ] Health checks + liveness probes tuned for cold start
- [ ] Model files in PVC (avoid repeated downloads)
- [ ] Backup to API provider on local failure
- [ ] Cost monitoring (GPU hours, electricity)
- [ ] Fine-tune pipeline if needed

---

## Related Docs
- `31_llm_integration_fastapi.md` — base LLM patterns
- `32_function_calling_endpoints.md` — tools (note: smaller models worse at tool use)
- `34_rag_backend_architecture.md` — local embeddings (BGE, GTE)
- `01_Year3-4_Mid/04_DevOps/06_kubernetes_helm.md` — K8s GPU scheduling
- `01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md` — metrics infra

## External References
- vLLM: https://docs.vllm.ai
- Ollama: https://ollama.com
- llama.cpp: https://github.com/ggml-org/llama.cpp
- TGI: https://huggingface.co/docs/text-generation-inference
- LiteLLM: https://docs.litellm.ai
