# Deep Architecture — Doc 9: How LLMs Are Trained (Briefly)

> **Goal:** Weights aate kahan se hain? Pre-training, fine-tuning, RLHF — high-level samjho. Inference samjhne ke liye yeh background helpful hai.

---

## 1. The Big Picture

Two phases:
1. **Pre-training**: Model learns language from raw internet text. Costs $millions, takes months.
2. **Post-training (fine-tuning + RLHF)**: Model learns to be helpful. Costs $thousands.

After both: you have the model you use via API.

---

## 2. Pre-Training — The Heavy Lift

### Data
- 10-15 trillion tokens of text
- Sources: web crawl (CommonCrawl), books, papers, code (GitHub), Wikipedia
- Multiple languages
- Quality filtered (deduplication, spam removal)

For GPT-4: estimated ~13 trillion tokens.
For Llama 3.1: 15.6 trillion tokens.

### Objective
**Next-token prediction**:
```
Input:  "The cat sat on the"
Target: "mat"  (the actual next token in training data)

Model predicts probability distribution over all tokens.
Loss = -log(P(correct token))
```

Repeat for **trillions of examples**.

### Training procedure
```python
for batch in dataset:
    # Forward pass
    input_tokens = batch["input"]
    target_tokens = batch["target"]
    
    logits = model(input_tokens)
    loss = cross_entropy(logits, target_tokens)
    
    # Backward pass
    loss.backward()
    
    # Update weights
    optimizer.step()
    optimizer.zero_grad()
```

Done ~10^6 to 10^7 times.

### Hardware
- 10,000+ H100 GPUs running for months
- $20-100 million in compute cost
- Custom networking (NVLink, InfiniBand)

---

## 3. What the Model Learns During Pre-Training

Just predicting next token, the model **somehow learns**:
- Grammar (next token follows grammar rules)
- Facts ("Paris is the capital of France")
- Reasoning patterns
- Code patterns
- Multiple languages
- Cultural knowledge

**It's an emergent property.** Trained to predict text, learned everything contained in human text.

This is the "**scaling hypothesis**" — bigger model + more data + more compute = more capable.

---

## 4. Pre-Training Output: Base Model

After pre-training, you have a "base model":
- Can complete text well
- Has world knowledge
- **CANNOT** follow instructions well
- Just predicts next token (might continue your question instead of answering it)

Example:
```
Input: "What is 2+2?"
Base model output: "What is 3+3? What is 4+4? ..."
                  (continues pattern, doesn't answer)
```

The base model is **not useful** for chat. Needs post-training.

---

## 5. Supervised Fine-Tuning (SFT)

Phase 2: Teach the model to follow instructions.

### Data
- ~10K-100K human-written examples
- Format: (instruction, ideal response) pairs
```
Instruction: "What is 2+2?"
Response: "4"

Instruction: "Write a haiku about Python."
Response: "Lines of code flowing / Whitespace marks the indentation / Python brings the calm"

Instruction: "Translate to French: Hello"
Response: "Bonjour"
```

### Training
Same objective (next-token prediction), but on this curated data:
```
Show model: "Instruction: ... Response: 4"
Target: predict "4"
```

Now the model learns the **format**: when given instruction, produce response.

### Cost
~Days of training on 100+ GPUs. ~$100K. Much cheaper than pre-training.

---

## 6. RLHF — Reinforcement Learning from Human Feedback

SFT alone isn't enough. Model can follow instructions but may produce:
- Harmful content
- Unhelpful responses
- Hallucinations
- Boring responses

RLHF teaches the model to **prefer helpful, safe, polite responses**.

### Step 1: Gather preference data

Show humans 2 responses to same prompt:
```
Prompt: "How do I learn Python?"

Response A: "Just look it up online."  (lazy)
Response B: "Great question! Start with the official tutorial at python.org. Pair it with practice on freeCodeCamp..."  (helpful)

Human picks: B
```

Collect ~10K-100K such pairs.

### Step 2: Train a reward model

```python
# Train a separate model that predicts human preference
reward_model = train(
    examples=[(prompt, response_chosen, response_rejected), ...]
)

# Now reward_model(prompt, response) → score
```

### Step 3: RL fine-tune the main model

Use PPO or similar RL algorithm:
```python
for prompt in prompts:
    response = model.generate(prompt)
    reward = reward_model(prompt, response)
    
    # Update model to make HIGH-REWARD responses more likely
    model.update(prompt, response, reward)
```

Model learns to maximize human preference scores.

---

## 7. DPO — Newer Alternative to RLHF

**Direct Preference Optimization** (2023):
- Skip the reward model
- Train directly on preference data
- Simpler, similar quality

