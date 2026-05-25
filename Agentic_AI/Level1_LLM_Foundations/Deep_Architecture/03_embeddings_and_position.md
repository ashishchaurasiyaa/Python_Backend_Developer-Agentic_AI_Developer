# Deep Architecture — Doc 3: Embeddings & Position Encoding

> **Goal:** Token IDs (integers) → high-dimensional vectors. Position encoding ka math. **Yahaan se "understanding" start hoti hai.**

---

## 1. The Problem

We have token IDs like `[13225, 1879, 0]`.

These are just **arbitrary numbers** — token 13225 doesn't have any meaning. The number was assigned during tokenizer training.

**For the model to understand**, we need to convert each ID to a **rich representation** — a vector of numbers where:
- Similar concepts → similar vectors
- Different concepts → different vectors
- Mathematical operations make sense

**This is the embedding.**

---

## 2. Embedding = Lookup Table

The embedding layer is just a **giant matrix**:
```
Embedding matrix shape: [vocab_size, hidden_dim]
                      = [100,000, 12,288]   (for GPT-4 scale)
                      = ~1.2 billion learned numbers
```

Each row is the vector for one token.

```python
# Conceptually:
embedding_matrix = [
    [0.12, -0.45, 0.78, ..., 0.23],   # Vector for token 0 (12,288 dims)
    [0.34, 0.11, -0.67, ..., -0.11],  # Vector for token 1
    [-0.05, 0.89, 0.45, ..., 0.34],   # Vector for token 2
    ...
    [0.21, -0.34, 0.56, ..., 0.78],  # Vector for token 99,999
]

# Lookup
def embed(token_id):
    return embedding_matrix[token_id]
```

That's it. Just a lookup.

But the **values** in the matrix are LEARNED during training — that's where the magic is.

---

## 3. What Do Embeddings Capture?

After training, vectors capture **semantic relationships**:

```
embedding("king") - embedding("man") + embedding("woman") ≈ embedding("queen")

embedding("Paris") - embedding("France") + embedding("Japan") ≈ embedding("Tokyo")

embedding("walking") - embedding("walk") + embedding("run") ≈ embedding("running")
```

Famous "vector arithmetic" property — vectors encode meaning.

### Concretely, after training:
- `embedding("dog")` and `embedding("cat")` are **close** (both animals, pets)
- `embedding("dog")` and `embedding("automobile")` are **far** (unrelated)
- `embedding("dog")` and `embedding(" dog")` (with space) might be slightly different but close

---

## 4. Dimensionality — Why 12,288?

| Model | Hidden dim |
|---|---|
| GPT-2 small | 768 |
| GPT-3 | 12,288 |
| GPT-4 | 12,288+ |
| Llama 3 8B | 4096 |
| Llama 3 70B | 8192 |

**Why so big?**
- Each dimension can encode a different "feature"
- Like RGB has 3 dimensions (red, green, blue), word vectors have thousands of "concept dims"
- More dims = more nuanced meanings

**Trade-off:**
- Bigger = more capacity to learn
- Bigger = slower computation, more memory

---

## 5. From Token Sequence → Embedding Sequence

```python
# Input
tokens = [13225, 1879, 0]   # 'Hello', ' world', '!'

# Lookup
embeddings = [
    embedding_matrix[13225],  # shape: [12288]
    embedding_matrix[1879],   # shape: [12288]
    embedding_matrix[0],      # shape: [12288]
]

# Result: matrix of shape [3, 12288]
# 3 tokens, each represented by 12,288-dim vector
```

This matrix is what flows into the transformer.

---

## 6. The Position Problem

So far we have:
```
"Hello world !" → [v1, v2, v3]    (each v is 12,288-dim)
"world Hello !" → [v2, v1, v3]
```

Both have the same vectors. The **set** of vectors is identical.

**Problem:** Transformer's self-attention treats inputs as a SET, not a sequence. It doesn't know order!

```
"Dog bites man" and "Man bites dog"
```
Same words, different meaning. We need to encode **position**.

---

## 7. Solution: Positional Encoding

Add **position information** to each embedding:

```python
final_vector_at_position_i = embedding(token_i) + position_encoding(i)
```

