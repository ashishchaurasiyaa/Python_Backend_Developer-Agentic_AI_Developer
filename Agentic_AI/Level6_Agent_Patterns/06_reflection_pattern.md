# Level 6.6 — Reflection Pattern
**Phase: Agent Patterns | Quality-Critical**

## Quick Concepts

- **Reflection** = agent reviews + critiques its own output, then revises
- **Self-critique** = LLM asks itself "what's wrong with this answer?"
- **Iterative refinement** = generate → critique → revise → repeat
- **Reflexion** = academic paper that formalized this (Shinn et al. 2023)
- **Self-correction** = catching + fixing errors during/after generation
- **Generator-evaluator loop** = two roles (sometimes two model calls)

---

## Why Reflection Improves Quality

```
Without reflection:
   Question → Answer
   (one-shot, may be wrong)

With reflection:
   Question → Initial Answer → Critique → Refined Answer
                            (often catches errors)

Empirical wins:
   ✓ Coding tasks: +15-25% pass rate (Reflexion paper)
   ✓ Math reasoning: +10-20% accuracy
   ✓ Writing quality: subjective but noticeable
   ✗ Pure recall: minimal gain (can't refine missing knowledge)
```

**Trade-off:** 2-3x cost for one query. Worth it for high-stakes outputs.

---

## Basic Reflection Loop

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()


async def generate(question: str, previous_answer: str = None, critique: str = None) -> str:
    """Generate (or refine) an answer."""
    
    if previous_answer is None:
        # Initial generation
        prompt = f"Answer this question: {question}"
    else:
        # Refinement
        prompt = (
            f"Question: {question}\n\n"
            f"Previous answer: {previous_answer}\n\n"
            f"Critique: {critique}\n\n"
            f"Provide an improved answer addressing the critique."
        )
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


async def critique(question: str, answer: str) -> str:
    """LLM critiques the answer."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Critique this answer:\n\n"
                f"Question: {question}\n\n"
                f"Answer: {answer}\n\n"
                f"What's missing, wrong, or could be improved? "
                f"Be specific. If the answer is good, say 'No issues found.'"
            ),
        }],
        temperature=0.3,
    )
    return response.choices[0].message.content


async def reflection_answer(question: str, max_iterations=3) -> str:
    """Generate-critique-refine loop."""
    
    answer = await generate(question)
    
    for i in range(max_iterations):
        critique_text = await critique(question, answer)
        
        if "no issues found" in critique_text.lower():
            print(f"✓ Converged at iteration {i+1}")
            return answer
        
        print(f"Iteration {i+1} critique: {critique_text[:100]}...")
        answer = await generate(question, previous_answer=answer, critique=critique_text)
    
    return answer
```

---

## Reflection for Code Generation

```python
async def code_with_reflection(spec: str, max_iterations=3) -> str:
    """Generate code, test mentally, refine."""
    
    code = await generate_code(spec)
    
    for i in range(max_iterations):
        # Step 1: Self-review
        review_prompt = f"""
        Review this code for bugs, edge cases, and improvements:
        
        Spec: {spec}
        
        Code:
        ```python
        {code}
        ```
        
        List specific issues. If none, say "READY".
        """
        review = await ask(review_prompt)
        
        if "READY" in review:
            return code
        
        # Step 2: Fix
        fix_prompt = f"""
        Original code:
        ```python
        {code}
        ```
        
        Issues found:
        {review}
        
        Rewrite the code addressing these issues.
        """
        code = await extract_code(await ask(fix_prompt))
    
    return code
```

### Bonus: Add Actual Testing

```python
async def code_with_test_reflection(spec: str, tests: list[str]):
    """Generate code, run tests, fix until passing."""
    
    code = await generate_code(spec)
    
    for i in range(3):
        # Run actual tests in sandbox
        test_results = await run_tests(code, tests)
        
        if test_results["all_passed"]:
            return code
        
        # Feed test failures back to LLM
        fix_prompt = f"""
        Code:
        ```python
        {code}
        ```
        
        Failing tests:
        {test_results["failures"]}
        
        Fix the code.
        """
        code = await extract_code(await ask(fix_prompt))
    
    raise Exception("Could not pass all tests")
```

→ This is how tools like Cursor / Cline / Devin work internally.

---

## Reflection with Different Models (Generator + Critic)

For better critique, use a DIFFERENT model as critic:

```python
GENERATOR_MODEL = "gpt-4o-mini"  # cheap
CRITIC_MODEL = "claude-3-7-sonnet-latest"  # different, smarter


async def diverse_reflection(question):
    # Generate with one model
    answer = await openai_client.chat.completions.create(
        model=GENERATOR_MODEL, ...
    )
    
    # Critique with another (different blind spots!)
    critique = await anthropic_client.messages.create(
        model=CRITIC_MODEL,
        messages=[{"role": "user", "content": f"Critique: {answer}"}],
    )
    
    # Refine
    refined = await openai_client.chat.completions.create(
        model=GENERATOR_MODEL,
        messages=[
            {"role": "user", "content": f"Original: {answer}\nCritique: {critique}\nRevise."}
        ],
    )
    return refined
```

**Why this helps:** Different models trained differently → different mistakes → critic catches what generator missed.

---

## Reflexion (with Memory)

The original paper adds **episodic memory** of past failures:

```python
class ReflexionAgent:
    def __init__(self):
        self.memory = []  # past failures + lessons learned
    
    async def solve(self, task: str, max_trials=5):
        for trial in range(max_trials):
            # Use memory as context
            attempt = await self._attempt(task, self.memory)
            
            # Evaluate
            success, feedback = await self._evaluate(task, attempt)
            
            if success:
                return attempt
            
            # Reflect on failure → store lesson
            lesson = await self._reflect(task, attempt, feedback)
            self.memory.append({
                "trial": trial,
                "attempt": attempt,
                "feedback": feedback,
                "lesson": lesson,
            })
        
        raise Exception("Failed after all trials")
    
    async def _reflect(self, task, attempt, feedback):
        """Distill failure into a reusable lesson."""
        return await ask(f"""
            Task: {task}
            My attempt: {attempt}
            Why it failed: {feedback}
            
            What lesson should I remember for similar tasks?
            Be specific and concise.
        """)
    
    async def _attempt(self, task, memory):
        """Attempt with past lessons."""
        lessons = "\n".join([f"- {m['lesson']}" for m in memory])
        return await ask(f"""
            Past lessons:
            {lessons}
            
            New task: {task}
            
            Apply lessons to solve correctly.
        """)
```

---

## Structured Critique

Force critic to evaluate specific dimensions:

```python
CRITIQUE_RUBRIC = """
Evaluate this answer on these dimensions (1-10):

