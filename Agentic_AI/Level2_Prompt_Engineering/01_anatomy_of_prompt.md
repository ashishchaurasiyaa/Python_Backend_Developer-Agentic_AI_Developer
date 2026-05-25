# Level 2 — Doc 1: Anatomy of a Prompt

> **Goal:** Prompt ke building blocks samjho — system, user, assistant messages, aur multi-turn structure. Ye foundation hai. Sab prompt engineering yahin se start hoti hai.

---

## 1. Prompt Kya Hota Hai?

Ek **prompt** matlab woh **complete input** jo tum LLM ko bhejte ho. Beginners ke liye "prompt = question" lagta hai, but production mein prompt = **structured message list** hota hai.

### Common galat-fahmi:
```python
# Beginner thinks prompt = string
prompt = "Translate this to Hindi: Hello"

# Reality: prompt = list of messages with roles
messages = [
    {"role": "system", "content": "You are a translator."},
    {"role": "user", "content": "Translate to Hindi: Hello"}
]
```

OpenAI / Claude / Gemini sab **Chat Completion** format use karte hain. Isme 3 roles hote hain:

| Role | Purpose | Example |
|---|---|---|
| `system` | LLM ko "personality" + rules deta hai | "You are a senior Python developer..." |
| `user` | Actual user message | "How do I fix this bug?" |
| `assistant` | LLM ka previous response (history mein) | "You can use try-except like..." |

---

## 2. The 3 Message Roles — Deep

### A. `system` Message
- LLM ki **identity, rules, constraints** define karta hai
- Conversation ke **start** mein ek baar (mostly)
- User ise dekh nahi sakta — internal hai
- **CRITICAL:** Ye sabse powerful prompt hai. Yahaan jo likhoge, woh poore conversation pe lagega

```python
system = """
You are a senior Python backend engineer.

Rules:
- Always answer in code-first style (code first, then explanation)
- Use type hints in all examples
- Prefer FastAPI over Flask
- If you don't know, say "I don't know" — never make up libraries

Output format:
- Code block (```python)
- 2-line explanation below
- Suggest one related improvement
"""
```

### B. `user` Message
- Actual question / task
- Multi-turn mein multiple user messages hote hain

### C. `assistant` Message
- LLM ka **previous response**
- **History rebuild karne ke liye** use hota hai
- LLM stateless hai — har request mein tum hi history bhejte ho

```python
messages = [
    {"role": "system", "content": "You are a calculator."},
    {"role": "user", "content": "What is 5 + 3?"},
    {"role": "assistant", "content": "5 + 3 = 8"},
    {"role": "user", "content": "Multiply that by 2"}
    # LLM ko pata hai context — kyunki history bheji
]
```

**Pro tip:** Agar history nahi bhejoge, LLM ko nothing yaad nahi. ChatGPT website tumhare liye ye background mein karta hai.

---

## 3. Multi-Turn Conversation Structure

```
[system]         ← Set rules (once at start)
[user 1]         ← User's first question
[assistant 1]    ← LLM's first answer
[user 2]         ← Follow-up question
[assistant 2]    ← LLM's follow-up answer
[user 3]         ← Next question
...
```

**Code:**
```python
conversation_history = [
    {"role": "system", "content": "You are a Python tutor."}
]

def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history
    )
    assistant_message = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_message})
    return assistant_message
```

### Context Window Problem
- Har turn pe history grow hoti hai
- LLM ka context window limit hai (e.g., GPT-4o = 128K tokens, Claude = 200K)
- Long conversations → truncate purane messages ya summarize

**Solutions:**
1. **Sliding window:** Last N messages rakho
2. **Summarization:** Purane messages ka summary banao, replace karo
3. **RAG:** Important parts vector DB mein store karo, retrieve karo

---

## 4. Role-Based Prompting (Persona Setting)

System message mein "role" assign karne se LLM ka behavior nateeke se badalta hai:

```python
# Bad (vague)
system = "Help me with code"

# Good (specific role)
system = "You are a senior staff engineer at Google with 15 years of Python and distributed systems experience. You review code like an interview panelist — strict, but constructive."
```

**Why?** Training data mein "Google staff engineer" se associated answers likely high-quality the. LLM pattern-match karega.

### Common Personas (Production):
- "You are a customer support agent for [Company]"
- "You are a technical writer who explains complex topics simply"
- "You are a data analyst — output only valid JSON"
- "You are a code reviewer — focus only on security issues"

---

## 5. Anthropic Claude vs OpenAI — Subtle Difference

**OpenAI:** System message goes in `messages` list with `role: system`.
**Anthropic:** System message is a **separate parameter** `system=...`.

```python
# OpenAI
openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"}
    ]
)

# Anthropic (note the difference)
anthropic.messages.create(
    model="claude-3-5-sonnet-20241022",
    system="You are helpful.",  # ← Separate param
    messages=[
        {"role": "user", "content": "Hi"}
    ]
)
```

LiteLLM ye difference handle kar leta hai automatically.

---

## 6. Prompt Anatomy Framework (Production Pattern)

Ek good system prompt mein **5 sections** hone chahiye:

```
1. ROLE     — "You are X"
2. CONTEXT  — "Working with Y data" / "User is Z"
3. TASK     — "Your job is to..."
4. RULES    — "Always / Never / Format"
5. EXAMPLES — Few-shot examples (optional but powerful)
```

**Full example:**
```python
system = """
ROLE: You are a SQL query generator for an e-commerce platform.

