# LlamaIndex — RAG-First Framework (Documents, Nodes, VectorStoreIndex, Query Engine)

## Quick Concepts
- **LlamaIndex** = RAG-first Python framework — documents load karo, index banao, query karo
- **Document** = raw data ka wrapper (text + metadata) — PDF, web page, CSV sab
- **Node** = chunked document piece — actual indexing unit with embeddings
- **VectorStoreIndex** = nodes ko embed karke vector store mein store karo
- **Settings** = global config (LLM, embed model, chunk size) — ek jagah set karo
- **QueryEngine** = retrieve + synthesize — "answer my question" interface
- **Key insight**: LangChain generalist hai, LlamaIndex RAG/indexing specialist hai

---

## LlamaIndex vs LangChain — Kab Kya Use Karo?

```
LlamaIndex (llama-index >= 0.10):
  RAG ko seriously build karna hai               -> LlamaIndex
  Complex indexing (hierarchical, multi-doc)     -> LlamaIndex
  Sub-question decomposition built-in chahiye    -> LlamaIndex
  Router/query engine switching chahiye          -> LlamaIndex
  Document ingestion pipeline + node parsers     -> LlamaIndex
  Fine-grained retrieval control                 -> LlamaIndex

LangChain:
  General agent + tool use                       -> LangChain
  Quick prototype + large ecosystem              -> LangChain
  LCEL chaining + callbacks                      -> LangChain
  Multi-step workflow with LangGraph             -> LangGraph

DECISION:
  "Sirf RAG chahiye, production quality"         -> LlamaIndex
  "Agent + tools + RAG mix"                      -> LangChain / LangGraph
  "Complex multi-agent team"                     -> CrewAI
  "Prompt optimization"                          -> DSPy

Remember Level5 RAG kya tha? Chunking -> Embedding -> VectorStore -> Retrieve -> Synthesize
LlamaIndex yahi karta hai but with much richer abstractions.
```

---

## Andar kya hota hai — Index build hota kaise hai, aur Query Engine ke andar kya chalta hai

### `VectorStoreIndex.from_documents(docs)` — 4 real steps

```
1. NodeParser (SentenceSplitter, default)
   Har Document → chunk karke Node objects (Level5 wali chunking, yahan wrap ki gayi hai)

2. Embedding
   Har Node.text → configured embed model se call → vector nikalta hai

3. Storage — DO jagah, ek saath
   a) Vector store: Node.id_ + vector (similarity search ke liye)
   b) Docstore: Node.id_ + poora text+metadata (retrieval ke baad full content chahiye)

4. Index object ban gaya — dono stores ko point karta hai
```

### `index.as_query_engine()` = Retriever + ResponseSynthesizer

```
QueryEngine.query(question):
    nodes = retriever.retrieve(question)       # default: top-k cosine similarity search
    response = synthesizer.synthesize(question, nodes)
    return response
```

### Response synthesis modes — DIFFERENT ALGORITHMS, ek config-flag nahi

Ye asli interview differentiator hai — "response_mode" sirf ek setting nahi, poora alag execution path hai:

**`compact`** (default) — jitne retrieved nodes ek prompt mein fit ho jaayein, sab ek saath
stuff karo, **1 LLM call**.
```
Prompt: "Context: [node1][node2][node3]\nQuestion: {q}\nAnswer:"
→ 1 LLM call
```

**`refine`** — nodes ko ONE AT A TIME process karo, sequentially:
```
node1 → LLM call 1: "Answer using this context: {node1}"        → initial_answer
node2 → LLM call 2: "Existing answer: {initial_answer}
                      New context: {node2}
                      Refine the answer if needed:"              → refined_answer
node3 → LLM call 3: "Existing answer: {refined_answer}
                      New context: {node3}
                      Refine the answer if needed:"              → final_answer
```
N nodes = N sequential LLM calls. Zyada accurate (har node explicitly consider hota hai) par
slower + costlier — production mein latency/cost trade-off explicitly justify karna padega.

