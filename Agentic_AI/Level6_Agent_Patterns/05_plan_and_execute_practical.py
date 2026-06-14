"""
Level 6 - Doc 5: Plan and Execute Pattern (PRACTICAL)
======================================================
KYA SEEKHENGE (What we will learn):
  1. Planner LLM   - pehle POORA plan banata hai (makes full plan first)
  2. Executor LLM  - ek-ek step execute karta hai (executes step by step)
  3. Replanning    - step fail ho toh nayi plan banana (replan on failure)
  4. ReAct vs Plan-and-Execute - kab kaun best hai (which is better when)
  5. Offline/graceful-degradation - bina API key ke bhi chalega (works without key)

KAISE CHALANA (How to run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python Level6_Agent_Patterns/05_plan_and_execute_practical.py

BINA KEY KE (without any key) - sirf offline demo chalega, EXIT 0 milega.
Groq key set karo toh live LLM calls bhi dekhoge:
  export GROQ_API_KEY="gsk_..."
"""

# ── Standard library imports ──────────────────────────────────────────────────
import os
import json
import re
import time
from typing import Optional, Callable
from dataclasses import dataclass, field


# ── Groq/OpenAI client helper -------------------------------------------------
# Theory se: planner model strong (smart), executor model cheap (faster)
# Yahan dono ke liye ek hi Groq client use karenge (free tier mein kaam karta hai)
def get_client():
    """
    Groq client return karta hai (OpenAI-compatible API).
    Agar key nahi hai toh placeholder deta hai taaki crash na ho.
    Offline mode mein is client ka use nahi hoga.
    """
    from openai import OpenAI  # openai SDK Groq ke saath compatible hai
    api_key = os.getenv("GROQ_API_KEY") or "placeholder"
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )


# ── Offline / Live mode detect ────────────────────────────────────────────────
# Key nahi = offline mode = fake data use karo, real LLM mat bulao
LIVE_MODE = bool(os.getenv("GROQ_API_KEY"))

if not LIVE_MODE:
    print("[OFFLINE MODE] GROQ_API_KEY nahi mila - fake/mock data se demo chalega.")
    print("[OFFLINE MODE] Live LLM calls skip hongi, EXIT 0 guarantee hai.\n")
else:
    print(f"[LIVE MODE] GROQ_API_KEY mila - Groq API use hogi.\n")


# =============================================================================
# SECTION 1: Concept - ReAct vs Plan-and-Execute comparison
# INTERVIEW POINT: dono ke beech ka fark samajhna zaroori hai
# =============================================================================

print("=" * 70)
print("SECTION 1: Plan-and-Execute Kya Hai? (ReAct se compare)")
print("=" * 70)

# Theory doc se liya hua comparison table
COMPARISON = [
    # (Aspect,                 ReAct,                       Plan-and-Execute)
    ("Steps decide kab",       "ek-ek step pe (reactive)",  "pehle sab (upfront)"),
    ("LLM calls (kitni)",      "zyada (har step pe thought)","kam (plan once, cheap exec)"),
    ("Adaptability (flexibility)", "better (surprises handle)", "worse (plan may fail)"),
    ("Cost (paisa)",           "zyada (smart model har step)","kam (cheap executor)"),
    ("Best for",               "exploratory / few steps",   "structured multi-step"),
]

print(f"\n  {'Aspect':<30} {'ReAct':<28} {'Plan-and-Execute'}")
print("  " + "-" * 78)
for aspect, react, pne in COMPARISON:
    print(f"  {aspect:<30} {react:<28} {pne}")

print("""
  THEORY (doc 5) ka key insight:
    - Plan-and-Execute = pehle POORA plan banao, fir execute karo
    - Planner = smarter/expensive model (GPT-4o like)
    - Executor = cheaper/faster model (GPT-4o-mini like)
    - Flow: User Question -> Planner -> [step1, step2, ...] -> Executor (loop) -> Final Answer
""")


# =============================================================================
# SECTION 2: Core Data Structures
# Plan aur StepResult classes - theory ka direct implementation
# =============================================================================

