"""
Phase6_GraphRAG — Complete Practical
=======================================
Topics:
  1. GraphRAG vs standard RAG
  2. Knowledge graph construction
  3. Entity and relation extraction
  4. NetworkX for graph operations
  5. Community detection (Leiden/Louvain)
  6. Graph-based retrieval
  7. Microsoft GraphRAG pipeline

Install: pip install networkx langchain-openai
Run: python 01_graphrag_practical.py
"""

import os, json, math, random
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("GRAPHRAG CONCEPTS")
print("=" * 60)

GRAPHRAG_CONCEPTS = {
    "GraphRAG":         "RAG using knowledge graph — captures relationships between entities",
    "Standard RAG":     "Chunk → embed → retrieve similar chunks. Loses entity relationships.",
    "Knowledge Graph":  "Nodes = entities, Edges = relationships. 'Alice WORKS_AT Google'",
    "Entity extraction":"NER: find people, places, orgs, concepts in text",
    "Relation extract": "Find (entity1, relation, entity2) triples from text",
    "Community":        "Cluster of related entities in the graph (e.g., 'Python ecosystem')",
    "Global queries":   "GraphRAG excels: 'What are the main themes?' (needs full-graph view)",
    "Local queries":    "Standard RAG excels: 'What does X say about Y?' (specific retrieval)",
    "Microsoft GRAG":   "GraphRAG by Microsoft: entities → graph → communities → summaries",
}
for k, v in GRAPHRAG_CONCEPTS.items():
    print(f"  {k:<22}: {v}")

print("\n  GraphRAG vs Standard RAG:")
print("  Standard RAG: 'What is Python?' → find similar chunks → answer")
print("  GraphRAG:     'What are the key themes?' → traverse knowledge graph → answer")
print("  GraphRAG wins: global queries, multi-hop reasoning, relationship-aware answers")
print("  Standard RAG wins: specific fact lookup, speed, simplicity")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Knowledge Graph Construction
# INTERVIEW: Build from text using LLM for entity/relation extraction
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Building a Knowledge Graph")
print("=" * 60)

KG_CONSTRUCTION_CODE = '''\
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

# ── Entity and relation extraction with LLM ────────────────────
class GraphTriplet(BaseModel):
    subject:   str   # "Python"
    predicate: str   # "CREATED_BY"
    object:    str   # "Guido van Rossum"
    confidence: float = 1.0

class ExtractedGraph(BaseModel):
    entities:  list[str]
    relations: list[GraphTriplet]

llm    = ChatOpenAI(model="gpt-4o-mini", temperature=0)
parser = JsonOutputParser(pydantic_object=ExtractedGraph)

extract_prompt = ChatPromptTemplate.from_template("""
Extract entities and relationships from this text.
Return JSON with:
- entities: list of entity names
- relations: list of {{"subject": str, "predicate": str, "object": str}}

Text: {text}

Focus on: people, organizations, technologies, concepts, and their relationships.
""")

chain = extract_prompt | llm | parser

result = chain.invoke({
    "text": "Python was created by Guido van Rossum in 1991 at CWI Amsterdam. "
            "FastAPI was built by Sebastián Ramírez using Python and Starlette."
})

# result.entities = ["Python", "Guido van Rossum", "CWI", "FastAPI", "Sebastián Ramírez", "Starlette"]
# result.relations = [
#   {"subject": "Python",  "predicate": "CREATED_BY",  "object": "Guido van Rossum"},
#   {"subject": "Python",  "predicate": "CREATED_AT",  "object": "CWI Amsterdam"},
#   {"subject": "FastAPI", "predicate": "CREATED_BY",  "object": "Sebastián Ramírez"},
#   {"subject": "FastAPI", "predicate": "BUILT_WITH",  "object": "Python"},
#   {"subject": "FastAPI", "predicate": "BUILT_WITH",  "object": "Starlette"},
# ]
'''
print(KG_CONSTRUCTION_CODE[:700])


@dataclass
class Entity:
    name: str
    type: str = "unknown"
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    subject: str
    predicate: str
    object: str
    weight: float = 1.0
    source: str = ""


