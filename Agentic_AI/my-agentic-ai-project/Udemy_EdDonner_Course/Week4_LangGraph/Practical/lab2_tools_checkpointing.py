"""
LAB 2 — Tools + Conditional Edges + Checkpointing/Memory (Lectures L75-L79)
============================================================================

Is lab me kya seekhenge:
  1. @tool decorator       -> Python function ko LLM-callable tool banana
                              (wiki_search via Wikipedia API + safe AST calculator)
  2. ToolNode + tools_condition -> Week-1 ka MANUAL agent while-loop ab GRAPH
                              EDGES ke roop me: conditional edge = if statement,
                              graph ka cycle (tools -> chatbot) = loop
  3. MemorySaver (L78)      -> in-memory checkpointer + thread_id se multi-turn
                              MEMORY: har super-step ke baad state snapshot
  4. SqliteSaver (L79)      -> wahi cheez par DISK pe — process restart ke baad
                              bhi conversation yaad rehti hai

Kaise chalana:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab2_tools_checkpointing.py

Requirements: .env me GROQ_API_KEY (free tier chalega, retry laga rakha hai).
"""

import ast
import operator
import os
import re
import sqlite3
import time
from typing import Annotated

import httpx
from dotenv import load_dotenv
from typing_extensions import TypedDict

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv(override=True)

# Paths — output folder me sqlite db persist hoga
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(THIS_DIR, "output")
SQLITE_DB_PATH = os.path.join(OUTPUT_DIR, "memory.db")


# =============================================================================
# PART 1 — TOOLS (L75-L76)
# =============================================================================
# @tool decorator function ke NAME + DOCSTRING + TYPE HINTS se ek JSON schema
# bana deta hai. LLM ko yahi schema dikhta hai — isliye docstring hi tool ka
# "prompt" hai. LLM tool ko khud RUN nahi karta, sirf "tool_call" (name + args
# ka JSON) emit karta hai; execution hamare graph ka ToolNode karega.

@tool
def wiki_search(query: str) -> str:
    """Search Wikipedia for a topic and return the top 2 results (title + snippet).
    Use this for factual/encyclopedic questions about people, places, concepts."""
    # httpx se Wikipedia ka official search API — no scraping, no API key needed.
    # Wikipedia ko ek User-Agent header chahiye hota hai warna 403 de sakta hai.
    try:
        resp = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 2,          # top-2 results kaafi hain LLM context ke liye
            },
            headers={"User-Agent": "langgraph-lab2/0.1 (learning project)"},
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        if not hits:
            return f"Wikipedia par '{query}' ke liye kuch nahi mila."
        lines = []
        for h in hits:
            # snippet me <span class="searchmatch"> jaise HTML tags hote hain — strip karo
            snippet = re.sub(r"<[^>]+>", "", h["snippet"])
            lines.append(f"- {h['title']}: {snippet}")
        return "\n".join(lines)
    except Exception as e:
        # Tool kabhi raise nahi karna chahiye — error string bhi LLM ke liye
        # ek valid observation hai (woh retry/apologize kar sakta hai).
        return f"ERROR: Wikipedia search fail ho gaya ({e})"


# ---- Week-1 jaisa SAFE calculator: eval() NAHI, sirf AST whitelist ----
# eval() arbitrary code chala deta hai (security disaster). Hum expression ko
# ast.parse karke sirf numbers + whitelisted operators recursively evaluate
# karte hain — function calls, names, attributes sab reject.
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval_node(node):
    """AST node ko recursively evaluate karo — sirf numbers + allowed operators."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Sirf numbers allowed hain, mila: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](
            _safe_eval_node(node.left), _safe_eval_node(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"Yeh expression allowed nahi hai: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression like '23 * 7 + 100'.
    Supports + - * / // % ** and parentheses. Use this for any math."""
    cleaned = re.sub(r"[^0-9+\-*/().%\s]", "", expression)
    try:
        tree = ast.parse(cleaned, mode="eval")
        return str(_safe_eval_node(tree))
    except Exception as e:
        return f"ERROR: '{expression}' evaluate nahi ho paaya ({e})"


TOOLS = [wiki_search, calculator]

# bind_tools = LLM ko tool schemas ATTACH karna. Ab LLM ka response ya to
# normal text hoga, ya AIMessage jisme .tool_calls populated honge.
llm = ChatGroq(model="llama-3.3-70b-versatile")
llm_with_tools = llm.bind_tools(TOOLS)


