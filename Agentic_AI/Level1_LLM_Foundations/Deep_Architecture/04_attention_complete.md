# Deep Architecture — Doc 4: Attention Mechanism (Complete)

> **Goal:** The HEART of transformers. Q, K, V matrices, attention math, masking, multi-head. **Yeh samjh gaye to LLM samajh aaya.**

---

## 1. Why Attention Matters

Without attention, processing "The cat sat on the mat" → each word processed in isolation.

With attention, when processing "sat", the model can **look at** "cat" (subject) and "mat" (location) to understand context.

**Attention = mechanism for tokens to communicate with each other.**

---

## 2. The High-Level Idea

For each token in the sequence:
1. **Look at** all other tokens
2. **Decide** which ones are important
3. **Combine** info from those important ones
4. **Update** your understanding of yourself

After this, each token's vector is **enriched** with relevant context.

---

## 3. The Library Analogy

Imagine a library:
- You (Query): want info on "cat"
- Books (Keys): each has a "topic" label
- Book content (Values): the actual info inside

Process:
1. **Compare** your Query with each book's Key
2. **Rank** books by relevance (higher match = more relevant)
3. **Read** the high-ranked books (weighted by relevance)
4. **Synthesize** info from them

That's attention in a nutshell.

---

## 4. Q, K, V — The Three Matrices

For each token's input embedding `x`, compute 3 versions:

```python
Q = x @ W_Q   # Query  — what am I looking for?
K = x @ W_K   # Key    — what do I offer/contain?
V = x @ W_V   # Value  — what info do I share?
```

Where `W_Q`, `W_K`, `W_V` are learned weight matrices.

```
Shape of x (one token):  [hidden_dim] = [12288]
Shape of W_Q, W_K, W_V:  [hidden_dim, head_dim] = [12288, 128]
Shape of Q, K, V (one token): [head_dim] = [128]
```

**Why three?**
- Query: "what I want"
- Key: "what I match against"
- Value: "what I actually give if matched"

Separating these gives flexibility — a token can want one thing (Q) but contribute differently (V).

---

## 5. Computing Attention — Step by Step

For a sequence of N tokens:
```
Q matrix: [N, head_dim]    (all tokens' queries)
K matrix: [N, head_dim]    (all tokens' keys)
V matrix: [N, head_dim]    (all tokens' values)
```

### Step 1: Compute attention scores
```python
scores = Q @ K.T    # Shape: [N, N]
# scores[i, j] = how much does token i want info from token j?
```

This is a **dot product** of each query with each key.

### Step 2: Scale
```python
scores = scores / sqrt(head_dim)
# Divide by sqrt(128) ≈ 11.3
```

**Why?** Without scaling, dot products of high-dim vectors can be huge → softmax gradient vanishes. Scaling keeps it stable.

### Step 3: Apply mask (for causal models like GPT)
```python
# For position i, can only attend to positions 0...i
# (Can't see the future!)
scores[i, j] = -inf for j > i
```

This is the **causal mask**. Critical for autoregressive generation.

### Step 4: Softmax
```python
attention_weights = softmax(scores, dim=-1)
# Shape: [N, N]
# Each row sums to 1
# attention_weights[i] = probability distribution over tokens
```

Now each token has a **probability distribution** over which other tokens to attend to.

### Step 5: Weighted sum of values
```python
output = attention_weights @ V    # Shape: [N, head_dim]
# Each token's output = weighted combination of all values
```

---

## 6. Visualizing Attention Weights

```
Sentence: "The cat sat on the mat"
              [0]  [1]  [2]  [3]  [4]   [5]
              "The" "cat" "sat" "on" "the" "mat"

When processing position 2 ("sat"):
attention_weights[2] = [
    0.05,  # "The" → low relevance
    0.50,  # "cat" → HIGH (subject!)
    0.10,  # "sat" → self
    0.05,  # "on"
    0.05,  # "the"
    0.25,  # "mat" → relevant (where sat?)
]

Sum = 1.0
```

The model learns these weights during training.

---

## 7. The Full Attention Formula

```
Attention(Q, K, V) = softmax(QK^T / √d_k + mask) · V
```

This is the famous equation from "Attention Is All You Need" (2017).

In Python:
```python
import torch
import torch.nn.functional as F

def attention(Q, K, V, mask=None):
    d_k = Q.size(-1)
    scores = Q @ K.transpose(-2, -1) / (d_k ** 0.5)
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))
    attention_weights = F.softmax(scores, dim=-1)
    output = attention_weights @ V
    return output, attention_weights
```

---

## 8. Causal Mask (For GPT-style Models)

