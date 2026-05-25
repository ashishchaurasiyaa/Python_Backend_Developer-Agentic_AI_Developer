# Deep Architecture — Doc 7: Sampling & Token Generation

> **Goal:** Logits se actual token kaise pick hota hai. Temperature, top-p, top-k, beam search — sab.

---

## 1. The Setup

After forward pass, we have logits over vocabulary (100K+ scores):
```
logits = [5.2, 3.8, 7.1, ..., 1.2]   # shape: [vocab_size]
```

Now we need to **pick ONE token** as the next token.

---

## 2. Greedy Decoding (Simplest)

Just pick the highest:
```python
def greedy(logits):
    return argmax(logits)
```

**Pros:**
- Deterministic
- Simple
- Fast

**Cons:**
- Boring outputs ("The cat sat on the mat. The cat sat on the mat. The cat...")
- Gets stuck in loops
- No diversity

Used sometimes for: classification, extraction, structured outputs (where determinism wanted).

---

## 3. Softmax + Temperature

Convert logits to probabilities, optionally **with temperature**:

```python
def softmax_with_temp(logits, temperature=1.0):
    scaled = logits / temperature
    exp = np.exp(scaled - max(scaled))  # numerical stability
    return exp / exp.sum()
```

### Effect of temperature:

**Temperature = 1.0** (default):
```
logits:  [5.2, 3.8, 7.1, 1.2, 8.5, ...]
probs:   [0.10, 0.03, 0.40, 0.002, 0.45, ...]
```
Normal distribution.

**Temperature = 0** (= greedy):
```
probs:   [0, 0, 0, 0, 1.0, 0, ...]   # All weight on argmax
```
Deterministic.

**Temperature = 0.1** (low, focused):
```
probs:   [0.0001, 0.00001, 0.05, 0, 0.95, ...]   # Very peaked
```
Almost always picks top tokens.

**Temperature = 2.0** (high, creative):
```
probs:   [0.08, 0.06, 0.18, 0.02, 0.20, 0.06, ...]   # Flatter
```
More likely to pick "unusual" tokens. More creative but also more random.

### When to use what:
- **0 / 0.1**: Code generation, classification, extraction (need consistency)
- **0.3-0.7**: General chat, balanced
- **0.7-1.0**: Creative writing, brainstorming
- **>1.0**: Wild creative (rarely useful in practice)

---

## 4. Top-K Sampling

Only consider the top K most likely tokens, ignore the rest:

```python
def top_k(logits, k=50):
    # Get top K values
    top_k_logits, indices = torch.topk(logits, k)
    
    # Zero out the rest
    mask = torch.zeros_like(logits)
    mask[indices] = 1
    logits = logits.masked_fill(mask == 0, -inf)
    
    probs = softmax(logits)
    return sample(probs)
```

**Why?** Prevents picking very unlikely tokens. Even with high temperature, won't pick token with prob 0.0001.

**Typical K**: 40-50.

---

## 5. Top-P (Nucleus) Sampling — More Popular

Instead of fixed K, pick smallest set whose cumulative probability ≥ P.

```python
def top_p(logits, p=0.9):
    probs = softmax(logits)
    sorted_probs, indices = torch.sort(probs, descending=True)
    
    cumsum = torch.cumsum(sorted_probs, dim=-1)
    cutoff = (cumsum >= p).nonzero()[0]
    
    # Zero out tokens beyond cutoff
    keep = indices[:cutoff + 1]
    
    # Renormalize
    masked = torch.zeros_like(probs)
    masked[keep] = probs[keep]
    masked = masked / masked.sum()
    
    return sample(masked)
```

**Example:**
```
probs:  [0.50, 0.20, 0.15, 0.08, 0.04, 0.02, 0.01, ...]
                ↑     ↑     ↑
              cumsum = 0.50, 0.70, 0.85
              
With p=0.9:
  cumsum ≥ 0.9 at index 3 (cumsum=0.93)
  Keep first 4 tokens
  Sample from {token0, token1, token2, token3}
```

**Why better than top-k?**
- Adaptive — sometimes the distribution is peaked (few options), sometimes flat (many)
- Top-k always picks 50, even when only 5 are reasonable
- Top-p picks just enough to cover p% of probability

**Typical P**: 0.9 or 0.95.

---

## 6. Combining Temperature + Top-P + Top-K

