"""
Phase5_LangChain — Complete Practical
========================================
Topics:
  1. LCEL (LangChain Expression Language) chains
  2. ChatPromptTemplate
  3. Memory: ConversationBufferMemory, RunnableWithMessageHistory
  4. Custom tools with @tool decorator
  5. ReAct Agent
  6. Output parsers: PydanticOutputParser, StrOutputParser
  7. Callbacks for logging/tracing

Install: pip install langchain langchain-openai langchain-anthropic
Env: OPENAI_API_KEY or ANTHROPIC_API_KEY

Run: python 01_langchain_practical.py
"""

import os
from typing import Optional

MOCK_MODE = not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: LCEL Chains (LangChain Expression Language)
# INTERVIEW: | operator chains components (Runnable protocol)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: LCEL Chains")
print("=" * 60)

LCEL_CODE = '''\
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ── LCEL: pipe operator chains Runnables ──────────────────────
# INTERVIEW: Each component = Runnable (has .invoke(), .stream(), .batch())
# | operator = chain output of left → input of right

llm    = ChatOpenAI(model="gpt-4o-mini", temperature=0)
parser = StrOutputParser()

# Simple chain: prompt | llm | parser
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a Python expert."),
    ("human",  "Explain {concept} in one sentence."),
])

chain = prompt | llm | parser

# .invoke() = single call
result = chain.invoke({"concept": "generators"})
print(result)

# .stream() = token by token
for chunk in chain.stream({"concept": "decorators"}):
    print(chunk, end="", flush=True)

# .batch() = multiple inputs concurrently
results = chain.batch([
    {"concept": "closures"},
    {"concept": "metaclasses"},
    {"concept": "descriptors"},
])

# ── Parallel chains with RunnableParallel ──────────────────
from langchain_core.runnables import RunnableParallel

parallel = RunnableParallel(
    explanation = prompt | llm | parser,
    example     = ChatPromptTemplate.from_template(
        "Give a code example of {concept}"
    ) | llm | parser,
)
result = parallel.invoke({"concept": "generators"})
# result = {"explanation": "...", "example": "def gen():..."}

# ── Conditional routing ────────────────────────────────────
from langchain_core.runnables import RunnableLambda, RunnableBranch

route = RunnableBranch(
    (lambda x: "python" in x["topic"].lower(), python_chain),
    (lambda x: "js" in x["topic"].lower(),     js_chain),
    default_chain,  # fallback
)
'''

print("  Key LCEL concepts:")
lcel_concepts = {
    "| operator":           "Chain Runnables — output of left → input of right",
    ".invoke()":            "Single synchronous call",
    ".stream()":            "Token-by-token streaming",
    ".batch()":             "Multiple inputs concurrently",
    ".ainvoke()":           "Async version of invoke",
    "RunnableParallel":     "Run multiple chains in parallel, merge results",
    "RunnableLambda":       "Wrap any Python function as a Runnable",
    "RunnableBranch":       "Conditional routing based on input",
}
for k, v in lcel_concepts.items():
    print(f"  {k:<22}: {v}")

print("\n  Chain code example:")
print(LCEL_CODE[:400])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Memory
# INTERVIEW: Conversation memory management patterns
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Conversation Memory")
print("=" * 60)

MEMORY_CODE = '''\
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

llm    = ChatOpenAI(model="gpt-4o-mini")
store  = {}  # In-memory session store

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    # INTERVIEW: In production use Redis or DB for persistence
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder("history"),  # ← Injects conversation history
    ("human", "{input}"),
])

chain_with_memory = RunnableWithMessageHistory(
    prompt | llm,
    get_session_history,
    input_messages_key   = "input",
    history_messages_key = "history",
)

# Use with session_id
config = {"configurable": {"session_id": "user-123"}}
r1 = chain_with_memory.invoke({"input": "My name is Alice."}, config=config)
r2 = chain_with_memory.invoke({"input": "What's my name?"}, config=config)
# r2 will say "Alice" — memory persists across calls!

# ── Memory types ──────────────────────────────────────────
# Buffer:  Store ALL messages (grows unboundedly)
# Summary: Summarize old messages when too long
# Window:  Keep only last K messages
# Entity:  Track entities (people, places, things) mentioned

# ── Summary memory (for long conversations) ────────────────
from langchain.memory import ConversationSummaryBufferMemory

memory = ConversationSummaryBufferMemory(
    llm=llm,
    max_token_limit=1000,    # Summarize when exceeds 1000 tokens
    return_messages=True,
)
'''
print(MEMORY_CODE[:600])

