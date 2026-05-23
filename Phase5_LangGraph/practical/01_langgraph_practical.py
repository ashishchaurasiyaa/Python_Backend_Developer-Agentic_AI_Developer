"""
Phase5_LangGraph — Complete Practical
========================================
Topics:
  1. StateGraph + TypedDict state
  2. Node functions + edges
  3. Conditional routing
  4. Checkpointing (memory across runs)
  5. Human-in-the-loop (interrupt_before)
  6. ReAct agent in LangGraph
  7. Multi-agent supervisor pattern
  8. Streaming execution

Install: pip install langgraph langchain-openai
Env: OPENAI_API_KEY

Run: python 01_langgraph_practical.py
"""

import os
from typing import TypedDict, Annotated, Literal
import operator

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("LANGGRAPH CONCEPTS")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: State + Graph Basics
# INTERVIEW: State = shared data structure, nodes = functions, edges = transitions
# ─────────────────────────────────────────────────────────────────────────────

print("\n  LangGraph core concepts:")
CONCEPTS = {
    "StateGraph":       "Graph where nodes share a typed State object",
    "TypedDict State":  "Defines what data flows through the graph",
    "Node":             "Python function that takes state, returns state update",
    "Edge":             "Connection between nodes (normal or conditional)",
    "Conditional edge": "Route to different nodes based on state",
    "Checkpointer":     "Saves state between runs (memory across conversations)",
    "interrupt_before": "Pause graph for human input (HITL)",
    "Command":          "Return value that can route to next node",
}
for k, v in CONCEPTS.items():
    print(f"  {k:<22}: {v}")

