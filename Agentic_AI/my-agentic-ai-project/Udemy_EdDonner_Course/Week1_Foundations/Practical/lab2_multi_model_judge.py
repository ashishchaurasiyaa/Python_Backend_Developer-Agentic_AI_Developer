"""
=========================================================================
LAB 2 — Multi-Model Orchestration + LLM-as-Judge
Week 1 / Day 3 — Ed Donner Course (lectures L11-L14)
=========================================================================

KYA SEEKHNA HAI (what you'll learn):
  1. Ek hi OpenAI client library se ALAG-ALAG providers ko hit karna,
     sirf `base_url` aur `api_key` badal kar (Groq, Gemini, OpenAI).
  2. Ek hi sawaal multiple models ko poochhna aur saare jawaab collect karna.
  3. JUDGE PATTERN (LLM-as-judge): ek LLM ko "evaluator" bana kar
     baaki models ke jawaab rank/score karwana. Yeh orchestration ka
     dil hai — ek model doosre models ko parakhta hai (bias hatane ke
     liye answers ko ANONYMISE + NUMBER kar ke dete hain).

KAISE CHALANA HAI (how to run):
  uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab2_multi_model_judge.py

SETUP:
  .env me GROQ_API_KEY hona ZAROORI hai (yeh hamesha chalega, free hai).
  GOOGLE_API_KEY aur OPENAI_API_KEY OPTIONAL hain — agar nahi honge to
  woh provider gracefully SKIP ho jaayega (script crash nahi karega).

RELATED LECTURES: L11-L14 (multi-model calls + evaluator/judge pattern).
=========================================================================
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# override=True => .env ki values OS env ko override karengi (Ed ka standard pattern)
load_dotenv(override=True)


# -------------------------------------------------------------------------
# get_client: provider ka naam do, (client, model_name) wapas milega.
# Trick yeh hai ki Groq aur Gemini dono OpenAI-COMPATIBLE endpoints dete hain,
# isliye same OpenAI() class chalti hai — bas base_url alag hota hai.
# -------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """Return (client, model_name). Groq/Gemini are OpenAI-compatible via base_url."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY")), "llama-3.3-70b-versatile"
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "gpt-4o-mini"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY")), "gemini-2.0-flash"
    raise ValueError(f"Unknown provider: {provider}")


# -------------------------------------------------------------------------
# ask_one_provider: ek provider ko sawaal poochho aur uska jawaab text laao.
# Yahan defensive programming hai:
#   - agar provider ki API key missing hai => skip (None return)
#   - agar network/API call fail hui => skip (None return), crash NAHI.
# Yeh "graceful degradation" hai — multi-model setup me ek model down ho
# to baaki kaam karte rahein, yeh production-grade soch hai.
# -------------------------------------------------------------------------
def ask_one_provider(provider: str, question: str) -> dict | None:
    # Pehle key check karo — bina key ke client banane ka koi fayda nahi.
    key_env = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GOOGLE_API_KEY"}[provider]
    if not os.getenv(key_env):
        print(f"  [SKIP] {provider:<7} -> {key_env} .env me nahi mila.")
        return None

    try:
        client, model = get_client(provider)
        # Standard chat.completions call — har OpenAI-compatible provider yeh samajhta hai.
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system",
                 "content": "You are a thoughtful assistant. Answer in 4-6 concise sentences."},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
        )
        answer = resp.choices[0].message.content.strip()
        print(f"  [OK]   {provider:<7} -> {model} ne jawaab diya ({len(answer)} chars).")
        # Provider/model label saath rakhte hain taaki baad me trace kar sakein.
        return {"provider": provider, "model": model, "answer": answer}
    except Exception as e:
        # Koi bhi error (rate limit, bad key, network) => skip, never crash.
        print(f"  [SKIP] {provider:<7} -> call fail hui: {type(e).__name__}: {e}")
        return None


# -------------------------------------------------------------------------
# collect_answers: groq HAMESHA, gemini + openai SIRF agar key ho.
# Saare valid jawaab ek list me aate hain (label ke saath).
# -------------------------------------------------------------------------
def collect_answers(question: str) -> list[dict]:
    answers = []
    # Order maayne rakhta hai sirf readability ke liye; groq guaranteed hai.
    for provider in ["groq", "gemini", "openai"]:
        result = ask_one_provider(provider, question)
        if result is not None:
            answers.append(result)
    return answers


