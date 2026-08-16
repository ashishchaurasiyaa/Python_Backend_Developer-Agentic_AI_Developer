# AI & LLM Skills — Deep Architecture Guide
### Resume Skills: Claude · GPT-4 · LangChain · LangGraph · MCP · AI Agents · RAG · Vector DBs · Prompt Engineering
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — definition → example → architecture samjho
> - Pass 2: Sirf "Interview Answer" sections loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo bina dekhe
> - Pass 4: Tera project connection dekho — interview mein wahi bolo

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | Claude | Toofan, AI Log Analysis Server |
| 2 | OpenAI GPT-4 | Niroskos SaaS |
| 3 | LangChain | Toofan (orchestration base) |
| 4 | LangGraph | Toofan (StateGraph) |
| 5 | MCP — Model Context Protocol | Toofan, AI Log Analysis Server |
| 6 | AI Agents | Toofan, triage agent |
| 7 | RAG | Niroskos, Log Analysis |
| 8 | Vector Databases | RAG pipeline |
| 9 | Prompt Engineering | Har project mein |

---

## TOPIC 1: CLAUDE

### Definition
```
Claude = Anthropic ka LLM (Large Language Model).
GPT-4 ka competitor — par alag philosophy:
Constitutional AI se trained, long context (200k tokens),
aur MCP natively support karta hai.
```

### Simple Example (analogy)
```
Soch ek bahut smart assistant hai jo:
- 200,000 words ek saath padh sakta hai (puri book!)
- Tumse tools use karne ke liye keh sakta hai
  ("database check karo", "file dekho")
- Instructions carefully follow karta hai
- Galti pe "I don't know" bolta hai, hallucinate kam karta hai
```

### Architecture — Models family

```
ANTHROPIC CLAUDE FAMILY (2025-26)
────────────────────────────────────────────────────────

claude-opus-4      ← Most powerful, complex reasoning
                      Multi-step agentic tasks
                      Expensive, slow

claude-sonnet-4-6  ← Balanced (YEH CURRENT MODEL HAI)
                      Production agentic workflows
                      Price/performance sweet spot

claude-haiku-4-5   ← Fastest, cheapest
                      Simple tasks, high volume
                      Classification, routing

claude-fable-5     ← Latest frontier model

KEY DIFFERENTIATORS vs GPT-4:
┌─────────────────────────────────────────────────────┐
│  Feature              Claude         GPT-4o         │
│  ─────────────────    ──────────     ──────────     │
│  Context window       200k tokens    128k tokens    │
│  MCP support          Native (made   Via plugins    │
│                       by Anthropic)                 │
│  Constitutional AI    Yes            RLHF           │
│  Tool use             Strong         Strong         │
│  Code generation      Very strong    Very strong    │
│  Multimodal           Yes (vision)   Yes (vision)  │
└─────────────────────────────────────────────────────┘
```

### How Claude works — internally

```
YOUR PROMPT (text + optional images + tool results)
          │
          ▼
┌─────────────────────────────────────────────────────┐
│              CLAUDE (Transformer model)              │
│                                                      │
│  1. TOKENIZE input                                   │
│     "Hello" → [9906] (token ID)                     │
│                                                      │
│  2. ATTENTION mechanism                              │
│     Har token doosre tokens se kaise related hai    │
│     200k context = 200k tokens attend kar sakta hai │
│                                                      │
│  3. GENERATE response token by token                 │
│     Next most likely token predict karo             │
│     Temperature = randomness control                 │
│                                                      │
│  4. STOP criteria                                    │
│     End token ya max_tokens reach hone pe           │
└─────────────────────────────────────────────────────┘
          │
          ▼
RESPONSE (text ya tool_call)
```

### Code — basic API call

```python
import anthropic

client = anthropic.Anthropic(api_key="...")

# Basic call
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain RAG in 2 lines."}
    ]
)
print(response.content[0].text)

# With system prompt
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a senior Python backend engineer. Answer concisely.",
    messages=[
        {"role": "user", "content": "What is N+1 problem?"}
    ]
)

# With tool use (Claude decides when to call)
tools = [{
    "name": "get_order_status",
    "description": "Get order status from database",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Order ID"}
        },
        "required": ["order_id"]
    }
}]

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Order #123 ka status?"}]
)

# Check if Claude wants to call a tool
if response.stop_reason == "tool_use":
    tool_call = response.content[1]
    print(f"Tool: {tool_call.name}")
    print(f"Input: {tool_call.input}")
```

### Tera project connection

```
TOOFAN PROJECT mein Claude ka role:
─────────────────────────────────────
User query → Claude (orchestrator) → decides which tool/agent to use
           → Tool result → Claude → final response

AI LOG ANALYSIS SERVER mein:
─────────────────────────────
Logs (MCP server se) → Claude → natural language mein diagnosis
"Service X pe 500 errors 3:45pm pe spike hue, root cause: DB timeout"
```

### Interview Answer

> **Q: "Why Claude over GPT-4 for your agentic projects?"**
>
> *"Claude choose kiya mainly 3 reasons se. First, 200k context window —
> log analysis mein large log files ek saath process karna padta tha,
> GPT-4 ka 128k window constraint tha. Second, MCP natively Anthropic
> ne banaya hai, so Claude ke saath MCP integration bahut clean hai —
> tool definitions, tool results sab structured hain. Third, agentic
> workflows mein Claude instructions carefully follow karta hai —
> hallucination rate kam hai jo production mein critical hai."*

---

## TOPIC 2: OPENAI GPT-4

### Definition
```
GPT-4 = OpenAI ka flagship LLM.
GPT = Generative Pre-trained Transformer.
Industry standard model — most widely used, largest ecosystem.
```

### Simple Example
```
GPT-4 ek universal translator jaisa hai:
- Text → Code
- Code → Explanation
- Image → Description (GPT-4o multimodal)
- Text → Structured JSON

Sabse bada advantage: ECOSYSTEM
- LangChain, LangGraph, CrewAI — sab GPT-4 ke saath pehle banaye
- Documentation, examples, community — bahut bada
```

### GPT family architecture

```
OPENAI MODEL FAMILY (2025-26)
────────────────────────────────────────────────────────

gpt-4o          ← Multimodal (text + vision + audio)
                   Fast, cheaper than gpt-4-turbo
                   Production default

gpt-4o-mini     ← Small, fast, cheap
                   Simple classification, routing

o3              ← Reasoning model (thinks before answering)
                   Math, code, complex problems
                   Slower, expensive

o4-mini         ← Reasoning, balanced cost

text-embedding-3-small/large ← Embedding models (RAG ke liye)

DALL-E 3        ← Image generation
Whisper         ← Speech to text
```

