"""
RAG 05: Basic RAG Pipeline
===========================

Topic: Section 7 from THEORY.md
Level: Intermediate → Advanced

What you'll learn:
- Complete RAG pipeline
- Retriever pattern
- Prompt template with context
- End-to-end Q&A system
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


# ===== STEP 1: Knowledge Base Setup =====

def create_knowledge_base():
    """Create a knowledge base from sample text."""
    print("\n" + "=" * 70)
    print("STEP 1: Creating Knowledge Base")
    print("=" * 70)

    # Sample knowledge (in production, load from PDFs/docs)
    knowledge_text = """
    Python Programming Language

    Python is a high-level, interpreted programming language known for its simplicity
    and readability. Created by Guido van Rossum in 1991, Python emphasizes code
    readability with its use of significant indentation.

    Key features of Python:
    - Easy to learn and use
    - Dynamically typed
    - Object-oriented
    - Cross-platform
    - Large standard library
    - Active community

    Python is widely used for:
    - Web development (Django, FastAPI, Flask)
    - Data science and machine learning
    - Automation and scripting
    - Scientific computing
    - DevOps and system administration

    FastAPI Web Framework

    FastAPI is a modern, fast (high-performance) web framework for building APIs
    with Python 3.7+ based on standard Python type hints. It was created by
    Sebastián Ramírez and released in 2018.

    FastAPI advantages:
    - Fast: One of the fastest Python frameworks
    - Easy: Designed to be easy to use and learn
    - Automatic API documentation (Swagger/OpenAPI)
    - Type hints based validation
    - Async support out of the box
    - Dependency injection system

    FastAPI is built on:
    - Starlette for web parts
    - Pydantic for data parts

    LangChain Framework

    LangChain is an open-source framework for developing applications powered by
    large language models (LLMs). It provides tools to chain together prompts,
    models, and outputs efficiently.

    LangChain components:
    - Models: Interface to LLMs
    - Prompts: Template system for prompts
    - Chains: Sequence of calls
    - Agents: LLM with tools
    - Memory: Conversation state
    - Vectorstores: For RAG applications

    LangChain supports multiple providers including OpenAI, Anthropic, Google,
    and many others through a unified interface.
    """

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    chunks = splitter.split_text(knowledge_text)

    # Convert to Documents
    docs = [
        Document(
            page_content=chunk,
            metadata={"source": "knowledge_base", "chunk_id": i}
        )
        for i, chunk in enumerate(chunks)
    ]

    print(f"\n📚 Created {len(docs)} chunks from knowledge base")

    return docs


# ===== STEP 2: Vector Store =====

def create_vector_store(docs):
    """Create vector store from documents."""
    print("\n" + "=" * 70)
    print("STEP 2: Creating Vector Store")
    print("=" * 70)

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
    )

    print(f"\n✅ Vector store created with {len(docs)} chunks")

    return vector_store


# ===== STEP 3: RAG Function =====

def create_rag_pipeline(vector_store):
    """Create RAG Q&A function."""
    print("\n" + "=" * 70)
    print("STEP 3: Building RAG Pipeline")
    print("=" * 70)

    # Initialize LLM
    llm = init_chat_model("groq:llama-3.3-70b-versatile")

    # Create prompt template
    prompt = ChatPromptTemplate.from_template("""
    You are a helpful AI assistant.
    Answer the question based ONLY on the context below.
    If the answer is not in the context, say "I don't have information about that".
    Be concise and accurate.

    Context:
    {context}

    Question: {question}

    Answer:
    """)

    def ask(question: str) -> str:
        """Ask a question using RAG."""
        # 1. Retrieve relevant chunks
        relevant_docs = vector_store.similarity_search(question, k=3)
        context = "\n\n".join([doc.page_content for doc in relevant_docs])

        # 2. Format prompt
        messages = prompt.format_messages(
            context=context,
            question=question
        )

        # 3. Get answer from LLM
        response = llm.invoke(messages)

        return response.content

    print("\n✅ RAG pipeline ready!")
    return ask


# ===== STEP 4: Test RAG =====

def test_rag(ask_function):
    """Test RAG with various questions."""
    print("\n" + "=" * 70)
    print("STEP 4: Testing RAG Pipeline")
    print("=" * 70)

    questions = [
        # Direct questions from knowledge
        "Who created Python?",
        "When was FastAPI released?",
        "What are the components of LangChain?",

        # Inference questions
        "Why is FastAPI considered fast?",
        "What are the main use cases of Python?",

        # Out-of-knowledge question
        "What is JavaScript?",  # Not in knowledge base
    ]

    for question in questions:
        print(f"\n{'=' * 70}")
        print(f"❓ Question: {question}")
        print('=' * 70)

        answer = ask_function(question)
        print(f"\n💬 Answer:\n{answer}")


# ===== INTERACTIVE: Chat Mode =====

def interactive_rag_chat(ask_function):
    """Interactive Q&A with RAG."""
    print("\n" + "=" * 70)
    print("INTERACTIVE RAG CHAT")
    print("Type 'quit' to exit")
    print("=" * 70)

    while True:
        question = input("\nYou: ").strip()

        if question.lower() in ["quit", "exit", "bye"]:
            print("Bye!")
            break

        if not question:
            continue

        answer = ask_function(question)
        print(f"\nAI: {answer}")


def main():
    """Run complete RAG pipeline."""
    print("=" * 70)
    print("BASIC RAG PIPELINE")
    print("=" * 70)

    # Step 1: Knowledge base
    docs = create_knowledge_base()

    # Step 2: Vector store
    vector_store = create_vector_store(docs)

    # Step 3: RAG pipeline
    ask = create_rag_pipeline(vector_store)

    # Step 4: Test
    test_rag(ask)

    # Interactive mode (uncomment to use)
    # interactive_rag_chat(ask)


if __name__ == "__main__":
    main()
