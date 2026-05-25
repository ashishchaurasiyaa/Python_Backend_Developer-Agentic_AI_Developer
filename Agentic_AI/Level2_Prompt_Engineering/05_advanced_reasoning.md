# Level 2 — Doc 5: Advanced Reasoning Patterns

> **Goal:** CoT ke beyond — Self-Consistency, Tree of Thoughts, Self-Critique, Reasoning models. State-of-the-art techniques jo production mein use hote hain.

---

## 1. Why Advanced Reasoning?

Plain CoT (Doc 4) ek baar reason karta hai. But:
- LLM galat reason kar sakta hai
- Single chain → single point of failure
- Complex problems mein multi-perspective chahiye

**Advanced patterns address these:**
1. **Self-Consistency** — multiple samples, vote
2. **Tree of Thoughts** — explore branches
3. **Self-Critique** — LLM reviews itself
4. **Reflexion** — LLM learns from past mistakes
5. **Reasoning Models** — o1, o3, Claude extended thinking

---

## 2. Self-Consistency (SC)

**Concept:** Same prompt N baar run karo with `temperature > 0`. **Vote** on most common answer.

### Algorithm:
```
1. Generate N reasoning chains (e.g., N=5, temp=0.7)
2. Extract final answer from each
3. Return most-frequent answer
```

### Why it works:
- Single LLM chain can be wrong
- N independent chains → wisdom of crowds
- Majority vote filters out noise

### When to use:
- ✅ Math problems (clear final answer)
- ✅ Classification (clear labels)
- ✅ Yes/No questions
- ❌ Open-ended creative tasks (no single "right" answer)

### Trade-offs:
- Cost: N × normal cost
- Latency: Can parallelize calls
- Accuracy gain: 5-20% on reasoning tasks

```python
def self_consistency(prompt, n=5):
    answers = [llm_call(prompt, temp=0.7) for _ in range(n)]
    extracted = [extract_final(a) for a in answers]
    return Counter(extracted).most_common(1)[0][0]
```

---

## 3. Tree of Thoughts (ToT)

**Concept:** CoT is linear (step → step → step). ToT explores **branches**, prunes bad ones.

### Use case:
Planning problems where you can backtrack:
- Optimal travel routes
- Game tree search (chess moves)
- Multi-step puzzles
- Code refactoring options

### Algorithm:
```
1. Define problem state
2. Generate K possible "next thoughts" at each step
3. Evaluate each (LLM scores them)
4. Keep top-M best branches
5. Repeat until solution
6. Backtrack if dead end
```

### Example: 24 Game
```
Problem: Use [3, 5, 6, 8] to make 24 using +-*/.

Tree:
Root: [3, 5, 6, 8]
├── 3 + 5 = 8 → [8, 6, 8]
│   ├── 8 + 6 = 14 → [14, 8] → dead end
│   ├── 8 × 6 = 48 → [48, 8] → 48 / 8 = 6 (not 24, prune)
│   └── 8 + 8 = 16 → [16, 6] → 16 + 6 = 22 (close, prune)
├── 8 - 3 = 5 → [5, 5, 6] 
│   └── 5 × 5 = 25 (close)
└── 6 / 3 = 2 → [2, 5, 8] → 8 × (5 - 2) = 24 ✓
```

### Implementation pattern:
```python
class ToTNode:
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.score = 0

def tot_search(initial_state, max_depth=5, branches_per_step=3):
    root = ToTNode(initial_state)
    frontier = [root]
    
    for depth in range(max_depth):
        new_frontier = []
        for node in frontier:
            # Generate K possible next thoughts (LLM call)
            next_thoughts = generate_thoughts(node.state, k=branches_per_step)
            for thought in next_thoughts:
                child = ToTNode(thought, parent=node)
                child.score = evaluate(thought)  # LLM scores it
                node.children.append(child)
                new_frontier.append(child)
        # Prune: keep top-M scored
        frontier = sorted(new_frontier, key=lambda x: -x.score)[:5]
    
    return best_path(frontier)
```

