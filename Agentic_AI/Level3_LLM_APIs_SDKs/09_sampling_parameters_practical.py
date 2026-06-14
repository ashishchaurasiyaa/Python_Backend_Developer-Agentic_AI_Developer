"""
Level 3.9 — Sampling Parameters Deep Dive (Practical)
======================================================

KYA SEEKHENGE (What We Will Learn):
  1. Temperature — randomness control: 0 (deterministic) se 1.5+ (wild) tak
  2. Top-P (Nucleus Sampling) — probability mass truncation
  3. Top-K — top-K tokens tak hi sample karo
  4. Frequency & Presence Penalty — repetition band karo
  5. max_tokens — output cap, cost control
  6. Stop Sequences — generation rokne ke strings
  7. Seed — reproducibility (same input → same output mostly)
  8. Logit Bias — specific tokens ko boost/suppress karo
  9. Per-task Parameter Recipes — task ke hisaab se best params
 10. A/B Testing Parameters — different configs compare karo
 11. Provider Differences — OpenAI vs Anthropic vs Cohere

KAISE CHALANA (How to Run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level3_LLM_APIs_SDKs/09_sampling_parameters_practical.py

  # Live API ke saath (Groq free tier):
  GROQ_API_KEY=gsk_... uv run --project /path/to/my-agentic-ai-project \\
      python 09_sampling_parameters_practical.py

THEORY LINK: 09_sampling_parameters.md
"""

import math
import os
import time
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# CLIENT SETUP — Groq free tier default, graceful degradation bina key ke
# ─────────────────────────────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or "placeholder"

# Live mode tab hi hoga jab real key mile (placeholder se crash avoid karo)
LIVE_MODE = GROQ_API_KEY != "placeholder"


def get_client():
    """
    Groq ka free OpenAI-compatible client return karo.
    Key nahi hai toh None return karo — caller gracefully skip karega.

    Theory connection:
      - Sampling params (temperature, top_p, etc.) provider-specific hain
      - Groq Llama/Mixtral serve karta hai OpenAI-compatible API se
    """
    if not LIVE_MODE:
        return None
    try:
        from openai import OpenAI  # openai package, Groq base_url se
        return OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    except ImportError:
        return None


# Default model for Groq (fast + free tier mein available)
GROQ_MODEL = "llama-3.1-8b-instant"

# ─────────────────────────────────────────────────────────────────────────────
# HELPER: LLM call with graceful fallback
# ─────────────────────────────────────────────────────────────────────────────

def llm_call(
    prompt: str,
    fake_response: str,
    **sampling_params: Any,
) -> dict:
    """
    LLM call karo — key nahi hai toh fake_response return karo.

    Returns dict with keys: content, finish_reason, mock (bool)
    """
    client = get_client()
    if client is None:
        # No key — graceful degradation: fake data dikhao
        return {
            "content": fake_response,
            "finish_reason": "stop",
            "mock": True,
        }
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            **sampling_params,
        )
        return {
            "content": resp.choices[0].message.content or "",
            "finish_reason": resp.choices[0].finish_reason,
            "mock": False,
        }
    except Exception as exc:
        # API error pe bhi gracefully degrade karo
        return {
            "content": fake_response,
            "finish_reason": "error",
            "mock": True,
            "error": str(exc),
        }


def section(title: str):
    """Section header print karo."""
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def show_result(label: str, result: dict, max_chars: int = 120):
    """Result neatly dikhao with mock indicator."""
    tag = "[MOCK]" if result.get("mock") else "[LIVE]"
    content = result["content"][:max_chars]
    if len(result["content"]) > max_chars:
        content += "..."
    print(f"  {tag} {label}: {content!r}")
    finish = result.get("finish_reason", "")
    if finish == "length":
        print("  *** max_tokens hit — output truncated! ***")


# ─────────────────────────────────────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("  SAMPLING PARAMETERS — Level 3.9 Practical")
print("=" * 65)

