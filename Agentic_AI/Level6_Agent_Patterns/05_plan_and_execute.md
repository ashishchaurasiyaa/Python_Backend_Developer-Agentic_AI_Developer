# Level 6 — Doc 5: Plan & Execute Pattern

> **Goal:** Pehle plan banao, fir execute karo. ReAct se zyada efficient for complex tasks.

---

## 1. The Problem with Plain ReAct

ReAct = reactive. Each step decided AFTER seeing previous observation.

For complex tasks:
- "Write a blog post about AI, then translate to Hindi, then summarize"
- ReAct: thinks step-by-step, may go in circles

**Plan & Execute** = plan FIRST, then execute the plan.

---

## 2. The Pattern

```
┌─────────────────────┐
│ User question       │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Planner LLM:        │
│ "Make a plan"       │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Plan:               │
│ 1. Search topic     │
│ 2. Draft outline    │
│ 3. Write sections   │
│ 4. Translate        │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Executor: for each  │
│   step, use tools   │
└──────────┬──────────┘
           ↓
        Final result
```

Plan once, execute many.

---

## 3. Implementation

```python
class PlanAndExecuteAgent:
    def __init__(self, tools, planner_model="gpt-4o", executor_model="gpt-4o-mini"):
        self.tools = tools
        self.planner_model = planner_model  # Smarter for planning
        self.executor_model = executor_model  # Cheaper for execution
    
    def plan(self, question: str) -> list[str]:
        """Generate plan."""
        prompt = f"""Given this task, create a step-by-step plan.

Task: {question}

Available tools: {list(self.tools.keys())}

Output JSON array of steps, e.g.:
["Step 1: do X", "Step 2: do Y", ...]

Plan:"""
        
        response = llm.call(prompt, model=self.planner_model)
        return json.loads(response)
    
    def execute_step(self, step: str, context: dict) -> str:
        """Execute one step using ReAct."""
        react_agent = BasicReActAgent(self.tools, model=self.executor_model)
        result = react_agent.run(f"Context: {context}\n\nTask: {step}")
        return result
    
    def run(self, question: str) -> str:
        # 1. Plan
        plan = self.plan(question)
        
        # 2. Execute
        results = {}
        for i, step in enumerate(plan):
            print(f"Step {i+1}: {step}")
            results[i] = self.execute_step(step, results)
        
        # 3. Synthesize final answer
        return self.synthesize(question, plan, results)
    
    def synthesize(self, question, plan, results):
        prompt = f"""Original question: {question}

Steps taken:
{plan}

Step results:
{json.dumps(results, indent=2)}

Synthesize final answer:"""
        return llm.call(prompt, model=self.planner_model)
```

---

## 4. Plan-and-Execute vs ReAct

| Aspect | ReAct | Plan & Execute |
|---|---|---|
| Steps | Decided one at a time | Pre-planned |
| Total LLM calls | More (each step's thought) | Fewer (plan once, simpler exec) |
| Adaptability | Better (reacts to surprises) | Worse (plan may need replanning) |
| Cost | Higher (smarter model each step) | Lower (cheap executor) |
| Complexity | Simpler code | More complex |

**Use ReAct when:** Few steps, exploratory.
**Use Plan & Execute when:** Many steps, structure clear.

---

## 5. Replanning

What if execution fails mid-plan?

```python
def run_with_replan(self, question):
    plan = self.plan(question)
    results = {}
    
    i = 0
    while i < len(plan):
        try:
            results[i] = self.execute_step(plan[i], results)
            i += 1
        except Exception as e:
            # Replan from here
            print(f"Step {i} failed: {e}. Replanning...")
            remaining = self.replan(question, plan, i, results)
            plan = plan[:i] + remaining
    
    return self.synthesize(question, plan, results)
```

---

## 6. Real Example

```
Question: "Find latest AI news, summarize, and email me a digest"

Plan:
[
  "Search for recent AI news from last 7 days",
  "Identify top 5 most important stories",  
  "Write 1-paragraph summary for each",
  "Combine into email format",
  "Send email to user"
]

Execution:
Step 1: search_web("AI news last 7 days")
  → Returns 20 articles
Step 2: ReAct decides: rank by importance → top 5
Step 3: For each of 5, summarize
Step 4: Format as email
Step 5: send_email(...)

Final: "Email sent with 5 AI news summaries"
```

---

## 7. When Plan & Execute Wins

✅ **Wins for:**
- Research reports (clear sections)
- Multi-step data pipelines
- Batch processing
- Documentation generation
- Workflows with known phases

❌ **Loses for:**
- Open-ended exploration
- Conversational chat
- Single-step tasks
- Tasks needing constant user feedback

---

## 8. Key Takeaways

✅ Plan & Execute = plan first, then execute steps
✅ Use smarter model for planning, cheaper for execution
✅ Replan on failure
✅ Best for structured multi-step tasks
✅ ReAct still better for exploratory tasks

**Next:** [06_reflection.md](06_reflection.md) — Reflection pattern (self-critique)
