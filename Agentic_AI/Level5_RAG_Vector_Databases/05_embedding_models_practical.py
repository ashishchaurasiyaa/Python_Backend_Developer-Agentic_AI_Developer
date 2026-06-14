"""
Level 5.5 -- Embedding Models Practical (Hinglish Lab)
=======================================================

KYA SEEKHENGE (What we will learn):
  1. Embedding kya hai -- text ko vector banana (theory grounding)
  2. Cosine similarity -- vectors ke beech semantic closeness
  3. Matryoshka (MRL) truncation -- dimensions kaise cut karo bina quality khoye
  4. Query vs Document embeddings -- alag input_type kyun important hai
  5. Batch embedding -- ek baar mein bahut sara text embed karna
  6. Cost + storage math -- dimension choice ka real cost
  7. Model comparison table -- kaunsa model kab use karo
  8. Bi-encoder vs Cross-encoder -- retrieval vs reranking
  9. Common pitfalls -- galtiyan jo production mein hoti hain
  10. Offline self-demo -- bina key ke bhi chalega

KAISE CHALANA (How to run):
  uv run /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/05_embedding_models_practical.py

  Ya full command:
  cd /tmp && uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/05_embedding_models_practical.py"

KEYS (optional, live calls enable ho jaate hain):
  export GROQ_API_KEY=gsk_xxxx   # groq free tier
  Bina key ke bhi EXIT 0 -- fake/demo data use hoga.

Theory reference: Level5_RAG_Vector_Databases/05_embedding_models.md
"""

import os
import sys
import math
import json
import time
import random


# ---------------------------------------------------------------------------
# GROQ CLIENT HELPER
# Theory: Embedding generation ke liye LLM client chahiye.
# Yahan hum groq free tier use karte hain -- OpenAI ka base_url switch karo.
# IMPORTANT: OpenAI() None key pe crash karta hai; isliye placeholder dete hain.
# ---------------------------------------------------------------------------

def get_client():
    """
    Groq free tier ka client return karta hai.
    Agar GROQ_API_KEY nahi hai toh 'placeholder' use hoga --
    live API call fail hogi but client construct ho jayega (no crash).
    """
    from openai import OpenAI  # openai SDK groq bhi support karta hai via base_url
    api_key = os.getenv("GROQ_API_KEY") or "placeholder"
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )


# ---------------------------------------------------------------------------
# GROQ KE PAAS EMBEDDING MODEL NAHI HAI -- hum numpy se fake embeddings banate
# hain for demo. Real case mein OpenAI / Voyage / sentence-transformers use karo.
# Yeh function seed-based deterministic vector deta hai taki similarity demo
# realistic lage (same text = same vector).
# ---------------------------------------------------------------------------

def _fake_embed(text: str, dims: int = 1536) -> list:
    """
    Deterministic pseudo-embedding banata hai -- text hash se seed.
    Theory: Embedding = text ka numeric vector representation.
    Yeh REAL embedding nahi hai; sirf structure demonstrate karta hai.
    """
    rng = random.Random(hash(text) % (2**32))
    vec = [rng.gauss(0, 1) for _ in range(dims)]
    # Normalize karo -- zyaadatar models normalized vectors dete hain
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def embed_texts_offline(texts: list, dims: int = 1536) -> list:
    """Offline mode: deterministic fake embeddings (normalized)."""
    return [_fake_embed(t, dims) for t in texts]


def embed_texts_live(texts: list, dims: int = 1536) -> list:
    """
    Live mode: Groq ke paas embedding nahi -- OpenAI text-embedding-3-small try karta hai.
    Isliye hum groq LLM se ek workaround use karte hain ya gracefully fall back.
    Production mein: OpenAI / Voyage / sentence-transformers use karo.
    """
    # Groq OpenAI-compatible API provide karta hai but embedding endpoint nahi hai.
    # Toh hum live mode mein bhi fake use karte hain with a clear note.
    print("  [NOTE] Groq embedding endpoint available nahi hai.")
    print("  [NOTE] Production: openai.text-embedding-3-small ya voyage-3 use karo.")
    print("  [NOTE] Demo ke liye deterministic fake vectors use ho rahe hain.\n")
    return embed_texts_offline(texts, dims)


HAS_KEY = bool(os.getenv("GROQ_API_KEY"))
MOCK_MODE = not HAS_KEY

# ---------------------------------------------------------------------------
# NUMPY -- optional. Agar available hai toh use karo, warna pure Python fallback.
# ---------------------------------------------------------------------------
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore


# ===========================================================================
# UTILITY FUNCTIONS
# Theory reference: 05_embedding_models.md -- Similarity Metrics section
# ===========================================================================

def cosine_similarity(a: list, b: list) -> float:
    """
    Cosine similarity compute karta hai -- most common metric for embeddings.
    Theory: Cosine = dot(a,b) / (|a| * |b|)
    Range: [-1, 1] -- 1 matlab bilkul same, 0 matlab unrelated, -1 matlab opposite.
    Normalized vectors ke liye dot product == cosine (division skip ho sakti hai).
    """
    if HAS_NUMPY:
        a_np = np.array(a)
        b_np = np.array(b)
        return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))
    # Pure Python fallback
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def dot_product(a: list, b: list) -> float:
    """
    Dot product -- normalized vectors ke liye cosine ke barabar, faster bhi.
    Theory: Modern embedding APIs normalized vectors dete hain -- dot use karo.
    """
    return sum(x * y for x, y in zip(a, b))


