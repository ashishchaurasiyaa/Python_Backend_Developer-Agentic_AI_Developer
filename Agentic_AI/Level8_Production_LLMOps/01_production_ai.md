# Production AI Systems — Observability, Guardrails, Semantic Caching, Cost Monitoring

## Quick Concepts
- **Observability** = LLM calls trace karo — latency, tokens, cost, errors — LangSmith/Langfuse
- **Guardrails** = input/output validate karo — harmful content, PII, hallucination detect
- **Semantic Caching** = similar queries ka cached response return karo — cost 60-80% reduce
- **Cost monitoring** = per-user/per-feature spend track karo — budget alerts
- **A/B testing** = different prompts compare karo — systematically improve quality

---

## Interview Questions & Answers

### Q1: LangSmith + Langfuse — LLM observability kaise karte hain?
**Answer:**
```python
# ===== LANGSMITH =====
# pip install langsmith langchain-anthropic

import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls__..."
os.environ["LANGCHAIN_PROJECT"] = "my-rag-app"

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

# Once env vars set, ALL langchain calls auto-traced
model = ChatAnthropic(model="claude-sonnet-4-6")
result = model.invoke("What is Python?")  # Automatically logged to LangSmith!

# Manual tracing for non-LangChain code
from langsmith import traceable, Client

client = Client()

@traceable(name="classify_support_ticket", run_type="llm")
def classify_ticket(ticket_text: str) -> dict:
    from anthropic import Anthropic
    ant_client = Anthropic()
    
    response = ant_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": f"Classify: {ticket_text}\nReturn: TECHNICAL/BILLING/GENERAL"}]
    )
    return {"category": response.content[0].text, "tokens": response.usage.input_tokens}

# Add metadata to traces
from langsmith import trace

with trace("rag_pipeline", metadata={"user_id": "user-123", "session": "sess-456"}):
    docs = retriever.invoke("query")     # Both calls grouped under same trace
    answer = model.invoke(f"Context: {docs}\nQuestion: query")

# ===== LANGFUSE =====
# pip install langfuse
# docker compose up (self-hosted) or langfuse.com (cloud)

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="https://cloud.langfuse.com",
)

# Decorator-based tracing
@observe(name="rag_answer")
def rag_answer(question: str, user_id: str) -> str:
    # Auto-tracked: function name, inputs, outputs, duration
    
    # Manual span karo sub-operation ke liye
    langfuse_context.update_current_observation(
        user_id=user_id,
        metadata={"question_length": len(question)}
    )
    
    docs = retriever.invoke(question)
    
    with langfuse.span(name="llm_call") as span:
        response = model.invoke(f"Context: {docs}\n{question}")
        span.update(
            output=response.content,
            usage={"input": 100, "output": 50}
        )
    
    return response.content

# Track scores (quality feedback)
@observe
def answer_with_feedback(question: str) -> dict:
    answer = rag_answer(question, "user-123")
    
    # Log quality score
    langfuse_context.score_current_trace(
        name="answer_quality",
        value=0.9,
        comment="Answer was relevant and accurate"
    )
    
    return {"answer": answer}

# Prompt management in Langfuse
prompt = langfuse.get_prompt("rag-system-prompt")
# Prompts versioned in Langfuse UI — no code deploy needed for prompt changes
compiled = prompt.compile(context="...", question="...")

# ===== CUSTOM OBSERVABILITY =====
import time
import asyncio
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class LLMCallMetric:
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    user_id: str
    feature: str
    success: bool
    error: Optional[str] = None

async def tracked_llm_call(
    messages: list,
    model: str,
    user_id: str,
    feature: str,
) -> tuple[str, LLMCallMetric]:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    
    start = time.time()
    error = None
    response_text = ""
    
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=messages,
        )
        response_text = response.content[0].text
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        
    except Exception as e:
        error = str(e)
        prompt_tokens = completion_tokens = 0
    
    latency = (time.time() - start) * 1000
    
    # Cost calculation
    PRICING = {
        "claude-haiku-4-5-20251001": (0.25, 1.25),   # per 1M tokens (input, output)
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-opus-4-7": (15.0, 75.0),
    }
    input_price, output_price = PRICING.get(model, (3.0, 15.0))
    cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
    
    metric = LLMCallMetric(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency,
        cost_usd=cost,
        user_id=user_id,
        feature=feature,
        success=error is None,
        error=error,
    )
    
    # Log to your metrics store (PostgreSQL, InfluxDB, etc.)
    print(f"[Metric] {feature} | {model} | {latency:.0f}ms | ${cost:.6f} | {user_id}")
    
    return response_text, metric
```

