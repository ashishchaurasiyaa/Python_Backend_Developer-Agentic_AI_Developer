"""
LAB 4 — Week 3 CAPSTONE: Mini Engineering Team jo REAL CODE FILES likhti hai (L61-L67)
=======================================================================================

KYA SEEKHENGE (Hinglish):
- Ed Donner ke course me Week 3 ka climax yahi hai: ek "engineering team" crew —
  Engineering Lead design banata hai, Backend Engineer pura Python module likhta hai,
  Test Engineer uske liye unittest file likhta hai. Sab kuch DISK par actual files
  ke roop me land hota hai (sirf chat output nahi!).
- Task CONTEXT CHAINING: task2 ko task1 ka design milta hai, task3 ko task2 ka code —
  ye CrewAI ka `context=[...]` parameter hai (sequential process me data pipeline).
- LLM-generated code ka SELF-VERIFICATION: kickoff ke baad script khud
  compile() se syntax-check karti hai aur subprocess se unittest chalati hai.
  Ye asli "agentic engineering" lesson hai — LLM output ko kabhi blindly trust
  mat karo, hamesha programmatically verify karo.

COURSE vs HUMARA LAB (important Hinglish notes):
- MEMORY (course Day 4, ~L63-L64): course me Crew(memory=True) dikhaya jata hai —
  CrewAI internally ShortTermMemory (RAG/ChromaDB vectors), LongTermMemory (SQLite)
  aur EntityMemory rakhta hai. Default embeddings OpenAI ke hote hain, aur hamari
  OPENAI_API_KEY INVALID hai (401 dega) — isliye hum memory SKIP kar rahe hain.
  Alternative jo try kar sakte ho (Google embeddings ke saath):
      Crew(..., memory=True,
           embedder={"provider": "google",
                     "config": {"model": "text-embedding-004",
                                "api_key": os.getenv("GOOGLE_API_KEY")}})
- CODE EXECUTION (course Day 5, ~L65-L66): course me coder Agent ko
  `allow_code_execution=True` diya jata hai — CrewAI tab code ko ek DOCKER
  container me safely run karta hai (sandboxing). Humare paas Docker setup nahi,
  isliye hum SKIP kar rahe — INSTEAD hum khud post-hoc verification karte hain
  (compile + unittest subprocess), jo honestly production me zyada common pattern hai.
- YAML CONFIG: Ed course me @CrewBase decorator + agents.yaml/tasks.yaml use hota
  hai (config code se alag). Hamare labs self-contained code-style me hain taaki
  ek file me sab samajh aa jaye — concepts bilkul same hain.

KAISE CHALANA:
    cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
    uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab4_engineering_team.py

OUTPUT FILES (is script ke folder me ./output/):
    design.md         — Engineering Lead ka detailed design document
    accounts.py       — Backend Engineer ka likha hua Python module
    test_accounts.py  — Test Engineer ki unittest file

LECTURES: L61-L67 (Week 3 Day 4-5: engineering team project, memory, coder agents, capstone)
"""

import os
import re
import sys
import time
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# .env se GROQ_API_KEY load karo (override=True = shell env se .env jeet jata hai)
load_dotenv(override=True)

# Telemetry band — CrewAI by default anonymized telemetry bhejta hai; speed + privacy
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Task, Crew, Process, LLM  # noqa: E402

# ---------------------------------------------------------------------------
# PATHS — sab outputs is lab ke bagal wale ./output folder me jayenge
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
DESIGN_FILE = OUTPUT_DIR / "design.md"
MODULE_FILE = OUTPUT_DIR / "accounts.py"
TEST_FILE = OUTPUT_DIR / "test_accounts.py"

# ---------------------------------------------------------------------------
# LLM — sab agents FREE Groq par. Course me "groq/model" LiteLLM string format
# dikhta hai, par is CrewAI version (1.14.x) me litellm optional extra hai —
# installed nahi. KOI BAAT NAHI: Groq ka API OpenAI-COMPATIBLE hai, isliye hum
# explicit provider="openai" + base_url ko Groq endpoint par point kar dete hain
# (CrewAI tab native OpenAI SDK client use karta hai, Groq ke against).
# (Agar litellm installed ho to LLM(model="groq/llama-3.3-70b-versatile") bhi chalta.)
# temperature low rakha hai kyunki CODE generation me determinism chahiye.
# ---------------------------------------------------------------------------
groq_llm = LLM(
    model="llama-3.3-70b-versatile",
    provider="openai",  # native OpenAI-compatible route — model-name validation bypass
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2,
)