CONTEXT: 
- Database has tables: users, orders, products, reviews
- Schema is shared in user message
- Users are non-technical product managers

TASK: 
- Convert natural language questions to PostgreSQL queries
- Explain the query in 1 line below the code

RULES:
- Always use parameterized queries (prevent SQL injection)
- Limit results to 1000 rows by default
- Use JOIN over subqueries when possible
- Never include DROP/DELETE/UPDATE — read-only

OUTPUT FORMAT:
```sql
SELECT ...
```
Explanation: 1-line description.

EXAMPLES:
Q: "Top 10 customers by total spend"
A:
```sql
SELECT u.id, u.name, SUM(o.total) as spend
FROM users u JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name
ORDER BY spend DESC LIMIT 10;
```
Explanation: Joins users with orders, sums totals, ranks by spend.
"""
```

---

## 7. Common Mistakes in Prompt Anatomy

### ❌ Mistake 1: No System Message
```python
# Bad
messages = [{"role": "user", "content": "Write a function"}]
```
**Problem:** LLM ne pata hi nahi role kya hai, output unpredictable.

### ❌ Mistake 2: Mixing Instructions in User Message
```python
# Bad
messages = [
    {"role": "user", "content": "You are a Python expert. Now write fibonacci in Python."}
]
```
**Problem:** Role + task mix ho gaye. Better separate karo.

### ❌ Mistake 3: Forgetting History in Multi-Turn
```python
# Bad
def chat(msg):
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": msg}]  # ← No history!
    )
```
**Problem:** Har request fresh hai. "Multiply that by 2" → LLM ko pata hi nahi "that" kya hai.

### ❌ Mistake 4: Conflicting Rules in System
```python
# Bad
system = """
- Be concise
- Provide detailed explanations  
- Output JSON
- Output markdown
"""
```
**Problem:** Contradictions. LLM confused → inconsistent output.

---

## 8. Real-World Production Example

```python
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """
You are an AI customer support agent for "TechShop", an online electronics store.

CONTEXT:
- Your job is to resolve customer queries about orders, returns, products
- Tone: friendly, empathetic, solution-focused
- Language: Match the customer's language (English/Hindi/Spanish)
- You have access to tools: get_order_status, initiate_return, check_inventory

RULES:
- Always greet by name if known
- Never share other customers' data
- For refund/cancel > $500 — escalate to human agent
- If you don't know — say so honestly, offer to escalate
- Don't make promises about delivery dates

OUTPUT:
- Keep responses under 100 words
- End with "Is there anything else I can help with?"
"""

def chat(history: list, user_message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_message}
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3  # Lower = more consistent for support
    )
    return response.choices[0].message.content
```

---

## 9. Interview Questions

1. **Q: System message vs User message — what's the difference?**
   - System = persona/rules (set once, applies to all turns)
   - User = actual query (changes each turn)
   - System is more authoritative

2. **Q: Why does the LLM need conversation history?**
   - LLMs are stateless — every API call is independent
   - To maintain context, YOU re-send the full conversation each time

3. **Q: How do you handle long conversations that exceed context window?**
   - Sliding window (keep last N turns)
   - Summarization (compress old turns)
   - RAG (store + retrieve relevant past)

4. **Q: System prompt mein conflicting rules ka kya effect padta hai?**
   - LLM unpredictable banta hai
   - Mostly last-mentioned rule wins, but not guaranteed
   - Always audit system prompts for contradictions

---

## 10. Practice Exercises

1. **Easy:** Write a system prompt for a haiku generator
2. **Medium:** Build a multi-turn chat with sliding window (last 5 turns)
3. **Hard:** Design a system prompt for legal document summarizer — include role, rules, output format, 2 few-shot examples

---

## 11. Key Takeaways

✅ Prompt = list of `{role, content}` messages, not a single string
✅ System message sets the LLM's personality, rules, constraints
✅ LLMs are stateless — you must re-send history every call
✅ Anthropic Claude has `system` as separate parameter
✅ Use 5-section framework: ROLE, CONTEXT, TASK, RULES, EXAMPLES
✅ Avoid conflicting rules — audit prompts carefully

**Next:** [02_zero_shot.md](02_zero_shot.md) — Zero-shot prompting (just ask, no examples)