def euclidean_distance(a: list, b: list) -> float:
    """
    Euclidean distance -- NLP mein kam use hota hai cosine se.
    Theory: Sirf tab use karo jab data ki magnitude matter kare.
    """
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def normalize_vector(vec: list) -> list:
    """
    Vector normalize karo (unit vector banana).
    Theory: MRL truncation ke baad re-normalize ZAROOR karo.
    """
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def mrl_truncate(vec: list, target_dims: int) -> list:
    """
    Matryoshka (MRL) truncation -- pehle K dimensions lo aur re-normalize karo.
    Theory: MRL-trained models (text-embedding-3, nomic-embed) support karte hain.
    Storage savings: 1536 -> 256 dims = 6x smaller, ~95% quality retain.
    """
    truncated = vec[:target_dims]
    return normalize_vector(truncated)


def storage_bytes(dims: int, dtype_bytes: int = 4) -> int:
    """
    Ek vector ka storage bytes mein.
    Theory: dims x float32 (4 bytes) = total bytes per doc.
    """
    return dims * dtype_bytes


# ===========================================================================
# SECTION 1: EMBEDDING KYA HAI -- CONCEPT DEMO
# Theory: Embedding = text ka numeric vector, semantic meaning capture karta hai
# ===========================================================================

def section_1_embedding_concepts():
    print("=" * 65)
    print("SECTION 1: Embedding Kya Hai -- Concept aur Structure")
    print("=" * 65)

    print("""
  Theory (05_embedding_models.md se):
  ------------------------------------
  Embedding = numeric vector representation of text (256-3072 dims)
  Embedding model = neural net jo text ko vector mein map karta hai
  Similarity = cosine / dot product between vectors (closer = more similar)
  Pooling = token vectors kaise ek vector mein combine hote hain (CLS, mean, max)

  Real-world analogy (Hinglish):
  "cat" aur "feline" -- dono sirf naamkaran ka fark hai, matlab same hai.
  Bad embedding model ye nahi samjhega.
  Good embedding model inhe PAAS wale vectors dega.
""")

    # Ek chhota example -- 4-dim vectors for illustration
    print("  Example: 4-dimensional fake vectors (illustration ke liye)")
    toy_vecs = {
        "cat":      [0.9, 0.1, 0.05, 0.02],
        "feline":   [0.88, 0.12, 0.06, 0.01],  # cat ke karib
        "dog":      [0.70, 0.50, 0.10, 0.05],   # animal hai, thoda alag
        "car":      [0.02, 0.01, 0.95, 0.88],   # bilkul alag domain
    }
    # Normalize karo
    toy_vecs = {k: normalize_vector(v) for k, v in toy_vecs.items()}

    words = list(toy_vecs.keys())
    print(f"\n  {'Pair':<22}  {'Cosine Sim':>12}  {'Interpretation'}")
    print("  " + "-" * 55)
    pairs = [
        ("cat", "feline"),
        ("cat", "dog"),
        ("cat", "car"),
        ("dog", "car"),
    ]
    for w1, w2 in pairs:
        sim = cosine_similarity(toy_vecs[w1], toy_vecs[w2])
        if sim > 0.95:
            interp = "Almost identical meaning"
        elif sim > 0.7:
            interp = "Related / same domain"
        elif sim > 0.3:
            interp = "Loosely related"
        else:
            interp = "Unrelated / different domain"
        print(f"  {w1+' vs '+w2:<22}  {sim:>12.4f}  {interp}")

    print("""
  Key insight: Good embeddings mein similar meaning = high cosine score.
  RAG mein hum isi score se "relevant documents" dhundte hain.
""")


# ===========================================================================
# SECTION 2: MODEL COMPARISON TABLE
# Theory: 05_embedding_models.md -- Major Embedding Models (2026)
# ===========================================================================

