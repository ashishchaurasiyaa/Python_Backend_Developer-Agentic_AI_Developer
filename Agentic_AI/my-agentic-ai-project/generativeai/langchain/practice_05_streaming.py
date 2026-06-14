"""
PRACTICE 05: Streaming
=======================

Topic: Section 9 from THEORY.md
Level: Intermediate

What you'll learn:
- Real-time word-by-word output (like ChatGPT)
- Model-level streaming
- Agent-level streaming
- Different stream modes
"""

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

load_dotenv()


# ===== BASIC: Model Streaming =====

def basic_model_streaming():
    """Stream response from model directly."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Model Streaming")
    print("=" * 70)

    model = init_chat_model("groq:llama-3.3-70b-versatile")

    query = "Tell me a short story about a programmer in Hindi (5 lines)"

    print(f"\nQuery: {query}")
    print("\nStreaming response:")
    print("-" * 70)

    # Stream word by word
    for chunk in model.stream(query):
        print(chunk.content, end="", flush=True)

    print("\n" + "-" * 70)


# ===== INTERMEDIATE: Agent Streaming =====

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: 28°C, Sunny"


@tool
def calculator(expression: str) -> str:
    """Calculate math expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


def agent_streaming_values():
    """Stream agent responses (values mode)."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Agent Streaming (values mode)")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[get_weather, calculator],
        system_prompt="Use tools and explain your reasoning."
    )

    query = "What's the weather in Mumbai and calculate 50 * 3?"
    print(f"\nQuery: {query}")
    print("\nStreaming (values - complete state at each step):")
    print("-" * 70)

    for chunk in agent.stream(
        {"messages": [("user", query)]},
        stream_mode="values"
    ):
        # Print latest message
        if "messages" in chunk and chunk["messages"]:
            latest = chunk["messages"][-1]
            if hasattr(latest, 'content') and latest.content:
                print(f"\n📝 {type(latest).__name__}: {latest.content[:200]}")


def agent_streaming_updates():
    """Stream agent responses (updates mode)."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Agent Streaming (updates mode)")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[get_weather],
        system_prompt="Help with weather queries."
    )

    query = "Check weather in Delhi"
    print(f"\nQuery: {query}")
    print("\nStreaming (updates - only changes):")
    print("-" * 70)

    for chunk in agent.stream(
        {"messages": [("user", query)]},
        stream_mode="updates"
    ):
        print(f"\n🔄 Update: {chunk}")


# ===== ADVANCED: Real-time Token Streaming =====

def real_time_typing_effect():
    """ChatGPT-style real-time typing effect."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Real-time Typing Effect")
    print("=" * 70)

    model = init_chat_model("groq:llama-3.3-70b-versatile")

    questions = [
        "Backend developer ko Python ke alawa kya seekhna chahiye?",
        "FastAPI vs Django mein difference batao",
        "Microservices kya hai? Explain in Hinglish",
    ]

    for question in questions:
        print(f"\n{'=' * 70}")
        print(f"❓ {question}")
        print("=" * 70)
        print("AI: ", end="", flush=True)

        # Real-time streaming
        for chunk in model.stream(question):
            print(chunk.content, end="", flush=True)

        print()  # New line


def main():
    """Run all streaming examples."""
    basic_model_streaming()
    agent_streaming_values()
    agent_streaming_updates()
    real_time_typing_effect()


if __name__ == "__main__":
    main()