```python
# For sequence length N=5:
mask = [
    [1, 0, 0, 0, 0],   # Position 0: only sees position 0
    [1, 1, 0, 0, 0],   # Position 1: sees 0, 1
    [1, 1, 1, 0, 0],   # Position 2: sees 0, 1, 2
    [1, 1, 1, 1, 0],   # Position 3: sees 0, 1, 2, 3
    [1, 1, 1, 1, 1],   # Position 4: sees all
]
```

This **lower triangular** mask ensures the model can't "cheat" by looking ahead during training.

**Bidirectional (BERT-style):** No mask. Each token sees everything. Good for understanding tasks (classification).

**Causal (GPT-style):** Triangular mask. Required for generation tasks.

---

## 9. Multi-Head Attention

ONE attention computation is good. But what if we want to capture **different types** of relationships?
- Head 1: subject-verb relationships
- Head 2: position relationships
- Head 3: semantic similarity
- Head 4: pronoun resolution
- ...

Solution: **Multi-head attention** — do attention multiple times in parallel.

### How it works:
```python
hidden_dim = 12288
n_heads = 96
head_dim = hidden_dim // n_heads  # = 128

# Project to multiple Q, K, V — one set per head
# But we use SAME total params:
W_Q: [hidden_dim, hidden_dim]  # [12288, 12288]

Q_full = x @ W_Q  # [N, 12288]
# Split into 96 heads, each 128-dim
Q_heads = Q_full.reshape(N, 96, 128)

# Same for K, V

# Run attention for EACH head in parallel
outputs = []
for h in range(96):
    out_h = attention(Q_heads[:, h], K_heads[:, h], V_heads[:, h])
    outputs.append(out_h)

# Concatenate heads
concat = torch.cat(outputs, dim=-1)  # [N, 12288]

# Final projection
final = concat @ W_O  # [N, 12288]
```

### Why does this help?
- Each head learns DIFFERENT patterns
- Output is **richer** than single attention

### Real numbers:
| Model | Layers | Heads per layer | Head dim |
|---|---|---|---|
| GPT-2 small | 12 | 12 | 64 |
| GPT-3 | 96 | 96 | 128 |
| GPT-4 | 96+ | 96+ | 128 |
| Llama 3 8B | 32 | 32 | 128 |

So GPT-4 has 96 layers × 96 heads = **9,216 different attention computations** per forward pass!

---

## 10. What Different Heads Learn (Real Research)

Researchers studied trained models:
- **Some heads** track POSITIONAL info (which token is next to which)
- **Some heads** track SYNTACTIC relationships (subject-verb)
- **Some heads** track SEMANTIC similarity (related concepts)
- **Some heads** track LONG-RANGE dependencies (pronouns to antecedents)
- **Some heads** look weird / random — maybe redundant or noise

This is similar to how CNN filters in vision models learn different features (edges, textures, faces).

---

## 11. Computational Cost — The Big O

For sequence length N:
```
Q @ K.T:  [N, d_k] @ [d_k, N]  → O(N²·d_k)
softmax:  O(N²)
attention_weights @ V:  [N, N] @ [N, d_k]  → O(N²·d_k)

Total: O(N² · d_k) per head
```

**Key observation: O(N²)** in sequence length.

For:
- N = 1,000 → 1M operations
- N = 10,000 → 100M operations
- N = 100,000 → 10B operations

This is why **long contexts are expensive**.

This is **the** bottleneck of transformers. Many optimizations target this (Flash Attention, sparse attention, etc.).

---

## 12. KV Cache (Inference Optimization)

During **inference** (generating tokens one at a time):

Without KV cache:
```
Generate token 100:
  Recompute Q, K, V for all 100 positions
  Compute attention for all 100 × 100
  Wasteful! K, V for tokens 0-98 unchanged
```

With KV cache:
```
Generate token 100:
  Compute Q for only position 100
  Use CACHED K, V for positions 0-99
  Compute new K, V for position 100
  Attend new Q to all K, V
```

**Speedup:** N×

KV cache memory cost:
```
2 (K + V) × n_layers × n_heads × head_dim × seq_len × batch_size
```

For Llama 3 70B at 4K context: ~640 MB per request.

For a 100K context: ~16 GB per request. **This is huge** — limits concurrent users.

---

## 13. Grouped-Query Attention (GQA)

Modern optimization (used in Llama 2/3, Mistral):
- Multiple Query heads share the SAME Key/Value heads
- Reduces KV cache memory by ~8x

```
Standard multi-head:
  32 Q heads, 32 K heads, 32 V heads  →  32 KV pairs to cache

GQA with grouping=4:
  32 Q heads, 8 K heads, 8 V heads  →  8 KV pairs to cache (4x smaller)
```

Slight quality drop, big memory savings → enables longer contexts.

---

## 14. Multi-Query Attention (MQA)

Extreme version of GQA:
- ALL Q heads share ONE K/V head
- Tiny KV cache
- Bigger quality drop

