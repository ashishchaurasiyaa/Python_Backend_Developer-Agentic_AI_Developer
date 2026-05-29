"""
LangGraph Advanced — Practical Demos
=====================================
Series: Phase 5 — LangGraph Advanced (File 2)
Target: 40 LPA Python Backend + Agentic AI interviews

Run:
    python 02_langgraph_advanced.py [demo_name|all]

Available demos:
    supervisor    — Multi-agent supervisor pattern
    subgraph      — Parent graph with subgraph node
    checkpointer  — SqliteSaver, thread_id, state history
    hitl          — Human-in-the-loop with interrupt()
    streaming     — stream_mode values/updates/messages
    parallel      — Send API map-reduce fan-out
    react_agent   — create_react_agent with ToolNode
    all           — Run all demos sequentially

Requirements:
    pip install langgraph langchain-core

Optional (for real LLM):
    pip install langchain-openai
    export OPENAI_API_KEY=sk-...
"""

import sys
import os
import operator
import asyncio
from typing import TypedDict, Annotated, Literal, List, Optional

# ─── LLM Flag — Real ya Mock ─────────────────────────────────────────────────
USE_REAL_LLM = os.getenv("OPENAI_API_KEY") is not None

if USE_REAL_LLM:
    print("✅ OPENAI_API_KEY found — real LLM will be used where available")
else:
    print("⚠️  No OPENAI_API_KEY — using mock LLM responses (all demos still runnable)")

# ─── Core Imports ─────────────────────────────────────────────────────────────
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send, interrupt, Command

print("=" * 70)
print("LangGraph Advanced — Phase 5 Practical")
print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 1: SUPERVISOR MULTI-AGENT
# Ek supervisor multiple specialized workers ko route karta hai
# ══════════════════════════════════════════════════════════════════════════════

