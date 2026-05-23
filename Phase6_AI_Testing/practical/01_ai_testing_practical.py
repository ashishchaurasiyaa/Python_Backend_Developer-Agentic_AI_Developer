"""
Phase6_AI_Testing — Complete Practical
========================================
Topics:
  1. LLM output evaluation patterns
  2. RAGAS metrics (faithfulness, relevancy, etc.)
  3. Hallucination detection
  4. LLM-as-judge evaluator
  5. Automated test suites for agents
  6. Regression testing for prompts
  7. DeepEval + Pytest integration

Install: pip install deepeval ragas langchain-openai
Run: python 01_ai_testing_practical.py
"""

import os, json, math, random
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("AI TESTING CONCEPTS")
print("=" * 60)

AI_TEST_CONCEPTS = {
    "Deterministic tests":  "Exact match, format check, schema validation. Always pass/fail.",
    "LLM-as-judge":         "Use LLM (GPT-4/Claude) to evaluate another LLM's output.",
    "RAGAS":                "Evaluate RAG: faithfulness, answer_relevancy, context_precision.",
    "Hallucination detect": "Check if answer claims are grounded in provided context.",
    "Consistency tests":    "Same prompt → similar answers across N runs (test stability).",
    "Regression tests":     "Ensure prompt changes don't degrade previous good cases.",
    "Red teaming":          "Adversarial inputs to find failure modes and safety issues.",
    "Trace-based eval":     "LangSmith: collect real traces, annotate, build test dataset.",
}
for k, v in AI_TEST_CONCEPTS.items():
    print(f"  {k:<24}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Deterministic Evaluation
# INTERVIEW: Always do these first — they're fast and cheap
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Deterministic Evaluation")
print("=" * 60)

DETERMINISTIC_CODE = '''\
import pytest
from pydantic import BaseModel, ValidationError

# ── Format/Schema validation ──────────────────────────────────
class LLMResponse(BaseModel):
    answer:     str
    confidence: float
    sources:    list[str]

def test_response_format(llm_output: str):
    """Test that LLM returns valid JSON matching expected schema."""
    data = json.loads(llm_output)
    resp = LLMResponse(**data)   # raises ValidationError if invalid
    assert 0 <= resp.confidence <= 1, "Confidence must be 0-1"
    assert len(resp.answer) > 0, "Answer must not be empty"

# ── Keyword presence ────────────────────────────────────────────
def test_response_mentions_key_concepts(response: str):
    """Check that response contains required concepts."""
    required = ["asyncio", "await", "coroutine"]
    missing  = [kw for kw in required if kw.lower() not in response.lower()]
    assert not missing, f"Missing keywords: {missing}"

# ── Length constraints ──────────────────────────────────────────
def test_response_length(response: str, min_words: int = 50, max_words: int = 500):
    word_count = len(response.split())
    assert min_words <= word_count <= max_words, (
        f"Response length {word_count} outside [{min_words}, {max_words}]"
    )

# ── No PII in output ────────────────────────────────────────────
import re
def test_no_pii(response: str):
    email_pattern = r"[\\w.%+\\-]+@[\\w.\\-]+\\.[A-Za-z]{2,}"
    ssn_pattern   = r"\\d{3}-\\d{2}-\\d{4}"
    assert not re.search(email_pattern, response), "Email in output"
    assert not re.search(ssn_pattern, response),   "SSN in output"
'''
print(DETERMINISTIC_CODE[:700])


# Demo deterministic tests
@dataclass
class EvalCase:
    name: str
    response: str
    expected_keywords: List[str] = field(default_factory=list)
    expected_schema: Optional[Dict] = None
    max_words: int = 500

    def run_tests(self) -> Dict[str, bool]:
        results = {}
        # Keyword test
        if self.expected_keywords:
            missing  = [kw for kw in self.expected_keywords if kw.lower() not in self.response.lower()]
            results["keywords"] = len(missing) == 0
        # Length test
        results["length"] = len(self.response.split()) <= self.max_words
        # No PII
        results["no_email"] = not bool(re.search(r"[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}", self.response) if __import__("re") else False)
        return results


import re

cases = [
    EvalCase("Python async", "asyncio and await enable coroutine-based concurrency",
             expected_keywords=["asyncio", "await", "coroutine"]),
    EvalCase("Short answer", "Yes",
             expected_keywords=["python", "framework"], max_words=1),
]

print("\n  Deterministic test results:")
for case in cases:
    results = case.run_tests()
    status  = "✓" if all(results.values()) else "✗"
    print(f"  {status} {case.name}: {results}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: RAGAS Metrics
# INTERVIEW: 4 key metrics for RAG evaluation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: RAGAS Evaluation")
print("=" * 60)

RAGAS_CODE = '''\
from ragas import evaluate
from ragas.metrics import (
    faithfulness,       # Is answer ONLY from context? (no hallucination)
    answer_relevancy,   # Does answer address the question?
    context_precision,  # Are retrieved contexts relevant to question?
    context_recall,     # Do retrieved contexts cover all needed info?
    answer_correctness, # Is answer correct vs ground truth? (needs labels)
)
from datasets import Dataset

# ── Prepare evaluation dataset ─────────────────────────────────
eval_data = {
    "question": [
        "What is Python?",
        "What is FastAPI used for?",
    ],
    "answer": [
        "Python is a high-level interpreted programming language.",
        "FastAPI is used to build REST APIs quickly.",
    ],
    "contexts": [
        # Retrieved chunks for each question
        ["Python is a high-level, interpreted language created by Guido van Rossum."],
        ["FastAPI is a modern Python web framework for building APIs with OpenAPI support."],
    ],
    "ground_truth": [
        "Python is a high-level interpreted language created in 1991.",
        "FastAPI is a modern web framework for building REST APIs.",
    ],
}

dataset = Dataset.from_dict(eval_data)
results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)
print(results)
# → {"faithfulness": 0.95, "answer_relevancy": 0.88, ...}

# ── Per-example scores ──────────────────────────────────────────
df = results.to_pandas()
print(df[["question", "faithfulness", "answer_relevancy"]])

# ── Interpretation ─────────────────────────────────────────────
# faithfulness < 0.8: LLM hallucinates → improve retrieval or prompt
# answer_relevancy < 0.8: answers off-topic → improve question routing
# context_precision < 0.7: retrieving irrelevant chunks → tune retrieval
# context_recall < 0.7: missing relevant chunks → add more docs or reduce chunk size
'''
print(RAGAS_CODE[:700])

print("\n  RAGAS metric formulas (simplified):")
print("  faithfulness:       |verified_claims| / |total_claims|")
print("  answer_relevancy:   cosine_sim(embed(question), embed(answer))")
print("  context_precision:  relevant_contexts / total_retrieved_contexts")
print("  context_recall:     retrieved_relevant / total_relevant_in_corpus")


# Mock RAGAS-style scoring
def score_faithfulness(answer: str, contexts: List[str]) -> float:
    """Faithfulness: what fraction of answer is grounded in context?"""
    context_text  = " ".join(contexts).lower()
    answer_words  = set(answer.lower().split())
    context_words = set(context_text.split())
    overlap       = len(answer_words & context_words)
    return min(1.0, overlap / max(len(answer_words), 1))


def score_answer_relevancy(question: str, answer: str) -> float:
    """Answer relevancy: does answer address the question? (mock)"""
    q_words = set(question.lower().split())
    a_words = set(answer.lower().split())
    overlap = len(q_words & a_words)
    return min(1.0, overlap / max(len(q_words), 1))


print("\n  Mock RAGAS scores:")
test_data = [
    {
        "question": "What is Python?",
        "answer":   "Python is a high-level interpreted programming language.",
        "contexts": ["Python is a high-level, interpreted language created by Guido van Rossum."],
    },
    {
        "question": "What is FastAPI?",
        "answer":   "The sky is blue and clouds are white.",  # hallucinated/irrelevant
        "contexts": ["FastAPI is a modern Python web framework."],
    },
]

for ex in test_data:
    f = score_faithfulness(ex["answer"], ex["contexts"])
    r = score_answer_relevancy(ex["question"], ex["answer"])
    print(f"  Q: {ex['question'][:40]}")
    print(f"    faithfulness={f:.2f}  answer_relevancy={r:.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: LLM-as-Judge
# INTERVIEW: Use GPT-4/Claude to evaluate another model's output
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: LLM-as-Judge")
print("=" * 60)

LLM_JUDGE_CODE = '''\
from openai import OpenAI
from pydantic import BaseModel
import instructor

client = instructor.from_openai(OpenAI())

class EvalScore(BaseModel):
    score:    int      # 1-10
    reason:   str
    issues:   list[str]

def llm_judge(question: str, answer: str, context: str = "") -> EvalScore:
    """
    INTERVIEW: LLM-as-judge = use stronger LLM to score weaker LLM.
    More accurate than heuristics for subjective quality.
    Use GPT-4 to evaluate GPT-4o-mini output.
    """
    prompt = f"""
    Evaluate the quality of this answer to the question.

    Question: {question}
    Context: {context}
    Answer: {answer}

    Rate 1-10 on:
    - Accuracy (is it factually correct?)
    - Completeness (does it fully answer the question?)
    - Conciseness (is it appropriately brief?)

    Provide: overall score (1-10), brief reason, and list of issues.
    """
    return client.chat.completions.create(
        model          = "gpt-4o",      # stronger judge
        response_model = EvalScore,
        messages       = [{"role": "user", "content": prompt}]
    )

# ── Pairwise comparison ────────────────────────────────────────
class PairwiseComparison(BaseModel):
    winner:  str      # "A" or "B"
    reason:  str

def compare_responses(question: str, response_a: str, response_b: str) -> str:
    result = client.chat.completions.create(
        model          = "gpt-4o",
        response_model = PairwiseComparison,
        messages       = [{
            "role": "user",
            "content": f"Question: {question}\\nA: {response_a}\\nB: {response_b}\\nWhich is better?"
        }]
    )
    return result.winner
'''
print(LLM_JUDGE_CODE[:700])

print("\n  LLM judge prompt design:")
print("  1. Be specific about evaluation criteria")
print("  2. Use reference answers when available")
print("  3. Ask for structured output (score + reason)")
print("  4. Avoid positional bias — randomize A/B order")
print("  5. Run 3+ times and average to reduce variance")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: DeepEval
# INTERVIEW: Pytest-like framework for LLM evaluation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: DeepEval Framework")
print("=" * 60)

DEEPEVAL_CODE = '''\
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    HallucinationMetric,
    ToxicityMetric,
    BiasMetric,
)
import pytest

# ── Define metrics ─────────────────────────────────────────────
answer_relevancy = AnswerRelevancyMetric(threshold=0.7, model="gpt-4o-mini")
faithfulness     = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")
hallucination    = HallucinationMetric(threshold=0.5, model="gpt-4o-mini")

# ── Test cases ─────────────────────────────────────────────────
@pytest.mark.parametrize("test_case", [
    LLMTestCase(
        input           = "What is Python?",
        actual_output   = "Python is a high-level interpreted language.",
        expected_output = "Python is a programming language.",
        retrieval_context = ["Python is a high-level, general-purpose language."],
    ),
    LLMTestCase(
        input         = "What is FastAPI?",
        actual_output = "FastAPI is a web framework for Python.",
        retrieval_context = ["FastAPI is a modern web framework."],
    ),
])
def test_rag_quality(test_case):
    assert_test(test_case, metrics=[
        answer_relevancy,
        faithfulness,
        hallucination,
    ])

# Run: deepeval test run test_llm.py
# → Shows pass/fail per metric, details on failures

# ── Standalone evaluation ──────────────────────────────────────
from deepeval import evaluate as deepeval_evaluate

test_cases = [LLMTestCase(...), ...]
results = deepeval_evaluate(
    test_cases = test_cases,
    metrics    = [answer_relevancy, faithfulness],
)
print(results.test_run_summary)
# → {"passed": 8, "failed": 2, ...}
'''
print(DEEPEVAL_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Regression Testing
# INTERVIEW: Ensure new prompts don't break existing behavior
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Regression Testing Pattern")
print("=" * 60)

REGRESSION_CODE = '''\
# INTERVIEW: Golden dataset = saved input/output pairs used for regression

import json
from pathlib import Path

GOLDEN_FILE = "golden_dataset.jsonl"

def save_golden(question: str, expected: str, tags: list = None):
    """Save a good response as a golden example."""
    with open(GOLDEN_FILE, "a") as f:
        f.write(json.dumps({
            "question": question,
            "expected": expected,
            "tags":     tags or [],
            "created":  datetime.now().isoformat(),
        }) + "\\n")

def load_golden() -> list:
    if not Path(GOLDEN_FILE).exists():
        return []
    return [json.loads(line) for line in open(GOLDEN_FILE)]

# ── Regression test (run on every prompt change) ──────────────
def regression_test(new_prompt: str) -> dict:
    """Test new prompt against all golden examples."""
    golden = load_golden()
    results = {"passed": 0, "failed": 0, "failures": []}

    for example in golden:
        # Generate response with new prompt
        response = run_with_prompt(new_prompt, example["question"])
        # Evaluate similarity to expected
        similarity = semantic_similarity(response, example["expected"])
        if similarity >= 0.8:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["failures"].append({
                "question":   example["question"],
                "expected":   example["expected"],
                "got":        response,
                "similarity": similarity,
            })

    results["pass_rate"] = results["passed"] / len(golden)
    return results

# Use in CI pipeline:
# if regression_test(new_prompt)["pass_rate"] < 0.9:
#     raise RuntimeError("New prompt failed regression! Rollback.")
'''
print(REGRESSION_CODE[:600])


print("\n  AI testing best practices:")
print("  1. Start with deterministic tests (format, schema, keywords)")
print("  2. Add RAGAS metrics for RAG pipelines")
print("  3. Use LLM-as-judge for subjective quality (use GPT-4 to eval GPT-mini)")
print("  4. Build golden dataset from production traffic (good real examples)")
print("  5. Run regression on every prompt change in CI/CD")
print("  6. Track metric trends over time (not just pass/fail)")
print("  7. Red team: adversarial inputs, edge cases, safety issues")


print("\n" + "=" * 60)
print("AI TESTING INTERVIEW SUMMARY:")
print("  Deterministic: format, schema, keywords, no-PII — always fast/free")
print("  RAGAS: faithfulness (no hallucination), relevancy, precision, recall")
print("  LLM-judge: GPT-4 evaluates GPT-4o-mini. Structured output with score+reason.")
print("  DeepEval: pytest-like framework for LLM tests. CI integration.")
print("  Regression: golden dataset → test every prompt change → block if fails")
print("  Key: LLM quality degrades silently — automated eval catches regressions")
print("=" * 60)
