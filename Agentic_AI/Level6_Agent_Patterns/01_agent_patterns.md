# Agent Patterns — ReAct, Reflection, Memory Types, Error Recovery

## Quick Concepts
- **ReAct** = Reason + Act — agent sochta hai phir action leta hai, loop mein
- **Reflection** = agent apna output khud evaluate karta hai aur improve karta hai
- **Planning** = task ko sub-tasks mein todna, phir execute karna
- **Tool selection** = agent dynamically decide karta hai kaun sa tool use karna hai
- **Error recovery** = failure pe retry, alternative approach, human escalation

---

## Interview Questions & Answers

### Q1: ReAct pattern kya hai? Kaise implement karte hain?
**Answer:**
```python
# ReAct = Reasoning + Acting
# Loop: Thought → Action → Observation → Thought → ... → Final Answer

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
import json

model = ChatAnthropic(model="claude-sonnet-4-6")

# Tools
@tool
def search(query: str) -> str:
    """Search for information on the internet."""
    # Mock implementation
    results = {
        "python generators": "Generators use yield keyword, lazy evaluation",
        "fastapi vs flask": "FastAPI is faster, async-native, has auto docs",
    }
    for key, value in results.items():
        if key in query.lower():
            return value
    return f"Search results for '{query}': Found relevant information about {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"

@tool
def get_current_date() -> str:
    """Get the current date."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

tools = [search, calculate, get_current_date]
tools_map = {t.name: t for t in tools}

# ReAct prompt
REACT_SYSTEM = """You are a helpful assistant that uses tools to answer questions.

Available tools:
{tools_description}

To use a tool, respond with:
Thought: [your reasoning]
Action: tool_name
Input: tool_input

When you have the final answer:
Thought: I now know the final answer
Final Answer: [your answer]"""

# Manual ReAct loop (educational — use LangGraph prebuilt in production)
def react_agent(question: str, max_iterations: int = 5) -> str:
    tools_description = "\n".join([
        f"- {t.name}: {t.description}" for t in tools
    ])
    
    messages = [
        HumanMessage(content=question)
    ]
    
    model_with_tools = model.bind_tools(tools)
    
    for i in range(max_iterations):
        print(f"\n--- Iteration {i+1} ---")
        
        response = model_with_tools.invoke(messages)
        messages.append(response)
        
        # Check if done
        if not response.tool_calls:
            return response.content
        
        # Execute tools
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]
            
            print(f"Calling tool: {tool_name}({tool_input})")
            
            if tool_name in tools_map:
                tool_result = tools_map[tool_name].invoke(tool_input)
            else:
                tool_result = f"Unknown tool: {tool_name}"
            
            print(f"Tool result: {tool_result}")
            
            messages.append(ToolMessage(
                content=str(tool_result),
                tool_call_id=tool_call["id"]
            ))
    
    return "Max iterations reached"

# Usage
result = react_agent("What is 15 * 23, and what is today's date?")
print(f"\nFinal: {result}")
```

---

### Q2: Reflection pattern — agent apna output kaise improve karta hai?
**Answer:**
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages

model = ChatAnthropic(model="claude-sonnet-4-6")

# ===== BASIC REFLECTION =====
def reflection_chain(task: str, max_reflections: int = 3) -> str:
    """Generate → Critique → Improve loop"""
    
    # Step 1: Initial generation
    initial = model.invoke([
        HumanMessage(content=f"Complete this task: {task}")
    ]).content
    
    current = initial
    
    for i in range(max_reflections):
        # Step 2: Critique
        critique = model.invoke([
            SystemMessage(content="You are a strict critic. Find flaws, missing parts, and improvements."),
            HumanMessage(content=f"Critique this response:\n\n{current}\n\nOriginal task: {task}")
        ]).content
        
        # Check if good enough
        if "no significant issues" in critique.lower() or "excellent" in critique.lower():
            print(f"Stopped after {i+1} reflections — quality sufficient")
            break
        
        # Step 3: Improve based on critique
        current = model.invoke([
            SystemMessage(content="Improve the response based on the critique."),
            HumanMessage(content=f"""
Original task: {task}

Current response:
{current}

Critique:
{critique}

Improved response:""")
        ]).content
        
        print(f"Reflection {i+1}: Improved ({len(current)} chars)")
    
    return current

