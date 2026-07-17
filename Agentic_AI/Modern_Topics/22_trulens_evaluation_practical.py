"""
22_trulens_evaluation_practical.py
TruLens — instrument an app + score it with feedback functions (RAG Triad).

Deps (optional):
    pip install trulens-core trulens-providers-openai

Needs OPENAI_API_KEY for the LLM-as-judge feedback functions. Guards gracefully.
"""

# ---------------------------------------------------------------------------
# 1) Instrument a tiny app and record a feedback score
# ---------------------------------------------------------------------------
def demo_feedback():
    import os
    try:
        from trulens.core import TruSession, Feedback
        from trulens.apps.app import TruApp, instrument
        from trulens.providers.openai import OpenAI as fOpenAI
    except ImportError:
        print("[trulens] pip install trulens-core trulens-providers-openai")
        return
    if not os.getenv("OPENAI_API_KEY"):
        print("[trulens] set OPENAI_API_KEY (used by feedback functions)")
        return

    session = TruSession()
    session.reset_database()

    # A trivial 'RAG' app; instrument the method we want traced:
    class RAG:
        @instrument
        def retrieve(self, query: str) -> str:
            return "Cassandra is masterless and scales writes linearly."

        @instrument
        def generate(self, query: str, context: str) -> str:
            return f"Based on context: {context}"

        @instrument
        def query(self, q: str) -> str:
            return self.generate(q, self.retrieve(q))

    rag = RAG()

    # Feedback function: answer relevance (LLM-as-judge)
    provider = fOpenAI(model_engine="gpt-4o-mini")
    f_relevance = Feedback(provider.relevance, name="Answer Relevance").on_input_output()

    tru_rag = TruApp(rag, app_name="demo_rag", app_version="v1",
                     feedbacks=[f_relevance])

    with tru_rag as recording:
        print("[trulens] answer:", rag.query("How does Cassandra scale?"))

    print("[trulens] leaderboard:")
    print(session.get_leaderboard())
    print("[trulens] run `TruSession().run_dashboard()` to open the UI")


if __name__ == "__main__":
    print("=" * 60); demo_feedback()
