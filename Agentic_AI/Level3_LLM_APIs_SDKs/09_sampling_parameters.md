# Level 3.9 — Sampling Parameters Deep
**Phase: LLM APIs & SDKs | Interview-Critical**

## Quick Concepts

- **Sampling** = picking the next token from probability distribution
- **temperature** = randomness control (0 = deterministic, 1 = creative, 2 = wild)
- **top_p** (nucleus) = sample from smallest set of tokens whose cumulative probability ≥ p
- **top_k** = sample from top K most likely tokens
- **frequency_penalty** = reduce repetition of tokens already used (0-2)
- **presence_penalty** = reduce repetition of any token (0-2)
- **max_tokens** = hard cap on output length
- **stop sequences** = strings that halt generation when emitted
- **seed** = reproducibility (mostly deterministic with seed + temp=0)
- **logit_bias** = boost/suppress specific token IDs
- **logprobs** = return log probabilities of chosen tokens (debugging)

---

## Why Sampling Matters for Production

```
Wrong parameters → wrong output:
   ✗ Code generation with temp=1.5 → garbage code
   ✗ Creative writing with temp=0 → boring repetition
   ✗ Classification with high temp → inconsistent labels
   ✗ JSON generation without stops → runs forever

Right parameters by task:
   ✓ Classification:        temp=0 (deterministic)
   ✓ Code generation:        temp=0 to 0.2
   ✓ Question answering:     temp=0.2 to 0.5
   ✓ Creative writing:       temp=0.7 to 1.0
   ✓ Brainstorming:         temp=1.0 to 1.3
```

---

## Temperature Deep Dive

### What it actually does

```
Raw logits → softmax(logits / temperature) → probability distribution

temperature → 0:
   distribution → spike at top token (argmax)
   → deterministic, same input = same output

temperature → 1:
   distribution unchanged from model
   → balanced creativity

temperature → ∞:
   distribution → uniform
   → random gibberish
```

### Practical values

```
0.0   →  classification, extraction, code
0.2   →  factual Q&A, summarization
0.5   →  conversational
0.7   →  creative writing, default for most cases
1.0   →  brainstorming
1.5+  →  exploration, RARELY useful
```

### Code

```python
# Deterministic classification
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Sentiment: 'I love this product'"}],
    temperature=0,
)

# Creative
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a poem"}],
    temperature=0.9,
)
```

---

## Top-P (Nucleus Sampling)

### What it does

```
Sort tokens by probability (high to low).
Cumulative sum until ≥ top_p.
Sample only from that "nucleus".

top_p=0.1:  only most likely tokens (very focused)
top_p=0.5:  half the probability mass
top_p=0.9:  default, sensible for most cases
top_p=1.0:  no filtering (consider all tokens)
```

### Temperature vs Top-P

```
temperature:  reshapes distribution (steeper/flatter)
top_p:        truncates distribution (cuts tail)

Combined:
   ✓ Use temp=0.7 + top_p=0.9 for creative
   ✗ Don't crank both to max (chaos)
   ✓ Rule of thumb: tune ONE, leave other default
```

### Code

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    temperature=0.7,
    top_p=0.9,
)
```

---

## Top-K (Less Common in Production)

```python
# Anthropic supports top_k
response = client.messages.create(
    model="claude-3-7-sonnet-latest",
    messages=[...],
    temperature=0.7,
    top_k=40,  # consider only top 40 tokens
)
```

```
top_k=1:    deterministic (always pick #1)
top_k=10:   focused
top_k=40:   default in many systems
top_k=100+: more variety
```

OpenAI doesn't expose top_k via Chat API. Use top_p instead.

---

## Frequency & Presence Penalty (Anti-Repetition)

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    frequency_penalty=0.5,   # 0-2: penalize repeated tokens
    presence_penalty=0.3,    # 0-2: encourage new topics
)
```

### When to use

```
Task                         Frequency Pres
─────────────────────────────────────────────
General chat                 0           0
Code generation              0           0     (repetition is OK)
Creative writing             0.3-0.5     0.3
Summarization                0.5-1.0     0
Brainstorming                0.3         0.6   (diverse ideas)
Avoiding generic phrases     0.5         0.5
```

### What they actually do

```
frequency_penalty:
   new_logit[i] -= freq * count(token_i_in_output)
   "stop saying the same word"

presence_penalty:
   new_logit[i] -= pres * (1 if token_i_in_output else 0)
   "stop repeating topics at all"
```

---

## max_tokens — Hard Output Cap

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    max_tokens=500,  # stop at 500 output tokens
)