print("=" * 70)
print("SECTION 2: Plan Data Structure")
print("=" * 70)


@dataclass
class PlanStep:
    """
    Plan ka ek step represent karta hai.
    Har step ka apna status hota hai: pending, running, done, failed.
    """
    index: int           # step number (0-based)
    description: str     # step ka kya karna hai
    status: str = "pending"   # pending | running | done | failed
    result: str = ""     # execution ke baad yahan result aata hai
    error: str = ""      # agar fail hua toh error message


@dataclass
class ExecutionPlan:
    """
    Poore plan ko hold karta hai - ek list of PlanStep objects.
    Theory se: planner yeh banata hai, executor isko execute karta hai.
    """
    task: str
    steps: list = field(default_factory=list)  # List[PlanStep]
    created_at: float = field(default_factory=time.time)

    def add_step(self, desc: str):
        step = PlanStep(index=len(self.steps), description=desc)
        self.steps.append(step)

    def is_complete(self) -> bool:
        # Sab steps done hain toh plan complete hai
        return all(s.status == "done" for s in self.steps)

    def has_failure(self) -> bool:
        return any(s.status == "failed" for s in self.steps)

    def pending_steps(self):
        return [s for s in self.steps if s.status == "pending"]

    def failed_steps(self):
        return [s for s in self.steps if s.status == "failed"]

    def get_context(self, upto_index: int) -> str:
        """
        Pichle steps ke results ko context ke roop mein deta hai.
        Executor ko yeh context milti hai taaki woh smartly execute kar sake.
        """
        lines = []
        for s in self.steps[:upto_index]:
            if s.status == "done":
                lines.append(f"Step {s.index + 1} result: {s.result[:200]}")
        return "\n".join(lines) if lines else "No prior context."

    def print_plan(self, title: str = "Current Plan"):
        print(f"\n  [{title}]")
        for s in self.steps:
            icon = {"pending": "[ ]", "running": "[>]", "done": "[x]", "failed": "[!]"}.get(s.status, "[ ]")
            result_preview = f" -> {s.result[:60]}..." if s.result else ""
            print(f"  {icon} Step {s.index + 1}: {s.description}{result_preview}")


# Demo: plan banate hain
demo_plan = ExecutionPlan(task="AI news digest email bhejna")
demo_plan.add_step("Last 7 din ke AI news search karo")
demo_plan.add_step("Top 5 stories identify karo")
demo_plan.add_step("Har story ka 1 paragraph summary likho")
demo_plan.add_step("Email format mein combine karo")
demo_plan.add_step("User ko email bhejo")
demo_plan.print_plan("Theory Doc Example Plan")


# =============================================================================
# SECTION 3: Mock Tools - Executor in yeh tools use karta hai
# Real scenario mein yahan web_search, send_email, etc. honge
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 3: Tools (Mock Implementations)")
print("=" * 70)


def search_web(query: str) -> str:
    """Web par search karta hai. Input: search query string."""
    # Offline mock - real mein yahan SerpAPI/Tavily hoga
    fake_results = {
        "ai news":         "2026 ke top AI news: GPT-5 launch, Google Gemini Ultra 2, OpenAI o3 model.",
        "python tutorial": "Python 3.13 release, PEP 703 no-GIL, pyodide 0.27 out.",
        "tesla":           "Tesla Robotaxi launch 2026, Model Y refresh, FSD v14 released.",
        "climate":         "2025 was hottest year on record. Paris agreement targets revised.",
    }
    query_lower = query.lower()
    for key, val in fake_results.items():
        if key in query_lower:
            return val
    return f"Search results for '{query}': Generic information found on internet."


def write_summary(content: str, max_words: int = 50) -> str:
    """Diye gaye content ka summary banata hai. Input: content string."""
    # Offline mock - real mein yahan LLM call hoga
    words = content.split()
    if len(words) <= max_words:
        return content
    return " ".join(words[:max_words]) + "... [summary truncated]"


