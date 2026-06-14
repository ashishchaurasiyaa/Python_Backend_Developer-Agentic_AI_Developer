"""
LAB 5 — Agent loop from scratch (no framework) | Week 1 Day 5 Extra | Lecture L27
=================================================================================

Kya seekhna hai (what you'll learn):
------------------------------------
Yeh lab dikhata hai ki ek "AGENT" andar se actually kaise kaam karta hai — bina
kisi framework ke. Hum apne haathon se woh LOOP likhenge jise OpenAI Agents SDK,
LangGraph, CrewAI etc. baad ke weeks me automate kar dete hain.

Ek agent = LLM + tools + ek WHILE LOOP. Bas itna hi. Loop ka funda:
    1. LLM ko messages + tools bhejo.
    2. Agar LLM tool_calls return kare  -> woh python functions chalao,
       result ko role="tool" message bana ke wapas history me daalo, loop repeat.
    3. Agar LLM bina tool_call ke seedha text de  -> woh FINAL ANSWER hai, loop khatam.
    4. Safety ke liye max_iters cap (warna infinite loop me phas sakte ho).

Yahi 4-step dance hi "agentic" behaviour hai. Frameworks isi plumbing
(tool_call_id matching, json parsing, message history) ko chhupa dete hain — par
hum aaj usse khol ke dekhenge taaki magic demystify ho jaaye.

Kaise chalana hai (how to run):
-------------------------------
    uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab5_agent_loop_from_scratch.py

Default provider = GROQ (free + fast). .env me GROQ_API_KEY hona chahiye.
Model: llama-3.3-70b-versatile — yeh tool/function calling support karta hai.
"""

import os
import re
import json
import ast
import operator

from dotenv import load_dotenv
from openai import OpenAI

# .env load karo (override=True taaki shell ke purane env vars override ho jaayein)
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# PROVIDER STRATEGY — har lab self-contained hai, isliye get_client yahin inline.
# Groq / Gemini OpenAI-compatible hain bas base_url alag hota hai. OpenAI default.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """Return (client, model_name). Groq default = free + fast + tool-calling capable."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY")), "llama-3.3-70b-versatile"
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY")), "gemini-2.0-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# STEP 1 — TOOLS define karo (do hisse: (a) python function, (b) JSON schema)
# ===========================================================================
# Yeh samajhna important hai: LLM khud kabhi code "run" nahi karta. LLM sirf
# kehta hai "mujhe yeh tool, yeh arguments ke saath chalwao". ASLI execution HUM
# (python me) karte hain. Tool ka JSON schema hi LLM ko batata hai ki tool ka
# naam kya hai, kya karta hai, aur kaunse arguments leta hai.

# ---- safe calculator ka backbone: sirf basic arithmetic, no arbitrary eval ----
# Hum eval() use NAHI karenge (security disaster). Iski jagah Python ke AST ko
# parse kar ke sirf allowed math operators evaluate karenge. Yeh "safe eval" hai.
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node):
    """AST node ko recursively evaluate karo — sirf numbers + allowed operators."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    # Python 3.8+ me numeric literals ast.Constant me aate hain
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Sirf numbers allowed hain, mila: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval_node(node.operand))
    # Koi bhi cheez jo allowed list me nahi -> reject (no function calls, no names)
    raise ValueError(f"Yeh expression allowed nahi hai: {ast.dump(node)}")


def calculator(expression: str) -> str:
    """Safe arithmetic calculator. Sirf + - * / // % ** aur numbers handle karta hai."""
    # Pehle ek mota-mota cleanup: sirf safe characters rakho
    cleaned = re.sub(r"[^0-9+\-*/().%\s]", "", expression)
    try:
        tree = ast.parse(cleaned, mode="eval")
        result = _safe_eval_node(tree)
        return f"{result}"
    except Exception as e:
        # Tool kabhi crash nahi hona chahiye — error bhi LLM ke liye ek "result" hai
        return f"ERROR: '{expression}' evaluate nahi ho paaya ({e})"