# Check if you hit the cap
if response.choices[0].finish_reason == "length":
    print("Output truncated — increase max_tokens")
```

### Why it matters

```
✓ Cost control (output is 2-3x cost of input)
✓ Prevent runaway generation
✓ Latency (less output = faster response)
✓ Predictable response sizes

Typical settings:
   Quick answer:     max_tokens=150
   Paragraph:        max_tokens=500
   Article:          max_tokens=2000
   Long-form:        max_tokens=4000
```

---

## Stop Sequences

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "List 3 facts about TCP:\n1."}],
    stop=["\n4.", "5."],  # stop at next item beyond 3
)
```

### Use cases

```
✓ Few-shot prompts: stop=["Q:", "Question:"]
✓ JSON generation: stop=["\n}"] (after closing brace)
✓ Code blocks: stop=["```"]
✓ Structured output: stop=["END_OF_RESPONSE"]
```

---

## Seed (Reproducibility)

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    seed=42,
    temperature=0,
)

# Same seed + temp=0 + same messages = same response (mostly)
```

**Caveats:**
- Not 100% reproducible across model versions
- Provider-specific behavior (OpenAI vs Anthropic)
- Useful for tests + debugging, not for legal proof

---

## Logit Bias (Token Steering)

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o-mini")

# Strongly favor "yes" / "no" tokens
yes_tokens = enc.encode(" yes")  # note leading space
no_tokens = enc.encode(" no")

bias = {}
for t in yes_tokens + no_tokens:
    bias[t] = 5  # 1-10 typical range, max 100 forces

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Is this spam?"}],
    logit_bias=bias,
    max_tokens=1,
    temperature=0,
)
```

### Use cases

```
✓ Constrain output to specific tokens (yes/no classifier)
✓ Suppress unwanted tokens (e.g., "I'm an AI...")
✓ Force structured outputs (rarely needed with JSON mode now)
```

**Limits:**
- 100+ bias = force; -100 = suppress
- Up to ~300 tokens biased per request
- Use sparingly; modern models handle constraints better via instructions

---

## logprobs (Debugging + Confidence)

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    logprobs=True,
    top_logprobs=5,  # see top 5 candidates per position
)

for choice in response.choices:
    for token_data in choice.logprobs.content:
        print(f"Token: {token_data.token}, "
              f"prob: {math.exp(token_data.logprob):.3f}")
        for alt in token_data.top_logprobs:
            print(f"   alt: {alt.token} (p={math.exp(alt.logprob):.3f})")
```

### Use cases

```
✓ Confidence score for classification
   if logprob(chosen) > -0.5: confident
✓ Debugging "why did model pick this?"
✓ Calibration (which predictions are reliable?)
```

---

## Per-Task Parameter Recipes

```python
# Classification (deterministic)
PARAMS_CLASSIFY = {
    "temperature": 0,
    "max_tokens": 10,
    "top_p": 1.0,
}

# Code generation (mostly deterministic, small variation)
PARAMS_CODE = {
    "temperature": 0.2,
    "max_tokens": 2000,
    "stop": ["```"],
}

# Conversational (natural variation)
PARAMS_CHAT = {
    "temperature": 0.7,
    "top_p": 0.9,
    "frequency_penalty": 0.2,
    "presence_penalty": 0.1,
}

# Creative writing (high creativity)
PARAMS_CREATIVE = {
    "temperature": 0.9,
    "top_p": 0.95,
    "frequency_penalty": 0.4,
    "presence_penalty": 0.4,
}

# Summarization (focused, no repetition)
PARAMS_SUMMARY = {
    "temperature": 0.3,
    "frequency_penalty": 0.5,
    "max_tokens": 500,
}

# RAG answer (grounded, low creativity)
PARAMS_RAG = {
    "temperature": 0.1,
    "max_tokens": 800,
    "stop": ["\nQ:", "\nQuestion:"],
}
```

---

## Provider Differences

```
                    OpenAI        Anthropic       Cohere
                    ────────────  ──────────────  ───────────
