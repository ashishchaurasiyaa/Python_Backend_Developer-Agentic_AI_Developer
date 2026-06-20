# RAG Advanced — Theory Deep Dive
### Python Backend Developer + Agentic AI Interview Prep | Target: 40 LPA
### Language: Hinglish (Hindi explanation + English technical terms/code)

---

## Table of Contents
1. RAG Limitations aur Advanced Solutions
2. Chunking Strategies — Deep Dive
3. Hybrid Search (BM25 + Vector)
4. Reranking
5. Advanced Retrieval Patterns
6. Corrective RAG (CRAG)
7. Self-RAG
8. Agentic RAG
9. RAPTOR
10. RAG Evaluation — RAGAS
11. Embedding Strategies
12. Production RAG Architecture
13. Multi-modal RAG (Basics)
14. 15 Interview Q&As

---

## 1. RAG Limitations aur Advanced Solutions

### Basic RAG kya karta hai?

Basic RAG (Retrieval-Augmented Generation) ek simple pipeline hai:
1. User query aati hai
2. Vector search se top-k chunks retrieve karo
3. Ye chunks LLM ko context ke roop mein do
4. LLM answer generate karta hai

Ye simple approach 80% cases mein theek kaam karta hai, lekin production mein kaafi problems aati hain.

---

### Problem 1: Poor Retrieval — "Galat Chunks Aa Rahe Hain"

**Kya hota hai:**
```
User: "FastAPI mein authentication kaise karein?"
Retrieved chunk: "FastAPI ek modern Python web framework hai jo async support karta hai"
```

Ye chunk relevant toh hai, lekin authentication ke baare mein kuch nahi batata. Retrieval fail hua.

**Kyun hota hai:**
- Query aur document ke beech semantic gap — user "authentication" poochh raha hai, document mein "JWT token verification" likha hai
- Chunking ne important context split kar diya
- Top-k number too small ya too large
- Embedding model task ke liye optimized nahi

**Solutions:**
- Better chunking strategies (Section 2)
- Hybrid search — BM25 + vector (Section 3)
- Multi-query retrieval (Section 5)
- Better embedding models (Section 11)

---

### Problem 2: Lost-in-the-Middle — "Beech Ka Context Bhool Jaata Hai"

**Research finding (Liu et al., 2023):**
LLMs retrieved chunks ko effectively use nahi karte jab relevant info beech mein hoti hai.

```
Context sent to LLM:
[Chunk 1 — FastAPI intro]          ← LLM ye yaad rakhta hai ✅
[Chunk 2 — Starlette middleware]    ← LLM ye bhool jaata hai ❌
[Chunk 3 — JWT authentication]      ← relevant chunk!  ❌ (beech mein hai)
[Chunk 4 — Pydantic models]         ← LLM ignore karta hai ❌
[Chunk 5 — Deployment options]      ← LLM ye bhi yaad rakhta hai ✅
```

**Solution:**
```python
# Reranking ke baad — best chunks ko start/end mein rakhna
def reorder_for_lost_in_middle(chunks):
    """
    Best chunks: positions 0, -1, 1, -2, 2, -3 ...
    Zigzag pattern — most relevant at extremes
    """
    reordered = []
    left, right = 0, len(chunks) - 1
    toggle = True
    while left <= right:
        if toggle:
            reordered.append(chunks[left])
            left += 1
        else:
            reordered.append(chunks[right])
            right -= 1
        toggle = not toggle
    return reordered
```

---

### Problem 3: Irrelevant Chunks — "Context Mein Noise Hai"

**Kya hota hai:**
Top-5 retrieve karo, unme se 3 irrelevant hain. LLM confuse ho jaata hai aur hallucinate karta hai.

**Solutions:**
- Reranking (Section 4) — irrelevant chunks filter karo
- Contextual compression — sirf relevant sentences extract karo
- CRAG (Section 6) — document quality grade karo, fallback to web search

---

### Problem 4: Context Window Overflow

**Problem:** 100 page PDF hai, top-20 chunks retrieve kiye, context window full ho gayi.

**Solutions:**
- Parent-document retriever — small chunks retrieve, large chunks context mein
- RAPTOR (Section 9) — hierarchical summaries
- Map-reduce pattern — har chunk pe separately process karo, phir combine karo

---

### Problem 5: Static Knowledge

**Problem:** Index ek baar bana, docs update ho gaye, lekin retrieval purani info de raha hai.

**Solutions:**
```python
# Incremental updates
def update_index(new_doc, doc_id, vectorstore):
    """
    Sirf naye/changed docs re-embed karo
    """
    # Check if doc already exists
    existing = vectorstore.get(doc_id)
    if existing and existing['hash'] == hash_document(new_doc):
        return  # No change, skip
    
    # Re-embed and update
    chunks = chunk_document(new_doc)
    embeddings = embed_chunks(chunks)
    vectorstore.upsert(doc_id, chunks, embeddings)
```

---

### Solutions Overview Table

| Problem | Solution | Complexity | Impact |
|---------|----------|------------|--------|
| Poor retrieval | Hybrid search | Medium | High |
| Wrong chunks ranked high | Reranking | Low | High |
| Lost-in-middle | Chunk reordering | Low | Medium |
| Complex queries | Multi-query retrieval | Medium | High |
| Irrelevant docs | CRAG + grading | High | High |
| Outdated info | Agentic RAG + web search | High | High |
| Long documents | RAPTOR | High | Medium |

---

## 2. Chunking Strategies — Deep Dive

### Chunking Kyun Important Hai?

> "Agar chunks galat hain, toh baaki saara pipeline waste hai."

Chunking = document ko meaningful pieces mein todna. Ye ek art hai — too small = context missing, too large = noise aata hai.

---

### Strategy 1: Fixed-Size Chunking

**Sabse simple approach:**

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,        # Characters per chunk
    chunk_overlap=50,      # Overlap between consecutive chunks
    length_function=len,
    separators=["\n\n", "\n", " ", ""]  # Try each separator in order
)

chunks = splitter.split_text(document)
```

**chunk_overlap kyun?**
```
Chunk 1: "...FastAPI uses Pydantic for data validation. It automatically"
Chunk 2: "It automatically generates OpenAPI docs based on type hints..."
```
Bina overlap ke "It automatically" ka context kho jaata. Overlap se continuity banti hai.

**Kab use karein:**
- Simple documents — plain text, articles
- Jab document structure important nahi
- Prototype banate waqt

**Kab avoid karein:**
- Code files — function beech se split ho jaati hai
- Tables — row beech se split ho jaata hai
- Markdown — heading aur content alag ho jaate hain

---

### Strategy 2: Recursive Text Splitter (RecursiveCharacterTextSplitter)

**Hierarchy of separators:**

```python
# Default separator hierarchy:
separators = [
    "\n\n",    # First try: double newline (paragraph boundary)
    "\n",      # Then: single newline
    " ",       # Then: space (word boundary)
    ""         # Last resort: character by character
]
```

**Example:**
```
Document:
"## Introduction\n\nPython is great.\n\nIt has many libraries.\n\nFastAPI is built on Starlette."

Step 1: Split on "\n\n"
  Chunk 1: "## Introduction"
  Chunk 2: "Python is great."
  Chunk 3: "It has many libraries."
  Chunk 4: "FastAPI is built on Starlette."

If any chunk > chunk_size, recursively split on next separator.
```

**Ye approach zyada natural hai** — sentence/paragraph boundaries respect karta hai.

---

### Strategy 3: Semantic Chunking

**Idea:** Embedding similarity change pe split karo, fixed size pe nahi.

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
semantic_splitter = SemanticChunker(
    embeddings,
    breakpoint_threshold_type="percentile",  # ya "standard_deviation", "interquartile"
    breakpoint_threshold_amount=95           # 95th percentile similarity drop = split
)

chunks = semantic_splitter.split_text(document)
```

**Andar kaise kaam karta hai:**

