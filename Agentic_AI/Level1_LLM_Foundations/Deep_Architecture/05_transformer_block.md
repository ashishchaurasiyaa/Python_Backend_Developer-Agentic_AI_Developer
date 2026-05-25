# Deep Architecture — Doc 5: The Full Transformer Block

> **Goal:** Attention is one piece. Ek poora transformer block mein: LayerNorm, Multi-head Attention, FFN, Residuals — sab kaise fit hote hain.

---

## 1. One Block — The Picture

```
        ┌─────────────────────────┐
input → │  → LayerNorm            │
        │  → Multi-Head Attention │
        │  → Add input (residual) │ ← intermediate
        │  → LayerNorm            │
        │  → Feed-Forward NN      │
        │  → Add (residual)       │ ← output of this block
        └─────────────────────────┘
              ↓
        Next block (96 of these!)
```

This **block** is repeated 96+ times. Each block transforms the token representations a bit more.

---

## 2. The Pieces

A transformer block has 4 main components:
1. **Layer Normalization** (×2)
2. **Multi-Head Attention** (covered in Doc 4)
3. **Feed-Forward Network (FFN)**
4. **Residual Connections** (skip connections)

Let's break each down.

---

## 3. Layer Normalization

**Problem:** As we stack many layers, activations can become extreme (very large or small numbers). This causes:
- Vanishing/exploding gradients during training
- Numerical instability

**Solution:** Normalize the values before each layer.

### LayerNorm formula:
```python
def layer_norm(x, gamma, beta, eps=1e-5):
    # x shape: [N, hidden_dim]
    mean = x.mean(dim=-1, keepdim=True)
    var = x.var(dim=-1, keepdim=True)
    x_normalized = (x - mean) / sqrt(var + eps)
    return gamma * x_normalized + beta
```

In words:
1. Compute mean and variance of the vector
2. Subtract mean, divide by std → zero-mean, unit-variance
3. Scale by `gamma` and shift by `beta` (learned parameters)

**Result:** Activations stay in a reasonable range, regardless of layer depth.

---

## 4. RMSNorm (Modern Variant)

Used by Llama, modern models:
```python
def rms_norm(x, gamma, eps=1e-5):
    rms = sqrt(mean(x²) + eps)
    return gamma * x / rms
```

Simpler than LayerNorm:
- No mean subtraction
- No `beta` (no shift)
- ~10% faster

Quality similar. Now standard in modern open-source models.

---

## 5. Pre-Norm vs Post-Norm

The position of LayerNorm matters:

### Post-Norm (Original 2017 Transformer)
```
output = LayerNorm(input + Attention(input))
```

### Pre-Norm (Modern)
```
output = input + Attention(LayerNorm(input))
```

**Pre-Norm wins** for stability in deep networks (96+ layers).

GPT-2, GPT-3, GPT-4, Claude, Llama all use **Pre-Norm**.

---

## 6. Feed-Forward Network (FFN)

After attention, each token's vector goes through a small neural network:

```python
def ffn(x, W1, b1, W2, b2):
    # x shape: [N, hidden_dim] = [N, 12288]
    
    # Project UP to 4x dimension
    hidden = x @ W1 + b1   # Shape: [N, 4*hidden_dim] = [N, 49152]
    
    # Activation function
    hidden = activation(hidden)
    
    # Project BACK DOWN
    output = hidden @ W2 + b2  # Shape: [N, hidden_dim] = [N, 12288]
    
    return output
```

### Key properties:
- **Up-projection by 4x** (standard)
- **Activation in middle** (non-linearity)
- **Down-projection back to original dim**
- **Each token processed INDEPENDENTLY** (unlike attention)

### Parameter count:
```
W1: [12288, 49152]  = 600M params
W2: [49152, 12288]  = 600M params
Total: ~1.2B params per FFN
```

**FFN has WAY MORE parameters than attention.** Most of an LLM's parameters are in FFN!

For GPT-3 (175B params):
- ~30% in attention
- ~65% in FFN
- ~5% in embeddings

---

## 7. Activation Functions

The middle activation in FFN matters. Evolution:

### ReLU (Old)
```python
def relu(x):
    return max(0, x)
```
- Simple, fast
- Dead neurons problem (always 0)

### GELU (GPT-2, GPT-3, BERT)
```python
def gelu(x):
    return 0.5 * x * (1 + tanh(sqrt(2/π) * (x + 0.044715 * x³)))
```
- Smoother than ReLU
- Better gradients

### SwiGLU (Llama, Modern)
```python
def swiglu(x, W1, W2, W3):
    return (silu(x @ W1) * (x @ W2)) @ W3

def silu(x):
    return x * sigmoid(x)
```
- "Gated" activation
- Slightly better quality
- Used in PaLM, Llama, modern models

