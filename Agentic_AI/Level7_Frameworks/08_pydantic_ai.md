# PydanticAI — Type-Safe Agent Framework

## Quick Concepts
- **PydanticAI** = Pydantic team ka agent framework — FastAPI-like DX, type-safety first, structured outputs built-in
- **result_type** = Agent ka return type ek Pydantic model hota hai — LLM output automatically validate + parse hota hai
- **deps_type** = Dependency injection — RunContext ke through tools aur system prompts ko real data milta hai
- **@agent.tool** = Tool register karo — typed parameters, automatic schema generation
- **Model-agnostic** = OpenAI, Anthropic, Gemini, Groq, Ollama — ek hi API, provider swap easy
- **Key insight**: PydanticAI mein "type errors" compile time pe pakad lo, runtime surprises nahi

---

## Interview Questions & Answers

### Q1: PydanticAI kya hai? Dusre frameworks se alag kyun?
**Answer:**
```python
# pip install pydantic-ai

"""
PydanticAI = Pydantic team ne banaya agent framework.
Philosophy:
  1. Type-safety FIRST  — result_type se LLM output structured + validated milta hai
  2. FastAPI-like DX    — decorators, dependency injection, familiar pattern
  3. Structured output as first-class — baad ka koi conversion step nahi
  4. Model-agnostic     — provider swap karo bina code badla
  5. Production-ready   — logfire integration, streaming, message history

LangChain se alag:
  LangChain → LCEL chains, huge ecosystem, complex
  PydanticAI → lightweight, typed, FastAPI developer ke liye natural

CrewAI se alag:
  CrewAI → multi-agent roles/tasks, high-level abstraction
  PydanticAI → single agent, type-safe, low-level control

DSPy se alag:
  DSPy → prompt optimization, declarative
  PydanticAI → structured output, dependency injection, production use

Tumhara ALEX project connection:
  ALEX mein typed handoff karte the (TypedDict se agent switch)
  PydanticAI mein result_type=Pydantic model se
  yahi kaam automatic hota hai, validation free mein
"""

from pydantic import BaseModel
from pydantic_ai import Agent

# Simplest possible agent
agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant.",
)

result = agent.run_sync("What is 2 + 2?")
print(result.data)  # "4" (string by default)
print(result.usage())  # token usage
```

---

### Q2: result_type — structured output kaise kaam karta hai?
**Answer:**
```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# ===== STRUCTURED OUTPUT — result_type =====
# INTERVIEW: result_type define karo — LLM output automatically parse hoga

class MovieReview(BaseModel):
    title: str = Field(description="Movie title")
    rating: float = Field(ge=0, le=10, description="Rating out of 10")
    pros: list[str] = Field(description="Good things about the movie")
    cons: list[str] = Field(description="Bad things about the movie")
    summary: str = Field(description="One sentence summary")
    recommended: bool

# Agent ko result_type batao
movie_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=MovieReview,  # <-- yahi magic hai
    system_prompt="You are a film critic. Always give structured reviews.",
)

result = movie_agent.run_sync("Review the movie Inception")
review = result.data  # yeh MovieReview instance hai, dict nahi

print(type(review))           # <class 'MovieReview'>
print(review.title)           # "Inception"
print(review.rating)          # 8.5
print(review.pros)            # ["Stunning visuals", "Complex plot"]
print(review.recommended)     # True

# Validation automatic:
# Agar LLM rating = 15 de — Pydantic raise karega (ge=0, le=10 constraint)
# PydanticAI retry karega automatically

# ===== NESTED MODELS =====
class Address(BaseModel):
    street: str
    city: str
    country: str

class PersonInfo(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)
    address: Address
    skills: list[str]
    experience_years: int

person_agent = Agent(
    "anthropic:claude-haiku-4-5",
    result_type=PersonInfo,
    system_prompt="Extract person information from text.",
)

result = person_agent.run_sync(
    "John Doe, 30 years old, lives at 123 Main St, New York, USA. "
    "Skills: Python, FastAPI, Docker. 5 years experience."
)
person = result.data
print(f"{person.name}, {person.age} years, {person.address.city}")

# ===== UNION TYPES — conditional output =====
from typing import Union

class SuccessResponse(BaseModel):
    status: str = "success"
    data: dict

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    error_code: int

flexible_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Union[SuccessResponse, ErrorResponse],
    system_prompt="Process requests. Return error if invalid.",
)
```