def section_2_model_comparison():
    print("=" * 65)
    print("SECTION 2: Major Embedding Models -- Kaunsa Kab Use Karo")
    print("=" * 65)

    print("""
  Theory (from 05_embedding_models.md):
  Embedding model selection determines RAG quality more than vector DB choice.
  Matlab: sahi model chunna vector DB se zyaada important hai.
""")

    models = [
        # (name,               provider,   dims,  cost_per_1m,  strength)
        ("text-embedding-3-large", "OpenAI",   3072, "$0.13",      "High quality, multilingual"),
        ("text-embedding-3-small", "OpenAI",   1536, "$0.02",      "Cheap, good quality, MRL"),
        ("voyage-3",               "Voyage AI",1024, "$0.06",      "Best general (beats OpenAI often)"),
        ("voyage-code-2",          "Voyage AI",1536, "$0.12",      "Code-specific corpus ke liye"),
        ("cohere-embed-v3",        "Cohere",   1024, "$0.10",      "Hybrid search optimized"),
        ("BGE-large-en-v1.5",      "OSS/BAAI", 1024, "Free+GPU",  "Top OSS English model"),
        ("BGE-M3",                 "OSS/BAAI", 1024, "Free+GPU",  "Multilingual, dense+sparse"),
        ("nomic-embed-text-v1.5",  "OSS",       768, "Free+GPU",  "Matryoshka support"),
        ("mxbai-embed-large",      "OSS",      1024, "Free+GPU",  "Strong OSS competitor"),
    ]

    print(f"  {'Model':<28} {'Provider':<12} {'Dims':>5} {'Cost/1M':>9}  Strengths")
    print("  " + "-" * 80)
    for name, provider, dims, cost, strength in models:
        print(f"  {name:<28} {provider:<12} {dims:>5} {cost:>9}  {strength}")

    print("""
  Decision Tree (simplified):
    Domain = Code?    --> voyage-code-2
    Domain = Medical? --> biobert-style fine-tuned
    Self-host chahiye?--> BGE-large-en-v1.5 (English) ya BGE-M3 (multi-lang)
    Budget tight?     --> text-embedding-3-small (256 dims via MRL)
    Best quality?     --> voyage-3 ya text-embedding-3-large
    Multilingual?     --> BGE-M3 ya multilingual-e5-large

  MTEB Benchmark 2026 (English retrieval):
    1. voyage-3              avg ~76
    2. NV-Embed-v2 (OSS)     avg ~74
    3. bge-large-en-v1.5     avg ~73
    4. text-embedding-3-large avg ~72
    Full list: https://huggingface.co/spaces/mteb/leaderboard
""")


# ===========================================================================
# SECTION 3: SIMILARITY METRICS -- COSINE, DOT PRODUCT, EUCLIDEAN
# Theory: 05_embedding_models.md -- Similarity Metrics section
# ===========================================================================

def section_3_similarity_metrics():
    print("=" * 65)
    print("SECTION 3: Similarity Metrics -- Cosine, Dot, Euclidean")
    print("=" * 65)

    print("""
  Theory:
    Cosine    = most common. Range [-1, 1]. Magnitude ignore karta hai.
    Dot Product = normalized vectors ke liye cosine ke barabar. Faster (no division).
    Euclidean = distance. NLP mein kam use hota hai.
    Tip: Modern APIs normalized vectors dete hain -- dot product use karo (faster).
""")

    # Real-ish texts ke liye fake embeddings generate karo
    texts = {
        "Python programming language":         _fake_embed("Python programming language"),
        "Python snake reptile":                 _fake_embed("Python snake reptile"),
        "Machine learning with Python":         _fake_embed("Machine learning with Python"),
        "Deep learning neural networks":        _fake_embed("Deep learning neural networks"),
        "SQL database queries":                 _fake_embed("SQL database queries"),
        "Cooking pasta Italian food":           _fake_embed("Cooking pasta Italian food"),
    }

    query_text = "Python for data science"
    query_vec  = _fake_embed(query_text)

    print(f"  Query: '{query_text}'")
    print(f"\n  {'Document':<40} {'Cosine':>8}  {'Dot Prod':>9}  {'Euclidean':>10}")
    print("  " + "-" * 75)

    results = []
    for doc_text, doc_vec in texts.items():
        cos  = cosine_similarity(query_vec, doc_vec)
        dot  = dot_product(query_vec, doc_vec)
        euc  = euclidean_distance(query_vec, doc_vec)
        results.append((cos, doc_text, dot, euc))

    results.sort(reverse=True)
    for cos, doc_text, dot, euc in results:
        print(f"  {doc_text:<40} {cos:>8.4f}  {dot:>9.4f}  {euc:>10.4f}")

    print("""
  Note: Yahan fake (random) embeddings hain isliye ranking arbitrary lag sakti hai.
  Real embeddings mein "Python for data science" ko "Machine learning with Python"
  aur "Python programming language" se CLOSE hona chahiye.
""")


# ===========================================================================
# SECTION 4: MATRYOSHKA (MRL) TRUNCATION
# Theory: 05_embedding_models.md -- Matryoshka Representation Learning (MRL)
# ===========================================================================

def section_4_mrl_truncation():
    print("=" * 65)
    print("SECTION 4: Matryoshka (MRL) -- Dimensions Truncate Karo")
    print("=" * 65)

    print("""
  Theory (05_embedding_models.md):
    MRL = training method jo vectors ko "nested" banata hai.
    Pehle K dimensions akele bhi valid embedding hain.
    Runtime pe truncate karo -- no re-embedding needed!
    Storage savings: 6x smaller, ~95% quality retain.

    Models supporting MRL:
      text-embedding-3-small / text-embedding-3-large
      nomic-embed-text-v1.5
      mxbai-embed-large

    OpenAI API pe directly truncate kar sakte ho:
      client.embeddings.create(input=text, model="text-embedding-3-small", dimensions=512)

    Ya post-hoc truncate karo (full vector ka pehla K slice):
      truncated = full_vec[:512]
      truncated = normalize(truncated)  # RE-NORMALIZE ZAROOR KARO!
""")

    # Demo: 1536-dim vector generate karo aur truncate karo
    full_vec = _fake_embed("Ek important document ka embedding", dims=1536)
    print(f"  Full vector dims:  {len(full_vec)}")

    print(f"\n  {'Dims':<8} {'Storage (float32)':>20}  {'Relative Size':>14}  {'Sim vs full':>12}")
    print("  " + "-" * 62)

    ref_sim = 1.0  # 1536 vs 1536 = 1.0
    for target_dims in [1536, 1024, 512, 256, 128, 64]:
        truncated    = mrl_truncate(full_vec, target_dims)
        # Similarity kaise compare karein: full vs truncated (normalized)
        # Padding karke compare karo (full ko same dims tak cut)
        full_cut     = normalize_vector(full_vec[:target_dims])
        sim_internal = cosine_similarity(truncated, full_cut)
        bytes_used   = storage_bytes(target_dims, 4)
        ratio        = target_dims / 1536
        print(f"  {target_dims:<8} {bytes_used:>16} bytes  {ratio:>13.1%}  {sim_internal:>12.4f}")

    print("""
  Cost + Storage Math (10M documents, 500 tokens each = 5B tokens):
    OpenAI text-embedding-3-small @ $0.02/1M tokens:
    Indexing cost = 5B / 1M * $0.02 = $100 one-time

    Storage:
    1536 dim x 4 bytes x 10M docs = ~57 GB
    512  dim x 4 bytes x 10M docs = ~19 GB  (3x smaller)
    512  dim x 2 bytes x 10M docs = ~10 GB  (6x smaller, float16 quantization)

  KEY TAKEAWAY: MRL + float16 = 6x storage savings with ~95% quality.
""")