### GPT-4 vs Claude — when to use what

```
USE GPT-4 WHEN:                    USE CLAUDE WHEN:
────────────────────               ────────────────────
Ecosystem matters                  Long context needed (200k)
  (LangChain examples)             MCP native support
OpenAI Assistants API              Constitutional AI constraints
Function calling                   Strong instruction following
DALL-E/Whisper integration         Log/document analysis
Azure OpenAI (enterprise)          Cost-effective long docs
```

### Code — OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(api_key="...")

# Basic call
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain microservices in 2 lines."}
    ],
    temperature=0.2,
    max_tokens=500
)
print(response.choices[0].message.content)

# Structured output (JSON mode)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "List 3 Python frameworks as JSON"}],
    response_format={"type": "json_object"}
)

# Function calling (same concept as Claude tools)
functions = [{
    "name": "search_packages",
    "description": "Search tour packages",
    "parameters": {
        "type": "object",
        "properties": {
            "destination": {"type": "string"},
            "budget": {"type": "number"}
        },
        "required": ["destination"]
    }
}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Goa trip under 50k?"}],
    functions=functions,
    function_call="auto"
)
```

### Tera project connection

```
NIROSKOS SAFARIS mein GPT-4 ka use:
────────────────────────────────────
Typesense search + GPT-4 SEO captions generate karna:
  Tour package data → GPT-4 → SEO-optimized description
  "Goa Beach Holiday 5D/4N ..."  →  rich meta description + title
```

### Interview Answer

> **Q: "GPT-4 vs Claude — aap kaunsa prefer karte ho aur kyun?"**
>
> *"Dono use kiye hain, alag contexts mein. Niroskos mein GPT-4o use kiya
> kyunki LangChain ecosystem ke saath tight integration tha aur SEO content
> generation ke liye excellent tha. Toofan aur log analysis mein Claude use
> kiya — MCP native support aur 200k context window ki wajah se. Honest
> answer yeh hai ki koi ek better nahi hai — task, context, aur ecosystem
> decide karta hai."*

---

## TOPIC 3: LANGCHAIN

### Definition
```
LangChain = Python/JS framework for building LLM applications.
2022 mein aaya, GenAI ecosystem ka building block ban gaya.
Abstractions provide karta hai: LLMs, prompts, chains, memory, tools.
```

### Simple Example (analogy)
```
LangChain = LEGO blocks for LLM apps.

Bina LangChain:              LangChain ke saath:
─────────────────            ────────────────────
Manually API call            Chain(prompt | llm | parser)
Manually parse response      Automatic
Manually handle memory       ConversationBufferMemory()
Manually retry               Built-in retry
Manually format prompt       PromptTemplate()

Tune manually kiya → LangChain ne abstract kar diya
```

### Architecture — LangChain layers

```
LANGCHAIN ARCHITECTURE
────────────────────────────────────────────────────────

LAYER 4: CHAINS & AGENTS (high level)
┌──────────────────────────────────────────────────────┐
│  ConversationalRetrievalChain  │  AgentExecutor      │
│  RetrievalQA                  │  create_react_agent  │
└──────────────────────────────────────────────────────┘
          │
LAYER 3: CORE COMPONENTS
┌──────────────────────────────────────────────────────┐
│  LLMs/ChatModels  │  Memory   │  Tools   │  Retrievers│
│  ChatOpenAI       │  Buffer   │  Search  │  VectorStore│
│  ChatAnthropic    │  Summary  │  Python  │  BM25      │
└──────────────────────────────────────────────────────┘
          │
LAYER 2: PROMPTS & OUTPUT PARSERS
┌──────────────────────────────────────────────────────┐
│  PromptTemplate  │  ChatPromptTemplate               │
│  PydanticParser  │  JSONOutputParser                 │
└──────────────────────────────────────────────────────┘
          │
LAYER 1: LLM PROVIDERS (interchangeable)
┌──────────────────────────────────────────────────────┐
│  OpenAI  │  Anthropic  │  Azure OpenAI  │  Ollama    │
└──────────────────────────────────────────────────────┘
```

### LCEL — LangChain Expression Language (modern way)

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ═══════════════════════════════════════════════════════
# LCEL: pipe operator se chain banao
# ═══════════════════════════════════════════════════════

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Answer concisely."),
    ("user", "{question}")
])

parser = StrOutputParser()

# CHAIN = prompt | llm | parser
chain = prompt | llm | parser

# Run
result = chain.invoke({"question": "What is Redis?"})
print(result)

# ═══════════════════════════════════════════════════════
# With Memory (conversation history)
# ═══════════════════════════════════════════════════════
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

memory = ConversationBufferMemory()
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True
)

conversation.predict(input="Hi, I'm Ashish")
conversation.predict(input="What's my name?")  # remembers "Ashish"

# ═══════════════════════════════════════════════════════
# RAG Chain (Retrieval Augmented Generation)
# ═══════════════════════════════════════════════════════
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA

# Vector store se retriever
vectorstore = Chroma(embedding_function=OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# RAG chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

result = qa_chain.invoke({"query": "Refund policy kya hai?"})
print(result["result"])
print(result["source_documents"])
```

### Interview Answer

> **Q: "LangChain use kiya hai — kya specifically build kiya?"**
>
> *"LangChain use kiya Toofan project mein — primarily LCEL chains aur
> retriever abstractions ke liye. Specifically RAG pipeline mein
> LangChain ka retriever interface use kiya — isse vector store swap
> karna easy tha (Chroma se FAISS bina chain badle). Memory management
> ke liye ConversationBufferMemory use kiya multi-turn conversations mein.
> LangGraph ko LangChain ke upar use kiya stateful workflows ke liye —
> dono complementary hain."*

---

## TOPIC 4: LANGGRAPH

### Definition
```
LangGraph = LangChain ka extension for stateful, multi-step AI workflows.
Graph = nodes (steps) + edges (transitions) + state (shared memory).
Cyclic graphs support karta hai — loops, retries, human-in-the-loop.
```

