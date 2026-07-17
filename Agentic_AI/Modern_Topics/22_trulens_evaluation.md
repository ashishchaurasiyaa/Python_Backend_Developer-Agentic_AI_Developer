# TruLens — LLM/RAG Observability & Feedback Evaluation

**Agentic AI · Modern Topics | Senior AI Engineer**

> Evaluation row complete karne ka teesra tool. Ragas = metrics ([Level5/09](../Level5_RAG_Vector_Databases/09_ragas_evaluation.md)), Giskard = red-team ([17](17_giskard_evaluation.md)), **TruLens = live tracing + feedback functions** on every call.

---

## Quick Concepts

**WHAT:** TruLens LLM apps ko **instrument** karta hai — har call trace hoti hai aur **feedback functions** (programmatic evaluators) automatically score karte hain. Observability + eval, dono.

**WHY on the diagram (Ragas/Giskard se alag):**
| | Ragas | Giskard | **TruLens** |
|---|-------|---------|-------------|
| Focus | offline metrics | red-team / scan | **live tracing + per-call feedback** |
| Runs | eval batch | pre-deploy | dev **and** production |
| Signature | scores | vuln report | **RAG Triad** + dashboard |

---

## The RAG Triad (TruLens' signature)

```
                    ┌─────────────────────────────────────┐
        query ─────►│  1. Context Relevance                │
                    │     (retrieved chunks vs query?)     │
                    │            │                         │
   retrieved ──────►│  2. Groundedness                     │
   context          │     (answer supported by context?)  │
                    │            │                         │
        answer ────►│  3. Answer Relevance                 │
                    │     (answer actually addresses query?)│
                    └─────────────────────────────────────┘
   All 3 high  ⇒  RAG is honest & useful.  Any low  ⇒  pinpoints the broken stage.
```

- **Feedback functions** = LLM-as-judge or classic metrics applied to any span (input/context/output)
- **Instrumentation:** wrap your app (`TruChain`, `TruLlama`, `TruApp`) → every invocation logged with scores
- **Dashboard:** compare app versions, drill into low-scoring traces, track cost/latency
- **Where:** dev iteration **and** production monitoring (not just a batch eval)

---

## How the three eval tools combine
```
 build RAG ─► TruLens (RAG Triad, trace each call)      ← dev + prod, continuous
           ─► Ragas   (aggregate metrics on a testset)  ← offline batch
           ─► Giskard (adversarial scan → CI gate)       ← pre-deploy
```

## Interview one-liners
- "TruLens instruments the app and scores every call with feedback functions — its RAG Triad is context relevance, groundedness, answer relevance."
- "Low groundedness with high context relevance means the retriever is fine but the generator is hallucinating."
- "Ragas is my offline scorecard, Giskard my red-team gate, TruLens my live observability."

See runnable example → [22_trulens_evaluation_practical.py](22_trulens_evaluation_practical.py)