# ===========================================================================
# SECTION 5: QUERY vs DOCUMENT EMBEDDINGS
# Theory: 05_embedding_models.md -- Query vs Document Embeddings
# ===========================================================================

def section_5_query_vs_document():
    print("=" * 65)
    print("SECTION 5: Query vs Document Embeddings -- input_type Kyun Zaroori")
    print("=" * 65)

    print("""
  Theory:
    Kuch models (Voyage, Cohere) query aur document ke liye ALAG embeddings dete hain.
    Query = short, baar baar aata hai
    Document = long, precomputed rehta hai
    Ye asymmetry handle karna quality improve karta hai.

  Voyage AI:
    docs_emb = vo.embed(texts=docs,    input_type="document", model="voyage-3")
    q_emb    = vo.embed(texts=[query], input_type="query",    model="voyage-3")

  Cohere:
    embed_docs = co.embed(texts=docs,   input_type="search_document", model="embed-english-v3.0")
    embed_q    = co.embed(texts=[q],    input_type="search_query",    model="embed-english-v3.0")

  PITFALL #4 (from theory doc):
    Same embed model for query + document jab API differs =>
    galat input_type use karna quality gira deta hai.

  BGE models ke liye instruction prefix add karo:
    query_prefix = "Represent this sentence for searching relevant passages: "
    BGE query = prefix + user_query
    BGE document = plain text (no prefix)
""")

    # Demo: BGE-style prefix embedding (fake)
    query_raw   = "Python mein async kaise kaam karta hai"
    query_bge   = "Represent this sentence for searching relevant passages: " + query_raw
    doc_text    = "Python asyncio event loop ko single thread mein chalaata hai..."

    q_raw_vec   = _fake_embed(query_raw)
    q_bge_vec   = _fake_embed(query_bge)
    doc_vec     = _fake_embed(doc_text)

    sim_raw = cosine_similarity(q_raw_vec, doc_vec)
    sim_bge = cosine_similarity(q_bge_vec, doc_vec)

    print(f"  Query (raw)   vs doc sim: {sim_raw:.4f}")
    print(f"  Query (BGE prefix) sim:   {sim_bge:.4f}")
    print("  (Fake vecs hain -- real data mein BGE prefix = higher retrieval accuracy)")
    print()


# ===========================================================================
# SECTION 6: BATCH EMBEDDING -- PRODUCTION PATTERN
# Theory: 05_embedding_models.md -- Production Embedding Pipeline
# ===========================================================================

