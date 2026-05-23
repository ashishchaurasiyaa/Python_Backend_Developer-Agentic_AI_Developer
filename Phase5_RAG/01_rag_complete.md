# RAG (Retrieval-Augmented Generation) — Chunking, Embeddings, Hybrid Search, Reranking, RAGAS

## Quick Concepts
- **RAG** = LLM ko external knowledge se augment karo — hallucination reduce hoti hai
- **Chunking** = documents ko meaningful pieces mein todna — size aur overlap matter karte hain
- **Hybrid Search** = dense (semantic) + sparse (keyword BM25) — best of both worlds
- **Reranking** = initial retrieval results ko better order mein lagana — CrossEncoder use karo
- **RAGAS** = RAG pipeline ka evaluation framework — faithfulness, relevancy, context recall

---

## Interview Questions & Answers

### Q1: RAG pipeline end-to-end kaise banate hain?
**Answer:**
```python
# pip install langchain langchain-anthropic langchain-openai faiss-cpu ragas

from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# ===== INDEXING PIPELINE =====

# 1. Load documents
loader = PyPDFLoader("knowledge_base.pdf")
documents = loader.load()

# 2. Split into chunks
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "],
)
chunks = splitter.split_documents(documents)
print(f"Total chunks: {len(chunks)}")

# 3. Create embeddings + vector store
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = FAISS.from_documents(chunks, embeddings)
vectorstore.save_local("./vectorstore")

# ===== RETRIEVAL + GENERATION PIPELINE =====

# Load vectorstore
vectorstore = FAISS.load_local("./vectorstore", embeddings,
                                allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Model
model = ChatAnthropic(model="claude-sonnet-4-6")

# RAG prompt
rag_prompt = ChatPromptTemplate.from_template("""
You are an AI assistant. Answer the question based ONLY on the context below.
If the answer isn't in the context, say "I don't have that information."

Context:
{context}

Question: {question}

Answer:""")

def format_docs(docs):
    return "\n\n---\n\n".join(
        f"[Source: {doc.metadata.get('source', 'unknown')}, Page: {doc.metadata.get('page', '?')}]\n{doc.page_content}"
        for doc in docs
    )

# Complete RAG chain
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | model
    | StrOutputParser()
)

# Query
answer = rag_chain.invoke("What is the main purpose of this document?")
print(answer)

# With source tracking
from langchain_core.runnables import RunnableParallel

rag_with_sources = RunnableParallel(
    answer=rag_chain,
    sources=lambda q: [
        {"content": doc.page_content[:200], "source": doc.metadata.get("source")}
        for doc in retriever.invoke(q)
    ]
)

result = rag_with_sources.invoke("What are the key findings?")
print(f"Answer: {result['answer']}")
print(f"\nSources: {result['sources']}")
```

---

### Q2: Chunking strategies — kaunsi strategy kab use karo?
**Answer:**
```python
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    MarkdownHeaderTextSplitter,
    HTMLHeaderTextSplitter,
    SentenceTransformersTokenTextSplitter,
)
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

# ===== STRATEGY 1: Recursive Character (DEFAULT — general purpose) =====
recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
)

# ===== STRATEGY 2: Markdown-aware (for documentation) =====
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "H1"),
        ("##", "H2"),
        ("###", "H3"),
    ],
    strip_headers=False,
    return_each_line=False,
)

md_chunks = md_splitter.split_text("""
# Chapter 1: Introduction
This is intro content.

## 1.1 Background
Background content here.

### 1.1.1 History
Historical details.
""")
# Each chunk has metadata: {"H1": "Chapter 1", "H2": "1.1 Background", "H3": "1.1.1 History"}

# ===== STRATEGY 3: Semantic Chunking (BEST QUALITY — expensive) =====
semantic_splitter = SemanticChunker(
    embeddings=OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile",   # percentile, standard_deviation, interquartile
    breakpoint_threshold_amount=95,           # split where semantic similarity drops
)
# Splits based on semantic meaning — similar content stays together

# ===== STRATEGY 4: Token-based (LLM context window respect) =====
token_splitter = TokenTextSplitter(
    chunk_size=512,     # in tokens, not characters
    chunk_overlap=50,
)

# ===== STRATEGY 5: Parent Document Retriever (ADVANCED) =====
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore
from langchain_community.vectorstores import Chroma

# Child splitter (small chunks for retrieval)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
# Parent splitter (larger chunks for context)
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)

vectorstore = Chroma(embedding_function=OpenAIEmbeddings(), collection_name="small_chunks")
store = InMemoryStore()  # stores parent docs

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=store,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)

# WHY: Small chunks → precise retrieval; Large parents → full context for LLM

# ===== CHUNK SIZE SELECTION GUIDE =====
# chunk_size=200-400:   Fine-grained — Q&A, fact extraction
# chunk_size=500-1000:  Balanced — general RAG (RECOMMENDED DEFAULT)
# chunk_size=1500-2000: Broad context — summaries, analysis
# overlap=10-20%:       Prevents context loss at boundaries
```

