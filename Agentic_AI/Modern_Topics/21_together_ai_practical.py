"""
21_together_ai_practical.py
Together AI — open-weight models via an OpenAI-compatible API.

Deps (optional):
    pip install openai              # Together is OpenAI-compatible
    #   or: pip install together

Needs TOGETHER_API_KEY. Guards gracefully if missing.
"""

# ---------------------------------------------------------------------------
# 1) Via the standard OpenAI SDK (just change base_url) — recommended pattern
# ---------------------------------------------------------------------------
def demo_openai_compatible():
    import os
    try:
        from openai import OpenAI
    except ImportError:
        print("[together] pip install openai")
        return
    key = os.getenv("TOGETHER_API_KEY")
    if not key:
        print("[together] set TOGETHER_API_KEY to run")
        return

    client = OpenAI(api_key=key, base_url="https://api.together.xyz/v1")
    resp = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        messages=[{"role": "user", "content": "One line: what is Together AI?"}],
    )
    print("[together/openai-sdk]", resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# 2) Via the native together SDK (embeddings example)
# ---------------------------------------------------------------------------
def demo_together_sdk_embeddings():
    import os
    try:
        from together import Together
    except ImportError:
        print("[together] pip install together (native SDK)")
        return
    if not os.getenv("TOGETHER_API_KEY"):
        print("[together] set TOGETHER_API_KEY to run")
        return
    client = Together()
    out = client.embeddings.create(
        model="BAAI/bge-base-en-v1.5",
        input=["Together serves open-weight models"],
    )
    print("[together/embeddings] dim:", len(out.data[0].embedding))


if __name__ == "__main__":
    print("=" * 60); demo_openai_compatible()
    print("=" * 60); demo_together_sdk_embeddings()
