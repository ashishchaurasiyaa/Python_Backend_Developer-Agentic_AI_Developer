"""
Phase5_RAG — Complete Practical
=================================
Topics:
  1. Document loading + text splitting
  2. Embeddings (OpenAI / mock)
  3. Vector store: FAISS in-memory
  4. Retrieval strategies: similarity, MMR, threshold
  5. RAG chain (retrieve → augment → generate)
  6. HyDE (Hypothetical Document Embeddings)
  7. Hybrid search (BM25 + vector)
  8. RAGAS evaluation metrics

Install: pip install langchain langchain-openai faiss-cpu rank_bm25
Env: OPENAI_API_KEY

Run: python 01_rag_practical.py
"""

import os, math, random, re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("RAG (Retrieval-Augmented Generation) CONCEPTS")
print("=" * 60)

RAG_CONCEPTS = {
    "RAG Pipeline":      "Retrieve relevant docs → augment prompt → generate answer",
    "Chunking":          "Split docs into overlapping chunks (chunk_size, chunk_overlap)",
    "Embeddings":        "Dense vector representations of text (semantic similarity)",
    "Vector Store":      "Index for fast approximate nearest-neighbor search",
    "Retriever":         "Returns top-k chunks given query embedding",
    "MMR":               "Maximal Marginal Relevance — diverse results, not just similar",
    "HyDE":              "Generate hypothetical answer, use IT as query embedding",
    "Hybrid Search":     "BM25 (keyword) + dense vector, merged with RRF or weighted",
    "RAGAS":             "Evaluate RAG: faithfulness, answer_relevancy, context_precision",
}
for k, v in RAG_CONCEPTS.items():
    print(f"  {k:<22}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Text Splitting
# INTERVIEW: chunk_size=1000 tokens, chunk_overlap=200 for continuity
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Document Loading & Text Splitting")
print("=" * 60)

SPLITTER_CODE = '''\
from langchain_community.document_loaders import (
    TextLoader, PyPDFLoader, WebBaseLoader, CSVLoader,
)
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    TokenTextSplitter,
)

# ── Load documents ─────────────────────────────────────────────
loader = PyPDFLoader("document.pdf")
docs   = loader.load()    # list[Document], each has .page_content, .metadata

# Web scraping
web_loader = WebBaseLoader("https://docs.python.org/3/")
web_docs   = web_loader.load()

# ── Recursive splitter (best general purpose) ─────────────────
splitter = RecursiveCharacterTextSplitter(
    chunk_size    = 1000,    # characters per chunk
    chunk_overlap = 200,     # overlap between chunks for continuity
    separators    = ["\\n\\n", "\\n", " ", ""],  # try these in order
)
chunks = splitter.split_documents(docs)

# ── Markdown-aware splitter ────────────────────────────────────
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on = [
        ("#",   "Header1"),
        ("##",  "Header2"),
        ("###", "Header3"),
    ]
)
md_chunks = md_splitter.split_text(markdown_text)
# Each chunk\'s metadata contains {"Header1": "Intro", "Header2": "Setup"}

# ── Token-based splitter (most accurate for LLM context) ──────
token_splitter = TokenTextSplitter(
    chunk_size    = 512,  # tokens, not chars
    chunk_overlap = 50,
    encoding_name = "cl100k_base",  # GPT-4 encoding
)
'''
print(SPLITTER_CODE[:700])


def simple_text_splitter(text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
    """
    INTERVIEW: RecursiveCharacterTextSplitter tries separators in order.
    overlap=200 means consecutive chunks share 200 chars for continuity.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk:
            chunks.append(chunk)
        start = end - overlap  # overlap ensures continuity
        if start >= len(text):
            break
    return chunks


# Demo
sample_text = """
Python is a high-level, interpreted programming language known for its clear syntax.
It supports multiple programming paradigms including procedural, object-oriented, and functional.

Python was created by Guido van Rossum and first released in 1991. It emphasizes code
readability and allows programmers to express concepts in fewer lines than C++ or Java.

The Python Package Index (PyPI) hosts thousands of third-party modules for Python.
FastAPI, Django, Flask are popular web frameworks. NumPy, Pandas are for data science.
LangChain and LlamaIndex are used for building LLM applications.
""".strip()

chunks = simple_text_splitter(sample_text, chunk_size=200, overlap=50)
print(f"\n  Text length: {len(sample_text)} chars")
print(f"  Chunks (size=200, overlap=50): {len(chunks)}")
for i, c in enumerate(chunks[:3]):
    print(f"  Chunk {i+1}: {c[:80].strip()!r}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Embeddings
# INTERVIEW: cosine_similarity > 0.8 = highly similar
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Embeddings")
print("=" * 60)

EMBEDDING_CODE = '''\
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings  # local, free

# ── OpenAI embeddings ──────────────────────────────────────────
embeddings = OpenAIEmbeddings(
    model = "text-embedding-3-small",  # 1536-dim, cheap
    # model = "text-embedding-3-large",  # 3072-dim, more accurate
)
vector = embeddings.embed_query("What is Python?")
# → list of 1536 floats

vectors = embeddings.embed_documents(["text1", "text2", "text3"])
# → list of 3 vectors

# ── Local embeddings (no API cost) ────────────────────────────
hf_embeddings = HuggingFaceEmbeddings(
    model_name = "sentence-transformers/all-MiniLM-L6-v2",
    # 384-dim, fast, free, runs locally
)
'''

print(EMBEDDING_CODE[:500])
print("\n  Embedding models comparison:")
EMBEDDING_MODELS = {
    "text-embedding-3-small":              "OpenAI, 1536-dim, $0.02/1M tokens",
    "text-embedding-3-large":              "OpenAI, 3072-dim, $0.13/1M tokens",
    "all-MiniLM-L6-v2":                    "Local HF, 384-dim, free, fast",
    "sentence-transformers/all-mpnet-base":"Local HF, 768-dim, higher quality",
    "text-embedding-ada-002":              "OpenAI legacy, 1536-dim",
}
for m, d in EMBEDDING_MODELS.items():
    print(f"  {m:<45}: {d}")


def mock_embed(text: str, dim: int = 8) -> List[float]:
    """Deterministic mock embedding based on text hash."""
    random.seed(hash(text) % (2**31))
    vec = [random.gauss(0, 1) for _ in range(dim)]
    # normalize
    mag = math.sqrt(sum(x*x for x in vec))
    return [x/mag for x in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """INTERVIEW: RAG uses cosine similarity to rank retrieved chunks."""
    dot = sum(x*y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x*x for x in a))
    mb  = math.sqrt(sum(x*x for x in b))
    return dot / (ma * mb + 1e-9)


# Demo similarity
docs_for_demo = [
    "Python is a programming language",
    "Python supports object-oriented programming",
    "JavaScript is used for web development",
    "Machine learning with Python is popular",
]
query = "Python programming"
q_vec = mock_embed(query)
print(f"\n  Query: '{query}'")
print(f"  Cosine similarities (mock embeddings):")
for doc in docs_for_demo:
    d_vec = mock_embed(doc)
    sim   = cosine_similarity(q_vec, d_vec)
    print(f"  {sim:+.4f}  {doc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Vector Store (FAISS)
# INTERVIEW: FAISS = Facebook AI Similarity Search, in-process, no server
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Vector Store (FAISS / Chroma)")
print("=" * 60)

VECTOR_STORE_CODE = '''\
from langchain_community.vectorstores import FAISS, Chroma
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()

# ── Build from documents ───────────────────────────────────────
# INTERVIEW: from_documents = embed + index in one call
db = FAISS.from_documents(chunks, embeddings)

# ── Persist / reload ───────────────────────────────────────────
db.save_local("faiss_index")
db = FAISS.load_local("faiss_index", embeddings)

# ── Similarity search ──────────────────────────────────────────
results = db.similarity_search(
    query = "What is Python?",
    k     = 4,                 # return top 4 chunks
)
for doc in results:
    print(doc.page_content[:100])
    print(doc.metadata)

# ── With scores ────────────────────────────────────────────────
results_with_scores = db.similarity_search_with_score("Python", k=3)
# Returns (Document, float) — float = L2 distance (lower = more similar)

# ── MMR: diverse results ───────────────────────────────────────
# INTERVIEW: MMR = Maximal Marginal Relevance
# lambda_mult=0.5: 50% relevance, 50% diversity
mmr_results = db.max_marginal_relevance_search(
    query       = "Python",
    k           = 4,
    fetch_k     = 20,           # fetch 20, then pick 4 diverse ones
    lambda_mult = 0.5,          # 0=max diversity, 1=max relevance
)

# ── As retriever ───────────────────────────────────────────────
retriever = db.as_retriever(
    search_type   = "mmr",          # or "similarity", "similarity_score_threshold"
    search_kwargs = {"k": 4, "lambda_mult": 0.5},
)
# Use in chain: retriever | format_docs | prompt | llm | parser
'''
print(VECTOR_STORE_CODE[:700])


# Simple in-memory vector store demo
@dataclass
class Document:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class SimpleVectorStore:
    """
    INTERVIEW: Vector store = list of (embedding, document) pairs.
    Search = compute cosine similarity, return top-k.
    FAISS uses ANN (approximate nearest neighbor) for speed at scale.
    """
    def __init__(self, dim: int = 8):
        self.docs: List[Document] = []
        self.dim = dim

    def add_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None):
        for i, text in enumerate(texts):
            meta = (metadatas or [{}]*len(texts))[i]
            doc  = Document(content=text, metadata=meta, embedding=mock_embed(text, self.dim))
            self.docs.append(doc)
        print(f"  Added {len(texts)} documents, total: {len(self.docs)}")

    def similarity_search(self, query: str, k: int = 3) -> List[tuple]:
        q_vec = mock_embed(query, self.dim)
        scored = []
        for doc in self.docs:
            sim = cosine_similarity(q_vec, doc.embedding)
            scored.append((sim, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def mmr_search(self, query: str, k: int = 3, fetch_k: int = 10, lambda_mult: float = 0.5) -> List[Document]:
        """
        INTERVIEW: MMR selects results that are relevant AND diverse.
        Prevents returning 4 nearly identical chunks.
        """
        q_vec  = mock_embed(query, self.dim)
        # fetch more candidates first
        candidates = self.similarity_search(query, k=min(fetch_k, len(self.docs)))
        selected   = []
        remaining  = list(candidates)

        while len(selected) < k and remaining:
            if not selected:
                best = remaining.pop(0)
                selected.append(best[1])
            else:
                # score = λ*relevance - (1-λ)*max_similarity_to_selected
                best_score, best_idx = -1e9, 0
                for i, (rel_score, doc) in enumerate(remaining):
                    max_sim_to_selected = max(
                        cosine_similarity(doc.embedding, s.embedding)
                        for s in selected
                    )
                    mmr = lambda_mult * rel_score - (1 - lambda_mult) * max_sim_to_selected
                    if mmr > best_score:
                        best_score, best_idx = mmr, i
                selected.append(remaining.pop(best_idx)[1])
        return selected


# Demo
print("\n  Building in-memory vector store:")
store = SimpleVectorStore()
store.add_documents([
    "Python is a high-level programming language",
    "Python supports functional and OOP programming",
    "FastAPI is a Python web framework",
    "JavaScript runs in browsers",
    "Machine learning uses Python extensively",
    "Django is another Python web framework",
], metadatas=[{"source": f"doc{i}"} for i in range(6)])

print("\n  Similarity search for 'Python web framework':")
for sim, doc in store.similarity_search("Python web framework", k=3):
    print(f"  {sim:+.4f}  {doc.content}")

print("\n  MMR search (diverse):")
for doc in store.mmr_search("Python web framework", k=3, lambda_mult=0.5):
    print(f"  {doc.content}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: RAG Chain
# INTERVIEW: retrieve → format → prompt with context → LLM → answer
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: RAG Chain")
print("=" * 60)

RAG_CHAIN_CODE = '''\
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ── Build retriever ────────────────────────────────────────────
embeddings = OpenAIEmbeddings()
db         = FAISS.from_documents(chunks, embeddings)
retriever  = db.as_retriever(search_type="mmr", search_kwargs={"k": 4})

# ── RAG prompt ─────────────────────────────────────────────────
rag_prompt = ChatPromptTemplate.from_template("""
You are an assistant answering questions based ONLY on the provided context.
If the answer is not in the context, say "I don't know from the provided documents."

Context:
{context}

Question: {question}

Answer:""")

# ── Format retrieved docs ──────────────────────────────────────
def format_docs(docs):
    return "\\n\\n---\\n\\n".join(
        f"Source: {doc.metadata.get(\'source\', \'unknown\')}\\n{doc.page_content}"
        for doc in docs
    )

# ── RAG chain (LCEL) ───────────────────────────────────────────
# INTERVIEW: RunnablePassthrough passes question through unchanged
rag_chain = (
    {"context": retriever | format_docs,
     "question": RunnablePassthrough()}
    | rag_prompt
    | ChatOpenAI(model="gpt-4o-mini")
    | StrOutputParser()
)

answer = rag_chain.invoke("What is Python used for?")

# ── With sources ───────────────────────────────────────────────
from langchain_core.runnables import RunnableParallel

rag_chain_with_sources = RunnableParallel(
    answer   = rag_chain,
    contexts = retriever,   # keep raw docs for citation
)
result = rag_chain_with_sources.invoke("What is FastAPI?")
print(result["answer"])
for doc in result["contexts"]:
    print(f"  Source: {doc.metadata[\'source\']}")
'''
print(RAG_CHAIN_CODE[:700])


def mock_rag_answer(query: str, retrieved_docs: List[Document]) -> str:
    """Mock RAG response demonstrating the concept."""
    context = "\n".join(f"- {doc.content}" for doc in retrieved_docs)
    return (
        f"[Mock RAG] Based on retrieved context:\n{context}\n\n"
        f"Answer to '{query}': Python is used for web development, "
        f"data science, and machine learning based on the retrieved documents."
    )


print("\n  Mock RAG demo:")
query = "What is Python used for?"
retrieved = store.mmr_search(query, k=3)
print(f"  Query: {query}")
print(f"  Retrieved {len(retrieved)} chunks:")
for doc in retrieved:
    print(f"    - {doc.content}")
print(f"\n  RAG Answer:")
print(f"  {mock_rag_answer(query, retrieved)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: HyDE — Hypothetical Document Embeddings
# INTERVIEW: Generate fake answer, embed it — better semantic match than query
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: HyDE (Hypothetical Document Embeddings)")
print("=" * 60)

HYDE_CODE = '''\
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

# ── INTERVIEW: HyDE steps ──────────────────────────────────────
# 1. Query: "What is Python's GIL?"
# 2. Generate hypothetical answer (without retrieval):
#    "The GIL is a mutex that prevents multiple threads..."
# 3. Embed the HYPOTHETICAL ANSWER (not the query)
# 4. Use that embedding for vector search
# WHY: Hypothetical answers are semantically closer to real docs!

hyde_prompt = ChatPromptTemplate.from_template(
    "Please write a paragraph that would directly answer the question below. "
    "Be specific and technical. Question: {question}"
)

# Generate hypothetical document
generate_hypothetical = hyde_prompt | ChatOpenAI(model="gpt-4o-mini") | StrOutputParser()

# HyDE retrieval: embed the generated answer, not the question
def hyde_retrieve(question: str, retriever, llm) -> list:
    # Step 1: generate a hypothetical answer
    hypothetical = generate_hypothetical.invoke({"question": question})
    # Step 2: retrieve using hypothetical answer as query
    results = retriever.invoke(hypothetical)
    return results

# Full HyDE chain
hyde_chain = (
    {"hypothetical": generate_hypothetical,
     "question": RunnableLambda(lambda x: x)}
    | RunnableLambda(lambda x: x["hypothetical"])  # use hypothetical for retrieval
    | retriever
)
'''
print(HYDE_CODE[:600])
print("\n  HyDE concept demo (mock):")
print("  Query:        'What web frameworks does Python have?'")
print("  Hypothetical: 'Python has several web frameworks. FastAPI provides")
print("                 fast async APIs. Django is a full-stack framework...'")
print("  → Embed HYPOTHETICAL TEXT → search with that vector")
print("  → Better match: doc about FastAPI ranked higher than with raw query")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Hybrid Search
# INTERVIEW: BM25 (keyword) + vector (semantic) = best of both worlds
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Hybrid Search (BM25 + Vector)")
print("=" * 60)

HYBRID_CODE = '''\
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS

# ── BM25 (keyword / sparse) ────────────────────────────────────
# INTERVIEW: BM25 = TF-IDF variant, good for exact keyword match
bm25_retriever = BM25Retriever.from_documents(chunks)
bm25_retriever.k = 4   # return top 4

# ── Dense (vector / semantic) ─────────────────────────────────
faiss_retriever = FAISS.from_documents(chunks, embeddings).as_retriever(
    search_kwargs={"k": 4}
)

# ── Ensemble = hybrid ─────────────────────────────────────────
# INTERVIEW: weights=[0.5, 0.5] = equal blend of BM25 + vector
# RRF (Reciprocal Rank Fusion) merges the ranked lists
hybrid_retriever = EnsembleRetriever(
    retrievers = [bm25_retriever, faiss_retriever],
    weights    = [0.5, 0.5],
)
results = hybrid_retriever.invoke("Python GIL threading")

# ── When to use hybrid ─────────────────────────────────────────
# BM25 alone: "list all functions in module X" (exact match)
# Vector alone: "explain the concept of X" (semantic)
# Hybrid: production RAG (best recall for both types)
'''
print(HYBRID_CODE[:600])


# Simple BM25 demo
def bm25_score(query: str, doc: str, corpus_size: int = 10, avg_doc_len: float = 20.0) -> float:
    """
    INTERVIEW: BM25 = probabilistic keyword match.
    k1=1.5, b=0.75 are standard params.
    Higher score = better keyword match.
    """
    k1, b = 1.5, 0.75
    query_terms  = query.lower().split()
    doc_terms    = doc.lower().split()
    doc_len      = len(doc_terms)
    score        = 0.0
    for term in query_terms:
        tf  = doc_terms.count(term)
        # Simplified IDF (real BM25 uses log((N-n+0.5)/(n+0.5)))
        idf = math.log(1 + corpus_size / (1 + sum(1 for d in [doc] if term in d.lower())))
        numerator   = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / avg_doc_len)
        score      += idf * numerator / denominator
    return score


print("\n  BM25 keyword scores for 'Python web framework':")
for doc_text in [d.content for d in store.docs]:
    score = bm25_score("Python web framework", doc_text, corpus_size=len(store.docs))
    print(f"  {score:.3f}  {doc_text}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: RAGAS Evaluation
# INTERVIEW: 4 metrics to evaluate RAG quality
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 7: RAGAS Evaluation Metrics")
print("=" * 60)

RAGAS_CODE = '''\
from ragas import evaluate
from ragas.metrics import (
    faithfulness,          # Is answer grounded in context?
    answer_relevancy,      # Does answer address the question?
    context_precision,     # Are retrieved contexts relevant?
    context_recall,        # Were all relevant contexts retrieved?
)
from datasets import Dataset

# ── Prepare evaluation dataset ────────────────────────────────
eval_data = {
    "question":         ["What is Python?", "What is FastAPI?"],
    "answer":           [
        "Python is a high-level programming language.",
        "FastAPI is a modern web framework for building APIs.",
    ],
    "contexts":         [
        ["Python is a high-level language..."],   # retrieved chunks
        ["FastAPI is built on Starlette..."],
    ],
    "ground_truth":     [
        "Python is a high-level interpreted language created by Guido van Rossum.",
        "FastAPI is a Python web framework based on OpenAPI.",
    ],
}

dataset = Dataset.from_dict(eval_data)
results = evaluate(dataset, metrics=[
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
])
print(results)
# → {"faithfulness": 0.95, "answer_relevancy": 0.88,
#    "context_precision": 0.82, "context_recall": 0.76}
'''
print(RAGAS_CODE[:600])

print("\n  RAGAS metrics explained:")
RAGAS_METRICS = {
    "faithfulness":       "Answer contains ONLY info from context (no hallucination). Target: >0.9",
    "answer_relevancy":   "Answer actually addresses the question. Target: >0.85",
    "context_precision":  "Retrieved chunks ARE relevant to question. Target: >0.8",
    "context_recall":     "Retrieved chunks COVER all needed info. Target: >0.75",
    "answer_correctness": "Answer matches ground truth (needs ground truth labels)",
}
for m, d in RAGAS_METRICS.items():
    print(f"  {m:<22}: {d}")


# Simple mock RAGAS-style evaluation
def evaluate_faithfulness(answer: str, contexts: List[str]) -> float:
    """
    INTERVIEW: Faithfulness = fraction of answer claims supported by context.
    Real RAGAS uses LLM to identify and verify claims.
    """
    answer_words = set(answer.lower().split())
    context_words = set(" ".join(contexts).lower().split())
    # simplified: word overlap
    overlap = len(answer_words & context_words)
    return min(1.0, overlap / max(len(answer_words), 1))


answer  = "Python is used for web development and machine learning"
contexts = ["Python is a high-level language", "Python supports web development and ML tasks"]
score   = evaluate_faithfulness(answer, contexts)
print(f"\n  Mock faithfulness score: {score:.2f}")


print("\n" + "=" * 60)
print("RAG INTERVIEW SUMMARY:")
print("  RAG = Retrieve relevant chunks → Augment prompt → Generate answer")
print("  Chunking: RecursiveCharacterTextSplitter(chunk_size=1000, overlap=200)")
print("  FAISS: in-process vector store, from_documents() to build")
print("  MMR: diverse retrieval (lambda_mult=0.5 balances relevance+diversity)")
print("  HyDE: embed hypothetical answer for better semantic match")
print("  Hybrid: BM25(keyword) + vector(semantic), merged with EnsembleRetriever")
print("  RAGAS: faithfulness, answer_relevancy, context_precision, context_recall")
print("=" * 60)
