"""
LAB 1 — LangGraph Fundamentals (Lectures L68-L74)
==================================================

KYA SEEKHENGE is lab me:
    1. LangGraph kya hai aur SDK/CrewAI se kaise alag hai
    2. State, Node, Edge, Reducer — core building blocks
    3. DEMO A: LLM-FREE 3-node graph (pure mechanics, deterministic)
    4. DEMO B: add_messages reducer ka magic (updates MERGE hote hain)
    5. DEMO C: Pehla CHATBOT graph (Groq llama-3.3) + graph diagram

KAISE CHALANA:
    cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
    uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab1_langgraph_basics.py

BIG PICTURE — LangGraph vs baaki frameworks:
    - OpenAI Agents SDK : "agent loop" — LLM ko tools do, woh khud loop me
                          decide karta hai. Control flow IMPLICIT hai.
    - CrewAI            : "crew" — agents + tasks declare karo, framework
                          unhe sequential/hierarchical chala deta hai.
    - LangGraph         : tum khud ek GRAPH define karte ho — nodes (kaam)
                          aur edges (flow). Control flow EXPLICIT hai, isliye
                          complex/cyclic/branching workflows yahan best bante
                          hain. Graph = state machine on steroids.

CORE VOCAB (ratta nahi, samajh lo):
    State   : ek shared TypedDict jo poore graph me flow karta hai.
              Har node ko current state milta hai.
    Node    : plain Python function — (state) -> partial state-update dict.
              NOTE: node PURA naya state return nahi karta, sirf woh keys
              return karta hai jo usne change ki (delta/update).
    Edge    : "is node ke baad kaun chalega" — flow ki wiring.
              START/END special markers hain entry/exit ke liye.
    Reducer : naya update PURANE state ke saath KAISE merge ho, yeh batata
              hai. Annotated[list, add_messages] ka matlab: messages field
              par add_messages reducer lagao — naye messages APPEND honge,
              poori list REPLACE nahi hogi.

SUPER-STEP MODEL (LangGraph ka secret sauce):
    Har graph-step me LangGraph nodes chala kar unke updates ko reducers
    se merge karta hai — state ko koi node directly MUTATE nahi karta.
    Yeh "immutable state + reducer merge" model hi checkpointing, time-travel
    aur parallel branches ko possible banata hai (aage ke labs me dekhenge).
"""

import os
import time
from typing import Annotated

from dotenv import load_dotenv
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

load_dotenv(override=True)


# =====================================================================
# DEMO A — LLM-FREE GRAPH: greet -> shout -> punctuate
# =====================================================================
# Pehle bina LLM ke graph banayenge taaki PURE MECHANICS dikhe —
# deterministic hai, har baar same output. LangGraph ko LLM ki zaroorat
# nahi hai; woh sirf ek orchestration engine hai.


class TextState(TypedDict):
    # NOTE: yahan koi reducer NAHI hai — default behaviour = naya update
    # purani value ko REPLACE kar deta hai. (Reducer DEMO B me dekhenge.)
    text: str


def greet_node(state: TextState) -> dict:
    """Node 1: incoming text ke aage greeting lagao."""
    print(f"  [greet_node]     incoming state = {state}")
    # Node sirf DELTA return karta hai — jo key change hui ({'text': ...}).
    # LangGraph isse current state me merge karega (yahan: replace).
    return {"text": f"hello, {state['text']}"}


def shout_node(state: TextState) -> dict:
    """Node 2: text ko UPPERCASE karo."""
    print(f"  [shout_node]     incoming state = {state}")
    return {"text": state["text"].upper()}


def punctuate_node(state: TextState) -> dict:
    """Node 3: end me '!!!' lagao."""
    print(f"  [punctuate_node] incoming state = {state}")
    return {"text": state["text"] + "!!!"}


