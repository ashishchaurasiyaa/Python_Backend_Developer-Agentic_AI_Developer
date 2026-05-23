# GraphRAG — Microsoft GraphRAG, Neo4j, Knowledge Graphs

## Quick Concepts
- **GraphRAG** = RAG + Knowledge Graph — entities aur relationships extract karo, graph traversal se answer karo
- **Knowledge Graph** = entities (nodes) + relationships (edges) — structured world model
- **Neo4j** = most popular graph database — Cypher query language
- **Community detection** = related entities cluster karo — global reasoning improve
- **Local vs Global search** = local: specific entities; global: community-level summaries

---

## Interview Questions & Answers

### Q1: GraphRAG kya hai aur regular RAG se kaise different hai?
**Answer:**
```
REGULAR RAG:
  Documents → Chunks → Embeddings → Vector DB
  Query → Retrieve similar chunks → Answer

  Problem: "What are all the connections between Company A and Person B?"
  - Can miss relationships spread across documents
  - No structured entity tracking

GRAPHRAG (Microsoft):
  Documents → Extract entities + relationships → Knowledge Graph + Vector DB
  Query → Find relevant entities → Traverse graph → Community summaries → Answer

  Benefits:
  - Understands complex relationships
  - Multi-hop reasoning (A connected to B connected to C)
  - Global questions: "What are the main themes?" (community summaries)
  - Local questions: specific entity details

PIPELINE:
  1. Entity extraction: "Ashish works at YAM" → (Ashish) -[WORKS_AT]-> (YAM)
  2. Relationship extraction: (YAM) -[LOCATED_IN]-> (Mumbai)
  3. Community detection: group related entities
  4. Summary generation: summarize each community
  5. Query: local search (entity lookup) OR global search (community search)

USE CASES:
  - Legal: find all connections between parties in documents
  - Medical: drug-disease-symptom relationships
  - Financial: company-person-transaction networks
  - Research: paper-author-citation networks
```

---

### Q2: Neo4j — graph database basic usage?
**Answer:**
```python
# pip install neo4j

from neo4j import GraphDatabase, AsyncGraphDatabase
import os

# ===== CONNECTION =====
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password")

# Docker: docker run -p 7474:7474 -p 7687:7687 neo4j:latest

driver = GraphDatabase.driver(URI, auth=AUTH)

# ===== CYPHER BASICS =====
# Cypher = SQL for graphs
# Node: (n:Label {property: value})
# Relationship: (a)-[:RELATION_TYPE]->(b)

# ===== CREATE NODES AND RELATIONSHIPS =====
def create_knowledge_graph(tx):
    # Create person
    tx.run("""
        MERGE (p:Person {name: $name, role: $role})
        RETURN p
    """, name="Ashish Kumar", role="Python Developer")
    
    # Create company
    tx.run("""
        MERGE (c:Company {name: $name, industry: $industry})
        RETURN c
    """, name="YAM Industries", industry="Technology")
    
    # Create relationship
    tx.run("""
        MATCH (p:Person {name: $person})
        MATCH (c:Company {name: $company})
        MERGE (p)-[:WORKS_AT {since: $since, role: $role}]->(c)
    """, person="Ashish Kumar", company="YAM Industries", since="2021", role="Backend Developer")
    
    # Create skill nodes
    for skill in ["Python", "FastAPI", "PostgreSQL", "Redis"]:
        tx.run("""
            MERGE (s:Skill {name: $name})
            WITH s
            MATCH (p:Person {name: $person})
            MERGE (p)-[:HAS_SKILL]->(s)
        """, name=skill, person="Ashish Kumar")

with driver.session() as session:
    session.execute_write(create_knowledge_graph)

# ===== QUERY GRAPH =====
def query_person_connections(tx, person_name: str) -> list[dict]:
    result = tx.run("""
        MATCH (p:Person {name: $name})
        OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:KNOWS]->(colleague:Person)
        RETURN p.name AS person,
               collect(DISTINCT c.name) AS companies,
               collect(DISTINCT s.name) AS skills,
               collect(DISTINCT colleague.name) AS colleagues
    """, name=person_name)
    
    return [dict(record) for record in result]

# Multi-hop: Who do Ashish's colleagues work for?
def multi_hop_query(tx, person_name: str) -> list[dict]:
    result = tx.run("""
        MATCH (p:Person {name: $name})-[:WORKS_AT]->(c:Company)
              <-[:WORKS_AT]-(colleague:Person)
              -[:WORKS_AT]->(other_company:Company)
        WHERE other_company <> c
        RETURN colleague.name AS colleague,
               other_company.name AS also_works_at
        LIMIT 10
    """, name=person_name)
    return [dict(r) for r in result]

# Shortest path
def find_path(tx, from_person: str, to_company: str) -> list:
    result = tx.run("""
        MATCH path = shortestPath(
            (p:Person {name: $from_person})-[*..6]-(c:Company {name: $to_company})
        )
        RETURN [n IN nodes(path) | coalesce(n.name, n.title)] AS path_nodes
    """, from_person=from_person, to_company=to_company)
    return [dict(r) for r in result]

# ===== ASYNC NEO4J =====
async def async_neo4j_query():
    async_driver = AsyncGraphDatabase.driver(URI, auth=AUTH)
    
    async with async_driver.session() as session:
        result = await session.run("""
            MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)
            WHERE s.name = 'Python'
            RETURN p.name, collect(s.name)
            LIMIT 10
        """)
        return [dict(r) async for r in result]
    
    await async_driver.close()
```

