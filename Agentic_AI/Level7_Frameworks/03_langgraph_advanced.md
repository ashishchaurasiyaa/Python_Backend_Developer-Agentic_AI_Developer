# LangGraph Advanced — Multi-Agent, HITL, Streaming, Subgraphs

> **Target:** 40 LPA Python Backend + Agentic AI interviews
> **Style:** Hinglish — Hindi explanations, English code/terms
> **Series:** Phase 5 — File 2 of N

---

## 1. LangGraph Quick Recap

### Core Concepts — Ek Baar Phir Se

LangGraph ek **state machine framework** hai jo agentic workflows banane ke liye use hota hai. Pehle ki basics:

```
StateGraph → nodes + edges ka web
State      → TypedDict — graph ke through travel karta hai
Node       → ek Python function jo state read karta hai, modified state return karta hai
Edge       → two nodes ke beech connection
compile()  → graph ko runnable CompiledGraph mein convert karta hai
invoke()   → synchronous run — poora graph run karo, final state lo
stream()   → synchronous streaming — har node ke baad update milti hai
```

### Basic Anatomy

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
import operator

class MyState(TypedDict):
    messages: Annotated[list, operator.add]   # reducer — append karta hai
    counter: int                               # last value wins

def node_a(state: MyState) -> dict:
    # State ka kuch subset return karo — sirf jo change hua
    return {"counter": state["counter"] + 1}

def node_b(state: MyState) -> dict:
    return {"messages": [f"Counter is {state['counter']}"]}

def should_continue(state: MyState) -> str:
    if state["counter"] < 3:
        return "continue"
    return "stop"

# Graph banana
builder = StateGraph(MyState)
builder.add_node("node_a", node_a)
builder.add_node("node_b", node_b)
builder.add_edge(START, "node_a")
builder.add_edge("node_a", "node_b")
builder.add_conditional_edges("node_b", should_continue, {
    "continue": "node_a",   # loop back
    "stop": END
})

graph = builder.compile()
result = graph.invoke({"messages": [], "counter": 0})
# Yeh loop chalega jab tak counter < 3
```

### invoke() vs stream() — Key Difference

```python
# invoke() — blocking, final state return karta hai
final_state = graph.invoke({"messages": [], "task": "do something"})
print(final_state)  # poora final state

# stream() — generator, har step pe update milti hai
for chunk in graph.stream({"messages": [], "task": "do something"}):
    print(chunk)  # {"node_name": {"field": "value"}} — just updates

# astream() — async version
async for chunk in graph.astream(input_data, stream_mode="updates"):
    print(chunk)
```

---

## 2. Multi-Agent Architecture

### Kyun Multi-Agent?

Single agent ki limitations:
- **Context window overflow** — ek hi agent sab kuch nahi kar sakta
- **Specialization missing** — researcher vs coder vs reviewer — alag skills
- **Parallel execution not possible** — ek agent ek kaam karta hai
- **Reliability low** — ek agent fail kare toh poora fail

Multi-agent mein:
- **Supervisor** orchestrates — decide karta hai kaun kab kaam kare
- **Workers** specialized hain — har agent apna domain jaanta hai
- **Coordination** clean hoti hai — state through passing

---

### 2.1 Supervisor Pattern — Ek Master, Kai Workers

```
           ┌─────────────────┐
Input ───► │   Supervisor    │
           └─────────────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
  Researcher    Coder      Writer
  (web search)  (code gen)  (content)
       │           │           │
       └───────────┴───────────┘
                   │
                   ▼
            Supervisor (review)
                   │
                   ▼
                  END
```

**Supervisor ka kaam:** State dekho, decide karo next agent kaun — phir us agent ka naam state mein daalo.

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
import operator

class SupervisorState(TypedDict):
    messages: Annotated[list, operator.add]
    task: str
    next_agent: str                          # supervisor yahan likhta hai
    results: Annotated[list, operator.add]  # workers yahan results add karte hain
    iteration: int

def supervisor(state: SupervisorState) -> dict:
    """Master controller — task dekho, route karo"""
    task = state["task"].lower()
    iteration = state.get("iteration", 0)

    if iteration >= 3:  # infinite loop se bachao
        return {"next_agent": "END", "iteration": iteration + 1}
    
    if "research" in task or "find" in task or "search" in task:
        return {"next_agent": "researcher", "iteration": iteration + 1}
    elif "code" in task or "program" in task or "function" in task:
        return {"next_agent": "coder", "iteration": iteration + 1}
    elif "write" in task or "content" in task or "blog" in task:
        return {"next_agent": "writer", "iteration": iteration + 1}
    else:
        return {"next_agent": "writer", "iteration": iteration + 1}

def researcher(state: SupervisorState) -> dict:
    """Specialized researcher agent"""
    task = state["task"]
    # Real app mein: Tavily search, Wikipedia API, etc.
    result = f"[Researcher] Task: '{task}' ke liye findings:\n" \
             f"- Found 5 relevant sources\n" \
             f"- Key insight: Important data retrieved\n" \
             f"- Summary: Research complete"
    return {"results": [result], "messages": [f"Researcher completed: {task}"]}

def coder(state: SupervisorState) -> dict:
    """Specialized coder agent"""
    task = state["task"]
    result = f"[Coder] Task: '{task}' ke liye code:\n" \
             f"```python\ndef solution():\n    # Implementation here\n    pass\n```"
    return {"results": [result], "messages": [f"Coder completed: {task}"]}

def writer(state: SupervisorState) -> dict:
    """Specialized writer agent"""
    task = state["task"]
    result = f"[Writer] Task: '{task}' ke liye content:\n" \
             f"# Title\nProfessional content generated for the given task.\n" \
             f"## Key Points\n- Point 1\n- Point 2"
    return {"results": [result], "messages": [f"Writer completed: {task}"]}

def route_to_agent(state: SupervisorState) -> Literal["researcher", "coder", "writer", "__end__"]:
    """Conditional edge — supervisor ke decision pe route karo"""
    next_agent = state["next_agent"]
    if next_agent == "END":
        return "__end__"
    return next_agent

# Graph build karo
builder = StateGraph(SupervisorState)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", researcher)
builder.add_node("coder", coder)
builder.add_node("writer", writer)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route_to_agent)

# Workers ke baad wapas supervisor jaao (ya END)
builder.add_edge("researcher", END)
builder.add_edge("coder", END)
builder.add_edge("writer", END)

graph = builder.compile()
```

**Note:** Workers directly END pe ja rahe hain upar ke example mein. Real apps mein workers wapas supervisor ko return karte hain for further orchestration.

---

### 2.2 Command Object — Route + State Update Ek Saath

LangGraph 0.2+ mein `Command` object aaya jo ek node ko allow karta hai:
1. **State update karo** — kuch fields change karo
2. **Next node decide karo** — routing bhi same function mein

```python
from langgraph.types import Command
from typing import Union

def supervisor_with_command(state: SupervisorState) -> Command[Literal["researcher", "coder", "writer"]]:
    """Command use karte hain — state update + routing ek saath"""
    task = state["task"].lower()
    
    if "research" in task:
        return Command(
            update={"next_agent": "researcher", "messages": ["Routing to researcher"]},
            goto="researcher"    # yahan directly node name dete hain
        )
    elif "code" in task:
        return Command(
            update={"next_agent": "coder"},
            goto="coder"
        )
    else:
        return Command(
            update={"next_agent": "writer"},
            goto="writer"
        )

