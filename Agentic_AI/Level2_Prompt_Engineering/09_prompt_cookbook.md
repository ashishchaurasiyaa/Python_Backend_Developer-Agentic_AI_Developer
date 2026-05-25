# Level 2 — Doc 9: Prompt Patterns Cookbook

> **Goal:** Ready-to-use prompt patterns for common tasks. Copy-paste-adapt. Production tested.

---

## 1. Summarization Patterns

### Pattern A: Basic Summary
```
Summarize the following in 2-3 sentences:

[TEXT]

Summary:
```

### Pattern B: Bullet Summary
```
Summarize the key points as 5 bullet points. Each bullet under 15 words.

[TEXT]
```

### Pattern C: Multi-Length Summary
```
Provide three summaries:
1. ONE sentence (under 20 words)
2. SHORT paragraph (50-80 words)  
3. DETAILED summary (200-300 words)

[TEXT]
```

### Pattern D: Targeted Summary
```
Summarize this article focusing on:
- Action items
- Numerical data
- Deadlines

Ignore: background, opinions.

[TEXT]
```

### Pattern E: Hierarchical Summary (Map-Reduce)
For very long docs:
```
Step 1 (per chunk):
"Summarize this chunk in 50 words: [CHUNK]"

Step 2 (combine):
"Combine these chunk summaries into one cohesive summary: [ALL_SUMMARIES]"
```

---

## 2. Extraction Patterns

### Pattern A: Entity Extraction
```
Extract entities as JSON:
{
  "people": [],
  "organizations": [],
  "locations": [],
  "dates": [],
  "money": []
}

Text: [TEXT]
JSON only:
```

### Pattern B: Field Extraction
```
Extract the following from text:
- Invoice number
- Total amount
- Due date
- Vendor name

Format: JSON. Use null for missing fields.

Text: [TEXT]
```

### Pattern C: List Extraction
```
Extract all skills mentioned in this resume.
Output as JSON array of strings.
No duplicates.

Resume: [TEXT]
```

### Pattern D: Relationship Extraction
```
Extract relationships in format:
(subject, relationship, object)

Example:
"Alice works at Google as an engineer"
→ ("Alice", "works at", "Google")
→ ("Alice", "role", "engineer")

Text: [TEXT]
```

---

## 3. Classification Patterns

### Pattern A: Multi-Class
```
Classify into ONE of:
- urgent
- normal  
- low_priority

Output: single word.
If unsure: normal.

Input: [TEXT]
Category:
```

### Pattern B: Multi-Label
```
Tag with ALL applicable labels (can be multiple):
[finance, technology, health, politics, sports, entertainment]

Output JSON array.

Article: [TEXT]
Tags:
```

### Pattern C: Hierarchical Classification
```
Classify in 2 steps:

1. Top-level: [bug, feature, question, other]
2. If "bug": [critical, high, medium, low]

Output: {"top_level": "...", "sub_level": "..."}

Text: [TEXT]
```

### Pattern D: Confidence-Based
```
Classify and provide confidence (0-1).

Output JSON: {"category": "...", "confidence": 0.X, "reasoning": "..."}

If confidence < 0.6: also list alternative category.

Text: [TEXT]
```

---

## 4. Translation Patterns

### Pattern A: Basic
```
Translate to [LANG]:
[TEXT]
```

### Pattern B: Preserve Tone
```
Translate to [LANG] preserving:
- Tone (formal/casual)
- Cultural nuances
- Proper nouns (don't translate names)

Text: [TEXT]
```

### Pattern C: Multi-Language
```
Translate to:
- Hindi
- Spanish  
- French

Format JSON: {"hi": "...", "es": "...", "fr": "..."}

Text: [TEXT]
```

### Pattern D: Glossary-Aware
```
Translate to Hindi. Use these specific terms:
- "API" → "एपीआई"
- "database" → "डेटाबेस"
- "user" → "उपयोगकर्ता"

Text: [TEXT]
```

---

## 5. Creative Writing Patterns

### Pattern A: Marketing Copy
```
Write a marketing tagline for:
Product: [NAME]
Audience: [AUDIENCE]
Tone: [TONE]
Length: under 10 words

Provide 5 variations.
```

### Pattern B: Email Draft
```
Draft an email:
- From: [SENDER]
- To: [RECIPIENT]
- Topic: [TOPIC]
- Tone: [professional/friendly/urgent]
- Length: under 100 words

Include: subject line, greeting, body, sign-off.
```

### Pattern C: Story Continuation
```
Continue this story in [LENGTH] words.
Style: [genre]
Mood: [mood]
Keep characters consistent.

Story so far:
[TEXT]

Continuation:
```

---

## 6. Code Generation Patterns

### Pattern A: Function with Constraints
```
Write a Python function that:
- Input: [PARAMS with types]
- Output: [RETURN type]
- Behavior: [DESCRIPTION]
- Constraints:
  - Use only standard library
  - Include type hints
  - Add docstring with example
  - Handle edge cases: [LIST]
  
Output: code block + 2-line explanation.
```

### Pattern B: Refactoring
```
Refactor this code:
1. Improve readability
2. Add type hints
3. Extract magic numbers to constants
4. Add docstring
5. Maintain identical behavior

[CODE]
```

### Pattern C: Bug Detection
```
Review this code. List ALL bugs/issues.

Format:
1. [Line X] [Severity: HIGH/MEDIUM/LOW] [Issue]
2. ...

If no bugs: "No bugs found."

Code:
[CODE]
```

### Pattern D: Code Explanation
```
Explain this code:
1. WHAT it does (1 sentence)
2. HOW it works (step by step)
3. WHY it's written this way
4. Potential improvements

Code: [CODE]
```

