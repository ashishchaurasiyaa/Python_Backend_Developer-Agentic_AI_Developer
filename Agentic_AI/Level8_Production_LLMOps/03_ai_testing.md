# AI Testing — Mocking LLM Calls, Snapshot Testing, Load Testing

## Quick Concepts
- **LLM Mocking** = real API calls ki jagah fake responses — tests fast, free, deterministic
- **Snapshot Testing** = LLM output save karo, regressions detect karo automatically
- **Evaluation Testing** = output quality test karo — RAGAS, custom metrics
- **Load Testing** = LLM application performance under concurrent users — Locust
- **Golden dataset** = hand-curated Q&A pairs — quality benchmark

---

## Andar kya hota hai — Mocking Level Matter Karta Hai, Aur "Snapshot" Ka Real Matlab

### Mocking — SDK method vs HTTP layer, dono alag cheez catch karte hain

```
Option A: mock the SDK client method (client.chat.completions.create ko patch)
  → Fast, simple. Par tumhare REQUEST-BUILDING code (headers, payload shape,
    retry logic) kabhi actually EXECUTE hi nahi hote — bug wahan chhup sakta.

Option B: mock at HTTP layer (respx/responses library intercepts the actual
  outgoing HTTP call, tumhara asli httpx/requests code chalta hai)
  → Tumhara poora request-construction path genuinely exercise hota hai,
    sirf actual network call replace hoti hai. Integration bugs yahi
    pakadta hai jo Option A miss kar deta.
```

### Snapshot testing — EXACT STRING diff LLM outputs pe kaam nahi karta

LLM output `temperature=0` pe bhi model-version update se, ya minor
infra-level nondeterminism se, THODA badal sakta hai — agar snapshot test
EXACT STRING match karega, woh baar-baar false-positive FAIL karega bina
tumhara code galat hue. Isliye LLM snapshot testing usually STRUCTURE
compare karta hai (schema match, required fields present) ya ek DOOSRA
LLM ko "judge" bana ke "kya yeh output pichle wale jaisa hi acceptable
hai?" poochta hai — exact text diff nahi.

### Golden-dataset eval — RAGAS jaisa metric andar se KAISE compute hota hai

```
Faithfulness score (example):
  1. Generated answer se INDIVIDUAL claims extract karo (ek LLM call)
  2. Har claim ko retrieved CONTEXT ke against verify karo — "kya yeh
     claim context se support hoti hai?" (ek aur LLM call, PER claim)
  3. Score = (context-se-supported claims) / (total claims)
```

Yeh metric khud EK LLM-as-judge pipeline hai — "score 0.85 aaya" ka matlab
hai 85% claims context se traceable the, judge-LLM ke hisaab se. Isi
mechanism ka detail `Level6_Agent_Patterns/10_agent_evaluation.md` mein hai.

---

## Interview Questions & Answers

### Q1: LLM calls ko pytest mein kaise mock karte hain?
**Answer:**
```python
# pip install pytest pytest-asyncio pytest-mock

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from anthropic import Anthropic
from anthropic.types import Message, TextBlock, Usage

# ===== FIXTURE: Mock Anthropic Client =====
@pytest.fixture
def mock_anthropic_response():
    """Reusable mock response factory"""
    def make_response(text: str, input_tokens: int = 100, output_tokens: int = 50) -> Message:
        return Message(
            id="msg_test123",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text=text)],
            model="claude-sonnet-4-6",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )
    return make_response

# ===== TEST WITH MOCK =====
from myapp.services import classify_support_ticket  # your code

def test_classify_ticket_technical(mock_anthropic_response):
    mock_response = mock_anthropic_response("TECHNICAL")
    
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        
        result = classify_support_ticket("My API is returning 500 errors")
        
        assert result["category"] == "TECHNICAL"
        MockClient.return_value.messages.create.assert_called_once()

# ===== ASYNC MOCK =====
@pytest.mark.asyncio
async def test_async_llm_call(mock_anthropic_response):
    mock_response = mock_anthropic_response("RAG is Retrieval-Augmented Generation")
    
    with patch("anthropic.AsyncAnthropic") as MockAsyncClient:
        MockAsyncClient.return_value.messages.create = AsyncMock(return_value=mock_response)
        
        from myapp.services import async_answer_question
        result = await async_answer_question("What is RAG?")
        
        assert "Retrieval" in result
        MockAsyncClient.return_value.messages.create.assert_awaited_once()

# ===== TOOL USE MOCK =====
from anthropic.types import ToolUseBlock

def test_agent_tool_call(mock_anthropic_response):
    # First response: tool call
    tool_response = Message(
        id="msg_tool_test",
        type="message",
        role="assistant",
        content=[
            ToolUseBlock(
                type="tool_use",
                id="tool_001",
                name="search_database",
                input={"query": "Python developers", "limit": 5}
            )
        ],
        model="claude-sonnet-4-6",
        stop_reason="tool_use",
        stop_sequence=None,
        usage=Usage(input_tokens=100, output_tokens=30, cache_creation_input_tokens=0, cache_read_input_tokens=0),
    )
    
    # Second response: final answer
    final_response = mock_anthropic_response("Found 5 Python developers.")
    
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [
            tool_response,    # First call returns tool use
            final_response,   # Second call returns answer
        ]
        
        from myapp.agents import run_agent
        result = run_agent("Find Python developers in database")
        
        assert "developers" in result.lower()
        assert MockClient.return_value.messages.create.call_count == 2

# ===== FIXTURE FILE: conftest.py =====
# conftest.py
import pytest
from unittest.mock import patch, AsyncMock
from anthropic.types import Message, TextBlock, Usage

@pytest.fixture(autouse=False)
def mock_claude():
    """Auto-mock Claude for all tests in a module"""
    with patch("anthropic.Anthropic") as mock:
        mock.return_value.messages.create.return_value = Message(
            id="test_msg",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text="Mocked response")],
            model="claude-sonnet-4-6",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0),
        )
        yield mock

@pytest.fixture
def mock_openai():
    with patch("openai.OpenAI") as mock:
        mock.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Mocked OpenAI response"))]
        )
        yield mock
```

