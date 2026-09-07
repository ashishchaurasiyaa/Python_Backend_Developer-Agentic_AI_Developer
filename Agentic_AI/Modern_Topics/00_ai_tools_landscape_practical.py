"""
Modern Topics — Doc 0: AI Tools Landscape (PRACTICAL)
========================================================
The doc's mental model — every tool classifies by 3 questions (output type,
modality, human-driven vs agentic) — turned into an actual queryable
classifier instead of a table you re-read every time you hit a new tool name.

Topics covered:
  1. The 3-question classifier, as a real function
  2. A tool database you can query by category/tier
  3. Classifying a NEW/unfamiliar tool name using the same framework
  4. "Model vs product" distinction, made concrete

Run: python 00_ai_tools_landscape_practical.py
"""

from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The 3-Question Classifier
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: The Mental Model, as Code")
print("=" * 70)


@dataclass
class ToolProfile:
    name: str
    output: str        # text / image / video / audio / code / action
    modality: str       # single / multimodal
    driven_by: str       # human / agent
    tier: str = "free+paid"


def classify(name: str, output: str, modality: str, driven_by: str) -> ToolProfile:
    assert output in {"text", "image", "video", "audio", "code", "action", "multi-output"}
    assert modality in {"single", "multimodal"}
    assert driven_by in {"human", "agent"}
    return ToolProfile(name, output, modality, driven_by)


examples = [
    classify("Claude (claude.ai)", "text", "multimodal", "human"),
    classify("Claude Code", "code", "multimodal", "agent"),
    classify("Midjourney", "image", "single", "human"),
    classify("Devin", "code", "multimodal", "agent"),
    classify("ElevenLabs", "audio", "single", "human"),
]

print()
for e in examples:
    print(f"  {e.name:22s} -> output={e.output:10s} modality={e.modality:10s} driven_by={e.driven_by}")

print("\n  Notice: 'output' varies a lot, 'driven_by' is the axis that actually")
print("  predicts how you'd EVALUATE the tool — human-driven tools are judged on")
print("  quality-per-prompt, agent-driven ones on task-completion-rate.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: A Queryable Tool Database
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Query the Landscape Instead of Scanning a Table")
print("=" * 70)

TOOLS = {
    "Claude": {"category": "foundation_model", "company": "Anthropic", "tier": "free+paid"},
    "GPT-4o/5": {"category": "foundation_model", "company": "OpenAI", "tier": "free+paid"},
    "Gemini": {"category": "foundation_model", "company": "Google", "tier": "free+paid"},
    "Llama": {"category": "foundation_model", "company": "Meta", "tier": "open"},
    "DeepSeek": {"category": "foundation_model", "company": "DeepSeek", "tier": "free+paid"},
    "ChatGPT": {"category": "chat_assistant", "company": "OpenAI", "tier": "free+paid"},
    "Perplexity": {"category": "search_research", "company": "Perplexity", "tier": "free+paid"},
    "Claude Code": {"category": "coding_agent", "company": "Anthropic", "tier": "paid"},
    "Cursor": {"category": "coding_ide", "company": "Anysphere", "tier": "paid"},
    "Copilot": {"category": "coding_autocomplete", "company": "GitHub/Microsoft", "tier": "paid"},
    "Devin": {"category": "autonomous_swe", "company": "Cognition", "tier": "paid"},
    "Midjourney": {"category": "image_gen", "company": "Midjourney", "tier": "paid"},
}


def tools_by_category(category: str) -> list[str]:
    return [name for name, info in TOOLS.items() if info["category"] == category]


def tools_by_company(company: str) -> list[str]:
    return [name for name, info in TOOLS.items() if info["company"] == company]


print(f"\n  Coding tools: {tools_by_category('coding_agent') + tools_by_category('coding_ide') + tools_by_category('coding_autocomplete')}")
print(f"  Everything from Anthropic: {tools_by_company('Anthropic')}")
print(f"  Free/open tier: {[n for n, i in TOOLS.items() if i['tier'] == 'open']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Classify an Unfamiliar Tool Using the Same Framework
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Classify Something You've Never Heard Of")
print("=" * 70)

print("""
  The whole point of the mental model: you don't need to memorize every new
  tool that launches. Given ANY new AI product announcement, ask:
    1. What does it OUTPUT?
    2. Is it single-modality or multimodal?
    3. Does a human drive it turn-by-turn, or does it act autonomously?
""")


def explain_new_tool(name: str, description: str, output: str, modality: str, driven_by: str) -> str:
    profile = classify(name, output, modality, driven_by)
    verdict = f"'{name}' is a {profile.modality} {profile.output}-output tool, {profile.driven_by}-driven"
    if driven_by == "agent":
        verdict += " — evaluate it on task-completion rate and failure recovery, not just output quality per turn."
    else:
        verdict += " — evaluate it on output quality and how much you have to steer it per prompt."
    return verdict


# Simulating "a brand new tool announced tomorrow" — same 3 questions apply
print(f"  {explain_new_tool('HypotheticalTool', 'auto-generates a slide deck from a prompt', 'multi-output', 'multimodal', 'agent')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: "Model" vs "Product" — Made Concrete
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Model vs Product (interview-common confusion)")
print("=" * 70)

MODEL_TO_PRODUCTS = {
    "Claude (model)": ["claude.ai (chat product)", "Claude Code (CLI agent product)", "Claude API (raw model access)"],
    "GPT (model)": ["ChatGPT (chat product)", "GitHub Copilot (autocomplete product, uses GPT/Codex)", "OpenAI API (raw model access)"],
    "Gemini (model)": ["Gemini app (chat product)", "Google integration in Docs/Gmail", "Vertex AI (enterprise API access)"],
}

print()
for model, products in MODEL_TO_PRODUCTS.items():
    print(f"  {model}")
    for p in products:
        print(f"    -> {p}")

print("\n  Same 'engine', different 'cars' — this is exactly why 'which AI is best'")
print("  is an underspecified question. The right question is 'best model for")
print("  which use case, wrapped in which product.'")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add 5 more tools you personally use to TOOLS, classified by category.

MEDIUM:
2. Extend classify() to also track a 4th axis: "cost_model" (subscription /
   per-token API / one-time). Classify 5 tools by all 4 axes.

HARD:
3. Pick a real AI product launch from the last month. Apply explain_new_tool()
   to it — does the 3-question framework actually help you place it quickly?

PRO:
4. Build a recommend_tool(task_description) function that uses TOOLS +
   tools_by_category() to suggest 2-3 candidates for a described task,
   with one sentence of reasoning per suggestion — this is the actual
   skill the mental model is training.
""")

if __name__ == "__main__":
    print("\nDone. Next: any Modern_Topics doc — no fixed order, browse by category.")