# =============================================================================
# PART 2 — GRAPH with TOOL LOOP (L76-L77)
# =============================================================================
# Week-1 me humne yeh MANUALLY likha tha:
#
#     while True:
#         response = llm.invoke(messages)
#         if not response.tool_calls:        # <- yahi tools_condition hai
#             break                          # <- yahi END edge hai
#         for tc in response.tool_calls:     # <- yahi ToolNode hai
#             messages.append(run_tool(tc))
#
# LangGraph me wahi loop ab GRAPH STRUCTURE ban gaya:
#   - conditional edge (tools_condition) = while-loop ka "if tool_calls" wala
#     IF STATEMENT — runtime pe decide hota hai next node kaun hoga
#   - tools -> chatbot wali edge = loop ka WAPAS JAANA (cycle in graph)
#   - ToolNode = prebuilt node jo AIMessage.tool_calls padhta hai, har tool
#     ko PARALLEL run karta hai, aur ToolMessage(s) state me append karta hai
# Fayda: loop ab DATA (graph) hai, code nahi — isliye checkpointing, streaming,
# human-in-the-loop sab framework-level pe free milta hai.


class State(TypedDict):
    # add_messages REDUCER hai: naye messages APPEND hote hain, state replace
    # nahi hoti. Bina reducer ke har node purani history ko overwrite kar deta.
    messages: Annotated[list, add_messages]


def chatbot_node(state: State):
    """LLM ko poori message history do; woh text ya tool_calls return karega."""
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


def build_graph(checkpointer=None):
    """Graph builder ko function me rakha hai taaki hum SAME topology ko alag
    checkpointers (None / MemorySaver / SqliteSaver) ke saath RE-COMPILE kar
    saken — Part 4 me 'fresh objects, same db' demo ke liye yahi chahiye."""
    builder = StateGraph(State)
    builder.add_node("chatbot", chatbot_node)
    builder.add_node("tools", ToolNode(TOOLS))   # prebuilt: tool_calls execute karta hai

    builder.add_edge(START, "chatbot")
    # CONDITIONAL EDGE: chatbot ke output me tool_calls hain -> "tools" node,
    # warna -> END. tools_condition prebuilt function hai jo exactly yahi
    # last-AIMessage.tool_calls check karta hai.
    builder.add_conditional_edges("chatbot", tools_condition)
    # CYCLE: tools chal gaye to results leke WAPAS chatbot — yahi "agent loop".
    builder.add_edge("tools", "chatbot")

    return builder.compile(checkpointer=checkpointer)


# =============================================================================
# Helper — free Groq tier kabhi-kabhi transient 429/503 deta hai -> retry
# =============================================================================
def invoke_with_retry(graph, payload, config=None, attempts=3):
    for i in range(1, attempts + 1):
        try:
            return graph.invoke(payload, config=config)
        except Exception as e:
            if i == attempts:
                raise
            print(f"   [retry {i}/{attempts - 1}] Groq transient error: {e} — 5s wait...")
            time.sleep(5)


def last_ai_text(result) -> str:
    """Result state ke last message (final AI answer) ka text nikaalo."""
    return result["messages"][-1].content


# =============================================================================
# DEMO 1 — Tool loop in action
# =============================================================================
def demo_tool_loop():
    print("=" * 70)
    print("DEMO 1: TOOLS + CONDITIONAL EDGES (Week-1 ka while-loop, ab graph me)")
    print("=" * 70)
    graph = build_graph()  # no checkpointer — stateless single-shot run

    question = (
        "First use wikipedia to find what LangChain is (one line), "
        "then use the calculator to compute 23 * 7 + 100. Give both answers."
    )
    print(f"\nUser: {question}\n")
    result = invoke_with_retry(graph, {"messages": [{"role": "user", "content": question}]})

    # Message trace print karo — isme dikhega: AIMessage(tool_calls) ->
    # ToolMessage(s) -> final AIMessage. Yahi loop ke iterations hain.
    print("--- Message trace (graph ne internally kya kya kiya) ---")
    for msg in result["messages"]:
        kind = type(msg).__name__
        if getattr(msg, "tool_calls", None):
            calls = ", ".join(f"{tc['name']}({tc['args']})" for tc in msg.tool_calls)
            print(f"  {kind}: TOOL CALLS -> {calls}")
        else:
            preview = str(msg.content).replace("\n", " ")[:120]
            print(f"  {kind}: {preview}")

    print(f"\nFinal answer:\n{last_ai_text(result)}")


