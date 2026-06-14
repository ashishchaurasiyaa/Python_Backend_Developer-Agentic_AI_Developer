# 🚀 4-Day Intensive Practice Plan (LangChain + RAG)

> **Status:** Both Krish Naik videos COMPLETED ✅
> **Goal:** Master LangChain + RAG through hands-on practice
> **Duration:** 4 days intensive (2-3 hrs daily)
> **Outcome:** 75% Agentic AI mastery + 2 portfolio projects

---

## 📊 Current State

```
✅ LangChain video (3 hrs) - COMPLETE
✅ RAG video (2 hrs) - COMPLETE
✅ 5 LangChain files working
⏳ Practice files - NEEDED
⏳ Mini projects - NEEDED
```

**Current %:** 50%
**After 4 days:** 75%
**Then:** LangGraph + Ed Donner course

---

# 📅 4-DAY MASTER PLAN

## Day 1: LangChain Modern API + Theory Review
## Day 2: LangChain Advanced + Mini Project
## Day 3: RAG Theory + Practical Implementation
## Day 4: Agentic RAG + Full Integration Project

---

# 🟢 DAY 1: LangChain Modern API + Theory

## Goal: Master create_agent() V1 + Build practice files

### Morning Session (2 hours): Theory Review

#### Topic 1: Old vs New API
```python
# OLD Pattern (your first_agent.py uses this)
llm = init_chat_model("groq:llama-3.3-70b-versatile")
llm_with_tools = llm.bind_tools(tools)

response = llm_with_tools.invoke("query")
if response.tool_calls:
    for tc in response.tool_calls:
        result = tools_map[tc["name"]].invoke(tc["args"])

# NEW Pattern (V1 - Industry Standard)
from langchain.agents import create_agent

agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=tools,
    system_prompt="You are helpful."
)

result = agent.invoke({"messages": [("user", "query")]})
# Auto-execution! 5 lines instead of 15!
```

#### Topic 2: create_agent() Parameters
```python
agent = create_agent(
    model="provider:model",         # Required
    tools=[tool1, tool2],            # Required
    system_prompt="...",             # Optional - Behavior
    response_format=PydanticModel,   # Optional - Structured output
    name="agent_name",               # Optional - Multi-agent
    checkpointer=InMemorySaver(),    # Optional - Memory
    middleware=[...]                 # Optional - Production
)
```

#### Topic 3: Message Types
```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# System: Behavior instructions
SystemMessage(content="You are a Python expert")

# Human: User input
HumanMessage(content="Explain async/await")

# AI: Previous responses
AIMessage(content="Async/await is...")
```

---

### Afternoon Session (2 hours): Practical Building

#### Task 1: Create `practice_01_modern_agent.py` (45 min)

```python
"""
Day 1: Modern Agent Pattern
Migrate first_agent.py to use create_agent() V1
"""

from datetime import datetime
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

load_dotenv()


# ===== TOOLS =====
@tool
def calculator(expression: str) -> str:
    """Calculate math expression."""
    try:
        return f"Result: {eval(expression)}"
    except Exception as e:
        return f"Error: {e}"


@tool
def get_current_time() -> str:
    """Get current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def greet_user(name: str, language: str = "english") -> str:
    """Greet user in specified language."""
    greetings = {
        "english": f"Hello {name}!",
        "hindi": f"Namaste {name}!",
        "spanish": f"Hola {name}!",
    }
    return greetings.get(language, greetings["english"])


# ===== MODERN AGENT =====
agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[calculator, get_current_time, greet_user],
    system_prompt="""
    You are a helpful assistant with 3 tools.
    Use them when appropriate. Be concise.
    """
)


# ===== USAGE =====
def main():
    queries = [
        "What's 25 * 4?",
        "What time is it?",
        "Greet Ashish in Hindi",
        "Calculate 100 + 200 and greet Priya in Spanish",
    ]
    
    for query in queries:
        print(f"\n{'=' * 60}")
        print(f"User: {query}")
        print('=' * 60)
        
        result = agent.invoke({
            "messages": [("user", query)]
        })
        
        # Modern API: Final answer directly
        print(f"Agent: {result['messages'][-1].content}")


if __name__ == "__main__":
    main()
```

