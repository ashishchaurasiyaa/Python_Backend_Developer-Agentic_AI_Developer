"""
Phase5_Agent_Memory — Complete Practical
==========================================
Topics:
  1. Memory taxonomy (short/long/episodic/semantic/procedural)
  2. In-context memory (message history window)
  3. External memory (vector store retrieval)
  4. Episodic memory (structured conversation history)
  5. Semantic memory (knowledge facts)
  6. Memory compression + summarization
  7. Memory retrieval strategies

Install: pip install langchain langchain-openai
Run: python 01_agent_memory_practical.py
"""

import os, json, math, random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("AGENT MEMORY CONCEPTS")
print("=" * 60)

MEMORY_TYPES = {
    "Short-term / In-context": "Last N messages in context window. Fast, limited by context size.",
    "Long-term / External":    "Vector store (Chroma/FAISS). Retrieve relevant chunks on demand.",
    "Episodic":                "Structured past interactions: when, who, what happened.",
    "Semantic":                "World knowledge + learned facts. 'Alice is a Python dev.'",
    "Procedural":              "How to do things: learned workflows, best practices.",
    "Working memory":          "Current task state: scratch pad within a single agent run.",
}
for k, v in MEMORY_TYPES.items():
    print(f"  {k:<30}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: In-Context Memory (Message Window)
# INTERVIEW: Simplest form — keep last K messages, trim oldest
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: In-Context (Window) Memory")
print("=" * 60)

IN_CONTEXT_CODE = '''\
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── Basic window memory ────────────────────────────────────────
store = {}   # session_id → InMemoryChatMessageHistory

def get_session(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

# ── Trim to last K messages ────────────────────────────────────
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import trim_messages

trim = trim_messages(
    max_tokens = 2000,         # trim when history exceeds 2000 tokens
    strategy   = "last",       # keep most RECENT messages
    token_counter = ChatOpenAI(model="gpt-4o-mini"),
    include_system = True,     # always keep system message
    allow_partial  = False,
    start_on       = "human",  # first message must be human
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Remember what the user tells you."),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])

chain = RunnableWithMessageHistory(
    trim | prompt | ChatOpenAI(model="gpt-4o-mini"),
    get_session,
    input_messages_key   = "input",
    history_messages_key = "history",
)

# Multi-turn conversation
config = {"configurable": {"session_id": "user-001"}}
r1 = chain.invoke({"input": "My name is Alice and I love Python."}, config=config)
r2 = chain.invoke({"input": "What is my name?"}, config=config)
# r2 will say "Alice" — short-term memory in action!
'''
print(IN_CONTEXT_CODE[:700])


# Demo implementation
@dataclass
class MessageHistory:
    """
    INTERVIEW: In-context memory = deque of messages.
    Trim from the left when exceeding token limit.
    Keep system message always.
    """
    messages: List[Dict] = field(default_factory=list)
    max_messages: int = 20

    def add(self, role: str, content: str):
        self.messages.append({
            "role":      role,
            "content":   content,
            "timestamp": datetime.now().isoformat(),
        })
        self._trim()

    def _trim(self):
        """Keep system messages + last max_messages messages."""
        system  = [m for m in self.messages if m["role"] == "system"]
        other   = [m for m in self.messages if m["role"] != "system"]
        if len(other) > self.max_messages:
            other = other[-self.max_messages:]  # keep most recent
        self.messages = system + other

    def get_context(self) -> List[Dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def summary(self) -> str:
        return f"MessageHistory({len(self.messages)} messages)"


hist = MessageHistory(max_messages=5)
hist.add("system", "You are a helpful assistant.")
for i in range(8):
    hist.add("user",      f"Message {i+1}: Hello!")
    hist.add("assistant", f"Response {i+1}: Hi there!")

print(f"\n  MessageHistory demo:")
print(f"  Added 8 exchanges (16 messages) + 1 system")
print(f"  After trim (max_messages=5): {len(hist.messages)} messages")
print(f"  Messages kept: {[m['role'] + ':' + m['content'][:15] for m in hist.messages]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: External Long-term Memory (Vector Store)
# INTERVIEW: Store → embed → retrieve relevant memories on demand
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: External Long-term Memory (Vector Store)")
print("=" * 60)

LONG_TERM_CODE = '''\
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.memory import VectorStoreRetrieverMemory

# ── Build vector memory ────────────────────────────────────────
embeddings   = OpenAIEmbeddings()
vectorstore  = Chroma(
    collection_name     = "agent_memory",
    embedding_function  = embeddings,
    persist_directory   = "./agent_memory_store",  # persists to disk!
)

# INTERVIEW: VectorStoreRetrieverMemory retrieves RELEVANT past memories
# (not just recent ones — semantic similarity-based recall)
memory = VectorStoreRetrieverMemory(
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3}),
)

# Store a memory
memory.save_context(
    inputs  = {"input": "My favorite language is Python."},
    outputs = {"output": "Got it! Python is your favorite."},
)
memory.save_context(
    inputs  = {"input": "I work at Google as an SRE."},
    outputs = {"output": "Noted — you\'re an SRE at Google."},
)

# Later: retrieve relevant memories for a new query
relevant = memory.load_memory_variables({"prompt": "What languages do you know?"})
print(relevant["history"])
# → "Human: My favorite language is Python. AI: Got it! Python is your favorite."
# NOT the Google memory — semantic retrieval returns only the language-related fact!
'''
print(LONG_TERM_CODE[:700])


def mock_embed(text: str, dim: int = 4) -> List[float]:
    """Mock embedding."""
    random.seed(hash(text) % (2**31))
    vec = [random.gauss(0, 1) for _ in range(dim)]
    mag = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x/mag for x in vec]


def cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x*x for x in a)) or 1.0
    mb  = math.sqrt(sum(x*x for x in b)) or 1.0
    return dot / (ma * mb)