Used in some early efficiency-focused models. Most have moved to GQA (better balance).

---

## 15. Flash Attention

Standard attention computes the full N×N attention matrix:
- Memory: O(N²) — too much for long sequences

**Flash Attention** (2022, by Tri Dao):
- Compute attention in **blocks**
- Never materialize full N×N matrix
- Re-compute parts during backward pass
- 2-4x faster, much less memory

**Now standard** in PyTorch, HuggingFace. You're using it without knowing!

---

## 16. Sliding Window Attention

For very long sequences:
- Each token only attends to nearby tokens (e.g., last 4096)
- Skip distant tokens

Used in Mistral, some Gemma models.

**Pros:** O(N · W) instead of O(N²)
**Cons:** Can't capture long-range dependencies

---

## 17. Cross-Attention (Encoder-Decoder)

In encoder-decoder models (like T5, original Transformer for translation):
- Encoder processes input (e.g., English)
- Decoder generates output (e.g., French)
- Decoder uses **cross-attention** to "look at" encoder output

```python
# Self-attention: Q, K, V all from same sequence
# Cross-attention: Q from decoder, K, V from encoder
```

Modern decoder-only LLMs (GPT, Claude) don't have cross-attention. Everything is self-attention.

---

## 18. Worked Example — Tiny

Let's compute attention for "I love AI" with hidden_dim=4 (toy size).

```python
# Embeddings (made up)
x = [
    [0.1, 0.2, 0.3, 0.4],  # "I"
    [0.5, 0.6, 0.7, 0.8],  # "love"
    [0.9, 0.1, 0.2, 0.3],  # "AI"
]

# Random Q, K, V projection matrices (4 → 4)
W_Q = [...] # 4x4
W_K = [...] # 4x4
W_V = [...] # 4x4

# Compute
Q = x @ W_Q  # [3, 4]
K = x @ W_K  # [3, 4]
V = x @ W_V  # [3, 4]

# Scores
scores = Q @ K.T   # [3, 3]
# Example values:
# [[ 0.5,  0.3,  0.1],
#  [ 0.2,  0.8,  0.4],   # "love" attends most to itself, then "AI"
#  [ 0.1,  0.4,  0.7]]   # "AI" attends most to itself, some to "love"

# Scale by sqrt(4) = 2
scores = scores / 2

# Causal mask
scores = [[0.25, -inf, -inf],
          [0.10, 0.40, -inf],
          [0.05, 0.20, 0.35]]

# Softmax
attention_weights = [
    [1.00, 0.00, 0.00],  # "I" only attends to self
    [0.43, 0.57, 0.00],  # "love" attends 43% to "I", 57% self
    [0.21, 0.34, 0.44],  # "AI" attends to all 3
]

# Output
output = attention_weights @ V  # [3, 4]
# Each row is a weighted combination of V vectors
```

After this, "AI" has been enriched with info from "I" and "love" — it "knows" the context.

---

## 19. Attention Patterns Visualization

You can visualize attention as a heatmap:

```
         I    love   AI
   I  [ 1.0   0     0   ]
love  [ 0.4   0.6   0   ]
  AI  [ 0.2   0.4  0.4  ]
```

In real models, you'd see:
- Sometimes attention is "diagonal" (self-attention dominant)
- Sometimes "vertical" (everyone attends to one important token)
- Sometimes "horizontal" (one token attends broadly)
- Sometimes complex patterns

Tools like BertViz, Attention Visualizer let you explore real models.

---

## 20. Common Questions / Confusion

### Q: Why scale by √d_k?
Without scaling, dot products grow with dimension. Large scores → softmax becomes extreme (0/1) → gradients vanish. Scaling keeps softmax in useful range.

### Q: Why softmax?
- Converts arbitrary scores to probabilities
- Differentiable (training works)
- Emphasizes high-scoring options

### Q: Why "attention" name?
Inspired by cognitive science — humans selectively attend to parts of input.

### Q: Can attention be replaced?
Yes! Active research: Mamba (state-space), RWKV, Hyena — alternatives to attention. None has displaced transformer yet.

---

## 21. Key Takeaways

✅ Attention = mechanism for tokens to communicate
✅ Each token → Q, K, V vectors via learned projections
✅ Score = Q · K (dot product)
✅ Mask hides future tokens (causal LM)
✅ Softmax → probability distribution over attention
✅ Output = weighted sum of V vectors
✅ Multi-head: parallel attentions for different relationships
✅ **O(N²) cost** — sequence-length squared (expensive!)
✅ KV cache speeds inference massively
✅ GQA reduces KV memory
✅ Flash Attention = standard optimization
✅ This is the **core** mechanism of transformers

**Next:** [05_transformer_block.md](05_transformer_block.md) — Full transformer block (FFN, LayerNorm, Residuals)
