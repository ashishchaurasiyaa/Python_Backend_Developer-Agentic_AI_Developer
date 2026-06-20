# Deep Architecture — Doc 1: Request Flow (Network → Server → GPU)

> **Goal:** Tumhare code se LLM tak request kaise pohchti hai. Network, load balancing, batching — sab.

---

## 1. Client Side — Before Network Hits

When you call:
```python
client.chat.completions.create(model="gpt-4o-mini", messages=[...])
```

The OpenAI SDK (Python library) does:

### Step A: Build HTTP request
```python
# Internally constructs:
{
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "headers": {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "User-Agent": "OpenAI/Python 1.x.x"
  },
  "json": {
    "model": "gpt-4o-mini",
    "messages": [...]
  }
}
```

### Step B: HTTPS connection
- TCP handshake (3-way: SYN, SYN-ACK, ACK)
- TLS handshake (certificates, key exchange)
- HTTP/2 stream opened

This takes 50-200ms typically (depends on geography).

**Pro tip:** SDKs use **connection pooling** — first call slow, subsequent fast.

---

## 2. DNS + Routing to OpenAI

```
api.openai.com → Cloudflare DNS → Anycast → closest edge → OpenAI data center
```

OpenAI likely uses a CDN/edge provider (e.g. Cloudflare) for DDoS protection + global routing — exact provider officially confirmed nahi hai, illustrative samjho.

---

## 3. Edge Layer (Cloudflare / Their CDN)

Before hitting OpenAI's actual servers:
- **DDoS protection**
- **WAF** (Web Application Firewall) — block malicious patterns
- **TLS termination** (Cloudflare decrypts, internal traffic may be plain HTTP)
- **Geographic routing** — send Indian users to closest region

---

## 4. OpenAI Internal Infrastructure

```
External Request
       ↓
   Cloudflare
       ↓
   API Gateway (handles thousands of req/sec)
       ↓
   Auth Service (validate API key)
       ↓
   Rate Limiter (check RPM, TPM limits)
       ↓
   Request Router (which model? which cluster?)
       ↓
   Inference Cluster (GPUs)
```

---

## 5. Authentication

API key format: `sk-proj-...` (project keys) or `sk-...` (legacy)

Server-side process:
1. **Hash** the API key (SHA-256 or similar)
2. **Lookup** in database (which org owns this key?)
3. **Check** key is active, not revoked
4. **Verify** project has access to requested model
5. **Attach** org_id, project_id to request metadata

If invalid → 401 Unauthorized.

---

## 6. Rate Limiting

OpenAI tracks two limits per org:
- **RPM** (Requests Per Minute)
- **TPM** (Tokens Per Minute)

```python
# Pseudo-code at OpenAI's gateway
if redis.incr(f"rpm:{org_id}:{minute}") > LIMITS[org_id]["rpm"]:
    return 429
if redis.incrby(f"tpm:{org_id}:{minute}", estimated_tokens) > LIMITS[org_id]["tpm"]:
    return 429
```

Modern systems use **token bucket** or **sliding window** algorithms.

**For free tier:**
- gpt-4o-mini: 3 RPM, 200K TPM (very low!)

**For tier-3+:**
- 5,000 RPM, millions of TPM

---

## 7. Request Routing

Different models on different GPU clusters:

| Model | Likely GPUs | Cluster Type |
|---|---|---|
| gpt-4o-mini | A100 / H100 | Smaller, optimized for speed |
| gpt-4o | H100 | Larger, more memory |
| o1 / o3 | H100 (latest) | Specialized for reasoning |
| text-embedding-3 | A100 | Embedding-specific |

The router picks:
- Which cluster has capacity
- Geographic proximity (to reduce latency)
- Cost optimization (cheaper clusters when possible)

---

## 8. Batching at the Server

GPUs are MASSIVE — wasteful to process 1 request at a time.

**Continuous batching** (modern technique):
```
Time 0: Request A starts (prefill 100 tokens)
Time 1: Request A still going. Request B arrives → joins batch
Time 2: A finishes one token. B starts. Request C arrives → joins
Time 3: A, B, C all generate together
```

Multiple users' requests **share** the same forward pass through the model.

This is why latency varies — when busy, you wait in queue.

---

## 9. Tokenization (Pre-GPU)

Once on the server, before going to GPU:
```
Server-side Python:
  text = format_messages(request.messages)  # Apply chat template
  tokens = tokenizer.encode(text)             # ~5ms
  
  if len(tokens) > model.max_context:
    return 400 "Context length exceeded"
```

Tokenization is **CPU-side** — happens before sending to GPU.

---

## 10. Sending to GPU

Once tokenized:
```
CPU memory: tokens = [3923, 374, 13325, 30, ...]   # illustrative IDs (actual encoder output alag hoga)

CPU → GPU transfer (via PCIe):
  tokens_tensor.to(device='cuda:0')

GPU memory:
  - Model weights (already loaded, persistent)
  - Input tokens (just transferred)
  - KV cache (allocated for this request)
  - Activations (temporary)
```

