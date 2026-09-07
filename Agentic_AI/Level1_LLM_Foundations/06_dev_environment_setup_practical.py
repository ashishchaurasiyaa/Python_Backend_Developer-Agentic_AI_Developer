"""
Level 1 — Doc 6: Dev Environment Setup (PRACTICAL)
====================================================
This doc is about tooling, not an API — so the practical here is an
"environment doctor": a script that actually checks whether your machine
is set up the way this doc says it should be, instead of just reading a
checklist and assuming you did it right.

Topics covered:
  1. Python version check
  2. Package manager detection (uv / poetry / pip)
  3. .env presence + required/optional keys set
  4. .gitignore correctly excludes .env (the #1 way people leak API keys)
  5. Essential packages installed vs missing, by category
  6. A final pass/fail readiness report

Run: python 06_dev_environment_setup_practical.py
"""

import importlib.util
import os
import shutil
import sys

REPORT = {"ok": [], "warn": [], "fail": []}


def check(label: str, condition: bool, ok_msg: str, fail_msg: str, severity: str = "fail"):
    if condition:
        REPORT["ok"].append(f"{label}: {ok_msg}")
    else:
        REPORT[severity].append(f"{label}: {fail_msg}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Python Version
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Python Version")
print("=" * 70)

version = sys.version_info
print(f"\n  Running: Python {version.major}.{version.minor}.{version.micro}")
check(
    "Python version",
    version >= (3, 11),
    f"{version.major}.{version.minor} — good, 3.11+ recommended for this repo",
    f"{version.major}.{version.minor} — below 3.11, some async/typing features in later docs will differ",
    severity="warn",
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Package Manager Detection
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Package Manager")
print("=" * 70)

managers = {"uv": shutil.which("uv"), "poetry": shutil.which("poetry"), "pip": shutil.which("pip") or shutil.which("pip3")}
print()
for name, path in managers.items():
    print(f"  {name:8s}: {'found at ' + path if path else 'not found'}")

check(
    "Package manager",
    any(managers.values()),
    "at least one found — " + ", ".join(n for n, p in managers.items() if p),
    "none of uv/poetry/pip found on PATH — install at least one",
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: .env File + Keys
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: .env File + API Keys")
print("=" * 70)

env_path = ".env"
env_exists = os.path.exists(env_path)
check(".env file", env_exists, "found in current directory", "not found — copy .env.example or create one")

if env_exists:
    from dotenv import load_dotenv
    load_dotenv()

REQUIRED_KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
OPTIONAL_KEYS = ["GEMINI_API_KEY", "TAVILY_API_KEY", "LANGCHAIN_API_KEY"]

print()
for key in REQUIRED_KEYS:
    present = bool(os.getenv(key))
    print(f"  {key:25s}: {'set' if present else 'MISSING'}")
    check(f"Key {key}", present, "set", "missing — required for most Level 1-8 practicals to run live", severity="warn")

print("\n  Optional:")
for key in OPTIONAL_KEYS:
    present = bool(os.getenv(key))
    print(f"  {key:25s}: {'set' if present else 'not set'}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: .gitignore Protects .env
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: .gitignore Protects Secrets")
print("=" * 70)

gitignore_path = ".gitignore"
gitignore_has_env = False
if os.path.exists(gitignore_path):
    with open(gitignore_path) as f:
        content = f.read()
        gitignore_has_env = ".env" in content

print(f"\n  .gitignore exists: {os.path.exists(gitignore_path)}")
print(f"  .gitignore excludes .env: {gitignore_has_env}")
check(
    ".env protection",
    gitignore_has_env,
    ".env is gitignored — safe",
    "'.env' NOT found in .gitignore — this is the #1 way API keys end up in a public repo. Fix this now.",
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Essential Packages, by Category
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Essential Packages Installed?")
print("=" * 70)

PACKAGE_CATEGORIES = {
    "Core": ["dotenv", "pydantic", "httpx"],
    "LLM Frameworks": ["openai", "anthropic", "litellm"],
    "RAG / Vector DBs": ["chromadb", "sentence_transformers"],
    "Backend": ["fastapi", "uvicorn"],
    "Observability": ["langfuse"],
}


def is_installed(module_name: str) -> bool:
    # dotenv's importable name differs from its pip name (python-dotenv)
    real_name = {"dotenv": "dotenv"}.get(module_name, module_name)
    return importlib.util.find_spec(real_name) is not None


for category, packages in PACKAGE_CATEGORIES.items():
    print(f"\n  {category}:")
    for pkg in packages:
        installed = is_installed(pkg)
        print(f"    {pkg:20s}: {'✓ installed' if installed else '✗ missing'}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Final Readiness Report
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Readiness Report")
print("=" * 70)

print(f"\n  ✓ OK   ({len(REPORT['ok'])})")
for item in REPORT["ok"]:
    print(f"    - {item}")

print(f"\n  ⚠ WARN ({len(REPORT['warn'])})")
for item in REPORT["warn"]:
    print(f"    - {item}")

print(f"\n  ✗ FAIL ({len(REPORT['fail'])})")
for item in REPORT["fail"]:
    print(f"    - {item}")

if REPORT["fail"]:
    print("\n  Verdict: fix the FAIL items before relying on this environment for the")
    print("  rest of Level 1-8 — most practicals assume these basics are already true.")
elif REPORT["warn"]:
    print("\n  Verdict: workable, but the WARN items will block some practicals from")
    print("  running live (they'll fall back to mock mode instead).")
else:
    print("\n  Verdict: fully ready. Every practical in this repo should run live.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Fix every FAIL item this script found. Re-run until FAIL is empty.

MEDIUM:
2. Add a check for whether you're inside a virtual environment
   (sys.prefix != sys.base_prefix) — installing packages globally is a
   common early mistake this doc warns about.

HARD:
3. Extend PACKAGE_CATEGORIES with the RAG/Vector DB and Search Tools
   packages this doc's "Essential Packages" section lists, and re-run.

PRO:
4. Turn this into a `pytest` suite (`test_environment.py`) so CI can fail
   a PR if a teammate's setup is missing a required key or package — this
   is literally what a real onboarding-check script looks like in production.
""")

if __name__ == "__main__":
    print("\nDone. Next: 07_first_api_calls_practical.py")