def run_demo_a() -> None:
    print("=" * 70)
    print("DEMO A — LLM-free 3-node graph (greet -> shout -> punctuate)")
    print("=" * 70)

    # 5-step recipe (yehi pattern HAR LangGraph program me repeat hota hai):
    #   1. State class    2. StateGraph builder    3. add_node
    #   4. add_edge       5. compile
    builder = StateGraph(TextState)
    builder.add_node("greet", greet_node)
    builder.add_node("shout", shout_node)
    builder.add_node("punctuate", punctuate_node)

    # Edges = flow wiring: START -> greet -> shout -> punctuate -> END
    builder.add_edge(START, "greet")
    builder.add_edge("greet", "shout")
    builder.add_edge("shout", "punctuate")
    builder.add_edge("punctuate", END)

    graph = builder.compile()  # compile() ke baad hi invoke kar sakte ho

    result = graph.invoke({"text": "langgraph"})
    print(f"\n  FINAL STATE: {result}")
    print("  (dekho: har node ne state TRANSFORM kiya, ek pipeline ki tarah)\n")


# =====================================================================
# DEMO B — REDUCER KA MAGIC: add_messages
# =====================================================================
# DEMO A me 'text' REPLACE ho raha tha (no reducer = default replace).
# Ab Annotated[list, add_messages] use karenge — ab updates APPEND honge.
# Yehi chat history ka backbone hai: har node naye messages ADD karta hai,
# purane messages kabhi lost nahi hote.


class ChatState(TypedDict):
    # Annotated[type, reducer] — dusra argument REDUCER function hai.
    # add_messages(old_list, new_update) -> merged_list (append semantics,
    # plus message IDs handle karta hai — same ID ho to update/replace).
    messages: Annotated[list, add_messages]


def node_one(state: ChatState) -> dict:
    print(f"  [node_one] incoming messages count = {len(state['messages'])}")
    # Hum sirf EK naya message return kar rahe hain — purani list nahi!
    # add_messages reducer ise existing list me APPEND kar dega.
    return {"messages": [{"role": "assistant", "content": "node_one ka message"}]}


def node_two(state: ChatState) -> dict:
    print(f"  [node_two] incoming messages count = {len(state['messages'])}")
    return {"messages": [{"role": "assistant", "content": "node_two ka message"}]}


def run_demo_b() -> None:
    print("=" * 70)
    print("DEMO B — Reducer magic: add_messages se updates MERGE hote hain")
    print("=" * 70)

    builder = StateGraph(ChatState)
    builder.add_node("node_one", node_one)
    builder.add_node("node_two", node_two)
    builder.add_edge(START, "node_one")
    builder.add_edge("node_one", "node_two")
    builder.add_edge("node_two", END)
    graph = builder.compile()

    # 1 user message se start karte hain...
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "user ka pehla message"}]}
    )

    print(f"\n  Final messages count = {len(result['messages'])}  (1 -> 3, GROW hui!)")
    for msg in result["messages"]:
        # add_messages dicts ko proper Message objects me convert kar deta hai
        print(f"    - [{msg.type}] {msg.content}")
    print(
        "\n  KEY INSIGHT: har node ne sirf 1 naya message return kiya, lekin\n"
        "  reducer ne APPEND kiya — replace hota to sirf aakhri message bachta.\n"
        "  Bina reducer ke chat history maintain karna manually karna padta!\n"
    )


# =====================================================================
# DEMO C — PEHLA CHATBOT GRAPH (real LLM: Groq llama-3.3-70b)
# =====================================================================
# Canonical LangGraph chatbot pattern: single node jo LLM call karta hai.
# START -> chatbot -> END. Conversation memory abhi MANUAL hai (hum khud
# history pass kar rahe hain) — checkpointers se automatic memory lab3 me.
# NOTE: course me yahan Gradio chat UI bhi banate hain — hum UI lab4 me
# denge, abhi console par focus (concepts > chrome).


def invoke_with_retry(graph, payload, attempts: int = 3):
    """Free Groq tier kabhi-kabhi transient errors deta hai (rate limit /
    503) — isliye simple retry loop with sleep. Production me tenacity
    jaisi library use hoti, demo ke liye yeh kaafi hai."""
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            return graph.invoke(payload)
        except Exception as e:  # noqa: BLE001 — demo me broad catch theek hai
            last_err = e
            print(f"  (attempt {attempt}/{attempts} fail hua: {e}; retry...)")
            time.sleep(2 * attempt)
    raise last_err


