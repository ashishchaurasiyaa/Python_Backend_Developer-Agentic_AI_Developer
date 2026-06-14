"""
============================================================================
LAB 4 — Career Alter-Ego Agent  (Week 1 ka CAPSTONE, Day 5, lectures L21-L25)
============================================================================

KYA SEEKHNA HAI (the whole point of this lab):
  Ham ek AI banayenge jo KHUD AAPKI (the user) digital alter-ego ban jaata hai.
  Visitors aapke career ke baare me sawaal puchte hain, aur ye agent aapki
  taraf se professionally jawaab deta hai — pehle person me, jaise aap khud
  bol rahe ho.

  Lekin asli magic do cheezein hain (Ed Donner's signature lab):
    1) TOOLS + FUNCTION CALLING — LLM khud decide karta hai ki kab ek
       Python function call karna hai (e.g. visitor ka email record karna,
       ya ek aisa sawaal log karna jiska jawaab usko nahi pata).
    2) THE AGENT LOOP — LLM ek tool maangta hai -> ham use chalate hain ->
       result wapas LLM ko dete hain -> LLM phir se sochta hai... ye loop
       tab tak chalta hai jab tak LLM ek normal text answer na de de.
       Yahi "agentic" behaviour ka core hai. Is loop ko dhyaan se padhna.

CHALANE KA TARIKA:
    uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab4_career_agent.py

  Script chalte hi ek Gradio chatbot UI browser me khulega. Yehi cheez
  course me aage HuggingFace Spaces par deploy ki jaati hai — yaani ye lab
  ek actual deployable product hai, sirf ek toy script nahi.

OPTIONAL SETUP (lab inke bina bhi chalta hai, placeholder bio use karega):
    Practical/me/summary.txt   -> aapka chhota sa bio / about-me (plain text)
    Practical/me/linkedin.pdf  -> aapka LinkedIn profile export (PDF)
  Aur agar aap phone par push notifications chahte ho jab koi tool fire ho:
    .env me PUSHOVER_TOKEN aur PUSHOVER_USER daal do (warna push silent rehta hai).

KAUNSI LECTURE: Week 1 Project 1 — "Build your own AI digital twin" (L21-L25).
============================================================================
"""

import os
import json
import httpx
import gradio as gr
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# .env load — override=True taaki shell ke purane vars overwrite ho jaayein.
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# PROVIDER STRATEGY — har lab apna get_client INLINE rakhta hai (self-contained).
# Default GROQ hai: free + fast, aur llama-3.3-70b-versatile TOOL CALLS support
# karta hai (verified). Isi liye is lab ka default provider groq hi hai.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """Return (client, model_name). Groq aur Gemini OpenAI-compatible hain base_url se."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY")), "llama-3.3-70b-versatile"
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY")), "gemini-2.0-flash"
    raise ValueError(f"Unknown provider: {provider}")


# Ek hi client/model poore script me reuse karenge.
client, MODEL = get_client("groq")

# Ye naam persona me use hoga. Aap chaaho to apna asli naam yahan daal sakte ho.
NAME = "Ashish Chaurasiya"


# ===========================================================================
# PART 1 — PERSONA SETUP  (summary.txt + linkedin.pdf padho, warna placeholder)
# ===========================================================================
# me/ folder isi file ke bagal me hota hai (Practical/me/...). __file__ ke
# relative path use kar rahe hain taaki cwd kuch bhi ho, raasta sahi rahe.
ME_DIR = Path(__file__).parent / "me"


def load_summary() -> str:
    """me/summary.txt padho. Agar nahi mila to clearly-marked placeholder do + tip print."""
    summary_path = ME_DIR / "summary.txt"
    try:
        text = summary_path.read_text(encoding="utf-8").strip()
        if text:
            print(f"[persona] summary.txt load ho gaya ({len(text)} chars).")
            return text
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[persona] summary.txt padhne me error: {e}")

    # --- Fallback placeholder bio (clearly marked as PLACEHOLDER) ---
    print(f"[tip] Apna asli bio dikhane ke liye file banao: {summary_path}")
    return (
        "[PLACEHOLDER BIO — asli summary.txt nahi mila] "
        f"{NAME} ek experienced backend software engineer hai (4+ years), "
        "Python, distributed systems aur API design me strong. Aajkal Agentic AI "
        "seekh raha hai — LLM tools, function calling, aur multi-agent systems. "
        "Curious, pragmatic, aur clean engineering pasand karta hai."
    )