---

### Q3: Hybrid Search — dense + sparse kaise combine karte hain?
**Answer:**
```python
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# ===== BM25 (Sparse/Keyword retrieval) =====
# pip install rank_bm25
bm25_retriever = BM25Retriever.from_documents(
    chunks,
    k=5,
)

# ===== FAISS (Dense/Semantic retrieval) =====
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_documents(chunks, embeddings)
dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# ===== Ensemble (Hybrid) =====
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],  # 40% BM25, 60% dense
)

# Hybrid search result
hybrid_docs = ensemble_retriever.invoke("Python async programming")
print(f"Retrieved {len(hybrid_docs)} docs")

# ===== pgvector Hybrid Search (production PostgreSQL) =====
from sqlalchemy import text
import asyncpg
import numpy as np

async def hybrid_search_pgvector(
    query: str,
    query_embedding: list[float],
    limit: int = 5,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
) -> list[dict]:
    """
    Combines:
    - Dense: pgvector cosine similarity
    - Sparse: Full-text search (tsvector)
    Uses RRF (Reciprocal Rank Fusion) to combine scores
    """
    pool = await asyncpg.create_pool("postgresql://user:pass@localhost/db")

    async with pool.acquire() as conn:
        results = await conn.fetch("""
            WITH dense_results AS (
                SELECT id, content, metadata,
                       1 - (embedding <=> $1::vector) as dense_score,
                       ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as dense_rank
                FROM documents
                ORDER BY embedding <=> $1::vector
                LIMIT 20
            ),
            sparse_results AS (
                SELECT id, content, metadata,
                       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $2)) as sparse_score,
                       ROW_NUMBER() OVER (ORDER BY sparse_score DESC) as sparse_rank
                FROM documents
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $2)
                LIMIT 20
            ),
            rrf_scores AS (
                SELECT
                    COALESCE(d.id, s.id) as id,
                    COALESCE(d.content, s.content) as content,
                    COALESCE(d.metadata, s.metadata) as metadata,
                    COALESCE(1.0/(60 + d.dense_rank), 0) * $3 +
                    COALESCE(1.0/(60 + s.sparse_rank), 0) * $4 as rrf_score
                FROM dense_results d
                FULL OUTER JOIN sparse_results s ON d.id = s.id
            )
            SELECT * FROM rrf_scores
            ORDER BY rrf_score DESC
            LIMIT $5
        """, query_embedding, query, dense_weight, sparse_weight, limit)

    return [dict(r) for r in results]
```

---

### Q4: Reranking — retrieved docs ko better order mein kaise laate hain?
**Answer:**
```python
# pip install sentence-transformers cohere

# ===== CrossEncoder Reranking (Local) =====
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_documents(query: str, documents: list, top_k: int = 3) -> list:
    """
    CrossEncoder: query + doc pair ko TOGETHER score karta hai
    BiEncoder (embeddings): query aur doc ko SEPARATELY encode karta hai
    CrossEncoder more accurate but slower
    """
    if not documents:
        return documents

    pairs = [[query, doc.page_content] for doc in documents]
    scores = reranker.predict(pairs)

    # Score ke hisab se sort karo
    doc_score_pairs = list(zip(documents, scores))
    doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

    reranked_docs = [doc for doc, score in doc_score_pairs[:top_k]]
    print(f"Reranking scores: {[f'{s:.3f}' for _, s in doc_score_pairs[:top_k]]}")

    return reranked_docs

# ===== Cohere Reranking (Cloud API — best quality) =====
import cohere

co = cohere.Client("YOUR_API_KEY")

def cohere_rerank(query: str, documents: list, top_k: int = 3) -> list:
    texts = [doc.page_content for doc in documents]

    results = co.rerank(
        query=query,
        documents=texts,
        top_n=top_k,
        model="rerank-english-v3.0",
    )

    reranked = [documents[r.index] for r in results.results]
    return reranked

# ===== Full RAG pipeline with reranking =====
from langchain_core.runnables import RunnableLambda

def create_rag_with_reranking(vectorstore, model):
    # Step 1: Retrieve many docs (k=10)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

    # Step 2: Rerank to top 3
    def retrieve_and_rerank(question: str):
        docs = retriever.invoke(question)
        return rerank_documents(question, docs, top_k=3)

    rag_chain = (
        {
            "context": RunnableLambda(retrieve_and_rerank) | format_docs,
            "question": RunnablePassthrough()
        }
        | rag_prompt
        | model
        | StrOutputParser()
    )
    return rag_chain
```

