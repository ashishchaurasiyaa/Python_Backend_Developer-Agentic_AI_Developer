# Level 4 — Doc 1: What is Tool Use?

> **Goal:** Tool use samjhna — the foundational concept that turns LLMs into **agents**. Without tools, LLM can only chat. With tools, it can do.

---

## 1. The Big Idea

A plain LLM can only **generate text**. It can't:
- Search the web
- Read your database
- Send an email
- Run code
- Check the weather

**Tool use** = giving the LLM the ability to **call your Python functions** when it needs to.

```
User: "What's the weather in Mumbai right now?"

LLM thinks: "I don't have real-time data. I need to call get_weather()"
LLM outputs: tool_call(get_weather, city="Mumbai")
Your code: actually calls get_weather("Mumbai") → returns "32°C, sunny"
LLM continues: "It's 32°C and sunny in Mumbai."
```

**This is the core mechanism that makes Agentic AI possible.**

---

## 2. Function Calling vs Tool Use — Same Thing

- **OpenAI** says "function calling" 
- **Anthropic** says "tool use"
- **Same concept**

Don't get confused by terminology. Both = LLM picks a function from a list, your code runs it, LLM continues with results.

---

## 3. The Tool Use Loop

```
                   ┌─────────────────────────────────┐
                   │  USER MESSAGE                    │
                   └─────────────┬───────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────────────┐
                   │  LLM RECEIVES message + tool defs│
                   └─────────────┬───────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────────────┐
                   │  LLM decides:                    │
                   │  - Use a tool? (which? args?)    │
                   │  - Or just respond?              │
                   └─────────────┬───────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
            ┌──────────────┐         ┌──────────────────┐
            │ Final answer │         │ Tool call request│
            │  → return    │         └────────┬─────────┘
            └──────────────┘                  │
                                              ▼
                                  ┌──────────────────────┐
                                  │ YOUR CODE executes   │
                                  │ the function         │
                                  └────────┬─────────────┘
                                           │
                                           ▼
                                  ┌──────────────────────┐
                                  │ Tool result sent     │
                                  │ back to LLM          │
                                  └────────┬─────────────┘
                                           │
                                           ▼
                              ┌───────────────────────────┐
                              │  LLM continues (loop back │
                              │  to "LLM decides...")     │
                              └───────────────────────────┘
```

LLM and your code go back-and-forth until LLM has enough info to answer.

---

## 4. Concrete Example — Weather Bot

### Step 1: Define a tool
```python
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # In reality, call a weather API
    return {"temp": 32, "condition": "sunny", "city": city}
```

### Step 2: Tell LLM about it (schema)
```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for any city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    }
}]
```

### Step 3: Send to LLM
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What's the weather in Mumbai?"}],
    tools=tools  # ← Pass tool definitions
)
```

### Step 4: LLM responds with tool call
```python
# response.choices[0].message contains:
{
    "content": None,
    "tool_calls": [{
        "id": "call_abc123",
        "function": {
            "name": "get_weather",
            "arguments": '{"city": "Mumbai"}'
        }
    }]
}
```

### Step 5: Your code executes the tool
```python
tool_call = response.choices[0].message.tool_calls[0]
func_name = tool_call.function.name  # "get_weather"
func_args = json.loads(tool_call.function.arguments)  # {"city": "Mumbai"}

# Call the actual function
result = get_weather(**func_args)  # {"temp": 32, ...}
```

### Step 6: Send result back to LLM
```python
messages = [
    {"role": "user", "content": "What's the weather in Mumbai?"},
    {"role": "assistant", "tool_calls": [...], "content": None},  # LLM's tool request
    {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": json.dumps(result)  # The tool result
    }
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=tools
)
```

### Step 7: LLM responds with natural language
```python
# response.choices[0].message.content:
"It's currently 32°C and sunny in Mumbai."
```

---

## 5. Why This is HUGE

Without tool use, LLMs are limited to:
- Trained knowledge (stale)
- Text generation
- Reasoning about what they were told

With tool use, LLMs can:
- **Access live data** (weather, stocks, your DB)
- **Take actions** (send email, write file, deploy code)
- **Use specialized capabilities** (Python interpreter, image generation)
- **Build complex workflows** (chains of tool calls)

**This is the difference between a chatbot and an agent.**

---

## 6. Real-World Use Cases

### A. Personal Assistant
```python
tools = [
    schedule_meeting,
    send_email,
    search_calendar,
    create_reminder,
    search_contacts,
]
# User: "Schedule a meeting with John next Tuesday at 3 PM"
# → LLM calls search_contacts(John) → schedule_meeting(...)
```

### B. Customer Support Bot
```python
tools = [
    get_order_status,
    initiate_refund,
    update_shipping_address,
    create_support_ticket,
]
# Customer: "Where's my order #12345?"
# → LLM calls get_order_status(12345) → responds with details
```

### C. Coding Assistant
```python
tools = [
    read_file,
    write_file,
    run_tests,
    execute_python,
    search_codebase,
]
# Dev: "Fix the bug in user_service.py"
# → LLM reads file → analyzes → writes fix → runs tests
```

### D. Data Analyst Agent
```python
tools = [
    query_database,
    create_chart,
    run_python_analysis,
    export_csv,
]
# User: "Show me monthly revenue trends as a chart"
# → LLM queries DB → analyzes → creates chart → exports
```

---

## 7. LLM Decides Which Tool — How?

LLM looks at:
1. **User's intent** (what do they want?)
2. **Tool descriptions** (what does each tool do?)
3. **Tool parameters** (what args does it need?)

**KEY INSIGHT:** Tool description is the **most important part**. Bad description → LLM picks wrong tool.

```python
# Bad description
{"name": "search", "description": "Search"}
# LLM has no idea WHAT it searches

