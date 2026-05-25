"""
Level 6 — Doc 4: ReAct Pattern (PRACTICAL — From Scratch)
==========================================================
Build a complete ReAct agent with NO framework. Pure Python + OpenAI.

Topics:
  1. Basic ReAct agent (simple)
  2. Production-grade with timeout, budget, stuck detection
  3. Streaming events
  4. Multiple tools demo
  5. Comparison with function calling

Install: pip install openai python-dotenv
Run: python 04_react_pattern_practical.py
"""

import os
import json
import re
import time
from typing import Optional, Callable
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tools (mock implementations)
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(city: str) -> str:
    """Get current weather for a city. Returns temperature and condition."""
    fake = {"Mumbai": "32°C, sunny", "Delhi": "28°C, cloudy", "Bangalore": "24°C, rainy"}
    return fake.get(city, "Unknown city")


def calculator(expression: str) -> str:
    """Calculate a math expression. Input: math expression as string."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def search_web(query: str) -> str:
    """Search the web for current information. Input: search query."""
    fake_results = {
        "tesla": "Tesla Inc., founded by Elon Musk. Latest news: 2026 launch of Robotaxi.",
        "python": "Python is a programming language created by Guido van Rossum in 1991.",
        "ai": "AI advances continue with new models like GPT-5 expected in 2026."
    }
    for key, val in fake_results.items():
        if key in query.lower():
            return val
    return f"No results for '{query}'"


TOOLS = {
    "get_weather": get_weather,
    "calculator": calculator,
    "search_web": search_web,
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Parsing ReAct Output
# ─────────────────────────────────────────────────────────────────────────────

def parse_react_output(text: str) -> dict:
    """Extract Thought, Action, Action Input or Final Answer from LLM output."""

    # Check for Final Answer
    final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
    if final_match:
        return {
            "type": "final",
            "answer": final_match.group(1).strip()
        }

    # Extract Thought
    thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", text, re.DOTALL)
    thought = thought_match.group(1).strip() if thought_match else ""

    # Extract Action
    action_match = re.search(r"Action:\s*([^\n]+)", text)
    action = action_match.group(1).strip() if action_match else ""

    # Extract Action Input
    input_match = re.search(r"Action Input:\s*(.*?)(?=Observation:|$)", text, re.DOTALL)
    action_input_str = input_match.group(1).strip() if input_match else ""

    # Parse as JSON, fall back to string
    try:
        action_input = json.loads(action_input_str)
    except (json.JSONDecodeError, ValueError):
        action_input = action_input_str

    return {
        "type": "action",
        "thought": thought,
        "action": action,
        "action_input": action_input
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Basic ReAct Agent (Simple Version)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: Basic ReAct Agent")
print("=" * 70)


class BasicReActAgent:
    def __init__(self, tools: dict[str, Callable], model: str = "gpt-4o-mini"):
        self.tools = tools
        self.model = model
        self.history = []

    def build_prompt(self, question: str) -> str:
        tool_desc = "\n".join(
            f"- {name}: {func.__doc__ or 'No description'}"
            for name, func in self.tools.items()
        )

        history_text = ""
        for step in self.history:
            history_text += f"\nThought: {step['thought']}\n"
            history_text += f"Action: {step['action']}\n"
            history_text += f"Action Input: {json.dumps(step['action_input']) if isinstance(step['action_input'], dict) else step['action_input']}\n"
            history_text += f"Observation: {step['observation']}\n"

        return f"""You are an AI agent that solves problems step-by-step using tools.

AVAILABLE TOOLS:
{tool_desc}

FORMAT (use EXACTLY this format):
Thought: think about what to do next
Action: tool_name
Action Input: {{"param": "value"}}
Observation: result will appear here

Continue Thought/Action/Observation until you can answer. Then respond with:
Thought: I now have the answer
Final Answer: your complete answer