**`tree_summarize`** — nodes ko tree mein bottom-up combine karo (map-reduce style): pehle
groups mein summarize, phir un summaries ko aur summarize, jab tak ek final answer na bache.
Bahut zyada retrieved nodes (jaise 50+) ke liye best — `refine` sequential O(n) LLM calls se
better scale karta hai.

**Interview me bolne wali line:** "Index build ek 3-step pipeline hai — parse, embed, dual
storage (vector + docstore). Query engine ek retriever + synthesizer hai, aur response_mode
sirf setting nahi — compact ek call, refine N sequential calls jo pichla answer refine karte
hain, tree_summarize map-reduce tree — teeno ka cost/accuracy trade-off alag hai."

---

## Interview Questions & Answers

### Q1: LlamaIndex kya hai? Basic Document -> Index -> Query flow?
**Answer:**
```python
# pip install llama-index
# pip install llama-index-embeddings-openai llama-index-llms-openai
# (ya huggingface, groq, ollama wale pakages bhi hain)

from llama_index.core import (
    VectorStoreIndex,
    Document,
    Settings,
    SimpleDirectoryReader,
)
from llama_index.core.node_parser import SentenceSplitter

# ===== STEP 1: Settings configure karo (global config) =====
# ye Level5 mein jo manually karte the (chunk size, embed model)
# wahi yahan centralize ho gaya

from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

Settings.llm = LlamaOpenAI(model="gpt-4o-mini", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
Settings.chunk_size = 512        # node ka size (tokens)
Settings.chunk_overlap = 50      # overlap between chunks

# ===== STEP 2: Documents banao =====
# Document = text + metadata
# Level5 mein ye manually string hoti thi, yahan rich object hai

docs = [
    Document(
        text="Python is a high-level interpreted language created by Guido van Rossum.",
        metadata={"source": "python_intro.txt", "topic": "programming"},
    ),
    Document(
        text="FastAPI is a modern web framework for building APIs with Python.",
        metadata={"source": "fastapi_intro.txt", "topic": "web"},
    ),
    Document(
        text="LlamaIndex is a RAG framework for building LLM applications over your data.",
        metadata={"source": "llamaindex_intro.txt", "topic": "ai"},
    ),
]

# ===== STEP 3: Index banao =====
# Internally:
#   1. Documents -> Nodes (chunking via SentenceSplitter)
#   2. Nodes -> Embeddings (via Settings.embed_model)
#   3. Embeddings -> VectorStore (default: in-memory SimpleVectorStore)

index = VectorStoreIndex.from_documents(docs)

# ===== STEP 4: Query Engine banao =====
query_engine = index.as_query_engine()

# ===== STEP 5: Query karo =====
response = query_engine.query("What is FastAPI?")
print(response)
# "FastAPI is a modern web framework for building APIs with Python."

print(response.source_nodes)   # retrieved nodes with scores
print(response.metadata)       # source metadata
```

---

### Q2: SimpleDirectoryReader — local files load karna?
**Answer:**
```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

# ===== DIRECTORY SE LOAD =====
# PDF, .txt, .md, .docx — sab automatically handle karta hai
# Level5 mein manual PyPDFLoader lagata tha, yahan automatic hai

reader = SimpleDirectoryReader(
    input_dir="./my_docs",          # folder path
    recursive=True,                  # subfolders bhi
    required_exts=[".pdf", ".txt"],  # sirf ye extensions
    filename_as_id=True,             # document ID = filename
)

documents = reader.load_data()
print(f"Loaded {len(documents)} documents")
print(documents[0].metadata)  # {'file_path': ..., 'file_name': ..., 'file_type': ...}

# ===== SPECIFIC FILES =====
reader_specific = SimpleDirectoryReader(
    input_files=["./docs/ml_paper.pdf", "./docs/notes.txt"]
)
docs = reader_specific.load_data()

# ===== WEB / URL READER (Data Connectors) =====
# LlamaIndex ke paas 100+ data connectors/readers hain (LlamaHub)
from llama_index.readers.web import SimpleWebPageReader  # pip install llama-index-readers-web

web_reader = SimpleWebPageReader(html_to_text=True)
web_docs = web_reader.load_data(urls=["https://docs.python.org/3/"])

# Database reader, Notion reader, Slack reader — sab available hai
# LlamaHub pe: https://llamahub.ai/

# ===== INGESTION PIPELINE (advanced) =====
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.extractors import TitleExtractor, QuestionsAnsweredExtractor

# Pipeline = transforms sequentially apply karo documents pe
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),  # chunking
        TitleExtractor(),      # LLM se title extract karo metadata mein
        # QuestionsAnsweredExtractor(),  # LLM se Q&A extract (expensive)
        OpenAIEmbedding(),     # embed karo
    ]
)
nodes = pipeline.run(documents=documents)
print(f"Created {len(nodes)} nodes")
```

