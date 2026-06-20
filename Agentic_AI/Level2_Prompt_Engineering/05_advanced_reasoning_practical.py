"""
Level 2 — Doc 5: Advanced Reasoning (PRACTICAL)
================================================
Topics:
  1. Self-consistency with parallel calls
  2. Self-critique pipeline
  3. Reflexion (learn from failures)
  4. Tree of Thoughts (mini implementation)
  5. Model routing (classify → cheap/expensive model)

Install: pip install openai python-dotenv
Run: python 05_advanced_reasoning_practical.py
"""

import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def llm_call(prompt: str, temperature: float = 0, max_tokens: int = 500,
             model: str = "gpt-4o-mini", system: Optional[str] = None) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from openai import OpenAI
        client = OpenAI()
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error: {e}]"


def extract_number(text: str) -> Optional[str]:
    """Find the final numeric answer."""
    match = re.search(r"(?:answer|final|=)[^:=]*[:=]\s*\$?([\d.]+)", text.lower())
    if match:
        return match.group(1).strip(".")
    nums = re.findall(r"\$?[\d.]+", text)
    return nums[-1].lstrip("$").rstrip(".") if nums else None


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Self-Consistency (Parallel)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Self-Consistency — Parallel N Runs + Vote")
print("=" * 70)


def self_consistency_parallel(question: str, n_runs: int = 5) -> dict:
    """Run N CoT chains in parallel, vote on answer."""
    prompt = f"{question}\nLet's think step by step. End with 'Answer: X'."

    with ThreadPoolExecutor(max_workers=n_runs) as ex:
        futures = [ex.submit(llm_call, prompt, 0.7, 400) for _ in range(n_runs)]
        outputs = [f.result() for f in futures]

    answers = [extract_number(o) for o in outputs if extract_number(o)]
    if not answers:
        return {"answer": None, "votes": {}, "runs": n_runs}

    votes = Counter(answers)
    best, count = votes.most_common(1)[0]
    return {
        "answer": best,
        "confidence": count / n_runs,
        "votes": dict(votes),
        "all_outputs": outputs
    }


