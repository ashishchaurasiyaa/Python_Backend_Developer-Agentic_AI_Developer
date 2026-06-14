"""
RAG 04: Vector Store (Chroma)
==============================

Topic: Section 6 from THEORY.md
Level: Intermediate

What you'll learn:
- Create Chroma vector store
- Add documents
- Similarity search
- Metadata filtering
- Score thresholds

Install:
uv add langchain-chroma langchain-google-genai
"""

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


# ===== SETUP =====

def get_embeddings():
    """Get embeddings model."""
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001")


def sample_documents():
    """Create sample documents."""
    return [
        Document(
            page_content="Python is a versatile programming language known for its readability",
            metadata={"source": "python_intro", "category": "language", "level": "basic"}
        ),
        Document(
            page_content="FastAPI is a modern, fast web framework for building APIs with Python",
            metadata={"source": "fastapi_docs", "category": "framework", "level": "intermediate"}
        ),
        Document(
            page_content="LangChain enables building applications with large language models",
            metadata={"source": "langchain_docs", "category": "framework", "level": "advanced"}
        ),
        Document(
            page_content="Docker containers package applications with their dependencies",
            metadata={"source": "docker_guide", "category": "devops", "level": "intermediate"}
        ),
        Document(
            page_content="PostgreSQL is a powerful open-source relational database",
            metadata={"source": "postgres_docs", "category": "database", "level": "intermediate"}
        ),
        Document(
            page_content="Redis is an in-memory data store used for caching",
            metadata={"source": "redis_docs", "category": "database", "level": "intermediate"}
        ),
        Document(
            page_content="React is a JavaScript library for building user interfaces",
            metadata={"source": "react_docs", "category": "frontend", "level": "intermediate"}
        ),
        Document(
            page_content="MongoDB is a NoSQL document database for flexible data storage",
            metadata={"source": "mongo_docs", "category": "database", "level": "intermediate"}
        ),
    ]


# ===== BASIC: Create Vector Store =====

def basic_vector_store_demo():
    """Create vector store and add documents."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Create Vector Store")
    print("=" * 70)

    docs = sample_documents()
    embeddings = get_embeddings()

    # Create from documents
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory="./chroma_db_demo"  # Saves to disk
    )

    print(f"\n✅ Vector store created!")
    print(f"📚 Documents stored: {len(docs)}")
    print(f"💾 Persisted to: ./chroma_db_demo")

    return vector_store


# ===== INTERMEDIATE: Similarity Search =====

def similarity_search_demo(vector_store):
    """Search for similar documents."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Similarity Search")
    print("=" * 70)

    queries = [
        "What is Python?",
        "Web framework for APIs",
        "Database for caching",
        "Frontend framework",
    ]

    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        print("-" * 70)

        # Top 2 most similar
        results = vector_store.similarity_search(query, k=2)

        for i, doc in enumerate(results, 1):
            print(f"\n  Result {i}:")
            print(f"    Content: {doc.page_content}")
            print(f"    Source: {doc.metadata['source']}")


# ===== INTERMEDIATE: Search with Scores =====

def search_with_scores_demo(vector_store):
    """Search and see similarity scores."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Search with Scores")
    print("=" * 70)

    query = "Python web framework"

    print(f"\n🔍 Query: '{query}'")
    print("(Lower score = more similar)\n")

    results = vector_store.similarity_search_with_score(query, k=3)

    for i, (doc, score) in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  Score: {score:.4f}")
        print(f"  Content: {doc.page_content}")
        print(f"  Category: {doc.metadata.get('category')}")
        print()


# ===== ADVANCED: Metadata Filtering =====

def metadata_filter_demo(vector_store):
    """Filter results by metadata."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Metadata Filtering")
    print("=" * 70)

    query = "data storage"

    # Filter 1: Only databases
    print(f"\n🔍 Query: '{query}'")
    print(f"📋 Filter: category = 'database'")
    print("-" * 70)

    results = vector_store.similarity_search(
        query,
        k=5,
        filter={"category": "database"}
    )

    for i, doc in enumerate(results, 1):
        print(f"\n{i}. {doc.page_content}")
        print(f"   Source: {doc.metadata['source']}")

    # Filter 2: Only intermediate level
    print(f"\n\n📋 Filter: level = 'intermediate'")
    print("-" * 70)

    results = vector_store.similarity_search(
        "framework",
        k=3,
        filter={"level": "intermediate"}
    )

    for i, doc in enumerate(results, 1):
        print(f"\n{i}. {doc.page_content}")
        print(f"   Level: {doc.metadata['level']}")


# ===== ADVANCED: Add New Documents =====

def add_documents_demo(vector_store):
    """Add new documents to existing store."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Add New Documents")
    print("=" * 70)

    new_docs = [
        Document(
            page_content="Kubernetes is a container orchestration platform",
            metadata={"source": "k8s_docs", "category": "devops", "level": "advanced"}
        ),
        Document(
            page_content="GraphQL is a query language for APIs",
            metadata={"source": "graphql_docs", "category": "api", "level": "intermediate"}
        ),
    ]

    # Add new documents
    ids = vector_store.add_documents(new_docs)

    print(f"\n✅ Added {len(new_docs)} new documents")
    print(f"📝 IDs: {ids[:2]}...")

    # Now search includes new docs
    print(f"\n🔍 Searching for 'container orchestration':")
    results = vector_store.similarity_search("container orchestration", k=2)
    for doc in results:
        print(f"  - {doc.page_content}")


# ===== ADVANCED: Load Persistent Store =====

def load_persistent_store():
    """Load previously saved vector store."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Load Persistent Vector Store")
    print("=" * 70)

    embeddings = get_embeddings()

    # Load from disk (no need to re-embed!)
    vector_store = Chroma(
        collection_name="langchain",
        embedding_function=embeddings,
        persist_directory="./chroma_db_demo"
    )

    print(f"\n✅ Loaded vector store from disk")

    # Use it
    results = vector_store.similarity_search("Python framework", k=2)
    print(f"\nFound {len(results)} results")


def main():
    """Run all vector store examples."""
    print("=" * 70)
    print("VECTOR STORE PRACTICE (Chroma)")
    print("=" * 70)

    # Basic
    vector_store = basic_vector_store_demo()

    # Intermediate
    similarity_search_demo(vector_store)
    search_with_scores_demo(vector_store)

    # Advanced
    metadata_filter_demo(vector_store)
    add_documents_demo(vector_store)
    # load_persistent_store()  # Run after first execution


if __name__ == "__main__":
    main()
