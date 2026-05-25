"""
Level 4 — Doc 4: Writing Great Tool Descriptions (PRACTICAL)
==============================================================
Topics:
  1. Bad vs good description comparison
  2. Tool selection accuracy testing
  3. "Cousin" tool differentiation
  4. Automated description quality checker
  5. Failure logging + iteration loop

Install: pip install openai python-dotenv
Run: python 04_tool_descriptions_practical.py
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def call_llm_with_tools(query: str, tools: list) -> Optional[str]:
    """Returns the tool name LLM chose, or None if no tool."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": query}],
            tools=tools,
            tool_choice="auto"
        )
        msg = response.choices[0].message
        if msg.tool_calls:
            return msg.tool_calls[0].function.name
        return None
    except Exception as e:
        return f"[Error: {e}]"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Bad vs Good Description Comparison
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Bad vs Good Descriptions — Same Tools")
print("=" * 70)

# BAD: vague, no differentiation
BAD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search for information",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look up data",
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string"}},
                "required": ["item"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find",
            "description": "Find stuff",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
]

# GOOD: clear, differentiated
GOOD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": """Search the public web (Google) for current information.

Use when:
- Current events, news, recent data
- General internet facts
- Stock prices, weather, sports scores

Do NOT use for: internal company data, personal user data.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_kb",
            "description": """Search internal company knowledge base for OUR product info, policies, FAQs.

Use when:
- Questions about OUR products / services
- Company policies
- Internal procedures

Do NOT use for: public web search, general info.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_user_emails",
            "description": """Search the current user's email inbox.

Use when:
- Finding specific emails
- Looking up email history

Do NOT use for: public web, company KB.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
]


TEST_CASES = [
    ("What's Tesla's stock price today?", "search_web"),
    ("What's our company's return policy?", "search_company_kb"),
    ("Find emails from John last week", "search_user_emails"),
    ("Latest news on AI?", "search_web"),
    ("What products do we sell?", "search_company_kb"),
]


def test_tool_selection(tools: list, test_cases: list, label: str) -> dict:
    """Run test cases, measure routing accuracy."""
    correct = 0
    misses = []
    for query, expected in test_cases:
        actual = call_llm_with_tools(query, tools)
        if actual == expected:
            correct += 1
        else:
            misses.append({"query": query, "expected": expected, "got": actual})
    return {
        "label": label,
        "accuracy": correct / len(test_cases) * 100,
        "correct": correct,
        "total": len(test_cases),
        "misses": misses
    }


print("\n[1.1 Testing BAD tools]")
bad_result = test_tool_selection(BAD_TOOLS, TEST_CASES, "BAD")
print(f"  Accuracy: {bad_result['accuracy']:.0f}%")
for m in bad_result['misses']:
    print(f"  ✗ '{m['query']}' → expected {m['expected']}, got {m['got']}")

print("\n[1.2 Testing GOOD tools]")
good_result = test_tool_selection(GOOD_TOOLS, TEST_CASES, "GOOD")
print(f"  Accuracy: {good_result['accuracy']:.0f}%")
for m in good_result['misses']:
    print(f"  ✗ '{m['query']}' → expected {m['expected']}, got {m['got']}")

print(f"\n💡 Improvement: {good_result['accuracy'] - bad_result['accuracy']:+.0f} percentage points")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Description Quality Checker
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Description Quality Checker")
print("=" * 70)


def audit_tool_description(tool: dict) -> dict:
    """Score a tool description on quality factors."""
    func = tool.get("function", tool)
    name = func.get("name", "")
    desc = func.get("description", "")
    params = func.get("parameters", {}).get("properties", {})

    issues = []

    # 1. Name quality
    if not name:
        issues.append("Missing name")
    elif "_" not in name and len(name) > 8:
        issues.append("Name should be snake_case verb_noun")
    elif len(name) < 3:
        issues.append("Name too short — be more descriptive")

    # 2. Description length
    word_count = len(desc.split())
    if word_count < 10:
        issues.append(f"Description too short ({word_count} words) — aim 30-150")
    elif word_count > 300:
        issues.append(f"Description too long ({word_count} words) — token waste")

    # 3. "When to use" clarity
    if "use when" not in desc.lower() and "for " not in desc.lower():
        issues.append("Missing WHEN to use guidance")

    # 4. "When NOT to use" (cousin differentiation)
    if "do not" not in desc.lower() and "don't" not in desc.lower() and "not for" not in desc.lower():
        issues.append("Missing WHEN NOT to use (cousin differentiation)")

    # 5. Param descriptions
    for pname, pdef in params.items():
        if not pdef.get("description"):
            issues.append(f"Param '{pname}' has no description")

    # Score: 100 - 15 per issue
    score = max(0, 100 - len(issues) * 15)
    return {"name": name, "score": score, "issues": issues}