### Simple Example (analogy)
```
LangChain = assembly line (A → B → C, linear)
LangGraph  = flowchart with conditions and loops

Example: Customer support agent
START
  │
  ▼
[Understand Query]
  │
  ├── Simple query → [Answer Directly] → END
  │
  └── Complex query → [Search KB] → [Generate Answer]
                           │
                           └── Low confidence → [Escalate to Human] → END
                                                     ↑
                                               (loop back possible)
```

### Architecture — StateGraph

```
LANGGRAPH STATEGRAPH ARCHITECTURE
────────────────────────────────────────────────────────

STATE (shared dict — sab nodes read/write karte hain)
┌──────────────────────────────────────────────────────┐
│  TypedDict / Pydantic model                          │
│  {                                                   │
│    "messages": [HumanMessage, AIMessage, ...],       │
│    "context": str,              # retrieved docs     │
│    "tool_calls": list,          # pending tools      │
│    "iteration": int,            # loop counter       │
│    "final_answer": str          # output             │
│  }                                                   │
└──────────────────────────────────────────────────────┘
           ↕ read/write
┌──────────────────────────────────────────────────────┐
│                     GRAPH                            │
│                                                      │
│  START                                               │
│    │                                                 │
│    ▼                                                 │
│  [NODE: agent]  ─── calls LLM, decides next step    │
│    │                                                 │
│    ├── "call_tool" ──► [NODE: tools]                 │
│    │                       │                         │
│    │                       └──► back to [agent]      │
│    │                            (CYCLE! LangChain    │
│    │                             nahi kar sakta)     │
│    │                                                 │
│    └── "respond" ──► END                             │
│                                                      │
│  CONDITIONAL EDGES (router function):                │
│  agent node ke baad → router decide karta hai        │
│  "call_tool" ya "respond"                            │
└──────────────────────────────────────────────────────┘
```

### Code — complete StateGraph example

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import operator

# ═══════════════════════════════════════════════════════
# STEP 1: STATE define karo
# ═══════════════════════════════════════════════════════
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    # operator.add = new messages append hote hain, overwrite nahi

# ═══════════════════════════════════════════════════════
# STEP 2: TOOLS define karo
# ═══════════════════════════════════════════════════════
from langchain_core.tools import tool

@tool
def search_knowledge_base(query: str) -> str:
    """Search the company knowledge base."""
    # Real implementation: vector DB query
    return f"Found: Policy for '{query}' is 30-day return."

@tool
def get_order_status(order_id: str) -> str:
    """Get order status from database."""
    return f"Order {order_id}: Shipped, arriving Aug 17"

tools = [search_knowledge_base, get_order_status]

# ═══════════════════════════════════════════════════════
# STEP 3: LLM with tools bind karo
# ═══════════════════════════════════════════════════════
llm = ChatAnthropic(model="claude-sonnet-4-6")
llm_with_tools = llm.bind_tools(tools)

# ═══════════════════════════════════════════════════════
# STEP 4: NODES define karo
# ═══════════════════════════════════════════════════════
def agent_node(state: AgentState) -> AgentState:
    """LLM call — decides next action."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

tool_node = ToolNode(tools)  # auto-executes tool calls

# ═══════════════════════════════════════════════════════
# STEP 5: ROUTER — conditional edge
# ═══════════════════════════════════════════════════════
def should_continue(state: AgentState) -> str:
    """Decide: call tool OR end."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "call_tool"   # tools call karna hai
    return "end"             # final answer ready

# ═══════════════════════════════════════════════════════
# STEP 6: GRAPH build karo
# ═══════════════════════════════════════════════════════
graph = StateGraph(AgentState)

# Nodes add karo
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)

# Entry point
graph.set_entry_point("agent")

# Conditional edge: agent ke baad kya?
graph.add_conditional_edges(
    "agent",
    should_continue,
    {
        "call_tool": "tools",   # tool call karo
        "end": END              # khatam
    }
)

# Tool ke baad waapas agent pe
graph.add_edge("tools", "agent")  # YEH HAI CYCLE!

# Compile
app = graph.compile()

# ═══════════════════════════════════════════════════════
# STEP 7: RUN karo
# ═══════════════════════════════════════════════════════
result = app.invoke({
    "messages": [HumanMessage(content="Order #123 ka status kya hai?")]
})

for message in result["messages"]:
    print(f"{message.type}: {message.content}")
```

### LangChain vs LangGraph — key difference

```
LANGCHAIN (linear):              LANGGRAPH (graph):
────────────────────             ────────────────────
A → B → C → D                   A → B → C → B → D (cycles!)
Fixed flow                       Dynamic flow
No loops                         Loops possible
No state                         Shared state
Simple pipelines                 Complex agents
                                 Human-in-the-loop
                                 Checkpointing/resume
```

### Tera project connection

```
TOOFAN PROJECT mein LangGraph:
──────────────────────────────
StateGraph banaya task decomposition ke liye:
  User request → decompose_node → [task1, task2, task3]
  → parallel tool calls → aggregate_node → final response

CYCLE USE CASE:
  agent_node → decides "need more info"
  → search_node → result → agent_node (cycle)
  → final answer mil gayi → END
```

### Interview Answer

> **Q: "LangGraph kyun use kiya, simple LangChain chain kyun nahi?"**
>
> *"Toofan mein user ka request sometimes multi-step tha — ek tool ki
> output se decide hota tha ki agle kaunsa tool call karna hai. Yeh
> dynamic flow LangChain ki linear chain mein possible nahi tha.
> LangGraph ka StateGraph use kiya — shared state mein messages store
> hote hain, agent node decide karta hai next step, aur tool results
> waapas agent ko jaate hain. Cycle support karta hai jo real agentic
> behavior ke liye zaruri hai — retry, clarification, multi-step reasoning."*

---

## TOPIC 5: MODEL CONTEXT PROTOCOL (MCP)

### Definition
```
MCP = Model Context Protocol.
Anthropic ka open standard (Nov 2024).
LLM apps ko external tools/data se connect karne ka standard way.
USB-C of AI — ek protocol, koi bhi tool connect karo.
```

### Simple Example (analogy)
```
PEHLE MCP KE BINA:
────────────────────────────────────────────
App A → Custom integration → Database
App A → Custom integration → GitHub
App A → Custom integration → Slack
(Har baar naya code likhna padta tha)

MCP KE SAATH:
────────────────────────────────────────────
Database MCP Server (ek baar banao)
     ↑
     │  Standard MCP protocol
     ↓
Claude / Any MCP Client → calls any tool

GitHub MCP Server (ek baar banao)
     ↑
     │  Same protocol
     ↓
