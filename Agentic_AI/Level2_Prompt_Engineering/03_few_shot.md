# Level 2 — Doc 3: Few-Shot Prompting

> **Goal:** Examples ke through LLM ko pattern teach karna. Zero-shot kab nahi kaam karta — few-shot save karta hai.

---

## 1. Few-Shot Kya Hai?

**Few-shot prompting** = Prompt mein **2-8 examples** include karke LLM ko pattern dikhana.

```python
prompt = """
Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL.

Examples:
"I love this!" → POSITIVE
"Worst purchase ever." → NEGATIVE
"It's okay, nothing special." → NEUTRAL

Now classify:
"This is amazing!" →
"""
# LLM outputs: POSITIVE
```

Naam "few-shot" — kyunki kuch (few) examples diye gaye.

**Variants:**
- **One-shot** = 1 example
- **Few-shot** = 2-8 examples (most common)
- **Many-shot** = 10-100+ examples (newer research — Claude 3.5+ supports this well)

---

## 2. Few-Shot Kab Use Karo?

✅ **Tab when:**
- Output format custom hai (your specific JSON schema)
- Domain-specific terminology (medical, legal, your product)
- Style/tone matching chahiye (brand voice)
- Edge cases handle karne hain
- Custom categories (your business taxonomy)

❌ **Tab NOT when:**
- Common task hai (zero-shot already works)
- Budget tight hai (examples = extra tokens = extra cost)
- Examples available nahi hain
- Task itna varied hai ki examples mislead karenge

---

## 3. Anatomy of Few-Shot Prompt

```
[INSTRUCTION]
[EXAMPLE 1]
  Input: ...
  Output: ...
[EXAMPLE 2]
  Input: ...
  Output: ...
[EXAMPLE 3]
  Input: ...
  Output: ...
[REAL QUERY]
  Input: ...
  Output:    ← LLM completes here
```

