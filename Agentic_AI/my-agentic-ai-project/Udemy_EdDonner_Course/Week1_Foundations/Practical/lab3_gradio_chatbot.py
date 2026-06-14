"""
LAB 3 — Gradio Chatbot jo "aap jaisa baat karta hai" (Week 1 / Day 4 / Lecture L18)
====================================================================================

KYA SEEKHNA HAI (what you'll learn):
- gr.ChatInterface ke saath ek proper chat UI banana — bina khud HTML/JS likhe.
- Sabse important agentic concept: STATELESS LLM ke saath stateful conversation chalana.
  LLM ko har turn pe poori history dobara bhejni padti hai (woh kuch yaad nahi rakhta).
- gradio ki history ko OpenAI messages format [{role, content}, ...] me convert karna —
  yahi is lab ka core lesson hai (history -> messages conversion).
- System prompt se ek PERSONA set karna (bot ko "aap jaisa" banane ke liye).
- Streaming response (token-by-token) yield karke smooth UX dena.

KAISE CHALANA HAI (how to run):
    uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab3_gradio_chatbot.py

Chalate hi yeh ek LOCAL WEB UI khol dega yahan:  http://127.0.0.1:7860
Browser apne aap khul jayega (ya manually upar wala URL khol lo). Ctrl+C se band karo.

SETUP:
- .env file me GROQ_API_KEY hona chahiye (free + fast). Default provider = "groq".
- Koi extra file ki zaroorat nahi — yeh lab self-contained hai.

NOTE: Yeh gradio v6 API use karta hai — messages-style ChatInterface (type="messages"),
jisme history pehle se hi [{role, content}] dicts ki list hoti hai. Purane gradio me
history tuples (user, bot) ki list hoti thi — woh ab deprecated hai.
"""

import os

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

# .env load karo — override=True taaki shell ke purane env vars overwrite ho jayein
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# PROVIDER HELPER (har lab me inline define karte hain — shared import nahi)
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model_name) return karta hai. Groq/Gemini OpenAI-compatible hain base_url se."""
    if provider == "groq":
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
        ), "llama-3.3-70b-versatile"
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
    if provider == "gemini":
        return OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.getenv("GOOGLE_API_KEY"),
        ), "gemini-2.0-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# SYSTEM PROMPT — yahan persona define hota hai.
# YE LINE EDIT KARO: apne naam, style, profession, tone ke hisaab se badlo.
# Jitna specific likhoge, bot utna "aap jaisa" sound karega.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Ashish — a friendly, experienced Python backend developer (4+ years) "
    "who is currently learning Agentic AI. You talk in a casual, approachable way, "
    "often mixing Hindi and English (Hinglish) like a real Indian dev would. "
    "You explain technical things clearly and concisely, with a bit of warmth and humour. "
    "You are helpful, encouraging, and never condescending. "
    "Keep replies fairly short and conversational unless asked to go deep."
)


# ---------------------------------------------------------------------------
# CHAT FUNCTION — gr.ChatInterface isi function ko har user message pe call karta hai.
#
# Signature: chat(message, history)
#   message : str            -> user ne abhi jo type kiya (latest turn)
#   history : list[dict]      -> ab tak ki poori baat-cheet, gradio v6 me already
#                                [{"role": "user"/"assistant", "content": "..."}] format me
#
# CORE LESSON — history -> OpenAI messages conversion:
#   LLM stateless hai. Use yaad nahi ki pehle kya bola. Isliye HAR turn pe humein:
#     1) system prompt (persona)  -> sabse pehle
#     2) poori purani history      -> beech me
#     3) abhi wala naya message    -> sabse aakhir me
#   ek hi list me jod ke bhejna padta hai. Tabhi bot ko "context" milta hai.
#
#   Lucky baat: gradio v6 (type="messages") ki history pehle se hi OpenAI ke
#   {role, content} format me hoti hai, isliye conversion almost free hai —
#   bas system prompt aage aur naya message peeche append karna hai.
# ---------------------------------------------------------------------------
def chat(message, history):
    client, model = get_client("groq")

    # Step 1: system prompt sabse aage — bot ki personality set karta hai
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Step 2: gradio ki purani history (already {role, content} dicts) ko jod do.
    # Defensive: agar koi entry None content rakhe ya format alag ho to skip kar do.
    for turn in history:
        if isinstance(turn, dict) and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    # Step 3: abhi user ne jo bola woh sabse aakhir me
    messages.append({"role": "user", "content": message})

    # ----- LLM ko call karo (streaming = True taaki token-by-token aaye) -----
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        # gr.ChatInterface streaming ko support karta hai agar hum partial string
        # baar-baar YIELD karein. Har chunk pe accumulated reply yield karte hain —
        # UI me text smoothly type hota dikhta hai.
        reply = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            reply += delta
            yield reply
    except Exception as e:
        # Fresh setup pe (missing key / network) crash mat karo — friendly error dikhao
        yield (
            f"Arre, LLM call fail ho gaya: {e}\n\n"
            "Check karo ki .env me GROQ_API_KEY set hai aur internet chal raha hai."
        )


# ---------------------------------------------------------------------------
# MAIN — yahan Gradio chat UI launch hota hai
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("LAB 3 — Gradio Chatbot jo 'aap jaisa' baat karta hai (persona-driven)")
    print("=" * 70)
    print("Local web UI khul raha hai... agar browser auto na khule to manually kholo:")
    print("   ->  http://127.0.0.1:7860")
    print("Band karne ke liye terminal me Ctrl+C dabao.\n")

    # type="messages" -> modern OpenAI-style history (v6 recommended; tuples deprecated)
    demo = gr.ChatInterface(
        fn=chat,
        type="messages",
        title="Ashish-Bot (talks like you)",
        description=(
            "Persona-driven chatbot built with gr.ChatInterface. "
            "System prompt edit karke ise apne jaisa banao. Powered by Groq (free)."
        ),
        examples=[
            "Hello! Tum kaun ho?",
            "Agentic AI seekhne ke liye kahaan se shuru karoon?",
            "Mujhe ek FastAPI background task ka quick example do.",
        ],
    )

    # launch() blocking server start karta hai. inbrowser=True -> browser auto-open.
    demo.launch(inbrowser=True)