#### Task 2: Create `practice_02_messages.py` (45 min)

```python
"""
Day 1: Message Types Practice
System + Human + AI messages
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

load_dotenv()

model = init_chat_model("groq:llama-3.3-70b-versatile")


# ===== PATTERN 1: System + Human =====
def test_system_message():
    """Test with system prompt."""
    messages = [
        SystemMessage(content="You are a Python expert. Reply in 2 lines."),
        HumanMessage(content="What is async/await?")
    ]
    
    response = model.invoke(messages)
    print(f"\nResponse: {response.content}")


# ===== PATTERN 2: Multi-turn Conversation =====
def chat_conversation():
    """Multi-turn conversation."""
    conversation = [
        SystemMessage(content="You are a helpful AI tutor in Hindi.")
    ]
    
    # First turn
    conversation.append(HumanMessage(content="Mera naam Ashish hai"))
    response1 = model.invoke(conversation)
    conversation.append(AIMessage(content=response1.content))
    print(f"\nTurn 1: {response1.content}")
    
    # Second turn (AI remembers!)
    conversation.append(HumanMessage(content="Mera naam kya hai?"))
    response2 = model.invoke(conversation)
    conversation.append(AIMessage(content=response2.content))
    print(f"\nTurn 2: {response2.content}")
    
    # Third turn
    conversation.append(HumanMessage(content="Mujhe Python sikhao"))
    response3 = model.invoke(conversation)
    print(f"\nTurn 3: {response3.content}")


if __name__ == "__main__":
    test_system_message()
    chat_conversation()
```

### End of Day 1 Checklist:
```
[ ] Read theory section
[ ] Build practice_01_modern_agent.py
[ ] Run and test it
[ ] Build practice_02_messages.py
[ ] Run and test it
[ ] Update NOTES.md
```

---

# 🟡 DAY 2: LangChain Advanced + Mini Project

## Goal: Structured output, memory, and build first project

### Morning Session (2 hours): Advanced Concepts

#### Topic 1: Structured Output (Pydantic)
```python
from pydantic import BaseModel, Field

class WeatherInfo(BaseModel):
    city: str = Field(description="City name")
    temperature: int = Field(description="Temp in Celsius")
    conditions: str = Field(description="Sunny/Rainy/etc")
    humidity: int = Field(description="Humidity %")

# Force LLM to return this structure
structured_model = model.with_structured_output(WeatherInfo)
result = structured_model.invoke("Weather in Mumbai")
# result is WeatherInfo object, not dict!
```

#### Topic 2: Memory with Checkpointer
```python
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[],
    checkpointer=InMemorySaver()
)

# Use thread_id for conversation
config = {"configurable": {"thread_id": "user_123"}}

# Conversation 1
agent.invoke({"messages": [("user", "I'm Ashish")]}, config=config)

# Conversation 2 - AI remembers!
agent.invoke({"messages": [("user", "What's my name?")]}, config=config)
```

#### Topic 3: Streaming
```python
# Real-time output
for chunk in agent.stream(
    {"messages": [("user", "Tell long story")]},
    stream_mode="values"
):
    latest = chunk["messages"][-1]
    print(latest.content, end="", flush=True)
```

---

### Afternoon Session (3 hours): Mini Project

#### Project: AI Tutor Chatbot

