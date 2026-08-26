# LangGraph — State Machines, Multi-Agent, Supervisor Pattern

## Quick Concepts
- **StateGraph** = nodes + edges ka graph — each node is a function that modifies state
- **State** = `TypedDict` — graph ke through flow hota hai, har node update karta hai
- **Conditional edges** = state ke basis par next node decide karo
- **Checkpointing** = state persist karo — human-in-the-loop, resume after interrupt
- **Supervisor** = orchestrator node jo decide karta hai kaun sa worker agent next chalega

---

## Andar kya hota hai — Pregel model, superstep by superstep

LangGraph koi naya invention nahi hai — ye Google ke **Pregel** (2010, large-scale graph
processing paper) ke **BSP (Bulk Synchronous Parallel)** model ko agent state machines pe reuse
karta hai. Ye foundational execution model hai — `03_langgraph_advanced.md` ke subgraphs,
checkpointers, aur parallel `Send` API sab isi model ke upar bane hain.

### Ek "superstep" ka exact loop

```
1. ACTIVE NODES pata karo   — jin nodes ko is round mein naya message/state-update mila
2. SAB active nodes RUN karo — conceptually parallel (ek hi superstep ke andar)
3. Har node ek PARTIAL state update return karta hai (poora state nahi, sirf apna hissa)
4. Updates CHANNELS mein MERGE hote hain via reducer function
5. Reducer ke writes se decide hota hai NEXT superstep ke active nodes kaun honge
   (conditional edges yahin evaluate hote hain)
6. Agar koi node active nahi bacha → graph HALT, wapas control caller ko
```

Ye "1 node chala, phir agla" wala mental model nahi hai — ek superstep mein **multiple nodes
ek saath** active ho sakte hain (parallel branches), aur agla superstep tabhi shuru hota hai jab
current superstep ke SAARE active nodes complete ho jaayein — isiliye "Bulk **Synchronous**".

### Reducers zaroori kyun hain (state.update() nahi karte, isliye)

```python
class State(TypedDict):
    messages: Annotated[list, operator.add]   # reducer = list append
    score: int                                # reducer = default (last write wins)
```

Agar ek superstep mein 2 parallel nodes dono `messages` mein likhna chahein, to "last write
wins" data khoyega. `operator.add` reducer batata hai LangGraph ko: dono writes ko **merge**
karo (append), overwrite mat karo. Yehi wajah hai ki LangGraph state mutation allow nahi karta —
har node sirf apna partial update *return* karta hai, engine reducer se merge karta hai.

### Checkpointer — kyun har superstep ke baad, sirf end pe nahi

```
Superstep 1 complete → FULL state snapshot save (checkpoint 1)
Superstep 2 complete → FULL state snapshot save (checkpoint 2)
Superstep 3 complete → FULL state snapshot save (checkpoint 3)
```

`interrupt_before`/`interrupt_after` koi special bolted-on feature nahi hai — checkpoint har
superstep boundary pe already ban raha tha, "interrupt" bas graph ko is natural save-point pe
rok deta hai aur baad mein wahi checkpoint se resume kar deta hai. Human-in-the-loop is wajah se
"free" feature hai, extra mechanism nahi.

### Trace — support-ticket router (2 nodes)

```
Input: {"ticket": "Refund not processed", "messages": []}

Superstep 1:
  active = [classify_node]
  classify_node runs → returns {"category": "billing"}
  reducer merges → state.category = "billing"
  conditional_edge(state) reads category → routes to billing_agent

Superstep 2:
  active = [billing_agent]
  billing_agent runs → returns {"messages": [AIMessage("Refund initiated")]}
  reducer merges (operator.add) → state.messages = [...,  AIMessage(...)]
  conditional_edge(state) → routes to END

Halt: no active nodes → return final state
```

**Interview me bolne wali line:** "LangGraph ek Pregel-style BSP engine hai — nodes superstep
mein parallel chalte hain, partial updates reducers se channels mein merge hote hain, aur har
superstep boundary automatically ek checkpoint hai. Isi checkpoint mechanism se HITL/resume
milta hai, alag se implement nahi karna padta."

---

## Interview Questions & Answers