# Command use karne se add_conditional_edges ki zaroorat nahi!
# Node khud hi next node decide kar leta hai
```

**Command ka fayda:**
- Cleaner code — routing logic node ke andar
- State update aur routing ek atomic operation mein
- Type hints se next possible nodes clearly visible

---

### 2.3 Worker Agent Specialization Pattern

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import TypedDict, Annotated, List
import operator

class ResearchState(TypedDict):
    query: str
    search_results: Annotated[list, operator.add]
    analysis: str
    final_report: str

# Researcher Agent — Tool use karta hai
def search_node(state: ResearchState) -> dict:
    """Web search simulate karo"""
    query = state["query"]
    # Real: TavilySearchResults tool use karo
    mock_results = [
        {"title": f"Article about {query}", "content": f"Detailed info about {query}..."},
        {"title": f"Research on {query}", "content": f"Academic perspective on {query}..."},
    ]
    return {"search_results": mock_results}

def analyze_node(state: ResearchState) -> dict:
    """Search results analyze karo"""
    results = state["search_results"]
    # Real: LLM call karo
    analysis = f"Analysis of {len(results)} results: Key themes identified..."
    return {"analysis": analysis}

def format_report_node(state: ResearchState) -> dict:
    """Final report format karo"""
    return {
        "final_report": f"# Research Report\n\n"
                       f"## Query: {state['query']}\n\n"
                       f"## Analysis\n{state['analysis']}\n\n"
                       f"## Sources\n{len(state['search_results'])} sources consulted"
    }
```

---

### 2.4 Handoff Patterns Between Agents

**Pattern 1: Linear Handoff** — A → B → C → END

```python
# Simple pipeline
builder.add_edge("researcher", "analyzer")
builder.add_edge("analyzer", "writer")
builder.add_edge("writer", END)
```

**Pattern 2: Hub-and-Spoke** — Supervisor routes to any worker

```python
# Supervisor central hub hai
builder.add_conditional_edges("supervisor", router_function, {
    "researcher": "researcher",
    "coder": "coder", 
    "writer": "writer",
    "done": END
})
# Har worker wapas supervisor ko report karta hai
for worker in ["researcher", "coder", "writer"]:
    builder.add_edge(worker, "supervisor")
```

**Pattern 3: Peer-to-Peer** — Agents directly ek doosre ko call karte hain

```python
# Coder reviewer ko call karta hai
builder.add_edge("coder", "reviewer")
# Reviewer approve kare toh END, reject kare toh coder wapas
builder.add_conditional_edges("reviewer", review_decision, {
    "approved": END,
    "needs_revision": "coder"
})
```

---

## 3. State Design

### 3.1 TypedDict vs Pydantic BaseModel

**TypedDict** — LangGraph ka default, lightweight:

```python
from typing import TypedDict, Annotated
import operator

class SimpleState(TypedDict):
    messages: Annotated[list, operator.add]  # reducer laga sakte ho
    name: str
    count: int
    data: dict
```

**Pydantic BaseModel** — validation chahiye toh:

```python
from pydantic import BaseModel, Field, validator
from typing import Annotated, List
import operator

class ValidatedState(BaseModel):
    messages: Annotated[List[str], operator.add] = Field(default_factory=list)
    name: str = Field(min_length=1, max_length=100)
    count: int = Field(default=0, ge=0)  # >= 0
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        return v.strip()
    
    class Config:
        arbitrary_types_allowed = True  # LangGraph types ke liye

# Pydantic state use karte waqt
builder = StateGraph(ValidatedState)
# Pydantic automatically validate karega har state update pe
```

**Kab kya use karein?**
- TypedDict: Fast prototyping, simple workflows, performance-critical
- Pydantic: External APIs, user input validation, strict type enforcement, prod systems

---

### 3.2 Annotated Reducers — Messages Append Karna

```python
from typing import Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class MessagingState(TypedDict):
    # operator.add — simple list append
    logs: Annotated[list, operator.add]
    
    # add_messages — LangChain messages ke liye, deduplication bhi karta hai
    messages: Annotated[list[BaseMessage], add_messages]

# Node kya return kare:
def my_node(state):
    return {
        "logs": ["New log entry"],          # existing logs mein ADD hoga
        "messages": [HumanMessage("Hi")]   # messages mein ADD hoga
        # Sirf changes return karo — poori list nahi!
    }
```

**Bina reducer ke:**
```python
class BadState(TypedDict):
    messages: list  # no reducer

def node_a(state):
    return {"messages": ["new message"]}  # POORI list replace ho jayegi!
    # Previous messages LOST ho jayenge!
```

---

### 3.3 Custom Reducers — Advanced Patterns

```python
from typing import Annotated, Any, Dict
import operator

# Reducer 1: Dict merge karna
def merge_dicts(existing: dict, new: dict) -> dict:
    """Dono dicts merge karo — new values override karengi"""
    return {**existing, **new}

# Reducer 2: Deduplication
def deduplicate_list(existing: list, new: list) -> list:
    """Duplicates remove karo"""
    combined = existing + new
    seen = set()
    result = []
    for item in combined:
        key = item if not isinstance(item, dict) else str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

# Reducer 3: Max value
def take_max(existing: int, new: int) -> int:
    """Sirf maximum value rakhho"""
    return max(existing, new)

# Reducer 4: Running count
def increment(existing: int, new: int) -> int:
    return existing + new

# Custom reducers use karte hue state mein:
class AdvancedState(TypedDict):
    metadata: Annotated[dict, merge_dicts]
    unique_items: Annotated[list, deduplicate_list]
    max_score: Annotated[int, take_max]
    total_tokens: Annotated[int, increment]

# Usage:
def node_1(state): return {"max_score": 85, "total_tokens": 100}
def node_2(state): return {"max_score": 92, "total_tokens": 150}
# After both: max_score=92, total_tokens=250 — reducer automatically kaam karta hai
```

---

### 3.4 Channels — LangGraph Internals

LangGraph internally state fields ko **Channels** ke roop mein manage karta hai:

**LastValue Channel** — Default, no reducer:
```python
# Sirf last written value store hoti hai
# Har node jo yeh field update kare, pichli value replace ho jaati hai
counter: int  # LastValue channel — koi reducer nahi
```

**BinaryOperatorAggregate Channel** — Annotated reducer wali fields:
```python
# Binary operator (jaise operator.add) use karta hai values combine karne ke liye
messages: Annotated[list, operator.add]  # BinaryOperatorAggregate channel
```

**Topic Channel** — Multiple producers, consumers:
```python
# Advanced: Multiple nodes ek saath likhte hain, order guaranteed nahi
# Parallel execution mein useful
```

---

### 3.5 State Schema Evolution — Production Mein

```python
# Version 1
class StateV1(TypedDict):
    messages: list
    task: str

# Version 2 — new field add karo with default
class StateV2(TypedDict):
    messages: list
    task: str
    priority: int  # Naya field — existing checkpoints mein nahi hoga

# Backward compatibility ke liye:
def node_with_defaults(state: StateV2) -> dict:
    priority = state.get("priority", 0)  # .get() with default — old checkpoints support
    return {"priority": priority + 1}

# Ya StateV2 mein total_keys check karo
```

---

## 4. Subgraphs

### Concept — Modules Ki Tarah

Subgraph ek **separate StateGraph** hoti hai jo ek parent graph ke **node ki tarah** behave karti hai. 

```
Parent Graph:
  input_node → [subgraph_node] → output_node

Subgraph (internally):
  step_1 → step_2 → step_3
```

**Kyon use karein?**
- **Modularity** — complex workflows ko manageable pieces mein todna
- **Reusability** — same subgraph multiple parent graphs mein use
- **Testing** — subgraph independently test karo
- **Team work** — different teams alag subgraphs pe kaam kar sakti hain

---

### 4.1 Subgraph Define Karna

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
import operator

# Subgraph ka apna state
class ResearchSubgraphState(TypedDict):
    query: str                                   # parent se aata hai
    search_results: Annotated[list, operator.add]
    summary: str                                 # parent ko return karte hain

# Subgraph ke nodes
def web_search(state: ResearchSubgraphState) -> dict:
    return {"search_results": [f"Result 1 for {state['query']}", 
                                f"Result 2 for {state['query']}"]}