def section_6_batch_embedding():
    print("=" * 65)
    print("SECTION 6: Batch Embedding -- Production-Ready Pattern")
    print("=" * 65)

    print("""
  Theory (05_embedding_models.md):
    Senior Mantra #3: Batch embeddings always. 100 at a time minimum.
    Synchronous embed-then-insert = slow indexing (Pitfall #10)
    Production: AsyncOpenAI + BATCH_SIZE=100 + bulk insert
""")

    # Mock batch embedding pipeline
    BATCH_SIZE = 5  # demo ke liye chhota rakha

    sample_docs = [
        {"id": f"doc_{i}", "content": f"Document {i}: Python mein {['async', 'OOP', 'RAG', 'embedding', 'vectorDB', 'chunking', 'retrieval', 'LLM', 'agent', 'tools'][i % 10]} ke baare mein jaankari"}
        for i in range(23)
    ]

    print(f"  Total docs: {len(sample_docs)}, Batch size: {BATCH_SIZE}")
    print("  Embedding pipeline shuru...")

    all_vectors = {}
    total_batches = math.ceil(len(sample_docs) / BATCH_SIZE)
    t_start = time.time()

    for batch_num in range(total_batches):
        batch = sample_docs[batch_num * BATCH_SIZE : (batch_num + 1) * BATCH_SIZE]
        texts = [d["content"] for d in batch]
        # Offline mode: fake embeddings
        vecs  = embed_texts_offline(texts, dims=512)
        for doc, vec in zip(batch, vecs):
            all_vectors[doc["id"]] = vec
        indexed = min((batch_num + 1) * BATCH_SIZE, len(sample_docs))
        print(f"    Batch {batch_num+1}/{total_batches}: {len(batch)} docs indexed ({indexed}/{len(sample_docs)})")

    elapsed = time.time() - t_start
    print(f"\n  Total time: {elapsed:.3f}s (fake/offline mode)")
    print(f"  Total vectors stored: {len(all_vectors)}")
    print(f"  Dims per vector: 512 (MRL truncated)")

    # Show production code pattern
    PROD_CODE = '''\
  Production async pattern (OpenAI):
  -----------------------------------
  import asyncio
  from openai import AsyncOpenAI

  client = AsyncOpenAI()
  BATCH_SIZE = 100

  async def embed_batch(texts: list[str]) -> list[list[float]]:
      resp = await client.embeddings.create(
          input=texts,
          model="text-embedding-3-small",
          dimensions=512,  # MRL truncation -- 3x storage savings
      )
      return [d.embedding for d in resp.data]

  async def index_documents(docs: list[dict], vector_db):
      for i in range(0, len(docs), BATCH_SIZE):
          batch  = docs[i:i+BATCH_SIZE]
          texts  = [d["content"] for d in batch]
          vecs   = await embed_batch(texts)
          await vector_db.upsert([
              {"id": d["id"], "vector": v, "payload": {"title": d.get("title")}}
              for d, v in zip(batch, vecs)
          ])
          print(f"Indexed {i+len(batch)}/{len(docs)}")
'''
    print(PROD_CODE)

    return all_vectors


# ===========================================================================
# SECTION 7: SENTENCE-TRANSFORMERS -- SELF-HOST OSS MODEL
# Theory: 05_embedding_models.md -- Self-host (sentence-transformers)
# Lazy import kyunki heavy library hai; graceful fallback dete hain
# ===========================================================================

def section_7_sentence_transformers():
    print("=" * 65)
    print("SECTION 7: Self-Host Embeddings -- sentence-transformers (OSS)")
    print("=" * 65)

    print("""
  Theory:
    Self-host karna = no per-token cost, data privacy, offline capability.
    Best OSS models:
      BGE-large-en-v1.5 (English)  -- 1024 dims, MTEB ~73
      BGE-M3 (multilingual)        -- 1024 dims, dense+sparse
      mxbai-embed-large-v1          -- 1024 dims, strong OSS
      nomic-embed-text-v1.5         -- 768 dims, MRL support

  Code pattern:
    from sentence_transformers import SentenceTransformer
    model  = SentenceTransformer("BAAI/bge-large-en-v1.5")
    vecs   = model.encode(texts, normalize_embeddings=True)  # (N, 1024)
    # normalize_embeddings=True -- dot product use kar sakte ho cos ke bajay

  ChromaDB integration:
    import chromadb
    chroma_client = chromadb.Client()
    collection = chroma_client.create_collection("my_docs")
    collection.add(documents=texts, ids=ids)
    results = collection.query(query_texts=[user_query], n_results=5)
""")

    # Lazy import -- only if available
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        print("  [sentence-transformers] Available hai! Real model load karna possible.")
        print("  Demo ke liye skip kar rahe hain (model download time bachane ke liye).")
        print("  Apne code mein:  model = SentenceTransformer('BAAI/bge-large-en-v1.5')")
    except ImportError:
        print("  [sentence-transformers] Installed nahi hai -- that's OK!")
        print("  Install karo (optional):  pip install sentence-transformers")
        print("  Ya pyproject.toml mein add karo.")
        print("  Demo ke liye offline fake embeddings use ho rahe hain.\n")

    # ChromaDB lazy import
    try:
        import chromadb  # noqa: F401
        print("  [chromadb] Available hai! Vector store ready.")
    except ImportError:
        print("  [chromadb] Installed nahi hai -- that's OK!")
        print("  Install karo (optional):  pip install chromadb")
        print("  langchain-chroma already pyproject.toml mein hai.\n")

    print("  Fake demo: BGE-style normalized embeddings (self-hosted pattern)")
    texts_demo = [
        "Python async programming kaise kaam karta hai",
        "Machine learning mein gradient descent kya hota hai",
        "Indian cricket team ka best batsman kaun hai",
    ]
    # normalize_embeddings=True simulate karo -- already normalized hain fake vecs mein
    vecs = embed_texts_offline(texts_demo, dims=1024)
    for t, v in zip(texts_demo, vecs):
        norm = math.sqrt(sum(x * x for x in v))
        print(f"  Text: '{t[:50]}...' | Dims: {len(v)} | Norm: {norm:.4f}")
    print()


# ===========================================================================
# SECTION 8: BI-ENCODER vs CROSS-ENCODER
# Theory: 05_embedding_models.md -- Quick Concepts + Interview Q4
# ===========================================================================

