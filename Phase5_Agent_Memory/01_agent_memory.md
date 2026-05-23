# Agent Memory — Mem0, Zep, Redis/PostgreSQL Memory Systems

## Quick Concepts
- **Mem0** = AI memory layer — user preferences, facts, interaction history personalize karo
- **Zep** = LLM memory server — conversations, summaries, entities extract karke store karo
- **Episodic memory** = past interactions yaad karo — "last time you asked..."
- **Semantic memory** = facts aur knowledge — "user is a Python developer"
- **Working memory** = current context window — temporary, current task ke liye

---

## Interview Questions & Answers

### Q1: Mem0 — AI ko user-specific memory kaise dete hain?
**Answer:**
```python
# pip install mem0ai

from mem0 import Memory
import os

# Setup Mem0 with OpenAI (default)
m = Memory()

# Custom config with Qdrant + Claude
config = {
    "llm": {
        "provider": "anthropic",
        "config": {
            "model": "claude-sonnet-4-6",
            "temperature": 0.1,
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "user_memories",
            "host": "localhost",
            "port": 6333,
        }
    },
    "history_db_path": "./mem0_history.db",  # SQLite for history
}

m = Memory.from_config(config)

# ===== ADD MEMORIES =====

# From conversation
messages = [
    {"role": "user", "content": "Hi, I'm Ashish. I'm a Python developer at YAM."},
    {"role": "assistant", "content": "Nice to meet you, Ashish!"},
    {"role": "user", "content": "I prefer FastAPI over Django for new projects."},
]

m.add(messages, user_id="user_ashish_123")
# Mem0 automatically extracts:
# - "User's name is Ashish"
# - "Ashish works at YAM"
# - "Ashish is a Python developer"
# - "Ashish prefers FastAPI over Django"

# Add explicit facts
m.add("I'm learning LangGraph and LangChain", user_id="user_ashish_123")
m.add("My company uses PostgreSQL and Redis", user_id="user_ashish_123")

# ===== SEARCH MEMORIES =====
related_memories = m.search("technology preferences", user_id="user_ashish_123")

for memory in related_memories["results"]:
    print(f"Memory: {memory['memory']}")
    print(f"Score: {memory['score']:.3f}")
    print()

# ===== USE IN CHAT =====
from anthropic import Anthropic

anthropic_client = Anthropic()

def chat_with_memory(user_message: str, user_id: str) -> str:
    # 1. Retrieve relevant memories
    memories = m.search(user_message, user_id=user_id)
    
    memory_context = "\n".join([
        f"- {mem['memory']}"
        for mem in memories["results"][:5]  # top 5 relevant
    ])
    
    # 2. Build context-aware prompt
    system = f"""You are a personalized AI assistant.

What you remember about this user:
{memory_context}

Use this context to provide personalized responses."""
    
    # 3. Get response
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}]
    )
    
    assistant_reply = response.content[0].text
    
    # 4. Store new memories from this interaction
    m.add([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ], user_id=user_id)
    
    return assistant_reply

# Usage
response = chat_with_memory("What framework should I use for my new API?", "user_ashish_123")
# Will remember: Ashish prefers FastAPI, works at YAM, Python developer

# ===== MANAGE MEMORIES =====
# Get all memories for user
all_memories = m.get_all(user_id="user_ashish_123")
print(f"Total memories: {len(all_memories['results'])}")

# Update specific memory
memory_id = all_memories['results'][0]['id']
m.update(memory_id, "Ashish is now a Senior Python Developer at YAM")

# Delete memory
m.delete(memory_id)

# Clear all user memories
m.delete_all(user_id="user_ashish_123")
```

---

