"""
Phase5_CrewAI — Complete Practical
=====================================
Topics:
  1. Agent / Task / Crew fundamentals
  2. Sequential vs Hierarchical process
  3. Built-in tools (search, file, code)
  4. Custom BaseTool
  5. Memory types (short/long-term/entity/contextual)
  6. Real-world: research → writer → reviewer crew

Install: pip install crewai crewai-tools
Env: OPENAI_API_KEY

Run: python 01_crewai_practical.py
"""

import os
from typing import Optional, Any
from dataclasses import dataclass, field

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("CREWAI CONCEPTS")
print("=" * 60)

CREWAI_CONCEPTS = {
    "Agent":       "An AI worker with a role, goal, backstory, tools, and LLM",
    "Task":        "A unit of work: description, expected output, assigned agent",
    "Crew":        "A team of agents with a process (sequential/hierarchical)",
    "Process":     "How tasks execute: sequential (chain) or hierarchical (manager routes)",
    "Tool":        "Function an agent can call (search, read file, run code, custom)",
    "Memory":      "Short-term (conversation), long-term (ChromaDB), entity (NER store)",
    "Delegation":  "Agent can delegate sub-tasks to other agents (hierarchical only)",
    "Kickoff":     "crew.kickoff(inputs={...}) — starts execution, returns final output",
}
for k, v in CREWAI_CONCEPTS.items():
    print(f"  {k:<14}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Agents and Tasks
# INTERVIEW: role+goal+backstory = prompt injection that shapes behavior
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Agent & Task Definitions")
print("=" * 60)

AGENT_CODE = '''\
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, FileReadTool, WebsiteSearchTool
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

# ── Define Agents ──────────────────────────────────────────────
# INTERVIEW: role/goal/backstory = system prompt content
researcher = Agent(
    role      = "Senior Research Analyst",
    goal      = "Find accurate, up-to-date information on {topic}",
    backstory  = (
        "You are an expert researcher with 10 years of experience. "
        "You find reliable sources and extract key facts. "
        "You NEVER make up information — if unsure, you say so."
    ),
    tools     = [SerperDevTool(), WebsiteSearchTool()],
    llm       = llm,
    verbose   = True,
    max_iter  = 5,   # prevent infinite loops
    memory    = True,
)

writer = Agent(
    role      = "Technical Writer",
    goal      = "Write clear, engaging content based on research",
    backstory  = (
        "You transform complex research into accessible articles. "
        "You use markdown formatting and include code examples."
    ),
    llm       = llm,
    verbose   = True,
    allow_delegation = False,  # writer doesn\'t delegate
)

reviewer = Agent(
    role      = "Quality Reviewer",
    goal      = "Ensure accuracy, completeness, and clarity of content",
    backstory  = "You are a strict technical editor who catches errors.",
    llm       = llm,
    verbose   = False,
)

# ── Define Tasks ───────────────────────────────────────────────
# INTERVIEW: expected_output is crucial — guides agent on what to produce
research_task = Task(
    description      = "Research the latest developments in {topic}. "
                       "Find 5 key facts, real examples, and current trends.",
    expected_output  = "A structured report with 5 key facts, examples, and sources.",
    agent            = researcher,
    output_file      = "research_output.md",  # save output to file
)

writing_task = Task(
    description      = "Write a 500-word technical blog post about {topic} "
                       "based on the research provided. Include code examples.",
    expected_output  = "A 500-word markdown blog post with code examples.",
    agent            = writer,
    context          = [research_task],  # uses research_task output as context!
)

review_task = Task(
    description      = "Review the blog post for technical accuracy, completeness, "
                       "and readability. Provide a score (1-10) and improvements.",
    expected_output  = "Review with score, 3 strengths, 3 improvement areas.",
    agent            = reviewer,
    context          = [writing_task],
)
'''
print(AGENT_CODE[:800])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Crew Processes
# INTERVIEW: Sequential = pipeline, Hierarchical = manager delegates
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Sequential vs Hierarchical Process")
print("=" * 60)

PROCESS_CODE = '''\
from crewai import Crew, Process
from langchain_openai import ChatOpenAI

# ── Sequential Process ─────────────────────────────────────────
# INTERVIEW: Tasks run in order, output of each → context of next
sequential_crew = Crew(
    agents  = [researcher, writer, reviewer],
    tasks   = [research_task, writing_task, review_task],
    process = Process.sequential,
    verbose = 2,
    memory  = True,  # enable memory across tasks
)

# Run the crew
result = sequential_crew.kickoff(inputs={"topic": "LangGraph for AI agents"})
print(result)

# ── Hierarchical Process ───────────────────────────────────────
# INTERVIEW: Manager LLM decides which agent to call and in what order
manager_llm = ChatOpenAI(model="gpt-4o", temperature=0)  # use stronger model for manager

hierarchical_crew = Crew(
    agents      = [researcher, writer, reviewer],
    tasks       = [research_task, writing_task, review_task],
    process     = Process.hierarchical,
    manager_llm = manager_llm,  # dedicated manager agent
    verbose     = True,
)
result = hierarchical_crew.kickoff(inputs={"topic": "Vector databases"})

# ── Async execution ────────────────────────────────────────────
import asyncio
result = asyncio.run(sequential_crew.kickoff_async(inputs={"topic": "RAG"}))

# ── Batch execution ────────────────────────────────────────────
results = sequential_crew.kickoff_for_each(inputs=[
    {"topic": "FastAPI"},
    {"topic": "LangChain"},
    {"topic": "Docker"},
])
'''
print(PROCESS_CODE[:700])

print("\n  Process comparison:")
print("  Sequential:    task1 → task2 → task3 (ordered pipeline)")
print("                 Predictable, good for content pipelines")
print("  Hierarchical:  manager routes to agents dynamically")
print("                 Flexible, good for complex multi-step research")
print("  Use sequential: if task order is always fixed (write → review)")
print("  Use hierarchical: if task order depends on what's discovered")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Custom Tools
# INTERVIEW: Extend CrewAI with any Python function as a tool
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Custom Tools (BaseTool)")
print("=" * 60)

CUSTOM_TOOL_CODE = '''\
from crewai_tools import BaseTool
from pydantic import BaseModel, Field
import requests, json

# ── Method 1: @tool decorator (simple) ────────────────────────
from crewai.tools import tool

@tool("Get Stock Price")
def get_stock_price(ticker: str) -> str:
    """Get the current stock price for a given ticker symbol."""
    # In production: call real API
    return f"{ticker}: $150.23 (+2.1%)"

# ── Method 2: BaseTool subclass (recommended for complex tools) ──
class DatabaseSearchTool(BaseTool):
    name:        str = "Database Search"
    description: str = (
        "Search the internal knowledge base for technical documentation. "
        "Input: search query string. Returns: top 3 matching documents."
    )

    # Optional: input schema validation
    class InputSchema(BaseModel):
        query: str = Field(description="The search query")
        limit: int = Field(default=3, description="Number of results")

    def _run(self, query: str, limit: int = 3) -> str:
        """Execute the tool."""
        # Real implementation: search vector DB, SQL DB, etc.
        results = [
            f"Doc {i+1}: Result for \'{query}\'..."
            for i in range(limit)
        ]
        return json.dumps({"results": results})

    async def _arun(self, query: str, limit: int = 3) -> str:
        """Async version."""
        return self._run(query, limit)


# ── Tool with caching ──────────────────────────────────────────
class CachedSearchTool(BaseTool):
    name:        str = "Cached Web Search"
    description: str = "Search the web, results are cached for 1 hour."
    cache_function: Optional[callable] = None   # CrewAI built-in cache

    def _run(self, query: str) -> str:
        # CrewAI calls cache_function(args, result) if provided
        return f"Search results for: {query}"


# Use custom tools in agent
db_tool     = DatabaseSearchTool()
stock_tool  = get_stock_price

analyst = Agent(
    role  = "Financial Analyst",
    goal  = "Analyze stock performance",
    tools = [db_tool, stock_tool],
    llm   = llm,
)
'''
print(CUSTOM_TOOL_CODE[:700])


# Mock BaseTool to demonstrate the pattern
class MockBaseTool:
    """
    INTERVIEW: BaseTool requires:
    - name: str — tool name shown to LLM
    - description: str — what the tool does (LLM reads this to decide when to use it)
    - _run(): str — execute the tool, return string result
    Description quality is critical! Vague = tool won't be used correctly.
    """
    name: str = "Mock Tool"
    description: str = "A mock tool for demonstration"

    def _run(self, query: str) -> str:
        return f"Mock result for: {query}"

    def run(self, query: str) -> str:
        """Public interface — catches errors, formats output."""
        try:
            result = self._run(query)
            return result
        except Exception as e:
            return f"Tool error: {e}"


class DatabaseSearchTool(MockBaseTool):
    name = "Database Search"
    description = "Search internal docs. Input: query. Returns: matching documents."

    def _run(self, query: str) -> str:
        results = {
            "python": ["Python is interpreted", "Python has GIL", "Python 3.12 released"],
            "fastapi": ["FastAPI uses ASGI", "FastAPI auto-generates OpenAPI docs"],
        }
        key = query.lower().split()[0] if query else ""
        return str(results.get(key, [f"No results for '{query}'"]))


tool = DatabaseSearchTool()
print("\n  Custom tool demo:")
print(f"  Tool: {tool.name}")
print(f"  Query 'python': {tool.run('python')}")
print(f"  Query 'fastapi': {tool.run('fastapi')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Memory Configuration
# INTERVIEW: memory=True enables all 4 memory types
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Memory in CrewAI")
print("=" * 60)

MEMORY_CODE = '''\
from crewai import Crew, Process
from crewai.memory import (
    ShortTermMemory,   # within a single kickoff (conversation buffer)
    LongTermMemory,    # persists across kickoffs (ChromaDB-backed)
    EntityMemory,      # tracks named entities (people, companies, etc.)
)

# ── Enable all memory types ────────────────────────────────────
crew = Crew(
    agents  = [researcher, writer],
    tasks   = [research_task, writing_task],
    process = Process.sequential,
    memory  = True,              # enables short + long + entity memory

    # Optional: custom storage
    long_term_memory  = LongTermMemory(
        storage=ChromaDBStorage(path="./crew_memory")
    ),
    entity_memory     = EntityMemory(
        storage=ChromaDBStorage(path="./entity_memory")
    ),
)

# ── Memory types ───────────────────────────────────────────────
# Short-term: last N exchanges in the current crew run
# Long-term:  what the crew learned in PAST runs (persists to disk)
# Entity:     "Alice is a Python developer" — remembered across runs
# Contextual: task context from previous tasks in same run

# ── Reset memory ──────────────────────────────────────────────
crew.reset_memories(command_type="all")   # wipe all memories
crew.reset_memories(command_type="long")  # wipe only long-term
'''
print(MEMORY_CODE[:600])

print("\n  Memory types:")
MEMORY_TYPES = {
    "Short-term":  "Buffer of last N interactions in current run. Like working memory.",
    "Long-term":   "ChromaDB-persisted knowledge across runs. Crew 'remembers' past work.",
    "Entity":      "Named entities: 'Alice → Python developer at Google'. NER-based.",
    "Contextual":  "Task output passed as context to subsequent tasks in same run.",
}
for t, d in MEMORY_TYPES.items():
    print(f"  {t:<14}: {d}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Full Pipeline Demo (Mock)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Complete Research Pipeline (Mock)")
print("=" * 60)


@dataclass
class MockAgent:
    role: str
    goal: str
    tools: list = field(default_factory=list)

    def execute_task(self, task_description: str, context: str = "") -> str:
        """Mock task execution."""
        role_responses = {
            "Research Analyst": f"Research findings: [1] Key fact about {task_description[:30]}... [2] Related concept... [3] Current trend...",
            "Technical Writer": f"# Article\n\nBased on research: {context[:50]}...\n\nThis is a comprehensive guide...",
            "Quality Reviewer": f"Review Score: 8/10\nStrengths: Clear structure, Good examples\nImprovements: Add more code examples",
        }
        return role_responses.get(self.role, f"[{self.role}]: Task completed — {task_description[:50]}")


@dataclass
class MockTask:
    description: str
    agent: MockAgent
    context_tasks: list = field(default_factory=list)
    output: str = ""

    def run(self) -> str:
        context = " | ".join(t.output for t in self.context_tasks if t.output)
        self.output = self.agent.execute_task(self.description, context)
        return self.output


@dataclass
class MockCrew:
    agents: list
    tasks: list
    process: str = "sequential"

    def kickoff(self, inputs: dict) -> str:
        print(f"\n  Crew kickoff with inputs: {inputs}")
        print(f"  Process: {self.process}")
        results = []
        for i, task in enumerate(self.tasks):
            print(f"\n  Task {i+1} [{task.agent.role}]:")
            print(f"    Description: {task.description[:60]}...")
            output = task.run()
            print(f"    Output: {output[:80]}...")
            results.append(output)
        return results[-1]  # return last task output


# Build mock crew
researcher_agent = MockAgent("Research Analyst", "Find information", [DatabaseSearchTool()])
writer_agent     = MockAgent("Technical Writer", "Write content")
reviewer_agent   = MockAgent("Quality Reviewer", "Review content")

r_task = MockTask("Research Python async programming patterns", researcher_agent)
w_task = MockTask("Write blog post about Python async", writer_agent, context_tasks=[r_task])
v_task = MockTask("Review the blog post for quality", reviewer_agent, context_tasks=[w_task])

crew = MockCrew(
    agents=[researcher_agent, writer_agent, reviewer_agent],
    tasks=[r_task, w_task, v_task],
    process="sequential",
)
final = crew.kickoff(inputs={"topic": "Python async programming"})
print(f"\n  Final output: {final[:100]}")


print("\n" + "=" * 60)
print("CREWAI INTERVIEW SUMMARY:")
print("  Agent = role + goal + backstory + tools + LLM")
print("  Task  = description + expected_output + agent + optional context")
print("  Crew  = agents + tasks + process (sequential/hierarchical)")
print("  Sequential: fixed pipeline, hierarchical: manager routes dynamically")
print("  Custom tools: BaseTool subclass with name, description, _run()")
print("  memory=True: short/long/entity memory across tasks and runs")
print("  kickoff(inputs={...}) → executes crew, returns final task output")
print("=" * 60)
