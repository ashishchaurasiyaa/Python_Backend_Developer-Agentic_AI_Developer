"""
Level 6 -- Doc 6: Reflection Pattern (PRACTICAL -- Hinglish Style)
===================================================================
KYA SEEKHENGE (What you will learn):
  1. Basic Reflection Loop  -- generate -> critique -> revise
  2. Structured Critique    -- rubric-based scoring (ACCURACY, COMPLETENESS, etc.)
  3. Code Reflection        -- code generate karo, self-review karo, refine karo
  4. Reflexion with Memory  -- episodic memory of past failures (Shinn et al. 2023)
  5. Convergence Detection  -- infinite loop ko rokne ka tarika
  6. Cost Trade-off Demo    -- 2-3x cost ka math samjho

KAISE CHALANA (How to run):
  # Offline demo (no key needed):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python Level6_Agent_Patterns/06_reflection_pattern_practical.py

  # Live LLM calls (Groq free tier):
  GROQ_API_KEY=gsk_xxx uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python Level6_Agent_Patterns/06_reflection_pattern_practical.py

THEORY GROUNDING (06_reflection_pattern.md):
  - Reflection = LLM apna output review + critique karta hai, phir revise karta hai
  - Empirical win: coding tasks mein +15-25% pass rate (Reflexion paper)
  - Trade-off: 2-3x cost for one query -- high-stakes ke liye worth it
  - Always cap iterations -- infinite loops = LLM cost bombs
"""

# ---- Standard imports (sab available hain, koi heavy optional nahi) ----
import os
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional

# ---- Groq client setup ----
# IMPORTANT: OpenAI() constructor None key par CRASH karta hai.
# Isliye hum api_key=os.getenv("GROQ_API_KEY") or "placeholder" dete hain.
# Groq ka OpenAI-compatible endpoint use karte hain -- same API, free tier.

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = GROQ_API_KEY != "placeholder"

# Groq endpoint constants
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.1-8b-instant"  # free tier mein available


def get_client():
    """
    Groq client return karo (OpenAI-compatible).
    RULE: api_key kabhi None nahi hona chahiye -- OpenAI() crash karta hai None par.
    Isliye 'placeholder' fallback use karte hain.
    """
    from openai import OpenAI
    return OpenAI(
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
    )


def llm_call(prompt: str, system: str = "You are a helpful assistant.", max_tokens: int = 500) -> str:
    """
    Single LLM call wrapper.
    LIVE_MODE mein Groq call karta hai, warna fake response deta hai.
    Graceful degradation -- no key = offline demo, EXIT 0 guarantee.
    """
    if not LIVE_MODE:
        # Offline mode -- placeholder response return karo
        # Real code mein yahi pattern use hoga, bas LLM call replace hoga
        return f"[OFFLINE] Response to: {prompt[:80]}..."

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        # API error gracefully handle karo
        return f"[LLM_ERROR: {e}] Falling back to offline mode."


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Basic Reflection Loop
# THEORY: Question -> Initial Answer -> Critique -> Refined Answer
# Ek hi model, teen steps -- generate, critique, revise
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("REFLECTION PATTERN -- Level 6 Practical")
print("Mode:", "LIVE (Groq)" if LIVE_MODE else "OFFLINE (no key -- demo data)")
print("=" * 65)

print("\n" + "=" * 65)
print("SECTION 1: Basic Reflection Loop")
print("=" * 65)

# CONCEPT PRINT -- theory se seedha liya gaya
print("""
  Theory se (06_reflection_pattern.md):
  Without reflection:   Question -> Answer  (one-shot, galat ho sakta hai)
  With reflection:      Question -> Draft -> Critique -> Refined Answer

  Empirical wins:
    Coding tasks: +15-25% pass rate (Reflexion paper, Shinn et al. 2023)
    Math reasoning: +10-20% accuracy

  Trade-off: 2-3x cost. High-stakes tasks ke liye worth it.
""")


def generate_answer(question: str, previous_answer: str = None, critique: str = None) -> str:
    """
    Answer generate karo (ya refine karo critique ke basis par).
    Pehli baar: question directly answer karo.
    Baad mein: previous answer + critique ke saath improve karo.
    """
    if previous_answer is None:
        # Initial generation -- seedha question ka jawab
        prompt = f"Answer this question clearly and concisely:\n\n{question}"
    else:
        # Refinement -- critique ko address karo
        prompt = (
            f"Question: {question}\n\n"
            f"Previous answer:\n{previous_answer}\n\n"
            f"Critique of previous answer:\n{critique}\n\n"
            f"Now provide an improved answer that addresses all the critique points."
        )

    return llm_call(prompt, system="You are an expert assistant. Be accurate and clear.")


