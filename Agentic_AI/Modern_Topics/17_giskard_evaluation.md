# Giskard — LLM/RAG Testing & Red-Teaming

**Agentic AI · Modern Topics | Senior AI Engineer**

> Evaluation row me **Ragas** covered ([Level5/09](../Level5_RAG_Vector_Databases/09_ragas_evaluation.md)); **Giskard** missing tha. Ragas metrics deta hai — Giskard **vulnerabilities dhoondta hai** aur test suite banata hai.

---

## Quick Concepts

**WHAT:** LLM/RAG apps ka automated **testing + red-teaming** framework — adversarial cases khud generate karta hai.

**Ragas vs Giskard:**
| | Ragas (covered) | Giskard (this file) |
|---|-----------------|---------------------|
| Focus | RAG quality metrics | vulnerability scan + red-team |
| Output | scores | issues report + reusable test suite + CI gate |
| Finds | "answer kitna accurate" | hallucination, prompt injection, harmfulness, bias, robustness |

---

## Architecture

```
                    ┌──────────────── GISKARD SCAN ────────────────┐
   your RAG/LLM ───►│  Auto-generate adversarial test cases         │
   (wrapped as      │        │                                      │
    a function)     │        ▼                                      │
                    │  Probe categories:                            │
                    │   • Hallucination / factual                   │
                    │   • Prompt injection / jailbreak              │
                    │   • Harmfulness / toxicity                    │
                    │   • Sensitive info disclosure                 │
                    │   • Robustness / stereotype / bias            │
                    │        │                                      │
                    │        ▼                                      │
                    │  Vulnerability REPORT + reusable Test Suite   │
                    └────────┼──────────────────────────────────────┘
                             ▼
              RAGET: auto Q&A testset from your KB → per-component diagnosis → CI gate
```

- **`giskard.scan(model)`** = automatic vulnerability report (no manual test writing)
- **Test Suite** = report se reusable tests → CI me deploy-gate
- **RAGET** (RAG Evaluation Toolkit): knowledge base se automatically Q&A testset banata hai + per-component (retriever / generator / rewriter / router) diagnosis — batata hai failure kahan hai

---

## Where it fits
```
build RAG ─► Ragas (metrics) ─► Giskard (red-team + scan) ─► CI gate ─► deploy
                                        ▲
                         TruLens (live tracing/feedback) complements at runtime
```
Eval row ab complete: **Ragas (metrics) + Giskard (red-team) + TruLens (tracing)**.

## Interview one-liners
- "Ragas scores my RAG; Giskard attacks it — injection, hallucination, bias — and emits a test suite."
- "RAGET auto-builds a Q&A testset from my knowledge base and tells me which component is failing."
- "I wire the generated suite into CI as a pre-deploy quality gate."

See runnable example → [17_giskard_evaluation_practical.py](17_giskard_evaluation_practical.py)
