# DSPy — Signatures, Modules, Optimizers (Prompt Programming)

## Quick Concepts
- **DSPy** = Declarative Self-improving Python — LLM programs ko prompt manually likhne ki jagah code likhte hain
- **Signature** = input/output types define karo — DSPy automatically prompt banata hai
- **Module** = ChainOfThought, Retrieve, ProgramOfThought — building blocks
- **Optimizer (Teleprompter)** = few-shot examples ya prompt instructions automatically optimize karo
- **Key insight**: DSPy mein "programming" hoti hai, "prompting" nahi

---

## Interview Questions & Answers

### Q1: DSPy kya hai? Basic usage?
**Answer:**
```python
# pip install dspy-ai

import dspy
from dspy import Signature, InputField, OutputField

# ===== CONFIGURE LLM =====
# Claude ke saath
claude = dspy.Claude(model="claude-sonnet-4-6")
dspy.settings.configure(lm=claude)

# OpenAI ke saath
# gpt4 = dspy.OpenAI(model="gpt-4o-mini", max_tokens=500)
# dspy.settings.configure(lm=gpt4)

# ===== SIGNATURES — Input/Output define karo =====

# Simple signature (string shorthand)
# "input_field -> output_field"
class BasicQA(dspy.Signature):
    """Answer questions with short factual answers."""
    question = InputField()
    answer = OutputField(desc="often between 1 and 5 words")

# Detailed signature
class SentimentClassifier(dspy.Signature):
    """Classify the sentiment of customer feedback."""
    
    feedback: str = InputField(desc="Customer feedback text")
    sentiment: str = OutputField(desc="One of: POSITIVE, NEGATIVE, NEUTRAL, MIXED")
    confidence: float = OutputField(desc="Confidence score between 0.0 and 1.0")
    reasoning: str = OutputField(desc="Brief explanation of the classification")

class CodeReviewer(dspy.Signature):
    """Review Python code and identify issues."""
    
    code: str = InputField(desc="Python code to review")
    language: str = InputField(desc="Programming language", default="python")
    issues: list[str] = OutputField(desc="List of identified issues")
    severity: str = OutputField(desc="Overall severity: LOW, MEDIUM, HIGH, CRITICAL")
    improved_code: str = OutputField(desc="Improved version of the code")

# ===== PREDICT — Simplest module =====
predict = dspy.Predict(BasicQA)
result = predict(question="What is the capital of France?")
print(result.answer)  # "Paris"
print(result.completions)  # all completions

# Sentiment classification
sentiment_classifier = dspy.Predict(SentimentClassifier)
result = sentiment_classifier(feedback="The product is great but shipping was slow!")
print(f"Sentiment: {result.sentiment}")
print(f"Confidence: {result.confidence}")
print(f"Reasoning: {result.reasoning}")
```

---

### Q2: ChainOfThought aur aur modules kaise use karte hain?
**Answer:**
```python
import dspy

dspy.settings.configure(lm=dspy.Claude(model="claude-sonnet-4-6"))

# ===== CHAIN OF THOUGHT =====
class MathProblem(dspy.Signature):
    """Solve mathematical problems step by step."""
    problem: str = InputField()
    solution: str = OutputField(desc="Final numerical answer")

# ChainOfThought: automatically "Let's think step by step" add karta hai
cot_solver = dspy.ChainOfThought(MathProblem)

result = cot_solver(problem="If a train travels 60 mph for 2.5 hours, then 80 mph for 1.5 hours, total distance?")
print(f"Reasoning: {result.rationale}")  # step-by-step thinking
print(f"Solution: {result.solution}")

# ===== MULTI-STEP MODULE =====
class SummarizeAndClassify(dspy.Module):
    """Summarize text then classify it"""
    
    def __init__(self):
        super().__init__()
        
        self.summarizer = dspy.ChainOfThought("text -> summary")
        self.classifier = dspy.Predict(
            dspy.Signature(
                "text, summary -> category",
                "Classify into: technical, business, general, news"
            )
        )
    
    def forward(self, text: str) -> dspy.Prediction:
        summary = self.summarizer(text=text)
        category = self.classifier(text=text, summary=summary.summary)
        
        return dspy.Prediction(
            summary=summary.summary,
            category=category.category,
        )

pipeline = SummarizeAndClassify()
result = pipeline(text="FastAPI version 0.100 introduces major performance improvements through Pydantic v2 integration and async SQLAlchemy support...")
print(f"Summary: {result.summary}")
print(f"Category: {result.category}")

# ===== RAG MODULE =====
class RAGSignature(dspy.Signature):
    """Answer questions using retrieved context."""
    context: list[str] = InputField(desc="Retrieved documents")
    question: str = InputField()
    answer: str = OutputField(desc="Factual answer based on context")
    citations: list[int] = OutputField(desc="Indices of context docs used")

class RAGModule(dspy.Module):
    def __init__(self, retriever, num_passages: int = 5):
        super().__init__()
        self.retriever = retriever
        self.num_passages = num_passages
        self.generate_answer = dspy.ChainOfThought(RAGSignature)
    
    def forward(self, question: str) -> dspy.Prediction:
        # Retrieve relevant documents
        passages = self.retriever.forward(question, k=self.num_passages).passages
        
        # Generate answer with CoT
        prediction = self.generate_answer(
            context=passages,
            question=question,
        )
        
        return dspy.Prediction(
            answer=prediction.answer,
            citations=prediction.citations,
            context=passages,
        )

# ===== ASSERTION-BASED REFINEMENT =====
class FactualQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought("question -> answer")
    
    def forward(self, question: str) -> dspy.Prediction:
        result = self.generate(question=question)
        
        # Assertions — if violated, DSPy retries with feedback
        dspy.Assert(
            len(result.answer) > 5,
            "Answer must be more than 5 characters long",
        )
        dspy.Suggest(  # soft constraint — won't raise, just feedback
            "Paris" not in result.answer or "France" in question,
            "Mention the country when talking about Paris",
        )
        
        return result
```

