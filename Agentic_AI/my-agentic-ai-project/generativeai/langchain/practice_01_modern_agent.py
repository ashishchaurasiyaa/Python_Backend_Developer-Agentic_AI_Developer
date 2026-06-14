"""
PRACTICE 01: Modern Agent (V1 API)
==================================

Topic: Section 5 from THEORY.md
Level: Basic → Intermediate

What you'll learn:
- create_agent() modern V1 pattern
- How it differs from bind_tools (old API)
- Auto tool execution
- ReAct pattern built-in

Compare with first_agent.py to see the difference!
"""

from datetime import datetime
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

load_dotenv()


# ===== TOOL DEFINITIONS =====

@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression.

    Args:
        expression: Math like '2+2' or '15 * 8'

    Returns:
        Calculation result
    """
    try:
        return f"Result: {eval(expression)}"
    except Exception as e:
        return f"Error: {e}"


@tool
def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def greet_user(name: str, language: str = "english") -> str:
    """Greet user in specified language.

    Args:
        name: User's name
        language: english, hindi, or spanish

    Returns:
        Greeting message
    """
    greetings = {
        "english": f"Hello {name}! How can I help you today?",
        "hindi": f"Namaste {name}! Aaj mai aapki kaise madad kar sakta hu?",
        "spanish": f"Hola {name}! ¿Cómo puedo ayudarte hoy?",
    }
    return greetings.get(language.lower(), greetings["english"])


# ===== MODERN AGENT (V1 API) =====

# Modern way: Just 5 lines!
agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[calculator, get_current_time, greet_user],
    system_prompt="""
    You are a helpful AI assistant with 3 tools:
    - calculator: For math operations
    - get_current_time: For current date/time
    - greet_user: For greetings

    Use them when appropriate. Be concise and friendly.
    """,
)


# ===== USAGE =====

def run_query(query: str) -> None:
    """Run a query through the modern agent."""
    print(f"\n{'=' * 70}")
    print(f"User: {query}")
    print('=' * 70)

    # Modern API: Auto tool execution!
    result = agent.invoke({
        "messages": [("user", query)]
    })

    # Get final answer directly
    final_message = result["messages"][-1]
    print(f"Agent: {final_message.content}")


def main():
    """Test modern agent with various queries."""
    print("=" * 70)
    print("MODERN AGENT DEMO (V1 API)")
    print("=" * 70)

    # Test queries (basic to complex)
    queries = [
        # Basic: Single tool
        "What is 25 * 4?",

        # Basic: Different tool
        "What time is it?",

        # Basic: Greeting
        "Greet Ashish in Hindi",

        # Intermediate: Multiple tools
        "Calculate 100 + 200, then greet Priya in Spanish",

        # Advanced: Complex reasoning
        "What time is it? Then greet me (Ashish) in Hindi and calculate 50 * 6 for me",
    ]

    for query in queries:
        run_query(query)


if __name__ == "__main__":
    main()