class KnowledgeGraph:
    """
    INTERVIEW: Knowledge graph = nodes (entities) + edges (relations).
    Multi-hop reasoning: Python → FastAPI → REST API
    """
    def __init__(self):
        self.entities: Dict[str, Entity]  = {}
        self.relations: List[Relation]    = []
        self._adj: Dict[str, List[Relation]] = defaultdict(list)

    def add_entity(self, name: str, entity_type: str = "unknown", **props):
        self.entities[name] = Entity(name=name, type=entity_type, properties=props)

    def add_relation(self, subject: str, predicate: str, obj: str, weight: float = 1.0):
        # Auto-create entities if missing
        if subject not in self.entities:
            self.add_entity(subject)
        if obj not in self.entities:
            self.add_entity(obj)
        rel = Relation(subject=subject, predicate=predicate, object=obj, weight=weight)
        self.relations.append(rel)
        self._adj[subject].append(rel)

    def get_neighbors(self, entity: str, predicate: Optional[str] = None) -> List[str]:
        rels = self._adj.get(entity, [])
        if predicate:
            rels = [r for r in rels if r.predicate == predicate]
        return [r.object for r in rels]

    def multi_hop(self, start: str, hops: int = 2) -> Set[str]:
        """BFS multi-hop traversal."""
        visited = {start}
        frontier = {start}
        for _ in range(hops):
            next_frontier = set()
            for node in frontier:
                for neighbor in self.get_neighbors(node):
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                        visited.add(neighbor)
            frontier = next_frontier
        return visited - {start}

    def stats(self) -> Dict:
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "avg_degree": len(self.relations) / max(len(self.entities), 1),
        }


# Build example knowledge graph
kg = KnowledgeGraph()

# Entities
for name, etype in [
    ("Python", "language"), ("FastAPI", "framework"), ("LangChain", "library"),
    ("Guido van Rossum", "person"), ("Sebastián Ramírez", "person"),
    ("Google", "company"), ("Starlette", "framework"), ("Pydantic", "library"),
]:
    kg.add_entity(name, etype)

# Relations
relations = [
    ("Python",    "CREATED_BY",   "Guido van Rossum"),
    ("FastAPI",   "CREATED_BY",   "Sebastián Ramírez"),
    ("FastAPI",   "BUILT_WITH",   "Python"),
    ("FastAPI",   "BUILT_WITH",   "Starlette"),
    ("FastAPI",   "USES",         "Pydantic"),
    ("LangChain", "BUILT_WITH",   "Python"),
    ("LangChain", "INTEGRATES",   "FastAPI"),
    ("Guido van Rossum", "WORKED_AT", "Google"),
]
for s, p, o in relations:
    kg.add_relation(s, p, o)

