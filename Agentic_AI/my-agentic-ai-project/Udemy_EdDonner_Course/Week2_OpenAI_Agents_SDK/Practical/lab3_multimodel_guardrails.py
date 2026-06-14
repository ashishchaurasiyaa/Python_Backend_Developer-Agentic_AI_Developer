"""
Lab 3 — Multi-model + Structured Outputs + Guardrails (Week 2: L39-L41)
========================================================================

Kya seekhenge:
  1. MULTI-MODEL (L39): OpenAI Agents SDK ka sabse bada flex — `Agent` class same rehti hai,
     sirf `model=` swap karo. Groq (llama) aur Gemini dono OpenAI-compatible endpoints dete
     hain, to ek hi `OpenAIChatCompletionsModel` wrapper se dono chal jaate hain.
  2. STRUCTURED OUTPUT (L40): `output_type=PydanticModel` dene se LLM ka jawab free-text nahi,
     ek TYPED Python object banta hai — downstream code me `result.final_output.field` use karo,
     string-parsing ka jugaad khatam.
  3. INPUT GUARDRAILS (L40-L41): production safety rails. Week 1 (L10) me dekha tha ki LLMs
     unpredictable hote hain — guardrail uska jawab hai. User input pehle ek chhote
     guardrail-agent se check hota hai; agar policy violate hui to TRIPWIRE trigger hota hai
     aur main (mehenga/powerful) agent chalta hi nahi — `InputGuardrailTripwireTriggered`
     exception milti hai jise hum catch karte hain.

Kaise chalana hai:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab3_multimodel_guardrails.py

Lectures: L39 (multi-model), L40 (structured outputs + guardrails intro), L41 (guardrail demo).
"""

import os
import json
import asyncio

from dotenv import load_dotenv
from pydantic import BaseModel
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
    input_guardrail,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
)

load_dotenv(override=True)

# Tracing by default OpenAI platform pe jaata hai; hamare paas valid OPENAI_API_KEY nahi hai,
# isliye tracing OFF — warna har run pe 401 warnings aayengi.
set_tracing_disabled(True)

GROQ_MODEL = "llama-3.3-70b-versatile"        # free, tool-calling supported
GROQ_STRUCTURED_FALLBACK = "openai/gpt-oss-120b"  # Groq par json_schema support karta hai (par flaky)
# NOTE: gemini-2.0-flash par is key ki free-tier quota 0 nikli (429 RESOURCE_EXHAUSTED),
# isliye gemini-2.5-flash use kar rahe hain — yeh chal raha hai aur json_schema bhi support karta hai.
GEMINI_MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# MODEL FACTORIES — yahi L39 ka core idea hai:
# Agent code ek hi hai, sirf yeh "model adapter" badalta hai. Koi bhi provider jo
# OpenAI-compatible /chat/completions endpoint deta hai, wo SDK me plug ho jaata hai.
# ---------------------------------------------------------------------------
def groq_model(model_name: str = GROQ_MODEL) -> OpenAIChatCompletionsModel:
    """Groq ka OpenAI-compatible endpoint -> SDK ka model object."""
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def gemini_model(model_name: str = GEMINI_MODEL) -> OpenAIChatCompletionsModel:
    """Google Gemini bhi OpenAI-compat endpoint deta hai — same wrapper, alag base_url/key."""
    client = AsyncOpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GOOGLE_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


# ===========================================================================
# PART 1 — MULTI-MODEL (L39)
# Ek hi prompt, do alag providers — outputs side-by-side compare karo.
# Real projects me yahi pattern hai: sasta/fast model drafts ke liye,
# strong model final judgement ke liye.
# ===========================================================================
async def part1_multi_model():
    print("=" * 70)
    print("PART 1 — MULTI-MODEL: same Agent, do alag providers (L39)")
    print("=" * 70)

    prompt = "In exactly 2 short sentences: why do AI agents need tools?"

    # (label, model) pairs — Gemini tabhi add karo jab key available ho.
    candidates = [("Groq / llama-3.3-70b", groq_model())]
    if os.getenv("GOOGLE_API_KEY"):
        candidates.append((f"Gemini / {GEMINI_MODEL}", gemini_model()))
    else:
        print("[skip] GOOGLE_API_KEY missing — sirf Groq se chala rahe hain.\n")

    for label, model in candidates:
        # Dekho: Agent definition bilkul same hai — sirf model= alag. Yahi multi-model magic hai.
        agent = Agent(
            name="Explainer",
            instructions="You are a concise technical explainer. Answer in plain English.",
            model=model,
        )
        try:
            result = await Runner.run(agent, prompt)
            print(f"--- {label} ---")
            print(result.final_output.strip())
            print()
        except Exception as e:
            # Provider down / key invalid ho to lab crash nahi hona chahiye — graceful skip.
            print(f"--- {label} --- ERROR ({type(e).__name__}): {e}\n")


