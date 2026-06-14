"""
Level5 — Doc 09: RAGAS Evaluation Practical
=============================================

KYA SEEKHENGE (What We Will Learn):
  1. RAGAS kya hai aur kyun zaroori hai  — RAGAS metric theory aur use-case
  2. Char core metrics — Faithfulness, Answer Relevancy, Context Precision, Recall
  3. Manual (mock) metric calculation — bina library ke formulas samajhna
  4. LLM-as-judge pattern — ek alag LLM ko evaluator banana
  5. Synthetic test-set generation — LLM se Q&A pairs banwana
  6. Score interpretation table — production-readiness check
  7. CI/CD gate logic — score threshold pe pass/fail decision
  8. Production sampling — 1% response ko live evaluate karna
  9. RAGAS library integration (optional) — real ragas library ka use
 10. Iteration loop — low score milne pe kya sudhar kare

KAISE CHALANA (How to Run):

  # Offline demo (no keys needed):
  cd /tmp && uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/09_ragas_evaluation_practical.py"

  # Live LLM calls (Groq free tier):
  GROQ_API_KEY=gsk_... uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/09_ragas_evaluation_practical.py"

DEPENDENCIES (all optional heavy libs):
  - ragas, datasets  -> pip install ragas datasets  (optional)
  - sentence-transformers -> pip install sentence-transformers  (optional)
  - openai / groq    -> already in pyproject.toml

Theory reference: 09_ragas_evaluation.md (Level5_RAG_Vector_Databases)
"""

import os
import sys
import json
import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

# ---------------------------------------------------------------------------
# GROQ CLIENT — graceful fallback jab key na ho
# OpenAI() constructor None key pe crash karta hai, isliye placeholder use karo
# ---------------------------------------------------------------------------

def get_client():
    """
    Groq free tier client return karta hai.
    Agar key nahi hai toh placeholder use karta hai — constructor crash nahi karega.
    Usage: client.chat.completions.create(...)
    """
    try:
        from openai import OpenAI
        api_key = os.getenv("GROQ_API_KEY") or "placeholder"
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        return client
    except ImportError:
        return None  # openai package bhi nahi — pure mock mode

HAS_KEY = bool(os.getenv("GROQ_API_KEY"))  # True only jab real key ho

def llm_call(prompt: str, model: str = "llama-3.1-8b-instant") -> Optional[str]:
    """
    LLM call karta hai.  Agar key nahi toh None return karta hai (graceful skip).
    Caller ko check karna chahiye:  result = llm_call(...) or "<fallback>"
    """
    if not HAS_KEY:
        return None
    client = get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [LLM call failed: {e}]")
        return None


print("=" * 65)
print("RAGAS EVALUATION — RAG Quality Measurement Framework")
print("=" * 65)

# Theory digest — theory doc se concepts
RAGAS_CONCEPTS = {
    "Faithfulness":       "Answer context mein grounded hai? Hallucination detect karta hai.",
    "Answer Relevancy":   "Answer ne sahi sawaal ka jawab diya? Off-topic detect karta hai.",
    "Context Precision":  "Retrieved docs mein se kitne relevant hain? Noise measure karta hai.",
    "Context Recall":     "Ground truth ke saare facts context mein mile? Coverage measure hai.",
    "LLM-as-Judge":       "Ek alag (stronger) LLM evaluator hota hai — bias avoid karne ke liye.",
    "Eval Set Size":      "50-200 labeled Q&A pairs chahiye production eval ke liye.",
    "Production Target":  "Saare 4 metrics > 0.85 — tabhi production-ready maano.",
}
print("\nCore Concepts (from theory doc):")
for k, v in RAGAS_CONCEPTS.items():
    print(f"  {k:<22}: {v}")


# ============================================================
# SECTION 1: RAGAS 4 METRICS — THEORY + MANUAL CALCULATION
# ============================================================
print("\n" + "=" * 65)
print("SECTION 1: RAGAS Char Metrics — Theory + Manual Formula")
print("=" * 65)

# ---------------------------------------------------------------------------
# Sample RAG data jisko hum evaluate karenge
# Yeh data represent karta hai ek RAG system ka output
# ---------------------------------------------------------------------------

@dataclass
class RAGSample:
    """
    Ek RAG evaluation sample.
    question   : user ne kya pucha
    answer     : RAG system ne kya jawab diya
    contexts   : retriever ne kya documents laaye
    ground_truth: sahi jawab kya hona chahiye tha
    """
    question: str
    answer: str
    contexts: List[str]
    ground_truth: str