---

### Q5: RAGAS — RAG pipeline evaluate kaise karte hain?
**Answer:**
```python
# pip install ragas datasets

from ragas import evaluate
from ragas.metrics import (
    faithfulness,          # Answer context se supported hai?
    answer_relevancy,      # Answer question ke liye relevant hai?
    context_recall,        # All needed info context mein hai?
    context_precision,     # Retrieved docs useful hain?
    answer_correctness,    # Ground truth se match?
)
from datasets import Dataset

# ===== Test dataset prepare karo =====
test_data = {
    "question": [
        "What is FastAPI?",
        "How does async work in Python?",
        "What is PostgreSQL?",
    ],
    "answer": [           # LLM ka answer
        "FastAPI is a modern web framework...",
        "Async in Python uses event loop...",
        "PostgreSQL is an open-source relational database...",
    ],
    "contexts": [         # Retrieved chunks (list of lists)
        ["FastAPI is a Python framework for building APIs...", "FastAPI supports async..."],
        ["Python's asyncio module...", "Coroutines with async/await..."],
        ["PostgreSQL is a powerful RDBMS...", "PostgreSQL supports ACID..."],
    ],
    "ground_truth": [     # Expected correct answers (for some metrics)
        "FastAPI is a modern, fast web framework for building APIs with Python.",
        "Python async uses coroutines and event loop for non-blocking IO.",
        "PostgreSQL is an open-source ACID-compliant relational database.",
    ],
}

dataset = Dataset.from_dict(test_data)

# ===== Evaluate =====
results = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    ]
)

print(results)
# Output:
# {'faithfulness': 0.85, 'answer_relevancy': 0.92, 'context_recall': 0.78, 'context_precision': 0.88}

# ===== Metrics explanation =====
# faithfulness:         0-1, answer context se support hota hai? (hallucination detect)
# answer_relevancy:     0-1, answer question ke liye relevant?
# context_recall:       0-1, ground truth ke liye needed info context mein hai?
# context_precision:    0-1, retrieved docs kitne useful hain? (noise measure)
# answer_correctness:   0-1, ground truth se match?

# Target scores for production:
# faithfulness > 0.8   (low = hallucination)
# answer_relevancy > 0.85
# context_precision > 0.7

# ===== End-to-End eval loop =====
def evaluate_rag_pipeline(rag_chain, retriever, test_questions, ground_truths):
    questions, answers, contexts = [], [], []

    for q, gt in zip(test_questions, ground_truths):
        ans = rag_chain.invoke(q)
        ctx = [doc.page_content for doc in retriever.invoke(q)]

        questions.append(q)
        answers.append(ans)
        contexts.append(ctx)

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    return evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_recall])
```

---

### Q6: Advanced RAG patterns — kaunse common hain interview mein?
**Answer:**
```
COMMON INTERVIEW QUESTIONS:

Q: RAG mein hallucination kaise reduce karte hain?
A:
  1. faithfulness score RAGAS se monitor karo
  2. Strict prompt: "Answer ONLY from context, nothing else"
  3. Reranking se better context provide karo
  4. chunk_overlap badhao — context loss prevent
  5. Multiple retrieval strategies (hybrid search)

Q: RAG vs Fine-tuning — kab kya?
A:
  RAG:        Dynamic knowledge, frequently changing data, need citations
  Fine-tuning: Style/tone change, domain-specific language patterns, static knowledge

Q: Context window overflow kaise handle karo?
A:
  1. Reranking se top-3 docs rakhte hain (top-10 retrieve, top-3 send)
  2. Summarize retrieved docs before sending
  3. Parent-child chunking — small retrieve, large context
  4. Map-reduce: chunks separately process karo, then combine

Q: Metadata filtering kaise karte hain?
A:
  retriever = vectorstore.as_retriever(
      search_kwargs={
          "k": 5,
          "filter": {"source": "annual_report_2025.pdf", "section": "financials"}
      }
  )
  # Only relevant documents retrieve hote hain

Q: Multi-hop RAG kya hai?
A:
  Complex questions jo multiple retrieval steps chahte hain.
  e.g., "Which author's book was published before 2000 and won a Booker Prize?"
  Step 1: Find Booker Prize winners
  Step 2: From those, filter published before 2000
  LangGraph mein implement karo with iterative retrieval nodes
```