def section_8_bi_vs_cross_encoder():
    print("=" * 65)
    print("SECTION 8: Bi-Encoder vs Cross-Encoder -- Retrieval vs Reranking")
    print("=" * 65)

    print("""
  Theory (05_embedding_models.md):
  ----------------------------------
  Bi-encoder:
    - Query aur Document ko INDEPENDENTLY embed karta hai
    - Pre-computed doc embeddings use kar sakte hain
    - Fast! O(1) per query for retrieval
    - Use karo: initial retrieval (top-K dhundna)
    - Example: text-embedding-3-small, BGE-large

  Cross-encoder:
    - (Query, Document) PAIR ko ek saath input deta hai
    - Document embeddings precompute nahi kar sakte (query-dependent)
    - Slow (har doc ke liye full model forward pass)
    - But MUCH more accurate -- captures query-doc interaction
    - Use karo: reranking top-K results
    - Example: cross-encoder/ms-marco-MiniLM-L-6-v2

  Production RAG pattern:
    Step 1: Bi-encoder se top-100 docs retrieve karo (fast)
    Step 2: Cross-encoder se top-100 rerank karo --> top-5 lo (accurate)

  Interview Q4 se:
    Bi-encoder ke liye: asymmetric embedding space kaam karta hai.
    Cross-encoder ke liye: attention across (query, doc) tokens.
""")

    # Mock demo: bi-encoder retrieval + cross-encoder reranking
    query = "Python async programming tutorial"

    docs = [
        "Python asyncio aur coroutines ka complete guide",
        "Python basics: loops, functions, variables",
        "JavaScript async/await explained",
        "Python machine learning with sklearn",
        "Async programming in Python: aiohttp, asyncio best practices",
    ]

    print(f"  Query: '{query}'")
    print("\n  Step 1: Bi-encoder retrieval (fast vector search):")

    q_vec = _fake_embed(query)
    bi_scores = []
    for doc in docs:
        d_vec = _fake_embed(doc)
        score = cosine_similarity(q_vec, d_vec)
        bi_scores.append((score, doc))
    bi_scores.sort(reverse=True)

    for rank, (score, doc) in enumerate(bi_scores, 1):
        print(f"    Rank {rank}: [{score:.4f}] {doc}")

    print("\n  Step 2: Cross-encoder reranking (top-3 rerank -- slow but accurate):")
    print("  (Mock mode -- real cross-encoder huggingface se aata hai)")
    # Cross-encoder pattern: (query, doc) pair score
    # Fake: slightly different seed to simulate better relevance capture
    cross_top3 = bi_scores[:3]
    cross_scores = []
    for _, doc in cross_top3:
        # Simulate cross-encoder by using joint hash (query+doc)
        joint_seed = hash(query + "|" + doc) % (2**32)
        rng = random.Random(joint_seed)
        score = rng.uniform(0.3, 0.98)
        cross_scores.append((score, doc))
    cross_scores.sort(reverse=True)

    for rank, (score, doc) in enumerate(cross_scores, 1):
        print(f"    Re-rank {rank}: [{score:.4f}] {doc}")

    print("""
  Production code (real):
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs    = [(query, doc) for doc in top_100_docs]
    scores   = reranker.predict(pairs)  # (100,) array
    reranked = sorted(zip(scores, top_100_docs), reverse=True)[:5]
""")


# ===========================================================================
# SECTION 9: DOMAIN ADAPTATION -- FINE-TUNING EMBEDDINGS
# Theory: 05_embedding_models.md -- Domain Adaptation (Fine-Tuning)
# ===========================================================================

def section_9_domain_adaptation():
    print("=" * 65)
    print("SECTION 9: Domain Adaptation -- Embedding Fine-Tuning Kab Karo")
    print("=" * 65)

    print("""
  Theory:
    Generic embeddings specialized domains mein underperform karte hain.
    Fine-tune karo jab:
      (a) Specialized vocabulary hai (medical, legal, code)
      (b) 10k+ labeled (query, doc) pairs available hain
      (c) Generic model clearly fail kar raha hai

    Fine-tune mat karo jab:
      - Generic model "OK" chal raha hai
      - Training data nahi hai
      - Budget / compute constraint hai

  Fine-tuning pattern (sentence-transformers):
    from sentence_transformers import SentenceTransformer, InputExample, losses
    from torch.utils.data import DataLoader

    # 1. Training pairs prepare karo
    train_examples = [
        InputExample(texts=["HTTP kya hai", "HTTP ek application-layer protocol hai..."]),
        InputExample(texts=["SQL JOIN", "JOIN do tables ke rows combine karta hai..."]),
        # ... hazaron pairs
    ]

    # 2. Base model load karo
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")

    # 3. Contrastive loss se fine-tune karo
    train_dataloader = DataLoader(train_examples, batch_size=32)
    train_loss       = losses.MultipleNegativesRankingLoss(model=model)
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=3,
        warmup_steps=100,
    )
    model.save("./my-domain-embed")

  Contrastive loss samajhna:
    Positive pair (query, relevant_doc) = closer karo vectors ko
    In-batch negatives = baaki sab docs ko door karo
    Model seekhta hai: "relevant" = high similarity
""")

    # Mock evaluation showing improvement after fine-tuning
    print("  Mock evaluation: Generic vs Fine-tuned model comparison")
    generic_recall  = 0.62  # recall@5 on domain test set
    finetuned_recall = 0.84

    print(f"  Generic BGE recall@5:    {generic_recall:.1%}")
    print(f"  Fine-tuned BGE recall@5: {finetuned_recall:.1%}")
    print(f"  Improvement:             +{(finetuned_recall - generic_recall):.1%}")
    print("""
  Note: Sirf tab fine-tune karo jab clearly zaroori ho.
  Zyaadatar cases mein: better chunking + hybrid search + reranking zyaada help karta hai.
""")