---

### Q3: Entity extraction — documents se knowledge graph kaise banate hain?
**Answer:**
```python
import instructor
import anthropic
from pydantic import BaseModel, Field
from typing import Optional
from neo4j import GraphDatabase

# ===== ENTITY EXTRACTION WITH INSTRUCTOR =====
class Entity(BaseModel):
    name: str
    type: str = Field(description="PERSON, ORGANIZATION, LOCATION, PRODUCT, CONCEPT, EVENT")
    description: Optional[str] = None

class Relationship(BaseModel):
    source: str = Field(description="Source entity name")
    target: str = Field(description="Target entity name")
    relation: str = Field(description="Relationship type: WORKS_AT, LOCATED_IN, FOUNDED_BY, USES, etc.")
    properties: dict = Field(default={}, description="Additional properties like date, amount")

class KnowledgeGraphData(BaseModel):
    entities: list[Entity]
    relationships: list[Relationship]

# Extract from text
client = instructor.from_anthropic(anthropic.Anthropic())

def extract_graph_data(text: str) -> KnowledgeGraphData:
    return client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        response_model=KnowledgeGraphData,
        messages=[{
            "role": "user",
            "content": f"""Extract all entities and relationships from this text as a knowledge graph.

Text:
{text}

Extract:
- All people, organizations, locations, products, concepts
- All relationships between entities
- Be specific about relationship types"""
        }]
    )

# Store in Neo4j
def store_graph_data(driver: GraphDatabase.driver, data: KnowledgeGraphData):
    with driver.session() as session:
        # Create entities
        for entity in data.entities:
            session.run("""
                MERGE (n {name: $name})
                SET n:$label, n.description = $description
            """, name=entity.name, label=entity.type, description=entity.description)
        
        # Create relationships
        for rel in data.relationships:
            session.run(f"""
                MERGE (a {{name: $source}})
                MERGE (b {{name: $target}})
                MERGE (a)-[r:{rel.relation}]->(b)
                SET r += $properties
            """, source=rel.source, target=rel.target, properties=rel.properties)

# ===== PROCESS DOCUMENTS =====
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_knowledge_graph_from_documents(docs_path: str, neo4j_driver):
    loader = PyPDFLoader(docs_path)
    pages = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    chunks = splitter.split_documents(pages)
    
    all_entities = {}
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        
        try:
            graph_data = extract_graph_data(chunk.page_content)
            store_graph_data(neo4j_driver, graph_data)
            
            print(f"  Extracted: {len(graph_data.entities)} entities, {len(graph_data.relationships)} relationships")
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    print("Knowledge graph built!")
```

---