---

### Q2: Snapshot testing — LLM output regressions kaise detect karte hain?
**Answer:**
```python
# pip install syrupy  # snapshot testing library
# OR manual approach below

import json
import hashlib
from pathlib import Path
import pytest

class SnapshotStore:
    """Simple snapshot testing for LLM outputs"""
    
    def __init__(self, snapshot_dir: str = "./tests/snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_snapshot_path(self, test_name: str) -> Path:
        return self.snapshot_dir / f"{test_name}.json"
    
    def assert_matches_snapshot(
        self,
        test_name: str,
        actual: str,
        update: bool = False,
        similarity_threshold: float = 0.8,
    ) -> bool:
        snapshot_path = self._get_snapshot_path(test_name)
        
        if update or not snapshot_path.exists():
            # Create/update snapshot
            snapshot_path.write_text(json.dumps({
                "output": actual,
                "hash": hashlib.md5(actual.encode()).hexdigest(),
                "created_at": "2026-05-19",
            }, indent=2))
            print(f"Snapshot {'updated' if snapshot_path.exists() else 'created'}: {test_name}")
            return True
        
        # Compare with stored snapshot
        stored = json.loads(snapshot_path.read_text())
        stored_output = stored["output"]
        
        # Exact match
        if actual == stored_output:
            return True
        
        # Semantic similarity check (instead of exact match)
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        emb1 = model.encode(actual)
        emb2 = model.encode(stored_output)
        similarity = float(util.cos_sim(emb1, emb2))
        
        if similarity < similarity_threshold:
            print(f"Snapshot mismatch '{test_name}'!")
            print(f"Similarity: {similarity:.3f} (threshold: {similarity_threshold})")
            print(f"Expected: {stored_output[:200]}")
            print(f"Actual:   {actual[:200]}")
            return False
        
        print(f"Snapshot match '{test_name}': similarity={similarity:.3f}")
        return True

snapshot_store = SnapshotStore()

# ===== SNAPSHOT TESTS =====
class TestRAGPipeline:
    """Test RAG pipeline outputs for regressions"""
    
    @pytest.fixture
    def rag_chain(self):
        # Return actual RAG chain (not mocked)
        from myapp.rag import create_rag_chain
        return create_rag_chain()
    
    def test_python_decorator_explanation(self, rag_chain):
        result = rag_chain.invoke("What is a Python decorator?")
        
        # Key assertions (not full text match)
        assert "decorator" in result.lower()
        assert "@" in result or "wraps" in result.lower()
        assert len(result) > 100
        
        # Snapshot for regression detection
        assert snapshot_store.assert_matches_snapshot(
            "python_decorator_explanation",
            result,
            similarity_threshold=0.85,
        )
    
    def test_fastapi_explanation(self, rag_chain):
        result = rag_chain.invoke("What is FastAPI?")
        
        # Factual assertions
        assert "fastapi" in result.lower()
        assert any(word in result.lower() for word in ["fast", "async", "api", "pydantic"])
        
        assert snapshot_store.assert_matches_snapshot(
            "fastapi_explanation",
            result,
        )

# ===== EVALUATION DATASET TESTING =====
GOLDEN_DATASET = [
    {
        "question": "What is Python GIL?",
        "expected_keywords": ["global interpreter lock", "thread", "cpython"],
        "forbidden_keywords": ["JavaScript", "Java"],
    },
    {
        "question": "Explain async/await in Python",
        "expected_keywords": ["coroutine", "event loop", "asyncio", "await"],
        "forbidden_keywords": [],
    },
]

def test_golden_dataset_coverage(rag_chain):
    """Ensure LLM covers key concepts for standard questions"""
    scores = []
    
    for item in GOLDEN_DATASET:
        result = rag_chain.invoke(item["question"]).lower()
        
        # Check expected keywords
        found = sum(1 for kw in item["expected_keywords"] if kw.lower() in result)
        coverage = found / len(item["expected_keywords"])
        
        # Check no forbidden keywords
        has_forbidden = any(kw.lower() in result for kw in item["forbidden_keywords"])
        
        score = coverage * (0 if has_forbidden else 1)
        scores.append(score)
        
        print(f"Q: {item['question'][:50]} | Score: {score:.2f}")
    
    avg_score = sum(scores) / len(scores)
    print(f"\nAverage coverage score: {avg_score:.2f}")
    
    assert avg_score >= 0.7, f"Coverage too low: {avg_score:.2f} (threshold: 0.7)"
```