### Q1: LangGraph basic StateGraph kaise banate hain?
**Answer:**
```python
# pip install langgraph langchain-anthropic

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic

# --- State define karo ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # auto-appends
    user_input: str
    analysis: str
    final_answer: str

# --- Nodes (functions) ---
model = ChatAnthropic(model="claude-sonnet-4-6")

def analyze_node(state: AgentState) -> AgentState:
    """Step 1: Analyze the question"""
    response = model.invoke([
        HumanMessage(content=f"Analyze this briefly: {state['user_input']}")
    ])
    return {"analysis": response.content}

def answer_node(state: AgentState) -> AgentState:
    """Step 2: Generate answer using analysis"""
    response = model.invoke([
        HumanMessage(
            content=f"Based on analysis: {state['analysis']}\n"
                    f"Original question: {state['user_input']}\n"
                    "Give a complete answer."
        )
    ])
    return {
        "final_answer": response.content,
        "messages": [AIMessage(content=response.content)]
    }

def should_continue(state: AgentState) -> str:
    """Conditional edge — decide next node"""
    if len(state["analysis"]) < 50:
        return "answer"   # skip and go to answer
    return "answer"       # always answer here, but can branch

# --- Build graph ---
graph_builder = StateGraph(AgentState)

# Nodes add karo
graph_builder.add_node("analyze", analyze_node)
graph_builder.add_node("answer", answer_node)

# Edges add karo
graph_builder.add_edge(START, "analyze")
graph_builder.add_conditional_edges(
    "analyze",
    should_continue,
    {
        "answer": "answer",
        "end": END,
    }
)
graph_builder.add_edge("answer", END)

# Compile
graph = graph_builder.compile()

# Run
result = graph.invoke({
    "user_input": "Explain Python decorators",
    "messages": [],
    "analysis": "",
    "final_answer": "",
})

print(result["final_answer"])

# Visualize graph (optional)
# from IPython.display import Image
# Image(graph.get_graph().draw_mermaid_png())
```

---

### Q2: ReAct agent with tools kaise banate hain LangGraph se?
**Answer:**
```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
import json

# --- Tools define karo ---
@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    # Real implementation mein: requests to search API
    return f"Search results for '{query}': Python is a high-level programming language..."

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"

@tool
def get_python_docs(topic: str) -> str:
    """Get Python documentation for a topic."""
    docs = {
        "generators": "Generators use yield keyword...",
        "decorators": "Decorators use @syntax...",
    }
    return docs.get(topic.lower(), f"No docs found for {topic}")

tools = [search_web, calculate, get_python_docs]

# --- LLM with tools bound ---
model = ChatAnthropic(model="claude-sonnet-4-6")
model_with_tools = model.bind_tools(tools)

# --- State ---
class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# --- Nodes ---
def agent_node(state: State) -> State:
    """Agent decides: answer directly or call a tool"""
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# ToolNode automatically executes tools from tool_calls
tool_node = ToolNode(tools)

# --- Conditional routing ---
def route_after_agent(state: State) -> Literal["tools", "__end__"]:
    """If last message has tool_calls → go to tools, else end"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"

# --- Build ReAct graph ---
builder = StateGraph(State)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)

builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {"tools": "tools", "__end__": END}
)
builder.add_edge("tools", "agent")  # After tools → back to agent (React loop)

react_agent = builder.compile()

# Run
from langchain_core.messages import HumanMessage

result = react_agent.invoke({
    "messages": [HumanMessage(content="What is 15 * 23? Also search for Python generators.")]
})

for msg in result["messages"]:
    print(f"{type(msg).__name__}: {msg.content[:100] if msg.content else 'tool_call'}")
```

---

