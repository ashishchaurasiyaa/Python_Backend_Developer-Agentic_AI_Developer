"""
Level 1 — Doc 4: Attention & Transformers (PRACTICAL)
=======================================================
Implements the actual math from scratch, in plain numpy — no torch, no
transformers library. Small enough to run line by line and actually see
WHY attention works, not just read a diagram of it.

Topics covered:
  1. Self-attention from scratch (Q, K, V, softmax, weighted sum)
  2. Why attention weights change depending on context (the whole point)
  3. Multi-head attention — same math, split into parallel heads
  4. Positional encoding — why order needs to be injected explicitly
  5. Autoregressive generation, simulated with a toy vocabulary

Install:
  pip install numpy

Run: python 04_attention_transformers_practical.py
"""

import numpy as np

np.random.seed(42)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Self-Attention From Scratch
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Self-Attention, Implemented")
print("=" * 70)

# Toy sequence: 4 tokens, each represented by a 8-dim embedding (normally 768-4096 dims)
tokens = ["The", "cat", "sat", "down"]
d_model = 8
seq_len = len(tokens)

X = np.random.randn(seq_len, d_model)  # stand-in for real token embeddings

# The three learned projections every transformer layer has
W_q = np.random.randn(d_model, d_model) * 0.1
W_k = np.random.randn(d_model, d_model) * 0.1
W_v = np.random.randn(d_model, d_model) * 0.1

Q = X @ W_q  # "what am I looking for?"
K = X @ W_k  # "what do I contain?"
V = X @ W_v  # "what do I actually pass along if attended to?"


def softmax(x, axis=-1):
    x = x - np.max(x, axis=axis, keepdims=True)  # numerical stability
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)


# THE core formula: Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
scores = Q @ K.T / np.sqrt(d_model)         # how much does token i "match" token j?
weights = softmax(scores, axis=-1)          # normalize into a probability distribution per row
output = weights @ V                        # weighted sum of V, weighted by attention

print(f"\n  Tokens: {tokens}")
print(f"  Attention weight matrix ({seq_len}x{seq_len}) — row i = how much token i attends to each token j:\n")
print("       " + "".join(f"{t:>8s}" for t in tokens))
for i, t in enumerate(tokens):
    row = "".join(f"{weights[i][j]:8.3f}" for j in range(seq_len))
    print(f"  {t:5s}{row}")

