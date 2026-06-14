"""
LangChain Introduction - Multi-Provider Testing (Production-Ready)
"""

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def test_groq() -> None:
    """Test Groq (FREE) - Llama 3.3 70B"""
    print("=" * 60)
    print("GROQ (Llama 3.3 - 70B):")
    print("=" * 60)
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
        response = llm.invoke("What is LangChain in 3 lines?")
        print(response.content)
    except Exception as e:
        print(f"Groq Error: {e}")


def test_gemini() -> None:
    """Test Google Gemini (FREE) - 2.5 Flash"""
    print("\n" + "=" * 60)
    print("GEMINI 2.5 Flash:")
    print("=" * 60)
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        response = llm.invoke("What is LangChain in 3 lines?")
        print(response.content)
    except Exception as e:
        print(f"Gemini Error: {e}")


def main() -> None:
    """Run all provider tests"""
    print("\n Testing Multiple LLM Providers...\n")
    test_groq()
    test_gemini()
    print("\n All tests complete!\n")


if __name__ == "__main__":
    main()