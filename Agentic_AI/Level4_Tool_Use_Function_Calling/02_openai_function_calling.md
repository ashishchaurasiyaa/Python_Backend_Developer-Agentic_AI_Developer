# Level 4 — Doc 2: OpenAI Function Calling — Complete

> **Goal:** OpenAI's function calling API ke saare features master karo. Parallel calls, strict mode, tool_choice, parallel disable.

---

## 1. The Anatomy

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    tools=[...],                # Tool schemas
    tool_choice="auto",         # When to use tools
    parallel_tool_calls=True,   # Allow N tools at once
)
```

---

## 2. Tool Schema Format (JSON Schema)

```python
{
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Send an email to a recipient",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CC recipients (optional)"
                }
            },
            "required": ["to", "subject", "body"]
        }
    }
}
```

### Supported types:
- `string` — text
- `integer`, `number` — numbers
- `boolean` — true/false
- `array` — list (with `items`)
- `object` — nested object

> NOTE: `enum` aur `null` alag "type" NAHI hain. `enum` ek **constraint** hai jo kisi typed field pe lagti
> hai (e.g. `"type":"string", "enum":[...]`); nullable ke liye **type union** use hota hai: `"type":["string","null"]`.

### Enum example:
```python
"priority": {
    "type": "string",
    "enum": ["low", "medium", "high", "urgent"],
    "description": "Email priority"
}
```

---

## 3. tool_choice — Control Tool Use

```python
# "auto" (default): LLM decides
tool_choice="auto"

# "none": Force LLM to NOT use tools, just text
tool_choice="none"

# "required": Force LLM to use SOME tool (LLM picks which)
tool_choice="required"

# Specific tool: Force LLM to use this exact one
tool_choice={"type": "function", "function": {"name": "get_weather"}}
```

### When to use each:

| tool_choice | Use Case |
|---|---|
| `"auto"` | General — LLM decides |
| `"none"` | Force text response (e.g., summarization step) |
| `"required"` | Make sure LLM uses at least one tool |
| Specific tool | Force a specific tool (e.g., classify must use classifier) |

---

## 4. Strict Mode (Guaranteed Schema)

Standard mode: LLM **mostly** follows schema, sometimes adds extra fields.
Strict mode: **Guaranteed** schema match.

```python
{
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "...",
        "strict": True,  # ← Strict mode
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": ["to", "subject", "body"],
            "additionalProperties": False  # ← Required for strict
        }
    }
}
```

**Requirements for strict mode:**
- All fields in `properties` must be in `required`
- `additionalProperties: false`
- Use newer model (`gpt-4o-2024-08-06+`)

**Trade-off:** Slightly slower (first call), but guaranteed compliance.

---

## 5. Parallel Tool Calls (Big Deal)

LLM can request **multiple tools at once** in a single response:

```python
# User: "What's the weather in Mumbai, Delhi, and Bangalore?"

# LLM responds with 3 tool calls in ONE message:
[
    {"name": "get_weather", "arguments": {"city": "Mumbai"}},
    {"name": "get_weather", "arguments": {"city": "Delhi"}},
    {"name": "get_weather", "arguments": {"city": "Bangalore"}}
]
```

**Execute in parallel:**
```python
from concurrent.futures import ThreadPoolExecutor

def execute_tool_calls(tool_calls):
    def run_one(tc):
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        return tc.id, TOOL_FUNCTIONS[name](**args)
    
    with ThreadPoolExecutor() as ex:
        return dict(ex.map(run_one, tool_calls))
```

**Saves time:** 3 sequential tool calls × 500ms = 1.5s vs parallel = 500ms.

### Disable parallel:
```python
parallel_tool_calls=False
# Forces LLM to call tools sequentially (one per message)
```

---

## 6. Full Production Loop

```python
import json
from openai import OpenAI

client = OpenAI()

def run_agent(user_message: str, tools: list, tool_functions: dict, max_iter: int = 10) -> str:
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": user_message}
    ]
    
    for i in range(max_iter):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        msg = response.choices[0].message
        
        if not msg.tool_calls:
            return msg.content  # Final answer
        
        # Add LLM's tool request
        messages.append(msg.model_dump(exclude_none=True))
        
        # Execute each tool call
        for tc in msg.tool_calls:
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments)
            
            try:
                result = tool_functions[func_name](**func_args)
            except Exception as e:
                result = {"error": str(e)}
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })
    
    return "[Max iterations reached]"
