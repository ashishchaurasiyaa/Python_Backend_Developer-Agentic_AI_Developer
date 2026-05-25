# Level 2 — Doc 2: Zero-Shot Prompting

> **Goal:** Zero-shot = examples ke bina LLM se kaam karwana. Kab kaam karta hai, kab fail hota hai — clear smajho.

---

## 1. Zero-Shot Kya Hai?

**Zero-shot** = LLM ko **task** do, **no examples**. Bas instruction.

```python
# Zero-shot example
prompt = "Translate to Hindi: 'I love programming'"
# Expected: 'मुझे प्रोग्रामिंग पसंद है'
```

Naam "zero" isliye — kyunki ZERO examples diye gaye.

### Compare with few-shot:
```python
# Few-shot (next doc)
prompt = """
English → Hindi
'Hello' → 'नमस्ते'
'Good morning' → 'सुप्रभात'
'I love programming' → ?
"""
```

---

## 2. Zero-Shot Kab Use Karo?

✅ **Tab when:**
- Task common hai (translation, summarization, basic QA)
- LLM ko ye task training mein dekha hi hoga
- Output format simple hai (string, basic JSON)
- Speed important hai (no example token waste)

❌ **Tab NOT when:**
- Task domain-specific hai (legal jargon, medical codes)
- Output format strict structured chahiye
- Edge cases handle karne hain
- Consistency critical hai (production grade)

---

## 3. Common Zero-Shot Tasks (Jo Work Karte Hain)

### 3.1 Translation
```python
prompt = "Translate to French: 'Where is the bathroom?'"
# Output: "Où sont les toilettes ?"
```
**Why works:** Translation pairs LLM ne lakhon dekhi hain training mein.

### 3.2 Summarization
```python
prompt = """
Summarize this in 2 sentences:

[long article text]
"""
```
**Why works:** Summarization is a common task — well represented in training data.

### 3.3 Classification (Simple)
```python
prompt = """
Classify this review as positive, negative, or neutral:

"The product is okay, nothing special."
"""
# Output: neutral
```
**Why works:** Sentiment analysis is super common.

### 3.4 Code Generation (Standard Tasks)
```python
prompt = "Write a Python function to check if a number is prime."
```
**Why works:** Fibonacci/prime/sorting — patterns LLM ne hazaar baar dekhe.

### 3.5 Q&A (General Knowledge)
```python
prompt = "Who wrote 'War and Peace'?"
# Output: Leo Tolstoy
```

---

## 4. Where Zero-Shot FAILS

### Failure Case 1: Domain-Specific Format
```python
prompt = "Extract the case number, defendant, and verdict from this legal document."
```
**Problem:** Without examples, LLM doesn't know exact JSON field names you want. Output format will be inconsistent.

**Fix:** Few-shot (next doc) OR strict output schema (structured outputs).

---

### Failure Case 2: Custom Categories
```python
prompt = "Classify this support ticket into one of our categories."
```
**Problem:** "Our categories" kya hain? LLM ko pata nahi.

**Fix:**
```python
# Better — list categories in prompt
prompt = """
Classify this ticket into ONE of:
- billing
- technical
- shipping
- refund
- other

Ticket: "I want to cancel my subscription"

Category:
"""
```

---

### Failure Case 3: Style Matching
```python
prompt = "Write an email in our company's tone."
```
**Problem:** "Our tone" undefined. Output will be generic corporate-speak.

**Fix:** Few-shot with 3 sample emails to demonstrate tone.

---

### Failure Case 4: Edge Cases
```python
prompt = "Extract phone numbers from this text."
```
**Problem:** What about formats? `+91-9876543210` vs `9876543210` vs `(987) 654-3210`?

**Fix:** Specify formats explicitly OR few-shot examples.

---

## 5. Improving Zero-Shot (Without Examples)

Tum zero-shot rakhna chahte ho but quality badhana hai? Try these:

### A. Add Constraints in Prompt
```python
# Vague
"Summarize this article"

# Better
"Summarize this article in exactly 3 bullet points, each under 15 words."
```

### B. Specify Output Format
```python
# Vague
"Extract entities"

# Better
"""
Extract entities and return as JSON:
{
  "people": [...],
  "organizations": [...],
  "locations": [...]
}
"""
```

### C. Use "Let's think step by step" (Zero-Shot CoT)
```python
# Without CoT
"What is 23% of 480?"
# Often wrong

# With Zero-Shot CoT
"What is 23% of 480? Let's think step by step."
# Usually correct: 
# Step 1: 23% = 0.23
# Step 2: 0.23 * 480 = 110.4
```
**This is a MASSIVE trick.** Adding "Let's think step by step" improves accuracy on reasoning by 20-40% in many studies.

### D. Specify Role + Context
```python
# Weak zero-shot
"Review this code"

# Strong zero-shot
"You are a senior Python security reviewer. Review this code for OWASP top-10 vulnerabilities only. Return findings as a numbered list."
```

### E. Add Negative Constraints
```python
# Helpful additions
"... Do NOT include preamble. Do NOT explain. Return JSON only."
```

