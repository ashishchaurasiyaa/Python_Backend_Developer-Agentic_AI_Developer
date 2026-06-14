"""
PydanticAI — Type-Safe Agent Framework (Practical Lab)
=======================================================
KYA SEEKHENGE:
  1. PydanticAI concepts walkthrough (mock + real code)
  2. Agent definition with result_type (Pydantic model)
  3. Dependency injection (deps_type + RunContext)
  4. @agent.tool tools — typed, schema auto-generated
  5. Static + dynamic system prompts
  6. Model-agnostic provider support
  7. Message history (multi-turn conversation)
  8. Validation + retries
  9. Typed multi-agent pipeline (ALEX-style handoff)
  10. Comparison: PydanticAI vs LangChain/CrewAI/DSPy

KAISE CHALANA:
  # Install karo (optional — graceful fallback hai)
  uv add pydantic-ai

  # Real LLM se chalana:
  export OPENAI_API_KEY="sk-..."
  uv run python 08_pydantic_ai_practical.py

  # Bina key ke bhi chalega (mock mode):
  uv run python 08_pydantic_ai_practical.py

PREREQS:
  Level5 RAG (LangChain chain basics) — similar tool/chain pattern
  Level7/02 LangGraph (ALEX project) — typed handoff comparison
  Level7/05 CrewAI — agent role comparison
  Level7/06 DSPy — declarative vs type-safe contrast
"""

import os
import sys
import json
from typing import Optional, Literal, Union
from dataclasses import dataclass
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# GRACEFUL IMPORT — PydanticAI installed nahi ho toh bhi EXIT 0
# ─────────────────────────────────────────────────────────────────────────────
try:
    from pydantic_ai import Agent, RunContext
    from pydantic_ai.exceptions import UnexpectedModelBehavior, UserError
    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    PYDANTIC_AI_AVAILABLE = False
    # Stub classes — real code structure dikhate hain bina crash ke
    class Agent:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
    class RunContext:  # type: ignore[no-redef]
        pass

# ─────────────────────────────────────────────────────────────────────────────
# API KEY CHECK — graceful fallback
# ─────────────────────────────────────────────────────────────────────────────
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_KEY      = os.getenv("GROQ_API_KEY", "")

LIVE_MODE = PYDANTIC_AI_AVAILABLE and bool(OPENAI_KEY or ANTHROPIC_KEY or GROQ_KEY)

def get_model() -> str:
    """Available API key ke basis pe model choose karo."""
    if OPENAI_KEY:
        return "openai:gpt-4o-mini"
    if ANTHROPIC_KEY:
        return "anthropic:claude-haiku-4-5"
    if GROQ_KEY:
        return "groq:llama-3.1-8b-instant"
    return "openai:gpt-4o-mini"  # placeholder

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("PYDANTIC AI — TYPE-SAFE AGENT FRAMEWORK (Practical Lab)")
print("=" * 65)

if not PYDANTIC_AI_AVAILABLE:
    print("\n[!] pydantic-ai NOT installed.")
    print("    Showing code structure + concepts (no LLM calls).")
    print("    Install: uv add pydantic-ai\n")
elif not LIVE_MODE:
    print("\n[!] pydantic-ai installed but no API key found.")
    print("    Showing code structure + running mock demonstrations.")
    print("    Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GROQ_API_KEY for live mode.\n")
else:
    print(f"\n[OK] LIVE MODE — using model: {get_model()}\n")


# =============================================================================
# SECTION 0: PydanticAI Philosophy — quick concept map
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 0: PydanticAI Philosophy")
print("=" * 65)

PHILOSOPHY = {
    "Type-safety first":   "result_type=PydanticModel → LLM output auto-validated",
    "FastAPI-like DX":     "decorators, dependency injection — familiar pattern",
    "Structured outputs":  "Pydantic models ARE the output spec — no post-processing",
    "Model-agnostic":      "'provider:model-id' string — swap providers easily",
    "Deps injection":      "deps_type + RunContext → tools get runtime data cleanly",
    "Streaming":           "run_stream() + stream_text() — real-time output",
    "Message history":     "result.new_messages() → multi-turn context preserved",
    "Retries":             "result_retries + ModelRetry → auto-retry on bad output",
}

for concept, desc in PHILOSOPHY.items():
    print(f"  {concept:<22}: {desc}")

print("\n  Key PydanticAI insight:")
print("  Type annotations = LLM schema guidance + Python runtime validation")
print("  Define once → get JSON schema for LLM AND Pydantic validation free")


# =============================================================================
# SECTION 1: Basic Agent + result_type
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 1: Agent Definition + result_type (Structured Output)")
print("=" * 65)

AGENT_BASICS_CODE = '''\
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# ── Pydantic model = output specification ─────────────────────
# INTERVIEW: result_type se LLM output auto-parsed + validated hota hai
class MovieReview(BaseModel):
    title: str
    rating: float = Field(ge=0, le=10, description="Rating out of 10")
    pros: list[str]
    cons: list[str]
    summary: str
    recommended: bool

# ── Agent create karo ─────────────────────────────────────────
agent = Agent(
    "openai:gpt-4o-mini",   # provider:model-id format
    result_type=MovieReview, # <-- structured output ka type
    system_prompt="You are a film critic. Give structured reviews.",
)

# ── Run (sync) ────────────────────────────────────────────────
result = agent.run_sync("Review the movie Inception")
review = result.data          # yeh MovieReview instance hai

print(type(review))           # <class \'__main__.MovieReview\'>
print(review.title)           # "Inception"
print(review.rating)          # 8.5
print(review.pros)            # ["Stunning visuals", "Complex plot"]
print(review.recommended)     # True
print(result.usage())         # token usage

# Automatic validation:
# rating=15 diya LLM ne → Pydantic raise ValueError (ge=0, le=10)
# PydanticAI retry karega with error feedback (result_retries times)
'''