@dataclass
class Memory:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class VectorMemoryStore:
    """
    INTERVIEW: Long-term memory = vector store of past experiences.
    Retrieve by semantic similarity, not just recency.
    Much better than window memory for factual recall across long sessions.
    """
    def __init__(self):
        self.memories: List[Memory] = []

    def store(self, content: str, metadata: Optional[Dict] = None):
        mem = Memory(
            content   = content,
            metadata  = metadata or {},
            embedding = mock_embed(content),
        )
        self.memories.append(mem)
        print(f"  Stored: '{content[:50]}'")

    def retrieve(self, query: str, k: int = 3) -> List[Memory]:
        q_emb  = mock_embed(query)
        scored = [(cosine_sim(q_emb, m.embedding), m) for m in self.memories]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k]]

    def retrieve_with_scores(self, query: str, k: int = 3) -> List[tuple]:
        q_emb  = mock_embed(query)
        scored = [(cosine_sim(q_emb, m.embedding), m) for m in self.memories]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]


vms = VectorMemoryStore()
vms.store("User likes Python and FastAPI")
vms.store("User works as a backend engineer at Startup")
vms.store("User's favorite food is pizza")
vms.store("User prefers async programming patterns")
vms.store("User has 5 years of Python experience")

print("\n  Vector memory retrieval:")
query = "Python skills and experience"
print(f"  Query: '{query}'")
for score, mem in vms.retrieve_with_scores(query, k=3):
    print(f"  {score:+.4f}  {mem.content}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Episodic Memory
# INTERVIEW: Structured log of past conversations with timestamp and summary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Episodic Memory")
print("=" * 60)

@dataclass
class Episode:
    """
    INTERVIEW: Episodic memory = structured record of a conversation.
    Used to recall: "what did we discuss last Tuesday?"
    """
    episode_id:    str
    session_id:    str
    start_time:    str
    end_time:      Optional[str]
    messages:      List[Dict]
    summary:       str = ""
    key_facts:     List[str] = field(default_factory=list)
    tags:          List[str] = field(default_factory=list)
    embedding:     List[float] = field(default_factory=list)

    def generate_summary(self) -> str:
        """Summarize the episode (in production: use LLM)."""
        num_turns = len([m for m in self.messages if m["role"] == "user"])
        topics    = list({word for m in self.messages
                          for word in m["content"].lower().split()
                          if len(word) > 5})[:5]
        return f"Conversation with {num_turns} turns. Topics: {', '.join(topics)}"


class EpisodicMemoryStore:
    """
    INTERVIEW: Episodic store + vector index for semantic retrieval.
    Also supports timeline search (recent episodes).
    """
    def __init__(self):
        self.episodes: List[Episode] = []

    def save_episode(self, session_id: str, messages: List[Dict], key_facts: List[str] = None) -> Episode:
        ep = Episode(
            episode_id  = f"ep-{len(self.episodes)+1:04d}",
            session_id  = session_id,
            start_time  = datetime.now().isoformat(),
            end_time    = datetime.now().isoformat(),
            messages    = messages,
            key_facts   = key_facts or [],
        )
        ep.summary   = ep.generate_summary()
        ep.embedding = mock_embed(ep.summary)
        self.episodes.append(ep)
        return ep

    def retrieve_similar(self, query: str, k: int = 3) -> List[Episode]:
        q_emb  = mock_embed(query)
        scored = [(cosine_sim(q_emb, ep.embedding), ep) for ep in self.episodes]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:k]]

    def get_recent(self, n: int = 5) -> List[Episode]:
        return self.episodes[-n:]