# Python ke baare mein sample data — theory doc ke examples se inspired
SAMPLE_DATA: List[RAGSample] = [
    RAGSample(
        question="Python kab create hua tha?",
        answer="Python 1991 mein create hua tha.",
        contexts=[
            "Python was created by Guido van Rossum and released in February 1991.",
            "Python is a high-level, general-purpose programming language.",
        ],
        ground_truth="Python 1991 mein Guido van Rossum ne create kiya tha.",
    ),
    RAGSample(
        question="Python ka creator kaun hai?",
        answer="Guido van Rossum ne Python banaya.",
        contexts=[
            "Guido van Rossum created Python in the late 1980s.",
            "Python is known for its simple syntax and readability.",
        ],
        ground_truth="Guido van Rossum ne Python create kiya tha 1980s mein.",
    ),
    RAGSample(
        # Yeh ek hallucinated answer hai — test ke liye
        question="Python kab release hua tha?",
        answer="Python 1980 mein release hua tha.",  # WRONG — hallucination
        contexts=[
            "Python was released in February 1991.",
            "Guido van Rossum is the creator of Python.",
        ],
        ground_truth="Python February 1991 mein release hua tha.",
    ),
    RAGSample(
        # Yeh ek irrelevant answer hai — answer relevancy test ke liye
        question="Python ki speed kesi hai?",
        answer="Python ek programming language hai.",  # IRRELEVANT — question ka jawab nahi
        contexts=[
            "Python is slower than C++ but faster to write.",
            "Python performance can be improved with NumPy and Cython.",
        ],
        ground_truth="Python C++ se slow hai but NumPy se fast ho sakta hai.",
    ),
]

print("\nEval Dataset:")
for i, s in enumerate(SAMPLE_DATA):
    print(f"  Sample {i+1}: Q='{s.question[:45]}...' | A='{s.answer[:40]}...'")


# ============================================================
# SECTION 2: METRIC 1 — FAITHFULNESS (Hallucination Detection)
# ============================================================
print("\n" + "=" * 65)
print("SECTION 2: Metric 1 — Faithfulness (Hallucination Detection)")
print("=" * 65)

# Theory:
# Faithfulness = kya answer ke claims context mein supported hain?
# High faithfulness = less hallucination
# Formula: (context-supported claims) / (total claims in answer)