---

### Q3: deps_type aur RunContext — dependency injection kaise kaam karta hai?
**Answer:**
```python
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

# ===== DEPENDENCY INJECTION =====
# INTERVIEW: deps_type = tool aur system prompts ko runtime data chahiye
#            RunContext = container jo deps inject karta hai

@dataclass
class DatabaseDeps:
    """Runtime dependencies — DB connection, user info, config"""
    user_id: str
    db_connection: str   # real use mein actual DB object hoga
    api_key: str
    user_role: str = "user"

class SearchResult(BaseModel):
    query: str
    results: list[str]
    total_count: int
    source: str

# deps_type se agent ko pata hai kaun deps expect karta hai
search_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=DatabaseDeps,       # <-- dependency type declare karo
    result_type=SearchResult,
    system_prompt="You are a search assistant.",
)

# ===== DYNAMIC SYSTEM PROMPT using deps =====
@search_agent.system_prompt
def dynamic_system_prompt(ctx: RunContext[DatabaseDeps]) -> str:
    """INTERVIEW: deps se dynamic system prompt — user-specific behavior"""
    role = ctx.deps.user_role
    user_id = ctx.deps.user_id
    
    base = f"You are a search assistant for user {user_id}."
    
    if role == "admin":
        return base + " Show all results including restricted ones."
    else:
        return base + " Show only public results."

# ===== TOOL using deps =====
@search_agent.tool
def search_database(ctx: RunContext[DatabaseDeps], query: str, limit: int = 10) -> list[str]:
    """
    INTERVIEW: @agent.tool decorator se tool register hota hai.
    ctx.deps se dependencies access karo.
    Return type se LLM ko pata hai kya milega.
    """
    # Real use mein: ctx.deps.db_connection se actual DB query
    user_id = ctx.deps.user_id
    db = ctx.deps.db_connection
    
    # Mock data — real mein async DB call hoga
    mock_results = [
        f"Result {i} for '{query}' (user: {user_id}, db: {db})"
        for i in range(1, min(limit + 1, 4))
    ]
    return mock_results

@search_agent.tool
def get_user_preferences(ctx: RunContext[DatabaseDeps]) -> dict:
    """Tool ko koi input nahi chahiye — sirf deps use karta hai"""
    return {
        "user_id": ctx.deps.user_id,
        "role": ctx.deps.user_role,
        "preferred_language": "en",
    }

# Run karo deps ke saath
deps = DatabaseDeps(
    user_id="user_42",
    db_connection="postgresql://prod-db:5432/main",
    api_key="secret",
    user_role="admin",
)

result = search_agent.run_sync(
    "Search for Python tutorials",
    deps=deps,    # <-- deps pass karo yahan
)
print(result.data.results)
```

---

### Q4: @agent.tool — tools define karna, schema auto-generation?
**Answer:**
```python
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from typing import Optional
import datetime

@dataclass
class AppDeps:
    weather_api_key: str
    user_location: str

class WeatherReport(BaseModel):
    location: str
    temperature_celsius: float
    condition: str
    humidity_percent: int
    advice: str

weather_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=AppDeps,
    result_type=WeatherReport,
    system_prompt="You are a weather assistant. Always use tools to get real data.",
)

# ===== TOOL VARIANTS =====

# Basic tool — simple function
@weather_agent.tool
def get_weather(ctx: RunContext[AppDeps], location: str) -> dict:
    """
    Get current weather for a location.
    
    Args:
        location: City name or coordinates
        
    Returns:
        Weather data dict
    """
    # Real mein: ctx.deps.weather_api_key se API call
    api_key = ctx.deps.weather_api_key
    return {
        "temp": 25.5,
        "condition": "Sunny",
        "humidity": 60,
        "location": location,
    }

# Tool with complex input
@weather_agent.tool
def get_forecast(
    ctx: RunContext[AppDeps],
    location: str,
    days: int = 3,
    unit: str = "celsius",
) -> list[dict]:
    """Get weather forecast for multiple days."""
    forecasts = []
    for i in range(days):
        date = datetime.date.today() + datetime.timedelta(days=i)
        forecasts.append({
            "date": str(date),
            "high": 28 + i,
            "low": 18 + i,
            "condition": "Partly cloudy",
        })
    return forecasts

# Tool without context (deps nahi chahiye)
@weather_agent.tool_plain
def convert_temperature(celsius: float) -> dict:
    """Convert Celsius to Fahrenheit and Kelvin."""
    return {
        "celsius": celsius,
        "fahrenheit": celsius * 9/5 + 32,
        "kelvin": celsius + 273.15,
    }

# INTERVIEW: Schema auto-generate — LLM ko tool description + params automatically milte hain
# Docstring = LLM ko batata hai tool kya karta hai
# Type hints = parameter types (LLM inka use karta hai)
# Default values = optional params
```