---

### Q3: Documents, Nodes, Node Parsers — core abstractions?
**Answer:**
```python
from llama_index.core import Document
from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
from llama_index.core.node_parser import (
    SentenceSplitter,          # sentence boundary pe split
    TokenTextSplitter,         # fixed token count pe split
    SemanticSplitterNodeParser,# semantic similarity se split (smart!)
    SentenceWindowNodeParser,  # window of surrounding sentences
    HierarchicalNodeParser,    # multi-level hierarchy (chapter -> section -> para)
)

# ===== DOCUMENT =====
doc = Document(
    text="LlamaIndex makes RAG easy. It provides abstractions...",
    doc_id="llamaindex_v1",
    metadata={
        "source": "website",
        "author": "Jerry Liu",
        "date": "2024-01-01",
    },
    excluded_llm_metadata_keys=["date"],   # LLM ko ye metadata mat dikhao
    excluded_embed_metadata_keys=["author"], # embedding mein ye skip karo
)

# ===== NODE =====
# Document -> Nodes (chunking ke baad)
splitter = SentenceSplitter(chunk_size=256, chunk_overlap=20)
nodes = splitter.get_nodes_from_documents([doc])

for node in nodes:
    print(node.node_id)        # unique ID
    print(node.text[:100])     # chunk text
    print(node.metadata)       # inherited from document
    print(node.embedding)      # vector (None until indexed)

# Nodes mein relationships bhi hoti hain
# node.relationships = {
#   NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc.doc_id),
#   NodeRelationship.PREVIOUS: RelatedNodeInfo(node_id="prev_node_id"),
#   NodeRelationship.NEXT: RelatedNodeInfo(node_id="next_node_id"),
# }

# ===== SENTENCE WINDOW (Context augmentation) =====
# Level5 advanced retrieval mein ye tha
# Retrieve karo small chunk, but LLM ko surrounding window do
window_parser = SentenceWindowNodeParser.from_defaults(
    window_size=3,            # 3 sentences left + right include karo
    window_metadata_key="window",
    original_text_metadata_key="original_text",
)
window_nodes = window_parser.get_nodes_from_documents([doc])

# ===== HIERARCHICAL NODE PARSER =====
# Parent-child hierarchy banata hai
# Retrieval: child chunk retrieve karo, but parent context do (small-to-big)
hier_parser = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[2048, 512, 128]  # chapter -> section -> paragraph
)
hier_nodes = hier_parser.get_nodes_from_documents([doc])
```

---

