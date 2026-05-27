# Level 5.5 — Embedding Models Deep
**Phase: RAG & Vector DBs | Production-Critical**

## Quick Concepts

- **Embedding** = numeric vector representation of text (typically 256-3072 dims)
- **Embedding model** = neural net that maps text → vector
- **Similarity** = cosine / dot product between vectors (closer = more semantically similar)
- **Dimension** = length of the vector (higher = more info, more storage)
- **Domain adaptation** = fine-tuning embeddings on your data
- **Bi-encoder** = independently embeds query + document (fast retrieval)
- **Cross-encoder** = re-ranks query+document pairs (slow but accurate)
- **MRL (Matryoshka)** = embeddings that can be truncated to lower dims and still work
- **Pooling** = how token vectors combine into one (CLS, mean, max)

---

## Why Embedding Choice Matters

```
Bad embeddings:
   ✗ "cat" and "feline" look unrelated
   ✗ Domain-specific terms confused
   ✗ Multi-language fails
   ✗ Long docs lose context

Good embeddings:
   ✓ Semantic similarity captured
   ✓ Domain-tuned for your corpus
   ✓ Right size for cost + quality trade-off
   ✓ Fast inference for retrieval
```

**Embedding model selection determines RAG quality more than vector DB choice.**

---

## Major Embedding Models (2026)

| Model | Provider | Dims | Strengths | Cost |
|---|---|---|---|---|
| **text-embedding-3-large** | OpenAI | 3072 (or trunc) | High quality, multilingual | $0.13/1M tokens |
| **text-embedding-3-small** | OpenAI | 1536 | Cheap, good quality | $0.02/1M tokens |
| **voyage-3** | Voyage AI | 1024 | Best general (often beats OpenAI) | $0.06/1M |
| **voyage-code-2** | Voyage AI | 1536 | Code-specific | $0.12/1M |
| **cohere-embed-v3** | Cohere | 1024 | Hybrid search optimized | $0.10/1M |
| **e5-large-v2** | OSS (HF) | 1024 | Strong OSS, self-host | Free + compute |
| **BGE-large-en-v1.5** | OSS (BAAI) | 1024 | Top OSS English | Free + compute |
| **BGE-M3** | OSS (BAAI) | 1024 | Multilingual, hybrid (dense+sparse) | Free |
| **nomic-embed-text-v1.5** | OSS | 768 (MRL) | OSS, Matryoshka | Free |
| **mxbai-embed-large** | OSS | 1024 | Strong OSS competitor | Free |

---

## How to Pick (Decision Tree)

```
                    ┌──────────────────────┐
                    │  Domain-specific?    │
                    └─────────┬────────────┘
                              │
                ┌─────────────┼────────────┐
                ▼             ▼            ▼
            Code        Medical       General
                │             │            │
                ▼             ▼            ▼
        voyage-code-2   biobert-style  voyage-3 / OpenAI 3-large
                                            │
                              ┌─────────────┴────────────┐
                              ▼                          ▼
                          Budget?                    Self-host OK?
                              │                          │
                ┌─────────────┴─────────────┐   ┌────────┴───────┐
                ▼                           ▼   ▼                ▼
        $$$ premium quality   $ budget        Yes              No
                │                   │            │                │
                ▼                   ▼            ▼                ▼
      text-embedding-3-large  text-embedding-3-small  BGE-large    voyage-3
                                                      mxbai-embed
```

### Quick recommendations

```
"I just want it to work":
   → text-embedding-3-small  (cheap, good enough)

"I need top quality":
   → voyage-3 OR text-embedding-3-large

"I'm cost-sensitive":
   → text-embedding-3-small (256 dims via MRL)

"I need to self-host":
   → BGE-large-en-v1.5 (English) OR BGE-M3 (multilingual)

"I have code corpus":
   → voyage-code-2

"I need hybrid (dense + sparse)":
   → cohere-embed-v3 OR BGE-M3 (built-in support)
```

---

## Generating Embeddings (Code)

### OpenAI