---

### Q3: Optimizers — few-shot examples automatically generate karna?
**Answer:**
```python
import dspy
from dspy.teleprompt import (
    BootstrapFewShot,
    BootstrapFewShotWithRandomSearch,
    MIPRO,
    BayesianSignatureOptimizer,
)

# ===== SETUP =====
dspy.settings.configure(
    lm=dspy.Claude(model="claude-sonnet-4-6"),
    rm=dspy.ColBERTv2(url="http://20.102.90.50:2017/wiki17_abstracts"),  # retriever
)

# ===== TRAINING DATA =====
# Few examples chahiye optimizer ke liye
train_data = [
    dspy.Example(
        question="What causes rain?",
        answer="Water vapor condenses into droplets that fall due to gravity",
    ).with_inputs("question"),
    
    dspy.Example(
        question="What is photosynthesis?",
        answer="Process where plants convert sunlight to food using CO2 and water",
    ).with_inputs("question"),
    
    dspy.Example(
        question="What is DNA?",
        answer="Molecule carrying genetic instructions for development and functioning",
    ).with_inputs("question"),
    # Need ~20+ examples for good optimization
]

# Validation examples
val_data = [
    dspy.Example(
        question="How does WiFi work?",
        answer="Radio waves transmit data between devices and router wirelessly",
    ).with_inputs("question"),
]

# ===== METRIC FUNCTION =====
def answer_quality_metric(example, prediction, trace=None) -> float:
    """Score: 0.0 to 1.0"""
    # Simple length check
    if len(prediction.answer) < 10:
        return 0.0
    
    # Check key words present (simplified)
    if example.answer and any(
        word in prediction.answer.lower()
        for word in example.answer.lower().split()[:3]
    ):
        return 1.0
    
    return 0.5

# ===== BOOTSTRAP FEW-SHOT OPTIMIZER =====
student_program = dspy.Predict("question -> answer")

optimizer = BootstrapFewShot(
    metric=answer_quality_metric,
    max_bootstrapped_demos=4,  # max few-shot examples to add
    max_labeled_demos=4,
    max_rounds=1,
)

# Optimize!
optimized_program = optimizer.compile(
    student=student_program,
    trainset=train_data,
)

# Inspect optimized prompt
optimized_program.save("optimized_qa.json")

# Compare: before vs after
before_answer = student_program(question="What is entropy?").answer
after_answer = optimized_program(question="What is entropy?").answer
print(f"Before: {before_answer}")
print(f"After: {after_answer}")

# ===== MIPRO (Advanced) =====
# MIPRO optimizes both instructions AND few-shot examples
mipro_optimizer = MIPRO(
    metric=answer_quality_metric,
    prompt_model=dspy.Claude(model="claude-sonnet-4-6"),
    task_model=dspy.Claude(model="claude-haiku-4-5-20251001"),  # cheaper for evaluation
    verbose=True,
)

optimized_mipro = mipro_optimizer.compile(
    student_program,
    trainset=train_data,
    valset=val_data,
    num_trials=10,          # bayesian optimization trials
    max_bootstrapped_demos=3,
)
```