def demo_supervisor():
    print("\n" + "═" * 70)
    print("DEMO 1: Supervisor Multi-Agent Pattern")
    print("Supervisor → Route → Researcher / Coder / Writer")
    print("═" * 70)

    # ── State Definition ──────────────────────────────────────────────────
    class AgentState(TypedDict):
        messages: Annotated[list, operator.add]
        task: str
        next_agent: str
        results: Annotated[list, operator.add]
        iteration: int

    # ── Supervisor Node ───────────────────────────────────────────────────
    def supervisor_node(state: AgentState) -> dict:
        """
        Master controller — task analyze karo, worker decide karo.
        Real app mein: LLM se routing decision lo.
        """
        task = state.get("task", "").lower()
        iteration = state.get("iteration", 0)

        print(f"  [Supervisor] Analyzing task: '{task}' (iteration {iteration})")

        # Simple keyword-based routing (real app: LLM-based)
        if any(kw in task for kw in ["research", "find", "search", "discover"]):
            next_agent = "researcher"
        elif any(kw in task for kw in ["code", "program", "function", "implement", "debug"]):
            next_agent = "coder"
        elif any(kw in task for kw in ["write", "content", "blog", "explain", "document"]):
            next_agent = "writer"
        else:
            next_agent = "writer"  # default

        print(f"  [Supervisor] Decision: → {next_agent}")
        return {
            "next_agent": next_agent,
            "iteration": iteration + 1,
            "messages": [f"Supervisor routed to: {next_agent}"]
        }

    # ── Worker Nodes ──────────────────────────────────────────────────────
    def researcher_node(state: AgentState) -> dict:
        """
        Specialized researcher — web search simulate karta hai.
        Real app mein: TavilySearchResults, Wikipedia, ArXiv tools.
        """
        task = state["task"]
        print(f"  [Researcher] Working on: '{task}'")

        # Mock research (real: tool calls)
        result = (
            f"📚 Research Results for '{task}':\n"
            f"   • Source 1: Academic paper found — high relevance\n"
            f"   • Source 2: Industry report — 2024 data\n"
            f"   • Source 3: Expert blog post — practical insights\n"
            f"   Key Finding: Comprehensive data collected successfully"
        )

        return {
            "results": [result],
            "messages": [f"Researcher completed task: {task}"]
        }

    def coder_node(state: AgentState) -> dict:
        """
        Specialized coder — code generate karta hai.
        Real app mein: GPT-4 with code-specific system prompt.
        """
        task = state["task"]
        print(f"  [Coder] Coding solution for: '{task}'")

        # Mock code generation
        result = (
            f"💻 Code Solution for '{task}':\n"
            f"```python\n"
            f"def solution(input_data):\n"
            f"    \"\"\"\n"
            f"    Solution for: {task}\n"
            f"    \"\"\"\n"
            f"    # Step 1: Validate input\n"
            f"    if not input_data:\n"
            f"        raise ValueError('Input cannot be empty')\n"
            f"    \n"
            f"    # Step 2: Process\n"
            f"    result = process(input_data)\n"
            f"    \n"
            f"    # Step 3: Return\n"
            f"    return result\n"
            f"```\n"
            f"   Tests: 5 unit tests written, all passing ✅"
        )

        return {
            "results": [result],
            "messages": [f"Coder completed task: {task}"]
        }

    def writer_node(state: AgentState) -> dict:
        """
        Specialized writer — content generate karta hai.
        Real app mein: LLM with writer persona system prompt.
        """
        task = state["task"]
        print(f"  [Writer] Writing content for: '{task}'")

        # Mock content generation
        result = (
            f"✍️  Content for '{task}':\n"
            f"   # {task.title()}\n"
            f"   \n"
            f"   ## Introduction\n"
            f"   This document covers {task} in detail...\n"
            f"   \n"
            f"   ## Key Points\n"
            f"   • Point 1: Foundation concepts explained\n"
            f"   • Point 2: Practical applications covered\n"
            f"   • Point 3: Best practices outlined\n"
            f"   \n"
            f"   ## Conclusion\n"
            f"   Content generated successfully for the requested task."
        )

        return {
            "results": [result],
            "messages": [f"Writer completed task: {task}"]
        }

    # ── Routing Function ──────────────────────────────────────────────────
    def route_by_supervisor(state: AgentState) -> Literal["researcher", "coder", "writer"]:
        """Supervisor ke decision pe route karo"""
        return state["next_agent"]

    # ── Build Graph ───────────────────────────────────────────────────────
    builder = StateGraph(AgentState)

    # Nodes add karo
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("coder", coder_node)
    builder.add_node("writer", writer_node)

    # Edges
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_by_supervisor,
        {
            "researcher": "researcher",
            "coder": "coder",
            "writer": "writer"
        }
    )
    # Workers ke baad END (simple version — real app mein wapas supervisor)
    builder.add_edge("researcher", END)
    builder.add_edge("coder", END)
    builder.add_edge("writer", END)

    supervisor_graph = builder.compile()

    # ── Run 3 Different Tasks ─────────────────────────────────────────────
    tasks = [
        "Research the latest trends in LangGraph and multi-agent systems",
        "Write a Python function to implement binary search",
        "Write a blog post explaining what is machine learning"
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n--- Task {i}: {task[:50]}...")
        result = supervisor_graph.invoke({
            "messages": [],
            "task": task,
            "next_agent": "",
            "results": [],
            "iteration": 0
        })
        print(f"  ✓ Agent used: {result['next_agent']}")
        print(f"  ✓ Result preview: {result['results'][0][:80]}...")

    print("\n✅ Demo 1 Complete — Supervisor correctly routed 3 different tasks")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 2: SUBGRAPH
# Parent graph ek subgraph ko node ki tarah call karta hai
# ══════════════════════════════════════════════════════════════════════════════

def demo_subgraph():
    print("\n" + "═" * 70)
    print("DEMO 2: Subgraph Pattern")
    print("Parent Graph → [Research Subgraph as Node] → Final Answer")
    print("═" * 70)

    # ── Subgraph State ────────────────────────────────────────────────────
    class ResearchSubgraphState(TypedDict):
        """Subgraph ka apna state — parent se independent"""
        query: str
        search_results: Annotated[list, operator.add]
        filtered_results: list
        summary: str

    # ── Subgraph Nodes ────────────────────────────────────────────────────
    def subgraph_search(state: ResearchSubgraphState) -> dict:
        """Subgraph Step 1: Web search"""
        query = state["query"]
        print(f"    [Subgraph → Search] Query: '{query}'")
        results = [
            f"Result 1: Comprehensive article about {query}",
            f"Result 2: Academic paper on {query}",
            f"Result 3: Industry report covering {query}",
            f"Result 4: Tutorial and examples for {query}",
            f"Result 5: Expert opinion on {query}"
        ]
        return {"search_results": results}

    def subgraph_filter(state: ResearchSubgraphState) -> dict:
        """Subgraph Step 2: Filter relevant results"""
        results = state["search_results"]
        print(f"    [Subgraph → Filter] {len(results)} results → filtering top 3")
        # Real: relevance scoring, deduplication
        filtered = results[:3]  # top 3 rakhho
        return {"filtered_results": filtered}

    def subgraph_summarize(state: ResearchSubgraphState) -> dict:
        """Subgraph Step 3: Summarize filtered results"""
        filtered = state["filtered_results"]
        query = state["query"]
        print(f"    [Subgraph → Summarize] Summarizing {len(filtered)} results")
        summary = (
            f"[Summary for '{query}']\n"
            f"   Top {len(filtered)} sources analyzed:\n"
        )
        for i, r in enumerate(filtered, 1):
            summary += f"   {i}. {r[:50]}...\n"
        summary += f"   Key Insight: Strong consensus on {query} found across sources."
        return {"summary": summary}

    # ── Build Subgraph ────────────────────────────────────────────────────
    subgraph_builder = StateGraph(ResearchSubgraphState)
    subgraph_builder.add_node("search", subgraph_search)
    subgraph_builder.add_node("filter", subgraph_filter)
    subgraph_builder.add_node("summarize", subgraph_summarize)

    subgraph_builder.add_edge(START, "search")
    subgraph_builder.add_edge("search", "filter")
    subgraph_builder.add_edge("filter", "summarize")
    subgraph_builder.add_edge("summarize", END)

    # Subgraph compile karo
    compiled_research_subgraph = subgraph_builder.compile()
    print("  ✓ Subgraph compiled: search → filter → summarize")

    # ── Parent Graph State ────────────────────────────────────────────────
    class ParentState(TypedDict):
        """Parent graph ka state"""
        user_request: str
        query: str              # subgraph ke liye input
        research_summary: str   # subgraph se output
        final_answer: str

    # ── Parent Nodes ──────────────────────────────────────────────────────
    def prepare_query(state: ParentState) -> dict:
        """Parent Step 1: User request se search query banao"""
        request = state["user_request"]
        print(f"  [Parent → PrepareQuery] Request: '{request}'")
        # Real: NLP se query extraction
        query = request.replace("Tell me about", "").replace("Explain", "").strip()
        return {"query": f"comprehensive guide: {query}"}

    def call_research_subgraph(state: ParentState) -> dict:
        """
        Parent Step 2: Subgraph ko node ki tarah call karo
        State mapping: parent fields → subgraph input → subgraph output → parent
        """
        print(f"  [Parent → ResearchNode] Calling subgraph with query: '{state['query']}'")

        # Parent state → Subgraph input (mapping)
        subgraph_input = {
            "query": state["query"],
            "search_results": [],
            "filtered_results": [],
            "summary": ""
        }

        # Subgraph invoke karo
        subgraph_output = compiled_research_subgraph.invoke(subgraph_input)

        # Subgraph output → Parent state (mapping)
        return {"research_summary": subgraph_output["summary"]}

    def generate_final_answer(state: ParentState) -> dict:
        """Parent Step 3: Research summary se final answer banao"""
        request = state["user_request"]
        summary = state["research_summary"]
        print(f"  [Parent → GenerateAnswer] Building answer from research")

        final = (
            f"Answer to: '{request}'\n\n"
            f"Based on research conducted:\n"
            f"{summary}\n\n"
            f"This answer is based on {3} curated sources from our research pipeline."
        )
        return {"final_answer": final}

    # ── Build Parent Graph ────────────────────────────────────────────────
    parent_builder = StateGraph(ParentState)
    parent_builder.add_node("prepare_query", prepare_query)
    parent_builder.add_node("research", call_research_subgraph)  # subgraph as node!
    parent_builder.add_node("generate_answer", generate_final_answer)

    parent_builder.add_edge(START, "prepare_query")
    parent_builder.add_edge("prepare_query", "research")
    parent_builder.add_edge("research", "generate_answer")
    parent_builder.add_edge("generate_answer", END)

    parent_graph = parent_builder.compile()

    # ── Run Demo ──────────────────────────────────────────────────────────
    print("\n  Running parent graph with embedded subgraph...")
    result = parent_graph.invoke({
        "user_request": "Tell me about Python asyncio and event loops",
        "query": "",
        "research_summary": "",
        "final_answer": ""
    })

    print(f"\n  Final Answer Preview:\n  {result['final_answer'][:200]}...")
    print("\n✅ Demo 2 Complete — Subgraph ran as node inside parent graph")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 3: CHECKPOINTER
# SqliteSaver se state persist karo, thread_id se isolate karo
# ══════════════════════════════════════════════════════════════════════════════

def demo_checkpointer():
    print("\n" + "═" * 70)
    print("DEMO 3: Checkpointer — SqliteSaver")
    print("Thread isolation, state persistence, state history")
    print("═" * 70)

    # ── State with counter ────────────────────────────────────────────────
    class ChatState(TypedDict):
        messages: Annotated[list, operator.add]
        user_name: str
        message_count: int
        context: str

    # ── Nodes ─────────────────────────────────────────────────────────────
    def chat_node(state: ChatState) -> dict:
        """Simple chat node — message count track karo"""
        messages = state.get("messages", [])
        count = state.get("message_count", 0)
        user = state.get("user_name", "User")

        last_msg = messages[-1] if messages else "Hello"
        response = f"[Bot to {user}] You said: '{last_msg}'. Message #{count + 1} processed."

        return {
            "messages": [response],
            "message_count": count + 1,
            "context": f"Last topic: {last_msg[:30]}"
        }

    # ── Build Graph with Checkpointer ─────────────────────────────────────
    builder = StateGraph(ChatState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)

    # SqliteSaver — in-memory SQLite (":memory:" = testing ke liye)
    # Production mein: SqliteSaver.from_conn_string("./conversations.db")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        memory = SqliteSaver.from_conn_string(":memory:")
        checkpointer_name = "SqliteSaver"
    except ImportError:
        # Fallback to MemorySaver if sqlite package not available
        memory = MemorySaver()
        checkpointer_name = "MemorySaver (fallback — pip install langgraph-checkpoint-sqlite)"

    print(f"  Using: {checkpointer_name}")
    graph = builder.compile(checkpointer=memory)

    # ── Thread 1: Alice ka conversation ───────────────────────────────────
    print("\n  --- Alice's conversation (thread: user-alice) ---")
    config_alice = {"configurable": {"thread_id": "user-alice"}}

    # Message 1
    r1 = graph.invoke({
        "messages": ["Hello, I want to learn Python"],
        "user_name": "Alice",
        "message_count": 0,
        "context": ""
    }, config_alice)
    print(f"  Turn 1: {r1['messages'][-1]}")

    # Message 2 — same thread, context preserved hai
    r2 = graph.invoke({
        "messages": ["Can you explain decorators?"],
        "user_name": "",  # state mein already hai from previous
        "message_count": 0,
        "context": ""
    }, config_alice)
    print(f"  Turn 2: {r2['messages'][-1]}")

    # Message 3
    r3 = graph.invoke({
        "messages": ["What about generators?"],
        "user_name": "",
        "message_count": 0,
        "context": ""
    }, config_alice)
    print(f"  Turn 3: {r3['messages'][-1]}")

    # ── Thread 2: Bob ka alag conversation ────────────────────────────────
    print("\n  --- Bob's conversation (thread: user-bob) ---")
    config_bob = {"configurable": {"thread_id": "user-bob"}}

    r_bob = graph.invoke({
        "messages": ["Hi, I need help with FastAPI"],
        "user_name": "Bob",
        "message_count": 0,
        "context": ""
    }, config_bob)
    print(f"  Bob Turn 1: {r_bob['messages'][-1]}")
    print(f"  Bob message_count: {r_bob['message_count']} (separate from Alice!)")

    # ── State Inspection ──────────────────────────────────────────────────
    print("\n  --- State Inspection ---")
    alice_state = graph.get_state(config_alice)
    print(f"  Alice's current message_count: {alice_state.values['message_count']}")
    print(f"  Alice's context: {alice_state.values['context']}")
    print(f"  Alice's total messages: {len(alice_state.values['messages'])}")

    # ── State History ─────────────────────────────────────────────────────
    print("\n  --- Alice's State History ---")
    history = list(graph.get_state_history(config_alice))
    print(f"  Total checkpoints saved: {len(history)}")
    for checkpoint in history[:3]:  # pehle 3 dekho
        step = checkpoint.metadata.get("step", "?")
        msg_count = len(checkpoint.values.get("messages", []))
        print(f"  Checkpoint step={step}: {msg_count} messages")

    # ── Manual State Update ───────────────────────────────────────────────
    print("\n  --- Manual State Update ---")
    print(f"  Before update: message_count = {alice_state.values['message_count']}")
    graph.update_state(config_alice, {"message_count": 99, "context": "MANUALLY UPDATED"})
    updated_state = graph.get_state(config_alice)
    print(f"  After update:  message_count = {updated_state.values['message_count']}")
    print(f"  After update:  context = {updated_state.values['context']}")

    print("\n✅ Demo 3 Complete — Checkpointer working, threads isolated")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 4: HUMAN-IN-THE-LOOP (HITL)
# interrupt() se graph pause karo, human approval ke baad resume karo
# ══════════════════════════════════════════════════════════════════════════════

def demo_hitl():
    print("\n" + "═" * 70)
    print("DEMO 4: Human-in-the-Loop (HITL)")
    print("interrupt() → pause → human approval → resume")
    print("═" * 70)

    # ── State ─────────────────────────────────────────────────────────────
    class ApprovalState(TypedDict):
        messages: Annotated[list, operator.add]
        planned_action: str
        approved: bool
        result: str
        risk_level: str

    # ── Nodes ─────────────────────────────────────────────────────────────
    def action_planner(state: ApprovalState) -> dict:
        """AI ek action plan karta hai"""
        task = state["messages"][-1] if state["messages"] else "unknown task"
        print(f"  [Planner] Planning action for: '{task}'")

        # Mock: action determine karo
        if "delete" in str(task).lower():
            action = "DELETE all records older than 30 days from production database"
            risk = "HIGH"
        elif "email" in str(task).lower():
            action = "Send promotional email to 50,000 users"
            risk = "MEDIUM"
        else:
            action = "Update configuration settings in production"
            risk = "LOW"

        print(f"  [Planner] Planned: '{action}' (Risk: {risk})")
        return {
            "planned_action": action,
            "risk_level": risk,
            "messages": [f"Action planned: {action}"]
        }

    def human_review_node(state: ApprovalState) -> dict:
        """
        interrupt() — yahan graph PAUSE ho jata hai.
        Human ko action dikhao, unka response lo.
        """
        action = state["planned_action"]
        risk = state["risk_level"]

        print(f"\n  ⚠️  [HITL Node] Interrupt triggered!")
        print(f"     Action: {action}")
        print(f"     Risk: {risk}")
        print(f"     → Graph is now PAUSED waiting for human input")

        # interrupt() — execution yahan ruk jata hai
        # Value human ko pass hoti hai
        human_response = interrupt({
            "message": f"Please review: {action}",
            "risk_level": risk,
            "instructions": "Call graph.invoke(Command(resume={...}), config) to continue"
        })

        # Jab resume hoga, human_response mein value hogi
        approved = human_response.get("approved", False) if isinstance(human_response, dict) else False
        reason = human_response.get("reason", "No reason given") if isinstance(human_response, dict) else str(human_response)

        print(f"\n  [HITL Node] Resumed! Human decision: approved={approved}, reason='{reason}'")
        return {
            "approved": approved,
            "messages": [f"Human review: {'APPROVED' if approved else 'REJECTED'} — {reason}"]
        }

    def execute_action(state: ApprovalState) -> dict:
        """Action execute karo — sirf approved hone pe"""
        action = state["planned_action"]

        if state.get("approved"):
            print(f"  [Execute] Executing approved action: '{action}'")
            return {
                "result": f"✅ Successfully executed: {action}",
                "messages": [f"Action executed: {action}"]
            }
        else:
            print(f"  [Execute] Action rejected — not executing")
            return {
                "result": f"❌ Action rejected by human reviewer: {action}",
                "messages": [f"Action rejected: {action}"]
            }

    # ── Build Graph ───────────────────────────────────────────────────────
    builder = StateGraph(ApprovalState)
    builder.add_node("planner", action_planner)
    builder.add_node("human_review", human_review_node)
    builder.add_node("execute", execute_action)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "human_review")
    builder.add_edge("human_review", "execute")
    builder.add_edge("execute", END)

    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)  # checkpointer REQUIRED for interrupt

    config = {"configurable": {"thread_id": "hitl-approval-demo"}}

    # ── Part 1: Run until interrupt ───────────────────────────────────────
    print("\n  Step 1: Running graph until interrupt point...")
    try:
        graph.invoke({
            "messages": ["Please delete old database records"],
            "planned_action": "",
            "approved": False,
            "result": "",
            "risk_level": ""
        }, config)
    except Exception as e:
        # interrupt() GraphInterrupted exception raise karta hai internally
        # invoke() se yeh as a return happen karta hai — no exception to catch usually
        pass

    # Check state after interrupt
    state = graph.get_state(config)
    print(f"\n  Graph state after interrupt:")
    print(f"     Next nodes: {state.next}")
    print(f"     Planned action: {state.values.get('planned_action', 'N/A')}")
    print(f"     Risk level: {state.values.get('risk_level', 'N/A')}")

    # ── Part 2: Simulate human APPROVING ─────────────────────────────────
    print("\n  Step 2: Human APPROVES the action...")
    from langgraph.types import Command

    final_result = graph.invoke(
        Command(resume={"approved": True, "reason": "Verified — safe to proceed"}),
        config
    )
    print(f"\n  Final result: {final_result.get('result', 'N/A')}")

    # ── Part 3: New thread — human REJECTS ───────────────────────────────
    print("\n  --- New thread: Human REJECTS ---")
    config2 = {"configurable": {"thread_id": "hitl-rejection-demo"}}

    graph.invoke({
        "messages": ["Send email to all users"],
        "planned_action": "",
        "approved": False,
        "result": "",
        "risk_level": ""
    }, config2)

    # Human rejects
    rejected_result = graph.invoke(
        Command(resume={"approved": False, "reason": "Too risky — needs more review"}),
        config2
    )
    print(f"  Rejection result: {rejected_result.get('result', 'N/A')}")

    print("\n✅ Demo 4 Complete — HITL working: interrupt → pause → resume")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 5: STREAMING
