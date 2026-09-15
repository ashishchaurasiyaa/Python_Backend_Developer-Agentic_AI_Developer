"""
DAY 26 — collections.deque  (double-ended queue)
Architecture Level: Senior Python Backend + Agentic AI

Why deque over list for queues?
  list.append()    O(1) | list.pop()    O(1)  ← right side fast
  list.insert(0)   O(n) | list.pop(0)   O(n)  ← left side SLOW
  deque.appendleft O(1) | deque.popleft O(1)  ← BOTH sides fast
"""

from collections import deque
from typing import Generic, TypeVar, Iterator
import time

T = TypeVar("T")


# ─────────────────────────────────────────────
# 1. BASICS
# ─────────────────────────────────────────────

dq: deque[int] = deque([1, 2, 3], maxlen=5)
dq.append(4)         # right end
dq.appendleft(0)     # left end
print(dq)            # deque([0, 1, 2, 3, 4])

dq.append(99)        # maxlen=5, pushes out leftmost (0)
print(dq)            # deque([1, 2, 3, 4, 99])

dq.rotate(2)         # rotate right by 2
print(dq)            # deque([4, 99, 1, 2, 3])

dq.rotate(-1)        # rotate left by 1
print(dq)            # deque([99, 1, 2, 3, 4])


# ─────────────────────────────────────────────
# 2. BACKEND USE CASE — Sliding Window Log Buffer
# ─────────────────────────────────────────────

class SlidingWindowLogger:
    """
    Keep only the last N log entries in memory.
    Used in AI agents to maintain recent context window.
    """

    def __init__(self, window_size: int):
        self._logs: deque[dict] = deque(maxlen=window_size)

    def log(self, level: str, message: str, **metadata):
        import datetime
        self._logs.append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **metadata,
        })

    def get_recent(self, n: int | None = None) -> list[dict]:
        logs = list(self._logs)
        return logs[-n:] if n else logs

    def has_recent_errors(self, last_n: int = 10) -> bool:
        recent = list(self._logs)[-last_n:]
        return any(log["level"] == "ERROR" for log in recent)


logger = SlidingWindowLogger(window_size=100)
logger.log("INFO", "Agent started", agent="research_agent")
logger.log("INFO", "Tool called", tool="web_search")
logger.log("ERROR", "Tool failed", tool="web_search", error="timeout")
logger.log("INFO", "Retrying", attempt=2)

print("Recent errors:", logger.has_recent_errors())
print("Last 2 logs:", logger.get_recent(2))


# ─────────────────────────────────────────────
# 3. AGENTIC AI USE CASE — Conversation history with token limit
# ─────────────────────────────────────────────

class ConversationBuffer:
    """
    Maintains a rolling window of messages for LLM context.
    When buffer is full, oldest messages are dropped automatically.
    This is a simplified version of LangChain's ConversationBufferWindowMemory.
    """

    def __init__(self, max_messages: int = 20):
        self._messages: deque[dict] = deque(maxlen=max_messages)

    def add_human(self, content: str):
        self._messages.append({"role": "user", "content": content})

    def add_ai(self, content: str):
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def token_estimate(self) -> int:
        """Rough estimate: 4 chars ≈ 1 token."""
        total_chars = sum(len(m["content"]) for m in self._messages)
        return total_chars // 4


buffer = ConversationBuffer(max_messages=6)
buffer.add_human("What is Python?")
buffer.add_ai("Python is a high-level programming language.")
buffer.add_human("What are its uses?")
buffer.add_ai("Web dev, AI/ML, automation, data science.")
buffer.add_human("Tell me about asyncio.")
buffer.add_ai("asyncio is Python's async I/O framework.")
buffer.add_human("How does it compare to threading?")  # oldest pair drops

print("\nConversation buffer (6 max):", len(buffer.get_messages()), "messages")
print("Estimated tokens:", buffer.token_estimate())


# ─────────────────────────────────────────────
# 4. ARCHITECTURE PATTERN — Thread-safe task queue
# ─────────────────────────────────────────────

import threading


class TaskQueue(Generic[T]):
    """
    Thread-safe FIFO queue using deque.
    deque.appendleft + deque.pop is thread-safe for single producer/consumer.
    For multiple producers/consumers, use queue.Queue instead.
    """

    def __init__(self):
        self._queue: deque[T] = deque()
        self._lock = threading.Lock()

    def enqueue(self, item: T) -> None:
        with self._lock:
            self._queue.appendleft(item)

    def dequeue(self) -> T | None:
        with self._lock:
            if self._queue:
                return self._queue.pop()
        return None

    def __len__(self) -> int:
        return len(self._queue)


queue: TaskQueue[str] = TaskQueue()
queue.enqueue("task_1")
queue.enqueue("task_2")
queue.enqueue("task_3")

print(f"\nQueue size: {len(queue)}")
print(f"Dequeued: {queue.dequeue()}")  # task_1 (FIFO)
print(f"Queue size after: {len(queue)}")


# ─────────────────────────────────────────────
# INTERVIEW — deque vs list vs queue.Queue
# ─────────────────────────────────────────────
# deque         — fast both ends, NOT thread-safe (appendleft/pop pair IS safe)
# list          — fast right end only (O(n) for left)
# queue.Queue   — fully thread-safe, blocking get/put, used for threads
# asyncio.Queue — fully async-safe, used for coroutines