def critique_answer(question: str, answer: str) -> str:
    """
    Answer ko critically review karo.
    THEORY: Different angle se dekhne par errors pakde jaate hain.
    'If answer is good, say PASS' -- convergence detection ke liye.
    """
    prompt = (
        f"Critique this answer critically:\n\n"
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Identify: [1] Factual errors, [2] Missing info, [3] Unclear parts.\n"
        f"Be specific. If the answer is good enough, say 'PASS' at the start."
    )
    return llm_call(prompt, system="You are a strict but fair critic. Be specific about issues.")


def basic_reflection_loop(question: str, max_iterations: int = 3) -> dict:
    """
    Core reflection loop implement karo.
    THEORY se: max_iterations ZAROORI hai -- infinite loops = cost bomb!
    Convergence check: 'PASS' keyword = accept karo aur ruko.
    """
    print(f"\n  Question: '{question}'")
    print(f"  Max iterations: {max_iterations}")

    # Step 1: Initial answer generate karo
    answer = generate_answer(question)
    print(f"\n  [Draft Answer]\n  {answer[:120]}...")

    history = []

    for i in range(max_iterations):
        print(f"\n  --- Iteration {i + 1}/{max_iterations} ---")

        # Step 2: Critique karo
        critique = critique_answer(question, answer)
        print(f"  [Critique]\n  {critique[:150]}...")

        # Step 3: Convergence check -- PASS matlab accept karo
        if critique.upper().startswith("PASS") or "PASS" in critique[:10].upper():
            print(f"  Converged at iteration {i + 1} -- 'PASS' mila, loop rok rahe hain.")
            break

        # Step 4: Critique ke basis par revise karo
        history.append({"iteration": i + 1, "critique": critique[:100]})
        answer = generate_answer(question, previous_answer=answer, critique=critique)
        print(f"  [Revised Answer]\n  {answer[:120]}...")

    return {
        "question": question,
        "final_answer": answer,
        "iterations_done": len(history),
        "history": history,
    }