# stream_mode ke different options ko demonstrate karo
# ══════════════════════════════════════════════════════════════════════════════

def demo_streaming():
    print("\n" + "═" * 70)
    print("DEMO 5: Streaming Modes")
    print("stream_mode: updates | values | messages")
    print("═" * 70)

    # ── State ─────────────────────────────────────────────────────────────
    class StreamState(TypedDict):
        messages: Annotated[list, operator.add]
        step: int
        data: str

    # ── Multi-step nodes (streaming clearly dikhne ke liye) ───────────────
    def step1_node(state: StreamState) -> dict:
        return {"messages": ["Step 1: Initialized"], "step": 1, "data": "raw_data"}

    def step2_node(state: StreamState) -> dict:
        return {"messages": ["Step 2: Processed"], "step": 2, "data": "processed_data"}

    def step3_node(state: StreamState) -> dict:
        return {"messages": ["Step 3: Formatted"], "step": 3, "data": "final_result"}

    # ── Build Graph ───────────────────────────────────────────────────────
    builder = StateGraph(StreamState)
    builder.add_node("step1", step1_node)
    builder.add_node("step2", step2_node)
    builder.add_node("step3", step3_node)

    builder.add_edge(START, "step1")
    builder.add_edge("step1", "step2")
    builder.add_edge("step2", "step3")
    builder.add_edge("step3", END)

    graph = builder.compile()
    input_data = {"messages": [], "step": 0, "data": ""}

    # ── Mode 1: updates (DEFAULT) — sirf changes ──────────────────────────
    print("\n  === stream_mode='updates' (default) ===")
    print("  Sirf changed fields per node — lightweight")
    for chunk in graph.stream(input_data, stream_mode="updates"):
        node_name = list(chunk.keys())[0]
        updates = chunk[node_name]
        print(f"  [{node_name}] changed: {list(updates.keys())}")

    # ── Mode 2: values — full state ───────────────────────────────────────
    print("\n  === stream_mode='values' ===")
    print("  Full state after each node — heavier")
    for i, state in enumerate(graph.stream(input_data, stream_mode="values")):
        print(f"  State {i}: step={state.get('step')}, "
              f"data='{state.get('data')}', "
              f"msgs={len(state.get('messages', []))}")

    # ── Async streaming ───────────────────────────────────────────────────
    print("\n  === Async streaming (astream) ===")

    async def run_async_stream():
        async for chunk in graph.astream(input_data, stream_mode="updates"):
            node_name = list(chunk.keys())[0]
            print(f"  [async/{node_name}] update received")

    asyncio.run(run_async_stream())

    # ── token-by-token simulation (messages mode) ─────────────────────────
    print("\n  === stream_mode='messages' (LLM token simulation) ===")
    print("  Real app mein: LLM tokens ek-ek karke aate hain")
    print("  Simulated token stream: ", end="")

    # Simulate token streaming
    mock_tokens = ["The", " answer", " is", " 42", ".", " This", " is", " computed", "."]
    for token in mock_tokens:
        print(token, end="", flush=True)
        # Real: event["data"]["chunk"].content
    print()  # newline

    # ── FastAPI SSE example (code only — not running server) ──────────────
    print("\n  === FastAPI SSE Pattern (code structure) ===")
    sse_code = '''
  @app.post("/chat/stream")
  async def chat_stream(request: ChatRequest):
      config = {"configurable": {"thread_id": request.thread_id}}

      async def event_generator():
          async for chunk in graph.astream(
              {"messages": [request.message]},
              config,
              stream_mode="updates"
          ):
              yield f"data: {json.dumps(chunk)}\\n\\n"
          yield "data: [DONE]\\n\\n"

      return StreamingResponse(event_generator(), media_type="text/event-stream")
  '''
    print(sse_code)

    print("✅ Demo 5 Complete — All streaming modes demonstrated")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 6: PARALLEL EXECUTION — SEND API (MAP-REDUCE)