```python
"""
Day 2 Project: AI Tutor with Memory
Features:
- Multiple subjects (Python, FastAPI, JavaScript)
- Conversation memory
- Structured progress tracking
"""

from uuid import uuid4
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, Field

load_dotenv()


# ===== STRUCTURED PROGRESS =====
class LearningProgress(BaseModel):
    """Track user's learning progress."""
    subject: str
    topics_covered: list[str]
    current_level: str = Field(description="beginner/intermediate/advanced")
    next_topic: str


# ===== TOOLS =====
@tool
def get_topic_outline(subject: str, level: str = "beginner") -> str:
    """Get outline for a subject at given level."""
    outlines = {
        "python": {
            "beginner": "1. Variables 2. Loops 3. Functions 4. Classes",
            "intermediate": "1. Decorators 2. Generators 3. Async 4. Metaclasses",
            "advanced": "1. Memory management 2. GIL 3. Threading 4. Performance",
        },
        "fastapi": {
            "beginner": "1. Basic routes 2. Path params 3. Query params 4. Body",
            "intermediate": "1. Dependencies 2. Auth 3. Database 4. Testing",
            "advanced": "1. Custom middleware 2. WebSockets 3. Background tasks",
        },
    }
    return outlines.get(subject.lower(), {}).get(level, "Topic not found")


@tool
def explain_concept(concept: str, subject: str) -> str:
    """Provide detailed explanation of a concept."""
    return f"Detailed explanation of {concept} in {subject}..."


# ===== AGENT WITH MEMORY =====
agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[get_topic_outline, explain_concept],
    system_prompt="""
    You are an AI Tutor specializing in programming.
    
    Subjects: Python, FastAPI, JavaScript
    
    Guidelines:
    - Remember what student has learned
    - Adapt to student's level
    - Use tools to provide accurate info
    - Be encouraging and patient
    - Reply in mix of Hindi and English (Hinglish)
    """,
    checkpointer=InMemorySaver()
)


# ===== CHAT INTERFACE =====
def start_tutoring_session():
    """Interactive tutoring session."""
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("\n" + "=" * 60)
    print("🎓 AI Tutor Started!")
    print("Type 'quit' to exit")
    print("=" * 60)
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ["quit", "exit", "bye"]:
            print("AI Tutor: Goodbye! Keep learning! 🚀")
            break
        
        if not user_input:
            continue
        
        result = agent.invoke(
            {"messages": [("user", user_input)]},
            config=config
        )
        
        print(f"AI Tutor: {result['messages'][-1].content}")


if __name__ == "__main__":
    start_tutoring_session()
```

### End of Day 2 Checklist:
```
[ ] Build practice_03_structured_output.py
[ ] Build practice_04_memory.py
[ ] Build practice_05_streaming.py
[ ] BUILD AI TUTOR PROJECT (Mini project #1!)
[ ] Push to GitHub
[ ] Update NOTES.md
```

---

# 🔵 DAY 3: RAG Theory + Practical

## Goal: Master RAG fundamentals + Build RAG files

### Morning Session (2 hours): RAG Theory Review

#### Topic 1: RAG Architecture
```
PHASE 1: INDEXING (One-time)
Document → Loader → Splitter → Embeddings → Vector DB

PHASE 2: RETRIEVAL (Every query)
Query → Embed → Search → Top K Chunks → LLM → Answer
```

#### Topic 2: Document Loaders
```python
# PDF
from langchain_community.document_loaders import PyPDFLoader
loader = PyPDFLoader("file.pdf")

# Text
from langchain_community.document_loaders import TextLoader
loader = TextLoader("file.txt")

# Web
from langchain_community.document_loaders import WebBaseLoader
loader = WebBaseLoader("https://example.com")
```

#### Topic 3: Text Splitters
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Each chunk size
    chunk_overlap=200,    # Overlap (context preservation)
)
```

#### Topic 4: Embeddings
```python
# FREE - Google
from langchain_google_genai import GoogleGenerativeAIEmbeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# FREE - HuggingFace
from langchain_huggingface import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
```

#### Topic 5: Vector Stores
```python
from langchain_chroma import Chroma

# Create
vector_store = Chroma.from_documents(chunks, embeddings)

# Search
results = vector_store.similarity_search("query", k=3)
```

---

### Afternoon Session (3 hours): Build RAG Files

#### Setup:
```bash
# Install RAG packages
uv add pypdf beautifulsoup4 langchain-text-splitters
uv add langchain-chroma langchain-google-genai
uv add sentence-transformers langchain-huggingface
```

#### File 1: `rag/01_document_loader.py` (30 min)

```python
"""
Day 3: Document Loading Practice
Test different loaders
"""

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    WebBaseLoader,
)


def load_text_file(path: str):
    """Load .txt file."""
    loader = TextLoader(path)
    docs = loader.load()
    print(f"Loaded {len(docs)} documents from text file")
    print(f"First 200 chars: {docs[0].page_content[:200]}")
    return docs


