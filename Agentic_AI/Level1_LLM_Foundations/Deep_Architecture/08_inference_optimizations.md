# Deep Architecture — Doc 8: Inference Optimizations

> **Goal:** Production LLM serving optimizations — KV cache, Flash Attention, continuous batching, speculative decoding, quantization.

---

## 1. The Problem

Raw transformer inference is slow:
- 175B params = lots of compute
- O(N²) attention = quadratic in context length
- Need to generate tokens sequentially (can't parallelize easily)

Without optimizations:
- 100ms per token
- Long context = exponentially slower
- Limited concurrent users

With optimizations:
- 20-50ms per token
- Long contexts feasible
- 1000s of concurrent users on same GPU

---

## 2. KV Cache (Most Important)

### The naive way
```python
# Generate token 100:
for layer in layers:
    Q = compute_Q(all_100_tokens)     # Recompute
    K = compute_K(all_100_tokens)     # Recompute (WASTE!)
    V = compute_V(all_100_tokens)     # Recompute (WASTE!)
    attention = compute_attention(Q, K, V)
```

K and V for tokens 0-99 are **the same** as before! Why recompute?

### With KV cache
```python
# Per layer, cache K and V values
kv_cache = {
    "layer_0": {"K": tensor[100, head_dim], "V": tensor[100, head_dim]},
    "layer_1": {...},
    ...
}

# Generate token 100:
for layer in layers:
    # Only compute Q for new token
    Q_new = compute_Q(token_100_only)
    
    # Compute K, V for new token only
    K_new, V_new = compute_KV(token_100_only)
    
    # Append to cache
    kv_cache[layer]["K"] = concat(kv_cache[layer]["K"], K_new)
    kv_cache[layer]["V"] = concat(kv_cache[layer]["V"], V_new)
    
    # Attention: Q_new attends to ALL cached K, V
    attention = Q_new @ kv_cache[layer]["K"].T → attend → cached_V
```

**Speedup:** N× (where N is context length).

### Memory cost
```
KV cache size = 2 × n_layers × n_heads × head_dim × seq_len × batch × precision_bytes
              = 2 × 96 × 96 × 128 × 4096 × 1 × 2 bytes
              ≈ 19 GB per request at 4K context
```

For 100K context: ~470 GB. That's why long context is **memory-constrained**.

This is why **GQA** (Grouped Query Attention, Doc 4) matters — reduces KV cache size 4-8x.

---

## 3. Flash Attention

Standard attention computes full `N × N` matrix:
- For N=4096: 4K × 4K = 16M entries × 4 bytes = 64 MB
- For N=100K: 10B entries × 4 bytes = 40 GB!

**Flash Attention** (2022, Tri Dao):
- Compute attention in **tiles/blocks**
- Never store full N×N matrix
- Recompute parts as needed during backward (training)

**Result:**
- 2-4x faster than standard attention
- Memory drops from O(N²) to O(N)
- Enables much longer contexts

**Now standard** in PyTorch, vLLM, all production serving stacks.

```python
# You're using it without knowing:
torch.nn.functional.scaled_dot_product_attention(Q, K, V)
# Uses Flash Attention internally
```

---

## 4. Continuous Batching (vLLM-style)

### Naive batching (old way)
```
Time 0: User A submits request (100 tokens to generate)
Time 1: User B submits request → waits
        User A still generating
Time 5: User A done → User B starts
Time 10: User B done
```

GPU mostly idle during single-user generation.

### Continuous batching
```
Time 0: User A starts (100 tokens to generate)
Time 1: User B joins → both in batch
Time 2: User A finishes one token, B finishes one token
        User C joins → now 3 in batch
Time 3: User D joins → 4 in batch
Time 5: User A completes (gets EOS) → leaves batch
        Batch: B, C, D
...
```

**Multiple users share the GPU at the same time.** GPU utilization stays near 100%.

### Implementation
- Each request has its own KV cache
- Batch processes "next token for each active request"
- Requests join/leave dynamically

**Used in:** vLLM, TensorRT-LLM, all major production serving stacks.

---

## 5. Speculative Decoding

We covered this briefly in Doc 7. Details:

```
Big model (e.g., GPT-4o): slow, accurate
Small model (e.g., GPT-4o-mini): fast, ~80% accurate

Algorithm:
1. Small model generates 5 candidate tokens:
   "Python is a programming language"
   
2. Big model verifies ALL 5 in parallel (1 forward pass):
   - Token 1 "Python": YES (would have generated)
   - Token 2 "is":     YES
   - Token 3 "a":      YES  
   - Token 4 "programming": NO (would have generated "scripting")
   - Token 5 "language": (skipped — already wrong above)
   
3. Accept first 3 ("Python is a") + take big model's correction at position 4
4. Continue from there

Speedup: 2-3x
```

The math works out because the big model's verification of 5 tokens costs about the same as generating 1 token.

---

## 6. Quantization

Default model weights: FP16 (16 bits per number).

For Llama 3 70B: ~140 GB memory.

### Lower precision options:
| Format | Bits | Memory | Quality loss |
|---|---|---|---|
| FP16 | 16 | 1x | None |
| BF16 | 16 | 1x | None |
| INT8 | 8 | 0.5x | Tiny (~1%) |
| INT4 (GPTQ/AWQ) | 4 | 0.25x | Small (~3-5%) |
| INT2/INT3 (extreme) | 2-3 | tiny | Larger loss |

### How INT4 works
```python
# Convert FP16 weight (range [-1, 1]) to INT4 (16 levels)
weight_fp16 = 0.37
scale = 0.0625  # 1/16
weight_int4 = round(weight_fp16 / scale)  # = 6 (4 bits)

# To use:
recovered_fp16 = weight_int4 * scale  # = 0.375 (close to 0.37)
```

Modern quantization (GPTQ, AWQ):
- Smart selection of which weights to quantize
- Per-channel scaling
- Calibration on real data

**Result:** Run Llama 70B on a single 24GB GPU at INT4. Run smaller models on phones.

---

## 7. Prefill vs Decode Optimization

### Prefill (first token)
- Process entire input prompt
- Compute K, V for all positions (build cache)
- Heavy compute, runs in parallel across positions

### Decode (each subsequent token)
- Only compute Q for new position
- Use cached K, V
- Sequential, can't easily parallelize

**Different optimizations** for each:
- Prefill: compute-bound → benefits from fast GPUs
- Decode: memory-bound → benefits from fast memory

**vLLM splits these** — prefill and decode use different scheduling.

---

## 8. Paged KV Cache

KV cache memory is huge and fragmented:
```
Request A: 4K tokens → 19 GB cache
Request B: 8K tokens → 38 GB cache
Request C: 2K tokens → 9 GB cache

GPU memory: fragmented, hard to allocate efficiently
```

**PagedAttention** (from vLLM):
- Borrow concept from OS virtual memory
- KV cache stored in fixed-size "pages"
- Logical → physical mapping
- Easier to allocate, fewer fragmentation issues

**Allows:**
- Better memory utilization
- Higher batch sizes
- Smoother user experience

---

## 9. Multi-GPU Parallelism

For models too big for one GPU:

### Tensor Parallelism
```
Each layer's weights split across GPUs
GPU 1: First half of FFN, first half of attention heads
GPU 2: Second half
Etc.

For each forward pass: all GPUs work together
Communication overhead: significant
```

Used for: GPT-4, Llama 70B, etc.

### Pipeline Parallelism
```
GPU 1: Layers 1-24
GPU 2: Layers 25-48
GPU 3: Layers 49-72
GPU 4: Layers 73-96

Token flows: GPU 1 → 2 → 3 → 4
```

Like an assembly line. Each GPU specializes.

### Combined (Megatron-LM style)
- Tensor parallel within a node (4-8 GPUs)
- Pipeline parallel across nodes

Used for: largest models, training and inference.

---

## 10. Compilation & Kernels

PyTorch is convenient but slow. Production uses:

### CUDA Kernels (custom)
- Hand-written GPU code for hot paths
- Flash Attention is one
- Quantized matmul kernels
- Layer norm fused operations

### TensorRT-LLM (NVIDIA)
- Compiler that fuses operations
- Optimizes for specific GPU (H100 vs A100)
- 2-5x faster than naive PyTorch

### torch.compile (PyTorch 2.0+)
- PyTorch-native compilation
- Easier to use than TensorRT
- Less optimized but improving

---

## 11. Caching Beyond KV — Prompt Caching

Anthropic's prompt caching:
```python
system=[{"type": "text", "text": LONG_PROMPT, "cache_control": {"type": "ephemeral"}}]
```

Server caches the computed K, V for that prompt prefix.
Next call with same prefix → reuse cache.

**Savings:**
- 90% cheaper on input tokens
- Faster (skip prefill of cached portion)

Implementation:
- Hash the prefix
- Store K, V activations
- TTL: ~5 minutes
- Different cache per ORG (privacy)

This is a SERVER-side optimization that Anthropic exposes as a feature.

---

## 12. Disaggregated Serving (Cutting Edge)

Latest research/production:
- **Prefill servers** (compute-heavy GPUs like H100)
- **Decode servers** (memory-heavy, different config)

Why?
- Prefill is bursty (one big computation)
- Decode is steady (continuous tokens)
- Different optimization profiles

Each server specializes. Communication via fast networking.

Used by: OpenAI, Anthropic at scale (presumably). Not exposed to you.

---

## 13. Streaming Optimization

For streaming output to user:

```python
# Each token generated immediately sent via SSE
async def stream_response():
    while not done:
        next_token = generate_one_token()
        text = tokenizer.decode(next_token)
        yield f"data: {json.dumps({'content': text})}\n\n"
```

User perceives speed:
- First token in ~100ms
- Subsequent tokens stream as generated
- Total time same as non-streaming but FEELS faster

This is **TTFT** (Time To First Token) — the metric that matters most for UX.

---

## 14. Memory Allocator (vLLM PagedAttention Deep)

Standard CUDA malloc/free is slow + fragments memory.

PagedAttention uses:
- Pre-allocated memory pool
- Fixed-size blocks (e.g., 16 tokens × dim)
- Block table mapping (like page tables in OS)

```
Logical KV cache:    [0][1][2][3][4][5][6][7]
                      ↓  ↓  ↓  ↓  ↓  ↓  ↓  ↓
Block table:         [block_5][block_2][block_7][block_1]

Physical:            blocks scattered in memory pool
```

Allocate/free is O(1). Fragmentation minimized.

---

## 15. Why You Should Care (As Developer)

These optimizations affect:

### Latency you experience
- First-token latency: ~100-500ms
- Each subsequent: ~10-50ms
- Knowing this helps you build better UX (streaming!)

### Cost you pay
- Anthropic prompt caching: USE IT for long system prompts (90% savings)
- Batch API: half cost if you don't need real-time

### Capacity limits
- Long contexts cost more (KV cache memory)
- Free tier limited because of memory constraints

### Model choice
- Smaller models (Haiku, Flash) optimized for high throughput
- Larger models slower but higher quality

---

## 16. Production Serving Stack

Modern LLM serving:
```
Client (your app)
  ↓ HTTPS
Load Balancer (nginx/cloudflare)
  ↓
API Gateway (auth, rate limit)
  ↓
Inference Server (vLLM, TGI, TensorRT-LLM)
  - Continuous batching
  - PagedAttention  
  - Flash Attention
  - Speculative decoding
  - Quantization
  ↓
GPU Cluster (H100s)
  - Tensor parallel within node
  - Pipeline parallel across nodes
```

Major open-source stacks:
- **vLLM** — most popular, all the optimizations
- **TGI** (Hugging Face) — similar
- **TensorRT-LLM** (NVIDIA) — fastest if you can use it
- **Ollama** (local single-user) — simpler

---

## 17. Self-Host Cost vs API

If you self-host a 70B model:
- H100 GPU: ~$2-5/hr cloud, ~$30K to buy
- Power, cooling, ops: ~$1/hr
- One H100 serves maybe 50 concurrent users at decent latency

Per-token cost: depends heavily on utilization.

OpenAI/Anthropic batch THOUSANDS of users per GPU. Their per-token cost is much lower.

**You self-host when:**
- Privacy critical
- Custom fine-tuning
- Very high volume (1B+ tokens/day)
- Latency-sensitive (run in your data center)

Otherwise: pay per-token to API. Simpler, often cheaper.

---

## 18. Common Misconceptions

### ❌ "Longer context is free"
NO. KV cache grows linearly with context. Memory limited.

### ❌ "All providers same cost"
NO. Different model sizes, different optimizations. 10x cost differences common.

### ❌ "Streaming = faster generation"
NO. Same total time, just feels faster (sees tokens as generated).

### ❌ "Quantization always saves time"
Often yes, but conversion + dequantize has overhead. Net win for large models.

---

## 19. Interview Questions

1. **Q: What's KV cache?**
   - During generation, store K and V from previous tokens. Avoid recomputing.

2. **Q: How does Flash Attention work?**
   - Compute attention in tiles, avoid materializing full N×N matrix. O(N) memory.

3. **Q: Continuous batching?**
   - Multiple users' requests share same GPU forward passes. Higher utilization.

4. **Q: Speculative decoding?**
   - Small model drafts tokens, big model verifies in parallel. 2-3x speedup.

5. **Q: Quantization trade-offs?**
   - INT8/INT4 reduces memory 2-4x. Tiny quality loss. Required for consumer hardware.

---

## 20. Key Takeaways

✅ **KV cache** = store K, V per layer; avoid recompute. N× speedup.
✅ **Flash Attention** = compute attention in tiles. O(N) memory.
✅ **Continuous batching** = multiple users share GPU. High utilization.
✅ **Speculative decoding** = small model drafts, big verifies. 2-3x faster.
✅ **Quantization** (INT8, INT4) = lower precision for memory savings.
✅ **PagedAttention** = OS-like virtual memory for KV cache.
✅ **Prompt caching** (Anthropic) = 90% cheaper for repeated prefixes.
✅ **Tensor + pipeline parallelism** for huge models across multiple GPUs.
✅ Production: vLLM, TGI, TensorRT-LLM are standard.

**Next:** [09_training_briefly.md](09_training_briefly.md) — How those magic weights are learned
