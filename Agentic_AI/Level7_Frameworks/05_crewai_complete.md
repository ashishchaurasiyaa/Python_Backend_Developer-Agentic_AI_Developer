# CrewAI — Agents, Tasks, Crew, Sequential vs Hierarchical

## Quick Concepts
- **Agent** = role-based AI worker — backstory, goal, tools dete hain
- **Task** = specific work unit — description, expected_output, assigned agent
- **Crew** = agents + tasks ka team — orchestrates execution
- **Process** = Sequential (ek ke baad ek) ya Hierarchical (manager assigns work)
- **Tool** = agent ke paas available capability

---

## Interview Questions & Answers

### Q1: CrewAI basic setup — agents aur tasks kaise banate hain?
**Answer:**
```python
# pip install crewai crewai-tools

from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, WebsiteSearchTool, FileReadTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# LLM setup
claude = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.7)
gpt4 = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

# Tools
search_tool = SerperDevTool()   # Google search
web_tool = WebsiteSearchTool()  # Website content

# ===== AGENTS =====
researcher = Agent(
    role="Senior Research Analyst",
    goal="Uncover cutting-edge developments in AI and Python backend development",
    backstory="""You are an expert researcher with 10 years of experience.
    You excel at finding accurate, up-to-date information and synthesizing
    complex topics into clear insights.""",
    tools=[search_tool, web_tool],
    llm=claude,
    verbose=True,
    max_iter=5,               # max tool call iterations
    allow_delegation=False,   # can delegate to other agents?
)

writer = Agent(
    role="Technical Content Writer",
    goal="Write clear, engaging technical documentation and tutorials",
    backstory="""You are a skilled technical writer who makes complex concepts
    accessible. You write production-quality documentation with code examples.""",
    tools=[],  # no tools needed for writing
    llm=claude,
    verbose=True,
)

code_reviewer = Agent(
    role="Senior Python Developer",
    goal="Review code for quality, security, and best practices",
    backstory="""You are a senior Python developer with expertise in FastAPI,
    async programming, and production systems. You catch bugs others miss.""",
    tools=[FileReadTool()],
    llm=gpt4,  # different LLM per agent
    verbose=True,
)

# ===== TASKS =====
research_task = Task(
    description="""Research the latest best practices for building RAG (Retrieval-Augmented
    Generation) systems in Python. Focus on:
    1. Best embedding models in 2025
    2. Vector database comparisons (pgvector vs Pinecone vs Qdrant)
    3. Chunking strategies
    
    Include specific version numbers and benchmarks.""",
    expected_output="""A comprehensive research report (500+ words) covering:
    - Top embedding models with performance metrics
    - Vector DB comparison table
    - Chunking strategy recommendations with examples""",
    agent=researcher,
    output_file="research_report.md",  # save to file
)

writing_task = Task(
    description="""Based on the research provided, write a comprehensive technical guide
    on building a production RAG system with Python and FastAPI.
    Include code examples for each major step.""",
    expected_output="""A technical tutorial with:
    - Architecture overview
    - Step-by-step implementation guide
    - Complete working code examples
    - Performance optimization tips""",
    agent=writer,
    context=[research_task],  # uses research_task output as input
    output_file="rag_tutorial.md",
)

# ===== CREW =====
crew = Crew(
    agents=[researcher, writer, code_reviewer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # tasks execute in order
    verbose=True,
    memory=True,             # enable crew memory
    cache=True,              # cache tool results
    max_rpm=10,              # max requests per minute
    share_crew=False,
)

# Run
result = crew.kickoff()
print(result)
print(f"Usage: {crew.usage_metrics}")
```

---

