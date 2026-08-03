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

### E. OpenAI Evals
OpenAI ka open-source eval framework (`openai/evals` repo + built-in Evals product in the platform dashboard).
- **Registry-based**: har eval = ek YAML/JSONL — samples + graded output rules. `oaieval <model> <eval-name>` se run.
- **Do tarah ke graders**: (1) `match`/`includes`/`fuzzy_match` — deterministic string checks; (2) `model-graded` — ek LLM judge rubric ke against grade kare (G-Eval jaisa).
- **Platform Evals API**: dataset upload → `eval` create → runs compare across model versions, dashboard me side-by-side. CI me regression-gate ke liye achha.

```python
# Platform Evals API (2025+) — code se eval banao
from openai import OpenAI
client = OpenAI()

eval_obj = client.evals.create(
    name="support-answer-quality",
    data_source_config={"type": "custom", "item_schema": {
        "type": "object",
        "properties": {"question": {"type": "string"}, "expected": {"type": "string"}},
    }},
    testing_criteria=[{
        "type": "label_model",           # LLM-as-judge grader
        "model": "gpt-4.1-mini",
        "input": [{"role": "user", "content": "Q: {{item.question}}\nExpected: {{item.expected}}\nAnswer: {{sample.output_text}}\nIs the answer correct? Reply pass/fail."}],
        "labels": ["pass", "fail"], "passing_labels": ["pass"],
    }],
)
# phir client.evals.runs.create(eval_id=..., data_source=...) se run + compare
```

**Kab kya**: RAG → RAGAS; general LLM app + Python-native asserts → DeepEval; prompt A/B (CLI/CI) → Promptfoo; OpenAI stack pe tightly-integrated regression gate → OpenAI Evals.

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

## 12. Public Agent Benchmarks (jab koi kahe "model X is better at agents")

Sections 1–11 = **apne** agent ko evaluate karna. Yeh section = **industry-standard public benchmarks** jo model/agent capability measure karte hain. Model announcements aur interviews dono me yehi naam aate hain.

| Benchmark | Kya test karta hai | Task shape |
|---|---|---|
| **SWE-bench (Verified)** | Real GitHub issues fix karna — repo samajhna, patch likhna, tests pass karna | Coding agent, full repo context |
| **tau-bench / tau2** | Customer-service agent — tools + policy rules follow karna, multi-turn user simulation | Tool use + policy compliance |
| **GAIA** | General assistant tasks — web browsing, file handling, multi-step reasoning | Generalist agent |
| **WebArena / OSWorld** | Real websites/OS me tasks complete karna (clicks, forms, navigation) | Browser/computer-use agent |
| **Terminal-Bench** | Shell me kaam — build, debug, sysadmin tasks | CLI/terminal agent |
| **HLE (Humanity's Last Exam)** | Expert-level knowledge questions — frontier "hard ceiling" | Knowledge + reasoning (agent-lite) |
| **AgentBench** | Multi-environment suite (OS, DB, web, games) | Broad agent survey |

### Benchmark numbers padhne ke caveats (interview gold)

1. **"Verified" matters** — original SWE-bench me kuch tasks broken/ambiguous the; SWE-bench **Verified** = human-filtered 500 solvable subset. Announcements me hamesha check karo kaunsa variant hai.
2. **pass@1 vs pass@k** — ek attempt me solve kiya ya k attempts me best? pass@8 number pass@1 se hamesha bada dikhega.
3. **Harness matters as much as model** — same model, different scaffold (tools, retries, context management) = 20+ point difference. "Model X scored Y" actually means "Model X + iska harness scored Y". (Dekho [12_agent_harness_engineering.md](12_agent_harness_engineering.md).)
4. **Contamination** — public benchmark → training data me leak ho sakta hai. Isliye private/rotating evals (LiveBench-style) zyada trusted hain.
5. **Benchmark ≠ tumhara workload** — SWE-bench score tumhare invoice-processing agent ka proxy nahi hai. Final decision hamesha apne eval set (§3) pe.

**Interview answer template:** "Public benchmarks (SWE-bench Verified for coding, tau-bench for tool-use/policy, GAIA for general assistance) se model shortlist karta hoon, phir apne domain ka 200-example eval set bana ke actual decision leta hoon — kyunki harness aur domain shift se public numbers directly transfer nahi hote."

---

## 13. Key Takeaways

✅ Eval is NOT optional. Critical for production.
✅ Categories: task accuracy, operational, quality, satisfaction
✅ Build eval set of 50-200 labeled examples
✅ Use RAGAS for RAG, DeepEval for general
✅ LLM-as-judge works well
✅ Monitor continuously in production (1% sampling)
✅ A/B test changes; don't ship without comparison
✅ Public benchmarks (SWE-bench Verified, tau-bench, GAIA) = model shortlisting; final call apne eval set pe

**Level 6 advanced patterns covered!** Next: Level 5 RAG deep dives.
