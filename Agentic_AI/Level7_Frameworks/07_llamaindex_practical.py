"""
Level7 — LlamaIndex Practical Lab
===================================
KYA SEEKHENGE (What we will learn):
  1. LlamaIndex ke core abstractions — Document, Node, Settings
  2. SimpleDirectoryReader — local files load karna
  3. IngestionPipeline + NodeParsers — chunking strategies
  4. VectorStoreIndex — build, persist, reload
  5. QueryEngine — retrieve + synthesize
  6. ChatEngine — conversation memory ke saath RAG
  7. SubQuestionQueryEngine + RouterQueryEngine — advanced routing
  8. LlamaIndex vs LangChain — kab kya use karna

KAISE CHALANA (How to run):
  cd /tmp
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level7_Frameworks/07_llamaindex_practical.py"

  Without API keys:
    Full code structure dikhega, LLM calls skip honge (graceful degradation).

  With API keys:
    Live RAG demo chalega local documents pe.

PREREQUISITES:
  pip install llama-index llama-index-embeddings-openai llama-index-llms-openai
  # ya huggingface local (no cost):
  pip install llama-index llama-index-embeddings-huggingface

Level5 RAG seekha tha? Wahi concepts yahan organized form mein hain.
LangChain (Level7/01) padha tha? Yahan compare karenge kab kya use karo.
"""

import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# GRACEFUL IMPORT — agar llama-index install nahi hai, structure dikhate hain
# ─────────────────────────────────────────────────────────────────────────────

LLAMA_AVAILABLE = False
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

try:
    import llama_index  # noqa: F401
    LLAMA_AVAILABLE = True
except ImportError:
    pass

if not LLAMA_AVAILABLE:
    print("=" * 65)
    print("  llama-index not installed -> showing structure + concepts")
    print("  Install: pip install llama-index llama-index-embeddings-openai")
    print("=" * 65)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 0: Core Concepts Table
# Yahan concepts hain jo Level5 RAG ko LlamaIndex mein map karte hain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("LLAMAINDEX CORE CONCEPTS")
print("=" * 65)

# Level5 mein ye manually karte the:
#   raw_text -> TextSplitter -> chunks -> embed -> FAISS -> retrieve -> answer
# LlamaIndex mein abstractions hain:

CONCEPTS = {
    "Document":               "Raw input wrapper (text + metadata). Level5 ka 'raw text'.",
    "Node / TextNode":        "Chunked piece with ID, embedding, relationships.",
    "SentenceSplitter":       "Document -> Nodes. Level5 ka CharacterTextSplitter but smarter.",
    "Settings":               "Global config — LLM, embed_model, chunk_size ek jagah.",
    "VectorStoreIndex":       "Nodes embed karo, vector store mein save karo.",
    "StorageContext":         "Storage backends ka container (vector, doc, index stores).",
    "QueryEngine":            "Retrieve + Synthesize = final answer. Level5 ka RetrievalQA.",
    "ChatEngine":             "QueryEngine + memory = conversation. Level5 ka ConversationRAG.",
    "Retriever":              "Sirf similarity search. Synthesis nahi.",
    "ResponseSynthesizer":    "Retrieved nodes -> final answer. Multiple modes (REFINE, COMPACT).",
    "SubQuestionQueryEngine": "Complex query -> sub-questions -> parallel retrieve -> combine.",
    "RouterQueryEngine":      "Query -> best matching index select karo automatically.",
    "IngestionPipeline":      "Transformations pipeline (split -> extract -> embed).",
    "SimpleDirectoryReader":  "Files load karo (PDF/txt/md auto-detect). LangChain ka loader.",
}