```
Sentences:
S1: "Python asyncio handles concurrent I/O."
S2: "Event loop manages coroutines efficiently."
S3: "Docker containers isolate processes."      ← Topic change!
S4: "Kubernetes orchestrates containers."

Embeddings:
embed(S1, S2) similarity = 0.92 (same topic)
embed(S2, S3) similarity = 0.41 (different topic!) ← SPLIT HERE
embed(S3, S4) similarity = 0.89 (same topic)

Result:
Chunk 1: "Python asyncio handles... Event loop manages..."
Chunk 2: "Docker containers... Kubernetes orchestrates..."
```

**Advantages:**
- Topically coherent chunks
- Better retrieval precision
- No arbitrary size limits

**Disadvantages:**
- Slow — embedding banane padte hain ingestion time pe
- API calls costly
- Chunk sizes variable — kuch bahut chote, kuch bahut bade

---

### Strategy 4: Late Chunking

**Naya technique (2024):**

Traditional approach:
```
Chunk → Embed each chunk separately
Problem: "it" refer karta hai "Python" ko, jo previous chunk mein hai
```

Late Chunking:
```python
# Step 1: Poora document embed karo (token-level embeddings)
full_doc_embeddings = model.encode(full_document, return_token_embeddings=True)
# Shape: (num_tokens, embedding_dim)

# Step 2: PHIR chunk boundaries decide karo
chunk_boundaries = determine_chunks(full_document)

# Step 3: Token embeddings ko mean-pool karke chunk embeddings banao
chunk_embeddings = []
for start, end in chunk_boundaries:
    chunk_embed = full_doc_embeddings[start:end].mean(axis=0)
    chunk_embeddings.append(chunk_embed)
```

**Benefit:**
- Har chunk ka embedding puri document ka context le kar banta hai
- Long-range dependencies preserved
- "it", "they", "this" jaise pronouns sahi context mein embed hote hain

**Limitation:**
- Sirf long-context embedding models ke saath kaam karta hai (e.g., jina-embeddings-v2)
- Token limit issue for very long docs

---

### Strategy 5: Parent-Document Retriever

**Problem with small chunks:**
Small chunks precise retrieval ke liye acche hain, lekin context ke liye LLM ko zyada chahiye.

**Solution: Two-level storage**

```
Parent chunks: 1000 tokens (full context ke liye)
Child chunks:  200 tokens  (precise retrieval ke liye)

Retrieval time:
1. Query se child chunks match karo (precise)
2. Child chunk ke parent chunk ko return karo (full context)
```

```python
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryByteStore
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Parent splitter — bade chunks
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)

# Child splitter — chhote chunks (sirf retrieval ke liye)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)

# Vector store — sirf child chunks store karta hai
vectorstore = Chroma(embedding_function=embeddings)

# Document store — parent chunks store karta hai
docstore = InMemoryByteStore()

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=docstore,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)

retriever.add_documents(documents)

# Query karo
results = retriever.get_relevant_documents("FastAPI authentication")
# Returns: Parent chunks (2000 tokens), not child chunks
```

**Real-world impact:**
- 30-40% better answer quality vs small chunk RAG
- Retrieval precision same as small chunks
- Context quality equal to large chunks

---

### Strategy 6: Document-Specific Splitters

**Markdown Headers:**
```python
from langchain.text_splitter import MarkdownHeaderTextSplitter

headers_to_split_on = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]
splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
chunks = splitter.split_text(markdown_doc)

# Output chunks mein metadata automatically:
# {"content": "...", "metadata": {"Header 1": "Installation", "Header 2": "Prerequisites"}}
```

**Code splitter:**
```python
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter

python_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=2000,
    chunk_overlap=200
)
# Python ke liye separators: ["\nclass ", "\ndef ", "\n\n", "\n", " ", ""]
# Functions aur classes intact rehte hain
```

**HTML splitter:**
```python
from langchain.text_splitter import HTMLHeaderTextSplitter

headers_to_split_on = [("h1", "Header 1"), ("h2", "Header 2")]
splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
chunks = splitter.split_text(html_doc)
```

---

### Chunking Tradeoffs Table

| Strategy | Chunk Size | Retrieval Precision | Context Quality | Speed | Use Case |
|----------|-----------|---------------------|-----------------|-------|----------|
| Fixed-size small (200) | Small | High | Low | Fast | FAQ, short docs |
| Fixed-size large (1000) | Large | Low | High | Fast | Long form articles |
| Recursive (500) | Medium | Medium | Medium | Fast | General purpose |
| Semantic | Variable | Very High | Medium | Slow | Technical docs |
| Parent-Document | Small+Large | High | High | Medium | Best of both worlds |
| Late Chunking | Variable | High | Very High | Slow | Long docs with references |
| Markdown-aware | Structure | High | High | Fast | Documentation, wikis |
| Code-aware | Function/class | High | High | Fast | Code repositories |

---

## 3. Hybrid Search — BM25 + Vector

### Kya Problem Solve Karta Hai?

**Pure vector search ki limitation:**
```
Query: "BM25 algorithm"
Vector search: "TF-IDF based document ranking" (semantically similar) ✅
But misses: documents where "BM25" exact word appears ❌

Query: "error code 404"  
Vector search: "HTTP not found" (semantically similar) ✅
But misses: logs mein exact "404" mention ❌
```

**Pure BM25 ki limitation:**
```
Query: "how to handle concurrent requests"
BM25: exact match — documents with "concurrent requests" keywords ✅
But misses: "asyncio event loop" document (same concept, different words) ❌
```

**Hybrid = Best of both worlds**

---

### BM25 Algorithm — Deep Dive

**BM25 (Best Matching 25)** — TF-IDF ka improved version

**Formula:**
```
BM25(D, Q) = Σ IDF(qi) × [f(qi,D) × (k1+1)] / [f(qi,D) + k1×(1-b+b×|D|/avgdl)]

Where:
- qi = query term i
- f(qi, D) = term frequency of qi in document D
- |D| = document length
- avgdl = average document length
- k1 = term saturation parameter (typical: 1.2-2.0)
- b = length normalization (typical: 0.75)
- IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))
  - N = total documents
  - n(qi) = documents containing qi
```

**Key Insight:**
```python
# k1 parameter — term saturation
# Same word 100 baar aaye ya 1 baar — diminishing returns
tf = 5  # Term appears 5 times
k1 = 1.5

# With BM25: score = tf * (k1+1) / (tf + k1) = 5*2.5/(5+1.5) = 1.92
# Without saturation: score = tf = 5 (linearly increases, overweights repetition)

# b parameter — document length normalization
# Lamba document mein word zyada baar aata hai naturally
# b=0.75 = partial normalization
```

---

### Dense Retrieval (Vector Search)

```python
import numpy as np

def cosine_similarity(vec1, vec2):
    """Dot product of normalized vectors = cosine similarity"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# Dense retrieval process:
# 1. Offline: embed all documents
# 2. Online: embed query, find nearest neighbors
# 3. FAISS / Pinecone / Weaviate for ANN (Approximate Nearest Neighbors)
```

**Dense Retrieval Advantages:**
- Paraphrasing handle karta hai
- Cross-lingual possible
- Semantic synonyms match karta hai

---

### Reciprocal Rank Fusion (RRF)

**Formula:**
```
RRF_score(d) = Σ_r∈R  1 / (k + r(d))

Where:
- R = set of rankers (BM25, vector, etc.)
- r(d) = rank of document d in ranker r
- k = constant (usually 60) to reduce impact of high ranks
```

**Example:**
```
Document A:
  BM25 rank = 1  → RRF score += 1/(60+1) = 0.0164
  Vector rank = 3 → RRF score += 1/(60+3) = 0.0159
  Total RRF = 0.0323

Document B:
  BM25 rank = 5  → RRF score += 1/(60+5) = 0.0154
  Vector rank = 1 → RRF score += 1/(60+1) = 0.0164
  Total RRF = 0.0318

Document A > Document B (slightly) — consistent across both methods
```

**Kyun k=60 default hai?**
- k chhota hoga → top rank ka bahut zyada advantage
- k=60 → rank 1 aur rank 5 mein zyada fark nahi
- Ye "rank insensitivity" deta hai — multiple methods agree karna zyada important

---

### Relative Score Fusion

