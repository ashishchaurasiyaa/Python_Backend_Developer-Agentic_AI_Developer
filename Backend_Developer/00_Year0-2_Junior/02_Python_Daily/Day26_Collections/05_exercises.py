"""
DAY 26 — EXERCISES: collections module
Solve all before moving to Day 27.
"""

# ─────────────────────────────────────────────
# Q1. EASY — Word frequency
# Given a list of words, find the top 3 most frequent words
# using Counter. Exclude stop words: ["the", "a", "is", "in"]
# ─────────────────────────────────────────────
words = ["the", "python", "is", "a", "language", "python", "is", "used", "in", "python", "ai"]
# Expected: [('python', 3), ('language', 1), ('used', 1)]
# YOUR CODE:


# ─────────────────────────────────────────────
# Q2. MEDIUM — Inverted index using defaultdict
# Given a list of documents, build an inverted index:
# {word: [list of doc ids that contain that word]}
# ─────────────────────────────────────────────
documents = {
    1: "python backend developer",
    2: "python agentic ai engineer",
    3: "backend developer salary",
}
# Expected: {'python': [1, 2], 'backend': [1, 3], ...}
# YOUR CODE:


# ─────────────────────────────────────────────
# Q3. MEDIUM — Sliding window maximum using deque
# Given a list of numbers and window size k,
# find the maximum in each window. O(n) solution using deque.
# ─────────────────────────────────────────────
nums = [1, 3, -1, -3, 5, 3, 6, 7]
k = 3
# Expected: [3, 3, 5, 5, 6, 7]
# YOUR CODE:


# ─────────────────────────────────────────────
# Q4. HARD — LLM Session Manager
# Build a SessionManager class that:
# - Stores conversation history per session_id (defaultdict)
# - Limits each session to last 10 messages (deque with maxlen)
# - Tracks total messages sent per session (Counter)
# - Returns session stats using NamedTuple
# ─────────────────────────────────────────────
from collections import defaultdict, deque, Counter
from typing import NamedTuple


class SessionStats(NamedTuple):
    session_id: str
    total_messages: int
    recent_messages: list[dict]


class SessionManager:
    # YOUR CODE:
    pass


# Test your implementation:
# sm = SessionManager()
# sm.add_message("sess_1", "user", "Hello")
# sm.add_message("sess_1", "ai", "Hi there!")
# stats = sm.get_stats("sess_1")
# print(stats)


# ─────────────────────────────────────────────
# Q5. ARCHITECTURE — Agent Tool Registry
# Build a ToolRegistry using defaultdict that:
# - Registers tools by category using a decorator
# - Supports listing all tools in a category
# - Tracks usage count per tool using Counter
# - Returns the most-used tool in a category
# ─────────────────────────────────────────────
# YOUR CODE:


# ─────────────────────────────────────────────
# ANSWERS (reveal after attempting)
# ─────────────────────────────────────────────

def answers():
    from collections import Counter, defaultdict, deque
    from typing import NamedTuple

    # Q1
    words = ["the", "python", "is", "a", "language", "python", "is", "used", "in", "python", "ai"]
    stop_words = {"the", "a", "is", "in"}
    filtered = [w for w in words if w not in stop_words]
    print("Q1:", Counter(filtered).most_common(3))

    # Q2
    documents = {1: "python backend developer", 2: "python agentic ai engineer", 3: "backend developer salary"}
    index: defaultdict[str, list[int]] = defaultdict(list)
    for doc_id, text in documents.items():
        for word in text.split():
            index[word].append(doc_id)
    print("Q2:", dict(index))

    # Q3
    nums = [1, 3, -1, -3, 5, 3, 6, 7]; k = 3
    dq: deque[int] = deque()
    result = []
    for i, n in enumerate(nums):
        while dq and nums[dq[-1]] <= n:
            dq.pop()
        dq.append(i)
        if dq[0] == i - k:
            dq.popleft()
        if i >= k - 1:
            result.append(nums[dq[0]])
    print("Q3:", result)
