# Deep Architecture — Doc 6: Layer Stacking & Output Projection

> **Goal:** 96 transformer blocks kaise compose karte hain. Aakhri layer ke baad — logits banane tak ka journey.

---

## 1. The Full Architecture

```
Input tokens
    ↓
[Embedding Layer]
    ↓
[+ Positional Encoding]      ← Doc 3
    ↓
[Transformer Block 1]         ┐
[Transformer Block 2]         │
[Transformer Block 3]         │  ← 96 blocks (Doc 5)
...                           │
[Transformer Block 95]        │
[Transformer Block 96]        ┘
    ↓
[Final LayerNorm]
    ↓
[Output Projection]            ← This doc
    ↓
[Logits over vocabulary]
    ↓
[Sampling]                     ← Doc 7
    ↓
Next token
```

---

## 2. Why Stack Many Layers?

Earlier we saw each block enriches token representations. Why 96?

**Empirical finding:** More layers = better quality (up to a point).

| Model | Layers | Notes |
|---|---|---|
| GPT-1 (2018) | 12 | Tiny by today's standards |
| GPT-2 (2019) | 48 | Medium |
| GPT-3 (2020) | 96 | Large |
| GPT-4 (2023) | 96+ | Wider AND deeper |
| Llama 3 8B | 32 | Smaller model, fewer layers |
| Llama 3 70B | 80 | Bigger needs more layers |

**Why diminishing returns?** After enough depth, additional layers add marginal value but cost a lot.

---

## 3. Information Flow Through Layers

Imagine processing: "The cat sat on the mat"

```
Layer 1-10:    Each token gathers basic info from neighbors
               "cat" learns it's a noun, near "The"
               
Layer 10-30:   Tokens start understanding roles
               "cat" learns it's the subject
               "sat" learns it's the verb
               
Layer 30-60:   Semantic relationships
               "cat" → animal, can sit
               "mat" → object, can be sat on
               
Layer 60-90:   Complex reasoning
               This is a complete grammatical sentence
               "cat" is the agent of "sit"
               
Layer 90-96:   Output preparation
               If we need to continue, likely tokens are:
               period, "and", "while", etc.
```

The exact dynamics are studied via "probing" — researchers extract layer activations and check what info is present.

---

## 4. Residual Stream Concept

Modern interpretability framing:
- The **input embedding** is added/modified by each block via residuals
- Each block READS from the residual stream, COMPUTES something, ADDS back
- The residual stream is the "shared workspace"

```
Block 1: stream += attention_out_1 + ffn_out_1
Block 2: stream += attention_out_2 + ffn_out_2
...
Block 96: stream += attention_out_96 + ffn_out_96

Final stream = sum of all blocks' contributions + initial embedding
```

This perspective makes it easier to think about **what each block contributes**.

---

## 5. Final LayerNorm

After the last transformer block, one more LayerNorm:
```python
output = LayerNorm(last_block_output)
```

**Why?** Stabilizes the final representation before the projection to vocabulary space.

---

## 6. Output Projection (LM Head)

The final transformation: vectors → vocabulary scores.

```python
# Each token's final vector → score for every vocabulary word
logits = output @ W_out + b_out

# Shapes:
output:  [N, hidden_dim]      = [N, 12288]
W_out:   [hidden_dim, vocab_size] = [12288, 100000]
logits:  [N, vocab_size]      = [N, 100000]
```

For each position, we get **100,000 scores** — one per possible next token.

---

## 7. Weight Tying (Optimization)

Many models **share** the input embedding matrix and output projection:
```python
# Standard: separate matrices
embedding = Embedding(vocab_size, hidden_dim)
lm_head = Linear(hidden_dim, vocab_size)

# Tied: same matrix used for both
embedding = Embedding(vocab_size, hidden_dim)
lm_head = embedding.weight.T   # Transpose of embedding!
```

**Why?** Saves ~1.2B params (for GPT-4 scale).