**Cost:** ToT is EXPENSIVE — many LLM calls per problem. Use only when CoT fails.

---

## 4. Self-Critique (LLM Reviews Itself)

**Concept:** Two-step pipeline:
1. LLM generates answer
2. Same LLM reviews and improves

### Pattern:
```python
def self_critique(question):
    # Step 1: Initial answer
    answer = llm_call(f"Answer: {question}")
    
    # Step 2: Critique
    critique = llm_call(f"""
    Question: {question}
    Initial Answer: {answer}
    
    Critique this answer. What's wrong? What's missing? Be harsh.
    """)
    
    # Step 3: Revised
    revised = llm_call(f"""
    Question: {question}
    Initial: {answer}
    Critique: {critique}
    
    Provide improved answer addressing the critique.
    """)
    
    return revised
```

### When this helps:
- Code generation (find bugs)
- Writing (improve clarity)
- Math proofs (catch errors)

### When it doesn't:
- LLM may agree with its own wrong answer (sycophancy)
- Costs 3x (3 LLM calls)

**Tip:** Use **different model** for critique. e.g., GPT-4o generates, Claude critiques. Diversity helps.

---

## 5. Reflexion (Learn from Past Mistakes)

**Concept:** Agent attempts task, fails, **writes notes about why**, retries with notes.

### Pattern (for agents):
```python
def reflexion_loop(task, max_attempts=3):
    notes = []  # Lessons learned
    
    for attempt in range(max_attempts):
        # Attempt with previous lessons
        result = agent.execute(task, hints=notes)
        
        # Check success
        if is_successful(result):
            return result
        
        # Reflect on failure
        reflection = llm_call(f"""
        Task: {task}
        Attempt {attempt + 1}: {result}
        
        What went wrong? What should you remember for next time?
        Be specific. One sentence.
        """)
        notes.append(reflection)
    
    return None  # Failed all attempts
```

This is **agent memory in action**. Production agents use this.

---

## 6. Reasoning Models (o1, o3, Claude Extended Thinking)

**Game-changer (2024-2026):** Models trained to reason **internally** before answering.

### How they differ:
| Standard LLM | Reasoning Model |
|---|---|
| Predicts tokens directly | Reasons internally, then outputs |
| Needs "step by step" hint | Reasons automatically |
| Cheap, fast | 5-10x cost, slower |
| Good for general | Better for hard problems |

### OpenAI o-series:
- `o1-mini` — cheaper, fast reasoning
- `o1` — full reasoning
- `o3` — even better (newer)

**Usage:**
```python
response = openai.chat.completions.create(
    model="o1-mini",
    messages=[{"role": "user", "content": "Solve this complex problem..."}]
    # NO "let's think step by step" — model does it internally
)
```

### Anthropic Extended Thinking:
```python
response = anthropic.messages.create(
    model="claude-3-7-sonnet-20250219",  # or later
    thinking={
        "type": "enabled",
        "budget_tokens": 16000  # How much internal reasoning to allow
    },
    messages=[{"role": "user", "content": "Hard problem"}]
)

# Response includes:
# - response.content (final answer)
# - response.thinking (internal reasoning, optional to expose)
```

### When to use reasoning models:
✅ Math olympiad-level
✅ Complex code (algorithmic, multi-file)
✅ Scientific reasoning
✅ Multi-step planning
✅ Cases where you'd run CoT + Self-Consistency anyway

❌ Simple lookups
❌ Translation
❌ Creative writing
❌ Cost-sensitive tasks

### Cost reality:
```
GPT-4o-mini:  $0.15 / 1M input tokens
GPT-4o:        $2.50 / 1M input tokens
o1-mini:       $3.00 / 1M input tokens (+ "thinking" tokens charged)
o1:           $15.00 / 1M input tokens
```

For 1000-token problems:
- gpt-4o-mini: $0.0001
- o1: $0.015 (~150x more expensive)