### Format conventions:
- Use clear delimiters (---, ###, ===)
- Be **consistent** across examples (same format)
- Show **edge cases** in examples
- Order: easy → hard, OR random

---

## 4. Few-Shot Examples (Real Production Patterns)

### 4.1 Custom Entity Extraction
```python
prompt = """
Extract product information as JSON.

Example 1:
Input: "Buy iPhone 15 Pro 256GB Space Black for $1,199"
Output: {"product": "iPhone 15 Pro", "storage": "256GB", "color": "Space Black", "price": 1199}

Example 2:
Input: "Samsung Galaxy S24 Ultra 512GB Titanium Gray — ₹1,29,999"
Output: {"product": "Samsung Galaxy S24 Ultra", "storage": "512GB", "color": "Titanium Gray", "price": 129999}

Example 3:
Input: "MacBook Air M3 8GB/256GB Midnight $1,099"
Output: {"product": "MacBook Air M3", "storage": "256GB", "color": "Midnight", "price": 1099}

Now extract:
Input: "Pixel 8 Pro 128GB Obsidian — $999"
Output:
"""
# LLM will match the JSON structure exactly
```

### 4.2 Brand Tone Matching
```python
prompt = """
Rewrite customer messages in our brand voice. We are casual, witty, and use Hindi-English mix.

Example 1:
Customer angry: "I never received my order!"
Our reply: "Arre yaar, sorry for the trouble! Let me track that order for you right now 🚀"

Example 2:
Customer confused: "How do I cancel my subscription?"
Our reply: "No worries! Cancellation is easy-peasy. Settings → Subscriptions → Cancel. Bas done!"

Example 3:
Customer happy: "Loved the product!"
Our reply: "YESSS! Thank you so much 🎉 Reviews like this make our day!"

Now rewrite:
Customer: "The product was delivered but it's broken."
Our reply:
"""
```

### 4.3 Format Conversion
```python
prompt = """
Convert resume bullets to STAR format (Situation, Task, Action, Result).

Example 1:
Bullet: "Improved API response time"
STAR: {
  "situation": "API serving 10k req/sec had P99 latency of 800ms",
  "task": "Reduce latency below 200ms",
  "action": "Added Redis caching + DB query optimization",
  "result": "P99 dropped to 120ms — 85% improvement"
}

Example 2:
Bullet: "Led team migration to microservices"
STAR: {
  "situation": "Monolith struggling with 500+ engineers committing daily",
  "task": "Architect migration to microservices",
  "action": "Designed 12 services, led 6-month migration with 4 engineers",
  "result": "Deployment frequency went from weekly to 50+/day"
}

Now convert:
Bullet: "Built recommendation system"
STAR:
"""
```

### 4.4 Hard-to-Specify Tasks
For tasks where rules are hard to write but examples are easy:

```python
prompt = """
Categorize technical questions by difficulty level.

Examples:
"What is a list?" → BEGINNER
"Difference between is and ==?" → BEGINNER
"How does Python's GIL work?" → INTERMEDIATE
"When to use threads vs asyncio?" → INTERMEDIATE
"Implement a custom metaclass for ORM" → ADVANCED
"Optimize Python bytecode for hot path" → EXPERT

Now categorize:
"What's the difference between a list and tuple?" →
"How does CPython implement dict?" →
"""
```

---

## 5. Choosing Good Examples (CRITICAL)

Bad examples = bad output. Examples chunho carefully.

### 5.1 Cover the Distribution
Agar 90% inputs short hain aur 10% long, **dono** types ke examples do.

### 5.2 Show Edge Cases
```python
# Examples should cover:
- Normal case
- Empty/null inputs
- Very long inputs
- Inputs with special characters
- Inputs in different formats
```

### 5.3 Match Real Distribution
- Production mein 70% positive reviews? → 70% positive examples
- Don't bias examples (e.g., all NEGATIVE) → LLM will favor NEGATIVE

### 5.4 Diversity > Quantity
3 diverse examples > 10 similar ones.

### 5.5 Order Matters (Slightly)
- Recent research: order can affect output
- Best practice: random shuffle OR show easy → hard
- For **strict format compliance**, put strictest format example **last**

---

## 6. Dynamic Few-Shot (Production Pattern)

Production mein **hardcoded examples** kabhi-kabhi work nahi karte. Solution: **dynamic examples** retrieve karo from DB.

```python
def get_dynamic_few_shot(user_query: str, example_db, k: int = 3) -> str:
    """Retrieve k most similar past examples from DB based on semantic similarity."""
    # Embed user query
    query_embedding = embed(user_query)
    
    # Find k most similar examples from database
    similar_examples = example_db.search(query_embedding, top_k=k)
    
    # Build few-shot prompt
    prompt = "Classify the following:\n\nExamples:\n"
    for ex in similar_examples:
        prompt += f"Input: {ex['input']}\nOutput: {ex['output']}\n\n"
    prompt += f"Input: {user_query}\nOutput:"
    return prompt
```

**This is how production tools work.** Tum static 3 examples nahi rakhte — har query ke liye **most relevant** examples DB se lao.

### Benefits:
- Higher accuracy (examples match input style)
- Scales to thousands of edge cases
- Continuous learning (add new labeled examples to DB)

---

## 7. How Many Shots? (Practical Guide)

| Shots | When | Cost | Quality |
|---|---|---|---|
| 0 | Common tasks | Cheapest | Variable |
| 1 | Format demonstration | Low | Better than 0 |
| 3-5 | **Sweet spot** for most cases | Medium | ⭐ Best ROI |
| 6-8 | Complex/varied tasks | High | Marginal gain |
| 20+ | Many-shot (Claude 3.5+, Gemini) | Very high | Sometimes huge gains |

**Research finding (Claude 3.5):** For some tasks, going from 5 to 50 examples gives 10-20% accuracy boost. But cost scales too.

**My rule of thumb:**
- Prototype: Start with 3 examples
- Refine: Add edge cases until accuracy plateaus
- Production: 3-5 carefully chosen examples (or dynamic retrieval)

---

## 8. Few-Shot Format Variations

### Variation A: Simple Q&A
```
Q: What is Python?
A: A programming language.

Q: What is Django?
A: A Python web framework.

Q: What is FastAPI?
A:
```

### Variation B: JSON Examples
```
Input: "Buy 3 apples"
Output: {"action": "buy", "item": "apples", "quantity": 3}

Input: "Sell my Tesla stock"
Output: {"action": "sell", "item": "Tesla stock"}

Input: "Order 2 pizzas"
Output:
```

### Variation C: Chat-Style (System + Multiple Turns)
```python
messages = [
    {"role": "system", "content": "You translate English to Hindi."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "नमस्ते"},
    {"role": "user", "content": "Good night"},
    {"role": "assistant", "content": "शुभ रात्रि"},
    {"role": "user", "content": "Thank you"}  # Real query
]
```
**This is the BEST format** for production. Examples become part of conversation history.

### Variation D: XML-Style (Anthropic Best Practice)
```
<example>
<input>What is 2+2?</input>
<output>4</output>
</example>

<example>
<input>What is 5*3?</input>
<output>15</output>
</example>

<query>
<input>What is 10/2?</input>
<output>
</query>
```
**Anthropic recommends XML tags** for Claude — it's trained to recognize these.

---

## 9. Common Mistakes in Few-Shot

### Mistake 1: Inconsistent Format Across Examples
```python
# BAD
"Example 1: Input='hello', Output='hi'
Example 2: input - 'bye' / output - 'cya'  
Example 3: 'thanks' => 'welcome'"
# LLM gets confused — which format?
```
**Fix:** Pick one format, use it for ALL examples.

### Mistake 2: Biased Examples
```python
# BAD — all examples are POSITIVE
"Examples:
'Great!' → POSITIVE
'Amazing!' → POSITIVE
'Loved it!' → POSITIVE

Classify: 'It sucks'"
```
**Result:** LLM likely outputs POSITIVE (biased by examples).
**Fix:** Balance — 1 positive, 1 negative, 1 neutral.

### Mistake 3: Too Few / Too Many
- 1 example = often not enough to establish pattern
- 20+ examples = waste of tokens, may confuse
- Sweet spot: 3-5

### Mistake 4: Misleading Examples
```python
# BAD
"Examples:
'I love it!' → POSITIVE
'I hate it!' → NEGATIVE"

Classify: "I love hating this"  # LLM confused
```
**Fix:** Include nuanced examples ("It's good but...", "Mixed feelings...")

### Mistake 5: Using Few-Shot When Zero-Shot Suffices
Common tasks (translation, sentiment) → zero-shot already works.
Don't waste tokens on examples LLM doesn't need.

---

## 10. Few-Shot for Tool/Function Selection

Agents mein few-shot use hota hai tool selection ke liye:

```python
prompt = """
Given a user query, select the right tool from: [search_web, calculator, send_email, get_weather].

Examples:
Query: "What's 2+2?" → calculator
Query: "What's the latest news on Tesla?" → search_web
Query: "Email John about meeting" → send_email
Query: "Is it raining in Mumbai?" → get_weather

Query: "Compute 15% tip on $80"
Tool:
"""
```

---

## 11. Interview Questions

1. **Q: When would you use few-shot over zero-shot?**
   - Custom format/schema, domain-specific terminology, brand tone, edge cases

2. **Q: How many examples is optimal?**
   - Start with 3-5. Add more only if accuracy plateaus.

3. **Q: Why does order of examples matter?**
   - Recent research shows order affects output. Best practice: random or easy→hard.

4. **Q: What's "dynamic few-shot"?**
   - At runtime, retrieve most similar examples from DB (vector search) instead of hardcoded examples.

5. **Q: How do you measure if few-shot is helping?**
   - A/B test: zero-shot vs few-shot on test set, measure accuracy delta.

---

## 12. Exercises

1. **Easy:** Convert your zero-shot ticket classifier to few-shot (use 5 examples). Measure accuracy diff.
2. **Medium:** Build a dynamic few-shot system — embed examples in ChromaDB, retrieve top-3 for each query.
3. **Hard:** Brand-voice rewriter — collect 10 examples of your brand's tone, use few-shot for new messages.
4. **Pro:** Compare 0, 1, 3, 5, 10 shots on same task. Plot accuracy vs cost curve.

---

## 13. Key Takeaways

✅ Few-shot = 2-8 examples in prompt to teach pattern
✅ **Use when:** custom format, domain terms, brand tone, edge cases
✅ Examples must be **consistent** in format
✅ Cover the **distribution** — don't bias examples
✅ 3-5 is sweet spot for most cases
✅ **Dynamic few-shot** (retrieval-based) > hardcoded in production
✅ For Claude, use **XML tags** (`<example>...</example>`)
✅ Chat-style few-shot (system + history) works best in conversations

**Next:** [04_chain_of_thought.md](04_chain_of_thought.md) — Chain-of-Thought reasoning