for concept, description in CONCEPTS.items():
    print(f"  {concept:<30}: {description}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Document + Node — basic abstractions
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 1: Document aur Node")
print("=" * 65)

DOCUMENT_CODE = '''\
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

# ===== DOCUMENT =====
# Level5 mein: raw_text = "..."
# LlamaIndex mein: Document object with metadata
doc = Document(
    text="Python is a high-level interpreted programming language. "
         "It was created by Guido van Rossum and released in 1991. "
         "Python is known for its simplicity and readability.",
    doc_id="python_intro_001",         # unique identifier
    metadata={
        "source": "python_wiki",
        "author": "Wikipedia",
        "topic": "programming",
        "date": "2024-01-01",
    },
    # Metadata ko LLM se chhupao (token save karo)
    excluded_llm_metadata_keys=["date", "author"],
    # Embedding mein sirf relevant metadata include karo
    excluded_embed_metadata_keys=["author"],
)
print(f"Document ID: {doc.doc_id}")
print(f"Text length: {len(doc.text)} chars")
print(f"Metadata: {doc.metadata}")

# ===== CHUNKING: Document -> Nodes =====
# Level5 mein: CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
# LlamaIndex mein: SentenceSplitter (sentence boundaries respect karta hai)
splitter = SentenceSplitter(
    chunk_size=100,      # tokens per chunk (not chars!)
    chunk_overlap=10,    # overlap between consecutive chunks
)
nodes = splitter.get_nodes_from_documents([doc])

print(f"\\nCreated {len(nodes)} nodes from document")
for i, node in enumerate(nodes):
    print(f"  Node {i}: ID={node.node_id[:8]}... | {len(node.text)} chars")
    print(f"    Text preview: {node.text[:60]}...")
    # Node mein relationships bhi hain (prev/next/source)
    # node.relationships[NodeRelationship.PREVIOUS]
    # node.relationships[NodeRelationship.NEXT]
    # node.relationships[NodeRelationship.SOURCE]
'''
print(DOCUMENT_CODE)

# Mock demo (bina llama-index ke)
print("\n  [Mock Demo] — Document + Node structure:")


class MockDocument:
    """LlamaIndex Document ka simplified mock."""

    def __init__(self, text: str, doc_id: str = None, metadata: dict = None):
        self.text = text
        self.doc_id = doc_id or f"doc_{id(self)}"
        self.metadata = metadata or {}

    def __repr__(self):
        return f"Document(id={self.doc_id[:12]}..., chars={len(self.text)})"


class MockNode:
    """LlamaIndex TextNode ka simplified mock."""

    def __init__(self, text: str, node_id: str, metadata: dict):
        self.text = text
        self.node_id = node_id
        self.metadata = metadata
        self.embedding = None  # set hoga VectorStoreIndex mein

    def __repr__(self):
        return f"TextNode(id={self.node_id[:8]}..., chars={len(self.text)})"


def mock_sentence_splitter(doc: MockDocument, chunk_size: int = 100) -> list:
    """SentenceSplitter ka simplified mock."""
    # Approximate: words pe split karo
    words = doc.text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk_words = words[i : i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append(
            MockNode(
                text=chunk_text,
                node_id=f"node_{doc.doc_id}_{i}",
                metadata=doc.metadata.copy(),
            )
        )
    return chunks


sample_doc = MockDocument(
    text=(
        "Python is a high-level interpreted programming language. "
        "FastAPI is a modern web framework built on Python. "
        "LlamaIndex makes RAG pipelines easy to build. "
        "Vector databases store embeddings for similarity search."
    ),
    doc_id="sample_001",
    metadata={"source": "notes.txt", "topic": "ai-tools"},
)

sample_nodes = mock_sentence_splitter(sample_doc, chunk_size=10)
print(f"  Document: {sample_doc}")
print(f"  Nodes created: {len(sample_nodes)}")
for node in sample_nodes:
    print(f"    {node} -> text: '{node.text[:50]}...'")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Settings — Global Config
# Level5 mein manually har jagah embed_model pass karte the
# LlamaIndex mein Settings se ek baar set karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Settings — Global Config")
print("=" * 65)

SETTINGS_CODE = '''\
from llama_index.core import Settings

# ===== LLM configure karo =====
from llama_index.llms.openai import OpenAI
Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0, max_tokens=512)

# ===== Embed model configure karo =====
from llama_index.embeddings.openai import OpenAIEmbedding
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# ===== Chunking settings =====
Settings.chunk_size = 512       # default token size per chunk
Settings.chunk_overlap = 50     # overlap between chunks
Settings.num_output = 256       # max response tokens
Settings.context_window = 4096  # LLM context window size

# ===== HuggingFace (free, no API key needed!) =====
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5"  # ~130MB, fast, good quality
)

# ===== Groq (free tier available) =====
from llama_index.llms.groq import Groq
Settings.llm = Groq(model="llama3-70b-8192", api_key=os.environ["GROQ_API_KEY"])

# Key insight: Settings set karo ek baar, sab jagah use hoga
# VectorStoreIndex, QueryEngine, ChatEngine sab Settings se inherit karte hain
'''
print(SETTINGS_CODE)

print("  Settings providers comparison:")
PROVIDERS = {
    "LLM Providers":       "OpenAI, Anthropic, Groq, Ollama (local), HuggingFace",
    "Embed Providers":     "OpenAI, HuggingFace (free!), Ollama (local), Cohere",
    "Free Options":        "HuggingFace embeddings + Groq LLM = zero cost!",
    "Local Options":       "Ollama for both LLM and embeddings (offline!)",
    "Best Quality":        "OpenAI gpt-4o + text-embedding-3-large",
    "Best Cost/Quality":   "Groq llama3-70b + HuggingFace BAAI/bge-small-en-v1.5",
}
for k, v in PROVIDERS.items():
    print(f"  {k:<22}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SimpleDirectoryReader + Data Connectors
# Level5 mein: PyPDFLoader, TextLoader, WebBaseLoader manually
# LlamaIndex mein: SimpleDirectoryReader sab kuch auto-detect karta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: SimpleDirectoryReader + Data Connectors")
print("=" * 65)

READER_CODE = '''\
from llama_index.core import SimpleDirectoryReader

# ===== FOLDER SE LOAD =====
# PDF, .txt, .md, .docx, .pptx, .csv — auto-detect karta hai!
reader = SimpleDirectoryReader(
    input_dir="./my_documents",
    recursive=True,                      # subfolders bhi
    required_exts=[".pdf", ".txt", ".md"],
    filename_as_id=True,                 # doc ID = filename
    num_files_limit=100,                 # max files
)
documents = reader.load_data()
print(f"Loaded: {len(documents)} documents")

# ===== SPECIFIC FILES =====
reader2 = SimpleDirectoryReader(
    input_files=[
        "./docs/company_policy.pdf",
        "./docs/technical_spec.md",
        "./data/faq.txt",
    ]
)

# ===== WEB PAGE READER =====
# pip install llama-index-readers-web
from llama_index.readers.web import SimpleWebPageReader
web_reader = SimpleWebPageReader(html_to_text=True)
web_docs = web_reader.load_data(
    urls=["https://docs.python.org/3/", "https://fastapi.tiangolo.com/"]
)

# ===== DATABASE READER =====
# from llama_index.readers.database import DatabaseReader
# reader = DatabaseReader(uri="postgresql://user:pass@localhost/mydb")
# docs = reader.load_data(query="SELECT title, content FROM articles")

# ===== GITHUB / NOTION / SLACK readers =====
# LlamaHub pe 100+ readers available hain!
# pip install llama-index-readers-github
# pip install llama-index-readers-notion
# pip install llama-index-readers-slack

# ===== INGESTION PIPELINE (advanced) =====
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.extractors import TitleExtractor  # LLM-based

pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),  # chunking
        TitleExtractor(nodes=5),   # LLM se document title extract karo
        embed_model,               # Settings.embed_model
    ]
)
nodes = pipeline.run(documents=documents)
'''
print(READER_CODE)

# Mock: demonstrate in-memory documents
print("\n  [Mock Demo] In-memory documents (no disk reads needed):")

SAMPLE_DOCS_TEXT = [
    {
        "text": (
            "Python is a high-level interpreted programming language. "
            "Created by Guido van Rossum in 1991. "
            "Python emphasizes code readability and simplicity. "
            "It supports multiple programming paradigms."
        ),
        "metadata": {"source": "python_overview.txt", "topic": "programming"},
    },
    {
        "text": (
            "FastAPI is a modern web framework for building APIs with Python. "
            "It is based on standard Python type hints. "
            "FastAPI provides automatic API documentation via Swagger UI. "
            "Performance comparable to NodeJS and Go."
        ),
        "metadata": {"source": "fastapi_intro.md", "topic": "web-framework"},
    },
    {
        "text": (
            "LlamaIndex is a RAG-first framework for LLM applications. "
            "It provides abstractions like Document, Node, VectorStoreIndex. "
            "LlamaIndex supports 100+ data connectors via LlamaHub. "
            "Key components: readers, node parsers, indexes, query engines."
        ),
        "metadata": {"source": "llamaindex_overview.md", "topic": "ai-framework"},
    },
    {
        "text": (
            "Vector databases store high-dimensional embeddings. "
            "Similarity search finds nearest neighbors via cosine or dot product. "
            "Popular options: Chroma, Pinecone, Weaviate, Qdrant, pgvector. "
            "Used in RAG pipelines for semantic document retrieval."
        ),
        "metadata": {"source": "vector_db_notes.txt", "topic": "databases"},
    },
]

print(f"  Sample documents created: {len(SAMPLE_DOCS_TEXT)}")
for d in SAMPLE_DOCS_TEXT:
    print(f"    -> {d['metadata']['source']} | topic: {d['metadata']['topic']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: VectorStoreIndex — Build + Query
# Level5 mein manually: embed -> faiss.add -> faiss.search
# LlamaIndex mein: sab internally manage hota hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: VectorStoreIndex — Build + Query")
print("=" * 65)

INDEX_CODE = '''\
from llama_index.core import VectorStoreIndex, Document, Settings, StorageContext
from llama_index.core import load_index_from_storage
import os

# Settings already set hain (Section 2 mein)

# ===== STEP 1: Documents =====
docs = [Document(text=d["text"], metadata=d["metadata"]) for d in SAMPLE_DOCS_TEXT]

# ===== STEP 2: Index banao (in-memory) =====
# Internally: chunk -> embed -> store in SimpleVectorStore
index = VectorStoreIndex.from_documents(
    docs,
    show_progress=True,   # progress bar dikhega
)

# ===== STEP 3: Persist to disk =====
PERSIST_DIR = "./my_index_storage"
index.storage_context.persist(persist_dir=PERSIST_DIR)
print(f"Index saved to {PERSIST_DIR}/")
# Files created:
#   docstore.json   — original documents
#   index_store.json — index metadata
#   vector_store.json — embeddings

# ===== STEP 4: Reload (next session mein) =====
storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
loaded_index = load_index_from_storage(storage_context)
print("Index reloaded — no re-embedding needed!")

# ===== STEP 5: Query =====
query_engine = loaded_index.as_query_engine(
    similarity_top_k=3,
)
response = query_engine.query("What is Python used for?")
print(f"Answer: {response}")
print(f"Sources: {[n.metadata['source'] for n in response.source_nodes]}")

# ===== CHROMA (production vector store) =====
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection("my_docs")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_ctx = StorageContext.from_defaults(vector_store=vector_store)

chroma_index = VectorStoreIndex.from_documents(
    docs,
    storage_context=storage_ctx,
)
# Chroma automatically persist karta hai
'''
print(INDEX_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Query Engine + Response Modes
# Level5 mein: RetrievalQA (basic), manually chain banate the
# LlamaIndex mein: multiple response modes built-in
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: QueryEngine + ResponseModes + Postprocessors")
print("=" * 65)

QUERY_ENGINE_CODE = '''\
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.response_synthesizers import get_response_synthesizer, ResponseMode
from llama_index.core.postprocessor import (
    SimilarityPostprocessor,
    KeywordNodePostprocessor,
    LLMRerank,
)

# ===== RETRIEVER =====
# Sirf retrieve karo (no synthesis)
retriever = VectorIndexRetriever(
    index=index,
    similarity_top_k=5,
)
nodes = retriever.retrieve("What are popular vector databases?")
for node in nodes:
    print(f"  Score: {node.score:.3f} | {node.text[:80]}...")

# ===== RESPONSE MODES =====
# COMPACT:        pehle nodes compact karo, phir ek call mein answer
# REFINE:         har node pe iteratively refine (best quality, slow)
# TREE_SUMMARIZE: tree-based summarization (large document sets ke liye)
# SIMPLE_SUMMARIZE: sirf concatenate + summarize (fastest)
# NO_TEXT:        sirf nodes return karo (no LLM synthesis)
# ACCUMULATE:     har node pe alag answer, phir combine

synthesizer = get_response_synthesizer(
    response_mode=ResponseMode.COMPACT,
    verbose=True,
)

# ===== NODE POSTPROCESSORS =====
# Retrieved nodes ko filter/transform BEFORE synthesis
postprocessors = [
    SimilarityPostprocessor(similarity_cutoff=0.65),  # low score remove karo
    # KeywordNodePostprocessor(required_keywords=["python"]),  # keyword filter
    # LLMRerank(top_n=3),   # expensive but best quality reranking
]

# ===== FULL QUERY ENGINE =====
query_engine = RetrieverQueryEngine(
    retriever=retriever,
    response_synthesizer=synthesizer,
    node_postprocessors=postprocessors,
)

response = query_engine.query("Compare Python with other languages")
print(f"Answer: {response}")
print(f"\\nSources used: {len(response.source_nodes)}")

# ===== SHORTCUTS (most common) =====
# as_query_engine = retriever + synthesizer combined
qe = index.as_query_engine(
    similarity_top_k=3,
    response_mode="compact",
    streaming=True,         # stream tokens
    verbose=True,
)

# Streaming
stream_response = qe.query("What is LlamaIndex?")
stream_response.print_response_stream()

# as_retriever = sirf retriever
retriever_only = index.as_retriever(similarity_top_k=5)
'''
print(QUERY_ENGINE_CODE)

print("\n  Response Modes comparison:")
RESPONSE_MODES = {
    "COMPACT":          "Best default — nodes ko compact karo, ek LLM call",
    "REFINE":           "Best quality — har node pe iteratively refine (slow)",
    "TREE_SUMMARIZE":   "Large docs — tree mein summarize karo",
    "SIMPLE_SUMMARIZE": "Fastest — sirf concatenate + one-shot summary",
    "NO_TEXT":          "Sirf nodes return karo — bina LLM synthesis",
    "ACCUMULATE":       "Har node pe alag answer, phir combine",
}
for mode, desc in RESPONSE_MODES.items():
    print(f"  {mode:<22}: {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Chat Engine — Conversation Memory
# Level5 mein: manually ConversationBufferMemory + history inject karte the
# LlamaIndex mein: as_chat_engine() — memory built-in
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: ChatEngine — Conversation with Memory")
print("=" * 65)

CHAT_ENGINE_CODE = '''\
from llama_index.core.memory import ChatMemoryBuffer

# ===== CHAT ENGINE =====
memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

chat_engine = index.as_chat_engine(
    chat_mode="condense_plus_context",   # best mode
    memory=memory,
    system_prompt=(
        "You are a helpful tech assistant. "
        "Answer based on the provided documents. "
        "If you don\'t know, say so clearly."
    ),
    verbose=True,
)

# ===== CONVERSATION =====
# Turn 1
r1 = chat_engine.chat("What is Python?")
print(f"User: What is Python?")
print(f"Bot: {r1}")

# Turn 2 — pichli conversation ka context yaad rahega
r2 = chat_engine.chat("What are its main use cases?")
print(f"User: What are its main use cases?")
print(f"Bot: {r2}")

# Turn 3 — "it" ko Python samjhega (context se)
r3 = chat_engine.chat("Is it good for web development?")
print(f"User: Is it good for web development?")
print(f"Bot: {r3}")

# Reset conversation
chat_engine.reset()

# ===== CHAT MODES =====
# "condense_plus_context": history condense -> retrieve -> answer (RECOMMENDED)
# "condense_question":     history se condensed query -> retrieve -> answer
# "context":               retrieve every turn, system prompt mein add karo
# "simple":                no retrieval, sirf LLM + memory
# "react":                 ReAct agent with index as tool
# "best":                  auto-select

# ===== STREAMING CHAT =====
streaming_chat = index.as_chat_engine(chat_mode="condense_plus_context")
stream_resp = streaming_chat.stream_chat("Explain LlamaIndex briefly")
for token in stream_resp.response_gen:
    print(token, end="", flush=True)
print()  # newline
'''
print(CHAT_ENGINE_CODE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: SubQuestion + Router Query Engines
# Ye LlamaIndex ka USP hai — LangChain mein manually implement karna padta hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: SubQuestionQueryEngine + RouterQueryEngine")
print("=" * 65)

ADVANCED_QE_CODE = '''\
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import SubQuestionQueryEngine, RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector, LLMMultiSelector

# Multiple indexes — alag topics ke liye
# (production mein alag files hote hain, yahan mock)
python_index = VectorStoreIndex.from_documents(python_docs)
fastapi_index = VectorStoreIndex.from_documents(fastapi_docs)
vector_db_index = VectorStoreIndex.from_documents(vector_db_docs)

# ===== TOOLS (index ko tool ke roop mein wrap karo) =====
tools = [
    QueryEngineTool(
        query_engine=python_index.as_query_engine(),
        metadata=ToolMetadata(
            name="python_knowledge",
            description="Python language, syntax, stdlib, paradigms ke baare mein",
        ),
    ),
    QueryEngineTool(
        query_engine=fastapi_index.as_query_engine(),
        metadata=ToolMetadata(
            name="fastapi_knowledge",
            description="FastAPI framework, endpoints, Pydantic, async ke baare mein",
        ),
    ),
    QueryEngineTool(
        query_engine=vector_db_index.as_query_engine(),
        metadata=ToolMetadata(
            name="vector_db_knowledge",
            description="Vector databases (Chroma, Pinecone, Qdrant) ke baare mein",
        ),
    ),
]

# ===== SUB-QUESTION QUERY ENGINE =====
# Complex query ko LLM automatically decompose karta hai sub-questions mein
# Har sub-question sahi tool pe jaata hai
# Sab answers combine hokar final response banta hai

sub_q_engine = SubQuestionQueryEngine.from_defaults(
    query_engine_tools=tools,
    verbose=True,           # sub-questions dikhao
    use_async=True,         # parallel queries
)

# Example: ye automatically 2 sub-questions generate karta hai
response = sub_q_engine.query(
    "How does Python\'s async support compare to how FastAPI uses async for APIs?"
)
# Internal:
#   Sub-Q 1: "How does Python handle async programming?" -> python_knowledge
#   Sub-Q 2: "How does FastAPI use async for API endpoints?" -> fastapi_knowledge
#   Final: Combine + synthesize
print(response)

# ===== ROUTER QUERY ENGINE =====
# Single best tool select karo (not multiple)
router_engine = RouterQueryEngine.from_defaults(
    query_engine_tools=tools,
    selector=LLMSingleSelector.from_defaults(),  # ek select karega
    verbose=True,
)

# Router automatically select karega sahi index
response = router_engine.query("What vector store should I use for production?")
# -> vector_db_knowledge select hoga
print(response)

# Multi-selector: multiple tools choose kar sakta hai
multi_router = RouterQueryEngine.from_defaults(
    query_engine_tools=tools,
    selector=LLMMultiSelector.from_defaults(),
)
'''
print(ADVANCED_QE_CODE)

print("\n  SubQuestion vs Router — kab kya use karo:")
ROUTING_COMPARISON = {
    "SubQuestionQueryEngine": "Complex multi-part queries. Multiple indexes parallel mein query hote hain.",
    "RouterQueryEngine":      "Single-topic queries. Best matching index select karo.",
    "LlamaIndex advantage":   "Dono built-in hain! LangChain mein manually implement karna padta.",
}
for k, v in ROUTING_COMPARISON.items():
    print(f"  {k:<28}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Complete RAG-over-Local-Docs DEMO
# Keys milne pe live run hoga, nahi to structure dikhaenge
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 8: Complete RAG Demo")
print("=" * 65)

LIVE_MODE = LLAMA_AVAILABLE and bool(OPENAI_KEY or GROQ_KEY)

if not LIVE_MODE:
    print("  [STRUCTURE MODE] — API key / llama-index not available")
    print("  Full pipeline structure:")
    print()

    COMPLETE_PIPELINE = '''\
  # ===== PRODUCTION RAG PIPELINE =====
  import os
  from llama_index.core import (
      VectorStoreIndex, SimpleDirectoryReader, Settings,
      StorageContext, load_index_from_storage,
  )
  from llama_index.core.node_parser import SentenceSplitter
  from llama_index.core.postprocessor import SimilarityPostprocessor
  from llama_index.core.memory import ChatMemoryBuffer
  from llama_index.llms.openai import OpenAI
  from llama_index.embeddings.openai import OpenAIEmbedding

  # 1. Global Settings
  Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
  Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
  Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)

  # 2. Load ya Build Index
  PERSIST_DIR = "./storage"
  if not os.path.exists(PERSIST_DIR):
      docs = SimpleDirectoryReader("./my_docs", recursive=True).load_data()
      print(f"Loaded {len(docs)} documents")
      index = VectorStoreIndex.from_documents(docs, show_progress=True)
      index.storage_context.persist(persist_dir=PERSIST_DIR)
  else:
      ctx = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
      index = load_index_from_storage(ctx)

  # 3. Query Engine
  qe = index.as_query_engine(
      similarity_top_k=5,
      node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.65)],
      response_mode="compact",
  )
  r = qe.query("What are the key topics in these documents?")
  print(r)
  for node in r.source_nodes:
      print(f"  [{node.score:.2f}] {node.metadata.get('file_name')} | {node.text[:60]}...")

  # 4. Chat Engine (with memory)
  mem = ChatMemoryBuffer.from_defaults(token_limit=3900)
  ce = index.as_chat_engine(
      chat_mode="condense_plus_context",
      memory=mem,
      system_prompt="You are a helpful assistant."
  )
  r1 = ce.chat("What is the main topic?")
  r2 = ce.chat("Can you elaborate on that?")   # context yaad rahega
  '''
    print(COMPLETE_PIPELINE)

    print("\n  To activate live mode:")
    print("  export OPENAI_API_KEY=sk-...")
    print("  pip install llama-index llama-index-embeddings-openai llama-index-llms-openai")
    print("  Then re-run this script")

else:
    # Live demo with available API
    print("  [LIVE MODE] Running with available API...")

    try:
        from llama_index.core import VectorStoreIndex, Document, Settings

        # Detect which LLM we have
        if OPENAI_KEY:
            from llama_index.llms.openai import OpenAI as LlamaOpenAI
            from llama_index.embeddings.openai import OpenAIEmbedding

            Settings.llm = LlamaOpenAI(model="gpt-4o-mini", temperature=0)
            Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
            print("  Using OpenAI LLM + embeddings")
        else:
            # Try HuggingFace embeddings (free, local)
            try:
                from llama_index.embeddings.huggingface import HuggingFaceEmbedding

                Settings.embed_model = HuggingFaceEmbedding(
                    model_name="BAAI/bge-small-en-v1.5"
                )
                print("  Using HuggingFace embeddings (no API key needed)")
            except ImportError:
                print("  llama-index-embeddings-huggingface not installed")
                print("  pip install llama-index-embeddings-huggingface")
                print("  Skipping live demo")
                LIVE_MODE = False

        if LIVE_MODE:
            # Build index from in-memory documents
            docs = [
                Document(
                    text=d["text"],
                    metadata=d["metadata"],
                )
                for d in SAMPLE_DOCS_TEXT
            ]

            print(f"\n  Building index from {len(docs)} documents...")
            index = VectorStoreIndex.from_documents(docs)
            print("  Index built!")

            # Query Engine
            qe = index.as_query_engine(similarity_top_k=2, response_mode="compact")

            questions = [
                "What is FastAPI?",
                "How do vector databases work?",
                "What makes LlamaIndex useful for RAG?",
            ]

            for q in questions:
                print(f"\n  Q: {q}")
                resp = qe.query(q)
                print(f"  A: {resp}")
                print(f"  Sources: {[n.metadata.get('source') for n in resp.source_nodes]}")

    except Exception as e:
        print(f"  Live demo error: {e}")
        print("  Continuing with structure mode...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: LlamaIndex vs LangChain — Final Comparison
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 9: LlamaIndex vs LangChain — Comparison")
print("=" * 65)

print("""
  ARCHITECTURE:

  LangChain RAG (Level7/01):
    TextLoader -> CharacterTextSplitter -> OpenAIEmbeddings
    -> FAISS/Chroma -> retriever.invoke() -> LCEL chain -> answer
    Memory: ConversationBufferMemory (manual)
    Multi-index: manually implement karo

  LlamaIndex RAG:
    SimpleDirectoryReader -> SentenceSplitter (via Settings)
    -> VectorStoreIndex (embed+store auto) -> as_query_engine()
    Memory: as_chat_engine() (built-in!)
    Multi-index: SubQuestionQueryEngine / RouterQueryEngine (built-in!)

  FEATURE MATRIX:
  Feature                    LangChain   LlamaIndex
  ─────────────────────────────────────────────────
  RAG focus                  Medium      HIGH
  Sub-question decomposition Manual      Built-in
  Multi-index routing        Manual      Built-in
  Conversation + RAG memory  Manual      Built-in
  Node relationships         No          Yes (prev/next/source)
  Hierarchical indexing      No          Yes
  Response modes (REFINE..)  No          Built-in
  Data connectors            50+         100+ (LlamaHub)
  Agents + tools             STRONG      Moderate
  LCEL / chain composition   Yes         No (not LlamaIndex's focus)
  Community size             Larger      Growing fast
  Learning curve             Moderate    Moderate

  DECISION GUIDE:
  "Sirf RAG chahiye, production grade"     -> LlamaIndex
  "Complex agents + tools + RAG"           -> LangChain + LangGraph
  "Multi-doc routing built-in chahiye"     -> LlamaIndex
  "Prompt optimization chahiye"            -> DSPy (Level7/06)
  "Multi-agent team"                       -> CrewAI (Level7/05)
  "Custom LCEL chains"                     -> LangChain

  BOTH CAN COEXIST:
  LlamaIndex as retrieval engine + LangChain as orchestrator
  LlamaIndex QueryEngine -> LangChain tool mein wrap karo
""")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("LLAMAINDEX INTERVIEW SUMMARY")
print("=" * 65)
print("""
  Core Abstractions:
    Document         = raw input with metadata
    Node/TextNode    = chunked piece with ID + relationships
    Settings         = global LLM + embed config (ek jagah)
    VectorStoreIndex = build + store embeddings
    StorageContext   = backend ko swap karne ki jagah (Chroma, Pinecone)
    QueryEngine      = retrieve + synthesize (as_query_engine())
    ChatEngine       = RAG + conversation memory (as_chat_engine())
    Retriever        = sirf similarity search (as_retriever())
    SubQuestionEngine= complex query -> sub-questions -> combine
    RouterQueryEngine= query -> best index select

  Key Flow:
    Files -> SimpleDirectoryReader -> Documents
    Documents -> SentenceSplitter -> Nodes
    Nodes -> embed_model -> embeddings
    Embeddings -> VectorStoreIndex (+ StorageContext)
    Index -> as_query_engine() -> answer
    Index -> as_chat_engine()  -> conversational answer

  vs LangChain:
    LlamaIndex = RAG specialist (more abstractions for retrieval)
    LangChain  = generalist (agents, chains, large ecosystem)

  vs Level5 RAG (manual):
    Level5: manually chunk -> embed -> search -> synthesize
    LlamaIndex: same concepts but organized, reusable, production-ready

  Install:
    pip install llama-index
    pip install llama-index-embeddings-openai llama-index-llms-openai
    pip install llama-index-embeddings-huggingface  (free! local)
""")
print("=" * 65)
print("EXIT 0 — LlamaIndex practical lab complete!")
