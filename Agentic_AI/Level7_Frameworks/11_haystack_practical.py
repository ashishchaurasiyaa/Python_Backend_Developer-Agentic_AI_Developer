"""
Level 7 — Doc 11: Haystack (PRACTICAL)
=========================================
Tries the real `haystack-ai` package first; falls back to a minimal manual
pipeline engine that enforces the SAME core idea (explicit, type-checked
component wiring) if it's not installed.

Topics covered:
  1. Explicit pipeline wiring — connect() validates types at BUILD time,
     not runtime (the doc's key differentiator vs LangChain/LangGraph)
  2. Document store abstraction — swap backends, same pipeline code
  3. A minimal RAG pipeline actually running end to end
  4. Haystack Agent — tool-calling, shown as the newer/less mature layer

Install (optional, real SDK): pip install haystack-ai
Falls back to: pip install openai python-dotenv

Run: python 11_haystack_practical.py
"""

import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))

try:
    import haystack  # noqa: F401
    HAS_HAYSTACK = True
except ImportError:
    HAS_HAYSTACK = False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Explicit, Type-Checked Pipeline Wiring
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Explicit Pipeline Wiring — Validated at Build Time")
print("=" * 70)

if not HAS_HAYSTACK:
    print("\n  [haystack-ai not installed — demonstrating the CONCEPT with a minimal")
    print("   manual pipeline engine. `pip install haystack-ai` for the real SDK.]")


class Component:
    """Every Haystack component declares typed inputs/outputs. Ours does too —
    that's the whole point being demonstrated here."""
    def __init__(self, name: str, input_type: type, output_type: type, fn):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.fn = fn

    def run(self, x):
        return self.fn(x)


class MiniPipeline:
    """Mirrors Haystack's connect()-then-run() shape: wiring is declared
    explicitly and validated BEFORE the pipeline ever runs, unlike an
    implicit chain (LangChain's `|`) where a type mismatch only surfaces
    when you actually execute it."""

    def __init__(self):
        self.components: dict[str, Component] = {}
        self.edges: list[tuple[str, str]] = []

    def add_component(self, comp: Component):
        self.components[comp.name] = comp

    def connect(self, from_name: str, to_name: str):
        from_comp, to_comp = self.components[from_name], self.components[to_name]
        if from_comp.output_type != to_comp.input_type:
            raise TypeError(
                f"Cannot connect {from_name} (outputs {from_comp.output_type.__name__}) "
                f"to {to_name} (expects {to_comp.input_type.__name__}) — caught at BUILD time, not runtime"
            )
        self.edges.append((from_name, to_name))

    def run(self, entry_input):
        order = [self.components[name] for name in self._topological_order()]
        value = entry_input
        for comp in order:
            value = comp.run(value)
        return value

    def _topological_order(self) -> list[str]:
        # Our demo pipelines are linear chains, so insertion order IS the run order.
        return list(self.components.keys())


# A 3-stage pipeline: retrieve -> build prompt -> generate
def retrieve(query: str) -> list:
    fake_docs = ["Contextual Retrieval prepends chunk-specific context before embedding.",
                 "It reduces retrieval failure rate by pairing chunks with a short LLM-written summary."]
    return fake_docs


def build_prompt(docs: list) -> str:
    joined = "\n".join(docs)
    return f"Given these documents:\n{joined}\nAnswer: What is Contextual Retrieval?"


def generate(prompt: str) -> str:
    if not HAS_KEY:
        return "[NO_API_KEY — would send this prompt to the LLM]"
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=100)
    return resp.choices[0].message.content


pipeline = MiniPipeline()
pipeline.add_component(Component("retriever", str, list, retrieve))
pipeline.add_component(Component("prompt_builder", list, str, build_prompt))
pipeline.add_component(Component("llm", str, str, generate))

pipeline.connect("retriever", "prompt_builder")
pipeline.connect("prompt_builder", "llm")
print(f"\n  Pipeline wired: {' -> '.join(name for name, _ in pipeline.edges)} -> llm")

result = pipeline.run("What is Contextual Retrieval?")
print(f"\n  Result: {result}")

print("\n  Now try wiring a TYPE MISMATCH on purpose:")
bad_pipeline = MiniPipeline()
bad_pipeline.add_component(Component("retriever", str, list, retrieve))
bad_pipeline.add_component(Component("llm", str, str, generate))  # llm expects str, retriever outputs list
try:
    bad_pipeline.connect("retriever", "llm")