# ---------------------------------------------------------------------------
# REQUIREMENT — Ed course ka classic example: trading simulation Account class.
# Fixed test prices isliye diye hain taaki Test Engineer deterministic asserts likh sake.
# ---------------------------------------------------------------------------
REQUIREMENT = (
    "Ek simple Account class for a trading simulation platform. Features: "
    "create account with initial deposit; deposit funds; withdraw funds "
    "(balance negative nahi ho sakta); buy and sell shares by symbol+quantity "
    "(buy tabhi jab paise hon, sell tabhi jab shares hon); report holdings; "
    "compute total portfolio value; compute profit/loss vs total deposits. "
    "Module me ek module-level helper function get_share_price(symbol) bhi ho "
    "jo FIXED test prices return kare: AAPL=150.0, TSLA=800.0, GOOGL=2500.0 "
    "(unknown symbol par ValueError). Pure standard library, koi external dependency nahi."
)


def build_crew() -> tuple[Crew, Task, Task, Task]:
    """3-agent engineering team banao: Lead -> Backend -> Test (sequential pipeline)."""

    # AGENT 1: Engineering Lead — role/goal/backstory hi CrewAI ka prompting model hai.
    # Backstory me "tum kaun ho" persona dalte hain — LLM us character me sochta hai.
    engineering_lead = Agent(
        role="Engineering Lead",
        goal=(
            "Take a high-level requirement and produce a crisp, detailed, "
            "unambiguous technical design that a backend engineer can implement "
            "without asking any questions."
        ),
        backstory=(
            "You are a seasoned engineering lead at a fintech startup. You are "
            "famous for writing design documents so precise that implementations "
            "match them on the first try. You always specify exact class names, "
            "method signatures with type hints, behaviors, and edge cases."
        ),
        llm=groq_llm,
        verbose=True,
    )

    # AGENT 2: Backend Engineer — course me ise allow_code_execution=True milta
    # (Docker sandbox me code run karke khud test karta). Hum wo skip kar rahe —
    # iska kaam sirf clean module likhna hai, verification HUM script me karenge.
    backend_engineer = Agent(
        role="Senior Backend Engineer",
        goal=(
            "Implement the given design as a single, complete, production-quality "
            "Python module. Output must be pure Python source code only."
        ),
        backstory=(
            "You are a senior Python backend engineer with 10 years of experience. "
            "You write clean, well-documented, defensive code with type hints and "
            "docstrings. You follow designs exactly and never leave TODOs or stubs."
        ),
        llm=groq_llm,
        verbose=True,
    )

    # AGENT 3: Test Engineer — module ke against unittest file likhega.
    test_engineer = Agent(
        role="Test Engineer",
        goal=(
            "Write a thorough Python unittest test file for the given module that "
            "runs cleanly with 'python -m unittest'. Output pure Python code only."
        ),
        backstory=(
            "You are a meticulous QA/test engineer. You only test behavior that "
            "actually exists in the code you are given — you never invent methods "
            "or assume behaviors not present in the implementation."
        ),
        llm=groq_llm,
        verbose=True,
    )

    # TASK 1: Design document. {requirement} placeholder kickoff(inputs=...) se fill hota hai.
    design_task = Task(
        description=(
            "Requirement: {requirement}\n\n"
            "Write a detailed technical DESIGN document in markdown for a single "
            "Python module named `accounts.py`. Include:\n"
            "1. Overview of the module.\n"
            "2. Every class with exact name, every method with exact signature "
            "(including type hints), and a one-line behavior description.\n"
            "3. The module-level function get_share_price(symbol: str) -> float "
            "with the fixed prices AAPL=150.0, TSLA=800.0, GOOGL=2500.0.\n"
            "4. Edge cases and the exceptions raised (e.g. ValueError for "
            "overdraft, insufficient shares, unknown symbol).\n"
            "Keep it implementable by one engineer in one file, stdlib only."
        ),
        expected_output=(
            "A markdown design document with exact class/method signatures, "
            "behaviors, and edge cases for accounts.py."
        ),
        agent=engineering_lead,
    )

    # TASK 2: Implementation. context=[design_task] => task1 ka pura output
    # is task ke prompt me inject hota hai. Yahi CrewAI ka data-pipeline glue hai.
    # NOTE: "no markdown fences" instruction + hum defensively strip bhi karenge,
    # kyunki LLMs aadat se ```python fences daal hi dete hain.
    code_task = Task(
        description=(
            "Using the design document from the engineering lead, implement the "
            "COMPLETE Python module `accounts.py`.\n"
            "STRICT RULES:\n"
            "- Output ONLY raw Python source code. No markdown, no ``` fences, "
            "no explanations before or after the code.\n"
            "- Implement EVERY class and method from the design, fully working — "
            "no stubs, no TODOs, no 'pass' placeholders.\n"
            "- Include get_share_price(symbol) with fixed prices "
            "AAPL=150.0, TSLA=800.0, GOOGL=2500.0 and ValueError for unknown symbols.\n"
            "- Use only the Python standard library.\n"
            "- The module must be importable as `accounts` (it will be saved as accounts.py)."
        ),
        expected_output=(
            "The complete raw Python source code of accounts.py, nothing else."
        ),
        agent=backend_engineer,
        context=[design_task],
    )

    # TASK 3: Tests. context=[code_task] => Test Engineer ko EXACT generated code
    # dikhega (design nahi) — taaki wo sirf real implemented behavior test kare.
    test_task = Task(
        description=(
            "You are given the full source code of the module accounts.py (from "
            "the backend engineer). Write a Python unittest test file named "
            "test_accounts.py for it.\n"
            "STRICT RULES:\n"
            "- Output ONLY raw Python source code. No markdown, no ``` fences, "
            "no explanations.\n"
            "- Import the module under test as: from accounts import ... "
            "(the file sits next to accounts.py).\n"
            "- Use only `import unittest` style tests (classes extending "
            "unittest.TestCase) and end the file with:\n"
            "  if __name__ == '__main__':\n      unittest.main()\n"
            "- ONLY test methods and behaviors that actually exist in the given "
            "code, with the exact signatures shown. Use the fixed share prices "
            "(AAPL=150.0, TSLA=800.0, GOOGL=2500.0) for deterministic asserts.\n"
            "- ARITHMETIC CHECK: before every buy in a test, make sure the "
            "account balance is ENOUGH (e.g. start accounts with a large "
            "deposit like 100000.0). Double-check every expected value "
            "calculation against the fixed prices before writing the assert.\n"
            "- Cover: deposit, withdraw (including overdraft error), buy/sell "
            "shares (including insufficient funds/shares errors), portfolio "
            "value, and profit/loss."
        ),
        expected_output=(
            "The complete raw Python source code of test_accounts.py, nothing else."
        ),
        agent=test_engineer,
        context=[code_task],
    )

    # CREW: sequential process => tasks order me chalenge, context chain ke saath.
    # (Course me yahi crew @CrewBase class + YAML config se banti hai — same concepts.)
    crew = Crew(
        agents=[engineering_lead, backend_engineer, test_engineer],
        tasks=[design_task, code_task, test_task],
        process=Process.sequential,
        verbose=True,
        # memory=True YAHAN NAHI — default OpenAI embeddings chahiye hote (401 for us).
        # Google embedder alternative upar module docstring me likha hai.
    )
    return crew, design_task, code_task, test_task


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def strip_code_fences(text: str) -> str:
    """LLM output se markdown fences DEFENSIVELY hatao.

    Humne prompt me bola hai 'no fences', par LLMs phir bhi ```python ... ```
    wrap kar dete hain. Agar fenced block mila to sabse LAMBA block uthao
    (asli code wahi hota hai), warna stray ``` lines drop kar do.
    """
    text = text.strip()
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip() + "\n"


