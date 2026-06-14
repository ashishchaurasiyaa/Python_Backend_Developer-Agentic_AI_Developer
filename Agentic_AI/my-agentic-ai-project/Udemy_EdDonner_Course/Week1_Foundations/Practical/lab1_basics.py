"""
LAB 1 — Basics & first agentic workflow
=========================================
Lecture: Ed Donner Agentic AI course, Week 1 Day 1 (L06).

Kya seekhna hai (what we learn here):
- LLM se connectivity prove karna (ek simple call).
- AGENTIC CHAIN ka core idea: ek LLM call ka OUTPUT ko agle LLM call ka
  INPUT bana dena. Yahi "chaining" hi sabse basic agentic workflow hai —
  model khud ek question banata hai, phir hum wahi question use karke
  doosri call me answer mangte hain.
- Commercial angle (course wala exercise): 3-step business chain ->
  sector -> pain point -> agentic AI solution.

Kaise chalana hai (how to run):
    uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab1_basics.py

Setup: .env me GROQ_API_KEY hona chahiye (default provider = groq, free + fast).
OPENAI_API_KEY / GOOGLE_API_KEY optional hain (sirf provider switch ke liye).
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Yahan hum .env load karte hain. override=True => agar shell me purani value
# set hai to .env wali jeet jayegi (Ed Donner isi tarah karwata hai).
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model_name) return karta hai.
# Groq aur Gemini OpenAI-compatible hain — bas base_url alag hota hai.
# Is file ko SELF-CONTAINED rakhne ke liye get_client yahin define kiya hai.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """Return (client, model_name). Default groq => zero cost, fast."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY")), "llama-3.3-70b-versatile"
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY")), "gemini-2.0-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# ask: ek chhota helper jo ek single LLM call karta hai.
# messages = OpenAI-style list of {"role": ..., "content": ...}.
# Hum isko baar-baar reuse karenge — yahi hamara "ek LLM step" hai.
# ---------------------------------------------------------------------------
def ask(client, model, messages, temperature=0.7):
    """Ek LLM call maaro aur sirf text content wapas do."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    # .strip() taaki leading/trailing whitespace clean rahe
    return response.choices[0].message.content.strip()


# ===========================================================================
# STEP 2 — Simple call (connectivity proof)
# ===========================================================================
def step_simple_call(client, model):
    """Sabse basic call: '2+2 kitna?' — sirf yeh prove karne ke liye ki
    client/key/model sab sahi se wired hai."""
    print("=" * 70)
    print("STEP 2 — SIMPLE CALL (connectivity check)")
    print("=" * 70)

    # Single user message. Koi system prompt nahi — bilkul minimal.
    messages = [{"role": "user", "content": "What is 2+2? Reply in one short sentence."}]
    answer = ask(client, model, messages)

    print(f"Q: What is 2+2?")
    print(f"A: {answer}")
    print()


# ===========================================================================
# STEP 3 — AGENTIC CHAIN (the key lesson)
#   Call-1: LLM se ek hard IQ/brain-teaser QUESTION banwao (sirf question).
#   Call-2: wahi generated question ko naye message ke roop me feed karke
#           ANSWER mangao.
#   ==> Call-1 ka OUTPUT, Call-2 ka INPUT ban gaya = AGENTIC WORKFLOW.
# ===========================================================================
def step_agentic_chain(client, model):
    """Do calls ko chain karke dikhao ki ek model ka output doosre ka
    input kaise banta hai — yahi sabse basic 'agentic' pattern hai."""
    print("=" * 70)
    print("STEP 3 — AGENTIC CHAIN (output of call-1 -> input of call-2)")
    print("=" * 70)

    # --- CALL 1: question generate karwao -------------------------------
    # System prompt strict rakha hai: model ko sirf QUESTION dena hai,
    # answer ya extra baat nahi. Isse agla step clean rahega.
    gen_messages = [
        {"role": "system", "content": "You are a puzzle master."},
        {"role": "user", "content": (
            "Propose a single hard IQ / brain-teaser question. "
            "Respond with ONLY the question text, nothing else — "
            "no answer, no preamble, no numbering."
        )},
    ]
    generated_question = ask(client, model, gen_messages)
    print("[Call-1] LLM ne yeh question banaya:")
    print(f"    {generated_question}")
    print()

    # --- CALL 2: us hi question ka answer mangao -----------------------
    # KEY POINT: generated_question (call-1 ka OUTPUT) ko hum naye
    # user message ke andar daal rahe hain (call-2 ka INPUT).
    # Yahi 'chaining' hai — manually orchestrate ki gayi do-step pipeline.
    answer_messages = [
        {"role": "system", "content": "You are a careful problem solver. "
                                       "Explain your reasoning briefly, then give the answer."},
        {"role": "user", "content": generated_question},
    ]
    final_answer = ask(client, model, answer_messages)
    print("[Call-2] Usi question ka answer (call-1 ka output yahan input bana):")
    print(f"    {final_answer}")
    print()

    # Concept summary print — taaki lesson saaf rahe.
    print(">>> AHA MOMENT: Ek LLM ka output ko dusre LLM ka input banana = "
          "agentic workflow. Itna hi simple core idea hai.")
    print()


# ===========================================================================
# STEP 4 — EXERCISE: 3-step BUSINESS chain (commercial angle)
#   (a) LLM ek promising BUSINESS SECTOR for AI choose karta hai.
#   (b) Us sector ka ek PAIN POINT identify karta hai.
#   (c) Us pain point ke liye ek AGENTIC AI SOLUTION propose karta hai.
#   Har step ka output agle step ka context banta hai — wahi chaining.
# ===========================================================================
def pick_business_sector(client, model):
    """(a) Ek promising sector choose karwao jahan AI ka bada scope ho."""
    messages = [
        {"role": "system", "content": "You are a sharp business analyst."},
        {"role": "user", "content": (
            "Name ONE business sector that is especially promising for AI "
            "disruption right now. Respond with ONLY the sector name "
            "(2-4 words max), nothing else."
        )},
    ]
    return ask(client, model, messages)


def find_pain_point(client, model, sector):
    """(b) Diye gaye sector me ek real PAIN POINT nikalwao.
    Note: 'sector' previous step ka output hai — yahi chaining hai."""
    messages = [
        {"role": "system", "content": "You are a sharp business analyst."},
        {"role": "user", "content": (
            f"For the '{sector}' sector, identify ONE concrete, painful, "
            "costly problem that companies struggle with today. "
            "Answer in 1-2 sentences only."
        )},
    ]
    return ask(client, model, messages)


def propose_agentic_solution(client, model, sector, pain_point):
    """(c) Us pain point ke liye ek AGENTIC AI solution propose karwao.
    Yahan dono pichhle outputs (sector + pain_point) input ban rahe hain."""
    messages = [
        {"role": "system", "content": "You are an agentic AI solutions architect."},
        {"role": "user", "content": (
            f"Sector: {sector}\n"
            f"Pain point: {pain_point}\n\n"
            "Propose an Agentic AI solution (using LLM agents / tools / "
            "multi-step workflows) that solves this pain point. "
            "Describe it in 3-4 sentences and mention what the agent(s) would do."
        )},
    ]
    return ask(client, model, messages)


def step_business_exercise(client, model):
    """Teeno business steps ko chain karke pura mini-pipeline chalata hai."""
    print("=" * 70)
    print("STEP 4 — EXERCISE: 3-STEP BUSINESS CHAIN (commercial use-case)")
    print("=" * 70)

    # (a) sector -> (b) pain point -> (c) agentic solution
    sector = pick_business_sector(client, model)
    print(f"(a) Promising business sector for AI:\n    {sector}\n")

    pain_point = find_pain_point(client, model, sector)
    print(f"(b) Pain point in '{sector}':\n    {pain_point}\n")

    solution = propose_agentic_solution(client, model, sector, pain_point)
    print(f"(c) Proposed Agentic AI solution:\n    {solution}\n")

    print(">>> Notice: har function ka output agle function ka argument bana. "
          "Yeh ek deterministic, hum-control-karte-hain wala agentic chain hai.")
    print()


# ===========================================================================
# MAIN — sab kuch yahan run hota hai.
# ===========================================================================
if __name__ == "__main__":
    # Default provider = groq (free + fast). Switch karna ho to yahan
    # "openai" ya "gemini" pass kar do (corresponding key .env me honi chahiye).
    PROVIDER = "groq"

    print("\n" + "#" * 70)
    print(f"#  LAB 1 — Basics & First Agentic Workflow   (provider = {PROVIDER})")
    print("#" * 70 + "\n")

    # Client + model build karo. Agar key missing/galat hai to friendly
    # message dikhao instead of ugly crash.
    try:
        client, model = get_client(PROVIDER)
    except Exception as e:
        print(f"[SETUP ERROR] get_client fail hua: {e}")
        raise SystemExit(1)

    # Har step ko try/except me wrap kiya hai taaki ek step fail ho to
    # baaki demo bhi context ke saath samajh aaye (network/key issues ke liye).
    try:
        step_simple_call(client, model)
        step_agentic_chain(client, model)
        step_business_exercise(client, model)
    except Exception as e:
        print(f"\n[RUNTIME ERROR] Koi LLM call fail hui: {e}")
        print("Check: GROQ_API_KEY .env me set hai? Internet on hai? "
              "Model name valid hai?")
        raise SystemExit(1)

    print("#" * 70)
    print("#  LAB 1 complete. Aapne dekha: simple call -> chained call -> "
          "business chain.")
    print("#" * 70 + "\n")
