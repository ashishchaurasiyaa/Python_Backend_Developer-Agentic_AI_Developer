"""
Modern Topics — Doc 11: Coding Agent Harness Deep Dive (PRACTICAL)
======================================================================
Implements the EXACT `apply_edit` mechanism this doc describes — which is,
not coincidentally, the same mechanism behind the Edit tool used throughout
this whole session to write these practicals. Seeing it fail on purpose
(ambiguous match, stale content) is the fastest way to understand why this
design choice exists.

Topics covered:
  1. apply_edit() — find-and-replace-by-unique-string, with real failure modes
  2. Why line-number-based patches break (simulated, not just claimed)
  3. The verification loop — a real post-edit test run, not a self-report
  4. Shell sandboxing — a risk-tiered command classifier

Run: python 11_coding_agent_harness_deep_dive_practical.py
"""

import subprocess
import tempfile
import os


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: apply_edit() — the Real Mechanism, With Real Failure Modes
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: apply_edit() — Find-and-Replace-by-Unique-Match")
print("=" * 70)


def apply_edit(file_path: str, old_string: str, new_string: str) -> str:
    content = open(file_path).read()

    occurrences = content.count(old_string)
    if occurrences == 0:
        raise ValueError("old_string not found — stale context, or hallucination")
    if occurrences > 1:
        raise ValueError(f"old_string matches {occurrences} locations — ambiguous, need more surrounding context")

    new_content = content.replace(old_string, new_string)
    with open(file_path, "w") as f:
        f.write(new_content)
    return f"Applied edit — {len(old_string)} chars -> {len(new_string)} chars"


tmpdir = tempfile.mkdtemp()
sample_file = os.path.join(tmpdir, "sample.py")
with open(sample_file, "w") as f:
    f.write("def add(a, b):\n    return a - b  # BUG\n\ndef subtract(a, b):\n    return a - b\n")

print(f"\n  File content:\n{open(sample_file).read()}")

# Case 1: ambiguous match — "return a - b" appears in BOTH functions right
# now (add's buggy line AND subtract's correct line), so this is genuinely
# ambiguous BEFORE any fix is applied — test this first, while it's still true.
try:
    apply_edit(sample_file, "return a - b", "return a * b")
except ValueError as e:
    print(f"  apply_edit (ambiguous match): BLOCKED — {e}")

# Case 2: unique match — the "# BUG" comment makes add's line unambiguous
result = apply_edit(sample_file, "return a - b  # BUG", "return a + b")
print(f"  apply_edit (unique match): {result}")
print(f"\n  File content now:\n{open(sample_file).read()}")

# Case 3: stale context — old_string doesn't exist anymore
try:
    apply_edit(sample_file, "def multiply(a, b):", "def multiply(a, b):  # renamed")