Where:
- `embedding(token_i)` = what the token means (~12,288 dims)
- `position_encoding(i)` = where in the sequence (also ~12,288 dims)
- Adding them → vector that encodes BOTH

Now the model can distinguish "Dog bites man" from "Man bites dog".

---

## 8. Sinusoidal Positional Encoding (Original)

The original Transformer paper (2017) used **sine/cosine** functions:

```python
def positional_encoding(pos, d_model):
    encoding = []
    for i in range(d_model):
        if i % 2 == 0:
            encoding.append(sin(pos / 10000^(i/d_model)))
        else:
            encoding.append(cos(pos / 10000^(i/d_model)))
    return encoding
```

**Why sin/cos?**
- Bounded between -1 and 1 (stable)
- Unique pattern per position
- Math properties allow learning relative positions

**Used in:** Original Transformer, GPT-2, BERT.

---

## 9. Learned Positional Embeddings

Some models just **learn** position embeddings (like word embeddings):

```python
positional_matrix = [
    [...],  # Vector for position 0
    [...],  # Vector for position 1
    [...],  # Vector for position 2
    ...
    [...],  # Vector for position 2047 (max length during training)
]

# Add to token embedding
final = embedding(token_i) + positional_matrix[i]
```

**Used in:** GPT-3, some older models.

**Problem:** Fixed max length — model can't go beyond what it saw in training.

---

## 10. Rotary Positional Embedding (RoPE) — Modern Choice ⭐

Used by:
- Llama, Mistral, Qwen, DeepSeek
- Most modern open-source models

**Key idea:** Instead of ADDING position to embeddings, **ROTATE** the query and key vectors based on position.

### Conceptually:
```
Token at position 0 → no rotation
Token at position 1 → rotate by angle θ
Token at position 2 → rotate by angle 2θ
Token at position 100 → rotate by angle 100θ
```

This rotation happens in **2D pairs** across the vector dimensions.

### Benefits:
1. **Relative positions** captured naturally
2. **Extrapolates** to longer sequences than training (better than learned embeddings)
3. **No extra parameters** to learn

### Code intuition:
```python
def apply_rope(q, k, position):
    # Rotate each 2D pair of dimensions
    # by angle proportional to position
    cos_vals = cos(position * frequencies)
    sin_vals = sin(position * frequencies)
    
    q_rotated = q * cos_vals + rotate_pairs(q) * sin_vals
    k_rotated = k * cos_vals + rotate_pairs(k) * sin_vals
    
    return q_rotated, k_rotated
```

This is applied **inside the attention mechanism**, not at the embedding layer.

---

## 11. ALiBi (Alternative)

Used by some models (like BLOOM):
- Add a **linear bias** to attention scores based on distance
- Closer tokens get higher attention
- No actual position embeddings added

Simpler but less expressive than RoPE.

---

## 12. Context Length Limits

The original sinusoidal/learned position encodings have **fixed max context**:
- GPT-3: 2,048 tokens
- GPT-4 (initial): 8,192 tokens
- Older Llama: 2,048

To extend context, options:
1. **Train longer sequences** (expensive)
2. **Use RoPE with extrapolation** (cheap but quality drops)
3. **Position interpolation** (scale rotation angles, train briefly)
4. **YaRN** (yet another RoPE extension)

Modern long-context models (Claude 3 with 200K, Gemini with 2M) use combinations of these.

---

## 13. Token Type Embeddings (BERT-style)

Some models add additional embeddings:
```
final = word_embedding + position_embedding + segment_embedding
```

BERT used segment embeddings to distinguish sentence A from sentence B.

Modern decoder-only LLMs (GPT, Claude) don't use segment embeddings.

---

## 14. Embedding Layer Parameters

Number of params in embedding layer:
```
Total params = vocab_size × hidden_dim
             = 100,000 × 12,288
             ≈ 1.2 billion parameters
```

That's HUGE — embedding layer alone is bigger than many entire LLMs!

This is why some models **share** input and output projection (tied weights):
- Embedding matrix and output projection matrix use the SAME weights
- Saves 1.2B params

---

## 15. Practical: Inspecting Embeddings

Using OpenAI's embedding API (different from LLM embeddings, but illustrative):