Question: {question}
{history_text}
Thought:"""

    def run(self, question: str, max_iterations: int = 8, verbose: bool = True) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return "[NO_API_KEY]"
        from openai import OpenAI
        client = OpenAI()

        self.history = []  # Reset

        for i in range(max_iterations):
            if verbose:
                print(f"\n--- Iteration {i + 1} ---")

            prompt = self.build_prompt(question)

            # Call LLM with stop sequence
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stop=["Observation:"],
                temperature=0
            )
            llm_output = response.choices[0].message.content
            llm_output = "Thought: " + llm_output if not llm_output.startswith("Thought") else llm_output

            if verbose:
                print(llm_output)

            parsed = parse_react_output(llm_output)

            if parsed["type"] == "final":
                if verbose:
                    print(f"\n✅ Done in {i + 1} iterations.")
                return parsed["answer"]

            # Execute action
            tool_name = parsed["action"]
            tool_args = parsed["action_input"]

            if tool_name not in self.tools:
                observation = f"Error: Unknown tool '{tool_name}'. Available: {list(self.tools.keys())}"
            else:
                try:
                    if isinstance(tool_args, dict):
                        observation = self.tools[tool_name](**tool_args)
                    else:
                        observation = self.tools[tool_name](tool_args)
                except Exception as e:
                    observation = f"Error executing {tool_name}: {e}"

            if verbose:
                print(f"Observation: {observation}")

            self.history.append({
                "thought": parsed["thought"],
                "action": tool_name,
                "action_input": tool_args,
                "observation": observation
            })

        return "Max iterations reached without final answer."


# Run basic agent
agent = BasicReActAgent(TOOLS)
result = agent.run("What is the weather in Mumbai and what is 25 * 8?")
print(f"\n🎯 FINAL ANSWER:\n{result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Production-Grade ReAct with Safety
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Production-Grade ReAct")
print("=" * 70)


class ProductionReActAgent(BasicReActAgent):
    def __init__(self, tools, model="gpt-4o-mini", max_iter=8, timeout_sec=30, budget_dollars=0.10):
        super().__init__(tools, model)
        self.max_iter = max_iter
        self.timeout = timeout_sec
        self.budget = budget_dollars
        self.total_cost = 0
        self.metrics = []

    def _llm_cost(self, usage):
        """Calculate cost for gpt-4o-mini."""
        return (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1_000_000

    def _is_stuck(self) -> bool:
        """Detect if agent is repeating the same action."""
        if len(self.history) < 2:
            return False
        last_two = self.history[-2:]
        return (last_two[0]["action"] == last_two[1]["action"] and
                last_two[0]["action_input"] == last_two[1]["action_input"])

    def run_safe(self, question: str) -> dict:
        if not os.getenv("OPENAI_API_KEY"):
            return {"error": "no_api_key"}
        from openai import OpenAI
        client = OpenAI()

        self.history = []
        self.total_cost = 0
        self.metrics = []
        start = time.time()

        for i in range(self.max_iter):
            # Safety checks
            elapsed = time.time() - start
            if elapsed > self.timeout:
                return {"status": "timeout", "elapsed": elapsed, "history": self.history, "cost": self.total_cost}
            if self.total_cost > self.budget:
                return {"status": "budget_exceeded", "cost": self.total_cost, "history": self.history}
            if i > 1 and self._is_stuck():
                return {"status": "stuck", "history": self.history, "cost": self.total_cost}

            # LLM call
            prompt = self.build_prompt(question)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stop=["Observation:"],
                temperature=0
            )
            self.total_cost += self._llm_cost(response.usage)

            llm_output = response.choices[0].message.content
            if not llm_output.startswith("Thought"):
                llm_output = "Thought: " + llm_output

            parsed = parse_react_output(llm_output)

            self.metrics.append({
                "iteration": i + 1,
                "tokens_in": response.usage.prompt_tokens,
                "tokens_out": response.usage.completion_tokens,
                "elapsed_sec": time.time() - start,
                "action": parsed.get("action")
            })

            if parsed["type"] == "final":
                return {
                    "status": "success",
                    "answer": parsed["answer"],
                    "iterations": i + 1,
                    "cost": self.total_cost,
                    "elapsed_sec": time.time() - start,
                    "tools_called": [m["action"] for m in self.metrics if m["action"]]
                }

            # Execute tool
            tool_name = parsed["action"]
            tool_args = parsed["action_input"]
            if tool_name not in self.tools:
                obs = f"Error: Unknown tool '{tool_name}'"
            else:
                try:
                    if isinstance(tool_args, dict):
                        obs = self.tools[tool_name](**tool_args)
                    else:
                        obs = self.tools[tool_name](tool_args)
                except Exception as e:
                    obs = f"Error: {e}"

            self.history.append({**parsed, "observation": obs, "action": tool_name, "action_input": tool_args})

        return {"status": "max_iterations", "history": self.history, "cost": self.total_cost}


prod_agent = ProductionReActAgent(TOOLS, max_iter=6, timeout_sec=20, budget_dollars=0.05)

questions = [
    "Calculate 100 * 17 + 250",
    "What's Tesla's recent news, and the weather in Bangalore?",
    "Compute the temperature in Delhi divided by 4",
]

for q in questions:
    print(f"\n🔵 Question: {q}")
    result = prod_agent.run_safe(q)
    print(f"   Status:    {result['status']}")
    print(f"   Cost:      ${result.get('cost', 0):.6f}")
    print(f"   Iterations: {result.get('iterations', '?')}")
    if "answer" in result:
        print(f"   Answer:    {result['answer'][:200]}")
    print(f"   Tools used: {result.get('tools_called', [])}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Streaming Events (Real-time UX)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Streaming Agent Events")
print("=" * 70)


def react_with_callbacks(question: str, callbacks: dict):
    """Run ReAct, emit events for each step."""
    agent = BasicReActAgent(TOOLS)
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    client = OpenAI()

    callbacks["on_start"](question)
    for i in range(8):
        callbacks["on_iteration_start"](i + 1)

        prompt = agent.build_prompt(question)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stop=["Observation:"],
            temperature=0
        )
        llm_output = response.choices[0].message.content
        if not llm_output.startswith("Thought"):
            llm_output = "Thought: " + llm_output

        parsed = parse_react_output(llm_output)

        if parsed["type"] == "final":
            callbacks["on_final"](parsed["answer"])
            return parsed["answer"]

        callbacks["on_thought"](parsed["thought"])
        callbacks["on_action"](parsed["action"], parsed["action_input"])

        # Execute
        try:
            if isinstance(parsed["action_input"], dict):
                obs = agent.tools[parsed["action"]](**parsed["action_input"])
            else:
                obs = agent.tools[parsed["action"]](parsed["action_input"])
        except Exception as e:
            obs = f"Error: {e}"

        callbacks["on_observation"](obs)
        agent.history.append({**parsed, "observation": obs})

    return None


# Demo with callbacks (like a chat UI would consume)
callbacks = {
    "on_start": lambda q: print(f"\n💬 User: {q}"),
    "on_iteration_start": lambda n: print(f"\n[Step {n}]"),
    "on_thought": lambda t: print(f"  🤔 Thinking: {t}"),
    "on_action": lambda a, args: print(f"  🔧 Using tool: {a}({args})"),
    "on_observation": lambda o: print(f"  👁️ Got: {o}"),
    "on_final": lambda a: print(f"\n✅ Final: {a}"),
}

react_with_callbacks("What is the weather in Mumbai and what is 99 + 1?", callbacks)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a "current_time" tool. Test with: "What time is it in Tokyo?"
2. Modify the agent to log all steps to a JSON file for audit.

MEDIUM:
3. Add streaming token-by-token from LLM (not just step-by-step events).
4. Build a retry mechanism — if observation contains "Error", try a different approach.

HARD:
5. Implement self-critique: after each Final Answer, ReAct evaluates if answer is complete.
   If not, continue with more steps.
6. Add tool description-based auto-disable: tools not used in 5 iterations → hide them.

PRO:
7. Build a multi-agent ReAct system:
   - Supervisor ReAct decides which specialist agent to call
   - Specialist agents (research, code, data) are also ReAct internally
   - Implement message passing between agents
""")

if __name__ == "__main__":
    print("\n✅ ReAct from scratch — the foundation of all agents!")