---

## 6. Zero-Shot for Classification (Production Pattern)

```python
def classify_ticket(ticket_text: str) -> str:
    prompt = f"""
You are a customer support classifier.

Classify this ticket into EXACTLY ONE of these categories:
- billing       (payment, refund, invoice)
- technical     (bugs, errors, can't login)
- shipping      (delivery, tracking, returns)
- account       (password, email, settings)
- other         (everything else)

Output only the category name, nothing else.

Ticket: "{ticket_text}"

Category:"""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # Deterministic
        max_tokens=10   # Just the category name
    )
    return response.choices[0].message.content.strip().lower()
```

---

## 7. Production Considerations

### Cost
- Zero-shot = cheapest (no example tokens)
- ~50-200 tokens per request for simple tasks

### Latency
- Faster (smaller prompt = faster response)

### Consistency
- ⚠️ Less consistent than few-shot
- Use `temperature=0` for max consistency
- Validate outputs (Pydantic, JSON schema)

### When Zero-Shot is Production-Ready
✅ Sentiment analysis (well-known task)
✅ Translation (common languages)
✅ Summarization (general)
✅ Standard code tasks
✅ General Q&A with RAG

### When You Need Few-Shot or Fine-tuning
❌ Custom domain (your company's product names, jargon)
❌ Specific output format / schema
❌ Brand-specific tone of voice
❌ Edge case handling

---

## 8. Zero-Shot Chain-of-Thought (CoT) — The Magic Phrase

Researchers ne discover kiya: ek single phrase add karne se reasoning huge boost milta hai:

> "Let's think step by step."

OR

> "Think carefully and explain your reasoning."

### Example without CoT:
```
Q: A bat and ball cost $1.10. The bat costs $1 more than the ball. How much is the ball?
A: $0.10  ❌ WRONG (intuitive but incorrect)
```

### Example with CoT:
```
Q: A bat and ball cost $1.10. The bat costs $1 more than the ball. How much is the ball? 
   Let's think step by step.

A: Let ball = x. Then bat = x + 1.
   Total: x + (x + 1) = 1.10
   2x + 1 = 1.10
   2x = 0.10
   x = 0.05
   Ball is $0.05 ✅ CORRECT
```

This is **zero-shot CoT**. No examples shown, just the magic phrase. Doc 4 mein full CoT cover karenge.

---

## 9. Common Mistakes in Zero-Shot

### Mistake 1: Vague Output Format
```python
# Bad
"Extract user info from this text"

# Good
"""
Extract user info as JSON:
{
  "name": "string",
  "email": "string or null",
  "phone": "string or null"
}
Return only JSON, no other text.
"""
```

### Mistake 2: No Anchoring Examples for Categories
```python
# Bad
"Classify as positive or negative"

# Good
"""
Classify as POSITIVE or NEGATIVE.

POSITIVE = customer is happy, recommends product
NEGATIVE = customer is unhappy, would not recommend
"""
```

### Mistake 3: Asking Too Much
```python
# Bad (asks 4 things at once)
"Summarize this, extract entities, classify sentiment, and translate to French."

# Good (one task per call)
"Summarize this in 2 sentences."
```

### Mistake 4: No Format Constraints
```python
# Bad
"List top 5 features"
# Output might be markdown, paragraphs, or numbered — inconsistent

# Good  
"List top 5 features as JSON array of strings."
```

---

## 10. Interview Questions

1. **Q: When would you use zero-shot over few-shot?**
   - Common tasks where LLM knows the pattern
   - When you want low cost / low latency
   - Prototyping / quick iteration

2. **Q: What's the trick to make zero-shot reasoning better?**
   - Add "Let's think step by step" (zero-shot CoT)
   - Specify output format
   - Use temperature=0 for consistency

3. **Q: Why does zero-shot fail for custom domains?**
   - LLM doesn't know your company-specific terms, formats, categories
   - Solution: Add definitions in prompt OR few-shot examples

4. **Q: How do you measure zero-shot quality?**
   - Create eval set (50-100 labeled examples)
   - Run prompt → compare output to gold
   - Track accuracy, format adherence

---

## 11. Exercises

1. **Easy:** Write a zero-shot prompt for sentiment classification with 3 categories
2. **Medium:** Compare zero-shot vs zero-shot+CoT on 5 math problems
3. **Hard:** Build a zero-shot ticket router with 8 categories. Get >85% accuracy on 50 test tickets
4. **Pro:** Run same task with `temperature=0`, `0.5`, `1.0`. Measure consistency.

---

## 12. Key Takeaways

✅ Zero-shot = no examples, just instruction
✅ Works for common tasks (translation, summarization, sentiment)
✅ Fails for domain-specific / custom formats
✅ **Add "Let's think step by step" for reasoning boost** (huge tip)
✅ Use `temperature=0` for max consistency
✅ Specify output format explicitly (JSON schema, exact categories)
✅ One task per call — don't bundle multiple

**Next:** [03_few_shot.md](03_few_shot.md) — Few-shot prompting with examples
