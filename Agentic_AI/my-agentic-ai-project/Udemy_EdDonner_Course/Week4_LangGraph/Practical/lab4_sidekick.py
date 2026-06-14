"""
LAB 4 — Week 4 CAPSTONE: "Sidekick" Personal Co-worker (Lectures L84-L90)
==========================================================================

KYA SEEKHENGE (course ka sabse rich lab — sab kuch ek saath):
  1. MULTI-TOOL AGENT  — worker LLM ke paas 4 tools bound hain:
       - wiki_search(query)            -> Wikipedia API (httpx) se research
       - write_file(filename, content) -> SIRF sandbox/ folder me file likho
       - read_file(filename)           -> sandbox/ se file padho
       - run_python(code)              -> SAFE restricted Python sandbox
     NOTE: Ed Donner ke course me yahan REAL Python REPL tool + Playwright
     browser tool use hota hai (L86-L87). Hum unke SAFE sandbox versions
     use kar rahe hain — same concept (LLM tool maangta hai, HUM execute
     karte hain), bina arbitrary code/browser ke risk ke. Free + offline-ish.

  2. WORKER-EVALUATOR PATTERN (L85) — yeh Sidekick ka dil hai:
       worker (tools ke saath kaam karta hai)
         -> tools loop (ToolNode + conditional edge, jab tak tool_calls hain)
         -> EVALUATOR node (structured output: feedback, success_criteria_met,
            user_input_needed)
         -> agar criteria met YA user input chahiye -> END
         -> warna feedback ke saath worker ko WAPAS bhejo (max 3 rounds)
     Yeh "LLM as judge in the loop" hai — Week 1 ke evaluator pattern ka
     graph version, jisme judge fail karne par kaam REDO hota hai.

  3. STATE BEYOND MESSAGES — Sidekick state me sirf messages nahi:
     success_criteria, feedback_on_work, success_criteria_met,
     user_input_needed, rounds — sab graph ke through flow karte hain.
     messages par add_messages REDUCER hai (append), baaki fields par
     default overwrite (last write wins).

  4. MEMORY (L88) — MemorySaver checkpointer + thread_id => multi-turn.
     Turn 2 me Sidekick ko yaad rehta hai turn 1 me kya hua tha.
     Har user/session ka APNA thread_id => isolated sessions (course me
     Gradio ke har browser session ke liye alag Sidekick instance banta hai).

KAISE CHALANA:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab4_sidekick.py        # console demo
  uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab4_sidekick.py ui     # Gradio chat UI

Lectures covered: L84 (Sidekick intro), L85 (worker-evaluator graph),
L86 (tools: Python REPL/file ops), L87 (browser tool -> hamara wiki_search),
L88 (memory + isolated sessions), L89-L90 (polish + capstone wrap).
"""

import io
import json
import os
import re
import sys
import time
import uuid
from typing import Annotated, Any, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

load_dotenv(override=True)

# ===========================================================================
# SANDBOX SETUP — file tools sirf is folder ke andar kaam karenge
# ===========================================================================
# Course me Sidekick ko poora filesystem + browser milta hai. Hum ek
# DEDICATED sandbox folder bana rahe hain aur PATH TRAVERSAL guard laga
# rahe hain — "../../etc/passwd" jaise filename reject ho jayenge.
SANDBOX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox")
os.makedirs(SANDBOX_DIR, exist_ok=True)


def _resolve_sandbox_path(filename: str) -> str:
    """Filename ko sandbox ke andar resolve karo; bahar nikla to ValueError.

    realpath() symlinks + '..' dono ko resolve karta hai, isliye check
    bulletproof hai: final absolute path SANDBOX_DIR se shuru hona chahiye.
    """
    candidate = os.path.realpath(os.path.join(SANDBOX_DIR, filename))
    sandbox_real = os.path.realpath(SANDBOX_DIR)
    if not (candidate == sandbox_real or candidate.startswith(sandbox_real + os.sep)):
        raise ValueError(f"Path traversal blocked: '{filename}' sandbox ke bahar jaata hai")
    return candidate