def format_email(subject: str, body: str) -> str:
    """Email format mein content organize karta hai."""
    return f"SUBJECT: {subject}\n---\n{body}\n---\n[Email formatted successfully]"


def calculator(expression: str) -> str:
    """Math expression calculate karta hai. Input: math expression."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


def get_current_date() -> str:
    """Aaj ki date return karta hai."""
    import datetime
    return datetime.date.today().isoformat()


# Tool registry - executor yahan se tools uthata hai
TOOLS: dict[str, Callable] = {
    "search_web":     search_web,
    "write_summary":  write_summary,
    "format_email":   format_email,
    "calculator":     calculator,
    "get_current_date": get_current_date,
}

print(f"\n  Available tools ({len(TOOLS)} total):")
for name, func in TOOLS.items():
    print(f"    - {name}: {func.__doc__}")


# =============================================================================
# SECTION 4: Planner Component
# Theory se: "Planner LLM: Make a plan" - smarter model use karo
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 4: Planner - Pehle Plan Banao")
print("=" * 70)

# Planner ka system prompt - theory doc ka direct implementation
PLANNER_SYSTEM_PROMPT = """You are a task planner. Given a complex task, break it into clear sequential steps.

Rules:
- Each step should be atomic and executable
- Steps should be in logical order
- Each step should use ONE of the available tools
- Keep steps concrete and specific
- Output ONLY a JSON array of step descriptions

Example output:
["Search for recent news about AI", "Summarize the top 3 stories", "Format as email"]"""


def planner_llm_call(task: str, available_tools: list[str]) -> list[str]:
    """
    LLM ko call karta hai plan generate karne ke liye.
    Agar key nahi hai toh mock plan return karta hai.
    Theory se: planner = smarter model (zyada sochta hai, ek baar)
    """
    if not LIVE_MODE:
        # Offline fallback - task ke basis pe hardcoded plan
        print("  [Planner - OFFLINE] Mock plan generate ho raha hai...")
        if "news" in task.lower() or "digest" in task.lower():
            return [
                "search_web use karo: 'ai news' query se latest AI news dhundo",
                "write_summary use karo: mili news ka concise summary banao",
                "format_email use karo: summary ko email format mein likho",
            ]
        elif "calculat" in task.lower() or "math" in task.lower():
            return [
                "get_current_date use karo: aaj ki date pata karo",
                "calculator use karo: given math expression solve karo",
                "write_summary use karo: result explain karo",
            ]
        else:
            return [
                f"search_web use karo: '{task[:30]}' ke baare mein information dhundo",
                "write_summary use karo: findings ka summary banao",
                "format_email use karo: final answer format karo",
            ]

    # Live mode - Groq API call
    client = get_client()
    user_prompt = f"""Task: {task}

Available tools: {available_tools}

Create a step-by-step plan using these tools. Output JSON array only."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Groq free tier model
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        print(f"  [Planner - LIVE] Groq se raw response: {raw[:100]}...")

        # JSON parse karne ki koshish - agar fail toh regex se lines nikalo
        try:
            steps = json.loads(raw)
            if isinstance(steps, list):
                return [str(s) for s in steps]
        except json.JSONDecodeError:
            pass

        # Fallback: line by line parse karo
        lines = [l.strip().lstrip("-0123456789. ") for l in raw.split("\n") if l.strip()]
        return [l for l in lines if len(l) > 10][:6]

    except Exception as e:
        print(f"  [Planner - ERROR] {e} - offline fallback use ho raha hai")
        return [
            f"search_web use karo: '{task[:20]}' ke baare mein dhundo",
            "write_summary use karo: mili information summarize karo",
        ]


# Demo: planner ko call karte hain
print("\n  Demo: Planner ko task do -")
sample_task = "AI news dhundo aur email digest bhejo"
steps = planner_llm_call(sample_task, list(TOOLS.keys()))
print(f"\n  Task: '{sample_task}'")
print(f"  Generated Plan ({len(steps)} steps):")
for i, step in enumerate(steps, 1):
    print(f"    {i}. {step}")


