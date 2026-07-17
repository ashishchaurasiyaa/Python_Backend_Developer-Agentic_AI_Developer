"""
20_opensearch_vector_practical.py
OpenSearch k-NN vector search + hybrid (BM25 + dense).

Deps (optional):
    pip install opensearch-py sentence-transformers

Needs a running OpenSearch (docker):
    docker run -p 9200:9200 -e "discovery.type=single-node" \
      -e "DISABLE_SECURITY_PLUGIN=true" opensearchproject/opensearch:latest

Guards gracefully if unavailable.
"""

INDEX = "rag_docs"


def _client():
    from opensearchpy import OpenSearch
    return OpenSearch(hosts=[{"host": "localhost", "port": 9200}],
                      use_ssl=False, verify_certs=False)


def demo_knn():
    try:
        from opensearchpy import OpenSearch  # noqa: F401
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[opensearch] pip install opensearch-py sentence-transformers")
        return
    try:
        client = _client()
        client.info()
    except Exception as e:
        print("[opensearch] no reachable cluster on :9200 ->", e)
        return

    model = SentenceTransformer("all-MiniLM-L6-v2")
    dim = model.get_sentence_embedding_dimension()

    # 1) Create a k-NN enabled index
    if client.indices.exists(INDEX):
        client.indices.delete(INDEX)
    client.indices.create(INDEX, body={
        "settings": {"index.knn": True},
        "mappings": {"properties": {
            "text": {"type": "text"},                       # BM25
            "embedding": {"type": "knn_vector", "dimension": dim,
                          "method": {"name": "hnsw", "engine": "lucene",
                                     "space_type": "cosinesimil"}},
        }},
    })

    # 2) Index docs with embeddings
    docs = ["OpenSearch does BM25 and kNN together",
            "Milvus scales vectors to billions",
            "Docling parses PDF tables"]
    for i, t in enumerate(docs):
        client.index(INDEX, id=str(i),
                     body={"text": t, "embedding": model.encode(t).tolist()},
                     refresh=True)

    # 3) Pure kNN query
    qv = model.encode("keyword plus semantic search").tolist()
    res = client.search(INDEX, body={"size": 1,
        "query": {"knn": {"embedding": {"vector": qv, "k": 1}}}})
    print("[opensearch] kNN top hit:", res["hits"]["hits"][0]["_source"]["text"])

    # 4) Hybrid-style (bool: BM25 should + kNN should)
    res2 = client.search(INDEX, body={"size": 1, "query": {"bool": {"should": [
        {"match": {"text": "semantic search"}},
        {"knn": {"embedding": {"vector": qv, "k": 3}}},
    ]}}})
    print("[opensearch] hybrid top hit:", res2["hits"]["hits"][0]["_source"]["text"])


if __name__ == "__main__":
    print("=" * 60); demo_knn()