# Usage
result = reflection_chain("Write a Python function to implement a binary search tree")
print(result)

# ===== LANGGRAPH REFLECTION AGENT =====
class ReflectionState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    draft: str
    critique: str
    iterations: int
    max_iterations: int

def generate_node(state: ReflectionState) -> ReflectionState:
    """Generate or regenerate content"""
    if state["draft"]:
        # Regenerate with critique
        prompt = f"""Task: {state['task']}

Previous draft:
{state['draft']}

Critique:
{state['critique']}

Improved version:"""
    else:
        prompt = f"Complete this task thoroughly: {state['task']}"
    
    response = model.invoke([HumanMessage(content=prompt)])
    return {
        "draft": response.content,
        "iterations": state.get("iterations", 0) + 1
    }

def critique_node(state: ReflectionState) -> ReflectionState:
    """Critique the current draft"""
    response = model.invoke([
        SystemMessage(content="""You are an expert reviewer.
Evaluate the response for:
1. Correctness and accuracy
2. Completeness
3. Code quality (if code present)
4. Missing edge cases

If satisfactory, start with: "APPROVED:"
Otherwise, list specific improvements needed."""),
        HumanMessage(content=f"Task: {state['task']}\n\nDraft:\n{state['draft']}")
    ])
    return {"critique": response.content}

def should_continue_reflection(state: ReflectionState) -> str:
    if state["iterations"] >= state["max_iterations"]:
        return "end"
    if state["critique"].startswith("APPROVED:"):
        return "end"
    return "generate"

# Build reflection graph
builder = StateGraph(ReflectionState)
builder.add_node("generate", generate_node)
builder.add_node("critique", critique_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "critique")
builder.add_conditional_edges(
    "critique",
    should_continue_reflection,
    {"generate": "generate", "end": END}
)

reflection_graph = builder.compile()

result = reflection_graph.invoke({
    "task": "Implement a Python class for a thread-safe LRU cache",
    "draft": "",
    "critique": "",
    "iterations": 0,
    "max_iterations": 3,
    "messages": [],
})
print(f"Final draft (after {result['iterations']} iterations):")
print(result["draft"])
```

---

### Q3: Planning pattern — complex tasks ko kaise todta hai agent?
**Answer:**
```python
from pydantic import BaseModel, Field
from typing import List
import instructor
import anthropic

client = instructor.from_anthropic(anthropic.Anthropic())

# ===== STRUCTURED PLANNING =====
class SubTask(BaseModel):
    id: int
    description: str
    tool_needed: str = Field(description="Which tool/skill needed: search, code, write, calculate, none")
    depends_on: List[int] = Field(default=[], description="IDs of tasks this depends on")
    estimated_time: str = Field(description="quick/medium/long")

class ExecutionPlan(BaseModel):
    goal: str
    subtasks: List[SubTask]
    final_synthesis: str = Field(description="How to combine results at the end")

def create_plan(task: str) -> ExecutionPlan:
    """Break task into executable sub-tasks"""
    return client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        response_model=ExecutionPlan,
        messages=[{
            "role": "user",
            "content": f"""Create a step-by-step execution plan for:

{task}

Break it into specific, executable sub-tasks with clear dependencies."""
        }]
    )