---

### Q2: Guardrails — harmful content aur PII kaise detect karte hain?
**Answer:**
```python
# pip install guardrails-ai presidio-analyzer presidio-anonymizer

from enum import Enum
from pydantic import BaseModel
import re

# ===== CUSTOM GUARDRAILS =====

class GuardrailResult(BaseModel):
    allowed: bool
    reason: str = ""
    sanitized_input: str = ""

class InputGuardrails:
    """Input validation before sending to LLM"""
    
    MAX_LENGTH = 10000
    
    # PII patterns (basic — use Presidio for production)
    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+91[-\s]?)?[6-9]\d{9}\b',
        "aadhar": r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    }
    
    BLOCKED_PATTERNS = [
        r'(?i)\b(bomb|weapon|hack|exploit|malware)\b',
        r'(?i)(how to (kill|harm|hurt|attack))',
    ]
    
    def validate(self, text: str) -> GuardrailResult:
        # Length check
        if len(text) > self.MAX_LENGTH:
            return GuardrailResult(
                allowed=False,
                reason=f"Input too long ({len(text)} chars, max {self.MAX_LENGTH})"
            )
        
        # Harmful content check
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, text):
                return GuardrailResult(allowed=False, reason="Potentially harmful content detected")
        
        # PII detection + redaction
        sanitized = text
        found_pii = []
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, sanitized)
            if matches:
                found_pii.append(pii_type)
                sanitized = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", sanitized)
        
        return GuardrailResult(
            allowed=True,
            sanitized_input=sanitized,
            reason=f"PII redacted: {found_pii}" if found_pii else "OK"
        )

class OutputGuardrails:
    """Output validation after LLM response"""
    
    def validate(self, response: str, context: str = "") -> GuardrailResult:
        # Hallucination detection (simple keyword check)
        hallucination_signals = [
            "I don't have access",
            "as of my knowledge cutoff",
            "I'm not sure but",
            "I think it might be",
        ]
        
        for signal in hallucination_signals:
            if signal.lower() in response.lower():
                return GuardrailResult(
                    allowed=True,
                    reason=f"Possible hallucination signal: '{signal}'"
                )
        
        # Length check (too short = likely failed)
        if len(response) < 10:
            return GuardrailResult(allowed=False, reason="Response too short — likely failed")
        
        return GuardrailResult(allowed=True, reason="OK")

# ===== PRESIDIO PII (Production-grade) =====
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def anonymize_pii(text: str, language: str = "en") -> tuple[str, list]:
    """Detect and anonymize PII using Presidio"""
    results = analyzer.analyze(
        text=text,
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "PERSON", "LOCATION"],
        language=language,
    )
    
    if results:
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        found_entities = [r.entity_type for r in results]
        return anonymized.text, found_entities
    
    return text, []

# ===== NEMO GUARDRAILS (Nvidia) =====
# pip install nemoguardrails

# config.yml
NEMO_CONFIG = """
models:
  - type: main
    engine: anthropic
    model: claude-sonnet-4-6

rails:
  input:
    flows:
      - check_jailbreak
      - check_sensitive_data

  output:
    flows:
      - check_hallucination
      - check_toxicity
"""

# colang flows (config/flows.co)
COLANG_FLOWS = """
define flow check_jailbreak
  user ask jailbreak
  bot refuse jailbreak

define bot refuse jailbreak
  "I can't help with that. Please ask appropriate questions."

define flow check_sensitive_data
  user provide sensitive data
  bot refuse sensitive data
"""

# ===== FULL PIPELINE WITH GUARDRAILS =====
async def safe_llm_call(user_input: str, user_id: str) -> dict:
    input_guard = InputGuardrails()
    output_guard = OutputGuardrails()
    
    # 1. Validate input
    input_check = input_guard.validate(user_input)
    if not input_check.allowed:
        return {"error": input_check.reason, "blocked": True}
    
    # 2. Use sanitized input
    safe_input = input_check.sanitized_input or user_input
    
    # 3. LLM call
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": safe_input}]
    )
    output = response.content[0].text
    
    # 4. Validate output
    output_check = output_guard.validate(output, context=safe_input)
    
    return {
        "response": output,
        "blocked": False,
        "pii_found": input_check.reason if "PII" in input_check.reason else None,
        "output_quality": output_check.reason,
    }
```

---

