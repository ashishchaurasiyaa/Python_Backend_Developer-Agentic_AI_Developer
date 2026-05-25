# Level 4 — Doc 4: Writing Great Tool Descriptions ⭐

> **Goal:** Tool description writing — the SINGLE most important skill in tool use. Yahaan jo seekhoge wo difference karega working agent vs broken agent.

---

## 1. Why This Matters Most

LLM ko **3 things dikhti hain** about your tool:
1. **Name** (e.g., `get_weather`)
2. **Description** (free text)
3. **Parameters** (with descriptions each)

LLM uses ALL THREE to decide:
- **WHICH** tool to use
- **WHEN** to use it (vs not)
- **HOW** to fill parameters

**Bad description → wrong tool → broken agent.**

This is where most agent bugs originate. Master this, save days of debugging.

---

## 2. The Description Formula

Every tool description should answer:

```
[WHAT] - What does it do? (1 sentence)
[WHEN] - When should LLM use this?
[WHEN NOT] - When should it NOT use this?
[PARAMS] - What does each param mean?
[RETURNS] - What format is the output?
```

### Template:
```
{Tool name}: {What it does in 1 sentence}.

Use this when:
- {Use case 1}
- {Use case 2}

Do NOT use when:
- {Anti-use case 1}
- {Anti-use case 2}

Returns: {Description of return format}
```

---

## 3. Bad vs Good Examples

### ❌ Bad Description
```python
{
    "name": "search",
    "description": "Search"
}
```
Problems:
- Search what? Web? DB? Files?
- When to use?
- What does it return?

### ✅ Good Description
```python
{
    "name": "search_web",
    "description": """Search the web (Google) for current information.

Use this when:
- User asks about current events (news, sports, latest)
- User asks about real-time data (stock prices, weather, current time)
- User asks about specific facts you might be unsure about

Do NOT use when:
- Math calculations (use calculator instead)
- User's personal data (use query_user_data)
- General knowledge well-known before 2024 (just answer from training)

Returns: JSON with 'results' array, each containing 'title', 'url', 'snippet'.""",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Specific search query. Be concrete: 'Tesla Q4 2024 earnings' beats 'Tesla news'."
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return. Default 5, max 10.",
                "default": 5
            }
        },
        "required": ["query"]
    }
}
```

---

## 4. Common Mistakes

### Mistake 1: Too Vague
```python
# Bad
"description": "Get user info"

# Good
"description": "Retrieve customer profile from CRM database including name, email, signup date, and total purchases. Use when answering questions about a specific customer's account."
```

### Mistake 2: Missing "WHEN NOT to use"
```python
# Bad — only positive examples
"description": "Search documentation. Use for product questions."

# Good
"description": "Search internal product docs. Use for OUR product questions ONLY. Do NOT use for general programming questions or competitor info."
```

### Mistake 3: Ambiguous Tool Names
```python
# Bad — what does "process" mean?
"name": "process_data"

# Good
"name": "transform_csv_to_json"
```

### Mistake 4: Same-Sounding Tools (Confusing LLM)
```python
# Bad — LLM can't tell apart
[
    {"name": "send_email", "description": "Send email"},
    {"name": "email", "description": "Email"},
    {"name": "mail", "description": "Send a mail"}
]

# Good — clear differentiation
[
    {"name": "send_email_to_user", "description": "Send email to the current logged-in user"},
    {"name": "send_email_to_team", "description": "Broadcast email to entire team"},
    {"name": "send_email_to_customer", "description": "Send email to a specific customer (needs customer_id)"}
]
```

### Mistake 5: Missing Edge Cases in Params
```python
# Bad
"description": "Date to check"

# Good
"description": "Date in YYYY-MM-DD format. Examples: '2024-12-25'. Do NOT use relative dates like 'tomorrow'."
```

---

## 5. The "Cousin" Problem

LLMs often pick tools that **sound similar** even when wrong. Be explicit about differentiation.