print("\n  Knowledge graph built:")
print(f"  {kg.stats()}")
print(f"\n  FastAPI neighbors: {kg.get_neighbors('FastAPI')}")
print(f"  FastAPI BUILT_WITH: {kg.get_neighbors('FastAPI', 'BUILT_WITH')}")
print(f"\n  Multi-hop from 'FastAPI' (2 hops): {kg.multi_hop('FastAPI', 2)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: NetworkX Integration
# INTERVIEW: Standard library for graph algorithms
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: NetworkX Graph Operations")
print("=" * 60)

NETWORKX_CODE = '''\
import networkx as nx

# ── Build graph from knowledge graph ──────────────────────────
G = nx.DiGraph()   # directed graph

# Add nodes with attributes
G.add_node("Python", type="language", year=1991)
G.add_node("FastAPI", type="framework")

# Add edges with attributes
G.add_edge("FastAPI", "Python",   relation="BUILT_WITH", weight=1.0)
G.add_edge("FastAPI", "Starlette", relation="BUILT_WITH", weight=0.8)

# ── Graph analytics ────────────────────────────────────────────
# PageRank: identify most important nodes
pagerank = nx.pagerank(G, weight="weight")
top_nodes = sorted(pagerank, key=pagerank.get, reverse=True)[:5]

# Degree centrality: nodes with most connections
centrality = nx.degree_centrality(G)

# Betweenness: nodes that bridge communities
between    = nx.betweenness_centrality(G)

# ── Shortest path ──────────────────────────────────────────────
path = nx.shortest_path(G, "LangChain", "Pydantic")
# → ["LangChain", "FastAPI", "Pydantic"]

# ── Community detection ────────────────────────────────────────
# Convert to undirected for community detection
G_undirected = G.to_undirected()
from networkx.algorithms.community import louvain_communities
communities = louvain_communities(G_undirected, seed=42)
# → [{Python, FastAPI, Starlette}, {LangChain, OpenAI}, ...]

# ── Subgraph extraction ────────────────────────────────────────
# Get all nodes within 2 hops of "FastAPI"
neighbors_2hop = nx.ego_graph(G, "FastAPI", radius=2)
# → subgraph with FastAPI and all connected nodes within 2 edges

# ── Serialize ─────────────────────────────────────────────────
data = nx.node_link_data(G)   # to dict (JSON serializable)
G2   = nx.node_link_graph(data)  # back from dict
nx.write_graphml(G, "graph.graphml")  # to file
'''
print(NETWORKX_CODE[:700])


try:
    import networkx as nx
    G = nx.DiGraph()
    for name, etype in kg.entities.items():
        G.add_node(name, type=etype.type)
    for rel in kg.relations:
        G.add_edge(rel.subject, rel.object, relation=rel.predicate, weight=rel.weight)

    pagerank = nx.pagerank(G)
    top      = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n  NetworkX PageRank (most important entities):")
    for node, score in top:
        print(f"    {score:.4f}  {node}")

    try:
        path = nx.shortest_path(G.to_undirected(), "LangChain", "Python")
        print(f"\n  Shortest path LangChain → Python: {' → '.join(path)}")
    except nx.NetworkXNoPath:
        print("\n  No path found between LangChain and Python")

except ImportError:
    print("\n  [networkx not installed] pip install networkx")
    print("  Key algorithms: pagerank, shortest_path, ego_graph, louvain_communities")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Graph-based Retrieval
# INTERVIEW: Retrieve context by graph traversal + community summaries
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Graph-based Retrieval")
print("=" * 60)

GRAPH_RETRIEVAL_CODE = '''\
# INTERVIEW: Two GraphRAG retrieval modes:
# 1. Local: entity-centric — find entity, traverse neighborhood, include summaries
# 2. Global: community-centric — summarize all communities, answer from summaries

class GraphRAGRetriever:
    def __init__(self, kg: KnowledgeGraph, community_summaries: dict, embedder):
        self.kg                  = kg
        self.community_summaries = community_summaries   # community_id → summary text
        self.embedder            = embedder

    # ── Local retrieval ───────────────────────────────────────
    def local_retrieve(self, query: str, k: int = 5) -> list:
        """
        Local search: find entities mentioned in query,
        expand to their neighborhoods, return relevant context.
        """
        # 1. Find entities mentioned in query
        query_entities = self._extract_query_entities(query)

        # 2. Expand to 2-hop neighborhood
        context_nodes = set()
        for entity in query_entities:
            context_nodes.update(self.kg.multi_hop(entity, hops=2))
            context_nodes.add(entity)

        # 3. Get relations within neighborhood
        context_rels = [
            r for r in self.kg.relations
            if r.subject in context_nodes and r.object in context_nodes
        ]

        # 4. Format as text context
        return self._format_graph_context(context_nodes, context_rels)

    # ── Global retrieval ──────────────────────────────────────
    def global_retrieve(self, query: str) -> list:
        """
        Global search: use community summaries.
        Best for: "What are the main themes?", "Summarize all..."
        """
        # Rank community summaries by similarity to query
        query_emb = self.embedder.embed(query)
        ranked_communities = sorted(
            self.community_summaries.items(),
            key=lambda x: cosine_sim(query_emb, embed(x[1])),
            reverse=True,
        )
        return [summary for _, summary in ranked_communities[:3]]
'''
print(GRAPH_RETRIEVAL_CODE[:700])

# Demo retrieval
def mock_local_retrieve(kg: KnowledgeGraph, query: str) -> str:
    """Simple entity-based graph retrieval."""
    # Find matching entities
    query_lower = query.lower()
    matched     = [e for e in kg.entities if e.lower() in query_lower]
    if not matched:
        matched = list(kg.entities.keys())[:3]

    # Get their neighborhood
    neighborhood = set(matched)
    for entity in matched:
        neighborhood.update(kg.get_neighbors(entity))

    # Get relevant relations
    context_rels = [
        f"{r.subject} --[{r.predicate}]--> {r.object}"
        for r in kg.relations
        if r.subject in neighborhood or r.object in neighborhood
    ][:10]

    return "\n".join(context_rels)


print("\n  Graph retrieval demo:")
queries = ["What was FastAPI built with?", "Who created Python?"]
for q in queries:
    context = mock_local_retrieve(kg, q)
    print(f"\n  Q: {q}")
    print(f"  Graph context:\n    {context.replace(chr(10), chr(10)+'    ')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Microsoft GraphRAG Pipeline
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Microsoft GraphRAG")
print("=" * 60)

MS_GRAPHRAG_CODE = '''\
# pip install graphrag

# ── Initialize project ────────────────────────────────────────
# graphrag init --root ./my-graphrag

# ── settings.yaml (configure) ─────────────────────────────────
"""
llm:
  api_key: ${GRAPHRAG_API_KEY}
  model: gpt-4o-mini

embeddings:
  api_key: ${GRAPHRAG_API_KEY}
  model: text-embedding-3-small

chunks:
  size: 1200
  overlap: 100
  group_by_columns: [id]

entity_extraction:
  prompt: "prompts/entity_extraction.txt"
  entity_types: [organization, person, technology, concept]
  max_gleanings: 1
"""

# ── Run indexing pipeline ─────────────────────────────────────
# Place documents in ./my-graphrag/input/
# graphrag index --root ./my-graphrag
# This runs:
# 1. Chunk documents
# 2. Extract entities + relations from each chunk (LLM calls)
# 3. Build knowledge graph
# 4. Detect communities (Leiden algorithm)
# 5. Generate community summaries (LLM calls)
# 6. Build embeddings for entities + chunks
# Results saved to: ./my-graphrag/output/

# ── Query ─────────────────────────────────────────────────────
# graphrag query --root ./my-graphrag --method local --query "What is FastAPI?"
# graphrag query --root ./my-graphrag --method global --query "What are the main themes?"

# ── Python API ────────────────────────────────────────────────
from graphrag.query.cli import run_local_search, run_global_search

results = run_local_search(
    root_dir = "./my-graphrag",
    query    = "What is Python used for?",
)
print(results.response)
'''
print(MS_GRAPHRAG_CODE[:700])

print("\n  GraphRAG pipeline steps:")
steps = [
    "1. Chunk documents (1200 tokens, 100 overlap)",
    "2. Extract entities + relations from each chunk (LLM)",
    "3. Merge duplicate entities across chunks",
    "4. Build knowledge graph (nodes=entities, edges=relations)",
    "5. Detect communities (Leiden algorithm)",
    "6. Generate community summaries (LLM for each community)",
    "7. Build embeddings for entities and communities",
    "8. Query: local (entity neighborhood) or global (community summaries)",
]
for step in steps:
    print(f"  {step}")


print("\n" + "=" * 60)
print("GRAPHRAG INTERVIEW SUMMARY:")
print("  GraphRAG = knowledge graph + RAG for relationship-aware retrieval")
print("  When: global queries, multi-hop reasoning, theme analysis")
print("  vs RAG: RAG wins for speed/simplicity; GraphRAG wins for reasoning")
print("  NetworkX: pagerank, shortest_path, ego_graph, community detection")
print("  Construction: LLM extracts (subject, predicate, object) triples from text")
print("  Retrieval: local (entity neighborhood) or global (community summaries)")
print("  Microsoft GraphRAG: graphrag index + graphrag query CLI")
print("=" * 60)