def load_linkedin() -> str:
    """me/linkedin.pdf se text nikaalo pypdf se. Nahi mila to khali string (optional hai)."""
    pdf_path = ME_DIR / "linkedin.pdf"
    try:
        from pypdf import PdfReader  # local import: pypdf na ho to bhi lab na toote
        reader = PdfReader(str(pdf_path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages).strip()
        print(f"[persona] linkedin.pdf load ho gaya ({len(reader.pages)} pages).")
        return text
    except FileNotFoundError:
        print(f"[tip] (optional) LinkedIn profile add karne ke liye: {pdf_path}")
        return ""
    except Exception as e:
        print(f"[persona] linkedin.pdf padhne me error (ignore kar rahe hain): {e}")
        return ""


# Persona content ek baar load kar lete hain (script start par).
SUMMARY = load_summary()
LINKEDIN = load_linkedin()


def build_system_prompt() -> str:
    """
    System prompt agent ko batata hai:
      - Tum {NAME} ho, pehle person me professionally jawaab do.
      - Apna bio + LinkedIn context use karo.
      - JAB JAWAAB NA PATA HO -> record_unknown_question tool call karo.
      - JAB visitor contact/email share kare -> record_user_details tool call karo.
    Ye instructions hi LLM ko tools use karne ke liye "nudge" karti hain.
    """
    prompt = (
        f"Tum {NAME} ho — is website par {NAME} ki taraf se baat kar rahe ho. "
        f"Tumhara kaam hai visitors ke career-related sawaalon ka jawaab dena, "
        f"jaise tum khud {NAME} ho. Background: career, skills, experience, projects. "
        f"Hamesha professional, friendly, aur engaging raho — jaise tum ek potential "
        f"client ya future employer se baat kar rahe ho. Pehle person ('main', 'I') me jawaab do.\n\n"
        f"## {NAME} ka Summary:\n{SUMMARY}\n\n"
    )
    if LINKEDIN:
        prompt += f"## LinkedIn Profile:\n{LINKEDIN}\n\n"

    prompt += (
        "## TOOLS USE KARNE KE RULES (very important):\n"
        "- Agar koi aisa sawaal aaye jiska jawaab tumhare paas context me NAHI hai "
        "(ya tum sure nahi ho), to GUESS mat karo — 'record_unknown_question' tool "
        "ko call karo aur us sawaal ko log kar do. Phir politely user ko batao ki tum "
        "ye note kar liya hai aur baad me follow up karoge.\n"
        "- Agar user contact me interested lage ya apna email/contact share kare, to "
        "'record_user_details' tool call karo taaki connection record ho jaaye. "
        "Agar email nahi diya to politely email maang lo.\n"
        f"Hamesha {NAME} ki aawaaz me, character me raho."
    )
    return prompt


# ===========================================================================
# PART 2 — TOOLS  (Pushover helper + do tool functions + JSON schemas + map)
# ===========================================================================

def push(message: str) -> None:
    """
    Pushover push notification bhejo (httpx se POST).
    AGAR PUSHOVER_TOKEN / PUSHOVER_USER env vars missing hain -> SILENT no-op.
    Kabhi crash nahi hota — try/except sab kuch swallow kar leta hai.
    (Note: project rule ke mutabik 'requests' nahi, httpx use kar rahe hain.)
    """
    token = os.getenv("PUSHOVER_TOKEN")
    user = os.getenv("PUSHOVER_USER")
    if not token or not user:
        return  # Pushover configured nahi hai -> chup-chaap nikal jao.
    try:
        httpx.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": token, "user": user, "message": message},
            timeout=10,
        )
    except Exception as e:
        # Network/Pushover fail ho to lab nahi toot na chahiye.
        print(f"[push] notification bhejne me error (ignore): {e}")