print(AGENT_BASICS_CODE)

# ── Pydantic models define karo (actually usable) ─────────────
class MovieReview(BaseModel):
    title: str
    rating: float = Field(ge=0.0, le=10.0, description="Rating out of 10")
    pros: list[str]
    cons: list[str]
    summary: str
    recommended: bool

class ExtractedEntity(BaseModel):
    name: str
    entity_type: Literal["person", "organization", "location", "product", "other"]
    confidence: float = Field(ge=0.0, le=1.0)
    context: str

class DocumentAnalysis(BaseModel):
    entities: list[ExtractedEntity]
    main_topic: str
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    key_facts: list[str]
    word_count_estimate: int

print("  [Demo] Pydantic models defined:")
print(f"  MovieReview fields: {list(MovieReview.model_fields.keys())}")
print(f"  DocumentAnalysis fields: {list(DocumentAnalysis.model_fields.keys())}")
print(f"  ExtractedEntity.entity_type constraint: Literal['person','organization','location','product','other']")

# Live demo agar possible ho
if LIVE_MODE:
    print("\n  [LIVE] Running basic agent with result_type...")
    try:
        basic_agent = Agent(
            get_model(),
            result_type=DocumentAnalysis,
            system_prompt="Extract entities and analyze the document.",
        )
        result = basic_agent.run_sync(
            "Apple Inc. announced that CEO Tim Cook will present at the "
            "WWDC conference in Cupertino, California next week."
        )
        doc = result.data
        print(f"  Main topic: {doc.main_topic}")
        print(f"  Sentiment: {doc.sentiment}")
        print(f"  Entities found: {len(doc.entities)}")
        for ent in doc.entities:
            print(f"    - {ent.name} ({ent.entity_type}) conf={ent.confidence:.2f}")
        print(f"  Key facts: {doc.key_facts[:2]}")
        print(f"  Tokens used: {result.usage()}")
    except Exception as e:
        print(f"  [!] Live call failed: {e}")


# =============================================================================
# SECTION 2: Dependency Injection — deps_type + RunContext
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 2: Dependency Injection (deps_type + RunContext)")
print("=" * 65)

DEPS_CODE = '''\
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext

# ── Dependency container (dataclass ya koi bhi class) ─────────
@dataclass
class AppDeps:
    """Runtime dependencies — DB, user info, config"""
    user_id: str
    db_url: str
    user_role: str = "user"

class SearchResult(BaseModel):
    query: str
    results: list[str]
    total: int

# ── Agent with deps_type ──────────────────────────────────────
search_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=AppDeps,         # <-- declare karo
    result_type=SearchResult,
    system_prompt="You are a search assistant.",
)

# ── Dynamic system prompt — deps access karo ─────────────────
@search_agent.system_prompt
def add_user_context(ctx: RunContext[AppDeps]) -> str:
    # INTERVIEW: Runtime pe call hota hai — per-request customization
    role = ctx.deps.user_role
    uid  = ctx.deps.user_id
    if role == "admin":
        return f"User {uid} is an ADMIN. Show all results."
    return f"User {uid} is a regular user. Show public results only."

# ── Tool — deps access karo ──────────────────────────────────
@search_agent.tool
def search_database(ctx: RunContext[AppDeps], query: str, limit: int = 5) -> list[str]:
    """Search database for given query."""
    # ctx.deps se real DB connection, user_id etc. milta hai
    db  = ctx.deps.db_url
    uid = ctx.deps.user_id
    # Real mein: DB query — yahan mock
    return [f"Result {i} for \'{query}\' (uid={uid})" for i in range(1, limit+1)]

# ── Run with deps ─────────────────────────────────────────────
deps = AppDeps(
    user_id  = "user_42",
    db_url   = "postgresql://prod:5432/main",
    user_role= "admin",
)
result = search_agent.run_sync("Search for Python tutorials", deps=deps)
print(result.data.results)
'''

print(DEPS_CODE)

# Actual demo with mock
@dataclass
class AppDeps:
    user_id: str
    db_url: str
    user_role: str = "user"

print("  [Demo] AppDeps dataclass:")
demo_deps = AppDeps(user_id="user_42", db_url="postgresql://prod:5432/main", user_role="admin")
print(f"    user_id={demo_deps.user_id}, role={demo_deps.user_role}")
print("  RunContext[AppDeps].deps gives typed access inside tools/system_prompt")
print("  INTERVIEW: deps_type = type declaration; actual deps = run_sync(..., deps=obj)")