```python
from openai import OpenAI

client = OpenAI()

# Single
resp = client.embeddings.create(
    input="Hello world",
    model="text-embedding-3-small",
)
vector = resp.data[0].embedding  # 1536 floats

# Batch (much more efficient)
resp = client.embeddings.create(
    input=["text1", "text2", "text3"],
    model="text-embedding-3-small",
)
vectors = [d.embedding for d in resp.data]
```

### Voyage AI

```python
import voyageai

vo = voyageai.Client()
result = vo.embed(
    texts=["text1", "text2"],
    model="voyage-3",
    input_type="document",  # or "query"
)
vectors = result.embeddings
```

**Note:** Voyage uses `input_type` to optimize for queries vs documents (uses different embeddings!).

### Self-host (sentence-transformers)

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-large-en-v1.5")
vectors = model.encode(["text1", "text2"], normalize_embeddings=True)
# Shape: (2, 1024)
```

---

## Matryoshka Representation Learning (MRL)

Newer embeddings support **truncation** — use fewer dimensions without re-embedding.

```python
# Generate full embedding
resp = client.embeddings.create(
    input=text,
    model="text-embedding-3-small",
    dimensions=512,  # truncate to 512 (from 1536)
)

# Or truncate post-hoc:
full = resp.data[0].embedding  # 1536 floats
truncated = full[:256]  # use only first 256 dims

# Re-normalize
import numpy as np
truncated = truncated / np.linalg.norm(truncated)
```

### Why MRL Matters

```
Storage:    1536-dim @ float32 = 6KB per doc
             256-dim @ float32 = 1KB per doc
             → 6x smaller, similar quality (~95%)

Search speed:  smaller vectors = faster index lookups
Cost:         smaller vector DB tier
```

---

## Query vs Document Embeddings

Some models distinguish between embedding queries vs documents:

```python
# Cohere
embed_docs = co.embed(
    texts=docs,
    input_type="search_document",
    model="embed-english-v3.0",
)

embed_query = co.embed(
    texts=[user_query],
    input_type="search_query",
    model="embed-english-v3.0",
)
```

```python
# Voyage
docs_emb = vo.embed(texts=docs, input_type="document", model="voyage-3")
q_emb = vo.embed(texts=[query], input_type="query", model="voyage-3")
```

**Why:** Queries are usually short, documents long. Specialized embeddings handle this asymmetry.

---

## Chunk Size + Embedding Quality

```
Embedding quality varies by input length:

512 tokens:    sweet spot for most models
1000 tokens:   still good, slightly worse
2000+ tokens:  quality degrades (model averages out)

For very long docs:
   ✗ Embed entire doc as one vector → loses detail
   ✓ Chunk into 256-512 token pieces, embed each
   ✓ Store chunks separately, retrieve top-k chunks
```

See [04_chunking_strategies.md](04_chunking_strategies.md) for chunking details.

---

## Similarity Metrics

```python
import numpy as np

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def dot_product(a, b):
    return np.dot(a, b)

def euclidean_distance(a, b):
    return np.linalg.norm(a - b)
```

### When to use

```
Cosine:    most common, normalized to [-1, 1]
           ✓ Use when magnitudes don't matter
           
Dot product: same as cosine IF vectors are normalized
           ✓ Faster (no division)
           ✓ Modern embeddings often pre-normalized

Euclidean: less common in NLP
           ✓ Use only if your data demands it
```

Most embedding APIs return **normalized** vectors → use dot product for speed.

---

## Domain Adaptation (Fine-Tuning Embeddings)

For specialized domains (legal, medical, code), generic embeddings underperform:

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

# 1. Prepare pairs of (query, relevant doc)
train_examples = [
    InputExample(texts=["What is HTTP", "HTTP is a protocol..."]),
    InputExample(texts=["legal precedent", "In Smith v. Jones (1992)..."]),
    # ... thousands of pairs
]

# 2. Load base model
model = SentenceTransformer("BAAI/bge-large-en-v1.5")

# 3. Fine-tune with contrastive loss
train_dataloader = DataLoader(train_examples, batch_size=32)
train_loss = losses.MultipleNegativesRankingLoss(model=model)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=100,
)

model.save("./my-domain-embed")
```

