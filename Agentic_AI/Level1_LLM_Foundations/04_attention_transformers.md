# Level 1 — Doc 4: Attention & Transformers (Simplified)

> **Goal:** Transformer + attention ka intuition. No math. Sirf understanding.

---

## 1. The Big Idea

A Transformer processes text by figuring out **which words to "pay attention to"** when generating each word.

Old way (RNN): Read left-to-right, sequentially.
New way (Transformer): Look at **all words at once**, decide which matter.

---

## 2. Attention Intuition

Example: "The animal didn't cross the street because **it** was too tired."

What does "it" refer to? animal or street?

Answer: animal (streets don't get tired).

How did your brain decide? You **attended to** both options, computed "tired makes more sense for animal".

**That's attention.** The model learns to weight which previous tokens matter for understanding the current token.

---

## 3. Self-Attention vs Cross-Attention

### Self-Attention
- Tokens in the **same sequence** attend to each other
- Used in encoders, decoders

### Cross-Attention
- Tokens in one sequence attend to tokens in **another sequence**
- Used in encoder-decoder models (translation: English → French)

Modern LLMs (GPT, Claude) are **decoder-only**: only self-attention.

---

## 4. Transformer Architecture (High-Level)

```
Input Tokens → Embeddings → 
   ┌────────────────────┐
   │ Layer 1            │
   │  ↳ Self-Attention  │
   │  ↳ Feed Forward    │
   ├────────────────────┤
   │ Layer 2            │
   │  ↳ Self-Attention  │
   │  ↳ Feed Forward    │
   ├────────────────────┤
   │ ... (96+ layers)   │
   └────────────────────┘ → Output Token
```

Each layer:
1. **Self-Attention**: tokens look at each other
2. **Feed-Forward**: process each token independently
3. Layer outputs become input to next layer

After all layers: predict next token.

GPT-4 has ~100 layers, billions of parameters in those Feed-Forward blocks.

---

## 5. Multi-Head Attention

Instead of ONE attention computation, do **multiple in parallel** ("heads").

Each head learns different relationships:
- Head 1 might focus on syntax (subject-verb)
- Head 2 on semantics (topic relevance)
- Head 3 on positional patterns

GPT-4: 96 heads per layer × 96 layers.

---

## 6. Positional Encoding

Transformers process tokens **in parallel**. But order matters!

"Dog bites man" ≠ "Man bites dog"

Solution: Add **positional information** to each token's embedding.
- Token 1: word vector + position 1 vector
- Token 2: word vector + position 2 vector
- ...

Modern variants: RoPE (Rotary Positional Embedding) in Llama, Qwen.

---

## 7. Why Transformers Scaled to LLM Era

| Property | Benefit |
|---|---|
| **Parallelizable** | Train on huge GPU clusters |
| **Long context** | Self-attention captures distant relationships |
| **Composable** | Stack more layers → more capability |
| **General** | Same architecture for text, code, music, etc. |

vs RNN/LSTM:
- Sequential → slow
- Forgot long context
- Hard to train deep networks

---

## 8. Autoregressive Generation (How LLMs Output)

LLMs generate **one token at a time**:

```
Step 1: Input: "The cat sat on the"
        Output: "mat" (with probability 0.4)
                "rug" (0.2)
                "floor" (0.15)
                ...

Step 2: Input: "The cat sat on the mat"  (appended)
        Output: "and" (0.3)
                "." (0.2)
                ...
```

Each output token becomes part of the next input. This is "autoregressive".

**Implications:**
- Streaming: tokens stream as generated
- Generation cost = output tokens × per-token cost
- Long outputs = expensive

---

## 9. Inference Time Optimizations

- **KV Cache**: Reuse previous tokens' computations
- **Flash Attention**: Faster attention computation
- **Speculative Decoding**: Predict multiple tokens, verify

These don't change behavior, just speed.

---

## 10. Context Window

The max tokens a model can "see":
- GPT-4o: 128K
- Claude 3.5: 200K  
- Gemini 2.0: 2M+

Why limit?
- Attention is O(n²) — doubling context = 4x compute
- Memory grows with context

Modern techniques (sliding window, mixture-of-experts) help but limits remain.

---

## 11. What You Don't Need to Know (For Now)

Skip math like:
- Q, K, V matrices
- Softmax in attention
- Backpropagation
- Optimizer details (Adam, AdamW)

You can build amazing agents without this. Come back when you want to fine-tune or build models from scratch.

---

## 12. Why This Helps You

Understanding the architecture helps when:
- **Choosing models**: long context = need to know context window
- **Cost optimization**: knowing attention is O(n²) → keep contexts focused
- **Debugging**: knowing autoregressive → understand streaming
- **Reading papers**: less intimidated

---

## 13. Key Takeaways

✅ Transformer = self-attention + feed-forward, stacked many times
✅ Self-attention: tokens "look at" each other, weight relevance
✅ Multi-head attention: parallel attention, different relationships
✅ Positional encoding: tokens know their position
✅ Autoregressive: generate one token at a time
✅ Context window limited by O(n²) attention cost

**Next:** [05_models_landscape.md](05_models_landscape.md) — Current LLM landscape