In production, often all three:
```python
def sample(logits, temperature=0.7, top_p=0.9, top_k=50):
    # Step 1: Apply temperature
    logits = logits / temperature
    
    # Step 2: Top-K filter
    if top_k > 0:
        top_k_vals = torch.topk(logits, top_k).values[..., -1, None]
        logits = torch.where(logits < top_k_vals, -inf, logits)
    
    # Step 3: Convert to probs
    probs = softmax(logits)
    
    # Step 4: Top-P filter
    if top_p < 1.0:
        sorted_probs, sorted_idx = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        mask = cumsum <= top_p
        mask[..., 0] = True  # Always keep top 1
        # Apply mask...
    
    # Step 5: Sample
    return torch.multinomial(probs, num_samples=1)
```

---

## 7. Other Sampling Parameters

### Frequency Penalty
Penalize tokens that have appeared frequently:
```python
def apply_frequency_penalty(logits, generated_tokens, penalty=0.5):
    for tok in generated_tokens:
        count = generated_tokens.count(tok)
        logits[tok] -= count * penalty
    return logits
```

**Effect:** Reduces repetition.

### Presence Penalty
Penalize tokens that have appeared AT LEAST ONCE:
```python
def apply_presence_penalty(logits, seen_tokens, penalty=0.5):
    for tok in seen_tokens:
        logits[tok] -= penalty
    return logits
```

**Effect:** Encourages topic diversity.

### Both can be combined:
```python
# OpenAI API
client.chat.completions.create(
    frequency_penalty=0.5,   # 0-2 (max penalty 2)
    presence_penalty=0.5,    # 0-2
    temperature=0.7,
    top_p=0.9
)
```

---

## 8. Beam Search (Alternative Strategy)

Instead of sampling, keep top K **sequences** at each step:

```
Step 1: Generate 5 candidate first tokens (top 5)
Step 2: For each, generate top 5 next tokens → 25 candidates
Step 3: Keep best 5 (by total log-prob)
Step 4: Repeat...

Final: Return the best complete sequence
```

**Pros:** Higher quality outputs (in theory)
**Cons:** 
- Expensive (K parallel generations)
- Boring (favors safer outputs)
- Rarely used in modern LLMs

Used in: machine translation (older models), some specialized tasks.

---

## 9. Sampling for Reasoning Models (o1, o3)

For models like o1, the "answer" is generated AFTER internal "thinking":
- Model generates many tokens of internal reasoning (hidden)
- Then generates the answer
- Sampling happens throughout but you mostly see the answer

These models use much HIGHER temperature internally for exploration of reasoning paths.

---

## 10. Speculative Decoding (Fast Inference)

Cool optimization:
- **Big model** is slow but accurate
- **Small model** is fast but slightly worse
- Strategy: small model **drafts** 5 tokens, big model verifies in parallel

```
Small model: "Python is a programming language"  (drafts 5 tokens)
Big model:   ↓ verifies in single forward pass
             accepts 3, rejects 2
             accepted: "Python is a"
             then continues from there

Speedup: 2-3x
```

Now standard in production inference (vLLM, etc.).

---

## 11. Stop Sequences

You can tell the model "stop when you see X":

```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    stop=["\n\n", "END_OF_RESPONSE"]
)
```

Process:
```
Generate token...
Generate token...
Generate token...
Check: did we just generate one of stop sequences?
   if yes → stop here, return result
   else → continue
```

Useful for:
- Multi-step prompts where you want sections
- Custom format enforcement

---

## 12. End-of-Sequence (EOS) Token

Every model has a special token meaning "I'm done":
- GPT: `<|endoftext|>` (token 100257 for cl100k)
- Llama: `<|eot_id|>`
- Claude: similar

The model is trained to output EOS when response is complete. Inference stops there.

**`max_tokens`** is a safety limit — stop after N tokens even if EOS not produced.

---

## 13. The Autoregressive Loop

Putting it all together:

```python
def generate(model, prompt_tokens, max_tokens=100):
    tokens = list(prompt_tokens)
    
    for i in range(max_tokens):
        # 1. Forward pass through model
        logits_all = model(tokens)
        
        # 2. Only care about last position
        logits = logits_all[-1]
        
        # 3. Apply sampling
        next_token = sample(logits, temperature=0.7, top_p=0.9)
        
        # 4. Check for EOS
        if next_token == EOS_TOKEN:
            break
        
        # 5. Check stop sequences
        if matches_stop_sequence(tokens, next_token):
            break
        
        # 6. Append and repeat
        tokens.append(next_token)
    
    return tokens
```

This is the core generation loop. Production has more optimizations (KV cache, batching).

---

## 14. Deterministic Reproducibility