**When to fine-tune:**
- Specialized vocabulary (medical, legal, code)
- Have 10k+ labeled query-doc pairs
- Generic embeddings clearly failing on your data

**Skip fine-tuning if:**
- Generic embeddings work "OK"
- Don't have training data
- Budget/compute constraints

---

## Cost + Storage Math

```python
# 10M documents, 500 tokens each = 5B tokens

# OpenAI text-embedding-3-small @ $0.02/1M tokens
indexing_cost = 5_000_000_000 / 1_000_000 * 0.02
# = $100 for one-time indexing

# Storage in vector DB:
# 1536 dim × 4 bytes (float32) = 6,144 bytes/doc
# 10M × 6,144 = ~57 GB

# With MRL truncation to 512 dim:
# 512 × 4 = 2,048 bytes/doc
# 10M × 2,048 = ~19 GB (3x smaller)

# With float16 quantization:
# 512 × 2 = 1,024 bytes/doc
# 10M × 1,024 = ~10 GB (6x smaller than float32 full)

# Search latency:
# Smaller vectors = faster vector ops + less memory bandwidth
```

---

## Comparing Embedding Quality

### MTEB Benchmark

The Massive Text Embedding Benchmark — gold standard for ranking models.

```
2026 leaderboard (English retrieval):
   1. voyage-3              avg ~76
   2. NV-Embed-v2 (OSS)     avg ~74
   3. bge-large-en-v1.5     avg ~73
   4. text-embedding-3-large avg ~72
   5. mxbai-embed-large     avg ~71
   ...
```

Check current rankings: https://huggingface.co/spaces/mteb/leaderboard

### Custom Evaluation

```python
# Build domain-specific benchmark
queries_with_gold = [
    ("question1", "doc_id_42"),
    ("question2", "doc_id_113"),
    # ...
]

def evaluate_model(model_name, queries, top_k=5):
    correct = 0
    for query, gold_doc_id in queries:
        results = vector_db.search(
            query_embedding=embed(query, model_name),
            top_k=top_k,
        )
        if gold_doc_id in [r.id for r in results]:
            correct += 1
    return correct / len(queries)


# Compare
recall_openai = evaluate_model("text-embedding-3-small", queries)
recall_voyage = evaluate_model("voyage-3", queries)
print(f"OpenAI Recall@5: {recall_openai:.2%}")
print(f"Voyage Recall@5: {recall_voyage:.2%}")
```

---

## Multilingual Embeddings

For non-English / multi-language corpora:

```
✓ BGE-M3                  — multilingual + multi-vector (dense + sparse)
✓ multilingual-e5-large   — strong multilingual
✓ text-embedding-3-large  — OK multilingual
✓ Cohere multilingual     — paid, very good
```

**Indian languages specifically:**
- AI4Bharat embeddings (IndicBERT-based)
- Hindi/Tamil/etc. quality varies — test on your data

---

## Common Pitfalls

```
1. ✗ Mixing embeddings from different models
   → Vectors are incompatible. Re-index entirely.

2. ✗ Embedding very long docs as single vector
   → Quality degrades past ~1000 tokens
   ✓ Chunk first

3. ✗ Forgetting to normalize when using dot product
   → Magnitudes skew similarity
   ✓ Check API docs; use normalize_embeddings=True

4. ✗ Same embed model for query + document when API differs
   → Use input_type correctly (Voyage, Cohere)

5. ✗ Re-embedding query on every search
   ✓ Cache embeddings for repeated queries

6. ✗ Storing 3072-dim when 512 would do
   → 6x storage, slower search
   ✓ Use MRL if model supports

7. ✗ Skipping evaluation
   → Don't know if your embedder is good
   ✓ Build a gold-standard query set

8. ✗ Embedding model version drift
   → text-embedding-ada-002 retired Sept 2025
   ✓ Pin version, watch deprecations

9. ✗ Multilingual generic embeddings for specialized
   → Use language-specific or fine-tune

10. ✗ Synchronous embed-then-insert
    → Slow indexing
    ✓ Batch embed (100s at a time) + bulk insert
```