temperature         0-2           0-1             0-5
top_p              0-1           0-1             0-1
top_k              ✗ (use top_p) ✓ (0-500)       ✓
frequency_penalty   ✓             ✗               ✓
presence_penalty    ✓             ✗               ✓
seed               ✓             ✗               ✓
logit_bias         ✓             ✗               ✗
logprobs           ✓             ✗               ✓
stop               ✓             ✓               ✓
max_tokens         ✓             ✓ (required)    ✓
```

---

## A/B Testing Parameters

```python
async def compare_params(question: str, configs: list[dict]):
    """Compare multiple parameter sets in parallel."""
    
    async def with_config(cfg):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}],
            **cfg,
        )
        return cfg, response.choices[0].message.content
    
    results = await asyncio.gather(*[with_config(c) for c in configs])
    return results


# Find best params for your task
configs = [
    {"temperature": 0.3, "top_p": 0.9},
    {"temperature": 0.7, "top_p": 0.9},
    {"temperature": 0.7, "top_p": 0.5},
    {"temperature": 1.0, "top_p": 0.95},
]
results = await compare_params("Write a tagline for our app", configs)
```

---

## Common Pitfalls

```
1. ✗ temp=0 always — never explores alternatives
   ✓ Use 0 for deterministic, 0.5+ for variety

2. ✗ top_p + temp + top_k all maxed
   ✓ Tune ONE primarily

3. ✗ Frequency penalty too high (>1)
   → Output becomes random / weird
   ✓ Stay 0-0.5 unless specific reason

4. ✗ No max_tokens
   → Model runs for 4000 tokens, $$$ + slow
   ✓ Always cap appropriately

5. ✗ Forgetting stop sequences
   → Model adds "Question 5:" after your 4-item list
   ✓ Add explicit stops

6. ✗ seed without temp=0
   → Still some variation
   ✓ seed + temp=0 = max reproducibility

7. ✗ Crazy logit_bias values
   → Coherence breaks
   ✓ Start with bias=5, tune carefully

8. ✗ Different params for same task across calls
   → Inconsistent outputs
   ✓ Centralize parameter sets per task
```

---

## Interview Questions

### Q1: Difference between temperature and top_p?

Temperature reshapes the entire probability distribution (low = peaked, high = flat). Top_p truncates the distribution (only consider tokens whose cumulative prob ≤ p). Temperature affects RANDOMNESS; top_p affects RANGE of candidates considered. Usually tune one or the other.

### Q2: When would you use frequency_penalty vs presence_penalty?

Frequency_penalty scales WITH repetition count (the more "X" is used, the more penalty). Presence_penalty is constant once a token appears. Frequency for "stop saying X over and over"; presence for "introduce new topics, don't dwell".

### Q3: Best parameters for production classification?

`temperature=0, max_tokens=10, top_p=1.0`. Determinism > creativity. Optionally `logit_bias` to constrain to specific labels. Use `logprobs` to extract confidence scores.

### Q4: How do you ensure reproducible LLM outputs?

`temperature=0` + `seed=N` + pin the model version. Still not 100% reproducible across releases — capture model name, params, and output for audit.

### Q5: How do you steer the model to output only "yes" or "no"?

(1) Clear prompt: "Answer with only 'yes' or 'no'." (2) `temperature=0`. (3) `max_tokens=1`. (4) Optional `logit_bias` to boost yes/no token IDs. Modern models do well with just (1)-(3).

---

## Senior Mantras

```
1. Default temp = 0.7. Default top_p = 0.9. Tune by task.

2. Always set max_tokens. Cost runs away otherwise.

3. temp=0 for anything requiring consistency.

4. Tune temperature OR top_p, not both at extremes.

5. Frequency penalty fights repetition. Use 0.2-0.5.

6. Stop sequences prevent runaway output.

7. Centralize parameter sets per task type.

8. A/B test params before locking them in.

9. logprobs for confidence scoring in classification.

10. Pin model version + record params. Reproducibility matters.
```

---

## Related

- [05_streaming_responses.md](05_streaming_responses.md)
- [06_async_parallel.md](06_async_parallel.md)
- [07_error_handling_retries.md](07_error_handling_retries.md)
- [10_cost_optimization.md](10_cost_optimization.md) — max_tokens for cost
- [../Level2_Prompt_Engineering/](../Level2_Prompt_Engineering/) — prompt-level controls