def load_pdf_file(path: str):
    """Load PDF file."""
    loader = PyPDFLoader(path)
    docs = loader.load()
    print(f"Loaded {len(docs)} pages from PDF")
    print(f"Metadata: {docs[0].metadata}")
    return docs


def load_web_page(url: str):
    """Load web page."""
    loader = WebBaseLoader(url)
    docs = loader.load()
    print(f"Loaded content from {url}")
    print(f"First 200 chars: {docs[0].page_content[:200]}")
    return docs


if __name__ == "__main__":
    # Test with sample files
    # load_text_file("sample.txt")
    # load_pdf_file("sample.pdf")
    load_web_page("https://docs.langchain.com/oss/python/langchain/overview")
```

#### File 2: `rag/02_text_splitter.py` (30 min)

```python
"""
Day 3: Text Splitter Practice
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50):
    """Split text into chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    
    # Convert to Document
    doc = Document(page_content=text)
    chunks = splitter.split_documents([doc])
    
    print(f"Original length: {len(text)}")
    print(f"Number of chunks: {len(chunks)}")
    
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Length: {len(chunk.page_content)}")
        print(f"Start index: {chunk.metadata.get('start_index')}")
        print(f"Content: {chunk.page_content[:100]}...")
    
    return chunks


if __name__ == "__main__":
    sample_text = """
    LangChain is an open-source framework for building applications powered by large language models (LLMs).
    It provides tools to chain together prompts, models, and outputs efficiently.
    
    RAG (Retrieval Augmented Generation) optimizes LLM outputs by referencing external knowledge bases.
    This eliminates the need to retrain models when adding new information.
    
    Vector databases store embeddings (numerical representations of text) for fast similarity search.
    Popular vector databases include Chroma, FAISS, Pinecone, and Qdrant.
    """ * 10  # Make it longer
    
    chunks = split_text(sample_text)
    print(f"\nTotal chunks created: {len(chunks)}")
```

#### File 3: `rag/03_embeddings.py` (30 min)

```python
"""
Day 3: Embeddings Practice
"""

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


def test_embeddings():
    """Test creating embeddings."""
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )
    
    # Single text
    text = "Python is a programming language"
    vector = embeddings.embed_query(text)
    
    print(f"Text: {text}")
    print(f"Vector dimensions: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")
    
    # Multiple texts (batch)
    texts = [
        "Python is great",
        "Java is verbose",
        "JavaScript runs in browsers",
        "Pizza is delicious"
    ]
    
    vectors = embeddings.embed_documents(texts)
    print(f"\nCreated {len(vectors)} embeddings")
    
    # Calculate similarity (cosine)
    import numpy as np
    
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    print("\nSimilarity scores:")
    for i, text in enumerate(texts):
        similarity = cosine_similarity(vectors[0], vectors[i])
        print(f"'{texts[0]}' vs '{text}': {similarity:.3f}")


if __name__ == "__main__":
    test_embeddings()
```

#### File 4: `rag/04_vector_store.py` (45 min)

```python
"""
Day 3: Vector Store Practice with Chroma
"""

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


def create_and_query_vector_store():
    """Create vector store and search."""
    
    # Sample documents
    documents = [
        Document(
            page_content="Python is a high-level programming language",
            metadata={"source": "python_docs", "type": "language"}
        ),
        Document(
            page_content="FastAPI is a modern web framework for Python",
            metadata={"source": "fastapi_docs", "type": "framework"}
        ),
        Document(
            page_content="React is a JavaScript library for UI",
            metadata={"source": "react_docs", "type": "library"}
        ),
        Document(
            page_content="MongoDB is a NoSQL database",
            metadata={"source": "mongo_docs", "type": "database"}
        ),
    ]
    
    # Create embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    
    # Create vector store
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    
    print("Vector store created!")
    
    # Search
    queries = [
        "Tell me about programming languages",
        "Web frameworks",
        "Database systems",
    ]
    
    for query in queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print('=' * 60)
        
        results = vector_store.similarity_search(query, k=2)
        
        for i, doc in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Content: {doc.page_content}")
            print(f"Source: {doc.metadata['source']}")


if __name__ == "__main__":
    create_and_query_vector_store()
