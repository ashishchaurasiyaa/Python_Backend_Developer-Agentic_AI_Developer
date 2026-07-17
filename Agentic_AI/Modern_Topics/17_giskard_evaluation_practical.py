"""
17_giskard_evaluation_practical.py
Giskard — scan an LLM/RAG app for vulnerabilities + build a test suite.

Deps (optional):
    pip install "giskard[llm]"

Needs an LLM key (e.g. OPENAI_API_KEY) for the scan to generate adversarial cases.
Guards gracefully if unavailable.
"""

# ---------------------------------------------------------------------------
# 1) WRAP your app as a giskard.Model and SCAN it
# ---------------------------------------------------------------------------
def demo_scan():
    import os
    try:
        import pandas as pd
        import giskard
    except ImportError:
        print("[giskard] pip install 'giskard[llm]' pandas")
        return
    if not os.getenv("OPENAI_API_KEY"):
        print("[giskard] set OPENAI_API_KEY (used to generate adversarial cases)")
        return

    # Your RAG/LLM app, as a plain function over a DataFrame column:
    def my_rag(question: str) -> str:
        # replace with your real retriever + LLM call
        return f"(stub answer for: {question})"

    def predict(df: "pd.DataFrame"):
        return [my_rag(q) for q in df["question"]]

    model = giskard.Model(
        predict,
        model_type="text_generation",
        name="Support bot",
        description="Answers product questions from the internal KB",
        feature_names=["question"],
    )

    report = giskard.scan(model)          # -> auto vulnerability report
    print("[giskard] scan done. Issues found:", len(report.issues))
    report.to_html("giskard_report.html")
    print("[giskard] wrote giskard_report.html")

    suite = report.generate_test_suite("Support bot suite")
    print("[giskard] generated reusable test suite for CI:", suite)


# ---------------------------------------------------------------------------
# 2) RAGET — auto Q&A testset from a knowledge base (concept)
# ---------------------------------------------------------------------------
def demo_raget():
    try:
        from giskard.rag import generate_testset, KnowledgeBase
        import pandas as pd
    except ImportError:
        print("[giskard-raget] pip install 'giskard[llm]' pandas")
        return
    kb_df = pd.DataFrame({"text": [
        "Cassandra is masterless and scales writes linearly.",
        "Docling preserves tables when parsing PDFs.",
    ]})
    kb = KnowledgeBase(kb_df)
    testset = generate_testset(kb, num_questions=3,
                               description="Internal AI-stack knowledge base")
    print("[giskard-raget] generated questions:")
    for s in testset.samples[:3]:
        print("  -", s.question)


if __name__ == "__main__":
    print("=" * 60); demo_scan()
    print("=" * 60); demo_raget()