### Q2: Zep — conversation memory server kaise use karte hain?
**Answer:**
```python
# pip install zep-python
# Zep server: docker run -p 8000:8000 ghcr.io/getzep/zep:latest

from zep_python import ZepClient, Message, Memory
from zep_python.user import CreateUserRequest
from zep_python.session import CreateSessionRequest
import uuid

ZEP_API_URL = "http://localhost:8000"  # ya cloud: https://api.getzep.com
ZEP_API_KEY = "your-api-key"  # cloud ke liye

client = ZepClient(base_url=ZEP_API_URL, api_key=ZEP_API_KEY)

# ===== USER + SESSION SETUP =====

# User create karo
user_id = "ashish-123"
client.user.add(CreateUserRequest(
    user_id=user_id,
    email="ashish@yam.com",
    first_name="Ashish",
    metadata={"role": "developer", "company": "YAM"}
))

# Session (conversation thread) create karo
session_id = str(uuid.uuid4())
client.memory.add_session(CreateSessionRequest(
    session_id=session_id,
    user_id=user_id,
    metadata={"channel": "chat", "topic": "python_help"}
))

# ===== ADD MESSAGES =====
messages = [
    Message(role="human", content="Can you explain Python generators?", role_type="human"),
    Message(role="assistant", content="Generators use yield keyword for lazy evaluation...", role_type="assistant"),
    Message(role="human", content="I work with FastAPI mostly. Can you give a FastAPI example?", role_type="human"),
]

from zep_python.memory import Memory as ZepMemory

client.memory.add(session_id, ZepMemory(messages=messages))

# ===== RETRIEVE MEMORY =====
# Zep automatically:
# 1. Stores raw messages
# 2. Generates summaries
# 3. Extracts entities (people, places, facts)
# 4. Runs embedding for semantic search

# Get memory with context window
memory = client.memory.get(session_id, lastn=10)

print(f"Summary: {memory.summary.content if memory.summary else 'Not yet'}")
print(f"Facts: {[f.fact for f in memory.facts]}")
print(f"Messages: {len(memory.messages)}")

# Search memory semantically
search_results = client.memory.search_sessions(
    user_id=user_id,
    text="Python framework preferences",
    search_scope="facts",  # facts, messages, summary
    limit=5,
)

for result in search_results.results:
    print(f"Score {result.score:.3f}: {result.fact.fact if result.fact else result.message.content}")

# ===== INTEGRATE WITH LANGCHAIN =====
from langchain_community.memory import ZepCloudChatMessageHistory, ZepMemory as LangChainZep
from langchain.memory import ConversationBufferMemory

# ZepMemory as LangChain memory backend
zep_memory = LangChainZep(
    session_id=session_id,
    url=ZEP_API_URL,
    api_key=ZEP_API_KEY,
    memory_key="chat_history",
    return_messages=True,
    input_key="input",
)

# Use with LangChain chains
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory

model = ChatAnthropic(model="claude-sonnet-4-6")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

chain = prompt | model
chain_with_zep = RunnableWithMessageHistory(
    chain,
    lambda sid: ZepCloudChatMessageHistory(session_id=sid, url=ZEP_API_URL),
    input_messages_key="input",
    history_messages_key="chat_history",
)
```

---