### Q4: VectorStoreIndex aur Storage Context — vector stores plug-in karna?
**Answer:**
```python
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.core.vector_stores import SimpleVectorStore

# ===== DEFAULT (in-memory) =====
# SimpleVectorStore — prototype ke liye
index = VectorStoreIndex.from_documents(docs)

# ===== PERSIST TO DISK =====
# Index save karo taaki dobara embed na karna pade
index.storage_context.persist(persist_dir="./storage")

# Load back
from llama_index.core import load_index_from_storage

storage_context = StorageContext.from_defaults(persist_dir="./storage")
loaded_index = load_index_from_storage(storage_context)

# ===== CHROMA (production) =====
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

chroma_client = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = chroma_client.get_or_create_collection("my_docs")

vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_documents(
    docs,
    storage_context=storage_context,
)

# ===== PINECONE =====
# from llama_index.vector_stores.pinecone import PineconeVectorStore
# import pinecone
# pinecone.init(api_key="...", environment="...")
# pinecone_index = pinecone.Index("my-index")
# vector_store = PineconeVectorStore(pinecone_index=pinecone_index)

# ===== WEAVIATE, QDRANT, REDIS, POSTGRES pgvector =====
# Sab available hain as llama-index-vector-stores-* packages

# ===== StorageContext — components ka container =====
# StorageContext manages:
#   - vector_store: embeddings store karta hai
#   - docstore: original documents store karta hai
#   - index_store: index metadata store karta hai
#   - graph_store: graph relationships (optional)

storage_ctx = StorageContext.from_defaults(
    vector_store=vector_store,
    docstore=SimpleDocumentStore(),
    index_store=SimpleIndexStore(),
)
```

---

### Q5: Query Engine, Retriever, Response Synthesizer — retrieval pipeline?
**Answer:**
```python
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import (
    ResponseMode,
    get_response_synthesizer,
)
from llama_index.core.postprocessor import (
    SimilarityPostprocessor,    # score threshold se filter
    MetadataReplacementPostProcessor,  # sentence window ke liye
    LLMRerank,                  # LLM se rerank karo
)

index = VectorStoreIndex.from_documents(docs)

# ===== RETRIEVER (retrieval part) =====
retriever = VectorIndexRetriever(
    index=index,
    similarity_top_k=5,     # top 5 nodes retrieve karo
)

retrieved_nodes = retriever.retrieve("What is Python?")
for node in retrieved_nodes:
    print(f"Score: {node.score:.3f} | Text: {node.text[:80]}")

# ===== RESPONSE SYNTHESIZER (synthesis part) =====
# ResponseMode options:
#   REFINE:        iteratively refine answer with each node
#   COMPACT:       pehle nodes ko compact karo, phir answer
#   TREE_SUMMARIZE: tree structure mein summarize (large docs ke liye)
#   SIMPLE_SUMMARIZE: sirf concatenate karo
#   NO_TEXT:       sirf nodes return karo, LLM call mat karo
#   ACCUMULATE:    har node pe alag answer, phir combine

synthesizer = get_response_synthesizer(
    response_mode=ResponseMode.COMPACT,
    verbose=True,
)

# ===== NODE POSTPROCESSORS =====
# Retrieved nodes ko filter/rerank karo BEFORE synthesis
postprocessors = [
    SimilarityPostprocessor(similarity_cutoff=0.7),  # low score nodes hata do
    LLMRerank(top_n=3),   # LLM se top 3 rerank karo (expensive but better)
]

# ===== QUERY ENGINE (all-in-one) =====
query_engine = RetrieverQueryEngine(
    retriever=retriever,
    response_synthesizer=synthesizer,
    node_postprocessors=postprocessors,
)

response = query_engine.query("What is Python used for?")
print(str(response))                  # final answer
print(response.source_nodes)          # sources
print(response.metadata)              # metadata

# ===== SHORTCUT (as_query_engine) =====
# Index directly se query engine banao (most common pattern)
query_engine = index.as_query_engine(
    similarity_top_k=3,
    response_mode="compact",
    streaming=True,           # stream karo tokens
)

# Streaming response
streaming_response = query_engine.query("Explain LlamaIndex")
streaming_response.print_response_stream()  # live print

# ===== RETRIEVER SHORTCUT =====
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve("FastAPI kya hai?")
```

---