**Used in:** GPT-2, Llama, many others.

**Not used in:** GPT-3 (used separate matrices).

---

## 8. What Are Logits?

Logits = raw scores. NOT probabilities yet.

```python
# Example logits for next token after "The cat is"
logits = [
    5.2,   # token "happy"
    3.8,   # token "sleeping"
    7.1,   # token "very"
    1.2,   # token "purple"   ← unlikely but non-zero
    8.5,   # token "cute"     ← highest!
    -2.1,  # token "elephant"
    ...
    -10.5, # token "fjkdsf"   ← random garbage
]
```

Higher score = more likely. But these are not probabilities (don't sum to 1).

---

## 9. Logits → Probabilities (Softmax)

```python
def softmax(logits):
    exp_logits = exp(logits)
    return exp_logits / exp_logits.sum()
```

This converts logits to a probability distribution:
```python
probs = softmax(logits)
# Now: each prob in [0, 1], sum = 1
```

For example:
```
logits:  [5.2, 3.8, 7.1, 1.2, 8.5, -2.1, ...]
probs:   [0.10, 0.03, 0.40, 0.002, 0.45, 0.0001, ...]
```

Now we can sample from this distribution → next token.

---

## 10. Position of Output We Care About

During inference, we usually only care about the LAST token's logits:

```python
# After forward pass
logits_all = model(input_tokens)  # Shape: [N, vocab_size]

# Only need last position
next_token_logits = logits_all[-1]  # Shape: [vocab_size]

# Sample next token
next_token = sample(next_token_logits)
```

During training, we use ALL positions' logits (to compute loss).

---

## 11. Training: Cross-Entropy Loss

How does the model learn?

```python
# Given input tokens, target_tokens are what model should predict
# (Usually: target is the input shifted by 1)

logits = model(input_tokens)        # [N, vocab_size]
loss = cross_entropy(logits, target_tokens)
```

Cross-entropy:
```python
def cross_entropy(logits, target):
    log_probs = log_softmax(logits)
    return -log_probs[target]  # Negative log probability of correct token
```

**Intuition:**
- If correct token has high probability → low loss (good)
- If correct token has low probability → high loss (bad)

Training: minimize this loss across billions of examples.

---

## 12. Forward Pass Compute Cost

For a single forward pass through the FULL model:

```
Total params: ~175B (for GPT-4 scale)
Operations per token: ~2 × 175B = 350 GFLOPS

For sequence length N:
  Attention: O(N² × hidden_dim) per layer
  FFN: O(N × hidden_dim²) per layer

Total for N=1000:
  ~3.5 × 10^14 ops
  ≈ 350 ms on H100 (roughly)
```

In practice, batching makes this much more efficient.

---

## 13. Memory Requirements

For inference:
```
Model weights:        175B × 2 bytes (fp16) = 350 GB
Activations:          ~10 GB per request (depends on batch)
KV cache:             1-100 GB depending on context length
```

**Why GPT-4 needs multiple GPUs:** A single H100 has 80GB. The model alone needs 350GB → must split across GPUs.

This is **tensor parallelism** — model weights split across GPUs, GPUs cooperate.

---

## 14. Quantization (Inference Optimization)

Default: weights stored as FP16 (16 bits per number) = ~350 GB for 175B params.

**Quantization** reduces precision:
- **INT8** (8 bits): half size, slight quality loss
- **INT4** (4 bits): 1/4 size, more quality loss
- **GPTQ, AWQ**: smart quantization preserves quality

For LLama 3 70B:
- FP16: 140 GB
- INT8: 70 GB
- INT4: 35 GB (fits on consumer GPU!)

This is how Llama runs on local hardware.

---

## 15. Hidden States — Useful Beyond Output

Each layer's output is a "hidden state". Some applications use these:

### Embedding extraction
```python
# Use second-to-last layer's output as text embedding
hidden_states = model(text, output_hidden_states=True)
embedding = hidden_states[-2].mean(dim=0)  # Average pooling
```

### Feature extraction for downstream tasks
- Sentiment classification: train a small classifier on hidden states
- Named entity recognition
- Etc.

### Probing experiments
- "Does layer 30 know that 'cat' is an animal?"
- Train a classifier on layer 30 outputs to predict animal/object

---

## 16. The "Bottom-up" Computation View

```
Bottom (input):    "The cat sat on the mat"
                   Each token has basic embedding
                                ↓
Block 1:           Tokens learn syntactic info
                                ↓  
Block 30:          Tokens know roles, agreement
                                ↓
Block 60:          Tokens encode semantics, world knowledge
                                ↓
Block 96:          Tokens are ready for output prediction
                                ↓
LM Head:           For next-token prediction, last position
                   → 100K logits over vocab
                                ↓
Sampling:          Choose one token → "the" (or whatever)
```

---

## 17. Different Models, Different Compositions

### GPT-style (decoder-only)
- Stack of identical transformer blocks
- Causal mask
- Predict next token

### BERT-style (encoder-only)
- Stack of identical transformer blocks
- No causal mask (bidirectional)
- Used for understanding (classification, NER, etc.)
- NOT for generation

### T5 (encoder-decoder)
- Encoder: bidirectional blocks
- Decoder: causal blocks with cross-attention to encoder
- Used for tasks where you transform one sequence to another

For modern LLMs (GPT, Claude, Gemini, Llama), the **decoder-only** architecture won.

---

## 18. Tensor Parallelism — How Multi-GPU Works

For huge models that don't fit on one GPU:

### Layer-wise (Pipeline parallelism)
```
GPU 1: Layers 1-24
GPU 2: Layers 25-48
GPU 3: Layers 49-72
GPU 4: Layers 73-96
```

Token's activation flows GPU 1 → 2 → 3 → 4.

### Tensor parallelism
```
EACH GPU has parts of EACH layer.
GPU 1 has first half of attention/FFN weights
GPU 2 has second half
```

All GPUs work on same forward pass, splitting tensor operations.

### Combined (Megatron-style)
Modern systems combine both for massive models.

---

## 19. Common Misconceptions

### ❌ "More layers always = better"
After ~100 layers, diminishing returns. Wider often beats deeper.

### ❌ "Each layer adds 'knowledge'"
Layers transform representations. Knowledge is in the WEIGHTS, present throughout.

### ❌ "Output projection chooses the answer"
The output projection produces SCORES. Sampling picks the answer.

### ❌ "Activations get bigger through layers"
LayerNorm keeps activations stable. They don't blow up.

---

## 20. Interview Questions

1. **Q: Why stack many transformer blocks?**
   - Each block enriches representations. Deeper = more sophisticated patterns.

2. **Q: What's weight tying?**
   - Sharing weights between input embedding and output projection. Saves params.

3. **Q: Logits vs probabilities?**
   - Logits = raw scores. Probabilities = softmax(logits). Sum to 1.

4. **Q: Cross-entropy loss?**
   - Negative log probability of correct token. Minimizes during training.

5. **Q: How does multi-GPU inference work?**
   - Tensor parallelism (split layers) + pipeline parallelism (different GPUs hold different layers).

---

## 21. Key Takeaways

✅ Model = embedding + N transformer blocks + final LayerNorm + output projection
✅ Information flows bottom-up, getting richer with depth
✅ Residual stream = shared workspace blocks read/write
✅ Output projection: hidden_dim → vocab_size
✅ Logits = raw scores; softmax → probabilities
✅ Cross-entropy = training loss
✅ Weight tying saves params (embedding ↔ LM head)
✅ Quantization (INT8/INT4) drastically reduces memory
✅ Multi-GPU needed for large models (tensor + pipeline parallelism)
✅ Hidden states useful for other tasks (embeddings, probing)

**Next:** [07_sampling_and_generation.md](07_sampling_and_generation.md) — How next token is chosen (temperature, top-p, etc.)