# Live ya offline demo run karo
result1 = basic_reflection_loop(
    question="Explain Python's Global Interpreter Lock (GIL) in simple terms.",
    max_iterations=2,
)
print(f"\n  Final answer (after {result1['iterations_done']} iterations):")
print(f"  {result1['final_answer'][:200]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Structured Critique (Rubric-Based)
# THEORY: Vague critique kaam nahi karta -- specific dimensions score karo
# Rubric: ACCURACY, COMPLETENESS, CLARITY, RELEVANCE, SUPPORT
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Structured Critique (Rubric-Based)")
print("=" * 65)

print("""
  THEORY: Vague critique problems:
    - "Looks good" bolna = iteration waste
    - "Bad answer" bolna = kya fix karein?

  Solution: Structured rubric with specific dimensions (1-10 score each):
    ACCURACY    -- Claims factually sahi hain?
    COMPLETENESS-- Key points cover hue?
    CLARITY     -- Samajhne mein aasan hai?
    RELEVANCE   -- Actual question ka jawab diya?
    SUPPORT     -- Reasoning/examples hain?

  Threshold: avg score >= 8 -> ACCEPT, warna revise karo.
""")

# CRITIQUE_RUBRIC -- theory doc se liya gaya
CRITIQUE_RUBRIC = """
Evaluate this answer on these FIVE dimensions (score 1-10 each):

1. ACCURACY    : Are all claims factually correct?
2. COMPLETENESS: Are all key points covered?
3. CLARITY     : Is it easy to understand?
4. RELEVANCE   : Does it directly answer the question?
5. SUPPORT     : Are claims backed by reasoning or examples?

Format your response EXACTLY as:
ACCURACY: <score>/10 -- <brief reason>
COMPLETENESS: <score>/10 -- <brief reason>
CLARITY: <score>/10 -- <brief reason>
RELEVANCE: <score>/10 -- <brief reason>
SUPPORT: <score>/10 -- <brief reason>
AVG_SCORE: <average>/10
VERDICT: ACCEPT (if avg >= 8) or REVISE (if avg < 8)
SUGGESTIONS: <specific improvements if REVISE>
"""


def structured_critique(question: str, answer: str) -> dict:
    """
    Rubric-based structured critique karo.
    Return: parsed scores + verdict + suggestions.
    """
    prompt = f"{CRITIQUE_RUBRIC}\n\nQuestion: {question}\n\nAnswer: {answer}"
    raw_critique = llm_call(prompt, system="You are a structured evaluator. Follow the format exactly.", max_tokens=400)

    # Parse scores from response
    scores = {}
    import re
    for dim in ["ACCURACY", "COMPLETENESS", "CLARITY", "RELEVANCE", "SUPPORT"]:
        match = re.search(rf"{dim}:\s*(\d+)/10", raw_critique)
        scores[dim] = int(match.group(1)) if match else 7  # default 7 if parsing fails

    # Verdict parse karo
    verdict = "ACCEPT" if "ACCEPT" in raw_critique.upper() else "REVISE"
    avg_score = sum(scores.values()) / len(scores) if scores else 0

    return {
        "raw": raw_critique,
        "scores": scores,
        "avg_score": round(avg_score, 1),
        "verdict": verdict,
    }


def structured_reflection_loop(question: str, max_iterations: int = 3) -> dict:
    """
    Structured critique ke saath reflection loop.
    THEORY: Score threshold par ruko -- quality guarantee karta hai.
    """
    print(f"\n  Question: '{question}'")

    answer = generate_answer(question)
    print(f"\n  [Draft]\n  {answer[:100]}...")

    for i in range(max_iterations):
        critique_result = structured_critique(question, answer)
        scores = critique_result["scores"]
        avg = critique_result["avg_score"]
        verdict = critique_result["verdict"]

        print(f"\n  Iteration {i + 1} scores: {scores}")
        print(f"  Avg score: {avg}/10 | Verdict: {verdict}")

        if verdict == "ACCEPT":
            print(f"  Quality threshold met (avg >= 8). Ruk rahe hain.")
            break

        # Suggestions ke saath revise karo
        answer = generate_answer(question, previous_answer=answer, critique=critique_result["raw"])
        print(f"  [Revised]\n  {answer[:100]}...")

    return {"final_answer": answer, "final_scores": critique_result["scores"]}


# Offline mode mein mock structured critique dikhate hain
print("\n  Structured Critique -- Offline Demo:")
demo_question = "What is asyncio in Python?"
demo_answer = "asyncio is for async programming."

# Mock structured critique output (offline)
mock_scores = {
    "ACCURACY": 8, "COMPLETENESS": 4, "CLARITY": 7, "RELEVANCE": 8, "SUPPORT": 3
}
mock_avg = sum(mock_scores.values()) / len(mock_scores)
print(f"\n  Demo answer: '{demo_answer}'")
print(f"  Scores: {mock_scores}")
print(f"  Avg: {mock_avg:.1f}/10 -- REVISE needed (avg < 8)")
print(f"  Issue: COMPLETENESS (4/10) -- examples missing, internals explain nahi kiye")

if LIVE_MODE:
    result2 = structured_reflection_loop(demo_question, max_iterations=2)
    print(f"\n  Final answer: {result2['final_answer'][:150]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Code Reflection Pattern
# THEORY: Generate code -> Self-review -> Fix -> Repeat
# Jab "READY" mile tab ruko. Yahi Cursor/Cline/Devin internally karte hain!
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: Code Reflection Pattern")
print("=" * 65)

print("""
  THEORY: Code reflection = generate -> self-review -> fix loop

  Ye kaise kaam karta hai:
    1. LLM code generate karta hai
    2. LLM apna code review karta hai (bugs, edge cases, improvements)
    3. Agar "READY" mile -> accept karo
    4. Warna issues fix karo aur repeat

  Real-world use: Cursor, Cline, Devin internally yahi karte hain!
  Reflexion paper (Shinn 2023): coding tasks mein +15-25% pass rate.
""")


def generate_code(spec: str, previous_code: str = None, issues: str = None) -> str:
    """
    Code generate karo ya previous code ko fix karo.
    """
    if previous_code is None:
        prompt = f"Write Python code for this specification:\n\n{spec}\n\nWrite clean, working Python code only."
    else:
        prompt = (
            f"Specification: {spec}\n\n"
            f"Previous code:\n```python\n{previous_code}\n```\n\n"
            f"Issues found:\n{issues}\n\n"
            f"Rewrite the code fixing all issues. Return only the Python code."
        )
    return llm_call(prompt, system="You are an expert Python developer. Write clean, correct code.", max_tokens=600)


def review_code(spec: str, code: str) -> str:
    """
    Code ko review karo -- bugs, edge cases, improvements dhundo.
    THEORY: 'READY' keyword = convergence signal
    """
    prompt = (
        f"Review this Python code:\n\n"
        f"Specification: {spec}\n\n"
        f"Code:\n```python\n{code}\n```\n\n"
        f"List specific issues: bugs, missing edge cases, improvements needed.\n"
        f"If code is correct and handles edge cases, say 'READY' as the first word."
    )
    return llm_call(prompt, system="You are a senior code reviewer. Be specific about issues.", max_tokens=300)


def code_reflection_loop(spec: str, max_iterations: int = 3) -> dict:
    """
    Code reflection loop -- THEORY doc ka exact pattern implement kiya.
    'READY' keyword par convergence.
    """
    print(f"\n  Spec: '{spec}'")

    code = generate_code(spec)
    print(f"\n  [Generated Code]\n  {code[:200]}...")

    for i in range(max_iterations):
        review = review_code(spec, code)
        print(f"\n  Iteration {i + 1} Review: {review[:120]}...")

        # READY = code theek hai, ruko
        if review.strip().upper().startswith("READY"):
            print(f"  Code accepted at iteration {i + 1}!")
            break

        # Issues fix karo
        code = generate_code(spec, previous_code=code, issues=review)
        print(f"  [Revised Code]\n  {code[:150]}...")

    return {"spec": spec, "final_code": code}


# Mock code reflection demo (offline mode)
print("\n  Code Reflection -- Offline Demo:")

MOCK_CODE_V1 = """\
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""

MOCK_REVIEW_V1 = """\
Issues found:
1. No input validation -- negative numbers pe infinite recursion
2. No type hints
3. Exponential time complexity O(2^n) -- memoization missing
4. n=0 aur n=1 ke edge cases test nahi kiye
Fix: add type hints, input validation, aur use memoization (lru_cache).
"""

MOCK_CODE_V2 = """\
from functools import lru_cache

def fibonacci(n: int) -> int:
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")

    @lru_cache(maxsize=None)
    def _fib(k: int) -> int:
        if k <= 1:
            return k
        return _fib(k-1) + _fib(k-2)

    return _fib(n)
"""

MOCK_REVIEW_V2 = "READY -- Code handles edge cases, has type hints, and uses memoization efficiently."

print(f"  Spec: 'Write fibonacci function'")
print(f"\n  [V1 Code]\n{MOCK_CODE_V1}")
print(f"  [Review V1]\n  {MOCK_REVIEW_V1}")
print(f"\n  [V2 Code]\n{MOCK_CODE_V2}")
print(f"  [Review V2]\n  {MOCK_REVIEW_V2}")
print(f"\n  Result: READY mila -- accepted after 1 revision!")

if LIVE_MODE:
    result3 = code_reflection_loop(
        spec="Write a Python function to check if a string is a palindrome (handle spaces and case)",
        max_iterations=2,
    )
    print(f"\n  LIVE Final code:\n{result3['final_code']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Reflexion with Episodic Memory (Shinn et al. 2023)
# THEORY: Basic reflection ek task ke liye hai.
# Reflexion = past failures yaad rakhta hai, similar tasks mein use karta hai.
# Memory = lessons learned from failures
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Reflexion with Episodic Memory")
print("=" * 65)

print("""
  INTERVIEW Q5 se (theory doc):
  Basic Reflection: single-task generate-critique-revise.
  Reflexion:        episodic memory add karo -- past failures + lessons store karo.
                    Similar tasks mein in lessons ko use karo.

  Paper: Shinn et al. 2023 -- "Reflexion: Language Agents with Verbal Reinforcement Learning"

  Memory structure:
    trial      -> attempt number
    attempt    -> kya kiya tha
    feedback   -> kyu fail hua
    lesson     -> future ke liye seekha kya
""")


@dataclass
class ReflexionMemory:
    """Episodic memory -- past failures aur lessons store karta hai."""
    episodes: list = field(default_factory=list)

    def add_episode(self, trial: int, attempt: str, feedback: str, lesson: str):
        self.episodes.append({
            "trial": trial,
            "attempt": attempt[:100],  # truncate for memory efficiency
            "feedback": feedback[:100],
            "lesson": lesson,
        })

    def get_lessons(self) -> str:
        """Past lessons format karo -- LLM ke liye context."""
        if not self.episodes:
            return "No previous lessons."
        lessons = [f"- Trial {e['trial']}: {e['lesson']}" for e in self.episodes]
        return "\n".join(lessons)

    def count(self) -> int:
        return len(self.episodes)


def reflexion_attempt(task: str, memory: ReflexionMemory) -> str:
    """
    Task attempt karo -- past lessons ko context mein dalo.
    THEORY: 'Apply lessons to solve correctly' -- past mistakes avoid karo.
    """
    lessons = memory.get_lessons()
    prompt = (
        f"Past lessons from previous failures:\n{lessons}\n\n"
        f"New task: {task}\n\n"
        f"Apply the lessons above to solve this correctly. "
        f"Avoid the mistakes mentioned in lessons."
    )
    return llm_call(prompt, system="You are an expert who learns from past mistakes.", max_tokens=400)


def evaluate_attempt(task: str, attempt: str) -> tuple:
    """
    Attempt evaluate karo -- success hai ya nahi.
    Return: (success: bool, feedback: str)
    Offline mode: mock evaluation.
    """
    prompt = (
        f"Task: {task}\n\nAttempt: {attempt}\n\n"
        f"Evaluate if this attempt successfully solves the task.\n"
        f"Reply with: SUCCESS or FAILURE\n"
        f"Then explain WHY in one sentence."
    )
    response = llm_call(prompt, system="You are an objective evaluator.", max_tokens=150)
    success = "SUCCESS" in response.upper()
    return success, response


def reflect_on_failure(task: str, attempt: str, feedback: str) -> str:
    """
    Failure ko analyze karo -- reusable lesson nikalo.
    THEORY: 'Distill failure into a reusable lesson.'
    """
    prompt = (
        f"Task: {task}\n\n"
        f"My attempt:\n{attempt}\n\n"
        f"Why it failed:\n{feedback}\n\n"
        f"What ONE specific lesson should I remember for similar tasks? "
        f"Be concise and actionable."
    )
    return llm_call(prompt, system="You are a reflective teacher extracting lessons.", max_tokens=150)


def reflexion_agent(task: str, max_trials: int = 3) -> dict:
    """
    Full Reflexion agent -- paper ke algorithm ko implement kiya.
    Memory accumulate karta hai across trials.
    """
    memory = ReflexionMemory()
    print(f"\n  Task: '{task}'")
    print(f"  Max trials: {max_trials}")

    for trial in range(max_trials):
        print(f"\n  --- Trial {trial + 1}/{max_trials} ---")
        print(f"  Memory episodes: {memory.count()}")

        # Step 1: Attempt (with memory)
        attempt = reflexion_attempt(task, memory)
        print(f"  [Attempt]\n  {attempt[:120]}...")

        # Step 2: Evaluate
        success, feedback = evaluate_attempt(task, attempt)
        print(f"  [Evaluation]\n  {'SUCCESS' if success else 'FAILURE'}: {feedback[:100]}...")

        if success:
            print(f"\n  Task solved at trial {trial + 1}!")
            return {"status": "success", "trial": trial + 1, "answer": attempt, "memory": memory}

        # Step 3: Reflect on failure -- lesson extract karo
        lesson = reflect_on_failure(task, attempt, feedback)
        print(f"  [Lesson]\n  {lesson[:100]}...")

        # Step 4: Memory mein add karo
        memory.add_episode(trial + 1, attempt, feedback, lesson)

    return {"status": "failed", "trial": max_trials, "memory": memory}


# Offline Reflexion demo
print("\n  Reflexion -- Offline Demo (Memory Accumulation):")

demo_memory = ReflexionMemory()

# Trial 1: Fail
demo_memory.add_episode(
    trial=1,
    attempt="Sort karte hain simple bubble sort se.",
    feedback="FAILURE: Edge case miss kiya -- empty list pe crash.",
    lesson="Hamesha empty list/None input validate karo before processing."
)

# Trial 2: Fail (par pehle se better)
demo_memory.add_episode(
    trial=2,
    attempt="Empty check add kiya, phir sort kiya.",
    feedback="FAILURE: Single element list ke liye unnecessarily loop chala.",
    lesson="len(lst) <= 1 check karo -- already sorted hota hai."
)

print(f"\n  Memory after 2 failed trials:")
print(f"  {demo_memory.get_lessons()}")
print(f"\n  Trial 3 attempt will USE these lessons to avoid same mistakes.")

if LIVE_MODE:
    result4 = reflexion_agent(
        task="Write a Python function to find the second largest number in a list",
        max_trials=3,
    )
    status = result4["status"]
    trial_done = result4["trial"]
    mem = result4["memory"]
    print(f"\n  LIVE Result: {status} at trial {trial_done}")
    print(f"  Lessons learned: {mem.count()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Convergence Detection Patterns
# THEORY: Common Pitfalls section se -- infinite loops ko avoid karo
# 4 tarike hain convergence detect karne ke
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Convergence Detection Patterns")
print("=" * 65)

print("""
  THEORY (Common Pitfalls from doc):
  Pitfall 1: Infinite loops -- koi convergence detection nahi
  Fix: Multiple convergence signals use karo:

    Method A: Keyword check     -- "PASS" / "READY" / "NO ISSUES" detect karo
    Method B: Score threshold   -- Avg score >= 8/10 -> stop
    Method C: Hard iteration cap-- max_iterations ALWAYS set karo
    Method D: Delta check       -- agar changes bahut small hain -> stop
""")


def convergence_method_a_keyword(critique_text: str) -> bool:
    """Method A: Keyword-based convergence."""
    stop_keywords = {"PASS", "READY", "NO ISSUES", "ACCEPTABLE", "LOOKS GOOD"}
    upper_critique = critique_text.upper()
    found = any(kw in upper_critique for kw in stop_keywords)
    return found


def convergence_method_b_score(avg_score: float, threshold: float = 8.0) -> bool:
    """Method B: Score threshold-based convergence."""
    return avg_score >= threshold


def convergence_method_d_delta(answer_v1: str, answer_v2: str, min_change_ratio: float = 0.05) -> bool:
    """
    Method D: Delta-based convergence.
    Agar naye answer mein bahut kam change hai -> stop.
    """
    # Simple heuristic: character overlap ratio
    len1, len2 = len(answer_v1), len(answer_v2)
    if len1 == 0 or len2 == 0:
        return True  # edge case

    # Common prefix length (approximate)
    common = sum(1 for a, b in zip(answer_v1, answer_v2) if a == b)
    change_ratio = 1 - (common / max(len1, len2))
    converged = change_ratio < min_change_ratio
    return converged


# Demo convergence methods
print("\n  Demo: Convergence Method A (Keyword)")
examples_a = [
    ("This is PASS -- answer looks great!", True),
    ("Missing examples, needs more detail.", False),
    ("READY -- code handles all edge cases.", True),
    ("Incomplete answer, please elaborate.", False),
]
for text, expected in examples_a:
    result = convergence_method_a_keyword(text)
    status = "OK" if result == expected else "WRONG"
    icon = "CONVERGE" if result else "CONTINUE"
    print(f"  [{status}] '{text[:50][:50]}' -> {icon}")

print("\n  Demo: Convergence Method B (Score Threshold)")
score_examples = [
    (9.2, True),
    (7.8, False),
    (8.0, True),
    (5.5, False),
]
for score, expected in score_examples:
    result = convergence_method_b_score(score)
    status = "OK" if result == expected else "WRONG"
    icon = "CONVERGE" if result else "CONTINUE"
    print(f"  [{status}] Avg score {score}/10 -> {icon}")

print("\n  Demo: Convergence Method D (Delta Check)")
v1 = "Python GIL prevents multiple threads from executing Python bytecodes at once."
v2 = "Python GIL prevents multiple threads from executing Python bytecodes at once."  # identical
v3 = "Python GIL is a mutex that protects access to Python objects, preventing multiple threads."
converged_same = convergence_method_d_delta(v1, v2)
converged_diff = convergence_method_d_delta(v1, v3)
print(f"  Identical answers -> Converged: {converged_same}  (expected: True)")
print(f"  Changed answers   -> Converged: {converged_diff}  (expected: False)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Cost Trade-off Math
# THEORY: 2-3x cost ka math samjho -- kab reflect karna worth it hai
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: Cost Trade-off -- Kab Use Karein Reflection?")
print("=" * 65)

print("""
  THEORY (Cost Math from doc):
  One-shot cost = question_tokens * INPUT_COST + answer_tokens * OUTPUT_COST
  Per iteration adds:
    - Critique: (question + answer) tokens as input + critique tokens as output
    - Refinement: (question + answer + critique) input + new answer output

  Typical: 2-3x cost of single shot.
  Latency: 3-4x (sequential calls).
""")


def estimate_reflection_cost(
    question_tokens: int,
    answer_tokens: int,
    critique_tokens: int = 200,
    iterations: int = 2,
    input_cost_per_1k: float = 0.0001,   # Groq free tier approximate
    output_cost_per_1k: float = 0.0002,
) -> dict:
    """
    Reflection ka estimated cost calculate karo.
    THEORY doc ka exact formula implement kiya.
    """
    def cost(inp, out):
        return (inp / 1000) * input_cost_per_1k + (out / 1000) * output_cost_per_1k

    # One-shot cost
    one_shot = cost(question_tokens, answer_tokens)

    # Reflection cost per iteration:
    # Critique: input = question + answer, output = critique
    critique_cost = cost(question_tokens + answer_tokens, critique_tokens)
    # Refinement: input = question + answer + critique, output = revised answer
    refine_cost = cost(question_tokens + answer_tokens + critique_tokens, answer_tokens)
    per_iter_cost = critique_cost + refine_cost

    total_reflection = one_shot + iterations * per_iter_cost
    multiplier = total_reflection / one_shot if one_shot > 0 else 0

    return {
        "one_shot_usd": round(one_shot, 6),
        "per_iteration_usd": round(per_iter_cost, 6),
        "total_reflection_usd": round(total_reflection, 6),
        "cost_multiplier": round(multiplier, 2),
        "iterations": iterations,
    }


# Ek realistic example chalate hain
cost_result = estimate_reflection_cost(
    question_tokens=50,    # "Explain Python GIL" = ~50 tokens
    answer_tokens=200,     # Ek paragraph = ~200 tokens
    critique_tokens=150,   # Critique = ~150 tokens
    iterations=2,
)
print(f"\n  Example: 'Explain Python GIL' with 2 iterations")
print(f"  One-shot cost:      ${cost_result['one_shot_usd']:.6f}")
print(f"  Per-iteration add:  ${cost_result['per_iteration_usd']:.6f}")
print(f"  Total reflection:   ${cost_result['total_reflection_usd']:.6f}")
print(f"  Cost multiplier:    {cost_result['cost_multiplier']}x")

print("""
  THEORY -- Kab Use Karein (When to USE):
    OK  : Code generation (testable, +15-25% pass rate)
    OK  : Math / reasoning (verifiable steps)
    OK  : Critical Q&A (high stakes -- business consequences)
    OK  : Writing tasks (quality > speed)

  THEORY -- Kab Skip Karein (When NOT to USE):
    SKIP: Real-time chat (2-3x latency = unacceptable)
    SKIP: Pure knowledge retrieval -- reflection adds facts nahi karta
    SKIP: Creative generation (subjective critique creativity hurt karta hai)
    SKIP: Cost-sensitive scale par
    SKIP: Simple tasks jahan model already great hai
""")

# Mitigation strategies
print("  Mitigation strategies (theory se):")
mitigations = [
    "Difficulty classification -- reflect only on hard queries",
    "Confidence check -- high confidence = skip reflection",
    "Cheap models use karo -- generator + critic dono ke liye",
    "Parallel reflection branches -- jab possible ho",
    "Hard iteration cap -- ALWAYS set max_iterations",
]
for m in mitigations:
    print(f"    - {m}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Common Pitfalls Reference
# THEORY: 7 pitfalls directly from doc -- interview mein poochhe jaate hain
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: Common Pitfalls -- Interview Reference")
print("=" * 65)

PITFALLS = [
    (
        "Infinite loops",
        "NAHI kiya: koi convergence detection nahi",
        "KARO: Always set max_iterations, 'PASS' keyword check karo",
    ),
    (
        "Critic too lenient",
        "NAHI kiya: 'looks good' bad answers pe bhi",
        "KARO: Structured rubric use karo, examples of bad outputs do",
    ),
    (
        "Critic too strict",
        "NAHI kiya: hamesha issues dhundhta hai, loop kabhi nahi rokta",
        "KARO: 'If acceptable, say PASS' explicitly prompt mein likho",
    ),
    (
        "Reflection on cheap tasks",
        "NAHI kiya: har query pe reflect karna = money waste",
        "KARO: Hard / high-stakes tasks pe hi reflect karo",
    ),
    (
        "Same model for gen + critic",
        "NAHI kiya: same biases, same mistakes, critic kuch nahi pakdega",
        "KARO: Different models use karo when possible",
    ),
    (
        "Vague critic role",
        "NAHI kiya: 'is this good?' -- useless critique",
        "KARO: 'Score X/10 on Y dimension' -- structured prompts",
    ),
    (
        "Not measuring improvement",
        "NAHI kiya: assume kar lena ki reflection helps",
        "KARO: A/B test reflection on/off, quality measure karo",
    ),
]

for i, (pitfall, bad, good) in enumerate(PITFALLS, 1):
    print(f"\n  Pitfall {i}: {pitfall}")
    print(f"    GALAT: {bad}")
    print(f"    SAHI : {good}")


# ─────────────────────────────────────────────────────────────────────────────
# INTERVIEW QUICK REFERENCE
# Theory doc ke 5 interview questions -- concise answers
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("INTERVIEW QUICK REFERENCE (theory doc se)")
print("=" * 65)

INTERVIEW_QA = [
    (
        "Q1: Reflection pattern kya hai?",
        "Generate -> Critique -> Revise loop. LLM apna output evaluate karke improve karta hai. "
        "2-3x tokens lagte hain. Code, math, critical Q&A mein sabse effective.",
    ),
    (
        "Q2: Generator aur critic ke liye alag model kyu?",
        "Different models ke different blind spots hote hain. GPT-4 generate kare, Claude critique kare "
        "-- critic woh errors pakdega jo generator miss kar gaya. Trade-off: cost + multi-vendor complexity.",
    ),
    (
        "Q3: Kab reflection NAHI karna chahiye?",
        "Pure retrieval/recall (facts add nahi ho sakte), real-time chat (latency too high), "
        "creative writing (subjective critique creativity hurt karti hai), simple tasks jahan model already great hai.",
    ),
    (
        "Q4: Infinite loops kaise rokein?",
        "(1) Hard cap max_iterations (3-5). (2) Keyword convergence ('PASS'/'READY'). "
        "(3) Score threshold (stop when avg > 8/10). (4) Delta check (bahut kam change = stop).",
    ),
    (
        "Q5: Reflexion vs Basic Reflection kya fark hai?",
        "Basic reflection: single task ke liye generate-critique-revise. "
        "Reflexion (Shinn 2023): episodic memory add karo -- past failures + lessons store, "
        "similar future tasks mein use karo. Agents ke liye zyada powerful.",
    ),
]

for q, a in INTERVIEW_QA:
    print(f"\n  {q}")
    print(f"  A: {a}")

# ─────────────────────────────────────────────────────────────────────────────
# SENIOR MANTRAS (from doc)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SENIOR MANTRAS (theory doc se word-for-word)")
print("=" * 65)

MANTRAS = [
    "1. Reflect on hard/critical outputs. Skip for cheap tasks.",
    "2. Always cap iterations. Loops are LLM cost bombs.",
    "3. Different models for gen + critic = better catches.",
    "4. Structured rubrics > vague 'is this good?'",
    "5. Reflection adds 2-3x cost. Worth it for high-stakes.",
    "6. Combine with testing for code (Devin/Cursor pattern).",
    "7. Convergence detection prevents infinite loops.",
    "8. Measure improvement. Don't just assume reflection helps.",
    "9. Reflexion (with memory) > basic reflection for agents.",
    "10. For latency-tight apps: skip reflection or do async.",
]
for m in MANTRAS:
    print(f"  {m}")

print("\n" + "=" * 65)
print("REFLECTION PATTERN PRACTICAL -- COMPLETE")
print("Mode was:", "LIVE (Groq LLM)" if LIVE_MODE else "OFFLINE (mock data, no API needed)")
print("Sections covered:")
print("  1. Basic Reflection Loop (generate -> critique -> revise)")
print("  2. Structured Critique (rubric-based scoring)")
print("  3. Code Reflection (READY keyword convergence)")
print("  4. Reflexion with Episodic Memory (Shinn 2023)")
print("  5. Convergence Detection (4 methods)")
print("  6. Cost Trade-off Math (2-3x cost formula)")
print("  7. Common Pitfalls (7 pitfalls + fixes)")
print("=" * 65)
