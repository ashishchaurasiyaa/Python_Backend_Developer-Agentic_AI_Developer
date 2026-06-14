"""
PRACTICE 04: Memory & Conversation
===================================

Topic: Section 8 from THEORY.md
Level: Intermediate → Advanced

What you'll learn:
- Checkpointer for memory
- Thread-based conversations
- Persistent state
- Multi-user sessions
"""

from uuid import uuid4
from dotenv import load_dotenv
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()


# ===== AGENT WITH MEMORY =====

agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[],
    system_prompt="""
    You are a helpful assistant that remembers context.
    Use information from previous messages when relevant.
    Reply in Hinglish for better understanding.
    """,
    checkpointer=InMemorySaver()  # ← Adds memory!
)


# ===== BASIC: Single Conversation with Memory =====

def basic_memory_demo():
    """Demonstrate basic memory across messages."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Memory (Single Conversation)")
    print("=" * 70)

    # Unique thread for this conversation
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"Thread ID: {thread_id[:8]}...\n")

    # Turn 1: Introduce
    print("User: Mera naam Ashish hai, mai backend developer hu")
    result = agent.invoke(
        {"messages": [("user", "Mera naam Ashish hai, mai backend developer hu")]},
        config=config
    )
    print(f"AI: {result['messages'][-1].content}\n")

    # Turn 2: Test memory
    print("User: Mera naam aur profession kya hai?")
    result = agent.invoke(
        {"messages": [("user", "Mera naam aur profession kya hai?")]},
        config=config
    )
    print(f"AI: {result['messages'][-1].content}\n")

    # Turn 3: Build on context
    print("User: Mere profession ke liye AI me kya seekhna chahiye?")
    result = agent.invoke(
        {"messages": [("user", "Mere profession ke liye AI me kya seekhna chahiye?")]},
        config=config
    )
    print(f"AI: {result['messages'][-1].content}")


# ===== INTERMEDIATE: Multiple Users =====

def multi_user_demo():
    """Different users have separate memories."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Multiple Users (Separate Memories)")
    print("=" * 70)

    # User A
    user_a_thread = "user_a_thread"
    config_a = {"configurable": {"thread_id": user_a_thread}}

    # User B
    user_b_thread = "user_b_thread"
    config_b = {"configurable": {"thread_id": user_b_thread}}

    # User A introduces themselves
    print("\n--- User A's Conversation ---")
    print("User A: Mera naam Priya hai, mai data scientist hu")
    agent.invoke(
        {"messages": [("user", "Mera naam Priya hai, mai data scientist hu")]},
        config=config_a
    )

    # User B introduces themselves
    print("\n--- User B's Conversation ---")
    print("User B: Mera naam Rahul hai, mai frontend developer hu")
    agent.invoke(
        {"messages": [("user", "Mera naam Rahul hai, mai frontend developer hu")]},
        config=config_b
    )

    # Check User A's memory
    print("\n--- Checking User A's Memory ---")
    print("User A: Mera profession kya hai?")
    result_a = agent.invoke(
        {"messages": [("user", "Mera profession kya hai?")]},
        config=config_a
    )
    print(f"AI to A: {result_a['messages'][-1].content}\n")

    # Check User B's memory
    print("--- Checking User B's Memory ---")
    print("User B: Mera profession kya hai?")
    result_b = agent.invoke(
        {"messages": [("user", "Mera profession kya hai?")]},
        config=config_b
    )
    print(f"AI to B: {result_b['messages'][-1].content}")


# ===== ADVANCED: Interactive Chat with Memory =====

def interactive_chat_with_memory():
    """Interactive chat with persistent memory."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Interactive Chat with Memory")
    print("Type 'quit' to exit, 'new' for new conversation")
    print("=" * 70)

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\nNew conversation started (Thread: {thread_id[:8]}...)\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "bye"]:
            print("AI: Goodbye! 👋")
            break

        if user_input.lower() == "new":
            thread_id = str(uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            print(f"\n🆕 New conversation (Thread: {thread_id[:8]}...)\n")
            continue

        if not user_input:
            continue

        result = agent.invoke(
            {"messages": [("user", user_input)]},
            config=config
        )

        print(f"AI: {result['messages'][-1].content}\n")


def main():
    """Run examples."""
    basic_memory_demo()
    multi_user_demo()

    # Interactive (uncomment to use)
    # interactive_chat_with_memory()


if __name__ == "__main__":
    main()
