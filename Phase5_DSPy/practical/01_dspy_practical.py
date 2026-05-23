"""
Phase5_DSPy — Complete Practical
===================================
Topics:
  1. Signatures (Input/Output field declarations)
  2. Modules: Predict, ChainOfThought, ReAct
  3. Optimizers: BootstrapFewShot, MIPRO
  4. RAG pipeline with DSPy
  5. Evaluation + metrics
  6. Assertions and constraints

Install: pip install dspy-ai
Env: OPENAI_API_KEY

Run: python 01_dspy_practical.py
"""

import os
from typing import List

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("DSPY CONCEPTS")
print("=" * 60)

DSPY_CONCEPTS = {
    "Signature":         "Declares input/output fields for a step (replaces manual prompts)",
    "Module":            "Composable building block (Predict, ChainOfThought, ReAct)",
    "Predict":           "Basic LLM call matching a Signature",
    "ChainOfThought":    "Adds 'rationale' field — forces step-by-step reasoning",
    "ReAct":             "Interleaves reasoning + tool actions (Thought/Action/Observation)",
    "Optimizer":         "Automatically tunes prompts/few-shot examples from data",
    "BootstrapFewShot":  "Optimizer: generates few-shot examples by forward-passing train set",
    "MIPRO":             "Optimizer: Bayesian prompt search over instruction + examples",
    "Teleprompter":      "Old name for Optimizer in DSPy",
    "dspy.Assert":       "Hard constraint: program fails if violated",
    "dspy.Suggest":      "Soft constraint: retry if violated (up to max_backtracks)",
}
for k, v in DSPY_CONCEPTS.items():
    print(f"  {k:<22}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Signatures
# INTERVIEW: Signature = what goes IN and what comes OUT (no manual prompt!)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Signatures")
print("=" * 60)

SIGNATURE_CODE = '''\
import dspy

dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

# ── Inline Signature (string format) ──────────────────────────
# INTERVIEW: "input_field -> output_field" format
# DSPy auto-generates the prompt from this!
summarize = dspy.Predict("document -> summary")
result = summarize(document="Python is a high-level language...")
print(result.summary)

# ── Class Signature (richer field descriptions) ───────────────
class SentimentAnalysis(dspy.Signature):
    """Classify the sentiment of text. Be precise."""
    # Input fields
    text:      str = dspy.InputField(desc="The text to analyze")
    # Output fields
    sentiment: str = dspy.OutputField(desc="positive, negative, or neutral")
    confidence:float = dspy.OutputField(desc="confidence score 0.0-1.0")
    reason:    str = dspy.OutputField(desc="one-sentence explanation")

predictor = dspy.Predict(SentimentAnalysis)
result = predictor(text="I absolutely love Python!")
print(result.sentiment)    # "positive"
print(result.confidence)   # 0.95
print(result.reason)       # "Strong positive language detected."

# ── Multi-field Signature ──────────────────────────────────────
class CodeReview(dspy.Signature):
    """Review Python code for bugs and style issues."""
    code:        str = dspy.InputField()
    language:    str = dspy.InputField(desc="programming language")
    bugs:        list[str] = dspy.OutputField(desc="list of bugs found")
    suggestions: list[str] = dspy.OutputField(desc="improvement suggestions")
    score:       int = dspy.OutputField(desc="quality score 1-10")
'''
print(SIGNATURE_CODE[:700])

print("\n  Key insight: DSPy compiles Signatures to optimized prompts.")
print("  You define WHAT, DSPy figures out HOW to prompt the LLM.")
print("  Changing optimizer → different prompt, same Signature.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Modules (ChainOfThought, ReAct)
# INTERVIEW: Modules = composable building blocks, like nn.Module in PyTorch
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: DSPy Modules")
print("=" * 60)

MODULE_CODE = '''\
import dspy

# ── Predict (basic call) ──────────────────────────────────────
predictor = dspy.Predict("question -> answer")
result = predictor(question="What is the GIL in Python?")
print(result.answer)

# ── ChainOfThought (adds rationale field) ─────────────────────
# INTERVIEW: CoT significantly improves accuracy for reasoning tasks
cot = dspy.ChainOfThought("question -> answer")
result = cot(question="If a train travels 60mph for 2 hours, how far?")
print(result.rationale)  # "The train travels 60*2 = 120 miles"
print(result.answer)     # "120 miles"

# ── ChainOfThoughtWithHint ────────────────────────────────────
cot_hint = dspy.ChainOfThoughtWithHint("question, hint -> answer")
result = cot_hint(
    question = "What is 15% of 200?",
    hint     = "Percentage calculation",
)

# ── ReAct (Reasoning + Acting with tools) ────────────────────
def search(query: str) -> str:
    """Search for information."""
    return f"Search results for: {query}"

def calculate(expr: str) -> str:
    """Calculate a math expression."""
    try:
        return str(eval(expr, {"__builtins__": {}}))
    except:
        return "Error in calculation"

react_agent = dspy.ReAct(
    "question -> answer",
    tools = [search, calculate],
    max_iters = 5,
)
result = react_agent(question="What is 1234 * 5678?")
print(result.answer)

# ── Custom Module ─────────────────────────────────────────────
class RAGModule(dspy.Module):
    def __init__(self, num_passages: int = 3):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=num_passages)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question: str) -> dspy.Prediction:
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)

rag = RAGModule(num_passages=3)
result = rag(question="What is Python used for?")
print(result.answer)
'''
print(MODULE_CODE[:700])


# Mock DSPy module demonstration
class MockSignature:
    """Represents a DSPy Signature with fields."""
    def __init__(self, spec: str):
        parts = spec.split("->")
        self.inputs  = [f.strip() for f in parts[0].split(",")]
        self.outputs = [f.strip() for f in parts[1].split(",")]

    def __repr__(self):
        return f"Signature({', '.join(self.inputs)} -> {', '.join(self.outputs)})"


class MockPredict:
    """Mock DSPy Predict module."""
    def __init__(self, signature: str):
        self.sig = MockSignature(signature)

    def __call__(self, **kwargs) -> dict:
        print(f"  [Predict] {self.sig}")
        print(f"  Inputs: {kwargs}")
        return {out: f"[mock {out}]" for out in self.sig.outputs}


class MockChainOfThought(MockPredict):
    """Mock DSPy ChainOfThought — adds rationale."""
    def __call__(self, **kwargs) -> dict:
        print(f"  [ChainOfThought] {self.sig}")
        print(f"  Inputs: {kwargs}")
        result = {out: f"[mock {out}]" for out in self.sig.outputs}
        result["rationale"] = "Step 1: analyze... Step 2: conclude..."
        return result


print("\n  Mock module demo:")
pred = MockPredict("question -> answer")
r1   = pred(question="What is Python?")
print(f"  Result: {r1}")

cot = MockChainOfThought("question -> answer")
r2  = cot(question="Why is Python popular?")
print(f"  CoT result: {r2}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Custom Module (RAG Pipeline)
# INTERVIEW: dspy.Module with forward() = nn.Module pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Custom RAG Module")
print("=" * 60)

RAG_MODULE_CODE = '''\
import dspy

class RAGPipeline(dspy.Module):
    """
    INTERVIEW: dspy.Module = composable AI program.
    forward() = how data flows through the module.
    self.* assignments = learnable parameters (optimized by BootstrapFewShot).
    """
    def __init__(self, num_passages: int = 3):
        super().__init__()
        self.num_passages = num_passages
        # Sub-modules
        self.retrieve      = dspy.Retrieve(k=num_passages)
        self.rerank        = dspy.Predict("query, passages -> ranked_passages")
        self.generate      = dspy.ChainOfThought(
            "context, question -> answer, citations"
        )

    def forward(self, question: str) -> dspy.Prediction:
        # Step 1: Retrieve
        passages = self.retrieve(question).passages

        # Step 2: Rerank
        reranked = self.rerank(
            query    = question,
            passages = passages,
        ).ranked_passages

        # Step 3: Generate with context
        context = "\\n".join(reranked[:self.num_passages])
        pred    = self.generate(context=context, question=question)

        # Step 4: Validate (dspy.Assert for hard constraints)
        dspy.Assert(
            len(pred.answer) > 10,
            "Answer must be at least 10 characters long"
        )
        return pred


class MultiHopRAG(dspy.Module):
    """Multi-hop: retrieve → reason → retrieve again → answer."""
    def __init__(self):
        super().__init__()
        self.retrieve  = dspy.Retrieve(k=3)
        self.hop       = dspy.ChainOfThought("question, context -> next_question")
        self.generate  = dspy.ChainOfThought("all_context, question -> answer")

    def forward(self, question: str) -> dspy.Prediction:
        # Hop 1
        ctx1    = "\\n".join(self.retrieve(question).passages)
        hop1    = self.hop(question=question, context=ctx1)

        # Hop 2 (follow-up question)
        ctx2    = "\\n".join(self.retrieve(hop1.next_question).passages)
        all_ctx = ctx1 + "\\n" + ctx2

        return self.generate(all_ctx=all_ctx, question=question)
'''
print(RAG_MODULE_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Optimizers
# INTERVIEW: BootstrapFewShot = most common optimizer, generates examples
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Optimizers (BootstrapFewShot, MIPRO)")
print("=" * 60)

OPTIMIZER_CODE = '''\
import dspy
from dspy.teleprompt import BootstrapFewShot, MIPRO, BootstrapFewShotWithRandomSearch

# ── Training data ──────────────────────────────────────────────
# INTERVIEW: DSPy only needs input/output pairs — no manual prompts!
trainset = [
    dspy.Example(
        question = "What is Python?",
        answer   = "Python is a high-level interpreted programming language.",
    ).with_inputs("question"),
    dspy.Example(
        question = "What is async/await in Python?",
        answer   = "async/await enables non-blocking concurrent code execution.",
    ).with_inputs("question"),
    # ... more examples
]

# ── Define metric ──────────────────────────────────────────────
def answer_quality(example, pred, trace=None) -> float:
    """
    INTERVIEW: Metric function returns float 0-1 or bool.
    Optimizer maximizes this metric on validation set.
    """
    # In real use: check semantic similarity or exact match
    correct_words = set(example.answer.lower().split())
    pred_words    = set(pred.answer.lower().split())
    overlap       = len(correct_words & pred_words)
    return overlap / max(len(correct_words), 1)

# ── BootstrapFewShot ───────────────────────────────────────────
# INTERVIEW: Most commonly used optimizer
# 1. Forward passes on trainset to gather examples
# 2. Selects best examples as few-shot demonstrations
optimizer = BootstrapFewShot(
    metric              = answer_quality,
    max_bootstrapped_demos = 4,    # max few-shot examples per predictor
    max_labeled_demos      = 8,    # max labeled examples from train set
)

# Compile = optimize the program
program = RAGPipeline()
optimized = optimizer.compile(
    student    = program,
    trainset   = trainset,
    valset     = trainset[:2],   # validation set
)

# Optimized program has better few-shot examples in each Predict/CoT module
result = optimized(question="What is the GIL?")

# ── MIPRO (more powerful, slower) ─────────────────────────────
mipro = MIPRO(
    metric         = answer_quality,
    num_candidates = 10,   # instruction variations to try
    init_temperature = 1.0,
)
mipro_optimized = mipro.compile(
    program,
    trainset     = trainset,
    max_bootstrapped_demos = 3,
    max_labeled_demos      = 5,
    num_trials   = 20,     # Bayesian optimization trials
)

# ── Save/Load optimized program ────────────────────────────────
optimized.save("optimized_rag.json")
loaded = RAGPipeline()
loaded.load("optimized_rag.json")
'''
print(OPTIMIZER_CODE[:700])

print("\n  Optimizer comparison:")
OPTIMIZERS = {
    "BootstrapFewShot":                "Fast, generates few-shot examples. Start here.",
    "BootstrapFewShotWithRandomSearch":"BootstrapFewShot + random search over examples",
    "MIPRO":                           "Bayesian search over instructions + examples. Slow but best.",
    "BayesianSignatureOptimizer":      "Optimizes Signature instructions using Bayesian methods",
    "Ensemble":                        "Combine multiple optimized programs",
}
for opt, desc in OPTIMIZERS.items():
    print(f"  {opt:<40}: {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Assertions
# INTERVIEW: Assert = hard constraint, Suggest = soft (retry)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Assertions & Constraints")
print("=" * 60)

ASSERT_CODE = '''\
import dspy

class ConstrainedQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(
            "question -> answer, confidence"
        )

    def forward(self, question: str) -> dspy.Prediction:
        pred = self.generate(question=question)

        # ── Hard constraint (dspy.Assert) ──────────────────────
        # INTERVIEW: Raises AssertionError if violated (stops pipeline)
        dspy.Assert(
            len(pred.answer) >= 20,
            "Answer must be at least 20 characters."
        )
        dspy.Assert(
            pred.confidence.replace(".", "").replace("%", "").isdigit(),
            "Confidence must be a number."
        )

        # ── Soft constraint (dspy.Suggest) ────────────────────
        # INTERVIEW: Retries the module if violated (up to max_backtracks)
        dspy.Suggest(
            "I don\'t know" not in pred.answer.lower(),
            "Try to provide a specific answer, not \'I don\'t know\'."
        )
        dspy.Suggest(
            len(pred.answer.split()) >= 10,
            "Provide a more detailed answer."
        )

        return pred

# Enable retries for Suggest constraints
program = dspy.assert_transform_module(
    ConstrainedQA(),
    dspy.backtrack_handler,
    max_backtracks = 3,   # retry up to 3 times if Suggest fails
)
'''
print(ASSERT_CODE[:600])


print("\n" + "=" * 60)
print("DSPY INTERVIEW SUMMARY:")
print("  DSPy = Declarative Self-improving Python (no manual prompt engineering)")
print("  Signature: 'input -> output' — defines structure, NOT the prompt")
print("  Predict: basic call. ChainOfThought: adds rationale. ReAct: tools")
print("  Module: class with forward() — composable like PyTorch nn.Module")
print("  BootstrapFewShot: optimizer — auto-generates few-shot examples")
print("  dspy.Assert: hard constraint. dspy.Suggest: soft (retries)")
print("  vs LangChain: DSPy optimizes prompts; LangChain wires them manually")
print("=" * 60)