def summarize_results(state: ResearchSubgraphState) -> dict:
    results = state["search_results"]
    summary = f"Summary of {len(results)} results: Key findings..."
    return {"summary": summary}

def format_output(state: ResearchSubgraphState) -> dict:
    return {"summary": f"[FORMATTED] {state['summary']}"}

# Subgraph banao
research_builder = StateGraph(ResearchSubgraphState)
research_builder.add_node("web_search", web_search)
research_builder.add_node("summarize", summarize_results)
research_builder.add_node("format", format_output)
research_builder.add_edge(START, "web_search")
research_builder.add_edge("web_search", "summarize")
research_builder.add_edge("summarize", "format")
research_builder.add_edge("format", END)

# Subgraph compile karo
research_subgraph = research_builder.compile()
```

---

### 4.2 Parent Graph Mein Subgraph Ko Node Ki Tarah Use Karna

```python
# Parent graph ka state
class ParentState(TypedDict):
    user_request: str
    query: str              # subgraph ke liye input
    research_summary: str   # subgraph se output
    final_answer: str

# Parent nodes
def prepare_query(state: ParentState) -> dict:
    """User request se search query nikalo"""
    return {"query": f"search: {state['user_request']}"}

def generate_answer(state: ParentState) -> dict:
    """Research summary se final answer banao"""
    return {"final_answer": f"Based on research: {state['research_summary']}"}

# IMPORTANT: Subgraph ko parent state se connect karne ke liye wrapper function
def research_node(state: ParentState) -> dict:
    """Subgraph wrapper — state mapping karo"""
    # Parent state → Subgraph state
    subgraph_input = {"query": state["query"], "search_results": [], "summary": ""}
    
    # Subgraph invoke karo
    subgraph_output = research_subgraph.invoke(subgraph_input)
    
    # Subgraph state → Parent state
    return {"research_summary": subgraph_output["summary"]}

# Parent graph banao
parent_builder = StateGraph(ParentState)
parent_builder.add_node("prepare_query", prepare_query)
parent_builder.add_node("research", research_node)  # subgraph yahan hai
parent_builder.add_node("generate_answer", generate_answer)

parent_builder.add_edge(START, "prepare_query")
parent_builder.add_edge("prepare_query", "research")
parent_builder.add_edge("research", "generate_answer")
parent_builder.add_edge("generate_answer", END)

parent_graph = parent_builder.compile()

result = parent_graph.invoke({
    "user_request": "Tell me about Python asyncio",
    "query": "",
    "research_summary": "",
    "final_answer": ""
})
```

---

### 4.3 Direct Subgraph Node (State Sharing)

Agar parent aur subgraph mein **common state fields** hain toh directly subgraph add kar sakte ho:

```python
# Parent aur subgraph dono mein 'query' aur 'summary' fields hain
# Toh direct add karo — LangGraph state automatically map karta hai
parent_builder.add_node("research", research_subgraph)  # directly compiled subgraph!

# LangGraph automatically common fields share karega
# Parent state se 'query' subgraph ko milega
# Subgraph ka 'summary' parent state mein merge ho jayega
```

---

## 5. Checkpointers — State Persistence

### Kyun Zaroori Hai?

Production apps mein:
- **Long conversations** — user wapas aaye toh history yaad ho
- **HITL** — graph pause ho, human review kare, phir continue
- **Fault tolerance** — server crash ho toh wahan se resume karo jahan tha
- **Multi-user** — har user ka apna conversation context

---

### 5.1 MemorySaver — Testing Ke Liye

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()  # RAM mein store hota hai

graph = builder.compile(checkpointer=memory)

# thread_id se conversations isolate hoti hain
config_alice = {"configurable": {"thread_id": "alice-session-001"}}
config_bob = {"configurable": {"thread_id": "bob-session-001"}}

# Alice ka conversation
result1 = graph.invoke({"messages": ["Hello!"], "task": "research AI"}, config_alice)
result2 = graph.invoke({"messages": ["More details please"], "task": ""}, config_alice)
# Alice ko previous context yaad hai!

# Bob ka alag conversation
result3 = graph.invoke({"messages": ["Hi, I need help"], "task": "write code"}, config_bob)
# Bob ko Alice ka context nahi milta

# Process restart hone pe MemorySaver data LOST ho jata hai
# Production mein use mat karo!
```

---

### 5.2 SqliteSaver — Local Development

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# NOTE: from_conn_string() ek CONTEXT MANAGER return karta hai — saver object nahi.
# Isliye `with` ke andar use karo (AsyncSqliteSaver/PostgresSaver bhi aise hi):
with SqliteSaver.from_conn_string("./checkpoints.db") as memory:   # disk pe persist
    graph = builder.compile(checkpointer=memory)
    # ... graph.invoke(...) isi block ke andar karo

# (Galat: `memory = SqliteSaver.from_conn_string(...)` seedha assign karna — wo CM hai, saver nahi.)

# Conversations restart ke baad bhi yaad rehti hain (file-based mein)
config = {"configurable": {"thread_id": "persistent-user-123"}}
graph.invoke({"messages": ["Hello"], "task": "do research"}, config)

# Baad mein — server restart ke baad bhi kaam karta hai
result = graph.invoke({"messages": ["Continue please"]}, config)
# Previous state se continue hoga!
```

---

### 5.3 AsyncSqliteSaver — Async Apps Ke Liye

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import asyncio

async def main():
    async with AsyncSqliteSaver.from_conn_string("./async_checkpoints.db") as memory:
        graph = builder.compile(checkpointer=memory)
        
        config = {"configurable": {"thread_id": "async-user-456"}}
        
        # Async invoke
        result = await graph.ainvoke({"messages": ["Hello async"], "task": "test"}, config)
        
        # Async stream
        async for chunk in graph.astream({"messages": ["More"]}, config):
            print(chunk)

asyncio.run(main())
```

---

### 5.4 State Inspection — Checkpoint History

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "debug-session"}}

# Kuch steps chalao
graph.invoke({"messages": ["Step 1"], "counter": 0}, config)
graph.invoke({"messages": ["Step 2"]}, config)
graph.invoke({"messages": ["Step 3"]}, config)

# *** Current state dekho ***
current_state = graph.get_state(config)
print("Current values:", current_state.values)       # poora current state
print("Next nodes:", current_state.next)              # next mein kya chalega
print("Config:", current_state.config)               # checkpoint ki details
print("Metadata:", current_state.metadata)           # step number, etc.

# *** State history dekho ***
print("\n=== State History ===")
for checkpoint in graph.get_state_history(config):
    step = checkpoint.metadata.get("step", "?")
    print(f"Step {step}: messages count = {len(checkpoint.values.get('messages', []))}")

# *** State manually update karo ***
graph.update_state(config, {"counter": 100})  # kisi field ko force update karo
new_state = graph.get_state(config)
print("After update:", new_state.values["counter"])  # 100

# *** Specific checkpoint se replay karo ***
# get_state_history se koi checkpoint lo
history = list(graph.get_state_history(config))
old_checkpoint = history[-1]  # sabse purana

# Us checkpoint ki config se invoke karo
replay_config = old_checkpoint.config
result = graph.invoke(None, replay_config)  # wahan se resume!
```

---

## 6. Human-in-the-Loop (HITL)

### Concept — AI Ruko, Human Dekhe

HITL ka matlab hai graph execution ko **pause karna**, human ko review/approve karne dena, phir **resume karna**.

Real use cases:
- Dangerous actions — "delete all records" — manager approve kare pehle
- Legal/financial decisions — AI suggestion, human final call
- Content moderation — AI flags, human reviews
- Tool execution review — AI kya tool call karne wala hai — human check kare

---

### 6.1 interrupt_before — Node Ke Pehle Ruko

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

# compile mein batao — kaun se node ke PEHLE rukna hai
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["execute_dangerous_action"]  # list dete hain
)

config = {"configurable": {"thread_id": "hitl-demo"}}

# Graph chalao — execute_dangerous_action ke PEHLE ruk jayega
result = graph.invoke({"task": "delete old records", "approved": False}, config)
print("Graph paused before dangerous action")

# Human ko dikhao kya hone wala tha
state = graph.get_state(config)
print("Planned action:", state.values.get("planned_action"))

# Human approve karta hai — state update karo
graph.update_state(config, {"approved": True})

# Resume karo — None pass karo (naya input nahi)
final_result = graph.invoke(None, config)
print("Resumed:", final_result)
```