### Q3: Redis-based memory — fast session storage kaise karte hain?
**Answer:**
```python
import redis.asyncio as aioredis
import json
from datetime import datetime
from typing import Optional
import uuid

class RedisAgentMemory:
    """Redis-backed agent memory with TTL"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl  # 1 hour default
    
    # ===== MESSAGE HISTORY =====
    async def add_message(self, session_id: str, role: str, content: str):
        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Sorted set: score = timestamp for ordering
        key = f"session:{session_id}:messages"
        await self.redis.zadd(
            key,
            {json.dumps(message): datetime.now().timestamp()}
        )
        await self.redis.expire(key, self.ttl)
    
    async def get_messages(self, session_id: str, last_n: int = 20) -> list[dict]:
        key = f"session:{session_id}:messages"
        # Get last N messages (highest scores)
        raw_messages = await self.redis.zrange(key, -last_n, -1)
        return [json.loads(m) for m in raw_messages]
    
    # ===== USER FACTS =====
    async def set_fact(self, user_id: str, fact_key: str, fact_value: str):
        key = f"user:{user_id}:facts"
        await self.redis.hset(key, fact_key, fact_value)
        await self.redis.expire(key, 86400 * 30)  # 30 days
    
    async def get_facts(self, user_id: str) -> dict:
        key = f"user:{user_id}:facts"
        return await self.redis.hgetall(key)
    
    # ===== SUMMARY CACHE =====
    async def cache_summary(self, session_id: str, summary: str):
        key = f"session:{session_id}:summary"
        await self.redis.setex(key, self.ttl, summary)
    
    async def get_summary(self, session_id: str) -> Optional[str]:
        key = f"session:{session_id}:summary"
        return await self.redis.get(key)
    
    # ===== CONTEXT BUILDER =====
    async def build_context(self, session_id: str, user_id: str) -> str:
        messages = await self.get_messages(session_id, last_n=10)
        facts = await self.get_facts(user_id)
        summary = await self.get_summary(session_id)
        
        context_parts = []
        
        if facts:
            facts_str = "\n".join([f"- {k}: {v}" for k, v in facts.items()])
            context_parts.append(f"User facts:\n{facts_str}")
        
        if summary:
            context_parts.append(f"Conversation summary:\n{summary}")
        
        if messages:
            recent = "\n".join([
                f"{m['role']}: {m['content'][:200]}"
                for m in messages[-5:]
            ])
            context_parts.append(f"Recent messages:\n{recent}")
        
        return "\n\n".join(context_parts)


# ===== POSTGRESQL LONG-TERM MEMORY =====
import asyncpg

class PostgresAgentMemory:
    """PostgreSQL-backed long-term memory with semantic search"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    async def initialize(self):
        """Create tables"""
        conn = await asyncpg.connect(self.db_url)
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
            
            CREATE TABLE IF NOT EXISTS agent_memories (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                session_id VARCHAR(255),
                memory_type VARCHAR(50),    -- 'fact', 'preference', 'interaction'
                content TEXT NOT NULL,
                embedding vector(1536),
                importance FLOAT DEFAULT 0.5,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                metadata JSONB DEFAULT '{}'
            );
            
            CREATE INDEX IF NOT EXISTS memories_user_idx ON agent_memories(user_id);
            CREATE INDEX IF NOT EXISTS memories_embedding_idx 
                ON agent_memories USING ivfflat(embedding vector_cosine_ops)
                WITH (lists = 100);
        """)
        await conn.close()
    
    async def store_memory(
        self, 
        user_id: str, 
        content: str, 
        memory_type: str,
        embedding: list[float],
        importance: float = 0.5,
        session_id: str = None,
    ):
        conn = await asyncpg.connect(self.db_url)
        await conn.execute("""
            INSERT INTO agent_memories 
            (user_id, session_id, memory_type, content, embedding, importance)
            VALUES ($1, $2, $3, $4, $5::vector, $6)
        """, user_id, session_id, memory_type, content, embedding, importance)
        await conn.close()
    
    async def recall_relevant(
        self, 
        user_id: str, 
        query_embedding: list[float], 
        limit: int = 5,
        memory_type: str = None,
    ) -> list[dict]:
        conn = await asyncpg.connect(self.db_url)
        
        filter_clause = "AND memory_type = $4" if memory_type else ""
        params = [user_id, query_embedding, limit]
        if memory_type:
            params.append(memory_type)
        
        rows = await conn.fetch(f"""
            SELECT content, memory_type, importance, created_at,
                   1 - (embedding <=> $2::vector) as similarity
            FROM agent_memories
            WHERE user_id = $1
              {filter_clause}
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY 
                importance * (1 - (embedding <=> $2::vector)) DESC
            LIMIT $3
        """, *params)
        
        await conn.close()
        return [dict(r) for r in rows]
```

---

### Q4: Memory types summary aur interview common questions?
**Answer:**
```
MEMORY TAXONOMY FOR AI AGENTS:

1. WORKING MEMORY (Current context)
   - LLM context window: 200K tokens (Claude), 128K (GPT-4o)
   - Contains: Current messages, retrieved docs, tool results
   - Lifetime: Single invocation
   - Storage: RAM (LLM context)

2. EPISODIC MEMORY (Past experiences)
   - What happened in past conversations
   - Storage: Zep, Redis Sorted Sets, PostgreSQL
   - Retrieval: By session_id, user_id, recency
   - Example: "Last week you asked about FastAPI rate limiting"

3. SEMANTIC MEMORY (Facts and knowledge)
   - User facts, preferences, entities
   - Storage: Mem0, Vector DB + PostgreSQL
   - Retrieval: Semantic search on query
   - Example: "User prefers FastAPI, works at YAM"

4. PROCEDURAL MEMORY (How to do things)
   - In model weights (fine-tuning)
   - Or: Stored prompt templates, workflows
   - Example: "For this user, always respond in Hindi"

INTERVIEW QUESTIONS:

Q: Memory overflow kaise handle karte hain?
A: 
  - Sliding window: keep last N messages
  - Summarization: old messages ko summarize karo
  - Importance scoring: high-importance memories keep, low discard
  - TTL: time-based expiry for old facts

Q: Multi-user memory isolation kaise karte hain?
A:
  - user_id ke basis par store karo (namespace)
  - Redis: key prefix "user:{user_id}:..."
  - PostgreSQL: WHERE user_id = $1 always
  - Vector DB: metadata filter {"user_id": "123"}

Q: Mem0 vs Zep — kab kya?
A:
  Mem0: Personalization — user preferences, facts auto-extract
  Zep: Conversation history — summaries, entities, semantic search
  Use both together: Zep for conversations, Mem0 for user profile

Q: Memory consistency kaise maintain kare across sessions?
A:
  - PostgreSQL as source of truth (persistent)
  - Redis as cache (fast, with TTL)
  - On session start: load from PostgreSQL into Redis
  - On update: write-through (update both)
  - Periodic sync: Redis → PostgreSQL flush
```