if LIVE_MODE:
    print("\n  [LIVE] Testing dependency injection...")
    try:
        @dataclass
        class LiveDeps:
            username: str
            language: str

        class LangAnswer(BaseModel):
            language: str
            message: str
            tips: list[str]

        lang_agent = Agent(
            get_model(),
            deps_type=LiveDeps,
            result_type=LangAnswer,
        )

        @lang_agent.system_prompt
        def lang_prompt(ctx: RunContext[LiveDeps]) -> str:
            return (
                f"You are helping {ctx.deps.username}. "
                f"They prefer: {ctx.deps.language}."
            )

        @lang_agent.tool
        def get_user_lang(ctx: RunContext[LiveDeps]) -> str:
            """Return the user's preferred programming language."""
            return ctx.deps.language

        deps_live = LiveDeps(username="Ashish", language="Python")
        res = lang_agent.run_sync("What's my preferred language and give tips?", deps=deps_live)
        print(f"  Language: {res.data.language}")
        print(f"  Message: {res.data.message[:80]}...")
        print(f"  Tips count: {len(res.data.tips)}")
    except Exception as e:
        print(f"  [!] Live deps call failed: {e}")


# =============================================================================
# SECTION 3: @agent.tool — typed tools, schema auto-generation
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 3: @agent.tool — Tools (Typed + Auto Schema)")
print("=" * 65)

TOOL_CODE = '''\
import datetime
from pydantic_ai import Agent, RunContext

@dataclass
class ToolDeps:
    api_key: str
    user_location: str

class WeatherReport(BaseModel):
    location: str
    temp_celsius: float
    condition: str
    advice: str

agent = Agent("openai:gpt-4o-mini", deps_type=ToolDeps, result_type=WeatherReport)

# ── @agent.tool — RunContext + typed params ───────────────────
@agent.tool
def get_weather(ctx: RunContext[ToolDeps], location: str) -> dict:
    """
    Get current weather for a location.

    Docstring = LLM ko tool description milti hai
    Type hints = parameter schema auto-generated
    """
    # ctx.deps.api_key se real API call karo
    return {"temp": 25.5, "condition": "Sunny", "humidity": 60}

@agent.tool
def get_forecast(
    ctx: RunContext[ToolDeps],
    location: str,
    days: int = 3,
) -> list[dict]:
    """Get weather forecast for multiple days."""
    today = datetime.date.today()
    return [
        {"date": str(today + datetime.timedelta(days=i)), "high": 28+i, "low": 18+i}
        for i in range(days)
    ]

# ── @agent.tool_plain — deps nahi chahiye ────────────────────
@agent.tool_plain
def convert_celsius_to_fahrenheit(celsius: float) -> float:
    """Convert temperature from Celsius to Fahrenheit."""
    return celsius * 9/5 + 32

# INTERVIEW: Schema auto-generation:
# get_weather → {"name": "get_weather", "params": {"location": "string"}}
# get_forecast → {"name": "get_forecast", "params": {"location": str, "days": int (default=3)}}
# Docstrings = LLM ko tool ka purpose samjhata hai
'''

print(TOOL_CODE)

# Demonstrate tool schema concept with pure Python
def demo_tool_schema():
    """Tool schema ko manually demonstrate karo."""
    import inspect

    def get_weather(location: str, units: str = "celsius") -> dict:
        """Get current weather for a location. Units can be celsius or fahrenheit."""
        pass

    sig = inspect.signature(get_weather)
    doc = inspect.getdoc(get_weather)

    schema = {
        "name": get_weather.__name__,
        "description": doc,
        "parameters": {}
    }
    for pname, param in sig.parameters.items():
        ptype = param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation)
        has_default = param.default is not inspect.Parameter.empty
        schema["parameters"][pname] = {
            "type": ptype,
            "required": not has_default,
            "default": param.default if has_default else None,
        }

    print("  [Demo] Tool schema auto-generation example:")
    print(f"    Function: {schema['name']}")
    print(f"    Description: {schema['description']}")
    print(f"    Parameters: {json.dumps(schema['parameters'], indent=6, default=str)}")

demo_tool_schema()


# =============================================================================
# SECTION 4: Static + Dynamic System Prompts
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 4: System Prompts — Static + Dynamic")
print("=" * 65)

SYSTEM_PROMPT_CODE = '''\
from pydantic_ai import Agent, RunContext
import datetime

@dataclass
class UserCtx:
    username: str
    language: str
    subscription: str

agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=UserCtx,
    # ── Static system prompt ──────────────────────────────────
    # INTERVIEW: Yeh har request mein same rahega
    system_prompt="You are a helpful coding assistant.",
)

# ── Dynamic system prompt (decorator) ────────────────────────
@agent.system_prompt
def add_user_info(ctx: RunContext[UserCtx]) -> str:
    """INTERVIEW: Per-request dynamic prompt — deps se user-specific"""
    premium = ctx.deps.subscription == "premium"
    return (
        f"User: {ctx.deps.username} | Language pref: {ctx.deps.language}\\n"
        + ("Premium: advanced features enabled." if premium
           else "Free tier: basic features only.")
    )

@agent.system_prompt
def add_date() -> str:
    """Deps ke bina dynamic context — date inject karo"""
    return f"Current date: {datetime.date.today().isoformat()}"

# Prompts combine hote hain (is order mein):
# 1. "You are a helpful coding assistant."    (constructor)
# 2. "User: Ashish | Language pref: Python\\n..." (first decorator)
# 3. "Current date: 2026-06-13"               (second decorator)
# Total = concatenated — LLM ko sab milta hai
'''