hard = "A farmer has chickens and cows. He counts 30 heads and 80 legs total. How many chickens?"
print(f"\nProblem: {hard}")
result = self_consistency_parallel(hard, n_runs=5)
print(f"  Best answer: {result['answer']}")
print(f"  Confidence: {result.get('confidence', 0) * 100:.0f}%")
print(f"  Vote distribution: {result['votes']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Self-Critique Pipeline
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Self-Critique — Generate → Critique → Revise")
print("=" * 70)


def self_critique_pipeline(question: str) -> dict:
    """3-step pipeline: answer → critique → revise."""
    # Step 1: Initial answer
    initial = llm_call(question, max_tokens=300)

    # Step 2: Critique
    critique_prompt = f"""You are a strict reviewer. Critique this answer harshly.

Question: {question}
Answer: {initial}

What's wrong? What's missing? What's unclear? Be specific.
If the answer is perfect, say "PERFECT" exactly."""
    critique = llm_call(critique_prompt, max_tokens=300)

    # Step 3: Revise (only if needed)
    if "PERFECT" in critique.upper():
        return {"initial": initial, "critique": critique, "revised": initial, "improved": False}

    revise_prompt = f"""Question: {question}
Initial answer: {initial}
Critique: {critique}

Provide an improved answer that addresses every critique point. Be thorough."""
    revised = llm_call(revise_prompt, max_tokens=500)

    return {
        "initial": initial,
        "critique": critique,
        "revised": revised,
        "improved": True
    }


task = "Write a Python function to find the largest palindrome in a string."
print(f"\nTask: {task}")
result = self_critique_pipeline(task)
print(f"\nInitial:\n{result['initial'][:300]}\n")
print(f"Critique:\n{result['critique'][:200]}\n")
if result["improved"]:
    print(f"Revised:\n{result['revised'][:300]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Reflexion — Learn from Failures
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Reflexion — Agent Learns from Past Failures")
print("=" * 70)


def reflexion_loop(task: str, evaluator, max_attempts: int = 3):
    """Task → attempt → reflect on failure → retry with notes."""
    lessons_learned = []

    for attempt in range(1, max_attempts + 1):
        # Build prompt with accumulated lessons
        hints = "\n".join(f"- {note}" for note in lessons_learned)
        # backslash f-string EXPRESSION ke bahar rakho — warna Python <=3.11 pe SyntaxError
        lessons_block = ("Past lessons:\n" + hints) if lessons_learned else ""
        prompt = f"""Task: {task}

{lessons_block}

Provide your solution:"""

        solution = llm_call(prompt, max_tokens=500)
        success, feedback = evaluator(solution)

        print(f"\n  Attempt {attempt}:")
        print(f"    Solution: {solution[:150]}...")
        print(f"    Success: {success}, Feedback: {feedback}")

        if success:
            return {"solution": solution, "attempts": attempt, "lessons": lessons_learned}

        # Reflect on failure
        reflection_prompt = f"""Task: {task}
Failed attempt: {solution}
Feedback: {feedback}

What went wrong? What's the key lesson for next attempt? One sentence."""
        lesson = llm_call(reflection_prompt, max_tokens=100)
        lessons_learned.append(lesson)

    return {"solution": None, "attempts": max_attempts, "lessons": lessons_learned}


# Simple evaluator example: check if Python code mentions specific function
def palindrome_evaluator(solution: str):
    """Check if solution mentions a palindrome function and uses Python."""
    has_palindrome = "palindrome" in solution.lower()
    has_python = "def " in solution and "return" in solution
    handles_edge = "len" in solution.lower() or "empty" in solution.lower()

    if has_palindrome and has_python and handles_edge:
        return True, "All criteria met"
    missing = []
    if not has_palindrome: missing.append("no palindrome logic")
    if not has_python: missing.append("not Python")
    if not handles_edge: missing.append("doesn't handle edge cases")
    return False, ", ".join(missing)


task = "Write a Python function to detect if a string is a palindrome. Handle empty/single char."
print(f"\nTask: {task}")
result = reflexion_loop(task, palindrome_evaluator, max_attempts=3)
print(f"\nFinal: {result['attempts']} attempts, success: {result['solution'] is not None}")
print(f"Lessons learned: {result['lessons']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Tree of Thoughts (Mini) — 24 Game
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Tree of Thoughts (Mini) — Math Reasoning")
print("=" * 70)


def tot_for_24_game(numbers: list[int], depth: int = 4) -> str:
    """Use ToT-style branching to solve 24 game.

    Asks LLM to generate K moves at each step, evaluates, picks best.
    Simplified version — real ToT does pruning, parallel branches.
    """
    state_history = [str(numbers)]
    current = numbers.copy()

    for step in range(depth):
        if len(current) == 1:
            break

        # Generate K candidate moves
        gen_prompt = f"""Current numbers: {current}
Goal: Combine 2 numbers using +, -, ×, ÷ to get closer to 24.

Suggest 3 different moves. Format:
1. A op B = C → new state
2. ...
3. ..."""
        moves_text = llm_call(gen_prompt, temperature=0.8, max_tokens=200)

        # Pick best move (evaluator: LLM scores closeness to 24)
        eval_prompt = f"""Given these moves toward goal 24:
{moves_text}

Which move is BEST (most likely to reach 24)? Output JUST the number (1, 2, or 3)."""
        best_idx = llm_call(eval_prompt, max_tokens=5).strip()

        state_history.append(f"Chose move {best_idx}: {moves_text}")
        # In real ToT, we'd parse the move and apply it to update `current`
        # For this demo, just track the reasoning
        break  # Simplified: one level deep

    return "\n".join(state_history)


numbers = [3, 5, 6, 8]
print(f"\nGoal: Make 24 from {numbers}")
result = tot_for_24_game(numbers)
print(result[:500])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Model Routing (Cost Optimization)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Model Routing — Cheap Classifier + Right Model")
print("=" * 70)


def classify_difficulty(query: str) -> str:
    """Use a cheap LLM call to classify difficulty."""
    prompt = f"""Classify difficulty of this query:
- SIMPLE: lookup, single fact, easy translation
- MEDIUM: multi-step reasoning, basic code, analysis
- HARD: complex math, algorithms, multi-step planning

Output ONE word: SIMPLE, MEDIUM, or HARD.

Query: "{query}"
Difficulty:"""
    return llm_call(prompt, model="gpt-4o-mini", max_tokens=10).strip().upper()


def route_and_answer(query: str) -> dict:
    """Classify → route to appropriate model."""
    difficulty = classify_difficulty(query)
    model_map = {
        "SIMPLE": "gpt-4o-mini",
        "MEDIUM": "gpt-4o-mini",  # Use "gpt-4o" in production
        "HARD": "gpt-4o-mini",    # Use "o1-mini" in production
    }
    chosen = model_map.get(difficulty, "gpt-4o-mini")

    if difficulty == "MEDIUM":
        prompt = f"{query}\nLet's think step by step."
    else:
        prompt = query

    answer = llm_call(prompt, model=chosen, max_tokens=300)
    return {"difficulty": difficulty, "model": chosen, "answer": answer}


queries = [
    "What is the capital of France?",       # SIMPLE
    "If 3 pens cost $9, how much for 7?",   # MEDIUM
    "Implement Dijkstra's algorithm in Python",  # HARD
]

for q in queries:
    r = route_and_answer(q)
    print(f"\nQuery: {q}")
    print(f"  → Classified: {r['difficulty']} → Model: {r['model']}")
    print(f"  → Answer: {r['answer'][:150]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Run self-consistency on 10 math problems. Plot accuracy by N (1, 3, 5, 10).
2. Build self-critique for code generation. Compare initial vs revised quality.

MEDIUM:
3. Implement Reflexion with a real evaluator (e.g., does code compile + pass tests).
4. Build a routing system: cheap/medium/expensive model based on user query.

HARD:
5. Implement full Tree of Thoughts for 24-game. Backtracking + pruning.
6. Compare gpt-4o-mini + self-consistency (N=5) vs o1-mini on hard problems.
   Which gives better cost-vs-accuracy ratio?

PRO:
7. Build a "smart router" that:
   - Classifies query
   - Routes to right model
   - Uses self-consistency for medium-hard
   - Uses self-critique for code
   - Logs cost per query and tracks accuracy
""")

if __name__ == "__main__":
    print("\n✅ Experiment with combinations of patterns!")
