"""
Phase5_Agent_Patterns — Complete Practical
============================================
Topics:
  1. ReAct (Reasoning + Acting)
  2. Plan-and-Execute
  3. Reflexion (self-critique + retry)
  4. Parallel tool execution
  5. Tool error handling + retry
  6. Agent evaluation metrics

Install: pip install langchain langchain-openai
Run: python 01_agent_patterns_practical.py
"""

import os, json, asyncio, time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("AGENT PATTERNS")
print("=" * 60)

PATTERN_CONCEPTS = {
    "ReAct":             "Thought → Action → Observation loop. Interleaves reasoning and tool calls.",
    "Plan-and-Execute":  "Plan ALL steps first (planner LLM), then execute each (executor LLM).",
    "Reflexion":         "Self-critique: generate → critique → revise. Improves output quality.",
    "Parallel Tools":    "Call multiple independent tools simultaneously (asyncio.gather).",
    "Tool Retry":        "Retry failed tool calls with exponential backoff.",
    "Self-consistency":  "Run same prompt multiple times, majority vote on answer.",
    "LATS":              "Language Agent Tree Search — MCTS-style exploration + backtracking.",
}
for k, v in PATTERN_CONCEPTS.items():
    print(f"  {k:<20}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: ReAct Pattern
# INTERVIEW: Thought/Action/Observation loop — original agentic pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: ReAct Pattern")
print("=" * 60)

REACT_CODE = '''\
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# ── Define tools ────────────────────────────────────────────────
@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"

@tool
def get_date() -> str:
    """Get the current date."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

tools = [search, calculate, get_date]
llm   = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ── ReAct prompt ──────────────────────────────────────────────
# INTERVIEW: hwchase17/react is the canonical ReAct prompt
prompt = hub.pull("hwchase17/react")

# ── Build agent ───────────────────────────────────────────────
agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

executor = AgentExecutor(
    agent                = agent,
    tools                = tools,
    verbose              = True,
    max_iterations       = 10,         # prevent infinite loops
    max_execution_time   = 60,         # timeout in seconds
    handle_parsing_errors = True,      # recover from LLM format errors
    return_intermediate_steps = True,  # see thought/action/obs
)

result = executor.invoke({"input": "What is 1234 * 5678? Also what year is it?"})
# Intermediate steps show the ReAct trace:
for step in result["intermediate_steps"]:
    action, observation = step
    print(f"Thought/Action: {action.log[:100]}")
    print(f"Observation: {observation[:50]}")
print(f"Final: {result['output']}")
'''
print(REACT_CODE[:700])

print("\n  ReAct trace format:")
REACT_TRACE = [
    ("Thought", "I need to calculate 1234 * 5678"),
    ("Action",  "calculate"),
    ("Input",   "1234 * 5678"),
    ("Obs",     "7006652"),
    ("Thought", "Now I need the year"),
    ("Action",  "get_date"),
    ("Input",   ""),
    ("Obs",     "2025-05-22"),
    ("Thought", "I have all information"),
    ("Answer",  "1234 * 5678 = 7,006,652. The year is 2025."),
]
for step, content in REACT_TRACE:
    print(f"  {step:<10}: {content}")


# Mock ReAct loop implementation
class MockTool:
    def __init__(self, name: str, func: Callable):
        self.name = name
        self.func = func

    def run(self, input_str: str) -> str:
        try:
            return str(self.func(input_str))
        except Exception as e:
            return f"Error: {e}"


def mock_react_loop(
    question: str,
    tools: List[MockTool],
    max_iterations: int = 5,
) -> str:
    """
    INTERVIEW: ReAct = iterative loop.
    1. LLM thinks (Thought)
    2. LLM picks tool (Action)
    3. Tool runs (Observation)
    4. Repeat until LLM says "Final Answer:"
    """
    tool_map = {t.name: t for t in tools}
    print(f"\n  ReAct loop for: '{question}'")

    # Simulate tool selection for demo
    actions = [
        ("calculate", "2 + 2", "arithmetic question"),
        ("get_date",  "",      "date question"),
    ]

    for i, (action_name, action_input, thought) in enumerate(actions):
        if i >= max_iterations:
            break
        print(f"\n  Iter {i+1}:")
        print(f"    Thought: {thought}")
        print(f"    Action:  {action_name}({action_input!r})")
        if action_name in tool_map:
            obs = tool_map[action_name].run(action_input)
            print(f"    Obs:     {obs}")

    return "Final Answer: [Mock answer based on observations]"


tools = [
    MockTool("calculate", lambda x: eval(x, {"__builtins__": {}}) if x else ""),
    MockTool("get_date",  lambda _: "2025-05-22"),
]
mock_react_loop("What is 2+2 and what is today's date?", tools)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Plan-and-Execute Pattern
# INTERVIEW: Planner creates plan first, executor runs each step
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Plan-and-Execute Pattern")
print("=" * 60)

PLAN_EXEC_CODE = '''\
from langchain_experimental.plan_and_execute import (
    PlanAndExecute, load_agent_executor, load_chat_planner
)
from langchain_openai import ChatOpenAI

# ── Plan-and-Execute ────────────────────────────────────────────
# INTERVIEW: Two-LLM pattern
# Planner: strong model (gpt-4o) creates complete plan upfront
# Executor: cheaper model (gpt-4o-mini) executes each step

planner  = load_chat_planner(ChatOpenAI(model="gpt-4o", temperature=0))
executor = load_agent_executor(
    ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools,
    verbose=True,
)

agent = PlanAndExecute(planner=planner, executor=executor, verbose=True)

result = agent.invoke({"input": "Research Python async and write a 200-word summary"})

# INTERVIEW: Plan created upfront:
# Step 1: Search for Python async programming information
# Step 2: Search for asyncio best practices
# Step 3: Combine information into a 200-word summary
# Step 4: Review summary for accuracy
# Execute each step sequentially using executor agent
'''
print(PLAN_EXEC_CODE[:600])

print("\n  Plan-and-Execute flow:")


@dataclass
class Plan:
    steps: List[str]
    status: List[str] = field(default_factory=list)
    results: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.status  = ["pending"] * len(self.steps)
        self.results = [""] * len(self.steps)

    def execute_step(self, i: int, result: str):
        self.results[i] = result
        self.status[i]  = "done"

    def is_complete(self) -> bool:
        return all(s == "done" for s in self.status)


def mock_planner(task: str) -> Plan:
    """Simulate a planner LLM generating steps."""
    steps = [
        f"Research: Find information about {task[:20]}",
        f"Analyze: Process and organize findings",
        f"Synthesize: Combine information into answer",
        f"Review: Verify accuracy and completeness",
    ]
    return Plan(steps=steps)


def mock_executor(step: str, context: str = "") -> str:
    """Simulate an executor LLM running a step."""
    return f"[Result of: {step[:40]}] Context used: {context[:30] if context else 'none'}"


task  = "Research Python async patterns"
plan  = mock_planner(task)
print(f"\n  Task: {task}")
print(f"  Plan ({len(plan.steps)} steps):")
for i, step in enumerate(plan.steps):
    print(f"    {i+1}. {step}")

print("\n  Executing steps:")
for i, step in enumerate(plan.steps):
    context = plan.results[i-1] if i > 0 else ""
    result  = mock_executor(step, context)
    plan.execute_step(i, result)
    print(f"    Step {i+1} ✓: {result[:60]}")

print(f"\n  Plan complete: {plan.is_complete()}")
print("  INTERVIEW: Plan-and-Execute better for multi-step tasks,")
print("  ReAct better for dynamic problems where plan changes based on results")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Reflexion Pattern
# INTERVIEW: Generate → Critique → Revise loop for quality improvement
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Reflexion Pattern")
print("=" * 60)

REFLEXION_CODE = '''\
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# ── Reflexion: Generate → Critique → Revise ────────────────────
# INTERVIEW: Reflexion = agent critiques its own output and improves it

generate_chain = ChatPromptTemplate.from_template(
    "Answer this question: {question}"
) | ChatOpenAI(model="gpt-4o-mini") | StrOutputParser()

critique_chain = ChatPromptTemplate.from_template(
    "Critique this answer to the question \'{question}\':\\n{answer}\\n\\n"
    "Identify: [1] factual errors, [2] missing info, [3] unclear parts. "
    "Rate quality 1-10. If score >= 8, say ACCEPTABLE."
) | ChatOpenAI(model="gpt-4o-mini") | StrOutputParser()

revise_chain = ChatPromptTemplate.from_template(
    "Original question: {question}\\n"
    "Original answer: {answer}\\n"
    "Critique: {critique}\\n\\n"
    "Write an improved answer addressing all critique points."
) | ChatOpenAI(model="gpt-4o-mini") | StrOutputParser()

def reflexion_loop(question: str, max_iterations: int = 3) -> str:
    answer = generate_chain.invoke({"question": question})
    for i in range(max_iterations):
        critique = critique_chain.invoke({"question": question, "answer": answer})
        if "ACCEPTABLE" in critique:
            print(f"Answer accepted at iteration {i+1}")
            break
        answer = revise_chain.invoke({
            "question": question,
            "answer":   answer,
            "critique": critique,
        })
    return answer
'''
print(REFLEXION_CODE[:700])


# Mock Reflexion implementation
@dataclass
class ReflexionState:
    question: str
    answer: str = ""
    critique: str = ""
    score: int = 0
    iterations: int = 0


def mock_reflexion(question: str, max_iterations: int = 3) -> ReflexionState:
    """
    INTERVIEW: Reflexion improves output quality through self-critique.
    Key insight: LLM is better at EVALUATING than GENERATING on first try.
    """
    state = ReflexionState(question=question)
    scores = [5, 7, 9]  # simulate improving quality

    print(f"\n  Reflexion for: '{question}'")
    state.answer = f"[Initial answer to '{question[:30]}']"

    for i in range(max_iterations):
        state.iterations = i + 1
        state.score      = scores[min(i, len(scores)-1)]
        state.critique   = (
            f"Issues: [1] Missing examples, [2] Too brief. Score: {state.score}/10"
            if state.score < 8 else
            "Answer is comprehensive and accurate. ACCEPTABLE. Score: 9/10"
        )
        print(f"\n  Iteration {i+1}:")
        print(f"    Answer:  {state.answer[:60]}...")
        print(f"    Critique: {state.critique[:70]}...")

        if "ACCEPTABLE" in state.critique:
            print(f"  ✓ Accepted at iteration {i+1}")
            break
        state.answer = f"[Revised answer v{i+2}: added examples and more detail...]"

    return state


result = mock_reflexion("Explain Python's GIL", max_iterations=3)
print(f"\n  Final score: {result.score}/10 after {result.iterations} iterations")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Parallel Tool Execution
# INTERVIEW: Use asyncio.gather for independent tool calls
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Parallel Tool Execution")
print("=" * 60)

PARALLEL_CODE = '''\
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# INTERVIEW: Parallel tool calling = multiple tools called simultaneously
# Claude/GPT-4 can return multiple tool_calls in ONE response!

@tool
async def get_stock_price(ticker: str) -> str:
    """Get stock price."""
    await asyncio.sleep(1)   # simulates API call
    return f"{ticker}: $150"

@tool
async def get_news(company: str) -> str:
    """Get latest news."""
    await asyncio.sleep(1)
    return f"News about {company}: ..."

@tool
async def get_financials(ticker: str) -> str:
    """Get financial data."""
    await asyncio.sleep(1)
    return f"Financials for {ticker}: PE=25, Revenue=$50B"

# ── Claude returns multiple tool calls at once ─────────────────
import anthropic

client   = anthropic.Anthropic()
response = client.messages.create(
    model    = "claude-sonnet-4-5",
    max_tokens = 1024,
    tools    = [get_stock_price, get_news, get_financials],
    messages = [{"role": "user", "content": "Analyze AAPL stock"}],
)

# Claude might return:
# tool_use: get_stock_price("AAPL")
# tool_use: get_news("Apple")
# tool_use: get_financials("AAPL")
# All at once! Execute in parallel:

tool_calls = [block for block in response.content if block.type == "tool_use"]
tasks = [
    tool_map[call.name].ainvoke(call.input)
    for call in tool_calls
]
results = await asyncio.gather(*tasks)  # ← ALL tools run simultaneously!
# Without parallel: 3 × 1s = 3 seconds
# With parallel:    max(1s, 1s, 1s) = 1 second
'''
print(PARALLEL_CODE[:700])


# Demo parallel timing
async def mock_tool(name: str, duration: float) -> str:
    await asyncio.sleep(duration)
    return f"{name} result"


async def demo_parallel():
    print("\n  Parallel tool execution demo:")
    tools_with_duration = [
        ("get_weather", 0.05),
        ("get_news",    0.08),
        ("get_stocks",  0.06),
    ]

    # Sequential
    start = time.time()
    results_seq = []
    for name, dur in tools_with_duration:
        r = await mock_tool(name, dur)
        results_seq.append(r)
    seq_time = time.time() - start
    print(f"  Sequential: {seq_time:.3f}s — {[r[:15] for r in results_seq]}")

    # Parallel
    start = time.time()
    results_par = await asyncio.gather(
        *[mock_tool(name, dur) for name, dur in tools_with_duration]
    )
    par_time = time.time() - start
    print(f"  Parallel:   {par_time:.3f}s — {[r[:15] for r in results_par]}")
    print(f"  Speedup:    {seq_time/par_time:.1f}x faster")


asyncio.run(demo_parallel())


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Tool Error Handling
# INTERVIEW: Agents must handle tool failures gracefully
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Tool Error Handling & Retry")
print("=" * 60)

ERROR_HANDLING_CODE = '''\
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio

# ── Retry with exponential backoff ────────────────────────────
@retry(
    stop              = stop_after_attempt(3),
    wait              = wait_exponential(multiplier=1, min=1, max=10),
    retry             = retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise           = True,
)
async def call_tool_with_retry(tool_name: str, args: dict) -> str:
    """Call a tool with automatic retry on transient failures."""
    result = await tool_registry[tool_name](**args)
    return result

# ── Handle tool errors in agent loop ──────────────────────────
async def agent_loop_with_error_handling(question: str):
    messages = [{"role": "user", "content": question}]
    for iteration in range(10):
        response = await llm.ainvoke(messages)
        if response.stop_reason == "end_turn":
            return response.content[0].text

        for tool_call in response.tool_calls:
            try:
                result = await call_tool_with_retry(tool_call.name, tool_call.args)
                tool_result = {"success": True, "result": result}
            except Exception as e:
                # INTERVIEW: Tell LLM about the error — it can try a different approach
                tool_result = {
                    "success": False,
                    "error":   str(e),
                    "hint":    f"Tool {tool_call.name} failed. Try alternative approach.",
                }
            messages.append(build_tool_result_message(tool_call.id, tool_result))
'''
print(ERROR_HANDLING_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Agent Evaluation Metrics
# INTERVIEW: How to measure agent quality
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Agent Evaluation Metrics")
print("=" * 60)

EVAL_METRICS = {
    "Task Success Rate":     "% of tasks completed correctly. Primary metric.",
    "Tool Call Accuracy":    "% of tool calls with correct name + arguments.",
    "Steps to Completion":   "Avg tool calls needed. Lower = more efficient.",
    "Hallucination Rate":    "% of responses with fabricated information.",
    "Tool Error Rate":       "% of tool calls that fail/error.",
    "Latency (P50/P99)":     "Response time percentiles. P99 = worst-case.",
    "Cost per Task":         "Total LLM tokens used × price per token.",
    "Human Eval Score":      "Human ratings on helpfulness, accuracy, safety.",
}
for metric, desc in EVAL_METRICS.items():
    print(f"  {metric:<28}: {desc}")

EVAL_CODE = '''\
# ── LangSmith evaluation ─────────────────────────────────────
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

# Define evaluator
def correct_tool_used(run, example):
    """Check if agent used the correct tool."""
    tool_calls = [s[0].tool for s in run.outputs.get("intermediate_steps", [])]
    expected   = example.outputs["expected_tool"]
    return {"score": 1 if expected in tool_calls else 0}

# Evaluate on dataset
results = evaluate(
    agent.invoke,
    data      = "agent-test-dataset",
    evaluators= [correct_tool_used],
    metadata  = {"model": "gpt-4o-mini", "agent_type": "react"},
)
print(results.to_pandas())
# → DataFrame with score per example + aggregate stats
'''
print(f"\n{EVAL_CODE[:400]}")


# Mock evaluation
@dataclass
class AgentEvalResult:
    task: str
    success: bool
    tool_calls: List[str]
    steps: int
    latency_ms: float


def evaluate_agent_run(task: str, expected_tools: List[str]) -> AgentEvalResult:
    """Mock agent evaluation."""
    import random
    random.seed(hash(task))
    used_tools  = random.sample(expected_tools + ["extra_tool"], len(expected_tools))
    success     = all(t in used_tools for t in expected_tools)
    return AgentEvalResult(
        task       = task,
        success    = success,
        tool_calls = used_tools,
        steps      = len(used_tools) + random.randint(0, 2),
        latency_ms = random.uniform(500, 2000),
    )


print("\n  Mock agent evaluation:")
test_cases = [
    ("Calculate 15% of 2500",        ["calculate"]),
    ("Search for Python tutorials",  ["search"]),
    ("Get today's date and weather", ["get_date", "search"]),
]
results = [evaluate_agent_run(task, tools) for task, tools in test_cases]
success_rate = sum(r.success for r in results) / len(results)
avg_steps    = sum(r.steps for r in results) / len(results)
avg_latency  = sum(r.latency_ms for r in results) / len(results)

for r in results:
    icon = "✓" if r.success else "✗"
    print(f"  {icon} {r.task[:40]:<40} {r.steps} steps, {r.latency_ms:.0f}ms")

print(f"\n  Metrics:")
print(f"  Success rate: {success_rate:.1%}")
print(f"  Avg steps:    {avg_steps:.1f}")
print(f"  Avg latency:  {avg_latency:.0f}ms")


print("\n" + "=" * 60)
print("AGENT PATTERNS INTERVIEW SUMMARY:")
print("  ReAct: Thought→Action→Observation loop. Best for dynamic problems.")
print("  Plan-and-Execute: Plan all steps first, then execute. Good for complex tasks.")
print("  Reflexion: Generate→Critique→Revise loop. Improves output quality.")
print("  Parallel: asyncio.gather for independent tool calls. N× speedup.")
print("  Error handling: retry transient errors, tell LLM about failures.")
print("  Eval metrics: success rate, tool accuracy, steps, latency, cost.")
print("=" * 60)
