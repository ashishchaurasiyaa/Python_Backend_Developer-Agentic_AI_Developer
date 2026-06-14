# 📚 LangChain Theory + Practical Guide

> **Complete theory aur practical files yahan organized hain**
> **Folder Structure:** Each topic has THEORY + working .py file

---

# 📋 LangChain Topics Index

## ✅ Practical Files (Working):
| # | File | Topic | Theory Section |
|---|---|---|---|
| 1 | `langchainintro.py` | Multi-provider intro | [Section 1](#section-1-models) |
| 2 | `multi_provider.py` | Provider comparison | [Section 1](#section-1-models) |
| 3 | `generative_with_open_ai.py` | Smart fallback | [Section 2](#section-2-production-patterns) |
| 4 | `first_agent.py` | Agent with tools (Old API) | [Section 3](#section-3-agents-old-api) |
| 5 | `tools.py` | Tools fundamentals | [Section 4](#section-4-tools) |

## ⏳ Practice Files to Build:
| # | File | Topic | Theory Section |
|---|---|---|---|
| 6 | `practice_01_modern_agent.py` | Modern V1 API | [Section 5](#section-5-modern-agents) |
| 7 | `practice_02_messages.py` | Message types | [Section 6](#section-6-messages) |
| 8 | `practice_03_structured.py` | Structured output | [Section 7](#section-7-structured-output) |
| 9 | `practice_04_memory.py` | Conversation memory | [Section 8](#section-8-memory) |
| 10 | `practice_05_streaming.py` | Real-time streaming | [Section 9](#section-9-streaming) |
| 11 | `practice_06_middleware.py` | Production middleware | [Section 10](#section-10-middleware) |

---

# 🌟 SECTION 1: MODELS

## Theory

### Core Concept:
```
Model = LLM ka instance (GPT, Claude, Gemini, Llama)
- Initialize karte ho
- invoke() karte ho
- Response milta hai
```

### Universal Pattern:
```python
from langchain.chat_models import init_chat_model

# ANY provider with same syntax
model = init_chat_model("provider:model-name")
```

### Provider Format:
- **Groq (FREE):** `"groq:llama-3.3-70b-versatile"`
- **Gemini (FREE):** `"google_genai:gemini-2.5-flash"`
- **OpenAI (Paid):** `"openai:gpt-4o-mini"`
- **Claude (Paid):** `"anthropic:claude-sonnet-4-6"`

### 4 Invocation Methods:

#### 1. invoke() - Single Call
```python
response = model.invoke("Hello")
print(response.content)
```

#### 2. stream() - Real-time
```python
for chunk in model.stream("Story"):
    print(chunk.content, end="", flush=True)
```

#### 3. batch() - Multiple Queries
```python
responses = model.batch(["Q1", "Q2", "Q3"])
```

#### 4. ainvoke() - Async
```python
response = await model.ainvoke("Hello")
```

### Parameters:
```python
model = init_chat_model(
    "groq:llama-3.3-70b-versatile",
    temperature=0.7,       # Creativity (0-1)
    max_tokens=500,        # Response length
    timeout=30,            # Wait time
    max_retries=6,         # Auto retries
)
```

## Practical Files
- ✅ `langchainintro.py` - Basic invoke
- ✅ `multi_provider.py` - Compare providers

---

# 🌟 SECTION 2: PRODUCTION PATTERNS

## Theory

### Smart Fallback Pattern:
```
Why? Production mein:
- API can be down
- Rate limits hit
- Credits exhausted

Solution: Try providers in priority order
- If one fails → try next
- Graceful degradation
```

### Provider Priority:
```
1. Anthropic (best quality)
2. OpenAI (industry standard)
3. Gemini (FREE alternative)
4. Groq (FREE fastest)
```

### Error Handling:
```python
for config in PROVIDERS:
    try:
        model = init_chat_model(...)
        model.invoke("test")  # Verify works
        return model
    except Exception as e:
        continue  # Try next
```

## Practical Files
- ✅ `generative_with_open_ai.py` - Smart fallback implementation

---

# 🌟 SECTION 3: AGENTS (OLD API)

## Theory

### Old Pattern (bind_tools):
```python
# Manual approach
llm = init_chat_model("...")
llm_with_tools = llm.bind_tools([tool1, tool2])

response = llm_with_tools.invoke(query)

# Manual tool execution
if response.tool_calls:
    for tc in response.tool_calls:
        result = tools_map[tc["name"]].invoke(tc["args"])
```

### When to Use:
- Learning fundamentals
- Custom tool execution logic
- Maximum control needed
- Understanding internals

### Limitations:
- 15+ lines of code
- Manual loops
- No ReAct pattern built-in
- More error-prone

## Practical Files
- ✅ `first_agent.py` - 4 tools with manual execution

---

# 🌟 SECTION 4: TOOLS

## Theory

### Tool Definition:
```
Tool = Python function jo agent use kar sakta hai
```

### Tool Anatomy:
```python
from langchain.tools import tool

@tool                              # Magic decorator
def my_tool(                       # Function name = tool name
    param: str,                    # Type hints (MANDATORY)
    optional: int = 10             # Default values
) -> str:                          # Return type
    """Clear docstring.            # LLM reads this!
    
    Args:
        param: Description
    
    Returns:
        Result description
    """
    return "result"                # Actual implementation
```

### 4 Critical Requirements:

#### 1. @tool Decorator
```python
@tool  # Without this, function won't be a tool
```

#### 2. Type Hints (MANDATORY!)
```python
# ❌ Wrong - LLM can't understand
def search(query, limit=10): ...

# ✅ Right
def search(query: str, limit: int = 10) -> str: ...
```

#### 3. Clear Docstring
```python
# ❌ Bad
"""Search"""

# ✅ Good
"""Search company database for employees matching the query."""
```

#### 4. snake_case Naming
```python
# ❌ Wrong: GetUserInfo
# ✅ Right: get_user_info
```

### Tool Patterns:

#### Pattern 1: Simple
```python
@tool
def calculator(expression: str) -> str:
    """Calculate math."""
    return str(eval(expression))
```

#### Pattern 2: With Default
```python
@tool
def search(query: str, limit: int = 10) -> str:
    """Search with optional limit."""
```

#### Pattern 3: Custom Name
```python
@tool("web_search", description="Search web")
def search(query: str) -> str:
    ...
```

#### Pattern 4: Pydantic (Complex)
```python
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    city: str = Field(description="City name")

@tool(args_schema=WeatherInput)
def get_weather(city: str) -> str:
    ...
```

### Tool Execution:
```python
# Standalone test
result = my_tool.invoke({"param": "value"})

# ❌ Wrong: my_tool("value")
# ✅ Right: my_tool.invoke({"param": "value"})
```

## Practical Files
- ✅ `tools.py` - get_weather + calculator tools

---

# 🌟 SECTION 5: MODERN AGENTS (V1 API)

## Theory

### Modern Pattern (create_agent):
```python
from langchain.agents import create_agent

# 5 lines = Complete agent!
agent = create_agent(
    model="groq:llama-3.3-70b-versatile",
    tools=[calculator],
    system_prompt="You are helpful."
)

result = agent.invoke({
    "messages": [("user", "What is 25 * 4?")]
})
```

### What create_agent Does Automatically:
- ✅ Tool execution loop
- ✅ ReAct pattern
- ✅ Multi-step reasoning
- ✅ Error handling
- ✅ Production-ready

### All Parameters:
```python
agent = create_agent(
    model="provider:model",         # Required
    tools=[tool1, tool2],            # Required
    system_prompt="...",             # Optional
    response_format=PydanticModel,   # Optional
    name="agent_name",               # Optional
    checkpointer=InMemorySaver(),    # Optional
    middleware=[...]                 # Optional
)
```

### Old vs New Comparison:

| Aspect | Old (bind_tools) | New (create_agent) |
|---|---|---|
| Code lines | 15+ | 5 |
| Tool execution | Manual | Auto |
| ReAct | Manual | Built-in |
| Multi-step | Manual loop | Automatic |
| Production | Need setup | Ready |

### When to Use:
- ✅ All new agents (always!)
- ✅ Production code
- ✅ Multi-step tasks
- ✅ Standard workflows

## Practical File to Build:
**`practice_01_modern_agent.py`** - Migrate first_agent.py to V1 API

---

# 🌟 SECTION 6: MESSAGES

## Theory

### 3 Message Types:

#### 1. SystemMessage (AI Behavior)
```python
SystemMessage(content="You are a Python expert. Reply in Hindi.")
```
**Use for:**
- Role definition
- Personality
- Constraints
- Expertise level

#### 2. HumanMessage (User Input)
```python
HumanMessage(content="What is async/await?")
```
**Use for:**
- User's actual question

#### 3. AIMessage (AI Response)
```python
AIMessage(content="Async/await is...")
```
**Use for:**
- Previous AI responses (memory)
- Multi-turn context

### Conversation Pattern:
```python
messages = [
    SystemMessage(content="You are helpful"),
    HumanMessage(content="Hello"),
    AIMessage(content="Hi! How can I help?"),
    HumanMessage(content="Tell me about Python"),
]

response = model.invoke(messages)
# AI sees full context!
```

### Multi-turn Conversation:
```python
conversation = [SystemMessage(content="You are helpful")]

def chat(user_msg):
    conversation.append(HumanMessage(content=user_msg))
    response = model.invoke(conversation)
    conversation.append(AIMessage(content=response.content))
    return response.content

chat("Mera naam Ashish hai")  # AI knows
chat("Mera naam kya hai?")     # AI: "Aapka naam Ashish hai"
```

## Practical File to Build:
**`practice_02_messages.py`** - System/Human/AI conversation

---

# 🌟 SECTION 7: STRUCTURED OUTPUT

## Theory

### Problem:
```
LLM returns text strings
Aapko typed data chahiye (dict, objects)
Parsing manually painful
```

### Solution: Pydantic Schema
```python
from pydantic import BaseModel, Field

class PersonInfo(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age")
    skills: list[str] = Field(description="Top skills")
```

### Two Ways:

#### Way 1: with_structured_output
```python
model = init_chat_model("groq:llama-3.3-70b-versatile")
structured_model = model.with_structured_output(PersonInfo)

result = structured_model.invoke("Tell me about APJ Abdul Kalam")
# result is PersonInfo object!
print(result.name)
print(result.skills)
```

#### Way 2: create_agent with response_format
```python
agent = create_agent(
    "groq:llama-3.3-70b-versatile",
    tools=[],
    response_format=PersonInfo  # Forces structured output
)

result = agent.invoke({"messages": [...]})
# Returns PersonInfo object
```

### Use Cases:
- Database insertion
- API responses
- Form parsing
- Data extraction

## Practical File to Build:
**`practice_03_structured.py`** - Pydantic models + extraction

---

# 🌟 SECTION 8: MEMORY

## Theory

### Problem:
```
Default: AI doesn't remember
Each invoke() is independent
"Mera naam Ashish" → AI forgets next time
```

### Solution: Checkpointer
```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model="...",
    tools=[],
    checkpointer=InMemorySaver()  # ← Adds memory
)
```

### Thread-based Memory:
```python
from uuid import uuid4

# Unique thread per conversation
thread_id = str(uuid4())
config = {"configurable": {"thread_id": thread_id}}

# Conversation 1
agent.invoke(
    {"messages": [("user", "I'm Ashish")]},
    config=config
)

# Conversation 2 - REMEMBERS!
agent.invoke(
    {"messages": [("user", "What's my name?")]},
    config=config
)
# AI: "Your name is Ashish"
```

### Memory Types:

#### 1. InMemorySaver (Development)
```python
checkpointer = InMemorySaver()
# Lost on restart
```

#### 2. SQLite (Local)
```python
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("./memory.db")
# Persistent local
```

#### 3. PostgreSQL (Production)
```python
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
# Production-grade
```

## Practical File to Build:
**`practice_04_memory.py`** - Persistent chat with memory

---

# 🌟 SECTION 9: STREAMING

## Theory

### Why Streaming?
```
Normal: Wait for full response
Streaming: Word-by-word (like ChatGPT)
- Better UX
- Faster perceived response
```

### Model Streaming:
```python
for chunk in model.stream("Tell me a story"):
    print(chunk.content, end="", flush=True)
```

### Agent Streaming:
```python
agent = create_agent("...", tools=[])

for chunk in agent.stream(
    {"messages": [("user", "Hello")]},
    stream_mode="values"
):
    latest = chunk["messages"][-1]
    print(latest.content)
```

### Stream Modes:

#### Mode 1: "values" (Full state)
```python
stream_mode="values"
# Returns: Complete state at each step
```

#### Mode 2: "updates" (Changes only)
```python
stream_mode="updates"
# Returns: Only what changed
```

#### Mode 3: "messages" (Word-by-word)
```python
stream_mode="messages"
# Returns: Individual tokens
```

## Practical File to Build:
**`practice_05_streaming.py`** - Real-time output

---

# 🌟 SECTION 10: MIDDLEWARE

## Theory

### What is Middleware?
```
Middleware = Cross-cutting concerns
Add functionality WITHOUT changing core code
Like Django/Express middleware
```

### 6 Categories (Official):

#### 1. Execution Environment
```python
# Filesystem, code execution
# Used in specific cases
```

#### 2. Context Management
```python
from langchain.agents.middleware import SummarizationMiddleware

# Auto-summarize long conversations
agent = create_agent(
    model="...",
    middleware=[SummarizationMiddleware(max_tokens=2000)]
)
```

#### 3. Planning & Delegation
```python
from langchain.agents.middleware import TodoListMiddleware

# Break tasks into steps
middleware=[TodoListMiddleware()]
```

#### 4. Fault Tolerance
```python
from langchain.agents.middleware import ToolRetryMiddleware

# Auto-retry failed tools
middleware=[ToolRetryMiddleware(max_retries=3)]
```

#### 5. Guardrails (Security)
```python
from langchain.agents.middleware import PIIMiddleware

# Detect & redact emails, SSNs, etc.
middleware=[PIIMiddleware()]
```

#### 6. Human-in-the-Loop
```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

# Pause for approval on destructive actions
middleware=[HumanInTheLoopMiddleware()]
```

### Custom Middleware:
```python
from langchain.agents.middleware import wrap_tool_call

@wrap_tool_call
def custom_logger(request, handler):
    print(f"Tool: {request.tool_call['name']}")
    return handler(request)

agent = create_agent(
    model="...",
    middleware=[custom_logger]
)
```

## Practical File to Build:
**`practice_06_middleware.py`** - Production patterns

---

# 🎯 LangChain Mastery Checklist

## After Building All Files:
```
Theory + Practical Coverage:

[x] Section 1: Models (✅ langchainintro.py + multi_provider.py)
[x] Section 2: Production (✅ generative_with_open_ai.py)
[x] Section 3: Old API (✅ first_agent.py)
[x] Section 4: Tools (✅ tools.py)
[ ] Section 5: Modern API (⏳ practice_01_modern_agent.py)
[ ] Section 6: Messages (⏳ practice_02_messages.py)
[ ] Section 7: Structured (⏳ practice_03_structured.py)
[ ] Section 8: Memory (⏳ practice_04_memory.py)
[ ] Section 9: Streaming (⏳ practice_05_streaming.py)
[ ] Section 10: Middleware (⏳ practice_06_middleware.py)
```

---

# 🏆 Complete LangChain Folder Structure (Goal)

```
generativeai/langchain/
├── 📚 THEORY.md                       (THIS FILE - All theory)
├── langchainintro.py                  ✅ Section 1
├── multi_provider.py                  ✅ Section 1
├── generative_with_open_ai.py         ✅ Section 2
├── first_agent.py                     ✅ Section 3 (Old API)
├── tools.py                           ✅ Section 4
├── practice_01_modern_agent.py        ⏳ Section 5
├── practice_02_messages.py            ⏳ Section 6
├── practice_03_structured.py          ⏳ Section 7
├── practice_04_memory.py              ⏳ Section 8
├── practice_05_streaming.py           ⏳ Section 9
└── practice_06_middleware.py          ⏳ Section 10
```

---

# 💡 How to Use This File

## Strategy 1: Theory + Code Together
```
1. Read theory section
2. Look at corresponding .py file
3. Run the code
4. Modify and experiment
```

## Strategy 2: Topic-by-Topic Learning
```
Day 1: Section 1 + 4 (Models + Tools)
Day 2: Section 5 + 6 (Modern Agent + Messages)
Day 3: Section 7 + 8 (Structured + Memory)
Day 4: Section 9 + 10 (Streaming + Middleware)
```

## Strategy 3: Quick Reference
```
Stuck somewhere?
→ Open THEORY.md
→ Search topic
→ Re-read concept
→ Check practical file
```

---

*All theory + practical in one place = Master LangChain easily!*