```python
def relative_score_fusion(bm25_results, vector_results, 
                           bm25_weight=0.5, vector_weight=0.5):
    """
    Normalize scores to [0,1] range, then weighted average
    """
    # Normalize BM25 scores
    bm25_scores = {idx: score for _, score, idx in bm25_results}
    max_bm25 = max(bm25_scores.values()) if bm25_scores else 1
    min_bm25 = min(bm25_scores.values()) if bm25_scores else 0
    
    norm_bm25 = {idx: (score - min_bm25) / (max_bm25 - min_bm25 + 1e-9) 
                 for idx, score in bm25_scores.items()}
    
    # Normalize vector scores (usually already [0,1])
    vec_scores = {idx: score for _, score, idx in vector_results}
    max_vec = max(vec_scores.values()) if vec_scores else 1
    min_vec = min(vec_scores.values()) if vec_scores else 0
    
    norm_vec = {idx: (score - min_vec) / (max_vec - min_vec + 1e-9) 
                for idx, score in vec_scores.items()}
    
    # Combine
    all_indices = set(norm_bm25.keys()) | set(norm_vec.keys())
    combined = {}
    for idx in all_indices:
        b_score = norm_bm25.get(idx, 0) * bm25_weight
        v_score = norm_vec.get(idx, 0) * vector_weight
        combined[idx] = b_score + v_score
    
    return sorted(combined.items(), key=lambda x: x[1], reverse=True)
```

---

### LangChain EnsembleRetriever

```python
from langchain.retrievers import BM25Retriever, EnsembleRetriever
from langchain_community.vectorstores import FAISS

# BM25 Retriever
bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 5

# Vector Retriever
vectorstore = FAISS.from_documents(documents, embeddings)
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Ensemble (uses RRF by default)
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5]  # Equal weight
)

results = ensemble_retriever.get_relevant_documents("async Python framework")
```

---

### Elasticsearch Hybrid Query

```python
# Elasticsearch mein native hybrid search
query = {
    "query": {
        "bool": {
            "should": [
                {
                    "match": {
                        "content": {
                            "query": user_query,
                            "boost": 1.0
                        }
                    }
                }
            ]
        }
    },
    "knn": {
        "field": "content_vector",
        "query_vector": query_embedding.tolist(),
        "k": 10,
        "num_candidates": 100,
        "boost": 1.0
    }
}
```

---

## 4. Reranking

### Problem: Retrieval ≠ Relevance for Answer Generation

```
Query: "Python mein deadlock kaise prevent karein?"

Top-5 Retrieved (by vector similarity):
1. "Python threading module overview" (similarity: 0.89)
2. "Deadlock conditions: mutual exclusion, hold and wait..." (similarity: 0.87)  ← Actually most useful!
3. "Python concurrency best practices" (similarity: 0.85)
4. "Threading vs multiprocessing in Python" (similarity: 0.84)
5. "asyncio vs threading comparison" (similarity: 0.82)

After reranking for "how to prevent deadlock":
1. "Deadlock conditions: mutual exclusion, hold and wait..." (most relevant for prevention)
2. "Python concurrency best practices" 
3. "Python threading module overview"
```

---

### Bi-Encoder vs Cross-Encoder

**Bi-Encoder (Dense Retrieval):**
```
Query → Encoder → Query Embedding (768-dim)
Document → Encoder → Doc Embedding (768-dim)
Score = cosine_similarity(query_emb, doc_emb)
```

- Fast: embeddings precomputed, sirf dot product at query time
- Scalable: millions of documents possible
- Less accurate: query aur document independently encoded

**Cross-Encoder (Reranking):**
```
[Query + Document] → Encoder → Relevance Score (single number)

Input: "[CLS] How to prevent deadlock? [SEP] Deadlock conditions... [SEP]"
Output: 0.94 (highly relevant)
```

- Slow: every (query, document) pair process karna padta hai
- More accurate: query aur document jointly encoded, full attention
- Not scalable: 1000 docs × 1 query = 1000 forward passes

**Pipeline:**
```
Bi-Encoder: retrieve top-100 (fast)
Cross-Encoder: rerank top-100 → pick top-5 (accurate)
```

---

### sentence-transformers Cross-Encoder

```python
from sentence_transformers import CrossEncoder

# MS MARCO — Microsoft dataset for passage ranking
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

query = "What is the capital of France?"
passages = [
    "Paris is the capital of France and a major European city.",
    "France is a country in Western Europe.",
    "The Eiffel Tower is located in Paris.",
    "Berlin is the capital of Germany.",
]

# Score all pairs
scores = model.predict([[query, p] for p in passages])
# Output: [0.98, 0.12, 0.67, 0.03]

# Sort by score
ranked = sorted(zip(passages, scores), key=lambda x: x[1], reverse=True)
```

**Available cross-encoders:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — fast, good for general
- `cross-encoder/ms-marco-TinyBERT-L-2-v2` — very fast, lower accuracy
- `cross-encoder/ms-marco-electra-base` — slower, better accuracy
- `BAAI/bge-reranker-large` — best open-source reranker

---

### Cohere Rerank API

```python
import cohere

co = cohere.Client("YOUR_API_KEY")

results = co.rerank(
    model="rerank-english-v3.0",
    query="What year was FastAPI created?",
    documents=[
        "FastAPI was created by Sebastián Ramírez in 2018.",
        "Flask is a micro web framework for Python.",
        "FastAPI is built on Starlette and Pydantic.",
        "Django was released in 2005.",
    ],
    top_n=2
)

for r in results.results:
    print(f"Score: {r.relevance_score:.4f} — {r.document['text'][:60]}")
```

**Cohere Rerank advantages:**
- No GPU required
- API call simple hai
- State-of-the-art accuracy
- Multilingual support

---

### FlashRank — Lightweight Local Reranker

```python
from flashrank import Ranker, RerankRequest

# Tiny model — 4MB, CPU pe runs
ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="/tmp")

rerank_request = RerankRequest(
    query="Python async programming",
    passages=[
        {"id": 1, "text": "asyncio provides infrastructure for async I/O"},
        {"id": 2, "text": "Flask is a synchronous web framework"},
        {"id": 3, "text": "Python GIL prevents true parallelism"},
    ]
)

results = ranker.rerank(rerank_request)
# Sorted by relevance, very fast even on CPU
```

---

### Lost-in-the-Middle Problem

**Research (2023):** LLMs perform best when relevant info is at the beginning or end of context.

```python
def optimized_context_ordering(reranked_chunks):
    """
    Sabse relevant chunks: positions 0 aur -1
    Less relevant: middle positions
    
    Input: [most_relevant, second, third, fourth, fifth]
    Output: [most_relevant, third, fifth, fourth, second]
    """
    if len(reranked_chunks) <= 2:
        return reranked_chunks
    
    result = []
    left_idx = 0
    right_idx = len(reranked_chunks) - 1
    add_to_left = True
    
    for chunk in reranked_chunks:
        if add_to_left:
            result.insert(0, chunk)
        else:
            result.append(chunk)
        add_to_left = not add_to_left
    
    return result

# Practical reranking pipeline
def full_reranking_pipeline(query, documents, retrieve_k=20, final_k=5):
    """
    Step 1: Retrieve top-20 (fast, bi-encoder)
    Step 2: Rerank to get top-5 (slow, cross-encoder)
    Step 3: Reorder for lost-in-middle
    """
    # Step 1
    retrieved = vector_retrieve(query, documents, k=retrieve_k)
    
    # Step 2
    reranked = cross_encoder_rerank(query, retrieved, k=final_k)
    
    # Step 3
    optimized = optimized_context_ordering(reranked)
    
    return optimized
```

---

## 5. Advanced Retrieval Patterns

### Pattern 1: Multi-Query Retriever

**Problem:** Single query se saare relevant chunks nahi milte.

```
Question: "microservices mein deployment kaise karte hain?"

User ka actual intent multiple angles mein:
- Docker containers kya hote hain
- Kubernetes orchestration kaise kaam karta hai  
- Service discovery aur load balancing
- CI/CD pipelines for microservices

Single query sirf ek angle retrieve karti hai.
```

**Solution:**

