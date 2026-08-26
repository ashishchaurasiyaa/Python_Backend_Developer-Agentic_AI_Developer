# LangChain — Chains, LCEL, Memory, Document Loaders, Callbacks

## Quick Concepts
- **LCEL (LangChain Expression Language)** = `|` operator se chains compose karo — pipe syntax
- **Chain** = prompt + model + output parser — pipeline
- **Memory** = conversation history manage karo — ConversationBufferMemory, Redis
- **Document Loaders** = PDF/web/CSV load karo → chunks → vector store
- **Callbacks** = token counting, logging, tracing — har step pe hooks

---

## Andar kya hota hai — Runnable Protocol, step by step

`prompt | model | parser` dekh ke lagta hai jaise koi magic pipe operator hai. Nahi — LangChain
ke har component (`ChatPromptTemplate`, `ChatOpenAI`, `StrOutputParser`, tools, retrievers, sab)
ek common interface implement karte hain: the **`Runnable` protocol** — `.invoke()`, `.batch()`,
`.stream()`, `.ainvoke()`, `.astream()`. `|` sirf Python ka `__or__` operator overload hai.

### `|` karta kya hai (build time, NOT execution)

```python
chain = prompt | model | parser
# yeh line koi LLM call NAHI karti. Yeh sirf ek object banati hai:
#   RunnableSequence(steps=[prompt, model, parser])
# ek linked-list jaisi pipeline — abhi kuch execute nahi hua.
```

### `.invoke(input)` karta kya hai (execution time)

```
RunnableSequence.invoke(input, config):
    value = input
    for step in self.steps:                 # [prompt, model, parser]
        value = step.invoke(value, config)   # output → next step ka input
    return value
```

Ek plain Python loop hai — har step ka output seedha agle step ka input ban jaata hai. `config`
(callbacks, run_id, tags) **har step ko thread ho ke jaata hai** — isi wajah se ek chain ke beech
mein LangSmith tracing ya token-counting callback lagane ke liye tumhe manually kuch pass nahi
karna padta; `RunnableSequence` khud propagate karta hai.

### Trace — "Explain LCEL" jaise sawaal ke liye

```
Input: {"question": "What is Contextual Retrieval?"}

Step 1 (prompt.invoke):  ChatPromptTemplate formats → ChatPromptValue
                          (system + human messages ban gaye)
Step 2 (model.invoke):   ChatOpenAI ko messages bheje → AIMessage(content="...")
Step 3 (parser.invoke):  StrOutputParser → AIMessage se .content nikal ke plain str return

Output: "Contextual Retrieval is..."
```

### `.batch()` aur `.stream()` — ye "for loop N baar" nahi hain

- `.batch([in1, in2, in3])` — har `Runnable` apni khud ki batching implement karta hai. Model
  wrapper ke liye ye ek single concurrent-request-pool bana sakta hai (thread pool ya async
  gather), sequential invoke() calls nahi. Batching per-step decide hota hai, poori chain ke
  across nahi.
- `.stream()` — pura chain **tabhi** end-to-end stream karega jab **har** step `.transform()`
  implement karta ho (generator-friendly ho). Beech mein ek non-streaming step (jaise koi custom
  function jo pehle poora input collect karta hai) pura streaming break kar dega — silent
  gotcha, production me isko test karna zaroori hai.

### Memory — decorator pattern hai, magic nahi

```python
chain_with_history = RunnableWithMessageHistory(chain, get_session_history, ...)
```

Ye ek **wrapper Runnable** hai: `.invoke()` call hone se pehle session history fetch karke
input mein inject karta hai, aur call ke baad naya turn history store mein append karta hai —
yaani `invoke()` ke around ek before/after hook, chain ke andar koi special memory-object nahi
ghoom raha.

**Interview me bolne wali line:** "LCEL ek pipe syntax nahi hai, ek uniform `Runnable` interface
hai jispe `invoke/batch/stream` sab components consistently implement karte hain — `|` sirf ek
`RunnableSequence` banata hai jo un steps ko loop mein call karta hai."

---

## Interview Questions & Answers

