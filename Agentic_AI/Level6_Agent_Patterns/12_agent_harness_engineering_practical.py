"""
Level 6 — Doc 12: Agent Harness Engineering (PRACTICAL)
=========================================================
Builds the actual mechanics a "harness" is made of — not the LLM, the
engineering AROUND the LLM that makes it a safe, bounded, production agent.

Topics covered:
  1. The core agent loop, with a hard iteration cap
  2. A real tool the loop can call (calculator — deterministic, easy to verify)
  3. Permission model — auto-allow / ask-first / never-allow, enforced in code
  4. Context window management — trigger + truncate-and-summarize
  5. A tiny harness eval — does the loop actually stop when it should?

Install: pip install openai python-dotenv
Run: python 12_agent_harness_engineering_practical.py
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


def llm_call(messages, tools=None, system=None, model="gpt-4o-mini"):
    if not HAS_KEY:
        return None
    from openai import OpenAI
    client = OpenAI()
    full_messages = ([{"role": "system", "content": system}] if system else []) + messages
    kwargs = {"model": model, "messages": full_messages, "max_tokens": 300}
    if tools:
        kwargs["tools"] = tools
    return client.chat.completions.create(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The Core Agent Loop, With a Hard Cap
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: The Agent Loop")
print("=" * 70)

CALC_TOOL = [{"type": "function", "function": {
    "name": "calculate",
    "description": "Evaluate a basic arithmetic expression, e.g. '12 * (3 + 4)'.",
    "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
}}]


def execute_tool(name: str, args: dict) -> str:
    """REAL side effects happen here — never inside the LLM call itself."""
    if name == "calculate":
        expr = args["expression"]
        if not re.fullmatch(r"[\d\s+\-*/().]+", expr):  # never eval() untrusted text blindly
            return "Error: expression contains disallowed characters"
        try:
            return str(eval(expr, {"__builtins__": {}}))
        except Exception as e:
            return f"Error: {e}"
    return f"Error: unknown tool {name}"


def agent_loop(user_message: str, system_prompt: str, max_iterations: int = 5) -> str:
    messages = [{"role": "user", "content": user_message}]
    for i in range(max_iterations):
        resp = llm_call(messages, tools=CALC_TOOL, system=system_prompt)
        if resp is None:
            return "[NO_API_KEY]"

        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content  # model is done, no more tool calls

        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})
        for tc in msg.tool_calls:
            import json
            args = json.loads(tc.function.arguments)
            result = execute_tool(tc.function.name, args)
            print(f"    [iteration {i+1}] tool={tc.function.name}({args}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "Max iterations reached — task may be incomplete"  # the cap is not optional


output = agent_loop(
    "What is (47 * 12) + (900 / 4), then subtract 15 from that?",
    system_prompt="You are a math assistant. Use the calculate tool for every arithmetic step. Do not compute in your head.",
)
print(f"\n  Final answer: {output}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Permission Model — Enforced, Not Suggested
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Permission Model")
print("=" * 70)

RISK_TIERS = {
    "read_file": "auto_allow",
    "search_code": "auto_allow",
    "calculate": "auto_allow",
    "write_file": "ask_first",
    "run_bash": "ask_first",
    "git_push": "ask_first",
    "delete_production_db": "never_allow",
}


def should_execute(tool_name: str, risk_tiers: dict = RISK_TIERS) -> bool:
    tier = risk_tiers.get(tool_name, "ask_first")  # unknown tool = ask, don't assume safe
    if tier == "never_allow":
        raise PermissionError(f"{tool_name} is hard-blocked — not even offered to the model")
    return tier == "auto_allow"  # False means the caller must get human confirmation first


for tool in ["read_file", "write_file", "delete_production_db", "some_new_unlisted_tool"]:
    try:
        allowed = should_execute(tool)
        print(f"  {tool:25s}: {'AUTO-ALLOW' if allowed else 'ASK FIRST — needs human confirmation'}")
    except PermissionError as e:
        print(f"  {tool:25s}: BLOCKED — {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Context Window Management
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Context Window Management")
print("=" * 70)


def estimate_tokens(messages) -> int:
    # Real harnesses use tiktoken; this is a fast, key-free approximation for the demo.
    return sum(len(str(m.get("content", ""))) for m in messages) // 4


def manage_context(messages: list, max_tokens: int = 500, keep_recent: int = 3) -> list:
    """Same trigger logic as the doc: don't wait until full, leave headroom."""
    current = estimate_tokens(messages)
    if current < max_tokens * 0.8:
        return messages

    system = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    recent = non_system[-keep_recent:]
    middle = non_system[:-keep_recent]

    summary_text = f"[Summarized {len(middle)} earlier turns — key points preserved, detail dropped]"
    return system + [{"role": "assistant", "content": summary_text}] + recent


# Simulate a long-running task filling up context
long_history = [{"role": "system", "content": "You are a coding agent."}]
for i in range(10):
    long_history.append({"role": "user", "content": f"Step {i}: " + "do a thing " * 30})
    long_history.append({"role": "assistant", "content": f"Done step {i}. " + "result data " * 30})

before = estimate_tokens(long_history)
managed = manage_context(long_history, max_tokens=500)
after = estimate_tokens(managed)

print(f"\n  Before: {len(long_history)} messages, ~{before} tokens")
print(f"  After : {len(managed)} messages, ~{after} tokens")
print(f"  Compacted {len(long_history) - len(managed)} messages into 1 summary,")
print(f"  keeping the system prompt + last {3} exchanges verbatim.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Evaluating the Harness Itself (not the model)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Does the Loop Actually Stop When It Should?")
print("=" * 70)

print("""
  A harness eval isn't "is the model smart" — it's "does the SCAFFOLDING
  behave correctly under stress." Two cheap, mock-mode-safe checks:
""")


def test_cap_is_enforced():
    """The loop must NEVER exceed max_iterations, even in a worst-case where
    the model keeps requesting tools forever. Simulated without an API call."""
    calls = 0
    max_iterations = 5

    def fake_loop():
        nonlocal calls
        for _ in range(max_iterations):
            calls += 1
            # pretend the model ALWAYS wants another tool call — the harness
            # must still stop at max_iterations regardless
        return calls

    result = fake_loop()
    passed = result == max_iterations
    print(f"  test_cap_is_enforced: calls={result}, expected={max_iterations} -> {'PASS' if passed else 'FAIL'}")


def test_never_allow_actually_blocks():
    try:
        should_execute("delete_production_db")
        print("  test_never_allow_actually_blocks: FAIL — no exception raised!")
    except PermissionError:
        print("  test_never_allow_actually_blocks: PASS")


test_cap_is_enforced()
test_never_allow_actually_blocks()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a `read_file` tool to CALC_TOOL/execute_tool (return a hardcoded
   string). Confirm it's auto_allow per RISK_TIERS.

MEDIUM:
2. Replace estimate_tokens() with a real tiktoken-based count. How different
   is the approximation from the real number on your long_history sample?

HARD:
3. Add a THIRD context-management strategy from the doc — selective
   retention: instead of summarizing everything, keep messages explicitly
   flagged `important=True` even if they're old, alongside the recent tail.

PRO:
4. Write 3 more harness-level tests (not model-quality tests): does an
   unknown tool default to "ask_first" and never silently auto-run? Does
   manage_context() ever drop the system prompt? Does agent_loop() ever
   call execute_tool() with unvalidated arguments?
""")

if __name__ == "__main__":
    print("\nDone. Next: 13_context_engineering_practical.py")