# Fan-out to parallel workers, fan-in to merge results
# ══════════════════════════════════════════════════════════════════════════════

def demo_parallel():
    print("\n" + "═" * 70)
    print("DEMO 6: Parallel Execution — Send API (Map-Reduce)")
    print("Fan-out: split topics → parallel research → merge results")
    print("═" * 70)

    # ── State ─────────────────────────────────────────────────────────────
    class ParallelResearchState(TypedDict):
        topics: List[str]
        results: Annotated[List[str], operator.add]  # parallel results merge honge
        final_report: str

    # Worker state (individual topic ke liye)
    class TopicWorkerState(TypedDict):
        topic: str
        results: Annotated[List[str], operator.add]

    # ── Fan-out: topics split karo ────────────────────────────────────────
    def split_into_topics(state: ParallelResearchState):
        """
        Returns list of Send objects — har topic ke liye ek parallel worker.
        Yeh LangGraph ko batata hai: 'in parallel chalao'
        """
        topics = state["topics"]
        print(f"  [Fan-out] Splitting {len(topics)} topics for parallel research")
        sends = []
        for topic in topics:
            sends.append(Send("research_topic", {"topic": topic, "results": []}))
        return sends

    # ── Parallel worker ───────────────────────────────────────────────────
    def research_topic(state: TopicWorkerState) -> dict:
        """
        Yeh node parallel mein chalta hai — ek saath multiple instances.
        Har instance apna topic research karta hai.
        """
        topic = state["topic"]
        print(f"  [Worker] Researching topic: '{topic}' (running in parallel)")

        # Mock research — real app: web search, LLM call
        findings = (
            f"Topic: '{topic}'\n"
            f"  • Definition: {topic} is a key concept in modern computing\n"
            f"  • Key facts: 3 important facts discovered\n"
            f"  • Examples: 2 practical examples found\n"
            f"  • Relevance: HIGH — critical for 40 LPA interviews"
        )

        return {"results": [findings]}  # operator.add se parent results mein merge hoga

    # ── Fan-in: results merge karo ────────────────────────────────────────
    def merge_all_results(state: ParallelResearchState) -> dict:
        """
        Sab parallel workers ke results ab state mein aa gaye hain.
        (operator.add reducer ne automatically combine kiya)
        Yahan final report banao.
        """
        all_results = state["results"]
        topics = state["topics"]
        print(f"  [Fan-in] Merging {len(all_results)} parallel results")

        report = f"# Parallel Research Report\n"
        report += f"Topics researched: {len(topics)}\n"
        report += f"Results collected: {len(all_results)}\n\n"
        report += "=" * 40 + "\n\n"

        for i, result in enumerate(all_results, 1):
            report += f"[Finding {i}]\n{result}\n\n"

        report += f"=" * 40 + "\n"
        report += f"✅ All {len(all_results)} topics researched in parallel"

        return {"final_report": report}

    # ── Build Graph ───────────────────────────────────────────────────────
    builder = StateGraph(ParallelResearchState)
    builder.add_node("research_topic", research_topic)
    builder.add_node("merge_results", merge_all_results)

    # Conditional edge jo Send objects return karta hai = fan-out
    builder.add_conditional_edges(
        START,
        split_into_topics,
        ["research_topic"]  # allowed destination nodes
    )

    # Parallel workers ke baad merge
    builder.add_edge("research_topic", "merge_results")
    builder.add_edge("merge_results", END)

    parallel_graph = builder.compile()

    # ── Run with 4 topics ─────────────────────────────────────────────────
    topics = [
        "Python asyncio",
        "LangGraph StateGraph",
        "FastAPI async patterns",
        "PostgreSQL indexing"
    ]

    print(f"\n  Researching {len(topics)} topics in parallel...")
    result = parallel_graph.invoke({
        "topics": topics,
        "results": [],
        "final_report": ""
    })

    print(f"\n  Final Report Preview:\n")
    print(result["final_report"][:400] + "...")

    # ── Performance comparison (simulation) ───────────────────────────────
    print(f"\n  Performance insight:")
    print(f"  Sequential would take: ~{len(topics) * 2}s (2s per topic)")
    print(f"  Parallel (Send API): ~2s (all topics simultaneously)")
    print(f"  Speedup: {len(topics)}x 🚀")

    print("\n✅ Demo 6 Complete — Send API map-reduce working")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO 7: REACT AGENT WITH TOOLNODE
