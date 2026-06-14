"""
PRACTICE 02: Message Types
==========================

Topic: Section 6 from THEORY.md
Level: Basic → Intermediate

What you'll learn:
- SystemMessage (AI behavior)
- HumanMessage (user input)
- AIMessage (AI responses)
- Multi-turn conversations
- Conversation memory
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

load_dotenv()

# Initialize model
model = init_chat_model("groq:llama-3.3-70b-versatile")


# ===== BASIC: System Message =====

def basic_system_message():
    """Use SystemMessage to define AI behavior."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: System Message (AI Behavior)")
    print("=" * 70)

    messages = [
        SystemMessage(content="You are a Python expert. Reply in 2 lines only."),
        HumanMessage(content="What is async/await?")
    ]

    response = model.invoke(messages)
    print(f"\nUser: What is async/await?")
    print(f"AI: {response.content}")


# ===== INTERMEDIATE: Multi-turn Conversation =====

def multi_turn_conversation():
    """Multi-turn conversation with memory."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Multi-turn Conversation (with context)")
    print("=" * 70)

    # Start with system message
    conversation = [
        SystemMessage(content="You are a helpful Hindi-speaking AI tutor.")
    ]

    # Turn 1
    conversation.append(HumanMessage(content="Mera naam Ashish hai"))
    response1 = model.invoke(conversation)
    conversation.append(AIMessage(content=response1.content))
    print(f"\nUser: Mera naam Ashish hai")
    print(f"AI: {response1.content}")

    # Turn 2 (AI should remember name)
    conversation.append(HumanMessage(content="Mera naam kya hai?"))
    response2 = model.invoke(conversation)
    conversation.append(AIMessage(content=response2.content))
    print(f"\nUser: Mera naam kya hai?")
    print(f"AI: {response2.content}")

    # Turn 3
    conversation.append(HumanMessage(content="Mujhe Python sikhao"))
    response3 = model.invoke(conversation)
    print(f"\nUser: Mujhe Python sikhao")
    print(f"AI: {response3.content}")


# ===== ADVANCED: Interactive Chat =====

def interactive_chat():
    """Interactive chat with role-based behavior."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Interactive Chat (type 'quit' to exit)")
    print("=" * 70)

    # System prompt defines AI personality
    conversation = [
        SystemMessage(content="""
        You are a friendly Hindi-English speaking coding mentor.
        Help users learn Python and FastAPI.
        Be encouraging and patient.
        Use simple Hinglish.
        """)
    ]

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() in ["quit", "exit", "bye"]:
            print("AI: Goodbye! Happy coding! 🚀")
            break

        if not user_input:
            continue

        # Add user message
        conversation.append(HumanMessage(content=user_input))

        # Get AI response
        response = model.invoke(conversation)

        # Store AI response for memory
        conversation.append(AIMessage(content=response.content))

        print(f"AI: {response.content}")


def main():
    """Run all examples."""
    # Basic
    basic_system_message()

    # Intermediate
    multi_turn_conversation()

    # Advanced (interactive - uncomment to use)
    # interactive_chat()


if __name__ == "__main__":
    main()