MEMORY_TYPES = {
    "InMemoryChatMessageHistory": "Local dict — development only",
    "RedisChatMessageHistory":    "Redis-backed — production (pip install redis)",
    "DynamoDBChatMessageHistory": "AWS DynamoDB — serverless scale",
    "PostgresChatMessageHistory": "PostgreSQL — if you're already using it",
    "ConversationSummaryMemory":  "Summarizes old turns when too long",
    "ConversationWindowMemory":   "Keeps only last K turns",
}
print("\n  Memory backends:")
for k, v in MEMORY_TYPES.items():
    print(f"  {k:<35}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Custom Tools
# INTERVIEW: @tool decorator, StructuredTool for complex inputs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Custom Tools")
print("=" * 60)

TOOLS_CODE = '''\
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun
from pydantic import BaseModel, Field

# ── Simple @tool decorator ────────────────────────────────────
@tool
def get_current_date() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"

# ── Structured tool (complex input) ───────────────────────────
class SearchInput(BaseModel):
    query:  str   = Field(description="Search query")
    limit:  int   = Field(default=5, description="Max results")

@tool("search_users", args_schema=SearchInput)
def search_users(query: str, limit: int = 5) -> list[dict]:
    """Search users in the database by name or email."""
    # Real implementation would query DB
    return [{"id": 1, "name": f"Result for: {query}"}]

# ── Web search tools (built-in) ────────────────────────────────
search = DuckDuckGoSearchRun()
wiki   = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

all_tools = [get_current_date, calculate, search_users, search]

# Tool inspection:
print(get_current_date.name)           # "get_current_date"
print(get_current_date.description)    # From docstring
print(calculate.args_schema.schema())  # {"expression": {"type": "string"}}
'''
print(TOOLS_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: ReAct Agent
# INTERVIEW: LLM decides which tools to use + when
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: ReAct Agent")
print("=" * 60)

REACT_CODE = '''\
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

# Prebuilt ReAct prompt
prompt = hub.pull("hwchase17/react")   # pulls from LangChain Hub

agent = create_react_agent(
    llm    = ChatOpenAI(model="gpt-4o-mini"),
    tools  = [calculate, get_current_date, search],
    prompt = prompt,
)

executor = AgentExecutor(
    agent      = agent,
    tools      = all_tools,
    verbose    = True,     # shows thought process
    max_iterations = 10,   # prevent infinite loops
    handle_parsing_errors = True,  # recover from LLM format errors
)

# Run agent
result = executor.invoke({"input": "What is 1234 * 5678? Also what day is it today?"})
print(result["output"])

# INTERVIEW: ReAct format:
# Thought: I need to calculate 1234 * 5678
# Action: calculate
# Action Input: 1234 * 5678
# Observation: 7006652
# Thought: I have the answer. Now I need the date.
# Action: get_current_date
# ...
# Final Answer: 1234 * 5678 = 7,006,652. Today is 2024-01-15.
'''
print(REACT_CODE[:500])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Output Parsers
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Output Parsers")
print("=" * 60)

PARSERS_CODE = '''\
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain.output_parsers import PydanticOutputParser, CommaSeparatedListOutputParser

# ── PydanticOutputParser ───────────────────────────────────────
from pydantic import BaseModel

class CodeReview(BaseModel):
    issues:      list[str]
    suggestions: list[str]
    score:       int  # 1-10

parser  = PydanticOutputParser(pydantic_object=CodeReview)
prompt  = ChatPromptTemplate.from_template(
    "Review this code:\\n{code}\\n\\n{format_instructions}"
)
chain = prompt | llm | parser

result = chain.invoke({
    "code": "def foo(x): return x*x",
    "format_instructions": parser.get_format_instructions(),
})
print(type(result))   # <class 'CodeReview'>
print(result.score)   # 8

# ── JsonOutputParser (streaming-compatible) ────────────────────
json_chain = prompt | llm | JsonOutputParser()

# ── StrOutputParser (simplest) ─────────────────────────────────
str_chain = prompt | llm | StrOutputParser()
'''
print(PARSERS_CODE[:500])

print("\n" + "=" * 60)
print("LANGCHAIN INTERVIEW SUMMARY:")
print("  LCEL: prompt | llm | parser — composable pipelines with | operator")
print("  Memory: RunnableWithMessageHistory + session_id for multi-turn")
print("  Tools: @tool decorator, description = what LLM reads")
print("  ReAct: LLM reasons → picks tool → sees result → decides next action")
print("  Parsers: PydanticOutputParser for typed output from LLM")
print("=" * 60)
