"""
Project 2: RAG Document Q&A System
====================================
Spec: ../02_project2_rag_document_qa.md

Yeh skeleton hai — full implementation ke liye spec padho aur milestones follow karo.
Bina API key ke bhi ye file run hogi (placeholder mode).
"""

import os
import sys

# ---------------------------------------------------------------------------
# MILESTONE 1 — TODO: Multi-format document loaders
# ---------------------------------------------------------------------------
# from pathlib import Path
# from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
#
# LOADERS = {
#     ".pdf":  PyPDFLoader,
#     # ".docx": UnstructuredWordDocumentLoader,
#     # ".xlsx": UnstructuredExcelLoader,
# }
#
# async def load_document(source: str):
#     if source.startswith("http"):
#         return WebBaseLoader(source).load()
#     ext = Path(source).suffix.lower()
#     return LOADERS[ext](source).load()

# ---------------------------------------------------------------------------
# MILESTONE 2 — TODO: Chunking strategies
# ---------------------------------------------------------------------------
# from langchain.text_splitter import RecursiveCharacterTextSplitter
#
# def chunk_documents(docs, strategy="recursive"):
#     if strategy == "recursive":
#         splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
#     # elif strategy == "semantic":
#     #     from langchain_experimental.text_splitter import SemanticChunker
#     #     splitter = SemanticChunker(embeddings)
#     return splitter.split_documents(docs)

# ---------------------------------------------------------------------------
# MILESTONE 3 — TODO: Hybrid search (BM25 + pgvector + RRF fusion)
# ---------------------------------------------------------------------------
# async def hybrid_search(query: str, user_id: str, db, top_k=10, alpha=0.5):
#     """
#     BM25 (keyword) + vector (semantic) dono se search karo.
#     RRF (Reciprocal Rank Fusion) se merge karo.
#     alpha=0: pure BM25,  alpha=1: pure vector
#     """
#     # TODO: vector_results from pgvector
#     # TODO: bm25_results from PostgreSQL full-text search
#     # TODO: RRF scoring aur merge
#     return []

# ---------------------------------------------------------------------------
# MILESTONE 4 — TODO: Reranking (local CrossEncoder ya Cohere)
# ---------------------------------------------------------------------------
# from sentence_transformers import CrossEncoder
#
# _model = None
# def get_cross_encoder():
#     global _model
#     if _model is None:
#         _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
#     return _model
#
# def rerank_local(query: str, documents: list, top_n=3):
#     model = get_cross_encoder()
#     pairs = [(query, d["content"]) for d in documents]
#     scores = model.predict(pairs)
#     for d, s in zip(documents, scores):
#         d["rerank_score"] = float(s)
#     return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)[:top_n]

# ---------------------------------------------------------------------------
# MILESTONE 5 — TODO: FastAPI endpoints (/upload, /query, /feedback)
# ---------------------------------------------------------------------------
# from fastapi import FastAPI, UploadFile
# app = FastAPI(title="RAG Document Q&A")
#
# @app.post("/upload")
# async def upload_document(file: UploadFile):
#     # TODO: save -> load -> chunk -> embed -> store in pgvector
#     return {"chunks_stored": 0}
#
# @app.post("/query")
# async def query(request: QueryRequest):
#     # TODO: hybrid_search -> rerank -> generate_with_cost_tracking
#     return {"answer": "", "sources": [], "cost_usd": 0.0}

# ---------------------------------------------------------------------------
# MILESTONE 6 — TODO: RAGAS evaluation
# ---------------------------------------------------------------------------
# from ragas import evaluate
# from ragas.metrics import faithfulness, answer_relevancy
#
# async def evaluate_rag_quality(questions, answers, contexts, ground_truths):
#     # TODO: Dataset banao, evaluate() call karo, Langfuse mein log karo
#     return {}

# ---------------------------------------------------------------------------
# MILESTONE 7 — TODO: Cost tracking per query
# ---------------------------------------------------------------------------
# async def generate_with_cost_tracking(query, context, model, db, user_id):
#     """Har query ka cost calculate karo aur DB mein log karo."""
#     # CLAUDE_PRICING = {"claude-sonnet-4-6": {"input": 3.00, "output": 15.00}}
#     # cost = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
#     return "", 0.0

# ---------------------------------------------------------------------------
# Client helper — API key optional, placeholder mode graceful
# ---------------------------------------------------------------------------

def get_client():
    """
    Anthropic client return karta hai.
    ANTHROPIC_API_KEY nahi hai toh placeholder — gracefully handle hota hai.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or "placeholder"
    if api_key == "placeholder":
        print("[INFO] ANTHROPIC_API_KEY nahi mili — placeholder mode chal raha hai.")
        return None
    try:
        import anthropic  # noqa: PLC0415
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("[WARN] anthropic package install nahi hai. `pip install anthropic`")
        return None


def demo_run(client):
    """Quick smoke-test: pipeline ka flow explain karo."""
    if client is None:
        print("[DEMO] Client nahi hai — sirf structure check kar rahe hain.")
        print("[DEMO] RAG Pipeline flow:")
        print("  PDF/DOCX/URL  -->  Chunker  -->  Embedder  -->  pgvector")
        print("  Query  -->  BM25 + Vector  -->  RRF  -->  Rerank  -->  LLM  -->  Answer")
        print("[DEMO] Steps:")
        print("  1. pip install -r requirements.txt")
        print("  2. export ANTHROPIC_API_KEY=sk-ant-...")
        print("  3. Milestones implement karo (README.md dekho)")
        return

    # TODO: Yahan actual RAG pipeline test karo
    print("[DEMO] Client ready — ab upload + query endpoints banana shuru karo (Milestone 5).")


if __name__ == "__main__":
    print("=" * 60)
    print("Project 2: RAG Document Q&A — Skeleton")
    print("Spec: ../02_project2_rag_document_qa.md")
    print("=" * 60)

    client = get_client()
    demo_run(client)

    print("\n[OK] Skeleton successfully run hua. Ab milestones implement karo!")
    sys.exit(0)