### Q3: Checkpointing aur Human-in-the-Loop kaise karte hain?
**Answer:**
```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver  # production
from langgraph.graph import StateGraph, END, START, interrupt
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pending_action: str
    approved: bool

# --- Checkpointer ---
memory = MemorySaver()  # in-memory, dev ke liye

# Production: PostgreSQL-backed
# with PostgresSaver.from_conn_string("postgresql://user:pass@localhost/db") as checkpointer:
#     graph = builder.compile(checkpointer=checkpointer)

def agent_node(state: State) -> State:
    # Plan an action
    return {"pending_action": "DELETE all users from database"}

def human_approval_node(state: State) -> State:
    """Human ko approve/reject karna hai"""
    action = state["pending_action"]
    print(f"\n⚠️  Pending action: {action}")
    print("Type 'approve' or 'reject': ")

    # interrupt() — execution rok do, human input ka wait karo
    human_response = interrupt({"action": action, "question": "Do you approve?"})

    return {"approved": human_response.get("approved", False)}

def execute_node(state: State) -> State:
    if state["approved"]:
        return {"messages": [HumanMessage(content=f"Executed: {state['pending_action']}")]}
    else:
        return {"messages": [HumanMessage(content="Action rejected by human.")]}

def check_approval(state: State) -> str:
    return "execute" if state.get("approved") else "rejected"

builder = StateGraph(State)
builder.add_node("agent", agent_node)
builder.add_node("human_approval", human_approval_node)
builder.add_node("execute", execute_node)

builder.add_edge(START, "agent")
builder.add_edge("agent", "human_approval")
builder.add_conditional_edges("human_approval", check_approval,
                               {"execute": "execute", "rejected": END})
builder.add_edge("execute", END)

# Compile with checkpointer
graph = builder.compile(checkpointer=memory)

# Thread config — same thread_id se resume karo
config = {"configurable": {"thread_id": "session-1"}}

# Run until interrupt
result = graph.invoke(
    {"messages": [], "pending_action": "", "approved": False},
    config=config
)
print("Paused at human approval")

# Resume with human input
result = graph.invoke(
    Command(resume={"approved": True}),  # Human approved!
    config=config
)

# State snapshot dekhna
snapshot = graph.get_state(config)
print(f"Current node: {snapshot.next}")

# History dekhna
for state in graph.get_state_history(config):
    print(f"Step: {state.metadata.get('step')}, Node: {state.next}")
```

---

### Q4: Multi-Agent Supervisor Pattern kaise banate hain?
**Answer:**
```python
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
import operator

# --- Shared State ---
class SupervisorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next_agent: str
    task: str

# --- Worker Agents ---
model = ChatAnthropic(model="claude-sonnet-4-6")

def research_agent(state: SupervisorState) -> SupervisorState:
    """Research agent — web search + information gathering"""
    response = model.invoke([
        SystemMessage(content="You are a research specialist. Gather facts and data."),
        HumanMessage(content=f"Research this topic: {state['task']}")
    ])
    return {"messages": [response]}

def code_agent(state: SupervisorState) -> SupervisorState:
    """Code agent — Python code generation"""
    response = model.invoke([
        SystemMessage(content="You are a Python coding expert. Write clean, production-ready code."),
        HumanMessage(content=f"Write code for: {state['task']}")
    ])
    return {"messages": [response]}

def writer_agent(state: SupervisorState) -> SupervisorState:
    """Writer agent — documentation and reports"""
    context = "\n".join([m.content for m in state["messages"][-3:] if hasattr(m, "content")])
    response = model.invoke([
        SystemMessage(content="You are a technical writer. Write clear documentation."),
        HumanMessage(content=f"Write documentation based on:\n{context}")
    ])
    return {"messages": [response]}

# --- Supervisor ---
WORKERS = ["researcher", "coder", "writer", "FINISH"]

def supervisor_node(state: SupervisorState) -> SupervisorState:
    """Supervisor decides which worker to call next"""

    supervisor_prompt = f"""You are a project supervisor coordinating these workers:
- researcher: Gathers information and facts
- coder: Writes Python code
- writer: Creates documentation and reports

Task: {state['task']}

Conversation so far:
{chr(10).join([f"{type(m).__name__}: {m.content[:200]}" for m in state["messages"][-5:]])}

Which worker should handle the next step? (researcher/coder/writer/FINISH)
Respond with ONLY the worker name, nothing else.
"""

    response = model.invoke([HumanMessage(content=supervisor_prompt)])
    next_worker = response.content.strip().lower()

    if next_worker not in ["researcher", "coder", "writer"]:
        next_worker = "FINISH"

    return {"next_agent": next_worker}

def route_supervisor(state: SupervisorState) -> str:
    return state["next_agent"]

# --- Build Supervisor Graph ---
builder = StateGraph(SupervisorState)

# Add nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("researcher", research_agent)
builder.add_node("coder", code_agent)
builder.add_node("writer", writer_agent)

# Supervisor decides routing
builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
        "researcher": "researcher",
        "coder": "coder",
        "writer": "writer",
        "FINISH": END,
    }
)

# After each worker → back to supervisor
builder.add_edge("researcher", "supervisor")
builder.add_edge("coder", "supervisor")
builder.add_edge("writer", "supervisor")

from langgraph.checkpoint.memory import MemorySaver
supervisor_graph = builder.compile(checkpointer=MemorySaver())

# Run
result = supervisor_graph.invoke(
    {
        "messages": [],
        "next_agent": "",
        "task": "Create a FastAPI CRUD app with PostgreSQL and document it",
    },
    config={"configurable": {"thread_id": "project-1"}}
)

print(f"Final messages: {len(result['messages'])}")
for msg in result["messages"]:
    print(f"\n--- {type(msg).__name__} ---")
    print(msg.content[:300])
```

