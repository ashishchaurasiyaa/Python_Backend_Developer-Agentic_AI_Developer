# 🔬 Deep Architecture — Internal Working of LLMs

> **The complete journey of a prompt** — from your `client.chat.completions.create(...)` call to the response you receive. Every component, every transformation, every byte of math.

---

## 📖 Reading Order

Read these in order — each builds on the previous.

| # | Doc | What You'll Learn |
|---|---|---|
| 0 | [00_complete_journey.md](00_complete_journey.md) | **Master overview** — full pipeline end-to-end |
| 1 | [01_request_flow.md](01_request_flow.md) | Network → Cloudflare → API → Auth → Routing → GPU |
| 2 | [02_tokenization_deep.md](02_tokenization_deep.md) | Text → tokens. BPE algorithm. Why Hindi costs more. |
| 3 | [03_embeddings_and_position.md](03_embeddings_and_position.md) | Token IDs → 12K-dim vectors. RoPE positional encoding. |
| 4 | [04_attention_complete.md](04_attention_complete.md) ⭐ | **The heart** — Q, K, V matrices. Self-attention math. Multi-head. |
| 5 | [05_transformer_block.md](05_transformer_block.md) | LayerNorm + Attention + FFN + Residuals = one block. |
| 6 | [06_layer_stacking_and_output.md](06_layer_stacking_and_output.md) | 96 blocks stacked → logits over vocab. |
| 7 | [07_sampling_and_generation.md](07_sampling_and_generation.md) | Logits → next token. Temperature, top-p, top-k. |
| 8 | [08_inference_optimizations.md](08_inference_optimizations.md) | KV cache, Flash Attention, batching, quantization. |
| 9 | [09_training_briefly.md](09_training_briefly.md) | How weights are learned. Pre-train + RLHF. |
| 10 | [10_visualize_internals_practical.py](10_visualize_internals_practical.py) | **RUN THIS** — see internals with real code |

---

## ⏱️ Time to Complete

- **Quick skim:** 2-3 hours (read 00, 04, 07)
- **Deep read:** 10-15 hours (all docs)
- **Mastery:** 20-30 hours (read + run practical + experiment)

---

## 🎯 What You'll Know After This

✅ **Exactly** what happens when you call the API
✅ Why long contexts are expensive (O(N²) attention)
✅ Why Hindi/Chinese cost more (tokenization)
✅ How RoPE encodes position
✅ Q/K/V matrices in attention
✅ Why GPT-4 has 96+ layers
✅ Logits vs probabilities vs sampling
✅ Why prompt caching saves 90% (Anthropic)
✅ KV cache + Flash Attention internals
✅ How RLHF makes models "helpful"
✅ Where hallucination comes from (training objective)

---

## 🎤 Interview-Ready Questions

After reading, you can answer:

1. Explain the complete journey of a prompt through GPT-4.
2. How does self-attention work? What are Q, K, V?
3. Why is the context window limited?
4. What's the difference between prefill and decode?
5. How does KV cache speed up inference?
6. Why use RoPE over learned positional embeddings?
7. Explain RLHF.
8. Why do models hallucinate?
9. How does multi-head attention differ from single-head?
10. What's Flash Attention and why does it matter?

---

## 🔧 Practical Application

Understanding internals helps you:

**Reduce costs:**
- Tokenize efficiently (avoid weird whitespace)
- Use prompt caching (Claude — 90% off)
- Choose right model size for task

**Improve quality:**
- Tune temperature/top-p correctly per task
- Understand why some prompts fail
- Use structured outputs (knowing constraints)

**Build agents:**
- Realistic latency expectations
- Token budget management
- Streaming for UX

**Pass interviews:**
- Stand out from "uses LLMs" crowd
- Show depth, not just usage

---

## 📚 Further Reading

After this series:
- **"The Illustrated Transformer"** by Jay Alammar (visual)
- **"Attention Is All You Need"** (original paper, 2017)
- **"Language Models Are Few-Shot Learners"** (GPT-3 paper)
- **Andrej Karpathy's YouTube** — "Let's build GPT" (code from scratch)
- **3Blue1Brown's "Attention" video** — beautiful animations

---

## 💡 Mental Model

```
You type:                              User space
   ↓
Python SDK                              Client side
   ↓
HTTPS to OpenAI                         Network
   ↓
Auth, Rate limit, Route                 Server side
   ↓
Tokenize (CPU)                          Server CPU
   ↓
Send to GPU                             GPU
   ↓
[Embedding] → [Attention × 96 layers] → [Sampling]  ← All on GPU
   ↓
Detokenize (CPU)                        Server CPU
   ↓
HTTPS response                          Network
   ↓
Python parses                           Client side
   ↓
You read response                       User space
```

**Total time:** ~500ms - 3 seconds for 100 tokens.

**Total operations on GPU:** ~10-100 trillion (yes, trillion).

That's what happens every time you make an API call. Mind-bending, right?

---

## 🚀 Start Here

→ **[00_complete_journey.md](00_complete_journey.md)** — Start with the master overview.

Then go in order, or jump to topics that interest you most.

**Most important docs:**
- ⭐ [04_attention_complete.md](04_attention_complete.md) — The heart of transformers
- ⭐ [08_inference_optimizations.md](08_inference_optimizations.md) — Production realities
- ⭐ [10_visualize_internals_practical.py](10_visualize_internals_practical.py) — Hands-on
