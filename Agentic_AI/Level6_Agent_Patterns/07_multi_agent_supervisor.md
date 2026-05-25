# Level 6 — Doc 7: Multi-Agent Supervisor Pattern ⭐

> **Goal:** Ek supervisor agent jo specialist agents ko delegate kare. Production-grade multi-agent system. Senior interview gold.

---

## 1. The Concept

Real-world tasks need different expertise:
- Code review needs **code expert** + **security expert** + **performance expert**
- Customer support needs **billing agent** + **technical agent** + **escalation agent**
- Research needs **searcher** + **summarizer** + **writer**

**Supervisor pattern:** One LLM coordinates specialists.

```
          ┌─────────────────┐
          │   Supervisor    │
          │   (router)      │
          └────────┬────────┘
                   │ delegates
        ┌──────────┼──────────┐
        ↓          ↓          ↓
   ┌────────┐ ┌────────┐ ┌────────┐
   │Coder   │ │Searcher│ │Writer  │
   │ Agent  │ │ Agent  │ │ Agent  │
   └────────┘ └────────┘ └────────┘
```

---

## 2. Architecture

```
User Query → Supervisor → analyzes intent
                       → routes to specialist(s)
                       → collects responses
                       → returns final answer
```

Two patterns:
- **Sequential**: Supervisor calls agents one at a time
- **Parallel**: Multiple agents work simultaneously

---

## 3. Implementation (From Scratch)

```python
class SpecialistAgent:
    """A specialist agent — domain-specific."""
    def __init__(self, name: str, role: str, tools: dict, system_prompt: str):
        self.name = name
        self.role = role
        self.tools = tools
        self.system_prompt = system_prompt
    
    def execute(self, task: str) -> str:
        # Use ReAct internally
        agent = BasicReActAgent(self.tools)
        return agent.run(f"{self.system_prompt}\n\nTask: {task}")


class SupervisorAgent:
    """Routes tasks to specialists."""
    
    def __init__(self, specialists: list[SpecialistAgent], model="gpt-4o"):
        self.specialists = {a.name: a for a in specialists}
        self.model = model
        self.history = []
    
    def decide_next(self, query: str, history: list) -> dict:
        """Decide which specialist to call next, or finish."""
        specialist_descriptions = "\n".join(
            f"- {a.name}: {a.role}" for a in self.specialists.values()
        )
        
        history_text = "\n".join(f"{h['agent']}: {h['result'][:200]}" for h in history)
        
        prompt = f"""You are a supervisor coordinating specialist agents.

User query: {query}

Available specialists:
{specialist_descriptions}

History so far:
{history_text}

Decide next action. Output JSON:
{{"action": "delegate" | "finish", "agent": "name", "task": "specific task", "reason": "why"}}

Or to finish:
{{"action": "finish", "final_answer": "..."}}"""

        response = llm_call(prompt, model=self.model)
        return json.loads(response)
    
    def run(self, query: str, max_iter: int = 5) -> str:
        history = []
        
        for i in range(max_iter):
            decision = self.decide_next(query, history)
            
            if decision["action"] == "finish":
                return decision["final_answer"]
            
            # Delegate to specialist
            specialist = self.specialists[decision["agent"]]
            result = specialist.execute(decision["task"])
            
            history.append({
                "agent": decision["agent"],
                "task": decision["task"],
                "result": result,
                "reason": decision["reason"]
            })
        
        return "Max iterations reached"
```

---

## 4. Example: Code Review System

```python
# Define specialists
security_agent = SpecialistAgent(
    name="security_reviewer",
    role="Reviews code for security vulnerabilities (OWASP Top 10)",
    tools={"static_analysis": run_bandit, "search_cve": search_cve_db},
    system_prompt="You are a security expert. Focus only on security issues."
)

performance_agent = SpecialistAgent(
    name="performance_reviewer",
    role="Analyzes code for performance issues (Big O, memory leaks)",
    tools={"profiler": run_profiler, "analyze_complexity": analyze},
    system_prompt="You are a performance engineer. Focus on speed and memory."
)

style_agent = SpecialistAgent(
    name="style_reviewer",
    role="Checks code style, readability, naming conventions",
    tools={"lint": run_ruff, "check_pep8": pep8_check},
    system_prompt="You are a style reviewer. Check readability and conventions."
)

# Set up supervisor
supervisor = SupervisorAgent([security_agent, performance_agent, style_agent])

# Run
result = supervisor.run("""
Review this Python function:

def process_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db.execute(query)
    return result[0]
""")

# Supervisor:
# 1. Calls security_reviewer → "SQL injection vulnerability!"
# 2. Calls performance_reviewer → "OK, basic select"
# 3. Calls style_reviewer → "Missing type hints, no docstring"
# 4. Synthesizes: "Issues: SQL injection (CRITICAL), missing types/docstring..."
```

---

## 5. Parallel Multi-Agent

For independent tasks, run agents in parallel:

```python
from concurrent.futures import ThreadPoolExecutor

class ParallelSupervisor:
    def run_parallel(self, query: str) -> dict:
        # Decide all specialists at once
        plan = self.plan_all(query)
        # plan = {"security": "task1", "performance": "task2", "style": "task3"}
        
        with ThreadPoolExecutor() as executor:
            futures = {
                name: executor.submit(self.specialists[name].execute, task)
                for name, task in plan.items()
            }
            results = {name: f.result() for name, f in futures.items()}
        
        return self.synthesize(query, results)
```

**Speedup:** N specialists in parallel = max(specialist time) instead of sum.

---

## 6. Communication Patterns