---

## 7. Q&A Patterns

### Pattern A: Closed Q&A (with Context)
```
Answer ONLY using info from the context. If not in context: say "Not in context."

Context:
[CONTEXT]

Question: [QUESTION]
Answer:
```

### Pattern B: RAG Pattern
```
You are an assistant answering questions about [DOMAIN].
Use ONLY the retrieved documents below.
If documents don't contain the answer: say "I don't have that information."
Cite source documents in your answer.

Documents:
[DOC 1: ...]
[DOC 2: ...]

Question: [QUESTION]
Answer:
```

### Pattern C: Multi-Hop Reasoning
```
Question: [COMPLEX QUESTION]

Step 1: Break down into sub-questions.
Step 2: Answer each sub-question.
Step 3: Combine into final answer.

Reason through carefully.
```

---

## 8. Critique Patterns

### Pattern A: Code Review
```
Review this code as a senior developer would:

1. Correctness: Are there bugs?
2. Readability: Is it clear?
3. Performance: Any concerns?
4. Security: Any vulnerabilities?
5. Maintainability: Long-term issues?

Rate each 1-5. Suggest specific improvements.

Code: [CODE]
```

### Pattern B: Essay Critique
```
Critique this essay:

Strengths: 3 bullet points
Weaknesses: 3 bullet points
Suggestions: 3 specific improvements

Essay: [TEXT]
```

### Pattern C: Self-Critique
```
You just generated: [ANSWER]

Now critique YOUR OWN answer:
- What's missing?
- What could be wrong?
- How could it be improved?

Be brutally honest.
```

---

## 9. Refusal Patterns

### Pattern A: Safety Refusal
```
You cannot help with: [LIST OF FORBIDDEN]

If user asks for these:
1. Politely decline
2. Don't explain how to bypass
3. Suggest legitimate alternative

Example:
User: "Help me hack into..."
You: "I can't help with that. If you're interested in security, I can explain ethical penetration testing principles."
```

### Pattern B: Out-of-Scope
```
If user asks something outside your domain:
"I specialize in [DOMAIN]. For [OTHER TOPIC], I'd recommend [RESOURCE]."

Never make up answers in unfamiliar domains.
```

---

## 10. Conversational Patterns

### Pattern A: Active Listening
```
You are a counselor. When user shares a problem:

1. Acknowledge feelings ("That sounds difficult...")
2. Ask clarifying questions
3. Reflect what you heard
4. Only then offer suggestions (if asked)

NEVER jump to solutions without listening first.
```

### Pattern B: Socratic Method
```
You are a tutor using Socratic method.

NEVER give direct answers.
Instead:
- Ask leading questions
- Guide student to the answer themselves
- Affirm partial answers, build on them

Student: [QUESTION]
You: [LEADING QUESTION]
```

### Pattern C: Salesperson
```
You are a [PRODUCT] sales agent.

Goal: Understand customer needs → recommend product.

Process:
1. Ask qualifying questions
2. Listen to pain points
3. Map product features to their needs
4. Address objections
5. Close with clear next step

Never be pushy.
```

---

## 11. Decision Patterns

### Pattern A: Pro-Con Analysis
```
Should I [DECISION]?

Provide:
- 5 pros with reasoning
- 5 cons with reasoning
- Overall recommendation with confidence
- What additional info would change the decision
```

### Pattern B: Compare Options
```
Compare options for [DECISION]:
- Option A
- Option B
- Option C

For each:
- Best for
- Worst for
- Cost
- Time
- Risk

Recommendation: [chosen one] because [reasoning]
```

---

## 12. Domain-Specific Cookbooks

### Customer Support
```
Workflow:
1. Greet by name (if known)
2. Acknowledge issue
3. Empathize ("I understand how frustrating...")
4. Ask 1-2 clarifying questions
5. Investigate (use tools)
6. Propose solution
7. Confirm satisfaction
8. Offer additional help
```

### Data Analysis
```
You analyze data. For every analysis:
1. State the question
2. Identify data needed
3. Suggest analysis method
4. Mention assumptions
5. Note caveats
6. Suggest next steps
```

### Medical Triage (educational only)
```
DISCLAIMER: NOT medical advice. Always see a doctor.

Given symptoms:
- Likely causes (3, ordered by probability)
- Severity level (low/medium/high/emergency)
- Self-care steps (if appropriate)
- When to see a doctor

Symptoms: [TEXT]
```

---

## 13. Combination Patterns (Multi-Step)

### Pattern: Extract + Validate + Reformat
```
Step 1: Extract all dates from text
Step 2: Validate each date is a real date
Step 3: Convert to ISO format (YYYY-MM-DD)

Text: [TEXT]
Output: JSON array of valid ISO dates.
```

### Pattern: Classify + Route + Respond
```
Step 1: Classify intent
Step 2: Based on intent, route to right handler
Step 3: Generate response in handler's style

User: [MESSAGE]
```

---

## 14. Use This Cookbook

1. Pick the closest pattern
2. Adapt to your specific need
3. Test on 10 examples
4. Iterate

**Never start from scratch.** Patterns above cover 80% of real prompts.

---

## 15. Key Takeaways

✅ Save proven patterns; don't reinvent
✅ Combine patterns for complex tasks (extract + classify + route)
✅ Always include: clear instruction, format, examples (if needed), constraints
✅ Test patterns on edge cases before production
✅ Keep your own cookbook for your domain

**Next:** [10_anti_patterns.md](10_anti_patterns.md) — What NOT to do