### Q6: Chat Engine — conversation memory ke saath RAG?
**Answer:**
```python
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine import (
    CondensePlusContextChatEngine,
    ContextChatEngine,
    SimpleChatEngine,
)
from llama_index.core.llms import ChatMessage, MessageRole

index = VectorStoreIndex.from_documents(docs)

# ===== CONTEXT CHAT ENGINE =====
# Har turn pe retrieve karo + history maintain karo
# Level5 RAG mein ye manually karna padta tha (ConversationBufferMemory)
# LlamaIndex mein built-in hai

memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

chat_engine = index.as_chat_engine(
    chat_mode="condense_plus_context",   # recommended mode
    memory=memory,
    verbose=True,
)

# First message
response1 = chat_engine.chat("Tell me about Python")
print(str(response1))

# Follow-up (memory se context milega)
response2 = chat_engine.chat("What are its main uses?")
print(str(response2))

# Stream
streaming = chat_engine.stream_chat("What about its performance?")
for token in streaming.response_gen:
    print(token, end="", flush=True)

# Reset conversation
chat_engine.reset()

# ===== CHAT MODES =====
# "best":                    auto-select (usually condense_plus_context)
# "condense_question":        history condense karo -> single query -> retrieve -> answer
# "context":                 retrieve every turn, prepend to system prompt
# "condense_plus_context":   condense question THEN retrieve (most accurate)
# "simple":                  sirf LLM, no retrieval
# "react":                   ReAct agent with index as tool

# ===== INITIAL MESSAGES =====
chat_engine2 = index.as_chat_engine(
    chat_mode="best",
    system_prompt="Tum ek helpful Python tutor ho. Hindi-English mix mein jawab do.",
)
```

---

### Q7: Sub-Question Query Engine — complex queries decompose karna?
**Answer:**
```python
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import (
    SubQuestionQueryEngine,
    RouterQueryEngine,
)
from llama_index.core.selectors import LLMSingleSelector, PydanticSingleSelector
from llama_index.core import VectorStoreIndex

# Multiple indexes — alag-alag topics ke liye
# (Level5 mein ye manually implement karna padta tha)
python_index = VectorStoreIndex.from_documents(python_docs)
fastapi_index = VectorStoreIndex.from_documents(fastapi_docs)
ml_index = VectorStoreIndex.from_documents(ml_docs)

# ===== QUERY ENGINE TOOLS =====
tools = [
    QueryEngineTool(
        query_engine=python_index.as_query_engine(),
        metadata=ToolMetadata(
            name="python_docs",
            description="Python language fundamentals, syntax, stdlib ke baare mein",
        ),
    ),
    QueryEngineTool(
        query_engine=fastapi_index.as_query_engine(),
        metadata=ToolMetadata(
            name="fastapi_docs",
            description="FastAPI web framework, endpoints, Pydantic ke baare mein",
        ),
    ),
    QueryEngineTool(
        query_engine=ml_index.as_query_engine(),
        metadata=ToolMetadata(
            name="ml_docs",
            description="Machine learning concepts, scikit-learn, model training",
        ),
    ),
]

# ===== SUB-QUESTION QUERY ENGINE =====
# Complex question -> LLM se sub-questions generate karo
# Har sub-question correct tool pe route karo
# Sab answers combine karo

sub_question_engine = SubQuestionQueryEngine.from_defaults(
    query_engine_tools=tools,
    verbose=True,
)

# Example: ye complex question automatically decompose hoti hai
response = sub_question_engine.query(
    "Compare how Python handles async programming vs how FastAPI uses it for web endpoints"
)
# Internal:
#   Sub-Q 1: "How does Python handle async programming?" -> python_docs
#   Sub-Q 2: "How does FastAPI use async for endpoints?" -> fastapi_docs
#   Then combine!
print(str(response))

# ===== ROUTER QUERY ENGINE =====
# Query ko ek BEST matching tool pe route karo
# vs SubQuestion: wahan multiple tools parallel mein, yahan sirf ek select

router_engine = RouterQueryEngine.from_defaults(
    query_engine_tools=tools,
    selector=LLMSingleSelector.from_defaults(),  # LLM select karega best tool
    verbose=True,
)

response = router_engine.query("What is an API endpoint in FastAPI?")
# Router automatically fastapi_docs select karega
print(str(response))

# Multi-selector (multiple tools choose kar sakta hai)
from llama_index.core.selectors import LLMMultiSelector
from llama_index.core.query_engine import RouterQueryEngine

router_multi = RouterQueryEngine.from_defaults(
    query_engine_tools=tools,
    selector=LLMMultiSelector.from_defaults(),  # ek se zyada select kar sakta hai
)
```