# =============================================================================
# SECTION 5: Executor Component
# Theory se: Executor = cheaper model, ek step pe focus, context mein pichle results
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 5: Executor - Ek-Ek Step Execute Karo")
print("=" * 70)

EXECUTOR_SYSTEM_PROMPT = """You are a task executor. You must execute ONE specific step using available tools.

Instructions:
- Read the step description carefully
- Choose the most appropriate tool
- Respond ONLY in this format:
TOOL: tool_name
INPUT: the input to pass to the tool
- If no tool is needed, respond:
TOOL: none
INPUT: direct answer here"""


def executor_llm_call(step_desc: str, context: str, available_tools: list[str]) -> tuple[str, str]:
    """
    Ek step execute karne ke liye LLM call karta hai.
    Return: (tool_name, tool_input) - executor decide karta hai kaun sa tool, kya input
    Theory se: executor = cheaper model (bas ek step pe focus)
    """
    if not LIVE_MODE:
        # Offline: step description se tool aur input guess karo
        print(f"  [Executor - OFFLINE] Step parse kar raha hai: '{step_desc[:50]}...'")

        step_lower = step_desc.lower()

        # Simple keyword matching se tool select karo
        if "search_web" in step_lower or "dhundo" in step_lower or "search" in step_lower:
            # Query extract karo - single quotes ya 'XYZ' pattern dhundo
            m = re.search(r"['\"]([^'\"]+)['\"]", step_desc)
            query = m.group(1) if m else "ai news"
            return "search_web", query

        elif "write_summary" in step_lower or "summary" in step_lower or "summarize" in step_lower:
            # Context ka last result use karo
            last_result = context.split("\n")[-1] if context else "General information"
            last_result = last_result.replace("Step 1 result: ", "").replace("Step 2 result: ", "")
            return "write_summary", last_result[:300]

        elif "format_email" in step_lower or "email" in step_lower:
            return "format_email", json.dumps({"subject": "AI News Digest", "body": context[:200] or "Summary ready."})

        elif "calculator" in step_lower or "calculat" in step_lower or "math" in step_lower:
            m = re.search(r"[\d\s\+\-\*\/\(\)\.]+", step_desc)
            expr = m.group(0).strip() if m else "2 + 2"
            return "calculator", expr

        elif "get_current_date" in step_lower or "date" in step_lower:
            return "get_current_date", ""

        else:
            return "write_summary", f"Task: {step_desc[:100]}"

    # Live mode - Groq API call
    client = get_client()
    user_prompt = f"""Step to execute: {step_desc}

Prior context (previous steps results):
{context}

Available tools: {available_tools}

Choose ONE tool and provide input."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        print(f"  [Executor - LIVE] Response: {raw[:80]}...")

        # Parse TOOL: ... INPUT: ... format
        tool_match  = re.search(r"TOOL:\s*(\w+)",  raw, re.IGNORECASE)
        input_match = re.search(r"INPUT:\s*(.*)",  raw, re.IGNORECASE | re.DOTALL)

        tool_name   = tool_match.group(1).strip()  if tool_match  else "write_summary"
        tool_input  = input_match.group(1).strip() if input_match else step_desc

        return tool_name, tool_input

    except Exception as e:
        print(f"  [Executor - ERROR] {e} - fallback use ho raha hai")
        return "write_summary", f"Step complete: {step_desc[:80]}"


def run_tool(tool_name: str, tool_input: str) -> str:
    """
    Tool registry se tool uthao aur run karo.
    Error aaye toh gracefully handle karo - plan continue karta rahe.
    """
    if tool_name == "none":
        return tool_input  # Direct answer

    if tool_name not in TOOLS:
        return f"[Tool '{tool_name}' nahi mila. Available: {list(TOOLS.keys())}]"

    try:
        import inspect
        func = TOOLS[tool_name]
        sig  = inspect.signature(func)
        # No-arg tools (jaise get_current_date) - empty string ignore karo
        if len(sig.parameters) == 0:
            return func()
        # format_email ko dict input chahiye - JSON parse karne ki koshish
        if tool_name == "format_email":
            try:
                kwargs = json.loads(tool_input)
                return func(**kwargs)
            except (json.JSONDecodeError, TypeError):
                return func(subject="Summary", body=tool_input)
        else:
            return func(tool_input)
    except Exception as e:
        return f"[Tool error in {tool_name}: {e}]"


# Demo: ek step execute karte hain
print("\n  Demo: Executor ko ek step do -")
ex_step = "search_web use karo: 'ai news' query se latest AI news dhundo"
ex_context = "No prior context."
tool, inp = executor_llm_call(ex_step, ex_context, list(TOOLS.keys()))
result = run_tool(tool, inp)
print(f"  Step: {ex_step[:60]}")
print(f"  Chose tool: {tool}")
print(f"  Tool input: {inp[:60]}")
print(f"  Tool result: {result[:100]}")


# =============================================================================
# SECTION 6: Main PlanAndExecuteAgent Class
# Theory se: plan() -> execute_step() loop -> synthesize() -> final answer
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 6: PlanAndExecuteAgent - Poora Agent")
print("=" * 70)


class PlanAndExecuteAgent:
    """
    Theory doc ka core implementation.
    Flow:
      1. plan()         - Planner LLM se steps generate karo
      2. execute()      - Har step ke liye Executor LLM + Tool run karo
      3. synthesize()   - Sab results combine karke final answer do

    Interview mein yeh zaror poochha jaata hai:
      Q: Planner aur Executor different models kyun hote hain?
      A: Planner smart (costly) hona chahiye - ek baar complex planning.
         Executor cheap (fast) hona chahiye - baar-baar simple execution.
    """

    def __init__(
        self,
        tools: dict,
        planner_model: str = "llama-3.1-70b-versatile",  # Groq strong model
        executor_model: str = "llama-3.1-8b-instant",    # Groq cheap/fast model
        max_replan_attempts: int = 2,
    ):
        self.tools = tools
        self.planner_model = planner_model
        self.executor_model = executor_model
        self.max_replan_attempts = max_replan_attempts

    def plan(self, task: str) -> ExecutionPlan:
        """
        Planner LLM ko call karo aur ExecutionPlan create karo.
        Theory se: yeh ONCE hota hai, pure task ke liye.
        """
        print(f"\n  [PLANNER] Task ke liye plan bana raha hai...")
        step_descs = planner_llm_call(task, list(self.tools.keys()))

        plan = ExecutionPlan(task=task)
        for desc in step_descs:
            plan.add_step(desc)

        plan.print_plan("Planner Generated Plan")
        return plan

    def execute_step(self, step: PlanStep, plan: ExecutionPlan) -> bool:
        """
        Ek PlanStep execute karo.
        Return: True agar success, False agar fail.
        Context = pichle steps ke results - executor ko context milti hai.
        """
        step.status = "running"
        context = plan.get_context(step.index)

        print(f"\n  [EXECUTOR] Step {step.index + 1}: {step.description[:70]}")

        tool_name, tool_input = executor_llm_call(
            step_desc=step.description,
            context=context,
            available_tools=list(self.tools.keys()),
        )

        result = run_tool(tool_name, tool_input)

        # Error check karo
        if result.startswith("[Tool error") or result.startswith("[Tool '"):
            step.status = "failed"
            step.error  = result
            print(f"  [EXECUTOR] Step {step.index + 1} FAIL: {result[:80]}")
            return False

        step.result = result
        step.status = "done"
        print(f"  [EXECUTOR] Step {step.index + 1} DONE: {result[:80]}")
        return True

    def replan(self, task: str, current_plan: ExecutionPlan, failed_at: int) -> list[str]:
        """
        Theory doc ka Section 5: Replanning.
        Jab koi step fail hota hai toh remaining steps ke liye nayi plan banao.
        'pichle steps ke results' context ke roop mein use hota hai.
        """
        print(f"\n  [REPLANNER] Step {failed_at + 1} fail hua - replanning...")
        done_context = current_plan.get_context(failed_at)
        modified_task = f"""Original task: {task}

