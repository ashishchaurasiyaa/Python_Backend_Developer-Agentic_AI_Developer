"""
DAY 33 — Dataclasses Advanced: field(), __post_init__, frozen, slots
Architecture Level: Senior Python Backend + Agentic AI
"""

from dataclasses import dataclass, field, asdict, astuple, fields, replace, KW_ONLY
from typing import ClassVar
import uuid
from datetime import datetime


# ═══════════════════════════════════════════════════════
# PART A: field() — the key to advanced dataclasses
# ═══════════════════════════════════════════════════════

@dataclass
class AgentConfig:
    # field(default_factory=) — for mutable defaults (NEVER use default=[])
    name: str
    model: str = "gpt-4"
    tools: list[str]             = field(default_factory=list)
    metadata: dict[str, str]     = field(default_factory=dict)

    # field with repr=False — hide sensitive data from repr
    api_key: str                 = field(default="", repr=False)

    # field with init=False — computed, not passed to __init__
    created_at: datetime         = field(default_factory=datetime.utcnow, init=False)
    agent_id: str                = field(default_factory=lambda: str(uuid.uuid4())[:8], init=False)

    # field with compare=False — exclude from __eq__ comparison
    _call_count: int             = field(default=0, init=False, repr=False, compare=False)

    def record_call(self):
        self._call_count += 1

    @property
    def call_count(self) -> int:
        return self._call_count


agent = AgentConfig(name="researcher", tools=["web_search", "calculator"])
print(f"Agent: {agent}")
print(f"ID: {agent.agent_id}")
print(f"Created: {agent.created_at}")
agent.record_call()
print(f"Calls: {agent.call_count}")

# GOTCHA — mutable default without field():
# @dataclass
# class Bad:
#     items: list = []  # ALL instances share same list! Bug!
#
# @dataclass
# class Good:
#     items: list = field(default_factory=list)  # each instance gets own list


# ═══════════════════════════════════════════════════════
# PART B: __post_init__ — validation and computed fields
# ═══════════════════════════════════════════════════════

@dataclass
class LLMRequest:
    prompt: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt: str = ""

    def __post_init__(self):
        # Validation
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"Temperature must be 0-2, got {self.temperature}")
        if self.max_tokens < 1 or self.max_tokens > 8192:
            raise ValueError(f"max_tokens must be 1-8192")

        # Normalization
        self.prompt = self.prompt.strip()
        self.model = self.model.lower()

        # Set default system prompt based on model
        if not self.system_prompt:
            self.system_prompt = f"You are a helpful assistant powered by {self.model}."


req = LLMRequest(prompt="  What is Python?  ", temperature=0.5)
print(f"\nRequest: {req}")

try:
    bad_req = LLMRequest(prompt="test", temperature=3.0)
except ValueError as e:
    print(f"Validation error: {e}")


# ═══════════════════════════════════════════════════════
# PART C: frozen=True — immutable dataclasses
# ═══════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModelConfig:
    """
    Immutable configuration — hashable, safe to use as dict key or set member.
    Use for configs that should never change after creation.
    """
    model: str
    temperature: float
    max_tokens: int
    provider: str = "openai"

    def with_temperature(self, temp: float) -> "ModelConfig":
        """frozen dataclasses use replace() for 'mutations'."""
        return replace(self, temperature=temp)

    @property
    def is_expensive(self) -> bool:
        return self.model in ("gpt-4", "claude-3-opus")


gpt4_config = ModelConfig("gpt-4", 0.7, 2000)
creative_config = gpt4_config.with_temperature(0.9)

print(f"\nBase config: {gpt4_config}")
print(f"Creative config: {creative_config}")

# frozen=True makes it hashable
config_cache: dict[ModelConfig, str] = {
    gpt4_config: "gpt4_result_cached",
    creative_config: "creative_result_cached",
}
print(f"Cache lookup: {config_cache[gpt4_config]}")

# try:
#     gpt4_config.temperature = 1.0  # FrozenInstanceError!


# ═══════════════════════════════════════════════════════
# PART D: slots=True — memory optimization (Python 3.10+)
# ═══════════════════════════════════════════════════════

@dataclass(slots=True)
class EmbeddingVector:
    """
    Use slots=True when creating MANY instances (e.g., embedding vectors).
    slots=True: ~30-40% less memory, faster attribute access.
    Trade-off: no __dict__, can't add new attributes dynamically.
    """
    document_id: str
    vector: list[float]
    model: str = "text-embedding-3-small"
    dimensions: int = field(init=False)

    def __post_init__(self):
        self.dimensions = len(self.vector)

    def cosine_similarity(self, other: "EmbeddingVector") -> float:
        import math
        dot = sum(a * b for a, b in zip(self.vector, other.vector))
        mag_a = math.sqrt(sum(a**2 for a in self.vector))
        mag_b = math.sqrt(sum(b**2 for b in self.vector))
        return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


v1 = EmbeddingVector("doc_1", [0.1, 0.2, 0.3, 0.4])
v2 = EmbeddingVector("doc_2", [0.1, 0.2, 0.3, 0.5])
print(f"\nSimilarity: {v1.cosine_similarity(v2):.4f}")


# ═══════════════════════════════════════════════════════
# PART E: dataclass utilities — asdict, astuple, fields, replace
# ═══════════════════════════════════════════════════════

@dataclass
class ToolCall:
    tool_name: str
    args: dict
    result: str | None = None
    success: bool = True
    execution_ms: float = 0.0


tc = ToolCall("web_search", {"query": "Python asyncio"}, "Found 10 results", True, 250.5)

# asdict — convert to dict (deep, including nested dataclasses)
tc_dict = asdict(tc)
print(f"\nasdict: {tc_dict}")

# replace — create modified copy (like frozen's with_temperature)
tc_failed = replace(tc, success=False, result=None)
print(f"replace: {tc_failed}")

# fields — introspect dataclass structure
print(f"\nfields of ToolCall:")
for f in fields(ToolCall):
    print(f"  {f.name}: {f.type} (default={f.default})")


# ═══════════════════════════════════════════════════════
# PART F: KW_ONLY — keyword-only fields (Python 3.10+)
# ═══════════════════════════════════════════════════════

@dataclass
class AgentStep:
    step_number: int
    description: str
    _: KW_ONLY           # everything after this is keyword-only
    agent_id: str = ""
    session_id: str = ""
    tokens_used: int = 0


# step = AgentStep(1, "Search", "agent_1")      # TypeError!
step = AgentStep(1, "Search", agent_id="agent_1", session_id="sess_1")
print(f"\nAgentStep: {step}")


# ─────────────────────────────────────────────
# INTERVIEW — dataclass vs Pydantic vs NamedTuple
# ─────────────────────────────────────────────
# dataclass       — mutable, no runtime validation, no serialization, fast
# frozen dataclass— immutable, hashable, no runtime validation
# NamedTuple      — immutable, tuple-compatible, minimal features
# Pydantic BaseModel — runtime validation, serialization, FastAPI native
#
# WHEN TO USE:
# dataclass  → internal objects, domain models, no external data
# Pydantic   → FastAPI request/response, config, external data validation
# NamedTuple → read-only DB rows, value objects, tuple compatibility needed
# frozen dc  → cache keys, set members, thread-safe configs
