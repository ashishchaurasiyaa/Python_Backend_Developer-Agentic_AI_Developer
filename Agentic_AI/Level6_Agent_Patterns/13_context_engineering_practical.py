"""
Level 6 — Doc 13: Context Engineering (PRACTICAL)
===================================================
Context engineering is a SYSTEMS skill, not a prompt-wording skill — this
file builds the actual pipeline pieces the doc describes, all measurable
in tokens, not vibes. Provider-agnostic where the doc's concepts are
provider-agnostic; the Claude-specific beta APIs (cache_control breakpoints,
compact-2026-01-12) are referenced as comments, not hard dependencies,
since this needs to run without a live key.

Topics covered:
  1. The 5-question budget framework, applied to a real block list
  2. A "silent cache killer" linter — catches the patterns the doc warns about
  3. Compaction with a PRIORITY ORDER, not just truncation
  4. Sub-agent context isolation — measuring the fan-out savings for real

Install: pip install tiktoken (optional — falls back to char/4 estimate)
Run: python 13_context_engineering_practical.py
"""

import json
import re


def count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4  # rough fallback, good enough for relative comparisons


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The 5-Question Budget Framework, Applied
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Does This Block Earn Its Place in Context?")
print("=" * 70)

CANDIDATE_BLOCKS = [
    {"name": "system_prompt", "content": "You are a senior Python reviewer. Report bugs with file:line.",
     "used_this_turn": True, "model_already_knows": False, "changes_per_call": False, "needs_verbatim": True},
    {"name": "generic_python_docs", "content": "Python is a general-purpose language created by Guido van Rossum in 1991. " * 20,
     "used_this_turn": False, "model_already_knows": True, "changes_per_call": False, "needs_verbatim": False},
    {"name": "current_user_request", "content": "Review this diff for security issues in the auth module.",
     "used_this_turn": True, "model_already_knows": False, "changes_per_call": True, "needs_verbatim": True},
    {"name": "old_tool_result_full_file", "content": "def old_function():\n    pass\n" * 100,
     "used_this_turn": False, "model_already_knows": False, "changes_per_call": False, "needs_verbatim": False},
    {"name": "request_timestamp", "content": "2026-08-31T14:22:01Z",
     "used_this_turn": False, "model_already_knows": False, "changes_per_call": True, "needs_verbatim": True},
]


def evaluate_block(block: dict) -> str:
    """The doc's 5-question table, as an actual decision function."""
    if not block["used_this_turn"]:
        return "DROP or move behind retrieval — model won't use it this turn"
    if block["model_already_knows"]:
        return "DROP — generic knowledge, don't pay tokens to re-teach it"
    if not block["needs_verbatim"]:
        return "COMPACT — gist is enough, don't keep verbatim"
    if block["changes_per_call"]:
        return "KEEP, position AFTER cache breakpoint — it's volatile"
    return "KEEP, position BEFORE cache breakpoint — it's stable, cache it"