# ===========================================================================
# PART 2 — STRUCTURED OUTPUT (L40)
# ===========================================================================
class NameCheckOutput(BaseModel):
    """Guardrail-agent ka TYPED jawab — free text nahi, bharosemand schema.
    Yahi class Part 3 ke guardrail me bhi reuse hogi."""
    is_name_in_message: bool   # kya message me kisi ka personal name hai?
    name: str                  # agar hai to kaunsa (warna empty string)


# FALLBACK CHAIN (verified run me yahi dekha):
#   (a) Groq llama-3.3        -> json_schema SUPPORT HI NAHI karta (400: "does not support json_schema")
#   (b) Groq gpt-oss-120b     -> json_schema leta hai par FLAKY hai (kabhi 'json_validate_failed' deta hai)
#   (c) Gemini 2.5 Flash      -> json_schema reliably chalta hai (OpenAI-compat endpoint se)
#   (d) LAST RESORT: output_type hata ke prompt me "respond ONLY with JSON" + manual json.loads
#       (yeh plain llama-3.3 par chalta hai, isliye Groq-only setup me bhi lab nahi tootega)
# Jo pehla candidate chal jaaye, use CACHE kar lete hain taaki har call pe failed providers
# pe time/rate-limit na jale.
STRUCTURED_CANDIDATES = [
    ("Groq / llama-3.3-70b", lambda: groq_model()),
    ("Groq / gpt-oss-120b", lambda: groq_model(GROQ_STRUCTURED_FALLBACK)),
    (f"Gemini / {GEMINI_MODEL}", lambda: gemini_model()),
]
_working_structured_idx: int | None = None  # pehli successful provider ka index (cache)


async def _run_structured_manual_json(name: str, instructions: str, output_type, prompt: str):
    """Fallback (d): koi provider json_schema nahi de raha to LLM se raw JSON mangwao
    aur khud parse karke pydantic me validate karo — old-school but bulletproof."""
    schema_hint = json.dumps(
        {k: str(v.annotation.__name__) for k, v in output_type.model_fields.items()}
    )
    agent = Agent(
        name=name,
        instructions=(
            instructions
            + f"\nRespond ONLY with a raw JSON object (no markdown, no extra text) "
              f"with exactly these fields/types: {schema_hint}"
        ),
        model=groq_model(),  # plain text mode — llama-3.3 yahan bilkul theek chalta hai
    )
    result = await Runner.run(agent, prompt)
    raw = result.final_output.strip()
    # LLM kabhi-kabhi ```json fences laga deta hai — unhe saaf karo.
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    # json.loads + pydantic validate = wahi type-safety jo output_type deta, bas haath se.
    parsed = output_type.model_validate(json.loads(raw))
    return parsed, result


async def run_structured(name: str, instructions: str, output_type, prompt: str):
    """Structured-output agent ko fallback chain ke saath chalao.
    Returns: (typed_output, jis_provider_ne_kaam_kiya)."""
    global _working_structured_idx
    last_err = None
    # Cache hit ho to wahi provider pehle try karo, warna chain order me.
    order = ([_working_structured_idx] if _working_structured_idx is not None
             else range(len(STRUCTURED_CANDIDATES)))
    for idx in order:
        label, factory = STRUCTURED_CANDIDATES[idx]
        if "Gemini" in label and not os.getenv("GOOGLE_API_KEY"):
            continue  # key hi nahi to try karne ka matlab nahi
        try:
            agent = Agent(name=name, instructions=instructions,
                          output_type=output_type, model=factory())
            result = await Runner.run(agent, prompt)
            _working_structured_idx = idx  # yaad rakho — agli baar seedha yahi
            return result.final_output, label
        except Exception as e:
            last_err = e  # json_schema reject / rate-limit / quota — agla candidate try karo
            # Cache reset zaroori: jo provider pehle chal raha tha agar ab fail hua to uska
            # stale index hata do, warna agli call cache hit pe wahi toota provider phir try karegi.
            _working_structured_idx = None
    # Saare json_schema providers fail — manual JSON wala plan (d) chalao.
    try:
        parsed, _ = await _run_structured_manual_json(name, instructions, output_type, prompt)
        return parsed, "Groq / llama-3.3 (manual JSON fallback)"
    except Exception as e:
        raise RuntimeError(
            f"Structured output kisi bhi tarike se nahi chala. json_schema err: {last_err}; manual err: {e}"
        )