```python
# DPO trains model to:
# - Increase probability of chosen response
# - Decrease probability of rejected response
# Har response ka log-ratio APNE policy vs REFERENCE (frozen SFT) model ke against liya jata hai:
#   r(y) = log π_θ(y) - log π_ref(y)
loss = -log(σ(β * ( (log_π_θ(chosen)  - log_π_ref(chosen))
                  - (log_π_θ(rejected) - log_π_ref(rejected)) )))
# Reference-model (π_ref) terms hi DPO ka core hain — inke bina ye sirf plain preference loss reh jata hai.
```

Used in: Mistral, Llama 3.1, modern open-source.

---

## 8. Constitutional AI (Anthropic's Approach)

Instead of human raters, use **AI feedback**:
- Define a "constitution" — list of principles ("be helpful", "be honest", "don't be harmful")
- Have an AI critique outputs against constitution
- Use critiques as preference signal

Cheaper than human raters. Used for Claude.

---

## 9. Reasoning Training (o1, o3)

For reasoning models:
- Train on **chains of reasoning**, not just answers
- Show problem → step-by-step thinking → final answer
- Reward correct reasoning steps, not just correct final answer

```
Problem: 2x + 3 = 11. Find x.
Reasoning:
  Step 1: Subtract 3 from both sides → 2x = 8
  Step 2: Divide by 2 → x = 4
Answer: x = 4
```

Reward signal includes both:
- Reasoning quality
- Final answer correctness

This is what makes o1/o3 great at math/code.

---

## 10. Training a Multi-Modal Model

For text + vision:

### Phase 1: Pre-train text model (as before)

### Phase 2: Train vision encoder separately
- Train on image classification, etc.
- Output: vector representation of image

### Phase 3: Align vision + text
- Show image-text pairs ("cat photo" + caption)
- Train projection so image features align with text token space

### Phase 4: Joint fine-tuning
- Show multimodal inputs (images + questions)
- Train to answer

Result: GPT-4V, Claude 3, Gemini — models that "see".

---

## 11. Continual Learning / Updates

How does Claude 3.5 differ from Claude 3?
- More training data (newer cutoff)
- Possibly new architecture improvements
- More RLHF rounds
- Better fine-tuning recipes

Companies update models regularly:
- Underlying weights change
- API name might stay same (e.g., "claude-3-5-sonnet-20241022" — date in name)
- Behavior may shift subtly

This is why **reproducibility is hard** — even with seed, different model version → different output.

---

## 12. Fine-Tuning YOUR Model

You can fine-tune OpenAI/Anthropic models on your data:

### OpenAI Fine-tuning
```python
# Upload training data (JSONL format)
client.files.create(file=open("data.jsonl"), purpose="fine-tune")

# Create job
client.fine_tuning.jobs.create(
    training_file="file-abc123",
    model="gpt-4o-mini"
)

# After training (hours), use your model:
client.chat.completions.create(model="ft:gpt-4o-mini:your-org:abc123", ...)
```

### When to fine-tune (vs RAG)
| Use case | Fine-tune | RAG |
|---|---|---|
| New facts/data | ❌ | ✅ |
| Specific style/format | ✅ | ❌ |
| Reduce prompt size | ✅ | ❌ |
| Domain jargon | Partial | ✅ |
| Real-time data | ❌ | ✅ |

Rule of thumb: try RAG first, fine-tune if not enough.

### Open-source fine-tuning
```python
# LoRA — efficient fine-tuning of Llama
from peft import LoraConfig, get_peft_model

config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
model = get_peft_model(base_model, config)

# Train on your data
trainer.train()

# Save: only the small LoRA weights (~100 MB)
```

LoRA / QLoRA: only train a tiny subset of weights. 100x cheaper than full fine-tuning.

---

## 13. Catastrophic Forgetting

When fine-tuning, model may "forget" pre-trained capabilities:
- Fine-tune for legal documents → forgets how to write code
- Fine-tune for one language → forgets others

