"""
Smart Multi-Provider LLM Selection (Production-Grade)
Auto-selects best available LLM with automatic fallback on failure.
"""

import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# Load environment variables FIRST
load_dotenv()


# Provider configurations (priority order)
PROVIDERS = [
    {
        "env_key": "ANTHROPIC_API_KEY",
        "name": "Anthropic Claude",
        "emoji": "[Anthropic]",
        "model": "claude-haiku-4-5",
        "provider": "anthropic",
    },
    {
        "env_key": "OPENAI_API_KEY",
        "name": "OpenAI GPT-4o-mini",
        "emoji": "[OpenAI]",
        "model": "gpt-4o-mini",
        "provider": "openai",
    },
    {
        "env_key": "GOOGLE_API_KEY",
        "name": "Google Gemini",
        "emoji": "[Gemini]",
        "model": "gemini-2.5-flash",
        "provider": "google_genai",
    },
    {
        "env_key": "GROQ_API_KEY",
        "name": "Groq Llama 3.3",
        "emoji": "[Groq]",
        "model": "llama-3.3-70b-versatile",
        "provider": "groq",
    },
]


def get_smart_model_with_fallback(test_message: str = "Hi"):
    """
    Auto-select best available LLM with automatic fallback.

    Tries each provider in priority order. If one fails
    (no credits, rate limit, invalid key, etc.), automatically
    tries the next provider in the list.
    """
    for config in PROVIDERS:
        if not os.getenv(config["env_key"]):
            continue  # Skip if API key not configured

        try:
            print(f"{config['emoji']} Trying {config['name']}...")
            model = init_chat_model(
                config["model"],
                model_provider=config["provider"],
            )

            # Test with a minimal request to verify it works
            model.invoke(test_message)

            print(f"SUCCESS: Connected to {config['name']}\n")
            return model

        except Exception as e:
            error_msg = str(e)[:120]
            print(f"FAILED: {config['name']} -> {error_msg}...")
            print("Trying next provider...\n")
            continue

    raise ValueError("No working LLM provider found!")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Smart LLM Selector with Automatic Fallback")
    print("=" * 60)
    print()

    model = get_smart_model_with_fallback()

    response = model.invoke("What is LangChain in 3 lines?")
    print("=" * 60)
    print("\nResponse:\n")
    print(response.content)
    print()


if __name__ == "__main__":
    main()