---

### Q8: Embeddings + Custom LLM — different providers use karna?
**Answer:**
```python
from llama_index.core import Settings

# ===== OpenAI =====
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0, max_tokens=512)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small", dimensions=1536)

# ===== Anthropic =====
from llama_index.llms.anthropic import Anthropic

Settings.llm = Anthropic(model="claude-sonnet-4-6", max_tokens=1024)
# Note: Anthropic ke paas embedding model nahi — use OpenAI/HuggingFace for embeddings

# ===== Groq (fast + free tier) =====
from llama_index.llms.groq import Groq

Settings.llm = Groq(model="llama3-70b-8192", api_key="your_groq_key")

# ===== HuggingFace (local, no API cost!) =====
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-small-en-v1.5",  # fast + good quality
)

# Popular HF embedding models:
# BAAI/bge-large-en-v1.5  — highest quality
# BAAI/bge-small-en-v1.5  — fast + small
# sentence-transformers/all-MiniLM-L6-v2 — very fast

# ===== Ollama (local LLM) =====
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.2", request_timeout=60.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

# ===== PER-QUERY override (Settings bypass karo) =====
from llama_index.core import VectorStoreIndex

# Specific query engine ko different LLM do
expensive_llm = OpenAI(model="gpt-4o")
cheap_llm = OpenAI(model="gpt-4o-mini")

query_engine = index.as_query_engine(llm=expensive_llm)  # override for this engine
```

---

### Q9: LlamaIndex vs LangChain RAG — detailed comparison?
**Answer:**
```
ARCHITECTURE COMPARISON:

LangChain RAG (Level7/01 mein padha):
  TextLoader/PyPDFLoader    -> Document
  CharacterTextSplitter     -> chunks
  OpenAIEmbeddings          -> embed
  FAISS/Chroma              -> vector store
  retriever = vectorstore.as_retriever()
  RetrievalQA / LCEL chain  -> answer
  Manual history management (ConversationBufferMemory)

LlamaIndex RAG:
  SimpleDirectoryReader     -> Document (auto file type detect)
  Settings.chunk_size       -> SentenceSplitter (smarter chunking)
  Settings.embed_model      -> embed
  VectorStoreIndex          -> index + storage context
  index.as_query_engine()   -> answer
  index.as_chat_engine()    -> chat with memory (built-in!)
  SubQuestionQueryEngine    -> complex query decomposition (built-in!)

FEATURE COMPARISON:
Feature                     LangChain   LlamaIndex
-----------------------------------|-----------|----------
RAG focus                  | Medium    | HIGH
Sub-question decomposition | Manual    | Built-in
Router (multi-index)       | Manual    | Built-in
Chat memory in RAG         | Manual    | Built-in
Node relationships         | No        | Yes
Hierarchical indexing      | No        | Yes
Sentence window retrieval  | Manual    | Built-in
Response modes (REFINE etc)| No        | Built-in
Data connectors (LlamaHub) | 50+       | 100+
Agent + tools              | STRONG    | Moderate
General ecosystem          | LARGER    | Smaller

WHEN LANGCHAIN WINS:
  - Complex multi-step agents (LangGraph)
  - Tool use + function calling heavy
  - Custom chain composition (LCEL)
  - Large community + integrations needed

WHEN LLAMAINDEX WINS:
  - RAG pe focus hai
  - Multiple document sources + routing
  - Complex queries jo decompose honge
  - Production document Q&A systems
  - Hierarchical document structures

BOTTOM LINE:
  "Sirf RAG chahiye?" -> LlamaIndex
  "RAG + Agents chahiye?" -> LangChain/LangGraph ya dono mix karo
```