---

### Q5: Parallel execution aur subgraphs kaise use karte hain?
**Answer:**
```python
from langgraph.graph import StateGraph, END, START, Send
from typing import TypedDict, Annotated
import operator

# --- Fan-out / Fan-in (parallel execution) ---
class ParallelState(TypedDict):
    topic: str
    analyses: Annotated[list[str], operator.add]  # list mein append karo
    final_report: str

def generate_tasks(state: ParallelState) -> list:
    """Fan-out: multiple parallel tasks generate karo"""
    topic = state["topic"]
    return [
        Send("analyze_technical", {"topic": topic, "aspect": "technical"}),
        Send("analyze_business", {"topic": topic, "aspect": "business"}),
        Send("analyze_security", {"topic": topic, "aspect": "security"}),
    ]

class AspectState(TypedDict):
    topic: str
    aspect: str
    analyses: Annotated[list[str], operator.add]

def analyze_node(state: AspectState) -> AspectState:
    response = model.invoke([
        HumanMessage(content=f"Analyze {state['aspect']} aspects of: {state['topic']}")
    ])
    return {"analyses": [f"[{state['aspect'].upper()}] {response.content}"]}

def compile_report(state: ParallelState) -> ParallelState:
    """Fan-in: results combine karo"""
    combined = "\n\n".join(state["analyses"])
    response = model.invoke([
        HumanMessage(content=f"Write a comprehensive report from:\n{combined}")
    ])
    return {"final_report": response.content}

# Graph with parallel branches
builder = StateGraph(ParallelState)
builder.add_node("analyze_technical", analyze_node)
builder.add_node("analyze_business", analyze_node)
builder.add_node("analyze_security", analyze_node)
builder.add_node("compile", compile_report)

builder.add_conditional_edges(START, generate_tasks, ["analyze_technical", "analyze_business", "analyze_security"])
builder.add_edge("analyze_technical", "compile")
builder.add_edge("analyze_business", "compile")
builder.add_edge("analyze_security", "compile")
builder.add_edge("compile", END)

parallel_graph = builder.compile()

result = parallel_graph.invoke({"topic": "FastAPI in Production", "analyses": [], "final_report": ""})
print(result["final_report"])
```

---

### Q6: LangGraph vs alternatives — kab kya choose karo?
**Answer:**
```
LangGraph:
  ✓ Complex stateful workflows
  ✓ Cycles (agent loops, retry logic)
  ✓ Human-in-the-loop
  ✓ Checkpointing + resume
  ✓ Multi-agent coordination
  ✓ Production-grade (LangChain Company support)

CrewAI (simpler):
  ✓ Team of AI agents quickly setup karo
  ✓ YAML-based config
  ✗ Less flexible than LangGraph
  Use: Simple multi-agent tasks without complex control flow

AutoGen (Microsoft):
  ✓ Conversational agents
  ✓ Code execution agents
  ✗ Less production-ready

When to use LangGraph:
  1. Agent needs to loop (ReAct pattern)
  2. Human approval required mid-workflow
  3. Multiple specialized agents need coordination
  4. State needs to persist across sessions
  5. Complex conditional routing based on runtime state
```
