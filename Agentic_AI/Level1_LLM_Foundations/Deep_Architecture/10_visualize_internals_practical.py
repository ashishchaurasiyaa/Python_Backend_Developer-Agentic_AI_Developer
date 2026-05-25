"""
Deep Architecture — Doc 10: VISUALIZE INTERNALS (PRACTICAL)
=============================================================
Run this to SEE what's happening inside an LLM:
  1. Tokenization — see how text breaks into tokens
  2. Token IDs vs words
  3. Embeddings — get real vectors, measure similarity
  4. Logits inspection — see what next token model is considering
  5. Sampling effects — temperature, top-p
  6. Stream tokens to see autoregressive generation
  7. Token counting + cost estimation
  8. Mini self-attention implementation (numpy)

Install:
  pip install openai tiktoken numpy python-dotenv

Run: python 10_visualize_internals_practical.py
"""

import os
import json
import math
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tokenization — See Text → Tokens
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Tokenization — See Text Become Tokens")
print("=" * 70)


def tokenize_demo(text: str):
    try:
        import tiktoken
    except ImportError:
        print("Install: pip install tiktoken")
        return
    enc = tiktoken.encoding_for_model("gpt-4o")
    tokens = enc.encode(text)
    print(f"\nText: {text!r}")
    print(f"Token count: {len(tokens)}")
    print(f"Characters: {len(text)}")
    print(f"Chars per token: {len(text) / max(len(tokens), 1):.2f}")
    print("\nToken breakdown:")
    for tok_id in tokens:
        decoded = enc.decode([tok_id])
        print(f"  {tok_id:>7} → {decoded!r}")


# Try different texts
samples = [
    "Hello world!",
    "Python is great",
    "नमस्ते दुनिया",       # Hindi
    "你好世界",            # Chinese
    "def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)",  # Code
    "GPT-4 was released in 2023",  # Numbers + acronyms
]

for s in samples:
    tokenize_demo(s)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Whitespace + Capitalization Matter
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Whitespace & Capitalization Effects")
print("=" * 70)

try:
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4o")

    variants = [
        "Python",
        " Python",
        "  Python",
        "python",
        "PYTHON",
        "Python ",  # trailing space
    ]

    print(f"\n  {'Text':<15} {'Token IDs':<25} {'Count'}")
    print(f"  {'-' * 50}")
    for v in variants:
        tokens = enc.encode(v)
        print(f"  {v!r:<15} {tokens!s:<25} {len(tokens)}")

    print("\n☝️ Different spacing/case → different token IDs!")
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Embeddings — Get Real Vectors, Measure Similarity
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Embeddings — Vector Similarity")
print("=" * 70)


def get_embedding(text: str, model: str = "text-embedding-3-small"):
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    client = OpenAI()
    resp = client.embeddings.create(input=text, model=model)
    return resp.data[0].embedding