Already completed:
{done_context}

Failed step was: {current_plan.steps[failed_at].description}
Error: {current_plan.steps[failed_at].error}

Generate ONLY the remaining steps to complete the task. Avoid the failed approach."""

        return planner_llm_call(modified_task, list(self.tools.keys()))

    def synthesize(self, task: str, plan: ExecutionPlan) -> str:
        """
        Theory se: final answer = sab step results ko combine karo.
        Yahan simple concatenation use kar rahe hain (LLM call bhi ho sakta tha).
        """
        all_results = []
        for step in plan.steps:
            if step.status == "done" and step.result:
                all_results.append(f"Step {step.index + 1} ({step.description[:40]}): {step.result[:200]}")

        if not all_results:
            return "Koi bhi step successfully complete nahi hua."

        synthesis = f"Task: {task}\n\nResults:\n" + "\n".join(all_results)
        return synthesis

    def run(self, task: str, enable_replan: bool = True) -> dict:
        """
        Main entry point.
        Theory doc ka complete flow:
          plan() -> execute each step -> replan if needed -> synthesize()
        """
        print(f"\n{'='*60}")
        print(f"  TASK: {task}")
        print(f"{'='*60}")

        start_time = time.time()
        replan_count = 0

        # Step 1: Plan banao
        plan = self.plan(task)

        # Step 2: Execute karo
        i = 0
        while i < len(plan.steps):
            step = plan.steps[i]
            success = self.execute_step(step, plan)

            if not success and enable_replan and replan_count < self.max_replan_attempts:
                # Replan karo
                replan_count += 1
                new_step_descs = self.replan(task, plan, i)

                # Failed step ke baad naye steps inject karo
                new_steps = []
                for desc in new_step_descs:
                    new_step = PlanStep(index=len(plan.steps) + len(new_steps), description=desc)
                    new_steps.append(new_step)

                # Plan mein add karo (failed step ke baad)
                plan.steps = plan.steps[:i + 1] + new_steps
                print(f"  [REPLAN] {len(new_steps)} naye steps add kiye gaye")
                plan.print_plan(f"Updated Plan (after replan #{replan_count})")
                i += 1  # Failed step skip, naye steps pe chalo
            elif not success:
                print(f"  [SKIP] Step {i + 1} fail hua, aage badh rahe hain...")
                i += 1
            else:
                i += 1

        # Step 3: Synthesize
        final_answer = self.synthesize(task, plan)
        elapsed = time.time() - start_time

        plan.print_plan("Final Plan Status")

        return {
            "task":          task,
            "final_answer":  final_answer,
            "steps_total":   len(plan.steps),
            "steps_done":    sum(1 for s in plan.steps if s.status == "done"),
            "steps_failed":  sum(1 for s in plan.steps if s.status == "failed"),
            "replan_count":  replan_count,
            "elapsed_sec":   elapsed,
        }


# =============================================================================
# SECTION 7: Self-Demo - Main offline demo chalao
# Yahan alag-alag tasks ke saath agent run hota hai
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 7: Self-Demo - Agent Run Karo")
print("=" * 70)

agent = PlanAndExecuteAgent(tools=TOOLS)

# Demo Task 1: AI News Digest
result1 = agent.run("AI news dhundo aur email digest format mein prepare karo")
print(f"\n  [Result 1]")
print(f"  Steps done:   {result1['steps_done']}/{result1['steps_total']}")
print(f"  Replan count: {result1['replan_count']}")
print(f"  Time:         {result1['elapsed_sec']:.2f}s")
print(f"  Answer:\n{result1['final_answer'][:400]}")

print()

# Demo Task 2: Math calculation
result2 = agent.run("Aaj ki date pata karo aur 1234 * 5678 calculate karo")
print(f"\n  [Result 2]")
print(f"  Steps done: {result2['steps_done']}/{result2['steps_total']}")
print(f"  Answer:\n{result2['final_answer'][:300]}")


# =============================================================================
# SECTION 8: ReAct vs Plan-and-Execute - Side by side comparison demo
# Theory doc Section 4 ka practical demonstration
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 8: ReAct vs Plan-and-Execute (Side-by-Side Demo)")
print("=" * 70)

# Theory doc se sab seekhe points ko demonstrate karo
print("""
  REACT APPROACH (yeh sirf illustrate hai, actual ReAct agent nahi):
  ----------------------------------------------------------------
  Question: "AI news dhundo aur email bhejo"

  Iter 1: Thought -> kya karna chahiye? search karna chahiye
          Action  -> search_web("ai news")
          Obs     -> "GPT-5, Gemini Ultra 2..."

  Iter 2: Thought -> ab summary banana chahiye
          Action  -> write_summary(prev_result)
          Obs     -> "Summary: GPT-5..."

  Iter 3: Thought -> email format chahiye
          Action  -> format_email(...)
          Obs     -> "SUBJECT: AI Digest..."

  Iter 4: Thought -> answer ready hai
          Final Answer: "Email ready!"

  Total: 4 LLM calls (smart model har baar)
  ---
  PLAN-AND-EXECUTE APPROACH (jo humne abhi implement kiya):
  -------------------------------------------------------
  Phase 1 - PLAN (1 smart model call):
    Step 1: search_web("ai news")
    Step 2: write_summary(results)
    Step 3: format_email(summary)

  Phase 2 - EXECUTE (cheap model x3 calls):
    Executor Step 1 -> search_web -> "GPT-5..."
    Executor Step 2 -> write_summary -> "Summary..."
    Executor Step 3 -> format_email -> "Email ready!"

  Total: 1 (smart) + 3 (cheap) = 4 calls, par CHEAPER overall!
