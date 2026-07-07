# Modern Topics — Doc 11: Coding Agent Harness Deep Dive 🛠️⭐

> **Goal:** `07_ai_coding_tools.md` covers WHAT these tools do and how to use them well. This file covers HOW they're actually BUILT — the specific harness-engineering decisions that make Claude Code/Cursor/Devin work on real codebases, not toy demos.

---

## 1. Why a Coding Agent Needs a Specialized Harness

```
A general-purpose chat agent harness (Level 6 Doc 12) needs adapting for code:

General agent tools: web_search, calculator, send_email
Coding agent tools:   read_file, edit_file (DIFF-based, not full rewrite),
                      run_bash, search_codebase (grep/semantic), git operations

The DIFF-based edit tool specifically is the single biggest harness design
decision that separates a working coding agent from a frustrating one.
```

---

## 2. The Diff/Edit Tool Design Problem

```
NAIVE approach: model outputs the ENTIRE new file content, harness
                overwrites the old file.

Problems:
- Wastes tokens re-generating unchanged parts of large files
- Model can silently drop code it "forgot" was there (a section outside
  its attention gets dropped in the rewrite)
- No natural way to show the user a clean, reviewable diff

BETTER approach: model outputs a targeted edit — "find THIS exact string,
replace with THIS string" — harness applies it as a patch.
```

```python
# The "find old_string, replace with new_string" pattern (what Claude
# Code's Edit tool and similar tools in Cursor/Aider use)
def apply_edit(file_path: str, old_string: str, new_string: str):
    content = open(file_path).read()

    occurrences = content.count(old_string)
    if occurrences == 0:
        raise ValueError("old_string not found — model's edit doesn't match "
                          "actual file content (stale context, or hallucination)")
    if occurrences > 1:
        raise ValueError("old_string matches multiple locations — ambiguous, "
                          "model must provide more surrounding context to "
                          "uniquely identify the target")

    new_content = content.replace(old_string, new_string)
    with open(file_path, "w") as f:
        f.write(new_content)
```

**This is a real, deliberate harness safety mechanism, not a limitation:**
requiring the `old_string` to match EXACTLY (and uniquely) forces the model
to demonstrate it actually has correct, current knowledge of the file's
content before modifying it — silently guessing at line numbers or applying
a fuzzy/approximate patch is exactly how agents corrupt files.

### Alternative: line-number-based patches (less robust, why it's avoided)

```
Some earlier tools used "replace lines 45-52 with X" — this BREAKS the
moment any earlier edit in the same session shifts line numbers, since
the model's mental model of line numbers goes stale after its own first edit.
String-match-based editing (above) is immune to this because it doesn't
depend on position, only content.
```

---

## 3. Codebase Context — Retrieval for Code, Not Prose

```
A coding agent can't fit an entire large repo into context. Strategies,
layered (most coding agents use several of these together):

1. AGENTIC SEARCH (grep/glob tools) — let the model itself decide what
   to search for and read, iteratively, rather than pre-computing
   "relevant" context. This is what Claude Code primarily relies on —
   the model actively explores the repo like a human would.

2. EMBEDDING-BASED RETRIEVAL (Cursor's approach, among others) — the
   codebase is pre-indexed into embeddings; relevant files are retrieved
   semantically before the model even starts, similar to standard RAG
   (Level 5) but over code instead of documents.

3. STRUCTURAL/AST-AWARE CONTEXT — understanding that a function call
   implies its DEFINITION is relevant context, using the language's
   actual syntax tree rather than pure text similarity (more precise
   than embeddings for code specifically, since code has exact
   reference structure that prose doesn't).

4. CLAUDE.md / RULES FILES — explicit, curated context the user
   maintains (exactly what THIS repo's own CLAUDE.md file does) —
   cheaper and more precise than any automatic retrieval for
   information that rarely changes (project conventions, safety rules,
   architecture decisions).
```

**The agentic-search-over-pre-indexed-embeddings tradeoff (a real
interview-worthy design decision):** pre-indexing (embeddings) is faster per
query but goes STALE the moment the codebase changes and needs
re-indexing; agentic search (grep/glob, live) is always fresh but costs more
tool-call round-trips per task. Claude Code leans toward live agentic search
specifically because codebases change constantly during an active coding
session — a stale embedding index would actively mislead the agent.

---

## 4. The Verification Loop — Tests as Ground Truth

```
The single biggest reliability lever in a coding-agent harness:
give the agent a way to CHECK ITS OWN WORK, and instruct/encourage it
to actually use that check before declaring success.

Without verification: model edits code, says "done" — confidence in
                       correctness is purely the model's self-report
With verification:    model edits code → runs the test suite/type
                       checker/linter → SEES actual pass/fail output →
                       fixes if failing → repeats until genuinely passing
```