def cosine_similarity(v1, v2):
    if v1 is None or v2 is None:
        return None
    try:
        import numpy as np
        v1, v2 = np.array(v1), np.array(v2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    except ImportError:
        # Fallback without numpy
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        return dot / (norm1 * norm2)


# Test semantic similarity
print("\nGenerating embeddings and measuring similarities...")
words = ["dog", "cat", "puppy", "kitten", "car", "truck", "airplane"]
embeddings = {w: get_embedding(w) for w in words}

if all(e is not None for e in embeddings.values()):
    print(f"\nVector dimensions: {len(embeddings['dog'])}")
    print("\nCosine similarities:")
    pairs = [
        ("dog", "cat"),       # similar (both pets)
        ("dog", "puppy"),     # very similar (dog → young dog)
        ("dog", "car"),       # different
        ("car", "truck"),     # similar (vehicles)
        ("car", "airplane"),  # related (transport)
        ("cat", "airplane"),  # very different
    ]
    for w1, w2 in pairs:
        sim = cosine_similarity(embeddings[w1], embeddings[w2])
        bar = "█" * int(sim * 20) if sim else "?"
        print(f"  {w1:8s} ↔ {w2:8s}  {sim:.3f}  {bar}")

    print("\n☝️ Note: 'dog' & 'puppy' very similar. 'cat' & 'airplane' very different.")
else:
    print("Skipped (no OPENAI_API_KEY)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Logits Inspection (using logprobs)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: See Token Probabilities (Logits)")
print("=" * 70)


def inspect_top_tokens(prompt: str, n_top: int = 10):
    """Show what tokens model is considering for next position."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1,                       # Generate only 1 token
        logprobs=True,                      # Return probabilities
        top_logprobs=n_top                  # Show top N
    )
    return resp.choices[0].logprobs.content[0].top_logprobs


tests = [
    "The capital of France is",
    "2 + 2 =",
    "The largest planet in our solar system is",
]

for prompt in tests:
    print(f"\nPrompt: {prompt!r}")
    top_tokens = inspect_top_tokens(prompt, n_top=8)
    if top_tokens:
        print(f"  Model's top candidates for next token:")
        for tp in top_tokens:
            prob = math.exp(tp.logprob) * 100
            bar = "█" * int(prob / 5)
            print(f"    {tp.token!r:15s} {prob:>6.2f}%  {bar}")
    else:
        print("  Skipped (no API key)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Sampling Effects — Temperature
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Temperature Effects on Sampling")
print("=" * 70)


def generate_with_temp(prompt: str, temperature: float, n: int = 5):
    if not os.getenv("OPENAI_API_KEY"):
        return ["[NO_API_KEY]"] * n
    from openai import OpenAI
    client = OpenAI()
    outputs = []
    for _ in range(n):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=20,
            )
            outputs.append(resp.choices[0].message.content)
        except Exception as e:
            outputs.append(f"[Error: {e}]")
    return outputs


prompt = "Complete this in exactly 5 words: Today is a beautiful"

for temp in [0.0, 0.5, 1.0, 1.5]:
    print(f"\n[Temperature = {temp}]")
    samples = generate_with_temp(prompt, temp, n=3)
    for i, s in enumerate(samples):
        print(f"  Run {i + 1}: {s}")

print("\n☝️ Higher temperature → more varied outputs")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Streaming — See Autoregressive Generation Live
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Streaming — See Tokens Generated One at a Time")
print("=" * 70)


def stream_and_count(prompt: str):
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    from openai import OpenAI
    import time
    client = OpenAI()
    print(f"Prompt: {prompt}")
    print("Output (streaming): ", end="", flush=True)

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=80,
    )

    start = time.time()
    first_token_time = None
    token_count = 0

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            if first_token_time is None:
                first_token_time = time.time() - start
            token_count += 1
            print(delta, end="", flush=True)

    total_time = time.time() - start
    print(f"\n\n  Time to first token: {first_token_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Total tokens generated: {token_count}")
    if token_count > 0:
        print(f"  Tokens/second: {token_count / total_time:.1f}")


stream_and_count("Explain photosynthesis in 3 sentences")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Token Counting + Cost Estimation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Token Counting + Cost Estimation")
print("=" * 70)

PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.25, "output": 1.25},
    "gemini-2-pro": {"input": 1.25, "output": 5.00},
}


def estimate(text_input: str, output_tokens: int = 200):
    """Estimate cost across providers for a given input + output."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o")
        input_tokens = len(enc.encode(text_input))
    except ImportError:
        input_tokens = len(text_input) // 4

    print(f"\nInput: {text_input[:60]}...")
    print(f"Input tokens: {input_tokens}")
    print(f"Expected output: {output_tokens} tokens")
    print(f"\n{'Model':<25} {'Input $':<10} {'Output $':<10} {'Total':<10}")
    print("-" * 55)
    for model, prices in PRICING.items():
        in_cost = input_tokens * prices["input"] / 1_000_000
        out_cost = output_tokens * prices["output"] / 1_000_000
        total = in_cost + out_cost
        print(f"  {model:<23} ${in_cost:.6f}  ${out_cost:.6f}  ${total:.6f}")