Claude → files read karo, PRs dekho

EK STANDARD → INFINITE TOOLS
```

### Architecture — MCP components

```
MCP ARCHITECTURE
────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────┐
│                  MCP HOST                            │
│         (Claude Desktop / Claude Code /              │
│          your FastAPI app with claude)               │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │              MCP CLIENT                        │  │
│  │  (protocol layer — talk to servers)            │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │  MCP Protocol
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  MCP SERVER  │ │  MCP SERVER  │ │  MCP SERVER  │
│  (Database)  │ │  (Filesystem)│ │  (Web Search)│
│              │ │              │ │              │
│  Tools:      │ │  Tools:      │ │  Tools:      │
│  - query_db  │ │  - read_file │ │  - search    │
│  - write_db  │ │  - write_file│ │  - fetch_url │
│  Resources:  │ │  Resources:  │ │              │
│  - schema    │ │  - directory │ │              │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       ▼                ▼                ▼
   PostgreSQL         File System     Web / APIs
```

### MCP 3 primitives — kya expose kar sakte ho

```
PRIMITIVE 1: TOOLS (functions LLM call kar sakta hai)
─────────────────────────────────────────────────────
  Tool: search_logs(query, start_time, end_time)
  Tool: query_database(sql)
  Tool: create_jira_ticket(title, description)

PRIMITIVE 2: RESOURCES (data LLM read kar sakta hai)
─────────────────────────────────────────────────────
  Resource: logs://today/errors  → today ke error logs
  Resource: db://schema          → database schema
  Resource: file:///app/config   → config file

PRIMITIVE 3: PROMPTS (reusable prompt templates)
─────────────────────────────────────────────────
  Prompt: "debug_template" → standard debugging prompt
  Prompt: "code_review"   → code review checklist
```

### Transport types

```
TRANSPORT 1: STDIO (local, subprocess)
────────────────────────────────────────
Claude Desktop → stdin/stdout → MCP Server (local process)
Fast, simple, no network
Use: local tools (filesystem, local DB)

TRANSPORT 2: HTTP + SSE (remote, network)
──────────────────────────────────────────
Your App → HTTP POST → MCP Server (remote service)
           ← SSE stream ← (streaming responses)
Use: remote services, cloud tools

TRANSPORT 3: Streamable HTTP (2025, replacing SSE)
────────────────────────────────────────────────────
Bidirectional, more efficient
Use: production remote MCP servers
```

### Code — MCP Server banana (FastMCP)

```python
# ═══════════════════════════════════════════════════════
# CUSTOM MCP SERVER — AI Log Analysis Server (tera project)
# ═══════════════════════════════════════════════════════
# pip install fastmcp

from fastmcp import FastMCP
from datetime import datetime
import json

mcp = FastMCP("log-analysis-server")

# ─── TOOL 1: Log search ──────────────────────────────
@mcp.tool()
def search_logs(
    query: str,
    service: str = "all",
    start_time: str = None,
    level: str = "ERROR"
) -> str:
    """
    Search application logs by keyword.
    Returns matching log entries with timestamp and context.
    """
    # Real implementation: Elasticsearch ya grep
    logs = _query_elasticsearch(query, service, start_time, level)
    return json.dumps(logs, indent=2)

# ─── TOOL 2: Error grouping ──────────────────────────
@mcp.tool()
def group_errors(time_window_minutes: int = 60) -> str:
    """
    Group similar errors in the last N minutes.
    Returns error patterns with frequency counts.
    """
    errors = _get_recent_errors(time_window_minutes)
    groups = _cluster_similar_errors(errors)
    return json.dumps(groups, indent=2)

# ─── TOOL 3: Timeline reconstruction ─────────────────
@mcp.tool()
def get_request_timeline(request_id: str) -> str:
    """
    Reconstruct full timeline of a specific request
    across all microservices using trace_id.
    """
    events = _get_trace_events(request_id)
    return json.dumps(events, indent=2)

# ─── RESOURCE: Current error rate ────────────────────
@mcp.resource("logs://current/error-rate")
def get_error_rate() -> str:
    """Current error rate per service (last 5 min)."""
    rates = _calculate_error_rates()
    return json.dumps(rates)

# Run server
if __name__ == "__main__":
    mcp.run(transport="stdio")  # Claude Desktop ke saath
    # ya
    # mcp.run(transport="http", port=8000)  # Remote
```

### How Claude uses MCP

```
USER: "Kal raat 2am pe service X pe errors kyun the?"

CLAUDE (thinking):
  1. "Mujhe logs check karne chahiye"
  2. search_logs tool call karo:
     {"query": "service X", "start_time": "2am yesterday", "level": "ERROR"}

MCP SERVER receives → queries Elasticsearch → returns results

CLAUDE receives results:
  "500 errors: Database connection timeout"
  "Root cause: DB max_connections exceeded"

CLAUDE: "Kal raat 2am pe service X pe 127 errors the.
         Root cause: PostgreSQL max_connections limit hit ho gayi.
         Recommendations: connection pooling increase karo ya
         read replicas add karo."
```

### Tera project connection

```
TOOFAN mein 3 custom MCP servers:
───────────────────────────────────
1. Filesystem server → files read/write/search
2. Web search server → internet se fetch
3. Database server   → PostgreSQL queries

AI LOG ANALYSIS SERVER:
───────────────────────
Custom MCP server expose kiya:
- search_logs tool
- group_errors tool
- get_request_timeline tool
Claude in tools se log analysis karta hai
Natural language mein → structured log query
```

### Interview Answer

> **Q: "MCP kya hai aur tune kaise use kiya?"**
>
> *"MCP Anthropic ka open standard hai LLM apps ko external tools se
> connect karne ke liye. Think of it as USB-C for AI — ek protocol,
> koi bhi tool connect karo. Maine do projects mein use kiya. AI Log
> Analysis Server mein custom MCP server banaya — 3 tools expose kiye:
> search_logs, group_errors, get_request_timeline. Claude in tools ko
> call karta hai aur natural language mein log analysis karta hai — koi
> manual grep nahi. Toofan mein 3 MCP servers hain — filesystem, web
> search, database. Sabka same standard protocol hai, isliye Claude ko
> ek jaisi tool definition milti hai sabke liye."*

---

## TOPIC 6: AI AGENTS

### Definition
```
AI Agent = LLM + Tools + Memory + Goal
           jo autonomously multi-step tasks complete kare.