```

### End of Day 3 Checklist:
```
[ ] Install RAG packages
[ ] Build 01_document_loader.py
[ ] Build 02_text_splitter.py
[ ] Build 03_embeddings.py
[ ] Build 04_vector_store.py
[ ] Test each file
[ ] Update NOTES.md
```

---

# 🔴 DAY 4: Agentic RAG + Full Integration Project

## Goal: Complete RAG mastery + Production project

### Morning Session (2 hours): Complete RAG Pipeline

#### File 5: `rag/05_complete_rag.py` (1 hour)

```python
"""
Day 4: Complete RAG Pipeline
End-to-end PDF Q&A bot
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


class PDFChatBot:
    """Chat with any PDF using RAG."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.vector_store = None
        self.llm = init_chat_model(
            "groq:llama-3.3-70b-versatile"
        )
        self._setup()
    
    def _setup(self):
        """Setup RAG pipeline."""
        print("📚 Loading PDF...")
        loader = PyPDFLoader(self.pdf_path)
        docs = loader.load()
        print(f"   Loaded {len(docs)} pages")
        
        print("✂️  Splitting into chunks...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        chunks = splitter.split_documents(docs)
        print(f"   Created {len(chunks)} chunks")
        
        print("🔢 Creating embeddings...")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001"
        )
        
        print("💾 Building vector store...")
        self.vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
        )
        print("✅ Setup complete!\n")
    
    def ask(self, question: str) -> str:
        """Ask question about the PDF."""
        # Retrieve relevant chunks
        docs = self.vector_store.similarity_search(question, k=3)
        context = "\n\n".join([d.page_content for d in docs])
        
        # Ask LLM with context
        prompt = f"""
        Answer the question based ONLY on the context below.
        If you don't know, say "I don't know based on the provided context".
        
        Context:
        {context}
        
        Question: {question}
        
        Answer:
        """
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def chat(self):
        """Interactive chat session."""
        print(f"💬 Chat with: {self.pdf_path}")
        print("Type 'quit' to exit\n")
        
        while True:
            question = input("You: ").strip()
            
            if question.lower() in ["quit", "exit", "bye"]:
                print("Goodbye!")
                break
            
            if not question:
                continue
            
            answer = self.ask(question)
            print(f"\nAI: {answer}\n")


if __name__ == "__main__":
    # Replace with your PDF path
    pdf_path = "your_resume.pdf"  # or any PDF
    
    bot = PDFChatBot(pdf_path)
    bot.chat()
```

---

### Afternoon Session (3 hours): Agentic RAG Project

#### Final Project: AI Research Assistant

```python
"""
Day 4 Final Project: AI Research Assistant
Combines: LangChain + RAG + Tools + Memory
"""

from uuid import uuid4
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()


# ===== GLOBAL VECTOR STORE =====
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vector_store = Chroma(
    collection_name="research",
    embedding_function=embeddings,
    persist_directory="./research_db"
)


# ===== TOOLS =====

@tool
def add_pdf_to_knowledge(pdf_path: str) -> str:
    """Add a PDF document to the research knowledge base."""
    try:
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        chunks = splitter.split_documents(docs)
        
        vector_store.add_documents(chunks)
        return f"Added {len(chunks)} chunks from {pdf_path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def add_url_to_knowledge(url: str) -> str:
    """Add a web page to the research knowledge base."""
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        chunks = splitter.split_documents(docs)
        
        vector_store.add_documents(chunks)
        return f"Added {len(chunks)} chunks from {url}"
    except Exception as e:
        return f"Error: {e}"


@tool
def search_knowledge_base(query: str) -> str:
    """Search the research knowledge base for information."""
    docs = vector_store.similarity_search(query, k=3)
    
    if not docs:
        return "No relevant information found."
    
    results = []
    for i, doc in enumerate(docs, 1):
        results.append(f"--- Result {i} ---\n{doc.page_content}\n")
    
    return "\n".join(results)


@tool
def summarize_topic(topic: str) -> str:
    """Get a summary of all knowledge about a topic."""
    docs = vector_store.similarity_search(topic, k=5)
    
    if not docs:
        return f"No information about '{topic}' in knowledge base."
    
    content = "\n\n".join([d.page_content for d in docs])
    return f"Found {len(docs)} relevant pieces:\n\n{content}"