**Note:** SwiGLU FFN has 3 matrices (W1, W2, W3) instead of 2.

---

## 8. Residual Connections (Skip Connections)

**Critical idea** from ResNet (2015):

```python
def block(x):
    attn_out = MultiHeadAttention(LayerNorm(x))
    x = x + attn_out                          # ← Residual!
    
    ffn_out = FFN(LayerNorm(x))
    x = x + ffn_out                           # ← Residual!
    
    return x
```

The `x + something` is the residual connection.

### Why it matters:
1. **Gradient flow**: Allows gradients to flow back easily through many layers
2. **Easier learning**: Layer learns "what to ADD" rather than full transformation
3. **Identity initialization**: If new layer learns nothing, block = identity (passthrough)

Without residuals, training 96-layer networks would be essentially impossible.

---

## 9. The Complete Block — Code

```python
class TransformerBlock(nn.Module):
    def __init__(self, hidden_dim, n_heads):
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.attention = MultiHeadAttention(hidden_dim, n_heads)
        self.ln2 = nn.LayerNorm(hidden_dim)
        self.ffn = FeedForward(hidden_dim)
    
    def forward(self, x, mask=None):
        # Attention block with residual
        attn_out = self.attention(self.ln1(x), mask)
        x = x + attn_out
        
        # FFN block with residual
        ffn_out = self.ffn(self.ln2(x))
        x = x + ffn_out
        
        return x
```

**Each block has TWO residual connections:**
1. Around attention
2. Around FFN

---

## 10. What Happens INSIDE a Block (Walkthrough)

Input: token vector `[12288]`

```
Step 1: LayerNorm
  - Normalize to mean=0, var=1
  - Apply learned scale/shift
  
Step 2: Multi-Head Attention  
  - Token "looks at" all other tokens
  - Pulls relevant context info
  - Output: enriched vector [12288]
  
Step 3: Add residual (original input + attention output)
  - Token retains its core meaning + new context info
  
Step 4: LayerNorm again
  - Renormalize
  
Step 5: Feed-Forward Network
  - Project to 4x dim (49152)
  - Apply nonlinearity (GELU/SwiGLU)
  - Project back to 12288
  - This adds "computation" — model can do non-linear transformations
  
Step 6: Add residual
  - Final output of this block
```

The output has same shape as input. So we can stack many blocks.

---

## 11. What Each Block "Does" (Intuition)

Different layers learn different things. Research shows roughly:

### Early layers (1-30):
- Syntax, basic patterns
- Token-level features
- "What is this word?"

### Middle layers (30-70):
- Semantic concepts
- Coreference resolution (pronouns)
- Subject-verb agreement
- "What does this mean?"

### Late layers (70-96):
- Task-specific patterns
- Output preparation
- Complex reasoning
- "What should I say next?"

It's a **hierarchical** computation, like how vision CNNs go from edges → shapes → faces.

---

## 12. Where Are the Parameters?

For a hypothetical GPT-4 scale model (hidden=12288, layers=96, heads=96, head_dim=128):

### Per block:
- LayerNorm 1: ~24K params
- Attention (Q, K, V, O matrices): 4 × 12288² ≈ 600M
- LayerNorm 2: ~24K
- FFN (W1, W2): 2 × 12288 × 49152 ≈ 1.2B
- **Total per block: ~1.8B params**

### Across 96 blocks:
- 96 × 1.8B = **~170B params** in blocks

### Plus:
- Embedding: ~1.2B
- Output projection: ~1.2B (often shared with embedding)

