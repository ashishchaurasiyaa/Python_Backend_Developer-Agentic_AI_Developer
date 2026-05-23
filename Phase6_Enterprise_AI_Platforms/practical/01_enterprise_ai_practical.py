"""
Phase6_Enterprise_AI_Platforms — Complete Practical
====================================================
Topics:
  1. Enterprise AI architecture patterns
  2. Multi-tenant LLM platform design
  3. Model registry + deployment
  4. A/B testing for LLM applications
  5. LLMOps pipeline (MLflow / LangSmith)
  6. Compliance: data residency, audit logging, PII
  7. Cost optimization strategies

Install: pip install mlflow langchain-openai
Run: python 01_enterprise_ai_practical.py
"""

import os, json, time, hashlib, uuid, re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

print("=" * 60)
print("ENTERPRISE AI PLATFORM CONCEPTS")
print("=" * 60)

ENTERPRISE_CONCEPTS = {
    "Multi-tenancy":      "Isolated LLM access per team/product with separate keys + billing",
    "Model registry":     "Central catalog of available models + versions + metadata",
    "LLMOps":             "ML Ops for LLM: version prompts, track experiments, monitor drift",
    "A/B testing":        "Compare prompt/model variants on real traffic with metrics",
    "Audit logging":      "Who called what with what input/output — compliance requirement",
    "PII protection":     "Detect/redact before LLM, re-inject after — GDPR/CCPA compliance",
    "Cost governance":    "Per-team/product budgets, chargebacks, optimization",
    "Data residency":     "LLM API region selection — EU data stays in EU (AWS Frankfurt, etc.)",
    "Shadow mode":        "New model receives real traffic but response not shown to user",
}
for k, v in ENTERPRISE_CONCEPTS.items():
    print(f"  {k:<18}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Multi-tenant LLM Platform
# INTERVIEW: Central gateway with per-tenant isolation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Multi-tenant Architecture")
print("=" * 60)

MULTITENANT_CODE = '''\
# Architecture: Central AI Gateway
#
#   Team A ──→ AI Gateway ──→ LiteLLM Router ──→ OpenAI
#   Team B ──→ AI Gateway ──→ LiteLLM Router ──→ Anthropic
#   Team C ──→ AI Gateway ──→ LiteLLM Router ──→ Azure OpenAI
#                  │
#                  ├─ Auth + API Keys
#                  ├─ Rate limits per team
#                  ├─ Cost tracking per team
#                  ├─ Audit logging
#                  └─ PII scrubbing

from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class Tenant:
    id:             str
    name:           str
    tier:           str        # "free", "starter", "enterprise"
    monthly_budget: float      # USD
    allowed_models: list[str]
    data_region:    str        # "us", "eu", "ap"
    pii_scrubbing:  bool = True
    audit_required: bool = True

@dataclass
class TenantUsage:
    tenant_id:    str
    month:        str           # "2025-05"
    total_cost:   float = 0.0
    total_requests: int = 0
    total_tokens: int = 0

class AIGateway:
    """
    INTERVIEW: Central AI gateway enforces:
    1. Authentication (API key → tenant)
    2. Model allowlist (tenant can only use approved models)
    3. Rate limiting (per-tenant RPM/TPM)
    4. Budget enforcement (stop requests when budget exceeded)
    5. PII scrubbing (before send to LLM)
    6. Audit logging (all requests + responses)
    7. Cost tracking (per-tenant, per-model)
    """
    def __init__(self, tenants: dict, litellm_router):
        self.tenants = tenants
        self.router  = litellm_router

    async def call(self, api_key: str, model: str, messages: list, **kwargs) -> dict:
        # 1. Authenticate
        tenant = self._authenticate(api_key)
        if not tenant:
            raise AuthError("Invalid API key")

        # 2. Check model allowlist
        if model not in tenant.allowed_models:
            raise PermissionError(f"Model {model} not allowed for {tenant.name}")

        # 3. Route to correct region
        regional_model = f"{tenant.data_region}/{model}"

        # 4. Check budget
        usage = self._get_usage(tenant.id)
        if usage.total_cost >= tenant.monthly_budget:
            raise BudgetExceededError(f"Monthly budget ${tenant.monthly_budget} exhausted")

        # 5. PII scrubbing
        if tenant.pii_scrubbing:
            messages = self._scrub_pii(messages)

        # 6. Call LLM
        start    = time.time()
        response = await self.router.acompletion(model=regional_model, messages=messages)
        latency  = time.time() - start

        # 7. Audit log
        if tenant.audit_required:
            self._audit_log(tenant.id, model, messages, response, latency)

        # 8. Track cost
        cost = litellm.completion_cost(response)
        self._record_cost(tenant.id, cost, response.usage)

        return response

    def _scrub_pii(self, messages: list) -> list:
        """Redact PII before sending to LLM."""
        pii_patterns = {
            "email": (r"[\\w.%+\\-]+@[\\w.\\-]+\\.[A-Za-z]{2,}", "[EMAIL]"),
            "phone": (r"\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b",  "[PHONE]"),
            "ssn":   (r"\\b\\d{3}-\\d{2}-\\d{4}\\b",                   "[SSN]"),
        }
        scrubbed = []
        for msg in messages:
            content = msg["content"]
            for _, (pattern, replacement) in pii_patterns.items():
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            scrubbed.append({**msg, "content": content})
        return scrubbed
'''
print(MULTITENANT_CODE[:900])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: LLMOps with MLflow
# INTERVIEW: Track experiments, prompts, metrics
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: LLMOps with MLflow")
print("=" * 60)

MLFLOW_CODE = '''\
import mlflow
import mlflow.langchain

# ── Track LLM experiments ──────────────────────────────────────
# INTERVIEW: MLflow for LLMs tracks: prompts, model params, eval metrics
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("rag-pipeline-v2")

with mlflow.start_run(run_name="gpt4o-mini-cohere-rerank"):
    # Log parameters
    mlflow.log_params({
        "llm_model":         "gpt-4o-mini",
        "embedding_model":   "text-embedding-3-small",
        "chunk_size":        1000,
        "chunk_overlap":     200,
        "retrieval_k":       5,
        "reranker":          "cohere",
        "temperature":       0.1,
    })

    # Log prompt template
    mlflow.log_text(rag_prompt.format(), "prompt_template.txt")

    # Run evaluation
    metrics = evaluate_rag_pipeline(rag_chain, eval_dataset)

    # Log metrics
    mlflow.log_metrics({
        "faithfulness":         metrics["faithfulness"],
        "answer_relevancy":     metrics["answer_relevancy"],
        "context_precision":    metrics["context_precision"],
        "avg_latency_ms":       metrics["avg_latency_ms"],
        "cost_per_query_usd":   metrics["cost_per_query_usd"],
    })

    # Log artifacts
    mlflow.log_artifact("eval_results.csv")
    mlflow.langchain.log_model(rag_chain, "model")

# ── Compare runs ───────────────────────────────────────────────
import mlflow.tracking

client = mlflow.tracking.MlflowClient()
runs   = client.search_runs(
    experiment_ids = [experiment.experiment_id],
    order_by       = ["metrics.faithfulness DESC"],
)
best_run = runs[0]
print(f"Best run: {best_run.info.run_id}")
print(f"Faithfulness: {best_run.data.metrics['faithfulness']:.3f}")

# ── Model registry ─────────────────────────────────────────────
mlflow.register_model(
    model_uri   = f"runs:/{best_run.info.run_id}/model",
    name        = "rag-pipeline",
)
# Transition to production
client.transition_model_version_stage(
    name    = "rag-pipeline",
    version = "3",
    stage   = "Production",
)
# Load production model
prod_model = mlflow.langchain.load_model("models:/rag-pipeline/Production")
'''
print(MLFLOW_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: A/B Testing LLM Applications
# INTERVIEW: Compare prompt/model variants on real traffic
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: A/B Testing")
print("=" * 60)

AB_TEST_CODE = '''\
import random, hashlib
from dataclasses import dataclass

@dataclass
class Variant:
    name:        str
    weight:      float           # traffic share (0.0-1.0)
    model:       str
    prompt:      str
    temperature: float

# ── Define variants ────────────────────────────────────────────
variants = [
    Variant("control",   weight=0.5, model="gpt-4o-mini",  prompt=PROMPT_V1, temperature=0.7),
    Variant("treatment", weight=0.5, model="gpt-4o-mini",  prompt=PROMPT_V2, temperature=0.3),
]

def assign_variant(user_id: str) -> Variant:
    """
    INTERVIEW: Consistent assignment — same user always gets same variant.
    Use hash of user_id for determinism.
    """
    # Hash ensures: user "alice" always gets same variant across requests
    bucket = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100 / 100.0
    cumulative = 0.0
    for variant in variants:
        cumulative += variant.weight
        if bucket < cumulative:
            return variant
    return variants[-1]

# ── Log A/B results ────────────────────────────────────────────
def log_ab_result(user_id: str, variant: str, metrics: dict):
    """Log to your analytics system (Mixpanel, Amplitude, BigQuery, etc.)"""
    analytics.track(user_id, "llm_response", {
        "variant":        variant,
        "session_id":     metrics["session_id"],
        "latency_ms":     metrics["latency_ms"],
        "user_rating":    metrics.get("user_rating"),     # if collected
        "task_completed": metrics.get("task_completed"),  # if measurable
        "tokens_used":    metrics["tokens"],
        "cost_usd":       metrics["cost"],
    })

# ── Statistical significance test ─────────────────────────────
from scipy import stats

# After collecting enough data:
control_ratings   = [4.2, 4.5, 3.8, 4.1, ...]   # user ratings for control
treatment_ratings = [4.6, 4.8, 4.3, 4.7, ...]   # user ratings for treatment

t_stat, p_value = stats.ttest_ind(control_ratings, treatment_ratings)
if p_value < 0.05:  # 95% confidence
    print(f"Treatment is significantly better (p={p_value:.4f})")
    promote_variant("treatment")
'''
print(AB_TEST_CODE[:700])


# Mock A/B assignment demo
def assign_variant(user_id: str, variants: List[Dict]) -> Dict:
    """Deterministic variant assignment based on user_id hash."""
    bucket = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100 / 100.0
    cumulative = 0.0
    for v in variants:
        cumulative += v["weight"]
        if bucket < cumulative:
            return v
    return variants[-1]


variants = [
    {"name": "control",   "weight": 0.5, "prompt": "v1"},
    {"name": "treatment", "weight": 0.5, "prompt": "v2"},
]
print("\n  A/B variant assignment (deterministic by user_id):")
test_users = ["alice", "bob", "charlie", "dave", "eve", "frank"]
for uid in test_users:
    v = assign_variant(uid, variants)
    print(f"  {uid:<10} → {v['name']} (prompt {v['prompt']})")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Cost Optimization
# INTERVIEW: How to reduce LLM costs in production
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Cost Optimization Strategies")
print("=" * 60)

COST_STRATEGIES = {
    "Model routing":       "Use cheap model (gpt-4o-mini) for simple queries, GPT-4 for complex",
    "Prompt compression":  "Summarize long contexts before sending. LLMLingua: 5-20x compression",
    "Semantic caching":    "Cache similar queries. Typical: 30-60% cache hit rate",
    "Batching":            "Batch N independent requests in one API call",
    "Prompt caching":      "Claude: cache_control:ephemeral for 90% discount on repeated context",
    "Output length control":"Set max_tokens tight. Shorter = cheaper.",
    "Few-shot examples":   "Cached few-shot examples → token reuse across requests",
    "Quantized models":    "Self-hosted quantized model (4-bit) for high-volume simple tasks",
}
for strategy, desc in COST_STRATEGIES.items():
    print(f"  {strategy:<22}: {desc}")

COST_ROUTING_CODE = '''\
from enum import Enum

class QueryComplexity(str, Enum):
    SIMPLE  = "simple"    # gpt-4o-mini → $0.60/1M out tokens
    MEDIUM  = "medium"    # gpt-4o      → $15/1M out tokens
    COMPLEX = "complex"   # claude-opus → $75/1M out tokens

def classify_query_complexity(query: str, chat_history: list) -> QueryComplexity:
    """
    INTERVIEW: Route to cheaper model when possible.
    Simple: short Q, no history, clear answer expected
    Complex: long Q, multi-step reasoning, code generation
    """
    words   = len(query.split())
    has_code= any(kw in query.lower() for kw in ["code", "implement", "debug", "write"])
    is_long = len(query) > 500

    if has_code or is_long or len(chat_history) > 10:
        return QueryComplexity.COMPLEX
    if words < 20 and not has_code:
        return QueryComplexity.SIMPLE
    return QueryComplexity.MEDIUM

MODEL_MAP = {
    QueryComplexity.SIMPLE:  "gpt-4o-mini",
    QueryComplexity.MEDIUM:  "gpt-4o",
    QueryComplexity.COMPLEX: "claude-sonnet-4-5",
}

def route_query(query: str, history: list) -> str:
    complexity = classify_query_complexity(query, history)
    model      = MODEL_MAP[complexity]
    metrics.increment("model_route", tags={"model": model, "complexity": complexity})
    return model
'''
print(COST_ROUTING_CODE[:600])


print("\n  Cost comparison at 1M queries/month:")
QUERY_MIX = [
    ("Simple (60%)", 600_000, 200, 100, "gpt-4o-mini"),
    ("Medium (30%)", 300_000, 1000, 500, "gpt-4o"),
    ("Complex (10%)", 100_000, 4000, 2000, "gpt-4o"),
]
total_cost = 0.0
for desc, count, inp, out, model in QUERY_MIX:
    pricing = {"gpt-4o-mini": (0.15, 0.60), "gpt-4o": (5.0, 15.0)}
    ip, op  = pricing[model]
    cost    = count * (inp * ip + out * op) / 1_000_000
    total_cost += cost
    print(f"  {desc:<20} {count:>10} reqs × {model}: ${cost:,.0f}/mo")
print(f"  {'Total':<20} {'':>10}             ${total_cost:,.0f}/mo")


print("\n" + "=" * 60)
print("ENTERPRISE AI INTERVIEW SUMMARY:")
print("  Multi-tenant: central gateway with per-tenant auth, models, budget, audit")
print("  LLMOps: MLflow to track prompt + model + metrics experiments")
print("  A/B testing: hash(user_id) for consistent variant assignment")
print("  Cost: model routing (60% simple→mini), semantic cache (30-60% hit), batching")
print("  Compliance: PII scrubbing before LLM, audit log all calls, data residency")
print("  Shadow mode: new model gets real traffic, compare offline before promoting")
print("=" * 60)