# ===== PLAN + EXECUTE =====
async def plan_and_execute(task: str):
    # 1. Create plan
    plan = create_plan(task)
    print(f"Goal: {plan.goal}")
    print(f"Sub-tasks: {len(plan.subtasks)}")
    
    results = {}
    
    # 2. Execute tasks respecting dependencies
    for subtask in plan.subtasks:
        # Wait for dependencies
        deps_done = all(dep in results for dep in subtask.depends_on)
        if not deps_done:
            print(f"Waiting for dependencies: {subtask.depends_on}")
            continue
        
        print(f"\nExecuting task {subtask.id}: {subtask.description}")
        
        # Gather context from dependencies
        dep_context = "\n".join([
            f"Task {dep} result: {results[dep]}"
            for dep in subtask.depends_on
        ])
        
        # Execute with context
        response = model.invoke([
            HumanMessage(content=f"""
Task: {subtask.description}

Context from previous steps:
{dep_context}

Complete this specific task.""")
        ])
        
        results[subtask.id] = response.content
        print(f"Task {subtask.id} done: {response.content[:100]}...")
    
    # 3. Synthesize final result
    final_response = model.invoke([
        HumanMessage(content=f"""
Original goal: {plan.goal}

Results from all sub-tasks:
{chr(10).join([f'Task {k}: {v}' for k, v in results.items()])}

Now {plan.final_synthesis}""")
    ])
    
    return final_response.content

import asyncio
result = asyncio.run(plan_and_execute(
    "Build a complete user authentication system with JWT, refresh tokens, and rate limiting"
))
```

---

### Q4: Error recovery aur retry strategies?
**Answer:**
```python
from langgraph.graph import StateGraph, END, START
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

class ResilientAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    result: str
    error: str
    retry_count: int
    max_retries: int
    fallback_used: bool

# ===== ERROR RECOVERY STRATEGIES =====

def primary_executor(state: ResilientAgentState) -> ResilientAgentState:
    """Primary approach — try best model/strategy"""
    try:
        # Simulate potential failure
        response = model.invoke([
            HumanMessage(content=f"Execute: {state['task']}")
        ])
        
        # Validate response
        if len(response.content) < 10:
            raise ValueError("Response too short — likely failed")
        
        return {"result": response.content, "error": ""}
        
    except Exception as e:
        return {"error": str(e), "result": ""}