print(SYSTEM_PROMPT_CODE)
print("  Key points:")
print("  1. Constructor string = base static prompt")
print("  2. @agent.system_prompt = additional prompts append hote hain")
print("  3. Multiple decorators = sab append hote hain (order: top to bottom)")
print("  4. Deps access: (ctx: RunContext[DepsType]) -> str")
print("  5. No deps needed: () -> str  or  no args at all")


# =============================================================================
# SECTION 5: Model-Agnostic Provider Support
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 5: Model-Agnostic Provider Support")
print("=" * 65)

PROVIDERS_CODE = '''\
from pydantic_ai import Agent
from pydantic_ai.models.openai    import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.groq      import GroqModel

# ── Provider string format (sabse simple) ────────────────────
# INTERVIEW: "provider:model-id" — provider swap = 1 line change
agent_openai    = Agent("openai:gpt-4o-mini")
agent_anthropic = Agent("anthropic:claude-haiku-4-5")
agent_groq      = Agent("groq:llama-3.1-8b-instant")
agent_gemini    = Agent("google-gla:gemini-2.0-flash")
agent_ollama    = Agent("ollama:llama3.2")         # local model

# ── Model objects (more control) ─────────────────────────────
custom_openai = OpenAIModel(
    "gpt-4o-mini",
    base_url = "https://api.custom-endpoint.com/v1",
    api_key  = "custom-key",
)
agent_custom = Agent(custom_openai)

# ── Runtime model override ────────────────────────────────────
# INTERVIEW: Run time pe model badal sako (A/B testing, cost optimization)
base_agent = Agent("openai:gpt-4o-mini")

# Cheap model for quick tasks
result_fast = base_agent.run_sync(
    "Quick question",
    model="groq:llama-3.1-8b-instant",   # override
)

# Expensive model for critical tasks
result_best = base_agent.run_sync(
    "Complex analysis",
    model="anthropic:claude-opus-4-5",    # override
)
'''

print(PROVIDERS_CODE)

PROVIDERS = [
    ("OpenAI",    "openai:gpt-4o-mini",             "OPENAI_API_KEY"),
    ("Anthropic", "anthropic:claude-haiku-4-5",      "ANTHROPIC_API_KEY"),
    ("Groq",      "groq:llama-3.1-8b-instant",       "GROQ_API_KEY"),
    ("Google",    "google-gla:gemini-2.0-flash",     "GEMINI_API_KEY"),
    ("Ollama",    "ollama:llama3.2",                  "(local, no key)"),
    ("Mistral",   "mistral:mistral-small-latest",    "MISTRAL_API_KEY"),
    ("Azure",     "azure:gpt-4o-mini",               "AZURE_OPENAI_*"),
]

print("\n  Provider support table:")
print(f"  {'Provider':<12} {'String Format':<40} {'Env Var'}")
print(f"  {'-'*12} {'-'*40} {'-'*20}")
for name, fmt, env in PROVIDERS:
    print(f"  {name:<12} {fmt:<40} {env}")


# =============================================================================
# SECTION 6: Message History — Multi-Turn Conversation
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 6: Message History (Multi-Turn Conversation)")
print("=" * 65)

HISTORY_CODE = '''\
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are helpful. Remember context from our conversation.",
)

# ── Turn 1 ────────────────────────────────────────────────────
result1 = agent.run_sync("My name is Ashish and I love Python.")
print(result1.data)

# ── Turn 2 — pehle ki history pass karo ──────────────────────
# INTERVIEW: message_history se agent ko pehle ki conversation milti hai
result2 = agent.run_sync(
    "What is my name and what do I love?",
    message_history=result1.new_messages(),   # <-- key param
)
print(result2.data)  # "Your name is Ashish and you love Python."

# ── Full history tracking ─────────────────────────────────────
all_messages: list[ModelMessage] = []

def chat(user_input: str) -> str:
    global all_messages
    result = agent.run_sync(user_input, message_history=all_messages)
    all_messages.extend(result.new_messages())  # accumulate
    return result.data

r1 = chat("I am building a FastAPI app.")
r2 = chat("What database should I use with it?")
r3 = chat("How do I connect it to the app I mentioned?")

# ── Serialization (DB mein save karo, reload karo) ────────────
from pydantic_ai.messages import ModelMessagesTypeAdapter

# Save
history_bytes = ModelMessagesTypeAdapter.dump_json(all_messages)
# Load
restored = ModelMessagesTypeAdapter.validate_json(history_bytes)
'''

print(HISTORY_CODE)
print("  Key methods:")
print("  result.new_messages()    → messages from THIS run (for next turn)")
print("  result.all_messages()   → ALL messages including history")
print("  ModelMessagesTypeAdapter.dump_json() → serialize to bytes")
print("  ModelMessagesTypeAdapter.validate_json() → deserialize")
print("  INTERVIEW: new_messages() vs all_messages() — naya vs sab")