```python
from langchain.retrievers import MultiQueryRetriever
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(temperature=0)

retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(),
    llm=llm
)

# Internally, LLM generates 3-5 variants:
# 1. "microservices deployment strategies"
# 2. "Docker Kubernetes container orchestration"
# 3. "CI/CD pipeline for microservices architecture"
# 4. "service deployment in distributed systems"

# Results from all queries → deduplicated → returned
results = retriever.get_relevant_documents("microservices mein deployment kaise karte hain?")
```

**Manual implementation:**
```python
QUERY_GENERATION_PROMPT = """
Given the user question, generate {n} different search queries 
to retrieve relevant documents. Output each on a new line.

Original question: {question}
"""

def generate_multiple_queries(question, n=4, llm=None):
    if llm:
        response = llm.invoke(QUERY_GENERATION_PROMPT.format(question=question, n=n))
        queries = response.content.strip().split('\n')
    else:
        # Mock for demo
        queries = [
            question,
            f"what is {question}",
            f"how to implement {question}",
            f"{question} best practices"
        ]
    return [q.strip() for q in queries if q.strip()]
```

---

### Pattern 2: Contextual Compression

**Problem:** Retrieved chunk mein relevant info hai, lekin bahut saari irrelevant info bhi hai.

```
Retrieved chunk (500 words):
"FastAPI is a modern Python web framework... [200 words about FastAPI history]
...FastAPI handles authentication using OAuth2 with JWT tokens. The HTTPBearer 
dependency can be used... [300 words about unrelated Pydantic features]"

We need: Only the 2 sentences about authentication
```

**Solution:**

```python
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.retrievers import ContextualCompressionRetriever

# Compressor: LLM se sirf relevant parts extract karo
compressor = LLMChainExtractor.from_llm(llm)

# Wrap existing retriever
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 5})
)

# Returns only relevant sentences, not full chunks
compressed_results = compression_retriever.get_relevant_documents(
    "FastAPI authentication kaise karein?"
)
```

**Alternative: Embeddings Filter**
```python
from langchain.retrievers.document_compressors import EmbeddingsFilter

embeddings_filter = EmbeddingsFilter(
    embeddings=embeddings,
    similarity_threshold=0.76  # Keep only highly relevant sentences
)
```

---

### Pattern 3: Self-Query Retriever

**Problem:** User natural language mein filter conditions bolta hai.

```
Query: "2024 ke baad publish hua Machine Learning articles dhundo"

Natural language → Structured filter:
{
  "query": "Machine Learning",
  "filter": {
    "operator": "gt",
    "attribute": "publish_date",
    "value": "2024-01-01"
  }
}
```

**Implementation:**

```python
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo

metadata_field_info = [
    AttributeInfo(
        name="source",
        description="The source document or URL",
        type="string",
    ),
    AttributeInfo(
        name="year",
        description="The year the document was published",
        type="integer",
    ),
    AttributeInfo(
        name="topic",
        description="Main topic: 'python', 'ml', 'devops', 'database'",
        type="string",
    ),
]

retriever = SelfQueryRetriever.from_llm(
    llm,
    vectorstore,
    "Technical documentation and articles",
    metadata_field_info,
    verbose=True
)

# LLM automatically extracts filter
results = retriever.get_relevant_documents(
    "2023 ke Python DevOps articles"
)
# Generated query: query="DevOps articles", filter=AND(topic=python, year>=2023)
```

---

### Pattern 4: Maximal Marginal Relevance (MMR)

**Problem:** Top-5 results saari same topic pe hain — redundant.

```
Query: "Python performance optimization"

Without MMR (top-5 similar):
1. "Use list comprehensions for better performance"
2. "List comprehensions are faster than loops"    ← Redundant!
3. "List comprehensions vs for loops benchmark"   ← Redundant!
4. "Python profiling with cProfile"
5. "Memory optimization in Python"

With MMR (diverse):
1. "Use list comprehensions for better performance"
2. "Python profiling with cProfile"
3. "Memory optimization in Python"
4. "NumPy for numerical computations"
5. "Cython for CPU-bound tasks"
```

**MMR Algorithm:**
```python
def mmr_selection(query_embedding, doc_embeddings, lambda_mult=0.5, k=5):
    """
    lambda_mult: 0 = max diversity, 1 = max relevance
    
    Score = lambda * sim(query, doc) - (1-lambda) * max_sim(doc, already_selected)
    """
    selected = []
    remaining = list(range(len(doc_embeddings)))
    
    for _ in range(k):
        if not remaining:
            break
        
        best_score = -float('inf')
        best_idx = None
        
        for idx in remaining:
            # Relevance to query
            relevance = cosine_sim(query_embedding, doc_embeddings[idx])
            
            # Similarity to already selected (max)
            if selected:
                redundancy = max(
                    cosine_sim(doc_embeddings[idx], doc_embeddings[s]) 
                    for s in selected
                )
            else:
                redundancy = 0
            
            score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
            
            if score > best_score:
                best_score = score
                best_idx = idx
        
        selected.append(best_idx)
        remaining.remove(best_idx)
    
    return selected

# LangChain mein:
results = vectorstore.max_marginal_relevance_search(
    query,
    k=5,
    fetch_k=20,   # Pehle 20 retrieve, phir MMR se 5 select
    lambda_mult=0.5
)
```

---

### Pattern 5: Step-Back Prompting

**Idea:** Specific question se pehle abstract question poochho.

```
Original: "FastAPI mein JWT token kaise verify karein?"

Step-back abstract: "Python web frameworks mein authentication kaise kaam karta hai?"

Process:
1. Abstract question se generic auth concepts retrieve karo
2. Specific question se JWT-specific info retrieve karo
3. Dono contexts combine karke answer do

Benefit: LLM ko broader context milta hai, better answers
```

```python
STEP_BACK_PROMPT = """
You are an expert at world knowledge. Your task is to step back and 
paraphrase a question to a more generic step-back question, which is 
easier to answer.

Original question: {question}
Step-back question:
"""

def step_back_retrieve(original_query, llm, retriever):
    # Step 1: Generate abstract question
    step_back_query = llm.invoke(
        STEP_BACK_PROMPT.format(question=original_query)
    ).content
    
    # Step 2: Retrieve for both
    original_results = retriever.get_relevant_documents(original_query)
    stepback_results = retriever.get_relevant_documents(step_back_query)
    
    # Step 3: Combine (deduplicated)
    all_docs = {doc.page_content: doc 
                for doc in original_results + stepback_results}
    
    return list(all_docs.values())
```

---

## 6. Corrective RAG (CRAG)

### Motivation

**Problem:** Retrieval always succeeds nahi karta. Agar retrieved docs irrelevant hain, toh LLM hallucinate karega.

**CRAG Solution:** Retrieved documents ko grade karo. Agar irrelevant, fallback to web search.

---

### CRAG Flow

```
Query
  ↓
Retrieve documents
  ↓
Grade each document (LLM judge)
  ↓
All relevant? → Use docs → Generate answer
  ↓
Some irrelevant? → Filter + Web search → Combine → Generate answer
  ↓  
All irrelevant? → Web search only → Generate answer
```

---

### LangGraph CRAG Implementation

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class GraphState(TypedDict):
    question: str
    documents: List[str]
    web_search_needed: bool
    generation: str

def retrieve(state: GraphState):
    docs = retriever.get_relevant_documents(state["question"])
    return {"documents": [d.page_content for d in docs]}

def grade_documents(state: GraphState):
    """LLM se har document ko grade karo"""
    grading_prompt = """
    Document: {document}
    Question: {question}
    
    Is this document relevant to answer the question? 
    Answer 'yes' or 'no' only.
    """
    
    relevant_docs = []
    web_needed = False
    
    for doc in state["documents"]:
        result = llm.invoke(grading_prompt.format(
            document=doc, 
            question=state["question"]
        )).content.strip().lower()
        
        if result == "yes":
            relevant_docs.append(doc)
        else:
            web_needed = True  # At least one irrelevant → consider web search
    
    return {
        "documents": relevant_docs,
        "web_search_needed": web_needed or len(relevant_docs) == 0
    }

def web_search(state: GraphState):
    """Tavily ya Google search"""
    from langchain_community.tools.tavily_search import TavilySearchResults
    search = TavilySearchResults(max_results=3)
    results = search.invoke(state["question"])
    web_docs = [r["content"] for r in results]
    return {"documents": state["documents"] + web_docs}