print(f"\n  Row sums to 1.0 (it's a probability distribution): {weights.sum(axis=-1).round(3)}")
print(f"  Output shape: {output.shape} — same shape as input, but each token's")
print(f"  representation is now a BLEND of every other token, weighted by relevance.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Same Word, Different Context -> Different Attention
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Context Changes What a Token Attends To")
print("=" * 70)
print("""
  This is the actual reason attention beat fixed word embeddings (word2vec-era):
  the word "bank" gets a DIFFERENT representation depending on neighbors —
  "river bank" vs "bank account" attend to completely different tokens.
  Below: two toy sequences sharing the word "bank", watch its attention row change.
""")


def attention_for_sentence(word_list):
    n = len(word_list)
    x = np.random.randn(n, d_model)
    q, k, v = x @ W_q, x @ W_k, x @ W_v
    w = softmax(q @ k.T / np.sqrt(d_model), axis=-1)
    return w


for sentence in [["river", "bank", "flooded"], ["bank", "account", "overdrawn"]]:
    w = attention_for_sentence(sentence)
    bank_idx = sentence.index("bank")
    print(f"  '{' '.join(sentence)}'")
    print(f"    'bank' attends to: " + ", ".join(f"{sentence[j]}={w[bank_idx][j]:.2f}" for j in range(len(sentence))))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Multi-Head Attention
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Multi-Head Attention")
print("=" * 70)

num_heads = 4
d_head = d_model // num_heads
print(f"\n  Splitting d_model={d_model} into {num_heads} heads of size {d_head} each.")
print(f"  Each head runs the SAME attention math independently, on a different")
print(f"  slice of the embedding — one head might learn 'syntax', another 'topic'.")

head_outputs = []
for h in range(num_heads):
    sl = slice(h * d_head, (h + 1) * d_head)
    q_h, k_h, v_h = Q[:, sl], K[:, sl], V[:, sl]
    w_h = softmax(q_h @ k_h.T / np.sqrt(d_head), axis=-1)
    head_outputs.append(w_h @ v_h)

multi_head_output = np.concatenate(head_outputs, axis=-1)  # concat heads back together
print(f"  {num_heads} heads concatenated back to shape: {multi_head_output.shape} (same as single-head output)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Positional Encoding — Why Order Needs to Be Injected
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Positional Encoding")
print("=" * 70)
print("""
  Attention itself is ORDER-BLIND — swap two tokens and the attention math
  above gives the same set of weights, just permuted. "Dog bites man" and
  "Man bites dog" would look identical to raw self-attention. Positional
  encoding fixes this by adding a position-dependent signal to each embedding
  BEFORE attention runs.
""")


def positional_encoding(seq_len, d_model):
    pos = np.arange(seq_len)[:, None]
    i = np.arange(d_model)[None, :]
    angle_rates = 1 / np.power(10000, (2 * (i // 2)) / d_model)
    angles = pos * angle_rates
    pe = np.zeros((seq_len, d_model))
    pe[:, 0::2] = np.sin(angles[:, 0::2])
    pe[:, 1::2] = np.cos(angles[:, 1::2])
    return pe


pe = positional_encoding(seq_len, d_model)
print(f"  Positional encoding matrix ({seq_len}x{d_model}), first 4 dims per position:")
for i in range(seq_len):
    print(f"    pos {i}: {pe[i][:4].round(3)}")
print(f"\n  X_with_position = X + positional_encoding  <- this is literally the line")
print(f"  of code that gives transformers order-awareness.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Autoregressive Generation, Simulated
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Autoregressive Generation (toy vocabulary)")
print("=" * 70)

VOCAB = ["the", "cat", "sat", "on", "mat", "."]
# Fake "next-token probabilities" a real model would compute via a softmax over the vocab
TOY_TRANSITIONS = {
    "<start>": "the",
    "the": "cat",
    "cat": "sat",
    "sat": "on",
    "on": "the",
    "on the": "mat",
    "mat": ".",
}


def generate(max_tokens=6):
    generated = []
    context = "<start>"
    for _ in range(max_tokens):
        next_token = TOY_TRANSITIONS.get(" ".join(generated[-2:]) if len(generated) >= 2 else context)
        if next_token is None:
            break
        generated.append(next_token)
        if next_token == ".":
            break
    return generated


result = generate()
print(f"\n  Generated one token at a time (each step re-attends over ALL previous tokens):")
print(f"  {' '.join(result)}")
print(f"\n  This is autoregressive generation — the SAME attention math from Section 1")
print(f"  runs again at every single generation step, over the growing sequence so far.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Change seq_len to 6 tokens. Does the attention matrix still sum to 1 per row?

MEDIUM:
2. Increase d_model to 64 and num_heads to 8. Print the shape of each head's
   output before and after concatenation.

HARD:
3. Implement CAUSAL masking — a real decoder-only LLM can't attend to future
   tokens. Add an upper-triangular mask of -inf before softmax and re-run
   Section 1. Watch how the attention matrix becomes lower-triangular.

PRO:
4. Implement scaled dot-product attention as a single reusable function
   `attention(Q, K, V, mask=None)` and use it for BOTH self-attention (Section 1)
   and a toy cross-attention (Q from one sequence, K/V from a different one —
   this is what a translation model's decoder does, attending to the encoder).
""")

if __name__ == "__main__":
    print("\nDone. Next: 05_models_landscape_practical.py")