---

## Production Embedding Pipeline

```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI()
BATCH_SIZE = 100


async def embed_batch(texts: list[str]) -> list[list[float]]:
    resp = await client.embeddings.create(
        input=texts,
        model="text-embedding-3-small",
        dimensions=512,  # MRL for storage savings
    )
    return [d.embedding for d in resp.data]


async def index_documents(docs: list[dict], vector_db):
    """Embed + store docs in batches."""
    
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i+BATCH_SIZE]
        texts = [d["content"] for d in batch]
        
        # Batch embed (rate-limit friendly)
        vectors = await embed_batch(texts)
        
        # Bulk insert
        await vector_db.upsert([
            {
                "id": d["id"],
                "vector": v,
                "payload": {"title": d["title"], "source": d["source"]},
            }
            for d, v in zip(batch, vectors)
        ])
        
        print(f"Indexed {i+len(batch)}/{len(docs)}")
```

---

## Interview Questions

### Q1: Which embedding model would you use and why?

Depends on:
1. **Domain**: code? voyage-code. Medical? Domain-fine-tuned. General? voyage-3 / OpenAI 3-large.
2. **Budget**: small (3-small) vs large.
3. **Self-host?**: BGE-large or mxbai for OSS.
4. **Latency-sensitive?**: smaller models or MRL truncation.

**Always test on your data** — leaderboards are general benchmarks.

### Q2: What is Matryoshka Representation Learning (MRL)?

Training method that makes embedding vectors "nested" — first K dimensions alone form a valid embedding. Lets you truncate at runtime for 3-10x storage savings with minimal quality loss. text-embedding-3 models, nomic-embed, support it.

### Q3: When would you fine-tune embeddings vs use generic?

Fine-tune when (a) you have specialized vocabulary (medical, legal, code), (b) you have 10k+ labeled (query, doc) pairs, (c) generic models clearly underperform your task. Otherwise, use generic + spend that time on chunking, hybrid search, reranking.

### Q4: What's the difference between bi-encoder and cross-encoder?

Bi-encoder: independently embeds query + each doc → fast (precompute doc embeddings). Cross-encoder: takes (query, doc) pair as single input → much slower but more accurate. Use bi-encoder for initial retrieval, cross-encoder for reranking top-K.

### Q5: How do you migrate from one embedding model to another?

(1) Index docs with both models in parallel during transition. (2) A/B test retrieval quality. (3) Cut over reads after metrics confirm new model is better. (4) Retire old vectors. Plan for ~$$ + downtime cost.

---

## Senior Mantras

```
1. Embedding choice > Vector DB choice for quality.

2. Test on YOUR data. Leaderboards are general.

3. Batch embeddings always. 100 at a time minimum.

4. MRL truncation = 3-6x storage savings, ~95% quality.

5. Match query vs doc input_type when API supports.

6. Don't mix embeddings across models. Re-index entirely.

7. Pin model version. Watch deprecation notices.

8. Cache query embeddings. Hot queries = hot cache hit.

9. Fine-tune only when generic clearly fails + you have data.

10. Chunk first, then embed. Don't embed entire books.
```

---

## Related

- [04_chunking_strategies.md](04_chunking_strategies.md) — how to split docs
- [06_hybrid_search.md](06_hybrid_search.md) — dense + sparse search
- [07_reranking.md](07_reranking.md) — cross-encoder reranking
- [08_query_transformation.md](08_query_transformation.md) — HyDE
- [09_ragas_evaluation.md](09_ragas_evaluation.md) — evaluate retrieval quality
- [../../Backend_Developer/Phase2_Database/28_vector_databases_comparison.md](../../Backend_Developer/Phase2_Database/28_vector_databases_comparison.md) — vector DB storage
