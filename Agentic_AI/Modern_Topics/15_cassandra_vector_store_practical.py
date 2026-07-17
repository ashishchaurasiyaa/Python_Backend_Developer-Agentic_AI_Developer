"""
15_cassandra_vector_store_practical.py
Cassandra / Astra DB as a vector store.

Two ways shown:
  A) LangChain Cassandra vector store (easiest)
  B) Raw CQL via cassandra-driver (shows the ANN syntax)

Deps (optional):
    pip install "cassio>=0.1" langchain-community sentence-transformers cassandra-driver

Needs a running Cassandra 5+ / Astra DB. Guards gracefully if unavailable.
"""

# ---------------------------------------------------------------------------
# A) LangChain vector store on Cassandra/Astra (drop-in like Chroma)
# ---------------------------------------------------------------------------
def demo_langchain_cassandra():
    import os
    try:
        import cassio
        from langchain_community.vectorstores import Cassandra
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except ImportError:
        print("[lc-cassandra] pip install cassio langchain-community sentence-transformers")
        return

    token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    db_id = os.getenv("ASTRA_DB_ID")
    if not (token and db_id):
        print("[lc-cassandra] set ASTRA_DB_APPLICATION_TOKEN + ASTRA_DB_ID to run")
        return

    cassio.init(token=token, database_id=db_id)
    emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    store = Cassandra(embedding=emb, table_name="rag_docs", session=None, keyspace=None)

    store.add_texts([
        "Cassandra scales horizontally and is masterless.",
        "Docling parses PDFs into structured markdown.",
    ])
    hits = store.similarity_search("how does cassandra scale?", k=1)
    print("[lc-cassandra] top hit:", hits[0].page_content if hits else None)


# ---------------------------------------------------------------------------
# B) Raw CQL — shows VECTOR column + ANN query directly
# ---------------------------------------------------------------------------
def demo_raw_cql():
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        print("[cql] pip install cassandra-driver (and run a local Cassandra 5+)")
        return
    try:
        cluster = Cluster(["127.0.0.1"])
        session = cluster.connect()
    except Exception as e:
        print("[cql] no reachable Cassandra:", e)
        return

    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS demo
        WITH replication = {'class':'SimpleStrategy','replication_factor':1}""")
    session.set_keyspace("demo")
    session.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            id int PRIMARY KEY, body text, embedding VECTOR<FLOAT, 3>)""")
    session.execute("CREATE CUSTOM INDEX IF NOT EXISTS ON docs(embedding) "
                    "USING 'StorageAttachedIndex'")

    session.execute("INSERT INTO docs (id, body, embedding) VALUES (1,'alpha',[0.1,0.2,0.3])")
    session.execute("INSERT INTO docs (id, body, embedding) VALUES (2,'beta', [0.9,0.8,0.7])")

    rows = session.execute(
        "SELECT id, body FROM docs ORDER BY embedding ANN OF [0.1,0.2,0.31] LIMIT 1")
    for r in rows:
        print("[cql] nearest:", r.id, r.body)


if __name__ == "__main__":
    print("=" * 60); demo_langchain_cassandra()
    print("=" * 60); demo_raw_cql()
