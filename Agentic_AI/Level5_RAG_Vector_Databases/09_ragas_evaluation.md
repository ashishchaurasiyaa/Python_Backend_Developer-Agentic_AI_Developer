# Level 5 — Doc 9: RAGAS Evaluation ⭐

> **Goal:** RAG ki quality kaise measure kare. RAGAS = industry standard framework.

---

## 1. Why RAG Eval is Hard

LLM testing is hard because:
- No single "correct" answer
- Quality is subjective
- Hallucinations look plausible

**RAGAS** solves this with **4 specific metrics** using LLM-as-judge.

---

## 2. The RAGAS Metrics

### A. Faithfulness (Hallucination Detection)
**Q:** Is the answer grounded in retrieved context?

```
Answer: "Python was created in 1991"
Context: "Python was created by Guido van Rossum, released February 1991"
Faithful? YES (1991 is in context)

Answer: "Python was created in 1980"
Context: same as above
Faithful? NO (1980 not in context — hallucinated)
```

**Higher = less hallucination.**

### B. Answer Relevancy
**Q:** Does answer match the question?

```
Q: "When was Python created?"
A: "Python is a programming language."
Relevant? NO (answers wrong question)

A: "Python was created in 1991."
Relevant? YES
```

### C. Context Precision
**Q:** Are retrieved docs relevant — AND are the relevant ones ranked HIGH?

```
Q: "Python's history"
Retrieved: 
  doc1: "Python was created in 1991" → relevant ✓
  doc2: "JavaScript is fast" → NOT relevant ✗
  doc3: "Python's design principles" → relevant ✓

Simple intuition: 2 relevant / 3 total = 0.67
```

⚠️ **Gotcha (interview me poochhte hain):** RAGAS ka `context_precision` SIRF relevant/total
nahi hai — ye **rank-aware** hai: har relevant chunk ki position pe precision@k ka mean.
Matlab relevant docs upar (rank 1,2) hain to score zyada; neeche (rank 3+) hain to kam —
bhale hi relevant count same ho. "2/3 = 0.67" sirf intuition ke liye; asli metric ranking ko reward karta hai.

### D. Context Recall
**Q:** Did we retrieve ALL needed info?

Needs ground truth answer:
```
Ground truth: "Python was created by Guido van Rossum in 1991"
Retrieved context: "Python was created in 1991"

Recall = 1 fact found / 2 facts in ground truth = 0.5
```

---

## 3. RAGAS Setup

```python
pip install ragas datasets
```

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)
from datasets import Dataset

# Your test data
data = {
    "question": ["When was Python created?", "Who made Python?", ...],
    "answer": ["Python was created in 1991.", "Guido van Rossum created Python.", ...],
    "contexts": [
        ["Python was created in 1991 by..."],
        ["Guido van Rossum created Python..."],
    ],
    "ground_truth": [
        "Python was created in 1991 by Guido van Rossum.",
        "Guido van Rossum created Python in the late 1980s.",
    ]
}

dataset = Dataset.from_dict(data)

result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)

print(result)
# {
#   "faithfulness": 0.85,
#   "answer_relevancy": 0.92,
#   "context_precision": 0.78,
#   "context_recall": 0.81
# }
```

---

## 4. Interpreting Scores

| Score | Quality |
|---|---|
| 0.9+ | Excellent |
| 0.8-0.9 | Good (production-ready) |
| 0.7-0.8 | Acceptable but improvable |
| < 0.7 | Needs work |

Target: **all 4 metrics > 0.85** for production RAG.

---

## 5. Building an Eval Set

You need:
- **questions** (50-200)
- **expected answers** (ground truth)
- For full eval: pairs of (question, ideal_answer)

Sources:
- Domain experts curate questions
- Synthetic: use LLM to generate from your docs
- Production: sample real user queries (anonymize)

---

## 6. Synthetic Test Generation

```python
from ragas.testset import TestsetGenerator

# Generate test set from your documents
generator = TestsetGenerator.with_openai()
testset = generator.generate_with_langchain_docs(
    documents,
    test_size=50,
    distributions={
        "simple": 0.5,
        "reasoning": 0.25,
        "multi_context": 0.25
    }
)
```

LLM auto-generates Q&A pairs covering different difficulty levels.

---

## 7. CI/CD Integration

```yaml
# .github/workflows/rag_eval.yml
name: RAG Quality Check
on: [pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install ragas
      - run: python eval_rag.py
      - name: Fail if scores too low
        run: |
          if [ $(python -c "import json; r=json.load(open('eval_results.json')); print(r['faithfulness'])") < 0.85 ]; then
            exit 1
          fi
```

Don't merge PRs that drop RAG quality.

---

## 8. Custom Metrics

RAGAS supports custom metrics:

```python
from ragas.metrics import AspectCritic

helpfulness = AspectCritic(
    name="helpfulness",
    definition="Is the answer helpful to a developer learning Python?"
)

result = evaluate(dataset, metrics=[helpfulness, faithfulness])
```

---

## 9. Beyond RAGAS

For comprehensive eval:
- **DeepEval** — G-Eval, hallucination, toxicity
- **PromptFoo** — A/B test prompts
- **LangSmith** — production monitoring + eval
- **TruLens** — RAG triad evaluation
- **Phoenix** (Arize) — open-source observability + eval

---

## 10. Production Monitoring

In addition to offline eval, monitor in production:

```python
# Sample 1% of production responses
if random() < 0.01:
    score = ragas.evaluate({
        "question": user_query,
        "answer": llm_response,
        "contexts": retrieved_chunks,
    })
    log_to_grafana("rag_eval", score)
```

Alert when:
- Faithfulness drops below 0.85
- Answer relevancy below 0.80
- Context precision below 0.70

---

## 11. Iteration Loop

```
1. Build initial RAG
2. Eval with RAGAS → scores
3. Identify weak metric (e.g., low context_recall)
4. Improve component (e.g., better retrieval — hybrid search, reranking)
5. Re-eval
6. Compare scores
7. Ship if improved, iterate if not
```

---

## 12. Common Pitfalls

❌ Evaluating only on easy questions → scores look great but production fails
❌ Not having ground truth → can't measure recall
❌ Using same LLM for generation AND evaluation → biased
❌ Skipping eval because "demo works" → catastrophic regressions later
❌ Optimizing one metric at expense of others

---

## 13. Key Takeaways

✅ RAGAS = 4 metrics (faithfulness, relevancy, context precision, context recall)
✅ All metrics > 0.85 for production
✅ Use LLM-as-judge (different model than generator)
✅ Build eval set of 50-200 labeled questions
✅ Synthetic test generation possible
✅ Integrate with CI/CD — block PRs that drop quality
✅ Monitor in production (1% sampling)

**Level 5 RAG deep dives done!** Next: Level 8 production essentials.