### A. Supervisor-only (Tree)
```
Supervisor → Agent A → Supervisor
Supervisor → Agent B → Supervisor
```
Agents don't talk to each other.

### B. Network (Mesh)
```
A ↔ B ↔ C
↕   ↕   ↕
D ↔ E ↔ F
```
Agents can call each other directly. More complex, more capable.

### C. Sequential pipeline
```
A → B → C → D → final
```
Each agent's output feeds next.

Most production systems start with **Supervisor-only** (simpler).

---

## 7. State Management

For long conversations, supervisor needs state:

```python
class StatefulSupervisor:
    def __init__(self, specialists):
        self.specialists = {a.name: a for a in specialists}
        self.shared_state = {}  # All agents can read
        self.agent_states = {}   # Per-agent private state
    
    def execute_with_state(self, agent_name, task):
        # Pass shared state to agent
        result = self.specialists[agent_name].execute(
            task,
            shared_state=self.shared_state
        )
        # Agent may update shared state
        return result
```

This is essentially what **LangGraph** provides — shared state across nodes.

---

## 8. Common Pitfalls

### Pitfall 1: Supervisor Re-Does Specialist Work
LLM may decide to answer itself instead of delegating.
**Fix:** Strong prompt: "ALWAYS delegate. Never solve directly."

### Pitfall 2: Specialists Overlap
Two specialists both claim a task.
**Fix:** Clearer role boundaries in their descriptions.

### Pitfall 3: Infinite Routing
Supervisor keeps calling same specialist.
**Fix:** Track call history, prevent loops, max iterations.

### Pitfall 4: Specialists Lose Context
Each specialist doesn't see overall goal.
**Fix:** Pass query context to each specialist.

---

## 9. Production-Grade Considerations

### Logging per agent
```python
{
  "query": "...",
  "supervisor_decisions": [
    {"step": 1, "delegated_to": "security", "task": "...", "result": "..."},
    {"step": 2, "delegated_to": "performance", "task": "...", "result": "..."}
  ],
  "final_answer": "...",
  "total_cost": 0.005,
  "total_time_sec": 12.3
}
```

### Cost tracking
- Supervisor model (smart, expensive)
- Specialist models (can be cheaper)
- Budget across all agents

### Failure handling
- One specialist fails → continue with others or surface failure?
- Retry strategies per agent

---

## 10. LangGraph Implementation (Production)

LangGraph makes this much easier:

```python
from langgraph.graph import StateGraph, END

# Define state
class State(TypedDict):
    query: str
    security_review: str | None
    performance_review: str | None
    style_review: str | None
    final: str | None

# Define nodes (specialists)
def security_node(state):
    return {"security_review": run_security(state["query"])}

def performance_node(state):
    return {"performance_review": run_perf(state["query"])}

def style_node(state):
    return {"style_review": run_style(state["query"])}

def synthesize_node(state):
    return {"final": combine(state)}

# Build graph
workflow = StateGraph(State)
workflow.add_node("security", security_node)
workflow.add_node("performance", performance_node)
workflow.add_node("style", style_node)
workflow.add_node("synthesize", synthesize_node)

# Edges (run security, performance, style in parallel, then synthesize)
workflow.add_edge("security", "synthesize")
workflow.add_edge("performance", "synthesize")
workflow.add_edge("style", "synthesize")
workflow.add_edge("synthesize", END)

# Compile and run
app = workflow.compile()
result = app.invoke({"query": "..."})
```

LangGraph manages parallelism, state, errors. We covered this in Level 7.

---

## 11. Real-World Use Cases

### Customer Support System
- Supervisor: classifies intent
- Billing agent: payments, refunds
- Technical agent: bugs, troubleshooting
- Account agent: settings, profile
- Escalation: handoff to human

### Coding Assistant
- Supervisor: understands request
- Research: find docs, similar code
- Code-gen: writes code
- Test-gen: writes tests
- Review: verifies quality

### Content Pipeline
- Supervisor: plans content
- Researcher: gathers facts
- Writer: drafts content
- Editor: polishes
- SEO agent: optimizes

---

## 12. Interview Questions

1. **Q: What's the multi-agent supervisor pattern?**
   - One LLM (supervisor) coordinates specialists; routes tasks to right agent.

2. **Q: Supervisor vs network architecture?**
   - Supervisor: tree (simpler). Network: agents talk to each other (more capable, complex).

3. **Q: How to prevent supervisor loops?**
   - Max iterations, track call history, force "finish" option.

4. **Q: When to use multi-agent over single ReAct?**
   - Complex tasks requiring DIFFERENT expertise. Single agent can't be expert in everything.

5. **Q: How does LangGraph help?**
   - Provides graph abstraction, state management, parallel execution.

---

## 13. Exercises

1. **Easy:** Build a 3-agent code reviewer (security + performance + style).
2. **Medium:** Add parallel execution. Compare to sequential.
3. **Hard:** Multi-agent chat — one supervisor, 4 specialists, all can call each other.
4. **Pro:** Build a debate system — 2 agents argue, 1 judge agent picks winner. Use to refine answers.

---

## 14. Key Takeaways

✅ Multi-agent supervisor = ONE coordinator + MANY specialists
✅ Each specialist has clear, narrow role + dedicated tools
✅ Supervisor routes tasks based on intent
✅ Sequential vs parallel execution
✅ State management via shared state object
✅ Production: LangGraph makes it easier
✅ Use when: task needs different expertise areas

**Next:** [10_agent_evaluation.md](10_agent_evaluation.md) — How to measure agent quality