estimate(
    text_input="What is Python? Python is a high-level programming language used for AI, web dev, data science...",
    output_tokens=500
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Mini Self-Attention Implementation (numpy)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: Mini Self-Attention from Scratch (numpy)")
print("=" * 70)


def softmax(x, axis=-1):
    """Numerically stable softmax."""
    try:
        import numpy as np
        x_max = np.max(x, axis=axis, keepdims=True)
        e_x = np.exp(x - x_max)
        return e_x / np.sum(e_x, axis=axis, keepdims=True)
    except ImportError:
        return None


def self_attention(X, mask=None):
    """Run self-attention from scratch.

    X: input matrix of shape [seq_len, hidden_dim]
    Returns: output of shape [seq_len, hidden_dim]
    """
    try:
        import numpy as np
        np.random.seed(42)
        seq_len, hidden_dim = X.shape

        # Initialize random Q, K, V projection matrices
        W_Q = np.random.randn(hidden_dim, hidden_dim) * 0.1
        W_K = np.random.randn(hidden_dim, hidden_dim) * 0.1
        W_V = np.random.randn(hidden_dim, hidden_dim) * 0.1

        # Compute Q, K, V
        Q = X @ W_Q   # [seq_len, hidden_dim]
        K = X @ W_K
        V = X @ W_V

        # Attention scores
        scores = Q @ K.T  # [seq_len, seq_len]

        # Scale
        scores = scores / np.sqrt(hidden_dim)

        # Apply causal mask (lower triangular)
        if mask is not None:
            scores = np.where(mask == 0, -1e9, scores)

        # Softmax
        attn_weights = softmax(scores, axis=-1)

        # Weighted sum of values
        output = attn_weights @ V

        return output, attn_weights
    except ImportError:
        return None, None


# Demo
try:
    import numpy as np

    # Toy example: 4 tokens, 8-dim each
    seq_len = 4
    hidden_dim = 8

    np.random.seed(0)
    X = np.random.randn(seq_len, hidden_dim)

    print(f"\nInput: {seq_len} tokens × {hidden_dim} dimensions")
    print(f"Input shape: {X.shape}")

    # Causal mask
    mask = np.tril(np.ones((seq_len, seq_len)))
    print(f"\nCausal mask (1=attend, 0=mask):\n{mask}")

    output, attn = self_attention(X, mask)
    print(f"\nAttention weights (rows attend to columns):")
    print(np.round(attn, 3))

    print(f"\nObservations:")
    print(f"  - Row 0: only attends to position 0 (1.0) — first token")
    print(f"  - Row 1: attends to 0 and 1 — bigger weights toward more relevant")
    print(f"  - Lower-right triangle: 0 (masked, can't see future)")
    print(f"\nOutput shape: {output.shape} (same as input)")
except ImportError:
    print("Install: pip install numpy")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 9: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Modify SECTION 1 — tokenize text in your native language. Compare token count vs English.
2. Try SECTION 4 with ambiguous prompts. Observe which tokens model considers.

MEDIUM:
3. Compute similarity for 10 word pairs you find interesting.
   E.g., (king, queen), (Python, Java), (happy, joyful).
4. Run SECTION 5 with extreme temperatures (0, 2, 5). What breaks?

HARD:
5. Extend the mini self-attention (SECTION 8) to multi-head attention.
   Hint: split hidden_dim into n_heads × head_dim.
6. Implement greedy vs top-p sampling from scratch on logits returned by API.

PRO:
7. Build a "transformer visualizer":
   - Input text
   - Show tokenization
   - Show top-K candidates at each generation step
   - Visualize attention weights (heatmap)
""")


if __name__ == "__main__":
    print("\n✅ You've now SEEN the internals — tokens, embeddings, attention, logits, sampling!")
    print("👉 This is what happens every time you call client.chat.completions.create(...)")