def record_user_details(email, name="Name not provided", notes="not provided"):
    """
    TOOL: ek interested visitor ko record karta hai.
    LLM tab call karega jab koi apna contact/email share karega.
    """
    print(f"[TOOL record_user_details] email={email!r}, name={name!r}, notes={notes!r}")
    push(f"Naya interested visitor! email={email}, name={name}, notes={notes}")
    # LLM ko ek structured result wapas dena best practice hai.
    return {"recorded": "ok", "email": email}


def record_unknown_question(question):
    """
    TOOL: koi aisa sawaal record karta hai jiska jawaab agent ko nahi pata.
    Isse aap baad me apni 'knowledge gaps' dekh sakte ho.
    """
    print(f"[TOOL record_unknown_question] question={question!r}")
    push(f"Agent ko ye sawaal nahi aata tha: {question}")
    return {"recorded": "ok", "question": question}


# --- OpenAI function-calling JSON SCHEMAS ---------------------------------
# Ye schemas LLM ko batate hain ki kaunse tools available hain, unke parameters
# kya hain, aur kab use karne hain (description bahut important hai — LLM yahi
# padh kar decide karta hai).
record_user_details_schema = {
    "type": "function",
    "function": {
        "name": "record_user_details",
        "description": (
            "Use this tool to record that a visitor is interested in getting in touch "
            "and provided an email address. Call this whenever the user shares contact details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address of the interested visitor",
                },
                "name": {
                    "type": "string",
                    "description": "The visitor's name, if they provided it",
                },
                "notes": {
                    "type": "string",
                    "description": "Any extra context about the conversation worth recording",
                },
            },
            "required": ["email"],
            "additionalProperties": False,
        },
    },
}