def simple_word_overlap(text_a: str, text_b: str) -> float:
    """
    Simple word overlap score — RAGAS internally LLM se check karta hai,
    hum yahan simple heuristic use kar rahe hain demo ke liye.
    Production mein yahi kaam LLM-as-judge karta hai.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a:
        return 0.0
    overlap = words_a & words_b
    return len(overlap) / len(words_a)


def calculate_faithfulness(sample: RAGSample) -> float:
    """
    Faithfulness score calculate karta hai.
    Real RAGAS: LLM ko deta hai answer + context, poochta hai 'Is each claim grounded?'
    Hum: simple keyword overlap heuristic use kar rahe hain (offline demo ke liye).
    Score 0.0 to 1.0 range mein hota hai.
    """
    combined_context = " ".join(sample.contexts)
    # Answer ke key numeric/named tokens check karo context mein
    answer_tokens = [t for t in sample.answer.lower().split() if len(t) > 3]
    if not answer_tokens:
        return 0.5  # empty answer — neutral

    supported = sum(
        1 for token in answer_tokens
        if token in combined_context.lower()
    )
    score = supported / len(answer_tokens)
    return min(score, 1.0)


print("\nFaithfulness Scores:")
print("  (High = grounded in context, Low = hallucinated)")
faithfulness_scores = []
for i, sample in enumerate(SAMPLE_DATA):
    score = calculate_faithfulness(sample)
    faithfulness_scores.append(score)
    flag = "OK" if score >= 0.7 else "HALLUCINATION RISK"
    print(f"  Sample {i+1}: {score:.2f}  [{flag}]  | Answer: '{sample.answer[:50]}'")

avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
print(f"\n  Average Faithfulness: {avg_faithfulness:.2f}")
print("  Theory reminder: Production mein 0.85+ chahiye hoti hai faithfulness.")


# ============================================================
# SECTION 3: METRIC 2 — ANSWER RELEVANCY
# ============================================================
print("\n" + "=" * 65)
print("SECTION 3: Metric 2 — Answer Relevancy")
print("=" * 65)

# Theory:
# Answer Relevancy = kya answer question ka sahi jawab hai?
# Real RAGAS approach: LLM answer se MULTIPLE questions generate karta hai,
#   phir original question ke saath cosine similarity dekhta hai.
# Hum yahan simplified heuristic use karte hain.

def calculate_answer_relevancy(sample: RAGSample) -> float:
    """
    Answer relevancy score.
    Real RAGAS: answer se N questions generate karo, orig question se compare karo.
    Hum: question aur answer ke beech word overlap + length heuristic.
    """
    question_words = set(sample.question.lower().split())
    # Stopwords hata do — yeh meaningful content nahi
    stopwords = {"kab", "kya", "kaun", "hai", "tha", "ki", "ka", "ne",
                 "is", "was", "the", "a", "an", "of", "in", "to", "for", "when"}
    q_meaningful = question_words - stopwords
    answer_words = set(sample.answer.lower().split())

    if not q_meaningful:
        return 0.5

    overlap = q_meaningful & answer_words
    relevancy = len(overlap) / len(q_meaningful)
    # Penalty for very short answers (< 5 words usually not helpful)
    if len(sample.answer.split()) < 4:
        relevancy *= 0.5
    return min(relevancy, 1.0)


print("\nAnswer Relevancy Scores:")
print("  (High = answer matches question, Low = off-topic)")
relevancy_scores = []
for i, sample in enumerate(SAMPLE_DATA):
    score = calculate_answer_relevancy(sample)
    relevancy_scores.append(score)
    flag = "OK" if score >= 0.6 else "IRRELEVANT"
    print(f"  Sample {i+1}: {score:.2f}  [{flag}]  | Q: '{sample.question[:40]}'")

avg_relevancy = sum(relevancy_scores) / len(relevancy_scores)
print(f"\n  Average Answer Relevancy: {avg_relevancy:.2f}")
print("  Theory reminder: 0.80+ target for answer relevancy in production.")


# ============================================================
# SECTION 4: METRIC 3 — CONTEXT PRECISION
# ============================================================
print("\n" + "=" * 65)
print("SECTION 4: Metric 3 — Context Precision")
print("=" * 65)

# Theory:
# Context Precision = retrieved documents mein se kitne relevant hain?
# Formula: relevant_docs / total_retrieved_docs
# Example: 2 relevant + 1 irrelevant = 2/3 = 0.67

def is_context_relevant_to_question(context: str, question: str) -> bool:
    """
    Kya yeh context chunk question ke liye relevant hai?
    Real RAGAS: LLM se judge karwata hai.
    Hum: simple keyword overlap threshold use karte hain.
    """
    q_words = set(question.lower().split()) - {"kab", "kya", "kaun", "hai", "tha", "ki", "ka"}
    c_words = set(context.lower().split())
    if not q_words:
        return True
    overlap_ratio = len(q_words & c_words) / len(q_words)
    return overlap_ratio > 0.2  # 20%+ overlap = relevant maano


def calculate_context_precision(sample: RAGSample) -> float:
    """
    Context precision score.
    Kitne retrieved contexts question ke liye relevant hain?
    """
    if not sample.contexts:
        return 0.0
    relevant_count = sum(
        1 for ctx in sample.contexts
        if is_context_relevant_to_question(ctx, sample.question)
    )
    return relevant_count / len(sample.contexts)


print("\nContext Precision Scores:")
print("  (High = relevant docs retrieve hue, Low = noise bhi aa gaya)")
precision_scores = []
for i, sample in enumerate(SAMPLE_DATA):
    score = calculate_context_precision(sample)
    precision_scores.append(score)
    relevant = sum(
        1 for ctx in sample.contexts
        if is_context_relevant_to_question(ctx, sample.question)
    )
    total = len(sample.contexts)
    print(f"  Sample {i+1}: {score:.2f}  ({relevant}/{total} relevant) | Q: '{sample.question[:40]}'")

avg_precision = sum(precision_scores) / len(precision_scores)
print(f"\n  Average Context Precision: {avg_precision:.2f}")
print("  Theory reminder: 0.70+ se production mein acceptable maana jata hai.")


# ============================================================
# SECTION 5: METRIC 4 — CONTEXT RECALL
# ============================================================
print("\n" + "=" * 65)
print("SECTION 5: Metric 4 — Context Recall")
print("=" * 65)

# Theory:
# Context Recall = ground truth ke saare facts context mein mile?
# Needs ground_truth — isliye yeh metric "reference-based" hai.
# Formula: (facts from ground truth found in context) / (total facts in ground truth)

def calculate_context_recall(sample: RAGSample) -> float:
    """
    Context recall score.
    Real RAGAS: ground truth ko sentences mein todata hai, phir har sentence
                check karta hai ki context mein supported hai ya nahi.
    Hum: simple word overlap between ground truth and combined context.
    """
    combined_context = " ".join(sample.contexts)
    gt_words = [w for w in sample.ground_truth.lower().split() if len(w) > 3]
    if not gt_words:
        return 0.5

    found = sum(1 for w in gt_words if w in combined_context.lower())
    return found / len(gt_words)


print("\nContext Recall Scores:")
print("  (High = ground truth ke facts context mein hain, Low = retriever miss kiya)")
recall_scores = []
for i, sample in enumerate(SAMPLE_DATA):
    score = calculate_context_recall(sample)
    recall_scores.append(score)
    flag = "OK" if score >= 0.7 else "POOR RETRIEVAL"
    print(f"  Sample {i+1}: {score:.2f}  [{flag}]  | GT: '{sample.ground_truth[:45]}'")

avg_recall = sum(recall_scores) / len(recall_scores)
print(f"\n  Average Context Recall: {avg_recall:.2f}")
print("  Theory reminder: Low recall = retriever mein problem, better chunks ya hybrid search use karo.")


# ============================================================
# SECTION 6: RAGAS AGGREGATE SCORE REPORT
# ============================================================
print("\n" + "=" * 65)
print("SECTION 6: RAGAS Aggregate Score Report")
print("=" * 65)

@dataclass
class RAGASReport:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float

    def overall(self) -> float:
        return (self.faithfulness + self.answer_relevancy +
                self.context_precision + self.context_recall) / 4

    def interpret(self, score: float) -> str:
        """
        Theory doc ki table se interpretation:
        0.9+      = Excellent
        0.8-0.9   = Good (production-ready)
        0.7-0.8   = Acceptable but improvable
        < 0.7     = Needs work
        """
        if score >= 0.9:
            return "Excellent"
        elif score >= 0.8:
            return "Good (production-ready)"
        elif score >= 0.7:
            return "Acceptable — sudhar karo"
        else:
            return "Needs Work — CICD block karo"

    def print_report(self):
        print(f"\n  {'Metric':<25} {'Score':>6}  {'Grade':<30}")
        print(f"  {'-'*25} {'-'*6}  {'-'*30}")
        metrics = [
            ("Faithfulness",       self.faithfulness),
            ("Answer Relevancy",   self.answer_relevancy),
            ("Context Precision",  self.context_precision),
            ("Context Recall",     self.context_recall),
        ]
        all_pass = True
        for name, score in metrics:
            grade = self.interpret(score)
            production_flag = "PASS" if score >= 0.85 else "FAIL"
            if production_flag == "FAIL":
                all_pass = False
            print(f"  {name:<25} {score:>6.2f}  {grade:<30}  [{production_flag}]")

        print(f"\n  {'Overall Score':<25} {self.overall():>6.2f}  {self.interpret(self.overall())}")
        print(f"\n  Production Ready? {'YES' if all_pass else 'NO — kuch metrics 0.85 se neeche hain'}")


report = RAGASReport(
    faithfulness=avg_faithfulness,
    answer_relevancy=avg_relevancy,
    context_precision=avg_precision,
    context_recall=avg_recall,
)
report.print_report()


# ============================================================
# SECTION 7: LLM-AS-JUDGE PATTERN (Live ya Mock)
# ============================================================
print("\n" + "=" * 65)
print("SECTION 7: LLM-as-Judge Pattern")
print("=" * 65)

# Theory:
# Generator aur evaluator ALAG models hone chahiye — bias avoid karne ke liye.
# "Same LLM for generation AND evaluation" = common pitfall hai.

print("""
  LLM-as-Judge kaise kaam karta hai:
  1. RAG system se answer generate hota hai (e.g., llama-3.1-8b with context)
  2. Evaluator LLM (alag / stronger model) ko diya jata hai:
       - Question
       - Answer
       - Context
       - Task: "Is the answer faithful to context? Score 0-1."
  3. Evaluator score return karta hai
  4. Yeh scores aggregate hokar RAGAS metrics bante hain.