---

### 6.2 interrupt_after — Node Ke Baad Ruko

```python
# compile mein interrupt_after
graph = builder.compile(
    checkpointer=memory,
    interrupt_after=["ai_decision"]  # node chale, phir ruko
)

# Graph chale → ai_decision node execute ho → phir ruke
result = graph.invoke({"task": "classify email"}, config)

# State mein AI ka decision dekho
state = graph.get_state(config)
ai_decision = state.values.get("decision")
print(f"AI decided: {ai_decision}")

# Agar human disagree kare — state override karo
graph.update_state(config, {"decision": "human_override_value"})

# Continue
graph.invoke(None, config)
```

---

### 6.3 interrupt() Function — Node Ke Andar Se

LangGraph 0.2+ mein nodes ke andar se interrupt call kar sakte ho:

```python
from langgraph.types import interrupt

def review_before_action(state):
    """Node jab HITL chahiye"""
    planned_action = state["planned_action"]
    
    # interrupt() call karo — graph yahan pause ho jayega
    # Koi bhi value pass karo — yeh human ko dikhegi
    human_response = interrupt({
        "message": f"Please review this action: {planned_action}",
        "action": planned_action,
        "requires": "approval"
    })
    
    # Jab human resume kare aur value provide kare,
    # human_response mein woh value hogi
    approved = human_response.get("approved", False)
    
    return {"approved": approved}

# interrupt() ke saath compile — checkpointer ZAROORI hai
graph = builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "interrupt-demo"}}

# Run until interrupt
graph.invoke({"planned_action": "send email to all users"}, config)

# State check karo
state = graph.get_state(config)
print("Interrupted at:", state.next)  # ['review_before_action'] ya next node

# Human ka response provide karo — Command ke saath resume
from langgraph.types import Command

# Human approve karta hai
graph.invoke(Command(resume={"approved": True}), config)
```

---

### 6.4 Tool Call Review Pattern

Production mein sabse common HITL pattern — AI tool call karne se pehle human check kare:

```python
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
import json

def should_continue_or_review(state):
    """Messages check karo — tool calls hain toh review ke liye bhejo"""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Koi dangerous tool hai?
        for tool_call in last_message.tool_calls:
            if tool_call["name"] in ["delete_records", "send_bulk_email", "charge_customer"]:
                return "human_review"  # dangerous — human se poocho
        return "tools"  # safe tools — directly chalao
    return "end"

# Graph mein:
builder.add_conditional_edges("agent", should_continue_or_review, {
    "tools": "tool_node",          # direct execute
    "human_review": "review_node", # pause for human
    "end": END
})

def review_node(state):
    """Interrupt karo — human ko tool calls dikhao"""
    messages = state["messages"]
    last = messages[-1]
    tool_calls_str = json.dumps(last.tool_calls, indent=2)
    
    # interrupt() — graph yahan freeze
    decision = interrupt(f"Review tool calls:\n{tool_calls_str}\nApprove? (yes/no)")
    
    if decision.lower() == "yes":
        return {}  # state unchanged — tool_node pe continue
    else:
        # Tool calls remove karo — AI ko different approach lene do
        return {"messages": [AIMessage(content="Action cancelled by human reviewer")]}
```

---

## 7. Streaming

### Kyun Streaming?

User experience ke liye zaroori hai:
- Long-running graphs mein user ko lage kuch ho raha hai
- Real-time feedback — har step ka output dikhao
- LLM token streaming — words ek-ek karke type hote dikhein
- Progressive loading — frontend pe partial results dikhao

---

### 7.1 stream_mode Samjho

```python
graph = builder.compile()
config = {"configurable": {"thread_id": "stream-test"}}
input_data = {"messages": ["Hello"], "task": "research AI"}

# ── stream_mode="updates" (DEFAULT) ──────────────────────────────
# Har node ke baad sirf CHANGED fields milti hain
for chunk in graph.stream(input_data, config, stream_mode="updates"):
    print(chunk)
# Output:
# {"supervisor": {"next_agent": "researcher"}}
# {"researcher": {"results": ["found data"]}}
# Lightweight — sirf diff

# ── stream_mode="values" ──────────────────────────────────────────
# Har node ke baad POORA state milta hai
for state in graph.stream(input_data, config, stream_mode="values"):
    print(state)
# Output:
# {"messages": ["Hello"], "task": "research AI", "next_agent": "", "results": []}
# {"messages": ["Hello"], "task": "research AI", "next_agent": "researcher", "results": []}
# {"messages": ["Hello", "Researcher done"], "task": "research AI", "results": ["found data"]}
# Heavier — full state har bar

# ── stream_mode="messages" ────────────────────────────────────────
# LLM tokens stream hote hain — word by word
for message_chunk, metadata in graph.stream(input_data, config, stream_mode="messages"):
    if hasattr(message_chunk, "content"):
        print(message_chunk.content, end="", flush=True)
# "The" "research" "shows" "that" "..." — real-time typing effect!

# ── stream_mode="events" ─────────────────────────────────────────
# All LangChain events — most detailed
for event in graph.stream(input_data, config, stream_mode="events"):
    print(event["event"], event.get("name", ""))
# on_chain_start, on_llm_start, on_tool_start, etc.
```

---

### 7.2 Async Streaming — FastAPI ke liye

```python
import asyncio
from langgraph.graph import StateGraph

async def async_stream_demo():
    graph = builder.compile(checkpointer=memory)
    config = {"configurable": {"thread_id": "async-stream"}}
    
    print("=== astream() with updates ===")
    async for chunk in graph.astream(input_data, config, stream_mode="updates"):
        print(f"Update: {chunk}")
    
    print("\n=== astream_events() ===")
    async for event in graph.astream_events(input_data, config, version="v2"):
        kind = event["event"]
        name = event.get("name", "")
        if kind == "on_chain_start" and name not in ("LangGraph",):
            print(f"Starting: {name}")
        elif kind == "on_chain_end" and name not in ("LangGraph",):
            print(f"Completed: {name}")
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            print(chunk.content, end="", flush=True)

asyncio.run(async_stream_demo())
```

---

### 7.3 FastAPI SSE Streaming

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(request: dict):
    thread_id = request.get("thread_id", "default")
    user_message = request["message"]
    
    config = {"configurable": {"thread_id": thread_id}}
    input_data = {"messages": [user_message], "task": user_message}
    
    async def event_generator():
        async for chunk in graph.astream(input_data, config, stream_mode="updates"):
            # SSE format: "data: {json}\n\n"
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
```

---

## 8. Parallel Execution — Send API

### Concept — Fan-Out aur Fan-In

Kai baar ek kaam ko parallel mein karna hota hai:
- 5 topics pe research — parallel mein 5 researcher run karo
- 10 documents review — parallel mein 10 reviewer
- Multiple APIs call — ek saath call karo

**Send API** yahi karne deta hai:

```python
from langgraph.types import Send
```

---

### 8.1 Map-Reduce Pattern

```python
from typing import TypedDict, Annotated, List
from langgraph.types import Send
from langgraph.graph import StateGraph, START, END
import operator

class ParallelState(TypedDict):
    topics: List[str]                          # input: research karne ke topics
    results: Annotated[List[str], operator.add] # output: parallel results merge honge
    final_report: str

