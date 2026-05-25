# Level 4 — Doc 3: Anthropic Claude Tool Use

> **Goal:** Claude ka tool use master karo. OpenAI se subtle differences hain, but powerful features bhi hain (prompt caching, Computer Use).

---

## 1. Claude vs OpenAI — Tool Use Differences

| Aspect | OpenAI | Anthropic |
|---|---|---|
| Term | function calling | tool use |
| Schema format | `{type: "function", function: {...}}` | `{name, description, input_schema}` |
| System prompt | In `messages` | Separate `system` parameter |
| Tool result | `role: "tool"` | `role: "user"` with `tool_result` block |
| Parallel calls | `parallel_tool_calls` flag | Built-in (no flag) |
| Forced tool | `tool_choice={...}` | `tool_choice={"type": "tool", "name": "..."}` |
| Prompt caching | Limited | **Powerful** (90% cost savings) |

---

## 2. Claude Tool Schema Format

```python
tools = [{
    "name": "get_weather",
    "description": "Get current weather for a city",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Name of the city"
            }
        },
        "required": ["city"]
    }
}]
```

**Differences from OpenAI:**
- No `{type: "function", function: {...}}` wrapper
- `input_schema` instead of `parameters`
- Otherwise same JSON Schema structure

---

## 3. Basic Tool Use Call

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in Mumbai?"}]
)
```

### Response structure:
```python
# response.content is a list of blocks
[
    TextBlock(text="I'll check the weather for you."),  # Optional thought
    ToolUseBlock(
        id="toolu_abc123",
        name="get_weather",
        input={"city": "Mumbai"}
    )
]

# Check stop_reason
response.stop_reason  # "tool_use" or "end_turn"
```

---

## 4. The Tool Use Loop (Claude Version)

```python
def run_claude_tool_loop(user_message, tools, tool_functions, max_iter=10):
    messages = [{"role": "user", "content": user_message}]
    
    for _ in range(max_iter):
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )
        
        # Add assistant response
        messages.append({"role": "assistant", "content": response.content})
        
        # End if no tool use
        if response.stop_reason != "tool_use":
            # Get final text
            return next((b.text for b in response.content if b.type == "text"), "")
        
        # Process tool uses
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = tool_functions[block.name](**block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result)
                })
        
        # Send tool results back
        messages.append({"role": "user", "content": tool_results})
```

**Note the differences:**
- Tool results go in **user message** (not "tool" role)
- Content is a **list of blocks**, not just a string
- Check `stop_reason` to know when LLM is done

---

## 5. tool_choice Options (Claude)

```python
# Auto (default)
tool_choice={"type": "auto"}

# Force any tool
tool_choice={"type": "any"}

# Force specific tool
tool_choice={"type": "tool", "name": "get_weather"}

# Disable tools (force text)
# Just omit tools or pass empty list
```

### `disable_parallel_tool_use`:
```python
tool_choice={"type": "auto", "disable_parallel_tool_use": True}
# Forces Claude to call only ONE tool at a time
```

---

## 6. Prompt Caching (HUGE Cost Saver) ⭐

This is **Claude's killer feature** for tool use:

```python
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": LONG_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}  # ← Cache this
    }],
    tools=tools,  # Tools also get cached automatically
    messages=[...]
)
```

**Result:**
- First call: full price ($3/1M input tokens for Sonnet)
- Cached calls (within 5 min): **90% cheaper** ($0.30/1M)

### When caching helps massively:
- Agents with long system prompts (instructions, persona, tool defs)
- RAG with retrieved context
- Multi-turn conversations

### Cache breakpoints:
You can place `cache_control` at 4 points max:
```python
system=[
    {"type": "text", "text": "Section 1", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "Section 2", "cache_control": {"type": "ephemeral"}},
]
```

---

## 7. Computer Use API ⭐⭐

Claude can **control a computer screen** via screenshots + actions:

```python
tools = [{
    "type": "computer_20241022",  # Special Anthropic tool type
    "name": "computer",
    "display_width_px": 1024,
    "display_height_px": 768
}]

# Claude can request:
# - screenshot()
# - click(x, y)
# - type(text)
# - key(key)
# - mouse_move(x, y)
# - scroll(x, y, direction)
```

### Use cases:
- Automate desktop apps
- Web scraping with vision
- UI testing
- Demo recording

### Mini example:
```python
# User: "Open my email and reply to John's latest message"
# Claude:
# 1. screenshot() → sees screen
# 2. click(email_app_icon)
# 3. screenshot() → sees email open
# 4. click(john_email)
# 5. type("Hi John, thanks for...")
# 6. click(send_button)
```

This is **next-level agentic AI**. Most advanced agent capability today.

---

## 8. Extended Thinking + Tool Use (Claude 3.7+)

Claude 3.7+ can do **extended thinking** before using tools:

```python
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=4096,
    thinking={"type": "enabled", "budget_tokens": 8000},  # Internal reasoning budget
    tools=tools,
    messages=[...]
)