# ===========================================================================
# TOOL 1 — wiki_search: httpx se Wikipedia API (course ka 'web browsing' stand-in)
# ===========================================================================
# Course me L87 par Playwright browser tool hai (LLM poora web browse karta
# hai). Hum free + deterministic Wikipedia API use kar rahe hain — concept
# same: "research tool" jo LLM ko fresh knowledge laakar deta hai.
_WIKI_HEADERS = {"User-Agent": "SidekickLab/1.0 (learning project; contact: student)"}


def _wiki_api_get(params: dict) -> dict:
    """Wikipedia API call with 429-backoff — free API hai, rate limit par
    thoda ruk kar retry karte hain (3 attempts, badhta hua sleep)."""
    resp = None
    for attempt in range(3):
        resp = httpx.get("https://en.wikipedia.org/w/api.php", params=params,
                         headers=_WIKI_HEADERS, timeout=20)
        if resp.status_code == 429:          # Too Many Requests -> backoff
            time.sleep(4 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


@tool
def wiki_search(query: str) -> str:
    """Wikipedia par search karo aur top articles ke intro extracts lao.
    Use this to research facts about any topic before writing notes."""
    try:
        # generator=search + prop=extracts => search AUR intro extracts EK HI
        # request me (pehle 3 alag HTTP calls the -> rate limit jaldi hit hota
        # tha). exlimit=max zaroori hai warna sirf pehle page ka extract aata.
        data = _wiki_api_get({
            "action": "query", "generator": "search", "gsrsearch": query,
            "gsrlimit": 2, "prop": "extracts", "exintro": 1,
            "explaintext": 1, "exlimit": "max", "format": "json",
        })
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return f"Wikipedia par '{query}' ke liye kuch nahi mila."
        chunks = []
        # 'index' key search-ranking order deta hai (dict order guaranteed nahi)
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            title = page.get("title", "?")
            extract = (page.get("extract") or "").strip()[:900]
            chunks.append(f"## {title}\n{extract}")
        return "\n\n".join(chunks)
    except Exception as e:
        # Tool kabhi raise nahi karta — error string bhi LLM ke liye signal hai
        return f"ERROR: Wikipedia search fail hua ({e})"


# ===========================================================================
# TOOL 2 & 3 — write_file / read_file: sandboxed file ops (L86 ka safe version)
# ===========================================================================
@tool
def write_file(filename: str, content: str) -> str:
    """Sandbox folder me ek text/markdown file likho (overwrite if exists).
    filename should be relative, e.g. 'notes.md' — no absolute paths."""
    try:
        path = _resolve_sandbox_path(filename)
        # Nested folders (e.g. 'notes/today.md') bhi allow — par sandbox ke andar hi
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"OK: wrote {len(content)} chars to sandbox/{filename}"
    except Exception as e:
        return f"ERROR: write_file fail hua ({e})"


@tool
def read_file(filename: str) -> str:
    """Sandbox folder se file ka content padho."""
    try:
        path = _resolve_sandbox_path(filename)
        if not os.path.exists(path):
            existing = os.listdir(SANDBOX_DIR)
            return f"ERROR: sandbox/{filename} exist nahi karti. Available: {existing}"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()[:4000]
    except Exception as e:
        return f"ERROR: read_file fail hua ({e})"


# ===========================================================================
# TOOL 4 — run_python: RESTRICTED exec sandbox (course ke Python REPL ka safe version)
# ===========================================================================
# Course me LangChain ka PythonREPLTool hai = LLM ka likha ARBITRARY code
# seedha exec hota hai (L86 me Ed khud warn karta hai!). Hum restricted
# version banate hain: limited builtins whitelist + dangerous patterns
# blocked + stdout capture. Teaching sandbox hai, production jail nahi —
# real production me Docker/firecracker jaisa isolation chahiye.
_SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "str": str, "int": int,
    "float": float, "bool": bool, "sum": sum, "min": min, "max": max,
    "abs": abs, "round": round, "sorted": sorted, "reversed": reversed,
    "enumerate": enumerate, "zip": zip, "list": list, "dict": dict,
    "set": set, "tuple": tuple, "map": map, "filter": filter, "any": any,
    "all": all, "divmod": divmod, "isinstance": isinstance,
}
_FORBIDDEN_PATTERNS = ["__", "import", "open(", "exec(", "eval(", "globals", "locals"]