def split_topics(state: ParallelState):
    """Fan-out — har topic ke liye ek Send"""
    return [
        Send("research_one_topic", {"topic": topic, "results": []})
        for topic in state["topics"]
    ]
    # Yeh list return karna fan-out karta hai
    # Har Send ek alag node instance chalata hai — PARALLEL mein!

def research_one_topic(state: dict) -> dict:
    """Parallel mein chalta hai — har topic ke liye alag instance"""
    topic = state["topic"]
    # Real: web search, LLM call, etc.
    finding = f"Research about '{topic}': Important facts discovered. " \
               f"Key data points: X, Y, Z."
    return {"results": [finding]}  # yeh parent state ke results mein ADD hoga

def merge_results(state: ParallelState) -> dict:
    """Fan-in — sab parallel results merge karo"""
    all_results = state["results"]  # automatically sab results aa gaye (operator.add se)
    
    report = "# Research Report\n\n"
    for i, result in enumerate(all_results, 1):
        report += f"## Topic {i}\n{result}\n\n"
    
    return {"final_report": report}

# Graph
builder = StateGraph(ParallelState)
builder.add_node("research_one_topic", research_one_topic)
builder.add_node("merge_results", merge_results)

# Conditional edge jo Send objects return karta hai = fan-out
builder.add_conditional_edges(START, split_topics, ["research_one_topic"])
                                                  # ^ allowed nodes list

# Sab parallel nodes ke baad merge
builder.add_edge("research_one_topic", "merge_results")
builder.add_edge("merge_results", END)

parallel_graph = builder.compile()

result = parallel_graph.invoke({
    "topics": ["Python asyncio", "LangGraph", "FastAPI", "PostgreSQL"],
    "results": [],
    "final_report": ""
})
print(result["final_report"])
```

---

### 8.2 Dynamic Number of Workers

```python
def create_dynamic_workers(state: ParallelState):
    """Topics ki count pe depend karta hai — har baar different count"""
    topics = state["topics"]
    
    # Har topic ke liye custom state bhi bhej sakte ho
    sends = []
    for i, topic in enumerate(topics):
        sends.append(Send("worker", {
            "topic": topic,
            "index": i,
            "priority": "high" if i < 2 else "normal",  # custom state
            "results": []
        }))
    
    return sends

# Agar topics = 4, toh 4 parallel workers
# Agar topics = 100, toh 100 parallel workers
```

---

## 9. Prebuilt Components

### 9.1 create_react_agent() — Quick Start

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI  # ya koi bhi LLM

@tool
def search_web(query: str) -> str:
    """Search the web for information"""
    return f"Search results for '{query}': Found relevant information..."

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"

llm = ChatOpenAI(model="gpt-4o-mini")
tools = [search_web, calculate]

# Ek line mein ReAct agent!
agent = create_react_agent(llm, tools)

# Use karo
result = agent.invoke({
    "messages": [("user", "What is 25 * 4? Also search for Python best practices")]
})
print(result["messages"][-1].content)

# Checkpointer bhi add kar sakte ho
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
agent_with_memory = create_react_agent(llm, tools, checkpointer=memory)
```

---

### 9.2 ToolNode — Manual Tool Execution

```python
from langgraph.prebuilt import ToolNode, tools_condition

# Tools define karo
@tool
def get_temperature(city: str) -> str:
    """Get current temperature for a city"""
    temps = {"Mumbai": "32°C", "Delhi": "28°C", "Bangalore": "22°C"}
    return temps.get(city, "Unknown city")

tools_list = [get_temperature, calculate]

# ToolNode automatically:
# 1. Last message se tool_calls extract karta hai
# 2. Har tool call execute karta hai
# 3. Tool results ko messages mein add karta hai
tool_node = ToolNode(tools_list)

# Graph mein:
def call_model(state):
    model_with_tools = llm.bind_tools(tools_list)
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}

builder = StateGraph(MessagesState)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)  # ToolNode is a node

builder.add_edge(START, "agent")
# tools_condition: agar last message mein tool_calls hain toh "tools", warna END
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")  # tools ke baad wapas agent

graph = builder.compile()
```

---

### 9.3 MessagesState — Built-in State

```python
from langgraph.graph import MessagesState
# MessagesState = TypedDict with:
#   messages: Annotated[List[BaseMessage], add_messages]
# Bas itna hai — aur kuch nahi

# Simple agents ke liye perfect
class MyState(MessagesState):
    # Extra fields add karo
    user_name: str
    session_id: str

# Agar aur kuch nahi chahiye:
builder = StateGraph(MessagesState)
```

---

## 10. Error Handling in Graphs

### 10.1 Node Level Error Handling

```python
def risky_node(state):
    """Node jo fail ho sakta hai"""
    try:
        result = some_external_api_call()
        return {"result": result, "error": None}
    except ConnectionError as e:
        return {"result": None, "error": f"Connection failed: {e}"}
    except Exception as e:
        return {"result": None, "error": f"Unexpected error: {e}"}

def after_risky(state):
    """Error check karo"""
    if state.get("error"):
        # Error recovery
        return {"result": "fallback response", "error": None}
    return {}  # no change needed
```

---

### 10.2 RetryPolicy

```python
from langgraph.pregel import RetryPolicy

# Node ke liye retry policy
retry = RetryPolicy(
    max_attempts=3,         # kitni baar retry karein
    initial_interval=1.0,   # pehli retry ke pehle wait (seconds)
    backoff_factor=2.0,     # exponential backoff: 1s, 2s, 4s
    jitter=True,            # random jitter add karo
    retry_on=Exception      # kaunsi exceptions pe retry
)

# Graph mein node add karte waqt retry policy do
builder.add_node("flaky_api_node", risky_node, retry=retry)
# Ab yeh node automatically 3 baar retry karega failure pe
```

---

### 10.3 Fallback Node Pattern

```python
class RobustState(TypedDict):
    task: str
    result: str
    error: str
    attempt: int

def primary_node(state):
    # Kuch karo
    if some_condition_fails:
        raise Exception("Primary failed")
    return {"result": "success", "error": ""}

def error_handler_node(state):
    """Fallback when primary fails"""
    error = state.get("error", "Unknown error")
    print(f"Handling error: {error}")
    return {"result": "fallback result", "error": ""}

def route_after_primary(state):
    if state.get("error"):
        return "error_handler"
    return "next_step"

# Ya try/except ke saath:
def safe_primary_node(state):
    try:
        return primary_node(state)
    except Exception as e:
        return {"error": str(e), "result": ""}

builder.add_node("primary", safe_primary_node)
builder.add_node("error_handler", error_handler_node)
builder.add_node("next_step", some_other_node)

builder.add_conditional_edges("primary", route_after_primary, {
    "error_handler": "error_handler",
    "next_step": "next_step"
})
builder.add_edge("error_handler", "next_step")  # error handle karo, continue karo
```

---

### 10.4 GraphRecursionError

```python
from langgraph.errors import GraphRecursionError

# Default recursion limit = 25
# Kisi bhi loop mein 25 se zyada steps hue toh error

# Limit badhana:
config = {
    "configurable": {"thread_id": "thread-1"},
    "recursion_limit": 100  # 100 steps allow karo
}

try:
    result = graph.invoke(input_data, config)
except GraphRecursionError as e:
    print(f"Graph exceeded recursion limit: {e}")
    # Handle gracefully

# Best practice: graph mein hi loop breaking condition daalo
def supervisor(state):
    if state["iteration"] >= 10:
        return {"next": END}  # Force stop
    # ... normal logic
```

---

## 11. LangGraph with FastAPI

### Production-Ready Async Setup

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import asyncio
import json
import uuid

app = FastAPI(title="LangGraph API")

# Global graph instance
graph = None
checkpointer = None