except TypeError as e:
    print(f"    Caught at BUILD time (never even ran): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Document Store Abstraction — Swap Backends, Same Pipeline
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Document Store Abstraction")
print("=" * 70)


class DocumentStore:
    """The interface every backend implements — pipeline code only ever
    talks to THIS shape, never to Qdrant/Elasticsearch specifics directly."""
    def write_documents(self, docs: list): raise NotImplementedError
    def search(self, query: str, top_k: int = 3) -> list: raise NotImplementedError


class InMemoryDocumentStore(DocumentStore):
    """Development backend — zero external dependencies."""
    def __init__(self):
        self.docs = []

    def write_documents(self, docs: list):
        self.docs.extend(docs)

    def search(self, query: str, top_k: int = 3) -> list:
        # naive substring match stands in for real embedding similarity search
        return [d for d in self.docs if any(w.lower() in d.lower() for w in query.split())][:top_k]


class FakeProductionDocumentStore(DocumentStore):
    """Stands in for QdrantDocumentStore/ElasticsearchDocumentStore — same
    interface, different backend. Real code just imports a different class;
    nothing else changes."""
    def __init__(self, url: str):
        self.url = url
        self.docs = []

    def write_documents(self, docs: list):
        print(f"    [would POST {len(docs)} docs to {self.url}]")
        self.docs.extend(docs)

    def search(self, query: str, top_k: int = 3) -> list:
        print(f"    [would query {self.url} for '{query}']")
        return [d for d in self.docs if any(w.lower() in d.lower() for w in query.split())][:top_k]


def run_search_pipeline(store: DocumentStore, docs: list, query: str) -> list:
    """SAME function, works unchanged with EITHER backend below — this is the
    whole point of the abstraction."""
    store.write_documents(docs)
    return store.search(query)


sample_docs = ["Contextual Retrieval improves RAG accuracy.", "Elasticsearch supports hybrid BM25+vector search."]

print("\n  Dev backend (InMemoryDocumentStore):")
dev_results = run_search_pipeline(InMemoryDocumentStore(), sample_docs, "retrieval accuracy")
print(f"    {dev_results}")

print("\n  'Production' backend (same pipeline function, different store):")
prod_results = run_search_pipeline(FakeProductionDocumentStore(url="http://localhost:6333"), sample_docs, "retrieval accuracy")
print(f"    {prod_results}")

print("\n  run_search_pipeline() never changed — only the DocumentStore instance")
print("  passed into it did. That's the abstraction paying for itself.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Haystack Agent — Tool-Calling (the Newer, Less Mature Layer)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Haystack Agent (tool-calling)")
print("=" * 70)


def search_web(query: str) -> str:
    return f"[mock search result for: {query}]"


def run_agent(user_message: str) -> str:
    if not HAS_KEY:
        return "[NO_API_KEY — agent needs a live model to decide whether to call search_web]"
    from openai import OpenAI
    client = OpenAI()
    tools = [{"type": "function", "function": {
        "name": "search_web", "description": "Search the web for current information",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }}]
    messages = [{"role": "user", "content": user_message}]
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools, max_tokens=100)
    msg = resp.choices[0].message
    if msg.tool_calls:
        import json
        args = json.loads(msg.tool_calls[0].function.arguments)
        result = search_web(**args)
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})
        messages.append({"role": "tool", "tool_call_id": msg.tool_calls[0].id, "content": result})
        final = client.chat.completions.create(model="gpt-4o-mini", messages=messages, max_tokens=100)
        return final.choices[0].message.content
    return msg.content


agent_answer = run_agent("What's today's top tech news?")
print(f"\n  {agent_answer}")
print("\n  This is genuinely the weaker part of Haystack per the doc — LangGraph's")
print("  graph/state model handles branching, retries, and human-in-the-loop more")
print("  richly. Haystack's differentiation is the RAG pipeline (Sections 1-2 above),")
print("  not this agent layer.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 4th component to the pipeline in Section 1 that reformats the
   final answer (e.g., adds a citation footer). Wire it in and re-run.

MEDIUM:
2. If you have `haystack-ai` installed: rewrite Section 1's pipeline using
   the REAL Pipeline, InMemoryDocumentStore, and OpenAIGenerator classes —
   compare the real connect() error message against MiniPipeline's.

HARD:
3. Extend DocumentStore's search() to do REAL embedding similarity instead
   of substring matching — reuse the embedding code from Level1 Doc 2's
   practical (cosine_similarity + get_embedding).

PRO:
4. Build a real decision function `pick_framework(use_case: str) -> str`
   that encodes the doc's "When to actually pick Haystack" table as logic,
   not just a lookup table — and justify each branch the way an interviewer
   would push you to.
""")

if __name__ == "__main__":
    print("\nDone. Level 7 complete — every doc now has hands-on code.")
    print("Next: Level 8 (Production LLMOps)")