@tool
def run_python(code: str) -> str:
    """Run a short Python snippet (math, string ops, loops) in a safe sandbox.
    Use print() to produce output. No imports, no file/network access."""
    for bad in _FORBIDDEN_PATTERNS:
        if bad in code:
            return f"ERROR: '{bad}' is sandbox me allowed nahi hai"
    stdout = io.StringIO()
    try:
        # exec ke time __builtins__ ko whitelist se REPLACE karte hain —
        # LLM ka code sirf yeh functions dekh sakta hai, os/sys kuch nahi.
        env: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
        old_stdout, sys.stdout = sys.stdout, stdout
        try:
            exec(code, env)  # noqa: S102 — intentionally restricted sandbox
        finally:
            sys.stdout = old_stdout
        output = stdout.getvalue().strip()
        return output if output else "(no output — print() use karo)"
    except Exception as e:
        return f"ERROR: code fail hua ({type(e).__name__}: {e})"


TOOLS = [wiki_search, write_file, read_file, run_python]


# ===========================================================================
# STATE — Sidekick ka shared whiteboard (messages se zyada cheezein!)
# ===========================================================================
# add_messages = REDUCER: naye messages APPEND hote hain (replace nahi).
# Baaki fields par koi reducer nahi => node jo return kare wahi OVERWRITE
# ho jaata hai. Yahi course ke Sidekick state ka design hai (L85).
class SidekickState(TypedDict):
    messages: Annotated[list, add_messages]
    success_criteria: str               # user ne kya "done" define kiya
    feedback_on_work: Optional[str]     # evaluator ka pichhla feedback (worker ke liye)
    success_criteria_met: bool          # evaluator ka verdict
    user_input_needed: bool             # worker stuck hai / question pooch raha hai
    rounds: int                         # kitni baar evaluator ne dekha (max 3 cap)


# Evaluator ka STRUCTURED OUTPUT — Pydantic model => guaranteed parseable
# verdict, free-text judgement nahi. Groq llama-3.3 par tool-calling ke
# through kaam karta hai (with_structured_output internally tool call banata hai).
class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Assistant ke kaam par concrete feedback")
    success_criteria_met: bool = Field(description="Kya success criteria genuinely meet hua?")
    user_input_needed: bool = Field(
        description="True agar assistant user se clarification maang raha hai ya stuck hai"
    )


# ===========================================================================
# LLMs — worker (tools bound) + evaluator (structured output, fallback chain)
# ===========================================================================
worker_llm = ChatGroq(model="llama-3.3-70b-versatile").bind_tools(TOOLS)

# Structured output ke liye fallback chain: Groq llama-3.3 pehle try hota
# hai; flaky ho to gpt-oss-120b; phir Gemini. Verification run me Groq
# llama-3.3 hi reliably kaam kar gaya — fallbacks safety net hain.
def _evaluator_candidates():
    yield "groq:llama-3.3", ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    yield "groq:gpt-oss-120b", ChatGroq(model="openai/gpt-oss-120b", temperature=0)
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        yield "gemini-2.0-flash", ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    except Exception:
        pass


def _evaluate_with_fallback(eval_messages) -> EvaluatorOutput:
    last_err = None
    for name, llm in _evaluator_candidates():
        try:
            result = llm.with_structured_output(EvaluatorOutput).invoke(eval_messages)
            if result is not None:
                return result
        except Exception as e:
            last_err = e
            print(f"   [evaluator fallback] {name} fail hua: {e}")
    # Sab fail? Conservative default: criteria NOT met, user input needed
    return EvaluatorOutput(
        feedback=f"Evaluator LLM unavailable ({last_err}) — manual review needed.",
        success_criteria_met=False,
        user_input_needed=True,
    )


