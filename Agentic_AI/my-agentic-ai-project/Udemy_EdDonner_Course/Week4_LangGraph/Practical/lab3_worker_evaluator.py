"""
LAB 3 — Worker-Evaluator Feedback Loop (Lectures L80-L83, L89)
================================================================

KYA SEEKHENGE:
- Anthropic ka "Evaluator-Optimizer" agentic pattern, LangGraph me implement kiya hua.
- L89 ka core idea: "inside AI feedback loops" — ek LLM kaam karta hai (WORKER),
  doosra LLM judge karta hai (EVALUATOR), aur fail hone par feedback ke saath
  wapas worker ko bheja jata hai. LangGraph me ye loop graph ka CYCLE hota hai —
  yahi graph framework ka natural advantage hai plain chains ke upar.
- CONDITIONAL EDGE se loop control: criteria met -> END, nahi to wapas worker,
  aur attempts cap (3) se infinite loop se bachna.
- STRUCTURED OUTPUT (with_structured_output + Pydantic) se evaluator ka verdict
  machine-readable banana — bool flag par routing hoti hai, vibes par nahi.
- Multi-provider setup: Worker = Groq (llama-3.3), Evaluator = Gemini
  (alag persona/model taaki judge biased na ho — "self-grading" problem avoid),
  Gemini fail ho to Groq fallback.

KAISE CHALANA:
    cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
    uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab3_worker_evaluator.py

GRAPH SHAPE (cycle dhyan se dekho — yahi feedback loop hai):

    START -> worker -> evaluator --(criteria met / max attempts)--> END
                ^                         |
                |____(feedback ke saath)__|
"""

import os
import time

from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# RETRY HELPER — free Groq tier kabhi-kabhi transient 429/503 deta hai,
# isliye har LLM call ko simple retry (3 attempts + sleep) me wrap karte hain.
# ---------------------------------------------------------------------------
def with_retry(fn, attempts: int = 3, delay: float = 3.0):
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — demo me broad catch theek hai
            last_err = e
            if i < attempts - 1:
                print(f"   [retry] LLM call fail ({type(e).__name__}), {delay}s baad dobara...")
                time.sleep(delay)
    raise last_err


# ---------------------------------------------------------------------------
# 1) STATE — graph ki shared memory. Har node isse padhta hai aur PARTIAL
#    update return karta hai. Sirf 'messages' par add_messages REDUCER laga
#    hai (append semantics); baaki fields par default LAST-WRITE-WINS
#    (naya value purane ko REPLACE karta hai) — attempts/feedback ke liye
#    yahi chahiye.
# ---------------------------------------------------------------------------
class State(TypedDict):
    messages: Annotated[list, add_messages]  # reducer: naye msgs APPEND hote hain
    feedback: str                            # evaluator ka latest feedback (replace)
    success_criteria: str                    # kaam pass hone ki kasauti (fixed input)
    attempts: int                            # worker ne kitni baar try kiya (counter)
    success_criteria_met: bool               # routing flag — conditional edge isi par chalti hai


# ---------------------------------------------------------------------------
# 2) EVALUATOR ka STRUCTURED OUTPUT schema — Pydantic model dekar
#    with_structured_output() use karenge, taaki verdict me guaranteed
#    'success_criteria_met' bool mile. Free-text judge se routing karna
#    fragile hota — bool flag par conditional edge solid rehti hai.
# ---------------------------------------------------------------------------
class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Concrete, actionable feedback on the worker's answer")
    success_criteria_met: bool = Field(description="True only if the answer fully meets the success criteria")


# ---------------------------------------------------------------------------
# LLMs — do ALAG models, do ALAG roles:
#   WORKER    = Groq llama-3.3-70b (creative kaam karne wala)
#   EVALUATOR = Gemini 2.0 Flash (alag provider = unbiased judge), structured
#               output ke saath. Gemini na chale to Groq fallback — dono
#               with_structured_output support karte hain (tool-calling se).
# ---------------------------------------------------------------------------
worker_llm = ChatGroq(model="llama-3.3-70b-versatile")  # GROQ_API_KEY env se uthata hai