### Q3: Semantic Caching — similar queries cache kaise karte hain?
**Answer:**
```python
import hashlib
import json
import numpy as np
from openai import OpenAI
import redis.asyncio as aioredis
from typing import Optional

openai_client = OpenAI()
redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)

class SemanticCache:
    """
    Cache LLM responses based on semantic similarity.
    Instead of exact match, find similar past queries.
    60-80% cache hit rate typical for production chatbots.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.95,
        ttl: int = 3600,
        max_cache_size: int = 10000,
    ):
        self.threshold = similarity_threshold
        self.ttl = ttl
        self.max_cache_size = max_cache_size
        self._cache: list[dict] = []  # In-memory index (use Qdrant in production)
    
    def _get_embedding(self, text: str) -> list[float]:
        response = openai_client.embeddings.create(
            input=text, model="text-embedding-3-small"
        )
        return response.data[0].embedding
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        a_arr, b_arr = np.array(a), np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))
    
    async def get(self, query: str) -> Optional[str]:
        """Find semantically similar cached response"""
        query_embedding = self._get_embedding(query)
        
        best_match = None
        best_score = 0.0
        
        for entry in self._cache:
            score = self._cosine_similarity(query_embedding, entry["embedding"])
            if score > best_score:
                best_score = score
                best_match = entry
        
        if best_score >= self.threshold and best_match:
            # Check Redis TTL
            cached = await redis_client.get(f"semantic_cache:{best_match['key']}")
            if cached:
                print(f"[Cache HIT] score={best_score:.3f}, query='{query[:50]}'")
                return json.loads(cached)["response"]
            else:
                # Expired in Redis, remove from index
                self._cache = [e for e in self._cache if e["key"] != best_match["key"]]
        
        print(f"[Cache MISS] best_score={best_score:.3f}")
        return None
    
    async def set(self, query: str, response: str):
        """Cache query + response"""
        embedding = self._get_embedding(query)
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        # Store in Redis
        await redis_client.setex(
            f"semantic_cache:{cache_key}",
            self.ttl,
            json.dumps({"query": query, "response": response})
        )
        
        # Update in-memory embedding index
        self._cache.append({"key": cache_key, "query": query, "embedding": embedding})
        
        # Evict old entries
        if len(self._cache) > self.max_cache_size:
            self._cache = self._cache[-self.max_cache_size:]
    
    async def get_stats(self) -> dict:
        keys = await redis_client.keys("semantic_cache:*")
        return {
            "cached_responses": len(keys),
            "index_size": len(self._cache),
            "threshold": self.threshold,
        }

# ===== USE IN APPLICATION =====
semantic_cache = SemanticCache(similarity_threshold=0.92)

async def cached_llm_call(query: str, model: str = "claude-sonnet-4-6") -> str:
    # 1. Check semantic cache
    cached = await semantic_cache.get(query)
    if cached:
        return cached
    
    # 2. Cache miss — call LLM
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": query}]
    )
    result = response.content[0].text
    
    # 3. Cache the result
    await semantic_cache.set(query, result)
    
    return result

# GPTCache library (alternative)
# pip install gptcache
from gptcache import cache
from gptcache.adapter import openai

cache.init(
    pre_embedding_func=lambda x: x["messages"][-1]["content"],
    embedding_func=lambda x, **kwargs: openai_client.embeddings.create(input=x, model="text-embedding-3-small").data[0].embedding,
)
# Now openai.ChatCompletion.create() automatically uses cache
```

---