# ===========================================================================
# NODE 1 — WORKER: tools ke saath kaam karta hai, feedback ho to redo karta hai
# ===========================================================================
def worker_node(state: SidekickState) -> dict:
    """Worker = main doer. System prompt me success criteria + (agar hai to)
    evaluator ka feedback inject hota hai. SystemMessage state me STORE nahi
    karte — har invoke par fresh banate hain, taaki feedback hamesha latest ho."""
    system = (
        "You are Sidekick, a helpful personal co-worker agent. "
        "You have tools: wiki_search (research), write_file/read_file "
        "(files live in a sandbox folder — use simple relative filenames like 'notes.md'), "
        "and run_python (small safe snippets, use print()).\n"
        f"The user's SUCCESS CRITERIA for this task: {state['success_criteria']}\n"
        "Work step by step using tools, ONE tool call per turn when steps depend on "
        "each other. IMPORTANT: if a task needs research, call wiki_search FIRST and "
        "WAIT for its result; only then call write_file with content BASED ON that "
        "result — never write facts from memory, and never batch write_file together "
        "with wiki_search in the same turn. Use SHORT search queries (1-2 words, e.g. "
        "'LangChain') — long multi-word queries return irrelevant articles. If a search "
        "result looks off-topic, retry wiki_search with a different shorter query. "
        "When fully done, reply with a clear final answer. "
        "Agar tumhe user se clarification chahiye, to ek clarifying question pooch sakte ho — "
        "start that reply with 'QUESTION:' and ask nothing else."
    )
    if state.get("feedback_on_work"):
        # Worker-evaluator loop ka core: pichhla attempt reject hua tha,
        # to feedback system prompt me daal kar RETRY karwa rahe hain.
        system += (
            "\n\nYour previous attempt was REJECTED by an evaluator. "
            f"Feedback: {state['feedback_on_work']}\n"
            "You MUST take corrective action using tools (e.g. call wiki_search again "
            "with a different shorter query, rewrite the file) — do NOT just repeat "
            "your previous answer."
        )
    response = worker_llm.invoke([SystemMessage(content=system)] + state["messages"])
    return {"messages": [response]}