print("\n[2.1 Audit BAD tools]")
for tool in BAD_TOOLS:
    audit = audit_tool_description(tool)
    print(f"\n  {audit['name']}: {audit['score']}/100")
    for issue in audit["issues"]:
        print(f"    ⚠️ {issue}")

print("\n[2.2 Audit GOOD tools]")
for tool in GOOD_TOOLS:
    audit = audit_tool_description(tool)
    print(f"\n  {audit['name']}: {audit['score']}/100")
    for issue in audit["issues"]:
        print(f"    ⚠️ {issue}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Edge Case — Refuse vs Call
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: When to REFUSE (Not Call Any Tool)")
print("=" * 70)

SIMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculate math expressions like '5 + 3 * 2'. Use ONLY for numerical math, not general knowledge.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet for current info. Use for facts you might not know.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }
]

REFUSE_CASES = [
    ("Hi, how are you?", None),               # Conversational, no tool
    ("Tell me a joke", None),                  # Creative, no tool
    ("What's 2+2?", "calculator"),             # Math
    ("Latest news on AI?", "search_web"),      # Current event
    ("What is the meaning of life?", None),    # Philosophy, no specific tool
]

print("\nTest cases — when SHOULD LLM use a tool?")
for query, expected in REFUSE_CASES:
    actual = call_llm_with_tools(query, SIMPLE_TOOLS)
    expected_label = expected if expected else "(no tool)"
    actual_label = actual if actual else "(no tool)"
    match = "✓" if actual == expected else "✗"
    print(f"  {match} '{query}' → expected: {expected_label}, got: {actual_label}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Failure Logger Pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Failure Logger for Iteration")
print("=" * 70)


class ToolFailureLogger:
    """Log routing failures for iterative description improvement."""

    def __init__(self):
        self.failures = []

    def log_failure(self, query: str, expected: str, actual: Optional[str], note: str = ""):
        self.failures.append({
            "query": query,
            "expected": expected,
            "actual": actual,
            "note": note
        })

    def summarize(self) -> dict:
        if not self.failures:
            return {"total": 0}
        # Most-confused pairs
        from collections import Counter
        confusions = Counter((f["expected"], f["actual"]) for f in self.failures)
        return {
            "total": len(self.failures),
            "top_confusions": confusions.most_common(3),
            "improvement_hint": "Strengthen differentiation for top confusions"
        }


logger = ToolFailureLogger()
# Simulate logging from bad results
for miss in bad_result["misses"]:
    logger.log_failure(miss["query"], miss["expected"], miss["got"])

print(f"\nFailure summary:")
summary = logger.summarize()
print(json.dumps(summary, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Description Improvement Workflow
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Iteration Workflow")
print("=" * 70)


WORKFLOW = """
Step 1: Define tools with initial descriptions
Step 2: Build test set (20+ queries → expected tool)
Step 3: Run tests, measure accuracy
Step 4: Analyze failures:
        - Tool A confused with Tool B → add 'NOT for B' to A's description
        - Tool not used when should be → check description is specific
        - Tool used when shouldn't → add 'Do not use for X' constraints
Step 5: Update descriptions
Step 6: Re-test
Step 7: Repeat until >95% accuracy
Step 8: Production deployment + ongoing failure logging
"""

print(WORKFLOW)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Take 3 of your existing tools. Run audit_tool_description(). Fix all issues.
2. Build a set of 4 "cousin" tools (e.g., 4 different search tools). Write descriptions that distinguish them.

MEDIUM:
3. Build a test set of 30 queries → expected tool. Measure routing accuracy.
4. Iterate descriptions until >90% accuracy.

HARD:
5. Build a "description generator" — input: Python function, output: AI-generated description following best practices.
6. Implement failure logging in production — log mismatches, weekly report.

PRO:
7. Build a "tool description CI":
   - On every PR, run accuracy tests
   - Block merge if accuracy drops below threshold
   - Track accuracy over time
""")

if __name__ == "__main__":
    print("\n✅ Tool descriptions are THE most important file. Iterate constantly!")