# prebuilt create_react_agent + custom tools
# ══════════════════════════════════════════════════════════════════════════════

def demo_react_agent():
    print("\n" + "═" * 70)
    print("DEMO 7: ReAct Agent with ToolNode")
    print("create_react_agent + custom tools + ToolNode internals")
    print("═" * 70)

    # ── Tool Definitions ──────────────────────────────────────────────────
    from langchain_core.tools import tool

    @tool
    def calculator(expression: str) -> str:
        """
        Calculate a mathematical expression safely.
        Examples: '15 * 23', '100 / 4 + 5', '2 ** 10'
        """
        try:
            # Safe eval — only math operations
            allowed = {
                "__builtins__": {},
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "pow": pow
            }
            result = eval(expression, allowed)
            return f"Result: {result}"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error: Invalid expression — {e}"

    @tool
    def word_counter(text: str) -> str:
        """
        Count words, characters, and sentences in text.
        """
        words = len(text.split())
        chars = len(text)
        sentences = text.count(".") + text.count("!") + text.count("?")
        return f"Words: {words}, Characters: {chars}, Sentences: {sentences}"

    @tool
    def get_weather(city: str) -> str:
        """
        Get current weather for a city. (Mock data for demo)
        Supported cities: Mumbai, Delhi, Bangalore, Chennai, Hyderabad
        """
        weather_data = {
            "Mumbai": "32°C, Humid, Partly cloudy",
            "Delhi": "28°C, Dry, Clear skies",
            "Bangalore": "22°C, Pleasant, Light breeze",
            "Chennai": "35°C, Hot, Sunny",
            "Hyderabad": "30°C, Warm, Few clouds"
        }
        city_title = city.title()
        return weather_data.get(city_title, f"Weather data unavailable for {city}")

    @tool
    def string_reverser(text: str) -> str:
        """Reverse a string"""
        return f"Reversed: {text[::-1]}"

    tools_list = [calculator, word_counter, get_weather, string_reverser]
    print(f"  Tools defined: {[t.name for t in tools_list]}")

    # ── Test tools directly ───────────────────────────────────────────────
    print("\n  Direct tool test:")
    print(f"  calculator('15 * 23'): {calculator.invoke('15 * 23')}")
    print(f"  word_counter('hello world foo bar'): {word_counter.invoke('hello world foo bar')}")
    print(f"  get_weather('Mumbai'): {get_weather.invoke('Mumbai')}")

    # ── ToolNode internals demo ───────────────────────────────────────────
    print("\n  === ToolNode Internals Demo ===")
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import AIMessage, ToolMessage

    # ToolNode create karo
    tool_node = ToolNode(tools_list)
    print("  ToolNode created with all tools")

    # Simulate what ToolNode processes:
    # AIMessage with tool_calls → ToolNode → ToolMessage results
    mock_tool_calls = [
        {
            "id": "call_001",
            "name": "calculator",
            "args": {"expression": "100 * 3.14"}
        },
        {
            "id": "call_002",
            "name": "get_weather",
            "args": {"city": "Bangalore"}
        }
    ]

    # Create mock AIMessage with tool calls
    mock_ai_message = AIMessage(
        content="I'll calculate that and check the weather.",
        tool_calls=mock_tool_calls
    )

    # ToolNode invoke — config parameter required in newer LangGraph versions
    from langchain_core.runnables import RunnableConfig
    tool_config = RunnableConfig()
    try:
        tool_result = tool_node.invoke({"messages": [mock_ai_message]}, tool_config)
    except Exception:
        # Fallback: direct tool call to show same output
        tool_result = {"messages": []}
        for tc in mock_tool_calls:
            tools_dict = {t.name: t for t in tools_list}
            t_fn = tools_dict[tc["name"]]
            res = t_fn.invoke(tc["args"])
            from langchain_core.messages import ToolMessage
            tool_result["messages"].append(ToolMessage(content=str(res), tool_call_id=tc["id"]))
    print(f"\n  ToolNode processed {len(tool_result['messages'])} tool calls:")
    for msg in tool_result["messages"]:
        if hasattr(msg, "content"):
            print(f"  Tool result: {msg.content}")

    # ── Full ReAct Graph (manual — shows internals) ───────────────────────
    print("\n  === Manual ReAct Graph (shows internals) ===")
    from langgraph.prebuilt import tools_condition
    from langgraph.graph import MessagesState
    from langchain_core.messages import HumanMessage, SystemMessage

    if USE_REAL_LLM:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_with_tools = llm.bind_tools(tools_list)

        def agent_node(state: MessagesState) -> dict:
            """LLM decide karta hai tool call karna hai ya answer dena hai"""
            messages = state["messages"]
            system = SystemMessage(content="You are a helpful assistant with access to tools.")
            response = llm_with_tools.invoke([system] + messages)
            return {"messages": [response]}

        builder = StateGraph(MessagesState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tool_node)

        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition)
        builder.add_edge("tools", "agent")

        react_graph = builder.compile()

        print("  Running ReAct with real LLM...")
        result = react_graph.invoke({
            "messages": [HumanMessage(content="What is 15 * 23? And how many words in 'hello world foo bar baz'?")]
        })
        print(f"  Final answer: {result['messages'][-1].content}")

    else:
        # Mock demo — shows graph structure without real LLM
        print("  ReAct Agent Graph Structure (no real LLM needed for structure):")
        print()
        print("  ┌─────────────────────────────────────────┐")
        print("  │          ReAct Agent Graph               │")
        print("  └─────────────────────────────────────────┘")
        print("                    │")
        print("                  START")
        print("                    │")
        print("             ┌──────▼──────┐")
        print("             │    agent    │  ← LLM decides: answer or tool?")
        print("             └──────┬──────┘")
        print("                    │")
        print("         tools_condition (conditional edge)")
        print("          /                    \\")
        print("    tool_calls?               No tool_calls")
        print("         │                        │")
        print("  ┌──────▼──────┐               END")
        print("  │  ToolNode   │  ← Execute tools")
        print("  │  (tools)    │")
        print("  └──────┬──────┘")
        print("         │")
        print("    wapas agent ← Results ke saath")
        print()
        print("  create_react_agent() — yeh sab ek line mein:")
        print("  agent = create_react_agent(llm, tools=[calculator, word_counter, get_weather])")
        print()
        print("  Mock conversation simulation:")

        # Simulate ReAct loop without real LLM
        conversations = [
            ("User", "What is 25 * 4?"),
            ("Agent", "I'll use the calculator tool."),
            ("Tool: calculator", calculator.invoke("25 * 4")),
            ("Agent", "The answer is 100."),
        ]
        for role, content in conversations:
            print(f"  [{role}]: {content}")

    # ── create_react_agent shortcut ───────────────────────────────────────
    print("\n  === create_react_agent() — Production Shortcut ===")
    if USE_REAL_LLM:
        from langgraph.prebuilt import create_react_agent
        from langchain_openai import ChatOpenAI

        agent = create_react_agent(
            ChatOpenAI(model="gpt-4o-mini"),
            tools=tools_list,
            state_modifier="You are a helpful assistant. Use tools when needed."
        )
        result = agent.invoke({
            "messages": [HumanMessage(content="Calculate 2^10 and check weather in Mumbai")]
        })
        print(f"  create_react_agent result: {result['messages'][-1].content}")
    else:
        print("  create_react_agent needs real LLM — set OPENAI_API_KEY")
        print("  Example usage:")
        print("  from langgraph.prebuilt import create_react_agent")
        print("  from langchain_openai import ChatOpenAI")
        print("  agent = create_react_agent(ChatOpenAI(), tools=[calculator, get_weather])")
        print("  result = agent.invoke({'messages': ['What is 15*4?']})")

    print("\n✅ Demo 7 Complete — ReAct agent and ToolNode demonstrated")