### Q4: GraphRAG querying — graph + LLM combine karna?
**Answer:**
```python
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate

# ===== LANGCHAIN GRAPHCYPHER QA CHAIN =====
graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password="password",
)

# Auto-generate Cypher from natural language
model = ChatAnthropic(model="claude-sonnet-4-6")

cypher_chain = GraphCypherQAChain.from_llm(
    llm=model,
    graph=graph,
    verbose=True,
    return_intermediate_steps=True,
    allow_dangerous_requests=True,
)

# Ask natural language questions
result = cypher_chain.invoke("Who are Ashish's colleagues at YAM?")
print(result["result"])
print(f"Cypher used: {result['intermediate_steps']}")

# ===== HYBRID: VECTOR + GRAPH SEARCH =====
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector

# Store document chunks with embeddings IN Neo4j
vector_store = Neo4jVector.from_documents(
    documents=chunks,
    embedding=OpenAIEmbeddings(),
    url="bolt://localhost:7687",
    username="neo4j",
    password="password",
    index_name="document_embeddings",
    node_label="Document",
    text_node_property="content",
    embedding_node_property="embedding",
)

# Hybrid search: vector + graph traversal
retriever = vector_store.as_retriever(
    search_type="hybrid",     # Uses both vector similarity AND graph connections
    search_kwargs={"k": 5}
)

# ===== CUSTOM GRAPH RAG =====
def graph_rag_query(question: str, neo4j_driver, vector_store) -> str:
    """Combine vector search with graph traversal"""
    
    # 1. Vector search for relevant document chunks
    docs = vector_store.similarity_search(question, k=3)
    
    # 2. Extract entities from question
    from anthropic import Anthropic
    ant_client = Anthropic()
    
    entities_response = ant_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"Extract entity names from: '{question}'\nReturn comma-separated names only."
        }]
    )
    entity_names = [e.strip() for e in entities_response.content[0].text.split(",")]
    
    # 3. Graph traversal for entity context
    graph_context = []
    with neo4j_driver.session() as session:
        for entity in entity_names:
            result = session.run("""
                MATCH (n {name: $name})
                OPTIONAL MATCH (n)-[r]->(related)
                RETURN n.name AS entity,
                       type(r) AS relationship,
                       related.name AS related_entity
                LIMIT 10
            """, name=entity)
            
            for record in result:
                if record["relationship"]:
                    graph_context.append(
                        f"{record['entity']} {record['relationship']} {record['related_entity']}"
                    )
    
    # 4. Generate answer with combined context
    doc_context = "\n".join([d.page_content for d in docs])
    graph_ctx = "\n".join(graph_context)
    
    final_response = ant_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""Answer using document context and knowledge graph relationships:

Document Context:
{doc_context}

Knowledge Graph Relationships:
{graph_ctx}

Question: {question}"""
        }]
    )
    
    return final_response.content[0].text

# Usage
answer = graph_rag_query(
    "What is the relationship between YAM Industries and FastAPI?",
    neo4j_driver,
    vector_store,
)
```

---

### Q5: GraphRAG vs RAG — kab graph use karo?
**Answer:**
```
REGULAR RAG ENOUGH KAB HAI:
  - Simple Q&A from documents
  - "What does section 3.2 say?"
  - Single document analysis
  - No complex entity relationships

GRAPHRAG ZAROOR KAB HAI:
  - Multi-hop reasoning: "Who funded the company that acquired X?"
  - Global summaries: "What are the main themes across all docs?"
  - Relationship queries: "Who knows whom in this organization?"
  - Temporal queries: "How did relationships change over time?"
  - Cross-document connections: same entity mentioned in 100 docs

MICROSOFT GRAPHRAG LIBRARY:
  pip install graphrag
  
  graphrag init --root ./my-project
  # Edit settings.yml (add LLM config)
  
  graphrag index --root ./my-project
  # Runs: entity extraction → graph building → community detection
  
  graphrag query --root ./my-project --method local "What is FastAPI?"
  graphrag query --root ./my-project --method global "What are the main AI trends?"
  
  LOCAL SEARCH: specific entities, facts, detailed info
  GLOBAL SEARCH: themes, patterns, community-level insights
  
  Cost: ~$10-50 for medium document set (entity extraction uses LLM per chunk)

INTERVIEW TIP:
  "GraphRAG is powerful but expensive to build. I'd use it when:
   1. Questions require connecting information across many documents
   2. Relationship/network analysis is core to the use case
   3. Budget allows for graph construction cost
   Otherwise, hybrid dense+sparse RAG with good reranking covers 80% of cases."
```