# ---- ek "knowledge lookup" jaisa tool, par real API ke bina (canned answers) ----
# Real duniya me yeh ek web search / DB query / RAG retrieval hota. Yahan hum
# canned strings de rahe hain taaki lab free aur deterministic rahe.
_CANNED_INFO = {
    "python": ("Python ek high-level, dynamically-typed language hai jo Guido van "
               "Rossum ne 1991 me release ki. Yeh readability aur batteries-included "
               "stdlib ke liye famous hai, aur AI/ML ki de-facto language hai."),
    "agentic ai": ("Agentic AI ka matlab hai LLM ko tools + memory + ek control loop "
                   "dena taaki woh multi-step tasks khud plan aur execute kar sake — "
                   "sirf ek single text reply ke bajaye."),
    "groq": ("Groq ek inference company hai jo custom LPU chips par open models "
             "(jaise Llama) ko bahut fast aur free-tier-friendly serve karti hai."),
}


def get_current_info(topic: str) -> str:
    """Ek topic ke baare me chhoti si canned info return karta hai (mock lookup)."""
    key = topic.strip().lower()
    # Exact match try karo, warna substring match, warna polite fallback
    if key in _CANNED_INFO:
        return _CANNED_INFO[key]
    for known, info in _CANNED_INFO.items():
        if known in key or key in known:
            return info
    return (f"'{topic}' ke baare me mere paas abhi koi stored info nahi hai. "
            f"Main sirf in topics par jaanta hoon: {', '.join(_CANNED_INFO)}.")


# ---------------------------------------------------------------------------
# TOOL REGISTRY — naam se asli python callable dhoondhne ke liye (dispatch table)
# ---------------------------------------------------------------------------
# Jab LLM bole "calculator chalao", hum is dict se asli function uthaate hain.
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_info": get_current_info,
}

# ---------------------------------------------------------------------------
# TOOL SCHEMAS — yeh exactly woh JSON hai jo LLM ko 'tools=' param me jaata hai.
# "parameters" ek JSON-Schema object hota hai. Yahin se LLM ko pata chalta hai
# ki arguments ka structure kya hona chahiye.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": ("Basic arithmetic evaluate karta hai. Use this jab bhi "
                            "math/numbers ka calculation chahiye. Supports + - * / // % "
                            "and ** (power)."),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression, e.g. '23*17 + 5'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_info",
            "description": ("Kisi topic ke baare me chhoti factual info laata hai. "
                            "Use this jab user kisi cheez ke baare me 'tell me about' "
                            "type ka sawaal kare."),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic name, e.g. 'Python' or 'Agentic AI'",
                    }
                },
                "required": ["topic"],
            },
        },
    },
]