def kickoff_with_retry(crew: Crew, inputs: dict, attempts: int = 3):
    """Free Groq tier kabhi-kabhi rate-limit/transient error deta hai — simple retry."""
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            return crew.kickoff(inputs=inputs)
        except Exception as exc:  # noqa: BLE001 — lab me graceful failure chahiye
            last_err = exc
            wait = 20 * attempt
            print(f"[retry] Attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                print(f"[retry] {wait}s wait karke dobara try...")
                time.sleep(wait)
    raise RuntimeError(f"Crew kickoff failed after {attempts} attempts: {last_err}")


def syntax_check(path: Path) -> tuple[bool, str]:
    """compile() se syntax-check — bina execute kiye (py_compile jaisa hi)."""
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        return True, "OK"
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc.msg} (line {exc.lineno})"


def run_unittests(output_dir: Path) -> tuple[bool, str]:
    """Generated tests ko SUBPROCESS me chalao.

    - cwd=output_dir => `python -m unittest` me sys.path[0] = output dir,
      isliye test file `from accounts import ...` resolve kar payegi.
    - sys.executable use kar rahe (hum already uv-managed venv me hain),
      isliye dobara `uv run` bootstrap karne ki zaroorat nahi.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "test_accounts", "-v"],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        # unittest apna report STDERR par print karta hai
        report = (proc.stderr or "") + (proc.stdout or "")
        return proc.returncode == 0, report.strip()
    except subprocess.TimeoutExpired:
        return False, "Tests timed out after 120s (possible infinite loop in generated code)."
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not run tests: {exc}"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY missing in .env — lab nahi chal sakta.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("LAB 4: ENGINEERING TEAM CAPSTONE — design -> code -> tests -> verify")
    print("=" * 70)

    # -------- PHASE 1: Crew chalao (3 LLM tasks, sequential) ----------------
    crew, design_task, code_task, test_task = build_crew()
    kickoff_with_retry(crew, inputs={"requirement": REQUIREMENT})

    # -------- PHASE 2: Outputs ko disk par likho ----------------------------
    # NOTE: CrewAI me Task(output_file="...") bhi hota hai (course me dikhta hai),
    # par wo raw output as-is dump karta hai — hum khud likh rahe hain taaki
    # fence-stripping post-processing apply kar saken (zyada reliable for code).
    design_md = design_task.output.raw.strip() + "\n"
    module_code = strip_code_fences(code_task.output.raw)
    test_code = strip_code_fences(test_task.output.raw)

    DESIGN_FILE.write_text(design_md, encoding="utf-8")
    MODULE_FILE.write_text(module_code, encoding="utf-8")
    TEST_FILE.write_text(test_code, encoding="utf-8")

    # -------- PHASE 3: SELF-VERIFICATION (yahi asli kicker hai) -------------
    # Course me ye kaam coder-agent Docker me khud karta (allow_code_execution=True);
    # hum deterministic script-level verification kar rahe hain.
    module_ok, module_msg = syntax_check(MODULE_FILE)
    tests_syntax_ok, tests_msg = syntax_check(TEST_FILE)

    tests_passed, test_report = (False, "Skipped (syntax error in generated files).")
    if module_ok and tests_syntax_ok:
        tests_passed, test_report = run_unittests(OUTPUT_DIR)

    # -------- PHASE 4: Final summary ----------------------------------------
    print("\n" + "=" * 70)
    print("FINAL SUMMARY — LAB 4 ENGINEERING TEAM")
    print("=" * 70)
    print("Files created:")
    for path in (DESIGN_FILE, MODULE_FILE, TEST_FILE):
        size = path.stat().st_size if path.exists() else 0
        print(f"  - {path}  ({size} bytes)")
    print(f"accounts.py syntax check     : {'PASS' if module_ok else 'FAIL — ' + module_msg}")
    print(f"test_accounts.py syntax check: {'PASS' if tests_syntax_ok else 'FAIL — ' + tests_msg}")
    print(f"unittest run                 : {'PASS' if tests_passed else 'FAIL'}")

    if tests_passed:
        # Report ki last lines (e.g. "Ran 8 tests ... OK") dikhate hain
        tail = "\n".join(test_report.splitlines()[-3:])
        print("\nTest report (tail):\n" + tail)
        print("\nSUCCESS: agent-generated code compiled AND its own tests passed!")
    else:
        # LESSON: LLM-generated code imperfect ho sakta hai — crash nahi karte,
        # details print karte hain. Real agentic systems me yahan ek
        # "fix-it loop" hota: failure report wapas Backend Engineer ko bhejte.
        print("\ngenerated code needs fixing — details below:")
        print("-" * 70)
        print(test_report[-3000:] if test_report else "(no report)")
        print("-" * 70)
        print(
            "NOTE: Ye bhi ek lesson hai — LLM code hamesha perfect nahi hota. "
            "Course me Docker-based allow_code_execution agent ko khud iterate "
            "karne deta hai; production me aap failure ko wapas agent ko feed "
            "karke fix-loop banate ho."
        )


if __name__ == "__main__":
    main()