### Q2: Hierarchical process — manager agent workers assign karta hai?
**Answer:**
```python
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, CodeInterpreterTool

# Manager agent
project_manager = Agent(
    role="Project Manager",
    goal="Coordinate team to deliver high-quality software projects on time",
    backstory="""Experienced PM who breaks projects into tasks, assigns to right
    team members, and ensures quality delivery. You delegate effectively.""",
    llm=claude,
    allow_delegation=True,  # REQUIRED for manager
    verbose=True,
)

# Worker agents
backend_dev = Agent(
    role="Senior Backend Developer",
    goal="Build robust, scalable Python backend APIs",
    backstory="Expert in FastAPI, PostgreSQL, Redis, and microservices.",
    tools=[CodeInterpreterTool()],
    llm=claude,
    allow_delegation=False,
)

frontend_dev = Agent(
    role="Frontend Developer",
    goal="Build responsive, user-friendly web interfaces",
    backstory="Expert in React, TypeScript, and modern CSS.",
    llm=gpt4,
    allow_delegation=False,
)

qa_engineer = Agent(
    role="QA Engineer",
    goal="Ensure software quality through comprehensive testing",
    backstory="Expert in pytest, Playwright, and test automation.",
    llm=gpt4,
    allow_delegation=False,
)

# ONE task — manager decides who does what
build_feature_task = Task(
    description="""Build a complete user authentication feature including:
    1. Backend: JWT authentication API (FastAPI + PostgreSQL)
    2. Frontend: Login/Register forms (React)
    3. Tests: Unit + integration tests
    
    Each component should be production-ready.""",
    expected_output="""Complete implementation with:
    - Backend API code with endpoints
    - Frontend components
    - Test suite with >80% coverage
    - Integration guide""",
    agent=project_manager,  # Manager coordinates
)

# Hierarchical crew — manager assigns to workers
crew = Crew(
    # NOTE: hierarchical mode me manager ko workers `agents` list me MAT daalo — sirf workers.
    # Manager alag se manager_agent (ya manager_llm) se aata hai; CrewAI use khud orchestrate karta hai.
    agents=[backend_dev, frontend_dev, qa_engineer],
    tasks=[build_feature_task],
    process=Process.hierarchical,      # Manager-led
    manager_agent=project_manager,     # workers list se ALAG
    verbose=True,
    memory=True,
)

result = crew.kickoff()
```

---

### Q3: Custom tools CrewAI mein kaise banate hain?
**Answer:**
```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import asyncpg
import json
import asyncio

# ===== Method 1: @tool decorator =====
from crewai.tools import tool

@tool("Database Query Tool")
def query_database(sql: str) -> str:
    """
    Execute a SELECT SQL query on the production database.
    Only SELECT queries are allowed for safety.
    Input: SQL SELECT query string
    Output: Query results as JSON string
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries allowed"
    
    # Synchronous wrapper for async operation
    async def _query():
        conn = await asyncpg.connect("postgresql://user:pass@localhost/mydb")
        rows = await conn.fetch(sql + " LIMIT 100")
        await conn.close()
        return [dict(row) for row in rows]
    
    try:
        results = asyncio.run(_query())
        return json.dumps(results, default=str)
    except Exception as e:
        return f"Database error: {e}"

# ===== Method 2: BaseTool class =====
class GitHubSearchInput(BaseModel):
    query: str = Field(description="GitHub search query")
    language: str = Field(default="python", description="Programming language filter")
    max_results: int = Field(default=5, description="Maximum results to return")

class GitHubSearchTool(BaseTool):
    name: str = "GitHub Repository Search"
    description: str = """Search GitHub repositories for code examples and libraries.
    Useful for finding open-source implementations and best practices."""
    args_schema: Type[BaseModel] = GitHubSearchInput

    def _run(self, query: str, language: str = "python", max_results: int = 5) -> str:
        import httpx
        
        try:
            response = httpx.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} language:{language}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": max_results,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            
            data = response.json()
            repos = data.get("items", [])
            
            results = []
            for repo in repos:
                results.append({
                    "name": repo["full_name"],
                    "description": repo["description"],
                    "stars": repo["stargazers_count"],
                    "url": repo["html_url"],
                })
            
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"GitHub search error: {e}"

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)

# Use custom tools in agent
researcher_with_custom_tools = Agent(
    role="Python Research Specialist",
    goal="Find best Python libraries and code patterns",
    backstory="Expert at finding and evaluating Python tools and frameworks.",
    tools=[
        GitHubSearchTool(),
        query_database,
    ],
    llm=claude,
)
```

