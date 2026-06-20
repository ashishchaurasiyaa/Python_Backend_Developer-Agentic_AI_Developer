# Deep Architecture — Doc 0: The Complete Journey of a Prompt

> **Goal:** Jab tum `client.chat.completions.create(...)` call karte ho, **exact kya hota hai** end-to-end. Network, server, GPU, math — sab.

---

## 1. The 30,000-Foot View

```
YOUR CODE                                            OPENAI SERVER (or Anthropic, etc.)
─────────                                            ─────────────────────────────────
                                                     
"What is Python?"  ─────HTTPS POST────►   ┌──────────────────────────────┐
                                          │ 1. Authentication            │
                                          │ 2. Rate limiting              │
                                          │ 3. Load balancer              │
                                          │ 4. Route to GPU cluster       │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 5. Tokenization              │
                                          │    text → token IDs           │
                                          │    "What is Python?" →        │
                                          │    [3923, 374, 13325, 30]    │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 6. Embedding lookup           │
                                          │    each token → 12,288-dim    │
                                          │    vector                     │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 7. Add positional encoding    │
                                          │    each vector + position info│
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 8. Transformer block × 96     │
                                          │    each block:                │
                                          │      - Multi-head attention   │
                                          │      - Feed-forward NN        │
                                          │      - Layer norms            │
                                          │      - Residual connections   │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 9. Final layer norm           │
                                          │ 10. Output projection         │
                                          │     vector → logits over     │
                                          │     vocabulary (100K+)        │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 11. Sampling                  │
                                          │     softmax + temperature     │
                                          │     + top-p → choose 1 token  │
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 12. Append, repeat steps      │
                                          │     6-11 for next token       │
                                          │     until [stop] or max_tokens│
                                          └────────────┬─────────────────┘
                                                       │
                                          ┌────────────▼─────────────────┐
                                          │ 13. Detokenization            │
                                          │     token IDs → text          │
                                          │ 14. JSON response back        │
                                          └────────────┬─────────────────┘
                                                       │
"Python is a language..."  ◄──────HTTPS response──────┘
```

---

## 2. Let's Trace ONE Real Example

**Input:**
```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is Python?"}]
)
```

**What happens, step by step:**

### Step 1: OpenAI SDK builds HTTP request
```http
POST /v1/chat/completions HTTP/2
Host: api.openai.com
Authorization: Bearer sk-...
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "What is Python?"}]
}
```

### Step 2: Request hits OpenAI infrastructure
- **DNS lookup** → api.openai.com → IP address
- **TLS handshake** → encrypted connection established
- **Load balancer** picks an API gateway server (probably AWS / GCP / Azure)

### Step 3: Authentication + Rate Limiting
- API gateway validates your API key (hashed lookup)
- Checks: are you within rate limits (RPM, TPM)?
- If yes → forward to inference cluster
- If no → 429 response

### Step 4: Request reaches inference orchestrator
- Picks which **GPU cluster** to use (based on model)
- gpt-4o-mini may run on smaller GPUs than gpt-4o
- Queues your request if all GPUs busy

### Step 5: Chat template formatting
Server converts your `messages` array to a specific text format. For gpt-4o-mini, looks something like:
```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
What is Python?<|im_end|>
<|im_start|>assistant
```

(Different models have different templates — Llama uses `[INST]`, Claude uses different)

