"""
Level 2 — Doc 4: Chain-of-Thought (PRACTICAL)
==============================================
Topics:
  1. Zero-shot CoT — magic phrase
  2. Few-shot CoT — examples with reasoning
  3. Hide CoT from user with XML tags
  4. Self-consistency — run N times + vote
  5. Structured CoT with Pydantic + Instructor
  6. CoT accuracy comparison (with vs without)

Install: pip install openai instructor pydantic python-dotenv
Run: python 04_chain_of_thought_practical.py
"""

import os
import re
from collections import Counter
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def llm_call(prompt: str, temperature: float = 0, max_tokens: int = 500, system: Optional[str] = None) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from openai import OpenAI
        client = OpenAI()
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error: {e}]"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Zero-Shot CoT — Magic Phrase
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Zero-Shot CoT — 'Let's think step by step'")
print("=" * 70)

PROBLEMS = [
    "A bat and ball cost $1.10. The bat costs $1 more than the ball. How much is the ball?",
    "If 5 workers build a wall in 8 days, how many workers needed to build the same wall in 4 days?",
    "A store offers 20% discount, then 10% tax. What's the final price of a $100 item?",
    "I have $50, spend 1/5 on lunch, then 30% of remaining on movie. How much left?"
]

for prob in PROBLEMS:
    print(f"\nProblem: {prob}")
    no_cot = llm_call(f"{prob}\nAnswer:", max_tokens=50)
    with_cot = llm_call(f"{prob}\nLet's think step by step.", max_tokens=400)
    print(f"  Without CoT: {no_cot[:80]}")
    print(f"  With CoT:    {with_cot[:200]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Few-Shot CoT
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Few-Shot CoT (Examples with Reasoning)")
print("=" * 70)

few_shot_cot = """Solve word problems showing each step.

Q: If 3 pens cost $9, how much for 7 pens?
A:
Step 1: 1 pen = $9 / 3 = $3
Step 2: 7 pens = $3 × 7 = $21
Answer: $21

Q: A box has 12 apples. Eat 3, add 5 more, split between 2 friends. How many each?
A:
Step 1: Start = 12 apples
Step 2: Eat 3 → 12 - 3 = 9
Step 3: Add 5 → 9 + 5 = 14
Step 4: Split between 2 → 14 / 2 = 7
Answer: 7 each

Q: A train travels 60 km in 1 hour. How far in 2.5 hours?
A:"""

result = llm_call(few_shot_cot, max_tokens=300)
print(result)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Hide CoT from User (Production Pattern)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Hide CoT — XML Tags for Production")
print("=" * 70)

prompt_hidden_cot = """Reason step by step, then give your final answer.

Format your response EXACTLY as:
<thinking>
your reasoning here
</thinking>
<answer>
final answer only
</answer>

Question: A pizza is cut into 8 slices. I eat 3, my friend eats 2. What fraction is left?"""

response = llm_call(prompt_hidden_cot, max_tokens=400)
print(f"Full LLM output:\n{response}\n")

# Parse out final answer only
def extract_answer(text: str) -> str:
    match = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)
    return match.group(1).strip() if match else text


