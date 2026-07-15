# Modern Topics — Doc 12: OpenAI Responses API (2025 Standard) ⭐

> **Goal:** Responses API = OpenAI ka naya flagship agentic API. Chat Completions ka superset — stateful, built-in tools, aur ek hi call me multi-step agent loop. 2025 se yahi default hai agentic apps ke liye. Interview me "Chat Completions vs Responses API" pucha jata hai.

---

## 1. Kyun aaya? (Chat Completions ki dikkat)

Chat Completions **stateless** hai — har turn pe pura `messages[]` array tumhe dobara bhejna padta hai, tool-calling loop tumhe khud manage karna padta hai (parse tool_calls → run → append → resend). Reasoning models ke saath reasoning tokens turns ke beech lost ho jate the.

**Responses API** teen problems solve karta hai:
1. **Server-side state** — `previous_response_id` do, OpenAI conversation history khud rakhta hai. Poora array resend nahi.
2. **Built-in (hosted) tools** — `web_search`, `file_search`, `code_interpreter`, `computer_use` — OpenAI apne infra pe chalata hai, tumhe implement nahi karna.
3. **Ek call = multi-step** — model tool call kare → OpenAI execute kare → model continue kare, sab ek `responses.create()` ke andar. Agent loop built-in.

> Chat Completions **deprecate nahi** hua — abhi bhi supported hai. Par naye agentic features (hosted tools, reasoning persistence) sirf Responses API me aate hain.

---

## 2. Basic call — `input` aur `output_text`

```python
# pip install openai
from openai import OpenAI
client = OpenAI()

resp = client.responses.create(
    model="gpt-4.1",
    input="Explain idempotency in REST APIs in 2 lines.",
)

print(resp.output_text)   # convenience: saara text ek string me
# resp.output -> list of output items (messages, tool_calls, reasoning, etc.)
```

Farq Chat Completions se:
- `messages=[{role, content}]` → ab `input=` (string ya structured list dono chalte hain)
- `resp.choices[0].message.content` → ab `resp.output_text` (helper) ya `resp.output[]` (full items)

Structured input (multi-turn / multimodal):
```python
resp = client.responses.create(
    model="gpt-4.1",
    input=[
        {"role": "system", "content": "You are a terse assistant."},
        {"role": "user", "content": [
            {"type": "input_text", "text": "Is image me kya hai?"},
            {"type": "input_image", "image_url": "https://example.com/x.png"},
        ]},
    ],
)
```

---

## 3. Stateful conversation — `previous_response_id`

Yahi Responses API ka killer feature hai. History dobara bhejne ki zarurat nahi:

```python
r1 = client.responses.create(model="gpt-4.1", input="Mera naam Ashish hai.")

r2 = client.responses.create(
    model="gpt-4.1",
    input="Mera naam kya hai?",
    previous_response_id=r1.id,      # <-- server-side chain
)
print(r2.output_text)   # "Ashish"
```

- Chaining se reasoning models ke **reasoning tokens preserve** rehte hain across turns (Chat Completions me lost).
- Default me OpenAI response 30 din retain karta hai. Zero-retention chahiye to `store=False` (phir khud history manage karo).

---

## 4. Built-in (hosted) tools

Ye tools OpenAI ke server pe chalte hain — tumhe koi function likhna/execute nahi karna:

```python
resp = client.responses.create(
    model="gpt-4.1",
    input="Aaj AI me sabse badi news kya hai? Source do.",
    tools=[{"type": "web_search"}],       # hosted: OpenAI khud search karega
)
print(resp.output_text)
```

Common hosted tools:
| Tool | Kaam |
|------|------|
| `web_search` | Live web se retrieve + cite |
| `file_search` | Tumhare uploaded vector store pe RAG (managed) |
| `code_interpreter` | Sandbox me Python chalaye (data/plots/math) |
| `computer_use` | Screenshot dekh ke GUI control (see [02_computer_use.md](02_computer_use.md)) |
| `image_generation` | Image banaye |

---

## 5. Custom function calling (tumhare apne tools)

Hosted tools ke alawa tum apne functions bhi de sakte ho. Loop Chat Completions se simple hai:

