"""
First REAL Agent with Tools
The agent decides which tool to use based on user query.

Concepts:
- @tool decorator: Convert functions into agent-usable tools
- llm.bind_tools(): Make tools available to the LLM
- response.tool_calls: Agent's tool selection decisions
- Tool execution: Run the selected tool with arguments
"""

from datetime import datetime

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

load_dotenv()


# ===== TOOL DEFINITIONS =====

@tool
def calculator(expression: str) -> str:
    """
    Calculate a mathematical expression.

    Args:
        expression: Math expression like '2 + 2', '15 * 8', '100 / 4'

    Returns:
        The calculated result as a string.
    """
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


@tool
def greet_user(name: str, language: str = "english") -> str:
    """
    Greet a user by name in their preferred language.

    Args:
        name: The name of the person to greet
        language: Language for greeting - 'english', 'hindi', or 'spanish'

    Returns:
        A personalized greeting message.
    """
    greetings = {
        "english": f"Hello {name}! How are you today?",
        "hindi": f"Namaste {name}! Aap kaise hain?",
        "spanish": f"Hola {name}! Como estas?",
    }
    return greetings.get(language.lower(), greetings["english"])


@tool
def get_current_time() -> str:
    """
    Get the current date and time.

    Returns:
        Current date and time as a formatted string.
    """
    now = datetime.now()
    return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"


@tool
def word_counter(text: str) -> str:
    """
    Count words in a given text.

    Args:
        text: The text to count words in

    Returns:
        Number of words in the text.
    """
    words = text.split()
    return f"Word count: {len(words)}"


# ===== AGENT EXECUTION =====

def execute_agent_query(llm_with_tools, tools_map, query: str) -> None:
    """Execute a single query through the agent and display results."""
    print(f"\n{'=' * 70}")
    print(f"USER QUERY: {query}")
    print('=' * 70)

    try:
        # Agent decides which tool to use (if any)
        response = llm_with_tools.invoke([HumanMessage(content=query)])

        # Check if agent decided to use tools
        if response.tool_calls:
            print(f"\nAgent decided to use {len(response.tool_calls)} tool(s):")

            for i, tool_call in enumerate(response.tool_calls, 1):
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                print(f"\n  Tool #{i}: {tool_name}")
                print(f"  Arguments: {tool_args}")

                # Execute the chosen tool
                try:
                    tool_result = tools_map[tool_name].invoke(tool_args)
                    print(f"  Output: {tool_result}")
                except Exception as e:
                    print(f"  Tool Error: {e}")
        else:
            # Agent decided to respond directly without tools
            print(f"\nAgent responded directly:")
            print(f"  {response.content}")

    except Exception as e:
        # Handle LLM/API errors gracefully (e.g., tool_use_failed)
        error_msg = str(e)[:150]
        print(f"\nAgent Error: {error_msg}...")
        print("(Continuing with next query)")


def main():
    """Main entry point - demonstrate agent with multiple tools."""
    print("=" * 70)
    print("FIRST REAL AGENT WITH TOOLS - DEMO")
    print("=" * 70)

    # Use Gemini for better tool calling reliability
    # (Groq sometimes fails with complex expressions like parentheses)
    llm = init_chat_model(
        "gemini-2.5-flash",
        model_provider="google_genai",
    )

    # Define available tools
    tools = [calculator, greet_user, get_current_time, word_counter]

    # Bind tools to LLM (agent now knows about these tools)
    llm_with_tools = llm.bind_tools(tools)

    # Create tool lookup map for execution
    tools_map = {t.name: t for t in tools}

    # Test queries - each requires different tool
    queries = [
        "Calculate 25 * 4 + 100",
        "Greet Ashish in Hindi",
        "What time is it right now?",
        "How many words are in 'Backend developer learning Agentic AI'?",
        "Calculate (50 + 30) * 2",
        "Greet Sarah in Spanish",
    ]

    # Execute each query through the agent
    for query in queries:
        execute_agent_query(llm_with_tools, tools_map, query)

    print(f"\n{'=' * 70}")
    print("Demo complete! Agent successfully chose the right tool for each task.")
    print('=' * 70)


if __name__ == "__main__":
    main()
