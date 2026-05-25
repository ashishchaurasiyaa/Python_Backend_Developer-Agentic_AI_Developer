# Level 2 — Doc 4: Chain-of-Thought (CoT) Prompting

> **Goal:** LLM se step-by-step reasoning karwana. Most powerful single technique for math/logic/multi-step problems.

---

## 1. Chain-of-Thought Kya Hai?

**CoT** = LLM ko force karna **answer dene se pehle steps explain karne**.

Without CoT:
```
Q: A bat and ball cost $1.10. Bat costs $1 more than ball. Ball price?
A: $0.10  ❌ Wrong
```

With CoT:
```
Q: A bat and ball cost $1.10. Bat costs $1 more than ball. Ball price? 
   Let's think step by step.
A: 
Let ball = x, bat = x + $1
Total: x + (x + 1) = 1.10
2x + 1 = 1.10
2x = 0.10
x = $0.05  ✅ Correct
```

**Why it works:** LLMs are autoregressive (predict one token at a time). Reasoning steps **constrain the search space** — each step makes the next more accurate.

---

## 2. Three Types of CoT

### A. Zero-Shot CoT (Easiest)
Just append magic phrase:
- "Let's think step by step."
- "Think carefully."
- "Reason through this."

```python
prompt = f"{question}\nLet's think step by step."
```

### B. Few-Shot CoT (More Control)
Show 2-3 examples WITH reasoning:

```python
prompt = """
Q: If a car travels 60 km/h for 3 hours, how far does it go?
A: Step 1: Speed = 60 km/h. Step 2: Time = 3 hours. Step 3: Distance = speed × time = 60 × 3 = 180 km.

Q: If 5 workers build a wall in 8 days, how many workers to build in 4 days?
A: Step 1: Total work = 5 × 8 = 40 worker-days. Step 2: For 4 days, need 40/4 = 10 workers.

Q: A train leaves at 9 AM at 60 km/h, another at 10 AM at 80 km/h same direction. When do they meet?
A:
"""
```

### C. CoT with Self-Consistency (Advanced)
- Run same prompt N times with `temperature > 0`
- Get multiple reasoning paths
- **Vote** on the most common answer
- Reduces hallucination

```python
def cot_self_consistency(prompt, n=5):
    answers = []
    for _ in range(n):
        result = llm_call(prompt, temperature=0.7)
        answers.append(extract_answer(result))
    return Counter(answers).most_common(1)[0][0]
```

---

## 3. When CoT Helps (And When Not)

### ✅ HELPS:
- Math / arithmetic problems
- Multi-step logical reasoning
- Code debugging (trace execution)
- Word problems
- Comparing options
- Causal reasoning
- Planning tasks

### ❌ DOESN'T HELP (might even hurt):
- Simple factual lookups ("Capital of France?")
- Classification tasks (use few-shot instead)
- Translation (just slows it down)
- Creative writing
- Reasoning models (o1, o3) — they reason internally already

---

## 4. Reasoning Models (o1, o3, Claude Extended Thinking)

**2025-26 paradigm shift:** OpenAI's o1/o3 series + Anthropic's "Extended Thinking" — these models **automatically do CoT internally**.

### Key differences:
| Old way | New (reasoning models) |
|---|---|
| Add "step by step" | Don't need to (model does it) |
| Use few-shot CoT | Often hurts (model reasons better alone) |
| Show your work | Don't — wastes tokens |
| Standard prompts | Use minimal, clear prompts |

### Anthropic Extended Thinking (Claude 3.7+):
```python
response = anthropic.messages.create(
    model="claude-3-7-sonnet-20250219",
    thinking={"type": "enabled", "budget_tokens": 16000},  # Internal reasoning budget
    messages=[{"role": "user", "content": "Hard math problem"}]
)
# Model thinks internally, returns final answer
```

### OpenAI o1/o3:
```python
response = openai.chat.completions.create(
    model="o1",
    messages=[{"role": "user", "content": "Hard math problem"}]
    # No "step by step" needed — o1 reasons internally
)
```

**Cost:** Reasoning models are 5-10x more expensive. Use only for hard problems.

---

## 5. CoT Patterns Library

### Pattern A: Numbered Steps
```
Step 1: [Identify what we know]
Step 2: [Identify what we need]
Step 3: [Calculate intermediate values]
Step 4: [Combine to get final answer]

Final answer: X
```

### Pattern B: Question Decomposition
```
Sub-question 1: ...
Sub-answer 1: ...
Sub-question 2: ...
Sub-answer 2: ...

Final answer: [combine]
```

### Pattern C: First Principles
```
What do we know?
- Fact 1
- Fact 2

What can we derive?
- Derivation 1
- Derivation 2

Conclusion: ...
```

### Pattern D: Compare-and-Decide
```
Option A: pros/cons
Option B: pros/cons
Option C: pros/cons

Best choice: B because...
```

---

## 6. Force CoT with Output Schema

Tum chaho ki LLM **always** reason kare? Schema force karo:

```python
from pydantic import BaseModel

class CoTAnswer(BaseModel):
    reasoning_steps: list[str]
    final_answer: str

# Using Instructor library
import instructor
client = instructor.from_openai(OpenAI())

response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_model=CoTAnswer,
    messages=[{"role": "user", "content": "What is 23% of 480?"}]
)

print(response.reasoning_steps)
print(response.final_answer)
```