def get_evaluator_verdict(eval_messages) -> EvaluatorOutput:
    """Pehle Gemini try karo, fail ho to Groq fallback — dono structured output ke saath."""
    try:
        # NOTE: gemini-2.0-flash ka free quota ab 429 deta hai — 2.5-flash use karo (verified working).
        gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        evaluator = gemini.with_structured_output(EvaluatorOutput)
        verdict = with_retry(lambda: evaluator.invoke(eval_messages), attempts=2, delay=2)
        print("   (evaluator model: gemini-2.5-flash)")
        return verdict
    except Exception as e:  # noqa: BLE001
        # Gemini flaky/quota issue — Groq par with_structured_output bhi
        # tool-calling ke through kaam karta hai, isliye seamless fallback.
        print(f"   (gemini fail: {type(e).__name__} — Groq evaluator fallback)")
        groq_eval = ChatGroq(model="llama-3.3-70b-versatile").with_structured_output(EvaluatorOutput)
        verdict = with_retry(lambda: groq_eval.invoke(eval_messages))
        print("   (evaluator model: groq llama-3.3-70b fallback)")
        return verdict


# ---------------------------------------------------------------------------
# 3) WORKER NODE — task solve karta hai. Agar state me pichla feedback pada
#    hai (matlab ye RETRY hai), to system prompt me feedback inject karke
#    use FIX karne bolte hain. Attempts counter yahi badhta hai — har worker
#    run = ek attempt.
# ---------------------------------------------------------------------------
def worker_node(state: State):
    attempt_no = state["attempts"] + 1

    # DEMO DESIGN NOTE: worker ko RAW success_criteria nahi dete — sirf user
    # ka task + evaluator feedback. Real world me bhi evaluator ke paas aksar
    # worker se zyada detailed rubric hota hai (e.g. QA checklist). Isi gap
    # ki wajah se feedback loop ACTUALLY kaam karta dikhega — attempt 1 me
    # worker hidden requirement miss karega, feedback se attempt 2 me fix.
    system = (
        "You are a skilled writing assistant. Complete the user's task exactly.\n"
        "Reply with ONLY the final answer, no explanations."
    )
    # FEEDBACK LOOP ka dil: pichle evaluator ka feedback worker ke context me
    # daal rahe hain — isi se dusra attempt pehle se behtar hota hai.
    if state["feedback"]:
        system += (
            "\nYour previous attempt FAILED evaluation. Evaluator feedback:\n"
            f"{state['feedback']}\n"
            "Fix these issues in your new attempt."
        )

    # NOTE: SystemMessage ko state me store nahi kar rahe — har attempt par
    # fresh banate hain (kyunki feedback badalta rehta hai). State ke
    # messages me sirf conversation (task + answers + feedback) jata hai.
    response = with_retry(lambda: worker_llm.invoke([SystemMessage(content=system)] + state["messages"]))

    print(f"\n{'=' * 70}")
    print(f"WORKER — ATTEMPT {attempt_no}")
    print("=" * 70)
    print(response.content)

    # Partial update: messages APPEND honge (reducer), attempts REPLACE hoga.
    return {"messages": [response], "attempts": attempt_no}


# ---------------------------------------------------------------------------
# 4) EVALUATOR NODE — worker ke LATEST jawab ko success_criteria ke against
#    judge karta hai, structured verdict deta hai. Fail hone par feedback ko
#    HumanMessage ke roop me conversation me bhi daal dete hain taaki message
#    history me poora loop dikhe (worker isi history par next attempt karega).
# ---------------------------------------------------------------------------
def evaluator_node(state: State):
    last_answer = state["messages"][-1].content  # worker ka abhi-abhi diya jawab

    eval_messages = [
        SystemMessage(content=(
            "You are a STRICT evaluator. Judge the assistant's answer ONLY against "
            "the success criteria. Be picky: if even one requirement is not fully met, "
            "set success_criteria_met=false and give precise, actionable feedback."
        )),
        HumanMessage(content=(
            f"SUCCESS CRITERIA:\n{state['success_criteria']}\n\n"
            f"ANSWER TO EVALUATE:\n{last_answer}\n\n"
            "Check every requirement one by one, then give your verdict."
        )),
    ]

    print(f"\n{'-' * 70}")
    print(f"EVALUATOR — verdict for attempt {state['attempts']}")
    print("-" * 70)
    verdict = get_evaluator_verdict(eval_messages)

    status = "PASS — criteria met" if verdict.success_criteria_met else "FAIL — criteria NOT met"
    print(f"   Verdict : {status}")
    print(f"   Feedback: {verdict.feedback}")

    update = {
        "feedback": verdict.feedback,
        "success_criteria_met": verdict.success_criteria_met,
    }
    if not verdict.success_criteria_met:
        # Feedback ko conversation me bhi append karo — add_messages reducer
        # ise history me joRega, worker next attempt me ise dekh payega.
        update["messages"] = [HumanMessage(content=f"Evaluator feedback (fix this): {verdict.feedback}")]
    return update