---

### Q4: CrewAI Memory — agents ke beech information share karna?
**Answer:**
```python
from crewai import Crew, Process, Agent, Task
from crewai.memory import (
    ShortTermMemory,
    LongTermMemory,
    EntityMemory,
)
from crewai.memory.storage.rag_storage import RAGStorage
from langchain_openai import OpenAIEmbeddings

# Memory types:
# ShortTermMemory: Current execution context
# LongTermMemory: Persistent across crew runs (SQLite)
# EntityMemory: Named entities track karta hai (people, companies, etc.)

crew_with_memory = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    memory=True,              # Enable all memory types
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"}
    },
    verbose=True,
)

# Long-term memory with custom storage
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage

crew_with_persistent_memory = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    memory=True,
    long_term_memory=LongTermMemory(
        storage=LTMSQLiteStorage(db_path="crew_memory.db")
    ),
)

# Kickoff with context (pass data to crew)
result = crew_with_memory.kickoff(
    inputs={
        "topic": "RAG systems",
        "target_audience": "senior Python developers",
        "deadline": "2026-05-30",
    }
)
```

---

### Q5: CrewAI vs LangGraph — kab kya use karo?
**Answer:**
```
CrewAI:
  ✓ Quick setup — YAML/Python config
  ✓ Role-based team metaphor — easy to understand
  ✓ Built-in tools ecosystem (50+ integrations)
  ✓ Memory, caching built-in
  ✓ Good for content creation, research, analysis workflows
  ✗ Less control over exact execution flow
  ✗ Harder to debug complex behaviors
  ✗ Limited graph/cycle support

LangGraph:
  ✓ Full control over workflow graph
  ✓ Complex conditional routing
  ✓ Human-in-the-loop with interrupts
  ✓ Checkpointing + resume
  ✓ Production-grade, more flexible
  ✗ More code required
  ✗ Steeper learning curve

Decision matrix:
  Simple multi-agent research/writing → CrewAI
  Complex stateful agent with loops    → LangGraph
  Customer service bot with escalation → LangGraph (human-in-loop)
  Code review pipeline                 → CrewAI (simple sequential)
  Dynamic workflow decisions           → LangGraph
  Rapid prototyping                    → CrewAI (faster to build)
  Production enterprise system         → LangGraph

YAML-based CrewAI config (newer approach):
```

```yaml
# agents.yaml
researcher:
  role: Senior Research Analyst
  goal: Uncover latest AI developments
  backstory: Expert researcher with 10 years experience...

writer:
  role: Technical Writer
  goal: Write clear technical documentation
  backstory: Skilled writer making complex concepts accessible...
```

```yaml
# tasks.yaml
research_task:
  description: Research {topic} and find key insights
  expected_output: Comprehensive report on {topic}
  agent: researcher

writing_task:
  description: Write tutorial based on research
  expected_output: Complete tutorial with code examples
  agent: writer
  context: [research_task]
```

```python
# main.py
from crewai import Crew, Process
from crewai.project import CrewBase, agent, task, crew

@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"], tools=[search_tool])

    @agent
    def writer(self) -> Agent:
        return Agent(config=self.agents_config["writer"])

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def writing_task(self) -> Task:
        return Task(config=self.tasks_config["writing_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential)

if __name__ == "__main__":
    crew = ResearchCrew()
    result = crew.crew().kickoff(inputs={"topic": "LangGraph vs CrewAI"})
    print(result)
```
