"""
RAG 03: Embeddings
===================

Topic: Section 5 from THEORY.md
Level: Basic → Intermediate

What you'll learn:
- Text to vector conversion
- Embedding similarity
- Different providers (Google, HuggingFace)
- embed_query vs embed_documents

Install:
uv add langchain-google-genai sentence-transformers langchain-huggingface
"""

import numpy as np
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


# ===== HELPER: Cosine Similarity =====

def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    v1 = np.array(v1)
    v2 = np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


# ===== BASIC: Single Text Embedding =====

def basic_embedding_demo():
    """Convert single text to vector."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Embedding (Single Text)")
    print("=" * 70)

    # Initialize Google embeddings (FREE)
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )

    text = "Python is a programming language"
    vector = embeddings.embed_query(text)

    print(f"\n📝 Text: '{text}'")
    print(f"🔢 Vector dimensions: {len(vector)}")
    print(f"🔍 First 10 numbers: {[round(v, 4) for v in vector[:10]]}")
    print(f"📊 Vector stats:")
    print(f"   Min: {min(vector):.4f}")
    print(f"   Max: {max(vector):.4f}")
    print(f"   Mean: {sum(vector)/len(vector):.4f}")


# ===== INTERMEDIATE: Multiple Texts (Batch) =====

def batch_embedding_demo():
    """Embed multiple texts at once."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Batch Embeddings")
    print("=" * 70)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )

    texts = [
        "Python is great for backend development",
        "FastAPI is a modern web framework",
        "React is a JavaScript library",
        "MongoDB is a NoSQL database",
    ]

    # Batch embed (faster than one-by-one)
    vectors = embeddings.embed_documents(texts)

    print(f"\n📦 Total texts: {len(texts)}")
    print(f"📊 Total vectors: {len(vectors)}")
    print(f"🔢 Each vector size: {len(vectors[0])}")

    print("\n📝 Texts and vector previews:")
    for i, (text, vector) in enumerate(zip(texts, vectors), 1):
        print(f"\n{i}. '{text}'")
        print(f"   Vector: {[round(v, 3) for v in vector[:5]]}...")


# ===== INTERMEDIATE: Similarity Calculation =====

def similarity_demo():
    """Calculate similarity between texts."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Text Similarity")
    print("=" * 70)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )

    # Test pairs (similar vs different)
    base_text = "Python programming"

    test_texts = [
        "Python coding",              # Very similar
        "Java development",            # Similar (programming)
        "JavaScript tutorial",         # Similar (programming)
        "Pizza recipe",                # Different
        "Cricket match score",         # Very different
    ]

    print(f"\n🎯 Base text: '{base_text}'")
    base_vector = embeddings.embed_query(base_text)

    print("\n📊 Similarity scores (higher = more similar):")
    print("-" * 70)

    for text in test_texts:
        text_vector = embeddings.embed_query(text)
        similarity = cosine_similarity(base_vector, text_vector)

        # Visual bar
        bar_length = int(similarity * 50)
        bar = "█" * bar_length + "░" * (50 - bar_length)

        print(f"\n'{text}'")
        print(f"Score: {similarity:.4f}")
        print(f"{bar}")


# ===== ADVANCED: Find Most Similar =====

def find_most_similar_demo():
    """Find most similar text from a list."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Find Most Similar (Search Pattern)")
    print("=" * 70)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )

    # Knowledge base
    knowledge = [
        "Python is great for data science and ML",
        "FastAPI helps build REST APIs quickly",
        "PostgreSQL is a powerful relational database",
        "Docker containerizes applications",
        "Kubernetes orchestrates containers",
        "React builds user interfaces",
        "MongoDB stores documents",
        "Redis is a fast in-memory cache",
    ]

    # Embed knowledge base
    print("\n📚 Embedding knowledge base...")
    knowledge_vectors = embeddings.embed_documents(knowledge)

    # User query
    query = "How to build APIs with Python?"

    print(f"\n❓ Query: '{query}'")
    query_vector = embeddings.embed_query(query)

    # Calculate similarities
    similarities = [
        (text, cosine_similarity(query_vector, vec))
        for text, vec in zip(knowledge, knowledge_vectors)
    ]

    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x[1], reverse=True)

    print("\n🏆 Top 3 most relevant:")
    for i, (text, score) in enumerate(similarities[:3], 1):
        print(f"\n{i}. {text}")
        print(f"   Score: {score:.4f}")


# ===== ADVANCED: Semantic Clustering =====

def semantic_clustering_demo():
    """Group similar texts together."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Semantic Clustering")
    print("=" * 70)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )

    # Mixed topics
    texts = [
        "Python programming language",
        "JavaScript for web development",
        "How to cook biryani",
        "Java enterprise applications",
        "Best biryani recipes",
        "C++ system programming",
        "Indian cuisine and dishes",
    ]

    # Embed all
    vectors = embeddings.embed_documents(texts)

    # Calculate all pairs similarity
    print(f"\n📊 Similarity Matrix ({len(texts)} texts):")
    print("-" * 70)

    for i, text1 in enumerate(texts):
        print(f"\n{i+1}. '{text1}'")
        similarities = []
        for j, text2 in enumerate(texts):
            if i != j:
                score = cosine_similarity(vectors[i], vectors[j])
                similarities.append((text2, score))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Show top 2 most similar
        for text2, score in similarities[:2]:
            print(f"   → '{text2}' (score: {score:.3f})")


def main():
    """Run all embedding examples."""
    print("=" * 70)
    print("EMBEDDINGS PRACTICE")
    print("=" * 70)

    basic_embedding_demo()
    batch_embedding_demo()
    similarity_demo()
    find_most_similar_demo()
    semantic_clustering_demo()


if __name__ == "__main__":
    main()