# ══════════════════════════════════════════════════════════════════════════════
# BONUS DEMO: ERROR HANDLING + RETRY
# ══════════════════════════════════════════════════════════════════════════════

def demo_error_handling():
    print("\n" + "═" * 70)
    print("BONUS: Error Handling in Graphs")
    print("try/except in nodes, fallback nodes, RetryPolicy")
    print("═" * 70)

    # ── State ─────────────────────────────────────────────────────────────
    class RobustState(TypedDict):
        messages: Annotated[list, operator.add]
        task: str
        result: str
        error: str
        attempt: int

    # ── Flaky node (sometimes fails) ──────────────────────────────────────
    _call_count = {"count": 0}

    def flaky_api_node(state: RobustState) -> dict:
        """Simulates an unreliable API call"""
        _call_count["count"] += 1
        attempt = _call_count["count"]

        print(f"  [FlakyAPI] Attempt #{attempt}")

        if attempt <= 2:
            # First 2 attempts fail
            print(f"  [FlakyAPI] FAILED (attempt {attempt})")
            raise ConnectionError(f"API timeout on attempt {attempt}")
        else:
            # Third attempt succeeds
            print(f"  [FlakyAPI] SUCCESS (attempt {attempt})")
            return {"result": "API response: data retrieved successfully", "error": ""}

    def safe_flaky_node(state: RobustState) -> dict:
        """Wrapper with try/except"""
        try:
            return flaky_api_node(state)
        except ConnectionError as e:
            return {"result": "", "error": str(e), "attempt": state.get("attempt", 0) + 1}

    def error_router(state: RobustState) -> Literal["retry", "fallback", "done"]:
        """Error hone pe route karo"""
        if state.get("error"):
            if state.get("attempt", 0) < 3:
                return "retry"
            else:
                return "fallback"
        return "done"

    def fallback_node(state: RobustState) -> dict:
        """When all retries fail"""
        print(f"  [Fallback] Primary failed {state.get('attempt')} times — using fallback")
        return {
            "result": "Fallback result: cached data used",
            "error": "",
            "messages": ["Fallback activated — using cached data"]
        }

    def success_node(state: RobustState) -> dict:
        return {"messages": [f"✅ Final result: {state['result']}"]}

    # ── Build Robust Graph ────────────────────────────────────────────────
    builder = StateGraph(RobustState)
    builder.add_node("flaky_api", safe_flaky_node)
    builder.add_node("fallback", fallback_node)
    builder.add_node("success", success_node)

    builder.add_edge(START, "flaky_api")
    builder.add_conditional_edges("flaky_api", error_router, {
        "retry": "flaky_api",
        "fallback": "fallback",
        "done": "success"
    })
    builder.add_edge("fallback", "success")
    builder.add_edge("success", END)

    graph = builder.compile()

    print("\n  Running graph with flaky API node (will fail 2 times, succeed on 3rd):")
    result = graph.invoke({
        "messages": [],
        "task": "fetch data",
        "result": "",
        "error": "",
        "attempt": 0
    })
    print(f"\n  Final: {result['messages'][-1]}")

    # ── RetryPolicy example (code structure) ─────────────────────────────
    print("\n  RetryPolicy usage (requires langgraph >=0.1.x):")
    retry_code = '''
  from langgraph.pregel import RetryPolicy

  retry_policy = RetryPolicy(
      max_attempts=3,       # Maximum retry count
      initial_interval=1.0, # 1s before first retry
      backoff_factor=2.0,   # Exponential: 1s, 2s, 4s
      jitter=True,          # Add randomness to avoid thundering herd
      retry_on=(ConnectionError, TimeoutError)  # Specific exceptions
  )

  # Node ke saath retry policy attach karo
  builder.add_node("api_call", my_node, retry=retry_policy)
  '''
    print(retry_code)

    print("✅ Bonus Demo Complete — Error handling patterns demonstrated")