Modern serving systems (vLLM, TGI, TensorRT-LLM) optimize this transfer.

---

## 11. The Forward Pass

We'll cover details in [Docs 3-6]. Brief:
- Tokens → Embeddings (matrix lookup)
- Through 96 transformer blocks
- Each block: attention + FFN (lots of matrix multiplication)
- Output: logits over vocabulary

For gpt-4o-mini, full forward pass per token:
- ~8B parameters × 2 (input + output) ≈ 16 GFLOPS
- On H100: ~1 ms per token

---

## 12. Streaming Setup

If `stream=true`:
```
Server keeps HTTP connection OPEN
For each generated token:
  - Run forward pass
  - Sample token
  - Convert to text
  - Send SSE (Server-Sent Event) chunk
  - Append to context, repeat

Client receives:
  data: {"choices": [{"delta": {"content": "Py"}}]}
  data: {"choices": [{"delta": {"content": "thon"}}]}
  data: {"choices": [{"delta": {"content": " is"}}]}
  ...
  data: [DONE]
```

This is **Server-Sent Events (SSE)** — HTTP protocol for streaming.

---

## 13. Logging & Monitoring (Server-Side)

OpenAI logs (likely):
- Request timestamp
- Model used
- Input/output token counts
- Latency
- Org/project ID
- Cost calculated

For **monitoring**:
- Cost per request
- Latency P50/P99
- Error rates
- GPU utilization

(They don't log content unless you opt-in via "Improve model" — privacy/safety reasons.)

---

## 14. Response Back to Client

After completion:
```
GPU → CPU: copy generated tokens
CPU: detokenize (tokens → text)
Build JSON response:
{
  "id": "chatcmpl-...",
  "choices": [...],
  "usage": {...}
}
HTTP/2 response → Cloudflare → Internet → Your machine
```

For streaming, the chunks went as generated. Final chunk sends `[DONE]`.

---

## 15. Latency Breakdown (Real Numbers)

For a "What is Python?" → 100 tokens response:

| Component | Time |
|---|---|
| DNS lookup | 0ms (cached) |
| TCP + TLS handshake | 100-200ms (first call) |
| Network to OpenAI | 30-80ms |
| Auth + Rate limiting | 5-10ms |
| Request routing | 1-5ms |
| Tokenization | <1ms |
| **First token (prefill)** | **50-200ms** |
| Each subsequent token | 10-30ms (decode) |
| 99 more tokens × 20ms | ~2 seconds |
| Detokenization | <1ms |
| Response back | 30-80ms |

**Total: ~2.5-3 seconds for 100 tokens.**

Optimizations possible:
- Connection reuse (skip handshake)
- Streaming (perceive faster)
- Closer geographic region

---

## 16. Self-Hosted (Llama, etc.)

If you self-host:
```
Your code → HTTPS → Your server (vLLM) → GPU
```

Skip OpenAI infra. But you handle:
- Auth / rate limiting yourself
- GPU procurement (~$2-10/hr per H100)
- Load balancing across multiple GPUs
- Failover, monitoring
- Model updates

---

## 17. Why Sometimes Calls Are Slow

Common reasons:
1. **First call** — handshake overhead
2. **Cold model** — your specific model not in cache, GPU loading it
3. **Other users** — sharing GPUs, you're in queue
4. **Long input** — prefill is expensive (proportional to input length²)
5. **Complex sampling** — top-p with low cutoff = slow
6. **GPU memory pressure** — many concurrent requests

---

## 18. Cost of a Single Request (OpenAI Side)

Rough estimates:
- GPU compute: ~$0.0001-0.001 per request
- Infrastructure (Cloudflare, etc.): negligible
- Storage / logging: <$0.0001

OpenAI charges $0.15/$0.60 per 1M tokens for gpt-4o-mini.

**Margin:** Healthy — they're profitable at this scale.

For tiny requests (10 tokens), per-request overhead dominates. For long requests (10K tokens), tokens dominate.

---

## 19. Why Self-Hosting Often Doesn't Save Money

Counter-intuitive, but:
- OpenAI batches thousands of requests on single GPU
- You batch 10
- They achieve 100x more GPU utilization
- Their per-token cost is much lower than yours

**Self-host pays off when:**
- Volume is HUGE (1B+ tokens/day)
- Data privacy is critical
- Latency-sensitive (run in same data center)
- Fine-tuning needs

---

## 20. Key Takeaways

✅ Request: Client SDK → DNS → Cloudflare → API Gateway → Auth → Rate Limit → Router → GPU
✅ Modern serving uses **continuous batching** — multiple users share GPU passes
✅ **Prefill is expensive** — proportional to input size² (attention)
✅ **Decode is cheaper** — one new token at a time
✅ Streaming uses **Server-Sent Events** (SSE) — chunks over HTTP
✅ First call slow (handshake), subsequent fast (connection pool)
✅ Network adds ~100-300ms baseline overhead
✅ Self-hosting rarely cheaper unless huge volume

**Next:** [02_tokenization_deep.md](02_tokenization_deep.md) — How text becomes tokens (BPE algorithm)