# -------------------------------------------------------------------------
# build_judge_prompt: judge ke liye ek single prompt banao.
# IMPORTANT — ANONYMISATION: judge ko sirf "Answer 1, Answer 2, ..." dikhte
# hain, kis provider ne likha yeh CHHUPA hota hai. Isse judge model-brand ke
# basis pe bias nahi karta (e.g. "OpenAI achha hoga" jaisa assume nahi karega).
# Hum mapping (index -> provider) alag se rakhte hain decode karne ke liye.
# -------------------------------------------------------------------------
def build_judge_prompt(question: str, answers: list[dict]) -> str:
    lines = [
        "You are an impartial judge evaluating answers from different AI models.",
        "Below is a question followed by several anonymised answers.",
        "",
        f"QUESTION:\n{question}",
        "",
        "ANSWERS:",
    ]
    # Numbered + anonymised answers — provider ka naam yahan NAHI daalte.
    for i, item in enumerate(answers, start=1):
        lines.append(f"\nAnswer {i}:\n{item['answer']}")

    lines += [
        "",
        "YOUR TASK:",
        "Rank ALL the answers from BEST to WORST.",
        "For each, give the answer number and a ONE-LINE reason.",
        "Then on the final line declare the winner like: WINNER: Answer <n>",
        "Be critical and specific about reasoning quality, clarity, and balance.",
    ]
    return "\n".join(lines)


# -------------------------------------------------------------------------
# judge_answers: judge LLM (groq) ko prompt do aur ranking text laao.
# Yahan hum ek model ko EVALUATOR bana rahe hain — yeh "LLM-as-judge"
# pattern hai jo evals, A/B testing aur self-improving agents me use hota hai.
# -------------------------------------------------------------------------
def judge_answers(question: str, answers: list[dict]) -> str:
    judge_prompt = build_judge_prompt(question, answers)
    # Judge ke liye groq (free + fast + tool-capable). Low temperature => consistent judging.
    # NOTE: yeh judge wahi groq model hai jisne Answer 1 (candidate) bhi banaya tha —
    # to thoda apne hi style ki taraf bias ho sakta hai; anonymisation + numbering
    # is bias ko partially kam kar dete hain (poora khatam nahi karte).
    client, model = get_client("groq")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system",
             "content": "You are a rigorous, unbiased evaluator of AI-generated answers."},
            {"role": "user", "content": judge_prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# -------------------------------------------------------------------------
# DEMO: poora flow chalao aur saaf-suthra output print karo.
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Ek challenging reasoning/ethics sawaal — yahan models ki soch dikhti hai.
    QUESTION = (
        "A self-driving car must choose between swerving (likely killing its single "
        "passenger) or staying course (likely killing three pedestrians who jaywalked). "
        "What should it do, and what ethical principle justifies your choice?"
    )

    print("=" * 70)
    print("LAB 2 — Multi-Model Orchestration + LLM-as-Judge")
    print("=" * 70)
    print(f"\nQUESTION:\n{QUESTION}\n")
    print("-" * 70)
    print("Step 1/3 — Har provider se jawaab maang rahe hain:\n")

    answers = collect_answers(QUESTION)

    # Edge case: agar kisi wajah se ek bhi jawaab nahi aaya (e.g. groq key galat).
    if not answers:
        print("\n[ERROR] Ek bhi provider ne jawaab nahi diya. GROQ_API_KEY check karein.")
        raise SystemExit(1)

    print("\n" + "-" * 70)
    print(f"Step 2/3 — {len(answers)} jawaab collect huye:\n")
    for i, item in enumerate(answers, start=1):
        # Yahan REAL provider naam dikhate hain (judge ko nahi, sirf humein).
        print(f"### Answer {i}  [{item['provider']} / {item['model']}]")
        print(item["answer"])
        print()

    print("-" * 70)
    print("Step 3/3 — Judge LLM (groq) saare jawaab ANONYMOUSLY rank kar raha hai:\n")

    ranking = judge_answers(QUESTION, answers)
    print(ranking)

    print("\n" + "-" * 70)
    print("DECODE MAP (judge ko yeh nahi pata tha — bias-free judging ke liye):")
    for i, item in enumerate(answers, start=1):
        print(f"  Answer {i}  =>  {item['provider']} / {item['model']}")
    print("=" * 70)
    print("Done. Notice: same OpenAI client, alag base_url => multi-provider, "
          "aur ek LLM ne baakiyon ko judge kiya.")