def run_demo_c() -> None:
    print("=" * 70)
    print("DEMO C — Pehla CHATBOT graph (Groq llama-3.3-70b-versatile)")
    print("=" * 70)

    if not os.getenv("GROQ_API_KEY"):
        print("  GROQ_API_KEY nahi mila .env me — DEMO C skip kar rahe hain.")
        return

    # Import yahan rakha hai taaki DEMO A/B bina API key ke bhi chalein
    from langchain_groq import ChatGroq

    llm = ChatGroq(model="llama-3.3-70b-versatile")  # key env se uthti hai

    def chatbot_node(state: ChatState) -> dict:
        # PURI history LLM ko bhejte hain, woh ek AIMessage return karta
        # hai — list me wrap karke return karo, add_messages append karega.
        return {"messages": [llm.invoke(state["messages"])]}

    builder = StateGraph(ChatState)
    builder.add_node("chatbot", chatbot_node)
    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", END)
    graph = builder.compile()

    # ---- Graph ka diagram print karo ----
    # draw_ascii() ke liye 'grandalf' package chahiye hota hai — agar woh
    # installed nahi hai to mermaid text print karenge (try/except).
    print("\n  Graph structure:")
    try:
        print(graph.get_graph().draw_ascii())
    except Exception:
        print("  (draw_ascii ke liye grandalf nahi hai — mermaid text de rahe:)")
        print(graph.get_graph().draw_mermaid())

    # ---- 3 hardcoded turns, MANUAL history ----
    # Graph khud kuch yaad NAHI rakhta (compile bina checkpointer ke) —
    # har invoke fresh hai. Isliye hum 'history' list khud carry kar rahe
    # hain aur har turn par poori history pass karte hain. Lab3 me yehi
    # kaam checkpointer + thread_id automatic karega.
    turns = [
        "Hi! My name is Ashish and I am a backend developer.",
        "What is LangGraph in one sentence?",
        "What is my name and profession? Answer in one short line.",
    ]

    history: list = []
    for user_text in turns:
        print(f"\n  USER: {user_text}")
        history.append({"role": "user", "content": user_text})
        result = invoke_with_retry(graph, {"messages": history})
        # result['messages'] = poori merged history (reducer ka kamaal);
        # aakhri message LLM ka jawab hai. Usi merged list ko agli turn
        # ke liye history bana lete hain — yehi 'manual memory' hai.
        history = result["messages"]
        print(f"  BOT : {history[-1].content}")

    print(
        "\n  Dekho turn 3 — bot ko naam/profession yaad tha kyunki HUM\n"
        "  poori history har invoke me pass kar rahe the. Yeh manual\n"
        "  approach lab3 me checkpointers se replace hogi.\n"
    )


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    print("\nLAB 1 — LangGraph Fundamentals (State, Reducers, Nodes, Edges)\n")
    run_demo_a()
    run_demo_b()
    try:
        run_demo_c()
    except Exception as e:  # Groq down ho to bhi A/B ka learning safe rahe
        print(f"  DEMO C fail hua (probably Groq transient issue): {e}")
        # SOFT warning — hard exit NAHI. DEMO C ko working GROQ_API_KEY +
        # network chahiye, lekin DEMO A & B pehle hi pass ho chuke hain aur
        # core concepts (state, reducer, nodes, edges) demonstrate kar chuke.
        # Isliye script normally finish hone do (exit 0) — sirf chetawani.
        print(
            "  WARNING: DEMO C skip/fail — iske liye working GROQ_API_KEY aur\n"
            "  network chahiye. Koi baat nahi: DEMO A & B already pass ho gaye\n"
            "  the aur concepts dikha chuke hain, isliye lab safe-finish ho raha."
        )
    print("LAB 1 done. Next: lab2 — tools, conditional edges, ToolNode.")