record_unknown_question_schema = {
    "type": "function",
    "function": {
        "name": "record_unknown_question",
        "description": (
            "Always use this tool to record any question that you could not answer "
            "because you did not know the answer from the provided context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question that could not be answered",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
}

# TOOLS = saare schemas ek list me (yehi LLM ko bheji jaati hai).
TOOLS = [record_user_details_schema, record_unknown_question_schema]

# Naam -> asli Python function ka map. Jab LLM tool maange to is map se
# function dhoond kar chalate hain.
TOOL_FUNCTIONS = {
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question,
}


def handle_tool_calls(tool_calls):
    """
    LLM ne jo tool_calls maange, unko execute karke role="tool" messages banao.
    Har tool result ka tool_call_id wahi hona chahiye jo LLM ne diya tha —
    yehi 'plumbing' LLM ko batati hai konsa result kis call ka hai.
    """
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        # arguments ek JSON *string* hota hai — json.loads se dict banao.
        arguments = json.loads(tool_call.function.arguments or "{}")
        print(f"[agent] LLM ne tool maanga: {tool_name}({arguments})")

        # Naam se asli function dhoondo aur chalao (unknown ho to error result do).
        tool = TOOL_FUNCTIONS.get(tool_name)
        if tool is None:
            result = {"error": f"Unknown tool: {tool_name}"}
        else:
            result = tool(**arguments)

        # Result ko role="tool" message banao — tool_call_id MUST match.
        results.append({
            "role": "tool",
            "content": json.dumps(result),
            "tool_call_id": tool_call.id,
        })
    return results


# ===========================================================================
# PART 3 — THE AGENT LOOP  (is lab ka dil — dhyaan se padho)
# ===========================================================================
def chat(message, history):
    """
    Gradio har user message par ye function call karta hai.
      message : abhi ka user message (string)
      history : pichhle turns — gr.ChatInterface "messages" format me
                [{'role': 'user'/'assistant', 'content': '...'}, ...] deta hai.

    Flow:
      1) messages banao = system prompt + purani history + naya user message.
      2) LLM ko call karo TOOLS ke saath.
      3) Agar LLM tool_calls maangta hai:
           - tools execute karo, results ko messages me append karo,
           - LLM ko PHIR se call karo (ab usko tool ka result dikhega).
         Ye loop tab tak chalega jab tak LLM ek normal text answer na de.
      4) Final text answer return karo (Gradio use dikha dega).
    """
    # Step 1 — message stack banao. System prompt sabse upar.
    messages = [{"role": "system", "content": build_system_prompt()}]
    # Gradio 'messages' format me history deta hai, par usme 'metadata'/'options'
    # jaisi extra keys ho sakti hain jinhe API reject kar de. Isliye sirf
    # role+content nikaal ke clean karte hain.
    for h in history:
        if isinstance(h, dict) and h.get("role") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    # Step 2-3 — THE LOOP. done=False jab tak LLM tool maangta rahega.
    # SAFETY CAP: lab5 (agent_loop_from_scratch) jaan-bujh kar ek max-iters cap
    # sikhata hai — consistency ke liye yahan bhi wahi rakha hai. Agar model
    # baar-baar tools maangta rahe (buggy/loop-prone), to ye loop infinite na ho;
    # cap par gracefully break karke jo best content available hai wahi return karenge.
    max_iters = 10
    iters = 0
    done = False
    while not done:
        iters += 1
        if iters > max_iters:
            # Cap hit — loop ko gracefully tod do (warna theoretically forever chal sakta hai).
            print(f"[agent] max_iters ({max_iters}) hit — loop break kar rahe hain.")
            break
        # LLM ko poora context + available TOOLS bhejo.
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        # Agar LLM ne tool(s) maange (finish_reason == "tool_calls"):
        if finish_reason == "tool_calls":
            # IMPORTANT: pehle ASSISTANT ka tool-call message append karo (jisme
            # tool_calls hain), tabhi uske baad tool results valid honge.
            # GOTCHA: raw choice.message me ek 'annotations' field hota hai jise
            # Groq (aur kuch OpenAI-compat endpoints) echo-back par REJECT karte
            # hain. Isliye SIRF role/content/tool_calls ke saath saaf dict banate hain.
            msg = choice.message
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # Saare requested tools execute karo -> role="tool" results.
            tool_results = handle_tool_calls(choice.message.tool_calls)
            messages.extend(tool_results)

            # Loop wapas upar jaayega -> LLM ko ab tool result dikhega aur
            # wo ya to aur tool maangega ya final answer dega. done abhi False.
        else:
            # Normal text answer aa gaya -> loop khatam.
            done = True

    # Step 4 — final assistant text return.
    # Final turn ka content seedha return karte hain (messages me append nahi karte) — Gradio history khud sambhalta hai, isliye ise stack me dobara daalne ki zaroorat nahi.
    return choice.message.content


# ===========================================================================
# PART 4 — DEPLOYABLE CHATBOT  (gr.ChatInterface — yehi HF Spaces par jaata hai)
# ===========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(f"  LAB 4 — Career Alter-Ego Agent  ({NAME})")
    print("=" * 70)
    print(f"  Provider : groq  |  Model: {MODEL}")
    print(f"  Persona  : summary={'loaded' if not SUMMARY.startswith('[PLACEHOLDER') else 'PLACEHOLDER'}"
          f", linkedin={'loaded' if LINKEDIN else 'none'}")
    pushover_on = bool(os.getenv("PUSHOVER_TOKEN") and os.getenv("PUSHOVER_USER"))
    print(f"  Pushover : {'ON (notifications enabled)' if pushover_on else 'OFF (silent no-op)'}")
    print("-" * 70)
    print("  Tip: try puchhna jisse tool fire ho, e.g.:")
    print("    'Aapse contact kaise karu? mera email hai test@example.com'")
    print("    'Aapka favourite quantum-physics theorem kaun sa hai?' (unknown -> logged)")
    print("=" * 70)

    # gr.ChatInterface type="messages" use karta hai -> history hamare chat()
    # ke expected format me aati hai (OpenAI-style role/content dicts). Yehi
    # poora object course me HuggingFace Spaces par deploy hota hai.
    gr.ChatInterface(
        fn=chat,
        type="messages",
        title=f"Chat with {NAME} (AI alter-ego)",
        description="Mere career, skills aur experience ke baare me kuch bhi puchho!",
    ).launch()