""")

print("  KEY INSIGHT:")
print("  - Simple tasks pe: ReAct better (less overhead)")
print("  - Complex multi-step tasks pe: Plan-and-Execute better (cheaper, clearer)")
print("  - Replan zaroorat pe: Plan-and-Execute mein built-in support hai")


# =============================================================================
# SECTION 9: Replanning Demo
# Theory doc Section 5 - "What if execution fails mid-plan?"
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 9: Replanning Demo - Step Fail Hone Pe")
print("=" * 70)

print("""
  Theory se pseudo-code (doc 5, Section 5):

    def run_with_replan(question):
        plan = self.plan(question)
        results = {}
        i = 0
        while i < len(plan):
            try:
                results[i] = self.execute_step(plan[i], results)
                i += 1
            except Exception as e:
                # Replan from here
                remaining = self.replan(question, plan, i, results)
                plan = plan[:i] + remaining
        return self.synthesize(question, plan, results)

  Hamara implementation mein:
    - step.status = "failed" jab tool error return kare
    - enable_replan=True hone par planner ko remaining steps ke liye
      naya plan banane ke liye call kiya jaata hai
    - Naye steps failed step ke baad inject ho jaate hain
    - max_replan_attempts = 2 (infinite loop prevent karne ke liye)
""")

# Simulate a plan with a deliberate failure then replan
print("  [Demo] Ek plan jisme step fail hoga:")

class DemoAgentWithForcedFailure(PlanAndExecuteAgent):
    """Sirf demo ke liye - step 2 ko force-fail karte hain."""
    def execute_step(self, step, plan):
        # Step 2 (index 1) ko intentionally fail karo
        if step.index == 1:
            step.status = "failed"
            step.error  = "[Simulated failure: API rate limit hit]"
            print(f"  [EXECUTOR] Step {step.index + 1} FORCED FAIL (demo)")
            return False
        return super().execute_step(step, plan)

demo_agent = DemoAgentWithForcedFailure(tools=TOOLS, max_replan_attempts=1)
demo_result = demo_agent.run("Search karo aur summary banao", enable_replan=True)
print(f"\n  Replan count: {demo_result['replan_count']}")
print(f"  Steps done:   {demo_result['steps_done']}/{demo_result['steps_total']}")


# =============================================================================
# SECTION 10: Performance Metrics - Agent kitna efficient hai?
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 10: Agent Efficiency Metrics")
print("=" * 70)

# Summary of all runs
all_runs = [result1, result2, demo_result]
print(f"\n  {'Task':<35} {'Steps':<12} {'Time':<10} {'Replans'}")
print("  " + "-" * 65)
for r in all_runs:
    task_short = r["task"][:33] + ".." if len(r["task"]) > 35 else r["task"]
    steps_str  = f"{r['steps_done']}/{r['steps_total']}"
    print(f"  {task_short:<35} {steps_str:<12} {r['elapsed_sec']:<9.2f}s {r['replan_count']}")

total_steps_done = sum(r["steps_done"] for r in all_runs)
total_steps      = sum(r["steps_total"] for r in all_runs)
success_rate     = total_steps_done / total_steps * 100 if total_steps > 0 else 0
print(f"\n  Overall success rate: {success_rate:.0f}% ({total_steps_done}/{total_steps} steps)")


# =============================================================================
# SECTION 11: Interview Cheat Sheet
# Yeh section sirf reference ke liye hai - run karne pe print hoga
# =============================================================================

print("\n" + "=" * 70)
print("SECTION 11: Interview Cheat Sheet")
print("=" * 70)
print("""
  Q1: Plan-and-Execute kya hai?
  A:  Pehle POORA plan banao (planner LLM), fir ek-ek step execute karo
      (executor LLM). ReAct reactive hai, Plan-and-Execute upfront hai.

  Q2: Planner aur Executor different kyun hote hain?
  A:  Planner = smarter/costly model (complex planning, ek baar).
      Executor = cheaper/faster model (simple execution, baar-baar).
      Isse cost kam hoti hai without quality loss.

  Q3: Replanning kab hota hai?
  A:  Jab koi step fail ho jaaye - planner ko baaki steps ke liye
      naya plan banane ke liye call kiya jaata hai, context (done steps)
      provide karke.

  Q4: Kab ReAct use karo, kab Plan-and-Execute?
  A:  ReAct: exploratory tasks, few steps, dynamic/unpredictable.
      P&E: structured multi-step, research reports, batch pipelines,
           known phases (data pipeline, blog writing, email digest).

  Q5: Plan-and-Execute ka limitation kya hai?
  A:  Plan upfront fix hoti hai - agar execution se naya information mile
      jo plan change kare, woh handle nahi hota (unless replan karo).
      ReAct zyada adaptive hai surprises ke liye.