### Step 6: Tokenization
The formatted text → numerical tokens (using OpenAI's `tiktoken` library):

```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode("What is Python?")
# Output (ILLUSTRATIVE example IDs — actual o200k_base IDs alag honge):
# [3923, 374, 13325, 30]
# 3923 = "What"
# 374  = " is"
# 13325 = " Python"
# 30   = "?"
```

But the WHOLE chat (with template) becomes ~20 tokens, not 4.

### Step 7: Tokens → Embeddings
Each token ID is **looked up** in a giant embedding matrix:
```
Embedding matrix shape: [vocab_size, hidden_dim]
                      = [100,000+, 12,288]   (ye GPT-3 175B ke numbers hain; GPT-4 internals public nahi — illustrative)

Token 3923 → embedding[3923] → vector of 12,288 numbers
```

Now you have a **sequence of vectors**, one per token:
```
[v1, v2, v3, v4, ...]  where each vi is 12,288-dim
```

### Step 8: Add Positional Encoding
Vectors don't know their position. Add position info:
```
v1 = embedding(token_1) + position_encoding(1)
v2 = embedding(token_2) + position_encoding(2)
...
```

Modern models use **RoPE** (Rotary Positional Embedding) — rotates the vectors based on position.

### Step 9: Through 96 Transformer Blocks
Each block does:
```
input → LayerNorm → Multi-Head Attention → Add input (residual)
      → LayerNorm → Feed-Forward NN → Add (residual)
      → output
```

The vectors get progressively richer in **contextual information**. By layer 96, each vector "knows" what every other token means in this context.

### Step 10: Final LayerNorm + Output Projection
Last layer's output vectors → projected to **vocabulary space**:
```
last_vector (12,288-dim) → projection_matrix (12,288 × 100,000+) → logits (100,000+ scores)
```

Each score = "how likely is THIS token to come next?"

### Step 11: Softmax + Sampling
Logits are raw scores. Convert to probabilities via softmax:
```
probabilities = softmax(logits / temperature)
```

Apply top-p / top-k filtering, then sample one token:
```
chosen_token = sample(probabilities)
# E.g., token 70192 = "Python" (probability 0.4)
```

### Step 12: Append + Repeat (Autoregressive)
The chosen token gets **appended** to input, and we go back to step 7:
```
Iteration 1: input = "<chat_template> What is Python?"
             → predicts "Python"

Iteration 2: input = "<chat_template> What is Python? Python"
             → predicts " is"

Iteration 3: input = "<chat_template> What is Python? Python is"
             → predicts " a"

...continues until [EOS] token or max_tokens
```

**This is autoregressive generation.** One token at a time.

### Step 13: Detokenization
After model says [EOS], collect all generated tokens:
```
[70192, 374, 264, 4221, ...] → "Python is a language..."
```

### Step 14: HTTP Response
Server packages response:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "gpt-4o-mini",
  "choices": [{
    "message": {"role": "assistant", "content": "Python is a language..."},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 45,
    "total_tokens": 65
  }
}
```

Sent back over HTTPS to your code.

### Step 15: Your SDK Parses
```python
response.choices[0].message.content  # "Python is a language..."
```

---

## 3. Key Numbers to Remember

For **GPT-4 scale** (~1.7T parameters):

> ⚠️ NOTE: ye numbers ANALYST ESTIMATES / GPT-3-derived hain — OpenAI ne GPT-4 internals officially disclose NAHI kiye. Hidden-dim 12,288 / 96 layers / 96 heads actually **GPT-3 175B** ke specs hain; 1.7T total + 280B active sirf **leaked estimates** hain. Concept ke liye theek, interview me fact ki tarah mat quote karna.

| Component | Size (estimated / illustrative) |
|---|---|
| Vocabulary size | ~100,000-200,000 tokens |
| Hidden dimension | 12,288 |
| Number of layers | 96-120 |
| Attention heads per layer | 96 |
| Total parameters | ~1.7T |
| Active params (per token, if MoE) | ~280B |

For **GPT-4o-mini** (smaller):
- Probably ~8B active params
- ~32 layers
- Hidden dim ~4096

For **Llama 3.1 8B**:
- Vocab: 128,000
- Hidden: 4096
- Layers: 32
- Heads: 32

---

## 4. Time Breakdown — Where Latency Goes

For a typical "What is Python?" → 100-token response:

```
Network round-trip:           50-100ms
Server-side overhead:         5-20ms
Tokenization:                 <1ms (fast)
Forward pass through layers:  
  - First token (prefill):    50-200ms (process entire input)
  - Each subsequent token:    10-50ms (just one new token)
Detokenization:               <1ms

Total: ~500-2000ms for 100 tokens (5-20 tokens/sec)
```

**Key insight:** First token = "prefill" = expensive. Then each new token is "decode" = much cheaper.

This is why **streaming feels fast** — you see tokens as they come, not waiting for everything.

---

## 5. What's Happening on GPU (Roughly)

```
GPU memory contains:
  - Model weights:        ~30-100 GB (depending on model)
  - KV cache:             grows with sequence length
  - Activations:          temporary, per request

Per token generated:
  - Load weights from GPU memory
  - Massive matrix multiplications (your token interacts with all weights)
  - GPU does these in parallel across thousands of cores
```

Modern serving stacks (vLLM, TGI) batch many requests together → GPU utilization stays high.

---

## 6. Multi-Modal Inputs (Vision, Audio)

If you send an image:
```
Image → Vision encoder (separate model) → image tokens (vectors)
                                          ↓
                                          mixed with text tokens
                                          → goes through same transformer
```

Audio is similar — encoded to tokens.

This is why GPT-4o can "see" and "hear" — it's all just tokens to the transformer.

---

## 7. Why It "Knows" Things (Briefly)

The model knows things because during **pre-training**, it saw:
- Trillions of words from internet
- Books, papers, code
- Pattern: "given context X, predicted token Y"
- Repeated for **billions of training iterations**

The **weights** in those 96 transformer blocks **encode** this learned pattern.

When you ask "What is Python?", the model's weights:
- Recognize "Python" pattern from training
- Recall related concepts (programming, language, code)
- Generate text that "matches" what it saw associated with this query

**It's not a database lookup.** It's a learned pattern that produces plausible text.

---

## 8. Why It Hallucinates

Sometimes the model produces plausible-sounding but FALSE text:
- Asked about obscure topics → may invent facts
- Pressed for specifics → may invent citations
- Outside training data → may guess

**Why?** The model is trained to produce **likely-looking text**, not necessarily **true text**. If "Python was created by James Joyce" is plausible-sounding, the model might output it (if it doesn't have strong knowledge).

**Defenses:** RAG (give it real data), tool use (let it look things up), structured output (force constraints).

---

## 9. The Documents in This Series

Now we'll deep-dive into each component:

| Doc | Topic |
|---|---|
| [01](01_request_flow.md) | Network → API → Server (the request flow) |
| [02](02_tokenization_deep.md) | Tokenization internals (BPE, vocab) |
| [03](03_embeddings_and_position.md) | Embeddings + Position encoding |
| [04](04_attention_complete.md) | Self-attention math (Q, K, V) |
| [05](05_transformer_block.md) | Full transformer block (FFN, LayerNorm, Residuals) |
| [06](06_layer_stacking_and_output.md) | Stacking layers, output projection |
| [07](07_sampling_and_generation.md) | Sampling (temperature, top-p, etc.) |
| [08](08_inference_optimizations.md) | KV cache, Flash Attention, batching |
| [09](09_training_briefly.md) | How weights are made (pre-train + RLHF) |

---

## 10. Key Takeaways

✅ Sending a prompt = network → server → tokenize → embed → 96 layers → sample → detokenize → return
✅ Generation is **autoregressive** — one token at a time
✅ "Prefill" (first token) is slow; "decode" (subsequent tokens) is fast
✅ Embeddings convert tokens to high-dim vectors (~12K dims for GPT-4)
✅ Transformer blocks progressively enrich token representations with context
✅ Sampling chooses next token from probability distribution
✅ Model doesn't "lookup" facts — it generates plausible text from learned patterns
✅ Hallucination = side effect of pattern matching, not truth-tracking

**Next:** [01_request_flow.md](01_request_flow.md) — Deep dive on the network/API layer