def error_handler(state: ResilientAgentState) -> str:
    """Decide recovery strategy based on error type"""
    error = state.get("error", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if not error:
        return "success"
    
    if retry_count >= max_retries:
        return "human_escalation"
    
    if "rate limit" in error.lower():
        return "rate_limit_retry"
    
    if "context" in error.lower() or "too long" in error.lower():
        return "simplify_task"
    
    return "retry"

def retry_with_backoff(state: ResilientAgentState) -> ResilientAgentState:
    """Retry with exponential backoff"""
    import time
    
    retry_count = state.get("retry_count", 0) + 1
    wait_time = 2 ** retry_count  # 2, 4, 8 seconds
    
    print(f"Retry {retry_count}, waiting {wait_time}s...")
    time.sleep(wait_time)
    
    return {"retry_count": retry_count}

def fallback_executor(state: ResilientAgentState) -> ResilientAgentState:
    """Simpler fallback approach when primary fails"""
    from langchain_openai import ChatOpenAI
    
    fallback_model = ChatOpenAI(model="gpt-4o-mini")
    
    try:
        response = fallback_model.invoke([
            HumanMessage(content=f"Execute (simplified): {state['task'][:500]}")
        ])
        return {
            "result": response.content,
            "error": "",
            "fallback_used": True
        }
    except Exception as e:
        return {"error": f"Fallback also failed: {e}"}

def simplify_and_retry(state: ResilientAgentState) -> ResilientAgentState:
    """Simplify task if context too long"""
    simplified = model.invoke([
        HumanMessage(content=f"Summarize this task in 1 sentence: {state['task']}")
    ]).content
    
    return {"task": simplified, "retry_count": state.get("retry_count", 0) + 1}

def escalate_to_human(state: ResilientAgentState) -> ResilientAgentState:
    """Last resort: escalate to human"""
    escalation_message = f"""
    ⚠️  Agent failed after {state['retry_count']} retries
    Task: {state['task']}
    Last error: {state['error']}
    Human intervention required.
    """
    print(escalation_message)
    return {"result": "ESCALATED_TO_HUMAN", "error": ""}

# Build resilient agent graph
builder = StateGraph(ResilientAgentState)
builder.add_node("execute", primary_executor)
builder.add_node("retry", retry_with_backoff)
builder.add_node("fallback", fallback_executor)
builder.add_node("simplify", simplify_and_retry)
builder.add_node("escalate", escalate_to_human)

builder.add_edge(START, "execute")
builder.add_conditional_edges("execute", error_handler, {
    "success": END,
    "retry": "retry",
    "rate_limit_retry": "retry",
    "simplify_task": "simplify",
    "human_escalation": "escalate",
})
builder.add_edge("retry", "execute")
builder.add_edge("simplify", "execute")
builder.add_edge("fallback", END)
builder.add_edge("escalate", END)

resilient_agent = builder.compile()
```

---

### Q5: Memory types — agent ko kaise yaad rehta hai?
**Answer:**
```
AGENT MEMORY TYPES:

1. IN-CONTEXT MEMORY (Short-term)
   - Current conversation messages
   - Retrieved documents in prompt
   - Tool results added to messages
   - Limited by context window (200K tokens for Claude)

2. EXTERNAL MEMORY (Long-term)
   - Vector DB (semantic search): ChromaDB, pgvector, Pinecone
   - Key-Value: Redis (fast, ephemeral), PostgreSQL (persistent)
   - Episodic: Conversation summaries stored in DB
   - Procedural: "How to" knowledge — usually stored prompts / skills / workflows / tool-use rules
     (fine-tuning-into-weights ek option hai par practice me kam — mostly prompts/skills me rehta hai)

3. IMPLEMENTATION PATTERNS:
```

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Pattern 1: Sliding window memory
class SlidingWindowMemory:
    def __init__(self, max_messages: int = 20):
        self.messages = []
        self.max_messages = max_messages

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            # Keep system message, remove oldest
            self.messages = self.messages[-self.max_messages:]

    def get_context(self) -> list:
        return self.messages.copy()

# Pattern 2: Summarization memory
class SummaryMemory:
    def __init__(self, max_tokens: int = 2000):
        self.summary = ""
        self.recent_messages = []
        self.max_tokens = max_tokens

    async def add_and_summarize(self, role: str, content: str):
        self.recent_messages.append({"role": role, "content": content})
        
        # When too long, summarize old messages
        total_len = sum(len(m["content"]) for m in self.recent_messages)
        if total_len > self.max_tokens * 4:  # rough char/token ratio
            old_messages = self.recent_messages[:-5]  # keep last 5
            
            summary_prompt = f"""Summarize this conversation:
{self.summary}
New messages:
{chr(10).join([f'{m["role"]}: {m["content"]}' for m in old_messages])}

Keep key facts, decisions, and context."""
            
            self.summary = model.invoke([HumanMessage(content=summary_prompt)]).content
            self.recent_messages = self.recent_messages[-5:]

    def get_context(self) -> list:
        messages = []
        if self.summary:
            messages.append({
                "role": "system",
                "content": f"Conversation summary: {self.summary}"
            })
        messages.extend(self.recent_messages)
        return messages

# Pattern 3: Vector memory (semantic search over past messages)
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import uuid

class VectorMemory:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = None
        self.docs = []

    def add(self, content: str, metadata: dict = None):
        doc = Document(
            page_content=content,
            metadata=metadata or {"id": str(uuid.uuid4())}
        )
        self.docs.append(doc)
        
        if self.vectorstore is None:
            self.vectorstore = FAISS.from_documents(self.docs, self.embeddings)
        else:
            self.vectorstore.add_documents([doc])

    def recall(self, query: str, k: int = 3) -> list[str]:
        if not self.vectorstore:
            return []
        docs = self.vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
```
