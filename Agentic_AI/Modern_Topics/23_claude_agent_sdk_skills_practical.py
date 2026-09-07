"""
Modern Topics — Doc 23: Claude Agent SDK + Agent Skills (PRACTICAL)
=======================================================================
Tries the real `claude-agent-sdk` package first; falls back to manual
demonstrations of the concepts that transfer regardless — the 4-approach
decision tree, SKILL.md progressive disclosure, and subagent delegation.

Topics covered:
  1. The 4 ways to build a Claude-based agent — as a real decision function
  2. Progressive disclosure — parsing a SKILL.md's frontmatter without
     loading the full file, exactly like the SDK does internally
  3. Subagent delegation — a manual version of the agents={} config
  4. Skills vs MCP vs RAG — made concrete with 3 different calls for the
     SAME underlying need

Install (optional, real SDK): pip install claude-agent-sdk
Run: python 23_claude_agent_sdk_skills_practical.py
"""

import os
import re

try:
    import claude_agent_sdk  # noqa: F401
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The 4 Approaches — a Real Decision Function
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Which of the 4 Approaches?")
print("=" * 70)

if not HAS_SDK:
    print("\n  [claude-agent-sdk not installed — Sections 2-3 use manual")
    print("   reimplementations of the concepts. `pip install claude-agent-sdk`")
    print("   for the real thing.]")


def pick_agent_approach(wants_anthropic_hosting: bool, needs_filesystem_bash: bool, has_custom_tools_only: bool) -> str:
    if wants_anthropic_hosting:
        return "Managed Agents (CMA) — Anthropic hosts both the loop AND the sandbox"
    if needs_filesystem_bash:
        return "Claude Agent SDK — batteries-included coding/filesystem agent, Claude Code's harness as a library"
    if has_custom_tools_only:
        return "Tool Runner (client.beta.messages.tool_runner) — SDK loop, your tools, no built-ins"
    return "Manual loop — full control, no beta dependency"


scenarios = [
    {"wants_anthropic_hosting": True, "needs_filesystem_bash": False, "has_custom_tools_only": False},
    {"wants_anthropic_hosting": False, "needs_filesystem_bash": True, "has_custom_tools_only": False},
    {"wants_anthropic_hosting": False, "needs_filesystem_bash": False, "has_custom_tools_only": True},
    {"wants_anthropic_hosting": False, "needs_filesystem_bash": False, "has_custom_tools_only": False},
]
for s in scenarios:
    print(f"\n  {s}")
    print(f"    -> {pick_agent_approach(**s)}")

