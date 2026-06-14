"""
Multi-Provider Response Comparison
"""

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def get_response(provider: str, question: str) -> str:
    """Get response from specified provider."""
    if provider == "groq":
        llm = ChatGroq(model="llama-3.3-70b-versatile")
    elif provider == "gemini":
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    else:
        return "Unknown provider"

    try:
        return llm.invoke(question).content
    except Exception as e:
        return f"Error: {e}"


def compare_providers(question: str) -> None:
    """Compare responses from all providers."""
    print(f"\n{'=' * 70}")
    print(f"❓ Question: {question}")
    print(f"{'=' * 70}\n")

    providers = ["groq", "gemini"]

    for provider in providers:
        print(f"--- {provider.upper()} ---")
        response = get_response(provider, question)
        print(response)
        print()


def main() -> None:
    questions = [
        "What is LangChain in 2 lines?",
        "What is the future of AI?",
        "Backend developer ko Agentic AI kyun seekhna chahiye?",
    ]

    for question in questions:
        compare_providers(question)


if __name__ == "__main__":
    main()