```python
import json

tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Ek city ka current weather",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}]

resp = client.responses.create(
    model="gpt-4.1",
    input="Mumbai ka mausam kaisa hai?",
    tools=tools,
)

# Model function call kar raha hai?
for item in resp.output:
    if item.type == "function_call":
        args = json.loads(item.arguments)
        result = {"temp_c": 32, "sky": "humid"}   # <- tumhara real function
        # result wapas bhejo, previous_response_id se chain karke:
        final = client.responses.create(
            model="gpt-4.1",
            previous_response_id=resp.id,
            input=[{
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps(result),
            }],
        )
        print(final.output_text)
```

Note: `function_call_output` naya item-type hai (Chat Completions ka `role: "tool"` message iski jagah).

---

## 6. Streaming (typed events)

Chat Completions me raw delta chunks aate the; Responses API **semantic typed events** deta hai — parse karna asaan:

```python
stream = client.responses.create(
    model="gpt-4.1",
    input="Ek haiku likho.",
    stream=True,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.completed":
        print("\n[done]")
```
Aur bhi events: `response.created`, `response.output_item.added`, `response.function_call_arguments.delta`, `response.error`. (Voice/live streaming ke liye Realtime API alag hai — see [01_voice_agents.md](01_voice_agents.md).)

---

## 7. Structured Outputs (JSON schema guarantee)

Responses API me bhi `text.format` se strict schema milta hai (Pydantic ke saath):

```python
from pydantic import BaseModel

class Ticket(BaseModel):
    priority: str
    summary: str

resp = client.responses.parse(
    model="gpt-4.1",
    input="Server down hai prod me, sab customers affected.",
    text_format=Ticket,
)
print(resp.output_parsed)   # Ticket(priority='high', summary='...')
```
(Deep dive: [Level2/07_structured_outputs.md](../Level2_Prompt_Engineering/07_structured_outputs.md).)

---

## 8. Chat Completions vs Responses API — interview table

| Cheez | Chat Completions | Responses API |
|-------|------------------|---------------|
| State | Stateless (full array resend) | Stateful (`previous_response_id`) |
| Entry field | `messages=[]` | `input=` (string ya items) |
| Output | `choices[0].message.content` | `output_text` / `output[]` items |
| Tool loop | Manual parse + resend | Built-in; hosted tools available |
| Hosted tools | ❌ | ✅ web/file/code/computer |
| Reasoning persist | ❌ (lost between turns) | ✅ (chained) |
| Streaming | Raw delta chunks | Typed semantic events |
| Status | Supported (legacy-ish) | **Default for new agentic apps** |

---

## 9. Common pitfalls

- `resp.output_text` **empty** ho sakta hai jab output pure tool_calls ho — hamesha `resp.output[]` items check karo, blindly text mat maano.
- `store=False` (zero-retention) me `previous_response_id` chaining **kaam nahi karega** — dono ek saath nahi.
- Hosted `web_search`/`code_interpreter` ke apne **extra charges** hain (base tokens ke upar) — cost estimate me include karo.
- `function_call_output` bhejte waqt sahi `call_id` match karna zaroori — warna model confuse.

---

## 10. Key Takeaways

- Responses API = 2025 ka **default agentic API** for OpenAI: stateful + hosted tools + built-in agent loop.
- `previous_response_id` se server-side history — reasoning tokens preserve, poora array resend nahi.
- Hosted tools (web_search/file_search/code_interpreter/computer_use) — no infra to build.
- Chat Completions abhi bhi valid, par naye agentic features yahin aate hain.
- Anthropic ka counterpart = Messages API + tool_use ([Level4](../Level4_Tool_Use_Function_Calling/)); Google ka = Gemini API + [13_gemini_live_api.md](13_gemini_live_api.md).

## Related Topics
- [11_openai_responses cross] Structured Outputs → [Level2/07](../Level2_Prompt_Engineering/07_structured_outputs.md)
- Tool use foundations → [Level4_Tool_Use_Function_Calling](../Level4_Tool_Use_Function_Calling/)
- Computer Use hosted tool → [02_computer_use.md](02_computer_use.md)
- Voice/Realtime streaming → [01_voice_agents.md](01_voice_agents.md)
- Gemini Live (Google's bidi API) → [13_gemini_live_api.md](13_gemini_live_api.md)