# ---------------------------------------------------------------------------
# 5) CONDITIONAL EDGE — evaluator ke baad teen raste:
#      a) criteria met        -> END (jeet gaye)
#      b) fail + attempts < 3 -> wapas "worker" (YAHI CYCLE feedback loop hai)
#      c) fail + attempts >= 3-> END (max attempts — infinite loop guard;
#                                bina iske graph recursion limit hit karta)
#    Ye function sirf STRING return karta hai (next node ka naam) — state
#    mutate nahi karta. Routing logic, node logic se alag rehti hai.
# ---------------------------------------------------------------------------
MAX_ATTEMPTS = 3

def route_after_evaluation(state: State) -> str:
    if state["success_criteria_met"]:
        return "success"          # END — kaam ho gaya
    if state["attempts"] >= MAX_ATTEMPTS:
        return "give_up"          # END — max attempts exhaust
    return "retry"                # wapas worker — feedback loop ka cycle


# ---------------------------------------------------------------------------
# 6) GRAPH BUILD — dhyan do: "evaluator -> worker" edge hi is graph ko CYCLIC
#    banati hai. LangGraph me cycles first-class hain (Pregel-style
#    super-steps), isliye evaluator-optimizer pattern yahan naturally fit
#    hota hai — plain LCEL chain me ye loop likhna painful hota.
# ---------------------------------------------------------------------------
def build_graph():
    builder = StateGraph(State)
    builder.add_node("worker", worker_node)
    builder.add_node("evaluator", evaluator_node)

    builder.add_edge(START, "worker")
    builder.add_edge("worker", "evaluator")
    # Conditional edge: route function ka return -> actual node mapping
    builder.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {"success": END, "give_up": END, "retry": "worker"},
    )
    return builder.compile()


# ---------------------------------------------------------------------------
# CONSOLE DEMO — poora feedback loop ek hi invoke me chalta hai; har
# iteration ke prints NODES ke andar se aate hain, isliye loop LIVE dikhega.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY .env me nahi mila — pehle .env set karo.")

    task = (
        "Write a 4-line poem about backend engineers learning AI. "
        "The word 'agentic' must appear, and every line must start with a capital letter."
    )
    # Criterion #5 worker ke task me NAHI hai — sirf evaluator ke rubric me.
    # Isse attempt 1 lagbhag pakka FAIL hoga aur feedback loop saaf dikhega:
    # evaluator feedback dega "LangGraph mention karo", worker attempt 2 me
    # use incorporate karega. Yahi L89 ka "inside AI feedback loops" hai.
    success_criteria = (
        "1) Exactly 4 lines. "
        "2) Topic: backend engineers learning AI. "
        "3) The word 'agentic' appears somewhere in the poem. "
        "4) Every line starts with a capital letter. "
        "5) The poem must also mention the word 'LangGraph'."
    )

    print("\n" + "#" * 70)
    print("# LAB 3 — WORKER-EVALUATOR FEEDBACK LOOP (evaluator-optimizer pattern)")
    print("#" * 70)
    print(f"\nTASK: {task}")
    print(f"SUCCESS CRITERIA: {success_criteria}")

    graph = build_graph()

    # Initial state — attempts=0, feedback khali; worker pehla attempt karega.
    initial_state: State = {
        "messages": [HumanMessage(content=task)],
        "feedback": "",
        "success_criteria": success_criteria,
        "attempts": 0,
        "success_criteria_met": False,
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:  # noqa: BLE001 — graceful exit agar saare retries fail
        raise SystemExit(f"\nDemo fail ho gaya (LLM/API issue): {type(e).__name__}: {e}")

    # Final answer = aakhri AI message (worker ka last attempt).
    final_answer = next(
        (m.content for m in reversed(final_state["messages"]) if isinstance(m, AIMessage)),
        "(koi answer nahi mila)",
    )

    print(f"\n{'#' * 70}")
    print("# FINAL RESULT")
    print("#" * 70)
    if final_state["success_criteria_met"]:
        print(f"Criteria MET in {final_state['attempts']} attempt(s).")
    else:
        print(f"MAX ATTEMPTS ({MAX_ATTEMPTS}) reached — criteria still NOT met. Best effort below.")
        print(f"Last feedback: {final_state['feedback']}")
    print(f"\nFINAL ANSWER:\n{final_answer}")
    print(f"\nTotal worker attempts: {final_state['attempts']}")