""")

# LLM-as-judge prompt template — theory doc ke faithfulness example se
FAITHFULNESS_JUDGE_PROMPT = """You are an evaluation expert.
Check if the answer is faithful to the given context.
Return only a JSON: {{"faithfulness_score": <0.0 to 1.0>, "reason": "<one line>"}}

Question: {question}
Answer: {answer}
Context: {context}

Is every claim in the answer supported by the context? Score 0.0 if not at all, 1.0 if fully supported."""

# Live judge — agar key hai toh use karo, warna mock result show karo
def llm_judge_faithfulness(sample: RAGSample) -> Dict[str, Any]:
    """
    LLM se faithfulness judge karwata hai.
    Key nahi hai toh mock result return karta hai (graceful fallback).
    """
    combined_ctx = " ".join(sample.contexts)[:800]
    prompt = FAITHFULNESS_JUDGE_PROMPT.format(
        question=sample.question,
        answer=sample.answer,
        context=combined_ctx,
    )

    if not HAS_KEY:
        # Mock result — score wahi use karo jo hum manually calculate kar chuke hain
        mock_score = calculate_faithfulness(sample)
        return {
            "faithfulness_score": round(mock_score, 2),
            "reason": "[MOCK — GROQ_API_KEY nahi hai, manual heuristic use ki]",
            "mode": "mock",
        }

    raw = llm_call(prompt)
    if raw is None:
        return {"faithfulness_score": 0.0, "reason": "LLM call failed", "mode": "error"}

    # JSON parse karo — agar fail ho toh graceful fallback
    try:
        # LLM kabhi kabhi extra text deta hai — JSON extract karo
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(raw[start:end])
            result["mode"] = "live"
            return result
    except json.JSONDecodeError:
        pass

    return {
        "faithfulness_score": 0.5,
        "reason": f"Parse failed: {raw[:60]}",
        "mode": "parse_error",
    }


print(f"\n  LLM Judge Demo (mode: {'LIVE' if HAS_KEY else 'MOCK — no GROQ_API_KEY'}):")
print(f"  Testing first 2 samples only (baaki ke liye saari keys lagti hain):")

for i, sample in enumerate(SAMPLE_DATA[:2]):
    result = llm_judge_faithfulness(sample)
    print(f"\n  Sample {i+1}:")
    print(f"    Question   : {sample.question}")
    print(f"    Answer     : {sample.answer}")
    print(f"    Judge Score: {result.get('faithfulness_score', 'N/A')}")
    print(f"    Reason     : {result.get('reason', 'N/A')}")
    print(f"    Mode       : {result.get('mode', 'unknown')}")


# ============================================================
# SECTION 8: SYNTHETIC TEST SET GENERATION
# ============================================================
print("\n" + "=" * 65)
print("SECTION 8: Synthetic Test Set Generation")
print("=" * 65)

# Theory:
# 50-200 labeled Q&A pairs banana manual tarike se expensive hai.
# LLM ko documents do aur wo automatically Q&A pairs generate karta hai.
# Ragas mein TestsetGenerator hai — hum yahan concept dikhate hain.

SYNTHETIC_GEN_CODE = '''\
# RAGAS ka real synthetic generation (jab ragas installed ho):
from ragas.testset import TestsetGenerator
from langchain_community.document_loaders import TextLoader

# Docs load karo
loader = TextLoader("python_docs.txt")
documents = loader.load()

# Generator banao (OpenAI ya Groq use kar sakta hai)
generator = TestsetGenerator.with_openai()

# 50 Q&A pairs generate karo — different difficulty levels
testset = generator.generate_with_langchain_docs(
    documents,
    test_size=50,
    distributions={
        "simple": 0.5,          # Seedha question — single doc se answer
        "reasoning": 0.25,       # Multiple docs combine karke answer
        "multi_context": 0.25,   # Context across docs chahiye
    }
)

# Dataset format mein convert karo
dataset = testset.to_dataset()
# question, contexts, ground_truth columns mil jayengi
'''
print("\nReal RAGAS Synthetic Generation code (reference ke liye):")
print(SYNTHETIC_GEN_CODE)

# Mock synthetic generation — yeh kaam without ragas library karta hai
def mock_synthetic_generator(documents: List[str], test_size: int = 5) -> List[RAGSample]:
    """
    Mock synthetic test set generator.
    Real TestsetGenerator LLM se Q&A pairs banata hai.
    Hum yahan document se simple patterns extract karte hain.
    """
    patterns = [
        ("kab", "year/date"),
        ("kaun", "person/entity"),
        ("kya", "definition/description"),
        ("kahan", "location"),
        ("kyun", "reason"),
    ]
    samples = []
    for i, doc in enumerate(documents[:test_size]):
        words = doc.split()
        # Simple question generate karo doc se
        q_type, q_hint = patterns[i % len(patterns)]
        question = f"Is document mein {q_hint} kya hai? ({q_type})"
        answer = " ".join(words[:8]) + "..."  # First sentence as mock answer
        samples.append(RAGSample(
            question=question,
            answer=answer,
            contexts=[doc],
            ground_truth=answer,  # mock — real mein expert annotate karta hai
        ))
    return samples


mock_docs = [
    "Python was created by Guido van Rossum in 1991. It emphasizes code readability.",
    "Python supports multiple programming paradigms including OOP and functional programming.",
    "The Python Software Foundation manages Python development and community.",
    "Python 3 was released in 2008 and is not backward compatible with Python 2.",
    "Python is widely used in data science, web development, and automation.",
]

synthetic_samples = mock_synthetic_generator(mock_docs, test_size=5)
print(f"\nMock Synthetic Test Set ({len(synthetic_samples)} samples generated):")
for i, s in enumerate(synthetic_samples):
    print(f"  {i+1}. Q: {s.question}")
    print(f"     A: {s.answer[:60]}")


# ============================================================
# SECTION 9: RAGAS LIBRARY INTEGRATION (Optional)
# ============================================================
print("\n" + "=" * 65)
print("SECTION 9: RAGAS Library Integration (Optional — lazy import)")
print("=" * 65)

# Heavy optional library — lazy import with try/except
# Agar ragas installed nahi hai toh gracefully skip karo

def run_ragas_eval(samples: List[RAGSample]) -> Optional[Dict]:
    """
    Real RAGAS library se evaluation karta hai.
    Agar ragas ya datasets installed nahi hai toh None return karta hai.
    Install: pip install ragas datasets
    """
    try:
        # Lazy import — tabhi import karo jab use karna ho
        import importlib.util
        ragas_spec = importlib.util.find_spec("ragas")
        datasets_spec = importlib.util.find_spec("datasets")

        if ragas_spec is None or datasets_spec is None:
            print("  [INFO] ragas ya datasets installed nahi hain.")
            print("  [INFO] pip install ragas datasets se install karo.")
            print("  [INFO] Skipping real RAGAS eval — mock scores use ho rahe hain.")
            return None

        from ragas import evaluate  # type: ignore
        from ragas.metrics import (  # type: ignore
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from datasets import Dataset  # type: ignore

        # Data format — RAGAS ko dict chahiye
        data = {
            "question":     [s.question for s in samples],
            "answer":       [s.answer for s in samples],
            "contexts":     [s.contexts for s in samples],
            "ground_truth": [s.ground_truth for s in samples],
        }
        dataset = Dataset.from_dict(data)

        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        return dict(result)

    except ImportError as e:
        print(f"  [INFO] Import failed: {e} — ragas library available nahi hai.")
        return None
    except Exception as e:
        print(f"  [INFO] RAGAS eval failed: {e}")
        return None


print("\nTrying real RAGAS library eval...")
ragas_result = run_ragas_eval(SAMPLE_DATA)

if ragas_result:
    print("\nReal RAGAS Scores:")
    for metric, score in ragas_result.items():
        print(f"  {metric:<25}: {score:.3f}")
else:
    print("\n  Real RAGAS library nahi chali — hamari manual scores use kar rahe hain.")
    print(f"  Manual Scores: Faithfulness={avg_faithfulness:.2f}, "
          f"Relevancy={avg_relevancy:.2f}, "
          f"Precision={avg_precision:.2f}, "
          f"Recall={avg_recall:.2f}")

# Real RAGAS code dikhao — reference ke liye
RAGAS_CODE_REF = '''\
# RAGAS official usage (theory doc se):
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

data = {
    "question":     ["Python kab create hua?", "Creator kaun hai?"],
    "answer":       ["Python 1991 mein create hua.", "Guido van Rossum ne banaya."],
    "contexts":     [
        ["Python was created in 1991 by Guido van Rossum."],
        ["Guido van Rossum created Python in the late 1980s."],
    ],
    "ground_truth": [
        "Python 1991 mein Guido van Rossum ne create kiya.",
        "Guido van Rossum ne Python banaya.",
    ],
}

dataset = Dataset.from_dict(data)
result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)
# Expected output:
# {
#   "faithfulness": 0.85,
#   "answer_relevancy": 0.92,
#   "context_precision": 0.78,
#   "context_recall": 0.81
# }
'''
print(f"\nRAGAS Official Code (reference):\n{RAGAS_CODE_REF}")


# ============================================================
# SECTION 10: CI/CD GATE — Score Threshold Check
# ============================================================
print("\n" + "=" * 65)
print("SECTION 10: CI/CD Gate — Score Threshold Validation")
print("=" * 65)

# Theory:
# Production mein CICD pipeline mein RAGAS eval run hota hai.
# Agar koi metric threshold se neeche gire toh PR merge nahi hoti.

PRODUCTION_THRESHOLDS = {
    "faithfulness":       0.85,
    "answer_relevancy":   0.80,
    "context_precision":  0.70,
    "context_recall":     0.81,
}


def cicd_gate_check(scores: Dict[str, float], thresholds: Dict[str, float]) -> bool:
    """
    CICD gate: saare metrics threshold se upar hain?
    Return True = PASS (merge karo), False = FAIL (block karo).
    Theory doc ke GitHub Actions example ka Python equivalent.
    """
    print("\n  CI/CD Gate Results:")
    print(f"  {'Metric':<25} {'Score':>6}  {'Threshold':>10}  {'Result':<10}")
    print(f"  {'-'*25} {'-'*6}  {'-'*10}  {'-'*10}")

    all_pass = True
    for metric, threshold in thresholds.items():
        score = scores.get(metric, 0.0)
        passed = score >= threshold
        if not passed:
            all_pass = False
        result = "PASS" if passed else "FAIL"
        print(f"  {metric:<25} {score:>6.2f}  {threshold:>10.2f}  {result}")

    if all_pass:
        print("\n  STATUS: ALL METRICS PASS — PR merge allow hai.")
    else:
        print("\n  STATUS: SOME METRICS FAIL — PR blocked hai.")
        print("  Action: Low metric wali component improve karo (retriever / chunking / prompts).")

    return all_pass


current_scores = {
    "faithfulness":       avg_faithfulness,
    "answer_relevancy":   avg_relevancy,
    "context_precision":  avg_precision,
    "context_recall":     avg_recall,
}
gate_passed = cicd_gate_check(current_scores, PRODUCTION_THRESHOLDS)

# CICD YAML reference dikhao
CICD_YAML = """\
# .github/workflows/rag_eval.yml  (theory doc se adapted)
name: RAG Quality Check
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install ragas datasets openai
      - run: python eval_rag.py  # scores ko eval_results.json mein save karo
      - name: Fail if faithfulness < 0.85
        run: |
          score=$(python -c "import json; r=json.load(open('eval_results.json')); print(r['faithfulness'])")
          python -c "exit(0 if $score >= 0.85 else 1)"