mode_label = "LIVE (Groq)" if LIVE_MODE else "OFFLINE MOCK"
print(f"\n  Mode: {mode_label}")
if not LIVE_MODE:
    print("  Key nahi mili — GROQ_API_KEY set karo live calls ke liye.")
    print("  Abhi fake data dikhayenge, lekin sab concepts clear honge.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: TEMPERATURE — Randomness Control
# Theory: softmax(logits / temperature) → probability distribution
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 1: TEMPERATURE — Randomness ka Master Control")

# Temperature ka mathematical effect samjhao
print("""
  Theory:
    Raw logits → softmax(logits / temperature) → probability distribution

    temperature → 0   : Distribution ek token pe spike → deterministic
    temperature = 1   : Model ki original distribution → balanced
    temperature → inf : Uniform distribution → random gibberish

  Practical values:
    0.0  → Classification, code extraction
    0.2  → Factual Q&A, summarization
    0.5  → Conversational
    0.7  → Creative writing (default)
    1.0  → Brainstorming
    1.5+ → Exploration (rarely useful, mostly wild)
""")

TEMP_EXPERIMENTS = [
    # (temperature, task_label, prompt, fake_response)
    (
        0.0,
        "Classification (temp=0, deterministic)",
        "Classify sentiment: 'I love this product!' Answer with exactly: POSITIVE, NEGATIVE, or NEUTRAL",
        "POSITIVE",
    ),
    (
        0.2,
        "Code generation (temp=0.2)",
        "Write a Python one-liner to reverse a string. Only code, no explanation.",
        "s[::-1]",
    ),
    (
        0.7,
        "Creative tagline (temp=0.7)",
        "Write ONE creative tagline for a coffee brand. One sentence only.",
        "Brew your boldest morning yet.",
    ),
    (
        1.2,
        "Brainstorming (temp=1.2)",
        "Give ONE unusual, creative name for a productivity app. Just the name.",
        "FocusForge",
    ),
]

print("  Temperature experiments chala rahe hain:")
for temp, label, prompt, fake in TEMP_EXPERIMENTS:
    result = llm_call(
        prompt,
        fake,
        temperature=temp,
        max_tokens=60,
    )
    show_result(f"temp={temp} | {label}", result)

# Interview-critical insight
print("""
  INTERVIEW INSIGHT:
    - temp=0 pe same input → same output (mostly deterministic)
    - temp=0 ke bina seed lagao toh bhi variation aa sakti hai
    - Code generation mein temp=0.2 best hai — structured output chahiye
    - Classification mein ALWAYS temp=0 use karo consistency ke liye
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: TOP-P (NUCLEUS SAMPLING)
# Theory: tokens ko prob high→low sort karo, cumulative sum >= top_p tak hi lo
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 2: TOP-P — Nucleus Sampling")

print("""
  Theory:
    1. Tokens ko probability high → low sort karo
    2. Cumulative sum chalao jab tak >= top_p
    3. Usi "nucleus" se sample karo

    top_p = 0.1  → Only the most likely tokens (very focused)
    top_p = 0.5  → Half the probability mass
    top_p = 0.9  → Default, sensible for most tasks
    top_p = 1.0  → No filtering (consider all tokens)

  Temperature vs Top-P:
    temperature  → reshapes distribution (steeper/flatter)
    top_p        → truncates distribution (tail cut karta hai)

  GOLDEN RULE: EK TIME PE EK HI TUNE KARO.
    OK:  temp=0.7 + top_p=0.9 (creative default)
    BAD: temp=1.5 + top_p=0.99 (chaos mode)
""")

TOP_P_EXPERIMENTS = [
    (0.1, "top_p=0.1 (very focused)"),
    (0.9, "top_p=0.9 (default nucleus)"),
    (1.0, "top_p=1.0 (no filtering)"),
]

CREATIVE_PROMPT = "Complete this sentence creatively: 'The stars tonight are like...'"
FAKE_CREATIVE = [
    "scattered diamonds on velvet.",
    "old friends gathering for reunion.",
    "pixels of a cosmic screensaver blinking softly.",
]

print("  Top-P experiments (temp=0.7 fixed, top_p vary karo):")
for i, (top_p, label) in enumerate(TOP_P_EXPERIMENTS):
    result = llm_call(
        CREATIVE_PROMPT,
        FAKE_CREATIVE[i],
        temperature=0.7,
        top_p=top_p,
        max_tokens=40,
    )
    show_result(label, result)

print("""
  INTERVIEW: top_p=0.9 aur temperature=0.7 saath mein use karna safe default hai.
    Dono ko extreme karna (1.5 + 1.0) → incoherent output.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: FREQUENCY & PRESENCE PENALTY — Anti-Repetition
# Theory: logit adjustment karo repetition rok ne ke liye
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 3: FREQUENCY & PRESENCE PENALTY — Repetition Band Karo")

print("""
  Theory (math):
    frequency_penalty:
      new_logit[i] -= freq_pen * count(token_i_already_in_output)
      "Jitna zyada bola, utna zyada penalty" → stop saying the same word

    presence_penalty:
      new_logit[i] -= pres_pen * (1 if token_i_in_output else 0)
      "Ek baar bhi bola toh penalty" → encourage new topics

  Per-task guide:
    General chat        → freq=0.0, pres=0.0
    Code generation     → freq=0.0, pres=0.0  (repetition is OK in code)
    Creative writing    → freq=0.3-0.5, pres=0.3
    Summarization       → freq=0.5-1.0, pres=0.0
    Brainstorming       → freq=0.3, pres=0.6  (diverse ideas chahiye)
    Avoiding filler     → freq=0.5, pres=0.5

  PITFALL: freq_penalty > 1.0 → output weird/random ho sakta hai
    SAFE ZONE: 0.0 to 0.5
""")

PENALTY_DEMOS = [
    (
        "No penalty (default)",
        {"frequency_penalty": 0.0, "presence_penalty": 0.0},
        "The cat sat on the mat. The cat was a happy cat. The cat liked sitting.",
    ),
    (
        "Creative writing (freq=0.4, pres=0.3)",
        {"frequency_penalty": 0.4, "presence_penalty": 0.3},
        "The feline perched elegantly, whiskers twitching with quiet satisfaction.",
    ),
    (
        "Brainstorm (freq=0.3, pres=0.6)",
        {"frequency_penalty": 0.3, "presence_penalty": 0.6},
        "Consider hedgehogs, blockchain calendars, edible notebooks, ambient sound maps.",
    ),
]

PENALTY_PROMPT = "Describe a small animal in two short sentences."

print("  Penalty experiments:")
for label, params, fake in PENALTY_DEMOS:
    result = llm_call(
        PENALTY_PROMPT,
        fake,
        temperature=0.7,
        max_tokens=60,
        **params,
    )
    show_result(label, result)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: MAX_TOKENS — Hard Output Cap
# Theory: output tokens pe cost control aur latency control
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 4: MAX_TOKENS — Output Cap & Cost Control")

print("""
  Theory:
    - Output tokens ka cost input se 2-3x zyada hota hai
    - max_tokens set nahi kiya → model 4000 tokens tak chala sakta hai → $$$
    - finish_reason == "length" → output cut ho gaya, max_tokens badha

  Typical values:
    Quick answer    → max_tokens=50-150
    Paragraph       → max_tokens=300-500
    Article         → max_tokens=1500-2000
    Long-form       → max_tokens=3000-4000

  ALWAYS CAP. Cost runs away otherwise.
""")

print("  Max tokens experiments:")

# Short cap demo
result_short = llm_call(
    "Tell me about machine learning in detail.",
    "[ML is a subset of AI that enables systems to learn from data automatically]",
    temperature=0.3,
    max_tokens=20,  # intentionally very short to trigger "length"
)
show_result("max_tokens=20 (too short)", result_short)
if result_short.get("finish_reason") == "length" or result_short.get("mock"):
    print("  NOTE: finish_reason='length' → output truncated, max_tokens badhao!")

# Appropriate cap
result_ok = llm_call(
    "What is machine learning? One sentence.",
    "Machine learning is a subset of AI that trains models on data to make predictions.",
    temperature=0.2,
    max_tokens=80,
)
show_result("max_tokens=80 (appropriate)", result_ok)

# Offline: finish_reason explain karo
print("""
  How to check truncation:
    if response.choices[0].finish_reason == "length":
        print("Truncated! Increase max_tokens")
    elif response.choices[0].finish_reason == "stop":
        print("Complete response milaa")
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: STOP SEQUENCES — Generation Rok Do
# Theory: jab model ye string emit kare, generation rok do
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 5: STOP SEQUENCES — Generation Rok Do")

print("""
  Theory:
    stop=["Q:", "\\n4."]  →  in strings pe generation ruk jaata hai
    String output mein shamil NAHI hoti (excluded from output)

  Use cases:
    Few-shot prompts     → stop=["Q:", "Question:"]
    JSON generation      → stop=["\\n}"] — closing brace ke baad rok do
    Numbered lists       → stop=["\\n4."] — 3 items ke baad rok do
    Code blocks          → stop=["```"] — code block end pe rok do
    Custom markers       → stop=["END_OF_RESPONSE"]
""")

STOP_EXAMPLES = [
    (
        "Numbered list with stop (stops at 4th item)",
        "List 3 benefits of exercise:\n1.",
        ["\n4."],  # 3 items ke baad rok do
        "1. Improves cardiovascular health\n2. Boosts mental wellbeing\n3. Increases strength",
    ),
    (
        "Few-shot stop (Q: pe rokna)",
        "Q: What is 2+2?\nA: 4\nQ: What is 3+3?\nA:",
        ["Q:"],  # next question pe rok do
        " 6",
    ),
]

for label, prompt, stop_seqs, fake in STOP_EXAMPLES:
    result = llm_call(
        prompt,
        fake,
        temperature=0.0,
        max_tokens=150,
        stop=stop_seqs,
    )
    show_result(f"Stop {stop_seqs} | {label}", result)

print("""
  PITFALL: Stop sequence bhool gaye → model "Item 4:", "Item 5:..." add kar deta hai
    numbered list ke liye always stop=["\\n4."] ya "\\n{n+1}." set karo
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: SEED — Reproducibility
# Theory: same seed + temp=0 = max reproducibility
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 6: SEED — Reproducibility ke Liye")

print("""
  Theory:
    seed=42 + temperature=0 → same input pe same output (mostly)

    Caveats:
      - 100% reproducible NAHI across model versions
      - Provider-specific: OpenAI support karta hai, Anthropic nahi
      - Tests aur debugging ke liye useful, legal proof ke liye nahi

  Best practice:
    - seed + temperature=0 = maximum reproducibility
    - Model version pin karo (e.g., gpt-4o-mini-2024-07-18)
    - Params record karo: model, seed, temperature, timestamp

  Provider support matrix:
    OpenAI     → seed SUPPORTED
    Anthropic  → seed NOT SUPPORTED (use temp=0 only)
    Groq       → seed SUPPORTED (varies by model)
    Cohere     → seed SUPPORTED
""")

SEED_PROMPT = "Give me a random number between 1 and 100. Just the number."

print("  Seed experiments (same seed = same result dono baar):")

result_seed_1 = llm_call(
    SEED_PROMPT,
    "42",
    temperature=0,
    seed=123,
    max_tokens=10,
)
result_seed_2 = llm_call(
    SEED_PROMPT,
    "42",
    temperature=0,
    seed=123,
    max_tokens=10,
)

show_result("seed=123, run 1", result_seed_1)
show_result("seed=123, run 2", result_seed_2)

if not result_seed_1["mock"] and not result_seed_2["mock"]:
    match = result_seed_1["content"].strip() == result_seed_2["content"].strip()
    print(f"  Results match: {match} (seed + temp=0 with same input)")
else:
    print("  [MOCK] Live mode mein same seed → same output milta hai (usually)")

print("""
  INTERVIEW ANSWER to Q4:
    "How do you ensure reproducible LLM outputs?"
    → temperature=0 + seed=N + model version pin karo
    → Still not 100% reproducible across releases
    → Params + output log karo for audit trail
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: LOGIT BIAS — Token Steering
# Theory: specific token IDs ke logits ko adjust karo
# NOTE: tiktoken optional hai, isey demo karte hain bina heavy import ke
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 7: LOGIT BIAS — Token Steering (Offline Demo)")

print("""
  Theory:
    logit_bias = {token_id: bias_value}

    bias = +5   → token ko zyada likely banao
    bias = +100 → force (practically guarantees the token)
    bias = -5   → token ko unlikely banao
    bias = -100 → suppress (practically bans the token)

  Up to ~300 tokens biased per request.

  MAIN USE CASES:
    1. Yes/No classifier → bias " yes" aur " no" token IDs ko +5
    2. Suppress filler   → bias "I'm an AI" tokens ko -100
    3. Force format      → JSON keys force karna (rare, JSON mode now better)

  HOW TO GET TOKEN IDs (tiktoken required, OpenAI models):
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    yes_tokens = enc.encode(" yes")   # leading space important hai
    no_tokens  = enc.encode(" no")
    bias = {t: 5 for t in yes_tokens + no_tokens}

  NOTE: Groq/Llama models ke liye logit_bias support limited hai.
    Modern approach: temp=0 + clear prompt "Answer only yes or no" + max_tokens=1
""")

# Demonstrate concept without tiktoken import (avoid heavy optional dep)
print("  Logit bias concept demo (token IDs sirf illustrative hain):")

MOCK_LOGIT_BIAS_CALL = """
  # Example code (OpenAI ke saath):
  import tiktoken
  enc = tiktoken.encoding_for_model("gpt-4o-mini")
  yes_tokens = enc.encode(" yes")   # e.g., [3763]
  no_tokens  = enc.encode(" no")    # e.g., [645]
  bias = {t: 5 for t in yes_tokens + no_tokens}

  response = client.chat.completions.create(
      model       = "gpt-4o-mini",
      messages    = [{"role": "user", "content": "Is this spam? 'Win free iPhone!!'"}],
      logit_bias  = bias,
      max_tokens  = 1,
      temperature = 0,
  )
  # Output: "yes" ya "no" only — constrained output
"""
print(MOCK_LOGIT_BIAS_CALL)

# Try tiktoken lazily if available
try:
    import tiktoken  # lazy import — heavy optional
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    yes_ids = enc.encode(" yes")
    no_ids = enc.encode(" no")
    bias_dict = {t: 5 for t in yes_ids + no_ids}
    print(f"  tiktoken available! yes tokens: {yes_ids}, no tokens: {no_ids}")
    print(f"  logit_bias dict: {bias_dict}")
except ImportError:
    print("  tiktoken not installed — pip install tiktoken for token ID lookup")
    print("  (Skipping live logit_bias demo — concept upar explain hua hai)")

# Modern alternative (no tiktoken needed)
result_modern = llm_call(
    "Is this spam? 'Congratulations! You won $1,000,000!! Click now!!' Answer with only 'yes' or 'no'.",
    "yes",
    temperature=0,
    max_tokens=3,
)
show_result(
    "Modern approach: clear prompt + temp=0 + max_tokens=3",
    result_modern,
)
print("  INTERVIEW: Modern models ke saath logit_bias ki zaroorat kam hai.")
print("    temp=0 + clear prompt 'only yes/no' + max_tokens=1 mostly kaam karta hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: PER-TASK PARAMETER RECIPES
# Theory: har task type ka ek best param set hota hai — centralize karo
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 8: PER-TASK PARAMETER RECIPES — Task ke Hisaab se Params")

print("""
  Theory: "Centralize parameter sets per task type" — Senior Mantra #7

  Galat params → galat output:
    Code gen with temp=1.5 → garbage code
    Classification with temp=0.7 → inconsistent labels
    JSON generation without stop → runs forever, $$$

  RECIPE TABLE:
    Task             temp   top_p  freq_pen  pres_pen  max_tokens  stop
    ───────────────────────────────────────────────────────────────────
    Classification   0.0    1.0    0.0       0.0       10          -
    Code gen         0.2    1.0    0.0       0.0       2000        ['```']
    Q&A              0.2    0.9    0.0       0.0       500         -
    Chat             0.7    0.9    0.2       0.1       500         -
    Creative         0.9    0.95   0.4       0.4       800         -
    Summarization    0.3    1.0    0.5       0.0       500         -
    Brainstorming    1.0    0.95   0.3       0.6       400         -
    RAG answer       0.1    1.0    0.0       0.0       800         ['\\nQ:']
""")

# Centralized recipe dicts — ye production mein use karo
PARAMS_CLASSIFY = {
    "temperature": 0.0,
    "max_tokens": 10,
    "top_p": 1.0,
}

PARAMS_CODE = {
    "temperature": 0.2,
    "max_tokens": 400,
    "stop": ["```"],
}

PARAMS_CHAT = {
    "temperature": 0.7,
    "top_p": 0.9,
    "frequency_penalty": 0.2,
    "presence_penalty": 0.1,
    "max_tokens": 300,
}

PARAMS_CREATIVE = {
    "temperature": 0.9,
    "top_p": 0.95,
    "frequency_penalty": 0.4,
    "presence_penalty": 0.4,
    "max_tokens": 200,
}

PARAMS_SUMMARY = {
    "temperature": 0.3,
    "frequency_penalty": 0.5,
    "max_tokens": 200,
}

PARAMS_RAG = {
    "temperature": 0.1,
    "max_tokens": 300,
    "stop": ["\nQ:", "\nQuestion:"],
}

# Demo each recipe
RECIPE_DEMOS = [
    (
        "Classification",
        PARAMS_CLASSIFY,
        "Sentiment: 'This product is amazing!' → POSITIVE, NEGATIVE, or NEUTRAL?",
        "POSITIVE",
    ),
    (
        "Creative",
        PARAMS_CREATIVE,
        "Write a one-sentence product tagline for a time-travel app.",
        "Yesterday's mistakes, tomorrow's adventures — travel time, your way.",
    ),
    (
        "Summarization",
        PARAMS_SUMMARY,
        "Summarize in one sentence: Machine learning is a subset of AI where systems learn from data to improve performance without being explicitly programmed.",
        "ML enables systems to learn from data and improve automatically without explicit programming.",
    ),
    (
        "RAG Answer",
        PARAMS_RAG,
        "Based on context: 'Python was created in 1991 by Guido van Rossum.' Q: Who created Python?\nA:",
        "Python was created by Guido van Rossum.",
    ),
]

print("  Recipe demos:")
for label, params, prompt, fake in RECIPE_DEMOS:
    result = llm_call(prompt, fake, **params)
    show_result(label, result)

print("""
  BEST PRACTICE: PARAMS_CLASSIFY, PARAMS_CODE, etc. ko ek config file mein rakh do.
    Ek hi jagah se change karo → sab calls consistent rahenge.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: A/B TESTING PARAMETERS
# Theory: multiple configs compare karo before locking them in
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 9: A/B TESTING — Best Params Dhundo")

print("""
  Theory (Senior Mantra #8): "A/B test params before locking them in."
    - Same task, multiple param configs run karo
    - Output quality compare karo (manually ya LLM-as-judge se)
    - Best config lock in karo production mein

  Classic A/B setup:
    configs = [
        {"temperature": 0.3, "top_p": 0.9},   # A: conservative
        {"temperature": 0.7, "top_p": 0.9},   # B: balanced
        {"temperature": 0.7, "top_p": 0.5},   # C: focused nucleus
        {"temperature": 1.0, "top_p": 0.95},  # D: creative
    ]
    # Same prompt, all configs → compare outputs
""")

AB_CONFIGS = [
    {"label": "A: temp=0.3 (conservative)", "temperature": 0.3, "top_p": 0.9, "max_tokens": 80},
    {"label": "B: temp=0.7 (balanced)",     "temperature": 0.7, "top_p": 0.9, "max_tokens": 80},
    {"label": "C: temp=1.0 (creative)",     "temperature": 1.0, "top_p": 0.95, "max_tokens": 80},
]

AB_FAKE_RESPONSES = [
    "Boost your workflow with smart automation.",
    "Where ideas sprint and deadlines dance.",
    "Unleash the chaos of calm productivity.",
]

AB_PROMPT = "Write a one-sentence tagline for a productivity app called 'FlowState'."

print("  A/B test — tagline generation ke liye:")
ab_results = []
for i, config in enumerate(AB_CONFIGS):
    label = config.pop("label")
    result = llm_call(AB_PROMPT, AB_FAKE_RESPONSES[i], **config)
    config["label"] = label  # restore
    ab_results.append((label, result))
    show_result(label, result)

print("""
  Production mein:
    1. Har config pe 10-20 runs karo (variance pakdne ke liye)
    2. Human eval ya LLM-as-judge se score karo
    3. Winning config centralize karo (PARAMS_CREATIVE, etc.)
    4. Log karo: model, params, scores → reproducibility ke liye
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: PROVIDER DIFFERENCES
# Theory: OpenAI vs Anthropic vs Cohere — different param support
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 10: PROVIDER DIFFERENCES — Kaun Kya Support Karta Hai")

PROVIDER_TABLE = {
    "Parameter":         ["OpenAI",   "Anthropic", "Groq/Llama", "Cohere"],
    "temperature":       ["0-2",      "0-1",       "0-2",        "0-5"],
    "top_p":             ["0-1",      "0-1",       "0-1",        "0-1"],
    "top_k":             ["NO",       "YES 0-500", "varies",     "YES"],
    "frequency_penalty": ["YES",      "NO",        "YES",        "YES"],
    "presence_penalty":  ["YES",      "NO",        "YES",        "YES"],
    "seed":              ["YES",      "NO",        "varies",     "YES"],
    "logit_bias":        ["YES",      "NO",        "NO",         "NO"],
    "logprobs":          ["YES",      "NO",        "varies",     "YES"],
    "stop":              ["YES",      "YES",       "YES",        "YES"],
    "max_tokens":        ["optional", "REQUIRED",  "optional",   "optional"],
}

print()
header = f"  {'Parameter':<22}" + "".join(f"{p:<16}" for p in PROVIDER_TABLE["Parameter"])
print(header)
print("  " + "-" * (22 + 16 * 4))
for param, values in PROVIDER_TABLE.items():
    if param == "Parameter":
        continue
    row = f"  {param:<22}" + "".join(f"{v:<16}" for v in values)
    print(row)

print("""
  KEY GOTCHAS:
    1. Anthropic: max_tokens REQUIRED hai (default nahi hai)
    2. Anthropic: frequency_penalty/presence_penalty nahi hain
    3. OpenAI: top_k nahi hai (top_p use karo instead)
    4. temperature range: OpenAI 0-2, Anthropic 0-1 (IMPORTANT for migration)

  PRODUCTION TIP:
    LiteLLM ya wrapper use karo → provider-independent params
    Warna per-provider adapter function likho.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: COMMON PITFALLS — Production Mein Kya Mat Karo
# Theory: theory doc se 8 pitfalls
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 11: COMMON PITFALLS — Galtiyan Mat Karo")

PITFALLS = [
    (
        "temp=0 ALWAYS",
        "Never explores alternatives → creative tasks boring ho jaate hain",
        "Classification/code mein 0, variety ke liye 0.5+ use karo",
    ),
    (
        "top_p + temp + top_k sab max",
        "Chaos mode → incoherent output",
        "EK TIME PE EK HI tune karo",
    ),
    (
        "frequency_penalty > 1.0",
        "Output random/weird ho jaata hai",
        "Safe zone: 0.0 to 0.5",
    ),
    (
        "max_tokens set nahi kiya",
        "Model 4000 tokens tak chala sakta hai → $$$ + slow",
        "ALWAYS cap appropriately — task ke hisaab se",
    ),
    (
        "Stop sequences bhool gaye",
        "Model 'Item 4:', 'Item 5:' add kar deta hai list ke baad",
        "Explicit stops lagao numbered lists mein",
    ),
    (
        "seed without temp=0",
        "Bhi variation aati hai — seed alone enough nahi",
        "seed + temp=0 = max reproducibility",
    ),
    (
        "Crazy logit_bias values",
        "Coherence breaks",
        "bias=5 se shuru karo, carefully tune karo",
    ),
    (
        "Same task pe different params across calls",
        "Inconsistent outputs → debugging nightmare",
        "Centralize: PARAMS_CLASSIFY, PARAMS_CREATIVE, etc.",
    ),
]

print()
for i, (pitfall, problem, fix) in enumerate(PITFALLS, 1):
    print(f"  Pitfall {i}: {pitfall}")
    print(f"    Problem: {problem}")
    print(f"    Fix:     {fix}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: INTERVIEW QUESTIONS — Rapid Fire
# Theory: theory doc ke 5 interview Q&A
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 12: INTERVIEW QUESTIONS — Rapid Fire")

IQ = [
    (
        "Q1: Temperature aur top_p mein kya difference hai?",
        "Temperature POORI distribution ko reshape karta hai (low=peaked, high=flat).\n"
        "    Top_p distribution ko TRUNCATE karta hai (sirf cumulative-p tak ke tokens consider hote hain).\n"
        "    Temperature → RANDOMNESS control; top_p → RANGE of candidates.\n"
        "    General rule: tune ONE, dusra default pe chhoddo.",
    ),
    (
        "Q2: frequency_penalty vs presence_penalty kab use karein?",
        "frequency_penalty: repetition COUNT ke saath scale karta hai.\n"
        "    'Stop saying the same word over and over.'\n"
        "    presence_penalty: ek baar appear hone ke baad constant penalty.\n"
        "    'Introduce new topics, dwell mat karo.'",
    ),
    (
        "Q3: Production classification ke best params kya hain?",
        "temperature=0, max_tokens=10, top_p=1.0.\n"
        "    Determinism > creativity for classification.\n"
        "    Optional: logit_bias to constrain to specific labels.\n"
        "    logprobs se confidence scores extract karo.",
    ),
    (
        "Q4: Reproducible LLM outputs kaise ensure karein?",
        "temperature=0 + seed=N + model version pin karo.\n"
        "    Still not 100% reproducible across model releases.\n"
        "    Audit ke liye: model name, params, aur output log karo.",
    ),
    (
        "Q5: Model ko sirf 'yes' ya 'no' output karne pe kaise force karein?",
        "(1) Clear prompt: 'Answer with only yes or no.'\n"
        "    (2) temperature=0\n"
        "    (3) max_tokens=1\n"
        "    (4) Optional: logit_bias to boost yes/no token IDs\n"
        "    Modern models ke saath (1)-(3) akele kaam karte hain.",
    ),
]

for question, answer in IQ:
    print(f"\n  {question}")
    print(f"    ANS: {answer}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13: SENIOR MANTRAS — Quick Summary
# ─────────────────────────────────────────────────────────────────────────────

section("SECTION 13: SENIOR MANTRAS — 10 Rules to Live By")

MANTRAS = [
    "Default temp=0.7, default top_p=0.9. Task ke hisaab se tune karo.",
    "ALWAYS set max_tokens. Cost runs away otherwise.",
    "temp=0 for ANYTHING requiring consistency.",
    "Temperature OR top_p tune karo — dono ko extreme mat karo.",
    "Frequency penalty fights repetition. Safe zone: 0.2-0.5.",
    "Stop sequences prevent runaway output — especially in lists/code.",
    "Centralize parameter sets per task type — ek jagah change, sab consistent.",
    "A/B test params before locking them in.",
    "logprobs → confidence scoring in classification.",
    "Pin model version + record params. Reproducibility matters.",
]

for i, mantra in enumerate(MANTRAS, 1):
    print(f"  {i:2d}. {mantra}")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("  SAMPLING PARAMETERS PRACTICAL COMPLETE!")
print("=" * 65)

print(f"""
  Kya seekha aaj:
    temperature  → randomness: 0=deterministic, 1=balanced, 1.5+=wild
    top_p        → nucleus: cumulative prob >= p tak hi tokens consider
    penalties    → freq: count-scaled, pres: binary (ek baar=penalty)
    max_tokens   → ALWAYS set karo, cost control ke liye
    stop         → generation ek specific string pe rokna
    seed         → reproducibility (temp=0 saath)
    logit_bias   → specific tokens boost/suppress karo
    recipes      → PARAMS_CLASSIFY, PARAMS_CODE, PARAMS_CHAT...
    A/B testing  → multiple configs compare karo, best lock karo
    providers    → OpenAI != Anthropic != Groq (param support alag hai)

  Mode: {mode_label}
  Real API calls ke liye: GROQ_API_KEY set karo.

  Next: 10_cost_optimization.md → max_tokens + batching + caching
""")