for block in CANDIDATE_BLOCKS:
    tokens = count_tokens(block["content"])
    decision = evaluate_block(block)
    print(f"\n  [{block['name']}] (~{tokens} tokens)")
    print(f"    -> {decision}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: A Silent-Cache-Killer Linter
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Silent Cache Killer Linter")
print("=" * 70)

print("""
  These patterns silently invalidate a cached prefix — no error, just a
  quiet cost/latency regression nobody notices until the bill arrives.
""")


def lint_system_prompt(build_fn_source: str) -> list[str]:
    issues = []
    if "datetime.now()" in build_fn_source or "utcnow()" in build_fn_source:
        issues.append("datetime.now()/utcnow() found — timestamp in a cached prefix changes every call")
    if "uuid4()" in build_fn_source:
        issues.append("uuid4() found — random ID in a cached prefix changes every call")
    if "json.dumps(" in build_fn_source and "sort_keys=True" not in build_fn_source:
        issues.append("json.dumps() without sort_keys=True — dict key order isn't guaranteed stable")
    if re.search(r"if\s+\w+\s*:\s*\n?\s*system\s*\+=", build_fn_source):
        issues.append("conditional 'system +=' found — every flag combination creates a distinct prefix")
    return issues


BAD_EXAMPLE = '''
def build_system_prompt(user, flags):
    system = "You are a helpful assistant."
    system += f"\\nCurrent time: {datetime.now()}"
    if flags.get("verbose"):
        system += "\\nBe extra detailed."
    tools = build_tools(user)
    return system, tools
'''

GOOD_EXAMPLE = '''
def build_system_prompt():
    return FROZEN_SYSTEM_PROMPT  # zero interpolation, identical every call

def build_messages(user, flags, timestamp):
    # volatile stuff goes in the LAST user message, not the cached system prompt
    return [{"role": "user", "content": f"[{timestamp}] verbose={flags.get('verbose')} {user}"}]
'''

for label, code in [("BAD (real trap)", BAD_EXAMPLE), ("GOOD (fixed)", GOOD_EXAMPLE)]:
    issues = lint_system_prompt(code)
    print(f"\n  {label}:")
    if issues:
        for issue in issues:
            print(f"    ✗ {issue}")
    else:
        print(f"    ✓ no cache-killer patterns found")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Compaction — With a Priority Order, Not Just Truncation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Priority-Ordered Compaction")
print("=" * 70)

# A fake long-running agent trace, tagged by what kind of content it is —
# a real harness would infer these tags, here they're set explicitly for the demo.
TRACE = [
    {"type": "task", "content": "Original task: migrate the payments module to async SQLAlchemy."},
    {"type": "decision", "content": "Chose asyncpg driver over psycopg2-async because it's faster for our workload."},
    {"type": "tool_noise", "content": "ls src/payments/ -> [12 files listed, already read]"},
    {"type": "tool_noise", "content": "grep 'def process' -> [8 matches, already reviewed]"},
    {"type": "constraint", "content": "Discovered: the test DB is read-only in CI, can't run migration tests there."},
    {"type": "state", "content": "Files touched so far: payments/models.py (done), payments/service.py (in progress)."},
    {"type": "tool_noise", "content": "cat payments/models.py -> [200 lines, already incorporated into state above]"},
    {"type": "reasoning", "content": "Considered 3 approaches to the connection pool sizing, concluded in the decision above."},
    {"type": "open_question", "content": "Still unresolved: should the migration be feature-flagged or a hard cutover?"},
]

PRIORITY_ORDER = ["task", "decision", "constraint", "state", "open_question"]  # what to KEEP
DROP_TYPES = {"tool_noise", "reasoning"}  # noise / already-captured-elsewhere


def compact(trace: list, priority_order: list = PRIORITY_ORDER) -> list:
    kept = [item for item in trace if item["type"] in priority_order]
    kept.sort(key=lambda item: priority_order.index(item["type"]))
    dropped = [item for item in trace if item["type"] not in priority_order]
    return kept, dropped


kept, dropped = compact(TRACE)
before_tokens = sum(count_tokens(t["content"]) for t in TRACE)
after_tokens = sum(count_tokens(t["content"]) for t in kept)

print(f"\n  Before: {len(TRACE)} entries, ~{before_tokens} tokens")
print(f"  After : {len(kept)} entries, ~{after_tokens} tokens ({100 - int(100*after_tokens/before_tokens)}% reduction)")
print(f"\n  KEPT (priority order):")
for item in kept:
    print(f"    [{item['type']:14s}] {item['content'][:70]}")
print(f"\n  DROPPED (routine noise, already captured elsewhere):")
for item in dropped:
    print(f"    [{item['type']:14s}] {item['content'][:70]}")

print("\n  Note what survived: the ORIGINAL TASK is still there after compaction —")
print("  the single most common compaction bug is losing this and letting the")
print("  agent quietly drift off the actual requirement.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Sub-Agent Context Isolation — Measured, Not Asserted
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Fan-Out vs One Long Context — Real Numbers")
print("=" * 70)

# Simulate: main agent needs to search 50 files for a pattern
fake_file_content = "def some_function():\n    # implementation\n    pass\n" * 40  # ~2K tokens/file
num_files = 50

naive_tokens = count_tokens(fake_file_content) * num_files
print(f"\n  NAIVE (main agent reads all {num_files} files itself):")
print(f"    ~{naive_tokens:,} tokens enter main context, and RIDE ALONG for every")
print(f"    subsequent turn — resent on every loop iteration, cached or not.")

# Fan-out: 5 sub-agents, each reads 10 files in ITS OWN fresh context,
# returns only a short finding — not its transcript
sub_agent_finding = "Found 2 matches: payments/service.py:45, payments/utils.py:12"
fanout_tokens_to_main = count_tokens(sub_agent_finding) * 5  # 5 sub-agents report back

print(f"\n  FAN-OUT (5 sub-agents, 10 files each, own fresh context per sub-agent):")
print(f"    Each sub-agent's {num_files // 5}-file read happens in ITS OWN context —")
print(f"    never touches main context at all.")
print(f"    Main context only receives the {5} distilled findings: ~{fanout_tokens_to_main} tokens")

reduction = 100 * (1 - fanout_tokens_to_main / naive_tokens)
print(f"\n  Main-context token reduction: {reduction:.1f}%")
print(f"  This is the doc's core claim, with actual numbers instead of a hand-wave.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 6th block to CANDIDATE_BLOCKS from a real agent you've built or
   read about. Run evaluate_block() on it — do you agree with the verdict?

MEDIUM:
2. Extend lint_system_prompt() to catch one more pattern: a per-user tool
   list (`tools = build_tools(user)`) placed at prompt position 0.

HARD:
3. TRACE's compact() currently drops "reasoning" entirely. Add a rule: if a
   reasoning entry has NO matching decision entry afterward, keep it instead
   of dropping it (uncaptured reasoning shouldn't silently vanish).

PRO:
4. If you have API access: build the REAL version of Section 1's stable-prefix
   layout against a live provider, make 3 identical calls, and read the
   actual `usage` object (cache_creation_input_tokens vs cache_read_input_tokens)
   to see the 0.1x cache-read discount for real, not simulated.
""")

if __name__ == "__main__":
    print("\nDone. Level 6 complete — every doc now has hands-on code.")
    print("Next: Level 7 (Frameworks)")