"""
print(f"\nCI/CD YAML Reference:\n{CICD_YAML}")


# ============================================================
# SECTION 11: PRODUCTION SAMPLING (1% Monitoring)
# ============================================================
print("\n" + "=" * 65)
print("SECTION 11: Production Monitoring — 1% Sampling")
print("=" * 65)

# Theory:
# Production mein SAARE responses eval nahi karte — expensive hai.
# Solution: 1% responses randomly sample karo aur unhe evaluate karo.
# Alert karo jab scores girate hain.

PRODUCTION_ALERTS = {
    "faithfulness":       0.85,  # Hallucination detect karna zaroori
    "answer_relevancy":   0.80,  # Off-topic answers
    "context_precision":  0.70,  # Noisy retrieval
}


def production_eval_sampler(
    request_id: str,
    question: str,
    answer: str,
    contexts: List[str],
    sample_rate: float = 0.01,
) -> Optional[Dict[str, float]]:
    """
    Production monitoring function.
    sample_rate=0.01 matlab 1% requests evaluate honge.
    Baaki 99% pe eval nahi chalega (cost bachao).
    Real mein yeh async background job se hota hai.
    """
    # Random sample check
    random.seed(hash(request_id))
    should_eval = random.random() < sample_rate

    if not should_eval:
        return None  # Is request ko eval nahi karna

    # Eval karo (yahan hum mock function use kar rahe hain)
    sample = RAGSample(
        question=question,
        answer=answer,
        contexts=contexts,
        ground_truth="",  # Production mein ground truth nahi hoti
    )

    scores = {
        "faithfulness":       calculate_faithfulness(sample),
        "answer_relevancy":   calculate_answer_relevancy(sample),
        "context_precision":  calculate_context_precision(sample),
    }
    return scores


def check_production_alerts(scores: Dict[str, float]) -> List[str]:
    """Alert karo agar koi metric threshold se neeche gira."""
    alerts = []
    for metric, threshold in PRODUCTION_ALERTS.items():
        score = scores.get(metric, 1.0)
        if score < threshold:
            alerts.append(
                f"ALERT: {metric} = {score:.2f} (threshold: {threshold}) — investigate!"
            )
    return alerts


# Simulate production traffic
print("\nSimulating 100 production requests (1% sample rate):")
evaluated_count = 0
all_eval_scores: List[Dict] = []

for req_num in range(100):
    # Har request ke liye random data (real mein yeh actual requests hoge)
    req_id = f"req_{req_num:03d}"
    q = random.choice([s.question for s in SAMPLE_DATA])
    a = random.choice([s.answer for s in SAMPLE_DATA])
    ctx = random.choice([s.contexts for s in SAMPLE_DATA])

    result = production_eval_sampler(req_id, q, a, ctx, sample_rate=0.1)  # 10% demo ke liye
    if result:
        evaluated_count += 1
        all_eval_scores.append(result)

print(f"  Total requests: 100")
print(f"  Evaluated: {evaluated_count} (~{evaluated_count}% sampled)")

if all_eval_scores:
    avg_prod_faithfulness = sum(s["faithfulness"] for s in all_eval_scores) / len(all_eval_scores)
    avg_prod_relevancy = sum(s["answer_relevancy"] for s in all_eval_scores) / len(all_eval_scores)
    print(f"\n  Production Metrics (sampled):")
    print(f"    Faithfulness:     {avg_prod_faithfulness:.2f}")
    print(f"    Answer Relevancy: {avg_prod_relevancy:.2f}")

    # Alert check
    prod_avg = {
        "faithfulness": avg_prod_faithfulness,
        "answer_relevancy": avg_prod_relevancy,
        "context_precision": avg_precision,
    }
    alerts = check_production_alerts(prod_avg)
    if alerts:
        print("\n  Production Alerts:")
        for alert in alerts:
            print(f"    {alert}")
    else:
        print("\n  Production Alerts: None — saare metrics thresholds ke upar hain.")


# ============================================================
# SECTION 12: ITERATION LOOP — Improvement Strategy
# ============================================================
print("\n" + "=" * 65)
print("SECTION 12: RAG Improvement Iteration Loop")
print("=" * 65)

# Theory doc ka iteration loop:
# 1. Build initial RAG
# 2. Eval with RAGAS -> scores
# 3. Identify weak metric (e.g., low context_recall)
# 4. Improve component (e.g., hybrid search, reranking)
# 5. Re-eval, compare, ship or iterate

IMPROVEMENT_MAP = {
    "faithfulness":       "Prompt mein 'Only use information from context' add karo. "
                          "Retrieved docs ko verify prompt mein include karo.",
    "answer_relevancy":   "System prompt mein strict question-answering instructions do. "
                          "Answer format specify karo (e.g., 'Answer in one sentence').",
    "context_precision":  "Retrieval improve karo — better embeddings, reranking add karo. "
                          "top_k kam karo — less noise aata hai.",
    "context_recall":     "Hybrid search use karo (BM25 + dense). "
                          "Chunk size badao ya overlap increase karo.",
}

print("\nRAG Iteration Strategy:")
print(f"  {'Low Metric':<25} {'Improvement Action'}")
print(f"  {'-'*25} {'-'*45}")
for metric, action in IMPROVEMENT_MAP.items():
    score = current_scores.get(metric, 0.0)
    needs_work = " <-- IMPROVE" if score < 0.85 else ""
    print(f"  {metric:<25} {action[:55]}{needs_work}")

print("""
  Iteration Loop Steps:
  1. RAGAS se eval karo -> baseline scores
  2. Sabse low metric identify karo
  3. Upar table se improvement action lo
  4. Change implement karo (retriever / chunking / prompt)
  5. Re-eval karo
  6. Scores compare karo
  7. Improved = ship karo, nahi to phir iterate karo
  8. CI/CD mein gate add karo — regression prevent karo