# ===== RESEARCH AGENT =====

agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[
        add_pdf_to_knowledge,
        add_url_to_knowledge,
        search_knowledge_base,
        summarize_topic,
    ],
    system_prompt="""
    You are an AI Research Assistant.
    
    Capabilities:
    - Add PDFs and URLs to knowledge base
    - Search and summarize research
    - Answer questions based on stored knowledge
    - Cite sources when possible
    
    Guidelines:
    - Use tools when information is needed
    - Always check knowledge base before answering
    - Be precise and cite sources
    - If info not found, suggest adding more documents
    """,
    checkpointer=InMemorySaver()
)


# ===== INTERACTIVE INTERFACE =====

def main():
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("\n" + "=" * 70)
    print("🔬 AI RESEARCH ASSISTANT")
    print("=" * 70)
    print("\nCommands:")
    print("- Add PDF: 'Add this PDF: /path/to/file.pdf'")
    print("- Add URL: 'Add this URL: https://example.com'")
    print("- Ask: 'What does the research say about X?'")
    print("- Quit: 'quit'")
    print("=" * 70 + "\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ["quit", "exit", "bye"]:
            print("\n👋 Research session ended!")
            break
        
        if not user_input:
            continue
        
        print()
        result = agent.invoke(
            {"messages": [("user", user_input)]},
            config=config
        )
        
        print(f"AI: {result['messages'][-1].content}\n")


if __name__ == "__main__":
    main()
```

### End of Day 4 Checklist:
```
[ ] Build 05_complete_rag.py (PDF Q&A bot)
[ ] Build research_assistant.py (FINAL PROJECT!)
[ ] Test with real PDFs
[ ] Push to GitHub
[ ] Update LinkedIn
[ ] Update NOTES.md
```

---

# 📊 4-Day Schedule Summary

```
DAY 1 (Mon): LangChain Modern API (4 hrs)
   Morning: Theory review (2 hrs)
   Afternoon: 2 practice files (2 hrs)

DAY 2 (Tue): LangChain Advanced + Project (5 hrs)
   Morning: Advanced concepts (2 hrs)
   Afternoon: AI Tutor project (3 hrs)

DAY 3 (Wed): RAG Theory + Practical (5 hrs)
   Morning: RAG fundamentals (2 hrs)
   Afternoon: 4 RAG files (3 hrs)

DAY 4 (Thu): Agentic RAG Project (5 hrs)
   Morning: Complete RAG (2 hrs)
   Afternoon: Research Assistant project (3 hrs)

TOTAL: 19 hours = LangChain + RAG MASTER!
```

---

# 🎯 What's NEXT After 4 Days?

## After Day 4 (75% Complete):

### **PHASE 2: LangGraph (Next 2 weeks)**

```
Week 1 of LangGraph:
├── Day 1-3: Krish Naik LangGraph playlist (FREE)
├── Day 4: LangGraph RAG Hindi video (FREE)
└── Day 5-7: Build LangGraph project

Week 2 of LangGraph:
├── Day 1-3: LangGraph Academy (FREE)
├── Day 4-5: Multi-agent patterns
└── Day 6-7: Build research agent v2
```

### **PHASE 3: Ed Donner Course (Week 3-8)**

```
Week 3-4: OpenAI Agents SDK
Week 5: CrewAI
Week 6: LangGraph (deeper)
Week 7: AutoGen  
Week 8: MCP Protocol ⭐
```

### **PHASE 4: Portfolio Projects (Week 9-12)**

```
Week 9-10: AI Customer Support SaaS
Week 11: AI Research Assistant v2
Week 12: AI Code Review Bot
```

### **PHASE 5: Job Hunt (Week 13)**

```
Week 13: Apply for jobs
Target: ₹25-40 LPA role 🎯
```

---

# 📁 Updated Project Structure (After 4 Days)

```
my-agentic-ai-project/
├── 📝 NOTES.md
├── 🗺️ COMPLETE_SEQUENCE.md
├── 📚 RAG_COMPLETE_GUIDE.md
├── 📘 OFFICIAL_LANGCHAIN_GUIDE.md
├── 📘 LANGCHAIN_PRACTICE.md
├── 📘 4_DAY_PRACTICE_PLAN.md ← NEW
└── generativeai/
    ├── langchain/  ✅ 5 + 5 practice files (10 total!)
    │   ├── langchainintro.py
    │   ├── multi_provider.py
    │   ├── generative_with_open_ai.py
    │   ├── first_agent.py
    │   ├── tools.py
    │   ├── practice_01_modern_agent.py
    │   ├── practice_02_messages.py
    │   ├── practice_03_structured_output.py
    │   ├── practice_04_memory.py
    │   ├── practice_05_streaming.py
    │   └── ai_tutor_project.py  ← Mini project!
    └── rag/  ✅ 5 files + 1 project
        ├── 01_document_loader.py
        ├── 02_text_splitter.py
        ├── 03_embeddings.py
        ├── 04_vector_store.py
        ├── 05_complete_rag.py
        └── research_assistant.py  ← Final project!
```

---

# 💎 % Progress Tracker

```
Today (Day 0):         50%
After Day 1:           55%
After Day 2:           60% + 1 project
After Day 3:           67%
After Day 4:           75% + 2 projects ⭐

Then LangGraph:        85%
Then Ed Donner:        95%
Then portfolio:        100% 🎯
```

---

# 🎯 Daily Discipline Rules

## Rules for 4 Days:

```
1. ✅ Block 4-5 hours daily (morning + afternoon)
2. ✅ No phone during practice sessions
3. ✅ Code along, don't just read
4. ✅ Test every file you create
5. ✅ Push to GitHub daily
6. ✅ Update NOTES.md daily
7. ✅ Take 15 min break every 1 hour
8. ✅ 1 LinkedIn post per project
```

---

# 🏆 What You'll Have After 4 Days

## Skills:
```
✅ LangChain (Old + New V1 API)
✅ Modern create_agent() pattern
✅ Pydantic structured output
✅ Conversation memory
✅ Streaming responses
✅ RAG (Complete pipeline)
✅ Document loaders
✅ Embeddings
✅ Vector databases
✅ Agentic RAG patterns
```

## Code:
```
✅ 11 working LangChain files
✅ 6 working RAG files
✅ 2 portfolio projects (AI Tutor + Research Assistant)
✅ All on GitHub
```

## Profile:
```
✅ 17 files of clean code
✅ 2 deployable projects
✅ LinkedIn updated
✅ Strong portfolio
```

## Salary Eligibility:
```
Before: ₹8-15 LPA (Junior)
After:  ₹15-22 LPA (Mid-level) ⭐
```

---

# 🚀 START NOW - Day 1

## Right Now (Today):

```bash
# Setup folders
mkdir -p generativeai/langchain
mkdir -p generativeai/rag

# Start Day 1 Theory + Practice
```

## Day 1 Begins:
```
Morning:
1. ✅ Read theory section above
2. ✅ Understand old vs new API
3. ✅ Plan first practice file

Afternoon:
1. ✅ Build practice_01_modern_agent.py
2. ✅ Build practice_02_messages.py
3. ✅ Test, commit, update notes
```

---

# 💪 Bottom Line

```
4 days. 19 hours. 17 files. 2 projects.
Result: 50% → 75% Agentic AI Master

Then:
LangGraph (2 weeks) → 85%
Ed Donner (6 weeks) → 95%
Portfolio (4 weeks) → 100%

Total: 4 months → ₹25-40 LPA Job 🎯
```

---

## 🔥 Execution Mode

```
Sequence locked: 4 days
Daily commitment: 4-5 hours
Distraction: ZERO
Result: TRANSFORMATION
```

---

**Day 1 START NOW!** 🚀💪🔥

Begin with `practice_01_modern_agent.py` — migrate your first_agent.py to V1 API!

---

*Day 1: LangChain Modern API*
*Day 2: LangChain Advanced + AI Tutor*
*Day 3: RAG Theory + Practical*
*Day 4: Agentic RAG + Research Assistant*

**After 4 days: 75% MILESTONE!** 🎯