---

### Q5: System prompts — static aur dynamic?
**Answer:**
```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

@dataclass
class UserContext:
    username: str
    language: str
    subscription: str  # "free" or "premium"

agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=UserContext,
    # ===== STATIC SYSTEM PROMPT (string) =====
    # INTERVIEW: String diya toh har request mein same hoga
    system_prompt="You are a helpful coding assistant.",
)

# ===== DYNAMIC SYSTEM PROMPT (decorator) =====
# INTERVIEW: Decorator se multiple system prompts compose ho sakte hain
@agent.system_prompt
def add_user_context(ctx: RunContext[UserContext]) -> str:
    """Yeh runtime pe call hoga — deps access kar sako"""
    return f"""
User: {ctx.deps.username}
Preferred language: {ctx.deps.language}
Subscription: {ctx.deps.subscription}
{'Premium features available: advanced debugging, code generation' 
 if ctx.deps.subscription == 'premium' else 'Upgrade for premium features'}
"""

@agent.system_prompt
def add_date_context() -> str:
    """Deps ke bina bhi dynamic prompt add kar sako"""
    return f"Today's date: {datetime.date.today().isoformat()}"

# INTERVIEW: Multiple @agent.system_prompt decorators = sab append hote hain
# Order: constructor string → decorator functions (upar se niche)

# Static + dynamic combination:
# 1. "You are a helpful coding assistant."
# 2. "User: ashish\nPreferred language: Python\n..."
# 3. "Today's date: 2026-06-13"
```

---

### Q6: Model-agnostic support — providers switch karna?
**Answer:**
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.groq import GroqModel

from pydantic import BaseModel

class Summary(BaseModel):
    main_points: list[str]
    word_count: int
    sentiment: str

# ===== PROVIDER STRINGS (shorthand) =====
# INTERVIEW: "provider:model-id" format — sabse simple
agent_openai     = Agent("openai:gpt-4o-mini",            result_type=Summary)
agent_anthropic  = Agent("anthropic:claude-haiku-4-5",    result_type=Summary)
agent_groq       = Agent("groq:llama-3.1-8b-instant",     result_type=Summary)
agent_gemini     = Agent("google-gla:gemini-2.0-flash",   result_type=Summary)
agent_ollama     = Agent("ollama:llama3.2",               result_type=Summary)  # local

# ===== MODEL OBJECTS (more control) =====
# Custom base URL, headers, timeouts
custom_model = OpenAIModel(
    "gpt-4o-mini",
    base_url="https://api.custom-openai-endpoint.com/v1",
    api_key="your-key",
)
agent_custom = Agent(custom_model, result_type=Summary)

# Anthropic with custom settings
anthropic_model = AnthropicModel(
    "claude-haiku-4-5",
    # API key from ANTHROPIC_API_KEY env var automatically
)
agent_anthropic_detailed = Agent(
    anthropic_model,
    result_type=Summary,
    system_prompt="Summarize concisely.",
)

# ===== RUNTIME MODEL OVERRIDE =====
# INTERVIEW: Run time pe model badal sako
base_agent = Agent("openai:gpt-4o-mini", result_type=Summary)

# Production mein cheap model use karo
result_cheap = base_agent.run_sync(
    "Summarize AI trends",
    model="groq:llama-3.1-8b-instant",  # override
)