Want same output every time?

```python
# OpenAI
client.chat.completions.create(
    seed=42,                    # Random seed
    temperature=0,              # Deterministic
    top_p=1.0,                  # Don't filter
    messages=[...]
)
```

Even with seed, results may vary slightly due to:
- Model updates (OpenAI may improve underlying weights)
- Floating point non-determinism (very small)
- Multi-GPU non-determinism

For STRICT reproducibility: use temperature=0 (still varies sometimes).

---

## 15. Sampling Comparison Visualization

For "The capital of France is":

```
Logits:
  "Paris":     12.5
  "London":     5.2
  "Berlin":     4.8
  "Rome":       4.5
  "Madrid":     3.9
  ... (rest very low)

Temperature=0 (greedy):
  Always picks "Paris" (100%)

Temperature=0.5, top_p=0.9:
  Paris: 88%, London: 5%, Berlin: 4%, Rome: 2%, Madrid: 1%
  Mostly "Paris", occasionally others

Temperature=1.5, top_p=0.95:
  Paris: 55%, London: 15%, Berlin: 12%, Rome: 10%, Madrid: 8%
  Lots of variation

Top-K=5:
  Only consider top 5 tokens
  All others: probability 0
```

---

## 16. Choosing Sampling Parameters

For **classification / extraction**:
- temperature=0 (deterministic)
- top_p=1.0 (no filter)
- max_tokens=small

For **chatbots / general**:
- temperature=0.3-0.7
- top_p=0.9
- max_tokens=500-1000

For **creative writing**:
- temperature=0.7-1.0
- top_p=0.95
- max_tokens=2000+

For **code generation**:
- temperature=0.0-0.3 (most reliable)
- OR temperature=0.7 + retry on failure
- top_p=0.95

For **agents / tool use**:
- temperature=0 (consistent decisions)
- structured outputs for reliability

---

## 17. Sampling for Multi-Modal

For image generation models (DALL-E, Stable Diffusion):
- Different sampling (not next-token, but denoising)
- Guidance scale instead of temperature
- "Steps" instead of token count

For audio (Whisper):
- Beam search common (better transcription quality)

But for LLMs (text), the patterns above apply.

---

## 18. Self-Consistency (Sampling-Based CoT)

Instead of single output, sample N times with temperature, vote:
```python
def self_consistency(prompt, n=5):
    outputs = []
    for _ in range(n):
        out = llm.call(prompt, temperature=0.7)
        outputs.append(extract_answer(out))
    return most_common(outputs)
```

Better accuracy at cost of N× compute. Works for tasks with clear answers (math, classification).

---

## 19. Common Pitfalls

### ❌ Setting temperature=2 in production
Wild, inconsistent outputs. Save for experiments.

### ❌ top_p=0.5 with temperature=0
Conflicting — temp=0 already deterministic.

### ❌ Forgetting EOS in custom training
Model never knows when to stop. Generates until max_tokens.

### ❌ Ignoring frequency penalty for long generations
Model gets repetitive. Add penalty=0.3-0.5.

### ❌ Relying on greedy for everything
Greedy fails for creative tasks. Need stochasticity.

---

## 20. Interview Questions

1. **Q: Greedy vs sampling?**
   - Greedy: argmax (deterministic). Sampling: random based on distribution (diverse).

2. **Q: Temperature explained?**
   - Scales logits before softmax. Higher = flatter distribution = more random.

3. **Q: Top-p vs top-k?**
   - Top-k: fixed K tokens. Top-p: smallest set covering p% probability (adaptive).

4. **Q: Why frequency penalty?**
   - Penalize repeated tokens. Prevents loops.

5. **Q: What's speculative decoding?**
   - Small model drafts tokens, big model verifies in parallel. 2-3x speedup.

---

## 21. Key Takeaways

✅ Sampling converts logits → next token choice
✅ **Greedy** = argmax (deterministic, boring)
✅ **Temperature** scales randomness (0=greedy, 1=natural, 2=wild)
✅ **Top-K** = consider top K tokens only
✅ **Top-P** (nucleus) = adaptive — smallest set covering p% probability
✅ **Frequency/Presence penalty** = reduce repetition
✅ **Beam search** = keep N best sequences (rare in modern LLMs)
✅ **EOS token** signals "I'm done"
✅ **Stop sequences** for custom stopping
✅ Production: combine temperature + top-p + penalties

**Next:** [08_inference_optimizations.md](08_inference_optimizations.md) — KV cache, Flash Attention, batching
