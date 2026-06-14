"""
Building Tools and Agents - Following Krish Naik LangChain Course

Concept:
    Input → LLM + Context → Output

Tools ──→ API
      ──→ Google Search
      ──→ Vector Database
      ──→ Calculator

With Prompt → AUTONOMOUS BRAIN = ReAct Agent

Core Concept: LLM Hallucination ko REDUCE Kaise Karein?
    LLM alone → Hallucinates → Wrong info

Solution:
    LLM + Tools → Get real context → Accurate output

Tools are pairings of:
    1. A schema (name, description, argument definitions in JSON)
    2. A function or coroutine to execute
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.tools import tool

# Load environment variables FIRST
load_dotenv()


# ===== TOOL DEFINITIONS =====

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city.

    Args:
        city: Name of the city

    Returns:
        Weather information as a string
    """
    # Simulated weather (in production, call real API)
    return f"Weather in {city}: 28°C, Partly Cloudy"


@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression.

    Args:
        expression: Math expression like '2 + 2' or '15 * 8'

    Returns:
        Result of the calculation
    """
    try:
        return f"Result: {eval(expression)}"
    except Exception as e:
        return f"Error: {e}"


# ===== INITIALIZE MODEL WITH TOOLS =====

model = init_chat_model("groq:llama-3.3-70b-versatile")

# Bind tools to LLM
tools = [get_weather, calculator]
model_with_tools = model.bind_tools(tools)

# Create tool lookup map
tools_map = {t.name: t for t in tools}


# ===== AGENT FUNCTION =====

def run_agent(query: str) -> None:
    """Run a query through the agent and execute tools."""
    print(f"\n{'=' * 60}")
    print(f"User: {query}")
    print('=' * 60)

    # Agent decides which tool to use
    response = model_with_tools.invoke(query)

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"Tool: {tool_name}({tool_args})")

            # Execute the tool
            result = tools_map[tool_name].invoke(tool_args)
            print(f"Result: {result}")
    else:
        print(f"Direct response: {response.content}")


# ===== MAIN =====

if __name__ == "__main__":
    # Test queries
    run_agent("What is the weather in Mumbai?")
    run_agent("Calculate 25 * 4 + 100")
    run_agent("Get weather in Delhi")