# Critical task mein expensive model
result_expensive = base_agent.run_sync(
    "Summarize the entire history of AI",
    model="anthropic:claude-opus-4-5",  # override
)

# COMPARISON TABLE:
"""
Provider      | String Format                    | Env Var
-----------   | -------------------------------- | --------------------
OpenAI        | openai:gpt-4o-mini               | OPENAI_API_KEY
Anthropic     | anthropic:claude-haiku-4-5       | ANTHROPIC_API_KEY
Groq          | groq:llama-3.1-8b-instant        | GROQ_API_KEY
Google        | google-gla:gemini-2.0-flash       | GEMINI_API_KEY
Ollama        | ollama:llama3.2                  | (local, no key)
Mistral       | mistral:mistral-small-latest     | MISTRAL_API_KEY
"""
```

---

### Q7: Message history — multi-turn conversation kaise rakho?
**Answer:**
```python
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant. Remember context from our conversation.",
)

# ===== MULTI-TURN CONVERSATION =====
# INTERVIEW: message_history param se previous messages pass karo

# Turn 1
result1 = agent.run_sync("My name is Ashish and I love Python.")
print(result1.data)

# Turn 2 — pehle ki history pass karo
result2 = agent.run_sync(
    "What is my name and what do I love?",
    message_history=result1.new_messages(),  # <-- yahi history hai
)
print(result2.data)  # "Your name is Ashish and you love Python."

# Turn 3 — sab previous turns ki history
result3 = agent.run_sync(
    "Recommend a Python framework for APIs.",
    message_history=result1.new_messages() + result2.new_messages(),
)
print(result3.data)

# ===== FULL HISTORY TRACK KARNA =====
all_messages: list[ModelMessage] = []

def chat_with_history(user_input: str) -> str:
    global all_messages
    
    result = agent.run_sync(
        user_input,
        message_history=all_messages,
    )
    
    # Naye messages add karo history mein
    all_messages.extend(result.new_messages())
    
    return result.data

# Multi-turn session
r1 = chat_with_history("I'm building a FastAPI app.")
r2 = chat_with_history("What database should I use?")
r3 = chat_with_history("How do I connect it to my app I mentioned?")

# all_messages mein poori conversation hai
print(f"Total messages in history: {len(all_messages)}")

# ===== SERIALIZATION (save/load history) =====
import json
from pydantic_ai.messages import ModelMessagesTypeAdapter

# Save
history_json = ModelMessagesTypeAdapter.dump_json(all_messages)
with open("chat_history.json", "wb") as f:
    f.write(history_json)

# Load
with open("chat_history.json", "rb") as f:
    loaded_history = ModelMessagesTypeAdapter.validate_json(f.read())
```

---

### Q8: Streaming — real-time response kaise karo?
**Answer:**
```python
import asyncio
from pydantic import BaseModel
from pydantic_ai import Agent

class ArticleOutline(BaseModel):
    title: str
    introduction: str
    sections: list[str]
    conclusion: str

agent = Agent(
    "openai:gpt-4o-mini",
    result_type=ArticleOutline,
    system_prompt="You write article outlines.",
)

# ===== TEXT STREAMING (async) =====
async def stream_text_example():
    """INTERVIEW: stream_text() se real-time output milta hai"""
    
    async with agent.run_stream("Write a story about AI.") as stream:
        async for text_chunk in stream.stream_text(delta=True):
            # delta=True → sirf naye characters milte hain
            print(text_chunk, end="", flush=True)
    
    print()  # newline at end
    final = await stream.get_data()  # final complete result
    print(f"Total tokens: {stream.usage().total_tokens}")

asyncio.run(stream_text_example())

# ===== STRUCTURED STREAMING =====
async def stream_structured_example():
    """
    INTERVIEW: Structured output ko bhi stream kar sako.
    Partial objects milte hain jaise LLM generate karta hai.
    """
    
    # String result ke saath stream
    text_agent = Agent("openai:gpt-4o-mini")
    
    async with text_agent.run_stream("Explain Python in 5 points.") as stream:
        async for message in stream.stream_text(delta=False):
            # delta=False → har call mein ab-tak-ka-poora text
            pass  # ya print karo
        
        result = await stream.get_data()
        print(result)  # complete string

asyncio.run(stream_structured_example())

