"""
RAG 02: Text Splitters
=======================

Topic: Section 4 from THEORY.md
Level: Basic → Intermediate

What you'll learn:
- RecursiveCharacterTextSplitter
- chunk_size and chunk_overlap
- Different splitter types
- Best practices

Install:
uv add langchain-text-splitters
"""

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter,
)
from langchain_core.documents import Document


# ===== BASIC: Recursive Character Splitter =====

def basic_recursive_splitter():
    """Most commonly used splitter."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Recursive Character Splitter")
    print("=" * 70)

    text = """
    LangChain is a powerful framework for building AI applications.
    It provides tools to chain together prompts, models, and outputs.

    RAG (Retrieval Augmented Generation) is a technique that:
    1. Retrieves relevant information from a knowledge base
    2. Augments the LLM context with this information
    3. Generates accurate answers based on retrieved data

    Vector databases store embeddings of text.
    Embeddings are numerical representations.
    Similar texts have similar embeddings.
    """ * 5  # Make it longer

    # Create splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,      # Each chunk = 500 chars
        chunk_overlap=50,    # 50 chars overlap
        add_start_index=True
    )

    # Split into Documents
    doc = Document(page_content=text)
    chunks = splitter.split_documents([doc])

    print(f"\n📊 Statistics:")
    print(f"  Original text: {len(text)} characters")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  Avg chunk size: {sum(len(c.page_content) for c in chunks) // len(chunks)} chars")

    print(f"\n📝 First 2 chunks:")
    for i, chunk in enumerate(chunks[:2], 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Length: {len(chunk.page_content)}")
        print(f"Start index: {chunk.metadata.get('start_index')}")
        print(f"Content: {chunk.page_content[:150]}...")


# ===== INTERMEDIATE: Different Chunk Sizes =====

def compare_chunk_sizes():
    """Compare different chunk sizes."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Compare Different Chunk Sizes")
    print("=" * 70)

    text = "Python is great. " * 200  # Long text

    sizes = [200, 500, 1000, 2000]

    for size in sizes:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=int(size * 0.2),  # 20% overlap
        )

        chunks = splitter.split_text(text)
        avg_chunk = sum(len(c) for c in chunks) // len(chunks)

        print(f"\nChunk size {size}:")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Average chunk: {avg_chunk} chars")


# ===== INTERMEDIATE: Overlap Importance =====

def overlap_importance():
    """Show why overlap matters."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Why Overlap Matters")
    print("=" * 70)

    text = "Ashish is a backend developer with 4 years experience in Python and FastAPI"

    # Without overlap
    splitter_no_overlap = RecursiveCharacterTextSplitter(
        chunk_size=40,
        chunk_overlap=0,
    )
    chunks_no = splitter_no_overlap.split_text(text)

    print("\n❌ WITHOUT overlap (context may break):")
    for i, chunk in enumerate(chunks_no, 1):
        print(f"  Chunk {i}: '{chunk}'")

    # With overlap
    splitter_overlap = RecursiveCharacterTextSplitter(
        chunk_size=40,
        chunk_overlap=15,
    )
    chunks_with = splitter_overlap.split_text(text)

    print("\n✅ WITH overlap (context preserved):")
    for i, chunk in enumerate(chunks_with, 1):
        print(f"  Chunk {i}: '{chunk}'")


# ===== ADVANCED: Character Splitter (Simple) =====

def character_splitter_demo():
    """Simple character splitter."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Character Splitter (split by separator)")
    print("=" * 70)

    text = """First paragraph here.

Second paragraph follows.

Third paragraph is here.

Final paragraph."""

    splitter = CharacterTextSplitter(
        separator="\n\n",     # Split by paragraphs
        chunk_size=100,
        chunk_overlap=20,
    )

    chunks = splitter.split_text(text)

    print(f"\n📊 Created {len(chunks)} chunks (split by paragraphs)")
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}: '{chunk}'")


# ===== ADVANCED: Best Practices =====

def best_practices_demo():
    """Show recommended settings."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Best Practices")
    print("=" * 70)

    long_text = """
    Backend Developer Skills:
    Python is a must-have language. FastAPI is the modern web framework.
    PostgreSQL handles structured data. Redis is great for caching.
    Docker containerizes applications. AWS provides cloud infrastructure.
    """ * 10

    # Recommended settings
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,       # Good balance
        chunk_overlap=200,     # 20% overlap
        add_start_index=True,
        length_function=len,   # Use character length
    )

    chunks = splitter.split_text(long_text)

    print(f"\n✅ Recommended settings used:")
    print(f"  chunk_size: 1000 (balanced)")
    print(f"  chunk_overlap: 200 (20%)")
    print(f"  Total chunks: {len(chunks)}")

    print(f"\n📋 First chunk preview:")
    print(f"  {chunks[0][:200]}...")


def main():
    """Run all splitter examples."""
    basic_recursive_splitter()
    compare_chunk_sizes()
    overlap_importance()
    character_splitter_demo()
    best_practices_demo()


if __name__ == "__main__":
    main()