Simple LLM call:  Input → LLM → Output (ek shot)
AI Agent:         Goal → Plan → Act → Observe → Plan → Act → ... → Done
                                        ↑__________________________|
                                              (feedback loop)
```

### Simple Example (analogy)
```
SIMPLE LLM (assistant):         AI AGENT:
────────────────────────        ────────────────────────
User: "Flights to Goa?"         User: "Book cheapest Goa flight
LLM: "Here are some tips..."         for Aug 20, notify me"
(generic answer, no action)
                                Agent:
                                1. Search flights (tool call)
                                2. Compare prices (reasoning)
                                3. Check availability (tool call)
                                4. Book ticket (tool call)
                                5. Send notification (tool call)
                                (autonomous multi-step execution)
```

### Agent architecture — ReAct pattern

```
ReAct = Reasoning + Acting
(Most common agent pattern)

LOOP:
┌──────────────────────────────────────────────────────┐
│  THOUGHT: "I need to find order status"              │
│      │                                               │
│      ▼                                               │
│  ACTION: search_database(order_id="123")             │
│      │                                               │
│      ▼                                               │
│  OBSERVATION: {"status": "shipped", "eta": "Aug 17"} │
│      │                                               │
│      ▼                                               │
│  THOUGHT: "I have the info, can answer now"          │
│      │                                               │
│      ▼                                               │
│  ACTION: respond to user                             │
│      │                                               │
│      ▼                                               │
│  END                                                 │
└──────────────────────────────────────────────────────┘
```

### Agent types — kaunsa kab

```
AGENT TYPE          PATTERN              USE CASE
──────────────      ─────────────        ──────────────────────────
ReAct Agent         Think-Act-Observe    General purpose, tool use
Plan-Execute        Plan first, then act Complex multi-step tasks
Reflection Agent    Self-critique loop   Quality improvement
Multi-Agent         Agents talk to agents Large complex tasks
Supervisor          One agent routes     Team of specialized agents
                    to sub-agents
Swarm               Peer agents hand off Flexible routing
                    to each other
```

### Multi-agent architecture (Toofan pattern)

```
TOOFAN MULTI-AGENT ARCHITECTURE
────────────────────────────────────────────────────────

USER REQUEST
     │
     ▼
┌─────────────────────────────────────────────────────┐
│            ORCHESTRATOR AGENT (Claude)               │
│  "Decompose task, route to right specialist"         │
│                                                      │
│  Receives: user request                              │
│  Decides: which sub-agent to call                   │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌─────────────┐ ┌──────────┐ ┌───────────────┐
│  SEARCH     │ │  CODE    │ │  DATABASE     │
│  AGENT      │ │  AGENT   │ │  AGENT        │
│             │ │          │ │               │
│  Web search │ │  Write + │ │  Query/write  │
│  tool use   │ │  execute │ │  PostgreSQL   │
│  MCP server │ │  Python  │ │  MCP server   │
└─────────────┘ └──────────┘ └───────────────┘
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
             AGGREGATOR NODE
             (results combine)
                     │
                     ▼
              FINAL RESPONSE
```

### Code — simple agent with tool loop

```python
from anthropic import Anthropic

client = Anthropic()

# Tools definition
tools = [
    {
        "name": "search_logs",
        "description": "Search application error logs",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "hours_back": {"type": "integer", "default": 1}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_metrics",
        "description": "Get system metrics for a service",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string"},
                "metric": {"type": "string"}
            },
            "required": ["service_name"]
        }
    }
]

def run_tool(tool_name: str, tool_input: dict) -> str:
    """Execute the actual tool."""
    if tool_name == "search_logs":
        return f"Found 15 errors: DB timeout in {tool_input['query']}"
    elif tool_name == "get_metrics":
        return f"CPU: 89%, Memory: 78% for {tool_input['service_name']}"

def run_agent(user_message: str) -> str:
    """Agent loop — runs until no more tool calls."""
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        # Add assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        # Check if done (no tool calls)
        if response.stop_reason == "end_turn":
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

        # Add tool results and continue loop
        messages.append({"role": "user", "content": tool_results})

# Run
answer = run_agent("Payment service pe errors kyun aa rahe hain?")
print(answer)
```

### Interview Answer

> **Q: "AI Agent kya hai — simple chatbot se kya alag hai?"**
>
> *"Simple chatbot ek shot mein answer deta hai — question in, answer out.
> AI Agent ka loop hota hai: goal set karo, agent plan banata hai, tools
> use karta hai, result observe karta hai, phir next action decide karta
> hai — jab tak goal achieve na ho. Toofan mein maine yeh implement kiya
> — user ka complex request aata hai, orchestrator agent decompose karta
> hai, sub-agents tools call karte hain (search, database, code execution),
> results aggregate hote hain. Key difference: autonomy aur multi-step
> execution, single inference nahi."*

---

## TOPIC 7: RAG — Retrieval Augmented Generation

### Definition
```
RAG = Retrieval Augmented Generation.
LLM ki knowledge = training cutoff tak.
RAG = LLM ko real-time external knowledge do.

= Search (retrieve relevant docs) + Generate (LLM answers using those docs)
```

### Simple Example (analogy)
```
WITHOUT RAG:                     WITH RAG:
──────────────────────           ────────────────────────────────
Q: "Our refund policy?"          Q: "Our refund policy?"
                                    │
LLM: "I don't know your           RETRIEVE: Search company docs
      specific policy..."            → "30-day return policy..."
                                    │
                                 GENERATE: LLM + context
                                    → "According to our policy
                                       (source: policy.pdf p.3):
                                       30-day return with receipt."

ANALOGY:
LLM without RAG = student without books (only memorized knowledge)
LLM with RAG    = student with open book exam (can look up answers)
```

### RAG Architecture — full pipeline

```
RAG PIPELINE — TWO PHASES
────────────────────────────────────────────────────────

PHASE 1: INDEXING (ek baar, offline)
──────────────────────────────────────
Documents (PDF, Word, Web pages)
     │
     ▼
CHUNKING (split into pieces)
  "Full document (50 pages)" → chunks of ~500 tokens
  Overlap: 50 tokens (context maintain karo)
     │
     ▼
EMBEDDING MODEL (text → vector)
  "30-day return policy..." → [0.12, -0.45, 0.78, ...]
  (1536 numbers for text-embedding-3-small)
     │
     ▼