# ===== SYNC EQUIVALENT =====
# Agar async nahi chahiye
result = agent.run_sync("Write article outline for Python decorators.")
outline = result.data  # complete structured output
print(outline.title)
print(outline.sections)
```

---

### Q9: Validation aur retries — error handling kaise kaam karta hai?
**Answer:**
```python
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior, ModelRetry

class StrictOutput(BaseModel):
    answer: str = Field(min_length=10, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    category: str
    
    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"technical", "business", "general", "sports"}
        if v.lower() not in allowed:
            raise ValueError(f"Category must be one of {allowed}, got: {v}")
        return v.lower()

# INTERVIEW: PydanticAI automatically retry karta hai agar validation fail ho
# Default: 1 retry, result_retries param se badha sako
agent = Agent(
    "openai:gpt-4o-mini",
    result_type=StrictOutput,
    result_retries=3,  # <-- validation fail ho toh 3 baar try karo
    system_prompt="Classify text into: technical, business, general, or sports.",
)

# ===== TOOL RETRY =====
from pydantic_ai import Agent, RunContext, ModelRetry

@dataclass
class Deps:
    max_results: int = 5

retrieval_agent = Agent("openai:gpt-4o-mini", deps_type=Deps)

@retrieval_agent.tool(retries=2)  # tool-level retries
def fetch_data(ctx: RunContext[Deps], url: str) -> str:
    """Fetch data from URL."""
    if not url.startswith("https://"):
        # ModelRetry raise karo — agent retry karega with error feedback
        raise ModelRetry(
            f"URL must start with https://. Got: {url}. "
            f"Please provide a valid HTTPS URL."
        )
    return f"Data from {url}"

# ===== ERROR HANDLING =====
try:
    result = agent.run_sync("This is about AI in software development")
    print(result.data)
except UnexpectedModelBehavior as e:
    print(f"Model behaved unexpectedly: {e}")
    # All retries fail ho gaye
```

---

### Q10: ALEX project se connection — typed handoff kaise?
**Answer:**
```python
"""
TUMHARA ALEX PROJECT:
  ALEX mein agents ke beech handoff TypedDict se hoti thi.
  Koi validation nahi tha runtime pe.
  
PydanticAI solution:
  result_type=HandoffDecision se automatic validation
  Ek agent ka output dusre ka input — fully typed
"""

from pydantic import BaseModel
from pydantic_ai import Agent
from typing import Literal

# ===== TYPED AGENT PIPELINE (ALEX-style) =====

class CustomerIntent(BaseModel):
    """Pehla agent: intent classify karta hai"""
    intent: Literal["billing", "technical", "general", "escalate"]
    confidence: float
    original_message: str
    extracted_info: dict

class BillingResponse(BaseModel):
    """Billing agent ka output"""
    action_taken: str
    amount_adjusted: float | None = None
    ticket_id: str
    next_steps: list[str]

class TechnicalResponse(BaseModel):
    """Technical agent ka output"""
    issue_identified: str
    steps_to_resolve: list[str]
    escalation_needed: bool
    ticket_id: str

# Agent 1: Intent classifier (ALEX ka Router Agent equivalent)
intent_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=CustomerIntent,
    system_prompt="""
    Classify customer message intent.
    intent options: billing, technical, general, escalate
    Extract any relevant info (amount, account, issue type).
    """,
)

# Agent 2: Billing specialist
billing_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=BillingResponse,
    system_prompt="You are a billing specialist. Resolve billing issues.",
)

# Agent 3: Technical support
technical_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=TechnicalResponse,
    system_prompt="You are a technical support specialist.",
)

