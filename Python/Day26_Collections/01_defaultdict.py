"""
DAY 26 — collections.defaultdict
Architecture Level: Senior Python Backend + Agentic AI
"""

from collections import defaultdict
from typing import DefaultDict

# ─────────────────────────────────────────────
# 1. BASICS — What problem does it solve?
# ─────────────────────────────────────────────

# Problem with regular dict:
data = {}
# data["key"].append(1)  # KeyError!

# defaultdict auto-creates missing keys with a factory
data: DefaultDict[str, list] = defaultdict(list)
data["users"].append("Alice")
data["users"].append("Bob")
data["admins"].append("Charlie")
print(dict(data))  # {'users': ['Alice', 'Bob'], 'admins': ['Charlie']}


# ─────────────────────────────────────────────
# 2. REAL BACKEND USE CASE — Group API logs by endpoint
# ─────────────────────────────────────────────

raw_logs = [
    {"endpoint": "/api/users", "status": 200, "latency_ms": 45},
    {"endpoint": "/api/orders", "status": 500, "latency_ms": 1200},
    {"endpoint": "/api/users", "status": 200, "latency_ms": 30},
    {"endpoint": "/api/orders", "status": 200, "latency_ms": 200},
    {"endpoint": "/api/ai/chat", "status": 200, "latency_ms": 800},
]

# Group latencies by endpoint
latency_by_endpoint: DefaultDict[str, list[int]] = defaultdict(list)
for log in raw_logs:
    latency_by_endpoint[log["endpoint"]].append(log["latency_ms"])

# Calculate average latency per endpoint
avg_latency = {
    endpoint: sum(latencies) / len(latencies)
    for endpoint, latencies in latency_by_endpoint.items()
}
print("Avg latency:", avg_latency)


# ─────────────────────────────────────────────
# 3. AGENTIC AI USE CASE — Track tool calls per agent
# ─────────────────────────────────────────────

tool_usage: DefaultDict[str, DefaultDict[str, int]] = defaultdict(
    lambda: defaultdict(int)
)

agent_actions = [
    ("research_agent", "web_search"),
    ("research_agent", "web_search"),
    ("code_agent", "run_code"),
    ("research_agent", "file_read"),
    ("code_agent", "run_code"),
    ("code_agent", "web_search"),
]

for agent, tool in agent_actions:
    tool_usage[agent][tool] += 1

print("Tool usage per agent:")
for agent, tools in tool_usage.items():
    print(f"  {agent}: {dict(tools)}")


# ─────────────────────────────────────────────
# 4. ADVANCED — defaultdict with custom factory
# ─────────────────────────────────────────────

class AgentMetrics:
    def __init__(self):
        self.calls = 0
        self.errors = 0
        self.total_tokens = 0

    def record(self, tokens: int, error: bool = False):
        self.calls += 1
        self.total_tokens += tokens
        if error:
            self.errors += 1

    def __repr__(self):
        return f"AgentMetrics(calls={self.calls}, errors={self.errors}, tokens={self.total_tokens})"


metrics: DefaultDict[str, AgentMetrics] = defaultdict(AgentMetrics)

metrics["gpt-4"].record(tokens=500)
metrics["gpt-4"].record(tokens=300, error=True)
metrics["claude-3"].record(tokens=800)

for model, m in metrics.items():
    print(f"{model}: {m}")


# ─────────────────────────────────────────────
# 5. ARCHITECTURE PATTERN — Registry with defaultdict
# ─────────────────────────────────────────────

from typing import Callable, Type

# Plugin registry pattern used in frameworks like LangChain
_tool_registry: DefaultDict[str, list[Callable]] = defaultdict(list)


def register_tool(category: str):
    """Decorator to register AI tools by category."""
    def decorator(func: Callable) -> Callable:
        _tool_registry[category].append(func)
        return func
    return decorator


@register_tool("search")
def google_search(query: str) -> str:
    return f"Results for: {query}"


@register_tool("search")
def bing_search(query: str) -> str:
    return f"Bing results for: {query}"


@register_tool("code")
def run_python(code: str) -> str:
    return f"Executed: {code}"


print("\nRegistered tools:")
for category, tools in _tool_registry.items():
    print(f"  {category}: {[t.__name__ for t in tools]}")


# ─────────────────────────────────────────────
# INTERVIEW QUESTION — What's the difference?
# ─────────────────────────────────────────────
# dict.get(key, default) — returns default but does NOT store it
# defaultdict         — stores the default value on first access
# dict.setdefault()   — stores the default value (similar to defaultdict)

d = {}
val = d.setdefault("key", [])  # stores [] in d
val.append(1)
print(d)  # {'key': [1]} — setdefault stored the reference

# defaultdict is cleaner for this pattern