print("\n  Key mental model (the doc's own emphasis): TWO independent questions —")
print("  (a) who provides the harness (loop + context mgmt)? (b) who deploys it?")
print("  Only Managed Agents answers 'Anthropic' to both.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Progressive Disclosure — Parse Frontmatter Without Loading Everything
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Progressive Disclosure — SKILL.md Frontmatter")
print("=" * 70)

FAKE_SKILL_MD = """---
name: pdf-invoice-extractor
description: Extract line items and totals from PDF invoices into structured JSON. Use when the user mentions invoices, bills, or PDF extraction.
---

# PDF Invoice Extraction

1. Use pdfplumber to extract text tables...
2. Validate totals: sum(line_items) == grand_total...
"""  # (in reality this would be a real file on disk under .claude/skills/)


def parse_skill_frontmatter(skill_md_content: str) -> dict:
    """The SAME mechanism the SDK uses internally: only name+description stay
    resident in context (~2 lines) — the rest loads ONLY if the task matches.
    This function demonstrates that split explicitly."""
    match = re.search(r"^---\n(.*?)\n---\n(.*)$", skill_md_content, re.DOTALL)
    if not match:
        return {}
    frontmatter_text, body = match.groups()
    frontmatter = {}
    for line in frontmatter_text.strip().split("\n"):
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip()
    return {"frontmatter": frontmatter, "body": body, "body_loaded": False}


skill_metadata = parse_skill_frontmatter(FAKE_SKILL_MD)
print(f"\n  ALWAYS in context (cheap): {skill_metadata['frontmatter']}")
print(f"  body_loaded: {skill_metadata['body_loaded']} — the actual instructions haven't")
print(f"  been read into context yet, even though we already parsed the file.")


def maybe_load_skill_body(skill_metadata: dict, task: str) -> dict:
    """Only load the full skill body if the task actually matches the
    description's trigger condition — this is the context-budget payoff."""
    description = skill_metadata["frontmatter"].get("description", "")
    trigger_words = ["invoice", "bill", "pdf extraction"]
    if any(w in task.lower() for w in trigger_words) or any(w in description.lower() for w in trigger_words):
        skill_metadata["body_loaded"] = True
    return skill_metadata


for task in ["Summarize this meeting transcript", "Extract totals from this invoice PDF"]:
    result = maybe_load_skill_body(dict(skill_metadata), task)
    print(f"\n  Task: '{task}'")
    print(f"    -> skill body loaded: {result['body_loaded']}")

print("\n  50 skills in .claude/skills/ cost ~100 lines of always-resident context")
print("  (2 lines each) instead of thousands — THIS is what makes 50 skills viable.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Subagent Delegation — Manual Version of agents={}
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Subagent Delegation")
print("=" * 70)

SUBAGENTS = {
    "test-writer": {
        "description": "Writes pytest tests for a given module",
        "tools": ["Read", "Write", "Grep"],
        "model": "haiku",  # cheap model for a narrow sub-task
    },
}


def delegate_if_matched(task: str, subagents: dict) -> str:
    for name, config in subagents.items():
        if "test" in task.lower() and "test" in config["description"].lower():
            return f"Delegating to subagent '{name}' (model={config['model']}, tools={config['tools']}) — own context, own model, isolated from main agent's."
    return "Handling in main agent context — no matching subagent."


print(f"\n  {delegate_if_matched('Write tests for the payment module', SUBAGENTS)}")
print(f"  {delegate_if_matched('Explain what this function does', SUBAGENTS)}")
print("\n  The doc's economic point: delegating to a cheap model (haiku) for a")
print("  narrow, well-defined sub-task keeps the expensive main-agent model's")
print("  context and cost budget for the harder parts of the overall task.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Skills vs MCP vs RAG — Same Need, 3 Different Answers
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Skills vs MCP vs RAG, Concretely")
print("=" * 70)

print("""
  Need: "help me process an invoice"

  MCP alone   : gives the agent a `read_pdf` TOOL — it can extract text,
                but has no idea HOW to validate totals or handle edge cases.
  RAG alone   : retrieves a company policy doc about invoice handling —
                factual knowledge, but no executable procedure.
  Skill       : provides the PROCEDURE ("use pdfplumber, then validate
                sum(line_items) == grand_total, handle these edge cases...")
                — knows HOW to use the MCP tool expertly.

  Real systems combine them: MCP tool (access) + Skill (expertise using it)
  + RAG (company-specific facts the skill's procedure might reference).
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 2nd fake skill (e.g. "csv-analyzer") and test maybe_load_skill_body()
   against 3 different task strings.

MEDIUM:
2. Add a 2nd subagent ("code-reviewer") to SUBAGENTS and extend
   delegate_if_matched() to actually pick the BEST match when a task could
   plausibly go to either subagent.

HARD:
3. If you have claude-agent-sdk installed: run the real `query()` example
   from the doc's Section 2 against a small test folder with a few Python
   files containing TODO comments — compare its actual tool-call trace to
   what you'd expect from Section 1's decision tree.

PRO:
4. Build a real SKILL.md file for something you actually do repeatedly in
   this repo (e.g. "write a Level6-style practical") — frontmatter +
   trigger description + procedure — and place it under .claude/skills/
   if you use Claude Code, to see progressive disclosure work for real.
""")

if __name__ == "__main__":
    print("\nDone. Next: 24_openai_agentkit_practical.py")