### Q1: LCEL (LangChain Expression Language) kya hai? Basic usage?
**Answer:**
```python
# pip install langchain langchain-anthropic langchain-openai

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# --- LCEL: pipe operator se chain banao ---
model = ChatAnthropic(model="claude-sonnet-4-6")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a Python expert. Answer concisely."),
    ("human", "{question}")
])

# Chain: prompt | model | parser
chain = prompt | model | StrOutputParser()

# Invoke
result = chain.invoke({"question": "What is a generator?"})
print(result)

# Batch invoke (parallel)
results = chain.batch([
    {"question": "What is a decorator?"},
    {"question": "What is async/await?"},
    {"question": "What is a context manager?"},
])

# Stream
for chunk in chain.stream({"question": "Explain metaclasses"}):
    print(chunk, end="", flush=True)

# Async
import asyncio
async def async_chain():
    result = await chain.ainvoke({"question": "What is GIL?"})
    return result

# --- Chaining multiple steps ---
# Step 1: Extract topic
# Step 2: Generate explanation
# Step 3: Format as structured output

extract_prompt = PromptTemplate.from_template(
    "Extract the main programming concept from: {text}\nReturn only the concept name."
)

explain_prompt = PromptTemplate.from_template(
    "Explain {concept} with a Python code example."
)

# Sequential chain
full_chain = (
    extract_prompt
    | model
    | StrOutputParser()
    | (lambda concept: {"concept": concept})
    | explain_prompt
    | model
    | StrOutputParser()
)

result = full_chain.invoke({"text": "I want to understand how Python handles multiple inheritance"})
```

---

### Q2: Memory — conversation history kaise maintain karte hain?
**Answer:**
```python
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import (
    ChatMessageHistory,
    RedisChatMessageHistory,
)
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

model = ChatAnthropic(model="claude-sonnet-4-6")

# In-memory history store
store: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

# Prompt with history placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful Python tutor."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | model | StrOutputParser()

# Wrap with message history
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Conversation — session_id se history track hoti hai
config = {"configurable": {"session_id": "user-123"}}

r1 = chain_with_history.invoke(
    {"input": "My name is Ashish. I'm learning Python."},
    config=config
)

r2 = chain_with_history.invoke(
    {"input": "What's my name?"},  # Context yaad rahega
    config=config
)
print(r2)  # "Your name is Ashish."

# Redis-backed history (production ke liye)
def get_redis_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(
        session_id=session_id,
        url="redis://localhost:6379",
        ttl=3600,  # 1 hour expiry
    )

chain_with_redis = RunnableWithMessageHistory(
    chain,
    get_redis_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Trim history to avoid context overflow
from langchain_core.messages import trim_messages

trimmer = trim_messages(
    max_tokens=4000,
    strategy="last",            # last N tokens rakhte hain
    token_counter=model,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

chain_with_trim = (
    RunnablePassthrough.assign(history=lambda x: trimmer.invoke(x["history"]))
    | prompt
    | model
    | StrOutputParser()
)
```

---

### Q3: Document Loaders aur Text Splitters kaise kaam karte hain?
**Answer:**
```python
from langchain_community.document_loaders import (
    PyPDFLoader,
    WebBaseLoader,
    CSVLoader,
    JSONLoader,
    DirectoryLoader,
    TextLoader,
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_core.documents import Document

# --- PDF Load ---
loader = PyPDFLoader("resume.pdf")
pages = loader.load()  # list[Document] — each page is a Document
print(f"Pages: {len(pages)}")
print(pages[0].page_content[:200])
print(pages[0].metadata)  # {"source": "resume.pdf", "page": 0}

# --- Web Load ---
web_loader = WebBaseLoader("https://docs.python.org/3/tutorial/")
docs = web_loader.load()

# --- CSV Load ---
csv_loader = CSVLoader("data.csv", csv_args={"delimiter": ","})
rows = csv_loader.load()

# --- Directory Load ---
dir_loader = DirectoryLoader(
    "./docs/",
    glob="**/*.md",
    loader_cls=TextLoader,
    show_progress=True,
)
all_docs = dir_loader.load()

# --- Text Splitting ---
# RecursiveCharacterTextSplitter (RECOMMENDED)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,        # characters per chunk
    chunk_overlap=200,      # overlap to maintain context
    separators=["\n\n", "\n", " ", ""],  # try in order
    length_function=len,
)

chunks = splitter.split_documents(pages)
print(f"Chunks: {len(chunks)}")

# Token-based splitting (for LLM token limits)
token_splitter = TokenTextSplitter(
    chunk_size=512,     # tokens
    chunk_overlap=50,
    encoding_name="cl100k_base",
)

# Markdown-aware splitting
headers_to_split_on = [
    ("#", "Header1"),
    ("##", "Header2"),
    ("###", "Header3"),
]
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,
)

# Metadata add karo
for doc in chunks:
    doc.metadata.update({
        "source_type": "pdf",
        "processing_date": "2026-05-19",
    })
```

