"""
DAY 26 — collections.Counter
Architecture Level: Senior Python Backend + Agentic AI
"""

from collections import Counter
from typing import Any

# ─────────────────────────────────────────────
# 1. BASICS
# ─────────────────────────────────────────────

words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
c = Counter(words)
print(c)                    # Counter({'apple': 3, 'banana': 2, 'cherry': 1})
print(c.most_common(2))     # [('apple', 3), ('banana', 2)]
print(c["apple"])           # 3
print(c["missing"])         # 0  ← no KeyError, returns 0

# From string
char_count = Counter("architecture")
print(char_count.most_common(3))


# ─────────────────────────────────────────────
# 2. ARITHMETIC OPERATIONS — unique to Counter
# ─────────────────────────────────────────────

week1 = Counter({"api_calls": 1000, "errors": 50, "timeouts": 10})
week2 = Counter({"api_calls": 1200, "errors": 30, "timeouts": 15})

total = week1 + week2      # add counts
diff  = week1 - week2      # subtract, drop zeros and negatives
inter = week1 & week2      # min of each
union = week1 | week2      # max of each

print("Total API calls:", total["api_calls"])   # 2200
print("Error diff:", diff["errors"])            # 20 (50-30)
print("Intersection:", inter)


# ─────────────────────────────────────────────
# 3. BACKEND USE CASE — Rate limiting tracker
# ─────────────────────────────────────────────

from datetime import datetime, timedelta


class RateLimitTracker:
    """Track API usage per client — interview-ready implementation."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._counters: dict[str, Counter] = {}
        self._windows: dict[str, datetime] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = datetime.utcnow()
        if client_id not in self._windows:
            self._windows[client_id] = now
            self._counters[client_id] = Counter()

        # Reset window if expired
        if (now - self._windows[client_id]).seconds >= self.window:
            self._windows[client_id] = now
            self._counters[client_id] = Counter()

        self._counters[client_id]["requests"] += 1
        return self._counters[client_id]["requests"] <= self.max_requests

    def get_usage(self, client_id: str) -> int:
        return self._counters.get(client_id, Counter())["requests"]


limiter = RateLimitTracker(max_requests=5, window_seconds=60)
for i in range(7):
    allowed = limiter.is_allowed("client_123")
    print(f"Request {i+1}: {'ALLOWED' if allowed else 'BLOCKED'}")


# ─────────────────────────────────────────────
# 4. AGENTIC AI USE CASE — Token usage tracking
# ─────────────────────────────────────────────

class TokenUsageTracker:
    """Track LLM token consumption across agents."""

    def __init__(self):
        self._usage: Counter = Counter()

    def record(self, model: str, input_tokens: int, output_tokens: int):
        self._usage[f"{model}.input"] += input_tokens
        self._usage[f"{model}.output"] += output_tokens
        self._usage[f"{model}.total"] += input_tokens + output_tokens

    def top_consumers(self, n: int = 3) -> list[tuple[str, int]]:
        return self._usage.most_common(n)

    def cost_estimate(self, input_price: float = 0.003, output_price: float = 0.015) -> float:
        """Estimate cost per 1K tokens."""
        total_input = sum(v for k, v in self._usage.items() if k.endswith(".input"))
        total_output = sum(v for k, v in self._usage.items() if k.endswith(".output"))
        return (total_input / 1000 * input_price) + (total_output / 1000 * output_price)


tracker = TokenUsageTracker()
tracker.record("gpt-4", 500, 300)
tracker.record("claude-3", 800, 500)
tracker.record("gpt-4", 200, 150)

print("\nTop token consumers:", tracker.top_consumers())
print(f"Estimated cost: ${tracker.cost_estimate():.4f}")


# ─────────────────────────────────────────────
# 5. ADVANCED — Counter as multiset
# ─────────────────────────────────────────────

# Frequency analysis for AI prompt optimization
prompts = [
    "Write a summary of this document",
    "Summarize this text",
    "Write a Python function",
    "Create a function in Python",
    "Write unit tests",
]

# Count word frequency across all prompts
all_words = []
for prompt in prompts:
    all_words.extend(prompt.lower().split())

word_freq = Counter(all_words)
# Remove common stop words
stop_words = {"a", "this", "of", "in"}
for word in stop_words:
    del word_freq[word]

print("\nTop keywords in prompts:", word_freq.most_common(5))

# elements() — iterate with repetition
print("\nElements sample:", list(Counter({"a": 3, "b": 1}).elements()))