# ===========================================================================
# SECTION 10: COMMON PITFALLS
# Theory: 05_embedding_models.md -- Common Pitfalls (10 listed)
# ===========================================================================

def section_10_common_pitfalls():
    print("=" * 65)
    print("SECTION 10: Common Pitfalls -- Galtiyan Jo Production Mein Hoti Hain")
    print("=" * 65)

    pitfalls = [
        (1,  "Alag models se embeddings mix karna",
             "Vectors incompatible hain. Puri collection re-index karni padegi."),
        (2,  "Bahut lamba doc ek hi vector mein embed karna",
             "Quality drops past ~1000 tokens. Chunk first, phir embed."),
        (3,  "Dot product ke liye normalize karna bhool jaana",
             "Magnitude similarity skew karti hai. normalize_embeddings=True use karo."),
        (4,  "Query aur doc ke liye same embedding (jab API alag ho)",
             "Voyage/Cohere ke liye input_type correctly set karo."),
        (5,  "Har search pe query dobara embed karna",
             "Repeated queries ke liye embedding cache karo."),
        (6,  "3072-dim store karna jab 512 kafi hoga",
             "6x zyaada storage, slower search. MRL use karo."),
        (7,  "Evaluation skip karna",
             "Pata nahi chalega ki embedder achha hai ya nahi. Gold queries banao."),
        (8,  "Embedding model version drift",
             "text-embedding-ada-002 retired Sept 2025. Pin version, watch deprecations."),
        (9,  "Multilingual generic model specialized language ke liye",
             "Language-specific ya fine-tune karo."),
        (10, "Synchronous embed-then-insert (slow indexing)",
             "Batch embed (100+ at a time) + async bulk insert use karo."),
    ]

    for num, pitfall, fix in pitfalls:
        print(f"  {num:>2}. PITFALL: {pitfall}")
        print(f"      FIX:    {fix}")
        print()


# ===========================================================================
# SECTION 11: INTERVIEW Q&A
# Theory: 05_embedding_models.md -- Interview Questions
# ===========================================================================

def section_11_interview_qa():
    print("=" * 65)
    print("SECTION 11: Interview Q&A -- Exam Mein Ye Poochha Jaata Hai")
    print("=" * 65)

    qna = [
        (
            "Q1: Which embedding model would you use and why?",
            """A: Depends on:
      1. Domain: Code = voyage-code-2. Medical = domain-fine-tuned. General = voyage-3 ya OpenAI 3-large.
      2. Budget: text-embedding-3-small (cheap) vs voyage-3 (premium).
      3. Self-host: BGE-large (English) ya BGE-M3 (multilingual).
      4. Latency-sensitive: chhote model ya MRL truncation use karo.
      ALWAYS test on YOUR data. Leaderboards = general benchmarks.""",
        ),
        (
            "Q2: What is Matryoshka Representation Learning (MRL)?",
            """A: Training technique jo vectors ko "nested" banata hai.
      Pehle K dimensions alone ek valid embedding hain.
      Runtime pe truncate kar sakte ho = 3-10x storage savings, minimal quality loss.
      Supported: text-embedding-3, nomic-embed-text-v1.5.""",
        ),
        (
            "Q3: When to fine-tune embeddings vs generic use karna?",
            """A: Fine-tune karo jab:
      (a) Specialized vocabulary (medical, legal, code)
      (b) 10k+ labeled (query, doc) pairs available hain
      (c) Generic model clearly fail kar raha hai
      Otherwise: better chunking + hybrid search + reranking spend karo.""",
        ),
        (
            "Q4: Bi-encoder vs Cross-encoder difference?",
            """A: Bi-encoder: query + doc independently embed hote hain. Fast (precompute docs).
         Use: initial retrieval (top-100 dhundna).
      Cross-encoder: (query, doc) PAIR ko ek saath input. Slow but more accurate.
         Use: reranking top-K results.
      Production: Bi-encoder se retrieve, Cross-encoder se rerank.""",
        ),
        (
            "Q5: Ek embedding model se doosre pe migrate kaise karo?",
            """A: (1) Dono models se parallel index karo transition mein.
      (2) Retrieval quality ka A/B test karo.
      (3) New model better hai toh reads cut over karo.
      (4) Purane vectors retire karo.
      Cost: $$$ + possible downtime. Plan karo.""",
        ),
    ]

    for q, a in qna:
        print(f"\n  {q}")
        for line in a.strip().split("\n"):
            print(f"  {line}")
    print()


# ===========================================================================
# SECTION 12: SENIOR MANTRAS
# Theory: 05_embedding_models.md -- Senior Mantras
# ===========================================================================

