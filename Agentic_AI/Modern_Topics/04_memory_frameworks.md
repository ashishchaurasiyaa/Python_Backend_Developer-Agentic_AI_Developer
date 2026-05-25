# Modern Topics — Doc 4: Memory Frameworks (Mem0, Zep)

> **Goal:** Persistent agent memory across sessions. Mem0 + Zep — production-grade memory.

---

## 1. The Memory Problem

LLMs are stateless. Each call:
- No memory of past conversations
- No knowledge of user preferences
- No learning from interactions

For chat agents to feel "alive", they need memory.

---

## 2. Memory Types

### Short-term (Conversation buffer)
- Last N messages
- In-memory or Redis
- Reset per session

### Long-term (Cross-session)
- User facts ("John works in finance")
- Preferences ("prefers concise answers")
- History summaries
- Persists across sessions

### Episodic
- Specific past conversations
- "Last week we discussed X"
- Vector DB

### Semantic
- General knowledge about user
- Knowledge graphs
- Neo4j-style

---

## 3. Mem0 (Most Popular Open-Source)

```bash
pip install mem0ai
```

```python
from mem0 import Memory

m = Memory()

# Add memories
m.add("I love Python and FastAPI", user_id="alice")
m.add("I'm working on an e-commerce project", user_id="alice")
m.add("I prefer concise code with type hints", user_id="alice")

# Search relevant memories
related = m.search("What does Alice like?", user_id="alice")
# Returns: ["I love Python and FastAPI", "I prefer concise code..."]

# Update
m.update(memory_id="...", data="I now use Django for newer projects")

# Delete
m.delete(memory_id="...")

# Get all for user
all_memories = m.get_all(user_id="alice")
```

---

## 4. Mem0 Integration with Agents

```python
def chat_with_memory(user_id, query):
    # 1. Retrieve relevant memories
    memories = m.search(query, user_id=user_id, limit=5)
    memory_text = "\n".join([f"- {mem['text']}" for mem in memories])
    
    # 2. Build prompt with memory context
    system = f"""You are a helpful assistant.

What you remember about this user:
{memory_text}"""
    
    # 3. Generate response
    response = llm.call(
        system=system,
        messages=[{"role": "user", "content": query}]
    )
    
    # 4. Extract and save new memories
    extracted = extract_facts_from_conversation(query, response)
    for fact in extracted:
        m.add(fact, user_id=user_id)
    
    return response
```

Mem0 auto-extracts facts. Or you can manually add.

---

## 5. Zep (Temporal Memory)

Focus on **time-aware** memory. Knows when things happened.

```python
from zep_python import ZepClient, Memory, Message

zep = ZepClient(api_key="...")

# Add memory
zep.memory.add_memory(
    session_id="user_alice_session_123",
    memory=Memory(
        messages=[
            Message(role="user", content="I love Python", role_type="user"),
            Message(role="assistant", content="Cool, what frameworks?", role_type="assistant")
        ]
    )
)

# Retrieve
session = zep.memory.get_memory(session_id="user_alice_session_123")
# Returns conversation history + summary
```

### Zep Features
- Auto-summarization of old messages
- Temporal queries ("what did user say last week?")
- Vector search across history
- Entity extraction
- Time decay (recent matters more)

---

## 6. Custom Memory System (DIY)

For full control, build your own:

```python
import redis
import json
from sentence_transformers import SentenceTransformer

class MemorySystem:
    def __init__(self):
        # Short-term: Redis (fast, ephemeral)
        self.short_term = redis.Redis()
        
        # Long-term: PostgreSQL + pgvector
        self.long_term_db = connect_postgres()
        
        # Embedder
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def add_short_term(self, session_id, message):
        """Add to current conversation buffer."""
        self.short_term.rpush(f"conv:{session_id}", json.dumps(message))
        self.short_term.expire(f"conv:{session_id}", 3600)  # 1hr TTL
    
    def get_short_term(self, session_id, n=10):
        """Last N messages."""
        msgs = self.short_term.lrange(f"conv:{session_id}", -n, -1)
        return [json.loads(m) for m in msgs]
    
    def add_long_term(self, user_id, fact):
        """Add persistent fact about user."""
        embedding = self.embedder.encode(fact).tolist()
        self.long_term_db.execute(
            "INSERT INTO user_facts (user_id, fact, embedding) VALUES (%s, %s, %s)",
            (user_id, fact, embedding)
        )
    
    def search_long_term(self, user_id, query, k=5):
        """Semantic search over user's facts."""
        q_emb = self.embedder.encode(query).tolist()
        results = self.long_term_db.execute(f"""
            SELECT fact FROM user_facts
            WHERE user_id = %s
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """, (user_id, q_emb, k))
        return [r[0] for r in results]
```

This pattern: **Redis (short) + PostgreSQL + pgvector (long)** is what most production systems do.

---

## 7. Memory Lifecycle

```
1. EXTRACT — From conversation, identify facts
   "I work at Google as a senior engineer" → fact: "user works at Google as senior engineer"

2. STORE — Save to memory layer
   Embed → store in vector DB

3. RETRIEVE — When relevant, retrieve
   New query: "Should I switch jobs?" → retrieve work facts

4. UPDATE — Facts change
   "I left Google last month" → update existing fact

5. DECAY — Old/irrelevant facts age out
   Time-based or relevance-based forgetting
```

---

## 8. Fact Extraction

```python
def extract_facts(conversation):
    prompt = f"""Extract facts about the user from this conversation.

Conversation:
{conversation}

Return JSON array of facts (one per fact):
["fact 1", "fact 2", ...]

Only include FACTS about the user (preferences, history, identity).
Skip questions, opinions, transient info."""
    
    return llm.call(prompt, json_mode=True)
```

Run after every conversation to populate memory.

---

## 9. Memory Search Strategies

### Recent + Relevant
```python
def smart_retrieve(query, user_id, k=10):
    # Recent messages (last hour)
    recent = redis.lrange(f"conv:{user_id}", -10, -1)
    
    # Semantically relevant from long-term
    relevant = search_pgvector(query, user_id, k=5)
    
    # Combine + dedupe
    return recent + relevant
```

### Time-weighted
```python
def time_weighted_retrieve(query, user_id):
    candidates = search(query, user_id, k=20)
    
    # Boost recent
    for c in candidates:
        age_days = (now - c.timestamp).days
        c.score = c.similarity * exp(-age_days / 30)  # Half-life 30 days
    
    return sorted(candidates, key=lambda x: -x.score)[:5]
```

---

## 10. Privacy + GDPR

User memories = personal data. Implications:
- **Right to delete**: implement `delete_user(user_id)`
- **Right to access**: implement `export_user_data(user_id)`
- **Encryption at rest**
- **Audit logs**
- **Retention policy** (auto-delete after X years)

```python
def delete_user_completely(user_id):
    # Delete short-term
    redis.delete(f"conv:{user_id}")
    
    # Delete long-term
    db.execute("DELETE FROM user_facts WHERE user_id = %s", (user_id,))
    db.execute("DELETE FROM user_episodes WHERE user_id = %s", (user_id,))
    
    # Audit log
    log_deletion(user_id)
```

---

## 11. Production Considerations

- **Cost**: every query embeds + searches DB. Cache hot users.
- **Latency**: memory retrieval adds ~50-100ms. Optimize.
- **Quality**: bad memories pollute responses. Validate facts.
- **Scale**: millions of users → sharding required.

---

## 12. Key Takeaways

✅ Memory = critical for "alive-feeling" agents
✅ Types: short-term, long-term, episodic, semantic
✅ Mem0 = easiest open-source framework
✅ Zep = temporal-aware memory
✅ DIY: Redis (short) + pgvector (long)
✅ Extract → store → retrieve → update → decay
✅ Privacy: implement delete + export
✅ Recent + relevant retrieval works well

**Next:** [05_multimodal_agents.md](05_multimodal_agents.md) — Vision + text + audio combined
