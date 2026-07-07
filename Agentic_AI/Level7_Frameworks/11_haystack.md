# Haystack (deepset) — RAG & Agent Framework

## Quick Concepts
- **Haystack** = open-source Python framework by deepset, focused specifically on production RAG pipelines and agents — the "LangChain alternative" that's more opinionated toward search/retrieval use cases
- **Pipeline** = Haystack's core abstraction — a DAG of connected `Component`s (retriever, generator, ranker, etc.), similar in spirit to LangGraph's graph model but purpose-built for RAG from day one
- **Component** = a single step in a pipeline (e.g., `InMemoryEmbeddingRetriever`, `OpenAIGenerator`) — swap components without rewriting the pipeline
- **Document Store** = Haystack's abstraction over vector/keyword stores (Elasticsearch, Qdrant, Weaviate, in-memory) — same pipeline code works across backends

---

## Why It Matters

You already have deep coverage of LangChain/LangGraph, CrewAI, DSPy,
LlamaIndex, PydanticAI, and Semantic Kernel — Haystack is the remaining
notable framework in that family, positioned specifically as
**production-RAG-first** (it predates the current LLM-agent hype cycle,
originally built for classical search/QA systems, then extended to
LLM-based RAG and agents). Lower priority than LangGraph/MCP for interviews,
but worth recognizing since it does come up, especially in roles emphasizing
search/retrieval quality over general agent orchestration.

Senior interview: "LangChain vs Haystack — when would you pick Haystack?" →
Haystack's pipeline abstraction and document-store swapping are more mature
for pure RAG/search use cases; LangChain/LangGraph win for general-purpose
agent orchestration flexibility.

---

## Core Concept — Pipelines of Components

```python
# pip install haystack-ai

from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
from haystack.components.generators import OpenAIGenerator
from haystack.components.builders import PromptBuilder
from haystack.document_stores.in_memory import InMemoryDocumentStore

document_store = InMemoryDocumentStore()

prompt_template = """
Given these documents, answer the question.
Documents:
{% for doc in documents %}
    {{ doc.content }}
{% endfor %}
Question: {{question}}
Answer:
"""

rag_pipeline = Pipeline()
rag_pipeline.add_component("embedder", SentenceTransformersTextEmbedder())
rag_pipeline.add_component("retriever", InMemoryEmbeddingRetriever(document_store=document_store))
rag_pipeline.add_component("prompt_builder", PromptBuilder(template=prompt_template))
rag_pipeline.add_component("llm", OpenAIGenerator(model="gpt-4o-mini"))

# Explicitly wire components together — this is the part LangChain's LCEL
# and LangGraph's edges do implicitly/declaratively; Haystack is explicit
rag_pipeline.connect("embedder.embedding", "retriever.query_embedding")
rag_pipeline.connect("retriever.documents", "prompt_builder.documents")
rag_pipeline.connect("prompt_builder.prompt", "llm.prompt")

result = rag_pipeline.run({
    "embedder": {"text": "What is Contextual Retrieval?"},
    "prompt_builder": {"question": "What is Contextual Retrieval?"},
})
print(result["llm"]["replies"][0])
```

**The key structural difference from LangChain/LangGraph:** Haystack's
`connect()` calls make the DATA FLOW between components fully explicit and
type-checked at pipeline-build time (it validates that `embedder.embedding`'s
output type matches what `retriever.query_embedding` expects) — catching
wiring mistakes before runtime, rather than LangChain's more implicit
chaining via `|` (LCEL) or LangGraph's state-dict passing.

---

## Document Store abstraction (swap backends without rewriting pipeline logic)

```python
# Development: in-memory, no external dependency
from haystack.document_stores.in_memory import InMemoryDocumentStore
document_store = InMemoryDocumentStore()

# Production: swap to a real vector DB — SAME pipeline code above works unchanged
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
document_store = QdrantDocumentStore(url="http://localhost:6333", index="my_docs")

# Or Elasticsearch (ties into your existing Elasticsearch coverage)
from haystack_integrations.document_stores.elasticsearch import ElasticsearchDocumentStore
document_store = ElasticsearchDocumentStore(hosts="http://localhost:9200")
```

---

## Haystack Agents (newer addition, competing with LangGraph/CrewAI territory)

```python
from haystack.components.agents import Agent
from haystack.tools import Tool

def search_web(query: str) -> str:
    return f"Search results for: {query}"

search_tool = Tool(
    name="web_search",
    description="Search the web for current information",
    function=search_web,
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)

agent = Agent(
    chat_generator=OpenAIGenerator(model="gpt-4o"),
    tools=[search_tool],
)

result = agent.run(messages=[{"role": "user", "content": "What's the weather in Delhi?"}])
```

Haystack's agent support is newer/less mature than LangGraph's — it's the
RAG pipeline capability that's genuinely differentiated, not the agent
orchestration layer, which is why LangGraph remains the stronger default
choice for general multi-step agentic workflows.

---

## When to actually pick Haystack over LangChain/LangGraph

| Need | Choice |
|---|---|
| Production RAG/search system as the PRIMARY use case, less need for complex agent branching | **Haystack** — more mature document-store ecosystem, explicit type-checked pipelines |
| General-purpose agent orchestration, complex conditional branching, human-in-the-loop | **LangGraph** — richer graph/state model, larger ecosystem |
| Team already has strong Elasticsearch/classical-search background | **Haystack** — its roots in classical IR/search make the abstractions feel natural |
| Need the widest possible integration ecosystem (most tutorials, most Stack Overflow answers) | **LangChain/LangGraph** — larger community by a wide margin |

---

## Interview Q&A

**Q: What's Haystack's core abstraction, and how does it differ from LangChain's?**
A: Pipelines of explicitly-connected, type-checked Components — data flow
between components is validated when the pipeline is built, not just at
runtime. LangChain's LCEL (`|` chaining) is more implicit; LangGraph uses a
shared state dict passed between graph nodes instead of Haystack's typed
point-to-point connections.

**Q: When would Haystack be a better choice than LangChain for a RAG system?**
A: When RAG/search quality is the primary concern and you want mature,
swappable Document Store integrations (Elasticsearch, Qdrant, Weaviate) with
type-safe pipeline wiring — Haystack's roots in classical information
retrieval give it more mature abstractions specifically for this, even
though LangChain has caught up significantly on RAG support too.

**Q: Is Haystack's agent support as mature as LangGraph's?**
A: No — Haystack's Agent component is a newer addition, useful for simpler
tool-calling agents, but LangGraph's graph-based state model handles
complex branching/looping/human-in-the-loop patterns more robustly. Pick
Haystack for RAG-heavy systems, LangGraph for complex agent orchestration.

---

Related: `01_langchain_complete.md` / `02_langgraph_complete.md` (the
comparison point), `Level5_RAG_Vector_Databases/03_vector_databases.md`
(the Document Store backends this abstracts over).