# Good description
{
    "name": "search_company_kb",
    "description": "Search the internal company knowledge base for product info, policies, and FAQs. Use this for questions about our products or company policies. Do NOT use for general web search."
}
```

We'll cover writing great descriptions in [04_tool_descriptions.md](04_tool_descriptions.md).

---

## 8. Multiple Tools — LLM Routes

Pass multiple tools, LLM picks the right one:

```python
tools = [
    {"name": "get_weather", "description": "Get current weather"},
    {"name": "search_web", "description": "Search the internet"},
    {"name": "send_email", "description": "Send an email"},
    {"name": "get_stock_price", "description": "Get current stock price"},
]

# User: "What's Apple's stock price?"
# → LLM picks get_stock_price(symbol="AAPL")

# User: "Email John about the meeting"  
# → LLM picks send_email(to="john", subject="...", body="...")
```

---

## 9. Multi-Step Tool Use (Chained)

For complex tasks, LLM may use multiple tools in sequence:

```
User: "Email me a summary of today's news about Tesla"

LLM Step 1: Call search_web(query="Tesla news today")
→ Returns 5 articles

LLM Step 2: Call summarize(articles=...)
→ Returns summary

LLM Step 3: Call send_email(to=user, subject="Tesla news", body=summary)
→ Returns "sent"

LLM Step 4: Reply to user "Done, sent the summary"
```

Each tool call is a separate round-trip with the LLM.

---

## 10. Tool Use vs RAG vs Fine-tuning

| Method | Use Case |
|---|---|
| **Tool Use** | Take ACTIONS, access LIVE data |
| **RAG** | Answer questions from your DOCS |
| **Fine-tuning** | Change LLM's STYLE or specialized knowledge |

They complement each other. Production agents use all three.

---

## 11. Common Patterns to Master

We'll cover these in detail in next docs:

1. **Single tool call** — basic pattern
2. **Multiple tools** — routing
3. **Parallel tool calls** — call N tools at once
4. **Sequential tool calls** — chain results
5. **Forced tool use** — make LLM use specific tool
6. **Error handling** — tool failures, retries
7. **Tool descriptions** — the most important skill

---

## 12. Interview Questions

1. **Q: What's the difference between function calling and tool use?**
   - Same concept, different vendor naming (OpenAI vs Anthropic)

2. **Q: Explain the tool use loop.**
   - LLM gets message + tools → decides to call tool → your code runs → result back → LLM continues or returns

3. **Q: What's the MOST important factor in good tool use?**
   - Tool description quality — LLM uses it to decide WHICH tool and WHEN

4. **Q: Tool use vs RAG?**
   - Tool use = actions + live data. RAG = retrieve docs for context.

5. **Q: How does the LLM "know" to call a tool?**
   - LLM is trained to detect when info needed isn't in its training. Sees tool descriptions, decides match.

---

## 13. Exercises

1. **Easy:** Define a `get_time()` tool. Have LLM call it when asked for current time.
2. **Medium:** Build a calculator tool + tip calculator tool. Test routing.
3. **Hard:** Chain 3 tools — search news → summarize → send email (mock email).
4. **Pro:** Implement the tool use loop yourself (without OpenAI SDK abstraction).

---

## 14. Key Takeaways

✅ Tool use = LLM calls your functions when needed
✅ Function calling (OpenAI) = Tool use (Anthropic) — same thing
✅ Loop: LLM → tool call → your code → result → LLM → response
✅ LLM picks tool based on description + intent + params
✅ Multi-step: LLM can chain tools to complete complex tasks
✅ This is what turns LLM into an **agent**
✅ Most important skill: **writing good tool descriptions**

**Next:** [02_openai_function_calling.md](02_openai_function_calling.md) — OpenAI's implementation