async def part2_structured_output():
    print("=" * 70)
    print("PART 2 — STRUCTURED OUTPUT: output_type=PydanticModel (L40)")
    print("=" * 70)

    message = "Please write a cold sales email addressed to Dear Alice, from our head of sales."
    out, used = await run_structured(
        name="Name Checker",
        instructions=(
            "Check if the user's message includes someone's personal name "
            "(a real person's first/last name, NOT job titles like CEO). "
            "Set is_name_in_message accordingly; put the name in 'name' (empty string if none)."
        ),
        output_type=NameCheckOutput,
        prompt=message,
    )

    # Yeh STRING nahi — pura typed Pydantic object hai. Fields directly access karo.
    print(f"[provider used: {used}]")
    print(f"Input message      : {message}")
    print(f"Typed final_output : {out!r}  (type: {type(out).__name__})")
    print(f"  .is_name_in_message = {out.is_name_in_message}")
    print(f"  .name               = {out.name!r}")
    print()


# ===========================================================================
# PART 3 — INPUT GUARDRAIL (L40-L41)
# Guardrail = production safety rail. Week 1 L10 me dekha tha ki LLM outputs
# unpredictable hote hain; input guardrail user ki request ko main agent tak
# pahunchne se PEHLE ek sasta checker-agent se validate karta hai.
# Tripwire trigger hua -> main agent kabhi run hi nahi hota (paisa + risk dono bacha).
# ===========================================================================
@input_guardrail
async def personal_name_guardrail(
    ctx: RunContextWrapper, agent: Agent, message
) -> GuardrailFunctionOutput:
    """Guardrail function = ek MINI AGENT jo user input ko judge karta hai.
    Yahan check: kya user kisi ka personal name use karwa raha hai? (privacy policy demo)"""
    check, _used = await run_structured(
        name="Name Check Guardrail",
        instructions=(
            "Check if the user's message includes someone's personal name "
            "(a real person's first/last name, NOT job titles like CEO or Manager). "
            "Set is_name_in_message accordingly; put the name in 'name' (empty if none)."
        ),
        output_type=NameCheckOutput,
        prompt=str(message),
    )
    return GuardrailFunctionOutput(
        # output_info = debugging/audit ke liye — trace me dikhta hai ki guardrail ne kya socha.
        output_info={"found_name": check.name if check.is_name_in_message else None},
        # tripwire_triggered=True -> SDK turant InputGuardrailTripwireTriggered raise karega.
        tripwire_triggered=check.is_name_in_message,
    )


async def part3_guardrail_demo():
    print("=" * 70)
    print("PART 3 — INPUT GUARDRAIL: tripwire in action (L40-L41)")
    print("=" * 70)

    # Protected agent: company policy = emails me personal names allowed nahi.
    # input_guardrails list me guardrail attach — har user input pehle wahan se guzrega.
    protected_agent = Agent(
        name="Sales Manager",
        instructions=(
            "You write one short, professional cold sales email (3-4 lines) "
            "based on the user's request."
        ),
        model=groq_model(),
        input_guardrails=[personal_name_guardrail],
    )

    # CASE A — normal request (koi personal name nahi) -> guardrail PASS, agent chalega.
    safe_request = "Write a cold sales email addressed to 'Dear CEO' about our AI consulting services."
    print(f"\nCASE A (safe input): {safe_request}")
    try:
        result = await Runner.run(protected_agent, safe_request)
        print("[guardrail PASS] Agent ka output:")
        print(result.final_output.strip()[:400])
    except InputGuardrailTripwireTriggered:
        # Is case me ideally yahan nahi aana chahiye — par LLM judge hai, 100% guarantee nahi.
        print("[unexpected] Guardrail ne safe request ko bhi rok diya (LLM judge strict nikla).")

    # CASE B — personal name wali request -> tripwire TRIGGER, main agent run hi nahi hoga.
    risky_request = "Write a cold sales email addressed to 'Dear Alice' from Bob, head of business development."
    print(f"\nCASE B (risky input): {risky_request}")
    try:
        result = await Runner.run(protected_agent, risky_request)
        print("[unexpected] Guardrail pass ho gaya:", str(result.final_output)[:200])
    except InputGuardrailTripwireTriggered as e:
        # Yahi expected hai: exception = tripwire. Production me yahan user ko polite
        # rejection bhejte ho aur incident log karte ho.
        print("[guardrail TRIPPED] Guardrail ne rok diya! Personal name detect hua,")
        print("  isliye main Sales Manager agent RUN HI NAHI hua — na token kharch, na policy breach.")
        info = e.guardrail_result.output.output_info
        print(f"  Guardrail ka audit info: {info}")
    print()


# ===========================================================================
# MAIN
# ===========================================================================
async def main():
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY .env me nahi mila — lab chalane ke liye key zaroori hai. Exiting gracefully.")
        return
    await part1_multi_model()
    await part2_structured_output()
    await part3_guardrail_demo()
    print("Lab 3 done — multi-model swap, typed outputs, aur guardrail tripwire teeno dekh liye.")


if __name__ == "__main__":
    asyncio.run(main())