---

### Q3: Load testing — LLM application under concurrent users?
**Answer:**
```python
# pip install locust

# locustfile.py
from locust import HttpUser, task, between, events
import json
import random
import time

# Test questions for realistic load
SAMPLE_QUESTIONS = [
    "What is Python?",
    "Explain FastAPI middleware",
    "How does PostgreSQL indexing work?",
    "What is a decorator in Python?",
    "Explain async/await with an example",
    "What is Redis used for?",
    "How to implement JWT authentication?",
]

class RAGUser(HttpUser):
    """Simulates a user of our RAG chatbot"""
    
    wait_time = between(1, 5)  # 1-5 seconds between requests
    
    def on_start(self):
        """Called when user starts"""
        self.session_id = f"load-test-{random.randint(1000, 9999)}"
        self.question_count = 0
    
    @task(3)
    def ask_question(self):
        """Main task: ask a RAG question"""
        question = random.choice(SAMPLE_QUESTIONS)
        
        with self.client.post(
            "/api/chat",
            json={
                "message": question,
                "session_id": self.session_id,
            },
            headers={"Content-Type": "application/json"},
            catch_response=True,
        ) as response:
            
            if response.status_code == 200:
                data = response.json()
                if "answer" not in data:
                    response.failure("Response missing 'answer' field")
                elif len(data["answer"]) < 10:
                    response.failure("Answer too short — likely failed")
                else:
                    response.success()
                    self.question_count += 1
            elif response.status_code == 429:
                response.failure("Rate limit hit")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def check_health(self):
        """Check health endpoint"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")

class StreamingUser(HttpUser):
    """Tests streaming endpoint"""
    
    wait_time = between(2, 8)
    
    @task
    def ask_streaming(self):
        question = random.choice(SAMPLE_QUESTIONS)
        
        start = time.time()
        first_token_time = None
        total_tokens = 0
        
        with self.client.post(
            "/api/chat/stream",
            json={"message": question},
            stream=True,
            catch_response=True,
        ) as response:
            
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            
            for line in response.iter_lines():
                if line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    
                    if first_token_time is None:
                        first_token_time = time.time()
                        ttft = (first_token_time - start) * 1000
                        # Log Time-to-First-Token metric
                    
                    if data.get("done"):
                        break
                    
                    total_tokens += 1
            
            response.success()

# ===== RUN LOCUST =====
# locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 for UI
# OR headless: locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5 --run-time=2m --headless

# ===== ASYNC LOAD TEST (httpx) =====
import asyncio
import httpx
import statistics
import time

async def load_test_endpoint(
    url: str,
    concurrent_users: int = 10,
    requests_per_user: int = 5,
) -> dict:
    """Custom async load test"""
    latencies = []
    errors = []
    
    async def user_session(client: httpx.AsyncClient, user_id: int):
        for i in range(requests_per_user):
            question = random.choice(SAMPLE_QUESTIONS)
            start = time.time()
            
            try:
                response = await client.post(
                    url,
                    json={"message": question, "session_id": f"user-{user_id}"},
                    timeout=30,
                )
                latency = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    latencies.append(latency)
                else:
                    errors.append(f"HTTP {response.status_code}")
            except Exception as e:
                errors.append(str(e))
            
            await asyncio.sleep(random.uniform(0.5, 2))
    
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[
            user_session(client, i)
            for i in range(concurrent_users)
        ])
    
    return {
        "total_requests": len(latencies) + len(errors),
        "successful": len(latencies),
        "errors": len(errors),
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
        "p50_latency_ms": statistics.median(latencies) if latencies else 0,
        # min(..., len-1) se boundary IndexError se bacho (jab 0.95*len == len)
        "p95_latency_ms": sorted(latencies)[min(int(0.95 * len(latencies)), len(latencies) - 1)] if latencies else 0,
        "error_rate": len(errors) / (len(latencies) + len(errors)) if latencies else 1,
    }

# Usage
async def run_load_test():
    results = await load_test_endpoint(
        "http://localhost:8000/api/chat",
        concurrent_users=20,
        requests_per_user=5,
    )
    print(f"Results: {json.dumps(results, indent=2)}")

asyncio.run(run_load_test())
```