# CONDITIONAL EDGE 1 — worker ke baad: tool_calls hain to ToolNode, warna evaluator
def worker_router(state: SidekickState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"     # ToolNode tools chala kar ToolMessages append karega
    return "evaluator"     # koi tool call nahi => worker ko lagta hai kaam done hai


# ===========================================================================
# NODE 2 — EVALUATOR: structured verdict deta hai (L85 ka judge-in-the-loop)
# ===========================================================================
def evaluator_node(state: SidekickState) -> dict:
    """Evaluator poori conversation dekh kar decide karta hai: kaam genuinely
    success criteria meet karta hai ya nahi. Verdict STRUCTURED hai (Pydantic),
    isliye routing 100% deterministic — free text parse nahi karna padta."""
    # Conversation ka compact transcript banao (tool results truncate karke)
    lines = []
    for m in state["messages"]:
        if isinstance(m, HumanMessage):
            lines.append(f"USER: {m.content}")
        elif isinstance(m, AIMessage):
            if m.tool_calls:
                # write_file ke args POORA content dikhate hain (truncate kam)
                # taaki evaluator file ka asli content judge kar sake
                calls = ", ".join(f"{tc['name']}({json.dumps(tc['args'])[:600]})" for tc in m.tool_calls)
                lines.append(f"ASSISTANT called tools: {calls}")
            if m.content:
                lines.append(f"ASSISTANT: {m.content}")
        elif isinstance(m, ToolMessage):
            lines.append(f"TOOL RESULT: {str(m.content)[:400]}")
    transcript = "\n".join(lines)

    eval_messages = [
        SystemMessage(content=(
            "You are a strict evaluator. Judge whether the assistant's work "
            "meets the success criteria. Check the TOOL RESULT lines for real "
            "evidence (e.g. 'OK: wrote ... chars' proves a file was written). "
            "Set user_input_needed=true ONLY if the assistant asked the user a "
            "question (starts with 'QUESTION:') or is clearly stuck."
        )),
        HumanMessage(content=(
            f"SUCCESS CRITERIA: {state['success_criteria']}\n\n"
            f"CONVERSATION:\n{transcript}\n\n"
            "Give your structured verdict."
        )),
    ]
    verdict = _evaluate_with_fallback(eval_messages)
    print(f"\n   [EVALUATOR round {state.get('rounds', 0) + 1}] met={verdict.success_criteria_met} "
          f"user_input_needed={verdict.user_input_needed}\n   feedback: {verdict.feedback[:200]}")
    return {
        "feedback_on_work": verdict.feedback,
        "success_criteria_met": verdict.success_criteria_met,
        "user_input_needed": verdict.user_input_needed,
        "rounds": state.get("rounds", 0) + 1,   # overwrite (no reducer) — counter badhao
    }


# CONDITIONAL EDGE 2 — evaluator ke baad: END ya worker ko wapas (max 3 rounds)
def evaluator_router(state: SidekickState) -> str:
    if state["success_criteria_met"] or state["user_input_needed"]:
        return END
    if state.get("rounds", 0) >= 3:
        # Infinite loop guard: 3 rejected rounds ke baad bhi END — graph
        # ka recursion_limit waise bhi hai, par explicit cap saaf-suthra hai.
        print("   [EVALUATOR] max 3 rounds ho gaye — stopping with best effort.")
        return END
    return "worker"   # feedback ke saath redo


# ===========================================================================
# GRAPH ASSEMBLY — worker <-> tools loop, phir evaluator gate, with MEMORY
# ===========================================================================
def build_sidekick():
    builder = StateGraph(SidekickState)
    builder.add_node("worker", worker_node)
    builder.add_node("tools", ToolNode(TOOLS))   # prebuilt: tool_calls execute + ToolMessage append
    builder.add_node("evaluator", evaluator_node)

    builder.add_edge(START, "worker")
    builder.add_conditional_edges("worker", worker_router, {"tools": "tools", "evaluator": "evaluator"})
    builder.add_edge("tools", "worker")          # tool results ke baad worker continue kare
    builder.add_conditional_edges("evaluator", evaluator_router, {"worker": "worker", END: END})

    # MemorySaver = in-RAM checkpointer (L88). Har super-step ke baad poora
    # state snapshot save hota hai, thread_id ke against. Same thread_id se
    # dobara invoke karo => purani conversation ke UPAR continue hota hai.
    return builder.compile(checkpointer=MemorySaver())


# ===========================================================================
# CONSOLE DEMO helpers — stream karke har step ka tool-call flow print karo
# ===========================================================================
def _print_update(node_name: str, update: dict) -> None:
    for m in update.get("messages", []):
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                print(f"   [{node_name}] TOOL CALL -> {tc['name']}({json.dumps(tc['args'])[:150]})")
        elif isinstance(m, ToolMessage):
            print(f"   [{node_name}] TOOL RESULT <- {str(m.content)[:160].replace(chr(10), ' ')}")
        elif isinstance(m, AIMessage) and m.content:
            print(f"   [{node_name}] ASSISTANT: {str(m.content)[:400]}")


def run_sidekick_turn(graph, user_message: str, success_criteria: str, thread_id: str) -> str:
    """Ek turn chalao with simple RETRY — free Groq tier kabhi-kabhi transient
    503/429 deta hai, isliye 3 attempts + sleep. Checkpointer ki wajah se
    retry bhi same thread par hota hai (purana context safe rehta hai)."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    payload = {
        "messages": [HumanMessage(content=user_message)],
        "success_criteria": success_criteria,
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
        "rounds": 0,
    }
    last_err = None
    for attempt in range(1, 4):
        try:
            final_text = ""
            # stream_mode="updates" => har node ke baad uska state-delta milta
            # hai — perfect for "graph andar kya kar raha hai" dikhane ke liye.
            for chunk in graph.stream(payload, config=config, stream_mode="updates"):
                for node_name, update in chunk.items():
                    if update:
                        _print_update(node_name, update)
            # Final answer checkpointed state se nikaalo (last AI message w/o tool calls)
            state = graph.get_state(config)
            for m in reversed(state.values["messages"]):
                if isinstance(m, AIMessage) and m.content and not m.tool_calls:
                    final_text = m.content
                    break
            return final_text
        except Exception as e:
            last_err = e
            print(f"   [retry] attempt {attempt} fail hua ({e}); 5s wait...")
            time.sleep(5)
            # Retry par fresh HumanMessage dobara mat bhejo agar pehle wala
            # checkpoint ho chuka hai — simplest safe move: payload None kar do
            # taaki graph wahi thread resume kare jahan atka tha.
            payload = None
    return f"ERROR: Sidekick turn fail ho gaya after retries ({last_err})"


def console_demo() -> None:
    print("=" * 78)
    print("SIDEKICK CAPSTONE — worker + tools + evaluator + memory (L84-L90)")
    print("=" * 78)
    graph = build_sidekick()
    thread_id = "demo-session-1"   # L88: har session ka apna thread => isolated memory

    # ---------------- TURN 1: research + file write + summary ----------------
    task = (
        "Research karke Wikipedia se 2-3 concrete facts nikalo LangGraph / LangChain "
        "ecosystem ke baare me (wiki_search tool use karo), phir unhe markdown bullet "
        "points ke roop me sandbox file 'langgraph_notes.md' me save karo (write_file "
        "tool se), aur end me mujhe ek chhota 2-line summary do."
    )
    criteria = (
        "1) wiki_search tool actually called for research, 2) file 'langgraph_notes.md' "
        "successfully written (tool result me 'OK: wrote' dikhna chahiye) with 2-3 factual "
        "bullet points, 3) final reply me short summary ho."
    )
    print(f"\nTURN 1 TASK: {task[:120]}...\n" + "-" * 78)
    answer = run_sidekick_turn(graph, task, criteria, thread_id)
    print("-" * 78)
    print(f"FINAL ANSWER (turn 1):\n{answer}\n")

    # ---------------- ARTIFACT VERIFICATION: file genuinely bani? ----------------
    notes_path = os.path.join(SANDBOX_DIR, "langgraph_notes.md")
    if os.path.exists(notes_path):
        with open(notes_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"ARTIFACT CHECK: sandbox/langgraph_notes.md EXISTS ({len(content)} chars)")
        print("--- file content (first 500 chars) ---")
        print(content[:500])
        print("---------------------------------------")
    else:
        print("ARTIFACT CHECK: FAIL — langgraph_notes.md nahi bani!")

    # ---------------- TURN 2: MEMORY demo — same thread, follow-up ----------------
    # Checkpointer ki wajah se Sidekick ko turn 1 ka poora context yaad hai.
    print("\nTURN 2 (memory test — same thread_id): file ko wapas padh kar count batao")
    print("-" * 78)
    answer2 = run_sidekick_turn(
        graph,
        "Maine abhi tumse jo notes file likhwayi thi, usse read_file tool se padho aur "
        "batao usme kitne bullet points hain. File ka naam tumhe yaad hona chahiye.",
        "Assistant correctly read the previously written file and reports the bullet count.",
        thread_id,
    )
    print("-" * 78)
    print(f"FINAL ANSWER (turn 2):\n{answer2}")
    print("\nDemo complete. 'ui' arg ke saath chalao to Gradio chat milega.")


# ===========================================================================
# OPTIONAL GRADIO UI (sys.argv 'ui') — L88 wale isolated sessions
# ===========================================================================
def launch_ui() -> None:
    """Gradio chat jo Sidekick graph ko thread_id ke saath call karta hai.
    L88 ka key idea: HAR browser session ka apna thread_id (gr.State me uuid)
    => do users/tabs ki conversations kabhi mix nahi hoti — MemorySaver me
    har thread ka alag checkpoint chain hai. Graph ek hi shared instance hai;
    isolation thread_id se aati hai, alag graph banane ki zaroorat nahi."""
    import gradio as gr

    graph = build_sidekick()

    def chat(message, history, criteria, thread_id):
        if not thread_id:
            thread_id = str(uuid.uuid4())   # naya session => naya isolated thread
        reply = run_sidekick_turn(
            graph, message,
            criteria or "User's request is sensibly and completely answered.",
            thread_id,
        )
        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        return history, "", thread_id

    with gr.Blocks(title="Sidekick — Week 4 Capstone") as demo:
        gr.Markdown("# Sidekick — personal co-worker (LangGraph capstone)")
        thread_state = gr.State("")          # per-session thread_id (isolated memory)
        criteria_box = gr.Textbox(label="Success criteria (optional)",
                                  placeholder="e.g. answer should cite a Wikipedia fact")
        # Gradio 6.x me Chatbot default 'messages' format use karta hai
        # (role/content dicts) — purana type="messages" kwarg ab hata diya gaya
        chatbot = gr.Chatbot(label="Sidekick", height=420)
        msg_box = gr.Textbox(label="Task", placeholder="e.g. research X and save notes to notes.md")
        msg_box.submit(chat, [msg_box, chatbot, criteria_box, thread_state],
                       [chatbot, msg_box, thread_state])
    demo.launch()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ui":
        launch_ui()
    else:
        console_demo()