""")


# =============================================================================
# SECTION 12: Exercises
# =============================================================================

print("=" * 70)
print("SECTION 12: Exercises - Try Karo!")
print("=" * 70)
print("""
  EASY:
    1. Ek naya tool add karo: translate(text, target_lang) - mock implementation.
       Agent ko use karo: "AI news dhundo aur Hindi mein translate karo".

    2. PlanAndExecuteAgent mein step timeout add karo (ek step 5 sec se zyada
       le toh fail mark karo aur replan karo).

  MEDIUM:
    3. Parallel step execution: agar 2 steps independent hain (context use nahi
       karte) toh unhe asyncio.gather() se simultaneously run karo.

    4. Plan ko JSON file mein save karo aur mid-execution pe load karo -
       "resume" feature implement karo.

  HARD:
    5. GROQ_API_KEY set karo aur live mode mein chala ke dekho planner aur
       executor ka actual output kaisa hota hai.

    6. Plan quality evaluator banao: planner ke baad ek third LLM call karo
       jo plan ke steps review kare aur "APPROVED" ya "NEEDS_REVISION" de.
       Revision pe automatically replan karo.

  PRO:
    7. Multi-agent version: ek supervisor Plan-and-Execute agent banao jo
       complex tasks ko sub-tasks mein todte waqt specialist ReAct agents
       ko delegate karta hai (research agent, code agent, write agent).
""")


# =============================================================================
# Final exit - always EXIT 0
# =============================================================================

print("\n" + "=" * 70)
print("  Plan-and-Execute Lab COMPLETE!")
print("  Theory covered: Sections 1-8 of 05_plan_and_execute.md")
print("  Run with GROQ_API_KEY for live LLM calls.")
print("=" * 70)
