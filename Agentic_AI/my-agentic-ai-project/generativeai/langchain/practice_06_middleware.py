"""
PRACTICE 06: Middleware (Production Patterns)
==============================================

Topic: Section 10 from THEORY.md
Level: Advanced

What you'll learn:
- 6 categories of middleware
- Error handling middleware
- Custom middleware
- Production patterns

Note: Some advanced middleware may need additional packages.
This file demonstrates the patterns conceptually.
"""

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import ToolMessage

load_dotenv()


# ===== TOOLS WITH POTENTIAL ERRORS =====

@tool
def divide(a: float, b: float) -> str:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero!")
    return f"Result: {a / b}"


@tool
def get_user_email(user_id: int) -> str:
    """Get user email (might fail)."""
    if user_id < 0:
        raise ValueError("Invalid user ID")
    # Simulated email
    return f"user{user_id}@example.com"


@tool
def calculate(expression: str) -> str:
    """Calculate math safely."""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error in calculation: {e}"


# ===== CUSTOM ERROR HANDLING MIDDLEWARE =====

def basic_error_handling_demo():
    """Demonstrate error handling without middleware."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Without Error Handling (will crash)")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[divide, calculate],
        system_prompt="Help with math. Use tools carefully."
    )

    try:
        result = agent.invoke({
            "messages": [("user", "Divide 100 by 0")]
        })
        print(f"Result: {result['messages'][-1].content}")
    except Exception as e:
        print(f"❌ Crashed: {e}")


# ===== TRY/EXCEPT PATTERN IN TOOLS =====

@tool
def safe_divide(a: float, b: float) -> str:
    """Safely divide with error handling."""
    try:
        if b == 0:
            return "Error: Cannot divide by zero"
        return f"Result: {a / b}"
    except Exception as e:
        return f"Error: {e}"


def safe_tools_demo():
    """Tools with built-in error handling."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Safe Tools (Error Handling Inside)")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[safe_divide],
        system_prompt="Help with math. Handle errors gracefully."
    )

    # Test cases
    queries = [
        "Divide 100 by 5",
        "Divide 50 by 0",  # Edge case
        "Divide 1000 by 7",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        result = agent.invoke({
            "messages": [("user", query)]
        })
        print(f"AI: {result['messages'][-1].content}")


# ===== RETRY PATTERN =====

import time
from functools import wraps


def retry_tool(max_retries: int = 3, delay: float = 1.0):
    """Decorator to add retry logic to tools."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        return f"Failed after {max_retries} attempts: {e}"
                    print(f"Retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
            return "Max retries exceeded"
        return wrapper
    return decorator


@tool
@retry_tool(max_retries=3)
def unstable_api_call(query: str) -> str:
    """Simulate unstable API call."""
    # Simulated random failure
    import random
    if random.random() < 0.5:
        raise ConnectionError("API timeout")
    return f"API success: {query}"


def retry_pattern_demo():
    """Demonstrate retry pattern."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Retry Pattern (Production Reliability)")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[unstable_api_call],
        system_prompt="Use the API tool to handle requests."
    )

    print("\nUser: Call API for 'weather data'")
    result = agent.invoke({
        "messages": [("user", "Call API for 'weather data'")]
    })
    print(f"AI: {result['messages'][-1].content}")


# ===== LOGGING PATTERN =====

def logging_middleware_demo():
    """Demonstrate logging pattern."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Logging Pattern (Track Everything)")
    print("=" * 70)

    @tool
    def logged_search(query: str) -> str:
        """Search with logging."""
        # Log before
        print(f"  📋 [LOG] Tool called: logged_search")
        print(f"  📋 [LOG] Args: {query}")

        # Do work
        result = f"Found 3 results for '{query}'"

        # Log after
        print(f"  📋 [LOG] Result: {result}")

        return result

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[logged_search],
        system_prompt="Use search tool to find information."
    )

    print("\nUser: Search for Python tutorials")
    result = agent.invoke({
        "messages": [("user", "Search for Python tutorials")]
    })
    print(f"\nAI Final Answer: {result['messages'][-1].content}")


# ===== INPUT VALIDATION PATTERN =====

@tool
def transfer_money(from_account: str, to_account: str, amount: float) -> str:
    """Transfer money between accounts (with validation)."""
    # Input validation
    if amount <= 0:
        return "Error: Amount must be positive"

    if amount > 100000:
        return "Error: Amount exceeds limit (max ₹1,00,000)"

    if from_account == to_account:
        return "Error: Cannot transfer to same account"

    # Simulate transfer
    return f"✅ Transferred ₹{amount} from {from_account} to {to_account}"


def validation_pattern_demo():
    """Demonstrate input validation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Input Validation Pattern")
    print("=" * 70)

    agent = create_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[transfer_money],
        system_prompt="Help with money transfers. Validate inputs."
    )

    queries = [
        "Transfer ₹5000 from ACC123 to ACC456",
        "Transfer -100 from ACC123 to ACC456",  # Invalid
        "Transfer ₹500000 from ACC123 to ACC456",  # Exceeds limit
    ]

    for query in queries:
        print(f"\nUser: {query}")
        result = agent.invoke({
            "messages": [("user", query)]
        })
        print(f"AI: {result['messages'][-1].content}")


def main():
    """Run all middleware patterns."""
    # basic_error_handling_demo()  # Skip - might crash
    safe_tools_demo()
    retry_pattern_demo()
    logging_middleware_demo()
    validation_pattern_demo()


if __name__ == "__main__":
    main()