```

---

## 7. Auto-Schema Generation from Python Functions

Don't write schemas by hand — generate from function signatures:

```python
from pydantic import BaseModel, Field
from typing import get_type_hints
import inspect

def python_func_to_schema(func) -> dict:
    """Generate OpenAI tool schema from Python function."""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    
    properties = {}
    required = []
    for name, param in sig.parameters.items():
        param_type = hints.get(name, str)
        type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
        properties[name] = {"type": type_map.get(param_type, "string")}
        if param.default is param.empty:
            required.append(name)
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }
```

**Better:** Pydantic se define karo (`model_json_schema()`), ya `instructor` / OpenAI ka `pydantic_function_tool` use karo:

```python
from pydantic import BaseModel, Field

class GetWeatherInput(BaseModel):
    city: str = Field(description="City name")

schema = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": GetWeatherInput.model_json_schema()
    }
}
```

---

## 8. Common OpenAI Function Calling Patterns

### Pattern A: Tool + Final Answer
```python
# 1. User asks → LLM calls tool → tool result → LLM gives final answer
# 2 LLM calls total
```

### Pattern B: Multi-Step
```python
# 1. User asks → LLM calls tool 1 → result
# 2. LLM analyzes → calls tool 2 → result  
# 3. LLM calls tool 3 → result
# 4. LLM gives final answer
# Many round-trips
```

### Pattern C: Parallel Then Synthesize
```python
# 1. User asks → LLM requests 5 tools at once → execute parallel
# 2. All results back → LLM synthesizes single answer
# Fast — 2 LLM calls but 5 parallel tool executions
```

---

## 9. Cost Considerations

Each tool call adds tokens:
- Tool schemas (in every request)
- Tool call output (LLM-generated JSON)
- Tool results (sent back to LLM)

**Optimization tips:**
1. Pass only relevant tools (not all 50)
2. Keep tool descriptions concise but clear
3. Cache tool results when possible
4. Use Anthropic prompt caching (covered in Doc 3)

---

## 10. Common Errors & Fixes

### Error: Tool not found
```python
# LLM hallucinates a tool name
# Fix: validate against TOOL_FUNCTIONS, return error to LLM
if func_name not in TOOL_FUNCTIONS:
    result = {"error": f"Unknown tool: {func_name}. Available: {list(TOOL_FUNCTIONS.keys())}"}
```

### Error: Wrong arguments
```python
# LLM passes wrong types
# Fix: use Pydantic to validate
try:
    args = GetWeatherInput(**parsed_args)
    result = get_weather(**args.model_dump())
except ValidationError as e:
    result = {"error": str(e)}
```

### Error: Infinite loop
```python
# LLM keeps calling tools, never gives final answer
# Fix: max_iterations + log warning
if iteration >= MAX_ITER:
    return "Unable to complete after multiple attempts"
```

### Error: Token limit hit
Long tool chains can blow context window.
**Fix:** Summarize tool results before passing back to LLM.

---

## 11. Interview Questions

1. **Q: Difference between `tool_choice="auto"` vs `"required"`?**
   - `auto`: LLM decides. `required`: LLM must use some tool.

2. **Q: What's strict mode?**
   - Guarantees LLM output matches schema exactly. Needs `additionalProperties: false`.

3. **Q: Why use parallel tool calls?**
   - Latency. 5 tools in parallel = 1 tool's time, not 5x.

4. **Q: How do you prevent infinite loops?**
   - Max iterations, log warnings, return graceful fallback.

5. **Q: How does LLM "see" your tool?**
   - Via the schema (name + description + params). Description quality matters most.

---

## 12. Exercises

1. **Easy:** Convert 3 of your Python functions to OpenAI tool schemas.
2. **Medium:** Implement strict mode for one tool. Test that LLM never adds extra fields.
3. **Hard:** Build parallel tool execution with timeout per tool + fallback.
4. **Pro:** Build auto-schema generator from Python functions (using `inspect` + Pydantic).

---

## 13. Key Takeaways

✅ OpenAI tool schema = JSON Schema format
✅ `tool_choice`: auto / none / required / specific tool
✅ Strict mode (`strict: True`) = guaranteed schema compliance
✅ Parallel tool calls = N tools in one LLM response (faster)
✅ Always have max_iterations to prevent infinite loops
✅ Validate tool args with Pydantic
✅ Auto-generate schemas from Python functions (less manual work)

**Next:** [03_claude_tool_use.md](03_claude_tool_use.md) — Anthropic's implementation