---

### Q10: Complete RAG-over-Local-Docs example?
**Answer:**
```python
"""
Production-ready RAG pipeline with LlamaIndex.
Level5 ke concepts (chunking, embedding, retrieval) yahan organized hain.
"""

import os
from pathlib import Path
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# ===== 1. Settings (ek baar globally set karo) =====
Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
Settings.num_output = 512         # max tokens in response
Settings.context_window = 4096   # context window for LLM

# ===== 2. Index banao ya load karo =====
PERSIST_DIR = "./storage"

if not os.path.exists(PERSIST_DIR):
    # First time — docs load karo, index banao, persist karo
    print("Building index from documents...")
    
    # Real files load karo
    documents = SimpleDirectoryReader(
        input_dir="./my_documents",    # apne documents yahan rakhna
        required_exts=[".pdf", ".txt", ".md"],
        recursive=True,
    ).load_data()
    
    print(f"Loaded {len(documents)} documents")
    
    # Index banao (automatically chunking + embedding hogi)
    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True,
    )
    
    # Save karo taaki dobara embed na karna pade
    index.storage_context.persist(persist_dir=PERSIST_DIR)
    print(f"Index saved to {PERSIST_DIR}")
    
else:
    # Already indexed hai, load karo
    print("Loading existing index...")
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)
    print("Index loaded!")

# ===== 3. Query Engine =====
query_engine = index.as_query_engine(
    similarity_top_k=5,
    node_postprocessors=[
        SimilarityPostprocessor(similarity_cutoff=0.65),
    ],
    response_mode="compact",
    streaming=False,
)

# ===== 4. Chat Engine (conversational) =====
from llama_index.core.memory import ChatMemoryBuffer

memory = ChatMemoryBuffer.from_defaults(token_limit=3900)
chat_engine = index.as_chat_engine(
    chat_mode="condense_plus_context",
    memory=memory,
    system_prompt="You are a helpful assistant. Answer based on the provided documents.",
)

# ===== 5. Query karo =====
def ask(question: str):
    response = query_engine.query(question)
    print(f"\nQ: {question}")
    print(f"A: {response}")
    print(f"\nSources ({len(response.source_nodes)}):")
    for i, node in enumerate(response.source_nodes):
        print(f"  [{i+1}] Score: {node.score:.3f} | {node.metadata.get('file_name', 'unknown')}")
        print(f"       {node.text[:100]}...")
    return response

# Usage
r = ask("What are the main features mentioned in the documents?")
r = ask("What technical concepts are covered?")

# Chat usage
chat_response = chat_engine.chat("Tell me about the main topics")
print(chat_response)
follow_up = chat_engine.chat("Can you elaborate on the first topic?")
print(follow_up)  # context maintain hoga!
```

---

## Summary Table

```
LlamaIndex Core Abstractions:

Document         = text + metadata wrapper (raw input)
Node             = chunked piece with relationships + embedding
TextNode         = most common Node type
SentenceSplitter = Document -> Nodes (sentence-aware chunking)
Settings         = global config (LLM, embed_model, chunk_size)
VectorStoreIndex = Nodes -> embeddings -> vector store
StorageContext   = storage backends ka container
QueryEngine      = retrieve + synthesize = final answer
Retriever        = similarity search only (no synthesis)
Synthesizer      = retrieved nodes + query -> answer
ChatEngine       = QueryEngine + conversation memory
SubQuestionEngine= complex query -> sub-questions -> combine
RouterEngine     = query -> best matching index/tool

Flow:
Files -> SimpleDirectoryReader -> Documents
       -> SentenceSplitter -> Nodes
       -> embed_model -> Embeddings
       -> VectorStoreIndex (with StorageContext)
          -> as_query_engine() -> QueryEngine -> Response
          -> as_chat_engine()  -> ChatEngine  -> ChatResponse
          -> as_retriever()    -> Retriever   -> Nodes only
```