eps = EpisodicMemoryStore()
ep1 = eps.save_episode("user-001", [
    {"role": "user",      "content": "Help me with Python decorators"},
    {"role": "assistant", "content": "Decorators wrap functions to add behavior"},
], key_facts=["User learning Python decorators"])

ep2 = eps.save_episode("user-001", [
    {"role": "user",      "content": "Explain FastAPI dependencies"},
    {"role": "assistant", "content": "FastAPI uses Depends() for DI"},
], key_facts=["User building FastAPI app"])

print("\n  Episodic memory demo:")
for ep in eps.get_recent(5):
    print(f"  Episode {ep.episode_id}: {ep.summary}")
    print(f"    Key facts: {ep.key_facts}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Semantic Memory (Entity/Fact Store)
# INTERVIEW: Store facts about entities, not conversations
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Semantic Memory (Entity Store)")
print("=" * 60)

SEMANTIC_CODE = '''\
# INTERVIEW: Semantic memory = what the agent KNOWS (not what happened)
# Store structured facts: entity → attribute → value

from langchain.memory import ConversationEntityMemory
from langchain_openai import ChatOpenAI

llm    = ChatOpenAI(model="gpt-4o-mini")
memory = ConversationEntityMemory(llm=llm)

# Conversation that builds entity memory
memory.save_context(
    {"input": "Alice is a Python developer at Google who loves async programming."},
    {"output": "Got it! I\'ll remember that about Alice."}
)
memory.save_context(
    {"input": "Alice recently joined the LangChain team as a contributor."},
    {"output": "Interesting! Alice is now contributing to LangChain."}
)

# Retrieve entity knowledge
entities = memory.load_memory_variables({"input": "Tell me about Alice"})
print(entities)
# → {"entities": {"Alice": "Python developer at Google. Loves async.
#                           Recently joined LangChain as contributor."}}
# INTERVIEW: Entity memory summarizes facts about people/places/things
# Uses LLM to extract and update entities from conversation
'''
print(SEMANTIC_CODE[:600])


class SimpleEntityStore:
    """
    INTERVIEW: Entity store = dict of entity → list of facts.
    Real implementation: Chroma with entity as metadata, LLM for extraction.
    """
    def __init__(self):
        self.entities: Dict[str, List[str]] = {}

    def upsert(self, entity: str, fact: str):
        if entity not in self.entities:
            self.entities[entity] = []
        if fact not in self.entities[entity]:
            self.entities[entity].append(fact)

    def get(self, entity: str) -> List[str]:
        return self.entities.get(entity, [])

    def get_summary(self, entity: str) -> str:
        facts = self.get(entity)
        return f"{entity}: {'. '.join(facts)}" if facts else f"No info about {entity}"


entity_store = SimpleEntityStore()
entity_store.upsert("Alice", "Python developer")
entity_store.upsert("Alice", "works at Google")
entity_store.upsert("Alice", "5 years experience")
entity_store.upsert("FastAPI", "Python web framework")
entity_store.upsert("FastAPI", "based on Starlette")

print("\n  Entity store demo:")
print(f"  Alice: {entity_store.get_summary('Alice')}")
print(f"  FastAPI: {entity_store.get_summary('FastAPI')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Memory Compression
# INTERVIEW: Summarize old memories to save token space
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Memory Compression")
print("=" * 60)

COMPRESSION_CODE = '''\
from langchain.memory import ConversationSummaryBufferMemory
from langchain_openai import ChatOpenAI

llm    = ChatOpenAI(model="gpt-4o-mini")
memory = ConversationSummaryBufferMemory(
    llm             = llm,
    max_token_limit = 1000,   # keep recent messages up to 1000 tokens
    return_messages = True,   # return Message objects, not string
)

# As conversation grows beyond 1000 tokens:
# 1. Oldest messages get SUMMARIZED (LLM generates a summary)
# 2. Summary stored as a SystemMessage at the start
# 3. Recent messages kept verbatim
# 4. Total stays under max_token_limit

# After 3000 tokens of conversation:
# memory.buffer = [
#   SystemMessage("Summary: User asked about Python. We discussed decorators..."),
#   HumanMessage("OK now explain async/await..."),     # recent kept verbatim
#   AIMessage("async/await allows non-blocking I/O..."),
# ]
# → LLM sees: summary + recent messages = compact + complete context!

memory.save_context({"input": "Tell me about Python"}, {"output": "Python is..."})
# Check if summary triggered:
print(memory.moving_summary_buffer)  # shows running summary
print(memory.chat_memory.messages)   # shows recent verbatim messages
'''
print(COMPRESSION_CODE[:600])


class SummaryBufferMemory:
    """
    INTERVIEW: Hybrid memory — recent messages verbatim + older messages summarized.
    Best for long conversations where you need both recent detail + full history.
    """
    def __init__(self, max_messages: int = 5):
        self.recent: List[Dict]  = []
        self.summary: str        = ""
        self.max_messages        = max_messages
        self.compressed_count    = 0

    def add(self, role: str, content: str):
        self.recent.append({"role": role, "content": content})
        if len(self.recent) > self.max_messages:
            self._compress()

    def _compress(self):
        """Compress oldest messages into summary."""
        to_compress = self.recent[:2]  # compress oldest 2
        self.recent = self.recent[2:]  # keep rest
        new_info    = " | ".join(f"{m['role']}: {m['content'][:30]}" for m in to_compress)
        if self.summary:
            self.summary += " ... " + new_info
        else:
            self.summary = new_info
        self.compressed_count += len(to_compress)

    def get_context(self) -> str:
        parts = []
        if self.summary:
            parts.append(f"[Summary of {self.compressed_count} earlier messages]: {self.summary}")
        parts.extend(f"{m['role']}: {m['content']}" for m in self.recent)
        return "\n".join(parts)


sbm = SummaryBufferMemory(max_messages=4)
for i in range(8):
    sbm.add("user",      f"Question {i+1}: Hello?")
    sbm.add("assistant", f"Answer {i+1}: Hi!")

print("\n  SummaryBufferMemory demo:")
print(f"  Added 8 Q/A pairs (16 messages)")
print(f"  Compressed: {sbm.compressed_count} messages into summary")
print(f"  Recent kept: {len(sbm.recent)} messages")
print(f"\n  Context window content:")
print(f"  {sbm.get_context()[:400]}")


print("\n" + "=" * 60)
print("AGENT MEMORY INTERVIEW SUMMARY:")
print("  Short-term: last N messages in context. Simple, limited by tokens.")
print("  Long-term: vector store retrieval. Semantic, scales to many memories.")
print("  Episodic: structured conversation records with timestamps/summaries.")
print("  Semantic: entity facts ('Alice → Python dev'). LLM extracts + stores.")
print("  SummaryBuffer: recent verbatim + old summarized. Best for long chats.")
print("  Strategy: short-term for recent, long-term for factual recall, episodic for audit.")
print("=" * 60)
