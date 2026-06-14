"""
RAG 01: Document Loaders
=========================

Topic: Section 3 from THEORY.md
Level: Basic

What you'll learn:
- TextLoader, PyPDFLoader, WebBaseLoader
- Document object structure
- Metadata handling
- Batch loading

Install required packages:
uv add pypdf beautifulsoup4 langchain-community
"""

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    WebBaseLoader,
)
from langchain_core.documents import Document


# ===== BASIC: Text Loader =====

def load_text_file_demo():
    """Load a .txt file."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Text File Loader")
    print("=" * 70)

    # Create sample text file
    sample_path = "/tmp/sample.txt"
    with open(sample_path, "w") as f:
        f.write("""
Welcome to LangChain RAG Tutorial!

LangChain is a powerful framework for building AI applications.
It supports multiple LLM providers and provides tools for RAG.

RAG stands for Retrieval Augmented Generation.
It allows AI to use external knowledge bases.
        """)

    # Load the file
    loader = TextLoader(sample_path)
    docs = loader.load()

    print(f"\n✅ Loaded {len(docs)} document(s)")
    print(f"\n📝 Content:\n{docs[0].page_content}")
    print(f"\n📋 Metadata: {docs[0].metadata}")


# ===== INTERMEDIATE: Web Page Loader =====

def load_web_page_demo():
    """Load content from a web page."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Web Page Loader")
    print("=" * 70)

    url = "https://docs.langchain.com/oss/python/langchain/overview"

    try:
        loader = WebBaseLoader(url)
        docs = loader.load()

        print(f"\n✅ Loaded from: {url}")
        print(f"📄 Documents: {len(docs)}")
        print(f"📝 Content (first 500 chars):\n{docs[0].page_content[:500]}")
        print(f"\n📋 Metadata: {docs[0].metadata}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ===== INTERMEDIATE: PDF Loader =====

def load_pdf_demo(pdf_path: str = None):
    """Load PDF file."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: PDF Loader")
    print("=" * 70)

    if not pdf_path:
        print("\n⚠️  Provide a PDF path to test this")
        print("Example: load_pdf_demo('/path/to/your.pdf')")
        return

    try:
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()

        print(f"\n✅ Loaded PDF: {pdf_path}")
        print(f"📄 Pages: {len(docs)}")
        print(f"\n📝 First page (300 chars):\n{docs[0].page_content[:300]}")
        print(f"\n📋 Metadata: {docs[0].metadata}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ===== ADVANCED: Custom Document =====

def create_custom_documents():
    """Create Document objects manually."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Custom Document Creation")
    print("=" * 70)

    # Create documents from your data
    docs = [
        Document(
            page_content="Python is a high-level programming language",
            metadata={
                "source": "python_docs",
                "type": "language",
                "level": "basic"
            }
        ),
        Document(
            page_content="FastAPI is a modern Python web framework",
            metadata={
                "source": "fastapi_docs",
                "type": "framework",
                "level": "intermediate"
            }
        ),
        Document(
            page_content="LangChain helps build LLM applications",
            metadata={
                "source": "langchain_docs",
                "type": "framework",
                "level": "advanced"
            }
        ),
    ]

    print(f"\n✅ Created {len(docs)} custom documents")

    for i, doc in enumerate(docs, 1):
        print(f"\n--- Document {i} ---")
        print(f"Content: {doc.page_content}")
        print(f"Source: {doc.metadata['source']}")
        print(f"Type: {doc.metadata['type']}")
        print(f"Level: {doc.metadata['level']}")


# ===== ADVANCED: Filter by Metadata =====

def filter_documents_demo():
    """Filter documents by metadata."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Filter Documents by Metadata")
    print("=" * 70)

    docs = [
        Document(page_content="Python basics", metadata={"level": "basic"}),
        Document(page_content="Python decorators", metadata={"level": "advanced"}),
        Document(page_content="FastAPI intro", metadata={"level": "basic"}),
        Document(page_content="FastAPI middleware", metadata={"level": "advanced"}),
    ]

    # Filter: only basic level
    basic_docs = [d for d in docs if d.metadata["level"] == "basic"]

    print(f"\n📚 Total documents: {len(docs)}")
    print(f"🎯 Basic level: {len(basic_docs)}")

    print("\nBasic documents:")
    for doc in basic_docs:
        print(f"  - {doc.page_content}")


def main():
    """Run all document loader examples."""
    print("=" * 70)
    print("DOCUMENT LOADERS PRACTICE")
    print("=" * 70)

    # Basic
    load_text_file_demo()

    # Intermediate
    load_web_page_demo()
    # load_pdf_demo("/path/to/your.pdf")  # Uncomment with actual PDF

    # Advanced
    create_custom_documents()
    filter_documents_demo()


if __name__ == "__main__":
    main()