VECTOR DATABASE (store vectors + original text)
  Qdrant / pgvector / FAISS / Azure AI Search
  Each chunk: {vector: [...], text: "...", metadata: {source, page}}

PHASE 2: RETRIEVAL + GENERATION (har query pe)
───────────────────────────────────────────────
User Query: "Refund policy kya hai?"
     │
     ▼
EMBED QUERY (same embedding model)
  "Refund policy kya hai?" → [0.09, -0.41, 0.81, ...]
     │
     ▼
VECTOR SIMILARITY SEARCH
  Query vector vs all stored vectors
  Top-K most similar chunks return karo
  (cosine similarity ya L2 distance)
     │
     ▼
CONTEXT ASSEMBLY
  Retrieved chunks → one context string
     │
     ▼
PROMPT CONSTRUCTION
  System: "Answer only from context below."
  Context: [retrieved chunks]
  User: "Refund policy kya hai?"
     │
     ▼
LLM GENERATION
  GPT-4o / Claude reads context → generates answer
     │
     ▼
RESPONSE + SOURCES
  "30-day return policy (source: policy.pdf, page 3)"
```

### Code — complete RAG implementation

```python
from openai import OpenAI
import numpy as np
import json

client = OpenAI()

# ═══════════════════════════════════════════════════════
# PHASE 1: INDEX DOCUMENTS
# ═══════════════════════════════════════════════════════

def chunk_document(text: str, chunk_size: int = 500, overlap: int = 50):
    """Split document into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def embed(text: str) -> list[float]:
    """Convert text to vector."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(a: list, b: list) -> float:
    """Similarity between two vectors (higher = more similar)."""
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Index your documents
documents = [
    "Our refund policy allows returns within 30 days with original receipt.",
    "Premium members get 60-day return window with free pickup.",
    "Electronics have 15-day return policy. No returns on opened software.",
    "For damaged items, contact support within 48 hours for replacement.",
]

# Build index (in memory — use Qdrant/pgvector in production)
index = []
for i, doc in enumerate(documents):
    chunks = chunk_document(doc)
    for chunk in chunks:
        index.append({
            "text": chunk,
            "embedding": embed(chunk),
            "source": f"policy_doc_{i}"
        })

# ═══════════════════════════════════════════════════════
# PHASE 2: RETRIEVE + GENERATE
# ═══════════════════════════════════════════════════════

def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Find most relevant chunks for query."""
    query_embedding = embed(query)

    # Score all chunks
    scored = [
        {
            "text": item["text"],
            "source": item["source"],
            "score": cosine_similarity(query_embedding, item["embedding"])
        }
        for item in index
    ]

    # Return top-k
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

def rag_answer(question: str) -> str:
    """Full RAG pipeline."""
    # Retrieve
    relevant_chunks = retrieve(question)

    # Build context
    context = "\n\n".join([
        f"[Source: {c['source']}]\n{c['text']}"
        for c in relevant_chunks
    ])

    # Generate
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer ONLY from the context provided below. "
                    "If the answer is not in context, say 'I don't know'. "
                    "Always cite the source."
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}"
            }
        ],
        temperature=0.1
    )

    return response.choices[0].message.content

# Test
answer = rag_answer("Electronics return kab tak kar sakte hain?")
print(answer)
# "Electronics 15 days mein return kar sakte hain (Source: policy_doc_2)"
```

### RAG quality problems aur solutions

```
PROBLEM 1: Wrong chunks retrieved
CAUSE: Semantic similarity kaam nahi kiya
FIX: Hybrid search (BM25 + vector) + Reranker (cross-encoder)

PROBLEM 2: LLM hallucinates despite context
CAUSE: LLM context ignore karta hai
FIX: Stricter prompt ("ONLY from context"), groundedness eval

PROBLEM 3: Retrieval misses relevant docs
CAUSE: Query aur doc mein vocabulary mismatch
FIX: Query expansion, HyDE (generate hypothetical answer first)

PROBLEM 4: Stale information
CAUSE: Index outdated
FIX: Incremental indexing, metadata freshness filter

PROBLEM 5: Slow retrieval
CAUSE: Large index, no optimization
FIX: HNSW index (Qdrant default), quantization, sharding
```

### Interview Answer

> **Q: "RAG kya hai aur tune kahan use kiya?"**
>
> *"RAG = Retrieval Augmented Generation. LLM ke paas training cutoff ke
> baad ka knowledge nahi hota — RAG se real-time external knowledge inject
> karte hain. Pipeline: documents ko chunks mein split karo, embed karo,
> vector DB mein store karo. Query aate time: query embed karo, similar
> chunks retrieve karo, context ke saath LLM ko do. Maine Niroskos mein
> implement kiya — tour packages aur policies ke baare mein GPT-4 se
> accurate answers generate kiye. Key challenge retrieval quality thi —
> hybrid search (BM25 + vector) use kiya accuracy ke liye."*

---

## TOPIC 8: VECTOR DATABASES

### Definition
```
Vector Database = database jo vectors (numbers ki list) store karta hai
                  aur unpe similarity search karta hai.

Text → Embedding Model → Vector [0.12, -0.45, 0.78, ...]
Vector DB mein store → Query vector se similar vectors fast dhundho
```

### Simple Example (analogy)
```
NORMAL DATABASE (exact match):          VECTOR DATABASE (similarity):
──────────────────────────────          ──────────────────────────────
SELECT * WHERE name = "Goa"             Find documents similar to
(exact word chahiye)                    "beach holiday in India"
                                        → Returns: Goa, Kovalam, Pondicherry
                                        (exact words match nahi, concept match!)

ANALOGY:
Normal DB = Library catalog (exact title search)
Vector DB = Librarian (tell me topic, I find related books)
```

### Vector similarity — kaise kaam karta hai

```
TEXT → VECTOR (embedding):
──────────────────────────
"Cat"  → [0.2, 0.8, 0.1, 0.9]
"Dog"  → [0.3, 0.7, 0.2, 0.8]   (similar to cat!)
"Car"  → [0.9, 0.1, 0.8, 0.2]   (different)

COSINE SIMILARITY (angle between vectors):
──────────────────────────────────────────
Cat vs Dog  = 0.97  (very similar → both animals)
Cat vs Car  = 0.12  (very different)
Cat vs Kitten = 0.99 (almost same → synonym)

VISUAL:
         Dog ●
        /
Cat ●──(small angle = similar)
        \
         ● Kitten

Car ●────────── (far away, different direction)
```

### Vector DB options — comparison

```
VECTOR DB        TYPE              BEST FOR
──────────────   ─────────────     ────────────────────────────
Qdrant           Dedicated         Production RAG, high perf
                 (Rust-based)      Filtering + vector search
                                   Self-hosted or cloud

pgvector         PostgreSQL ext.   Already using Postgres
                 (your familiar)   Simple RAG, small scale
                                   SQL + vector in one DB

FAISS            Library (Meta)    Research, in-memory
                 (not a DB)        Fast for batch search
                                   No persistence

Chroma           Embedded          Local dev, prototyping
                 (Python)          Easy to start, no server

Azure AI Search  Cloud managed     Azure stack (PwC!)
                                   Hybrid BM25 + vector
                                   Enterprise governance

Pinecone         Cloud managed     Serverless, easy to use
                                   No infra management
```

### Code — pgvector (tera Postgres ke saath)

```python
# pip install psycopg2-binary pgvector openai

import psycopg2
from pgvector.psycopg2 import register_vector
from openai import OpenAI
import numpy as np

client = OpenAI()

# ═══════════════════════════════════════════════════════
# SETUP (ek baar)
# ═══════════════════════════════════════════════════════
conn = psycopg2.connect("postgresql://user:pass@localhost/mydb")
register_vector(conn)

cur = conn.cursor()

# Extension enable karo
cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

# Table banao
cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding vector(1536),    -- text-embedding-3-small = 1536 dims
        source VARCHAR(255),
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

# HNSW index for fast search
cur.execute("""
    CREATE INDEX IF NOT EXISTS docs_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops)
