"""
Phase6_Vector_Databases — Complete Practical
=============================================
Topics:
  1. Vector DB concepts (indexes, distance metrics)
  2. Chroma (in-memory + persistent)
  3. FAISS (Facebook AI Similarity Search)
  4. Pinecone (managed cloud)
  5. Metadata filtering + hybrid search
  6. Collection management
  7. Performance tuning (HNSW, IVF)

Install: pip install chromadb faiss-cpu langchain-openai
Run: python 01_vector_db_practical.py
"""

import os, math, random, json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("VECTOR DATABASE CONCEPTS")
print("=" * 60)

VDB_CONCEPTS = {
    "Vector":           "Dense float array representing text/image semantics (1536-dim for OpenAI)",
    "Index":            "Data structure for fast approximate nearest-neighbor (ANN) search",
    "HNSW":             "Hierarchical Navigable Small World — best recall/speed tradeoff",
    "IVF":              "Inverted File Index — clusters vectors, searches subset of clusters",
    "Distance metrics": "cosine (angle), L2/euclidean (magnitude), dot product",
    "Collection":       "Named group of vectors (like a table in SQL)",
    "Metadata":         "Arbitrary key-value attached to each vector (used for filtering)",
    "Hybrid search":    "Combine dense (vector) + sparse (BM25) retrieval for best recall",
    "ANN":              "Approximate Nearest Neighbor — trades small accuracy loss for huge speed",
}
for k, v in VDB_CONCEPTS.items():
    print(f"  {k:<20}: {v}")

print("\n  Vector DB comparison:")
VDB_COMPARISON = {
    "Chroma":    "Open-source, in-process or server. Best for dev/small scale.",
    "FAISS":     "Facebook, in-process, fastest for batch. No persistence out of box.",
    "Pinecone":  "Managed cloud. Easiest ops. $0.096/hr for p1.x1 pod.",
    "Weaviate":  "Open-source, GraphQL, hybrid search built-in.",
    "Qdrant":    "Rust-based, fast, payload filtering, cloud + self-hosted.",
    "pgvector":  "PostgreSQL extension. If you already have Postgres, use this.",
    "Milvus":    "Enterprise scale, distributed, cloud-native.",
}
for db, desc in VDB_COMPARISON.items():
    print(f"  {db:<12}: {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Chroma
# INTERVIEW: Most popular for prototyping — zero-config, Python-native
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Chroma")
print("=" * 60)

CHROMA_CODE = '''\
import chromadb
from chromadb.utils import embedding_functions

# ── In-memory client (dev/testing) ────────────────────────────
client = chromadb.Client()

# ── Persistent client (stores to disk) ────────────────────────
client = chromadb.PersistentClient(path="./chroma_db")

# ── Embedding function ─────────────────────────────────────────
# INTERVIEW: OpenAI embeddings via Chroma wrapper
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key    = os.getenv("OPENAI_API_KEY"),
    model_name = "text-embedding-3-small",
)

# ── Create/get collection ──────────────────────────────────────
collection = client.get_or_create_collection(
    name              = "documents",
    embedding_function= openai_ef,
    metadata          = {"hnsw:space": "cosine"},  # distance metric
)

# ── Add documents ──────────────────────────────────────────────
collection.add(
    documents = [
        "Python is a high-level programming language",
        "FastAPI is a modern web framework",
        "Docker containers package applications",
    ],
    ids       = ["doc1", "doc2", "doc3"],
    metadatas = [
        {"source": "python_docs", "chapter": 1, "language": "python"},
        {"source": "fastapi_docs", "chapter": 3, "language": "python"},
        {"source": "docker_docs", "chapter": 1, "language": "yaml"},
    ],
)

# ── Basic query ───────────────────────────────────────────────
results = collection.query(
    query_texts = ["web framework"],
    n_results   = 2,
    include     = ["documents", "distances", "metadatas"],
)
print(results["documents"])   # [["FastAPI...", "Python..."]]
print(results["distances"])   # [[0.12, 0.45]]

# ── Metadata filtering ─────────────────────────────────────────
# INTERVIEW: $eq, $ne, $gt, $lt, $in, $nin, $and, $or operators
results = collection.query(
    query_texts = ["Python"],
    n_results   = 5,
    where = {
        "$and": [
            {"language": {"$eq": "python"}},
            {"chapter":  {"$gt": 0}},
        ]
    },
)

# Filter on document content
results = collection.query(
    query_texts  = ["Python"],
    n_results    = 5,
    where_document = {"$contains": "framework"},
)

# ── Upsert + Delete ────────────────────────────────────────────
collection.upsert(
    ids       = ["doc1"],
    documents = ["Python is a versatile programming language"],
    metadatas = [{"updated": True}],
)
collection.delete(ids=["doc3"])
collection.delete(where={"source": "docker_docs"})

# ── Get collection stats ───────────────────────────────────────
print(collection.count())           # number of documents
print(client.list_collections())    # all collections
'''
print(CHROMA_CODE[:800])


# In-memory Chroma demo
def mock_embed(text: str, dim: int = 4) -> List[float]:
    random.seed(hash(text) % (2**31))
    vec = [random.gauss(0, 1) for _ in range(dim)]
    mag = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x/mag for x in vec]


def cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x*x for x in a)) or 1.0
    mb  = math.sqrt(sum(x*x for x in b)) or 1.0
    return dot / (ma * mb)


try:
    import chromadb
    client     = chromadb.Client()
    collection = client.create_collection("demo")
    collection.add(
        documents = ["Python language", "FastAPI framework", "Docker container"],
        ids       = ["1", "2", "3"],
        metadatas = [{"type": "lang"}, {"type": "framework"}, {"type": "tool"}],
    )
    results = collection.query(query_texts=["web framework"], n_results=2)
    print("\n  Chroma demo (real):")
    print(f"  Query: 'web framework'")
    print(f"  Results: {results['documents']}")
except ImportError:
    print("\n  [Mock Chroma] chromadb not installed")
    print("  Query: 'web framework'")
    docs = ["Python language", "FastAPI framework", "Docker container"]
    q_vec = mock_embed("web framework")
    ranked = sorted(docs, key=lambda d: -cosine_sim(q_vec, mock_embed(d)))
    print(f"  Results (mock similarity): {ranked[:2]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: FAISS
# INTERVIEW: Fastest for batch operations, no metadata filter built-in
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: FAISS")
print("=" * 60)

FAISS_CODE = '''\
import faiss
import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# ── Build FAISS index ──────────────────────────────────────────
texts    = ["Python programming", "FastAPI web framework", "Docker containers"]
metadatas= [{"id": i} for i in range(len(texts))]

# from_texts: embed + index in one call
db = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

# ── Search ────────────────────────────────────────────────────
results = db.similarity_search("web framework", k=2)
results_with_scores = db.similarity_search_with_score("web framework", k=2)

for doc, score in results_with_scores:
    # INTERVIEW: FAISS score is L2 distance (LOWER = MORE similar)
    # Chroma cosine score is also distance (LOWER = MORE similar)
    print(f"  Score: {score:.4f} — {doc.page_content}")

# ── MMR retrieval ─────────────────────────────────────────────
mmr_results = db.max_marginal_relevance_search(
    query       = "Python",
    k           = 3,          # return 3
    fetch_k     = 20,         # consider top 20
    lambda_mult = 0.5,        # diversity/relevance tradeoff
)

# ── Persist / reload ───────────────────────────────────────────
db.save_local("faiss_index")
db_loaded = FAISS.load_local(
    "faiss_index", embeddings,
    allow_dangerous_deserialization=True
)

# ── Direct FAISS index (without LangChain) ────────────────────
dim     = 128
index   = faiss.IndexFlatL2(dim)         # exact L2 distance
# OR:
index   = faiss.IndexFlatIP(dim)         # inner product (for cosine with normalized vectors)
# OR: Approximate (much faster for large datasets)
quantizer = faiss.IndexFlatL2(dim)
index   = faiss.IndexIVFFlat(quantizer, dim, 100)  # 100 clusters
index.train(vectors)                                # MUST train IVF
index.nprobe = 10                                   # search 10 of 100 clusters

index.add(np.array(vectors, dtype=np.float32))
distances, indices = index.search(np.array([query_vec], dtype=np.float32), k=5)
'''
print(FAISS_CODE[:700])

print("\n  FAISS index types:")
FAISS_INDEXES = {
    "IndexFlatL2":   "Exact L2 search. Accurate but O(n) slow for large n. Dev/testing.",
    "IndexFlatIP":   "Exact inner product. Use with normalized vectors for cosine similarity.",
    "IndexIVFFlat":  "Approximate: clusters → search subset. 10-100x faster, ~1% accuracy loss.",
    "IndexHNSW":     "HNSW graph: best recall/speed. No training needed. Large RAM usage.",
    "IndexPQ":       "Product quantization: compressed vectors. Low RAM, lower accuracy.",
    "IndexIVFPQ":    "IVF + PQ: fast + compressed. Production-scale.",
}
for idx, desc in FAISS_INDEXES.items():
    print(f"  {idx:<18}: {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Pinecone
# INTERVIEW: Managed cloud, serverless, easiest for production
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Pinecone (Managed Cloud)")
print("=" * 60)

PINECONE_CODE = '''\
from pinecone import Pinecone, ServerlessSpec
import os

# ── Connect ────────────────────────────────────────────────────
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# ── Create index ───────────────────────────────────────────────
pc.create_index(
    name      = "documents",
    dimension = 1536,      # must match embedding model dimension
    metric    = "cosine",  # cosine, euclidean, or dotproduct
    spec = ServerlessSpec(
        cloud  = "aws",
        region = "us-east-1",
    )
)

index = pc.Index("documents")

# ── Upsert vectors ─────────────────────────────────────────────
# INTERVIEW: Pinecone expects: id, values (vector), optional metadata
vectors_to_upsert = [
    {
        "id":       "doc-1",
        "values":   embeddings.embed_query("Python programming"),
        "metadata": {"text": "Python programming", "source": "docs", "chapter": 1},
    },
    {
        "id":       "doc-2",
        "values":   embeddings.embed_query("FastAPI framework"),
        "metadata": {"text": "FastAPI framework", "source": "docs", "chapter": 2},
    },
]
index.upsert(vectors=vectors_to_upsert, namespace="production")

# ── Query ──────────────────────────────────────────────────────
query_embedding = embeddings.embed_query("web framework")
results = index.query(
    vector          = query_embedding,
    top_k           = 5,
    include_values  = False,
    include_metadata= True,
    namespace       = "production",
    filter = {                          # metadata filter
        "$and": [
            {"source": {"$eq": "docs"}},
            {"chapter": {"$gte": 1}},
        ]
    }
)
for match in results["matches"]:
    print(f"  score={match['score']:.4f} id={match['id']} text={match['metadata']['text']}")

# ── Namespace: isolate data ────────────────────────────────────
# INTERVIEW: Namespace = tenant isolation within same index
# Use case: separate users, environments, or document types
index.upsert(vectors=..., namespace="user-alice")
index.upsert(vectors=..., namespace="user-bob")
index.query(vector=..., namespace="user-alice")  # only alice\'s data

# ── Index stats ───────────────────────────────────────────────
stats = index.describe_index_stats()
print(stats["total_vector_count"])
print(stats["namespaces"])
'''
print(PINECONE_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Metadata Filtering
# INTERVIEW: Critical for RAG — filter by date, source, user, etc.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Metadata Filtering Patterns")
print("=" * 60)

METADATA_PATTERNS = [
    {
        "use_case": "Date-restricted search",
        "chroma_filter": {"timestamp": {"$gt": 1700000000}},
        "pinecone_filter": {"timestamp": {"$gt": 1700000000}},
    },
    {
        "use_case": "Multi-tenant isolation",
        "chroma_filter": {"user_id": {"$eq": "user-alice"}},
        "pinecone_filter": {"user_id": {"$eq": "user-alice"}},
    },
    {
        "use_case": "Source + language filter",
        "chroma_filter": {
            "$and": [
                {"source": {"$in": ["docs", "wiki"]}},
                {"language": {"$eq": "python"}},
            ]
        },
        "note": "Chroma supports $and, $or, $in, $nin, $eq, $ne, $gt, $gte, $lt, $lte",
    },
]

print("\n  Common metadata filter patterns:")
for p in METADATA_PATTERNS:
    print(f"\n  Use case: {p['use_case']}")
    if "chroma_filter" in p:
        print(f"  Filter: {json.dumps(p['chroma_filter'])}")
    if "note" in p:
        print(f"  Note: {p['note']}")

print("\n  Metadata design best practices:")
print("  1. Add source, timestamp, user_id to every document")
print("  2. Use consistent data types (don't mix str and int for same key)")
print("  3. Keep metadata small — it's stored alongside vector (adds memory)")
print("  4. Design for filtering upfront — can't add metadata without re-indexing")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: LangChain Integration
# INTERVIEW: Both Chroma and FAISS work identically via LangChain interface
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: LangChain Vector Store Interface")
print("=" * 60)

LANGCHAIN_VS_CODE = '''\
from langchain_community.vectorstores import Chroma, FAISS, Pinecone
from langchain_openai import OpenAIEmbeddings

# INTERVIEW: All vector stores share the same LangChain interface
# Swap backend by changing import — same code!
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# ── Build from documents ───────────────────────────────────────
from langchain_core.documents import Document

docs = [
    Document(page_content="Python is great", metadata={"source": "manual"}),
    Document(page_content="FastAPI is fast",  metadata={"source": "docs"}),
]

# Identical API for all backends:
chroma_store = Chroma.from_documents(docs, embeddings, persist_directory="./chroma")
faiss_store  = FAISS.from_documents(docs, embeddings)
pinecone_store = PineconeVectorStore.from_documents(
    docs, embeddings, index_name="my-index"
)

# ── As retriever (use in RAG chain) ──────────────────────────
retriever = chroma_store.as_retriever(
    search_type   = "mmr",          # similarity, mmr, similarity_score_threshold
    search_kwargs = {
        "k":           4,
        "lambda_mult": 0.5,         # for mmr only
        "filter":      {"source": "docs"},  # metadata filter
        "score_threshold": 0.7,     # for similarity_score_threshold only
    }
)

# ── Use in RAG chain ──────────────────────────────────────────
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | ChatPromptTemplate.from_template("Context: {context}\\nQuestion: {question}\\nAnswer:")
    | ChatOpenAI(model="gpt-4o-mini")
)
answer = chain.invoke("What is FastAPI?")
'''
print(LANGCHAIN_VS_CODE[:700])


print("\n" + "=" * 60)
print("VECTOR DB INTERVIEW SUMMARY:")
print("  Chroma: in-process, zero config, perfect for dev. chromadb.Client()")
print("  FAISS: fastest batch, HNSW for prod, save_local/load_local")
print("  Pinecone: managed cloud, namespaces for tenants, serverless")
print("  Metadata filter: $eq/$gt/$in/$and/$or — design upfront!")
print("  Distance: cosine (angle, best for text), L2 (magnitude), IP (dot product)")
print("  ANN: HNSW (best recall), IVF (fast+tunable), IVF+PQ (compressed)")
print("  LangChain: same .from_documents() / .as_retriever() for all backends")
print("=" * 60)