**Grand total: ~170-175B params** (matches GPT-3's reported size; GPT-4 is larger likely via Mixture of Experts).

---

## 13. Mixture of Experts (MoE) — Modern Twist

Some models (GPT-4 rumored, Mixtral) use **MoE FFN**:

Instead of one FFN per block:
```
For each token, a "router" picks 2-8 "expert" FFNs out of 8-64 available.
Only those experts compute. Saves compute.
```

```
Standard:  Each token → 1 FFN
MoE:       Each token → top-K out of N experts → weighted combination
```

**Benefits:**
- Same total params but only fraction active per token
- Higher capacity with same compute
- Specialization (different experts learn different things)

**Drawback:**
- More complex
- Memory still needed for all experts

---

## 14. Forward Pass Through a Block — Numbers

For one token through a GPT-4 scale block:

```
LayerNorm:           ~24K ops
Attention:           ~600M ops (Q,K,V projections + attention math)
FFN:                 ~1.2B ops (2 matrix multiplies)
LayerNorms + adds:   ~50K ops

Total per block:    ~1.8B ops per token
```

Through 96 blocks: ~170B ops per token!

A GPU like H100 does ~1000 TFLOPS = 10^15 ops/sec.

```
170B / 10^15 = 0.17 ms per token (theoretical minimum)
```

In practice, ~10-50 ms per token due to memory bandwidth, batching, etc.

---

## 15. Block Variants (Different Models)

### Standard (GPT, BERT)
- Attention + FFN as described

### GLU/SwiGLU FFN (Llama, modern)
- FFN uses gated linear units (3 matrices instead of 2)

### MoE Blocks (Mixtral, GPT-4 likely)
- FFN replaced by Mixture of Experts

### Parallel attention + FFN (some research)
- Attention and FFN run in parallel, then summed
- Faster, slightly different quality
- Used in PaLM

---

## 16. Why Two Sub-layers? (Attention + FFN)

Why not just attention? Why not just FFN?

**Attention** = communication between tokens (info exchange)
**FFN** = computation within each token (processing what was received)

You need BOTH:
- Pure attention: tokens see each other but can't compute much
- Pure FFN: tokens process info but can't share

Like a team meeting:
- Attention = listening to teammates
- FFN = thinking about what you heard
- Repeat

---

## 17. Dropout (Training Only)

During training, **dropout** randomly zeros some activations:
```python
# Training only
def dropout(x, p=0.1):
    mask = torch.rand_like(x) > p
    return x * mask / (1 - p)
```

Helps prevent overfitting.

During **inference (your API calls)**, dropout is disabled. So you don't see it in production.

---

## 18. Trainable Parameters of a Block

For one block (GPT-4 scale):
```
LayerNorm 1:    {gamma: 12288, beta: 12288}  →  ~24K params
W_Q:            [12288, 12288]                →  150M params
W_K:            [12288, 12288]                →  150M params
W_V:            [12288, 12288]                →  150M params
W_O:            [12288, 12288]                →  150M params
LayerNorm 2:    ~24K params
W1 (up):        [12288, 49152]                →  600M params
W2 (down):      [49152, 12288]                →  600M params

Total:          ~1.8B params per block
```

All these are learned during training.

---

## 19. Visualizing Activations

If you could "peek" inside a block:

```
Input token vector "Python":
[0.1, 0.3, -0.2, ..., 0.5]   (12288 numbers)

After LayerNorm 1:
[0.0, 0.1, -0.05, ..., 0.2]  (normalized)

After Attention:
[0.0, 0.4, -0.1, ..., 0.3]   (context infused — e.g., "programming language" features active)

After + residual:
[0.1, 0.7, -0.3, ..., 0.8]   (combined with original)

After LayerNorm 2:
[0.0, 0.3, -0.1, ..., 0.4]   (normalized again)

After FFN:
[0.05, 0.1, 0.3, ..., -0.1]  (processed via small NN)

After + residual:
[0.15, 0.8, 0.0, ..., 0.7]   (FINAL — output of this block)
```

Each block adds a bit more "understanding".

---

## 20. Common Misconceptions

### ❌ "Each block does the same thing"
NO. Different blocks learn DIFFERENT computations (early = syntax, middle = semantics, late = output prep).

### ❌ "FFN is less important than attention"
WRONG. FFN has MORE parameters than attention. It's the computational workhorse.

### ❌ "Layer Norm is just normalization"
LayerNorm has LEARNED parameters (gamma, beta) — it's a learned transformation, not just normalization.

### ❌ "Residual connections are optional"
You CAN'T train deep transformers without residuals. They're essential.

---

## 21. Interview Questions

1. **Q: What's in a transformer block?**
   - LayerNorm → Attention → Residual → LayerNorm → FFN → Residual

2. **Q: Why FFN if you have attention?**
   - Attention = info exchange between tokens. FFN = computation per token. Need both.

3. **Q: Pre-norm vs Post-norm?**
   - Pre-norm (LayerNorm before attention) is more stable for deep networks. Modern choice.

4. **Q: Why residual connections?**
   - Gradient flow, easier learning, identity initialization

5. **Q: Where are most parameters?**
   - FFN (~65%), then attention (~30%). Embeddings small.

---

## 22. Key Takeaways

✅ One block = LayerNorm → Attention → Residual → LayerNorm → FFN → Residual
✅ LayerNorm keeps activations stable (modern: RMSNorm)
✅ FFN: up-project 4x → activation → down-project. MOST params here.
✅ Activations: GELU (older), SwiGLU (modern Llama-style)
✅ Residual connections essential for deep networks
✅ Different blocks learn different things (syntax → semantics → output)
✅ MoE: alternative where FFN routes to expert sub-networks
✅ Per-block params (GPT-4 scale): ~1.8B
✅ 96+ blocks stacked = full model

**Next:** [06_layer_stacking_and_output.md](06_layer_stacking_and_output.md) — Stacking layers, output projection, logits