---

### Q4: Complex DSPy programs — multi-hop reasoning?
**Answer:**
```python
import dspy

class HopSearchSignature(dspy.Signature):
    """Search for information to help answer a complex question."""
    context: list[str] = InputField(desc="Previously retrieved information")
    question: str = InputField()
    search_query: str = OutputField(desc="Specific search query for next hop")

class AnswerFromContext(dspy.Signature):
    """Answer complex question using accumulated context."""
    context: list[str] = InputField(desc="All retrieved information")
    question: str = InputField()
    answer: str = OutputField()
    confidence: float = OutputField(desc="0.0 to 1.0")

class MultiHopQA(dspy.Module):
    """Answer questions requiring multiple search steps"""
    
    def __init__(self, retriever, num_hops: int = 3):
        super().__init__()
        self.retriever = retriever
        self.num_hops = num_hops
        self.generate_query = dspy.ChainOfThought(HopSearchSignature)
        self.generate_answer = dspy.ChainOfThought(AnswerFromContext)
    
    def forward(self, question: str) -> dspy.Prediction:
        context = []
        
        for hop in range(self.num_hops):
            # Generate targeted search query
            hop_result = self.generate_query(
                context=context,
                question=question,
            )
            
            # Search
            retrieved = self.retriever(hop_result.search_query, k=3).passages
            context.extend(retrieved)
            
            print(f"Hop {hop+1} query: {hop_result.search_query}")
            print(f"Retrieved {len(retrieved)} passages")
        
        # Generate final answer from accumulated context
        answer = self.generate_answer(
            context=context,
            question=question,
        )
        
        dspy.Assert(answer.confidence > 0.5, "Answer confidence too low")
        
        return dspy.Prediction(
            answer=answer.answer,
            confidence=answer.confidence,
            context=context,
            rationale=answer.rationale,
        )

# ===== TEXT CLASSIFICATION WITH DSPY =====
class TextClassifier(dspy.Module):
    """Multi-label text classifier"""
    
    def __init__(self, categories: list[str]):
        super().__init__()
        self.categories = categories
        categories_str = ", ".join(categories)
        
        self.classifier = dspy.ChainOfThought(
            dspy.Signature(
                f"text -> category",
                f"Classify the text into exactly one of: {categories_str}. Return only the category name."
            )
        )
    
    def forward(self, text: str) -> dspy.Prediction:
        result = self.classifier(text=text)
        
        dspy.Assert(
            result.category in self.categories,
            f"Category must be one of {self.categories}, got: {result.category}"
        )
        
        return dspy.Prediction(
            category=result.category,
            reasoning=result.rationale,
        )

classifier = TextClassifier(["technical", "business", "sports", "entertainment", "science"])
result = classifier(text="FastAPI now supports WebSockets natively in version 0.100")
print(f"Category: {result.category}")
```

---

### Q5: DSPy vs LangChain/Instructor — kab kya use karo?
**Answer:**
```
DSPy (Declarative Self-improving Python):
  ✓ Prompts ko automatically optimize karna hai
  ✓ Training data available hai (20+ examples)
  ✓ Systematic A/B testing of prompts
  ✓ Research/academic work
  ✓ Production systems jahan prompt quality critical hai
  ✗ More complex setup
  ✗ Needs labeled examples for optimization
  ✗ Newer ecosystem, less community support

LangChain:
  ✓ Quick prototyping
  ✓ Large ecosystem (100+ integrations)
  ✓ Document loading, RAG pipelines
  ✗ Manual prompt engineering
  ✗ No automatic optimization

Instructor:
  ✓ Pydantic structured output extraction
  ✓ Auto-retry on validation failure
  ✓ Simple integration with existing code
  ✗ No optimization
  ✗ Single LLM call focus

DECISION TABLE:
  Need structured output → Instructor
  RAG pipeline → LangChain + FAISS/pgvector
  Multi-step agent → LangGraph
  Auto-optimize prompts → DSPy
  Multi-agent team → CrewAI

DSPy Best Use Cases:
  1. Classification tasks (sentiment, intent detection)
  2. Information extraction pipelines
  3. QA systems requiring high accuracy
  4. When you have evaluation data and want
     to systematically improve prompt quality

DSPy Core Insight:
  Traditional: Write prompt → hope it works
  DSPy:        Define metric → compile → automatic improvement
               Like ML training but for prompts
```