### Example: Search-like tools
```python
[
    {
        "name": "search_web",
        "description": "Web search (Google). For PUBLIC info on the internet."
    },
    {
        "name": "search_company_kb",
        "description": "Internal knowledge base search. For OUR COMPANY info (policies, products, procedures). NOT for general web search."
    },
    {
        "name": "search_emails",
        "description": "Search user's email inbox. For PERSONAL emails. NOT for general info."
    },
    {
        "name": "search_docs",
        "description": "Search uploaded PDF documents. For specific documents the user uploaded. NOT for live web or company KB."
    }
]
```

The `NOT for` clarification prevents LLM from picking the wrong cousin.

---

## 6. Tool Description Length

**Sweet spot:** 50-200 words per tool.

- < 30 words: probably too vague
- > 300 words: token waste, LLM may skip parts

For complex tools, **bullet points** > prose.

---

## 7. Param Descriptions Matter Too

LLM fills params based on **param descriptions**. Be specific:

```python
# Bad
"properties": {
    "user_id": {"type": "string"}
}

# Good
"properties": {
    "user_id": {
        "type": "string",
        "description": "UUID format user identifier. Example: '550e8400-e29b-41d4-a716-446655440000'. NOT email or username."
    }
}
```

### Especially for:
- **IDs** (specify format)
- **Dates** (specify format)
- **Enums** (list allowed values)
- **Booleans** (when true vs false)
- **Optional params** (default behavior)

---

## 8. Show, Don't Just Tell — Examples in Description

LLM learns from examples. Include 1-2 in description:

```python
"description": """Convert natural language to PostgreSQL SQL query.

Examples:
- "Top 10 customers" → 'SELECT * FROM customers ORDER BY total_spent DESC LIMIT 10'
- "Orders from last week" → 'SELECT * FROM orders WHERE created_at > NOW() - INTERVAL 7 DAY'

Use ONLY for SELECT queries. Never INSERT/UPDATE/DELETE."""
```

---

## 9. Negative Examples (When to Refuse)

Tell LLM when to **refuse** to call:

```python
{
    "name": "process_refund",
    "description": """Process a refund up to ₹500 automatically.

Use when:
- Customer requests refund for valid order
- Amount is ≤ ₹500

REFUSE (don't call) when:
- Amount > ₹500 (escalate to human agent)
- Order is older than 30 days
- Customer has 3+ recent refunds (potential fraud)
- Order status is 'delivered_and_signed'

If refusing, explain to user why and suggest escalation."""
}
```

---

## 10. Tool Description Anti-Patterns

### ❌ Marketing language
```
"description": "The amazing weather tool that brings you the best..."
```
LLM doesn't care. Be functional.

### ❌ Internal jargon
```
"description": "Calls the X11-prod endpoint"
```
LLM doesn't know what X11-prod is. Use plain language.

### ❌ Sales-pitch tone
```
"description": "Try this great tool to get awesome results!"
```
Be neutral, factual.

### ❌ Multi-purpose tools
```
"description": "Search, sort, filter, and analyze data"
```
LLM gets confused. **One tool = one purpose.**

---

## 11. Tool Naming Conventions

### ✅ Good naming patterns:
- `verb_noun`: `get_weather`, `send_email`, `create_user`
- Action-oriented: `search_`, `get_`, `create_`, `update_`, `delete_`, `send_`
- Specific: `search_company_kb` not `search`
- Snake_case: Python convention

### ❌ Bad naming:
- One-word: `data`, `info`, `help`
- Vague: `process`, `handle`, `do`
- Camelcase mixed: `getWeatherInfo` (use snake_case)

---

## 12. Production Pattern — Tool Categories

For agents with many tools (10+), **group with consistent naming**:

```python
# Data retrieval (read-only)
- get_user_profile(user_id)
- get_order_history(user_id)
- get_product_details(product_id)

# Search (read-only)
- search_products(query)
- search_orders(query)
- search_users(query)

# Actions (state-changing)
- create_order(...)
- update_address(...)
- cancel_subscription(...)

# Notifications
- send_email(...)
- send_sms(...)
- send_push(...)
```

