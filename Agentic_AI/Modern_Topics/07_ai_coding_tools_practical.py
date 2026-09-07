"""
Modern Topics — Doc 7: AI Coding Tools (PRACTICAL)
=====================================================
Topics covered:
  1. The 5-family classifier + a queryable tool database
  2. A "what should I use" recommender for backend engineering work
  3. The doc's own "interview gold" claim, made literal — a toy coding agent
     built from the exact concepts it maps (ReAct loop + tool use + memory),
     to prove "AI coding tools are just a ReAct loop over file/shell tools"
     isn't hand-waving

Run: python 07_ai_coding_tools_practical.py
"""

FAMILIES = {
    "autocomplete": ["Copilot", "Codeium", "Tabnine"],
    "chat_in_ide": ["Copilot Chat", "Cursor chat"],
    "agentic_ide": ["Cursor", "Windsurf"],
    "cli_agent": ["Claude Code", "Aider", "Codex CLI"],
    "app_builder": ["v0", "Bolt", "Lovable", "Replit Agent"],
    "autonomous_swe": ["Devin"],
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The 5-Family Classifier
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: 5 Families, Queryable")
print("=" * 70)


def family_of(tool_name: str) -> str:
    for family, tools in FAMILIES.items():
        if tool_name in tools:
            return family
    return "unknown"


for tool in ["Claude Code", "Cursor", "Copilot", "v0", "Devin"]:
    print(f"  {tool:15s} -> {family_of(tool)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: What Should a Backend Engineer Actually Use?
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Recommend a Stack, Not Just a Tool")
print("=" * 70)


def recommend_stack(task: str, needs_scriptable: bool, needs_visual_diff: bool) -> list[str]:
    stack = []
    if needs_scriptable or task == "large_refactor":
        stack.append("Claude Code (cli_agent) — scriptable, headless, strong multi-step planning")
    if needs_visual_diff:
        stack.append("Cursor (agentic_ide) — when you want to SEE the diff before accepting")
    if task == "boilerplate":
        stack.append("Copilot/Codeium (autocomplete) — fastest for repetitive patterns")
    if task == "quick_frontend_demo":
        stack.append("v0/Bolt (app_builder) — prototype only, don't trust for production backend")
    return stack or ["Claude Code — safe default for backend work"]


scenarios = [
    {"task": "large_refactor", "needs_scriptable": True, "needs_visual_diff": False},
    {"task": "boilerplate", "needs_scriptable": False, "needs_visual_diff": True},
    {"task": "quick_frontend_demo", "needs_scriptable": False, "needs_visual_diff": False},
]
for s in scenarios:
    print(f"\n  Task: {s['task']}")
    for rec in recommend_stack(**s):
        print(f"    -> {rec}")

print("\n  Doc's own rule of thumb: Claude Code (heavy lifting) + Cursor (visual edits)")
print("  + one autocomplete tool. More than that is context-switching waste.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: "It's Just a ReAct Loop" — Proven, Not Just Claimed
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: A Toy Coding Agent, Built From the Concept Map")
print("=" * 70)

print("""
  The doc's table maps coding-tool "magic" to concepts you already have from
  other levels: ReAct loop (L6), tool use (L4), MCP-style external tools (L7),
  codebase retrieval (L5), memory (L6), guardrails (L8). Below: a minimal
  coding agent using exactly those pieces — not a real coding tool, but proof
  the mapping is literal, not a metaphor.
""")


class ToyFileSystem:
    """Stands in for a real repo — 'files' are just a dict."""

    def __init__(self):
        self.files = {"app.py": "def add(a, b):\n    return a - b  # BUG: should be +\n"}

    def read_file(self, path: str) -> str:
        return self.files.get(path, f"Error: {path} not found")

    def write_file(self, path: str, content: str) -> str:
        self.files[path] = content
        return f"Wrote {len(content)} chars to {path}"

    def run_tests(self) -> str:
        # Simulate running the file's code against a known-good expectation
        ns = {}
        exec(self.files["app.py"], ns)
        result = ns["add"](2, 3)
        return "PASS" if result == 5 else f"FAIL — add(2,3) returned {result}, expected 5"


class ProjectMemory:
    """The doc's 'memory' row — project conventions, past edits — kept
    minimal here, but note it's the SAME shape as Modern_Topics Doc 4's
    memory practical, applied specifically to coding-agent context."""

    def __init__(self):
        self.past_edits: list[str] = []

    def record(self, summary: str):
        self.past_edits.append(summary)

    def relevant_context(self) -> str:
        return "; ".join(self.past_edits) or "(no prior edits this session)"


def toy_coding_agent(fs: ToyFileSystem, memory: ProjectMemory, task: str, max_iterations: int = 5) -> str:
    """Thought -> Action -> Observation -> repeat — the doc's literal claim."""
    print(f"  TASK: {task}")
    for i in range(max_iterations):
        # THOUGHT (in a real tool, an LLM call; here, deterministic for a
        # runnable demo — the LOOP STRUCTURE is the point, not the reasoning)
        current_code = fs.read_file("app.py")
        print(f"\n  [iter {i+1}] THOUGHT: read app.py, current content:\n    {current_code.strip()}")

        if "return a - b" in current_code:
            # ACTION: tool use (write_file) — same "tool" concept as Level4
            fixed = current_code.replace("return a - b  # BUG: should be +", "return a + b")
            observation = fs.write_file("app.py", fixed)
            memory.record("Fixed add() to use + instead of -")
            print(f"  ACTION: write_file(app.py, <fixed>) -> OBSERVATION: {observation}")
            continue

        # ACTION: run tests (verification loop — Level6 harness engineering)
        test_result = fs.run_tests()
        print(f"  ACTION: run_tests() -> OBSERVATION: {test_result}")
        if test_result == "PASS":
            return f"Done in {i+1} iterations. Memory: {memory.relevant_context()}"

    return "Max iterations reached — task incomplete"


fs = ToyFileSystem()
memory = ProjectMemory()
result = toy_coding_agent(fs, memory, task="Fix the bug in add()")
print(f"\n  {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a `search_code(pattern)` tool to ToyFileSystem and use it in
   toy_coding_agent() to locate the bug instead of assuming app.py.

MEDIUM:
2. Add a second file with a second bug, and make the agent handle both
   before running tests — this is closer to a real multi-file edit.

HARD:
3. Add a guardrail (Level8 concept, per the doc's table): write_file() should
   require an explicit `confirm=True` flag when the diff touches more than
   N lines, refusing otherwise — mirrors Level6 Doc 12's permission model.

PRO:
4. Replace the THOUGHT step's deterministic logic with a real LLM call (any
   provider) that reads current_code and decides the next action via tool
   calling — this turns the toy agent into an actual (tiny) coding agent.
""")

if __name__ == "__main__":
    print("\nDone. Next: 08_mcp_advanced_server_dev_practical.py")