@app.on_event("startup")
async def startup():
    global graph, checkpointer
    checkpointer = AsyncSqliteSaver.from_conn_string("./prod_checkpoints.db")
    # Graph compile karo — ek baar
    graph = builder.compile(checkpointer=checkpointer)

class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None  # None = new conversation

class ChatResponse(BaseModel):
    thread_id: str
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        result = await graph.ainvoke(
            {"messages": [request.message], "task": request.message},
            config
        )
        return ChatResponse(
            thread_id=thread_id,
            response=result["messages"][-1] if result.get("messages") else "Done"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    async def event_stream():
        # Thread ID pehle bhejo
        yield f"data: {json.dumps({'thread_id': thread_id, 'type': 'start'})}\n\n"
        
        try:
            async for chunk in graph.astream(
                {"messages": [request.message], "task": request.message},
                config,
                stream_mode="updates"
            ):
                yield f"data: {json.dumps({'type': 'update', 'data': str(chunk)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/chat/{thread_id}/history")
async def get_history(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    return {"thread_id": thread_id, "state": str(state.values)}

@app.post("/chat/{thread_id}/approve")
async def approve_action(thread_id: str, approved: bool):
    """HITL endpoint — human approval"""
    config = {"configurable": {"thread_id": thread_id}}
    await graph.aupdate_state(config, {"approved": approved})
    
    # Resume karo
    result = await graph.ainvoke(None, config)
    return {"status": "resumed", "result": str(result)}
```

---

## 12. LangGraph Studio

LangGraph Studio ek **visual debugger + playground** hai LangGraph workflows ke liye.

### Key Features:

**1. Graph Visualization**
- StateGraph ka visual diagram dikhata hai
- Nodes circles/boxes ke roop mein
- Edges arrows ke roop mein
- Current execution node highlight hota hai

**2. Time-Travel Debugging**
- Har step ka snapshot store hota hai (checkpointer required)
- Kisi bhi past state pe click karo — wahan se resume karo
- "What if" scenarios — state manually change karo, re-run karo
- Bug reproduce karo — exact checkpoint se replay

**3. State Inspector**
- Har node ke baad state ka JSON dikhata hai
- Nested state bhi clearly visible
- State changes highlighted

**4. Thread Management**
- Multiple conversations ek saath dekho
- Thread switch karo

**5. Interrupt Points**
- HITL nodes clearly marked
- Studio se directly approve/reject
- Input provide karo interrupted node ke liye

### Setup (Local):
```bash
# LangGraph CLI install karo
pip install langgraph-cli

# langgraph.json file banao
{
  "graphs": {
    "agent": "./my_graph.py:graph"
  },
  "dependencies": ["."]
}

# Studio chalao
langgraph dev
# Opens at http://localhost:2024
```

---

## 13. Real Use Cases with Code

### 13.1 Customer Support Bot with Escalation

```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import operator

class SupportState(TypedDict):
    messages: Annotated[list, operator.add]
    customer_id: str
    issue_type: str           # billing, technical, general
    sentiment: str            # positive, neutral, negative, angry
    escalated: bool
    resolution: str
    agent_notes: str

def triage_bot(state: SupportState) -> dict:
    """Issue classify karo"""
    message = state["messages"][-1] if state["messages"] else ""
    msg_lower = str(message).lower()
    
    # Issue type detect karo
    if any(w in msg_lower for w in ["bill", "charge", "payment", "refund"]):
        issue_type = "billing"
    elif any(w in msg_lower for w in ["not working", "error", "bug", "crash"]):
        issue_type = "technical"
    else:
        issue_type = "general"
    
    # Sentiment detect karo
    if any(w in msg_lower for w in ["angry", "furious", "terrible", "worst", "sue"]):
        sentiment = "angry"
    elif any(w in msg_lower for w in ["frustrated", "annoyed", "disappointed"]):
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    return {
        "issue_type": issue_type,
        "sentiment": sentiment,
        "messages": [f"[Triage] Issue: {issue_type}, Sentiment: {sentiment}"]
    }

def ai_support_agent(state: SupportState) -> dict:
    """AI first-line support"""
    issue = state["issue_type"]
    message = state["messages"][0] if state["messages"] else ""
    
    responses = {
        "billing": "I understand your billing concern. Let me check your account...",
        "technical": "I can help with technical issues. Have you tried clearing cache?",
        "general": "Thank you for contacting support. How can I help you today?"
    }
    
    response = responses.get(issue, "I'll be happy to help you.")
    return {
        "messages": [f"[AI Agent] {response}"],
        "resolution": "ai_attempted"
    }

def should_escalate(state: SupportState) -> Literal["escalate", "resolve"]:
    """Escalate karna chahiye?"""
    if state["sentiment"] == "angry":
        return "escalate"
    if state["issue_type"] == "billing" and "refund" in str(state["messages"]).lower():
        return "escalate"
    return "resolve"

def human_escalation(state: SupportState) -> dict:
    """Human agent ke liye escalate karo"""
    return {
        "escalated": True,
        "messages": [
            "[System] Escalating to human agent...",
            "[System] A human agent will join in 2-3 minutes"
        ],
        "resolution": "escalated_to_human"
    }

def auto_resolve(state: SupportState) -> dict:
    """AI resolution"""
    return {
        "escalated": False,
        "messages": ["[AI Agent] Is there anything else I can help you with?"],
        "resolution": "resolved_by_ai"
    }

# Support graph
support_builder = StateGraph(SupportState)
support_builder.add_node("triage", triage_bot)
support_builder.add_node("ai_support", ai_support_agent)
support_builder.add_node("escalation", human_escalation)
support_builder.add_node("resolve", auto_resolve)

support_builder.add_edge(START, "triage")
support_builder.add_edge("triage", "ai_support")
support_builder.add_conditional_edges("ai_support", should_escalate, {
    "escalate": "escalation",
    "resolve": "resolve"
})
support_builder.add_edge("escalation", END)
support_builder.add_edge("resolve", END)

support_graph = support_builder.compile(checkpointer=MemorySaver())
```

---

### 13.2 Code Review Pipeline

```python
class CodeReviewState(TypedDict):
    code_snippet: str
    language: str
    review_comments: Annotated[list, operator.add]
    quality_score: int
    approved: bool
    revision_count: int

def code_writer(state: CodeReviewState) -> dict:
    """Code generate karo (ya receive karo)"""
    return {"messages": [f"Code submitted for review: {state['code_snippet'][:50]}..."]}

def code_reviewer(state: CodeReviewState) -> dict:
    """Automated code review"""
    code = state["code_snippet"]
    comments = []
    score = 100
    
    # Simple checks (real mein: AST analysis, linters, etc.)
    if "eval(" in code:
        comments.append("⚠️ Avoid eval() — security risk")
        score -= 20
    if "password" in code.lower() and "=" in code:
        comments.append("🚨 Possible hardcoded password detected")
        score -= 30
    if len(code.split("\n")) > 50:
        comments.append("📝 Function too long — consider refactoring")
        score -= 10
    if not any(line.strip().startswith("#") for line in code.split("\n")):
        comments.append("💬 No comments — add documentation")
        score -= 10
    
    if not comments:
        comments.append("✅ Code looks good!")
    
    return {
        "review_comments": comments,
        "quality_score": max(score, 0)
    }

def senior_reviewer(state: CodeReviewState) -> dict:
    """Senior reviewer — high-level architecture review"""
    score = state["quality_score"]
    comments = []
    
    if score < 70:
        comments.append("🔴 Senior Review: Significant issues found, needs revision")
    elif score < 90:
        comments.append("🟡 Senior Review: Minor issues, approve with changes")
    else:
        comments.append("🟢 Senior Review: Approved!")
    
    return {"review_comments": comments, "approved": score >= 70}

def approval_gate(state: CodeReviewState) -> Literal["approved", "needs_revision"]:
    """Approve karo ya revision chahiye?"""
    if state["approved"] and state["quality_score"] >= 70:
        return "approved"
    if state["revision_count"] >= 3:
        return "approved"  # Force approve after 3 revisions
    return "needs_revision"

def request_revision(state: CodeReviewState) -> dict:
    """Revision request karo"""
    return {
        "review_comments": [f"🔄 Revision {state['revision_count'] + 1} requested"],
        "revision_count": state["revision_count"] + 1,
        "approved": False
    }

# Pipeline
review_builder = StateGraph(CodeReviewState)
review_builder.add_node("write", code_writer)
review_builder.add_node("review", code_reviewer)
review_builder.add_node("senior_review", senior_reviewer)
review_builder.add_node("revision", request_revision)

review_builder.add_edge(START, "write")
review_builder.add_edge("write", "review")
review_builder.add_edge("review", "senior_review")
review_builder.add_conditional_edges("senior_review", approval_gate, {
    "approved": END,
    "needs_revision": "revision"
})
review_builder.add_edge("revision", "review")  # Re-review after revision

review_graph = review_builder.compile()
```

---

### 13.3 Research Agent with Web Search + Summarize

```python
class ResearchAgentState(TypedDict):
    query: str
    search_results: Annotated[list, operator.add]
    summaries: Annotated[list, operator.add]
    final_report: str
    iteration: int
    search_queries: Annotated[list, operator.add]

def query_expander(state: ResearchAgentState) -> dict:
    """Original query se multiple search queries banao"""
    query = state["query"]
    # Real: LLM se query expansion
    queries = [
        query,
        f"{query} best practices",
        f"{query} examples",
        f"{query} tutorial"
    ]
    return {"search_queries": queries}

def web_searcher(state: ResearchAgentState) -> dict:
    """Har query ke liye search karo"""
    queries = state["search_queries"]
    results = []
    
    for query in queries[:3]:  # Limit to 3
        # Real: TavilySearchResults().invoke(query)
        results.append({
            "query": query,
            "results": [
                {"title": f"Article: {query}", "content": f"Content about {query}..."},
                {"title": f"Guide: {query}", "content": f"Detailed guide for {query}..."}
            ]
        })
    
    return {"search_results": results}

def summarizer(state: ResearchAgentState) -> dict:
    """Search results summarize karo"""
    results = state["search_results"]
    summaries = []
    
    for result_set in results:
        query = result_set["query"]
        count = len(result_set["results"])
        summary = f"For '{query}': Found {count} relevant articles. " \
                  f"Key topics: implementation, best practices, examples."
        summaries.append(summary)
    
    return {"summaries": summaries}

def report_writer(state: ResearchAgentState) -> dict:
    """Final report likho"""
    summaries = state["summaries"]
    report = f"# Research Report: {state['query']}\n\n"
    report += f"## Executive Summary\n"
    report += f"Comprehensive research on '{state['query']}' completed.\n\n"
    report += f"## Findings\n"
    for i, summary in enumerate(summaries, 1):
        report += f"{i}. {summary}\n"
    report += f"\n## Conclusion\nResearch complete. {len(summaries)} sources analyzed."
    
    return {"final_report": report}

# Research graph
research_builder = StateGraph(ResearchAgentState)
research_builder.add_node("expand_query", query_expander)
research_builder.add_node("search", web_searcher)
research_builder.add_node("summarize", summarizer)
research_builder.add_node("write_report", report_writer)

research_builder.add_edge(START, "expand_query")
research_builder.add_edge("expand_query", "search")
research_builder.add_edge("search", "summarize")
research_builder.add_edge("summarize", "write_report")
research_builder.add_edge("write_report", END)

research_graph = research_builder.compile()
```

---

## 14. Advanced Patterns

### 14.1 Conditional Subgraph Routing

```python
def route_to_specialized_subgraph(state):
    """Task type ke basis par alag subgraph chalao"""
    task_type = state["task_type"]
    
    if task_type == "research":
        subgraph_result = research_subgraph.invoke(state)
        return {"result": subgraph_result["final_report"]}
    elif task_type == "code":
        subgraph_result = code_subgraph.invoke(state)
        return {"result": subgraph_result["code_output"]}
    else:
        return {"result": "Unknown task type"}
```

### 14.2 State Versioning for Long-Running Workflows

```python
from datetime import datetime

class VersionedState(TypedDict):
    data: dict
    version: int
    last_modified: str
    history: Annotated[list, operator.add]

def update_with_version(state: VersionedState, new_data: dict) -> dict:
    """State update + version bump"""
    return {
        "data": {**state["data"], **new_data},
        "version": state["version"] + 1,
        "last_modified": datetime.now().isoformat(),
        "history": [{"version": state["version"], "data": state["data"]}]
    }
```

---

## 15. Interview Q&A — 15 Key Questions

### Q1: Checkpointer vs Memory — Kya Fark Hai?

**Answer:**
- **Checkpointer** = LangGraph infrastructure — state ko disk/memory mein persist karta hai. Thread-specific hota hai. `MemorySaver` (RAM), `SqliteSaver` (disk) — dono checkpointers hain.
- **Memory** (LangChain sense) = agent ke andar stored information — jaise user preferences, past facts. Separate concept.
- **Key point:** Checkpointer graph ke state ko save karta hai taaki interrupt/resume ho sake. Memory agent-level knowledge store karta hai.
- **Interview tip:** "Checkpointer state machine persistence handle karta hai, memory semantic information."

---

### Q2: HITL Implement Kaise Karte Hain LangGraph Mein?

**Answer:** 3 ways hain:
1. **`interrupt_before=["node"]`** — node ke PEHLE rukna, compile() mein dete hain
2. **`interrupt_after=["node"]`** — node ke BAAD rukna, compile() mein dete hain
3. **`interrupt()` function** — node ke andar se explicitly call karo (most flexible)

Implementation steps:
```
1. Checkpointer lagao (required)
2. compile() mein interrupt_before/after specify karo
3. graph.invoke() chalao — interrupt point pe rukta hai
4. graph.get_state() se current state dekho
5. graph.update_state() se human input daalo
6. graph.invoke(None, config) se resume karo
```

---

### Q3: Subgraph State Sharing Kaise Kaam Karta Hai?

**Answer:**
- Subgraph ka **apna state** hota hai, parent se alag
- **Option 1 — Wrapper function:** Parent state → transform → subgraph invoke → transform → parent state
- **Option 2 — Direct node:** Agar parent aur subgraph mein **same-named fields** hain toh LangGraph automatically map karta hai
- **Input/output mapping:** `input_map` aur `output_map` parameters se explicit mapping possible
- **Important:** Subgraph ke private fields parent ko nahi dikhte — sirf shared fields

---

### Q4: Send API Use Case Explain Karo

**Answer:**
Send API **dynamic fan-out** ke liye hai — runtime pe decide karo kitne parallel workers chahiye.

Use cases:
- **Map-reduce:** 10 documents → 10 parallel processors → merge results
- **Batch processing:** 1000 items → N workers → aggregate
- **Dynamic agents:** User input se determine hota hai kitne specialists chahiye

```python
# Conditional edge jo list of Sends return kare
def fan_out(state):
    return [Send("worker_node", {"item": item}) for item in state["items"]]
```

Traditional `add_edge`/`add_conditional_edges` static hain — pehle se decide karte hain. `Send` runtime pe decide karta hai.

---

### Q5: stream_mode Differences?

**Answer:**
| Mode | Kya milta hai | Kab use karein |
|------|--------------|----------------|
| `updates` | Sirf changed fields per node | Default, lightweight monitoring |
| `values` | Full state after each node | Debug, state tracking |
| `messages` | LLM tokens real-time | Chat UI, typing effect |
| `events` | All LangChain events | Detailed observability, logging |

`updates` fastest hai, `events` most detailed lekin heaviest.

---

### Q6: interrupt() Function Kaise Kaam Karta Hai?

**Answer:**
`interrupt()` node execution ko **pause** karta hai aur value store karta hai checkpoint mein.

Process:
1. Node mein `interrupt(value)` call hota hai
2. Graph checkpoint save karta hai current state
3. `GraphInterrupted` exception raise hoti hai (internally)
4. `invoke()` return kar deta hai — graph paused state mein hai
5. `get_state()` se `next` field mein current node dikhta hai
6. Human `update_state()` se input deta hai
7. `invoke(None, config)` se graph wahan se resume karta hai
8. `interrupt()` return karta hai human-provided value

**Key:** Checkpointer ke bina `interrupt()` kaam nahi karta — state save karna zaroori hai.

---

### Q7: Multi-Agent vs Single Agent — Kab Kya?

**Answer:**

**Single Agent use karo jab:**
- Task simple aur well-defined
- Context window mein fit hota hai
- Ek domain ki expertise kaafi hai
- Latency critical hai

**Multi-Agent use karo jab:**
- Task complex, multi-step
- Different expertise chahiye (research + code + write)
- Parallel execution possible hai
- Quality control chahiye (separate reviewer)
- Context window overflow hone ka risk

**Rule of thumb:** Start with single agent. Jab ek agent context overflow kare ya quality girne lage, tab multi-agent pe jaao.

---

### Q8: Supervisor Pattern Kab Use Karein?

**Answer:**
Supervisor pattern tab use karo jab:
- **Dynamic routing** chahiye — runtime pe decide ho kaun kaam kare
- **Workers specialized** hain lekin tasks varied hain
- **Coordination logic** complex hai
- **Quality gate** chahiye — supervisor result check kare

Alternatives:
- **Fixed pipeline:** Task simple linear hai — A → B → C
- **Peer-to-peer:** Agents directly communicate karte hain
- **Hierarchical:** Supervisor of supervisors (large scale)

Supervisor pattern overhead add karta hai — simple tasks ke liye overkill.

---

### Q9: thread_id Ka Purpose?

**Answer:**
`thread_id` ek **unique identifier** hai jo ek conversation/session ko isolate karta hai.

```python
config = {"configurable": {"thread_id": "user-alice-session-1"}}
```

- Ek hi graph multiple users ke liye alag conversations maintain karta hai
- Same thread_id = same conversation context
- Different thread_id = completely separate contexts, separate checkpoints
- Production mein: user_id + session_id combine karo — `f"{user_id}-{session_id}"`
- Thread_id se graph state isolate hoti hai — Bob ko Alice ka context nahi milta

---

### Q10: Reducer Function Kyun Chahiye?

**Answer:**
**Problem bina reducer ke:**
```python
class State(TypedDict):
    messages: list  # no reducer

# Node A: {"messages": ["msg1"]}  → state = ["msg1"]
# Node B: {"messages": ["msg2"]}  → state = ["msg2"]  ← msg1 LOST!
```

**Solution with reducer:**
```python
class State(TypedDict):
    messages: Annotated[list, operator.add]  # reducer = operator.add

# Node A: {"messages": ["msg1"]}  → state = ["msg1"]
# Node B: {"messages": ["msg2"]}  → state = ["msg1", "msg2"]  ← BOTH preserved!
```

Reducer batata hai LangGraph ko "jab is field pe naya value aaye toh existing ke saath kaise merge karein." Bina reducer ke har update pichla value overwrite kar deta hai.

---

### Q11: MemorySaver vs SqliteSaver Production Mein?

**Answer:**

| | MemorySaver | SqliteSaver |
|---|---|---|
| Storage | RAM | SQLite file/disk |
| Persistence | Process restart pe lost | File mein persist |
| Performance | Fast | Slightly slower |
| Use case | Testing, development | Local dev, small prod |
| Multi-process | No sharing | File sharing possible |

**Production mein kya use karein?**
- Development: MemorySaver ya SqliteSaver(":memory:")
- Local prod: SqliteSaver("./checkpoints.db")
- Real production: PostgreSQL checkpointer (`langgraph-checkpoint-postgres`) ya Redis-based

`AsyncSqliteSaver` FastAPI/async apps ke liye.

---

### Q12: Graph Recursion Limit Kya Hai aur Handle Kaise Karein?

**Answer:**
- Default limit = **25 steps** — ek invoke() call mein maximum 25 node executions
- `GraphRecursionError` raise hoti hai limit exceed hone pe
- Reason: Infinite loops se protect karna

Solutions:
```python
# 1. config mein limit badhao
config = {"recursion_limit": 50}

# 2. Graph mein hi exit condition daalo (BEST PRACTICE)
def supervisor(state):
    if state["steps"] >= 20:
        return {"next": "END"}
    state["steps"] += 1
    ...

# 3. Exception handle karo
try:
    result = graph.invoke(input, config)
except GraphRecursionError:
    # Graceful fallback
```

Best practice: Explicit exit conditions daalo — recursion limit pe depend mat karo.

---

### Q13: ToolNode Internally Kaise Kaam Karta Hai?

**Answer:**
ToolNode ek prebuilt node hai jo:

1. **Messages extract karta hai** — state se last `AIMessage` lo
2. **tool_calls check karta hai** — AIMessage mein tool_calls field hoti hai
3. **Har tool call execute karta hai:**
   - `tool_name` se actual tool function dhundho
   - `tool_args` pass karo
   - Result capture karo
4. **ToolMessage banata hai** — har tool result ke liye
5. **State update karta hai** — `{"messages": [ToolMessage(...)]}`

```python
# ToolNode internally yeh karta hai:
def tool_node_logic(state):
    last_message = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_fn = tools_dict[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return {"messages": tool_messages}
```

Error handling bhi built-in hai — `handle_tool_errors=True` se tool errors gracefully handle hote hain.

---

### Q14: Async Graph FastAPI Mein Kaise Use Karein?

**Answer:**
Key points:
1. **`AsyncSqliteSaver`** — async checkpointer
2. **`graph.ainvoke()`** — async invoke
3. **`graph.astream()`** — async streaming
4. **Startup event** mein graph initialize karo — ek baar
5. **Thread_id** = user session identifier

Common mistakes:
- Sync `SqliteSaver` async endpoint mein use karna → blocking!
- Har request pe naya graph compile karna → expensive!
- Thread safety: graph instance shared karo lekin config unique rakho

```python
# Correct pattern:
graph_instance = None  # global

@app.on_event("startup")
async def startup():
    global graph_instance
    # Ek baar compile
    graph_instance = compile_my_graph()

@app.post("/chat")
async def chat(req: Request):
    # graph_instance reuse, thread_id unique
    result = await graph_instance.ainvoke(data, {"configurable": {"thread_id": req.user_id}})
```

---

### Q15: State Persistence Production Mein?

**Answer:**
Production considerations:

**1. Backend Selection:**
- Small scale: SqliteSaver
- Medium scale: PostgreSQL (`psycopg2` ya `asyncpg`)
- High scale: Redis (fast, in-memory with persistence)
- Managed: LangGraph Cloud

**2. TTL (Time To Live):**
- Old conversations automatically expire karni chahiye
- SQLite: Cron job se old records delete karo
- Redis: TTL automatically expire karta hai

**3. Security:**
- Thread IDs user-specific aur unpredictable hone chahiye
- Ek user doosre ka thread_id guess na kar sake
- `uuid4()` use karo predictable IDs ke jagah

**4. Scalability:**
- Multiple FastAPI instances ek hi database se connect kar sakti hain
- SQLite file sharing problematic hai multi-instance mein
- PostgreSQL/Redis preferred for distributed systems

**5. Backup:**
- Production checkpoints ka regular backup
- Time-travel debugging ke liye important

---

*End of LangGraph Advanced Theory — 40 LPA Interview Ready!*