if LIVE_MODE:
    print("\n  [LIVE] Testing multi-turn conversation...")
    try:
        conv_agent = Agent(
            get_model(),
            system_prompt="You are a helpful assistant. Remember what I tell you.",
        )
        r1 = conv_agent.run_sync("I am learning PydanticAI framework.")
        r2 = conv_agent.run_sync(
            "What framework am I learning?",
            message_history=r1.new_messages(),
        )
        print(f"  Turn 1 response: {r1.data[:60]}...")
        print(f"  Turn 2 response (should mention PydanticAI): {r2.data[:80]}...")
        print(f"  Messages in turn 2 history: {len(r1.new_messages())}")
    except Exception as e:
        print(f"  [!] Live history call failed: {e}")


# =============================================================================
# SECTION 7: Streaming
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 7: Streaming (run_stream + stream_text)")
print("=" * 65)

STREAMING_CODE = '''\
import asyncio
from pydantic_ai import Agent

agent = Agent("openai:gpt-4o-mini")

# ── Text streaming (async) ────────────────────────────────────
async def stream_demo():
    """INTERVIEW: run_stream() context manager se streaming milti hai"""

    async with agent.run_stream("Tell me 3 interesting Python facts.") as stream:
        # delta=True → sirf naye characters
        async for chunk in stream.stream_text(delta=True):
            print(chunk, end="", flush=True)

    print()                            # newline
    data   = await stream.get_data()  # complete final result
    usage  = stream.usage()           # token count
    print(f"Total tokens: {usage.total_tokens}")

asyncio.run(stream_demo())

# ── Structured streaming ───────────────────────────────────────
# INTERVIEW: Structured output ke saath bhi stream possible hai
# Note: partial structured objects milte hain as JSON assembles

async def stream_structured():
    from pydantic import BaseModel

    class Summary(BaseModel):
        points: list[str]
        conclusion: str

    summary_agent = Agent("openai:gpt-4o-mini", result_type=Summary)

    async with summary_agent.run_stream("Summarize Python benefits.") as stream:
        # Structured streaming
        async for partial in stream.stream_text(delta=False):
            pass  # partial text accumulates

        result = await stream.get_data()  # final Summary object
        print(result.points)

asyncio.run(stream_structured())

# ── Sync fallback (no streaming, simpler) ─────────────────────
result = agent.run_sync("Tell me about Python.")
print(result.data)
'''

print(STREAMING_CODE)
print("  Sync vs Async:")
print("  agent.run_sync() → blocking, simple, no streaming")
print("  await agent.run() → async, no streaming")
print("  async with agent.run_stream() → async, real-time chunks")


# =============================================================================
# SECTION 8: Validation + Retries
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 8: Validation + Retries")
print("=" * 65)

VALIDATION_CODE = '''\
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior

# ── Strict Pydantic model — validation rules ──────────────────
class StrictOutput(BaseModel):
    answer:     str   = Field(min_length=10, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    category:   str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"technical", "business", "general", "sports"}
        if v.lower() not in allowed:
            # INTERVIEW: Pydantic raise kare → PydanticAI retry karega
            raise ValueError(
                f"Category must be one of {allowed}, got: {v!r}"
            )
        return v.lower()

# result_retries = max retry count on validation failure
agent = Agent(
    "openai:gpt-4o-mini",
    result_type=StrictOutput,
    result_retries=3,          # <-- validation fail → retry with error feedback
    system_prompt="Classify text. Category must be: technical, business, general, or sports.",
)

# ── ModelRetry — tool level retry ────────────────────────────
from pydantic_ai import ModelRetry

@dataclass
class FetchDeps:
    max_results: int = 5

fetch_agent = Agent("openai:gpt-4o-mini", deps_type=FetchDeps)

@fetch_agent.tool(retries=2)   # tool-specific retry count
def fetch_url(ctx: RunContext[FetchDeps], url: str) -> str:
    """Fetch content from a URL."""
    if not url.startswith("https://"):
        # INTERVIEW: ModelRetry raise karo — agent ko pata chale kya galat tha
        raise ModelRetry(
            f"URL must start with https://. Got: {url!r}. "
            "Provide a valid secure URL."
        )
    return f"Content from {url}"

# ── Error handling ─────────────────────────────────────────────
try:
    result = agent.run_sync("AI is revolutionizing software development")
    print(result.data)
except UnexpectedModelBehavior as e:
    print(f"Model failed after all retries: {e}")
'''

print(VALIDATION_CODE)
print("  Retry flow:")
print("  1. LLM output → Pydantic validate")
print("  2. Fail → error message append to conversation")
print("  3. LLM retry → hopefully fixes it")
print("  4. After result_retries exhausted → UnexpectedModelBehavior raised")
print("  ModelRetry = explicit tool-level retry trigger")


# =============================================================================
# SECTION 9: Typed Multi-Agent Pipeline (ALEX-style handoff)
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 9: Typed Multi-Agent Pipeline (ALEX Project Comparison)")
print("=" * 65)