**Mitigations:**
- Mix in original data during fine-tuning
- Use LoRA (small modifications, doesn't overwrite base)
- Lower learning rate

---

## 14. Why Models Hallucinate (Connection to Training)

Pre-training objective: predict next token.

Result: model produces **plausible-sounding** text, not necessarily **true** text.

If the model was trained on text where statements followed certain patterns, it produces text following those patterns — even if specific facts are made up.

RLHF helps but doesn't eliminate this. The fundamental issue is the training objective.

**Solutions:**
- RAG (force model to use real sources)
- Tool use (let model look things up)
- Structured output (constrain to known fields)
- Fine-tuning on YOUR data (reduces hallucination in domain)

---

## 15. Why "Bigger Is Better" Plateaued

Through 2020-2023: bigger model = better.

By 2024: signs of diminishing returns. Newer focus:
- Better data (synthetic data, high-quality filtering)
- Better algorithms (DPO, RLHF improvements)
- Better architectures (MoE, mamba experiments)
- Reasoning training (o1-style)

So GPT-5 may not be 10x bigger than GPT-4 — may be similar size with much better training.

---

## 16. Open vs Closed Training Recipes

### Closed (OpenAI, Anthropic)
- Exact data not disclosed
- Architecture details often hidden
- Training procedures secret
- Why? Competitive moat, safety, IP

### Open (Llama, Mistral, etc.)
- Papers describe approach
- Open weights (some)
- Data sometimes disclosed
- Why? Build community, research

Both are valuable. Open-source closes the gap quickly.

---

## 17. The Cost of Training

For frontier models (rough estimates):

| Model | Compute Cost | Time |
|---|---|---|
| Llama 3.1 8B | ~$0.5M | weeks |
| Llama 3.1 70B | ~$5M | weeks |
| Llama 3.1 405B | ~$60M | months |
| GPT-4 (estimated) | ~$100M | months |
| GPT-5 (likely) | ~$1B | months |
| (Future) | $10B+ | months |

This is why only big companies / well-funded labs train frontier models.

Fine-tuning costs:
- LoRA fine-tune small model: ~$10-100
- Full fine-tune: ~$1K-10K
- Domain adaptation: ~$10K-100K

---

## 18. Why You Should Care (Practical Implications)

### As a developer:
1. **Knowledge cutoff** — model only knows what was in training. Add RAG for recent info.
2. **Hallucination** — model trained for plausibility, not truth. Use structured outputs, validate.
3. **Style** — RLHF shapes how model "sounds". Different providers feel different.
4. **Capability** — bigger/newer models have broader knowledge. Choose model for task.
5. **Fine-tuning** — option for niche tasks where prompting alone insufficient.

### As an interviewer / interviewee:
- Understanding training helps explain WHY models behave as they do
- Differentiates "uses LLMs" from "understands LLMs"

---

## 19. Frontier Research Directions

Areas of active research:
- **Test-time compute** — let model "think longer" for hard problems (o1 paradigm)
- **Synthetic data** — generate training data with LLMs (chicken-and-egg)
- **Better alignment** — making models more truthful, less biased
- **Smaller, faster models** — same capability with 10x less compute
- **Multi-modal native** — vision/audio not bolted on, but integrated from start
- **Agentic training** — train models specifically to be good agents (use tools, plan)
- **Constitutional / debate methods** — AI critiquing AI for safety

---

## 20. Interview Questions

1. **Q: How is GPT-4 trained?**
   - Pre-train on trillions of tokens (next-token prediction). Then SFT + RLHF.

2. **Q: Why does the base model not work for chat?**
   - Only predicts next token. Doesn't "follow instructions" without fine-tuning.

3. **Q: What's RLHF?**
   - Train reward model on human preferences → use RL to maximize reward.

4. **Q: SFT vs RLHF vs DPO?**
   - SFT: supervised on instructions. RLHF: RL with reward model. DPO: direct from preferences.

5. **Q: Fine-tuning vs RAG?**
   - Fine-tune for style/format. RAG for new data.

6. **Q: Why do models hallucinate?**
   - Trained for plausibility, not truth. Pattern-matching, not lookup.

---

## 21. Key Takeaways

✅ **Pre-training**: trillions of tokens, next-token prediction. $$$, months.
✅ **Base model**: knows language, doesn't follow instructions yet.
✅ **SFT**: teach instruction-following with curated (instruction, response) pairs.
✅ **RLHF**: reward model + RL → model prefers helpful, safe responses.
✅ **DPO**: simpler alternative to RLHF, similar quality.
✅ **Multi-modal**: train vision encoder + align with text space.
✅ **Reasoning models** (o1, o3): trained on chains of reasoning, rewarded for correct steps.
✅ **Fine-tuning**: LoRA for cheap customization. Full fine-tune for major changes.
✅ Hallucination is fundamental to training objective — mitigate with RAG, tools, structured output.
✅ Frontier training: $100M-$1B+ cost.

**Deep Architecture series complete!** 🎉
- 00 — [Complete Journey](00_complete_journey.md)
- 01 — [Request Flow](01_request_flow.md)
- 02 — [Tokenization](02_tokenization_deep.md)
- 03 — [Embeddings + Position](03_embeddings_and_position.md)
- 04 — [Attention Mechanism](04_attention_complete.md)
- 05 — [Transformer Block](05_transformer_block.md)
- 06 — [Layer Stacking + Output](06_layer_stacking_and_output.md)
- 07 — [Sampling + Generation](07_sampling_and_generation.md)
- 08 — [Inference Optimizations](08_inference_optimizations.md)
- 09 — [Training Brief](09_training_briefly.md) ← You are here

**Next:** Practical visualization code → [practical.py](10_visualize_internals_practical.py)