# response.content may include:
# - ThinkingBlock(text="Let me think about this...")  ← Internal reasoning
# - TextBlock(text="I'll check the weather...")
# - ToolUseBlock(name="get_weather", input={...})
```

Better for complex multi-step tasks where Claude needs to plan before acting.

---

## 9. Streaming Tool Use

```python
with client.messages.stream(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=[...]
) as stream:
    for event in stream:
        if event.type == "content_block_start":
            if event.content_block.type == "tool_use":
                print(f"Starting tool: {event.content_block.name}")
        elif event.type == "content_block_delta":
            if event.delta.type == "input_json_delta":
                # Tool input being streamed as JSON deltas
                print(event.delta.partial_json, end="")
        elif event.type == "message_stop":
            print("Done")
```

**Use case:** Show user "thinking..." indicator with live tool name updates.

---

## 10. Multi-Tool Parallel (Claude does this naturally)

Claude often calls multiple tools in parallel by default:

```python
# User: "Weather in Mumbai, Delhi, Bangalore?"

# response.content:
[
    TextBlock(text="I'll check all three cities."),
    ToolUseBlock(id="1", name="get_weather", input={"city": "Mumbai"}),
    ToolUseBlock(id="2", name="get_weather", input={"city": "Delhi"}),
    ToolUseBlock(id="3", name="get_weather", input={"city": "Bangalore"}),
]
```

Execute in parallel:
```python
from concurrent.futures import ThreadPoolExecutor

tool_blocks = [b for b in response.content if b.type == "tool_use"]

def run(block):
    return block.id, tool_functions[block.name](**block.input)

with ThreadPoolExecutor() as ex:
    results = dict(ex.map(run, tool_blocks))
```

---

## 11. Model Selection for Tool Use

| Model | When |
|---|---|
| `claude-3-5-haiku` | Cheap, simple tool calls |
| `claude-3-5-sonnet` | **Default for most agents** |
| `claude-3-5-opus` | Most capable, expensive |
| `claude-3-7-sonnet` (with thinking) | Hard reasoning + tool use |

For agent loops, **Sonnet** is the sweet spot — capable + reasonable cost.

---

## 12. Error Handling — Tool Result Failures

When tool fails:
```python
tool_results.append({
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": f"Error: {str(e)}",
    "is_error": True  # ← Important flag
})
```

Claude reads `is_error` and adjusts its behavior (e.g., retry, use different tool, ask user).

---

## 13. When to Use Claude vs OpenAI for Tools

### Use Claude when:
✅ Long system prompts (caching saves big money)
✅ Computer Use needed
✅ Extended thinking for complex tasks
✅ Better at following nuanced instructions
✅ Better at admitting uncertainty (less hallucination)

### Use OpenAI when:
✅ Strict JSON schema mode needed
✅ Larger ecosystem of integrations
✅ o1/o3 reasoning models
✅ Image generation (DALL-E)

---

## 14. Interview Questions

1. **Q: Key difference between OpenAI and Claude tool use?**
   - Schema format, tool result role (Claude: user with tool_result block), prompt caching

2. **Q: Why is prompt caching huge for agents?**
   - Long system prompts + tool definitions get cached → 90% cheaper on repeat calls

3. **Q: What's Computer Use?**
   - Claude controls a computer via screenshots + click/type actions

4. **Q: When to use Claude's extended thinking with tools?**
   - Complex multi-step tasks requiring planning before acting

5. **Q: How does Claude handle parallel tool calls?**
   - By default, requests multiple tool calls in one response. Execute parallel.

---

## 15. Exercises

1. **Easy:** Port your OpenAI tool agent to Claude. Note differences in code.
2. **Medium:** Add prompt caching to long system prompt. Measure cost difference.
3. **Hard:** Build agent with extended thinking enabled. Compare to standard Claude.
4. **Pro:** Try Computer Use API — automate a simple desktop task (open app, take screenshot).

---

## 16. Key Takeaways

✅ Claude `input_schema` (not `parameters` like OpenAI)
✅ Tool results go in **user message** with `tool_result` block
✅ Check `stop_reason` to know when LLM done
✅ **Prompt caching = 90% cost savings** on long system prompts
✅ Computer Use = control desktop apps
✅ Extended thinking for complex pre-tool planning
✅ Parallel tool calls happen naturally

**Next:** [04_tool_descriptions.md](04_tool_descriptions.md) — Writing tool descriptions (THE most important skill)