PIPELINE_CODE = '''\
"""
TUMHARA ALEX PROJECT:
  Level7/02_langgraph + 03_langgraph_advanced mein multi-agent banaya tha
  State: TypedDict (runtime mein koi validation nahi tha)
  Routing: LangGraph conditional_edges

PydanticAI equivalent:
  State: Pydantic models (fully validated, type-safe)
  Routing: Regular Python if/else
  Simpler code, same power for linear pipelines
"""

from pydantic import BaseModel
from pydantic_ai import Agent
from typing import Literal

# ── Agent 1: Intent Classifier (ALEX Router equivalent) ───────
class CustomerIntent(BaseModel):
    intent: Literal["billing", "technical", "general", "escalate"]
    confidence: float = Field(ge=0.0, le=1.0)
    original_message: str
    extracted_info: dict

intent_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=CustomerIntent,
    system_prompt=(
        "Classify customer message intent. "
        "Options: billing, technical, general, escalate. "
        "Extract relevant info (amounts, issue type, account info)."
    ),
)

# ── Agent 2: Billing Specialist ───────────────────────────────
class BillingResponse(BaseModel):
    action_taken:    str
    amount_adjusted: float | None = None
    ticket_id:       str
    next_steps:      list[str]

billing_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=BillingResponse,
    system_prompt="You are a billing specialist. Resolve billing issues and provide ticket IDs.",
)

# ── Agent 3: Technical Support ────────────────────────────────
class TechnicalResponse(BaseModel):
    issue_identified:   str
    steps_to_resolve:   list[str]
    escalation_needed:  bool
    ticket_id:          str

tech_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=TechnicalResponse,
    system_prompt="You are a technical support specialist. Diagnose issues step by step.",
)

# ── Pipeline function (ALEX-style routing) ────────────────────
async def process_customer_message(message: str):
    # Step 1: Intent classify (typed output)
    intent_result = await intent_agent.run(message)
    intent: CustomerIntent = intent_result.data    # fully typed

    print(f"Intent: {intent.intent} (confidence={intent.confidence:.2f})")

    if intent.intent == "billing":
        res = await billing_agent.run(
            f"Issue: {intent.original_message}\\nInfo: {intent.extracted_info}"
        )
        return res.data   # BillingResponse (typed)

    elif intent.intent == "technical":
        res = await tech_agent.run(
            f"Issue: {intent.original_message}\\nInfo: {intent.extracted_info}"
        )
        if res.data.escalation_needed:
            print("Escalating to human agent!")
        return res.data   # TechnicalResponse (typed)

    else:
        general = Agent("openai:gpt-4o-mini")
        res = await general.run(message)
        return res.data   # str

# vs ALEX (LangGraph):
# LangGraph: TypedDict state, conditional_edges, checkpointing
# PydanticAI: Pydantic models, if/else routing, simpler code
# Use PydanticAI for: linear/simple pipelines, type-safety focus
# Use LangGraph for: cyclic graphs, pause/resume, complex state
'''

print(PIPELINE_CODE)

# Mock pipeline demonstration
print("  [Demo] Mock typed pipeline:")

class MockCustomerIntent(BaseModel):
    intent: Literal["billing", "technical", "general", "escalate"]
    confidence: float = Field(ge=0.0, le=1.0)
    original_message: str
    extracted_info: dict

class MockBillingResponse(BaseModel):
    action_taken: str
    ticket_id: str
    next_steps: list[str]

# Simulate typed handoff
mock_intent = MockCustomerIntent(
    intent="billing",
    confidence=0.92,
    original_message="I was charged twice for my subscription",
    extracted_info={"amount": "overcharged", "subscription": "monthly"},
)

print(f"    Step 1 output type: {type(mock_intent).__name__}")
print(f"    intent = {mock_intent.intent!r} (confidence={mock_intent.confidence})")

mock_response = MockBillingResponse(
    action_taken="Refund initiated for duplicate charge",
    ticket_id="TKT-2026-001",
    next_steps=["Refund in 3-5 business days", "Email confirmation sent"],
)

print(f"    Step 2 output type: {type(mock_response).__name__}")
print(f"    action_taken = {mock_response.action_taken!r}")
print(f"    ticket_id = {mock_response.ticket_id!r}")
print("    [OK] Typed handoff demonstrated — Pydantic validates each step!")

if LIVE_MODE:
    print("\n  [LIVE] Running typed multi-agent pipeline...")
    try:
        import asyncio

        class IntentResult(BaseModel):
            intent: Literal["technical", "billing", "general"]
            summary: str

        class HandledResult(BaseModel):
            handler: str
            response: str
            resolved: bool

        router_agent = Agent(
            get_model(),
            result_type=IntentResult,
            system_prompt="Classify: technical, billing, or general. Summarize the issue.",
        )

        handler_agent = Agent(
            get_model(),
            result_type=HandledResult,
            system_prompt="Handle the customer issue appropriately.",
        )

        async def live_pipeline():
            msg = "My payment failed but money was deducted from my account."
            r1 = await router_agent.run(msg)
            intent_data: IntentResult = r1.data
            print(f"    Intent: {intent_data.intent}")
            print(f"    Summary: {intent_data.summary}")

            r2 = await handler_agent.run(
                f"Intent: {intent_data.intent}\n"
                f"Issue: {intent_data.summary}"
            )
            result_data: HandledResult = r2.data
            print(f"    Handler: {result_data.handler}")
            print(f"    Resolved: {result_data.resolved}")
            print(f"    Response: {result_data.response[:80]}...")

        asyncio.run(live_pipeline())
    except Exception as e:
        print(f"  [!] Live pipeline failed: {e}")


# =============================================================================
# SECTION 10: Comparison — PydanticAI vs Other Frameworks
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 10: Comparison — PydanticAI vs LangChain/CrewAI/DSPy")
print("=" * 65)

