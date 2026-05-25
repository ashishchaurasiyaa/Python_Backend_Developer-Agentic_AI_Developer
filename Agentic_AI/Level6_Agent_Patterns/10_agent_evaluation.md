# Level 6 — Doc 10: Agent Evaluation

> **Goal:** Agent kaise measure karte hain? Accuracy, latency, cost, hallucination — sab metrics.

---

## 1. Why Evaluate?

"Demo works, ship it" = recipe for production disaster. Real agents need:
- **Quality metrics** (accuracy, helpfulness)
- **Cost metrics** ($/query, tokens)
- **Speed metrics** (latency, P99)
- **Safety metrics** (hallucination rate, harmful outputs)

Without metrics, you can't:
- Compare prompt versions
- Detect regression after changes
- Optimize costs
- Justify model upgrades

---

## 2. Categories of Metrics

### A. Task-Level (Accuracy)
- Did the agent complete the task?
- Was the answer correct?
- Did it use right tools?

### B. Operational
- Latency per query
- Cost per query
- Failure rate (timeouts, errors)
- Iterations to completion

### C. Quality
- Hallucination rate
- Helpfulness (subjective)
- Safety/toxicity
- Format adherence (JSON, etc.)

### D. User Satisfaction
- Thumbs up/down
- Re-prompts (user didn't get answer first try)
- Session length

---

## 3. Building an Eval Set

```python
EVAL_SET = [
    {
        "id": "ticket_001",
        "query": "Refund order #12345",
        "expected_tool": "process_refund",
        "expected_args": {"order_id": "12345"},
        "expected_outcome": "refund_initiated",
        "ground_truth_answer": "Refund of $50 processed for order #12345",
    },
    {
        "id": "ticket_002",
        "query": "Where is my package?",
        "expected_tool": "track_shipment",
        ...
    },
    # 50-200 examples
]
```

**Build this manually** — sample from real user queries, label expected outcomes.

---

## 4. Running Evals

```python
def evaluate_agent(agent, eval_set):
    results = []
    for case in eval_set:
        start = time.time()
        try:
            actual = agent.run(case["query"])
            latency = time.time() - start
            
            tool_correct = actual["tool_called"] == case["expected_tool"]
            outcome_correct = check_outcome(actual["result"], case["expected_outcome"])
            
            results.append({
                "id": case["id"],
                "tool_correct": tool_correct,
                "outcome_correct": outcome_correct,
                "latency": latency,
                "cost": actual["cost"]
            })
        except Exception as e:
            results.append({"id": case["id"], "error": str(e)})
    
    return aggregate(results)
```

---

## 5. Specific Eval Frameworks

### A. RAGAS (RAG-specific)
For Q&A systems:
- **Faithfulness**: answer grounded in retrieved docs?
- **Answer Relevancy**: does answer match question?
- **Context Precision**: are retrieved docs relevant?
- **Context Recall**: did we retrieve all needed info?

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy

result = evaluate(
    dataset,  # questions, answers, contexts, ground_truths
    metrics=[faithfulness, answer_relevancy]
)
```

### B. DeepEval
General LLM eval:
- G-Eval (custom criteria via LLM judge)
- Hallucination detection
- Bias / toxicity

### C. PromptFoo
Prompt comparison framework — A/B test prompts.

### D. LangSmith / Langfuse
Production observability + eval.

---

## 6. LLM-as-Judge

Use another LLM to evaluate outputs:

```python
def llm_judge(question, agent_answer, ground_truth=None):
    prompt = f"""You are evaluating an AI agent's response.

Question: {question}
Agent's answer: {agent_answer}
{"Ground truth: " + ground_truth if ground_truth else ""}

Rate on these criteria (1-5):
- Accuracy: factually correct?
- Helpfulness: addresses the question?
- Completeness: covers what's asked?
- Format: well-structured?

Output JSON:
{{"accuracy": X, "helpfulness": X, "completeness": X, "format": X, "reasoning": "..."}}
"""
    return llm.call(prompt)
```

**Pro tip:** Use a different/stronger model for judging (e.g., gpt-4 judges gpt-4o-mini agent).

---

## 7. Specific Metrics for Agents

### Tool Selection Accuracy
```python
tool_accuracy = correct_tool_picks / total_queries
```

### Steps to Completion
```python
avg_steps = sum(iterations) / total
# Lower is better for simple tasks
```

### Recovery Rate (Error Handling)
```python
recovery_rate = recovered_from_errors / total_errors_encountered
```

### Hallucination Rate
```python
# For each answer, check if facts are in source data
hallucination = facts_made_up / total_facts_stated
```

---

## 8. Test Categories

Build eval sets for:

### Happy Path
Standard, expected queries. Agent should handle 100%.

### Edge Cases
- Empty input
- Very long input
- Ambiguous queries
- Multi-step queries

### Adversarial
- Prompt injection attempts
- Toxic inputs
- Out-of-scope requests

### Cost
- Budget queries
- Track $$ per query type

### Latency
- Time per query
- P50, P95, P99

---

## 9. Continuous Eval (Production)

Don't just eval before launch. Monitor continuously:

```python
# Sample 1% of production traffic for evaluation
if random() < 0.01:
    judge_score = llm_judge(query, response)
    log_to_dashboard("eval", judge_score)
```

Set alerts:
- If accuracy drops > 5%, alert team
- If cost per query > threshold, alert
- If P99 latency > 5s, alert

---

## 10. Comparing Versions

```python
def compare_agents(agent_a, agent_b, eval_set):
    results_a = evaluate_agent(agent_a, eval_set)
    results_b = evaluate_agent(agent_b, eval_set)
    
    return {
        "accuracy_diff": results_b["accuracy"] - results_a["accuracy"],
        "latency_diff": results_b["latency_p50"] - results_a["latency_p50"],
        "cost_diff": results_b["cost_per_query"] - results_a["cost_per_query"],
        "winner": "B" if results_b > results_a else "A"
    }
```

A/B test framework essential.

---

## 11. Common Pitfalls

### Eval set too small
50 examples not enough. Aim for 200+.

### Stale eval set
Production data drifts. Refresh every quarter.

### Cherry-picked examples
Eval only "easy" cases. Include hard ones too.

### No baselines
Compare to: human performance, previous version, competitor.

### Optimizing for wrong metric
"Accuracy=99%" but P99 latency = 30s = bad UX.

---

## 12. Key Takeaways

✅ Eval is NOT optional. Critical for production.
✅ Categories: task accuracy, operational, quality, satisfaction
✅ Build eval set of 50-200 labeled examples
✅ Use RAGAS for RAG, DeepEval for general
✅ LLM-as-judge works well
✅ Monitor continuously in production (1% sampling)
✅ A/B test changes; don't ship without comparison

**Level 6 advanced patterns covered!** Next: Level 5 RAG deep dives.