""")
conn.commit()

# ═══════════════════════════════════════════════════════
# INSERT (indexing)
# ═══════════════════════════════════════════════════════
def insert_document(content: str, source: str):
    embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=content
    ).data[0].embedding

    cur.execute(
        "INSERT INTO documents (content, embedding, source) VALUES (%s, %s, %s)",
        (content, embedding, source)
    )
    conn.commit()

# ═══════════════════════════════════════════════════════
# SEARCH (retrieval)
# ═══════════════════════════════════════════════════════
def search(query: str, top_k: int = 5) -> list[dict]:
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding

    # Cosine similarity search (1 - distance = similarity)
    cur.execute("""
        SELECT content, source,
               1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        ORDER BY embedding <=> %s::vector   -- cosine distance
        LIMIT %s
    """, (query_embedding, query_embedding, top_k))

    results = cur.fetchall()
    return [
        {"content": r[0], "source": r[1], "similarity": r[2]}
        for r in results
    ]

# Test
insert_document("30-day return policy for all products", "policy.pdf")
insert_document("Electronics have 15-day return only", "policy.pdf")

results = search("How long can I return electronics?")
for r in results:
    print(f"[{r['similarity']:.2f}] {r['content']}")
```

### Interview Answer

> **Q: "Vector database kya hai aur RAG mein kaise use hota hai?"**
>
> *"Vector database text ko numbers ki list (vectors) ke roop mein store
> karta hai aur similarity se search karta hai — exact word match nahi,
> concept match. RAG pipeline mein yeh retrieval layer hai: documents
> embed karke store karo, query embed karke similar chunks dhundho.
> Maine pgvector use kiya PostgreSQL pe — already production mein
> Postgres tha, alag DB manage nahi karna tha. HNSW index lagaya fast
> approximate nearest neighbor search ke liye. Azure stack mein
> Azure AI Search use karta hoon — hybrid search (BM25 + vector)
> better results deta hai pure vector search se."*

---

## TOPIC 9: PROMPT ENGINEERING

### Definition
```
Prompt Engineering = LLM ko clear, specific instructions dene ki technique
                     taaki consistent, accurate, useful output mile.

Garbage in → Garbage out
Good prompt → Good output

Engineering kyunki: systematic, testable, iterable
```

### Simple Example
```
BAD PROMPT:                      GOOD PROMPT:
────────────────                 ───────────────────────────────────
"Write about Python"             "You are a senior Python developer.
                                  Explain async/await in Python 3.12
                                  to a developer who knows threading.
                                  Include:
                                  - One analogy
                                  - Code example with FastAPI
                                  - Common mistake to avoid
                                  Max 200 words."

Result: vague, generic           Result: specific, actionable, correct format
```

### Prompt Engineering techniques

```
TECHNIQUE 1: ROLE PROMPTING
────────────────────────────
"You are a [specific expert] with [specific experience]."

Without: Generic answer
With:    Domain-specific, appropriate vocabulary, right depth

Example:
"You are a senior PostgreSQL DBA with 10 years experience.
 Diagnose this slow query: [QUERY]"

─────────────────────────────────────────────────────────

TECHNIQUE 2: FEW-SHOT EXAMPLES
────────────────────────────────
Show 2-3 examples of input/output before your question.

System: "Classify customer sentiment:"
User: "Product is amazing!" → Positive
User: "Delivery was late." → Negative
User: "Package arrived damaged" → [NEW: let LLM classify]

Without examples: ~70% accuracy
With 3 examples: ~92% accuracy

─────────────────────────────────────────────────────────

TECHNIQUE 3: CHAIN OF THOUGHT (CoT)
──────────────────────────────────────
"Think step by step before answering."
"First analyze X, then Y, then conclude Z."

Forces LLM to show reasoning → fewer mistakes

─────────────────────────────────────────────────────────

TECHNIQUE 4: OUTPUT FORMAT CONTROL
──────────────────────────────────────
"Return ONLY valid JSON. No explanation. Format:
{
  'sentiment': 'positive|negative|neutral',
  'confidence': 0.0-1.0,
  'reason': 'one line'
}"

─────────────────────────────────────────────────────────

TECHNIQUE 5: CONTEXT INJECTION (RAG)
──────────────────────────────────────
"Answer ONLY from the context below.
 If not in context, say 'I don't know'.
 Never make up information.

 Context:
 [RETRIEVED CHUNKS]

 Question: [USER QUESTION]"

─────────────────────────────────────────────────────────

TECHNIQUE 6: NEGATIVE CONSTRAINTS
──────────────────────────────────────
"Do NOT:
 - Make up information not in context
 - Give generic advice
 - Use jargon without explanation
 - Exceed 200 words"
```

### System prompt architecture

```
WELL-STRUCTURED SYSTEM PROMPT:
────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────┐
│  SECTION 1: PERSONA (who are you)                   │
│  "You are a customer support agent for Niroskos     │
│   Safaris. You help customers with booking queries." │
├─────────────────────────────────────────────────────┤
│  SECTION 2: GOAL (what to do)                       │
│  "Your goal is to resolve customer queries          │
│   accurately using the knowledge base provided."    │
├─────────────────────────────────────────────────────┤
│  SECTION 3: CONSTRAINTS (what not to do)            │
│  "Do NOT:                                           │
│   - Discuss competitor services                     │
│   - Make promises not in policy                     │
│   - Share internal system information"              │
├─────────────────────────────────────────────────────┤
│  SECTION 4: OUTPUT FORMAT                           │
│  "Respond in this format:                           │
│   ANSWER: [your response]                           │
│   SOURCE: [policy document name if applicable]      │
│   ACTION: [if customer needs to do something]"      │
├─────────────────────────────────────────────────────┤
│  SECTION 5: EXAMPLES (few-shot, optional)           │
│  Q: "Can I cancel my booking?"                      │
│  A: "ANSWER: Yes, cancellation is free 48hrs...     │
│      SOURCE: Cancellation Policy v2                 │
│      ACTION: Visit booking dashboard > Cancel"      │
└─────────────────────────────────────────────────────┘
```

### Code — production prompt template

```python
from string import Template

# ═══════════════════════════════════════════════════════
# VERSIONED PROMPT TEMPLATE (git mein track karo)
# ═══════════════════════════════════════════════════════

SYSTEM_PROMPT_V2 = """You are a senior customer support agent for Niroskos Safaris.