def extract_thinking(text: str) -> str:
    match = re.search(r"<thinking>(.*?)</thinking>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


print("=" * 50)
print(f"User sees (clean): {extract_answer(response)}")
print(f"Logs/debug (hidden): {extract_thinking(response)[:100]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Self-Consistency CoT
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Self-Consistency — Run N Times, Vote on Answer")
print("=" * 70)


def extract_numeric_answer(text: str) -> Optional[str]:
    """Extract the final numeric answer from CoT output."""
    # Try to find "Answer: X" pattern
    match = re.search(r"(?:answer|final)[^:]*:\s*\$?([\d.]+)", text.lower())
    if match:
        return match.group(1).strip(".")
    # Try last number in text
    nums = re.findall(r"\$?[\d.]+", text)
    return nums[-1].lstrip("$").rstrip(".") if nums else None


def self_consistency_cot(question: str, n_runs: int = 5) -> dict:
    """Run CoT N times with temperature, return most-voted answer."""
    prompt = f"{question}\nLet's think step by step. Final answer at the end as 'Answer: X'."
    answers = []
    for _ in range(n_runs):
        result = llm_call(prompt, temperature=0.7, max_tokens=300)
        ans = extract_numeric_answer(result)
        if ans:
            answers.append(ans)
    if not answers:
        return {"answer": None, "votes": {}, "runs": n_runs}
    votes = Counter(answers)
    best = votes.most_common(1)[0]
    return {
        "answer": best[0],
        "confidence": best[1] / n_runs,
        "votes": dict(votes),
        "runs": n_runs
    }


hard_problem = "A farmer has chickens and cows. He counts 30 heads and 80 legs. How many chickens?"
print(f"\nProblem: {hard_problem}")
result = self_consistency_cot(hard_problem, n_runs=5)
print(f"  Most voted answer: {result['answer']}")
print(f"  Confidence: {result.get('confidence', 0) * 100:.0f}%")
print(f"  All votes: {result['votes']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Structured CoT with Pydantic (using Instructor)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Structured CoT — Pydantic + Instructor")
print("=" * 70)


def structured_cot_demo():
    """Force LLM to output reasoning_steps + final_answer as Pydantic model."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    try:
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field

        class CoTAnswer(BaseModel):
            reasoning_steps: list[str] = Field(description="Step-by-step reasoning")
            final_answer: str = Field(description="The final answer only")
            confidence: float = Field(description="0-1 confidence in answer")

        client = instructor.from_openai(OpenAI())
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=CoTAnswer,
            messages=[
                {"role": "user", "content": "If a car covers 240 km in 3 hours, what's its speed in m/s?"}
            ]
        )

        print(f"Reasoning steps:")
        for i, step in enumerate(response.reasoning_steps, 1):
            print(f"  {i}. {step}")
        print(f"Final answer: {response.final_answer}")
        print(f"Confidence: {response.confidence}")
    except ImportError:
        print("Install: pip install instructor")
    except Exception as e:
        print(f"Error: {e}")


structured_cot_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Accuracy Comparison (No CoT vs CoT vs Self-Consistency)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Accuracy Comparison")
print("=" * 70)

# Test set: problem → expected answer (numeric)
TEST_SET = [
    ("A bat and ball cost $1.10. Bat is $1 more than ball. Ball cost?", "0.05"),
    ("3 pens cost $9. How much for 7?", "21"),
    ("$100 with 20% off then 10% tax?", "88"),
    ("12 apples, eat 3, add 5, split between 2. Each gets?", "7"),
]

print("\nProblem | NoCoT | CoT | Expected")
print("-" * 60)
for prob, expected in TEST_SET:
    no_cot = llm_call(f"{prob} Just answer with a number.", max_tokens=20)
    cot = llm_call(f"{prob} Let's think step by step. End with 'Answer: X'.", max_tokens=300)
    no_cot_ans = extract_numeric_answer(no_cot) or "?"
    cot_ans = extract_numeric_answer(cot) or "?"
    print(f"  {prob[:35]:35s} | {no_cot_ans:6s} | {cot_ans:6s} | {expected}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Test "step by step" on 20 math problems. Compute accuracy boost.
2. Hide CoT using <thinking>/<answer> tags. Build a clean user-facing chat.

MEDIUM:
3. Implement self-consistency for 5 problems. Compare 1-run vs 5-run accuracy.
4. Build structured CoT with Pydantic. Validate confidence scores.

HARD:
5. Implement Tree of Thoughts for a planning problem (knapsack, route planning).
6. Build a CoT debugger — show user how LLM arrived at wrong answer.

PRO:
7. Compare gpt-4o-mini + CoT vs o1-mini (reasoning model). Cost vs accuracy.
""")

if __name__ == "__main__":
    print("\n✅ Try modifying problems and observe reasoning quality!")