""")


# ============================================================
# SECTION 13: COMMON PITFALLS
# ============================================================
print("\n" + "=" * 65)
print("SECTION 13: Common Pitfalls (Theory Doc se)")
print("=" * 65)

PITFALLS = [
    ("Sirf easy questions pe eval",
     "Scores acche dikhenge but production mein fail hoga. "
     "Hard questions bhi eval set mein include karo."),
    ("Ground truth nahi hai",
     "Context recall measure nahi ho sakta. "
     "50+ annotated pairs zaroor banao."),
    ("Same LLM for generation + eval",
     "Evaluator biased hoga apne hi output ke favor mein. "
     "Alag (stronger) model use karo judge ke liye."),
    ("'Demo works' = skip eval",
     "Demo pe accha dikhna production readiness proof nahi hai. "
     "Systematic eval mandatory hai."),
    ("Ek metric optimize karo, baaki bhool jao",
     "Faithfulness badha to relevancy gir sakti hai. "
     "Saare 4 metrics balance mein rakhne honge."),
]

for pitfall, fix in PITFALLS:
    print(f"\n  PITFALL: {pitfall}")
    print(f"  FIX    : {fix}")


# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 65)
print("RAGAS EVALUATION — FINAL SUMMARY")
print("=" * 65)
print("""
  RAGAS 4 Metrics (theory doc summary):
  1. Faithfulness       — Hallucination detect karta hai (0.85+ target)
  2. Answer Relevancy   — Off-topic answers detect karta hai (0.80+ target)
  3. Context Precision  — Retriever noise measure karta hai (0.70+ target)
  4. Context Recall     — Retriever coverage measure karta hai (0.81+ target)

  Key Patterns Seekhe:
  - LLM-as-Judge: alag model se evaluate karo (bias avoid)
  - Synthetic Test Set: LLM se Q&A pairs generate karwao (50-200)
  - CI/CD Gate: threshold check — block PR agar scores girate hain
  - Production Sampling: 1% requests evaluate karo (cost vs quality balance)
  - Iteration Loop: low metric -> specific component improve karo

  Beyond RAGAS (theory doc se):
  - DeepEval: G-Eval, hallucination, toxicity checks
  - LangSmith: production monitoring + eval integration
  - TruLens: RAG triad evaluation
  - Phoenix (Arize): open-source observability + eval

  Ab kya karo:
  - pip install ragas datasets  -> real RAGAS library use karo
  - GROQ_API_KEY set karo       -> live LLM-as-judge dekho
  - Apne RAG system pe yeh eval run karo
  - CI/CD mein integrate karo
""")

print("=" * 65)
print("Level 5 — RAGAS Evaluation Practical COMPLETE")
print("Exit 0 — Offline mode mein bhi poora chala!")
print("=" * 65)

sys.exit(0)