---

## 7. CoT Gotchas (Real-World)

### Gotcha 1: Increased Cost
CoT = more output tokens = more cost. A "Yes/No" answer might become 200 tokens.

### Gotcha 2: Slower Responses
More tokens = slower. For chatbots, this hurts UX.

**Solution:** Hide CoT from user. Return only final answer.

```python
prompt = """
Reason step by step, then give your final answer.

Format your response as:
<thinking>your reasoning</thinking>
<answer>final answer only</answer>

Question: ...
"""

# Parse out <thinking>, show only <answer> to user
```

### Gotcha 3: CoT Can Be Wrong
LLM may reason confidently but incorrectly. Always **validate critical outputs**.

### Gotcha 4: Stale Knowledge in CoT
LLM may "reason" using outdated facts (e.g., "Donald Trump is the current president..." — could be wrong now). For factual queries, use **RAG** instead of CoT.

---

## 8. CoT for Different Domains

### Math
```
"Calculate: If a store sells items at 20% discount, then 10% tax, what's the final price of a $100 item?"

CoT:
Step 1: Original = $100
Step 2: Apply 20% discount → $100 × 0.80 = $80
Step 3: Apply 10% tax → $80 × 1.10 = $88
Final: $88
```

### Code Debugging
```
"Why does this code raise an error: def f(x): return x + 1 / 0"

CoT:
Step 1: Identify operations: x + (1 / 0)
Step 2: Operator precedence: / runs before +
Step 3: 1 / 0 → ZeroDivisionError
Conclusion: Division by zero before addition
```

### Decision Making
```
"Should I use SQL or NoSQL for my e-commerce app?"

CoT:
Consideration 1: Data relationships (orders→users→products are relational) → SQL favored
Consideration 2: Scale (10K users) → either works
Consideration 3: Transactions (payments) → SQL ACID critical
Consideration 4: Team skills (SQL experience) → SQL easier
Conclusion: PostgreSQL — relational nature + transactions are the deciding factors
```

---

## 9. Combining CoT with Few-Shot (Most Powerful)

```python
prompt = """
Solve word problems by showing your steps.

Q: If 3 pens cost $9, how much for 7 pens?
A: 
Step 1: 1 pen = $9 / 3 = $3
Step 2: 7 pens = $3 × 7 = $21
Answer: $21

Q: A box has 12 apples. If you eat 3, then add 5 more, then split equally among 2 friends, how many each?
A:
Step 1: Start = 12 apples
Step 2: Eat 3 → 12 - 3 = 9
Step 3: Add 5 → 9 + 5 = 14
Step 4: Split between 2 → 14 / 2 = 7
Answer: 7 each

Q: A train travels 60 km in 1 hour. How far in 2.5 hours?
A:
"""
```

---

## 10. Tree of Thoughts (ToT) — Beyond Linear CoT

CoT = linear (step → step → step)
**ToT** = explore multiple branches, prune bad ones

```
Problem: Maximize profit from these 5 items in 10kg backpack.

Branch A: Item 1 + 2 → 8kg, $50
  Branch A1: Add item 3 (4kg) → over capacity, prune
  Branch A2: Add item 4 (2kg) → 10kg, $70 ✓
Branch B: Item 1 + 3 → 9kg, $60
  ...

Best: Branch A2, $70
```

This is overkill for most tasks. Use only for complex planning.

---

## 11. Interview Questions

1. **Q: Why does CoT work?**
   - Autoregressive nature — each token conditions on previous. Reasoning steps constrain search.

2. **Q: When to use CoT vs reasoning models (o1)?**
   - Standard models + CoT: Best for moderate problems, cheaper
   - o1/o3: Hard problems, math, code. 5-10x cost but better quality.

3. **Q: What's "self-consistency"?**
   - Run N times with temperature, vote on most common answer. Reduces hallucination.

4. **Q: How do you hide CoT from end user?**
   - Use XML tags `<thinking>...</thinking><answer>...</answer>`. Parse out, show only answer.

---

## 12. Exercises

1. **Easy:** Test "Let's think step by step" on 10 math problems. Measure accuracy boost vs no CoT.
2. **Medium:** Implement self-consistency CoT — run 5 times, vote. Compare to single-run.
3. **Hard:** Build CoT extraction pipeline — use Instructor to force structured CoT output.
4. **Pro:** Implement Tree of Thoughts for a planning problem (e.g., optimal travel route).

---

## 13. Key Takeaways

✅ CoT = make LLM reason step-by-step before answering
✅ Zero-shot CoT: "Let's think step by step" — single biggest prompt trick
✅ Helps with: math, logic, multi-step reasoning
✅ Doesn't help: lookups, classification, translation
✅ Reasoning models (o1, o3, Claude extended thinking) do CoT internally — don't add "step by step" to those
✅ Self-consistency: N runs + vote for higher accuracy
✅ Force structured CoT with Pydantic + Instructor
✅ Hide CoT with `<thinking>` tags in production

**Next:** [05_advanced_reasoning.md](05_advanced_reasoning.md) — Self-consistency, ToT, reflection
