"""
Modern Topics — Doc 4: Memory Frameworks (PRACTICAL)
=======================================================
`mem0ai` isn't required to understand what a memory framework actually does
underneath — this builds a minimal one from scratch with the same
add/search/update/delete shape Mem0 exposes, covering all 4 memory types the
doc names. If you have `mem0ai` installed, Section 5 shows the real import.

Topics covered:
  1. Short-term memory — a conversation buffer, capped
  2. Long-term memory — persistent facts, searchable by relevance
  3. Episodic memory — "what happened when," searchable by recency + content
  4. Semantic memory — general facts about the user, not tied to one moment
  5. Wiring memory into a chat function (memory-augmented system prompt)

Install: pip install mem0ai (optional, for Section 6's real version)
Run: python 04_memory_frameworks_practical.py
"""

import time
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Short-Term Memory — Conversation Buffer
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Short-Term Memory (Conversation Buffer)")
print("=" * 70)


class ConversationBuffer:
    """Last N messages, in-memory, reset per session — exactly what the doc
    describes. No persistence, no search — it's just a bounded deque."""

    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages
        self.messages: list[dict] = []

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)  # drop oldest — this IS the "short-term" property

    def get(self) -> list[dict]:
        return self.messages


buffer = ConversationBuffer(max_messages=3)
for i in range(5):
    buffer.add("user", f"message {i}")