LLM picks correctly more often when names follow patterns.

---

## 13. Testing Tool Descriptions

How do you know if descriptions are good?

### Test 1: LLM picks right tool
Build 20 test queries, see if LLM picks correct tool >90% of the time.

```python
TEST_CASES = [
    ("What's Tesla stock price?", "get_stock_price"),
    ("Email John about meeting", "send_email"),
    ("Where is my order?", "get_order_status"),
    # ...
]

for query, expected_tool in TEST_CASES:
    actual_tool = run_agent(query).tool_called
    assert actual_tool == expected_tool, f"Failed: {query}"
```

### Test 2: LLM doesn't call when not needed
```python
NON_TOOL_QUERIES = [
    "What is 2+2?",  # Should use calculator, NOT search
    "Hi, how are you?",  # Should not call ANY tool
]
```

### Test 3: LLM fills params correctly
```python
test = "What's the weather in 'mumbai' (lowercase)?"
expected_args = {"city": "Mumbai"}  # Should normalize
# OR
expected_args = {"city": "mumbai"}  # Should leave alone
# Test which behavior you want
```

---

## 14. Iterative Improvement

Tool descriptions evolve. Track failures:

```python
TOOL_FAILURES = []  # Log when LLM picks wrong tool

def log_failure(query, expected, actual):
    TOOL_FAILURES.append({
        "query": query,
        "expected_tool": expected,
        "actual_tool": actual,
        "timestamp": datetime.now()
    })

# Weekly: analyze failures, refine descriptions
def refine_descriptions():
    # Common failure patterns?
    # E.g., LLM keeps confusing search_web with search_kb
    # → Add stronger differentiation in descriptions
```

---

## 15. Description Audit Checklist

For each tool, ask:

- [ ] Name is verb_noun and specific?
- [ ] Description explains WHAT it does (1 sentence)?
- [ ] Description explains WHEN to use?
- [ ] Description explains WHEN NOT to use?
- [ ] Examples included (if useful)?
- [ ] Each param has description?
- [ ] Format constraints specified (UUID, date format)?
- [ ] Differentiation from cousin tools (if any)?
- [ ] Under 200 words?
- [ ] Tested with 10+ queries — LLM picks correctly?

---

## 16. Interview Questions

1. **Q: What's the #1 skill for tool use?**
   - Writing great tool descriptions — most failures originate here.

2. **Q: What makes a description "good"?**
   - WHAT (functional), WHEN (use cases), WHEN NOT (anti-cases), examples, param specs

3. **Q: Why does LLM pick wrong tool?**
   - Usually description ambiguity. Multiple similar-sounding tools without differentiation.

4. **Q: How do you test descriptions?**
   - Build test queries → expected tool. Measure routing accuracy.

5. **Q: How to scale to 50+ tools?**
   - Group with consistent naming (get_*, send_*, search_*), clear differentiation, group categories.

---

## 17. Exercises

1. **Easy:** Audit 5 existing tools — apply the checklist. Fix issues.
2. **Medium:** Build a "cousin" set (search_web, search_kb, search_docs). Make sure LLM distinguishes them.
3. **Hard:** Build test suite — 50 queries, measure tool selection accuracy. Iterate until >95%.
4. **Pro:** Build automatic description generator — Pydantic model + AI generates descriptions for you.

---

## 18. Key Takeaways

✅ Tool descriptions = THE single biggest lever in tool use
✅ Formula: WHAT + WHEN + WHEN NOT + PARAMS + RETURNS
✅ Differentiate "cousin" tools explicitly (`NOT for X`)
✅ Param descriptions matter — specify formats, examples
✅ One tool = one purpose (avoid multi-purpose tools)
✅ Use consistent naming: `verb_noun`, snake_case
✅ Test with 20+ queries; aim >95% routing accuracy
✅ Iterate based on failure logs

**Next:** [05_tool_libraries.md](05_tool_libraries.md) — Building your tool library (calculator, web search, file IO, etc.)