1. ACCURACY: Are claims factually correct?
2. COMPLETENESS: Are key points covered?
3. CLARITY: Is it easy to understand?
4. RELEVANCE: Does it answer the actual question?
5. SUPPORT: Are claims backed by reasoning/examples?

For each dimension, score + brief justification.
Then suggest improvements.
"""


async def structured_critique(question, answer):
    return await ask(f"""
        {CRITIQUE_RUBRIC}
        
        Question: {question}
        Answer: {answer}
    """)
```

Now you get specific actionable feedback per dimension.

---

## When NOT to Use Reflection

```
✗ Real-time chat (latency: 2-3x cost = unacceptable)
✗ Pure knowledge retrieval (RAG)
   → reflection can't add facts the model doesn't know
✗ Creative generation (subjective; critique may hurt creativity)
✗ Cost-sensitive at scale
✗ Tasks the model is already great at

Use reflection when:
   ✓ Code generation (testable)
   ✓ Math / reasoning (verifiable steps)
   ✓ Critical Q&A (high stakes)
   ✓ Writing where quality > speed
   ✓ When error has business consequences
```

---

## Cost Math

```python
def estimate_reflection_cost(question_tokens, answer_tokens, iterations=2):
    # Generator: input + output
    # Critic: input (question + answer) + output (critique)
    # Refiner: input (orig + critique) + output
    
    cost_per_iteration = (
        (question_tokens + answer_tokens) * 2 * INPUT_COST +
        (answer_tokens + 200) * OUTPUT_COST  # critique ~200 tokens
    )
    
    total = ONE_SHOT_COST + iterations * cost_per_iteration
    return total

# Typical: 2-3x cost of single shot
# Latency: 3-4x (sequential calls)
```

**Mitigation:**
- Only reflect on hard queries (classify difficulty first)
- Skip reflection if confidence is high
- Use cheap models for both generator + critic
- Parallelize reflection branches when possible

---

## Reflection in LangGraph

```python
from langgraph.graph import StateGraph, END

class ReflectionState(dict):
    question: str
    draft: str
    critique: str
    iterations: int


def generate_node(state):
    draft = llm.invoke(f"Answer: {state['question']}")
    return {"draft": draft, "iterations": state.get("iterations", 0) + 1}


def critique_node(state):
    critique = llm.invoke(f"Critique: {state['draft']}")
    return {"critique": critique}


def revise_node(state):
    revised = llm.invoke(
        f"Original: {state['draft']}\nCritique: {state['critique']}\nRevise."
    )
    return {"draft": revised}


def should_continue(state):
    if state["iterations"] >= 3:
        return END
    if "no issues" in state["critique"].lower():
        return END
    return "revise"


graph = StateGraph(ReflectionState)
graph.add_node("generate", generate_node)
graph.add_node("critique", critique_node)
graph.add_node("revise", revise_node)

graph.set_entry_point("generate")
graph.add_edge("generate", "critique")
graph.add_conditional_edges("critique", should_continue)
graph.add_edge("revise", "critique")

app = graph.compile()
```

---

## Combining Reflection with Other Patterns

### Reflection + ReAct
ReAct's "Thought" step IS a mini-reflection. Add explicit reflection after final answer.

### Reflection + RAG
Critique retrieval quality: "Did we have enough context to answer?" → re-retrieve with different query.

### Reflection + Tool Use
Verify tool outputs before using: "Does this database query result look reasonable?"

---

## Common Pitfalls

```
1. ✗ Infinite loops (no convergence detection)
   ✓ Always set max_iterations

2. ✗ Critic too lenient
   → Says "looks good" on bad answers
   ✓ Add structured rubric, examples of bad outputs

3. ✗ Critic too strict
   → Always finds issues, loops forever
   ✓ "If answer is acceptable, say PASS"

4. ✗ Reflection on cheap tasks
   → Wastes money for no gain
   ✓ Reflect only on hard / high-stakes

5. ✗ Same model as generator + critic
   → Same biases, misses same issues
   ✓ Different models when possible

6. ✗ Critic role too vague
   ✓ Structured prompts: "Score X/10 on Y dimension"

7. ✗ Not measuring improvement
   → Doesn't know if reflection actually helps
   ✓ A/B test reflection on/off, measure quality
```

---

## Interview Questions

### Q1: What is the reflection pattern?

A two-step (or N-step) process: LLM generates an answer, then critiques itself, then revises based on critique. Improves quality at the cost of 2-3x tokens. Especially effective for code, math, and critical Q&A.

### Q2: Why use different models for generator vs critic?

Different models have different blind spots — a critic of a different family is more likely to catch errors the generator missed. e.g., GPT-4o-mini generates, Claude critiques. Trade-off: cost + multi-vendor complexity.

### Q3: When does reflection NOT help?

Pure retrieval/recall tasks (can't add facts model doesn't know), real-time chat (latency too high), creative writing (subjective critique hurts), simple queries where model is already accurate.

### Q4: How do you prevent infinite reflection loops?

(1) Hard cap on iterations (3-5). (2) Convergence detection ("If satisfied, say PASS"). (3) Quality threshold (stop when critic score > 8/10). (4) Diminishing returns check (if delta between iterations < threshold).

### Q5: What's Reflexion vs basic reflection?

Reflexion adds episodic memory — store past failures + lessons, use across multiple trials of similar tasks. Basic reflection is single-task generate-critique-revise. Reflexion is more powerful for agents that face many similar challenges.

---

## Senior Mantras

```
1. Reflect on hard/critical outputs. Skip for cheap tasks.

2. Always cap iterations. Loops are LLM cost bombs.

3. Different models for gen + critic = better catches.

4. Structured rubrics > vague "is this good?"

5. Reflection adds 2-3x cost. Worth it for high-stakes.

6. Combine with testing for code (Devin/Cursor pattern).

7. Convergence detection prevents infinite loops.

8. Measure improvement. Don't just assume reflection helps.

9. Reflexion (with memory) > basic reflection for agents.

10. For latency-tight apps: skip reflection or do async.
```

---

## Related

- [04_react_pattern.md](04_react_pattern.md) — ReAct has implicit reflection
- [05_plan_and_execute.md](05_plan_and_execute.md) — combine with planning
- [07_multi_agent_supervisor.md](07_multi_agent_supervisor.md) — critic as agent
- [09_human_in_loop.md](09_human_in_loop.md) — human-in-the-loop reflection
- [10_agent_evaluation.md](10_agent_evaluation.md) — measuring quality