print(f"\n  Added 5 messages, max_messages=3 -> buffer holds: {[m['content'] for m in buffer.get()]}")
print("  (oldest 2 were dropped — this resets entirely at session end)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Long-Term Memory — Persistent, Searchable Facts
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Long-Term Memory (Mem0-shaped)")
print("=" * 70)


@dataclass
class MemoryEntry:
    id: str
    user_id: str
    text: str
    created_at: float = field(default_factory=time.time)


def mock_embed(text: str) -> list[float]:
    import hashlib
    h = hashlib.sha256(text.lower().encode()).digest()
    return [b / 255.0 for b in h[:16]]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class MiniMemory:
    """Same public shape as Mem0's Memory class: add / search / update /
    delete / get_all, all scoped by user_id — so the mental model transfers
    directly when you do use the real library."""

    def __init__(self):
        self._store: dict[str, MemoryEntry] = {}
        self._next_id = 0

    def add(self, text: str, user_id: str) -> str:
        self._next_id += 1
        mid = f"mem_{self._next_id}"
        self._store[mid] = MemoryEntry(id=mid, user_id=user_id, text=text)
        return mid

    def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        query_emb = mock_embed(query)
        candidates = [m for m in self._store.values() if m.user_id == user_id]
        scored = [(m, cosine_similarity(query_emb, mock_embed(m.text))) for m in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{"id": m.id, "text": m.text, "score": round(s, 3)} for m, s in scored[:limit]]

    def update(self, memory_id: str, data: str):
        if memory_id in self._store:
            self._store[memory_id].text = data

    def delete(self, memory_id: str):
        self._store.pop(memory_id, None)

    def get_all(self, user_id: str) -> list[dict]:
        return [{"id": m.id, "text": m.text} for m in self._store.values() if m.user_id == user_id]


m = MiniMemory()
m.add("I love Python and FastAPI", user_id="alice")
m.add("I'm working on an e-commerce project", user_id="alice")
m.add("I prefer concise code with type hints", user_id="alice")

print(f"\n  All memories for alice: {m.get_all('alice')}")
related = m.search("What does Alice like?", user_id="alice")
print(f"\n  Search 'What does Alice like?': {related}")
if not related or related[0]["score"] < 0.3:
    print("  [mock_embed is hash-based, not semantic — a real embedding model would")
    print("   rank 'I love Python and FastAPI' clearly highest for this query]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Episodic Memory — What Happened When
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Episodic Memory — Time-Anchored Events")
print("=" * 70)


class EpisodicMemory:
    """Unlike long-term facts, episodes are tied to WHEN they happened —
    'last week we discussed X' needs a timestamp, not just semantic content."""

    def __init__(self):
        self.episodes: list[dict] = []

    def record(self, summary: str, topic: str):
        self.episodes.append({"summary": summary, "topic": topic, "timestamp": time.time()})

    def recall_by_topic(self, topic: str) -> list[dict]:
        return [e for e in self.episodes if topic.lower() in e["topic"].lower()]

    def recall_recent(self, n: int = 3) -> list[dict]:
        return sorted(self.episodes, key=lambda e: e["timestamp"], reverse=True)[:n]


episodic = EpisodicMemory()
episodic.record("Discussed database indexing strategy", topic="database")
episodic.record("Debugged a race condition in the payment flow", topic="concurrency")
episodic.record("Reviewed the RAG pipeline chunking approach", topic="database")

print(f"\n  Episodes about 'database': {[e['summary'] for e in episodic.recall_by_topic('database')]}")
print(f"  Most recent 2 episodes: {[e['summary'] for e in episodic.recall_recent(2)]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Semantic Memory — General Facts, Not Tied to a Moment
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Semantic Memory — Knowledge-Graph-Shaped")
print("=" * 70)


class SemanticMemory:
    """Facts as (subject, relation, object) triples — the doc calls this
    'Neo4j-style'. A real implementation would use a graph DB; this is the
    same shape as an adjacency list, enough to show the structure."""

    def __init__(self):
        self.triples: list[tuple[str, str, str]] = []

    def add_fact(self, subject: str, relation: str, obj: str):
        self.triples.append((subject, relation, obj))

    def query(self, subject: str = None, relation: str = None) -> list[tuple]:
        return [t for t in self.triples if (subject is None or t[0] == subject) and (relation is None or t[1] == relation)]


semantic = SemanticMemory()
semantic.add_fact("Alice", "works_at", "Acme Corp")
semantic.add_fact("Alice", "prefers_language", "Python")
semantic.add_fact("Acme Corp", "industry", "fintech")

print(f"\n  Everything about Alice: {semantic.query(subject='Alice')}")
print(f"  Everything with relation 'prefers_language': {semantic.query(relation='prefers_language')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Wiring Memory Into a Chat Function
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Memory-Augmented System Prompt")
print("=" * 70)


def build_memory_augmented_system_prompt(user_id: str, query: str, memory: MiniMemory) -> str:
    memories = memory.search(query, user_id=user_id, limit=5)
    memory_text = "\n".join(f"- {mem['text']}" for mem in memories) or "(no relevant memories found)"
    return f"""You are a helpful assistant.

What you remember about this user:
{memory_text}"""


prompt = build_memory_augmented_system_prompt("alice", "help me write some code", m)
print(f"\n{prompt}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: If You Have mem0ai Installed
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: The Real Thing")
print("=" * 70)

try:
    from mem0 import Memory  # noqa: F401
    print("\n  mem0ai IS installed — swap MiniMemory for the real Memory class above;")
    print("  the API shape (add/search/update/delete/get_all) is identical on purpose.")
except ImportError:
    print("\n  [mem0ai not installed — `pip install mem0ai` to use the real thing.")
    print("   MiniMemory above mirrors its exact API shape, so switching later is")
    print("   a one-line change, not a redesign.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add 3 more facts to `semantic` and query by a relation you added.

MEDIUM:
2. Add an `update` method to EpisodicMemory that lets you correct a past
   episode's summary without losing its original timestamp.

HARD:
3. Combine long-term (MiniMemory) and semantic (SemanticMemory) into one
   `search_all(query, user_id)` that returns both fact-search hits AND any
   semantic triples where the subject matches user_id.

PRO:
4. If you have `mem0ai` installed: run Section 2's exact add/search calls
   against the real Memory class and compare its search ranking against
   MiniMemory's mock version on the same 3 memories + query.
""")

if __name__ == "__main__":
    print("\nDone. Next: 05_multimodal_agents_practical.py")
