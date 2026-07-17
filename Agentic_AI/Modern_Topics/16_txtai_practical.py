"""
16_txtai_practical.py
Txtai — all-in-one embeddings database + pipelines + workflows.

Deps (optional):
    pip install txtai

Run:  python 16_txtai_practical.py
"""

# ---------------------------------------------------------------------------
# 1) EMBEDDINGS DB — index + semantic search (+ SQL metadata filter)
# ---------------------------------------------------------------------------
def demo_embeddings():
    try:
        from txtai import Embeddings
    except ImportError:
        print("[txtai] not installed -> pip install txtai")
        return

    emb = Embeddings(path="sentence-transformers/all-MiniLM-L6-v2", content=True)
    emb.index([
        {"id": 0, "text": "Cassandra scales horizontally", "topic": "db"},
        {"id": 1, "text": "Docling parses PDFs into markdown", "topic": "extract"},
        {"id": 2, "text": "Giskard red-teams LLM apps", "topic": "eval"},
    ])

    print("[txtai] pure semantic:")
    print(" ", emb.search("how to read a PDF", 1))

    # Hybrid semantic + SQL metadata filter in ONE query:
    print("[txtai] semantic + SQL WHERE:")
    print(" ", emb.search("scaling databases where topic = 'db'", 1))


# ---------------------------------------------------------------------------
# 2) PIPELINE — summarization (ready ML task, no wiring)
# ---------------------------------------------------------------------------
def demo_pipeline():
    try:
        from txtai.pipeline import Summary
    except ImportError:
        print("[txtai] not installed -> pip install txtai")
        return
    text = ("Data extraction is RAG's step zero. Retrieval quality is capped by "
            "parse quality. Docling handles tables locally; LlamaParse handles the "
            "nastiest PDFs via a managed vision model.")
    print("[txtai] summary:", Summary()(text, maxlength=30))


# ---------------------------------------------------------------------------
# 3) WORKFLOW — chain pipelines declaratively
# ---------------------------------------------------------------------------
def demo_workflow():
    try:
        from txtai.pipeline import Translation
        from txtai.workflow import Workflow, Task
    except ImportError:
        print("[txtai] not installed -> pip install txtai")
        return
    translate = Translation()
    workflow = Workflow([Task(lambda x: [translate(t, "hi") for t in x])])
    print("[txtai] workflow (en->hi):", list(workflow(["Vector search is fast"])))


if __name__ == "__main__":
    print("=" * 60); demo_embeddings()
    print("=" * 60); demo_pipeline()
    print("=" * 60); demo_workflow()