GOAL: Answer customer queries accurately using ONLY the provided context.

RULES:
- Answer ONLY from the Context section below
- If information is not in context, say exactly: "I don't have that information. Please contact support@niroskos.com"
- Never fabricate policies, prices, or availability
- Keep response under 150 words unless detail is essential
- Always end with one actionable next step

OUTPUT FORMAT:
Answer: [your response]
Next step: [what customer should do]
Source: [document name if applicable]"""

USER_PROMPT_TEMPLATE = Template("""Context:
$context

Customer question: $question""")

def answer_customer_query(question: str, retrieved_docs: list) -> str:
    context = "\n\n".join([
        f"[{doc['source']}]: {doc['content']}"
        for doc in retrieved_docs
    ])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT_V2,   # versioned prompt
        messages=[{
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.substitute(
                context=context,
                question=question
            )
        }],
        temperature=0.1   # low temp = consistent output
    )
    return response.content[0].text
```

### Prompt engineering for agents

```python
# AGENT SYSTEM PROMPT — structured for tool use
AGENT_SYSTEM = """You are a log analysis expert with access to tools.

WHEN TO USE TOOLS:
- search_logs: when user asks about errors, events, or specific timeframes
- group_errors: when user asks about error patterns or frequency
- get_request_timeline: when user mentions a specific request_id or trace

REASONING PROCESS:
1. Understand what the user wants
2. Decide which tool gives that information
3. Call the tool
4. Interpret results in plain English
5. If more info needed, call another tool
6. Give final diagnosis with specific recommendations

RESPONSE FORMAT:
Diagnosis: [what happened]
Root cause: [why it happened]
Impact: [what was affected]
Fix: [what to do]"""
```

### Interview Answer

> **Q: "Prompt Engineering ka kya experience hai — practically kaise karte ho?"**
>
> *"Prompt engineering mere har LLM project mein core part tha. Practically,
> 3 principles follow karta hoon. First, structured system prompts — persona,
> goal, constraints, output format alag sections mein, versioned in git.
> Prompt code hai, documentation nahi. Second, few-shot examples — especially
> classification tasks mein 2-3 examples se accuracy significantly improve
> hoti hai. Third, evaluation-driven iteration — RAGAS ya manual golden
> dataset pe test karo, score dekho, prompt badlo, score dobara check karo.
> Blind 'try karo aur dekho' nahi — metrics se decide karo. Log Analysis
> Server mein, prompt v1 pe hallucination rate 15% tha — negative constraints
> add kiye, v3 pe 2% aa gayi."*

---

## QUICK RECALL — 1 ghanta pehle padho

```
╔════════════════════════════════════════════════════════════════╗
║                    AI & LLM QUICK RECALL                      ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  CLAUDE      = Anthropic LLM, 200k context, MCP native        ║
║                Toofan + Log Analysis mein use kiya            ║
║                                                                ║
║  GPT-4       = OpenAI LLM, largest ecosystem                  ║
║                Niroskos mein SEO captions ke liye             ║
║                                                                ║
║  LANGCHAIN   = Framework (LCEL chains, memory, retrievers)    ║
║                Building blocks; LangGraph ka base             ║
║                                                                ║
║  LANGGRAPH   = Stateful graph (nodes, edges, cycles)          ║
║                StateGraph, conditional edges, tool loop       ║
║                Toofan ka core orchestration                   ║
║                                                                ║
║  MCP         = Model Context Protocol (Anthropic standard)    ║
║                Tools + Resources + Prompts                    ║
║                STDIO (local) / HTTP+SSE (remote)              ║
║                Log Analysis Server + Toofan mein custom MCP   ║
║                                                                ║
║  AI AGENTS   = LLM + Tools + Memory + Goal                    ║
║                ReAct = Think → Act → Observe → loop           ║
║                Multi-agent = orchestrator + specialists        ║
║                                                                ║
║  RAG         = Retrieve relevant docs + Generate with context ║
║                Index: chunk → embed → store                   ║
║                Query: embed → similarity search → LLM         ║
║                                                                ║
║  VECTOR DB   = Store embeddings, similarity search            ║
║                pgvector (tera fav: Postgres pe!)              ║
║                Azure AI Search (PwC ke liye)                  ║
║                                                                ║
║  PROMPT ENG  = Role + Few-shot + CoT + Format + Constraints   ║
║                Versioned in git, eval-driven iteration        ║
║                                                                ║
║  CONNECTIONS:                                                  ║
║  Claude + MCP + LangGraph = Toofan architecture               ║
║  GPT-4 + RAG + pgvector   = Niroskos search                   ║
║  Claude + MCP tools       = AI Log Analysis Server            ║
╚════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · For: PwC Senior Associate GenAI interview 2026-08-18*
*Resume skills: Claude · GPT-4 · LangChain · LangGraph · MCP · AI Agents · RAG · Vector DBs · Prompt Engineering*