### Q4: Cost Monitoring — per-user aur per-feature spend track karna?
**Answer:**
```python
import asyncpg
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import asyncio

# ===== COST TRACKING SCHEMA =====
CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    feature VARCHAR(100),
    model VARCHAR(100),
    prompt_tokens INT,
    completion_tokens INT,
    cost_usd DECIMAL(10, 8),
    latency_ms INT,
    success BOOLEAN,
    error_type VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS llm_usage_user_idx ON llm_usage(user_id, created_at);
CREATE INDEX IF NOT EXISTS llm_usage_feature_idx ON llm_usage(feature, created_at);
CREATE INDEX IF NOT EXISTS llm_usage_cost_idx ON llm_usage(cost_usd, created_at);
"""

# Model pricing (per 1M tokens)
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    "claude-opus-4-7":           {"input": 15.00, "output": 75.00},
    "gpt-4o":                    {"input": 5.00, "output": 15.00},
    "gpt-4o-mini":               {"input": 0.15, "output": 0.60},
}

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000

class CostMonitor:
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    async def log_usage(
        self,
        user_id: str,
        feature: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        success: bool,
        error_type: str = None,
        metadata: dict = None,
    ):
        cost = calculate_cost(model, prompt_tokens, completion_tokens)
        
        conn = await asyncpg.connect(self.db_url)
        await conn.execute("""
            INSERT INTO llm_usage
            (user_id, feature, model, prompt_tokens, completion_tokens,
             cost_usd, latency_ms, success, error_type, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """, user_id, feature, model, prompt_tokens, completion_tokens,
            cost, latency_ms, success, error_type, metadata or {})
        await conn.close()
    
    async def get_user_spend(self, user_id: str, days: int = 30) -> dict:
        conn = await asyncpg.connect(self.db_url)
        
        row = await conn.fetchrow("""
            SELECT
                SUM(cost_usd) AS total_cost,
                SUM(prompt_tokens + completion_tokens) AS total_tokens,
                COUNT(*) AS total_calls,
                AVG(latency_ms) AS avg_latency_ms,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) AS errors
            FROM llm_usage
            WHERE user_id = $1 AND created_at > NOW() - INTERVAL '$2 days'
        """, user_id, days)
        
        await conn.close()
        return dict(row) if row else {}
    
    async def get_feature_costs(self, days: int = 7) -> list[dict]:
        conn = await asyncpg.connect(self.db_url)
        
        rows = await conn.fetch("""
            SELECT
                feature,
                SUM(cost_usd) AS total_cost,
                COUNT(*) AS calls,
                AVG(cost_usd) AS avg_cost_per_call,
                AVG(latency_ms) AS avg_latency
            FROM llm_usage
            WHERE created_at > NOW() - INTERVAL '$1 days'
            GROUP BY feature
            ORDER BY total_cost DESC
        """, days)
        
        await conn.close()
        return [dict(r) for r in rows]
    
    async def check_budget_alert(self, user_id: str, daily_budget_usd: float) -> bool:
        """Return True if user exceeded daily budget"""
        conn = await asyncpg.connect(self.db_url)
        
        row = await conn.fetchrow("""
            SELECT SUM(cost_usd) AS today_cost
            FROM llm_usage
            WHERE user_id = $1 AND created_at > NOW() - INTERVAL '1 day'
        """, user_id)
        
        await conn.close()
        today_cost = float(row["today_cost"] or 0)
        
        if today_cost > daily_budget_usd:
            print(f"⚠️  Budget alert: {user_id} spent ${today_cost:.4f} (budget: ${daily_budget_usd})")
            return True
        return False
```

---

### Q5: A/B Testing Prompts — systematically improve karna?
**Answer:**
```python
import random
import hashlib
from typing import Literal

# ===== PROMPT VARIANTS =====
PROMPT_VARIANTS = {
    "v1_concise": {
        "system": "You are a helpful assistant. Be concise.",
        "weight": 0.5,
    },
    "v2_detailed": {
        "system": "You are an expert assistant. Provide detailed, step-by-step answers with examples.",
        "weight": 0.3,
    },
    "v3_structured": {
        "system": """You are an expert assistant. Format answers as:
1. Direct answer (1 sentence)
2. Explanation
3. Example""",
        "weight": 0.2,
    }
}

def select_variant(user_id: str) -> str:
    """Deterministic variant selection — same user always gets same variant"""
    # Hash user_id for consistent assignment
    hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
    
    cumulative = 0
    for variant_name, config in PROMPT_VARIANTS.items():
        cumulative += config["weight"] * 100
        if hash_val < cumulative:
            return variant_name
    
    return list(PROMPT_VARIANTS.keys())[0]

async def ab_test_call(user_id: str, question: str) -> dict:
    variant = select_variant(user_id)
    system_prompt = PROMPT_VARIANTS[variant]["system"]
    
    from anthropic import AsyncAnthropic
    import time
    client = AsyncAnthropic()
    
    start = time.time()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": question}]
    )
    latency = (time.time() - start) * 1000
    
    # Log for analysis
    print(f"[A/B] user={user_id} variant={variant} latency={latency:.0f}ms")
    
    return {
        "answer": response.content[0].text,
        "variant": variant,
        "latency_ms": latency,
    }

# Analyze results (after collecting data)
ANALYSIS_QUERY = """
SELECT
    metadata->>'variant' AS variant,
    COUNT(*) AS calls,
    AVG((metadata->>'user_rating')::float) AS avg_rating,
    AVG(latency_ms) AS avg_latency,
    AVG(prompt_tokens + completion_tokens) AS avg_tokens
FROM llm_usage
WHERE feature = 'ab_test_chat'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY variant
ORDER BY avg_rating DESC;
"""
# Run query → pick best variant → set as default
```