BASIC_GRAPH_CODE = '''\
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, Annotated, Sequence
import operator

# ── Define State ──────────────────────────────────────────────
class AgentState(TypedDict):
    messages:  Annotated[list, operator.add]  # Annotated = reducer function
    # operator.add → new messages appended (not replaced)
    user_id:   str
    task_done: bool

# ── Node functions ────────────────────────────────────────────
def call_llm(state: AgentState) -> dict:
    """Call LLM and return state update."""
    from langchain_openai import ChatOpenAI
    llm   = ChatOpenAI(model="gpt-4o-mini")
    response = llm.invoke(state["messages"])
    return {"messages": [response]}   # operator.add appends this

def check_if_done(state: AgentState) -> dict:
    """Check completion condition."""
    last_msg = state["messages"][-1]
    is_done  = "DONE" in last_msg.content.upper()
    return {"task_done": is_done}

# ── Router function ────────────────────────────────────────────
def router(state: AgentState) -> Literal["continue", "end"]:
    """INTERVIEW: Conditional edge = function returns node name."""
    if state.get("task_done"):
        return "end"
    if len(state["messages"]) > 10:  # prevent infinite loop
        return "end"
    return "continue"

# ── Build graph ────────────────────────────────────────────────
graph = StateGraph(AgentState)

graph.add_node("llm_node",       call_llm)
graph.add_node("check_node",     check_if_done)

graph.set_entry_point("llm_node")
graph.add_edge("llm_node", "check_node")

# Conditional edge: check_node → "llm_node" or END
graph.add_conditional_edges(
    "check_node",
    router,
    {"continue": "llm_node", "end": END}
)

app = graph.compile()

# Run
result = app.invoke({
    "messages": [HumanMessage(content="Hello!")],
    "user_id":  "user-123",
    "task_done": False,
})
'''
print("\n  Basic graph code:")
print(BASIC_GRAPH_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Checkpointing (Memory)
# INTERVIEW: Persist state between runs for multi-turn conversations
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Checkpointing")
print("=" * 60)

CHECKPOINT_CODE = '''\
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # production

# ── In-memory checkpointer (dev) ──────────────────────────────
memory = MemorySaver()
app    = graph.compile(checkpointer=memory)

# Run with thread_id = persistent conversation ID
config1 = {"configurable": {"thread_id": "user-alice-session-1"}}

# First message
r1 = app.invoke({"messages": [HumanMessage("My name is Alice")]}, config=config1)

# Second message — graph REMEMBERS previous state!
r2 = app.invoke({"messages": [HumanMessage("What is my name?")]}, config=config1)
# r2 will include Alice's name from previous turn

# ── Get state snapshot ────────────────────────────────────────
snapshot = app.get_state(config1)
print(snapshot.values["messages"])   # All messages in this thread

# ── List all checkpoints ───────────────────────────────────────
for state in app.get_state_history(config1):
    print(state.config["configurable"]["checkpoint_id"])

# ── Production: PostgreSQL checkpointer ───────────────────────
async def use_postgres_checkpointer():
    async with AsyncPostgresSaver.from_conn_string(DB_URL) as checkpointer:
        await checkpointer.setup()
        app = graph.compile(checkpointer=checkpointer)
        # Now state persists in PostgreSQL!
'''
print(CHECKPOINT_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Human-in-the-Loop
# INTERVIEW: Pause graph for approval before sensitive actions
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Human-in-the-Loop (HITL)")
print("=" * 60)

HITL_CODE = '''\
from langgraph.graph import StateGraph, END

# INTERVIEW: interrupt_before = pause BEFORE this node executes
app = graph.compile(
    checkpointer     = memory,
    interrupt_before = ["execute_action"],  # pause here for human approval
)

config = {"configurable": {"thread_id": "approval-flow-1"}}

# Start → graph pauses at "execute_action" node
result = app.invoke({"task": "Delete 5000 user records"}, config=config)
print(result["__interrupt__"])  # Shows what the graph wants to do

# Human reviews and approves (or modifies state)
human_input = input("Approve? (y/n): ")

if human_input == "y":
    # Resume — continue from where it paused
    result = app.invoke(None, config=config)  # None = continue
else:
    # Update state to cancel
    app.update_state(config, {"task": "CANCELLED"})
    result = app.invoke(None, config=config)

# Use case: approve database modifications, financial transactions,
#           AI-written emails before sending, code deployment
'''
print(HITL_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Multi-Agent Supervisor
# INTERVIEW: One supervisor routes to specialized agents
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Multi-Agent Supervisor Pattern")
print("=" * 60)

SUPERVISOR_CODE = '''\
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict, Literal

# ── Supervisor decides which agent to call ─────────────────────
class SupervisorState(TypedDict):
    messages: list
    next:     str   # which agent to route to

AGENTS = ["researcher", "writer", "coder", "reviewer"]

def supervisor_node(state: SupervisorState) -> dict:
    """LLM-based supervisor — reads conversation, decides next agent."""
    llm    = ChatOpenAI(model="gpt-4o-mini")
    system = (
        f"You are a supervisor managing agents: {AGENTS}. "
        "Based on the task, choose the next agent. "
        "When done, say FINISH."
    )
    result = llm.invoke([
        {"role": "system",    "content": system},
        {"role": "user",      "content": str(state["messages"])},
    ])
    next_agent = extract_next_agent(result.content, AGENTS)
    return {"next": next_agent}

# ── Specialized agents ─────────────────────────────────────────
def researcher_agent(state):
    # Search web, read docs, gather facts
    return {"messages": state["messages"] + ["Research complete: ...facts..."]}

def writer_agent(state):
    # Write content based on research
    return {"messages": state["messages"] + ["Draft: ..."]}

def coder_agent(state):
    # Write and test code
    return {"messages": state["messages"] + ["Code: def foo(): ..."]}

# ── Build supervisor graph ─────────────────────────────────────
graph = StateGraph(SupervisorState)
graph.add_node("supervisor",  supervisor_node)
graph.add_node("researcher",  researcher_agent)
graph.add_node("writer",      writer_agent)
graph.add_node("coder",       coder_agent)

graph.set_entry_point("supervisor")

# Supervisor routes to any agent
graph.add_conditional_edges("supervisor", lambda s: s["next"], {
    "researcher": "researcher",
    "writer":     "writer",
    "coder":      "coder",
    "FINISH":     END,
})

# All agents return to supervisor
for agent in ["researcher", "writer", "coder"]:
    graph.add_edge(agent, "supervisor")
'''
print(SUPERVISOR_CODE[:700])

print("\n" + "=" * 60)
print("LANGGRAPH INTERVIEW SUMMARY:")
print("  StateGraph = graph with shared typed state")
print("  Nodes = Python functions that update state")
print("  Conditional edges = route based on state values")
print("  Checkpointer = memory across runs (thread_id = session)")
print("  interrupt_before = pause for human approval (HITL)")
print("  Supervisor = LLM routes to specialized agent nodes")
print("  vs LangChain: LangGraph = stateful loops, LangChain = simple chains")
print("=" * 60)