---

### Q4: Vector Store integration — RAG chain kaise banate hain?
**Answer:**
```python
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma, FAISS
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

# Embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Vector store create karo
# In-memory FAISS
vectorstore = FAISS.from_documents(
    documents=chunks,  # from previous step
    embedding=embeddings,
)

# Persist to disk
vectorstore.save_local("./faiss_index")

# Load from disk
vectorstore = FAISS.load_local(
    "./faiss_index",
    embeddings,
    allow_dangerous_deserialization=True,
)

# Retriever
retriever = vectorstore.as_retriever(
    search_type="similarity",           # similarity, mmr, similarity_score_threshold
    search_kwargs={
        "k": 5,                         # top 5 docs
        "score_threshold": 0.7,         # min similarity
        # "filter": {"source": "resume.pdf"}  # metadata filter
    }
)

# RAG Chain
model = ChatAnthropic(model="claude-sonnet-4-6")

template = """Answer the question based ONLY on the following context:

{context}

Question: {question}

If the answer is not in the context, say "I don't know based on the provided documents."
"""

rag_prompt = ChatPromptTemplate.from_template(template)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# LCEL RAG chain
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | rag_prompt
    | model
    | StrOutputParser()
)

answer = rag_chain.invoke("What is Ashish's total experience?")
print(answer)

# RAG with sources
from langchain_core.runnables import RunnableParallel

rag_chain_with_source = RunnableParallel(
    {"context": retriever, "question": RunnablePassthrough()}
).assign(answer=lambda x: rag_prompt | model | StrOutputParser())
```

---

### Q5: Callbacks — token counting aur logging kaise karte hain?
**Answer:**
```python
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any
import time

# Custom callback
class TokenCountCallback(BaseCallbackHandler):
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.start_time = None

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.start_time = time.time()
        self.calls += 1
        print(f"\n[LLM Call #{self.calls}] Starting...")

    def on_llm_end(self, response: LLMResult, **kwargs):
        duration = time.time() - self.start_time
        if response.llm_output:
            usage = response.llm_output.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            self.total_tokens += tokens
            print(f"[LLM End] Tokens: {tokens}, Duration: {duration:.2f}s")

    def on_chain_error(self, error: Exception, **kwargs):
        print(f"[Error] Chain failed: {error}")

    def on_retriever_end(self, documents, **kwargs):
        print(f"[Retriever] Retrieved {len(documents)} docs")

# Use callback
callback = TokenCountCallback()

result = chain.invoke(
    {"question": "Explain async in Python"},
    config={"callbacks": [callback]}
)

print(f"\nTotal tokens used: {callback.total_tokens}")
print(f"Total calls: {callback.calls}")

# LangSmith tracing (built-in observability)
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls__..."
os.environ["LANGCHAIN_PROJECT"] = "my-rag-app"
# Now all chains are automatically traced in LangSmith

# Async callback
class AsyncStreamCallback(BaseCallbackHandler):
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        print(token, end="", flush=True)
```

---

### Q6: LangChain vs LangGraph — kab kya use karo?
**Answer:**
```
LangChain (ye file):
  ✓ Linear pipelines — prompt | model | parser
  ✓ RAG chains
  ✓ Simple Q&A bots with memory
  ✓ Document processing
  ✗ Complex multi-step agent logic
  ✗ Conditional branching
  ✗ Cycles/loops in workflow

LangGraph (next file):
  ✓ Multi-step agents with state
  ✓ Conditional routing between nodes
  ✓ Human-in-the-loop
  ✓ Multi-agent coordination
  ✓ Complex workflows with cycles
  ✓ Supervisor pattern
  Use when: agent needs to decide its next action dynamically

Rule of thumb:
  - Simple pipeline → LangChain LCEL
  - Agent with multiple tools/steps → LangGraph
  - Multi-agent system → LangGraph with supervisor
```