**Senior decision:** Route easy problems to cheap models, hard problems to reasoning models.

---

## 7. Routing Pattern (Production)

```python
def route_to_model(query: str) -> str:
    """Choose model based on query difficulty."""
    
    # Step 1: Cheap classifier
    classification = llm_call(
        f"""Classify difficulty of: "{query}"
        
        Categories:
        - SIMPLE (lookup, single fact, easy translation)
        - MEDIUM (multi-step reasoning, code, analysis)
        - HARD (math proofs, algorithmic, complex code)
        
        Output ONE word.""",
        model="gpt-4o-mini"
    )
    
    # Step 2: Route accordingly
    if classification == "SIMPLE":
        return llm_call(query, model="gpt-4o-mini")
    elif classification == "MEDIUM":
        return llm_call(query + "\nLet's think step by step.", model="gpt-4o")
    else:  # HARD
        return llm_call(query, model="o1-mini")
```

This **saves 10-100x cost** vs always using o1.

---

## 8. Combining Patterns

Real production systems **combine** these:

### Example: Math homework helper
```
1. Classify problem difficulty (cheap model)
2. If easy: gpt-4o-mini + Zero-shot CoT
3. If medium: gpt-4o + Few-shot CoT + Self-Consistency (3 runs)
4. If hard: o1-mini (let it reason internally)
5. Validate output (extract number, sanity check)
6. If validation fails: retry with self-critique
```

This is **closer to how production AI works** than single-prompt systems.

---

## 9. Anti-Patterns to Avoid

### ❌ Using CoT with Reasoning Models
```python
# Bad — wastes thinking tokens
response = openai.chat.completions.create(
    model="o1",
    messages=[{"role": "user", "content": "Solve X. Let's think step by step."}]
)
```
o1 already reasons internally. "Step by step" wastes tokens.

### ❌ Self-Consistency for Creative Tasks
```python
# Bad — there's no "majority answer" for creative writing
poems = [llm.write_poem() for _ in range(5)]
final = vote(poems)  # Doesn't make sense
```

### ❌ Tree of Thoughts for Simple Problems
ToT = expensive. Don't use for problems CoT solves.

### ❌ Over-Critiquing
3+ rounds of self-critique often → no improvement, sometimes worse.

---

## 10. Interview Questions

1. **Q: Explain self-consistency.**
   - Run prompt N times with temperature, vote on answer. Reduces variance.

2. **Q: When would you use o1 over gpt-4o + CoT?**
   - Hard problems where CoT isn't enough. Worth 5-10x cost.

3. **Q: How does ToT differ from CoT?**
   - CoT = linear. ToT = explores multiple branches, can backtrack.

4. **Q: What's Reflexion?**
   - Agent attempts task, reflects on failure, retries with lessons learned.

5. **Q: How do you route between models?**
   - Cheap classifier first → routes to gpt-4o-mini / gpt-4o / o1 based on difficulty.

---

## 11. Exercises

1. **Easy:** Implement self-consistency for 10 math problems. Plot accuracy by N.
2. **Medium:** Build self-critique pipeline. Test on code generation.
3. **Hard:** Implement ToT for 24-game (combine 4 numbers to make 24).
4. **Pro:** Build a routing system that decides between gpt-4o-mini, gpt-4o, and o1 based on classification.

---

## 12. Key Takeaways

✅ Self-Consistency: N runs + majority vote → 5-20% accuracy boost
✅ Tree of Thoughts: explore branches, prune. Use for planning, NOT simple tasks.
✅ Self-Critique: LLM reviews own output. Better with different model.
✅ Reflexion: Agent learns from failures via reflection notes.
✅ Reasoning models (o1, o3, Claude extended) — built-in CoT
✅ Routing: cheap classifier → expensive model only when needed
✅ Combine patterns in production (classify → route → reason → validate)

**Next:** [06_system_prompts.md](06_system_prompts.md) — System prompts deep dive
