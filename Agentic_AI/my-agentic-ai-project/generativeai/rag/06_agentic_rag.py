"""
RAG 06: Agentic RAG (Modern Pattern)
=====================================

Topic: Section 8 from THEORY.md
Level: Advanced

What you'll learn:
- Combining create_agent + RAG
- RAG as a tool
- Agent decides when to retrieve
- Multi-step research patterns
"""

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


# ===== SETUP: Knowledge Base =====

def setup_knowledge_base():
    """Setup global knowledge base."""
    print("\n📚 Setting up knowledge base...")

    # Sample knowledge about the company
    company_knowledge = """
    TechCorp Company Information

    About Us:
    TechCorp is a leading technology company founded in 2010 by Rahul Sharma.
    We specialize in cloud computing, AI/ML solutions, and enterprise software.
    Headquartered in Bangalore, India, we have offices in 12 countries.

    Our Products:
    1. CloudMaster - Cloud infrastructure management platform
    2. AIInsights - Business intelligence powered by AI
    3. DataStream - Real-time data analytics tool
    4. SecureShield - Enterprise security suite

    Team:
    - CEO: Rahul Sharma (15 years experience)
    - CTO: Priya Patel (12 years experience)
    - VP Engineering: Amit Kumar (10 years experience)
    - Total employees: 5,000+

    HR Policies:
    - Work hours: 9 AM to 6 PM
    - Remote work: 3 days per week allowed
    - Vacation: 20 days per year
    - Sick leave: 10 days per year
    - Health insurance: Covered for employee and family
    - Bonus: Performance-based, annual

    Tech Stack:
    - Backend: Python, FastAPI, Java
    - Frontend: React, TypeScript
    - Databases: PostgreSQL, MongoDB, Redis
    - Cloud: AWS, GCP
    - DevOps: Docker, Kubernetes, Jenkins
    - AI/ML: TensorFlow, PyTorch, LangChain
    """

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    chunks = splitter.split_text(company_knowledge)

    # Create documents
    docs = [
        Document(
            page_content=chunk,
            metadata={"source": "company_docs", "chunk_id": i}
        )
        for i, chunk in enumerate(chunks)
    ]

    # Create vector store
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = Chroma.from_documents(docs, embeddings)

    print(f"✅ Knowledge base ready: {len(docs)} chunks")
    return vector_store


# ===== GLOBAL VECTOR STORE =====

vector_store = setup_knowledge_base()


# ===== TOOL: RAG Retrieval =====

@tool(response_format="content_and_artifact")
def search_company_knowledge(query: str):
    """Search the company knowledge base for information.

    Use this tool when the user asks about:
    - Company information (products, team, history)
    - HR policies (vacation, leaves, work hours)
    - Tech stack and technologies used

    Args:
        query: What to search for in company docs

    Returns:
        Relevant information from company knowledge base
    """
    docs = vector_store.similarity_search(query, k=3)

    serialized = "\n\n".join([
        f"Source: {doc.metadata['source']}\nContent: {doc.page_content}"
        for doc in docs
    ])

    return serialized, docs


# ===== ADDITIONAL TOOLS =====

@tool
def calculate(expression: str) -> str:
    """Calculate a math expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


@tool
def get_current_datetime() -> str:
    """Get current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ===== AGENTIC RAG AGENT =====

agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[
        search_company_knowledge,
        calculate,
        get_current_datetime,
    ],
    system_prompt="""
    You are TechCorp's helpful AI assistant.

    Guidelines:
    1. For company-related questions, ALWAYS use search_company_knowledge tool
    2. For math, use calculate tool
    3. For time-related queries, use get_current_datetime tool
    4. For general questions (not company-specific), answer directly
    5. Always cite sources when using company knowledge
    6. If info not in knowledge base, say "I don't have that information"

    Be professional, accurate, and helpful.
    """
)


# ===== TEST CASES =====

def test_agentic_rag():
    """Test agent with various queries."""
    print("\n" + "=" * 70)
    print("AGENTIC RAG TESTING")
    print("=" * 70)

    queries = [
        # Company questions (will use RAG)
        "Who founded TechCorp?",
        "What products does the company offer?",
        "What's the vacation policy?",
        "What tech stack do you use?",
        "How many employees work here?",

        # Math (will use calculator)
        "What is 1500 * 12?",

        # Time (will use datetime)
        "What's the current time?",

        # Mixed (will use multiple tools)
        "If our work hours are 9 to 6, how many hours per day?",

        # Not in knowledge base
        "What is the company's CEO's email?",

        # General (no tool needed)
        "What is Python?",
    ]

    for query in queries:
        print(f"\n{'=' * 70}")
        print(f"❓ {query}")
        print('=' * 70)

        result = agent.invoke({
            "messages": [("user", query)]
        })

        print(f"💬 Answer: {result['messages'][-1].content}")


# ===== INTERACTIVE MODE =====

def interactive_mode():
    """Interactive Q&A with agent."""
    print("\n" + "=" * 70)
    print("TECHCORP AI ASSISTANT (Interactive)")
    print("Type 'quit' to exit")
    print("=" * 70)

    while True:
        query = input("\nYou: ").strip()

        if query.lower() in ["quit", "exit", "bye"]:
            print("Goodbye!")
            break

        if not query:
            continue

        result = agent.invoke({
            "messages": [("user", query)]
        })

        print(f"\nAI: {result['messages'][-1].content}")


def main():
    """Run agentic RAG examples."""
    test_agentic_rag()

    # Interactive (uncomment to use)
    # interactive_mode()


if __name__ == "__main__":
    main()