```python
# Harness-level pattern: after a code-editing tool call, prompt/nudge
# the agent toward verification rather than assuming success
def post_edit_hook(agent, edited_files):
    test_command = detect_test_command(edited_files)  # e.g., "pytest path/to/test.py"
    if test_command:
        agent.suggest_next_action(
            f"Consider running `{test_command}` to verify this change "
            f"before continuing."
        )
```

This is why "write tests first, or alongside" is repeatedly emphasized as
coding-agent best practice (already noted in `07_ai_coding_tools.md`
section 6) — it's not just good software engineering hygiene in the
abstract, it's specifically what gives a harness a REAL, executable
feedback signal instead of relying on the model's own unverified confidence.

---

## 5. Sandboxing Shell Execution — the highest-risk tool

```
run_bash / run_command is simultaneously the MOST USEFUL tool (can do
almost anything: run tests, install deps, git operations) and the
HIGHEST RISK (can also do almost anything destructive: rm -rf, curl
| sh from an untrusted source, force-push).

Harness mitigations, layered:
1. SANDBOX the execution environment (container, restricted filesystem
   view, no/limited network) so even a genuinely destructive command
   has bounded blast radius
2. PERMISSION TIERS (Level 6 Doc 12) — auto-allow read-only/build/test
   commands, require confirmation for anything matching destructive
   patterns (rm, git push --force, DROP TABLE, etc.)
3. WORKING DIRECTORY SCOPING — restrict execution to the project
   directory, block access to unrelated parts of the filesystem
4. TIMEOUT ENFORCEMENT — a hung command (waiting on stdin, infinite
   loop) shouldn't block the agent loop forever
```

This is precisely why THIS conversation's own tool-use has visible
"permission mode" behavior — destructive operations get flagged for
confirmation, reversible ones don't — you're interacting with exactly this
kind of tiered permission system live, right now.

---

## 6. Multi-File / Large Refactor Handling

```
A single-file edit is straightforward. A refactor spanning 20 files
(rename a function used everywhere, change a shared interface) needs:

1. DISCOVERY phase — find ALL call sites (grep/AST search, not guessing)
2. PLANNING — decide edit order (dependencies matter — a shared type
   definition should change before its consumers, generally)
3. INCREMENTAL APPLICATION — apply edits file-by-file, verifying
   (compile/typecheck) periodically rather than all-at-once with no
   checkpoint — catches a broken intermediate state before it compounds
4. FINAL VERIFICATION — full test suite / build, not just per-file checks
```

This is where CLI-first agents (Claude Code) tend to outperform
visual/IDE-first agents (Cursor) specifically — a CLI agent can run
`grep -r` across the WHOLE repo, execute the full test suite, and chain many
tool calls in a scripted loop without a human clicking through each file;
an IDE-centric agent is often optimized more for a human-in-the-loop,
file-at-a-time review flow instead.

---

## 7. Interview Q&A

**Q: Why do coding agents use diff/patch-style edits instead of just having the model rewrite the whole file?**
A: Rewriting risks the model silently dropping code outside its attention,
wastes tokens regenerating unchanged content, and doesn't give a clean
reviewable diff. String-match-based patching (find exact old content,
replace with new) forces the model to demonstrate accurate knowledge of
current file state and produces a natural diff for human review.

**Q: What's the single most effective way to make a coding agent more reliable?**
A: Give it a verification loop — tests, type-checking, linting — that it
actually runs and reads the output of, rather than self-reporting success.
This converts "the model believes it's done" into "the model has evidence
it's done," which is the biggest lever on real-world reliability.

**Q: Why is shell execution the highest-risk tool in a coding agent's toolkit, and how do harnesses mitigate that?**
A: It's nearly unrestricted — capable of almost any operation, including
destructive ones (deleting files, force-pushing, running untrusted scripts).
Harnesses mitigate this with sandboxed execution environments, tiered
permission systems (auto-allow safe commands, confirm risky ones),
working-directory scoping, and timeout enforcement.

**Q: Why might a CLI-based coding agent handle a 20-file refactor better than an IDE-based one?**
A: CLI agents can script full-repo search, chain many tool calls, and run
the complete test suite without needing a human to click through each file
— better suited to headless, large-scope, checkpoint-and-verify workflows.
IDE-centric agents are often optimized for a tighter human-in-the-loop,
file-at-a-time review cycle instead.

---

➡️ Related: `07_ai_coding_tools.md` (the tool landscape and usage
best-practices this deep-dives into), [../Level6_Agent_Patterns/12_agent_harness_engineering.md](../Level6_Agent_Patterns/12_agent_harness_engineering.md)
(the general harness-engineering discipline this applies specifically to
coding agents), `06_playwright_browser_automation.md` (a comparable
tool-sandboxing problem in a different domain).