comparisons = {
    "PydanticAI": {
        "strengths": [
            "Type-safe structured output (result_type)",
            "FastAPI-like DX — familiar for Python devs",
            "Dependency injection (deps_type + RunContext)",
            "Validation + auto-retry built-in",
            "Model-agnostic (one API, many providers)",
            "Lightweight — minimal abstraction",
        ],
        "weaknesses": [
            "No complex graph support (use LangGraph for that)",
            "Smaller ecosystem than LangChain",
            "No prompt auto-optimization (use DSPy for that)",
            "No built-in RAG pipeline (build manually)",
        ],
        "use_when": [
            "Pydantic/FastAPI already in stack",
            "Structured output extract karna hai",
            "Production-grade validation needed",
            "Simple agent with tools (not complex graphs)",
        ],
    },
    "LangChain/LangGraph": {
        "strengths": ["Huge ecosystem (100+ integrations)", "Complex graph/cyclic agents", "Checkpointing/resume"],
        "weaknesses": ["No type-safety", "Heavy abstraction", "Manual prompt engineering"],
        "use_when": ["Complex stateful multi-agent", "Existing LangChain codebase"],
    },
    "CrewAI": {
        "strengths": ["Role-based autonomous agents", "Task decomposition", "Easy multi-agent team setup"],
        "weaknesses": ["Less type control", "Higher abstraction", "Opinionated structure"],
        "use_when": ["Team simulation", "Autonomous research pipeline"],
    },
    "DSPy": {
        "strengths": ["Prompt auto-optimization", "Declarative signatures", "Systematic improvement"],
        "weaknesses": ["Needs labeled examples", "Complex setup", "Not production-structured-output focused"],
        "use_when": ["Labeled training data available", "Prompt quality critical", "Research/academic work"],
    },
}

DECISION_TREE = """
Decision Tree — Kya use karo?

Need structured/typed output?
  YES → PydanticAI (full type-safety + validation)

Complex cyclic agent graph needed?
  YES → LangGraph (ALEX-style, checkpointing)

Role-based autonomous multi-agent team?
  YES → CrewAI

Prompt auto-optimization, have labeled data?
  YES → DSPy

Simple RAG + document processing?
  YES → LangChain (big ecosystem)

FastAPI backend mein AI endpoint?
  YES → PydanticAI (same Pydantic models, natural fit)

Local/cheap inference?
  YES → PydanticAI + Ollama (ollama:llama3.2)
"""

for framework, info in comparisons.items():
    print(f"\n  {framework}:")
    print(f"    Best for:    {info['use_when'][0]}")
    print(f"    Top strength: {info['strengths'][0]}")
    print(f"    Main weakness: {info['weaknesses'][0]}")

print(DECISION_TREE)


# =============================================================================
# SECTION 11: Complete Typed Agent Example (Worked Example)
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 11: Worked Example — Typed Code Reviewer Agent")
print("=" * 65)

WORKED_EXAMPLE_CODE = '''\
"""
Worked Example: Type-safe Code Reviewer Agent
  - result_type: Pydantic model with strict validation
  - deps_type: user + config injection
  - @agent.tool: static analysis tool
  - Dynamic system prompt: user-specific context
"""

from dataclasses import dataclass
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from typing import Literal

# ── Dependencies ──────────────────────────────────────────────
@dataclass
class ReviewerDeps:
    reviewer_name: str
    language: str
    strictness: Literal["lenient", "moderate", "strict"] = "moderate"

# ── Output model ──────────────────────────────────────────────
class Issue(BaseModel):
    line: int | None
    severity: Literal["info", "warning", "error", "critical"]
    description: str
    fix_suggestion: str

class CodeReviewResult(BaseModel):
    language: str
    overall_quality: Literal["poor", "fair", "good", "excellent"]
    score: int = Field(ge=0, le=100, description="Quality score out of 100")
    issues: list[Issue]
    positive_aspects: list[str]
    summary: str
    approved: bool = Field(description="Whether code can be merged as-is")

# ── Agent ─────────────────────────────────────────────────────
reviewer_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=ReviewerDeps,
    result_type=CodeReviewResult,
    result_retries=2,
)

@reviewer_agent.system_prompt
def reviewer_system_prompt(ctx: RunContext[ReviewerDeps]) -> str:
    strictness_desc = {
        "lenient": "Focus on critical issues only.",
        "moderate": "Flag warnings and errors. Note style issues as info.",
        "strict": "Flag all issues including minor style. High standards.",
    }
    return (
        f"You are {ctx.deps.reviewer_name}, an expert {ctx.deps.language} code reviewer. "
        f"Strictness level: {ctx.deps.strictness}. "
        + strictness_desc[ctx.deps.strictness]
    )

@reviewer_agent.tool_plain
def get_language_conventions(language: str) -> dict:
    """Get coding conventions for a programming language."""
    conventions = {
        "python": {
            "style_guide": "PEP 8",
            "naming": "snake_case for functions, PascalCase for classes",
            "line_length": 79,
            "docstring_style": "Google or NumPy",
        },
        "javascript": {
            "style_guide": "Airbnb or Standard",
            "naming": "camelCase for functions, PascalCase for classes",
            "line_length": 100,
            "docstring_style": "JSDoc",
        },
    }
    return conventions.get(language.lower(), {"style_guide": "None specified"})

# ── Usage ─────────────────────────────────────────────────────
sample_code = """
def calc(x, y, op):
    if op == "add":
        return x + y
    elif op == "sub":
        return x - y
    elif op == "mul":
        return x * y
    elif op == "div":
        if y == 0:
            return None
        return x / y
"""

deps = ReviewerDeps(
    reviewer_name="SeniorDev Bot",
    language="Python",
    strictness="strict",
)

result = reviewer_agent.run_sync(
    f"Review this Python code:\\n{sample_code}",
    deps=deps,
)

review = result.data   # CodeReviewResult — fully typed
print(f"Score: {review.score}/100")
print(f"Quality: {review.overall_quality}")
print(f"Approved: {review.approved}")
print(f"Issues: {len(review.issues)}")
for issue in review.issues:
    print(f"  [{issue.severity.upper()}] {issue.description}")
print(f"Summary: {review.summary}")
'''