except ValueError as e:
    print(f"  apply_edit (stale context): BLOCKED — {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Why Line-Number Patches Break — Simulated
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Line-Number Patches Go Stale After the First Edit")
print("=" * 70)


def apply_line_patch(lines: list[str], start: int, end: int, replacement: list[str]) -> list[str]:
    """The fragile alternative — works ONCE, then the model's mental model
    of line numbers is wrong for every SUBSEQUENT edit in the same session."""
    return lines[:start] + replacement + lines[end:]


original_lines = ["def add(a, b):", "    return a + b", "", "def subtract(a, b):", "    return a - b"]
print(f"\n  Original (5 lines):")
for i, l in enumerate(original_lines):
    print(f"    {i}: {l}")

# Model's FIRST edit: insert a line at position 1 (a docstring, say)
after_first_edit = apply_line_patch(original_lines, 1, 1, ["    '''Adds two numbers.'''"])
print(f"\n  After inserting a docstring at line 1 (5 -> 6 lines):")
for i, l in enumerate(after_first_edit):
    print(f"    {i}: {l}")

print(f"\n  Model's mental model still says 'subtract is at line 3' — but it's")
print(f"  now at line {after_first_edit.index('def subtract(a, b):')}. A SECOND line-number-based edit")
print(f"  targeting line 3 would corrupt the WRONG line. String-match editing")
print(f"  (Section 1) is immune to this — it doesn't care about position at all.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: The Verification Loop — a Real Test Run, Not Self-Report
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Verification Loop — Actually Run the Tests")
print("=" * 70)

test_file = os.path.join(tmpdir, "test_sample.py")
with open(test_file, "w") as f:
    f.write("from sample import add, subtract\n\ndef test_add():\n    assert add(2, 3) == 5\n\ndef test_subtract():\n    assert subtract(5, 2) == 3\n")


def detect_test_command(edited_files: list[str]) -> str | None:
    import sys
    for f in edited_files:
        test_candidate = f.replace(os.path.basename(f), f"test_{os.path.basename(f)}")
        if os.path.exists(test_candidate):
            return f"{sys.executable} -m pytest {test_candidate} -v"
    return None


def post_edit_hook(edited_files: list[str]) -> str:
    """Same shape as the doc's post_edit_hook — but this one actually RUNS
    the command instead of just suggesting it, to show what the harness sees."""
    test_command = detect_test_command(edited_files)
    if not test_command:
        return "No test file detected — no verification signal available."

    # PYTEST_DISABLE_PLUGIN_AUTOLOAD isolates this from whatever pytest plugins
    # happen to be globally installed on the host machine (e.g. a project-
    # specific plugin that fails to import outside its own project) — without
    # it, this demo's pass/fail depends on unrelated ambient machine state.
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = subprocess.run(test_command.split(), cwd=tmpdir, capture_output=True, text=True, timeout=10, env=env)
    passed = result.returncode == 0
    output = result.stdout[-300:] if result.stdout else result.stderr[-300:]
    return f"Ran `{test_command}` -> {'PASS' if passed else 'FAIL'}\n{output if not passed else '(all tests passed)'}"


print(f"\n  {post_edit_hook([sample_file])}")
print("\n  This is the actual difference the doc calls out: the harness doesn't")
print("  TRUST the model's 'I fixed it' — it runs the check and reads real output.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Shell Sandboxing — Risk-Tiered Command Classifier
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Shell Command Risk Classification")
print("=" * 70)

DESTRUCTIVE_PATTERNS = ["rm -rf", "> /dev/", "sudo", "chmod -R 777", "git push --force", "DROP TABLE", "DROP DATABASE"]
READ_ONLY_PREFIXES = ["ls", "cat", "grep", "find", "git status", "git diff", "git log", "pytest", "python -m pytest"]


def classify_shell_command(cmd: str) -> str:
    if any(p in cmd for p in DESTRUCTIVE_PATTERNS):
        return "NEVER_ALLOW — matches a destructive pattern, hard-blocked regardless of context"
    if any(cmd.strip().startswith(p) for p in READ_ONLY_PREFIXES):
        return "AUTO_ALLOW — read-only or verification command"
    return "ASK_FIRST — unrecognized command, needs human confirmation before running"


test_commands = ["ls -la", "pytest tests/", "rm -rf /", "git push --force origin main", "curl https://api.example.com/data", "sudo apt-get install foo"]
for cmd in test_commands:
    print(f"\n  '{cmd}'\n    -> {classify_shell_command(cmd)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Trigger a THIRD apply_edit() failure mode of your own design — e.g.
   old_string with trailing whitespace that doesn't match exactly.

MEDIUM:
2. Add a `replace_all` parameter to apply_edit() that, when True, allows
   multiple matches and replaces all of them (mirrors the real Edit tool's
   replace_all option) — but still blocks the ambiguous case by default.

HARD:
3. Extend post_edit_hook() to retry the edit automatically ONCE if tests
   fail, feeding the actual pytest failure output back as new context —
   this is the harness-level "verification loop" the doc describes, not
   just a single check.

PRO:
4. classify_shell_command() uses substring matching — write 3 commands that
   would evade DESTRUCTIVE_PATTERNS while still being genuinely destructive
   (e.g. obfuscated via variable substitution), and propose a more robust
   check (parsing the command with shlex, checking the actual binary + args).
""")

if __name__ == "__main__":
    print("\nDone. Next: 12_openai_responses_api_practical.py")
