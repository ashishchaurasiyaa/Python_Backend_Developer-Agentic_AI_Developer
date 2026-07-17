"""
19_milvus_vector_db_practical.py
Milvus — using Milvus Lite (no server needed) for a local vector search demo.

Deps (optional):
    pip install pymilvus sentence-transformers

Milvus Lite runs in-process from a local file — no docker/k8s needed.
Guards gracefully if deps missing.
"""

def demo_milvus_lite():
    try:
        from pymilvus import MilvusClient
    except ImportError:
        print("[milvus] pip install pymilvus  (Milvus Lite, no server needed)")
        return

    # Local file-backed Milvus Lite instance:
    client = MilvusClient("milvus_demo.db")

    if client.has_collection("docs"):
        client.drop_collection("docs")
    client.create_collection(collection_name="docs", dimension=4)

    # (In real use, dimension = your embedding size; vectors from an embedder.)
    rows = [
        {"id": 1, "vector": [0.1, 0.2, 0.3, 0.4], "text": "Milvus scales to billions"},
        {"id": 2, "vector": [0.9, 0.8, 0.7, 0.6], "text": "Chroma is great for dev"},
    ]
    client.insert(collection_name="docs", data=rows)

    res = client.search(
        collection_name="docs",
        data=[[0.1, 0.2, 0.3, 0.41]],
        limit=1,
        output_fields=["text"],
    )
    print("[milvus] nearest:", res[0][0]["entity"]["text"], "dist:", res[0][0]["distance"])


def demo_with_real_embeddings():
    try:
        from pymilvus import MilvusClient
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[milvus+sbert] pip install pymilvus sentence-transformers")
        return
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = ["Milvus disaggregates compute and storage",
             "Docling parses PDF tables",
             "Giskard red-teams LLMs"]
    vecs = model.encode(texts).tolist()

    client = MilvusClient("milvus_sbert.db")
    if client.has_collection("kb"):
        client.drop_collection("kb")
    client.create_collection("kb", dimension=len(vecs[0]))
    client.insert("kb", [{"id": i, "vector": v, "text": t}
                         for i, (v, t) in enumerate(zip(vecs, texts))])

    q = model.encode(["how does milvus store data?"]).tolist()
    res = client.search("kb", data=q, limit=1, output_fields=["text"])
    print("[milvus+sbert] hit:", res[0][0]["entity"]["text"])


if __name__ == "__main__":
    print("=" * 60); demo_milvus_lite()
    print("=" * 60); demo_with_real_embeddings()