def generate(state: GraphState):
    context = "\n\n".join(state["documents"])
    response = llm.invoke(
        f"Context:\n{context}\n\nQuestion: {state['question']}\nAnswer:"
    )
    return {"generation": response.content}

def should_web_search(state: GraphState):
    return "web_search" if state["web_search_needed"] else "generate"

# Build graph
workflow = StateGraph(GraphState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate", generate)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges("grade_documents", should_web_search)
workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", END)

app = workflow.compile()
result = app.invoke({"question": "Latest Python 3.13 features"})
```

---

### Knowledge Refinement in CRAG

```python
KNOWLEDGE_REFINEMENT_PROMPT = """
Given the following documents, extract and refine the key information 
relevant to answering: "{question}"

Documents:
{documents}

Extract only the relevant facts, removing noise and irrelevant information.
Refined knowledge:
"""

def refine_knowledge(question, docs, llm):
    """
    Web search results mein bahut noise hoti hai.
    LLM se relevant parts extract karo.
    """
    refined = llm.invoke(
        KNOWLEDGE_REFINEMENT_PROMPT.format(
            question=question,
            documents="\n---\n".join(docs[:5])  # Top 5 docs
        )
    ).content
    return [refined]  # Single refined document
```

---

## 7. Self-RAG

### Concept

**Problem with standard RAG:** Har query ke liye retrieval karo — even simple questions ko.

```
Q: "2 + 2 kya hai?"
Standard RAG: Retrieve karo → Context do → Answer
Self-RAG: Is retrieval even needed? NO → Direct answer: 4
```

**Self-RAG ke 4 special tokens:**

| Token | Meaning | Values |
|-------|---------|--------|
| `[Retrieve]` | Should I retrieve? | yes/no |
| `[ISREL]` | Is retrieved doc relevant? | relevant/irrelevant |
| `[ISSUP]` | Does generation follow from doc? | supported/partially supported/not supported |
| `[ISUSE]` | Is generation useful? | 1-5 scale |

---

### Self-RAG Flow

```python
def self_rag_pipeline(query, retriever, llm):
    """
    Simplified Self-RAG implementation
    """
    
    # Step 1: Should we retrieve?
    retrieve_decision = llm.invoke(
        f"""Question: {query}
        
        Do you need external knowledge to answer this, or can you answer from 
        your training data? Answer 'retrieve' or 'direct'.
        Decision:"""
    ).content.strip()
    
    if retrieve_decision == "direct":
        # No retrieval needed
        answer = llm.invoke(f"Answer: {query}").content
        return {"answer": answer, "retrieved": False}
    
    # Step 2: Retrieve
    docs = retriever.get_relevant_documents(query)
    
    # Step 3: Grade relevance
    relevant_docs = []
    for doc in docs:
        is_relevant = llm.invoke(
            f"""Query: {query}
            Document: {doc.page_content[:500]}
            
            Is this document relevant? Answer 'relevant' or 'irrelevant'."""
        ).content.strip()
        if is_relevant == "relevant":
            relevant_docs.append(doc)
    
    if not relevant_docs:
        # Self-correction: no relevant docs found
        answer = llm.invoke(f"I couldn't find relevant information. Best answer: {query}").content
        return {"answer": answer, "retrieved": True, "relevant_docs": 0}
    
    # Step 4: Generate
    context = "\n".join([d.page_content for d in relevant_docs[:3]])
    answer = llm.invoke(
        f"Context: {context}\n\nQuestion: {query}\nAnswer:"
    ).content
    
    # Step 5: Hallucination check
    is_supported = llm.invoke(
        f"""Context: {context}
        Generated answer: {answer}
        
        Is every claim in the answer supported by the context? 
        Answer 'supported', 'partially supported', or 'not supported'."""
    ).content.strip()
    
    if is_supported == "not supported":
        # Regenerate more carefully
        answer = llm.invoke(
            f"Based ONLY on this context:\n{context}\n\nAnswer: {query}\nStay strictly within the context."
        ).content
    
    return {
        "answer": answer,
        "retrieved": True,
        "relevant_docs": len(relevant_docs),
        "support_status": is_supported
    }
```

---

### Self-RAG vs CRAG — Key Differences

| Aspect | CRAG | Self-RAG |
|--------|------|---------|
| Retrieval trigger | Always retrieves | Decides if retrieval needed |
| Fallback | Web search | More careful generation |
| Hallucination check | No explicit check | Yes — [ISSUP] token |
| Usefulness check | No | Yes — [ISUSE] token |
| Complexity | Medium | High |
| Best for | When docs may be outdated | When some queries don't need retrieval |

---

## 8. Agentic RAG

### RAG as a Tool

**Standard RAG:** Fixed pipeline — always retrieve → generate.

**Agentic RAG:** RAG ek tool hai jise agent kab aur kaise use karna hai ye khud decide karta hai.

```python
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent

@tool
def search_knowledge_base(query: str) -> str:
    """Search internal documentation and knowledge base for relevant information."""
    docs = retriever.get_relevant_documents(query)
    return "\n\n".join([d.page_content for d in docs[:3]])

@tool  
def search_web(query: str) -> str:
    """Search the web for current information not in knowledge base."""
    results = tavily_search.invoke(query)
    return "\n".join([r["content"] for r in results[:3]])

@tool
def get_database_info(sql_query: str) -> str:
    """Execute a read-only SQL query to get structured data."""
    # Execute safely
    return execute_readonly_query(sql_query)

# Agent with multiple tools including RAG
agent = create_openai_tools_agent(
    llm=ChatOpenAI(model="gpt-4"),
    tools=[search_knowledge_base, search_web, get_database_info],
    prompt=agent_prompt
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Agent decides which tool to use and when
result = agent_executor.invoke({
    "input": "Compare our API documentation with current industry standards"
})
```

---

### Multi-Step Retrieval

**Complex query decomposition:**

```python
DECOMPOSE_PROMPT = """
Break down this complex question into 2-4 simpler sub-questions 
that can be answered independently.

Complex question: {question}

Sub-questions (one per line):
"""

def iterative_rag(complex_query, retriever, llm):
    """
    Multi-step RAG:
    1. Decompose complex query
    2. Answer each sub-question
    3. Combine answers
    """
    
    # Step 1: Decompose
    subquestions_text = llm.invoke(
        DECOMPOSE_PROMPT.format(question=complex_query)
    ).content
    subquestions = [q.strip() for q in subquestions_text.strip().split('\n') if q.strip()]
    
    print(f"Decomposed into {len(subquestions)} sub-questions:")
    for sq in subquestions:
        print(f"  - {sq}")
    
    # Step 2: Answer each sub-question
    sub_answers = []
    for sq in subquestions:
        docs = retriever.get_relevant_documents(sq)
        context = "\n".join([d.page_content for d in docs[:3]])
        answer = llm.invoke(f"Context: {context}\n\nQuestion: {sq}\nAnswer:").content
        sub_answers.append({"question": sq, "answer": answer})
    
    # Step 3: Synthesize final answer
    synthesis_prompt = f"""
    Original question: {complex_query}
    
    Sub-answers gathered:
    {chr(10).join([f"Q: {sa['question']}\nA: {sa['answer']}" for sa in sub_answers])}
    
    Based on the above, provide a comprehensive final answer:
    """
    
    final_answer = llm.invoke(synthesis_prompt).content
    return final_answer
```

---

### LangGraph Agentic RAG Pattern

```
[User Query]
     ↓
[Agent — decides action]
     ↓
  ┌──────────────────────────┐
  │  Tool selection:          │
  │  - search_docs            │
  │  - web_search             │
  │  - calculate              │
  │  - lookup_db              │
  └──────────────────────────┘
     ↓
[Execute Tool]
     ↓
[Agent evaluates result]
     ↓
Enough info? → YES → Generate Answer
     ↓
NO → Select another tool → Loop
```

---

## 9. RAPTOR — Recursive Abstractive Processing for Tree-Organized Retrieval

### Motivation

**Problem:** Large document mein:
- Low-level details: Section 3.2.1 mein specific implementation
- Mid-level: Chapter 3 ka summary
- High-level: Entire document ka theme

Simple RAG sirf leaf-level chunks retrieve karta hai. Big picture miss ho jaati hai.

---

### RAPTOR Tree Building

```
Original chunks (leaf nodes):
[C1] [C2] [C3] [C4] [C5] [C6] [C7] [C8]
  ↓ Cluster similar chunks
[Cluster 1: C1,C2,C3] [Cluster 2: C4,C5] [Cluster 3: C6,C7,C8]
  ↓ Summarize each cluster
[Summary 1] [Summary 2] [Summary 3]
  ↓ Cluster summaries
[Super-cluster: Sum1,Sum2,Sum3]
  ↓ Final summary
[Root Summary: Document overview]
```

**Implementation:**

```python
from sklearn.mixture import GaussianMixture
import numpy as np

def build_raptor_tree(chunks, embeddings_model, llm, max_levels=3):
    """
    RAPTOR tree: bottom-up summarization with clustering
    """
    tree = {"leaves": chunks, "levels": []}
    current_level = chunks
    
    for level in range(max_levels):
        if len(current_level) <= 1:
            break
        
        # Step 1: Embed current level nodes
        texts = [c if isinstance(c, str) else c["content"] for c in current_level]
        embeddings = embeddings_model.encode(texts)
        
        # Step 2: Cluster using GMM
        n_clusters = max(2, len(current_level) // 3)
        gmm = GaussianMixture(n_components=n_clusters, random_state=42)
        gmm.fit(embeddings)
        cluster_labels = gmm.predict(embeddings)
        
        # Step 3: Summarize each cluster
        summaries = []
        for cluster_id in range(n_clusters):
            cluster_texts = [texts[i] for i, l in enumerate(cluster_labels) if l == cluster_id]
            
            if not cluster_texts:
                continue
            
            summary = llm.invoke(
                f"Summarize the following related documents concisely:\n\n"
                + "\n---\n".join(cluster_texts[:5])  # Limit to 5 per cluster
            ).content
            
            summaries.append({
                "content": summary,
                "level": level + 1,
                "source_chunks": cluster_texts
            })
        
        tree["levels"].append(summaries)
        current_level = summaries
        
        print(f"Level {level+1}: {len(summaries)} summaries from {len(texts)} nodes")
    
    return tree

def raptor_retrieve(query, tree, embeddings_model, k_per_level=2):
    """
    Retrieve from multiple levels of the tree
    """
    query_embedding = embeddings_model.encode([query])[0]
    all_retrieved = []
    
    # Retrieve from leaves
    leaf_embeddings = embeddings_model.encode(tree["leaves"])
    scores = leaf_embeddings @ query_embedding
    top_leaf_idx = np.argsort(scores)[::-1][:k_per_level]
    all_retrieved.extend([tree["leaves"][i] for i in top_leaf_idx])
    
    # Retrieve from each summary level
    for level_summaries in tree["levels"]:
        texts = [s["content"] for s in level_summaries]
        level_embeddings = embeddings_model.encode(texts)
        scores = level_embeddings @ query_embedding
        top_idx = np.argsort(scores)[::-1][:k_per_level]
        all_retrieved.extend([level_summaries[i]["content"] for i in top_idx])
    
    return all_retrieved
```

**When to use RAPTOR:**
- Annual reports, research papers, books
- Queries requiring big-picture understanding
- "Give me an overview of X" type questions
- Multi-hop reasoning across document sections

---

## 10. RAG Evaluation — RAGAS

### Kyun Evaluation Important Hai?

> "Jo measure nahi hota, wo improve nahi hota."

RAG pipeline ke multiple components hain — koi bhi fail ho sakta hai:
- Chunking poor? → Bad retrieval
- Retrieval poor? → Wrong context
- Generation poor? → Hallucination

RAGAS (RAG Assessment) framework in sab ko measure karta hai.

---

### 4 Core RAGAS Metrics

#### 1. Faithfulness (0-1)

**Kya answer context pe grounded hai?**

```
Context: "Python was created by Guido van Rossum in 1991."
Answer: "Python was created by Guido van Rossum in 1991 and is now maintained by the PSF."

Claim 1: "Python created by Guido van Rossum in 1991" → Supported ✅
Claim 2: "maintained by PSF" → Not in context! ❌

Faithfulness = 1/2 = 0.5

High faithfulness → Low hallucination
```

#### 2. Answer Relevancy (0-1)

**Kya answer question address karta hai?**

```python
# RAGAS implementation: LLM backwards questions generate karta hai
# Answer se hypothetical questions banao → query se similarity check karo

def answer_relevancy_score(question, answer, llm, n_questions=3):
    """
    Generate questions from answer, compare to original question
    """
    gen_questions = llm.invoke(
        f"Generate {n_questions} questions that the following answer is answering:\n{answer}"
    ).content.split('\n')
    
    question_embedding = embed(question)
    gen_embeddings = [embed(q) for q in gen_questions]
    
    similarities = [cosine_sim(question_embedding, ge) for ge in gen_embeddings]
    return np.mean(similarities)
```

#### 3. Context Precision (0-1)

**Retrieved chunks mein se kitne actually useful hain?**

```
Query: "Python ke data types"
Retrieved chunks:
1. "Python has int, float, str, list, dict types" ← Relevant ✅
2. "Python was created in 1991" ← Not relevant ❌
3. "Python list is mutable, tuple is immutable" ← Relevant ✅
4. "Guido van Rossum is Python's creator" ← Not relevant ❌
5. "Python dict stores key-value pairs" ← Relevant ✅

Simple intuition: 3 relevant / 5 total = 0.60

High precision → Less noise in context
```

> ⚠️ RAGAS ka actual `context_precision` SIRF relevant/total nahi — wo **rank-aware** hai
> (relevant chunks ki position pe precision@k ka mean). Relevant docs upar ranked → score zyada.
> "3/5" sirf intuition ke liye.

#### 4. Context Recall (0-1)

**Ground truth answer ke liye zaruri saari info retrieved hui?**

```
Ground truth: "Python data types include int, float, str, list, tuple, dict, set, bool"

Ground truth statements:
1. "int" ← Found in context ✅
2. "float" ← Found in context ✅
3. "str" ← Found in context ✅  
4. "tuple" ← NOT in context ❌ (we forgot to retrieve tuple info)
5. "set" ← NOT in context ❌
6. "bool" ← NOT in context ❌

Context Recall = 3/6 = 0.50

High recall → Nothing important was missed
```

#### 5. Answer Correctness

```python
# Factual correctness vs ground truth
# F1 = harmonic mean of precision and recall on facts

def answer_correctness(answer, ground_truth, llm):
    # Extract claims from answer
    answer_claims = extract_claims(answer, llm)
    gt_claims = extract_claims(ground_truth, llm)
    
    # Check overlap
    supported = sum(1 for claim in answer_claims if claim_in(claim, gt_claims))
    precision = supported / len(answer_claims) if answer_claims else 0
    recall = supported / len(gt_claims) if gt_claims else 0
    
    if precision + recall == 0:
        return 0
    f1 = 2 * precision * recall / (precision + recall)
    return f1
```

---

### RAGAS Full Pipeline

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness
)
from datasets import Dataset

# Test dataset banana
test_data = {
    "question": [
        "What is Python's GIL?",
        "How does FastAPI handle async requests?",
    ],
    "answer": [
        "GIL stands for Global Interpreter Lock...",
        "FastAPI uses Starlette's async capabilities...",
    ],
    "contexts": [
        ["Python's GIL prevents multiple threads...", "GIL was introduced because..."],
        ["FastAPI is built on Starlette...", "async def endpoints..."],
    ],
    "ground_truth": [
        "The Global Interpreter Lock (GIL) is a mutex...",
        "FastAPI handles async requests using Python's asyncio...",
    ]
}

dataset = Dataset.from_dict(test_data)

# Evaluate
results = evaluate(
    dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness
    ]
)

print(results)
# Output: {'faithfulness': 0.87, 'answer_relevancy': 0.92, ...}
```

---

### LangSmith Integration

```python
from langsmith import Client

client = Client()

# Online evaluation — production mein automatically evaluate karo
# Har query ka evaluation automatically track ho
with langsmith_tracer:
    result = rag_pipeline.invoke({"question": user_query})
    
# LangSmith dashboard mein:
# - Per-query faithfulness scores
# - Retrieval quality over time
# - Regression detection
```

---

## 11. Embedding Strategies

### Embedding Model Selection

**Key criteria:**

| Factor | Consideration |
|--------|---------------|
| Dimension | Higher = more expressive but slower/costly |
| Max tokens | Document max length |
| Speed | Batch throughput for ingestion |
| Task | Retrieval vs classification vs clustering |
| Language | English-only vs multilingual |
| Cost | API pricing vs self-hosted |

---

### OpenAI Embeddings

```python
from openai import OpenAI
client = OpenAI()

# text-embedding-3-small
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="Python asyncio tutorial"
)
embedding = response.data[0].embedding  # 1536 dimensions

# text-embedding-3-large  
response = client.embeddings.create(
    model="text-embedding-3-large",
    input="Python asyncio tutorial"
)
embedding = response.data[0].embedding  # 3072 dimensions
```

**Comparison:**

| Model | Dimensions | MTEB Score | Cost | Best For |
|-------|-----------|------------|------|----------|
| text-embedding-3-small | 1536 | 62.3 | $0.02/1M tokens | Production (cost-effective) |
| text-embedding-3-large | 3072 | 64.6 | $0.13/1M tokens | Best quality needed |
| text-embedding-ada-002 | 1536 | 61.0 | $0.10/1M tokens | Legacy |

---

### Open-Source Embedding Models

```python
from sentence_transformers import SentenceTransformer

# BAAI/bge-m3 — Best open-source general purpose
model = SentenceTransformer("BAAI/bge-m3")
embeddings = model.encode(["Hello world"], normalize_embeddings=True)
# 1024 dimensions, multilingual, ~570M params

# nomic-embed-text — Apache 2.0, good for long docs  
model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)
# 768 dimensions, 8192 token context!

# all-MiniLM-L6-v2 — Fast, lightweight
model = SentenceTransformer("all-MiniLM-L6-v2")
# 384 dimensions, very fast, good for real-time
```

---

### Matryoshka Embeddings

**Concept:** Russian doll jaisi — embedding truncate karo, phir bhi kaam kare.

```python
# text-embedding-3 supports Matryoshka (Adaptive Dimensionality)
response = client.embeddings.create(
    model="text-embedding-3-large",
    input="Hello world",
    dimensions=256  # Truncate from 3072 to 256 — still works well!
)

# Why useful?
# Full 3072 dim: highest quality, high storage/compute
# 256 dim: 12x faster similarity search, 12x less storage, ~95% quality retained

# MTEB scores for text-embedding-3-large at various dimensions:
# 3072 dim: 64.6
# 1536 dim: 64.1 (same model, half size!)
# 512 dim: 63.1
# 256 dim: 62.0
# 64 dim: 56.5
```

---

### Multi-lingual Embeddings

```python
# paraphrase-multilingual-MiniLM-L12-v2 — 50+ languages
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Cross-lingual retrieval:
# Index: English documents
# Query: Hindi mein — "Python kya hai?"
# Still finds relevant English docs!
hindi_query = "Python kya hai aur iska use kahan hota hai?"
embedding = model.encode(hindi_query)
# Returns relevant English docs about Python

# BAAI/bge-m3 — best multilingual
# Supports 100+ languages
# Handles mixed-language queries
```

---

## 12. Production RAG Architecture

### Ingestion Pipeline

```
Raw Documents (PDF, DOCX, Web, DB)
           ↓
    Document Loader
           ↓
    Text Extraction + Cleaning
           ↓
    Chunking Strategy (based on doc type)
           ↓
    Metadata Enrichment (source, date, section)
           ↓
    Embedding Generation (batch, async)
           ↓
    Vector Store Upsert
           ↓
    BM25 Index Update (if hybrid search)
```

```python
import asyncio
from typing import List
from dataclasses import dataclass

@dataclass
class Document:
    content: str
    metadata: dict
    doc_id: str

async def ingest_document(doc: Document, vectorstore, embedder):
    """Async document ingestion"""
    # Step 1: Chunk
    chunks = chunker.split_text(doc.content)
    
    # Step 2: Embed in batches
    batch_size = 100
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        embeddings = await asyncio.to_thread(embedder.encode, batch)
        all_embeddings.extend(embeddings)
    
    # Step 3: Store
    await vectorstore.aadd_texts(
        texts=chunks,
        embeddings=all_embeddings,
        metadatas=[{**doc.metadata, "chunk_idx": i} for i in range(len(chunks))]
    )

async def bulk_ingest(documents: List[Document], vectorstore, embedder):
    """Parallel ingestion for multiple docs"""
    tasks = [ingest_document(doc, vectorstore, embedder) for doc in documents]
    await asyncio.gather(*tasks, return_exceptions=True)
```

---

### Query Pipeline

```
User Query
    ↓
Query Analysis (language, intent, filters)
    ↓
Semantic Cache Check → HIT: return cached answer
    ↓ MISS
Multi-Query Expansion (optional)
    ↓
Hybrid Retrieval (BM25 + Vector)
    ↓
Reranking (cross-encoder)
    ↓
Context Assembly + Lost-in-Middle Fix
    ↓
LLM Generation
    ↓
Answer + Sources
    ↓
Cache Store
```

---

### Semantic Caching

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticCache:
    def __init__(self, threshold=0.95):
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.cache = []  # [(query_embedding, answer)]
        self.threshold = threshold
    
    def get(self, query: str):
        if not self.cache:
            return None
        
        query_emb = self.encoder.encode([query])[0]
        
        for cached_emb, answer in self.cache:
            similarity = np.dot(query_emb, cached_emb)
            if similarity > self.threshold:
                print(f"Cache HIT (similarity: {similarity:.3f})")
                return answer
        
        return None
    
    def set(self, query: str, answer: str):
        query_emb = self.encoder.encode([query])[0]
        self.cache.append((query_emb, answer))
    
    # Production: Redis + pgvector mein store karo
```

---

### Multi-Tenant RAG

```python
# Namespace per user/organization
def get_retriever_for_tenant(tenant_id: str):
    """
    Har tenant ka alag namespace/collection
    """
    return Chroma(
        collection_name=f"tenant_{tenant_id}",  # Isolated collection
        embedding_function=embeddings
    ).as_retriever()

# Pinecone mein namespace:
index.upsert(vectors=embeddings, namespace=f"tenant_{tenant_id}")

results = index.query(
    vector=query_embedding,
    top_k=10,
    namespace=f"tenant_{tenant_id}"  # Only search this tenant's docs
)
```

---

### Incremental Updates

```python
import hashlib

class IncrementalIndexer:
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
        self.doc_hashes = {}  # doc_id → hash
    
    def compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()
    
    def update(self, doc_id: str, content: str):
        new_hash = self.compute_hash(content)
        
        if doc_id in self.doc_hashes:
            if self.doc_hashes[doc_id] == new_hash:
                print(f"Doc {doc_id}: No change, skipping")
                return
            else:
                # Delete old chunks
                self.vectorstore.delete(filter={"doc_id": doc_id})
                print(f"Doc {doc_id}: Updated, re-indexing")
        else:
            print(f"Doc {doc_id}: New document, indexing")
        
        # Re-index
        chunks = chunker.split_text(content)
        self.vectorstore.add_texts(
            texts=chunks,
            metadatas=[{"doc_id": doc_id, "chunk": i} for i in range(len(chunks))]
        )
        self.doc_hashes[doc_id] = new_hash
```

---

## 13. Multi-modal RAG (Basics)

### Image + Text Retrieval

**Traditional RAG:** Only text documents

**Multi-modal RAG:** Images, tables, charts bhi index karo

```python
# ColPali: Document page ko directly embed karo (no text extraction needed)
# CLIP: Images aur text ko same embedding space mein

from transformers import CLIPProcessor, CLIPModel
import torch

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

def embed_image(image):
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    return image_features[0].numpy()

def embed_text_for_images(text):
    inputs = processor(text=text, return_tensors="pt")
    with torch.no_grad():
        text_features = model.get_text_features(**inputs)
    return text_features[0].numpy()

# Cross-modal retrieval:
# Query: text → text embedding
# Documents: images → image embeddings
# They're in same space → search works!
```

---

### Tables Extraction

```python
# PyMuPDF ya Camelot se tables extract karo
import camelot

tables = camelot.read_pdf("report.pdf", pages="1-3")

for table in tables:
    # Convert to markdown for better LLM understanding
    markdown_table = table.df.to_markdown()
    
    # Index as text
    vectorstore.add_texts(
        texts=[f"Table from page {table.page}:\n{markdown_table}"],
        metadatas=[{"type": "table", "page": table.page}]
    )
```

---

## 14. 15 Interview Q&As

### Q1: BM25 vs Vector Search — kab kaunsa use karein?

**Answer:**
BM25 keyword-based hai — exact terms, product codes, IDs, legal terms ke liye better. Vector search semantic hai — paraphrasing, synonyms handle karta hai. Production mein always hybrid use karo. BM25 weight zyada jab: technical docs, exact term matching needed. Vector weight zyada jab: conversational queries, multilingual.

---

### Q2: RRF formula explain karo aur k=60 kyun?

**Answer:**
`RRF_score(d) = Σ 1/(k + rank(d))` where k=60 is a smoothing constant.

k=60 isliye default hai kyunki ye "rank insensitivity" deta hai — rank 1 aur rank 5 ke beech score difference minimum ho jaata hai. Iska matlab: agar document consistently middle mein ranked hai sabhi methods mein, toh bhi wo high score paata hai. Ye individual ranker bias reduce karta hai.

---

### Q3: Reranking kab zaruri hai?

**Answer:**
Jab: (1) retrieval pool bada ho (top-50 se top-5 mein refine karna), (2) query complex ho with multiple aspects, (3) answer quality critical ho, (4) false positives costly hon (e.g., medical, legal). Nahi chahiye jab: real-time search with latency < 100ms, simple keyword queries.

---

### Q4: Cross-encoder vs bi-encoder — accuracy vs speed tradeoff

**Answer:**
Bi-encoder: query aur document alag encode → dot product. Fast (precomputed), scalable to millions. Less accurate — no cross-attention.

Cross-encoder: [query + document] ek saath encode → relevance score. Slow (query time pe), not scalable. Highly accurate — full cross-attention.

Production pattern: bi-encoder retrieve top-100, cross-encoder rerank to top-5.

---

### Q5: Lost-in-the-middle problem solve kaise karein?

**Answer:**
Liu et al. 2023 research: LLMs tend to use beginning aur end of context, ignore middle.

Solutions:
1. Reorder chunks: best chunks at position 0 and -1, zigzag remaining
2. Fewer, better chunks: reranking se quality improve karo
3. Shorter context: compress chunks, extract only relevant sentences
4. Models with better long-context: GPT-4-turbo, Claude Opus (better at attending to middle)

---

### Q6: CRAG vs Self-RAG — key differences?

**Answer:**
CRAG: Retrieved documents ko grade karta hai (relevant/irrelevant), irrelevant hone pe web search fallback. Focus on retrieval quality improvement.

Self-RAG: Pehle decide karta hai ki retrieval zaruri hai ya nahi. Generate karne ke baad bhi check karta hai (hallucination? useful?). More comprehensive self-reflection.

CRAG better when: docs may be outdated/irrelevant (use web fallback).
Self-RAG better when: selective retrieval needed, hallucination prevention critical.

---

### Q7: RAGAS 4 metrics explain karo

**Answer:**
1. **Faithfulness**: Answer ke claims context mein supported hain? Hallucination measure.
2. **Answer Relevancy**: Answer ne question address kiya? Off-topic answers penalize.
3. **Context Precision**: Retrieved chunks me se useful ones — **rank-aware** (relevant chunks upar ranked hone par zyada score; plain ratio nahi). Noise measure.
4. **Context Recall**: Ground truth ke liye zaruri saari info retrieved? Missing info measure.

Perfect system: all four = 1.0. Trade-off: high recall often means lower precision (more chunks = more noise).

---

### Q8: Parent-document retriever ka benefit kya hai?

**Answer:**
Small chunks precise retrieval ke liye, large chunks better context ke liye. Problem solve: "Retrieve small, return large."

Example: 200-token child chunk precisely matches query. Parent 2000-token chunk LLM ko full context deta hai — coreferences, examples, surrounding explanation ke saath. 30-40% answer quality improvement vs pure small-chunk RAG.

---

### Q9: Multi-query retrieval kyun aur kaise kaam karta hai?

**Answer:**
Single query se saare relevant perspectives retrieve nahi hote. Multi-query: LLM 3-5 query variants generate karta hai (synonyms, different angles, rephrasing). Har variant se retrieve karo, results merge + deduplicate karo.

Example: "Python performance" → "Python optimization techniques", "speed up Python code", "Python profiling", "Python bottlenecks"

Result: 40-60% better recall, especially for complex multi-faceted questions.

---

### Q10: MMR diversity kaise provide karta hai?

**Answer:**
MMR (Maximal Marginal Relevance): `score = λ × relevance(query, doc) - (1-λ) × max_similarity(doc, selected_docs)`

λ=0: max diversity, λ=1: max relevance.

Iteration mein: greedy selection — har step pe query ke liye relevant lekin already selected docs se different document choose karo. Redundant chunks eliminate karta hai, comprehensive coverage deta hai.

---

### Q11: Agentic RAG vs Pipeline RAG — difference?

**Answer:**
Pipeline RAG: Fixed flow — always retrieve → generate. Simple, predictable, fast.

Agentic RAG: Agent decides when to retrieve, what to search, multiple tools, iterative. Handle karta hai: complex multi-step queries, tool use, web search fallback, database queries.

Use pipeline: simple Q&A, latency critical, single knowledge base.
Use agentic: research tasks, multi-source synthesis, dynamic information needed.

---

### Q12: Chunking strategy kaise choose karein?

**Answer:**
Decision tree:
- Plain text articles → Recursive (500 tokens, 50 overlap)
- Markdown documentation → MarkdownHeaderSplitter
- Code → Language-specific splitter (Python/JS/etc.)
- Need both precision and context → Parent-Document Retriever
- Semantic consistency critical → SemanticChunker (slower)
- Long docs with cross-references → Late Chunking
- Always: test with eval dataset, measure retrieval recall

---

### Q13: Embedding model kaise select karein?

**Answer:**
Criteria:
1. **Task**: Retrieval → bge-m3, all-mpnet. Classification → different models.
2. **Language**: Multilingual → bge-m3, paraphrase-multilingual. English only → all-MiniLM.
3. **Speed**: Real-time → all-MiniLM-L6 (384 dim). Batch ingestion → larger models ok.
4. **Cost**: Self-hosted → open source. Managed → OpenAI (small for prod, large for quality).
5. **Dimension**: Matryoshka models → truncate as needed for speed.

Test on your domain-specific eval set before production!

---

### Q14: RAPTOR ka use case kya hai?

**Answer:**
RAPTOR best suited for:
- Long documents (100+ pages): annual reports, research papers, legal documents
- Questions requiring big-picture understanding: "What is the overall strategy?"
- Multi-hop reasoning: information scattered across sections
- Both detail and summary needed

Not suited for: real-time ingestion (slow tree building), frequently updated docs, short documents.

---

### Q15: Production RAG ke bottlenecks kya hain?

**Answer:**

| Bottleneck | Impact | Solution |
|-----------|--------|----------|
| Embedding generation | Slow ingestion | Batch + async, GPU if needed |
| Vector search latency | Slow queries | FAISS HNSW, Pinecone, caching |
| LLM generation | Highest latency | Streaming, smaller models for rerank |
| Reranking | Adds 100-500ms | FlashRank (local, fast), cache frequent queries |
| Context too large | Token costs | Compression, parent-doc retriever |
| Stale index | Wrong answers | Incremental updates, versioning |

**P95 latency target:** Retrieval <200ms, reranking <300ms, generation <2s, total <3s.

---

*End of RAG Advanced Theory — 900+ lines*
*Next: Practical implementation in 02_rag_advanced.py*