print(WORKED_EXAMPLE_CODE)

# Define models for possible live run
@dataclass
class ReviewerDeps:
    reviewer_name: str
    language: str
    strictness: Literal["lenient", "moderate", "strict"] = "moderate"

class Issue(BaseModel):
    line: Optional[int] = None
    severity: Literal["info", "warning", "error", "critical"]
    description: str
    fix_suggestion: str

class CodeReviewResult(BaseModel):
    language: str
    overall_quality: Literal["poor", "fair", "good", "excellent"]
    score: int = Field(ge=0, le=100, description="Quality score out of 100")
    issues: list[Issue]
    positive_aspects: list[str]
    summary: str
    approved: bool = Field(description="Whether code can be merged as-is")

sample_code = """
def calc(x, y, op):
    if op == "add":
        return x + y
    elif op == "sub":
        return x - y
    elif op == "mul":
        return x * y
    elif op == "div":
        if y == 0:
            return None
        return x / y
"""

if LIVE_MODE:
    print("\n  [LIVE] Running typed code reviewer...")
    try:
        reviewer_agent = Agent(
            get_model(),
            deps_type=ReviewerDeps,
            result_type=CodeReviewResult,
            result_retries=2,
        )

        @reviewer_agent.system_prompt
        def reviewer_sys(ctx: RunContext[ReviewerDeps]) -> str:
            return (
                f"You are {ctx.deps.reviewer_name}, "
                f"an expert {ctx.deps.language} code reviewer. "
                f"Strictness: {ctx.deps.strictness}."
            )

        @reviewer_agent.tool_plain
        def get_lang_conventions(language: str) -> dict:
            """Get coding conventions for a language."""
            return {"style_guide": "PEP 8" if language.lower() == "python" else "N/A"}

        rdeps = ReviewerDeps("SeniorDev Bot", "Python", "strict")
        rresult = reviewer_agent.run_sync(
            f"Review this Python code:\n{sample_code}",
            deps=rdeps,
        )
        review = rresult.data
        print(f"  Score: {review.score}/100")
        print(f"  Quality: {review.overall_quality}")
        print(f"  Approved: {review.approved}")
        print(f"  Issues ({len(review.issues)}):")
        for issue in review.issues[:3]:
            print(f"    [{issue.severity.upper()}] {issue.description[:60]}")
        print(f"  Summary: {review.summary[:100]}...")
    except Exception as e:
        print(f"  [!] Live code review failed: {e}")


# =============================================================================
# FINAL SUMMARY
# =============================================================================
print("\n" + "=" * 65)
print("PYDANTIC AI — INTERVIEW CHEAT SHEET")
print("=" * 65)

CHEAT_SHEET = {
    "Agent creation":     "Agent('provider:model', result_type=Model, deps_type=Deps)",
    "Structured output":  "result_type=PydanticModel → auto-parsed + validated",
    "Dependency inject":  "deps_type=Dataclass + @agent.tool(ctx: RunContext[Deps])",
    "Tool registration":  "@agent.tool / @agent.tool_plain decorators",
    "System prompt":      "constructor string + @agent.system_prompt decorators",
    "Multi-turn":         "result.new_messages() → next call ka message_history",
    "Streaming":          "async with agent.run_stream() as s: async for c in s.stream_text()",
    "Retries":            "result_retries=N on Agent; ModelRetry in tools",
    "Provider swap":      "'openai:gpt-4o-mini' → 'groq:llama3.1' — 1 string change",
    "Run methods":        "run_sync() blocking / await run() async / run_stream() streaming",
    "vs LangChain":       "PydanticAI = type-safe structured; LangChain = big ecosystem",
    "vs CrewAI":          "PydanticAI = single agent precision; CrewAI = role-based team",
    "vs DSPy":            "PydanticAI = structured output; DSPy = prompt optimization",
    "vs LangGraph":       "PydanticAI = simple routing; LangGraph = complex cyclic graphs",
}

for k, v in CHEAT_SHEET.items():
    print(f"  {k:<22}: {v}")

print("\n" + "=" * 65)
mode_str = "LIVE" if LIVE_MODE else ("MOCK (pydantic-ai not installed)" if not PYDANTIC_AI_AVAILABLE else "MOCK (no API key)")
print(f"DONE! Mode: {mode_str}")
print("Next: Level7/09 — explore OpenAI Agents SDK or Instructor comparison")
print("=" * 65)