def section_12_senior_mantras():
    print("=" * 65)
    print("SECTION 12: Senior Mantras -- Yaad Rakhna Hai Ye")
    print("=" * 65)

    mantras = [
        "Embedding choice > Vector DB choice for quality.",
        "Test on YOUR data. Leaderboards = general benchmarks.",
        "Batch embeddings always. 100 at a time minimum.",
        "MRL truncation = 3-6x storage savings, ~95% quality.",
        "Match query vs doc input_type when API supports (Voyage, Cohere).",
        "Alag models ke embeddings mix mat karo. Re-index entirely.",
        "Model version pin karo. Deprecation notices watch karo.",
        "Query embeddings cache karo. Hot queries = hot cache hit.",
        "Fine-tune only when generic clearly fails + data available ho.",
        "Chunk first, phir embed. Poori kitaab ek vector mein mat dalo.",
    ]

    for i, mantra in enumerate(mantras, 1):
        print(f"  {i:>2}. {mantra}")
    print()


# ===========================================================================
# SECTION 13: LIVE API DEMO (optional -- GROQ_API_KEY se activate hota hai)
# Groq pe embedding endpoint nahi hai, isliye hum LLM se ek creative workaround
# demonstrate karte hain: "LLM-as-similarity-judge" pattern
# ===========================================================================

def section_13_live_api_demo():
    print("=" * 65)
    print("SECTION 13: Live API Demo -- Groq se LLM-as-Similarity-Judge")
    print("=" * 65)

    if MOCK_MODE:
        print("  [SKIP] GROQ_API_KEY nahi mili -- offline demo.")
        print("  Set karo: export GROQ_API_KEY=gsk_xxxx")
        print("  Tab yahan ek real Groq LLM call hogi (llama model).")
        print()

        # Offline fallback: fake similarity judging output print karo
        print("  [MOCK OUTPUT] LLM-as-similarity-judge pattern:")
        mock_pairs = [
            ("Python programming language", "Machine learning with Python",   "HIGH"),
            ("Python programming language", "Cooking pasta Italian food",     "LOW"),
            ("Deep learning neural networks", "Machine learning with Python", "HIGH"),
        ]
        print(f"\n  {'Text A':<35} {'Text B':<35} {'Verdict':>7}")
        print("  " + "-" * 80)
        for a, b, verdict in mock_pairs:
            print(f"  {a:<35} {b:<35} {verdict:>7}")
        return

    # Live path -- GROQ_API_KEY available hai
    try:
        client = get_client()
        text_pairs = [
            ("Python async programming", "asyncio event loop in Python"),
            ("Indian cricket", "Cooking pasta Italian food"),
        ]

        print("  Live Groq call: LLM judge kar raha hai ki texts similar hain ya nahi.")
        print(f"  {'Text A':<32} {'Text B':<32} {'Verdict':>10}")
        print("  " + "-" * 78)

        for text_a, text_b in text_pairs:
            prompt = (
                f"Are these two texts semantically similar? Answer SIMILAR or DIFFERENT only.\n"
                f"Text A: {text_a}\nText B: {text_b}"
            )
            try:
                resp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0,
                )
                verdict = resp.choices[0].message.content.strip()
            except Exception as exc:
                verdict = f"[err: {str(exc)[:30]}]"
            print(f"  {text_a:<32} {text_b:<32} {verdict:>10}")

        print()
        print("  Note: Yeh REAL embedding nahi hai.")
        print("  Production mein: embedding models se cosine similarity use karo.")
        print("  LLM-as-judge = evaluation ke liye useful, retrieval ke liye nahi.\n")
    except Exception as exc:
        print(f"  [ERROR] Live call fail hua: {exc}")
        print("  Offline demo se kaam chalao.\n")


# ===========================================================================
# MAIN: POORA LAB RUN KARO
# ===========================================================================

def main():
    print()
    print("#" * 65)
    print("# LEVEL 5.5 -- EMBEDDING MODELS PRACTICAL LAB (HINGLISH)")
    print("# Theory: Level5_RAG_Vector_Databases/05_embedding_models.md")
    print("#" * 65)
    print()

    if MOCK_MODE:
        print("  [MODE] OFFLINE / MOCK -- koi API key nahi mili.")
        print("  Sab sections run honge, live API calls skip honge.")
    else:
        print("  [MODE] LIVE -- GROQ_API_KEY mili! Section 13 live hoga.")
    print()

    section_1_embedding_concepts()
    section_2_model_comparison()
    section_3_similarity_metrics()
    section_4_mrl_truncation()
    section_5_query_vs_document()
    all_vecs = section_6_batch_embedding()
    section_7_sentence_transformers()
    section_8_bi_vs_cross_encoder()
    section_9_domain_adaptation()
    section_10_common_pitfalls()
    section_11_interview_qa()
    section_12_senior_mantras()
    section_13_live_api_demo()

    print("=" * 65)
    print("LAB COMPLETE! Kya seekha:")
    print("  1. Embedding = text ka numeric vector")
    print("  2. Cosine / dot product = similarity metric")
    print("  3. MRL = truncation ke baad 6x storage savings")
    print("  4. Query vs doc input_type -- Voyage/Cohere pe critical")
    print("  5. Batch embed karo (100+), async use karo")
    print("  6. sentence-transformers = free self-hosted option")
    print("  7. Bi-encoder retrieve karo, cross-encoder rerank karo")
    print("  8. Fine-tune sirf tab jab clearly zaroori ho")
    print("  9. 10 pitfalls yaad karo -- production mein kaam aayenge")
    print(" 10. Senior mantras -- 'Embedding choice > Vector DB choice'")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
    sys.exit(0)