---

### Q4: RAGAS-based automated evaluation pipeline?
**Answer:**
```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
from datasets import Dataset
import pandas as pd

class AutomatedEvalPipeline:
    """Run RAGAS evaluation on your RAG pipeline automatically"""
    
    def __init__(self, rag_chain, retriever, test_dataset_path: str):
        self.rag_chain = rag_chain
        self.retriever = retriever
        self.test_dataset = pd.read_csv(test_dataset_path)
        # CSV columns: question, ground_truth
    
    def generate_predictions(self) -> dict:
        questions, answers, contexts, ground_truths = [], [], [], []
        
        for _, row in self.test_dataset.iterrows():
            question = row["question"]
            ground_truth = row["ground_truth"]
            
            # Get retrieved docs
            docs = self.retriever.invoke(question)
            context = [doc.page_content for doc in docs]
            
            # Get answer
            answer = self.rag_chain.invoke(question)
            
            questions.append(question)
            answers.append(answer)
            contexts.append(context)
            ground_truths.append(ground_truth)
        
        return {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
    
    def evaluate(self) -> dict:
        predictions = self.generate_predictions()
        dataset = Dataset.from_dict(predictions)
        
        results = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )
        
        scores = {
            "faithfulness": results["faithfulness"],
            "answer_relevancy": results["answer_relevancy"],
            "context_recall": results["context_recall"],
            "context_precision": results["context_precision"],
        }
        
        # Quality gate
        thresholds = {
            "faithfulness": 0.8,
            "answer_relevancy": 0.8,
            "context_recall": 0.7,
            "context_precision": 0.7,
        }
        
        passed = all(
            scores[metric] >= threshold
            for metric, threshold in thresholds.items()
        )
        
        return {
            "scores": scores,
            "passed": passed,
            "failures": [
                f"{m}: {scores[m]:.3f} < {thresholds[m]}"
                for m, t in thresholds.items()
                if scores[m] < t
            ]
        }

# CI/CD integration
def pytest_test_rag_quality():
    """Run as part of CI/CD pipeline"""
    pipeline = AutomatedEvalPipeline(
        rag_chain=create_rag_chain(),
        retriever=create_retriever(),
        test_dataset_path="tests/golden_dataset.csv",
    )
    
    results = pipeline.evaluate()
    print(f"RAGAS Scores: {results['scores']}")
    
    assert results["passed"], f"RAG quality gate failed: {results['failures']}"
```

---

### Q5: Testing best practices for AI applications?
**Answer:**
```
AI APPLICATION TESTING PYRAMID:

        ┌─────────────┐
        │  E2E Tests  │  ← Few, slow, expensive
        │  (RAGAS)    │
        ├─────────────┤
        │Integration  │  ← Some, against real LLM
        │  Tests      │  (ANTHROPIC_TEST_API)
        ├─────────────┤
        │  Unit Tests │  ← Many, fast, mocked LLM
        │  (Mocked)   │
        └─────────────┘

UNIT TESTS (Fast, Always Mock LLM):
  - Business logic
  - Prompt formatting
  - Response parsing
  - Tool execution

INTEGRATION TESTS (Real LLM, limited):
  - Full RAG pipeline on small dataset
  - Tool use with real external APIs
  - Use cheaper model (Haiku) to reduce cost

E2E / EVALUATION TESTS (Weekly/Monthly):
  - RAGAS on full golden dataset
  - Load testing (Locust)
  - A/B test metric collection

USEFUL PYTEST MARKERS:
  @pytest.mark.unit        — always run (no LLM)
  @pytest.mark.integration — run with env flag: REAL_LLM=true
  @pytest.mark.slow        — exclude from fast CI: pytest -m "not slow"

ENVIRONMENT VARIABLES:
  ANTHROPIC_API_KEY=test_key  — mock mode
  REAL_LLM=true               — actual API calls

CI/CD STRATEGY:
  PR:     unit tests only (fast, free)
  Merge:  unit + integration (small golden dataset)
  Weekly: full RAGAS evaluation (catch quality regressions)
  Deploy: load test (catch performance regressions)
```