# ===========================================================================
# STEP 2 — THE AGENT LOOP (yeh hi pure lab ka dil hai)
# ===========================================================================
def run_agent(task: str, provider: str = "groq", max_iters: int = 8) -> str:
    """
    Ek explicit while-loop agent. LLM ko baar-baar call karta hai, tool_calls
    execute karta hai, results wapas feed karta hai, aur tab rukta hai jab LLM
    bina tool_call ke final answer de — ya max_iters hit ho jaaye.

    Return: final answer string.
    """
    client, model = get_client(provider)

    # 'messages' = poori conversation history. Har iteration me yeh grow hoti hai.
    # System message agent ko uska role aur tools-discipline samjhata hai.
    messages = [
        {
            "role": "system",
            "content": ("Tum ek helpful agent ho jiske paas tools hain. Jab bhi math "
                        "ya factual lookup chahiye, available tools use karo — apne "
                        "head se guess mat karo. Saare tool results milne ke baad ek "
                        "clear final answer do."),
        },
        {"role": "user", "content": task},
    ]

    print("=" * 70)
    print(f"AGENT START  |  provider={provider}  model={model}")
    print(f"TASK: {task}")
    print("=" * 70)

    # ---- THE LOOP ----
    for iteration in range(1, max_iters + 1):
        print(f"\n----- ITERATION {iteration}/{max_iters} -----")

        # (a) LLM ko current history + tools ke saath call karo.
        #     tool_choice='auto' => LLM khud decide karega tool use karna hai ya nahi.
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        # LLM ka jawab nikaalo. Yeh ya to (i) tool_calls maangega ya (ii) text dega.
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

        # (b) AGAR koi tool_call NAHI hai -> yeh FINAL ANSWER hai. Loop tod do.
        if not tool_calls:
            final_text = assistant_message.content or "(LLM ne empty response diya)"
            print("LLM ne koi tool nahi maanga -> yeh FINAL ANSWER hai.")
            print("\n" + "=" * 70)
            print("FINAL ANSWER:")
            print(final_text)
            print("=" * 70)
            return final_text

        # (c) AGAR tool_calls hain -> pehle assistant ka yeh "main yeh tools chalwana
        #     chahta hoon" wala message history me daalo. Yeh STEP critical hai:
        #     baad me hum jo role="tool" results bhejenge unko in tool_call ids se
        #     match hona padta hai. Isliye assistant message zaroor add karo.
        #
        #     GOTCHA: assistant_message.model_dump() ek 'annotations' field bhi add
        #     karta hai jise Groq (aur kuch OpenAI-compat endpoints) echo-back par
        #     REJECT kar dete hain ("property 'annotations' is unsupported"). Isliye
        #     hum SIRF zaroori fields (role, content, tool_calls) ke saath ek saaf
        #     dict banate hain.
        messages.append({
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })

        print(f"LLM ne {len(tool_calls)} tool call(s) maange. Ab unhe execute karte hain:")

        # (d) Har tool_call ko execute karo aur result ko role="tool" message bana
        #     ke history me daalo. tool_call_id ka plumbing yahin hota hai.
        for tc in tool_calls:
            fn_name = tc.function.name
            raw_args = tc.function.arguments  # yeh ek JSON *string* hota hai

            # json.loads se arguments string ko python dict me parse karo.
            # Defensive: agar LLM ne kharaab JSON bheja to crash mat hone do.
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}
                print(f"   [warn] '{fn_name}' ke arguments parse nahi hue: {raw_args!r}")

            print(f"   -> TOOL CALL: {fn_name}({args})   [id={tc.id}]")

            # Registry se asli python function uthao aur chalao.
            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn is None:
                result = f"ERROR: '{fn_name}' naam ka koi tool registered nahi hai."
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    # Tool exception ko bhi ek text result ki tarah LLM ko de do —
                    # taaki agent re-plan kar sake, crash na ho.
                    result = f"ERROR while running {fn_name}: {e}"

            print(f"      RESULT: {result}")

            # Result ko role="tool" message bana ke history me daalo. tool_call_id
            # se LLM ko pata chalta hai ki yeh result KAUNSE call ka jawab hai.
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,   # <-- yeh id assistant ke tool_call se match honi chahiye
                "name": fn_name,
                "content": str(result),
            })

        # (e) Loop wapas upar jaata hai: ab LLM ke paas tool results aa gaye, woh
        #     ya to aur tools maangega ya final answer dega. Yahi "reasoning loop" hai.

    # max_iters khatam ho gaye aur LLM abhi bhi tools maang raha hai -> safety stop.
    print("\n[stop] max_iters hit ho gaya — agent ko force-stop kar rahe hain.")
    return "(Agent max_iters tak final answer par nahi pahuncha.)"


# ===========================================================================
# STEP 3 — DEMO: aisa task jo tool use FORCE karta hai (math + lookup dono)
# ===========================================================================
if __name__ == "__main__":
    # Yeh task jaan-bujhke do tools ko trigger karta hai:
    #   - "23*17 + 5"  -> calculator
    #   - "tell me something about Python" -> get_current_info
    # Iss se aap dekh paaoge ki agent loop multiple iterations / tool calls handle
    # karta hai aur fir results ko jodke ek final answer banata hai.
    demo_task = "What is 23*17 + 5, and tell me something about Python?"

    try:
        run_agent(demo_task, provider="groq", max_iters=8)
    except Exception as e:
        # Fresh setup pe agar GROQ_API_KEY missing/galat ho to graceful message.
        print("\n[ERROR] Agent loop chalane me dikkat hui:")
        print(f"        {type(e).__name__}: {e}")
        print("        Check karo ki .env me GROQ_API_KEY set hai (uv run se chalao).")

    # ---- TAKEAWAY (Hinglish) -------------------------------------------------
    # Jo while-loop tumne upar dekha — LLM call -> tool_calls execute -> results
    # wapas feed -> repeat -> final answer — yahi pura "agent" hai. Koi magic nahi.
    # OpenAI Agents SDK / LangGraph / CrewAI bas isi loop ko, plus state-management,
    # retries, parallel tool calls, aur guardrails ke saath, tumhare liye automate
    # karte hain. Baad ke weeks me hum wahi frameworks use karenge — par ab tum
    # andar ka mechanism JAANTE ho. Yahi is lab ka asli inaam hai.
    print("\n[done] Lab 5 complete — ab tum jaante ho ki agent loop andar se kaisa dikhta hai.")