async def process_customer_message(message: str):
    """
    ALEX-style multi-agent pipeline — typed handoff ke saath.
    LangGraph ki jagah simple function composition.
    """
    
    # Step 1: Intent classify karo (typed output)
    intent_result = await intent_agent.run(message)
    intent: CustomerIntent = intent_result.data  # type: CustomerIntent
    
    print(f"Intent: {intent.intent} (confidence: {intent.confidence:.2f})")
    
    # Step 2: Route based on intent
    if intent.intent == "billing":
        billing_result = await billing_agent.run(
            f"Customer issue: {intent.original_message}\n"
            f"Extracted info: {intent.extracted_info}"
        )
        response: BillingResponse = billing_result.data
        print(f"Billing resolved: {response.action_taken}")
        return response
    
    elif intent.intent == "technical":
        tech_result = await technical_agent.run(
            f"Technical issue: {intent.original_message}\n"
            f"Context: {intent.extracted_info}"
        )
        response: TechnicalResponse = tech_result.data
        if response.escalation_needed:
            print("Escalating to human agent...")
        return response
    
    else:
        # General query — direct answer
        general_agent = Agent(
            "openai:gpt-4o-mini",
            system_prompt="Answer general customer questions helpfully.",
        )
        result = await general_agent.run(message)
        return result.data

# COMPARISON: ALEX (LangGraph) vs PydanticAI approach
"""
ALEX/LangGraph approach:
  - State: TypedDict (runtime type unsafe)
  - Routing: conditional_edges function
  - Output: manually validated
  - Tools: via ToolNode
  
PydanticAI approach:
  - State: Pydantic models (fully validated)
  - Routing: regular Python if/else
  - Output: automatically validated + parsed
  - Tools: @agent.tool decorators
  
When to use PydanticAI over LangGraph:
  - Simpler pipelines (linear or basic branching)
  - Type safety critical hai
  - FastAPI/Pydantic already use karte ho
  - Production structured output needed
  
When to use LangGraph:
  - Complex cyclic graphs needed
  - Multiple parallel branches
  - Checkpointing/resume required
  - Existing LangChain ecosystem
"""
```

---

### Q11: PydanticAI vs LangChain vs CrewAI vs DSPy — kab kya?
**Answer:**
```
PydanticAI:
  Strength: Type-safe structured output, FastAPI-like DX, validation built-in
  Use karo jab:
    - Pydantic/FastAPI already use karte ho
    - Structured output extract karna hai (forms, reports, entities)
    - Production-grade validation chahiye
    - Simple agent with tools (not complex multi-agent graphs)
  Avoid karo jab:
    - Complex cyclic agent graphs chahiye (LangGraph better)
    - Large ecosystem integrations (LangChain better)
    - Team-based autonomous agents (CrewAI better)
    - Prompt auto-optimization (DSPy better)

LangChain/LangGraph:
  Strength: Huge ecosystem, LCEL, complex graphs, checkpointing
  Use karo jab: Complex stateful multi-agent, existing LangChain code
  
CrewAI:
  Strength: Role-based agents, autonomous task decomposition
  Use karo jab: Team simulation, autonomous multi-agent research
  
DSPy:
  Strength: Prompt optimization, declarative signatures
  Use karo jab: Labeled training data hai, prompt quality critical hai

DECISION FLOWCHART:
  Structured output chahiye?
    YES → PydanticAI (type-safe) ya Instructor (simple extraction)
    NO  → Continue...
  
  Complex multi-agent graph?
    YES → LangGraph (cyclic, checkpointing)
    NO  → Continue...
  
  Role-based autonomous team?
    YES → CrewAI
    NO  → Continue...
  
  Prompt optimization needed?
    YES → DSPy
    NO  → PydanticAI ya simple OpenAI SDK
```

---

## Core Architecture Summary

```
PydanticAI Architecture:
  
  Agent
  ├── model: "provider:model-id"
  ├── result_type: PydanticModel  ← structured output
  ├── deps_type: DataClass        ← dependency injection
  ├── system_prompt: str | fn     ← static + dynamic
  ├── result_retries: int         ← validation retry count
  │
  ├── @agent.tool                 ← tools (use deps, typed)
  ├── @agent.tool_plain           ← tools (no deps)
  ├── @agent.system_prompt        ← dynamic prompts
  │
  └── run_sync() / run() / run_stream()
      ├── message_history         ← multi-turn
      ├── deps                    ← inject dependencies
      └── model (override)        ← runtime model swap

Result Object:
  result.data         → parsed Pydantic model instance
  result.usage()      → token usage
  result.new_messages()  → messages for next turn
  result.all_messages()  → all messages in this run

Key Insight:
  Type annotations = LLM schema guidance + Python validation
  One definition, dual purpose (no manual JSON schema)
```