# ══════════════════════════════════════════════════════════════════════════════
# QUICK REFERENCE — Interview Key Points
# ══════════════════════════════════════════════════════════════════════════════

def print_interview_quickref():
    print("\n" + "═" * 70)
    print("QUICK REFERENCE — 40 LPA Interview Key Points")
    print("═" * 70)

    points = [
        ("Checkpointer types", "MemorySaver(RAM) | SqliteSaver(disk) | AsyncSqliteSaver(async)"),
        ("thread_id purpose", "Isolates conversation state per user/session"),
        ("Reducer needed when", "Multiple nodes same field update karte hain (e.g., messages list)"),
        ("interrupt() requires", "Checkpointer MUST be attached — state save karna zaroori"),
        ("Send API use case", "Dynamic fan-out — runtime decide, kitne parallel workers"),
        ("stream_mode=updates", "Default — sirf changed fields per node (lightweight)"),
        ("stream_mode=values", "Full state after each node (debug)"),
        ("stream_mode=messages", "LLM token streaming (chat UI)"),
        ("Command object", "State update + routing ek saath in one node"),
        ("Subgraph vs node", "Subgraph = reusable child StateGraph as a node"),
        ("ToolNode internals", "AIMessage.tool_calls → execute each → ToolMessage results"),
        ("GraphRecursionError", "25 steps default limit — config recursion_limit se override"),
        ("interrupt_before vs after", "before=node nahi chala, after=node chala phir ruka"),
        ("HITL resume", "graph.invoke(None, config) ya graph.invoke(Command(resume=val), config)"),
        ("Production checkpointer", "PostgreSQL checkpointer (langgraph-checkpoint-postgres)"),
    ]

    for concept, explanation in points:
        print(f"\n  ► {concept}")
        print(f"    {explanation}")

    print("\n" + "═" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — CLI argument se demo select karo
# ══════════════════════════════════════════════════════════════════════════════

DEMOS = {
    "supervisor": demo_supervisor,
    "subgraph": demo_subgraph,
    "checkpointer": demo_checkpointer,
    "hitl": demo_hitl,
    "streaming": demo_streaming,
    "parallel": demo_parallel,
    "react_agent": demo_react_agent,
    "error": demo_error_handling,
}

if __name__ == "__main__":
    # Argument parse karo
    args = sys.argv[1:]
    selected = args[0].lower() if args else "all"

    if selected == "all":
        print("\nRunning ALL demos...\n")
        for name, func in DEMOS.items():
            try:
                func()
            except Exception as e:
                print(f"\n⚠️  Demo '{name}' error: {e}")
                import traceback
                traceback.print_exc()
        print_interview_quickref()

    elif selected in DEMOS:
        DEMOS[selected]()
        print_interview_quickref()

    elif selected in ("ref", "quickref", "reference"):
        print_interview_quickref()

    else:
        print(f"\n❌ Unknown demo: '{selected}'")
        print(f"\nAvailable demos: {', '.join(DEMOS.keys())}, all, ref")
        print("\nExamples:")
        print("  python 02_langgraph_advanced.py all")
        print("  python 02_langgraph_advanced.py supervisor")
        print("  python 02_langgraph_advanced.py hitl")
        print("  python 02_langgraph_advanced.py parallel")
        sys.exit(1)