```python
from openai import OpenAI
client = OpenAI()

resp = client.embeddings.create(
    model="text-embedding-3-small",
    input="The cat sat on the mat"
)
# Returns 1536-dim vector
embedding = resp.data[0].embedding
print(f"Dimensions: {len(embedding)}")  # 1536
print(f"First 5 values: {embedding[:5]}")
```

For similarity:
```python
import numpy as np

def cosine_sim(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

emb1 = get_embedding("dog")
emb2 = get_embedding("cat")
emb3 = get_embedding("airplane")

print(cosine_sim(emb1, emb2))   # ~0.7 (related)
print(cosine_sim(emb1, emb3))   # ~0.3 (unrelated)
```

**Note:** These OpenAI embeddings are output of an embedding model, not the internal embeddings of GPT-4. Concept is the same.

---

## 16. Visualizing Embeddings

You can't truly visualize 12,288-dim space, but reduce to 2D/3D:

```python
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

words = ["dog", "cat", "puppy", "kitten", "car", "truck", "airplane"]
embeddings = [get_embedding(w) for w in words]

# Reduce to 2D
pca = PCA(n_components=2)
points_2d = pca.fit_transform(embeddings)

# Plot
plt.scatter(points_2d[:,0], points_2d[:,1])
for i, w in enumerate(words):
    plt.annotate(w, points_2d[i])
```

You'd see:
- "dog", "cat", "puppy", "kitten" cluster together (animals)
- "car", "truck", "airplane" cluster (vehicles)
- Two clusters separated

---

## 17. Embeddings ≠ The Final Story

The embedding is the **starting point**. After embedding:
- Token "bank" has ONE embedding
- But "bank" means different things in:
  - "river bank"
  - "money bank"

The **transformer layers** then **contextualize** the embedding. After 96 layers:
- "bank" in "river bank" → vector pointing toward "river" concepts
- "bank" in "money bank" → vector pointing toward "finance" concepts

So the embedding is the **input**. The transformer **refines** based on context.

---

## 18. Cross-Attention with Multimodal

For models like GPT-4o (text + image):

```
Text tokens → text embeddings (from vocab matrix)
Image patches → vision encoder → image embeddings (different model)

Both concatenated:
[image_emb_1, image_emb_2, ..., text_emb_1, text_emb_2, ...]

All go through same transformer.
```

Embedding spaces of text and image are **aligned** during training (so similar concepts have similar vectors).

---

## 19. Common Mistakes / Misconceptions

### ❌ "Each token has fixed meaning"
NO. The embedding is just the **input**. Layers transform it based on context.

### ❌ "Embeddings are like dictionary lookups"
The matrix is a lookup, but the **values** are learned representations, not definitions.

### ❌ "OpenAI's text-embedding-3 are GPT-4's internal embeddings"
NO. They're separate models trained for different purposes (search/retrieval).

### ❌ "Positional encoding determines word order"
It encodes position info. **Attention** uses this to figure out relationships.

---

## 20. Interview Questions

1. **Q: How does an LLM convert token IDs to vectors?**
   - Embedding matrix lookup. Each row = vector for that token ID.

2. **Q: Why is positional encoding needed?**
   - Self-attention treats input as a set; position encoding adds order info.

3. **Q: RoPE vs learned positional embeddings?**
   - RoPE rotates Q/K based on position; learned embeddings are added like words. RoPE extrapolates better to longer sequences.

4. **Q: Embedding dimensionality trade-offs?**
   - Bigger = more capacity but slower. Modern LLMs: 4K-12K dims.

5. **Q: Why "king - man + woman ≈ queen" works?**
   - During training, vectors learn to encode meaningful relationships in geometric space.

---

## 21. Key Takeaways

✅ Embedding = lookup matrix (vocab_size × hidden_dim)
✅ Each token → high-dim vector (4K-12K)
✅ Vectors encode meaning — similar concepts close, different far
✅ Positional encoding adds order information
✅ RoPE (modern) rotates Q/K based on position
✅ Embedding layer is HUGE (~1.2B params for GPT-4 scale)
✅ Embedding is just the START — transformer refines based on context
✅ Cross-modal: image embeddings + text embeddings share same space

**Next:** [04_attention_complete.md](04_attention_complete.md) — The attention mechanism (Q, K, V math)