# =============================================================================
# DEMO 2 — MemorySaver checkpointing + thread_id (L78)
# =============================================================================
# CHECKPOINTING ka concept: LangGraph execution ko SUPER-STEPS me chalata hai
# (ek super-step = ek round of node executions). Checkpointer HAR super-step
# ke baad poori state ka SNAPSHOT save karta hai, thread_id ke against.
# Agla invoke same thread_id ke saath aaye to state WAHIN se resume hoti hai —
# isliye purane messages "yaad" rehte hain. Alag thread_id = alag conversation,
# bilkul alag state — zero leakage.
def demo_memory_saver():
    print("\n" + "=" * 70)
    print("DEMO 2: MemorySaver + thread_id (in-memory multi-turn memory)")
    print("=" * 70)
    graph = build_graph(checkpointer=MemorySaver())

    thread1 = {"configurable": {"thread_id": "1"}}
    thread2 = {"configurable": {"thread_id": "2"}}

    # Turn 1 (thread 1): naam batao — checkpoint me save ho jayega
    r1 = invoke_with_retry(
        graph, {"messages": [{"role": "user", "content": "Mera naam Ashish hai."}]}, thread1
    )
    print(f"\n[thread 1] 'Mera naam Ashish hai.' -> {last_ai_text(r1)[:150]}")

    # Turn 2 (SAME thread 1): hum sirf NAYA message bhej rahe hain — purani
    # history checkpointer khud load karke add_messages se merge karega.
    r2 = invoke_with_retry(
        graph, {"messages": [{"role": "user", "content": "Mera naam kya hai?"}]}, thread1
    )
    print(f"[thread 1] 'Mera naam kya hai?'    -> {last_ai_text(r2)[:150]}")
    print("           ^ YAAD RAHA — same thread_id, checkpointer ne history di.")

    # Same sawaal thread 2 me — FRESH state, naam ka koi checkpoint nahi
    r3 = invoke_with_retry(
        graph, {"messages": [{"role": "user", "content": "Mera naam kya hai?"}]}, thread2
    )
    print(f"[thread 2] 'Mera naam kya hai?'    -> {last_ai_text(r3)[:150]}")
    print("           ^ YAAD NAHI — naya thread_id = bilkul nayi conversation.")


# =============================================================================
# DEMO 3 — SqliteSaver: disk persistence across "restarts" (L79)
# =============================================================================
# MemorySaver process ke saath mar jaata hai. SqliteSaver wahi checkpoints
# ek .db FILE me likhta hai — isliye graph object (ya pura process) dobara
# banao, same db + same thread_id do, aur conversation continue ho jaati hai.
# Hum yahan sqlite3.connect + SqliteSaver(conn) use kar rahe hain (note:
# SqliteSaver.from_conn_string() ek CONTEXT MANAGER hai, 'with' maangta hai).
def demo_sqlite_saver():
    print("\n" + "=" * 70)
    print("DEMO 3: SqliteSaver (disk persistence — restart-proof memory)")
    print("=" * 70)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    config = {"configurable": {"thread_id": "sqlite-demo"}}

    # ---- Phase A: pehla "process" — fact store karo ----
    conn_a = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    graph_a = build_graph(checkpointer=SqliteSaver(conn_a))
    fact = "Remember this: my favourite framework is LangGraph and I live in India."
    ra = invoke_with_retry(graph_a, {"messages": [{"role": "user", "content": fact}]}, config)
    print(f"\n[Phase A] Fact stored -> {last_ai_text(ra)[:140]}")
    conn_a.close()  # connection band — jaise process exit ho gaya ho
    del graph_a     # graph object bhi gaya — koi in-memory state nahi bachi

    # ---- Phase B: DOBARA compile — FRESH connection, FRESH graph, SAME db ----
    conn_b = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    graph_b = build_graph(checkpointer=SqliteSaver(conn_b))
    rb = invoke_with_retry(
        graph_b,
        {"messages": [{"role": "user", "content": "What is my favourite framework and where do I live?"}]},
        config,  # same thread_id -> sqlite se checkpoint load hoga
    )
    print(f"[Phase B] Fresh graph, same db -> {last_ai_text(rb)[:160]}")
    print("          ^ Fact YAAD RAHA bina kisi in-memory object ke — pure disk se.")
    conn_b.close()

    if os.path.exists(SQLITE_DB_PATH):
        size_kb = os.path.getsize(SQLITE_DB_PATH) / 1024
        print(f"\nDB file ban gayi: {SQLITE_DB_PATH} ({size_kb:.1f} KB)")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY .env me nahi mila — pehle woh set karo.")

    demo_tool_loop()
    demo_memory_saver()
    demo_sqlite_saver()

    print("\n" + "=" * 70)
    print("LAB 2 DONE: tools + conditional edges (agent loop as graph),")
    print("MemorySaver thread isolation, SqliteSaver disk persistence. ✔")
    print("=" * 70)
